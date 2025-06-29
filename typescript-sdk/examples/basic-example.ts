/**
 * Basic RAG Toolkit TypeScript Example
 */

import { configure, openaiChatCompletion, anthropicCreateMessage, tracer } from '@ragtoolkit/sdk';

// Configure RAG Toolkit
configure({
  apiUrl: 'http://localhost:8000',
  project: 'typescript-example'
});

// Example 1: OpenAI with automatic tracing
async function exampleOpenAI() {
  console.log('🤖 OpenAI Example with RAG Toolkit');
  
  try {
    const response = await openaiChatCompletion({
      model: 'gpt-4',
      messages: [
        { role: 'system', content: 'You are a helpful AI assistant.' },
        { role: 'user', content: 'Explain what RAG is in one sentence.' }
      ],
      temperature: 0.7,
      max_tokens: 100
    });
    
    console.log('Response:', response.choices[0]?.message?.content);
    console.log('✅ Trace automatically submitted to RAG Toolkit');
  } catch (error) {
    console.error('Error:', error);
  }
}

// Example 2: Anthropic with automatic tracing
async function exampleAnthropic() {
  console.log('\n🤖 Anthropic Example with RAG Toolkit');
  
  try {
    const response = await anthropicCreateMessage({
      model: 'claude-3-sonnet-20240229',
      max_tokens: 100,
      messages: [
        { role: 'user', content: 'What are the benefits of retrieval-augmented generation?' }
      ]
    });
    
    console.log('Response:', response.content[0]?.text);
    console.log('✅ Trace automatically submitted to RAG Toolkit');
  } catch (error) {
    console.error('Error:', error);
  }
}

// Example 3: Manual tracing with retrieved context
async function exampleManualRAGTracing() {
  console.log('\n📚 Manual RAG Tracing Example');
  
  const result = await tracer.startTrace('What is vector search?', async (ctx) => {
    // Simulate retrieved chunks
    const retrievedChunks = [
      {
        text: 'Vector search is a method of finding similar items by comparing their vector representations in a high-dimensional space.',
        source: 'vector_search_guide.pdf',
        metadata: { page: 1, confidence: 0.95 }
      },
      {
        text: 'In RAG systems, vector search helps find relevant documents to provide context for language model responses.',
        source: 'rag_overview.pdf',
        metadata: { page: 3, confidence: 0.87 }
      }
    ];
    
    // Add chunks to trace
    ctx.addRetrievedChunks(retrievedChunks, [0.95, 0.87]);
    
    // Build prompt with context
    const context = retrievedChunks.map(chunk => chunk.text).join('\n\n');
    const prompt = `Context:\n${context}\n\nQuestion: What is vector search?\n\nAnswer:`;
    
    ctx.addPrompt(prompt);
    
    // Simulate LLM response (in real code, you'd call your LLM here)
    const mockResponse = 'Vector search is a powerful technique used in RAG systems to find semantically similar documents by comparing vector representations in high-dimensional space.';
    
    ctx.setModelOutput(mockResponse, 'gpt-4', 150, 75);
    
    return { answer: mockResponse };
  });
  
  console.log('Answer:', result.answer);
  console.log('✅ RAG trace with retrieved context submitted');
}

// Example 4: Client wrapping
async function exampleClientWrapping() {
  console.log('\n🔧 Client Wrapping Example');
  
  try {
    // This would work if you have OpenAI installed:
    // import OpenAI from 'openai';
    // import { wrapOpenAIClient } from '@ragtoolkit/sdk';
    // 
    // const openai = new OpenAI({ apiKey: process.env.OPENAI_API_KEY });
    // const tracedOpenAI = wrapOpenAIClient(openai);
    // 
    // const response = await tracedOpenAI.chat.completions.create({
    //   model: 'gpt-3.5-turbo',
    //   messages: [{ role: 'user', content: 'Hello!' }]
    // });
    
    console.log('Client wrapping allows you to trace existing OpenAI/Anthropic clients');
    console.log('Just wrap your client and all calls are automatically traced!');
  } catch (error) {
    console.error('Error:', error);
  }
}

// Run examples
async function main() {
  console.log('🚀 RAG Toolkit TypeScript SDK Examples\n');
  
  // Note: These examples require actual API keys to work
  // Uncomment the lines below if you have OpenAI/Anthropic API keys
  
  // await exampleOpenAI();
  // await exampleAnthropic();
  await exampleManualRAGTracing();
  await exampleClientWrapping();
  
  console.log('\n✨ Examples completed! Check your RAG Toolkit dashboard for traces.');
}

// Run if this file is executed directly
if (require.main === module) {
  main().catch(console.error);
}

export {
  exampleOpenAI,
  exampleAnthropic,
  exampleManualRAGTracing,
  exampleClientWrapping
}; 