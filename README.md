# RAG Toolkit

A vendor-neutral observability and evaluation toolkit for Retrieval-Augmented Generation (RAG) applications.

## Features

- 🔍 **Full RAG Tracing**: Capture end-to-end traces of user queries, retrieved chunks, and model outputs
- 📊 **Automatic Evaluation**: Score answers for grounding, helpfulness, and safety
- 🚦 **Traffic Light Scoring**: Simple red/amber/green indicators for answer quality
- 📈 **Dashboard**: Web UI for monitoring traces and metrics
- 🔔 **Alerts**: Slack notifications when quality drops
- 🧪 **CLI Testing**: Batch evaluation and testing tools
- 🐳 **Easy Deployment**: Docker Compose setup

## Quick Start

### 1. Installation

```bash
pip install ragtoolkit
```

### 2. Basic Usage

Wrap your RAG pipeline with the `@trace` decorator:

```python
from ragtoolkit import trace

@trace
def my_rag_pipeline(query: str) -> str:
    # Your RAG logic here
    retrieved_docs = retrieve_documents(query)
    answer = generate_answer(query, retrieved_docs)
    return answer

# Use your pipeline as normal
result = my_rag_pipeline("What is the capital of France?")
```

### 3. Start the Dashboard

```bash
# Using Docker Compose (recommended)
docker-compose up

# Or run locally
uvicorn ragtoolkit.api.main:app --reload
```

Visit http://localhost:8000 to see your traces!

## Advanced Usage

### Manual Tracing

For more control, use the context manager:

```python
from ragtoolkit.sdk.tracer import RAGTracker

tracker = RAGTracker()

with tracker.trace_context(user_input="What is AI?") as trace:
    # Add retrieved context
    chunks = [{"text": "AI is...", "source": "doc1.pdf"}]
    tracker.add_retrieved_chunks(chunks, scores=[0.9])
    
    # Add prompts
    tracker.add_prompt("You are a helpful assistant...")
    
    # Set model output
    tracker.set_model_output("AI is artificial intelligence...", 
                           model_name="gpt-4", 
                           tokens_in=100, 
                           tokens_out=50)
```

### CLI Evaluation

Batch evaluate Q&A pairs:

```bash
# Create a test file (CSV format)
echo "question,expected_context,expected_answer" > test.csv
echo "What is AI?,AI is artificial intelligence,AI stands for..." >> test.csv

# Run evaluation
ragtoolkit eval test.csv --output results.json --format json
```

### Configuration

Set up API keys and endpoints:

```bash
ragtoolkit config --api-url http://localhost:8000 --openai-key YOUR_KEY
```

## Environment Variables

- `DATABASE_URL`: PostgreSQL connection string (default: SQLite)
- `RAGTOOLKIT_API_KEY`: API key for authentication
- `OPENAI_API_KEY`: OpenAI API key for LLM-based evaluation

## Development

### Setup

```bash
git clone https://github.com/yourusername/ragtoolkit.git
cd ragtoolkit

# Install in development mode
pip install -e ".[dev]"

# Run tests
pytest

# Format code
black ragtoolkit/
isort ragtoolkit/
```

### Architecture

```
┌─────────────────┐    HTTP     ┌─────────────────┐
│   Your RAG App  │────────────▶│  RAG Toolkit    │
│ (LangChain etc) │   Traces    │  API (FastAPI)  │
└─────────────────┘◀────────────┴─────────────────┘
                                         │
                                         ▼
                               ┌─────────────────┐
                               │   PostgreSQL    │
                               └─────────────────┘
                                         │
                                         ▼
                               ┌─────────────────┐
                               │ React Dashboard │
                               └─────────────────┘
```

## API Reference

### Core Decorators

- `@trace`: Automatic tracing decorator
- `@trace(user_input_key="query")`: Custom input extraction

### Manual API

- `tracker.trace_context()`: Context manager for manual tracing
- `tracker.add_retrieved_chunks()`: Add retrieval results
- `tracker.set_model_output()`: Set LLM response

### CLI Commands

- `ragtoolkit eval <file>`: Batch evaluation
- `ragtoolkit test`: Generate test traces
- `ragtoolkit config`: Manage configuration

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests: `pytest`
5. Submit a pull request

## License

MIT License - see LICENSE file for details.

## Support

- 📖 [Documentation](https://ragtoolkit.readthedocs.io/)
- 🐛 [Issues](https://github.com/yourusername/ragtoolkit/issues)
- 💬 [Discussions](https://github.com/yourusername/ragtoolkit/discussions) 