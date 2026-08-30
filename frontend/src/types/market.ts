import { DownsideCrisisState, FreshnessState, MarketRegime, UpsideEuphoriaState } from './api';

export interface MarketStateData {
  regime: MarketRegime;
  regimeLabel: string;
  regimeConfidencePct: number | null; // e.g. 78%
  sessionStatus: 'PRE_OPEN' | 'OPEN' | 'POST_CLOSE' | 'CLOSED' | 'HOLIDAY';
  sessionTimeRemaining: string | null;
  nifty50: {
    spot: number | null;
    change: number | null;
    pChange: number | null;
  };
  bankNifty: {
    spot: number | null;
    change: number | null;
    pChange: number | null;
  };
  vix: {
    current: number | null;
    change: number | null;
    trend: 'RISING' | 'FALLING' | 'FLAT' | null;
  };
  freshness: FreshnessState;
  lastUpdated: string | null;
}

export interface MarketExtremesData {
  downsideState: DownsideCrisisState;
  downsideScore: number | null; // 0-100 or scale
  downsideDescription: string;
  upsideState: UpsideEuphoriaState;
  upsideScore: number | null;
  upsideDescription: string;
  evidenceQuality: 'HIGH' | 'MEDIUM' | 'DEGRADED' | 'LOW';
  activeWarnings: string[];
  lastAssessed: string | null;
}

export interface MarketBreadthData {
  advances: number | null;
  declines: number | null;
  unchanged: number | null;
  advanceDeclineRatio: number | null;
  above50DmaPct: number | null;
  above200DmaPct: number | null;
  participationScore: number | null; // 0-100
  breadthCoverageCount: number | null; // total stocks tracked e.g. 500
  leadershipConcentration: {
    top5WeightPct: number | null;
    isConcentrated: boolean | null;
    dominantSectors: string[];
  };
}

export interface SectorItem {
  id: string;
  name: string;
  indexSymbol: string;
  phase: 'LEADING' | 'IMPROVING' | 'WEAKENING' | 'LAGGING';
  relativeStrengthRank: number | null;
  oneDayChangePct: number | null;
  oneWeekChangePct: number | null;
  oneMonthChangePct: number | null;
  breadthParticipationPct: number | null;
  topContributingStock: string | null;
  dragStock: string | null;
}

export interface SectorLeadershipData {
  leadingSectors: SectorItem[];
  improvingSectors: SectorItem[];
  weakeningSectors: SectorItem[];
  laggingSectors: SectorItem[];
  summaryNote: string;
}
