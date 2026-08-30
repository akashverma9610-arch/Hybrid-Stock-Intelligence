import React from 'react';
import { DownsideCrisisState, UpsideEuphoriaState } from '../../types/api';

interface DownsideBadgeProps {
  state: DownsideCrisisState | string | null | undefined;
  score?: number | null;
  className?: string;
  showBar?: boolean;
}

export const DownsideStateBadge: React.FC<DownsideBadgeProps> = ({
  state,
  score,
  className = '',
  showBar = false,
}) => {
  const norm = (state || 'NORMAL').toUpperCase() as DownsideCrisisState;

  const map: Record<DownsideCrisisState, { bg: string; label: string; text: string; step: number }> = {
    NORMAL: {
      bg: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/40',
      text: 'text-emerald-400',
      label: 'NORMAL DOWNSIDE RISK',
      step: 1,
    },
    STRESS: {
      bg: 'bg-amber-500/15 text-amber-400 border-amber-500/40',
      text: 'text-amber-400',
      label: 'ELEVATED STRESS',
      step: 2,
    },
    CRISIS: {
      bg: 'bg-rose-600 text-white font-bold border-rose-600',
      text: 'text-rose-400',
      label: 'CRISIS / DISLOCATION',
      step: 3,
    },
    RECOVERY: {
      bg: 'bg-sky-500/15 text-sky-400 border-sky-500/40',
      text: 'text-sky-400',
      label: 'CRISIS RECOVERY',
      step: 4,
    },
  };

  const current = map[norm] || map.NORMAL;

  return (
    <div className="inline-flex flex-col gap-1">
      <span
        id={`downside-state-${norm.toLowerCase()}`}
        className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded text-[11px] font-mono font-semibold uppercase tracking-wider border ${current.bg} ${className}`}
      >
        <span>{current.label}</span>
        {score !== undefined && score !== null && (
          <span className="opacity-90 font-mono text-[10px] font-bold">({score}/100)</span>
        )}
      </span>

      {showBar && (
        <div className="flex gap-1 h-1.5 w-full mt-0.5">
          <div className={`flex-1 rounded-xs transition-colors ${current.step >= 1 ? 'bg-emerald-500' : 'bg-neutral-800'}`} title="Normal" />
          <div className={`flex-1 rounded-xs transition-colors ${current.step >= 2 ? 'bg-amber-500' : 'bg-neutral-800'}`} title="Stress" />
          <div className={`flex-1 rounded-xs transition-colors ${current.step >= 3 ? 'bg-rose-500' : 'bg-neutral-800'}`} title="Crisis" />
          <div className={`flex-1 rounded-xs transition-colors ${current.step >= 4 ? 'bg-sky-500' : 'bg-neutral-800'}`} title="Recovery" />
        </div>
      )}
    </div>
  );
};

interface UpsideBadgeProps {
  state: UpsideEuphoriaState | string | null | undefined;
  score?: number | null;
  className?: string;
  showBar?: boolean;
}

export const UpsideStateBadge: React.FC<UpsideBadgeProps> = ({
  state,
  score,
  className = '',
  showBar = false,
}) => {
  const norm = (state || 'NORMAL').toUpperCase() as UpsideEuphoriaState;

  const map: Record<UpsideEuphoriaState, { bg: string; label: string; text: string; step: number }> = {
    NORMAL: {
      bg: 'bg-neutral-800 text-gray-300 border-neutral-700',
      text: 'text-gray-300',
      label: 'NORMAL UPSIDE',
      step: 1,
    },
    CROWDING: {
      bg: 'bg-amber-500/15 text-amber-400 border-amber-500/40',
      text: 'text-amber-400',
      label: 'SELECTIVE CROWDING',
      step: 2,
    },
    SPECULATION: {
      bg: 'bg-orange-500/20 text-orange-400 border-orange-500/50',
      text: 'text-orange-400',
      label: 'SPECULATIVE HEATING',
      step: 3,
    },
    EUPHORIA: {
      bg: 'bg-rose-600 text-white font-bold border-rose-600',
      text: 'text-rose-400',
      label: 'EXTREME EUPHORIA',
      step: 4,
    },
    DISTRIBUTION: {
      bg: 'bg-purple-500/15 text-purple-400 border-purple-500/40',
      text: 'text-purple-400',
      label: 'DISTRIBUTION',
      step: 5,
    },
  };

  const current = map[norm] || map.NORMAL;

  return (
    <div className="inline-flex flex-col gap-1">
      <span
        id={`upside-state-${norm.toLowerCase()}`}
        className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded text-[11px] font-mono font-semibold uppercase tracking-wider border ${current.bg} ${className}`}
      >
        <span>{current.label}</span>
        {score !== undefined && score !== null && (
          <span className="opacity-90 font-mono text-[10px] font-bold">({score}/100)</span>
        )}
      </span>

      {showBar && (
        <div className="flex gap-1 h-1.5 w-full mt-0.5">
          <div className={`flex-1 rounded-xs transition-colors ${current.step >= 1 ? 'bg-blue-500' : 'bg-neutral-800'}`} title="Normal" />
          <div className={`flex-1 rounded-xs transition-colors ${current.step >= 2 ? 'bg-amber-500' : 'bg-neutral-800'}`} title="Crowding" />
          <div className={`flex-1 rounded-xs transition-colors ${current.step >= 3 ? 'bg-orange-500' : 'bg-neutral-800'}`} title="Speculation" />
          <div className={`flex-1 rounded-xs transition-colors ${current.step >= 4 ? 'bg-rose-500' : 'bg-neutral-800'}`} title="Euphoria" />
          <div className={`flex-1 rounded-xs transition-colors ${current.step >= 5 ? 'bg-purple-500' : 'bg-neutral-800'}`} title="Distribution" />
        </div>
      )}
    </div>
  );
};

