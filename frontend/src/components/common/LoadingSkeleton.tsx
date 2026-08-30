import React from 'react';

interface LoadingSkeletonProps {
  rows?: number;
  type?: 'card' | 'table' | 'metric' | 'text';
  className?: string;
}

export const LoadingSkeleton: React.FC<LoadingSkeletonProps> = ({
  rows = 4,
  type = 'card',
  className = '',
}) => {
  if (type === 'metric') {
    return (
      <div className={`grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 ${className}`}>
        {Array.from({ length: rows }).map((_, i) => (
          <div
            key={i}
            className="bg-[#161616] border border-[#222] rounded-lg p-4 animate-pulse"
          >
            <div className="h-3 bg-neutral-800 rounded w-1/3 mb-3" />
            <div className="h-7 bg-neutral-800 rounded w-2/3 mb-2" />
            <div className="h-3 bg-neutral-800/60 rounded w-1/2" />
          </div>
        ))}
      </div>
    );
  }

  if (type === 'table') {
    return (
      <div className={`w-full bg-[#161616] border border-[#222] rounded-lg p-4 animate-pulse ${className}`}>
        <div className="h-5 bg-neutral-800 rounded w-1/4 mb-4" />
        <div className="space-y-3">
          {Array.from({ length: rows }).map((_, i) => (
            <div key={i} className="flex gap-4">
              <div className="h-4 bg-neutral-800 rounded w-1/6" />
              <div className="h-4 bg-neutral-800/60 rounded w-1/4" />
              <div className="h-4 bg-neutral-800/60 rounded w-1/4" />
              <div className="h-4 bg-neutral-800 rounded w-1/6" />
              <div className="h-4 bg-neutral-800/60 rounded w-1/6" />
            </div>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className={`bg-[#161616] border border-[#222] rounded-lg p-6 animate-pulse space-y-4 ${className}`}>
      <div className="h-5 bg-neutral-800 rounded w-1/3" />
      <div className="h-4 bg-neutral-800/60 rounded w-3/4" />
      <div className="h-4 bg-neutral-800/60 rounded w-1/2" />
      <div className="h-24 bg-neutral-800/40 rounded w-full" />
    </div>
  );
};

