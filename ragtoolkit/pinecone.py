"""
Pinecone Integration for RAG Toolkit

Wraps Pinecone operations with automatic retrieval tracing.
"""

import functools
import time
from typing import Any, Dict, List, Optional, Union
from .sdk.tracer import RAGTracker


def with_retrieval_tracing(func):
    """Decorator to add retrieval tracing to Pinecone operations"""
    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        # Get current tracker instance
        tracker = RAGTracker.get_current_tracker()
        
        if not tracker or not hasattr(tracker, 'current_trace'):
            # No active trace context, just execute normally
            return func(self, *args, **kwargs)
        
        # Record start time
        start_time = time.time()
        
        try:
            # Execute the query
            result = func(self, *args, **kwargs)
            
            # Extract retrieval information
            latency_ms = int((time.time() - start_time) * 1000)
            
            # Parse results to extract chunks and scores
            chunks = []
            if hasattr(result, 'matches'):
                for match in result.matches:
                    chunk_data = {
                        'text': match.metadata.get('text', ''),
                        'source': match.metadata.get('source', f'pinecone:{match.id}'),
                        'metadata': match.metadata
                    }
                    chunks.append(chunk_data)
                
                # Extract scores
                scores = [match.score for match in result.matches]
                
                # Add to trace
                tracker.add_retrieved_chunks(chunks=chunks, scores=scores)
            
            return result
            
        except Exception as e:
            # Log retrieval error  
            tracker.add_retrieved_chunks(chunks=[], scores=[])
            raise
    
    return wrapper


class Index:
    """
    Enhanced Pinecone Index with automatic retrieval tracing.
    
    Usage:
        from ragtoolkit.pinecone import Index
        import pinecone
        
        # Wrap existing index
        pc_index = pinecone.Index("your-index")
        traced_index = Index.wrap(pc_index)
        
        # Or create directly
        traced_index = Index("your-index")
        
        # Use normally - retrieval tracing happens automatically
        results = traced_index.query(vector=[...], top_k=5)
    """
    
    def __init__(self, index_name: str, **kwargs):
        """Initialize traced Pinecone index"""
        try:
            import pinecone
        except ImportError:
            raise ImportError("pinecone-client package is required. Install with: pip install pinecone-client")
        
        self._index = pinecone.Index(index_name, **kwargs)
        self.index_name = index_name
    
    @with_retrieval_tracing
    def query(self, *args, **kwargs):
        """Query with automatic retrieval tracing"""
        return self._index.query(*args, **kwargs)
    
    @with_retrieval_tracing  
    def fetch(self, *args, **kwargs):
        """Fetch with automatic retrieval tracing"""
        return self._index.fetch(*args, **kwargs)
    
    def upsert(self, *args, **kwargs):
        """Upsert (no tracing needed for writes)"""
        return self._index.upsert(*args, **kwargs)
    
    def delete(self, *args, **kwargs):
        """Delete (no tracing needed for writes)"""
        return self._index.delete(*args, **kwargs)
    
    def describe_index_stats(self, *args, **kwargs):
        """Describe index stats (no tracing needed)"""
        return self._index.describe_index_stats(*args, **kwargs)
    
    @classmethod
    def wrap(cls, pinecone_index):
        """
        Wrap an existing Pinecone index to add tracing.
        
        Args:
            pinecone_index: Existing Pinecone Index instance
            
        Returns:
            Wrapped index with automatic tracing
        """
        # Create wrapper instance
        wrapper = cls.__new__(cls)
        wrapper._index = pinecone_index
        wrapper.index_name = getattr(pinecone_index, 'index_name', 'unknown')
        return wrapper


def traced_pinecone_index(index_name: str, **kwargs):
    """
    Create a Pinecone index with automatic retrieval tracing.
    
    Args:
        index_name: Name of the Pinecone index
        **kwargs: Additional arguments for Pinecone index
        
    Returns:
        Pinecone index with automatic retrieval tracing
    """
    return Index(index_name, **kwargs) 