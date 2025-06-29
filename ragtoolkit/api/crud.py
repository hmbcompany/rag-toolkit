"""CRUD operations for RAG Toolkit database."""

from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from uuid import UUID

from sqlalchemy.orm import Session
from sqlalchemy import func, desc, and_, or_

from .models import TraceRecord, EvaluationRecord, TraceCreate


class TraceCRUD:
    """CRUD operations for traces."""
    
    @staticmethod
    def create_trace(db: Session, trace_data: TraceCreate) -> TraceRecord:
        """Create a new trace record."""
        db_trace = TraceRecord(
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
    def get_trace(db: Session, trace_id: str) -> Optional[TraceRecord]:
        """Get a trace by trace_id."""
        return db.query(TraceRecord).filter(TraceRecord.trace_id == trace_id).first()
    
    @staticmethod
    def get_trace_by_uuid(db: Session, trace_uuid: UUID) -> Optional[TraceRecord]:
        """Get a trace by UUID."""
        return db.query(TraceRecord).filter(TraceRecord.id == trace_uuid).first()
    
    @staticmethod
    def list_traces(db: Session, 
                   skip: int = 0, 
                   limit: int = 100,
                   model_name: Optional[str] = None,
                   traffic_light: Optional[str] = None,
                   start_date: Optional[datetime] = None,
                   end_date: Optional[datetime] = None,
                   has_error: Optional[bool] = None) -> List[TraceRecord]:
        """List traces with optional filtering."""
        query = db.query(TraceRecord)
        
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
                    model_name: Optional[str] = None,
                    traffic_light: Optional[str] = None,
                    start_date: Optional[datetime] = None,
                    end_date: Optional[datetime] = None,
                    has_error: Optional[bool] = None) -> int:
        """Count traces with optional filtering."""
        query = db.query(TraceRecord)
        
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
                           trace_id: str,
                           grounding_score: Optional[float] = None,
                           helpfulness_score: Optional[float] = None,
                           safety_score: Optional[float] = None,
                           overall_score: Optional[float] = None,
                           traffic_light: Optional[str] = None) -> Optional[TraceRecord]:
        """Update evaluation scores for a trace."""
        trace = db.query(TraceRecord).filter(TraceRecord.trace_id == trace_id).first()
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
    def delete_old_traces(db: Session, days_to_keep: int = 30) -> int:
        """Delete traces older than specified days."""
        cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)
        
        # First delete related evaluations
        evaluation_count = db.query(EvaluationRecord).filter(
            EvaluationRecord.evaluation_timestamp < cutoff_date
        ).count()
        
        db.query(EvaluationRecord).filter(
            EvaluationRecord.evaluation_timestamp < cutoff_date
        ).delete()
        
        # Then delete traces
        trace_count = db.query(TraceRecord).filter(
            TraceRecord.timestamp < cutoff_date
        ).count()
        
        db.query(TraceRecord).filter(
            TraceRecord.timestamp < cutoff_date
        ).delete()
        
        db.commit()
        return trace_count
    
    @staticmethod
    def get_traces_for_evaluation(db: Session, limit: int = 100) -> List[TraceRecord]:
        """Get traces that need evaluation (no scores yet)."""
        return db.query(TraceRecord).filter(
            and_(
                TraceRecord.overall_score.is_(None),
                TraceRecord.error.is_(None),  # Skip errored traces
                TraceRecord.model_output.isnot(None)  # Must have output
            )
        ).order_by(TraceRecord.timestamp).limit(limit).all()


class EvaluationCRUD:
    """CRUD operations for evaluations."""
    
    @staticmethod
    def create_evaluation(db: Session,
                         trace_id: str,
                         score_type: str,
                         score: float,
                         confidence: float = 1.0,
                         explanation: Optional[str] = None,
                         metadata: Optional[Dict[str, Any]] = None,
                         evaluator_version: Optional[str] = None) -> EvaluationRecord:
        """Create a new evaluation record."""
        db_evaluation = EvaluationRecord(
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
    def get_evaluations_for_trace(db: Session, trace_id: str) -> List[EvaluationRecord]:
        """Get all evaluations for a specific trace."""
        return db.query(EvaluationRecord).filter(
            EvaluationRecord.trace_id == trace_id
        ).order_by(EvaluationRecord.evaluation_timestamp).all()


class StatsCRUD:
    """CRUD operations for statistics."""
    
    @staticmethod
    def get_dashboard_stats(db: Session) -> Dict[str, Any]:
        """Get dashboard statistics."""
        now = datetime.utcnow()
        yesterday = now - timedelta(days=1)
        
        # Total traces
        total_traces = db.query(TraceRecord).count()
        
        # Traces in last 24h
        traces_24h = db.query(TraceRecord).filter(
            TraceRecord.timestamp >= yesterday
        ).count()
        
        # Average response time
        avg_response_time = db.query(func.avg(TraceRecord.response_latency_ms)).filter(
            TraceRecord.response_latency_ms.isnot(None)
        ).scalar() or 0.0
        
        # Traffic light distribution
        traffic_light_stats = db.query(
            TraceRecord.traffic_light,
            func.count(TraceRecord.traffic_light)
        ).filter(
            TraceRecord.traffic_light.isnot(None)
        ).group_by(TraceRecord.traffic_light).all()
        
        traffic_light_distribution = {
            "green": 0,
            "amber": 0, 
            "red": 0
        }
        for light, count in traffic_light_stats:
            traffic_light_distribution[light] = count
        
        # Top models
        top_models = db.query(
            TraceRecord.model_name,
            func.count(TraceRecord.model_name).label('count'),
            func.avg(TraceRecord.response_latency_ms).label('avg_latency')
        ).filter(
            TraceRecord.model_name.isnot(None)
        ).group_by(TraceRecord.model_name).order_by(
            desc('count')
        ).limit(5).all()
        
        top_models_list = [
            {
                "model": model,
                "count": count,
                "avg_latency_ms": round(avg_latency or 0, 2)
            }
            for model, count, avg_latency in top_models
        ]
        
        # Error rate
        total_with_output = db.query(TraceRecord).filter(
            or_(
                TraceRecord.model_output.isnot(None),
                TraceRecord.error.isnot(None)
            )
        ).count()
        
        error_count = db.query(TraceRecord).filter(
            TraceRecord.error.isnot(None)
        ).count()
        
        error_rate = (error_count / total_with_output * 100) if total_with_output > 0 else 0.0
        
        return {
            "total_traces": total_traces,
            "traces_last_24h": traces_24h,
            "avg_response_time_ms": round(avg_response_time, 2),
            "traffic_light_distribution": traffic_light_distribution,
            "top_models": top_models_list,
            "error_rate": round(error_rate, 2)
        }
    
    @staticmethod
    def get_time_series_data(db: Session, 
                           hours: int = 24,
                           bucket_size_minutes: int = 60) -> List[Dict[str, Any]]:
        """Get time series data for charts."""
        now = datetime.utcnow()
        start_time = now - timedelta(hours=hours)
        
        # This is a simplified version - in production you'd want proper time bucketing
        traces = db.query(TraceRecord).filter(
            TraceRecord.timestamp >= start_time
        ).order_by(TraceRecord.timestamp).all()
        
        # Group by hour for simplicity
        time_buckets = {}
        for trace in traces:
            hour = trace.timestamp.replace(minute=0, second=0, microsecond=0)
            if hour not in time_buckets:
                time_buckets[hour] = {
                    "timestamp": hour,
                    "count": 0,
                    "avg_latency": 0,
                    "error_count": 0,
                    "traffic_lights": {"green": 0, "amber": 0, "red": 0}
                }
            
            bucket = time_buckets[hour]
            bucket["count"] += 1
            
            if trace.response_latency_ms:
                bucket["avg_latency"] = (
                    (bucket["avg_latency"] * (bucket["count"] - 1) + trace.response_latency_ms) 
                    / bucket["count"]
                )
            
            if trace.error:
                bucket["error_count"] += 1
                
            if trace.traffic_light:
                bucket["traffic_lights"][trace.traffic_light] += 1
        
        return list(time_buckets.values()) 