export interface PerformanceData {
  timeframe: string;
  totalReturnPct: number | null;
  benchmarkReturnPct: number | null; // Nifty 50
  alphaPct: number | null;
  maxDrawdownPct: number | null;
  expectancyR: number | null; // e.g. 0.85R
  winRatePct: number | null;
  lossRatePct: number | null;
  profitFactor: number | null; // e.g. 2.14
  sharpeRatio: number | null;
  sortinoRatio: number | null;
  calmarRatio: number | null;
  portfolioTurnoverPct: number | null;
  capitalEfficiencyScore: number | null;
  avgWinningTradePct: number | null;
  avgLosingTradePct: number | null;
  monthlyBreakdown: Array<{
    month: string;
    returnPct: number | null;
    benchmarkPct: number | null;
  }>;
}
