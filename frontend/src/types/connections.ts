export type ProviderId = 'kotak_neo' | 'upstox' | 'global_datafeeds' | 'gnews';

export type ProviderStatusType =
  | 'CONNECTED'
  | 'CONFIGURED'
  | 'NOT_CONFIGURED'
  | 'NOT_VALIDATED'
  | 'VALIDATED'
  | 'VALIDATION_FAILED'
  | 'DISCONNECTED'
  | 'DEGRADED'
  | 'UNAVAILABLE'
  | 'PENDING_SETUP';

export interface UpstoxValidationFlow {
  credentials: 'NOT_REQUIRED' | 'NOT_TESTED' | 'TESTING' | 'VALIDATED' | 'FAILED' | 'UNAVAILABLE';
  instrumentResolution: 'NOT_TESTED' | 'TESTING' | 'VALIDATED' | 'FAILED' | 'UNAVAILABLE';
  historicalAccess: 'NOT_TESTED' | 'TESTING' | 'VALIDATED' | 'FAILED' | 'UNAVAILABLE';
  normalization: 'NOT_TESTED' | 'TESTING' | 'VALIDATED' | 'FAILED' | 'UNAVAILABLE';
  persistence: 'NOT_TESTED' | 'TESTING' | 'VALIDATED' | 'FAILED' | 'UNAVAILABLE';
  lastTestedTimestamp?: string | null;
  errorMessage?: string | null;
}

export interface ConnectionProviderStatus {
  id: ProviderId;
  name: string;
  category: 'BROKER_API' | 'DATA_FEED' | 'NEWS_PROVIDER' | 'HISTORICAL_PROVIDER';
  roleBadge: string;
  roleDescription: string;
  isOptional?: boolean;
  configured: boolean;
  validated: boolean;
  status: ProviderStatusType;
  capabilities: string[];
  lastValidatedTimestamp: string | null;
  warnings: string[];
  latencyMs: number | null;
  hasSavedToken?: boolean;
}

export interface DataCoverageData {
  universeCount: number | null;
  universeLabel: string | null;
  currentQuotes: string | null;
  historicalOhlcv: string | null;
  taxonomy: string | null;
  fundamentals: string | null;
  ownership: string | null;
  delivery: string | null;
  lastUpdated?: string | null;
}

export type ReadinessStatus = 'READY' | 'DEGRADED' | 'IN_PROGRESS' | 'UNAVAILABLE' | 'NOT_STARTED';

export interface BrainReadinessItem {
  key: 'historical' | 'taxonomy' | 'market_context' | 'fundamentals' | 'ownership' | 'delivery' | 'news_catalysts';
  name: string;
  status: ReadinessStatus;
  detail?: string | null;
  lastSync?: string | null;
}

export interface BrainDataReadinessData {
  overallStatus: ReadinessStatus;
  disclaimer: string;
  items: BrainReadinessItem[];
  lastAssessed?: string | null;
}

export interface RealBrainTrialData {
  isAvailable: boolean;
  frozenCohort: string | null;
  historicalReady: string | null;
  technicalReady: string | null;
  preBreakoutReady: string | null;
  inflectionReady: string | null;
  unavailabilityMessage?: string | null;
}

export interface ConnectionsState {
  providers: ConnectionProviderStatus[];
  activeEnvironment: 'DEVELOPMENT' | 'STAGING' | 'PRODUCTION';
  upstoxValidation?: UpstoxValidationFlow;
  dataCoverage?: DataCoverageData | null;
  brainReadiness?: BrainDataReadinessData | null;
  realBrainTrial?: RealBrainTrialData | null;
}
