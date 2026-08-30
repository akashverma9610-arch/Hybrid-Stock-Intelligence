import React from 'react';
import { Cpu, CheckCircle2, AlertTriangle, ShieldAlert, Clock, Info } from 'lucide-react';
import { BrainDataReadinessData, BrainReadinessItem } from '../../types/connections';
import { StatusBadge } from '../common/StatusBadge';

interface BrainReadinessPanelProps {
  readiness?: BrainDataReadinessData | null;
}

export const BrainReadinessPanel: React.FC<BrainReadinessPanelProps> = ({ readiness }) => {
  // Default structure if backend returned items or if we need standard placeholders
  const standardCategories: { key: BrainReadinessItem['key']; name: string; defaultDetail: string }[] = [
    { key: 'historical', name: 'Historical Data', defaultDetail: 'Adjusted OHLCV daily candle history' },
    { key: 'taxonomy', name: 'Sector Taxonomy', defaultDetail: 'Sector classification & industry group mappings' },
    { key: 'market_context', name: 'Market Context', defaultDetail: 'Regime indicators, breadth, VIX & macro context' },
    { key: 'fundamentals', name: 'Fundamentals', defaultDetail: 'Financial statements, revenue growth & quarterly filings' },
    { key: 'ownership', name: 'Ownership', defaultDetail: 'FII/DII shareholding patterns & promoter holding' },
    { key: 'delivery', name: 'Delivery', defaultDetail: 'NSE delivery volume & security-wise trade statistics' },
    { key: 'news_catalysts', name: 'News / Catalysts', defaultDetail: 'Corporate announcements, events & filings feeds' },
  ];

  const items: BrainReadinessItem[] = standardCategories.map((cat) => {
    const existing = readiness?.items?.find((it) => it.key === cat.key || it.name.toLowerCase().includes(cat.name.toLowerCase()));
    if (existing) return existing;
    return {
      key: cat.key,
      name: cat.name,
      status: readiness?.overallStatus || 'UNAVAILABLE',
      detail: cat.defaultDetail,
    };
  });

  return (
    <div id="brain-readiness-section" className="bg-[#161616] border border-[#222] rounded-lg p-5 space-y-4">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <Cpu className="w-4 h-4 text-blue-400" />
          <h3 className="text-sm sm:text-base font-bold text-white tracking-wide">
            Brain Data Readiness
          </h3>
        </div>

        <div className="flex items-center gap-3">
          {readiness?.lastAssessed && (
            <span className="text-[11px] font-mono text-gray-400 flex items-center gap-1">
              <Clock className="w-3 h-3 text-gray-500" />
              <span>Assessed: {readiness.lastAssessed}</span>
            </span>
          )}
          <StatusBadge status={readiness?.overallStatus || 'UNAVAILABLE'} />
        </div>
      </div>

      {/* Mandatory Disclaimer Note */}
      <div className="p-2.5 rounded bg-blue-500/10 border border-blue-500/20 flex items-center gap-2 text-xs text-blue-300">
        <Info className="w-4 h-4 shrink-0 text-blue-400" />
        <span>
          <strong>Explicit Disclaimer:</strong> This is data readiness, NOT an investment score. All pipeline statuses are supplied strictly by the backend ingestion system.
        </span>
      </div>

      {/* Table / List of items */}
      <div className="border border-[#262626] rounded-lg overflow-hidden divide-y divide-[#222]">
        {items.map((it) => (
          <div
            key={it.key}
            id={`readiness-row-${it.key}`}
            className="p-3 bg-black/30 hover:bg-black/50 flex flex-col sm:flex-row sm:items-center justify-between gap-2 transition-colors"
          >
            <div className="space-y-0.5">
              <div className="text-xs font-bold text-gray-200">
                {it.name}
              </div>
              {it.detail && (
                <div className="text-[11px] text-gray-500 font-mono">
                  {it.detail}
                </div>
              )}
            </div>

            <div className="flex items-center gap-3 self-start sm:self-auto shrink-0">
              {it.lastSync && (
                <span className="text-[10px] font-mono text-gray-500">
                  Synced: {it.lastSync}
                </span>
              )}
              <StatusBadge status={it.status} />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
