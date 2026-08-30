import React from 'react';
import { SignalAction } from '../../types/api';

interface ActionBadgeProps {
  action: SignalAction | string | null | undefined;
  size?: 'sm' | 'md';
  className?: string;
}

export const ActionBadge: React.FC<ActionBadgeProps> = ({ action, size = 'sm', className = '' }) => {
  const norm = (action || 'WATCH').toUpperCase() as SignalAction;

  const styleMap: Record<SignalAction, { bg: string; text: string; label: string }> = {
    BUY: {
      bg: 'bg-emerald-600 text-white dark:bg-emerald-500 dark:text-slate-950 font-bold',
      text: 'text-white',
      label: 'BUY',
    },
    ACCUMULATE: {
      bg: 'bg-emerald-500/20 text-emerald-700 dark:text-emerald-300 border border-emerald-500/40 font-semibold',
      text: 'text-emerald-700 dark:text-emerald-300',
      label: 'ACCUMULATE',
    },
    HOLD: {
      bg: 'bg-slate-500/20 text-slate-700 dark:text-slate-300 border border-slate-500/40 font-medium',
      text: 'text-slate-700 dark:text-slate-300',
      label: 'HOLD',
    },
    TRIM: {
      bg: 'bg-amber-500/20 text-amber-700 dark:text-amber-300 border border-amber-500/40 font-semibold',
      text: 'text-amber-700 dark:text-amber-300',
      label: 'TRIM',
    },
    EXIT: {
      bg: 'bg-rose-600 text-white dark:bg-rose-500 dark:text-slate-950 font-bold',
      text: 'text-white',
      label: 'EXIT',
    },
    AVOID: {
      bg: 'bg-rose-500/20 text-rose-700 dark:text-rose-300 border border-rose-500/40 font-semibold',
      text: 'text-rose-700 dark:text-rose-300',
      label: 'AVOID',
    },
    WATCH: {
      bg: 'bg-stone-500/15 text-stone-600 dark:text-stone-400 border border-stone-500/30 font-normal',
      text: 'text-stone-600 dark:text-stone-400',
      label: 'WATCH',
    },
  };

  const style = styleMap[norm] || styleMap.WATCH;
  const padding = size === 'sm' ? 'px-2 py-0.5 text-xs' : 'px-3 py-1 text-sm';

  return (
    <span
      id={`action-badge-${norm.toLowerCase()}`}
      className={`inline-flex items-center justify-center rounded tracking-wider uppercase ${padding} ${style.bg} ${className}`}
    >
      {style.label}
    </span>
  );
};
