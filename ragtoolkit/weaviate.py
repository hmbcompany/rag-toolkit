"""
Weaviate Integration for RAG Toolkit

Wraps Weaviate operations with automatic retrieval tracing.
"""

import functools
import time
from typing import Any, Dict, List, Optional, Union
from .sdk.tracer import RAGTracker


def with_retrieval_tracing(func):
    """Decorator to add retrieval tracing to Weaviate operations"""
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
            scores = []
            
            # Handle different result formats
            if isinstance(result, dict):
                # GraphQL query result
                if 'data' in result and 'Get' in result['data']:
                    # Extract from Get query
                    class_results = result['data']['Get']
                    for class_name, objects in class_results.items():
                        for obj in objects:
                            chunk_data = {
                                'text': obj.get('text', str(obj)),
                                'source': f'weaviate:{class_name}:{obj.get("_additional", {}).get("id", "unknown")}',
                                'metadata': {k: v for k, v in obj.items() if k != '_additional'}
                            }
                            chunks.append(chunk_data)
                            
                            # Extract score if available
                            additional = obj.get('_additional', {})
                            if 'distance' in additional:
                                # Convert distance to similarity score (1 - distance)
                                score = max(0, 1 - additional['distance'])
                                scores.append(score)
                            elif 'certainty' in additional:
                                scores.append(additional['certainty'])
                            else:
                                scores.append(1.0)  # Default score
            
            elif hasattr(result, 'objects'):
                # Batch result format
                for obj in result.objects:
                    chunk_data = {
                        'text': getattr(obj, 'properties', {}).get('text', str(obj.properties)),
                        'source': f'weaviate:{obj.class_name}:{obj.uuid}',
                        'metadata': getattr(obj, 'properties', {})
                    }
                    chunks.append(chunk_data)
                    scores.append(1.0)  # Default score for batch operations
            
            # Add to trace if we found chunks
            if chunks:
                tracker.add_retrieved_chunks(chunks=chunks, scores=scores)
            
            return result
            
        except Exception as e:
            # Log retrieval error
            tracker.add_retrieved_chunks(chunks=[], scores=[])
            raise
    
    return wrapper


class Client:
    """
    Enhanced Weaviate Client with automatic retrieval tracing.
    
    Usage:
        from ragtoolkit.weaviate import Client
        import weaviate
        
        # Wrap existing client
        wv_client = weaviate.Client("http://localhost:8080")
        traced_client = Client.wrap(wv_client)
        
        # Or create directly
        traced_client = Client("http://localhost:8080")
        
        # Use normally - retrieval tracing happens automatically
        results = traced_client.query.get("Article", ["title", "content"]).do()
    """
    
    def __init__(self, url: str = "http://localhost:8080", **kwargs):
        """Initialize traced Weaviate client"""
        try:
            import weaviate
        except ImportError:
            raise ImportError("weaviate-client package is required. Install with: pip install weaviate-client")
        
        self._client = weaviate.Client(url, **kwargs)
        self.url = url
    
    @property
    def query(self):
        """Get query interface with tracing"""
        return TracedQuery(self._client.query)
    
    @property 
    def batch(self):
        """Get batch interface with tracing"""
        return TracedBatch(self._client.batch)
    
    @property
    def schema(self):
        """Get schema interface (no tracing needed)"""
        return self._client.schema
    
    @property
    def data_object(self):
        """Get data object interface (no tracing needed for CRUD)"""
        return self._client.data_object
    
    def get_meta(self):
        """Get meta information (no tracing needed)"""
        return self._client.get_meta()
    
    def is_ready(self):
        """Check if Weaviate is ready (no tracing needed)"""
        return self._client.is_ready()
    
    @classmethod
    def wrap(cls, weaviate_client):
        """
        Wrap an existing Weaviate client to add tracing.
        
        Args:
            weaviate_client: Existing Weaviate Client instance
            
        Returns:
            Wrapped client with automatic tracing
        """
        wrapper = cls.__new__(cls)
        wrapper._client = weaviate_client
        wrapper.url = getattr(weaviate_client, '_connection', {}).get('url', 'unknown')
        return wrapper


class TracedQuery:
    """Query interface with automatic tracing"""
    
    def __init__(self, query):
        self._query = query
    
    def get(self, *args, **kwargs):
        """Get query with tracing"""
        return TracedGet(self._query.get(*args, **kwargs))


class TracedGet:
    """Get query builder with automatic tracing"""
    
    def __init__(self, get_query):
        self._get_query = get_query
    
    def with_additional(self, *args, **kwargs):
        """Add additional fields"""
        return TracedGet(self._get_query.with_additional(*args, **kwargs))
    
    def with_limit(self, *args, **kwargs):
        """Add limit"""
        return TracedGet(self._get_query.with_limit(*args, **kwargs))
    
    def with_near_text(self, *args, **kwargs):
        """Add near text search"""
        return TracedGet(self._get_query.with_near_text(*args, **kwargs))
    
    def with_near_vector(self, *args, **kwargs):
        """Add near vector search"""
        return TracedGet(self._get_query.with_near_vector(*args, **kwargs))
    
    def with_where(self, *args, **kwargs):
        """Add where filter"""
        return TracedGet(self._get_query.with_where(*args, **kwargs))
    
    @with_retrieval_tracing
    def do(self):
        """Execute query with automatic tracing"""
        return self._get_query.do()


class TracedBatch:
    """Batch interface with automatic tracing"""
    
    def __init__(self, batch):
        self._batch = batch
    
    def add_data_object(self, *args, **kwargs):
        """Add data object to batch (no tracing needed)"""
        return self._batch.add_data_object(*args, **kwargs)
    
    def create_objects(self, *args, **kwargs):
        """Create objects in batch (no tracing needed)"""
        return self._batch.create_objects(*args, **kwargs)
    
    def flush(self, *args, **kwargs):
        """Flush batch (no tracing needed)"""
        return self._batch.flush(*args, **kwargs)


def traced_weaviate_client(url: str = "http://localhost:8080", **kwargs):
    """
    Create a Weaviate client with automatic retrieval tracing.
    
    Args:
        url: Weaviate server URL
        **kwargs: Additional arguments for Weaviate client
        
    Returns:
        Weaviate client with automatic retrieval tracing
    """
    return Client(url, **kwargs) 