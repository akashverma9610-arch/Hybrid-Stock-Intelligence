import React from 'react';
import { ApiStatus } from '../../types/api';

interface StatusBadgeProps {
  status: ApiStatus | string | null | undefined;
  className?: string;
}

export const StatusBadge: React.FC<StatusBadgeProps> = ({ status, className = '' }) => {
  const norm = (status || 'UNKNOWN').toUpperCase().replace(/[\s-]/g, '_');

  const getStyle = (s: string): { bg: string; label: string } => {
    switch (s) {
      case 'READY':
      case 'LIVE':
      case 'CONNECTED':
      case 'VALIDATED':
      case 'HEALTHY':
      case 'ONLINE':
      case 'SUCCESS':
        return {
          bg: 'bg-emerald-500/10 text-emerald-300 border-emerald-500/30',
          label: s.replace(/_/g, ' '),
        };

      case 'CONFIGURED':
        return {
          bg: 'bg-blue-500/10 text-blue-300 border-blue-500/30',
          label: 'CONFIGURED',
        };

      case 'NOT_CONFIGURED':
      case 'UNCONFIGURED':
        return {
          bg: 'bg-stone-500/15 text-stone-400 border-stone-500/30',
          label: 'NOT CONFIGURED',
        };

      case 'NOT_VALIDATED':
      case 'PENDING_SETUP':
      case 'PENDING':
      case 'NOT_TESTED':
      case 'NOT_STARTED':
        return {
          bg: 'bg-stone-500/15 text-amber-400/80 border-amber-500/20',
          label: s.replace(/_/g, ' '),
        };

      case 'PARTIAL':
      case 'IN_PROGRESS':
      case 'TESTING':
        return {
          bg: 'bg-sky-500/10 text-sky-300 border-sky-500/30',
          label: s.replace(/_/g, ' '),
        };

      case 'DEGRADED':
      case 'STALE':
      case 'ELEVATED':
      case 'WARN':
        return {
          bg: 'bg-amber-500/15 text-amber-300 border-amber-500/40',
          label: s.replace(/_/g, ' '),
        };

      case 'UNAVAILABLE':
      case 'OFFLINE':
      case 'DISCONNECTED':
        return {
          bg: 'bg-stone-500/15 text-stone-400 border-stone-500/30',
          label: s.replace(/_/g, ' '),
        };

      case 'ERROR':
      case 'FAILED':
      case 'VALIDATION_FAILED':
      case 'CRITICAL':
        return {
          bg: 'bg-rose-500/15 text-rose-300 border-rose-500/40',
          label: s.replace(/_/g, ' '),
        };

      case 'LOADING':
        return {
          bg: 'bg-slate-500/10 text-slate-400 border-slate-500/30',
          label: 'LOADING',
        };

      case 'EMPTY':
      case 'NO_DATA':
        return {
          bg: 'bg-stone-500/10 text-stone-400 border-stone-500/20',
          label: 'NO DATA',
        };

      default:
        return {
          bg: 'bg-stone-500/15 text-stone-300 border-stone-500/30',
          label: s.replace(/_/g, ' '),
        };
    }
  };

  const style = getStyle(norm);

  return (
    <span
      id={`status-badge-${norm.toLowerCase()}`}
      className={`inline-flex items-center px-2 py-0.5 rounded text-[10px] sm:text-[11px] font-semibold font-mono tracking-wider uppercase border ${style.bg} ${className}`}
    >
      {style.label}
    </span>
  );
};
