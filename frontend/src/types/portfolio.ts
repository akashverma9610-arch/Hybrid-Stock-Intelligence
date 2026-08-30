import { ConfidenceLevel, RiskLevel, SignalAction } from './api';

export interface HoldingItem {
  symbol: string;
  companyName: string;
  sector: string;
  quantity: number | null;
  avgPrice: number | null;
  currentPrice: number | null;
  investedValue: number | null;
  currentValue: number | null;
  unrealizedPnL: number | null;
  unrealizedPnLPct: number | null;
  weightPct: number | null;
  decisionScore: number | null;
  confidence: ConfidenceLevel;
  healthState: 'HEALTHY' | 'NEUTRAL' | 'AT_RISK' | 'CRITICAL' | 'UNAVAILABLE';
  riskContribution: RiskLevel;
}

export interface ReviewedPortfolioHolding {
  symbol: string;
  quantity: number | null;
  avgPrice: number | null;
  currentPrice?: number | null;
  companyName?: string | null;
  sector?: string | null;
}

export interface PortfolioImportDraft {
  draftId?: string | null;
  sourceImageName?: string | null;
  extractedHoldings: ReviewedPortfolioHolding[];
  confidenceScore?: number | null;
  unresolvedRows?: Array<{
    rawText: string;
    reason?: string | null;
  }>;
  parsedAt?: string | null;
}

export interface PortfolioSummaryData {
  investedValue: number | null;
  currentValue: number | null;
  totalPnL: number | null;
  totalPnLPct: number | null;
  todayPnL: number | null;
  todayPnLPct: number | null;
  cashAvailable: number | null;
  capitalDeployedPct: number | null;
  portfolioHeatScore: number | null; // 0-100 portfolio risk heat
  portfolioRiskLevel: RiskLevel;
  weakestHolding: {
    symbol: string;
    currentLossPct: number | null;
    score: number | null;
    reason: string;
  } | null;
  strongestHolding: {
    symbol: string;
    currentGainPct: number | null;
    score: number | null;
  } | null;
  holdingsCount: number | null;
  holdings: HoldingItem[];
}
