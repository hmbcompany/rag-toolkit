import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { 
  Copy, 
  Check, 
  ExternalLink, 
  Code, 
  Zap 
} from 'lucide-react';

const IntegrationWizard = () => {
  const [config, setConfig] = useState({
    language: 'python',
    framework: 'langchain',
    llm: 'openai',
    vectorStore: 'none',
    project: 'default'
  });
  
  const [copied, setCopied] = useState(false);
  const [userConfig, setUserConfig] = useState(null);
  const [loading, setLoading] = useState(false);

  // Load user config from API
  useEffect(() => {
    fetchUserConfig();
  }, []);

  const fetchUserConfig = async () => {
    try {
      setLoading(true);
      const response = await fetch('/api/config');
      if (response.ok) {
        const data = await response.json();
        setUserConfig(data);
        setConfig(prev => ({ ...prev, project: data.project || 'default' }));
      }
    } catch (error) {
      console.error('Failed to load config:', error);
    } finally {
      setLoading(false);
    }
  };

  const updateConfig = async (updates) => {
    try {
      await fetch('/api/config', {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(updates)
      });
    } catch (error) {
      console.error('Failed to update config:', error);
    }
  };

  const frameworks = {
    python: [
      { id: 'langchain', name: 'LangChain', popular: true },
      { id: 'llamaindex', name: 'LlamaIndex', popular: true },
      { id: 'plain', name: 'Plain Python', popular: false }
    ],
    javascript: [
      { id: 'langchain-js', name: 'LangChain.js', popular: true },
      { id: 'plain-js', name: 'Plain JavaScript', popular: false }
    ]
  };

  const llmProviders = [
    { id: 'openai', name: 'OpenAI (GPT-4)', popular: true },
    { id: 'anthropic', name: 'Anthropic (Claude)', popular: true },
    { id: 'gemini', name: 'Google Gemini', popular: false },
    { id: 'ollama', name: 'Ollama (Local)', popular: false }
  ];

  const vectorStores = [
    { id: 'none', name: 'None / In-Memory', popular: false },
    { id: 'pinecone', name: 'Pinecone', popular: true },
    { id: 'weaviate', name: 'Weaviate', popular: true },
    { id: 'chroma', name: 'ChromaDB', popular: false }
  ];

  const generateCode = () => {
    const { language, framework, llm, vectorStore, project } = config;
    const token = userConfig?.token || 'your-api-token';
    const apiUrl = userConfig?.api_url || 'http://localhost:8000';

    if (language === 'python') {
      return generatePythonCode(framework, llm, vectorStore, project, token, apiUrl);
    } else {
      return generateJavaScriptCode(framework, llm, vectorStore, project, token, apiUrl);
    }
  };

  const generatePythonCode = (framework, llm, vectorStore, project, token, apiUrl) => {
    let imports = ['from ragtoolkit import trace, configure_tracker'];
    let setup = [`configure_tracker(api_url="${apiUrl}", api_key="${token}", project="${project}")`];
    let example = '';

    // Framework-specific imports and setup
    if (framework === 'langchain') {
      if (llm === 'openai') {
        imports.push('from langchain_openai import ChatOpenAI');
        imports.push('from langchain.chains import RetrievalQA');
      } else if (llm === 'anthropic') {
        imports.push('from langchain_anthropic import ChatAnthropic');
      }
      
      if (vectorStore === 'pinecone') {
        imports.push('from langchain_pinecone import PineconeVectorStore');
        setup.push('# Initialize your Pinecone vector store');
        setup.push('vectorstore = PineconeVectorStore.from_existing_index("your-index")');
      }

      const retrievalLine = vectorStore !== 'none' ? 'retriever = vectorstore.as_retriever()' : '# Add your retrieval logic here';

      example = `
@trace
def ask_question(query: str) -> str:
    """Your RAG function with automatic tracing"""
    llm = ChatOpenAI(model="gpt-4")
    ${retrievalLine}
    
    # Your RAG logic here
    response = llm.invoke(query)
    return response.content`;

    } else if (framework === 'llamaindex') {
      imports.push('from llama_index.core import VectorStoreIndex, SimpleDirectoryReader');
      if (llm === 'openai') {
        imports.push('from llama_index.llms.openai import OpenAI');
      }
      
      example = `
@trace
def query_documents(question: str) -> str:
    """LlamaIndex RAG with tracing"""
    # Load your documents
    documents = SimpleDirectoryReader("data").load_data()
    index = VectorStoreIndex.from_documents(documents)
    
    query_engine = index.as_query_engine()
    response = query_engine.query(question)
    return str(response)`;

    } else {
      example = `
@trace
def my_rag_function(query: str) -> str:
    """Your custom RAG implementation"""
    # Add your retrieval logic
    # Add your LLM call
    # Return the response
    return "Your RAG response here"`;
    }

    const functionName = framework === 'llamaindex' ? 'query_documents' : framework === 'langchain' ? 'ask_question' : 'my_rag_function';
    const viewUrl = apiUrl.replace('localhost', '127.0.0.1');

    return `# RAG Toolkit Integration - ${framework}
${imports.join('\n')}

# Configure RAG Toolkit
${setup.join('\n')}
${example}

# Test your integration
if __name__ == "__main__":
    result = ${functionName}("What is the capital of France?")
    print(result)
    
    # View traces at: ${viewUrl}`;
  };

  const generateJavaScriptCode = (framework, llm, vectorStore, project, token, apiUrl) => {
    const viewUrl = apiUrl.replace('localhost', '127.0.0.1');
    
    return `// RAG Toolkit Integration - JavaScript
import { trace, configure } from '@ragtoolkit/sdk';

// Configure RAG Toolkit  
configure({
  apiUrl: "${apiUrl}",
  apiKey: "${token}",
  project: "${project}"
});

const ragFunction = trace(async (query) => {
  // Your RAG implementation here
  // Add LLM calls, vector search, etc.
  
  return "Your RAG response";
});

// Test your integration
ragFunction("What is the capital of France?")
  .then(result => console.log(result));
  
// View traces at: ${viewUrl}`;
  };

  const copyCode = async () => {
    const code = generateCode();
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error('Failed to copy:', err);
    }
  };

  const handleConfigChange = (key, value) => {
    const newConfig = { ...config, [key]: value };
    setConfig(newConfig);
    
    // Update server config
    if (key === 'project') {
      updateConfig({ project: value });
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">
            <Zap className="inline-block mr-2 text-blue-600" />
            Integration Wizard
          </h1>
          <p className="text-gray-600">
            Generate code snippets for your RAG application. Copy, paste, and start tracing in under 3 minutes.
          </p>
        </div>
      </div>

      <div className="grid lg:grid-cols-2 gap-8">
        {/* Configuration Panel */}
        <div className="space-y-6">
          <div className="bg-white p-6 rounded-lg shadow-sm border">
            <h2 className="text-lg font-semibold mb-4">Choose Your Stack</h2>
            
            {/* Language Selection */}
            <div className="mb-4">
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Programming Language
              </label>
              <div className="grid grid-cols-2 gap-2">
                {['python', 'javascript'].map(lang => (
                  <button
                    key={lang}
                    onClick={() => handleConfigChange('language', lang)}
                    className={`p-3 rounded-lg border-2 text-left transition-colors ${
                      config.language === lang
                        ? 'border-blue-500 bg-blue-50 text-blue-700'
                        : 'border-gray-200 hover:border-gray-300'
                    }`}
                  >
                    <div className="font-medium">
                      {lang === 'python' ? 'Python' : 'JavaScript'}
                    </div>
                    <div className="text-sm text-gray-500">
                      {lang === 'python' ? 'pip install ragtoolkit' : 'npm install @ragtoolkit/sdk'}
                    </div>
                  </button>
                ))}
              </div>
            </div>

            {/* Framework Selection */}
            <div className="mb-4">
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Framework / Library
              </label>
              <div className="space-y-2">
                {frameworks[config.language]?.map(framework => (
                  <button
                    key={framework.id}
                    onClick={() => handleConfigChange('framework', framework.id)}
                    className={`w-full p-3 rounded-lg border-2 text-left transition-colors ${
                      config.framework === framework.id
                        ? 'border-blue-500 bg-blue-50'
                        : 'border-gray-200 hover:border-gray-300'
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-medium">{framework.name}</span>
                      {framework.popular && (
                        <span className="px-2 py-1 bg-green-100 text-green-800 text-xs rounded-full">
                          Popular
                        </span>
                      )}
                    </div>
                  </button>
                ))}
              </div>
            </div>

            {/* LLM Provider */}
            <div className="mb-4">
              <label className="block text-sm font-medium text-gray-700 mb-2">
                LLM Provider
              </label>
              <div className="space-y-2">
                {llmProviders.map(provider => (
                  <button
                    key={provider.id}
                    onClick={() => handleConfigChange('llm', provider.id)}
                    className={`w-full p-3 rounded-lg border-2 text-left transition-colors ${
                      config.llm === provider.id
                        ? 'border-blue-500 bg-blue-50'
                        : 'border-gray-200 hover:border-gray-300'
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-medium">{provider.name}</span>
                      {provider.popular && (
                        <span className="px-2 py-1 bg-green-100 text-green-800 text-xs rounded-full">
                          Popular
                        </span>
                      )}
                    </div>
                  </button>
                ))}
              </div>
            </div>

            {/* Vector Store */}
            <div className="mb-4">
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Vector Store
              </label>
              <div className="space-y-2">
                {vectorStores.map(store => (
                  <button
                    key={store.id}
                    onClick={() => handleConfigChange('vectorStore', store.id)}
                    className={`w-full p-3 rounded-lg border-2 text-left transition-colors ${
                      config.vectorStore === store.id
                        ? 'border-blue-500 bg-blue-50'
                        : 'border-gray-200 hover:border-gray-300'
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-medium">{store.name}</span>
                      {store.popular && (
                        <span className="px-2 py-1 bg-green-100 text-green-800 text-xs rounded-full">
                          Popular
                        </span>
                      )}
                    </div>
                  </button>
                ))}
              </div>
            </div>

            {/* Project Name */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Project Name
              </label>
              <input
                type="text"
                value={config.project}
                onChange={(e) => handleConfigChange('project', e.target.value)}
                className="w-full p-3 border rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                placeholder="my-rag-app"
              />
            </div>
          </div>
        </div>

        {/* Code Panel */}
        <div className="space-y-6">
          <div className="bg-gray-900 rounded-lg overflow-hidden">
            <div className="flex items-center justify-between p-4 bg-gray-800">
              <div className="flex items-center space-x-2">
                <Code className="w-4 h-4 text-gray-400" />
                <span className="text-gray-300 text-sm font-medium">
                  Integration Code
                </span>
              </div>
              <button
                onClick={copyCode}
                className="flex items-center space-x-2 px-3 py-1 bg-blue-600 hover:bg-blue-700 text-white rounded-md transition-colors"
              >
                {copied ? (
                  <Check className="w-4 h-4" />
                ) : (
                  <Copy className="w-4 h-4" />
                )}
                <span className="text-sm">
                  {copied ? 'Copied!' : 'Copy'}
                </span>
              </button>
            </div>
            <pre className="p-4 text-sm text-gray-300 overflow-x-auto">
              <code>{generateCode()}</code>
            </pre>
          </div>

          {/* Next Steps */}
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
            <h3 className="font-semibold text-blue-900 mb-2">Next Steps:</h3>
            <ol className="list-decimal list-inside space-y-1 text-sm text-blue-800">
              <li>Copy the code above</li>
              <li>Install dependencies: <code className="bg-blue-100 px-1 rounded">pip install ragtoolkit</code></li>
              <li>Paste into your application</li>
              <li>Run your code - traces will appear automatically!</li>
            </ol>
          </div>

          {/* Helpful Links */}
          <div className="bg-white p-4 rounded-lg border">
            <h3 className="font-semibold text-gray-900 mb-3">Helpful Resources</h3>
            <div className="space-y-2">
              <a
                href="/docs/quickstart"
                className="flex items-center text-blue-600 hover:text-blue-800 text-sm"
              >
                <ExternalLink className="w-4 h-4 mr-2" />
                Quickstart Guide
              </a>
              <a
                href="/docs/connectors"
                className="flex items-center text-blue-600 hover:text-blue-800 text-sm"
              >
                <ExternalLink className="w-4 h-4 mr-2" />
                SDK Connectors Documentation
              </a>
              <a
                href="https://github.com/hmbcompany/rag-toolkit/tree/main/examples"
                className="flex items-center text-blue-600 hover:text-blue-800 text-sm"
              >
                <ExternalLink className="w-4 h-4 mr-2" />
                Example Applications
              </a>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default IntegrationWizard;