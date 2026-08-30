import React from 'react';
import { Target, Layers, CheckCircle2, Clock, AlertCircle } from 'lucide-react';
import { RealBrainTrialData } from '../../types/connections';
import { StatusBadge } from '../common/StatusBadge';

interface RealBrainTrialPanelProps {
  trial?: RealBrainTrialData | null;
}

export const RealBrainTrialPanel: React.FC<RealBrainTrialPanelProps> = ({ trial }) => {
  const isAvailable = Boolean(trial && trial.isAvailable && trial.frozenCohort);

  const metrics = [
    {
      label: 'Frozen Cohort',
      value: trial?.frozenCohort,
      description: 'Designated benchmark cohort for deterministic evaluation',
    },
    {
      label: 'Historical Ready',
      value: trial?.historicalReady,
      description: 'Complete 10Y daily bar coverage across cohort symbols',
    },
    {
      label: 'Technical Ready',
      value: trial?.technicalReady,
      description: 'Moving averages, momentum, volatility & trend metrics',
    },
    {
      label: 'Pre-Breakout Ready',
      value: trial?.preBreakoutReady,
      description: 'Volatility contraction & accumulation patterns verified',
    },
    {
      label: 'Inflection Ready',
      value: trial?.inflectionReady,
      description: 'Multi-factor inflection criteria validated on backend',
    },
  ];

  return (
    <div id="real-brain-trial-section" className="bg-[#161616] border border-[#222] rounded-lg p-5 space-y-4">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <Target className="w-4 h-4 text-purple-400" />
          <h3 className="text-sm sm:text-base font-bold text-white tracking-wide">
            Real Brain Trial Status
          </h3>
        </div>

        <div>
          <StatusBadge status={isAvailable ? 'READY' : 'UNAVAILABLE'} />
        </div>
      </div>

      <p className="text-xs text-gray-400">
        Cohort readiness and backtest ingestion verification supplied by the intelligence engine.
      </p>

      {!isAvailable ? (
        <div className="p-4 rounded-lg bg-black/40 border border-[#262626] text-center space-y-2">
          <div className="inline-flex items-center justify-center p-2 rounded-full bg-stone-500/10 text-stone-400">
            <Layers className="w-5 h-5" />
          </div>
          <div className="text-xs font-semibold text-gray-300">
            {trial?.unavailabilityMessage || 'Available after backend data ingestion'}
          </div>
          <p className="text-[11px] text-gray-500 max-w-md mx-auto">
            Real Brain trial metrics will be unlocked automatically once the historical data ingestion and cohort verification pipelines complete on the FastAPI backend.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3">
          {metrics.map((m, idx) => (
            <div
              key={idx}
              id={`trial-metric-${m.label.toLowerCase().replace(/[^a-z0-9]/g, '-')}`}
              className="bg-black/40 border border-[#262626] rounded-lg p-3 flex flex-col justify-between space-y-2"
            >
              <div className="space-y-1">
                <div className="text-[11px] font-bold uppercase tracking-wider text-gray-400">
                  {m.label}
                </div>
                <div className="text-[10px] text-gray-500 leading-tight">
                  {m.description}
                </div>
              </div>

              <div className="pt-2 border-t border-[#1f1f1f]">
                {m.value ? (
                  <div className="text-xs sm:text-sm font-bold font-mono text-purple-300 truncate" title={m.value}>
                    {m.value}
                  </div>
                ) : (
                  <span className="text-[10px] font-mono text-stone-400">UNAVAILABLE</span>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
