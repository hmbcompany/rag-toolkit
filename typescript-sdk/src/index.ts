/**
 * RAG Toolkit TypeScript/JavaScript SDK
 * Observability and evaluation for RAG applications
 */

// Core exports
export { configure, getConfig, RAGTracker, trace, tracer } from './tracer';

// Type exports
export type {
  TraceData,
  ChunkData,
  RAGToolkitConfig,
  TracerOptions,
  TraceContext,
  HTTPResponse,
  HTTPRequestOptions,
  HTTPClient,
  OpenAIMessage,
  OpenAICompletionRequest,
  OpenAICompletionResponse,
  AnthropicMessage,
  AnthropicCompletionRequest,
  AnthropicCompletionResponse
} from './types';

// LLM Connectors
export * as openai from './connectors/openai';
export * as anthropic from './connectors/anthropic';

// Convenience re-exports for direct access
export {
  chatCompletion as openaiChatCompletion,
  wrapOpenAIClient,
  createTracedOpenAI,
  openaiUtils
} from './connectors/openai';

export {
  createMessage as anthropicCreateMessage,
  wrapAnthropicClient,
  createTracedAnthropic,
  anthropicUtils
} from './connectors/anthropic';

import {
  configure as configureImport,
  getConfig as getConfigImport,
  RAGTracker as RAGTrackerImport,
  trace as traceImport,
  tracer as tracerImport
} from './tracer';

import * as openaiConnector from './connectors/openai';
import * as anthropicConnector from './connectors/anthropic';

// Default export
export default {
  configure: configureImport,
  getConfig: getConfigImport,
  RAGTracker: RAGTrackerImport,
  trace: traceImport,
  tracer: tracerImport,
  openai: openaiConnector,
  anthropic: anthropicConnector
}; 