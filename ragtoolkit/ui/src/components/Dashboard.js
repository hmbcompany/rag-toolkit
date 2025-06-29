import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { 
  Activity, 
  Clock, 
  AlertTriangle, 
  CheckCircle, 
  XCircle,
  TrendingUp,
  Zap,
  Database
} from 'lucide-react';
import { apiService, formatTrafficLight, formatDuration } from '../utils/api';

const Dashboard = () => {
  const [stats, setStats] = useState(null);
  const [recentTraces, setRecentTraces] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true);
        
        // Fetch stats and recent traces in parallel
        const [statsResponse, tracesResponse] = await Promise.all([
          apiService.getStats(),
          apiService.getTraces({ page: 1, size: 5 })
        ]);
        
        setStats(statsResponse.data);
        setRecentTraces(tracesResponse.data.traces);
      } catch (err) {
        setError('Failed to load dashboard data');
        console.error('Dashboard error:', err);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
    
    // Refresh every 30 seconds
    const interval = setInterval(fetchData, 30000);
    return () => clearInterval(interval);
  }, []);

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
          <XCircle className="h-5 w-5 text-red-400" />
          <div className="ml-3">
            <h3 className="text-sm font-medium text-red-800">Error</h3>
            <p className="mt-1 text-sm text-red-700">{error}</p>
          </div>
        </div>
      </div>
    );
  }

  const statCards = [
    {
      title: 'Total Traces',
      value: stats?.total_traces || 0,
      icon: Database,
      color: 'text-blue-600',
      bg: 'bg-blue-50'
    },
    {
      title: 'Traces (24h)',
      value: stats?.traces_last_24h || 0,
      icon: TrendingUp,
      color: 'text-green-600',
      bg: 'bg-green-50'
    },
    {
      title: 'Avg Response Time',
      value: formatDuration(stats?.avg_response_time_ms || 0),
      icon: Zap,
      color: 'text-yellow-600',
      bg: 'bg-yellow-50'
    },
    {
      title: 'Error Rate',
      value: `${((stats?.error_rate || 0) * 100).toFixed(1)}%`,
      icon: stats?.error_rate > 0.05 ? AlertTriangle : CheckCircle,
      color: stats?.error_rate > 0.05 ? 'text-red-600' : 'text-green-600',
      bg: stats?.error_rate > 0.05 ? 'bg-red-50' : 'bg-green-50'
    }
  ];

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Dashboard</h1>
          <p className="text-gray-600">Monitor your RAG pipeline performance</p>
        </div>
        <div className="flex items-center space-x-2 text-sm text-gray-500">
          <Activity className="h-4 w-4" />
          <span>Last updated: {new Date().toLocaleTimeString()}</span>
        </div>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        {statCards.map((stat) => {
          const Icon = stat.icon;
          return (
            <div key={stat.title} className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
              <div className="flex items-center">
                <div className={`p-2 rounded-md ${stat.bg}`}>
                  <Icon className={`h-6 w-6 ${stat.color}`} />
                </div>
                <div className="ml-4">
                  <p className="text-sm font-medium text-gray-600">{stat.title}</p>
                  <p className="text-2xl font-bold text-gray-900">{stat.value}</p>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* Traffic Light Distribution */}
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Quality Status Distribution</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {Object.entries(stats?.traffic_light_distribution || {}).map(([status, count]) => {
            const statusInfo = formatTrafficLight(status);
            return (
              <div key={status} className={`p-4 rounded-lg ${statusInfo.bg}`}>
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-2">
                    <div className={`w-3 h-3 rounded-full ${statusInfo.color.replace('text-', 'bg-')}`}></div>
                    <span className="font-medium text-gray-900">{statusInfo.label}</span>
                  </div>
                  <span className={`text-2xl font-bold ${statusInfo.color}`}>{count}</span>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Recent Traces */}
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-gray-900">Recent Traces</h2>
          <Link
            to="/traces"
            className="text-rag-blue hover:text-blue-700 text-sm font-medium"
          >
            View all →
          </Link>
        </div>
        
        {recentTraces.length === 0 ? (
          <p className="text-gray-500 text-center py-8">No traces found</p>
        ) : (
          <div className="space-y-3">
            {recentTraces.map((trace) => {
              const statusInfo = formatTrafficLight(trace.traffic_light);
              return (
                <Link
                  key={trace.id}
                  to={`/traces/${trace.trace_id}`}
                  className="block p-4 rounded-lg border border-gray-200 hover:border-rag-blue hover:shadow-sm transition-all"
                >
                  <div className="flex items-center justify-between">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center space-x-2">
                        <div className={`w-2 h-2 rounded-full ${statusInfo.color.replace('text-', 'bg-')}`}></div>
                        <p className="text-sm font-medium text-gray-900 truncate">
                          {trace.user_input || 'No input provided'}
                        </p>
                      </div>
                      <div className="mt-1 flex items-center space-x-4 text-xs text-gray-500">
                        <span>{new Date(trace.timestamp).toLocaleString()}</span>
                        {trace.model_name && <span>Model: {trace.model_name}</span>}
                        {trace.response_latency_ms && (
                          <span>
                            <Clock className="inline h-3 w-3 mr-1" />
                            {formatDuration(trace.response_latency_ms)}
                          </span>
                        )}
                      </div>
                    </div>
                    <div className="ml-4">
                      <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${statusInfo.bg} ${statusInfo.color}`}>
                        {statusInfo.label}
                      </span>
                    </div>
                  </div>
                </Link>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
};

export default Dashboard; 