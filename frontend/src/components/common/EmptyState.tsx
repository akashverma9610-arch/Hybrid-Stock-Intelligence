import React from 'react';
import { Database } from 'lucide-react';

interface EmptyStateProps {
  id?: string;
  title: string;
  description?: string;
  action?: React.ReactNode;
  icon?: React.ReactNode;
  className?: string;
}

export const EmptyState: React.FC<EmptyStateProps> = ({
  id,
  title,
  description,
  action,
  icon,
  className = '',
}) => {
  return (
    <div
      id={id || 'empty-state-container'}
      className={`flex flex-col items-center justify-center p-8 text-center bg-[#161616] border border-dashed border-[#333] rounded-lg ${className}`}
    >
      <div className="w-12 h-12 rounded-full bg-black/40 border border-[#222] flex items-center justify-center text-gray-500 mb-3">
        {icon || <Database className="w-5 h-5" />}
      </div>
      <h3 className="text-sm font-semibold text-white mb-1">
        {title}
      </h3>
      {description && (
        <p className="text-xs text-gray-400 max-w-sm mb-4 leading-relaxed font-mono">
          {description}
        </p>
      )}
      {action}
    </div>
  );
};

