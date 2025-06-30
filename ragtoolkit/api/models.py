"""Database models for RAG Toolkit API."""

from datetime import datetime
from typing import Optional, Dict, Any, List
from uuid import uuid4

from sqlalchemy import Column, String, DateTime, Float, Integer, Text, Boolean, JSON, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from pydantic import BaseModel, Field


Base = declarative_base()


class Tenant(Base):
    """Database model for tenants in multi-tenant setup."""
    __tablename__ = "tenants"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    slug = Column(String(50), unique=True, nullable=False, index=True)  # for subdomain
    name = Column(String(200), nullable=False)
    
    # Subscription details
    stripe_customer_id = Column(String(100), unique=True, index=True)
    subscription_status = Column(String(20), default="trial")  # trial, active, cancelled, past_due
    subscription_plan = Column(String(50), default="starter")
    
    # Usage limits and settings
    rate_limit_per_second = Column(Integer, default=200)
    max_users = Column(Integer, default=5)
    retention_days = Column(Integer, default=30)
    
    # Audit fields
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    traces = relationship("TraceRecord", back_populates="tenant")
    users = relationship("TenantUser", back_populates="tenant")
    usage_records = relationship("UsageRecord", back_populates="tenant")


class TenantUser(Base):
    """Database model for users within a tenant."""
    __tablename__ = "tenant_users"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True)
    email = Column(String(255), nullable=False, index=True)
    role = Column(String(20), default="viewer")  # admin, analyst, viewer
    api_key = Column(String(100), unique=True, index=True)
    
    # User status
    is_active = Column(Boolean, default=True)
    last_login = Column(DateTime)
    
    # Audit fields
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    tenant = relationship("Tenant", back_populates="users")


class UsageRecord(Base):
    """Database model for tracking tenant usage metrics."""
    __tablename__ = "usage_records"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True)
    
    # Usage period
    period_start = Column(DateTime, nullable=False, index=True)
    period_end = Column(DateTime, nullable=False, index=True)
    
    # Usage metrics
    trace_count = Column(Integer, default=0)
    seat_count = Column(Integer, default=0)  # Active users in period
    api_requests = Column(Integer, default=0)
    storage_mb = Column(Float, default=0.0)
    
    # Cost metrics
    total_tokens_in = Column(Integer, default=0)
    total_tokens_out = Column(Integer, default=0)
    
    # Audit fields
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    tenant = relationship("Tenant", back_populates="usage_records")


class TraceRecord(Base):
    """Database model for storing RAG traces."""
    __tablename__ = "traces"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True)
    trace_id = Column(String(36), nullable=False, index=True)
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
    
    # Relationships
    tenant = relationship("Tenant", back_populates="traces")


class EvaluationRecord(Base):
    """Database model for storing detailed evaluation results."""
    __tablename__ = "evaluations"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True)
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
class TenantCreate(BaseModel):
    """Model for creating new tenants."""
    slug: str = Field(..., pattern=r"^[a-z0-9-]+$", min_length=2, max_length=50)
    name: str = Field(..., min_length=1, max_length=200)
    admin_email: str = Field(..., pattern=r"^[^@]+@[^@]+\.[^@]+$")


class TenantResponse(BaseModel):
    """Model for tenant API responses."""
    id: str
    slug: str
    name: str
    subscription_status: str
    subscription_plan: str
    rate_limit_per_second: int
    max_users: int
    retention_days: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class TenantUserCreate(BaseModel):
    """Model for creating tenant users."""
    email: str = Field(..., pattern=r"^[^@]+@[^@]+\.[^@]+$")
    role: str = Field(default="viewer", pattern=r"^(admin|analyst|viewer)$")


class TenantUserResponse(BaseModel):
    """Model for tenant user API responses."""
    id: str
    email: str
    role: str
    api_key: str
    is_active: bool
    last_login: Optional[datetime]
    created_at: datetime
    
    class Config:
        from_attributes = True


class UsageResponse(BaseModel):
    """Model for usage API responses."""
    id: str
    period_start: datetime
    period_end: datetime
    trace_count: int
    seat_count: int
    api_requests: int
    storage_mb: float
    total_tokens_in: int
    total_tokens_out: int
    
    class Config:
        from_attributes = True


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