import axios from 'axios';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

// Create axios instance with default config
const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor to add auth if needed
api.interceptors.request.use((config) => {
  // Add auth header if token exists
  const token = localStorage.getItem('rag_toolkit_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Response interceptor for error handling
api.interceptors.response.use(
  (response) => response,
  (error) => {
    console.error('API Error:', error);
    return Promise.reject(error);
  }
);

// API functions
export const apiService = {
  // Health check
  health: () => api.get('/'),

  // Stats
  getStats: () => api.get('/api/v1/stats'),
  getTimeSeries: (hours = 24) => api.get(`/api/v1/stats/timeseries?hours=${hours}`),

  // Traces
  getTraces: (params = {}) => {
    const queryParams = new URLSearchParams();
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== '') {
        queryParams.append(key, value);
      }
    });
    return api.get(`/api/v1/traces?${queryParams}`);
  },
  
  getTrace: (traceId) => api.get(`/api/v1/traces/${traceId}`),
  
  getTraceEvaluations: (traceId) => api.get(`/api/v1/traces/${traceId}/evaluations`),
  
  evaluateTrace: (traceId) => api.post(`/api/v1/traces/${traceId}/evaluate`),

  // Export
  exportTraces: (params = {}) => {
    const queryParams = new URLSearchParams();
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== '') {
        queryParams.append(key, value);
      }
    });
    return api.get(`/api/v1/export/traces?${queryParams}`);
  },

  // Cleanup
  cleanupTraces: (days = 30) => api.delete(`/api/v1/traces/cleanup?days=${days}`),
};

// Helper functions
export const formatTrafficLight = (status) => {
  const statusMap = {
    green: { color: 'text-rag-green', bg: 'bg-green-100', label: 'Good' },
    amber: { color: 'text-rag-amber', bg: 'bg-yellow-100', label: 'Warning' },
    red: { color: 'text-rag-red', bg: 'bg-red-100', label: 'Issue' },
  };
  return statusMap[status?.toLowerCase()] || statusMap.red;
};

export const formatDate = (dateString) => {
  return new Date(dateString).toLocaleString();
};

export const formatDuration = (ms) => {
  if (ms < 1000) return `${ms.toFixed(1)}ms`;
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
  return `${(ms / 60000).toFixed(1)}m`;
};

export default api; 