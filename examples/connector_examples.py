"""
RAG Toolkit Connector Examples

Examples showing how to use the pre-built connectors for automatic tracing.
"""

import os


# Example 1: OpenAI Connector
def openai_example():
    """Example using OpenAI connector with automatic tracing"""
    from ragtoolkit.connectors.openai import traced_openai_client
    
    # Create client with automatic tracing
    client = traced_openai_client(api_key=os.getenv("OPENAI_API_KEY"))
    
    # Use normally - tracing happens automatically
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "user", "content": "What is the capital of France?"}
        ]
    )
    
    print(f"Response: {response.choices[0].message.content}")
    # Trace automatically sent to RAG Toolkit!


# Example 2: Anthropic Connector  
def anthropic_example():
    """Example using Anthropic connector with automatic tracing"""
    from ragtoolkit.connectors.anthropic import traced_anthropic_client
    
    # Create client with automatic tracing
    client = traced_anthropic_client(api_key=os.getenv("ANTHROPIC_API_KEY"))
    
    # Use normally - tracing happens automatically
    response = client.messages.create(
        model="claude-3-sonnet-20240229",
        max_tokens=100,
        messages=[
            {"role": "user", "content": "What is the capital of Spain?"}
        ]
    )
    
    print(f"Response: {response.content[0].text}")
    # Trace automatically sent to RAG Toolkit!


# Example 3: Gemini Connector
def gemini_example():
    """Example using Gemini connector with automatic tracing"""
    from ragtoolkit.connectors.gemini import traced_gemini_model
    
    # Create model with automatic tracing
    model = traced_gemini_model(
        model_name='gemini-pro',
        api_key=os.getenv("GOOGLE_API_KEY")
    )
    
    # Use normally - tracing happens automatically
    response = model.generate_content("What is the capital of Italy?")
    
    print(f"Response: {response.text}")
    # Trace automatically sent to RAG Toolkit!


# Example 4: Ollama Connector (Local)
def ollama_example():
    """Example using Ollama connector with automatic tracing"""
    from ragtoolkit.connectors.ollama import traced_ollama_client
    
    # Create client with automatic tracing
    client = traced_ollama_client(host="http://localhost:11434")
    
    # Use normally - tracing happens automatically
    response = client.generate(
        model='llama2',
        prompt='What is the capital of Germany?'
    )
    
    print(f"Response: {response['response']}")
    # Trace automatically sent to RAG Toolkit!


# Example 5: Wrapper Pattern (Existing Clients)
def wrapper_pattern_example():
    """Example showing how to wrap existing clients"""
    from openai import OpenAI
    from ragtoolkit.connectors.openai import ChatCompletion
    
    # Your existing client
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    
    # Wrap it to add tracing
    traced_client = ChatCompletion.wrap_client(client)
    
    # Now all calls are automatically traced
    response = traced_client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": "Hello!"}]
    )
    
    return response


if __name__ == "__main__":
    # Configure RAG Toolkit (optional - uses defaults if not set)
    from ragtoolkit import configure_tracker
    configure_tracker(
        api_url="http://localhost:8000",
        project="connector_examples"
    )
    
    print("Testing RAG Toolkit Connectors...")
    print("Traces will appear at: http://localhost:8000")
    print()
    
    # Test each connector (uncomment to try)
    # openai_example()
    # anthropic_example() 
    # gemini_example()
    # ollama_example()
    
    print("✅ All examples completed. Check your RAG Toolkit dashboard!") 