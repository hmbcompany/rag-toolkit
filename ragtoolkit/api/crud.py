"""CRUD operations for RAG Toolkit database."""

import secrets
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from uuid import UUID

from sqlalchemy.orm import Session
from sqlalchemy import func, desc, and_, or_

from .models import (
    TraceRecord, EvaluationRecord, TraceCreate, Tenant, TenantUser, UsageRecord,
    TenantCreate, TenantUserCreate
)


class TenantCRUD:
    """CRUD operations for tenants."""
    
    @staticmethod
    def create_tenant(db: Session, tenant_data: TenantCreate) -> Tenant:
        """Create a new tenant."""
        db_tenant = Tenant(
            slug=tenant_data.slug,
            name=tenant_data.name
        )
        
        db.add(db_tenant)
        db.commit()
        db.refresh(db_tenant)
        
        # Create admin user for tenant
        admin_api_key = f"rtk_{secrets.token_urlsafe(32)}"
        admin_user = TenantUser(
            tenant_id=db_tenant.id,
            email=tenant_data.admin_email,
            role="admin",
            api_key=admin_api_key
        )
        
        db.add(admin_user)
        db.commit()
        
        return db_tenant
    
    @staticmethod
    def get_tenant(db: Session, tenant_id: UUID) -> Optional[Tenant]:
        """Get tenant by ID."""
        return db.query(Tenant).filter(Tenant.id == tenant_id).first()
    
    @staticmethod
    def get_tenant_by_slug(db: Session, slug: str) -> Optional[Tenant]:
        """Get tenant by slug."""
        return db.query(Tenant).filter(Tenant.slug == slug).first()
    
    @staticmethod
    def list_tenants(db: Session, skip: int = 0, limit: int = 100) -> List[Tenant]:
        """List all tenants."""
        return db.query(Tenant).order_by(Tenant.created_at).offset(skip).limit(limit).all()
    
    @staticmethod
    def update_tenant(db: Session, tenant_id: UUID, **updates) -> Optional[Tenant]:
        """Update tenant."""
        tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
        if not tenant:
            return None
            
        for key, value in updates.items():
            if hasattr(tenant, key) and value is not None:
                setattr(tenant, key, value)
        
        tenant.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(tenant)
        return tenant


class TenantUserCRUD:
    """CRUD operations for tenant users."""
    
    @staticmethod
    def create_user(db: Session, tenant_id: UUID, user_data: TenantUserCreate) -> TenantUser:
        """Create a new tenant user."""
        api_key = f"rtk_{secrets.token_urlsafe(32)}"
        
        db_user = TenantUser(
            tenant_id=tenant_id,
            email=user_data.email,
            role=user_data.role,
            api_key=api_key
        )
        
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
        return db_user
    
    @staticmethod
    def get_user_by_api_key(db: Session, api_key: str) -> Optional[TenantUser]:
        """Get user by API key."""
        return db.query(TenantUser).filter(TenantUser.api_key == api_key).first()
    
    @staticmethod
    def get_user(db: Session, user_id: UUID) -> Optional[TenantUser]:
        """Get user by ID."""
        return db.query(TenantUser).filter(TenantUser.id == user_id).first()
    
    @staticmethod
    def list_tenant_users(db: Session, tenant_id: UUID) -> List[TenantUser]:
        """List all users for a tenant."""
        return db.query(TenantUser).filter(TenantUser.tenant_id == tenant_id).all()
    
    @staticmethod
    def update_user_login(db: Session, user_id: UUID) -> Optional[TenantUser]:
        """Update user's last login timestamp."""
        user = db.query(TenantUser).filter(TenantUser.id == user_id).first()
        if user:
            user.last_login = datetime.utcnow()
            db.commit()
            db.refresh(user)
        return user


class UsageCRUD:
    """CRUD operations for usage tracking."""
    
    @staticmethod
    def create_usage_record(db: Session, tenant_id: UUID, period_start: datetime, 
                           period_end: datetime, **metrics) -> UsageRecord:
        """Create a new usage record."""
        db_usage = UsageRecord(
            tenant_id=tenant_id,
            period_start=period_start,
            period_end=period_end,
            **metrics
        )
        
        db.add(db_usage)
        db.commit()
        db.refresh(db_usage)
        return db_usage
    
    @staticmethod
    def get_usage_for_period(db: Session, tenant_id: UUID, 
                            start: datetime, end: datetime) -> Optional[UsageRecord]:
        """Get usage record for a specific period."""
        return db.query(UsageRecord).filter(
            and_(
                UsageRecord.tenant_id == tenant_id,
                UsageRecord.period_start >= start,
                UsageRecord.period_end <= end
            )
        ).first()
    
    @staticmethod
    def get_tenant_usage_history(db: Session, tenant_id: UUID, 
                                limit: int = 12) -> List[UsageRecord]:
        """Get usage history for a tenant."""
        return db.query(UsageRecord).filter(
            UsageRecord.tenant_id == tenant_id
        ).order_by(desc(UsageRecord.period_start)).limit(limit).all()
    
    @staticmethod
    def calculate_current_usage(db: Session, tenant_id: UUID) -> Dict[str, Any]:
        """Calculate current period usage for a tenant."""
        now = datetime.utcnow()
        period_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        # Count traces this period
        trace_count = db.query(TraceRecord).filter(
            and_(
                TraceRecord.tenant_id == tenant_id,
                TraceRecord.timestamp >= period_start
            )
        ).count()
        
        # Count active seats (users who logged in this period)
        seat_count = db.query(TenantUser).filter(
            and_(
                TenantUser.tenant_id == tenant_id,
                TenantUser.is_active == True,
                or_(
                    TenantUser.last_login >= period_start,
                    TenantUser.created_at >= period_start
                )
            )
        ).count()
        
        # Sum tokens
        token_stats = db.query(
            func.sum(TraceRecord.tokens_in).label('total_tokens_in'),
            func.sum(TraceRecord.tokens_out).label('total_tokens_out')
        ).filter(
            and_(
                TraceRecord.tenant_id == tenant_id,
                TraceRecord.timestamp >= period_start
            )
        ).first()
        
        return {
            "period_start": period_start,
            "period_end": now,
            "trace_count": trace_count,
            "seat_count": seat_count,
            "total_tokens_in": token_stats.total_tokens_in or 0,
            "total_tokens_out": token_stats.total_tokens_out or 0
        }


class TraceCRUD:
    """CRUD operations for traces."""
    
    @staticmethod
    def create_trace(db: Session, tenant_id: UUID, trace_data: TraceCreate) -> TraceRecord:
        """Create a new trace record."""
        db_trace = TraceRecord(
            tenant_id=tenant_id,
            trace_id=trace_data.trace_id,
            timestamp=datetime.fromtimestamp(trace_data.timestamp),
            user_input=trace_data.user_input,
            retrieved_chunks=trace_data.retrieved_chunks,
            retrieval_scores=trace_data.retrieval_scores,
            prompts=trace_data.prompts,
            model_output=trace_data.model_output,
            model_name=trace_data.model_name,
            response_latency_ms=trace_data.response_latency_ms,
            tokens_in=trace_data.tokens_in,
            tokens_out=trace_data.tokens_out,
            trace_metadata=trace_data.trace_metadata,
            error=trace_data.error
        )
        
        db.add(db_trace)
        db.commit()
        db.refresh(db_trace)
        return db_trace
    
    @staticmethod
    def get_trace(db: Session, tenant_id: UUID, trace_id: str) -> Optional[TraceRecord]:
        """Get a trace by trace_id for a specific tenant."""
        return db.query(TraceRecord).filter(
            and_(
                TraceRecord.tenant_id == tenant_id,
                TraceRecord.trace_id == trace_id
            )
        ).first()
    
    @staticmethod
    def get_trace_by_uuid(db: Session, tenant_id: UUID, trace_uuid: UUID) -> Optional[TraceRecord]:
        """Get a trace by UUID for a specific tenant."""
        return db.query(TraceRecord).filter(
            and_(
                TraceRecord.tenant_id == tenant_id,
                TraceRecord.id == trace_uuid
            )
        ).first()
    
    @staticmethod
    def list_traces(db: Session, 
                   tenant_id: UUID,
                   skip: int = 0, 
                   limit: int = 100,
                   model_name: Optional[str] = None,
                   traffic_light: Optional[str] = None,
                   start_date: Optional[datetime] = None,
                   end_date: Optional[datetime] = None,
                   has_error: Optional[bool] = None) -> List[TraceRecord]:
        """List traces for a tenant with optional filtering."""
        query = db.query(TraceRecord).filter(TraceRecord.tenant_id == tenant_id)
        
        # Apply filters
        if model_name:
            query = query.filter(TraceRecord.model_name == model_name)
        if traffic_light:
            query = query.filter(TraceRecord.traffic_light == traffic_light)
        if start_date:
            query = query.filter(TraceRecord.timestamp >= start_date)
        if end_date:
            query = query.filter(TraceRecord.timestamp <= end_date)
        if has_error is not None:
            if has_error:
                query = query.filter(TraceRecord.error.isnot(None))
            else:
                query = query.filter(TraceRecord.error.is_(None))
        
        # Order by timestamp descending (newest first)
        query = query.order_by(desc(TraceRecord.timestamp))
        
        return query.offset(skip).limit(limit).all()
    
    @staticmethod
    def count_traces(db: Session,
                    tenant_id: UUID,
                    model_name: Optional[str] = None,
                    traffic_light: Optional[str] = None,
                    start_date: Optional[datetime] = None,
                    end_date: Optional[datetime] = None,
                    has_error: Optional[bool] = None) -> int:
        """Count traces for a tenant with optional filtering."""
        query = db.query(TraceRecord).filter(TraceRecord.tenant_id == tenant_id)
        
        # Apply same filters as list_traces
        if model_name:
            query = query.filter(TraceRecord.model_name == model_name)
        if traffic_light:
            query = query.filter(TraceRecord.traffic_light == traffic_light)
        if start_date:
            query = query.filter(TraceRecord.timestamp >= start_date)
        if end_date:
            query = query.filter(TraceRecord.timestamp <= end_date)
        if has_error is not None:
            if has_error:
                query = query.filter(TraceRecord.error.isnot(None))
            else:
                query = query.filter(TraceRecord.error.is_(None))
        
        return query.count()
    
    @staticmethod
    def update_trace_scores(db: Session, 
                           tenant_id: UUID,
                           trace_id: str,
                           grounding_score: Optional[float] = None,
                           helpfulness_score: Optional[float] = None,
                           safety_score: Optional[float] = None,
                           overall_score: Optional[float] = None,
                           traffic_light: Optional[str] = None) -> Optional[TraceRecord]:
        """Update evaluation scores for a trace."""
        trace = db.query(TraceRecord).filter(
            and_(
                TraceRecord.tenant_id == tenant_id,
                TraceRecord.trace_id == trace_id
            )
        ).first()
        
        if not trace:
            return None
            
        if grounding_score is not None:
            trace.grounding_score = grounding_score
        if helpfulness_score is not None:
            trace.helpfulness_score = helpfulness_score
        if safety_score is not None:
            trace.safety_score = safety_score
        if overall_score is not None:
            trace.overall_score = overall_score
        if traffic_light is not None:
            trace.traffic_light = traffic_light
            
        trace.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(trace)
        return trace
    
    @staticmethod
    def delete_old_traces(db: Session, tenant_id: UUID, days_to_keep: int = 30) -> int:
        """Delete traces older than specified days for a tenant."""
        cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)
        
        # First delete related evaluations
        evaluation_count = db.query(EvaluationRecord).filter(
            and_(
                EvaluationRecord.tenant_id == tenant_id,
                EvaluationRecord.evaluation_timestamp < cutoff_date
            )
        ).count()
        
        db.query(EvaluationRecord).filter(
            and_(
                EvaluationRecord.tenant_id == tenant_id,
                EvaluationRecord.evaluation_timestamp < cutoff_date
            )
        ).delete()
        
        # Then delete traces
        trace_count = db.query(TraceRecord).filter(
            and_(
                TraceRecord.tenant_id == tenant_id,
                TraceRecord.timestamp < cutoff_date
            )
        ).count()
        
        db.query(TraceRecord).filter(
            and_(
                TraceRecord.tenant_id == tenant_id,
                TraceRecord.timestamp < cutoff_date
            )
        ).delete()
        
        db.commit()
        return trace_count
    
    @staticmethod
    def get_traces_for_evaluation(db: Session, tenant_id: UUID, limit: int = 100) -> List[TraceRecord]:
        """Get traces that need evaluation for a tenant."""
        return db.query(TraceRecord).filter(
            and_(
                TraceRecord.tenant_id == tenant_id,
                TraceRecord.overall_score.is_(None),
                TraceRecord.error.is_(None),  # Skip errored traces
                TraceRecord.model_output.isnot(None)  # Must have output
            )
        ).order_by(TraceRecord.timestamp).limit(limit).all()


class EvaluationCRUD:
    """CRUD operations for evaluations."""
    
    @staticmethod
    def create_evaluation(db: Session,
                         tenant_id: UUID,
                         trace_id: str,
                         score_type: str,
                         score: float,
                         confidence: float = 1.0,
                         explanation: Optional[str] = None,
                         metadata: Optional[Dict[str, Any]] = None,
                         evaluator_version: Optional[str] = None) -> EvaluationRecord:
        """Create a new evaluation record."""
        db_evaluation = EvaluationRecord(
            tenant_id=tenant_id,
            trace_id=trace_id,
            score_type=score_type,
            score=score,
            confidence=confidence,
            explanation=explanation,
            eval_metadata=metadata or {},
            evaluator_version=evaluator_version
        )
        
        db.add(db_evaluation)
        db.commit()
        db.refresh(db_evaluation)
        return db_evaluation
    
    @staticmethod
    def get_evaluations_for_trace(db: Session, tenant_id: UUID, trace_id: str) -> List[EvaluationRecord]:
        """Get all evaluations for a specific trace."""
        return db.query(EvaluationRecord).filter(
            and_(
                EvaluationRecord.tenant_id == tenant_id,
                EvaluationRecord.trace_id == trace_id
            )
        ).all()


class StatsCRUD:
    """CRUD operations for statistics."""
    
    @staticmethod
    def get_dashboard_stats(db: Session, tenant_id: UUID) -> Dict[str, Any]:
        """Get dashboard statistics for a tenant."""
        now = datetime.utcnow()
        
        # Total traces
        total_traces = db.query(TraceRecord).filter(TraceRecord.tenant_id == tenant_id).count()
        
        # Traces in last 24 hours
        last_24h = now - timedelta(hours=24)
        traces_last_24h = db.query(TraceRecord).filter(
            and_(
                TraceRecord.tenant_id == tenant_id,
                TraceRecord.timestamp >= last_24h
            )
        ).count()
        
        # Average response time
        avg_response_time = db.query(func.avg(TraceRecord.response_latency_ms)).filter(
            and_(
                TraceRecord.tenant_id == tenant_id,
                TraceRecord.response_latency_ms.isnot(None)
            )
        ).scalar() or 0
        
        # Traffic light distribution
        traffic_light_query = db.query(
            TraceRecord.traffic_light,
            func.count(TraceRecord.traffic_light)
        ).filter(
            and_(
                TraceRecord.tenant_id == tenant_id,
                TraceRecord.traffic_light.isnot(None)
            )
        ).group_by(TraceRecord.traffic_light).all()
        
        traffic_light_distribution = {color: count for color, count in traffic_light_query}
        
        # Top models
        top_models_query = db.query(
            TraceRecord.model_name,
            func.count(TraceRecord.model_name).label('count'),
            func.avg(TraceRecord.response_latency_ms).label('avg_latency')
        ).filter(
            and_(
                TraceRecord.tenant_id == tenant_id,
                TraceRecord.model_name.isnot(None)
            )
        ).group_by(TraceRecord.model_name).order_by(desc('count')).limit(5).all()
        
        top_models = [
            {
                "model": model_name,
                "count": count,
                "avg_latency_ms": round(avg_latency or 0, 2)
            }
            for model_name, count, avg_latency in top_models_query
        ]
        
        # Error rate
        error_count = db.query(TraceRecord).filter(
            and_(
                TraceRecord.tenant_id == tenant_id,
                TraceRecord.error.isnot(None)
            )
        ).count()
        
        error_rate = (error_count / total_traces * 100) if total_traces > 0 else 0
        
        return {
            "total_traces": total_traces,
            "traces_last_24h": traces_last_24h,
            "avg_response_time_ms": round(avg_response_time, 2),
            "traffic_light_distribution": traffic_light_distribution,
            "top_models": top_models,
            "error_rate": round(error_rate, 2)
        }
    
    @staticmethod
    def get_time_series_data(db: Session, 
                           tenant_id: UUID,
                           hours: int = 24,
                           bucket_size_minutes: int = 60) -> List[Dict[str, Any]]:
        """Get time series data for traces."""
        now = datetime.utcnow()
        start_time = now - timedelta(hours=hours)
        
        # Generate time buckets
        buckets = []
        current_time = start_time
        
        while current_time < now:
            bucket_end = current_time + timedelta(minutes=bucket_size_minutes)
            
            # Count traces in this bucket
            trace_count = db.query(TraceRecord).filter(
                and_(
                    TraceRecord.tenant_id == tenant_id,
                    TraceRecord.timestamp >= current_time,
                    TraceRecord.timestamp < bucket_end
                )
            ).count()
            
            # Count errors in this bucket
            error_count = db.query(TraceRecord).filter(
                and_(
                    TraceRecord.tenant_id == tenant_id,
                    TraceRecord.timestamp >= current_time,
                    TraceRecord.timestamp < bucket_end,
                    TraceRecord.error.isnot(None)
                )
            ).count()
            
            # Average response time in this bucket
            avg_latency = db.query(func.avg(TraceRecord.response_latency_ms)).filter(
                and_(
                    TraceRecord.tenant_id == tenant_id,
                    TraceRecord.timestamp >= current_time,
                    TraceRecord.timestamp < bucket_end,
                    TraceRecord.response_latency_ms.isnot(None)
                )
            ).scalar()
            
            buckets.append({
                "timestamp": current_time.isoformat(),
                "trace_count": trace_count,
                "error_count": error_count,
                "avg_latency_ms": round(avg_latency or 0, 2),
                "error_rate": round((error_count / trace_count * 100) if trace_count > 0 else 0, 2)
            })
            
            current_time = bucket_end
        
        return buckets 