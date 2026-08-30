import { ConfidenceLevel, RiskLevel, SignalAction } from './api';

export interface SignalItem {
  id: string;
  symbol: string;
  companyName: string;
  sector: string;
  action: SignalAction;
  score: number | null; // e.g. 84.5
  confidence: ConfidenceLevel;
  signalState: 'ACTIVE' | 'PENDING_VALIDATION' | 'TRIGGERED' | 'EXPIRED' | 'INVALIDATED';
  currentPrice: number | null;
  entryPrice: number | null;
  stopLoss: number | null;
  target1: number | null;
  target2: number | null;
  riskRewardRatio: number | null; // e.g. 2.8
  timeframe: string | null;
  timestamp: string | null;
  shortRationale: string;
  keyCatalyst: string | null;
  riskRating: RiskLevel;
}

export interface SignalsData {
  count: number | null;
  activeSignals: SignalItem[];
  recentTriggers: SignalItem[];
  lastAssessedTime: string | null;
}
