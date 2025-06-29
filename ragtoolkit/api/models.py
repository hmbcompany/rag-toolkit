"""Database models for RAG Toolkit API."""

from datetime import datetime
from typing import Optional, Dict, Any, List
from uuid import uuid4

from sqlalchemy import Column, String, DateTime, Float, Integer, Text, Boolean, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.dialects.postgresql import UUID
from pydantic import BaseModel, Field


Base = declarative_base()


class TraceRecord(Base):
    """Database model for storing RAG traces."""
    __tablename__ = "traces"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    trace_id = Column(String(36), unique=True, nullable=False, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    
    # Input data
    user_input = Column(Text)
    retrieved_chunks = Column(JSON)
    retrieval_scores = Column(JSON)
    prompts = Column(JSON)
    
    # Output data
    model_output = Column(Text)
    model_name = Column(String(100))
    
    # Performance metrics
    response_latency_ms = Column(Float)
    tokens_in = Column(Integer)
    tokens_out = Column(Integer)
    
    # Metadata and error handling
    trace_metadata = Column(JSON)
    error = Column(Text)
    
    # Evaluation scores (populated after evaluation)
    grounding_score = Column(Float)
    helpfulness_score = Column(Float)
    safety_score = Column(Float)
    overall_score = Column(Float)
    traffic_light = Column(String(10))  # green, amber, red
    
    # Audit fields
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class EvaluationRecord(Base):
    """Database model for storing detailed evaluation results."""
    __tablename__ = "evaluations"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    trace_id = Column(String(36), nullable=False, index=True)
    
    # Score details
    score_type = Column(String(20), nullable=False)  # grounding, helpfulness, safety, composite
    score = Column(Float, nullable=False)
    confidence = Column(Float, default=1.0)
    explanation = Column(Text)
    eval_metadata = Column(JSON)
    
    # Evaluation metadata
    evaluator_version = Column(String(50))
    evaluation_timestamp = Column(DateTime, default=datetime.utcnow)


# Pydantic models for API requests/responses
class TraceCreate(BaseModel):
    """Model for creating new traces."""
    trace_id: str
    timestamp: float
    user_input: Optional[str] = None
    retrieved_chunks: List[Dict[str, Any]] = []
    retrieval_scores: List[float] = []
    prompts: List[str] = []
    model_output: Optional[str] = None
    model_name: Optional[str] = None
    response_latency_ms: Optional[float] = None
    tokens_in: Optional[int] = None
    tokens_out: Optional[int] = None
    trace_metadata: Dict[str, Any] = {}
    error: Optional[str] = None


class TraceResponse(BaseModel):
    """Model for trace API responses."""
    id: str
    trace_id: str
    timestamp: datetime
    user_input: Optional[str]
    retrieved_chunks: List[Dict[str, Any]]
    retrieval_scores: List[float]
    prompts: List[str]
    model_output: Optional[str]
    model_name: Optional[str]
    response_latency_ms: Optional[float]
    tokens_in: Optional[int]
    tokens_out: Optional[int]
    trace_metadata: Dict[str, Any]
    error: Optional[str]
    
    # Evaluation scores
    grounding_score: Optional[float]
    helpfulness_score: Optional[float]
    safety_score: Optional[float]
    overall_score: Optional[float]
    traffic_light: Optional[str]
    
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class TraceListResponse(BaseModel):
    """Model for paginated trace list responses."""
    traces: List[TraceResponse]
    total: int
    page: int
    size: int
    has_next: bool


class EvaluationResponse(BaseModel):
    """Model for evaluation API responses."""
    id: str
    trace_id: str
    score_type: str
    score: float
    confidence: float
    explanation: Optional[str]
    eval_metadata: Dict[str, Any]
    evaluator_version: Optional[str]
    evaluation_timestamp: datetime
    
    class Config:
        from_attributes = True


class StatsResponse(BaseModel):
    """Model for statistics API responses."""
    total_traces: int
    traces_last_24h: int
    avg_response_time_ms: float
    traffic_light_distribution: Dict[str, int]
    top_models: List[Dict[str, Any]]
    error_rate: float 