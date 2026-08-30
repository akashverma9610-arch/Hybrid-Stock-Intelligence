import React from 'react';
import { RiskLevel } from '../../types/api';

interface RiskBadgeProps {
  risk: RiskLevel | string | null | undefined;
  className?: string;
}

export const RiskBadge: React.FC<RiskBadgeProps> = ({ risk, className = '' }) => {
  const norm = (risk || 'UNAVAILABLE').toUpperCase() as RiskLevel;

  const styleMap: Record<RiskLevel, { bg: string; label: string }> = {
    LOW: {
      bg: 'bg-emerald-500/10 text-emerald-700 dark:text-emerald-300 border-emerald-500/30',
      label: 'LOW RISK',
    },
    MODERATE: {
      bg: 'bg-sky-500/10 text-sky-700 dark:text-sky-300 border-sky-500/30',
      label: 'MODERATE RISK',
    },
    ELEVATED: {
      bg: 'bg-amber-500/10 text-amber-700 dark:text-amber-300 border-amber-500/30',
      label: 'ELEVATED RISK',
    },
    HIGH: {
      bg: 'bg-orange-500/15 text-orange-700 dark:text-orange-300 border-orange-500/40',
      label: 'HIGH RISK',
    },
    EXTREME: {
      bg: 'bg-rose-500/20 text-rose-700 dark:text-rose-300 border-rose-500/50 font-bold',
      label: 'EXTREME RISK',
    },
    UNAVAILABLE: {
      bg: 'bg-stone-500/10 text-stone-600 dark:text-stone-400 border-stone-500/20',
      label: 'RISK UNAVAILABLE',
    },
  };

  const style = styleMap[norm] || styleMap.UNAVAILABLE;

  return (
    <span
      id={`risk-badge-${norm.toLowerCase()}`}
      className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium border uppercase tracking-wider ${style.bg} ${className}`}
    >
      {style.label}
    </span>
  );
};
