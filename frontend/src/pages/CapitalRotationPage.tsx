import React, { useEffect, useState } from 'react';
import {
  AlertCircle,
  ArrowLeftRight,
  ArrowRight,
  CheckCircle2,
  Clock,
  Info,
  Layers,
  Lock,
  RefreshCw,
  Shield,
  XCircle,
} from 'lucide-react';
import { useDataClient } from '../api/context';
import { ApiResponse } from '../types/api';
import { CapitalRotationData, CapitalRotationItem } from '../types/rotation';
import { SectionHeader } from '../components/common/SectionHeader';
import { WarningBanner } from '../components/common/WarningBanner';
import { ScoreBadge } from '../components/common/ScoreBadge';
import { ConfidenceBadge } from '../components/common/ConfidenceBadge';
import { ActionBadge } from '../components/common/ActionBadge';
import { formatINR, formatPercent, formatRatio, formatScore } from '../utils/formatters';

export const CapitalRotationPage: React.FC = () => {
  const { client, refreshTrigger } = useDataClient();
  const [rotationRes, setRotationRes] = useState<ApiResponse<CapitalRotationData> | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let isMounted = true;
    const fetchRotation = async () => {
      setLoading(true);
      try {
        const res = await client.getCapitalRotation();
        if (isMounted) setRotationRes(res);
      } catch (err) {
        console.error('Failed to load rotation data:', err);
      } finally {
        if (isMounted) setLoading(false);
      }
    };

    fetchRotation();
    return () => {
      isMounted = false;
    };
  }, [client, refreshTrigger]);

  return (
    <div id="capital-rotation-page" className="space-y-6">
      <SectionHeader
        title="Capital Rotation Recommendation Engine"
        subtitle="Systematic reallocation from underperforming/weakening equity holdings to high-score leadership candidates"
        badge={
          <span className="text-[11px] font-bold px-2 py-0.5 rounded bg-amber-500/20 text-amber-800 dark:text-amber-300 border border-amber-500/40">
            ENGINE STATUS: BACKEND UNEXPOSED
          </span>
        }
      />

      {/* Explicit Notice / Status Alert */}
      <div className="bg-amber-500/10 dark:bg-amber-950/30 border border-amber-500/40 rounded-xl p-5 space-y-3">
        <div className="flex items-start gap-3">
          <AlertCircle className="w-5 h-5 text-amber-600 dark:text-amber-400 shrink-0 mt-0.5" />
          <div className="space-y-1">
            <h3 className="text-sm font-bold text-amber-950 dark:text-amber-200">
              Backend Rotation Endpoint Unexposed (v2.1 Shell Protocol)
            </h3>
            <p className="text-xs text-amber-900 dark:text-amber-300 leading-relaxed">
              The FastAPI backend service has not yet published the live public Capital Rotation recommendations endpoint (<code>/api/v2/rotation/recommendations</code>).
            </p>
            <p className="text-xs text-amber-800 dark:text-amber-400 font-medium">
              <strong>Strict Separation of Concerns:</strong> The frontend does <em>not</em> calculate rotation recommendations locally. The shell below displays the planned data structure and UI placeholders to confirm contract compatibility once the backend endpoint is exposed.
            </p>
          </div>
        </div>
      </div>

      {/* Six Execution Gates Specification (Visual Architecture Reference) */}
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-5 shadow-xs space-y-4">
        <div>
          <h3 className="text-sm font-bold text-slate-900 dark:text-slate-100 flex items-center gap-2">
            <Shield className="w-4 h-4 text-emerald-500" />
            <span>Six Execution Gates Architecture (Backend Gated)</span>
          </h3>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
            When the backend endpoint is active, candidates must pass all 6 quantitative execution gates before rotation is triggered:
          </p>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 text-xs">
          <div className="p-3 rounded-lg bg-slate-50 dark:bg-slate-800/40 border border-slate-200 dark:border-slate-800 space-y-1">
            <div className="font-bold text-slate-800 dark:text-slate-200 flex items-center gap-1.5">
              <span className="w-5 h-5 rounded-full bg-slate-200 dark:bg-slate-700 flex items-center justify-center text-[10px] font-mono">1</span>
              <span>Regime Gate</span>
            </div>
            <p className="text-[11px] text-slate-500">
              Verifies macro market regime allows aggressive capital rotation without systemic downside hazard.
            </p>
          </div>

          <div className="p-3 rounded-lg bg-slate-50 dark:bg-slate-800/40 border border-slate-200 dark:border-slate-800 space-y-1">
            <div className="font-bold text-slate-800 dark:text-slate-200 flex items-center gap-1.5">
              <span className="w-5 h-5 rounded-full bg-slate-200 dark:bg-slate-700 flex items-center justify-center text-[10px] font-mono">2</span>
              <span>Score Delta Hurdle</span>
            </div>
            <p className="text-[11px] text-slate-500">
              Requires candidate score advantage &gt; +15.0 pts over current holding to justify transaction friction.
            </p>
          </div>

          <div className="p-3 rounded-lg bg-slate-50 dark:bg-slate-800/40 border border-slate-200 dark:border-slate-800 space-y-1">
            <div className="font-bold text-slate-800 dark:text-slate-200 flex items-center gap-1.5">
              <span className="w-5 h-5 rounded-full bg-slate-200 dark:bg-slate-700 flex items-center justify-center text-[10px] font-mono">3</span>
              <span>Sector Phase Flow</span>
            </div>
            <p className="text-[11px] text-slate-500">
              Confirms capital flows from lagging/weakening sectors into leading or improving industry groups.
            </p>
          </div>

          <div className="p-3 rounded-lg bg-slate-50 dark:bg-slate-800/40 border border-slate-200 dark:border-slate-800 space-y-1">
            <div className="font-bold text-slate-800 dark:text-slate-200 flex items-center gap-1.5">
              <span className="w-5 h-5 rounded-full bg-slate-200 dark:bg-slate-700 flex items-center justify-center text-[10px] font-mono">4</span>
              <span>Liquidity & Impact Cost</span>
            </div>
            <p className="text-[11px] text-slate-500">
              Assesses 20-day average daily turnover to guarantee sub-0.05% slippage on exit and entry.
            </p>
          </div>

          <div className="p-3 rounded-lg bg-slate-50 dark:bg-slate-800/40 border border-slate-200 dark:border-slate-800 space-y-1">
            <div className="font-bold text-slate-800 dark:text-slate-200 flex items-center gap-1.5">
              <span className="w-5 h-5 rounded-full bg-slate-200 dark:bg-slate-700 flex items-center justify-center text-[10px] font-mono">5</span>
              <span>Drawdown Buffer & R:R</span>
            </div>
            <p className="text-[11px] text-slate-500">
              Enforces minimum risk-to-reward ratio &gt; 2.5:1 with structural support invalidation levels.
            </p>
          </div>

          <div className="p-3 rounded-lg bg-slate-50 dark:bg-slate-800/40 border border-slate-200 dark:border-slate-800 space-y-1">
            <div className="font-bold text-slate-800 dark:text-slate-200 flex items-center gap-1.5">
              <span className="w-5 h-5 rounded-full bg-slate-200 dark:bg-slate-700 flex items-center justify-center text-[10px] font-mono">6</span>
              <span>STCG Friction Netting</span>
            </div>
            <p className="text-[11px] text-slate-500">
              Nets tax and exchange charges to ensure after-friction alpha expectancy remains positive.
            </p>
          </div>
        </div>
      </div>

      {/* UI Placeholder: Future Contract Structure Mock View */}
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-5 shadow-xs space-y-4">
        <div className="flex items-center justify-between pb-3 border-b border-slate-100 dark:border-slate-800">
          <div>
            <h3 className="text-sm font-bold text-slate-900 dark:text-slate-100">
              Future Contract UI Placeholder Preview
            </h3>
            <p className="text-xs text-slate-500">
              Example pair structure awaiting live backend response payload
            </p>
          </div>
          <span className="text-[11px] font-mono bg-slate-100 dark:bg-slate-800 px-2 py-0.5 rounded text-slate-500">
            UI CONTRACT READY
          </span>
        </div>

        {/* Pair Card Placeholder */}
        {rotationRes?.data?.candidatePairs.map((pair) => (
          <div
            key={pair.id}
            id={pair.id}
            className="p-5 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50/60 dark:bg-slate-800/30 space-y-4"
          >
            {/* Context & Advantage header */}
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <span className="text-xs font-bold text-slate-700 dark:text-slate-300">
                  {pair.sectorContext}
                </span>
                <ConfidenceBadge confidence={pair.confidence} />
              </div>
              <div className="flex items-center gap-2">
                <span className="text-xs text-slate-500">Advantage:</span>
                <span className="font-mono text-sm font-bold text-emerald-600 dark:text-emerald-400">
                  +{pair.scoreAdvantage} pts
                </span>
                <ActionBadge action={pair.action} />
              </div>
            </div>

            {/* Holding vs Candidate Swap Visualizer */}
            <div className="grid grid-cols-1 md:grid-cols-11 gap-3 items-center">
              {/* Left: Current Holding */}
              <div className="md:col-span-5 p-4 rounded-lg bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 space-y-2">
                <div className="flex justify-between items-baseline">
                  <span className="text-[11px] uppercase font-bold text-rose-600 dark:text-rose-400">
                    Exit / Rotate Out
                  </span>
                  <ScoreBadge score={pair.currentHolding.score} size="sm" showLabel />
                </div>
                <div className="text-base font-bold text-slate-900 dark:text-slate-100 font-mono">
                  {pair.currentHolding.symbol}
                </div>
                <div className="text-xs text-slate-500 flex justify-between">
                  <span>Sector: {pair.currentHolding.sector}</span>
                  <span className="font-mono text-rose-500">
                    P&L: {formatPercent(pair.currentHolding.gainPct, { showSign: true })}
                  </span>
                </div>
              </div>

              {/* Center Arrow */}
              <div className="md:col-span-1 flex items-center justify-center">
                <div className="w-8 h-8 rounded-full bg-slate-200 dark:bg-slate-700 flex items-center justify-center text-slate-700 dark:text-slate-300">
                  <ArrowRight className="w-4 h-4" />
                </div>
              </div>

              {/* Right: Rotation Candidate */}
              <div className="md:col-span-5 p-4 rounded-lg bg-white dark:bg-slate-900 border border-emerald-500/30 space-y-2">
                <div className="flex justify-between items-baseline">
                  <span className="text-[11px] uppercase font-bold text-emerald-600 dark:text-emerald-400">
                    Enter / Rotate In
                  </span>
                  <ScoreBadge score={pair.candidate.score} size="sm" showLabel />
                </div>
                <div className="text-base font-bold text-slate-900 dark:text-slate-100 font-mono">
                  {pair.candidate.symbol}
                </div>
                <div className="text-xs text-slate-500 flex justify-between">
                  <span>Sector: {pair.candidate.sector}</span>
                  <span className="text-emerald-500 font-medium">Catalyst: {pair.candidate.expectedCatalyst}</span>
                </div>
              </div>
            </div>

            {/* Gates Check List */}
            <div className="p-3 rounded-lg bg-slate-100 dark:bg-slate-800/80 space-y-2">
              <div className="text-[11px] font-bold uppercase tracking-wider text-slate-500">
                Gate Status Checks ({pair.gates.length} Gates)
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-2">
                {pair.gates.map((g) => (
                  <div key={g.gateNumber} className="flex items-center gap-2 text-xs">
                    {g.passed ? (
                      <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500 shrink-0" />
                    ) : (
                      <XCircle className="w-3.5 h-3.5 text-rose-500 shrink-0" />
                    )}
                    <span className="font-semibold text-slate-800 dark:text-slate-200 truncate">
                      {g.name}:
                    </span>
                    <span className="text-slate-500 truncate text-[11px]">{g.statusText}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* Rationale note */}
            <p className="text-xs text-slate-600 dark:text-slate-400 italic">
              {pair.rationale}
            </p>
          </div>
        ))}
      </div>
    </div>
  );
};
