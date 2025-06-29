/**
 * Core tracing functionality for RAG applications - TypeScript SDK
 */

import { randomUUID } from 'crypto';

// Use Node.js built-in fetch (Node 18+) or fallback
const globalFetch = globalThis.fetch || (() => {
  throw new Error('fetch is not available. Please use Node.js 18+ or install a polyfill.');
});
import {
  TraceData,
  ChunkData,
  RAGToolkitConfig,
  TracerOptions,
  TraceContext,
  HTTPResponse,
  HTTPRequestOptions
} from './types';

// Global configuration
let globalConfig: RAGToolkitConfig = {
  apiUrl: 'http://localhost:8000',
  project: 'default'
};

/**
 * Configure the global RAG Toolkit settings
 */
export function configure(config: Partial<RAGToolkitConfig>): void {
  globalConfig = { ...globalConfig, ...config };
}

/**
 * Get current configuration
 */
export function getConfig(): RAGToolkitConfig {
  return { ...globalConfig };
}

/**
 * RAG Tracker class for managing traces
 */
export class RAGTracker {
  private config: RAGToolkitConfig;
  private currentTrace: TraceData | null = null;

  constructor(options?: TracerOptions) {
    this.config = {
      apiUrl: options?.apiUrl || globalConfig.apiUrl,
      apiKey: options?.apiKey || globalConfig.apiKey,
      project: options?.project || globalConfig.project
    };
  }

  /**
   * Start a new trace
   */
  startTrace(userInput?: string, metadata: Record<string, any> = {}): TraceData {
    const trace: TraceData = {
      trace_id: randomUUID(),
      timestamp: Date.now() / 1000,
      project: this.config.project,
      user_input: userInput,
      retrieved_chunks: [],
      retrieval_scores: [],
      prompts: [],
      metadata
    };

    this.currentTrace = trace;
    return trace;
  }

  /**
   * Add retrieved chunks to current trace
   */
  addRetrievedChunks(chunks: ChunkData[], scores?: number[]): void {
    if (!this.currentTrace) return;

    this.currentTrace.retrieved_chunks.push(...chunks);
    if (scores) {
      this.currentTrace.retrieval_scores.push(...scores);
    }
  }

  /**
   * Add prompt to current trace
   */
  addPrompt(prompt: string): void {
    if (!this.currentTrace) return;
    this.currentTrace.prompts.push(prompt);
  }

  /**
   * Set model output and metadata
   */
  setModelOutput(
    output: string,
    modelName?: string,
    tokensIn?: number,
    tokensOut?: number,
    latencyMs?: number
  ): void {
    if (!this.currentTrace) return;

    this.currentTrace.model_output = output;
    if (modelName) this.currentTrace.model_name = modelName;
    if (tokensIn) this.currentTrace.tokens_in = tokensIn;
    if (tokensOut) this.currentTrace.tokens_out = tokensOut;
    if (latencyMs) this.currentTrace.response_latency_ms = latencyMs;
  }

  /**
   * Set error information
   */
  setError(error: string): void {
    if (!this.currentTrace) return;
    this.currentTrace.error = error;
  }

  /**
   * Submit trace to API
   */
  async submitTrace(trace?: TraceData): Promise<boolean> {
    const traceToSubmit = trace || this.currentTrace;
    if (!traceToSubmit) {
      console.warn('No trace data to submit');
      return false;
    }

    try {
      // Calculate response latency if not set
      if (!traceToSubmit.response_latency_ms) {
        traceToSubmit.response_latency_ms = (Date.now() / 1000 - traceToSubmit.timestamp) * 1000;
      }

      const headers: Record<string, string> = {
        'Content-Type': 'application/json'
      };

      if (this.config.apiKey) {
        headers['Authorization'] = `Bearer ${this.config.apiKey}`;
      }

      const response = await globalFetch(`${this.config.apiUrl}/api/v1/traces`, {
        method: 'POST',
        headers,
        body: JSON.stringify(traceToSubmit)
      });

      if (response.ok) {
        console.debug(`Trace ${traceToSubmit.trace_id} submitted successfully`);
        return true;
      } else {
        console.error(`Failed to submit trace: ${response.status} - ${await response.text()}`);
        return false;
      }
    } catch (error) {
      console.error('Error submitting trace:', error);
      return false;
    }
  }

  /**
   * Create a trace context for manual tracing
   */
  async traceContext<T>(
    userInput?: string,
    metadata: Record<string, any> = {}
  ): Promise<{ context: TraceContext; execute: (fn: (ctx: TraceContext) => Promise<T>) => Promise<T> }> {
    const trace = this.startTrace(userInput, metadata);
    const startTime = Date.now();

    const context: TraceContext = {
      trace,
      addRetrievedChunks: (chunks: ChunkData[], scores?: number[]) => {
        this.addRetrievedChunks(chunks, scores);
      },
      addPrompt: (prompt: string) => {
        this.addPrompt(prompt);
      },
      setModelOutput: (output: string, modelName?: string, tokensIn?: number, tokensOut?: number) => {
        this.setModelOutput(output, modelName, tokensIn, tokensOut);
      },
      setError: (error: string) => {
        this.setError(error);
      }
    };

    const execute = async (fn: (ctx: TraceContext) => Promise<T>): Promise<T> => {
      try {
        const result = await fn(context);
        return result;
      } catch (error) {
        this.setError(error instanceof Error ? error.message : String(error));
        throw error;
      } finally {
        trace.response_latency_ms = Date.now() - startTime;
        // Submit trace in background
        this.submitTrace(trace).catch(console.error);
        this.currentTrace = null;
      }
    };

    return { context, execute };
  }
}

// Global tracker instance
let globalTracker: RAGTracker | null = null;

/**
 * Get or create global tracker
 */
function getGlobalTracker(): RAGTracker {
  if (!globalTracker) {
    globalTracker = new RAGTracker();
  }
  return globalTracker;
}

/**
 * Decorator function for automatic tracing
 */
export function trace<T extends (...args: any[]) => any>(
  options?: TracerOptions
): (target: any, propertyKey: string, descriptor: PropertyDescriptor) => void;
export function trace<T extends (...args: any[]) => any>(
  fn: T
): (...args: Parameters<T>) => Promise<ReturnType<T>>;
export function trace<T extends (...args: any[]) => any>(
  fnOrOptions?: T | TracerOptions
): any {
  // Handle both decorator and direct function usage
  if (typeof fnOrOptions === 'function') {
    // Direct function wrapping
    return wrapFunction(fnOrOptions, {});
  } else {
    // Decorator usage
    const options = fnOrOptions || {};
    return function (target: any, propertyKey: string, descriptor: PropertyDescriptor) {
      const originalMethod = descriptor.value;
      descriptor.value = wrapFunction(originalMethod, options);
      return descriptor;
    };
  }
}

/**
 * Wrap a function with tracing
 */
function wrapFunction<T extends (...args: any[]) => any>(
  fn: T,
  options: TracerOptions
): (...args: Parameters<T>) => Promise<ReturnType<T>> {
  return async function (...args: Parameters<T>): Promise<ReturnType<T>> {
    const tracker = getGlobalTracker();
    
    // Extract user input
    let userInput: string | undefined;
    if (options.userInputKey && args.length > 0) {
      const firstArg = args[0];
      if (typeof firstArg === 'object' && firstArg !== null) {
        userInput = firstArg[options.userInputKey];
      }
    } else if (args.length > 0 && typeof args[0] === 'string') {
      userInput = args[0];
    }

    const { context, execute } = await tracker.traceContext(userInput);

    return execute(async (ctx) => {
      const result = await (fn(...args) as any) as ReturnType<T>;
      
      // Extract output if specified
      if (options.outputKey && typeof result === 'object' && result !== null) {
        const output = (result as any)[options.outputKey];
        if (typeof output === 'string') {
          ctx.setModelOutput(output);
        }
      } else if (typeof result === 'string') {
        ctx.setModelOutput(result);
      }

      return result;
    }) as Promise<ReturnType<T>>;
  };
}

/**
 * Manual tracing utilities
 */
export const tracer = {
  /**
   * Start a manual trace context
   */
  async startTrace<T>(
    userInput?: string,
    fn?: (ctx: TraceContext) => Promise<T>
  ): Promise<T | TraceContext> {
    const tracker = getGlobalTracker();
    const { context, execute } = await tracker.traceContext(userInput);

    if (fn) {
      return execute(fn) as Promise<T>;
    } else {
      return context as TraceContext;
    }
  },

  /**
   * Add chunks to current trace
   */
  addChunks(chunks: ChunkData[], scores?: number[]): void {
    const tracker = getGlobalTracker();
    tracker.addRetrievedChunks(chunks, scores);
  },

  /**
   * Add prompt to current trace
   */
  addPrompt(prompt: string): void {
    const tracker = getGlobalTracker();
    tracker.addPrompt(prompt);
  },

  /**
   * Set model output
   */
  setOutput(output: string, modelName?: string, tokensIn?: number, tokensOut?: number): void {
    const tracker = getGlobalTracker();
    tracker.setModelOutput(output, modelName, tokensIn, tokensOut);
  }
}; 