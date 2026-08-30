import { ConfidenceLevel, RiskLevel, SignalAction } from './api';

export interface StockDetailData {
  symbol: string;
  companyName: string;
  isin: string | null;
  sector: string;
  industry: string | null;
  marketCapCategory: 'LARGE_CAP' | 'MID_CAP' | 'SMALL_CAP' | 'MICRO_CAP' | null;
  marketCapCr: number | null;
  currentPrice: number | null;
  dayHigh: number | null;
  dayLow: number | null;
  dayChangePct: number | null;
  volume: number | null;
  avgVolume20D: number | null;

  // Backend distilled scores (no proprietary diagnostic IDs or weights)
  decisionScore: number | null;
  confidence: ConfidenceLevel;
  action: SignalAction;
  distilledRationale: string;

  // Market Context
  marketContext: {
    sectorRank: number | null;
    sectorName: string | null;
    relativeStrengthIndexRank: number | null;
    sectorPhase: string | null;
  };

  // Technical Summary
  technicalSummary: {
    trendClassification: string | null;
    dma50: number | null;
    dma200: number | null;
    supportLevel: number | null;
    resistanceLevel: number | null;
    volatilityAtr: number | null;
  };

  // Fundamentals Summary
  fundamentalsSummary: {
    peRatio: number | null;
    sectorPe: number | null;
    pbRatio: number | null;
    roePct: number | null;
    rocePct: number | null;
    debtToEquity: number | null;
    quarterlyRevenueGrowthYoY: number | null;
    quarterlyProfitGrowthYoY: number | null;
  };

  // Catalyst & Research
  catalystResearch: {
    upcomingEvents: Array<{
      date: string;
      title: string;
      category: string;
    }>;
    recentFilings: Array<{
      date: string;
      title: string;
      type: string;
    }>;
  };

  // Risk & Execution
  riskExecution: {
    riskRating: RiskLevel;
    liquidityScore: number | null;
    slippageEstPct: number | null;
    suggestedStopLoss: number | null;
    suggestedTarget1: number | null;
    suggestedTarget2: number | null;
  };
}

export interface StockListItem {
  symbol: string;
  companyName: string;
  sector: string;
  marketCapCr: number | null;
  price: number | null;
  changePct: number | null;
  decisionScore: number | null;
  confidence: ConfidenceLevel;
  action: SignalAction;
  riskRating: RiskLevel;
}

/** Read-only presentation of the governed U15 Shared Brain response. */
export interface SharedBrainFinancialSemantic {
  metric: string;
  trajectoryBasis: string;
  previousPeriodLabel: string | null;
  currentPeriodLabel: string | null;
  previousValue: string | null;
  currentValue: string | null;
  absoluteDelta: string | null;
  relativeDelta: string | null;
  signTransition: string | null;
  factualDisplayPhrase: string | null;
  directionalityOrientation: string | null;
  directionalityRationaleCode: string | null;
  materialityGovernanceState: string;
  trajectoryFingerprint: string;
  directionalityFingerprint: string | null;
}

export interface SharedBrainAnalysisData {
  canonicalInstrumentId: string;
  symbol: string;
  name: string | null;
  exchange: string;
  asOf: string;
  requestedContext: string;
  evidenceStatus: string;
  evidenceDomains: Array<{ domain: string; availability: string }>;
  financialSemantics: SharedBrainFinancialSemantic[];
  blockers: string[];
  warnings: string[];
  snapshotFingerprint: string;
  unifiedStateFingerprint: string;
  brainResearchStateV2Fingerprint: string;
  contextProjectionFingerprint: string;
  financialSemanticSectionFingerprint: string;
  materialityPolicyId: string;
  materialityPolicyVersion: string;
  materialityPolicyFingerprint: string;
  materialityCalibrationStatus: string;
}
