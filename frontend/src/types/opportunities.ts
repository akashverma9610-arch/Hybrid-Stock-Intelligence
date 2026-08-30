export interface OpportunityItem {
  symbol: string;
  sector: string | null;
  score: number | null;
  confidence: number | null;
  riskReward: string | null;
  executionStatus: string;
  candidateStatus: string;
  catalystSummary: string | null;
  freshness: string;
  warnings: string[];
}

export interface OpportunitySetData {
  asOf: string;
  universeCount: number;
  eligibleCount: number;
  analyzedCount: number;
  completeCount: number;
  partialCount: number;
  unavailableCount: number;
  qualifiedCandidateCount: number;
  warnings: string[];
  freshness: string;
  opportunities: OpportunityItem[];
}
