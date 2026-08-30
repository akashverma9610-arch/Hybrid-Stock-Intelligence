import React from 'react';
import { formatPercent } from '../../utils/formatters';

interface MetricCardProps {
  id?: string;
  label: string;
  value: string | number | null | undefined;
  change?: number | null;
  changeLabel?: string;
  subtext?: string | null;
  badge?: React.ReactNode;
  icon?: React.ReactNode;
  tooltip?: string;
  loading?: boolean;
  className?: string;
  isConfidence?: boolean;
}

export const MetricCard: React.FC<MetricCardProps> = ({
  id,
  label,
  value,
  change,
  changeLabel = 'vs prev',
  subtext,
  badge,
  icon,
  loading = false,
  className = '',
  isConfidence = false,
}) => {
  const cardId = id || `metric-${label.toLowerCase().replace(/[^a-z0-9]/g, '-')}`;

  if (loading) {
    return (
      <div
        id={cardId}
        className={`bg-[#161616] border border-[#222] rounded-lg p-5 animate-pulse ${className}`}
      >
        <div className="h-3 bg-neutral-800 rounded w-1/3 mb-3" />
        <div className="h-7 bg-neutral-800 rounded w-3/4 mb-2" />
        <div className="h-3 bg-neutral-800/60 rounded w-1/2" />
      </div>
    );
  }

  const renderValue = () => {
    if (value === null || value === undefined || value === '') {
      return <span className="text-gray-500 font-sans text-base">unavailable</span>;
    }
    return typeof value === 'number' ? value.toLocaleString('en-IN') : value;
  };

  const isPositive = change !== null && change !== undefined && change > 0;
  const isNegative = change !== null && change !== undefined && change < 0;

  return (
    <div
      id={cardId}
      className={`bg-[#161616] border border-[#222] rounded-lg p-5 transition-colors ${className}`}
    >
      <div className="flex items-center justify-between gap-2 mb-1">
        <span className="text-[10px] uppercase text-gray-500 font-bold tracking-wider">
          {label}
        </span>
        <div className="flex items-center gap-1.5">
          {badge}
          {icon && <span className="text-gray-500">{icon}</span>}
        </div>
      </div>

      <div className="flex items-baseline gap-2 mb-1">
        <div
          className={`text-2xl font-semibold tracking-tight ${
            isConfidence ? 'text-blue-400 font-mono' : 'text-white font-mono'
          }`}
        >
          {renderValue()}
        </div>
      </div>

      {((change !== null && change !== undefined) || subtext) && (
        <div className="flex items-center gap-2 text-xs">
          {change !== null && change !== undefined && (
            <span
              className={`font-mono font-semibold ${
                isPositive
                  ? 'text-emerald-400'
                  : isNegative
                  ? 'text-rose-400'
                  : 'text-gray-400'
              }`}
            >
              {formatPercent(change, { showSign: true })}
            </span>
          )}
          {subtext && (
            <span className="text-gray-400 text-[11px] truncate font-mono">
              {subtext}
            </span>
          )}
        </div>
      )}
    </div>
  );
};

