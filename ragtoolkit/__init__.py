"""
RAG Toolkit - Observability and evaluation for RAG applications.

A vendor-neutral toolkit for capturing, measuring, and monitoring
RAG answer quality, safety, and cost.
"""

__version__ = "0.1.0"

from .sdk.tracer import trace, RAGTracker, configure_tracker

__all__ = ["trace", "RAGTracker", "configure_tracker"] 