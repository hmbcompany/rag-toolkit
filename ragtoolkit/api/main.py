"""
Main FastAPI application for RAG Toolkit API.

Provides endpoints for:
- Receiving and storing RAG traces
- Retrieving trace data and statistics  
- Evaluation results
- Dashboard data
"""

import os
import asyncio
from datetime import datetime, timedelta
from typing import List, Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

from .models import Base, TraceCreate, TraceResponse, TraceListResponse, StatsResponse
from .crud import TraceCRUD, EvaluationCRUD, StatsCRUD
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
API_KEY = os.getenv("RAGTOOLKIT_API_KEY")

# Background evaluator
evaluator = CompositeScorer()
evaluation_task = None


def get_db():
    """Database dependency."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Authentication dependency."""
    if API_KEY and credentials:
        if credentials.credentials != API_KEY:
            raise HTTPException(status_code=401, detail="Invalid API key")
    elif API_KEY and not credentials:
        raise HTTPException(status_code=401, detail="API key required")
    return True


async def evaluate_traces_background():
    """Background task to evaluate traces."""
    while True:
        try:
            db = SessionLocal()
            try:
                # Get traces that need evaluation
                traces = TraceCRUD.get_traces_for_evaluation(db, limit=10)
                
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
    # Start background evaluation task
    global evaluation_task
    evaluation_task = asyncio.create_task(evaluate_traces_background())
    
    yield
    
    # Cleanup
    if evaluation_task:
        evaluation_task.cancel()
        try:
            await evaluation_task
        except asyncio.CancelledError:
            pass


# FastAPI application
app = FastAPI(
    title="RAG Toolkit API",
    description="API for RAG observability and evaluation",
    version="0.1.0",
    lifespan=lifespan
)

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
    return {"message": "RAG Toolkit API", "version": "0.2.0", "status": "healthy"}


@app.get("/health")
async def health_check():
    """Health check endpoint for Docker."""
    return {"status": "healthy", "version": "0.2.0"}


@app.post("/api/v1/traces", status_code=201)
async def create_trace(
    trace: TraceCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    _: bool = Depends(get_current_user)
):
    """Create a new trace."""
    try:
        db_trace = TraceCRUD.create_trace(db, trace)
        return {"message": "Trace created successfully", "trace_id": db_trace.trace_id}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/v1/traces", response_model=TraceListResponse)
async def list_traces(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    model_name: Optional[str] = None,
    traffic_light: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    has_error: Optional[bool] = None,
    db: Session = Depends(get_db),
    _: bool = Depends(get_current_user)
):
    """List traces with pagination and filtering."""
    skip = (page - 1) * size
    
    traces = TraceCRUD.list_traces(
        db, 
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
        model_name=model_name,
        traffic_light=traffic_light,
        start_date=start_date,
        end_date=end_date,
        has_error=has_error
    )
    
    has_next = (skip + size) < total
    
    return TraceListResponse(
        traces=[TraceResponse.model_validate({
            **trace.__dict__,
            'id': str(trace.id)
        }) for trace in traces],
        total=total,
        page=page,
        size=size,
        has_next=has_next
    )


@app.get("/api/v1/traces/{trace_id}", response_model=TraceResponse)
async def get_trace(
    trace_id: str,
    db: Session = Depends(get_db),
    _: bool = Depends(get_current_user)
):
    """Get a specific trace by ID."""
    # Try both lookup methods since both id and trace_id can be UUIDs
    trace = None
    
    # First try looking up by database UUID (id field)
    try:
        from uuid import UUID
        trace_uuid = UUID(trace_id)
        trace = TraceCRUD.get_trace_by_uuid(db, trace_uuid)
    except ValueError:
        pass
    
    # If not found, try looking up by trace_id field
    if not trace:
        trace = TraceCRUD.get_trace(db, trace_id)
    
    if not trace:
        raise HTTPException(status_code=404, detail="Trace not found")
    
    return TraceResponse.model_validate({
        **trace.__dict__,
        'id': str(trace.id)
    })


@app.get("/api/v1/traces/{trace_id}/evaluations")
async def get_trace_evaluations(
    trace_id: str,
    db: Session = Depends(get_db),
    _: bool = Depends(get_current_user)
):
    """Get all evaluations for a specific trace."""
    # Find the trace using both lookup methods
    trace = None
    
    # First try looking up by database UUID (id field)
    try:
        from uuid import UUID
        trace_uuid = UUID(trace_id)
        trace = TraceCRUD.get_trace_by_uuid(db, trace_uuid)
    except ValueError:
        pass
    
    # If not found, try looking up by trace_id field
    if not trace:
        trace = TraceCRUD.get_trace(db, trace_id)
    
    if not trace:
        raise HTTPException(status_code=404, detail="Trace not found")
    
    # Use the actual trace_id from the database record
    actual_trace_id = trace.trace_id
    
    evaluations = EvaluationCRUD.get_evaluations_for_trace(db, actual_trace_id)
    return [
        {
            "id": str(eval.id),
            "trace_id": eval.trace_id,
            "score_type": eval.score_type,
            "score": eval.score,
            "confidence": eval.confidence,
            "explanation": eval.explanation,
            "eval_metadata": eval.eval_metadata or {},
            "evaluator_version": eval.evaluator_version,
            "evaluation_timestamp": eval.evaluation_timestamp.isoformat() if eval.evaluation_timestamp else None
        }
        for eval in evaluations
    ]


@app.get("/api/v1/stats", response_model=StatsResponse)
async def get_stats(
    db: Session = Depends(get_db),
    _: bool = Depends(get_current_user)
):
    """Get dashboard statistics."""
    stats = StatsCRUD.get_dashboard_stats(db)
    return StatsResponse(**stats)


@app.get("/api/v1/stats/timeseries")
async def get_timeseries(
    hours: int = Query(24, ge=1, le=168),  # Max 1 week
    db: Session = Depends(get_db),
    _: bool = Depends(get_current_user)
):
    """Get time series data for charts."""
    data = StatsCRUD.get_time_series_data(db, hours=hours)
    return {"data": data}


@app.post("/api/v1/traces/{trace_id}/evaluate")
async def manual_evaluate_trace(
    trace_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    _: bool = Depends(get_current_user)
):
    """Manually trigger evaluation for a specific trace."""
    # Find the trace using both lookup methods
    trace = None
    
    # First try looking up by database UUID (id field) 
    try:
        from uuid import UUID
        trace_uuid = UUID(trace_id)
        trace = TraceCRUD.get_trace_by_uuid(db, trace_uuid)
    except ValueError:
        pass
    
    # If not found, try looking up by trace_id field
    if not trace:
        trace = TraceCRUD.get_trace(db, trace_id)
    
    if not trace:
        raise HTTPException(status_code=404, detail="Trace not found")
    
    if not trace.model_output:
        raise HTTPException(status_code=400, detail="Trace has no output to evaluate")
    
    # Add to background tasks for evaluation
    async def evaluate_single_trace():
        try:
            composite_score = await evaluator.score(
                answer=trace.model_output,
                retrieved_chunks=trace.retrieved_chunks or [],
                query=trace.user_input
            )
            
            # Update scores in database
            TraceCRUD.update_trace_scores(
                db,
                trace.trace_id,
                grounding_score=composite_score.grounding.score if composite_score.grounding else None,
                helpfulness_score=composite_score.helpfulness.score if composite_score.helpfulness else None,
                safety_score=composite_score.safety.score if composite_score.safety else None,
                overall_score=composite_score.overall_score,
                traffic_light=composite_score.overall_traffic_light.value
            )
        except Exception as e:
            print(f"Manual evaluation failed for {trace_id}: {e}")
    
    background_tasks.add_task(evaluate_single_trace)
    
    return {"message": "Evaluation started", "trace_id": trace_id}


@app.delete("/api/v1/traces/cleanup")
async def cleanup_old_traces(
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
    _: bool = Depends(get_current_user)
):
    """Delete traces older than specified days."""
    deleted_count = TraceCRUD.delete_old_traces(db, days_to_keep=days)
    return {"message": f"Deleted {deleted_count} old traces", "days": days}


@app.get("/api/v1/export/traces")
async def export_traces(
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    format: str = Query("json", regex="^(json|csv)$"),
    db: Session = Depends(get_db),
    _: bool = Depends(get_current_user)
):
    """Export traces for audit purposes."""
    # Set default date range if not provided
    if not end_date:
        end_date = datetime.utcnow()
    if not start_date:
        start_date = end_date - timedelta(days=30)
    
    traces = TraceCRUD.list_traces(
        db,
        start_date=start_date,
        end_date=end_date,
        limit=10000  # Large limit for export
    )
    
    if format == "json":
        return {
            "traces": [TraceResponse.model_validate({
                **trace.__dict__,
                'id': str(trace.id)
            }).model_dump() for trace in traces],
            "exported_at": datetime.utcnow(),
            "date_range": {
                "start": start_date,
                "end": end_date
            }
        }
    else:
        # CSV format would be implemented here
        raise HTTPException(status_code=501, detail="CSV export not yet implemented")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 