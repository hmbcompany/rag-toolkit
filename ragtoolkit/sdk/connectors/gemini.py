"""
Google Gemini Connector for RAG Toolkit

Wraps Google Gemini API with automatic tracing capabilities.
"""

import functools
import time
from typing import Any, Dict, Optional, Union, List
from ..tracer import RAGTracker


def with_tracing(func):
    """Decorator to add tracing to Gemini API calls"""
    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        # Extract user input - could be from args or kwargs
        user_input = None
        if args:
            user_input = str(args[0])
        elif 'prompt' in kwargs:
            user_input = str(kwargs['prompt'])
        elif 'contents' in kwargs:
            contents = kwargs['contents']
            if isinstance(contents, list) and contents:
                user_input = str(contents[-1])
            else:
                user_input = str(contents)
        
        # Get model name
        model = getattr(self, 'model_name', 'gemini-pro')
        
        # Start tracing
        tracker = RAGTracker()
        
        with tracker.trace_context(user_input=user_input or 'Gemini API call') as trace:
            # Add prompt
            if user_input:
                tracker.add_prompt(f"user: {user_input}")
            
            # Record start time
            start_time = time.time()
            
            try:
                # Make the original API call
                response = func(self, *args, **kwargs)
                
                # Record timing
                end_time = time.time()
                latency_ms = int((end_time - start_time) * 1000)
                
                # Extract response content
                content = None
                tokens_in = None
                tokens_out = None
                
                # Handle different response formats
                if hasattr(response, 'text'):
                    content = response.text
                elif hasattr(response, 'candidates') and response.candidates:
                    candidate = response.candidates[0]
                    if hasattr(candidate, 'content') and hasattr(candidate.content, 'parts'):
                        content = candidate.content.parts[0].text
                    elif hasattr(candidate, 'text'):
                        content = candidate.text
                
                # Try to extract token usage if available
                if hasattr(response, 'usage_metadata'):
                    usage = response.usage_metadata
                    tokens_in = getattr(usage, 'prompt_token_count', None)
                    tokens_out = getattr(usage, 'candidates_token_count', None)
                
                if content:
                    tracker.set_model_output(
                        output=content,
                        model_name=model,
                        tokens_in=tokens_in,
                        tokens_out=tokens_out,
                        latency_ms=latency_ms
                    )
                
                return response
                
            except Exception as e:
                # Record error
                tracker.set_model_output(
                    output=f"Error: {str(e)}",
                    model_name=model,
                    latency_ms=int((time.time() - start_time) * 1000)
                )
                raise
    
    return wrapper


class Chat:
    """
    Drop-in replacement for Google Gemini with automatic tracing.
    
    Usage:
        from ragtoolkit.connectors.gemini import Chat
        import google.generativeai as genai
        
        model = genai.GenerativeModel('gemini-pro')
        # Replace: response = model.generate_content(...)
        response = Chat.generate_content(model, "Your prompt here")
    """
    
    @staticmethod
    @with_tracing
    def generate_content(model, *args, **kwargs):
        """Generate content with automatic tracing"""
        return model.generate_content(*args, **kwargs)
    
    @classmethod 
    def wrap_model(cls, model):
        """
        Wrap an existing Gemini model to add tracing to all content generation.
        
        Args:
            model: Gemini GenerativeModel instance
            
        Returns:
            Modified model with tracing enabled
        """
        original_generate = model.generate_content
        model.generate_content = lambda *args, **kwargs: cls.generate_content(model, *args, **kwargs)
        return model


def traced_gemini_model(model_name: str = 'gemini-pro', api_key: Optional[str] = None, **kwargs):
    """
    Create a new Gemini model with tracing enabled.
    
    Args:
        model_name: Gemini model name (default: 'gemini-pro')
        api_key: Google API key
        **kwargs: Additional arguments for model configuration
        
    Returns:
        Gemini model with automatic tracing
    """
    try:
        import google.generativeai as genai
    except ImportError:
        raise ImportError("google-generativeai package is required. Install with: pip install google-generativeai")
    
    if api_key:
        genai.configure(api_key=api_key)
    
    model = genai.GenerativeModel(model_name, **kwargs)
    return Chat.wrap_model(model) 