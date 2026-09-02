export interface RuntimeStatusData {
  schedulerEnabled: boolean;
  schedulerRunning: boolean;
  runtimeMode: string;
  universeId: string | null;
  lastCycleId: string | null;
  lastCycleStatus: string | null;
  lastStartedAt: string | null;
  lastCompletedAt: string | null;
  lastSuccessAt: string | null;
  lastFailureAt: string | null;
  lastDataAsOf: string | null;
  consecutiveFailures: number;
  warnings: string[];
}

export interface LocalRuntimeReadinessData {
  databaseBackend: string;
  storageMode: string;
  databasePath: string | null;
  sqliteIntegrity: string | null;
  foreignKeyViolations: number | null;
  financialFacts: number | null;
  corporateFilings: number | null;
  portfolioSnapshots: number | null;
  bseReceipts: number | null;
  bsePlanId: string | null;
  bseStatus: string;
  marketWideWatchStatus: string;
  warnings: string[];
}

export interface DataOperationRunData {
  runId: string;
  family: string;
  mode: string;
  status: string;
  completedAt: string;
  acceptedCount: number;
  duplicateCount: number;
  conflictCount: number;
  rejectedCount: number;
  gapCount: number;
  warnings: string[];
}

export interface DataOperationFamilyHealthData {
  family: string;
  status: string;
  lastRun: DataOperationRunData | null;
  nextDueAt: string | null;
  reasons: string[];
}

export interface DataOperationsHealthData {
  generatedAt: string;
  families: DataOperationFamilyHealthData[];
}

export interface PortfolioRuntimeHolding {
  instrumentId: string;
  symbol: string | null;
  quantity: string;
  averagePrice: string;
  marketPrice: string | null;
  currentValue: string | null;
  unrealizedPnl: string | null;
  sector: string | null;
  dataAsOf: string;
  warnings: string[];
}

export interface OpportunitySnapshotData {
  asOf: string;
  universeCount: number;
  eligibleCount: number;
  analyzedCount: number;
  completeCount: number;
  partialCount: number;
  unavailableCount: number;
  qualifiedCandidateCount: number;
  freshness: string;
  coverageStatus: string;
  warnings: string[];
  opportunities: Array<{
    symbol: string;
    sector: string | null;
    executionStatus: string;
    candidateStatus: string;
    warnings: string[];
  }>;
}

export interface DecisionTrustDomain {
  domain: string;
  availability: string;
  freshness: string;
  evidenceAsOf: string | null;
  observedAt: string | null;
  artifactIds: string[];
  artifactFingerprints: string[];
  blockers: string[];
}

export interface DecisionTrustEnvelopeData {
  version: string;
  canonicalInstrumentId: string;
  symbol: string;
  intelligenceAsOf: string;
  latestCompletedMarketSession: string | null;
  sharedBrainState: string;
  domains: DecisionTrustDomain[];
  coverageCount: number;
  coverageTotal: number;
  coveragePct: string;
  missingDomains: string[];
  blockers: string[];
  decisionReadiness: string;
  decisionScore: {
    state: string;
    value: string | null;
    artifactId: string | null;
    policyVersion: string | null;
    policyFingerprint: string | null;
    scoreAsOf: string | null;
    blockers: string[];
  };
  setup: {
    state: string;
    setupId: string | null;
    setupAsOf: string | null;
    setupType: string | null;
    entry: string | null;
    structuralInvalidation: string | null;
    target1: string | null;
    target2: string | null;
    extendedTarget: string | null;
    riskReward: string | null;
    maximumExecutableEntry: string | null;
    blockers: string[];
  };
  sixGates: {
    state: string;
    evaluationId: string | null;
    policyId: string | null;
    policyVersion: string | null;
    policyFingerprint: string | null;
    evaluationAsOf: string | null;
    aggregateState: string | null;
    gateResults: Array<[string, string]>;
    blockers: string[];
  };
  thesis: {
    tradingThesis: string | null;
    investmentThesis: string | null;
    invalidationStatus: string | null;
    structuralInvalidation: string | null;
    sourceAsOf: string | null;
    blockers: string[];
  };
  liveMarket: {
    ltp: string | null;
    receivedAt: string | null;
    freshness: string | null;
  };
  fingerprint: string;
}

export interface MarketWideWatchRecordData {
  watchId: string;
  canonicalInstrumentId: string;
  symbol: string;
  companyName: string | null;
  watchAsOf: string;
  classifications: string[];
  status: string;
  evidenceSufficiency: string;
  evidenceReferences: Array<{ ruleId: string; diagnosticResult: string; artifactId: string; artifactFingerprint: string }>;
  sector: string | null;
  sectorRank: number | null;
  top3Eligible: boolean;
  decisionScoreId: string | null;
  decisionScoreStatus: string;
  decisionScoreValue: string | null;
  setupState: string;
  sixGatesState: string;
  reliabilityState: string;
  blockerCodes: string[];
  lastEvidenceAsOf: string | null;
  policyIdentity: string;
  fingerprint: string;
  archetypes: string[];
  externalEvidenceReferences: Array<{ canonicalEventId: string; evidenceVersionId: string; eventType: string; materiality: string; policyStage: string | null; primarySourceType: string; exposureType: string; exposureVerificationStatus: string; evidenceFingerprint: string }>;
  policyMaturity: string | null;
  historicalQualityState: string;
  currentInflectionState: string;
  setupPolicyRoutes: Array<[string, string]>;
  lifecycleFlags: string[];
  evidenceDomainCoverage: string[];
  rotationChallengerState: string;
  comparisonReadiness: string;
}

export interface MarketWideWatchData {
  runId: string;
  watchAsOf: string;
  universeId: string;
  universeCount: number;
  eligibleCount: number;
  excludedCount: number;
  exclusionCounts: Array<[string, number]>;
  evidenceReadyCount: number;
  watchCandidateCount: number;
  classificationCounts: Array<[string, number]>;
  top3EligibleCount: number;
  setupCandidateCount: number;
  validSetupCount: number;
  decisionScoreReadyCount: number;
  sixGatesEvaluatedCount: number;
  sixGatesPassCount: number;
  filterAttribution: Array<[string, number]>;
  unsupportedClassifications: string[];
  records: MarketWideWatchRecordData[];
  portfolioRecords: MarketWideWatchRecordData[];
  policyIdentity: string;
  fingerprint: string;
  archetypeCounts: Array<[string, number]>;
  rotationFunnel: Array<[string, number]>;
  rotationChallengerCount: number;
  actualRotationCandidateCount: number;
  evidenceReadinessCounts: Array<[string, number]>;
  evidenceDomainCounts: Array<[string, number]>;
  evidenceBlockerAttribution: Array<[string, number]>;
}
