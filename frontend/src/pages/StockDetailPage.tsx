import React, { useEffect, useState } from 'react';
import {
  ArrowLeft,
  Calendar,
  Compass,
  FileText,
  LineChart,
  Layers,
} from 'lucide-react';
import { useDataClient } from '../api/context';
import { useNavigation } from '../context/NavigationContext';
import { ApiResponse } from '../types/api';
import { SharedBrainAnalysisData, StockDetailData } from '../types/stock';
import { SectionHeader } from '../components/common/SectionHeader';
import { ScoreBadge } from '../components/common/ScoreBadge';
import { ConfidenceBadge } from '../components/common/ConfidenceBadge';
import { ActionBadge } from '../components/common/ActionBadge';
import { RiskBadge } from '../components/common/RiskBadge';
import { ApiStateWrapper } from '../components/common/ApiStateWrapper';
import { FinancialIntelligencePanel } from '../components/stocks/FinancialIntelligencePanel';
import { ForwardPerformanceIntelligencePanel } from '../components/stocks/ForwardPerformanceIntelligencePanel';
import {
  formatCr,
  formatINR,
  formatPercent,
  formatRatio,
} from '../utils/formatters';

export const StockDetailPage: React.FC = () => {
  const { client, refreshTrigger } = useDataClient();
  const { params, navigate } = useNavigation();
  const symbol = params.symbol || 'M&M';

  const [stockRes, setStockRes] = useState<ApiResponse<StockDetailData> | null>(null);
  const [sharedBrainRes, setSharedBrainRes] = useState<ApiResponse<SharedBrainAnalysisData> | null>(null);
  const [loading, setLoading] = useState(true);
  const [sharedBrainLoading, setSharedBrainLoading] = useState(true);

  useEffect(() => {
    let isMounted = true;
    const fetchDetail = async () => {
      setLoading(true);
      try {
        const res = await client.getStockDetail(symbol);
        if (isMounted) setStockRes(res);
      } catch (err) {
        console.error('Failed to load stock detail:', err);
      } finally {
        if (isMounted) setLoading(false);
      }
    };

    fetchDetail();
    return () => {
      isMounted = false;
    };
  }, [client, symbol, refreshTrigger]);

  useEffect(() => {
    let isMounted = true;
    const fetchSharedBrain = async () => {
      setSharedBrainLoading(true);
      try {
        const res = await client.getSharedBrainAnalysis(symbol);
        if (isMounted) setSharedBrainRes(res);
      } catch (err) {
        console.error('Failed to load Shared Brain analysis:', err);
      } finally {
        if (isMounted) setSharedBrainLoading(false);
      }
    };
    fetchSharedBrain();
    return () => { isMounted = false; };
  }, [client, symbol, refreshTrigger]);

  return (
    <div id="stock-detail-page" className="space-y-6">
      {/* Back button & Header */}
      <div className="flex items-center gap-3">
        <button
          id="back-to-stocks-btn"
          onClick={() => navigate('/stocks')}
          className="inline-flex items-center gap-1 px-3 py-1.5 rounded-md bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 text-xs font-semibold text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors shadow-2xs"
        >
          <ArrowLeft className="w-4 h-4" />
          <span>Back to Equities List</span>
        </button>
      </div>

      <ApiStateWrapper<StockDetailData>
        response={stockRes}
        isLoading={loading}
        skeletonType="card"
        skeletonRows={4}
      >
        {(stock: StockDetailData) => (
          <div className="space-y-6">
            {/* 1. OVERVIEW & DISTILLED DECISION SCORE HEADER */}
            <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-5 sm:p-6 shadow-xs">
              <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-6 pb-6 border-b border-slate-100 dark:border-slate-800">
                <div>
                  <div className="flex items-center gap-3 flex-wrap">
                    <h1 className="text-2xl sm:text-3xl font-black font-mono tracking-tight text-slate-900 dark:text-slate-100">
                      {stock.symbol}
                    </h1>
                    <ActionBadge action={stock.action} size="md" />
                    <ScoreBadge score={stock.decisionScore} size="lg" showLabel />
                    <ConfidenceBadge confidence={stock.confidence} />
                    <RiskBadge risk={stock.riskExecution.riskRating} />
                  </div>
                  <div className="text-sm font-semibold text-slate-600 dark:text-slate-400 mt-1">
                    {stock.companyName}
                  </div>
                  <div className="text-xs text-slate-400 mt-0.5 flex items-center gap-2 flex-wrap font-mono">
                    <span>ISIN: {stock.isin ?? '—'}</span>
                    <span>•</span>
                    <span>Sector: {stock.sector}</span>
                    <span>•</span>
                    <span>Industry: {stock.industry ?? '—'}</span>
                  </div>
                </div>

                {/* Live Quote Block */}
                <div className="flex items-baseline lg:items-end flex-col font-mono shrink-0">
                  <div className="text-2xl sm:text-3xl font-bold text-slate-900 dark:text-slate-100">
                    {formatINR(stock.currentPrice)}
                  </div>
                  <div className="flex items-center gap-2 text-xs">
                    <span
                      className={`font-semibold ${
                        (stock.dayChangePct ?? 0) >= 0
                          ? 'text-emerald-600 dark:text-emerald-400'
                          : 'text-rose-600 dark:text-rose-400'
                      }`}
                    >
                      {formatPercent(stock.dayChangePct, { showSign: true })}
                    </span>
                    <span className="text-slate-400">
                      Range: {formatINR(stock.dayLow)} - {formatINR(stock.dayHigh)}
                    </span>
                  </div>
                </div>
              </div>

              {/* Distilled Rationale */}
              <div className="mt-4 p-4 rounded-lg bg-slate-50 dark:bg-slate-800/40 border border-slate-200 dark:border-slate-800">
                <div className="text-[11px] font-bold uppercase tracking-wider text-slate-500 mb-1">
                  Distilled Investment Rationale
                </div>
                <p className="text-xs sm:text-sm text-slate-800 dark:text-slate-200 leading-relaxed">
                  {stock.distilledRationale}
                </p>
              </div>
            </div>

            {/* 2. THREE-PANEL SUMMARY GRID */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              {/* Market Context */}
              <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-5 shadow-xs space-y-3">
                <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-slate-500">
                  <Compass className="w-4 h-4 text-emerald-500" />
                  <span>Market Context</span>
                </div>
                <div className="divide-y divide-slate-100 dark:divide-slate-800 text-xs">
                  <div className="py-2 flex justify-between">
                    <span className="text-slate-500">Sector Group</span>
                    <span className="font-semibold text-slate-900 dark:text-slate-100">{stock.marketContext.sectorName ?? stock.sector}</span>
                  </div>
                  <div className="py-2 flex justify-between">
                    <span className="text-slate-500">Sector Rank</span>
                    <span className="font-mono font-bold text-emerald-600 dark:text-emerald-400">#{stock.marketContext.sectorRank ?? '—'}</span>
                  </div>
                  <div className="py-2 flex justify-between">
                    <span className="text-slate-500">Sector Phase</span>
                    <span className="font-semibold">{stock.marketContext.sectorPhase ?? '—'}</span>
                  </div>
                  <div className="py-2 flex justify-between">
                    <span className="text-slate-500">Market Cap</span>
                    <span className="font-mono">{formatCr(stock.marketCapCr)}</span>
                  </div>
                </div>
              </div>

              {/* Technical Summary */}
              <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-5 shadow-xs space-y-3">
                <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-slate-500">
                  <LineChart className="w-4 h-4 text-sky-500" />
                  <span>Technical Structure</span>
                </div>
                <div className="divide-y divide-slate-100 dark:divide-slate-800 text-xs">
                  <div className="py-2 flex justify-between">
                    <span className="text-slate-500">Trend Classification</span>
                    <span className="font-semibold text-right max-w-[160px] truncate">{stock.technicalSummary.trendClassification ?? '—'}</span>
                  </div>
                  <div className="py-2 flex justify-between">
                    <span className="text-slate-500">50 DMA / 200 DMA</span>
                    <span className="font-mono">{formatINR(stock.technicalSummary.dma50)} / {formatINR(stock.technicalSummary.dma200)}</span>
                  </div>
                  <div className="py-2 flex justify-between">
                    <span className="text-slate-500">Support / Resistance</span>
                    <span className="font-mono">{formatINR(stock.technicalSummary.supportLevel)} / {formatINR(stock.technicalSummary.resistanceLevel)}</span>
                  </div>
                  <div className="py-2 flex justify-between">
                    <span className="text-slate-500">Daily ATR Volatility</span>
                    <span className="font-mono">{formatINR(stock.technicalSummary.volatilityAtr)}</span>
                  </div>
                </div>
              </div>

              {/* Fundamentals Summary */}
              <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-5 shadow-xs space-y-3">
                <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-slate-500">
                  <Layers className="w-4 h-4 text-purple-500" />
                  <span>Fundamentals Snapshot</span>
                </div>
                <div className="divide-y divide-slate-100 dark:divide-slate-800 text-xs">
                  <div className="py-2 flex justify-between">
                    <span className="text-slate-500">P/E vs Sector P/E</span>
                    <span className="font-mono">{formatRatio(stock.fundamentalsSummary.peRatio, '')} (Sec: {formatRatio(stock.fundamentalsSummary.sectorPe, '')})</span>
                  </div>
                  <div className="py-2 flex justify-between">
                    <span className="text-slate-500">P/B Ratio</span>
                    <span className="font-mono">{formatRatio(stock.fundamentalsSummary.pbRatio, '')}</span>
                  </div>
                  <div className="py-2 flex justify-between">
                    <span className="text-slate-500">ROE / ROCE</span>
                    <span className="font-mono">{formatPercent(stock.fundamentalsSummary.roePct)} / {formatPercent(stock.fundamentalsSummary.rocePct)}</span>
                  </div>
                  <div className="py-2 flex justify-between">
                    <span className="text-slate-500">YoY Revenue / Profit Growth</span>
                    <span className="font-mono font-semibold text-emerald-600 dark:text-emerald-400">
                      {formatPercent(stock.fundamentalsSummary.quarterlyRevenueGrowthYoY, { showSign: true })} / {formatPercent(stock.fundamentalsSummary.quarterlyProfitGrowthYoY, { showSign: true })}
                    </span>
                  </div>
                </div>
              </div>
            </div>

            {/* 3. EXECUTION LEVELS & CATALYST RESEARCH */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* Execution & Risk Guidance */}
              <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-5 shadow-xs space-y-4">
                <SectionHeader
                  title="Execution Levels & Risk Guidance"
                  subtitle="Backend structural stop and target levels for capital deployment"
                />

                <div className="grid grid-cols-3 gap-3 font-mono text-center">
                  <div className="p-3 rounded-lg bg-rose-500/10 border border-rose-500/20">
                    <div className="text-[10px] uppercase font-bold text-rose-700 dark:text-rose-400">Stop Loss</div>
                    <div className="text-base font-bold text-rose-700 dark:text-rose-300 mt-1">
                      {formatINR(stock.riskExecution.suggestedStopLoss)}
                    </div>
                  </div>

                  <div className="p-3 rounded-lg bg-emerald-500/10 border border-emerald-500/20">
                    <div className="text-[10px] uppercase font-bold text-emerald-700 dark:text-emerald-400">Target 1</div>
                    <div className="text-base font-bold text-emerald-700 dark:text-emerald-300 mt-1">
                      {formatINR(stock.riskExecution.suggestedTarget1)}
                    </div>
                  </div>

                  <div className="p-3 rounded-lg bg-emerald-500/10 border border-emerald-500/20">
                    <div className="text-[10px] uppercase font-bold text-emerald-700 dark:text-emerald-400">Target 2</div>
                    <div className="text-base font-bold text-emerald-700 dark:text-emerald-300 mt-1">
                      {formatINR(stock.riskExecution.suggestedTarget2)}
                    </div>
                  </div>
                </div>

                <div className="text-xs text-slate-500 flex justify-between pt-2 border-t border-slate-100 dark:border-slate-800">
                  <span>Liquidity Score: <strong className="font-mono text-slate-800 dark:text-slate-200">{stock.riskExecution.liquidityScore ?? '—'}/100</strong></span>
                  <span>Est Slippage: <strong className="font-mono text-slate-800 dark:text-slate-200">{formatPercent(stock.riskExecution.slippageEstPct)}</strong></span>
                </div>
              </div>

              {/* Upcoming Catalysts & Recent Filings */}
              <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-5 shadow-xs space-y-4">
                <SectionHeader
                  title="Catalyst Calendar & Exchange Filings"
                  subtitle="Key upcoming dates and regulatory disclosures"
                />

                <div className="space-y-3">
                  <div>
                    <div className="text-[11px] font-bold uppercase text-slate-500 mb-2 flex items-center gap-1.5">
                      <Calendar className="w-3.5 h-3.5" />
                      <span>Upcoming Catalysts</span>
                    </div>
                    <div className="space-y-1.5">
                      {stock.catalystResearch.upcomingEvents.map((evt, idx) => (
                        <div key={idx} className="p-2 rounded bg-slate-50 dark:bg-slate-800/40 border border-slate-200 dark:border-slate-800 text-xs flex justify-between gap-2">
                          <span className="font-semibold text-slate-800 dark:text-slate-200 truncate">{evt.title}</span>
                          <span className="font-mono text-slate-500 shrink-0 text-[11px]">{evt.date}</span>
                        </div>
                      ))}
                    </div>
                  </div>

                  <div>
                    <div className="text-[11px] font-bold uppercase text-slate-500 mb-2 flex items-center gap-1.5">
                      <FileText className="w-3.5 h-3.5" />
                      <span>Recent Filings</span>
                    </div>
                    <div className="space-y-1.5">
                      {stock.catalystResearch.recentFilings.map((filing, idx) => (
                        <div key={idx} className="p-2 rounded bg-slate-50 dark:bg-slate-800/40 border border-slate-200 dark:border-slate-800 text-xs flex justify-between gap-2">
                          <span className="text-slate-700 dark:text-slate-300 truncate">{filing.title}</span>
                          <span className="font-mono text-slate-400 shrink-0 text-[11px]">{filing.date}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}
      </ApiStateWrapper>
      <FinancialIntelligencePanel response={sharedBrainRes} loading={sharedBrainLoading} />
      <ForwardPerformanceIntelligencePanel response={sharedBrainRes} loading={sharedBrainLoading} />
    </div>
  );
};
