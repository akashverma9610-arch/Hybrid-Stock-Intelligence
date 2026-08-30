import React from 'react';
import { AlertTriangle, RefreshCw } from 'lucide-react';

interface ErrorStateProps {
  id?: string;
  title?: string;
  message?: string;
  onRetry?: () => void;
  className?: string;
}

export const ErrorState: React.FC<ErrorStateProps> = ({
  id,
  title = 'Unable to Load Data',
  message = 'A connection or server error occurred while retrieving data from the backend.',
  onRetry,
  className = '',
}) => {
  return (
    <div
      id={id || 'error-state-container'}
      className={`p-6 bg-[#161616] border border-rose-500/30 rounded-lg text-center flex flex-col items-center justify-center ${className}`}
    >
      <div className="w-10 h-10 rounded-full bg-rose-500/10 border border-rose-500/30 text-rose-400 flex items-center justify-center mb-3">
        <AlertTriangle className="w-5 h-5" />
      </div>
      <h3 className="text-sm font-bold text-rose-300 mb-1">
        {title}
      </h3>
      <p className="text-xs text-rose-400/90 max-w-md mb-4 leading-relaxed font-mono">
        {message}
      </p>
      {onRetry && (
        <button
          id="error-state-retry-btn"
          onClick={onRetry}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-rose-600 hover:bg-rose-500 text-white rounded text-xs font-semibold shadow-xs transition-colors"
        >
          <RefreshCw className="w-3.5 h-3.5" />
          <span>Retry Request</span>
        </button>
      )}
    </div>
  );
};

