/**
 * Anthropic connector with automatic RAG tracing - TypeScript SDK
 */

import {
  AnthropicMessage,
  AnthropicCompletionRequest,
  AnthropicCompletionResponse,
  ChunkData
} from '../types';
import { tracer } from '../tracer';

/**
 * Traced Anthropic Messages function
 * Drop-in replacement for anthropic.messages.create()
 */
export async function createMessage(
  params: AnthropicCompletionRequest,
  anthropicClient?: any
): Promise<AnthropicCompletionResponse> {
  const userMessage = params.messages.find((m: AnthropicMessage) => m.role === 'user');
  const userInput = userMessage?.content || 'Anthropic Message';

  return tracer.startTrace(userInput, async (ctx) => {
    const startTime = Date.now();

    try {
      // Add prompt to trace
      let fullPrompt = '';
      if (params.system) {
        fullPrompt += `system: ${params.system}\n`;
      }
      fullPrompt += params.messages.map((m: AnthropicMessage) => `${m.role}: ${m.content}`).join('\n');
      ctx.addPrompt(fullPrompt);

      let response: AnthropicCompletionResponse;

      if (anthropicClient) {
        // Use provided client
        response = await anthropicClient.messages.create(params);
      } else {
        // Try to use global Anthropic client if available
        try {
          // @ts-ignore - Anthropic might be available globally
          const Anthropic = require('@anthropic-ai/sdk');
          const client = new Anthropic();
          response = await client.messages.create(params);
        } catch (error) {
          throw new Error('Anthropic client not provided and global Anthropic not available. Install @anthropic-ai/sdk package or pass client.');
        }
      }

      // Extract response data
      const output = response.content[0]?.text || '';
      const tokensIn = response.usage?.input_tokens;
      const tokensOut = response.usage?.output_tokens;
      const latencyMs = Date.now() - startTime;

      ctx.setModelOutput(output, params.model, tokensIn, tokensOut);

      return response;
    } catch (error) {
      ctx.setError(error instanceof Error ? error.message : String(error));
      throw error;
    }
  }) as Promise<AnthropicCompletionResponse>;
}

/**
 * Wrap an existing Anthropic client with automatic tracing
 */
export function wrapAnthropicClient(client: any): any {
  const originalCreate = client.messages.create.bind(client.messages);

  client.messages.create = async (params: AnthropicCompletionRequest) => {
    return createMessage(params, { messages: { create: originalCreate } });
  };

  return client;
}

/**
 * Create a traced Anthropic client factory
 */
export function createTracedAnthropic(Anthropic: any, options?: any): any {
  const client = new Anthropic(options);
  return wrapAnthropicClient(client);
}

/**
 * RAG-specific utilities for Anthropic
 */
export const anthropicUtils = {
  /**
   * Helper to add retrieved chunks before Anthropic call
   */
  async createMessageWithRAG(
    params: AnthropicCompletionRequest,
    retrievedChunks: ChunkData[],
    scores?: number[],
    anthropicClient?: any
  ): Promise<AnthropicCompletionResponse> {
    const userMessage = params.messages.find((m: AnthropicMessage) => m.role === 'user');
    const userInput = userMessage?.content || 'Anthropic RAG Query';

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
      
      // Call the regular traced message creation
      return createMessage(modifiedParams, anthropicClient);
    }) as Promise<AnthropicCompletionResponse>;
  }
};

// Export types for convenience
export type { AnthropicMessage, AnthropicCompletionRequest, AnthropicCompletionResponse }; 