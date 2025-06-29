"""
Simple example showing how to use RAG Toolkit with a basic RAG pipeline.

This example demonstrates:
1. Setting up a mock RAG pipeline
2. Using the @trace decorator
3. Manual context addition
4. Running the pipeline and viewing traces

To run this example:
1. Start the RAG Toolkit API: `uvicorn ragtoolkit.api.main:app --reload`
2. Run this script: `python examples/simple_rag_example.py`
3. Check the dashboard at http://localhost:8000 to see your traces
"""

import asyncio
import random
from typing import List, Dict

# Import RAG Toolkit components
from ragtoolkit import trace, configure_tracker
from ragtoolkit.sdk.tracer import add_retrieval_context, add_prompt_to_trace


def mock_retrieve_documents(query: str) -> List[Dict[str, any]]:
    """Mock document retrieval function."""
    # Simulated document chunks
    mock_docs = [
        {
            "text": "Paris is the capital and most populous city of France. It is located in the north-central part of the country.",
            "source": "geography_facts.pdf",
            "score": 0.95
        },
        {
            "text": "France is a country in Western Europe with Paris as its capital city.",
            "source": "world_capitals.txt", 
            "score": 0.87
        },
        {
            "text": "The French capital, Paris, is known for landmarks like the Eiffel Tower and Louvre Museum.",
            "source": "travel_guide.md",
            "score": 0.82
        }
    ]
    
    # Return random subset of docs
    return random.sample(mock_docs, k=random.randint(1, 3))


def mock_generate_answer(query: str, docs: List[Dict]) -> str:
    """Mock answer generation function."""
    if "capital" in query.lower() and "france" in query.lower():
        return "Paris is the capital of France. It is located in north-central France and is the country's most populous city, known for iconic landmarks like the Eiffel Tower."
    elif "france" in query.lower():
        return "France is a country in Western Europe. Its capital is Paris, and it's known for its rich culture, cuisine, and historical landmarks."
    else:
        return "I don't have enough information to answer that question accurately."


@trace
def basic_rag_pipeline(query: str) -> str:
    """
    A basic RAG pipeline with automatic tracing.
    
    The @trace decorator automatically captures:
    - Input query
    - Output answer
    - Execution time
    - Any errors
    """
    print(f"🔍 Processing query: {query}")
    
    # Step 1: Retrieve relevant documents
    retrieved_docs = mock_retrieve_documents(query)
    print(f"📄 Retrieved {len(retrieved_docs)} documents")
    
    # Step 2: Generate answer based on retrieved docs
    answer = mock_generate_answer(query, retrieved_docs)
    print(f"✅ Generated answer: {answer[:100]}...")
    
    return answer


@trace
def advanced_rag_pipeline(query: str) -> str:
    """
    Advanced RAG pipeline with manual context addition.
    
    This shows how to add additional context to traces:
    - Retrieved documents with scores
    - Prompts used
    - Model information
    """
    print(f"🔍 Processing query: {query}")
    
    # Step 1: Retrieve documents
    retrieved_docs = mock_retrieve_documents(query)
    
    # Add retrieval context to the trace
    add_retrieval_context(
        chunks=retrieved_docs,
        scores=[doc["score"] for doc in retrieved_docs]
    )
    
    # Step 2: Build prompt
    context_text = "\n".join([doc["text"] for doc in retrieved_docs])
    prompt = f"""
Context:
{context_text}

Question: {query}

Please provide a comprehensive answer based on the context above.
"""
    
    # Add prompt to trace
    add_prompt_to_trace(prompt)
    
    # Step 3: Generate answer
    answer = mock_generate_answer(query, retrieved_docs)
    
    print(f"📄 Retrieved {len(retrieved_docs)} documents")
    print(f"✅ Generated answer: {answer[:100]}...")
    
    return answer


async def run_examples():
    """Run the example pipelines."""
    
    # Configure the tracker to connect to local API
    configure_tracker(
        api_url="http://localhost:8000",
        api_key=None  # No API key needed for local development
    )
    
    print("🚀 RAG Toolkit Example")
    print("=" * 50)
    
    # Example queries
    queries = [
        "What is the capital of France?",
        "Tell me about France",
        "What are some famous landmarks in Paris?",
        "What is the population of France?",
    ]
    
    print("\n📊 Running Basic RAG Pipeline:")
    print("-" * 30)
    
    for i, query in enumerate(queries, 1):
        print(f"\nExample {i}:")
        try:
            answer = basic_rag_pipeline(query)
            print(f"Answer: {answer}")
        except Exception as e:
            print(f"Error: {e}")
        
        # Small delay between requests
        await asyncio.sleep(1)
    
    print("\n📊 Running Advanced RAG Pipeline:")
    print("-" * 35)
    
    for i, query in enumerate(queries[:2], 1):  # Just first 2 for advanced
        print(f"\nAdvanced Example {i}:")
        try:
            answer = advanced_rag_pipeline(query)
            print(f"Answer: {answer}")
        except Exception as e:
            print(f"Error: {e}")
        
        # Small delay between requests
        await asyncio.sleep(1)
    
    print("\n✅ Examples completed!")
    print("🌐 Check the dashboard at http://localhost:8000 to see your traces")
    print("📊 You should see traces with evaluation scores appearing shortly")


def create_test_data_file():
    """Create a sample test data file for CLI evaluation."""
    import csv
    
    test_cases = [
        {
            "question": "What is the capital of France?",
            "expected_context": "Paris is the capital of France.",
            "expected_answer": "Paris is the capital of France."
        },
        {
            "question": "Tell me about France",
            "expected_context": "France is a country in Western Europe.",
            "expected_answer": "France is a country in Western Europe with rich culture and history."
        },
        {
            "question": "What are famous landmarks in Paris?",
            "expected_context": "Paris has landmarks like the Eiffel Tower and Louvre Museum.",
            "expected_answer": "Famous landmarks in Paris include the Eiffel Tower and Louvre Museum."
        }
    ]
    
    with open("example_test_data.csv", "w", newline='') as csvfile:
        fieldnames = ["question", "expected_context", "expected_answer"]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(test_cases)
    
    print("📄 Created example_test_data.csv for CLI testing")
    print("🧪 Run: ragtoolkit eval example_test_data.csv --output results.json")


if __name__ == "__main__":
    print("🎯 RAG Toolkit Simple Example")
    print("\nMake sure the RAG Toolkit API is running:")
    print("   uvicorn ragtoolkit.api.main:app --reload")
    print("\nThen visit: http://localhost:8000")
    print("\n" + "="*50)
    
    # Create test data file
    create_test_data_file()
    
    # Run the examples
    asyncio.run(run_examples()) 