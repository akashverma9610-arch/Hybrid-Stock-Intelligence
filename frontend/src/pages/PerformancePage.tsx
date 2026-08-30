import React, { useEffect, useState } from 'react';
import {
  Award,
  BarChart3,
  CheckCircle,
  Percent,
  ShieldAlert,
  TrendingUp,
} from 'lucide-react';
import { useDataClient } from '../api/context';
import { ApiResponse } from '../types/api';
import { PerformanceData } from '../types/performance';
import { SectionHeader } from '../components/common/SectionHeader';
import { MetricCard } from '../components/common/MetricCard';
import { ApiStateWrapper } from '../components/common/ApiStateWrapper';
import { formatPercent, formatRatio } from '../utils/formatters';

export const PerformancePage: React.FC = () => {
  const { client, refreshTrigger } = useDataClient();
  const [perfRes, setPerfRes] = useState<ApiResponse<PerformanceData> | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let isMounted = true;
    const fetchPerformance = async () => {
      setLoading(true);
      try {
        const res = await client.getPerformance();
        if (isMounted) setPerfRes(res);
      } catch (err) {
        console.error('Failed to load performance analytics:', err);
      } finally {
        if (isMounted) setLoading(false);
      }
    };

    fetchPerformance();
    return () => {
      isMounted = false;
    };
  }, [client, refreshTrigger]);

  return (
    <div id="performance-page" className="space-y-6">
      <SectionHeader
        title="Historical & Backtested Performance Analytics"
        subtitle="Benchmark alpha, drawdown dynamics, Sharpe/Sortino ratios, and monthly attribution"
        freshness={perfRes?.freshness}
        timestamp={perfRes?.timestamp}
      />

      <ApiStateWrapper<PerformanceData>
        response={perfRes}
        isLoading={loading}
        skeletonType="card"
        skeletonRows={4}
      >
        {(data: PerformanceData) => (
          <div className="space-y-6">
            {/* Top Alpha & Return Cards */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              <MetricCard
                id="perf-total-return"
                label="Strategy Total Return"
                value={formatPercent(data.totalReturnPct, { showSign: true })}
                change={data.totalReturnPct}
                subtext={`Timeframe: ${data.timeframe}`}
              />

              <MetricCard
                id="perf-benchmark"
                label="Nifty 50 Benchmark"
                value={formatPercent(data.benchmarkReturnPct, { showSign: true })}
                change={data.benchmarkReturnPct}
                subtext="Broad market baseline"
              />

              <MetricCard
                id="perf-alpha"
                label="Generated Alpha"
                value={formatPercent(data.alphaPct, { showSign: true })}
                badge={<span className="text-[10px] font-mono font-bold px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-600 dark:text-emerald-400">Alpha Outperformance</span>}
                subtext="Excess return over benchmark"
              />

              <MetricCard
                id="perf-drawdown"
                label="Max Historical Drawdown"
                value={formatPercent(data.maxDrawdownPct, { showSign: true })}
                subtext="Peak-to-trough systemic risk"
              />
            </div>

            {/* Risk-Adjusted Metrics Matrix */}
            <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-5 sm:p-6 shadow-xs space-y-4">
              <div className="text-sm font-bold text-slate-900 dark:text-slate-100 flex items-center gap-2">
                <BarChart3 className="w-4 h-4 text-sky-500" />
                <span>Risk-Adjusted Ratios & Statistical Robustness</span>
              </div>

              <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
                <div className="p-3 rounded-lg bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-800">
                  <div className="text-[11px] text-slate-400 font-medium">Sharpe Ratio</div>
                  <div className="text-base font-bold font-mono text-slate-900 dark:text-slate-100 mt-1">
                    {formatRatio(data.sharpeRatio, '')}
                  </div>
                </div>

                <div className="p-3 rounded-lg bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-800">
                  <div className="text-[11px] text-slate-400 font-medium">Sortino Ratio</div>
                  <div className="text-base font-bold font-mono text-slate-900 dark:text-slate-100 mt-1">
                    {formatRatio(data.sortinoRatio, '')}
                  </div>
                </div>

                <div className="p-3 rounded-lg bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-800">
                  <div className="text-[11px] text-slate-400 font-medium">Calmar Ratio</div>
                  <div className="text-base font-bold font-mono text-slate-900 dark:text-slate-100 mt-1">
                    {formatRatio(data.calmarRatio, '')}
                  </div>
                </div>

                <div className="p-3 rounded-lg bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-800">
                  <div className="text-[11px] text-slate-400 font-medium">Win Rate</div>
                  <div className="text-base font-bold font-mono text-emerald-600 dark:text-emerald-400 mt-1">
                    {formatPercent(data.winRatePct)}
                  </div>
                </div>

                <div className="p-3 rounded-lg bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-800">
                  <div className="text-[11px] text-slate-400 font-medium">Profit Factor</div>
                  <div className="text-base font-bold font-mono text-slate-900 dark:text-slate-100 mt-1">
                    {formatRatio(data.profitFactor, 'x')}
                  </div>
                </div>

                <div className="p-3 rounded-lg bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-800">
                  <div className="text-[11px] text-slate-400 font-medium">Expectancy</div>
                  <div className="text-base font-bold font-mono text-slate-900 dark:text-slate-100 mt-1">
                    {data.expectancyR !== null ? `${data.expectancyR > 0 ? '+' : ''}${data.expectancyR.toFixed(2)}R` : '—'}
                  </div>
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-2 text-xs text-slate-500 border-t border-slate-100 dark:border-slate-800">
                <div>Portfolio Turnover: <strong className="font-mono text-slate-800 dark:text-slate-200">{formatPercent(data.portfolioTurnoverPct)}</strong></div>
                <div>Capital Efficiency Score: <strong className="font-mono text-slate-800 dark:text-slate-200">{data.capitalEfficiencyScore ?? '—'}/100</strong></div>
              </div>
            </div>

            {/* Monthly Breakdown Table */}
            <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-5 sm:p-6 shadow-xs space-y-4">
              <div className="text-sm font-bold text-slate-900 dark:text-slate-100">
                Monthly Attribution Breakdown
              </div>

              <div className="overflow-x-auto">
                <table className="w-full text-xs text-left">
                  <thead className="bg-slate-50 dark:bg-slate-800/60 border-b border-slate-200 dark:border-slate-800 text-[11px] uppercase tracking-wider text-slate-500 font-mono">
                    <tr>
                      <th className="py-2 px-3">Month</th>
                      <th className="py-2 px-3 text-right">Strategy Return</th>
                      <th className="py-2 px-3 text-right">Benchmark Return</th>
                      <th className="py-2 px-3 text-right">Alpha (Spread)</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 dark:divide-slate-800/60 font-mono">
                    {data.monthlyBreakdown.map((m, idx) => {
                      const alpha = m.returnPct !== null && m.benchmarkPct !== null ? m.returnPct - m.benchmarkPct : null;
                      const isStratPos = (m.returnPct ?? 0) >= 0;
                      const isAlphaPos = (alpha ?? 0) >= 0;

                      return (
                        <tr key={idx} className="hover:bg-slate-50/50 dark:hover:bg-slate-800/30">
                          <td className="py-2 px-3 font-semibold text-slate-900 dark:text-slate-100">{m.month}</td>
                          <td className={`py-2 px-3 text-right font-bold ${isStratPos ? 'text-emerald-600 dark:text-emerald-400' : 'text-rose-600 dark:text-rose-400'}`}>
                            {formatPercent(m.returnPct, { showSign: true })}
                          </td>
                          <td className="py-2 px-3 text-right text-slate-500">
                            {formatPercent(m.benchmarkPct, { showSign: true })}
                          </td>
                          <td className={`py-2 px-3 text-right font-bold ${isAlphaPos ? 'text-emerald-600 dark:text-emerald-400' : 'text-rose-600 dark:text-rose-400'}`}>
                            {formatPercent(alpha, { showSign: true })}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}
      </ApiStateWrapper>
    </div>
  );
};
