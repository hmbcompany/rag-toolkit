import React, { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { 
  ArrowLeft,
  Clock,
  User,
  Bot,
  FileText,
  BarChart3,
  AlertCircle,
  CheckCircle,
  Play,
  Download
} from 'lucide-react';
import { apiService, formatTrafficLight, formatDuration, formatDate } from '../utils/api';

const TraceDetail = () => {
  const { traceId } = useParams();
  const [trace, setTrace] = useState(null);
  const [evaluations, setEvaluations] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [evaluating, setEvaluating] = useState(false);

  useEffect(() => {
    const fetchTraceData = async () => {
      try {
        setLoading(true);
        
        // Fetch trace and evaluations in parallel
        const [traceResponse, evaluationsResponse] = await Promise.all([
          apiService.getTrace(traceId),
          apiService.getTraceEvaluations(traceId)
        ]);
        
        setTrace(traceResponse.data);
        setEvaluations(evaluationsResponse.data.evaluations || []);
      } catch (err) {
        setError('Failed to load trace details');
        console.error('Trace detail error:', err);
      } finally {
        setLoading(false);
      }
    };

    if (traceId) {
      fetchTraceData();
    }
  }, [traceId]);

  const handleEvaluate = async () => {
    try {
      setEvaluating(true);
      await apiService.evaluateTrace(traceId);
      // Refresh evaluations
      const evaluationsResponse = await apiService.getTraceEvaluations(traceId);
      setEvaluations(evaluationsResponse.data.evaluations || []);
    } catch (err) {
      console.error('Evaluation error:', err);
    } finally {
      setEvaluating(false);
    }
  };

  const exportTrace = () => {
    const exportData = {
      trace,
      evaluations,
      exported_at: new Date().toISOString()
    };
    
    const blob = new Blob([JSON.stringify(exportData, null, 2)], {
      type: 'application/json'
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `trace_${traceId.substring(0, 8)}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-rag-blue"></div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-md p-4">
        <div className="flex">
          <AlertCircle className="h-5 w-5 text-red-400" />
          <div className="ml-3">
            <h3 className="text-sm font-medium text-red-800">Error</h3>
            <p className="mt-1 text-sm text-red-700">{error}</p>
          </div>
        </div>
      </div>
    );
  }

  if (!trace) {
    return (
      <div className="text-center py-8">
        <p className="text-gray-500">Trace not found</p>
      </div>
    );
  }

  const statusInfo = formatTrafficLight(trace.traffic_light);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-4">
          <Link
            to="/traces"
            className="inline-flex items-center text-rag-blue hover:text-blue-700"
          >
            <ArrowLeft className="h-4 w-4 mr-1" />
            Back to Traces
          </Link>
          <div>
            <h1 className="text-3xl font-bold text-gray-900">Trace Details</h1>
            <p className="text-gray-600">ID: {trace.trace_id}</p>
          </div>
        </div>
        
        <div className="flex items-center space-x-3">
          {evaluations.length === 0 && (
            <button
              onClick={handleEvaluate}
              disabled={evaluating}
              className="inline-flex items-center px-4 py-2 border border-transparent rounded-md shadow-sm bg-rag-blue text-white text-sm font-medium hover:bg-blue-700 disabled:opacity-50"
            >
              {evaluating ? (
                <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div>
              ) : (
                <Play className="h-4 w-4 mr-2" />
              )}
              {evaluating ? 'Evaluating...' : 'Run Evaluation'}
            </button>
          )}
          <button
            onClick={exportTrace}
            className="inline-flex items-center px-4 py-2 border border-gray-300 rounded-md shadow-sm bg-white text-sm font-medium text-gray-700 hover:bg-gray-50"
          >
            <Download className="h-4 w-4 mr-2" />
            Export
          </button>
        </div>
      </div>

      {/* Overview Card */}
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          <div className="flex items-center space-x-3">
            <div className={`w-4 h-4 rounded-full ${statusInfo.color.replace('text-', 'bg-')}`}></div>
            <div>
              <p className="text-sm text-gray-600">Status</p>
              <p className="font-semibold">{statusInfo.label}</p>
            </div>
          </div>
          
          <div className="flex items-center space-x-3">
            <Clock className="h-4 w-4 text-gray-400" />
            <div>
              <p className="text-sm text-gray-600">Response Time</p>
              <p className="font-semibold">
                {trace.response_latency_ms ? formatDuration(trace.response_latency_ms) : 'N/A'}
              </p>
            </div>
          </div>
          
          <div>
            <p className="text-sm text-gray-600">Model</p>
            <p className="font-semibold">{trace.model_name || 'N/A'}</p>
          </div>
          
          <div>
            <p className="text-sm text-gray-600">Timestamp</p>
            <p className="font-semibold">{formatDate(trace.timestamp)}</p>
          </div>
        </div>
      </div>

      {/* RAG Chain */}
      <div className="space-y-4">
        {/* User Input */}
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
          <div className="flex items-center space-x-2 mb-4">
            <User className="h-5 w-5 text-rag-blue" />
            <h3 className="text-lg font-semibold text-gray-900">User Input</h3>
          </div>
          <div className="bg-gray-50 rounded-lg p-4">
            <p className="text-gray-800">{trace.user_input || 'No input provided'}</p>
          </div>
        </div>

        {/* Retrieved Documents */}
        {trace.retrieved_docs && trace.retrieved_docs.length > 0 && (
          <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
            <div className="flex items-center space-x-2 mb-4">
              <FileText className="h-5 w-5 text-green-600" />
              <h3 className="text-lg font-semibold text-gray-900">
                Retrieved Documents ({trace.retrieved_docs.length})
              </h3>
            </div>
            <div className="space-y-3">
              {trace.retrieved_docs.map((doc, index) => (
                <div key={index} className="border border-gray-200 rounded-lg p-4">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm font-medium text-gray-600">Document {index + 1}</span>
                    {doc.score && (
                      <span className="text-sm text-gray-500">Score: {doc.score.toFixed(3)}</span>
                    )}
                  </div>
                  <p className="text-sm text-gray-800">{doc.content || doc.text || 'No content'}</p>
                  {doc.metadata && Object.keys(doc.metadata).length > 0 && (
                    <div className="mt-2 text-xs text-gray-500">
                      Metadata: {JSON.stringify(doc.metadata)}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Model Output */}
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
          <div className="flex items-center space-x-2 mb-4">
            <Bot className="h-5 w-5 text-purple-600" />
            <h3 className="text-lg font-semibold text-gray-900">Model Output</h3>
          </div>
          <div className="bg-gray-50 rounded-lg p-4">
            <p className="text-gray-800">{trace.model_output || 'No output provided'}</p>
          </div>
          
          {/* Token Usage */}
          {(trace.tokens_in || trace.tokens_out) && (
            <div className="mt-4 grid grid-cols-2 gap-4 text-sm">
              <div>
                <span className="text-gray-600">Tokens In:</span>{' '}
                <span className="font-medium">{trace.tokens_in || 0}</span>
              </div>
              <div>
                <span className="text-gray-600">Tokens Out:</span>{' '}
                <span className="font-medium">{trace.tokens_out || 0}</span>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Evaluations */}
      {evaluations.length > 0 && (
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
          <div className="flex items-center space-x-2 mb-4">
            <BarChart3 className="h-5 w-5 text-orange-600" />
            <h3 className="text-lg font-semibold text-gray-900">Evaluations</h3>
          </div>
          
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {evaluations.map((evaluation) => {
              const scoreColor = evaluation.score >= 0.8 ? 'text-green-600' : 
                               evaluation.score >= 0.6 ? 'text-yellow-600' : 'text-red-600';
              const bgColor = evaluation.score >= 0.8 ? 'bg-green-50' : 
                             evaluation.score >= 0.6 ? 'bg-yellow-50' : 'bg-red-50';
              
              return (
                <div key={evaluation.id} className={`${bgColor} rounded-lg p-4`}>
                  <div className="flex items-center justify-between mb-2">
                    <h4 className="font-semibold text-gray-900 capitalize">
                      {evaluation.evaluation_type}
                    </h4>
                    <span className={`text-lg font-bold ${scoreColor}`}>
                      {(evaluation.score * 100).toFixed(0)}%
                    </span>
                  </div>
                  
                  <div className="flex items-center space-x-1 mb-2">
                    {evaluation.score >= 0.8 ? (
                      <CheckCircle className="h-4 w-4 text-green-600" />
                    ) : (
                      <AlertCircle className="h-4 w-4 text-red-600" />
                    )}
                    <span className={`text-sm font-medium ${scoreColor}`}>
                      {evaluation.status?.toUpperCase() || 'COMPLETED'}
                    </span>
                  </div>
                  
                  {evaluation.explanation && (
                    <p className="text-sm text-gray-600 mt-2">{evaluation.explanation}</p>
                  )}
                  
                  <div className="mt-2 text-xs text-gray-500">
                    Confidence: {(evaluation.confidence * 100).toFixed(0)}%
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Raw Data */}
      <div className="bg-white rounded-lg shadow-sm border border-gray-200">
        <div className="px-6 py-4 border-b border-gray-200">
          <h3 className="text-lg font-semibold text-gray-900">Raw Trace Data</h3>
        </div>
        <div className="p-6">
          <pre className="bg-gray-50 rounded-lg p-4 text-xs overflow-x-auto">
            {JSON.stringify(trace, null, 2)}
          </pre>
        </div>
      </div>
    </div>
  );
};

export default TraceDetail; 