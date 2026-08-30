import { FreshnessState } from './api';

export type HealthStatus = 'HEALTHY' | 'DEGRADED' | 'UNAVAILABLE' | 'DISCONNECTED';

export interface SourceHealth {
  name: string;
  category: 'QUOTES' | 'HISTORICAL' | 'FUNDAMENTALS' | 'NEWS' | 'PRIMARY_MARKET' | 'BROKER';
  status: HealthStatus;
  latencyMs: number | null;
  lastSuccessTimestamp: string | null;
  freshness: FreshnessState;
  warningNote?: string;
}

export interface SystemHealthData {
  runtimeStatus: 'OPERATIONAL' | 'DEGRADED' | 'MAINTENANCE' | 'CRITICAL';
  uptimeSeconds: number | null;
  schedulerStatus: 'ACTIVE' | 'PAUSED' | 'IDLE' | 'ERROR';
  lastCycleRunTime: string | null;
  nextScheduledCycle: string | null;
  sources: SourceHealth[];
  systemWarnings: string[];
  environment: string;
}
