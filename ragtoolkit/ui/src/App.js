import React from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import Header from './components/Header';
import Dashboard from './components/Dashboard';
import TracesList from './components/TracesList';
import TraceDetail from './components/TraceDetail';
import IntegrationWizard from './components/IntegrationWizard';

function App() {
  return (
    <Router>
      <div className="min-h-screen bg-gray-50">
        <Header />
        <main className="container mx-auto px-4 py-8">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/traces" element={<TracesList />} />
            <Route path="/traces/:traceId" element={<TraceDetail />} />
            <Route path="/integrate" element={<IntegrationWizard />} />
          </Routes>
        </main>
      </div>
    </Router>
  );
}

export default App; 