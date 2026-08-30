import React from 'react';
import { ApiResponse, ApiStatus } from '../../types/api';
import { LoadingSkeleton } from './LoadingSkeleton';
import { ErrorState } from './ErrorState';
import { EmptyState } from './EmptyState';
import { WarningBanner } from './WarningBanner';

interface ApiStateWrapperProps<T> {
  response: ApiResponse<T> | null | undefined;
  isLoading?: boolean;
  skeletonType?: 'card' | 'table' | 'metric' | 'text';
  skeletonRows?: number;
  emptyTitle?: string;
  emptyDescription?: string;
  onRetry?: () => void;
  children: (data: T) => React.ReactNode;
}

export function ApiStateWrapper<T>({
  response,
  isLoading = false,
  skeletonType = 'card',
  skeletonRows = 4,
  emptyTitle = 'No data available',
  emptyDescription = 'The requested endpoint returned an empty record set.',
  onRetry,
  children,
}: ApiStateWrapperProps<T>) {
  if (isLoading || !response || response.status === 'LOADING') {
    return <LoadingSkeleton type={skeletonType} rows={skeletonRows} />;
  }

  const { status, data, message, warnings } = response;

  if (status === 'ERROR') {
    return (
      <ErrorState
        title="Failed to Load Data"
        message={message || 'An error occurred while fetching from the backend.'}
        onRetry={onRetry}
      />
    );
  }

  if (status === 'UNAVAILABLE') {
    return (
      <div className="space-y-3">
        <WarningBanner
          type="unavailable"
          title="Backend Service / Endpoint Unavailable"
          message={message || 'This module or endpoint is currently not exposed by the active backend service.'}
          action={
            onRetry ? (
              <button
                onClick={onRetry}
                className="px-2.5 py-1 rounded bg-[#222] hover:bg-[#333] text-gray-200 text-xs font-semibold flex items-center gap-1 border border-[#444] transition-colors"
              >
                <span>Retry</span>
              </button>
            ) : undefined
          }
        />
        {data ? children(data) : (
          <EmptyState
            title="Data Currently Unavailable"
            description={message || 'Live data from this backend endpoint could not be retrieved.'}
            onAction={onRetry}
            actionLabel={onRetry ? 'Retry Request' : undefined}
          />
        )}
      </div>
    );
  }

  if (status === 'DEGRADED') {
    return (
      <div className="space-y-3">
        <WarningBanner
          type="warning"
          title="Degraded Data Mode"
          message={message || 'Backend feeds are running with delayed or partial data.'}
        />
        {data ? children(data) : (
          <EmptyState title="Degraded Data" description="No valid cached data available." />
        )}
      </div>
    );
  }

  if (status === 'EMPTY' || !data || (Array.isArray(data) && data.length === 0)) {
    return <EmptyState title={emptyTitle} description={emptyDescription} />;
  }

  return (
    <div className="space-y-3">
      {status === 'PARTIAL' && (
        <WarningBanner
          type="info"
          title="Partial Response"
          message={message || 'Some data providers did not respond within cycle timeout.'}
        />
      )}
      {warnings && warnings.length > 0 && (
        <WarningBanner
          type="warning"
          title="Active System Warnings"
          message={
            <ul className="list-disc list-inside space-y-0.5">
              {warnings.map((w, idx) => (
                <li key={idx}>{w}</li>
              ))}
            </ul>
          }
        />
      )}
      {children(data)}
    </div>
  );
}
