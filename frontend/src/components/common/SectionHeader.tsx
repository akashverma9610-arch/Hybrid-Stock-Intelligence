import React from 'react';
import { FreshnessState } from '../../types/api';
import { FreshnessBadge } from './FreshnessBadge';

interface SectionHeaderProps {
  id?: string;
  title: string;
  subtitle?: string;
  freshness?: FreshnessState | string | null;
  timestamp?: string | null;
  badge?: React.ReactNode;
  actions?: React.ReactNode;
  className?: string;
}

export const SectionHeader: React.FC<SectionHeaderProps> = ({
  id,
  title,
  subtitle,
  freshness,
  timestamp,
  badge,
  actions,
  className = '',
}) => {
  return (
    <div
      id={id || `header-${title.toLowerCase().replace(/[^a-z0-9]/g, '-')}`}
      className={`flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 mb-4 border-b border-[#222] ${className}`}
    >
      <div>
        <div className="flex items-center gap-2.5 flex-wrap">
          <h2 className="text-base sm:text-lg font-bold text-white tracking-tight">
            {title}
          </h2>
          {badge}
          {freshness && <FreshnessBadge freshness={freshness} timestamp={timestamp} />}
        </div>
        {subtitle && (
          <p className="text-xs text-gray-400 mt-0.5 max-w-3xl leading-relaxed">
            {subtitle}
          </p>
        )}
      </div>

      {actions && <div className="flex items-center gap-2 shrink-0">{actions}</div>}
    </div>
  );
};

