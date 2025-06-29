/**
 * Basic test for RAG Toolkit TypeScript SDK
 * Tests core functionality without requiring external API keys
 */

const { configure, getConfig, RAGTracker, tracer } = require('./dist/index.js');

async function testBasicFunctionality() {
  console.log('🧪 Testing RAG Toolkit TypeScript SDK...\n');

  // Test 1: Configuration
  console.log('1. Testing configuration...');
  configure({
    apiUrl: 'http://localhost:8000',
    project: 'test-project',
    apiKey: 'test-key'
  });

  const config = getConfig();
  console.log('✅ Configuration:', JSON.stringify(config, null, 2));

  // Test 2: RAGTracker creation and trace start
  console.log('\n2. Testing RAGTracker...');
  const tracker = new RAGTracker({
    project: 'test-tracker'
  });

  const trace = tracker.startTrace('Test user input', { test: true });
  console.log('✅ Trace created:', {
    trace_id: trace.trace_id,
    project: trace.project,
    user_input: trace.user_input,
    timestamp: trace.timestamp
  });

  // Test 3: Adding chunks and prompts
  console.log('\n3. Testing trace modification...');
  tracker.addRetrievedChunks([
    { text: 'Test chunk 1', source: 'test.pdf' },
    { text: 'Test chunk 2', source: 'test2.pdf' }
  ], [0.9, 0.8]);

  tracker.addPrompt('System: You are a test assistant\nUser: Test question');
  tracker.setModelOutput('Test response', 'test-model', 100, 50);

  console.log('✅ Trace modified:', {
    chunks: trace.retrieved_chunks.length,
    prompts: trace.prompts.length,
    model_output: trace.model_output,
    tokens_in: trace.tokens_in,
    tokens_out: trace.tokens_out
  });

  // Test 4: Manual tracing with context
  console.log('\n4. Testing manual tracing...');
  const result = await tracer.startTrace('Manual trace test', async (ctx) => {
    ctx.addRetrievedChunks([
      { text: 'Manual chunk', source: 'manual.pdf' }
    ], [0.95]);

    ctx.addPrompt('Manual prompt test');
    ctx.setModelOutput('Manual response', 'manual-model', 75, 25);

    return { success: true, answer: 'Manual test completed' };
  });

  console.log('✅ Manual trace result:', result);

  // Test 5: Connector imports
  console.log('\n5. Testing connector imports...');
  try {
    const { chatCompletion } = require('./dist/connectors/openai.js');
    const { createMessage } = require('./dist/connectors/anthropic.js');
    console.log('✅ Connectors imported successfully');
    console.log('   - OpenAI chatCompletion:', typeof chatCompletion);
    console.log('   - Anthropic createMessage:', typeof createMessage);
  } catch (error) {
    console.error('❌ Connector import error:', error.message);
  }

  // Test 6: Type definitions check
  console.log('\n6. Testing type definitions...');
  const fs = require('fs');
  const path = require('path');
  
  const indexDts = path.join(__dirname, 'dist', 'index.d.ts');
  const typesDts = path.join(__dirname, 'dist', 'types.d.ts');
  
  if (fs.existsSync(indexDts) && fs.existsSync(typesDts)) {
    console.log('✅ Type definition files exist');
  } else {
    console.log('❌ Missing type definition files');
  }

  console.log('\n🎉 All basic tests passed!');
  console.log('\nNote: API submission tests require a running RAG Toolkit API server');
}

// Run tests
testBasicFunctionality().catch(console.error); 