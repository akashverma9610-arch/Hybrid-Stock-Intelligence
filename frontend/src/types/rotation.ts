export interface CapitalRotationOpportunity {
  currentHoldingSymbol: string | null;
  currentHoldingScore: string | null;
  candidateSymbol: string;
  candidateScore: string | null;
  scoreAdvantage: string | null;
  candidateConfidence: number | null;
  holdingConfidence: number | null;
  candidateRiskReward: string | null;
  sectorContext: string | null;
  catalystContext: string | null;
  freshness: string;
  executionEligibility: string;
  publicGateSummary: string[];
  recommendedAction: string;
  rationale: string;
  invalidationSummary: string | null;
  warnings: string[];
}

/** Read-only projection of the published capital-rotation evaluation. */
export interface CapitalRotationData {
  overallStatus: string;
  dataAsOf: string | null;
  freshness: string;
  marketRegime: string | null;
  opportunityCoverage: string;
  rotationComparisonStatus: string;
  holdingCount: number | null;
  portfolioHeat: string | null;
  weakestHoldingSymbol: string | null;
  opportunities: CapitalRotationOpportunity[];
  warnings: string[];
  message: string | null;
}
