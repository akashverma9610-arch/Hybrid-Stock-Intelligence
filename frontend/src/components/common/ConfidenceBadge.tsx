import React from 'react';
import { ConfidenceLevel } from '../../types/api';

interface ConfidenceBadgeProps {
  confidence: ConfidenceLevel | null | undefined;
  percentage?: number | null;
  className?: string;
}

export const ConfidenceBadge: React.FC<ConfidenceBadgeProps> = ({ confidence, percentage, className = '' }) => {
  const normalized = (confidence || 'INSUFFICIENT_DATA').toUpperCase() as ConfidenceLevel;

  const styleMap: Record<ConfidenceLevel, { bg: string; label: string }> = {
    HIGH: {
      bg: 'bg-emerald-500/10 dark:bg-emerald-500/20 border-emerald-500/30 text-emerald-700 dark:text-emerald-300',
      label: 'HIGH CONFIDENCE',
    },
    MEDIUM: {
      bg: 'bg-sky-500/10 dark:bg-sky-500/20 border-sky-500/30 text-sky-700 dark:text-sky-300',
      label: 'MED CONFIDENCE',
    },
    LOW: {
      bg: 'bg-amber-500/10 dark:bg-amber-500/20 border-amber-500/30 text-amber-700 dark:text-amber-300',
      label: 'LOW CONFIDENCE',
    },
    INSUFFICIENT_DATA: {
      bg: 'bg-stone-500/10 dark:bg-stone-500/20 border-stone-500/30 text-stone-600 dark:text-stone-400',
      label: 'INSUFFICIENT DATA',
    },
  };

  const style = styleMap[normalized] || styleMap.INSUFFICIENT_DATA;

  return (
    <span
      id={`confidence-badge-${normalized.toLowerCase()}`}
      className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium border ${style.bg} ${className}`}
    >
      <span>{style.label}</span>
      {percentage !== undefined && percentage !== null && (
        <span className="font-bold opacity-90 font-mono text-[11px]">({percentage}%)</span>
      )}
    </span>
  );
};
