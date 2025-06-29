# RAG Toolkit TypeScript/JavaScript SDK

TypeScript/JavaScript SDK for [RAG Toolkit](https://github.com/hmbcompany/rag-toolkit) - observability and evaluation for RAG applications.

## Installation

```bash
npm install @ragtoolkit/sdk
```

## Quick Start

### Configuration

```typescript
import { configure } from '@ragtoolkit/sdk';

// Configure once at the start of your application
configure({
  apiUrl: 'http://localhost:8000',  // Your RAG Toolkit API URL
  apiKey: 'your-api-key',           // Optional API key
  project: 'my-rag-project'         // Project name
});
```

### Basic Usage with OpenAI

```typescript
import { openaiChatCompletion } from '@ragtoolkit/sdk';

// Drop-in replacement for OpenAI chat completion
const response = await openaiChatCompletion({
  model: 'gpt-4',
  messages: [
    { role: 'user', content: 'What is machine learning?' }
  ]
});
// Automatically traced to RAG Toolkit!
```

### Basic Usage with Anthropic

```typescript
import { anthropicCreateMessage } from '@ragtoolkit/sdk';

// Drop-in replacement for Anthropic messages
const response = await anthropicCreateMessage({
  model: 'claude-3-sonnet-20240229',
  max_tokens: 1000,
  messages: [
    { role: 'user', content: 'Explain quantum computing' }
  ]
});
// Automatically traced to RAG Toolkit!
```

## Usage Patterns

### 1. Drop-in Replacement Functions

Replace your LLM calls with traced versions:

```typescript
import { openaiChatCompletion, anthropicCreateMessage } from '@ragtoolkit/sdk';

// Instead of openai.chat.completions.create()
const openaiResponse = await openaiChatCompletion(params);

// Instead of anthropic.messages.create()
const anthropicResponse = await anthropicCreateMessage(params);
```

### 2. Client Wrapping

Wrap existing clients to add automatic tracing:

```typescript
import OpenAI from 'openai';
import { wrapOpenAIClient } from '@ragtoolkit/sdk';

const openai = new OpenAI({ apiKey: process.env.OPENAI_API_KEY });
const tracedOpenAI = wrapOpenAIClient(openai);

// All calls through tracedOpenAI are automatically traced
const response = await tracedOpenAI.chat.completions.create({
  model: 'gpt-4',
  messages: [{ role: 'user', content: 'Hello!' }]
});
```

### 3. Factory Pattern

Create traced clients from the start:

```typescript
import OpenAI from 'openai';
import Anthropic from '@anthropic-ai/sdk';
import { createTracedOpenAI, createTracedAnthropic } from '@ragtoolkit/sdk';

const tracedOpenAI = createTracedOpenAI(OpenAI, { 
  apiKey: process.env.OPENAI_API_KEY 
});

const tracedAnthropic = createTracedAnthropic(Anthropic, {
  apiKey: process.env.ANTHROPIC_API_KEY
});
```

## RAG-Specific Features

### Adding Retrieved Context

```typescript
import { openaiUtils } from '@ragtoolkit/sdk';

const retrievedChunks = [
  { text: 'Machine learning is...', source: 'doc1.pdf' },
  { text: 'AI algorithms can...', source: 'doc2.pdf' }
];
const scores = [0.95, 0.87];

const response = await openaiUtils.chatCompletionWithRAG({
  model: 'gpt-4',
  messages: [{ role: 'user', content: 'What is ML?' }]
}, retrievedChunks, scores);
// Context automatically added to prompt and traced
```

### Manual Tracing

For more control over tracing:

```typescript
import { tracer } from '@ragtoolkit/sdk';

const result = await tracer.startTrace('User question', async (ctx) => {
  // Add retrieved chunks
  ctx.addRetrievedChunks([
    { text: 'Context...', source: 'file.pdf' }
  ], [0.9]);
  
  // Add prompts
  ctx.addPrompt('System: You are a helpful assistant\nUser: Question');
  
  // Your LLM call
  const response = await callLLM();
  
  // Set output
  ctx.setModelOutput(response.text, 'gpt-4', 100, 50);
  
  return response;
});
```

### Function Decorators

Automatically trace functions:

```typescript
import { trace } from '@ragtoolkit/sdk';

class RAGService {
  @trace({ userInputKey: 'query', outputKey: 'answer' })
  async answerQuestion(query: string): Promise<{ answer: string }> {
    // Your RAG logic here
    return { answer: 'Response...' };
  }
}
```

## API Reference

### Core Functions

- `configure(config)` - Configure global settings
- `RAGTracker` - Main tracing class
- `trace()` - Function decorator for automatic tracing
- `tracer` - Manual tracing utilities

### OpenAI Connector

- `openaiChatCompletion()` - Drop-in replacement
- `wrapOpenAIClient()` - Wrap existing client
- `createTracedOpenAI()` - Factory for traced client
- `openaiUtils.chatCompletionWithRAG()` - RAG-specific helper

### Anthropic Connector

- `anthropicCreateMessage()` - Drop-in replacement
- `wrapAnthropicClient()` - Wrap existing client
- `createTracedAnthropic()` - Factory for traced client
- `anthropicUtils.createMessageWithRAG()` - RAG-specific helper

## TypeScript Support

This SDK is written in TypeScript and includes full type definitions for:

- All API interfaces
- LLM provider request/response types
- Tracing metadata structures
- Configuration options

## Development Setup

The TypeScript SDK requires some additional setup for the build environment:

```bash
cd typescript-sdk
npm install
npm run build
```

Note: Some module resolution fixes may be needed for crypto and node-fetch imports in the current implementation.

## License

MIT - see [LICENSE](../LICENSE) file. 