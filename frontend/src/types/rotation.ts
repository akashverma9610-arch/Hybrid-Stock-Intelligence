import { ConfidenceLevel, SignalAction } from './api';

export interface RotationExecutionGate {
  gateNumber: number;
  name: string;
  passed: boolean | null;
  statusText: string;
  detail: string | null;
}

export interface CapitalRotationItem {
  id: string;
  currentHolding: {
    symbol: string;
    score: number | null;
    sector: string;
    currentValue: number | null;
    gainPct: number | null;
  };
  candidate: {
    symbol: string;
    score: number | null;
    sector: string;
    expectedCatalyst: string | null;
  };
  scoreAdvantage: number | null; // delta e.g. +18.4
  riskReward: number | null;
  confidence: ConfidenceLevel;
  sectorContext: string;
  gateStatus: 'ALL_PASSED' | 'BLOCKED' | 'PENDING' | 'DEGRADED';
  gates: RotationExecutionGate[];
  action: 'RECOMMENDED' | 'EVALUATING' | 'RESTRICTED' | 'DISMISSED';
  rationale: string;
}

export interface CapitalRotationData {
  isAvailableOnBackend: boolean;
  unavailableReason?: string;
  rotationThresholdPct: number | null;
  candidatePairs: CapitalRotationItem[];
  lastCalculated: string | null;
}
