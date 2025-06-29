"""
Core tracing functionality for RAG pipelines.

Provides decorator and context manager to capture full RAG traces
including user input, retrieved chunks, model outputs, and metadata.
"""

import asyncio
import json
import time
import uuid
from contextlib import contextmanager
from functools import wraps
from typing import Any, Dict, List, Optional, Union
from dataclasses import dataclass, field, asdict
import threading
import logging

import httpx


logger = logging.getLogger(__name__)


@dataclass
class TraceData:
    """Structure for capturing RAG trace data."""
    trace_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: float = field(default_factory=time.time)
    user_input: Optional[str] = None
    retrieved_chunks: List[Dict[str, Any]] = field(default_factory=list)
    retrieval_scores: List[float] = field(default_factory=list)
    prompts: List[str] = field(default_factory=list)
    model_output: Optional[str] = None
    model_name: Optional[str] = None
    response_latency_ms: Optional[float] = None
    tokens_in: Optional[int] = None
    tokens_out: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None


class RAGTracker:
    """Main tracker class for managing RAG traces."""
    
    def __init__(self, api_url: str = "http://localhost:8000", api_key: Optional[str] = None):
        self.api_url = api_url.rstrip('/')
        self.api_key = api_key
        self.session = httpx.AsyncClient()
        self._current_trace = threading.local()
        
    def _get_headers(self) -> Dict[str, str]:
        """Get HTTP headers for API requests."""
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers
        
    @property
    def current_trace(self) -> Optional[TraceData]:
        """Get current trace data for this thread."""
        return getattr(self._current_trace, 'data', None)
    
    @current_trace.setter
    def current_trace(self, trace_data: Optional[TraceData]):
        """Set current trace data for this thread."""
        self._current_trace.data = trace_data
        
    def start_trace(self, user_input: str = None, **metadata) -> TraceData:
        """Start a new trace."""
        trace_data = TraceData(
            user_input=user_input,
            metadata=metadata
        )
        self.current_trace = trace_data
        return trace_data
        
    def add_retrieved_chunks(self, chunks: List[Dict[str, Any]], scores: List[float] = None):
        """Add retrieved chunks to current trace."""
        if self.current_trace:
            self.current_trace.retrieved_chunks.extend(chunks)
            if scores:
                self.current_trace.retrieval_scores.extend(scores)
                
    def add_prompt(self, prompt: str):
        """Add prompt to current trace."""
        if self.current_trace:
            self.current_trace.prompts.append(prompt)
            
    def set_model_output(self, output: str, model_name: str = None, 
                        tokens_in: int = None, tokens_out: int = None):
        """Set model output and metadata."""
        if self.current_trace:
            self.current_trace.model_output = output
            if model_name:
                self.current_trace.model_name = model_name
            if tokens_in:
                self.current_trace.tokens_in = tokens_in
            if tokens_out:
                self.current_trace.tokens_out = tokens_out
                
    def set_error(self, error: str):
        """Set error information."""
        if self.current_trace:
            self.current_trace.error = error
            
    async def submit_trace(self, trace_data: TraceData = None) -> bool:
        """Submit trace to API."""
        if not trace_data:
            trace_data = self.current_trace
            
        if not trace_data:
            logger.warning("No trace data to submit")
            return False
            
        try:
            # Calculate response latency if not set
            if trace_data.response_latency_ms is None:
                trace_data.response_latency_ms = (time.time() - trace_data.timestamp) * 1000
                
            response = await self.session.post(
                f"{self.api_url}/api/v1/traces",
                json=asdict(trace_data),
                headers=self._get_headers(),
                timeout=5.0
            )
            
            if response.status_code == 201:
                logger.debug(f"Trace {trace_data.trace_id} submitted successfully")
                return True
            else:
                logger.error(f"Failed to submit trace: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Error submitting trace: {e}")
            return False
            
    def submit_trace_sync(self, trace_data: TraceData = None) -> bool:
        """Submit trace synchronously."""
        return asyncio.run(self.submit_trace(trace_data))
        
    @contextmanager
    def trace_context(self, user_input: str = None, **metadata):
        """Context manager for tracing RAG operations."""
        trace_data = self.start_trace(user_input=user_input, **metadata)
        start_time = time.time()
        
        try:
            yield trace_data
        except Exception as e:
            self.set_error(str(e))
            raise
        finally:
            trace_data.response_latency_ms = (time.time() - start_time) * 1000
            
            # Submit trace async in background
            asyncio.create_task(self.submit_trace(trace_data))
            
            # Clear current trace
            self.current_trace = None


# Global tracker instance
_global_tracker = RAGTracker()


def configure_tracker(api_url: str = "http://localhost:8000", api_key: str = None):
    """Configure the global tracker instance."""
    global _global_tracker
    _global_tracker = RAGTracker(api_url=api_url, api_key=api_key)


def trace(func=None, *, user_input_key: str = None, output_key: str = None):
    """
    Decorator to automatically trace RAG function calls.
    
    Args:
        user_input_key: Key to extract user input from function args/kwargs
        output_key: Key to extract output from function result
        
    Usage:
        @trace
        def my_rag_pipeline(query: str) -> str:
            # Your RAG logic here
            return answer
            
        @trace(user_input_key="question", output_key="answer")
        def my_rag_pipeline(question: str) -> dict:
            # Your RAG logic here
            return {"answer": "...", "sources": [...]}
    """
    
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Extract user input
            user_input = None
            if user_input_key and user_input_key in kwargs:
                user_input = kwargs[user_input_key]
            elif len(args) > 0:
                user_input = str(args[0])
                
            with _global_tracker.trace_context(user_input=user_input, function=func.__name__) as trace:
                start_time = time.time()
                
                try:
                    result = func(*args, **kwargs)
                    
                    # Extract output
                    output = None
                    if output_key and isinstance(result, dict) and output_key in result:
                        output = result[output_key]
                    else:
                        output = str(result)
                        
                    _global_tracker.set_model_output(output)
                    
                    return result
                    
                except Exception as e:
                    _global_tracker.set_error(str(e))
                    raise
                    
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            # Extract user input
            user_input = None
            if user_input_key and user_input_key in kwargs:
                user_input = kwargs[user_input_key]
            elif len(args) > 0:
                user_input = str(args[0])
                
            with _global_tracker.trace_context(user_input=user_input, function=func.__name__) as trace:
                start_time = time.time()
                
                try:
                    result = await func(*args, **kwargs)
                    
                    # Extract output
                    output = None
                    if output_key and isinstance(result, dict) and output_key in result:
                        output = result[output_key]
                    else:
                        output = str(result)
                        
                    _global_tracker.set_model_output(output)
                    
                    return result
                    
                except Exception as e:
                    _global_tracker.set_error(str(e))
                    raise
                    
        # Return appropriate wrapper based on function type
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return wrapper
            
    # Handle both @trace and @trace() usage
    if func is None:
        return decorator
    else:
        return decorator(func)


# Convenience functions
def get_current_trace() -> Optional[TraceData]:
    """Get current trace data."""
    return _global_tracker.current_trace


def add_retrieval_context(chunks: List[Dict[str, Any]], scores: List[float] = None):
    """Add retrieval context to current trace."""
    _global_tracker.add_retrieved_chunks(chunks, scores)


def add_prompt_to_trace(prompt: str):
    """Add prompt to current trace."""
    _global_tracker.add_prompt(prompt) 