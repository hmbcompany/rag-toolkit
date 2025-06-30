"""
Metering service for RAG Toolkit.

Implements F-4.3: Cron job every 1 hour to aggregate trace.count, seat.count into usage table.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any
from uuid import UUID

from sqlalchemy.orm import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from .models import Tenant, TraceRecord, TenantUser, UsageRecord
from .crud import TenantCRUD, UsageCRUD
from .stripe_service import StripeService, TenantBillingService


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MeteringService:
    """Service for aggregating and tracking tenant usage metrics."""
    
    def __init__(self, database_url: str):
        """Initialize the metering service with database connection."""
        self.engine = create_engine(database_url)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
    
    def get_db(self) -> Session:
        """Get database session."""
        return self.SessionLocal()
    
    def calculate_hourly_usage(self, tenant_id: UUID, period_start: datetime, 
                              period_end: datetime) -> Dict[str, Any]:
        """Calculate usage metrics for a specific hour period."""
        db = self.get_db()
        try:
            # Count traces in this period
            trace_count = db.query(TraceRecord).filter(
                TraceRecord.tenant_id == tenant_id,
                TraceRecord.timestamp >= period_start,
                TraceRecord.timestamp < period_end
            ).count()
            
            # Count API requests (using traces as proxy for now)
            api_requests = trace_count
            
            # Count active seats (users who created traces or logged in during period)
            active_user_ids = set()
            
            # Users who created traces
            trace_users = db.query(TraceRecord.trace_metadata).filter(
                TraceRecord.tenant_id == tenant_id,
                TraceRecord.timestamp >= period_start,
                TraceRecord.timestamp < period_end,
                TraceRecord.trace_metadata.isnot(None)
            ).all()
            
            for trace in trace_users:
                if trace.trace_metadata and 'user_id' in trace.trace_metadata:
                    active_user_ids.add(trace.trace_metadata['user_id'])
            
            # Users who logged in during period
            logged_in_users = db.query(TenantUser).filter(
                TenantUser.tenant_id == tenant_id,
                TenantUser.last_login >= period_start,
                TenantUser.last_login < period_end
            ).all()
            
            for user in logged_in_users:
                active_user_ids.add(str(user.id))
            
            # Default to at least 1 seat if there's any activity
            seat_count = max(len(active_user_ids), 1) if trace_count > 0 else 0
            
            # Calculate token usage
            token_stats = db.query(
                db.func.coalesce(db.func.sum(TraceRecord.tokens_in), 0).label('total_tokens_in'),
                db.func.coalesce(db.func.sum(TraceRecord.tokens_out), 0).label('total_tokens_out')
            ).filter(
                TraceRecord.tenant_id == tenant_id,
                TraceRecord.timestamp >= period_start,
                TraceRecord.timestamp < period_end
            ).first()
            
            # Estimate storage (simple calculation)
            # Rough estimate: 1KB per trace on average
            storage_mb = (trace_count * 1.0) / 1024  # Convert KB to MB
            
            return {
                "trace_count": trace_count,
                "seat_count": seat_count,
                "api_requests": api_requests,
                "storage_mb": round(storage_mb, 2),
                "total_tokens_in": int(token_stats.total_tokens_in or 0),
                "total_tokens_out": int(token_stats.total_tokens_out or 0)
            }
            
        finally:
            db.close()
    
    def aggregate_tenant_usage(self, tenant_id: UUID, period_start: datetime, 
                              period_end: datetime) -> UsageRecord:
        """Aggregate usage for a tenant for a specific period."""
        logger.info(f"Aggregating usage for tenant {tenant_id} from {period_start} to {period_end}")
        
        db = self.get_db()
        try:
            # Check if usage record already exists for this period
            existing_record = UsageCRUD.get_usage_for_period(
                db, tenant_id, period_start, period_end
            )
            
            if existing_record:
                logger.info(f"Usage record already exists for tenant {tenant_id}, updating...")
                # Update existing record
                usage_data = self.calculate_hourly_usage(tenant_id, period_start, period_end)
                
                for key, value in usage_data.items():
                    setattr(existing_record, key, value)
                
                existing_record.updated_at = datetime.utcnow()
                db.commit()
                db.refresh(existing_record)
                return existing_record
            else:
                # Create new usage record
                usage_data = self.calculate_hourly_usage(tenant_id, period_start, period_end)
                
                usage_record = UsageCRUD.create_usage_record(
                    db=db,
                    tenant_id=tenant_id,
                    period_start=period_start,
                    period_end=period_end,
                    **usage_data
                )
                
                logger.info(f"Created usage record for tenant {tenant_id}: {usage_data}")
                return usage_record
                
        finally:
            db.close()
    
    def run_hourly_aggregation(self) -> Dict[str, Any]:
        """Run the hourly usage aggregation for all tenants."""
        logger.info("Starting hourly usage aggregation...")
        
        # Define the period (previous hour)
        now = datetime.utcnow()
        period_end = now.replace(minute=0, second=0, microsecond=0)
        period_start = period_end - timedelta(hours=1)
        
        db = self.get_db()
        try:
            # Get all active tenants
            tenants = TenantCRUD.list_tenants(db, limit=1000)  # Assume max 1000 tenants for now
            
            results = {
                "period_start": period_start.isoformat(),
                "period_end": period_end.isoformat(),
                "tenants_processed": 0,
                "total_traces": 0,
                "total_seats": 0,
                "errors": []
            }
            
            for tenant in tenants:
                try:
                    usage_record = self.aggregate_tenant_usage(
                        tenant.id, period_start, period_end
                    )
                    
                    results["tenants_processed"] += 1
                    results["total_traces"] += usage_record.trace_count
                    results["total_seats"] += usage_record.seat_count
                    
                except Exception as e:
                    logger.error(f"Failed to aggregate usage for tenant {tenant.id}: {e}")
                    results["errors"].append({
                        "tenant_id": str(tenant.id),
                        "error": str(e)
                    })
            
            logger.info(f"Hourly aggregation complete. Processed {results['tenants_processed']} tenants")
            return results
            
        finally:
            db.close()
    
    def run_daily_cleanup(self) -> Dict[str, Any]:
        """Run daily cleanup of old usage records and data."""
        logger.info("Starting daily cleanup...")
        
        db = self.get_db()
        try:
            # Clean up usage records older than 2 years
            cutoff_date = datetime.utcnow() - timedelta(days=730)
            
            old_records = db.query(UsageRecord).filter(
                UsageRecord.period_start < cutoff_date
            ).count()
            
            db.query(UsageRecord).filter(
                UsageRecord.period_start < cutoff_date
            ).delete()
            
            db.commit()
            
            logger.info(f"Cleaned up {old_records} old usage records")
            
            return {
                "cleanup_date": cutoff_date.isoformat(),
                "records_deleted": old_records
            }
            
        finally:
            db.close()
    
    def get_tenant_usage_summary(self, tenant_id: UUID, days: int = 30) -> Dict[str, Any]:
        """Get usage summary for a tenant over the last N days."""
        db = self.get_db()
        try:
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=days)
            
            usage_records = db.query(UsageRecord).filter(
                UsageRecord.tenant_id == tenant_id,
                UsageRecord.period_start >= start_date
            ).order_by(UsageRecord.period_start).all()
            
            if not usage_records:
                return {
                    "tenant_id": str(tenant_id),
                    "period_days": days,
                    "total_traces": 0,
                    "total_seats": 0,
                    "total_api_requests": 0,
                    "total_storage_mb": 0,
                    "daily_averages": {
                        "traces_per_day": 0,
                        "seats_per_day": 0,
                        "requests_per_day": 0
                    }
                }
            
            # Aggregate totals
            total_traces = sum(r.trace_count for r in usage_records)
            total_seats = sum(r.seat_count for r in usage_records)
            total_requests = sum(r.api_requests for r in usage_records)
            total_storage = sum(r.storage_mb for r in usage_records)
            total_tokens_in = sum(r.total_tokens_in for r in usage_records)
            total_tokens_out = sum(r.total_tokens_out for r in usage_records)
            
            # Calculate daily averages
            hours_covered = len(usage_records)
            days_covered = max(hours_covered / 24, 1)  # At least 1 day
            
            return {
                "tenant_id": str(tenant_id),
                "period_days": days,
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "total_traces": total_traces,
                "total_seats": total_seats,
                "total_api_requests": total_requests,
                "total_storage_mb": round(total_storage, 2),
                "total_tokens_in": total_tokens_in,
                "total_tokens_out": total_tokens_out,
                "daily_averages": {
                    "traces_per_day": round(total_traces / days_covered, 1),
                    "seats_per_day": round(total_seats / days_covered, 1),
                    "requests_per_day": round(total_requests / days_covered, 1),
                    "storage_mb_per_day": round(total_storage / days_covered, 2)
                },
                "hours_of_data": hours_covered
            }
            
        finally:
            db.close()


class MeteringScheduler:
    """Scheduler for running metering tasks."""
    
    def __init__(self, database_url: str):
        """Initialize the scheduler."""
        self.metering_service = MeteringService(database_url)
        self.running = False
    
    async def start_hourly_scheduler(self):
        """Start the hourly aggregation scheduler."""
        logger.info("Starting hourly metering scheduler...")
        self.running = True
        
        while self.running:
            try:
                # Calculate time until next hour
                now = datetime.utcnow()
                next_hour = (now + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
                sleep_seconds = (next_hour - now).total_seconds()
                
                logger.info(f"Sleeping for {sleep_seconds:.0f} seconds until next hour...")
                await asyncio.sleep(sleep_seconds)
                
                if self.running:
                    # Run the hourly aggregation
                    try:
                        results = self.metering_service.run_hourly_aggregation()
                        logger.info(f"Hourly aggregation results: {results}")
                    except Exception as e:
                        logger.error(f"Error in hourly aggregation: {e}")
                
            except asyncio.CancelledError:
                logger.info("Hourly scheduler cancelled")
                break
            except Exception as e:
                logger.error(f"Error in hourly scheduler: {e}")
                await asyncio.sleep(60)  # Wait 1 minute before retrying
    
    async def start_daily_scheduler(self):
        """Start the daily cleanup scheduler."""
        logger.info("Starting daily cleanup scheduler...")
        
        while self.running:
            try:
                # Calculate time until next midnight UTC
                now = datetime.utcnow()
                next_midnight = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
                sleep_seconds = (next_midnight - now).total_seconds()
                
                logger.info(f"Sleeping for {sleep_seconds:.0f} seconds until midnight...")
                await asyncio.sleep(sleep_seconds)
                
                if self.running:
                    # Run daily cleanup
                    try:
                        results = self.metering_service.run_daily_cleanup()
                        logger.info(f"Daily cleanup results: {results}")
                    except Exception as e:
                        logger.error(f"Error in daily cleanup: {e}")
                
            except asyncio.CancelledError:
                logger.info("Daily scheduler cancelled")
                break
            except Exception as e:
                logger.error(f"Error in daily scheduler: {e}")
                await asyncio.sleep(3600)  # Wait 1 hour before retrying
    
    async def run_schedulers(self):
        """Run both hourly and daily schedulers concurrently."""
        logger.info("Starting metering schedulers...")
        
        tasks = [
            asyncio.create_task(self.start_hourly_scheduler()),
            asyncio.create_task(self.start_daily_scheduler())
        ]
        
        try:
            await asyncio.gather(*tasks)
        except asyncio.CancelledError:
            logger.info("Schedulers cancelled")
            for task in tasks:
                task.cancel()
        finally:
            self.running = False
    
    def stop(self):
        """Stop the scheduler."""
        logger.info("Stopping metering schedulers...")
        self.running = False


# Convenience function for manual testing
def run_manual_aggregation(database_url: str, tenant_id: str = None):
    """Run manual aggregation for testing purposes."""
    service = MeteringService(database_url)
    
    if tenant_id:
        # Run for specific tenant
        now = datetime.utcnow()
        period_end = now.replace(minute=0, second=0, microsecond=0)
        period_start = period_end - timedelta(hours=1)
        
        usage_record = service.aggregate_tenant_usage(
            UUID(tenant_id), period_start, period_end
        )
        print(f"Manual aggregation complete for tenant {tenant_id}")
        print(f"Usage: {usage_record.trace_count} traces, {usage_record.seat_count} seats")
    else:
        # Run for all tenants
        results = service.run_hourly_aggregation()
        print(f"Manual aggregation complete: {results}")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python metering_service.py <database_url> [tenant_id]")
        sys.exit(1)
    
    database_url = sys.argv[1]
    tenant_id = sys.argv[2] if len(sys.argv) > 2 else None
    
    run_manual_aggregation(database_url, tenant_id) 