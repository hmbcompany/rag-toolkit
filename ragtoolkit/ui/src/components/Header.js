import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import { Activity, BarChart3, List } from 'lucide-react';

const Header = () => {
  const location = useLocation();

  const navigation = [
    { name: 'Dashboard', href: '/', icon: BarChart3 },
    { name: 'Traces', href: '/traces', icon: List },
  ];

  return (
    <header className="bg-white shadow-sm border-b border-gray-200">
      <div className="container mx-auto px-4">
        <div className="flex items-center justify-between h-16">
          {/* Logo */}
          <div className="flex items-center space-x-2">
            <Activity className="h-8 w-8 text-rag-blue" />
            <div>
              <h1 className="text-xl font-bold text-gray-900">RAG Toolkit</h1>
              <p className="text-xs text-gray-500">Observability Dashboard</p>
            </div>
          </div>

          {/* Navigation */}
          <nav className="flex space-x-8">
            {navigation.map((item) => {
              const Icon = item.icon;
              const isActive = location.pathname === item.href;
              
              return (
                <Link
                  key={item.name}
                  to={item.href}
                  className={`flex items-center space-x-1 px-3 py-2 rounded-md text-sm font-medium transition-colors ${
                    isActive
                      ? 'bg-rag-blue text-white'
                      : 'text-gray-600 hover:text-rag-blue hover:bg-gray-50'
                  }`}
                >
                  <Icon className="h-4 w-4" />
                  <span>{item.name}</span>
                </Link>
              );
            })}
          </nav>
        </div>
      </div>
    </header>
  );
};

export default Header; 