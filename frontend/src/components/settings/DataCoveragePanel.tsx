import React from 'react';
import { Database, BarChart3, CheckCircle2, AlertCircle, Clock } from 'lucide-react';
import { DataCoverageData } from '../../types/connections';
import { StatusBadge } from '../common/StatusBadge';

interface DataCoveragePanelProps {
  coverage?: DataCoverageData | null;
  isLoading?: boolean;
}

export const DataCoveragePanel: React.FC<DataCoveragePanelProps> = ({ coverage, isLoading }) => {
  const isDataAvailable = Boolean(coverage && (coverage.universeLabel || coverage.universeCount || coverage.currentQuotes));

  const items = [
    {
      label: 'Equities Universe',
      value: coverage?.universeLabel || (coverage?.universeCount ? `${coverage.universeCount.toLocaleString()} equities` : null),
      description: 'Active NSE listed equity instruments in core universe',
    },
    {
      label: 'Current Quotes',
      value: coverage?.currentQuotes,
      description: 'Real-time LTP & tick coverage from broker gateway',
    },
    {
      label: 'Historical OHLCV',
      value: coverage?.historicalOhlcv,
      description: '10Y Adjusted daily candle & time series availability',
    },
    {
      label: 'Sector Taxonomy',
      value: coverage?.taxonomy,
      description: 'NIFTY industry classification and macro tagging',
    },
    {
      label: 'Fundamentals',
      value: coverage?.fundamentals,
      description: 'Quarterly financial filings and balance sheet metrics',
    },
    {
      label: 'Ownership & Shareholding',
      value: coverage?.ownership,
      description: 'FII, DII, promoter pledges & float synchronization',
    },
    {
      label: 'Delivery & Trade Volume',
      value: coverage?.delivery,
      description: 'Security-wise gross delivery and transaction volume',
    },
  ];

  return (
    <div id="data-coverage-section" className="bg-[#161616] border border-[#222] rounded-lg p-5 space-y-4">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <Database className="w-4 h-4 text-emerald-400" />
          <h3 className="text-sm sm:text-base font-bold text-white tracking-wide">
            Data Coverage & Universe Ingestion
          </h3>
        </div>

        <div className="flex items-center gap-3">
          {coverage?.lastUpdated && (
            <span className="text-[11px] font-mono text-gray-400 flex items-center gap-1">
              <Clock className="w-3 h-3 text-gray-500" />
              <span>Updated: {coverage.lastUpdated}</span>
            </span>
          )}
          <StatusBadge status={isDataAvailable ? 'LIVE' : 'UNAVAILABLE'} />
        </div>
      </div>

      <p className="text-xs text-gray-400">
        Read-only metrics from backend data ingestion pipelines. Coverage values reflect verified records in local storage.
      </p>

      {/* Grid of coverage metrics */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 pt-2">
        {items.map((item, idx) => (
          <div
            key={idx}
            id={`coverage-metric-${item.label.toLowerCase().replace(/[^a-z0-9]/g, '-')}`}
            className="bg-black/40 border border-[#262626] rounded-lg p-3.5 flex flex-col justify-between space-y-2"
          >
            <div className="space-y-1">
              <div className="text-[11px] font-bold uppercase tracking-wider text-gray-400">
                {item.label}
              </div>
              <div className="text-xs text-gray-500 leading-tight">
                {item.description}
              </div>
            </div>

            <div className="pt-2 border-t border-[#1f1f1f]">
              {item.value ? (
                <div className="text-sm font-bold font-mono text-emerald-300">
                  {item.value}
                </div>
              ) : (
                <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-mono font-semibold bg-stone-500/15 text-stone-400 border border-stone-500/30">
                  UNAVAILABLE
                </span>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
