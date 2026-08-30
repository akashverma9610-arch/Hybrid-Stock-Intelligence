import React from 'react';
import { FreshnessState } from '../../types/api';

interface FreshnessBadgeProps {
  freshness: FreshnessState | string | null | undefined;
  timestamp?: string | null;
  size?: 'sm' | 'md';
  className?: string;
}

export const FreshnessBadge: React.FC<FreshnessBadgeProps> = ({
  freshness,
  timestamp,
  size = 'md',
  className = '',
}) => {
  const normalized = (freshness || 'UNKNOWN').toUpperCase() as FreshnessState;

  const styleMap: Record<FreshnessState, { bg: string; dot: string; label: string }> = {
    LIVE: {
      bg: 'bg-emerald-500/10 dark:bg-emerald-500/15 border-emerald-500/30 text-emerald-700 dark:text-emerald-300',
      dot: 'bg-emerald-500 animate-pulse',
      label: 'LIVE',
    },
    DELAYED: {
      bg: 'bg-amber-500/10 dark:bg-amber-500/15 border-amber-500/30 text-amber-700 dark:text-amber-300',
      dot: 'bg-amber-500',
      label: 'DELAYED',
    },
    EOD: {
      bg: 'bg-blue-500/10 dark:bg-blue-500/15 border-blue-500/30 text-blue-700 dark:text-blue-300',
      dot: 'bg-blue-500',
      label: 'EOD',
    },
    STALE: {
      bg: 'bg-rose-500/10 dark:bg-rose-500/15 border-rose-500/30 text-rose-700 dark:text-rose-300',
      dot: 'bg-rose-500',
      label: 'STALE',
    },
    UNKNOWN: {
      bg: 'bg-stone-500/10 dark:bg-stone-500/15 border-stone-500/30 text-stone-700 dark:text-stone-300',
      dot: 'bg-stone-400',
      label: 'UNKNOWN',
    },
  };

  const style = styleMap[normalized] || styleMap.UNKNOWN;
  const padding = size === 'sm' ? 'px-1.5 py-0.2 text-[10px]' : 'px-2 py-0.5 text-xs';

  return (
    <span
      id={`freshness-badge-${normalized.toLowerCase()}`}
      className={`inline-flex items-center gap-1.5 rounded font-semibold tracking-wide uppercase border ${padding} ${style.bg} ${className}`}
      title={timestamp ? `Updated: ${timestamp}` : undefined}
    >
      <span className={`w-1.5 h-1.5 rounded-full ${style.dot}`} />
      <span>{style.label}</span>
      {timestamp && size !== 'sm' && (
        <span className="opacity-70 lowercase text-[10px] font-normal">({timestamp})</span>
      )}
    </span>
  );
};
