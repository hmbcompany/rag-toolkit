"""
Ollama Connector for RAG Toolkit

Wraps Ollama client with automatic tracing capabilities.
"""

import functools
import time
from typing import Any, Dict, Optional, Union, List
from ..tracer import RAGTracker


def with_tracing(func):
    """Decorator to add tracing to Ollama API calls"""
    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        # Extract parameters
        model = kwargs.get('model', args[0] if args else 'llama2')
        prompt = kwargs.get('prompt', args[1] if len(args) > 1 else '')
        messages = kwargs.get('messages', [])
        
        # Start tracing
        tracker = RAGTracker()
        
        # Extract user input
        user_input = prompt
        if not user_input and messages:
            user_messages = [m for m in messages if m.get('role') == 'user']
            if user_messages:
                user_input = user_messages[-1].get('content', '')
        
        with tracker.trace_context(user_input=user_input or 'Ollama API call') as trace:
            # Add prompts
            if prompt:
                tracker.add_prompt(f"user: {prompt}")
            elif messages:
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
                
                # Extract response content
                content = None
                tokens_in = None
                tokens_out = None
                
                # Handle different response formats
                if isinstance(response, dict):
                    content = response.get('response') or response.get('message', {}).get('content')
                    
                    # Extract token usage if available
                    if 'prompt_eval_count' in response:
                        tokens_in = response['prompt_eval_count']
                    if 'eval_count' in response:
                        tokens_out = response['eval_count']
                        
                elif hasattr(response, 'response'):
                    content = response.response
                elif hasattr(response, 'message') and hasattr(response.message, 'content'):
                    content = response.message.content
                
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


class Llama:
    """
    Drop-in replacement for Ollama with automatic tracing.
    
    Usage:
        from ragtoolkit.connectors.ollama import Llama
        import ollama
        
        client = ollama.Client()
        # Replace: response = client.generate(...)
        response = Llama.generate(client, model='llama2', prompt='Your prompt')
    """
    
    @staticmethod
    @with_tracing
    def generate(client, **kwargs):
        """Generate content with automatic tracing"""
        return client.generate(**kwargs)
    
    @staticmethod
    @with_tracing
    def chat(client, **kwargs):
        """Chat with automatic tracing"""
        return client.chat(**kwargs)
    
    @classmethod 
    def wrap_client(cls, client):
        """
        Wrap an existing Ollama client to add tracing to all completions.
        
        Args:
            client: Ollama client instance
            
        Returns:
            Modified client with tracing enabled
        """
        original_generate = client.generate
        original_chat = client.chat
        
        client.generate = lambda **kwargs: cls.generate(client, **kwargs)
        client.chat = lambda **kwargs: cls.chat(client, **kwargs)
        
        return client


def traced_ollama_client(host: Optional[str] = None, **kwargs):
    """
    Create a new Ollama client with tracing enabled.
    
    Args:
        host: Ollama server host (default: http://localhost:11434)
        **kwargs: Additional arguments for Ollama client
        
    Returns:
        Ollama client with automatic tracing
    """
    try:
        import ollama
    except ImportError:
        raise ImportError("ollama package is required. Install with: pip install ollama")
    
    client = ollama.Client(host=host, **kwargs) if host else ollama.Client(**kwargs)
    return Llama.wrap_client(client)


# Convenience functions for direct usage
def generate(model: str, prompt: str, host: Optional[str] = None, **kwargs):
    """
    Generate text with Ollama and automatic tracing.
    
    Args:
        model: Model name (e.g., 'llama2', 'mistral')
        prompt: Input prompt
        host: Ollama server host
        **kwargs: Additional generation parameters
        
    Returns:
        Generation response with automatic tracing
    """
    client = traced_ollama_client(host=host)
    return client.generate(model=model, prompt=prompt, **kwargs)


def chat(model: str, messages: List[Dict[str, str]], host: Optional[str] = None, **kwargs):
    """
    Chat with Ollama and automatic tracing.
    
    Args:
        model: Model name (e.g., 'llama2', 'mistral')
        messages: List of message dictionaries with 'role' and 'content'
        host: Ollama server host
        **kwargs: Additional chat parameters
        
    Returns:
        Chat response with automatic tracing
    """
    client = traced_ollama_client(host=host)
    return client.chat(model=model, messages=messages, **kwargs) 