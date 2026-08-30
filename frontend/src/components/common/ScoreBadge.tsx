import React from 'react';
import { formatScore } from '../../utils/formatters';

interface ScoreBadgeProps {
  score: number | null | undefined;
  size?: 'sm' | 'md' | 'lg';
  showLabel?: boolean;
  className?: string;
}

export const ScoreBadge: React.FC<ScoreBadgeProps> = ({
  score,
  size = 'md',
  showLabel = false,
  className = '',
}) => {
  if (score === null || score === undefined || isNaN(score)) {
    return (
      <span
        id="score-badge-unavailable"
        className="inline-flex items-center px-2 py-0.5 rounded text-xs font-mono bg-stone-500/10 dark:bg-stone-500/20 text-stone-500 border border-stone-500/20"
      >
        Score unavailable
      </span>
    );
  }

  // Institutional styling by score tiers
  let colorClass = 'bg-stone-500/10 text-stone-700 dark:text-stone-300 border-stone-500/30';
  if (score >= 80) {
    colorClass = 'bg-emerald-500/15 dark:bg-emerald-500/20 text-emerald-700 dark:text-emerald-300 border-emerald-500/40';
  } else if (score >= 65) {
    colorClass = 'bg-sky-500/15 dark:bg-sky-500/20 text-sky-700 dark:text-sky-300 border-sky-500/40';
  } else if (score >= 50) {
    colorClass = 'bg-amber-500/15 dark:bg-amber-500/20 text-amber-700 dark:text-amber-300 border-amber-500/40';
  } else {
    colorClass = 'bg-rose-500/15 dark:bg-rose-500/20 text-rose-700 dark:text-rose-300 border-rose-500/40';
  }

  const sizeClass = {
    sm: 'text-xs px-1.5 py-0.5 font-medium',
    md: 'text-sm px-2.5 py-1 font-bold',
    lg: 'text-base px-3 py-1.5 font-extrabold',
  }[size];

  return (
    <span
      id={`score-badge-${Math.round(score)}`}
      className={`inline-flex items-center gap-1 rounded border font-mono tracking-tight ${colorClass} ${sizeClass} ${className}`}
    >
      {showLabel && <span className="text-[11px] font-sans font-normal opacity-80 uppercase tracking-wider">Score</span>}
      <span>{formatScore(score)}</span>
    </span>
  );
};
