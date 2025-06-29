"""
OpenAI Connector for RAG Toolkit

Wraps OpenAI client with automatic tracing capabilities.
"""

import functools
import time
from typing import Any, Dict, Optional, Union, List
from ..tracer import RAGTracker


def with_tracing(func):
    """Decorator to add tracing to OpenAI API calls"""
    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        # Extract common parameters
        messages = kwargs.get('messages', args[0] if args else [])
        model = kwargs.get('model', getattr(self, 'model', 'gpt-3.5-turbo'))
        
        # Start tracing
        tracker = RAGTracker()
        
        # Extract user input from messages
        user_input = None
        if messages and isinstance(messages, list):
            user_messages = [m for m in messages if m.get('role') == 'user']
            if user_messages:
                user_input = user_messages[-1].get('content', '')
        
        with tracker.trace_context(user_input=user_input or 'OpenAI API call') as trace:
            # Add system/user prompts
            if messages:
                full_prompt = "\n".join([f"{m.get('role', 'unknown')}: {m.get('content', '')}" 
                                       for m in messages])
                tracker.add_prompt(full_prompt)
            
            # Record start time
            start_time = time.time()
            
            try:
                # Make the original API call
                response = func(self, *args, **kwargs)
                
                # Record timing
                end_time = time.time()
                latency_ms = int((end_time - start_time) * 1000)
                
                # Extract response content and tokens
                if hasattr(response, 'choices') and response.choices:
                    content = response.choices[0].message.content
                    tracker.set_model_output(
                        output=content,
                        model_name=model,
                        tokens_in=getattr(response.usage, 'prompt_tokens', None) if hasattr(response, 'usage') else None,
                        tokens_out=getattr(response.usage, 'completion_tokens', None) if hasattr(response, 'usage') else None,
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


class ChatCompletion:
    """
    Drop-in replacement for OpenAI ChatCompletion with automatic tracing.
    
    Usage:
        from ragtoolkit.connectors.openai import ChatCompletion
        from openai import OpenAI
        
        client = OpenAI()
        # Replace: response = client.chat.completions.create(...)
        response = ChatCompletion.create(client, messages=[...], model="gpt-4")
    """
    
    @staticmethod
    @with_tracing
    def create(client, **kwargs):
        """Create a chat completion with automatic tracing"""
        return client.chat.completions.create(**kwargs)
    
    @classmethod 
    def wrap_client(cls, client):
        """
        Wrap an existing OpenAI client to add tracing to all chat completions.
        
        Args:
            client: OpenAI client instance
            
        Returns:
            Modified client with tracing enabled
        """
        original_create = client.chat.completions.create
        client.chat.completions.create = with_tracing(original_create)
        return client


def traced_openai_client(api_key: Optional[str] = None, **kwargs):
    """
    Create a new OpenAI client with tracing enabled.
    
    Args:
        api_key: OpenAI API key
        **kwargs: Additional arguments for OpenAI client
        
    Returns:
        OpenAI client with automatic tracing
    """
    try:
        from openai import OpenAI
    except ImportError:
        raise ImportError("openai package is required. Install with: pip install openai")
    
    client = OpenAI(api_key=api_key, **kwargs)
    return ChatCompletion.wrap_client(client) 