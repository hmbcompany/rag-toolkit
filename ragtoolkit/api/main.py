"""
Main FastAPI application for RAG Toolkit API - Sprint 3 Multi-Tenant.

Provides endpoints for:
- Multi-tenant trace management
- Tenant and user management
- Billing and subscription management
- Usage tracking and metering
- Rate limiting per tenant
"""

import os
import asyncio
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from contextlib import asynccontextmanager
from uuid import UUID

from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

from .models import (
    Base, TraceCreate, TraceResponse, TraceListResponse, StatsResponse,
    TenantCreate, TenantResponse, TenantUserCreate, TenantUserResponse, 
    UsageResponse, Tenant, TenantUser
)
from .crud import (
    TraceCRUD, EvaluationCRUD, StatsCRUD, TenantCRUD, 
    TenantUserCRUD, UsageCRUD
)
from .stripe_service import StripeService, TenantBillingService
from .metering_service import MeteringScheduler
from .rate_limiter import RateLimitMiddleware
from ..sdk.evaluator import CompositeScorer


# Database setup
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./ragtoolkit.db")

if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
else:
    engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create tables
Base.metadata.create_all(bind=engine)

# Security
security = HTTPBearer(auto_error=False)
LEGACY_API_KEY = os.getenv("RAGTOOLKIT_API_KEY")  # For backward compatibility

# Background services
evaluator = CompositeScorer()
evaluation_task = None
metering_scheduler = None


def get_db():
    """Database dependency."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class TenantContext:
    """Context object for tenant and user information."""
    def __init__(self, tenant: Tenant, user: TenantUser):
        self.tenant = tenant
        self.user = user


def get_tenant_context(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> TenantContext:
    """Enhanced authentication dependency that resolves tenant context."""
    
    # Handle legacy API key for backward compatibility
    if LEGACY_API_KEY and credentials and credentials.credentials == LEGACY_API_KEY:
        # Create or get default tenant for legacy support
        default_tenant = TenantCRUD.get_tenant_by_slug(db, "default")
        if not default_tenant:
            # Create default tenant for legacy users
            default_tenant = TenantCRUD.create_tenant(
                db, 
                TenantCreate(
                    slug="default", 
                    name="Default Tenant", 
                    admin_email="admin@localhost"
                )
            )
        
        # Get admin user for default tenant
        admin_user = TenantUserCRUD.list_tenant_users(db, default_tenant.id)[0]
        return TenantContext(default_tenant, admin_user)
    
    # Tenant-based API key authentication
    if not credentials:
        raise HTTPException(status_code=401, detail="API key required")
    
    api_key = credentials.credentials
    user = TenantUserCRUD.get_user_by_api_key(db, api_key)
    
    if not user:
        raise HTTPException(status_code=401, detail="Invalid API key")
    
    if not user.is_active:
        raise HTTPException(status_code=401, detail="User account disabled")
    
    # Update last login
    TenantUserCRUD.update_user_login(db, user.id)
    
    # Get tenant
    tenant = TenantCRUD.get_tenant(db, user.tenant_id)
    if not tenant:
        raise HTTPException(status_code=401, detail="Tenant not found")
    
    return TenantContext(tenant, user)


async def evaluate_traces_background():
    """Background task to evaluate traces for all tenants."""
    while True:
        try:
            db = SessionLocal()
            try:
                # Get all tenants
                tenants = TenantCRUD.list_tenants(db, limit=1000)
                
                for tenant in tenants:
                    # Get traces that need evaluation for this tenant
                    traces = TraceCRUD.get_traces_for_evaluation(db, tenant.id, limit=5)
                    
                    for trace in traces:
                        if not trace.model_output:
                            continue
                            
                        try:
                            # Run evaluation
                            composite_score = await evaluator.score(
                                answer=trace.model_output,
                                retrieved_chunks=trace.retrieved_chunks or [],
                                query=trace.user_input
                            )
                            
                            # Update trace with scores
                            TraceCRUD.update_trace_scores(
                                db,
                                tenant.id,
                                trace.trace_id,
                                grounding_score=composite_score.grounding.score if composite_score.grounding else None,
                                helpfulness_score=composite_score.helpfulness.score if composite_score.helpfulness else None,
                                safety_score=composite_score.safety.score if composite_score.safety else None,
                                overall_score=composite_score.overall_score,
                                traffic_light=composite_score.overall_traffic_light.value
                            )
                            
                            # Store detailed evaluations
                            if composite_score.grounding:
                                EvaluationCRUD.create_evaluation(
                                    db,
                                    tenant.id,
                                    trace.trace_id,
                                    "grounding",
                                    composite_score.grounding.score,
                                    composite_score.grounding.confidence,
                                    composite_score.grounding.explanation,
                                    composite_score.grounding.metadata
                                )
                                
                            if composite_score.helpfulness:
                                EvaluationCRUD.create_evaluation(
                                    db,
                                    tenant.id,
                                    trace.trace_id,
                                    "helpfulness", 
                                    composite_score.helpfulness.score,
                                    composite_score.helpfulness.confidence,
                                    composite_score.helpfulness.explanation,
                                    composite_score.helpfulness.metadata
                                )
                                
                            if composite_score.safety:
                                EvaluationCRUD.create_evaluation(
                                    db,
                                    tenant.id,
                                    trace.trace_id,
                                    "safety",
                                    composite_score.safety.score,
                                    composite_score.safety.confidence,
                                    composite_score.safety.explanation,
                                    composite_score.safety.metadata
                                )
                                
                        except Exception as e:
                            print(f"Error evaluating trace {trace.trace_id}: {e}")
                            continue
                            
            finally:
                db.close()
                
        except Exception as e:
            print(f"Error in evaluation background task: {e}")
            
        # Wait before next batch
        await asyncio.sleep(30)  # Check every 30 seconds


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan."""
    global evaluation_task, metering_scheduler
    
    # Start background evaluation task
    evaluation_task = asyncio.create_task(evaluate_traces_background())
    
    # Start metering scheduler
    metering_scheduler = MeteringScheduler(DATABASE_URL)
    metering_task = asyncio.create_task(metering_scheduler.run_schedulers())
    
    yield
    
    # Cleanup
    if evaluation_task:
        evaluation_task.cancel()
        try:
            await evaluation_task
        except asyncio.CancelledError:
            pass
    
    if metering_scheduler:
        metering_scheduler.stop()
        try:
            await metering_task
        except asyncio.CancelledError:
            pass


# FastAPI application
app = FastAPI(
    title="RAG Toolkit API - Multi-Tenant",
    description="Multi-tenant API for RAG observability and evaluation",
    version="0.3.0",
    lifespan=lifespan
)

# Add rate limiting middleware
app.add_middleware(RateLimitMiddleware, default_rate=200)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure as needed
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """Root endpoint."""
    return {"message": "RAG Toolkit API - Multi-Tenant", "version": "0.3.0", "status": "healthy"}


@app.get("/health")
async def health_check():
    """Health check endpoint for Docker."""
    return {"status": "healthy", "version": "0.3.0", "features": ["multi-tenant", "rate-limiting", "billing"]}


# =============================================================================
# TENANT MANAGEMENT ENDPOINTS
# =============================================================================

@app.post("/api/v1/tenants", response_model=TenantResponse, status_code=201)
async def create_tenant(
    tenant_data: TenantCreate,
    db: Session = Depends(get_db)
):
    """Create a new tenant (public endpoint for signup)."""
    try:
        # Check if slug is already taken
        existing = TenantCRUD.get_tenant_by_slug(db, tenant_data.slug)
        if existing:
            raise HTTPException(status_code=409, detail="Tenant slug already exists")
        
        tenant = TenantCRUD.create_tenant(db, tenant_data)
        
        # Set up billing if Stripe is configured
        try:
            if os.getenv("STRIPE_SECRET_KEY"):
                TenantBillingService.setup_tenant_billing(
                    db, tenant.id, tenant_data.admin_email
                )
        except Exception as e:
            print(f"Warning: Failed to set up billing for tenant {tenant.id}: {e}")
        
        return tenant
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create tenant: {e}")


@app.get("/api/v1/tenant", response_model=TenantResponse)
async def get_current_tenant(context: TenantContext = Depends(get_tenant_context)):
    """Get current tenant information."""
    return context.tenant


@app.get("/api/v1/tenant/users", response_model=List[TenantUserResponse])
async def list_tenant_users(
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db)
):
    """List users in current tenant."""
    if context.user.role not in ["admin", "analyst"]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    users = TenantUserCRUD.list_tenant_users(db, context.tenant.id)
    return users


@app.post("/api/v1/tenant/users", response_model=TenantUserResponse, status_code=201)
async def create_tenant_user(
    user_data: TenantUserCreate,
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db)
):
    """Create a new user in current tenant."""
    if context.user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    # Check user limit
    current_users = TenantUserCRUD.list_tenant_users(db, context.tenant.id)
    if len(current_users) >= context.tenant.max_users:
        raise HTTPException(status_code=403, detail="User limit exceeded")
    
    user = TenantUserCRUD.create_user(db, context.tenant.id, user_data)
    return user


# =============================================================================
# TRACE MANAGEMENT ENDPOINTS (Updated for Multi-Tenancy)
# =============================================================================

@app.post("/api/v1/traces", status_code=201)
async def create_trace(
    trace: TraceCreate,
    background_tasks: BackgroundTasks,
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db)
):
    """Create a new trace for the current tenant."""
    try:
        db_trace = TraceCRUD.create_trace(db, context.tenant.id, trace)
        
        # Schedule evaluation if model output is present
        if db_trace.model_output:
            background_tasks.add_task(
                TraceCRUD.get_traces_for_evaluation, 
                db, 
                context.tenant.id, 
                1
            )
        
        return {"trace_id": db_trace.trace_id, "status": "created"}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create trace: {e}")


@app.get("/api/v1/traces", response_model=TraceListResponse)
async def list_traces(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    model_name: Optional[str] = None,
    traffic_light: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    has_error: Optional[bool] = None,
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db)
):
    """List traces for the current tenant."""
    skip = (page - 1) * size
    
    traces = TraceCRUD.list_traces(
        db,
        context.tenant.id,
        skip=skip,
        limit=size,
        model_name=model_name,
        traffic_light=traffic_light,
        start_date=start_date,
        end_date=end_date,
        has_error=has_error
    )
    
    total = TraceCRUD.count_traces(
        db,
        context.tenant.id,
        model_name=model_name,
        traffic_light=traffic_light,
        start_date=start_date,
        end_date=end_date,
        has_error=has_error
    )
    
    return TraceListResponse(
        traces=traces,
        total=total,
        page=page,
        size=size,
        has_next=(skip + size) < total
    )


@app.get("/api/v1/traces/{trace_id}", response_model=TraceResponse)
async def get_trace(
    trace_id: str,
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db)
):
    """Get a specific trace for the current tenant."""
    trace = TraceCRUD.get_trace(db, context.tenant.id, trace_id)
    if not trace:
        raise HTTPException(status_code=404, detail="Trace not found")
    return trace


@app.get("/api/v1/traces/{trace_id}/evaluations")
async def get_trace_evaluations(
    trace_id: str,
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db)
):
    """Get evaluations for a specific trace."""
    # Verify trace exists and belongs to tenant
    trace = TraceCRUD.get_trace(db, context.tenant.id, trace_id)
    if not trace:
        raise HTTPException(status_code=404, detail="Trace not found")
    
    evaluations = EvaluationCRUD.get_evaluations_for_trace(db, context.tenant.id, trace_id)
    return {"trace_id": trace_id, "evaluations": evaluations}


@app.get("/api/v1/stats", response_model=StatsResponse)
async def get_stats(
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db)
):
    """Get statistics for the current tenant."""
    stats = StatsCRUD.get_dashboard_stats(db, context.tenant.id)
    return StatsResponse(**stats)


@app.get("/api/v1/stats/timeseries")
async def get_timeseries(
    hours: int = Query(24, ge=1, le=168),  # Max 1 week
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db)
):
    """Get time series data for the current tenant."""
    timeseries = StatsCRUD.get_time_series_data(db, context.tenant.id, hours)
    return {"timeseries": timeseries}


# =============================================================================
# USAGE AND BILLING ENDPOINTS
# =============================================================================

@app.get("/api/v1/usage", response_model=Dict[str, Any])
async def get_current_usage(
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db)
):
    """Get current usage for the tenant."""
    usage = UsageCRUD.calculate_current_usage(db, context.tenant.id)
    return usage


@app.get("/api/v1/usage/history")
async def get_usage_history(
    months: int = Query(3, ge=1, le=12),
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db)
):
    """Get usage history for the tenant."""
    usage_records = UsageCRUD.get_tenant_usage_history(db, context.tenant.id, limit=months)
    return {"usage_history": usage_records}


@app.get("/api/v1/billing")
async def get_billing_info(
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db)
):
    """Get billing information for the tenant."""
    if context.user.role not in ["admin"]:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    try:
        billing_info = TenantBillingService.get_tenant_billing_info(db, context.tenant.id)
        return billing_info
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get billing info: {e}")


@app.post("/api/v1/billing/setup")
async def setup_billing(
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db)
):
    """Set up billing for the tenant."""
    if context.user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    try:
        result = TenantBillingService.setup_tenant_billing(
            db, context.tenant.id, context.user.email
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to set up billing: {e}")


@app.post("/api/v1/billing/subscription")
async def create_subscription(
    plan: str = Query(..., regex="^(starter|pro|enterprise)$"),
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db)
):
    """Create a subscription for the tenant."""
    if context.user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    try:
        result = TenantBillingService.create_tenant_subscription(
            db, context.tenant.id, plan
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create subscription: {e}")


@app.post("/api/v1/billing/invoice/test")
async def generate_test_invoice(
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db)
):
    """Generate a test invoice for the current period."""
    if context.user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    try:
        now = datetime.utcnow()
        period_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        period_end = now
        
        result = TenantBillingService.generate_usage_invoice(
            db, context.tenant.id, period_start, period_end
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate invoice: {e}")


# =============================================================================
# LEGACY ENDPOINTS (Backward Compatibility)
# =============================================================================

@app.get("/api/config")
async def get_config():
    """Legacy config endpoint."""
    return {
        "api_url": "http://localhost:8000",
        "project": "default",
        "version": "0.3.0",
        "features": ["multi-tenant", "rate-limiting", "billing"]
    }


@app.patch("/api/config")
async def update_config(updates: dict):
    """Legacy config update endpoint."""
    return {"status": "config_updated", "updates": updates}


# =============================================================================
# ADMIN ENDPOINTS
# =============================================================================

@app.get("/api/v1/admin/tenants")
async def admin_list_tenants(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """Admin endpoint to list all tenants."""
    # In a real system, this would require admin authentication
    tenants = TenantCRUD.list_tenants(db, skip=skip, limit=limit)
    return {"tenants": tenants}


@app.post("/api/v1/admin/metering/run")
async def admin_run_metering(
    db: Session = Depends(get_db)
):
    """Admin endpoint to manually trigger metering."""
    global metering_scheduler
    if metering_scheduler:
        try:
            results = metering_scheduler.metering_service.run_hourly_aggregation()
            return {"status": "metering_complete", "results": results}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Metering failed: {e}")
    else:
        raise HTTPException(status_code=503, detail="Metering service not available")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 