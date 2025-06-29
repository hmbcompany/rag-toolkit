/**
 * OpenAI connector with automatic RAG tracing - TypeScript SDK
 */

import {
  OpenAIMessage,
  OpenAICompletionRequest,
  OpenAICompletionResponse,
  ChunkData
} from '../types';
import { tracer } from '../tracer';

/**
 * Traced OpenAI Chat Completion function
 * Drop-in replacement for openai.chat.completions.create()
 */
export async function chatCompletion(
  params: OpenAICompletionRequest,
  openaiClient?: any
): Promise<OpenAICompletionResponse> {
  const userMessage = params.messages.find((m: OpenAIMessage) => m.role === 'user');
  const userInput = userMessage?.content || 'OpenAI Chat Completion';

  return tracer.startTrace(userInput, async (ctx) => {
    const startTime = Date.now();

    try {
      // Add prompt to trace
      const fullPrompt = params.messages.map((m: OpenAIMessage) => `${m.role}: ${m.content}`).join('\n');
      ctx.addPrompt(fullPrompt);

      let response: OpenAICompletionResponse;

      if (openaiClient) {
        // Use provided client
        response = await openaiClient.chat.completions.create(params);
      } else {
        // Try to use global OpenAI client if available
        try {
          // @ts-ignore - OpenAI might be available globally
          const OpenAI = require('openai');
          const client = new OpenAI();
          response = await client.chat.completions.create(params);
        } catch (error) {
          throw new Error('OpenAI client not provided and global OpenAI not available. Install openai package or pass client.');
        }
      }

      // Extract response data
      const output = response.choices[0]?.message?.content || '';
      const tokensIn = response.usage?.prompt_tokens;
      const tokensOut = response.usage?.completion_tokens;
      const latencyMs = Date.now() - startTime;

      ctx.setModelOutput(output, params.model, tokensIn, tokensOut);

      return response;
    } catch (error) {
      ctx.setError(error instanceof Error ? error.message : String(error));
      throw error;
    }
  }) as Promise<OpenAICompletionResponse>;
}

/**
 * Wrap an existing OpenAI client with automatic tracing
 */
export function wrapOpenAIClient(client: any): any {
  const originalCreate = client.chat.completions.create.bind(client.chat.completions);

  client.chat.completions.create = async (params: OpenAICompletionRequest) => {
    return chatCompletion(params, { chat: { completions: { create: originalCreate } } });
  };

  return client;
}

/**
 * Create a traced OpenAI client factory
 */
export function createTracedOpenAI(OpenAI: any, options?: any): any {
  const client = new OpenAI(options);
  return wrapOpenAIClient(client);
}

/**
 * RAG-specific utilities for OpenAI
 */
export const openaiUtils = {
  /**
   * Helper to add retrieved chunks before OpenAI call
   */
  async chatCompletionWithRAG(
    params: OpenAICompletionRequest,
    retrievedChunks: ChunkData[],
    scores?: number[],
    openaiClient?: any
  ): Promise<OpenAICompletionResponse> {
    const userMessage = params.messages.find((m: OpenAIMessage) => m.role === 'user');
    const userInput = userMessage?.content || 'OpenAI RAG Query';

    return tracer.startTrace(userInput, async (ctx) => {
      // Add retrieved chunks to trace
      ctx.addRetrievedChunks(retrievedChunks, scores);

      // Modify the prompt to include context
      const context = retrievedChunks.map(chunk => chunk.text).join('\n\n');
      const modifiedMessages = [...params.messages];
      
      // Find the last user message and enhance it with context
      const lastUserMsgIndex = modifiedMessages.map(m => m.role).lastIndexOf('user');
      if (lastUserMsgIndex !== -1) {
        modifiedMessages[lastUserMsgIndex] = {
          ...modifiedMessages[lastUserMsgIndex],
          content: `Context:\n${context}\n\nQuestion: ${modifiedMessages[lastUserMsgIndex].content}`
        };
      }

      const modifiedParams = { ...params, messages: modifiedMessages };
      
      // Call the regular traced completion
      return chatCompletion(modifiedParams, openaiClient);
    }) as Promise<OpenAICompletionResponse>;
  }
};

// Export types for convenience
export type { OpenAIMessage, OpenAICompletionRequest, OpenAICompletionResponse }; 