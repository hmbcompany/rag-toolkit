"""
Anthropic Connector for RAG Toolkit

Wraps Anthropic client with automatic tracing capabilities.
"""

import functools
import time
from typing import Any, Dict, Optional, Union, List
from ..tracer import RAGTracker


def with_tracing(func):
    """Decorator to add tracing to Anthropic API calls"""
    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        # Extract common parameters
        messages = kwargs.get('messages', args[0] if args else [])
        model = kwargs.get('model', getattr(self, 'model', 'claude-3-sonnet-20240229'))
        
        # Start tracing
        tracker = RAGTracker()
        
        # Extract user input from messages
        user_input = None
        if messages and isinstance(messages, list):
            user_messages = [m for m in messages if m.get('role') == 'user']
            if user_messages:
                user_input = user_messages[-1].get('content', '')
        
        with tracker.trace_context(user_input=user_input or 'Anthropic API call') as trace:
            # Add system/user prompts
            if messages:
                full_prompt = "\n".join([f"{m.get('role', 'unknown')}: {m.get('content', '')}" 
                                       for m in messages])
                tracker.add_prompt(full_prompt)
            
            # Add system prompt if provided separately
            system_prompt = kwargs.get('system')
            if system_prompt:
                tracker.add_prompt(f"system: {system_prompt}")
            
            # Record start time
            start_time = time.time()
            
            try:
                # Make the original API call
                response = func(self, *args, **kwargs)
                
                # Record timing
                end_time = time.time()
                latency_ms = int((end_time - start_time) * 1000)
                
                # Extract response content and tokens
                if hasattr(response, 'content') and response.content:
                    # Anthropic returns content as a list of content blocks
                    if isinstance(response.content, list) and response.content:
                        content = response.content[0].text if hasattr(response.content[0], 'text') else str(response.content[0])
                    else:
                        content = str(response.content)
                    
                    tracker.set_model_output(
                        output=content,
                        model_name=model,
                        tokens_in=getattr(response.usage, 'input_tokens', None) if hasattr(response, 'usage') else None,
                        tokens_out=getattr(response.usage, 'output_tokens', None) if hasattr(response, 'usage') else None,
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


class Complete:
    """
    Drop-in replacement for Anthropic Messages with automatic tracing.
    
    Usage:
        from ragtoolkit.connectors.anthropic import Complete
        from anthropic import Anthropic
        
        client = Anthropic()
        # Replace: response = client.messages.create(...)
        response = Complete.create(client, messages=[...], model="claude-3-sonnet-20240229")
    """
    
    @staticmethod
    @with_tracing
    def create(client, **kwargs):
        """Create a message completion with automatic tracing"""
        return client.messages.create(**kwargs)
    
    @classmethod 
    def wrap_client(cls, client):
        """
        Wrap an existing Anthropic client to add tracing to all message completions.
        
        Args:
            client: Anthropic client instance
            
        Returns:
            Modified client with tracing enabled
        """
        original_create = client.messages.create
        client.messages.create = with_tracing(original_create)
        return client


def traced_anthropic_client(api_key: Optional[str] = None, **kwargs):
    """
    Create a new Anthropic client with tracing enabled.
    
    Args:
        api_key: Anthropic API key
        **kwargs: Additional arguments for Anthropic client
        
    Returns:
        Anthropic client with automatic tracing
    """
    try:
        from anthropic import Anthropic
    except ImportError:
        raise ImportError("anthropic package is required. Install with: pip install anthropic")
    
    client = Anthropic(api_key=api_key, **kwargs)
    return Complete.wrap_client(client) 