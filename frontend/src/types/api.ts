export type ApiStatus = 'READY' | 'PARTIAL' | 'DEGRADED' | 'UNAVAILABLE' | 'ERROR' | 'LOADING' | 'EMPTY';

export type FreshnessState = 'LIVE' | 'DELAYED' | 'EOD' | 'STALE' | 'UNKNOWN';

export interface ApiResponse<T> {
  status: ApiStatus;
  freshness: FreshnessState;
  timestamp: string | null;
  data: T | null;
  message?: string;
  warnings?: string[];
}

export type MarketRegime = 
  | 'TRENDING_BULL'
  | 'TRENDING_BEAR'
  | 'VOLATILE_EXPANSION'
  | 'COMPRESSION_CONSOLIDATION'
  | 'MEAN_REVERTING'
  | 'DISTRIBUTION'
  | 'ACCUMULATION'
  | 'TRANSITIONAL'
  | 'UNKNOWN';

export type DownsideCrisisState = 'NORMAL' | 'STRESS' | 'CRISIS' | 'RECOVERY';

export type UpsideEuphoriaState = 'NORMAL' | 'CROWDING' | 'SPECULATION' | 'EUPHORIA' | 'DISTRIBUTION';

export type ConfidenceLevel = 'HIGH' | 'MEDIUM' | 'LOW' | 'INSUFFICIENT_DATA';

export type SignalAction = 'BUY' | 'ACCUMULATE' | 'HOLD' | 'TRIM' | 'EXIT' | 'AVOID' | 'WATCH';

export type SectorPhase = 'LEADING' | 'IMPROVING' | 'WEAKENING' | 'LAGGING';

export type RiskLevel = 'LOW' | 'MODERATE' | 'ELEVATED' | 'HIGH' | 'EXTREME' | 'UNAVAILABLE';
