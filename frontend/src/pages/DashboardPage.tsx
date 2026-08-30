import React, { useEffect, useState } from 'react';
import {
  Activity,
  AlertOctagon,
  ArrowRight,
  BarChart3,
  Compass,
  Flame,
  Layers,
  PieChart,
  RefreshCw,
  Shield,
  TrendingDown,
  TrendingUp,
  Zap,
} from 'lucide-react';
import { useDataClient } from '../api/context';
import { useNavigation } from '../context/NavigationContext';
import { ApiResponse } from '../types/api';
import {
  MarketBreadthData,
  MarketExtremesData,
  MarketStateData,
  SectorLeadershipData,
} from '../types/market';
import { PortfolioSummaryData } from '../types/portfolio';
import { SignalsData } from '../types/signals';

import { MetricCard } from '../components/common/MetricCard';
import { SectionHeader } from '../components/common/SectionHeader';
import { ScoreBadge } from '../components/common/ScoreBadge';
import { ActionBadge } from '../components/common/ActionBadge';
import { ConfidenceBadge } from '../components/common/ConfidenceBadge';
import { RiskBadge } from '../components/common/RiskBadge';
import { DownsideStateBadge } from '../components/common/DownsideStateBadge';
import { UpsideStateBadge } from '../components/common/UpsideStateBadge';
import { StatusBadge } from '../components/common/StatusBadge';
import { ApiStateWrapper } from '../components/common/ApiStateWrapper';
import { WarningBanner } from '../components/common/WarningBanner';
import {
  formatCr,
  formatINR,
  formatNumber,
  formatPercent,
  formatRatio,
  formatScore,
} from '../utils/formatters';

export const DashboardPage: React.FC = () => {
  const { client, refreshTrigger, triggerRefresh } = useDataClient();
  const { navigate, navigateToStock } = useNavigation();

  // State for all 6 Dashboard data slices
  const [marketStateRes, setMarketStateRes] = useState<ApiResponse<MarketStateData> | null>(null);
  const [extremesRes, setExtremesRes] = useState<ApiResponse<MarketExtremesData> | null>(null);
  const [breadthRes, setBreadthRes] = useState<ApiResponse<MarketBreadthData> | null>(null);
  const [sectorsRes, setSectorsRes] = useState<ApiResponse<SectorLeadershipData> | null>(null);
  const [portfolioRes, setPortfolioRes] = useState<ApiResponse<PortfolioSummaryData> | null>(null);
  const [signalsRes, setSignalsRes] = useState<ApiResponse<SignalsData> | null>(null);

  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let isMounted = true;

    const fetchAll = async () => {
      setLoading(true);
      try {
        const [mState, mExtremes, mBreadth, mSectors, mPortfolio, mSignals] =
          await Promise.all([
            client.getMarketState(),
            client.getMarketExtremes(),
            client.getMarketBreadth(),
            client.getSectorLeadership(),
            client.getPortfolioSummary(),
            client.getSignals(),
          ]);

        if (isMounted) {
          setMarketStateRes(mState);
          setExtremesRes(mExtremes);
          setBreadthRes(mBreadth);
          setSectorsRes(mSectors);
          setPortfolioRes(mPortfolio);
          setSignalsRes(mSignals);
        }
      } catch (err) {
        console.error('Error fetching dashboard feeds:', err);
      } finally {
        if (isMounted) {
          setLoading(false);
        }
      }
    };

    fetchAll();

    return () => {
      isMounted = false;
    };
  }, [client, refreshTrigger]);

  return (
    <div id="dashboard-page" className="space-y-8 pb-12">
      {/* Top Controls & Freshness Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-white">
            Executive Market & Capital Rotation Monitor
          </h1>
          <p className="text-xs sm:text-sm text-gray-400 mt-0.5">
            NSE broad market regimes, systemic risk gates, sector rotation, and actionable high-conviction signals
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            id="dashboard-refresh-btn"
            onClick={triggerRefresh}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded bg-[#161616] border border-[#333] hover:border-gray-500 text-xs font-semibold text-gray-200 hover:text-white transition-colors"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            <span>Sync Live Feed</span>
          </button>
        </div>
      </div>

      {/* 1. MARKET REGIME & CRISIS/EUPHORIA MONITOR */}
      <section id="market-regime-section" className="space-y-4">
        <SectionHeader
          title="1. Market Regime & Extremes Monitor"
          subtitle="Backend broad market intelligence, macro risk regime, and systemic risk diagnostics"
          freshness={marketStateRes?.freshness}
          timestamp={marketStateRes?.timestamp}
        />

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 sm:gap-6">
          {/* Main Regime Card */}
          <div className="lg:col-span-2 bg-[#161616] border border-[#222] rounded-lg p-5 sm:p-6">
            <ApiStateWrapper<MarketStateData>
              response={marketStateRes}
              isLoading={loading}
              skeletonType="card"
              skeletonRows={2}
              onRetry={triggerRefresh}
            >
              {(data: MarketStateData) => (
                <div className="space-y-5">
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-4 border-b border-[#222]">
                    <div>
                      <div className="text-[10px] uppercase font-bold text-gray-500 tracking-wider">
                        Active Market Regime
                      </div>
                      <div className="text-xl sm:text-2xl font-bold text-white flex items-center gap-2 mt-1">
                        <Compass className="w-5 h-5 text-emerald-400 shrink-0" />
                        <span>{data.regimeLabel || data.regime.replace(/_/g, ' ')}</span>
                        <StatusBadge status={data.sessionStatus === 'OPEN' ? 'ONLINE' : 'DEGRADED'} />
                      </div>
                    </div>

                    <div className="flex items-center gap-2 self-start sm:self-auto font-mono text-xs flex-wrap">
                      <div className="px-3 py-1.5 rounded bg-black/40 border border-[#222] text-gray-300">
                        Nifty: <span className="font-bold text-white">{formatINR(data.nifty50.spot)}</span> (
                        <span className={(data.nifty50.pChange ?? 0) >= 0 ? 'text-emerald-400' : 'text-rose-400'}>
                          {formatPercent(data.nifty50.pChange, { showSign: true })}
                        </span>)
                      </div>
                      <div className="px-3 py-1.5 rounded bg-black/40 border border-[#222] text-gray-300">
                        Bank Nifty: <span className="font-bold text-white">{formatINR(data.bankNifty.spot)}</span>
                      </div>
                      <div className="px-3 py-1.5 rounded bg-black/40 border border-[#222] text-gray-300">
                        India VIX: <span className="font-bold text-white">{formatNumber(data.vix.current, { decimals: 2 })}</span>
                      </div>
                    </div>
                  </div>

                  {/* Regime Indicators Grid */}
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                    <div className="p-3 rounded bg-black/30 border border-[#222]">
                      <div className="text-[10px] text-gray-500 uppercase font-bold tracking-wider">Session Status</div>
                      <div className="text-sm font-bold text-white mt-1">
                        {data.sessionStatus}
                      </div>
                    </div>

                    <div className="p-3 rounded bg-black/30 border border-[#222]">
                      <div className="text-[10px] text-gray-500 uppercase font-bold tracking-wider">Regime Confidence</div>
                      <div className="text-sm font-bold font-mono text-blue-400 mt-1">
                        {data.regimeConfidencePct !== null ? `${data.regimeConfidencePct}%` : '—'}
                      </div>
                    </div>

                    <div className="p-3 rounded bg-black/30 border border-[#222]">
                      <div className="text-[10px] text-gray-500 uppercase font-bold tracking-wider">VIX Trend</div>
                      <div className="text-sm font-bold text-white mt-1">
                        {data.vix.trend ?? '—'}
                      </div>
                    </div>

                    <div className="p-3 rounded bg-black/30 border border-[#222]">
                      <div className="text-[10px] text-gray-500 uppercase font-bold tracking-wider">Time In Session</div>
                      <div className="text-sm font-bold text-white mt-1">
                        {data.sessionTimeRemaining || 'Active'}
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </ApiStateWrapper>
          </div>

          {/* Extremes (Downside Crisis & Upside Euphoria) */}
          <div className="bg-[#161616] border border-[#222] rounded-lg p-5 sm:p-6 flex flex-col justify-between space-y-4">
            <ApiStateWrapper<MarketExtremesData>
              response={extremesRes}
              isLoading={loading}
              skeletonType="card"
              skeletonRows={2}
              onRetry={triggerRefresh}
            >
              {(data: MarketExtremesData) => (
                <div className="space-y-4">
                  <div className="flex items-center justify-between">
                    <span className="text-[10px] uppercase font-bold text-gray-500 tracking-wider">
                      Market Extremes
                    </span>
                    <span className="text-[10px] font-mono text-gray-500">
                      Assessed: {data.lastAssessed ?? 'Live'}
                    </span>
                  </div>

                  {/* Crisis state */}
                  <div className="p-3 rounded bg-black/30 border border-[#222] space-y-1.5">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-semibold text-gray-200 flex items-center gap-1.5">
                        <AlertOctagon className="w-3.5 h-3.5 text-rose-400" />
                        <span>Downside Risk</span>
                      </span>
                      <DownsideStateBadge state={data.downsideState} score={data.downsideScore} showBar />
                    </div>
                    <p className="text-[11px] text-gray-400 leading-tight">
                      {data.downsideDescription}
                    </p>
                  </div>

                  {/* Euphoria state */}
                  <div className="p-3 rounded bg-black/30 border border-[#222] space-y-1.5">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-semibold text-gray-200 flex items-center gap-1.5">
                        <Flame className="w-3.5 h-3.5 text-amber-400" />
                        <span>Upside Excess</span>
                      </span>
                      <UpsideStateBadge state={data.upsideState} score={data.upsideScore} showBar />
                    </div>
                    <p className="text-[11px] text-gray-400 leading-tight">
                      {data.upsideDescription}
                    </p>
                  </div>

                  {/* Warning banner if elevated */}
                  {data.activeWarnings && data.activeWarnings.length > 0 && (
                    <WarningBanner
                      type="warning"
                      message={data.activeWarnings.join(' • ')}
                    />
                  )}
                </div>
              )}
            </ApiStateWrapper>
          </div>
        </div>
      </section>

      {/* 2. MARKET BREADTH & PARTICIPATION */}
      <section id="market-breadth-section" className="space-y-4">
        <SectionHeader
          title="2. Market Breadth & Participation"
          subtitle="Underlying market participation ratios and moving average health across 500 equities"
          freshness={breadthRes?.freshness}
          timestamp={breadthRes?.timestamp}
        />

        <div className="bg-[#161616] border border-[#222] rounded-lg p-5 sm:p-6">
          <ApiStateWrapper<MarketBreadthData>
            response={breadthRes}
            isLoading={loading}
            skeletonType="table"
            skeletonRows={2}
            onRetry={triggerRefresh}
          >
            {(data: MarketBreadthData) => (
              <div className="space-y-6">
                {/* Advance/Decline Visual Bar */}
                <div className="space-y-2">
                  <div className="flex justify-between text-xs font-mono font-medium">
                    <span className="text-emerald-400">
                      Advances: {data.advances ?? '—'} (
                      {data.advances !== null && data.declines !== null && data.unchanged !== null
                        ? `${Math.round((data.advances / (data.advances + data.declines + data.unchanged || 1)) * 100)}%`
                        : '—'}
                      )
                    </span>
                    <span className="text-gray-500">
                      Unchanged: {data.unchanged ?? '—'}
                    </span>
                    <span className="text-rose-400">
                      Declines: {data.declines ?? '—'} (
                      {data.advances !== null && data.declines !== null && data.unchanged !== null
                        ? `${Math.round((data.declines / (data.advances + data.declines + data.unchanged || 1)) * 100)}%`
                        : '—'}
                      )
                    </span>
                  </div>

                  <div className="h-2 w-full rounded-full bg-neutral-800 overflow-hidden flex">
                    <div
                      className="bg-emerald-500 transition-all duration-500"
                      style={{
                        width: `${
                          data.advances !== null && data.declines !== null && data.unchanged !== null
                            ? (data.advances / (data.advances + data.declines + data.unchanged || 1)) * 100
                            : 50
                        }%`,
                      }}
                    />
                    <div
                      className="bg-neutral-600 transition-all duration-500"
                      style={{
                        width: `${
                          data.unchanged !== null && data.advances !== null && data.declines !== null
                            ? (data.unchanged / (data.advances + data.declines + data.unchanged || 1)) * 100
                            : 0
                        }%`,
                      }}
                    />
                    <div
                      className="bg-rose-500 transition-all duration-500"
                      style={{
                        width: `${
                          data.declines !== null && data.advances !== null && data.declines !== null
                            ? (data.declines / (data.advances + data.declines + data.unchanged || 1)) * 100
                            : 50
                        }%`,
                      }}
                    />
                  </div>
                </div>

                {/* Key Breadth Metrics Grid */}
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                  <MetricCard
                    id="breadth-adr"
                    label="A/D Ratio"
                    value={formatRatio(data.advanceDeclineRatio, 'x')}
                    subtext="Market volume participation"
                  />

                  <MetricCard
                    id="breadth-50dma"
                    label="Stocks > 50 DMA"
                    value={formatPercent(data.above50DmaPct)}
                    subtext="Medium-term momentum"
                  />

                  <MetricCard
                    id="breadth-200dma"
                    label="Stocks > 200 DMA"
                    value={formatPercent(data.above200DmaPct)}
                    subtext="Long-term structural health"
                  />

                  <MetricCard
                    id="breadth-concentration"
                    label="Participation Score"
                    value={data.participationScore !== null ? `${data.participationScore}/100` : '—'}
                    badge={
                      data.leadershipConcentration?.isConcentrated ? (
                        <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-amber-500/15 text-amber-400 border border-amber-500/30">
                          Concentrated
                        </span>
                      ) : undefined
                    }
                    subtext="Breadth thrust dispersion"
                  />
                </div>
              </div>
            )}
          </ApiStateWrapper>
        </div>
      </section>

      {/* 3. SECTOR ROTATION & LEADERSHIP MATRIX */}
      <section id="sector-rotation-section" className="space-y-4">
        <SectionHeader
          title="3. Sector Rotation & Leadership Matrix"
          subtitle="Relative strength phases (Leading, Improving, Weakening, Lagging) computed by backend algorithms"
          freshness={sectorsRes?.freshness}
          timestamp={sectorsRes?.timestamp}
        />

        <div className="bg-[#161616] border border-[#222] rounded-lg p-5 sm:p-6">
          <ApiStateWrapper<SectorLeadershipData>
            response={sectorsRes}
            isLoading={loading}
            skeletonType="table"
            skeletonRows={4}
            onRetry={triggerRefresh}
          >
            {(data: SectorLeadershipData) => (
              <div className="space-y-4">
                {data.summaryNote && (
                  <p className="text-xs text-gray-400 italic font-mono">
                    {data.summaryNote}
                  </p>
                )}

                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                  {/* Leading */}
                  <div className="rounded-lg border border-emerald-900/40 bg-emerald-950/20 p-4 space-y-3">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-bold uppercase tracking-wider text-emerald-400 flex items-center gap-1.5">
                        <TrendingUp className="w-4 h-4 text-emerald-400" />
                        <span>Leading</span>
                      </span>
                      <span className="text-[11px] font-mono font-bold px-1.5 py-0.5 rounded bg-emerald-900/60 text-emerald-300">
                        {data.leadingSectors.length}
                      </span>
                    </div>

                    <div className="space-y-2">
                      {data.leadingSectors.map((s) => (
                        <div
                          key={s.id}
                          className="bg-[#111] p-2.5 rounded border border-[#222] text-xs flex justify-between items-center"
                        >
                          <div>
                            <div className="font-semibold text-white">
                              {s.name}
                            </div>
                            <div className="text-[10px] text-gray-500 font-mono">
                              Rank: #{s.relativeStrengthRank ?? '—'}
                            </div>
                          </div>
                          <div className="text-right font-mono">
                            <div
                              className={`font-semibold ${
                                (s.oneDayChangePct ?? 0) >= 0
                                  ? 'text-emerald-400'
                                  : 'text-rose-400'
                              }`}
                            >
                              {formatPercent(s.oneDayChangePct, { showSign: true })}
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Improving */}
                  <div className="rounded-lg border border-sky-900/40 bg-sky-950/20 p-4 space-y-3">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-bold uppercase tracking-wider text-sky-400 flex items-center gap-1.5">
                        <Activity className="w-4 h-4 text-sky-400" />
                        <span>Improving</span>
                      </span>
                      <span className="text-[11px] font-mono font-bold px-1.5 py-0.5 rounded bg-sky-900/60 text-sky-300">
                        {data.improvingSectors.length}
                      </span>
                    </div>

                    <div className="space-y-2">
                      {data.improvingSectors.map((s) => (
                        <div
                          key={s.id}
                          className="bg-[#111] p-2.5 rounded border border-[#222] text-xs flex justify-between items-center"
                        >
                          <div>
                            <div className="font-semibold text-white">
                              {s.name}
                            </div>
                            <div className="text-[10px] text-gray-500 font-mono">
                              Rank: #{s.relativeStrengthRank ?? '—'}
                            </div>
                          </div>
                          <div className="text-right font-mono">
                            <div
                              className={`font-semibold ${
                                (s.oneDayChangePct ?? 0) >= 0
                                  ? 'text-emerald-400'
                                  : 'text-rose-400'
                              }`}
                            >
                              {formatPercent(s.oneDayChangePct, { showSign: true })}
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Weakening */}
                  <div className="rounded-lg border border-amber-900/40 bg-amber-950/20 p-4 space-y-3">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-bold uppercase tracking-wider text-amber-400 flex items-center gap-1.5">
                        <TrendingDown className="w-4 h-4 text-amber-400" />
                        <span>Weakening</span>
                      </span>
                      <span className="text-[11px] font-mono font-bold px-1.5 py-0.5 rounded bg-amber-900/60 text-amber-300">
                        {data.weakeningSectors.length}
                      </span>
                    </div>

                    <div className="space-y-2">
                      {data.weakeningSectors.map((s) => (
                        <div
                          key={s.id}
                          className="bg-[#111] p-2.5 rounded border border-[#222] text-xs flex justify-between items-center"
                        >
                          <div>
                            <div className="font-semibold text-white">
                              {s.name}
                            </div>
                            <div className="text-[10px] text-gray-500 font-mono">
                              Rank: #{s.relativeStrengthRank ?? '—'}
                            </div>
                          </div>
                          <div className="text-right font-mono">
                            <div
                              className={`font-semibold ${
                                (s.oneDayChangePct ?? 0) >= 0
                                  ? 'text-emerald-400'
                                  : 'text-rose-400'
                              }`}
                            >
                              {formatPercent(s.oneDayChangePct, { showSign: true })}
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Lagging */}
                  <div className="rounded-lg border border-rose-900/40 bg-rose-950/20 p-4 space-y-3">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-bold uppercase tracking-wider text-rose-400 flex items-center gap-1.5">
                        <TrendingDown className="w-4 h-4 text-rose-400" />
                        <span>Lagging</span>
                      </span>
                      <span className="text-[11px] font-mono font-bold px-1.5 py-0.5 rounded bg-rose-900/60 text-rose-300">
                        {data.laggingSectors.length}
                      </span>
                    </div>

                    <div className="space-y-2">
                      {data.laggingSectors.map((s) => (
                        <div
                          key={s.id}
                          className="bg-[#111] p-2.5 rounded border border-[#222] text-xs flex justify-between items-center"
                        >
                          <div>
                            <div className="font-semibold text-white">
                              {s.name}
                            </div>
                            <div className="text-[10px] text-gray-500 font-mono">
                              Rank: #{s.relativeStrengthRank ?? '—'}
                            </div>
                          </div>
                          <div className="text-right font-mono">
                            <div
                              className={`font-semibold ${
                                (s.oneDayChangePct ?? 0) >= 0
                                  ? 'text-emerald-400'
                                  : 'text-rose-400'
                              }`}
                            >
                              {formatPercent(s.oneDayChangePct, { showSign: true })}
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            )}
          </ApiStateWrapper>
        </div>
      </section>

      {/* 4. PORTFOLIO CAPITAL & RISK HEALTH */}
      <section id="portfolio-capital-section" className="space-y-4">
        <div className="flex items-center justify-between">
          <SectionHeader
            title="4. Portfolio Capital & Risk Health"
            subtitle="Allocation health, aggregate heat score, and individual holding diagnostics"
            freshness={portfolioRes?.freshness}
            timestamp={portfolioRes?.timestamp}
          />
          <button
            id="view-full-portfolio-btn"
            onClick={() => navigate('/portfolio')}
            className="text-xs font-semibold text-blue-400 hover:text-blue-300 flex items-center gap-1 shrink-0"
          >
            <span>Full Holdings</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </button>
        </div>

        <div className="bg-[#161616] border border-[#222] rounded-lg p-5 sm:p-6">
          <ApiStateWrapper<PortfolioSummaryData>
            response={portfolioRes}
            isLoading={loading}
            skeletonType="card"
            skeletonRows={2}
            onRetry={triggerRefresh}
          >
            {(data: PortfolioSummaryData) => (
              <div className="space-y-6">
                {/* Metric Strip */}
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                  <MetricCard
                    id="port-invested"
                    label="Invested Value"
                    value={data.investedValue !== null ? formatINR(data.investedValue) : '—'}
                    subtext={data.cashAvailable !== null ? `Cash Reserve: ${formatINR(data.cashAvailable)}` : undefined}
                  />

                  <MetricCard
                    id="port-current"
                    label="Current Portfolio Value"
                    value={data.currentValue !== null ? formatINR(data.currentValue) : '—'}
                    subtext={`Deployed: ${formatPercent(data.capitalDeployedPct)}`}
                  />

                  <MetricCard
                    id="port-total-pnl"
                    label="Total Unrealized P&L"
                    value={data.totalPnL !== null ? formatINR(data.totalPnL, { showSign: true }) : '—'}
                    change={data.totalPnLPct}
                    subtext="All-time return"
                  />

                  <MetricCard
                    id="port-today-pnl"
                    label="Today's Movement"
                    value={data.todayPnL !== null ? formatINR(data.todayPnL, { showSign: true }) : '—'}
                    change={data.todayPnLPct}
                    badge={<RiskBadge risk={data.portfolioRiskLevel} />}
                    subtext={`Heat Score: ${data.portfolioHeatScore ?? '—'}/100`}
                  />
                </div>

                {/* Strongest vs Weakest Holding Highlights */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  {data.strongestHolding && (
                    <div
                      onClick={() => navigateToStock(data.strongestHolding!.symbol)}
                      className="p-3.5 rounded-lg border border-[#222] bg-[#111] cursor-pointer hover:border-emerald-500/50 transition-colors flex items-center justify-between"
                    >
                      <div>
                        <div className="text-[10px] font-bold text-emerald-400 uppercase tracking-wider">
                          Top Performer
                        </div>
                        <div className="text-sm font-bold font-mono text-white mt-0.5">
                          {data.strongestHolding.symbol}
                        </div>
                        <div className="text-xs font-mono text-emerald-400">
                          Gain: {formatPercent(data.strongestHolding.currentGainPct, { showSign: true })}
                        </div>
                      </div>
                      <ScoreBadge score={data.strongestHolding.score} size="sm" />
                    </div>
                  )}

                  {data.weakestHolding && (
                    <div
                      onClick={() => navigateToStock(data.weakestHolding!.symbol)}
                      className="p-3.5 rounded-lg border border-[#222] bg-[#111] cursor-pointer hover:border-rose-500/50 transition-colors flex items-center justify-between"
                    >
                      <div>
                        <div className="text-[10px] font-bold text-rose-400 uppercase tracking-wider">
                          Position at Risk / Lagging
                        </div>
                        <div className="text-sm font-bold font-mono text-white mt-0.5">
                          {data.weakestHolding.symbol}
                        </div>
                        <div className="text-xs font-mono text-rose-400">
                          Loss: {formatPercent(data.weakestHolding.currentLossPct, { showSign: true })}
                        </div>
                        <div className="text-[11px] text-gray-500 truncate max-w-[200px]">
                          {data.weakestHolding.reason}
                        </div>
                      </div>
                      <ScoreBadge score={data.weakestHolding.score} size="sm" />
                    </div>
                  )}
                </div>
              </div>
            )}
          </ApiStateWrapper>
        </div>
      </section>

      {/* 5. ACTIVE SIGNALS SNAPSHOT */}
      <section id="active-signals-section" className="space-y-4">
        <div className="flex items-center justify-between">
          <SectionHeader
            title="5. Actionable High-Conviction Signals"
            subtitle="Distilled backend signals with execution gates, entry/stop levels, and calculated risk-reward"
            freshness={signalsRes?.freshness}
            timestamp={signalsRes?.timestamp}
          />
          <button
            id="view-all-signals-btn"
            onClick={() => navigate('/signals')}
            className="text-xs font-semibold text-blue-400 hover:text-blue-300 flex items-center gap-1 shrink-0"
          >
            <span>All Signals</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </button>
        </div>

        <div className="bg-[#161616] border border-[#222] rounded-lg p-5 sm:p-6">
          <ApiStateWrapper<SignalsData>
            response={signalsRes}
            isLoading={loading}
            skeletonType="card"
            skeletonRows={3}
            onRetry={triggerRefresh}
          >
            {(data: SignalsData) => (
              <div className="space-y-3">
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                  {data.activeSignals.slice(0, 3).map((sig) => (
                    <div
                      key={sig.id}
                      onClick={() => navigateToStock(sig.symbol)}
                      className="p-4 rounded-lg bg-[#111] border border-[#222] hover:border-blue-500/50 transition-all cursor-pointer space-y-3 group"
                    >
                      <div className="flex items-center justify-between">
                        <div>
                          <div className="text-base font-bold font-mono text-white group-hover:text-blue-400 transition-colors">
                            {sig.symbol}
                          </div>
                          <div className="text-[11px] text-gray-500 font-mono">{sig.sector}</div>
                        </div>
                        <ActionBadge action={sig.action} />
                      </div>

                      <div className="flex items-center justify-between border-t border-b border-[#222] py-2 text-xs font-mono">
                        <div>
                          <div className="text-[10px] text-gray-500 uppercase font-sans">Decision Score</div>
                          <div className="flex items-center gap-1 mt-0.5">
                            <ScoreBadge score={sig.score} size="sm" />
                            <ConfidenceBadge confidence={sig.confidence} />
                          </div>
                        </div>

                        <div className="text-right">
                          <div className="text-[10px] text-gray-500 uppercase font-sans">Risk / Reward</div>
                          <div className="font-bold text-white mt-0.5">
                            {formatRatio(sig.riskRewardRatio, '')}
                          </div>
                        </div>
                      </div>

                      {/* Levels */}
                      <div className="grid grid-cols-3 text-center text-xs font-mono gap-1.5">
                        <div className="p-1 rounded bg-black/40 border border-[#222]">
                          <div className="text-[9px] text-gray-500 font-sans">Entry</div>
                          <div className="font-semibold text-white">{formatINR(sig.entryPrice)}</div>
                        </div>
                        <div className="p-1 rounded bg-rose-500/10 border border-rose-500/20 text-rose-400">
                          <div className="text-[9px] font-sans">Stop</div>
                          <div className="font-bold">{formatINR(sig.stopLoss)}</div>
                        </div>
                        <div className="p-1 rounded bg-emerald-500/10 border border-emerald-500/20 text-emerald-400">
                          <div className="text-[9px] font-sans">Target 1</div>
                          <div className="font-bold">{formatINR(sig.target1)}</div>
                        </div>
                      </div>

                      <p className="text-xs text-gray-400 line-clamp-2 leading-relaxed">
                        {sig.shortRationale}
                      </p>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </ApiStateWrapper>
        </div>
      </section>
    </div>
  );
};
