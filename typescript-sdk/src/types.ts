/**
 * Type definitions for RAG Toolkit TypeScript SDK
 */

export interface TraceData {
  trace_id: string;
  timestamp: number;
  project: string;
  user_input?: string;
  retrieved_chunks: ChunkData[];
  retrieval_scores: number[];
  prompts: string[];
  model_output?: string;
  model_name?: string;
  response_latency_ms?: number;
  tokens_in?: number;
  tokens_out?: number;
  metadata: Record<string, any>;
  error?: string;
}

export interface ChunkData {
  text: string;
  source: string;
  metadata?: Record<string, any>;
}

export interface RAGToolkitConfig {
  apiUrl: string;
  apiKey?: string;
  project: string;
}

export interface TracerOptions {
  apiUrl?: string;
  apiKey?: string;
  project?: string;
  userInputKey?: string;
  outputKey?: string;
}

export interface TraceContext {
  trace: TraceData;
  addRetrievedChunks: (chunks: ChunkData[], scores?: number[]) => void;
  addPrompt: (prompt: string) => void;
  setModelOutput: (output: string, modelName?: string, tokensIn?: number, tokensOut?: number) => void;
  setError: (error: string) => void;
}

// HTTP Client interfaces
export interface HTTPResponse {
  ok: boolean;
  status: number;
  statusText: string;
  json(): Promise<any>;
  text(): Promise<string>;
}

export interface HTTPRequestOptions {
  method?: string;
  headers?: Record<string, string>;
  body?: string;
}

export interface HTTPClient {
  post(url: string, options: HTTPRequestOptions): Promise<HTTPResponse>;
}

// LLM Provider types
export interface OpenAIMessage {
  role: 'system' | 'user' | 'assistant';
  content: string;
}

export interface OpenAICompletionRequest {
  model: string;
  messages: OpenAIMessage[];
  temperature?: number;
  max_tokens?: number;
  [key: string]: any;
}

export interface OpenAICompletionResponse {
  choices: Array<{
    message: {
      content: string;
      role: string;
    };
  }>;
  usage?: {
    prompt_tokens: number;
    completion_tokens: number;
    total_tokens: number;
  };
  model: string;
}

export interface AnthropicMessage {
  role: 'user' | 'assistant';
  content: string;
}

export interface AnthropicCompletionRequest {
  model: string;
  messages: AnthropicMessage[];
  max_tokens: number;
  system?: string;
  temperature?: number;
  [key: string]: any;
}

export interface AnthropicCompletionResponse {
  content: Array<{
    text: string;
    type: string;
  }>;
  usage?: {
    input_tokens: number;
    output_tokens: number;
  };
  model: string;
} 