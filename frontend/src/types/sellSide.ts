export interface SellSideDecision {
  holdingId: string;
  action: string;
  thesisState: string;
  capitalEfficiencyState: string | null;
  rotationState: string | null;
  reasons: string[];
  blockers: string[];
  evidenceFreshness: string;
  policyFingerprint: string;
}

export interface SellSideData {
  status: string;
  portfolioSnapshotId: string | null;
  policyFingerprint: string;
  decisions: SellSideDecision[];
  warnings: string[];
}

