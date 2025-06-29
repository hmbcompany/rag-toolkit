"""
RAG Toolkit - Observability and evaluation for RAG applications.

A vendor-neutral toolkit for capturing, measuring, and monitoring
RAG answer quality, safety, and cost.
"""

__version__ = "0.2.0"

from .sdk.tracer import trace, RAGTracker, configure_tracker
from .sdk import connectors
from . import pinecone, weaviate

__all__ = [
    "trace", 
    "RAGTracker", 
    "configure_tracker",
    "connectors",
    "pinecone",
    "weaviate",
    "__version__"
] 