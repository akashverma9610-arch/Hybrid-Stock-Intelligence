import { ApiResponse, ApiStatus, FreshnessState } from '../types/api';
import { MarketBreadthData, MarketExtremesData, MarketStateData, SectorItem, SectorLeadershipData } from '../types/market';
import { PortfolioSummaryData, HoldingItem } from '../types/portfolio';
import { SignalsData, SignalItem } from '../types/signals';
import { CapitalRotationData } from '../types/rotation';
import { SellSideData } from '../types/sellSide';
import { SharedBrainAnalysisData, StockDetailData, StockListItem } from '../types/stock';
import { PaperTradingData } from '../types/paperTrading';
import { PerformanceData } from '../types/performance';
import { PrimaryMarketData } from '../types/primaryMarket';
import { NewsData } from '../types/news';
import { SystemHealthData, SourceHealth } from '../types/systemHealth';
import {
  ConnectionsState,
  ConnectionProviderStatus,
  DataCoverageData,
  BrainDataReadinessData,
  RealBrainTrialData,
  UpstoxValidationFlow,
} from '../types/connections';
import { DataClientInterface } from './clientInterface';

const DEFAULT_TIMEOUT_MS = 6000;

// Published FastAPI contract.  Connection credentials never use route
// guessing: a 404/transport failure is displayed as unavailable instead.
const CONNECTION_ROUTES = {
  upstox: {
    profile: '/api/v1/connections/upstox',
    credentials: '/api/v1/connections/upstox/credentials',
    test: '/api/v1/connections/upstox/test',
  },
} as const;

type UpstoxStage = UpstoxValidationFlow['credentials'];
type UpstoxPipelineStage = Exclude<UpstoxStage, 'NOT_REQUIRED'>;

const upstoxStage = (value: unknown): UpstoxStage => (
  ['NOT_REQUIRED', 'NOT_TESTED', 'TESTING', 'VALIDATED', 'FAILED', 'UNAVAILABLE'].includes(String(value))
    ? value as UpstoxStage
    : 'NOT_TESTED'
);

const upstoxPipelineStage = (value: unknown): UpstoxPipelineStage => {
  const stage = upstoxStage(value);
  return stage === 'NOT_REQUIRED' ? 'NOT_TESTED' : stage;
};

const normalizeUpstoxValidationFlow = (value: any, errorCode?: string | null): UpstoxValidationFlow | undefined => {
  if (!value || typeof value !== 'object') return undefined;
  const message = value.errorMessage ?? value.error_message ?? null;
  return {
    credentials: upstoxStage(value.credentials),
    instrumentResolution: upstoxPipelineStage(value.instrumentResolution ?? value.instrument_resolution),
    historicalAccess: upstoxPipelineStage(value.historicalAccess ?? value.historical_access),
    normalization: upstoxPipelineStage(value.normalization),
    persistence: upstoxPipelineStage(value.persistence),
    lastTestedTimestamp: value.lastTestedTimestamp ?? value.last_tested_timestamp ?? null,
    errorMessage: errorCode ? `${errorCode}${message ? `: ${message}` : ''}` : message,
  };
};

export class HttpDataClient implements DataClientInterface {
  private baseUrl: string;

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl.replace(/\/+$/, '');
  }

  private async fetchWithTimeout<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<ApiResponse<T>> {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), DEFAULT_TIMEOUT_MS);

    const url = `${this.baseUrl}${endpoint.startsWith('/') ? endpoint : `/${endpoint}`}`;

    try {
      const res = await fetch(url, {
        ...options,
        signal: controller.signal,
        headers: {
          'Content-Type': 'application/json',
          Accept: 'application/json',
          ...options.headers,
        },
      });

      clearTimeout(timeoutId);

      if (!res.ok) {
        let safeErrorMessage: string | null = null;
        try {
          const payload = await res.json();
          const error = payload?.error;
          if (typeof error?.code === 'string' && typeof error?.message === 'string') {
            safeErrorMessage = `${error.code}: ${error.message}`;
          }
        } catch {
          // Non-JSON failures retain the generic public-safe HTTP message.
        }
        if (res.status === 404) {
          return {
            status: 'UNAVAILABLE',
            freshness: 'UNKNOWN',
            timestamp: new Date().toISOString(),
            data: null,
            message: safeErrorMessage || `Endpoint ${endpoint} not exposed by backend (404 Not Found)`,
          };
        }
        if (res.status === 503 || res.status === 502) {
          return {
            status: 'DEGRADED',
            freshness: 'STALE',
            timestamp: new Date().toISOString(),
            data: null,
            message: safeErrorMessage || `Backend service temporarily unavailable (${res.status})`,
          };
        }
        return {
          status: 'ERROR',
          freshness: 'UNKNOWN',
          timestamp: new Date().toISOString(),
          data: null,
          message: safeErrorMessage || `Backend returned error ${res.status}: ${res.statusText}`,
        };
      }

      const json = await res.json();

      // Normalize if backend wrapped in custom envelope
      if (json && typeof json === 'object' && ('status' in json || 'data' in json)) {
        return {
          status: (json.status as ApiStatus) || 'READY',
          freshness: (json.freshness as FreshnessState) || 'LIVE',
          timestamp: json.timestamp || new Date().toISOString(),
          data: json.data !== undefined ? json.data : json,
          message: json.message,
          warnings: json.warnings,
        };
      }

      return {
        status: 'READY',
        freshness: 'LIVE',
        timestamp: new Date().toISOString(),
        data: json as T,
      };
    } catch (err: any) {
      clearTimeout(timeoutId);
      const isTimeout = err.name === 'AbortError';
      return {
        status: 'UNAVAILABLE',
        freshness: 'UNKNOWN',
        timestamp: new Date().toISOString(),
        data: null,
        message: isTimeout
          ? `Request to backend timed out after ${DEFAULT_TIMEOUT_MS / 1000}s.`
          : `Unable to connect to backend at ${this.baseUrl}. Please check server connectivity.`,
      };
    }
  }

  /**
   * Tries candidate endpoints in priority order until one succeeds or all fail.
   */
  private async fetchWithFallback<T>(
    candidateEndpoints: string[],
    options: RequestInit = {}
  ): Promise<ApiResponse<T>> {
    let lastResponse: ApiResponse<T> | null = null;

    for (const ep of candidateEndpoints) {
      const res = await this.fetchWithTimeout<T>(ep, options);
      if (res.status === 'READY' || res.status === 'PARTIAL' || res.status === 'DEGRADED') {
        return res;
      }
      lastResponse = res;
      // If error is network failure (cannot connect at all), break early to avoid waiting through all timeouts
      if (res.status === 'UNAVAILABLE' && res.message?.includes('Unable to connect to backend')) {
        return res;
      }
    }

    return (
      lastResponse || {
        status: 'UNAVAILABLE',
        freshness: 'UNKNOWN',
        timestamp: new Date().toISOString(),
        data: null,
        message: `None of the candidate endpoints (${candidateEndpoints.join(', ')}) were accessible on the backend.`,
      }
    );
  }

  // ==========================================
  // 1. DASHBOARD APIS
  // ==========================================

  async getMarketState(): Promise<ApiResponse<MarketStateData>> {
    const raw = await this.fetchWithFallback<any>([
      '/api/v1/market/state',
      '/api/v1/market/regime',
      '/api/v1/market-state',
      '/api/v2/market/state',
    ]);

    if (!raw.data) {
      return {
        status: raw.status,
        freshness: raw.freshness,
        timestamp: raw.timestamp,
        data: null,
        message: raw.message,
        warnings: raw.warnings,
      };
    }

    const d = raw.data;
    const normalized: MarketStateData = {
      regime: d.regime || 'UNKNOWN',
      regimeLabel: d.regimeLabel || d.regime_label || d.label || d.regime || 'Unspecified Regime',
      regimeConfidencePct: d.regimeConfidencePct ?? d.regime_confidence_pct ?? d.confidence ?? null,
      sessionStatus: d.sessionStatus || d.session_status || d.status || 'CLOSED',
      sessionTimeRemaining: d.sessionTimeRemaining || d.session_time_remaining || d.time_remaining || null,
      nifty50: {
        spot: d.nifty50?.spot ?? d.nifty_50?.spot ?? d.nifty?.spot ?? null,
        change: d.nifty50?.change ?? d.nifty_50?.change ?? d.nifty?.change ?? null,
        pChange: d.nifty50?.pChange ?? d.nifty_50?.p_change ?? d.nifty50?.p_change ?? d.nifty?.p_change ?? null,
      },
      bankNifty: {
        spot: d.bankNifty?.spot ?? d.bank_nifty?.spot ?? null,
        change: d.bankNifty?.change ?? d.bank_nifty?.change ?? null,
        pChange: d.bankNifty?.pChange ?? d.bank_nifty?.p_change ?? null,
      },
      vix: {
        current: d.vix?.current ?? d.india_vix?.current ?? d.vix?.spot ?? null,
        change: d.vix?.change ?? d.india_vix?.change ?? null,
        trend: d.vix?.trend ?? d.india_vix?.trend ?? 'FLAT',
      },
      freshness: raw.freshness,
      lastUpdated: d.lastUpdated || d.last_updated || d.timestamp || raw.timestamp,
    };

    return {
      status: raw.status,
      freshness: raw.freshness,
      timestamp: raw.timestamp,
      data: normalized,
      message: raw.message,
      warnings: raw.warnings,
    };
  }

  async getMarketExtremes(): Promise<ApiResponse<MarketExtremesData>> {
    const raw = await this.fetchWithFallback<any>([
      '/api/v1/market/extremes',
      '/api/v1/market-extremes',
      '/api/v2/market/extremes',
    ]);

    if (!raw.data) {
      return {
        status: raw.status,
        freshness: raw.freshness,
        timestamp: raw.timestamp,
        data: null,
        message: raw.message,
        warnings: raw.warnings,
      };
    }

    const d = raw.data;
    const normalized: MarketExtremesData = {
      downsideState: d.downsideState || d.downside_state || 'NORMAL',
      downsideScore: d.downsideScore ?? d.downside_score ?? null,
      downsideDescription: d.downsideDescription || d.downside_description || 'No downside commentary provided by backend.',
      upsideState: d.upsideState || d.upside_state || 'NORMAL',
      upsideScore: d.upsideScore ?? d.upside_score ?? null,
      upsideDescription: d.upsideDescription || d.upside_description || 'No upside excess commentary provided by backend.',
      evidenceQuality: d.evidenceQuality || d.evidence_quality || 'MEDIUM',
      activeWarnings: d.activeWarnings || d.active_warnings || d.warnings || [],
      lastAssessed: d.lastAssessed || d.last_assessed || d.timestamp || raw.timestamp,
    };

    return {
      status: raw.status,
      freshness: raw.freshness,
      timestamp: raw.timestamp,
      data: normalized,
      message: raw.message,
      warnings: raw.warnings,
    };
  }

  async getMarketBreadth(): Promise<ApiResponse<MarketBreadthData>> {
    const raw = await this.fetchWithFallback<any>([
      '/api/v1/market/breadth',
      '/api/v1/market-breadth',
      '/api/v2/market/breadth',
    ]);

    if (!raw.data) {
      return {
        status: raw.status,
        freshness: raw.freshness,
        timestamp: raw.timestamp,
        data: null,
        message: raw.message,
        warnings: raw.warnings,
      };
    }

    const d = raw.data;
    const normalized: MarketBreadthData = {
      advances: d.advances ?? null,
      declines: d.declines ?? null,
      unchanged: d.unchanged ?? null,
      advanceDeclineRatio: d.advanceDeclineRatio ?? d.advance_decline_ratio ?? (d.declines && d.advances ? Number((d.advances / d.declines).toFixed(2)) : null),
      above50DmaPct: d.above50DmaPct ?? d.above_50_dma_pct ?? null,
      above200DmaPct: d.above200DmaPct ?? d.above_200_dma_pct ?? null,
      participationScore: d.participationScore ?? d.participation_score ?? null,
      breadthCoverageCount: d.breadthCoverageCount ?? d.breadth_coverage_count ?? d.coverage_count ?? 500,
      leadershipConcentration: {
        top5WeightPct: d.leadershipConcentration?.top5WeightPct ?? d.leadership_concentration?.top_5_weight_pct ?? null,
        isConcentrated: d.leadershipConcentration?.isConcentrated ?? d.leadership_concentration?.is_concentrated ?? null,
        dominantSectors: d.leadershipConcentration?.dominantSectors ?? d.leadership_concentration?.dominant_sectors ?? [],
      },
    };

    return {
      status: raw.status,
      freshness: raw.freshness,
      timestamp: raw.timestamp,
      data: normalized,
      message: raw.message,
      warnings: raw.warnings,
    };
  }

  async getSectorLeadership(): Promise<ApiResponse<SectorLeadershipData>> {
    const raw = await this.fetchWithFallback<any>([
      '/api/v1/sectors/leadership',
      '/api/v1/sectors',
      '/api/v1/sector-rotation',
      '/api/v2/sectors/leadership',
    ]);

    if (!raw.data) {
      return {
        status: raw.status,
        freshness: raw.freshness,
        timestamp: raw.timestamp,
        data: null,
        message: raw.message,
        warnings: raw.warnings,
      };
    }

    const d = raw.data;
    const mapSector = (s: any, fallbackPhase: 'LEADING' | 'IMPROVING' | 'WEAKENING' | 'LAGGING'): SectorItem => ({
      id: s.id || s.name || `sec-${Math.random()}`,
      name: s.name || s.sector || 'Sector',
      indexSymbol: s.indexSymbol || s.index_symbol || s.symbol || s.name || '',
      phase: s.phase || fallbackPhase,
      relativeStrengthRank: s.relativeStrengthRank ?? s.relative_strength_rank ?? s.rank ?? null,
      oneDayChangePct: s.oneDayChangePct ?? s.one_day_change_pct ?? s.return_1d ?? s.change ?? null,
      oneWeekChangePct: s.oneWeekChangePct ?? s.one_week_change_pct ?? s.return_1w ?? null,
      oneMonthChangePct: s.oneMonthChangePct ?? s.one_month_change_pct ?? s.return_1m ?? null,
      breadthParticipationPct: s.breadthParticipationPct ?? s.breadth_pct ?? null,
      topContributingStock: s.topContributingStock || s.top_contributing_stock || null,
      dragStock: s.dragStock || s.drag_stock || null,
    });

    const leadingSectors = (d.leadingSectors || d.leading_sectors || d.leaders || []).map((s: any) => mapSector(s, 'LEADING'));
    const improvingSectors = (d.improvingSectors || d.improving_sectors || []).map((s: any) => mapSector(s, 'IMPROVING'));
    const weakeningSectors = (d.weakeningSectors || d.weakening_sectors || []).map((s: any) => mapSector(s, 'WEAKENING'));
    const laggingSectors = (d.laggingSectors || d.lagging_sectors || d.laggards || []).map((s: any) => mapSector(s, 'LAGGING'));

    const normalized: SectorLeadershipData = {
      leadingSectors,
      improvingSectors,
      weakeningSectors,
      laggingSectors,
      summaryNote: d.summaryNote || d.summary_note || d.summary || '',
    };

    return {
      status: raw.status,
      freshness: raw.freshness,
      timestamp: raw.timestamp,
      data: normalized,
      message: raw.message,
      warnings: raw.warnings,
    };
  }

  async getPortfolioSummary(): Promise<ApiResponse<PortfolioSummaryData>> {
    const raw = await this.fetchWithFallback<any>([
      '/api/v1/portfolio/summary',
      '/api/v1/portfolio',
      '/api/v2/portfolio/summary',
    ]);

    if (!raw.data) {
      return {
        status: raw.status,
        freshness: raw.freshness,
        timestamp: raw.timestamp,
        data: null,
        message: raw.message,
        warnings: raw.warnings,
      };
    }

    const d = raw.data;
    const rawHoldings = Array.isArray(d.holdings) ? d.holdings : [];

    const holdings: HoldingItem[] = rawHoldings.map((h: any) => ({
      symbol: h.symbol || 'STOCK',
      companyName: h.companyName || h.company_name || h.name || h.symbol || '',
      sector: h.sector || 'Equities',
      quantity: h.quantity ?? h.qty ?? null,
      avgPrice: h.avgPrice ?? h.avg_price ?? null,
      currentPrice: h.currentPrice ?? h.current_price ?? h.ltp ?? null,
      investedValue: h.investedValue ?? h.invested_value ?? null,
      currentValue: h.currentValue ?? h.current_value ?? null,
      unrealizedPnL: h.unrealizedPnL ?? h.unrealized_pnl ?? h.pnl ?? null,
      unrealizedPnLPct: h.unrealizedPnLPct ?? h.unrealized_pnl_pct ?? h.pnl_pct ?? null,
      weightPct: h.weightPct ?? h.weight_pct ?? null,
      decisionScore: h.decisionScore ?? h.decision_score ?? h.score ?? null,
      confidence: h.confidence || 'MEDIUM',
      healthState: h.healthState || h.health_state || 'HEALTHY',
      riskContribution: h.riskContribution || h.risk_contribution || 'LOW',
    }));

    const normalized: PortfolioSummaryData = {
      investedValue: d.investedValue ?? d.invested_value ?? null,
      currentValue: d.currentValue ?? d.current_value ?? null,
      totalPnL: d.totalPnL ?? d.total_pnl ?? d.pnl ?? null,
      totalPnLPct: d.totalPnLPct ?? d.total_pnl_pct ?? d.pnl_pct ?? null,
      todayPnL: d.todayPnL ?? d.today_pnl ?? d.day_pnl ?? null,
      todayPnLPct: d.todayPnLPct ?? d.today_pnl_pct ?? d.day_pnl_pct ?? null,
      cashAvailable: d.cashAvailable ?? d.cash_available ?? d.cash ?? null,
      capitalDeployedPct: d.capitalDeployedPct ?? d.capital_deployed_pct ?? null,
      portfolioHeatScore: d.portfolioHeatScore ?? d.portfolio_heat_score ?? d.heat_score ?? null,
      portfolioRiskLevel: d.portfolioRiskLevel || d.portfolio_risk_level || d.risk_level || 'LOW',
      weakestHolding: d.weakestHolding ? {
        symbol: d.weakestHolding.symbol || '',
        currentLossPct: d.weakestHolding.currentLossPct ?? d.weakestHolding.current_loss_pct ?? null,
        score: d.weakestHolding.score ?? null,
        reason: d.weakestHolding.reason || '',
      } : null,
      strongestHolding: d.strongestHolding ? {
        symbol: d.strongestHolding.symbol || '',
        currentGainPct: d.strongestHolding.currentGainPct ?? d.strongestHolding.current_gain_pct ?? null,
        score: d.strongestHolding.score ?? null,
      } : null,
      holdingsCount: d.holdingsCount ?? d.holdings_count ?? holdings.length,
      holdings,
    };

    return {
      status: raw.status,
      freshness: raw.freshness,
      timestamp: raw.timestamp,
      data: normalized,
      message: raw.message,
      warnings: raw.warnings,
    };
  }

  async getSignals(): Promise<ApiResponse<SignalsData>> {
    const raw = await this.fetchWithFallback<any>([
      '/api/v1/signals',
      '/api/v1/signals/active',
      '/api/v2/signals',
    ]);

    if (!raw.data) {
      return {
        status: raw.status,
        freshness: raw.freshness,
        timestamp: raw.timestamp,
        data: null,
        message: raw.message,
        warnings: raw.warnings,
      };
    }

    const d = raw.data;
    const rawActive = Array.isArray(d) ? d : (d.activeSignals || d.active_signals || d.signals || []);
    const rawRecent = Array.isArray(d.recentTriggers || d.recent_triggers) ? (d.recentTriggers || d.recent_triggers) : [];

    const mapSignal = (s: any): SignalItem => ({
      id: s.id || `sig-${s.symbol || Math.random()}`,
      symbol: s.symbol || 'UNKNOWN',
      companyName: s.companyName || s.company_name || s.name || s.symbol || '',
      sector: s.sector || 'Equities',
      action: s.action || 'WATCH',
      score: s.score ?? s.strength_score ?? s.decision_score ?? null,
      confidence: s.confidence || 'MEDIUM',
      signalState: s.signalState || s.signal_state || 'ACTIVE',
      currentPrice: s.currentPrice ?? s.current_price ?? s.price ?? null,
      entryPrice: s.entryPrice ?? s.entry_price ?? s.entry ?? null,
      stopLoss: s.stopLoss ?? s.stop_loss ?? null,
      target1: s.target1 ?? s.target_1 ?? s.targetPrice ?? s.target_price ?? null,
      target2: s.target2 ?? s.target_2 ?? null,
      riskRewardRatio: s.riskRewardRatio ?? s.risk_reward_ratio ?? null,
      timeframe: s.timeframe || s.horizon || s.time_horizon || 'SWING',
      timestamp: s.timestamp || s.generated_at || raw.timestamp,
      shortRationale: s.shortRationale || s.short_rationale || s.catalyst_rationale || s.rationale || '',
      keyCatalyst: s.keyCatalyst || s.key_catalyst || s.catalyst || null,
      riskRating: s.riskRating || s.risk_rating || 'MEDIUM',
    });

    const activeSignals = rawActive.map(mapSignal);
    const recentTriggers = rawRecent.map(mapSignal);

    const normalized: SignalsData = {
      count: d.count ?? activeSignals.length,
      activeSignals,
      recentTriggers,
      lastAssessedTime: d.lastAssessedTime || d.last_assessed_time || raw.timestamp,
    };

    return {
      status: raw.status,
      freshness: raw.freshness,
      timestamp: raw.timestamp,
      data: normalized,
      message: raw.message,
      warnings: raw.warnings,
    };
  }

  // ==========================================
  // 2. SYSTEM HEALTH & DATA SOURCE STATUS APIS
  // ==========================================

  async getSystemHealth(): Promise<ApiResponse<SystemHealthData>> {
    // Concurrently attempt to query /api/v1/runtime/status and /api/v1/data-sources/status
    const [runtimeRes, dataSourcesRes, healthRes] = await Promise.all([
      this.fetchWithFallback<any>([
        '/api/v1/runtime/status',
        '/api/v1/system/status',
        '/api/v2/system/health',
      ]),
      this.fetchWithFallback<any>([
        '/api/v1/data-sources/status',
        '/api/v1/data-sources',
        '/api/v1/datasources/status',
      ]),
      this.fetchWithTimeout<any>('/health'),
    ]);

    // If both runtime and health checks failed completely
    if (!runtimeRes.data && !healthRes.data && !dataSourcesRes.data) {
      return {
        status: 'UNAVAILABLE',
        freshness: 'UNKNOWN',
        timestamp: new Date().toISOString(),
        data: null,
        message: runtimeRes.message || 'System health and runtime status endpoints are currently unreachable.',
      };
    }

    const rt = runtimeRes.data || {};
    const ds = dataSourcesRes.data || {};
    const hl = healthRes.data || {};

    const rawSourcesList = ds.sources || ds.data_sources || rt.sources || (Array.isArray(ds) ? ds : []);

    const sources: SourceHealth[] = rawSourcesList.map((s: any) => ({
      name: s.name || s.source_name || s.id || 'Data Feed',
      category: s.category || s.type || 'QUOTES',
      status: s.status || 'HEALTHY',
      latencyMs: s.latencyMs ?? s.latency_ms ?? s.latency ?? null,
      lastSuccessTimestamp: s.lastSuccessTimestamp || s.last_success_timestamp || s.last_sync || null,
      freshness: s.freshness || 'LIVE',
      warningNote: s.warningNote || s.warning_note || s.warning || undefined,
    }));

    const warnings: string[] = [
      ...(rt.warnings || rt.system_warnings || []),
      ...(ds.warnings || []),
      ...(healthRes.warnings || []),
    ];

    if (dataSourcesRes.status === 'UNAVAILABLE' && !ds.sources) {
      warnings.push('Data Sources status endpoint (/api/v1/data-sources/status) was not published by backend.');
    }

    const normalized: SystemHealthData = {
      runtimeStatus: (rt.runtimeStatus || rt.runtime_status || rt.status || hl.status === 'healthy' ? 'OPERATIONAL' : 'DEGRADED') as any,
      uptimeSeconds: rt.uptimeSeconds ?? rt.uptime_seconds ?? rt.uptime ?? null,
      schedulerStatus: rt.schedulerStatus || rt.scheduler_status || rt.scheduler || 'ACTIVE',
      lastCycleRunTime: rt.lastCycleRunTime || rt.last_cycle_run_time || rt.last_run || null,
      nextScheduledCycle: rt.nextScheduledCycle || rt.next_scheduled_cycle || rt.next_run || null,
      sources,
      systemWarnings: warnings,
      environment: rt.environment || rt.env || 'FastAPI Core (Live)',
    };

    return {
      status: runtimeRes.status === 'READY' || healthRes.status === 'READY' ? 'READY' : 'DEGRADED',
      freshness: 'LIVE',
      timestamp: new Date().toISOString(),
      data: normalized,
      warnings: warnings.length > 0 ? warnings : undefined,
    };
  }

  // ==========================================
  // 3. SETTINGS & PROVIDER CONNECTIONS APIS
  // ==========================================

  async getConnectionsState(): Promise<ApiResponse<ConnectionsState>> {
    // Concurrently fetch specific connection endpoints for kotak-neo, upstox, global-datafeeds, gnews, and aggregate
    const [kotakRes, upstoxRes, datafeedsRes, gnewsRes, aggregateRes, coverageRes, readinessRes, trialRes] = await Promise.all([
      this.fetchWithFallback<any>([
        '/api/v1/connections/kotak-neo',
        '/api/v1/connections/kotak_neo',
        '/api/v1/settings/connections/kotak-neo',
      ]),
      this.fetchWithTimeout<any>(CONNECTION_ROUTES.upstox.profile),
      this.fetchWithFallback<any>([
        '/api/v1/connections/global-datafeeds',
        '/api/v1/connections/global_datafeeds',
        '/api/v1/settings/connections/global-datafeeds',
      ]),
      this.fetchWithFallback<any>([
        '/api/v1/connections/gnews',
        '/api/v1/settings/connections/gnews',
      ]),
      this.fetchWithFallback<any>([
        '/api/v1/connections',
        '/api/v1/settings/connections',
        '/api/v2/settings/connections',
      ]),
      this.fetchWithFallback<any>([
        '/api/v1/data-coverage',
        '/api/v1/system/coverage',
        '/api/v1/coverage',
      ]),
      this.fetchWithFallback<any>([
        '/api/v1/brain/readiness',
        '/api/v1/system/brain-readiness',
        '/api/v1/readiness',
      ]),
      this.fetchWithFallback<any>([
        '/api/v1/brain/trial',
        '/api/v1/trial/cohort',
      ]),
    ]);

    // If aggregate connection state exists on backend
    if (aggregateRes.data && aggregateRes.data.providers) {
      return aggregateRes as ApiResponse<ConnectionsState>;
    }

    // Map each provider individually from its connection endpoint
    const mapProvider = (
      id: 'kotak_neo' | 'upstox' | 'global_datafeeds' | 'gnews',
      defaultName: string,
      category: 'BROKER_API' | 'DATA_FEED' | 'NEWS_PROVIDER' | 'HISTORICAL_PROVIDER',
      roleBadge: string,
      roleDescription: string,
      res: ApiResponse<any>,
      defaultCaps: string[],
      isOptional: boolean = false
    ): ConnectionProviderStatus => {
      const d = res.data;
      if (!d) {
        return {
          id,
          name: defaultName,
          category,
          roleBadge,
          roleDescription,
          isOptional,
          configured: false,
          validated: false,
          status: res.status === 'UNAVAILABLE' ? 'UNAVAILABLE' : 'NOT_CONFIGURED',
          capabilities: defaultCaps,
          lastValidatedTimestamp: null,
          warnings: res.message ? [res.message] : [],
          latencyMs: null,
          hasSavedToken: false,
        };
      }

      return {
        id,
        name: d.name || defaultName,
        category: d.category || category,
        roleBadge: d.roleBadge || roleBadge,
        roleDescription: d.roleDescription || roleDescription,
        isOptional: d.isOptional ?? isOptional,
        configured: id === 'upstox'
          ? d.credential_fields_configured?.access_token === true
          : Boolean(d.configured ?? d.is_configured ?? d.credential_fields_configured ?? d.has_credentials ?? false),
        validated: Boolean(d.validated ?? d.is_validated ?? false),
        status: d.status || (d.validated ? 'VALIDATED' : (d.configured ? 'CONFIGURED' : 'NOT_CONFIGURED')),
        capabilities: d.capabilities || defaultCaps,
        lastValidatedTimestamp: d.lastValidatedTimestamp || d.last_validated_timestamp || d.last_validated || null,
        warnings: d.warnings || [],
        latencyMs: d.latencyMs ?? d.latency_ms ?? null,
        hasSavedToken: id === 'upstox'
          ? d.credential_fields_configured?.access_token === true
          : Boolean(d.hasSavedToken ?? d.has_saved_token ?? d.credential_fields_configured ?? d.has_credentials ?? false),
      };
    };

    const providers: ConnectionProviderStatus[] = [
      mapProvider(
        'kotak_neo',
        'Kotak Neo API',
        'BROKER_API',
        'CURRENT QUOTES',
        'Current Quotes / Current Market Data',
        kotakRes,
        ['Real-time NSE LTP', 'Order Execution Gateway', 'Portfolio Holdings Sync']
      ),
      mapProvider(
        'upstox',
        'Upstox API',
        'HISTORICAL_PROVIDER',
        'HISTORICAL OHLCV',
        'Historical Market Data (OHLCV Candles & Time Series)',
        upstoxRes,
        ['Historical Daily OHLCV', 'Multi-Year Historical OHLCV', 'Adjustment Basis: UNKNOWN']
      ),
      mapProvider(
        'global_datafeeds',
        'Global Datafeeds (GFDL)',
        'DATA_FEED',
        'HISTORICAL OHLCV · OPTIONAL',
        'Historical OHLCV — Optional',
        datafeedsRes,
        ['Level-2 Market Depth', 'Tick-by-Tick Feed', 'Index Greeks & Open Interest'],
        true
      ),
      mapProvider(
        'gnews',
        'GNews Financial API',
        'NEWS_PROVIDER',
        'SECONDARY NEWS / RESEARCH',
        'Secondary News / Research & Sentiment',
        gnewsRes,
        ['NSE Corporate Announcements', 'Macro Regulatory Feeds', 'Sentiment Scoring']
      ),
    ];

    // Data coverage normalization (Use backend values ONLY, do not fabricate numbers)
    const cov = coverageRes.data;
    const dataCoverage: DataCoverageData | null = cov
      ? {
          universeCount: cov.universeCount ?? cov.universe_count ?? null,
          universeLabel: cov.universeLabel ?? cov.universe_label ?? null,
          currentQuotes: cov.currentQuotes ?? cov.current_quotes ?? null,
          historicalOhlcv: cov.historicalOhlcv ?? cov.historical_ohlcv ?? null,
          taxonomy: cov.taxonomy ?? null,
          fundamentals: cov.fundamentals ?? null,
          ownership: cov.ownership ?? null,
          delivery: cov.delivery ?? null,
          lastUpdated: cov.lastUpdated ?? cov.last_updated ?? null,
        }
      : null;

    // Brain readiness normalization
    const br = readinessRes.data;
    const brainReadiness: BrainDataReadinessData | null = br
      ? {
          overallStatus: br.overallStatus || br.overall_status || 'UNAVAILABLE',
          disclaimer: 'This is data readiness, NOT an investment score.',
          items: Array.isArray(br.items)
            ? br.items.map((it: any) => ({
                key: it.key || it.name?.toLowerCase().replace(/[^a-z0-9]/g, '_') || 'item',
                name: it.name || 'Data Feed',
                status: it.status || 'UNAVAILABLE',
                detail: it.detail || it.description || null,
                lastSync: it.lastSync || it.last_sync || null,
              }))
            : [],
          lastAssessed: br.lastAssessed || br.last_assessed || null,
        }
      : null;

    // Real brain trial normalization
    const tr = trialRes.data;
    const realBrainTrial: RealBrainTrialData = tr
      ? {
          isAvailable: Boolean(tr.isAvailable ?? tr.is_available ?? true),
          frozenCohort: tr.frozenCohort ?? tr.frozen_cohort ?? null,
          historicalReady: tr.historicalReady ?? tr.historical_ready ?? null,
          technicalReady: tr.technicalReady ?? tr.technical_ready ?? null,
          preBreakoutReady: tr.preBreakoutReady ?? tr.pre_breakout_ready ?? null,
          inflectionReady: tr.inflectionReady ?? tr.inflection_ready ?? null,
          unavailabilityMessage: tr.unavailabilityMessage ?? tr.message ?? null,
        }
      : {
          isAvailable: false,
          frozenCohort: null,
          historicalReady: null,
          technicalReady: null,
          preBreakoutReady: null,
          inflectionReady: null,
          unavailabilityMessage: 'Available after backend data ingestion',
        };

    const upstoxValData = upstoxRes.data?.validationFlow || upstoxRes.data?.validation_flow;
    const upstoxValidation: UpstoxValidationFlow = upstoxValData
      ? {
          credentials: upstoxValData.credentials || 'NOT_TESTED',
          instrumentResolution: upstoxValData.instrumentResolution || upstoxValData.instrument_resolution || 'NOT_TESTED',
          historicalAccess: upstoxValData.historicalAccess || upstoxValData.historical_access || 'NOT_TESTED',
          normalization: upstoxValData.normalization || 'NOT_TESTED',
          persistence: upstoxValData.persistence || 'NOT_TESTED',
          lastTestedTimestamp: upstoxValData.lastTestedTimestamp || upstoxValData.last_tested_timestamp || null,
          errorMessage: upstoxValData.errorMessage || upstoxValData.error_message || null,
        }
      : {
          credentials: 'NOT_TESTED',
          instrumentResolution: 'NOT_TESTED',
          historicalAccess: 'NOT_TESTED',
          normalization: 'NOT_TESTED',
          persistence: 'NOT_TESTED',
          lastTestedTimestamp: null,
        };

    return {
      status: 'READY',
      freshness: 'LIVE',
      timestamp: new Date().toISOString(),
      data: {
        providers,
        activeEnvironment: 'PRODUCTION',
        upstoxValidation,
        dataCoverage,
        brainReadiness,
        realBrainTrial,
      },
    };
  }

  async validateConnection(
    providerId: string,
    credentials?: Record<string, string>
  ): Promise<ApiResponse<{ success: boolean; message: string; stageResults?: Partial<UpstoxValidationFlow> }>> {
    const formattedProvider = providerId.replace(/_/g, '-');
    const body = JSON.stringify({ providerId, ...credentials });

    const res = await this.fetchWithFallback<any>([
      `/api/v1/connections/${formattedProvider}/validate`,
      `/api/v1/connections/${providerId}/validate`,
      `/api/v1/settings/connections/validate`,
    ], {
      method: 'POST',
      body,
    });

    if (res.status === 'READY' && res.data) {
      return {
        status: 'READY',
        freshness: 'LIVE',
        timestamp: res.timestamp,
        data: {
          success: res.data.success ?? true,
          message: res.data.message || 'Validation completed successfully',
          stageResults: res.data.stageResults || res.data.stage_results || undefined,
        },
      };
    }

    return {
      status: res.status,
      freshness: res.freshness,
      timestamp: res.timestamp,
      data: {
        success: false,
        message: res.message || 'Validation endpoint unreachable on backend.',
      },
      message: res.message,
    };
  }

  async saveConnectionCredentials(
    providerId: string,
    credentials: Record<string, string>
  ): Promise<ApiResponse<{ success: boolean; message: string }>> {
    if (providerId === 'upstox') {
      // The published schema deliberately accepts only access_token.  Do not
      // propagate alternate token names or any local form state to the API.
      const accessToken = credentials.access_token;
      if (!accessToken) {
        return {
          status: 'ERROR', freshness: 'UNKNOWN', timestamp: new Date().toISOString(), data: {
            success: false, message: 'MISSING_CONFIGURATION: Upstox Analytics Token is required.',
          },
        };
      }
      const saved = await this.fetchWithTimeout<any>(CONNECTION_ROUTES.upstox.profile, {
        method: 'PUT', body: JSON.stringify({ access_token: accessToken }),
      });
      if (saved.status !== 'READY') {
        return {
          status: saved.status, freshness: saved.freshness, timestamp: saved.timestamp,
          data: { success: false, message: saved.message || 'Upstox credential save failed on backend.' },
          message: saved.message,
        };
      }
      // A successful PUT is not enough to show SAVED. Re-read the public
      // profile and use its boolean presence flag as the only UI authority.
      const profile = await this.fetchWithTimeout<any>(CONNECTION_ROUTES.upstox.profile);
      const configured = profile.status === 'READY' && profile.data?.credential_fields_configured?.access_token === true;
      return {
        status: profile.status, freshness: profile.freshness, timestamp: profile.timestamp,
        data: {
          success: configured,
          message: configured
            ? 'Upstox Analytics Token is saved securely on the backend.'
            : profile.message || 'Backend did not confirm the Upstox Analytics Token was saved.',
        },
        message: profile.message,
      };
    }
    const formattedProvider = providerId.replace(/_/g, '-');
    const body = JSON.stringify({ providerId, ...credentials });

    const res = await this.fetchWithFallback<any>([
      `/api/v1/connections/${formattedProvider}/credentials`,
      `/api/v1/connections/${providerId}/credentials`,
      `/api/v1/connections/${formattedProvider}/save`,
      `/api/v1/settings/connections/save`,
    ], {
      method: 'POST',
      body,
    });

    if (res.status === 'READY' && res.data) {
      return {
        status: 'READY',
        freshness: 'LIVE',
        timestamp: res.timestamp,
        data: {
          success: res.data.success ?? true,
          message: res.data.message || `Credentials for ${providerId} saved securely on backend.`,
        },
      };
    }

    return {
      status: res.status,
      freshness: res.freshness,
      timestamp: res.timestamp,
      data: {
        success: false,
        message: res.message || `Failed to save credentials for ${providerId} on backend.`,
      },
      message: res.message,
    };
  }

  async testHistoricalData(
    providerId: string
  ): Promise<ApiResponse<{ success: boolean; message: string; flow?: UpstoxValidationFlow }>> {
    if (providerId === 'upstox') {
      const res = await this.fetchWithTimeout<any>(CONNECTION_ROUTES.upstox.test, { method: 'POST' });
      const flow = normalizeUpstoxValidationFlow(
        res.data?.validation_flow || res.data?.validationFlow,
        res.data?.error_code,
      );
      const safeMessage = res.data?.error_code
        ? `${res.data.error_code}: ${res.message || 'Upstox historical validation failed.'}`
        : res.message || 'Upstox historical test completed.';
      return {
        status: res.status, freshness: res.freshness, timestamp: res.timestamp,
        data: { success: res.status === 'READY', message: safeMessage, flow }, message: safeMessage,
      };
    }
    const formattedProvider = providerId.replace(/_/g, '-');

    const res = await this.fetchWithFallback<any>([
      `/api/v1/connections/${formattedProvider}/test-historical`,
      `/api/v1/connections/${providerId}/test-historical`,
      `/api/v1/connections/${formattedProvider}/historical-test`,
      `/api/v1/connections/${formattedProvider}/test`,
    ], {
      method: 'POST',
    });

    if (res.status === 'READY' && res.data) {
      const fl = res.data.flow || res.data.stages || res.data;
      return {
        status: 'READY',
        freshness: 'LIVE',
        timestamp: res.timestamp,
        data: {
          success: res.data.success ?? true,
          message: res.data.message || 'Historical OHLCV access validated successfully.',
          flow: fl && typeof fl === 'object' && 'credentials' in fl
            ? {
                credentials: fl.credentials || 'VALIDATED',
                instrumentResolution: fl.instrumentResolution || fl.instrument_resolution || 'VALIDATED',
                historicalAccess: fl.historicalAccess || fl.historical_access || 'VALIDATED',
                normalization: fl.normalization || 'VALIDATED',
                persistence: fl.persistence || 'VALIDATED',
                lastTestedTimestamp: fl.lastTestedTimestamp || new Date().toLocaleTimeString('en-IN') + ' IST',
                errorMessage: fl.errorMessage || null,
              }
            : undefined,
        },
      };
    }

    return {
      status: res.status,
      freshness: res.freshness,
      timestamp: res.timestamp,
      data: {
        success: false,
        message: res.message || 'Historical test endpoint is currently unavailable on backend.',
        flow: {
          credentials: 'UNAVAILABLE',
          instrumentResolution: 'UNAVAILABLE',
          historicalAccess: 'UNAVAILABLE',
          normalization: 'UNAVAILABLE',
          persistence: 'UNAVAILABLE',
          lastTestedTimestamp: null,
          errorMessage: res.message,
        },
      },
      message: res.message,
    };
  }

  async clearConnectionCredentials(
    providerId: string
  ): Promise<ApiResponse<{ success: boolean; message: string }>> {
    if (providerId === 'upstox') {
      const res = await this.fetchWithTimeout<any>(CONNECTION_ROUTES.upstox.credentials, { method: 'DELETE' });
      return {
        status: res.status, freshness: res.freshness, timestamp: res.timestamp,
        data: { success: res.status === 'READY', message: res.message || 'Upstox credential clear completed.' }, message: res.message,
      };
    }
    const formattedProvider = providerId.replace(/_/g, '-');

    const res = await this.fetchWithFallback<any>([
      `/api/v1/connections/${formattedProvider}/credentials`,
      `/api/v1/connections/${providerId}/credentials`,
      `/api/v1/connections/${formattedProvider}/clear`,
    ], {
      method: 'DELETE',
    });

    if (res.status === 'READY' && res.data) {
      return {
        status: 'READY',
        freshness: 'LIVE',
        timestamp: res.timestamp,
        data: {
          success: res.data.success ?? true,
          message: res.data.message || `Credentials for ${providerId} cleared on backend.`,
        },
      };
    }

    return {
      status: res.status,
      freshness: res.freshness,
      timestamp: res.timestamp,
      data: {
        success: false,
        message: res.message || `Clear credentials endpoint for ${providerId} unavailable on backend.`,
      },
      message: res.message,
    };
  }

  async getDataCoverage(): Promise<ApiResponse<DataCoverageData>> {
    return this.fetchWithFallback<DataCoverageData>([
      '/api/v1/data-coverage',
      '/api/v1/system/coverage',
      '/api/v1/coverage',
    ]);
  }

  async getBrainReadiness(): Promise<ApiResponse<BrainDataReadinessData>> {
    return this.fetchWithFallback<BrainDataReadinessData>([
      '/api/v1/brain/readiness',
      '/api/v1/system/brain-readiness',
      '/api/v1/readiness',
    ]);
  }

  async getRealBrainTrial(): Promise<ApiResponse<RealBrainTrialData>> {
    return this.fetchWithFallback<RealBrainTrialData>([
      '/api/v1/brain/trial',
      '/api/v1/trial/cohort',
    ]);
  }

  async getCapitalRotation(): Promise<ApiResponse<CapitalRotationData>> {
    const response = await this.fetchWithTimeout<any>('/api/v1/capital-rotation');
    if (!response.data) return response as ApiResponse<CapitalRotationData>;
    const value = response.data;
    const status: ApiStatus = value.overall_status === 'UNAVAILABLE' ? 'UNAVAILABLE'
      : value.overall_status === 'PARTIAL' ? 'PARTIAL'
      : value.overall_status === 'EMPTY' ? 'EMPTY'
      : 'READY';
    return {
      ...response, status,
      freshness: value.freshness === 'AS_OF_SNAPSHOT' ? 'EOD' : 'UNKNOWN',
      message: value.message ?? response.message, warnings: value.warnings ?? [],
      data: {
        overallStatus: value.overall_status, dataAsOf: value.data_as_of ?? null,
        freshness: value.freshness, marketRegime: value.market_regime ?? null,
        opportunityCoverage: value.opportunity_coverage,
        rotationComparisonStatus: value.rotation_comparison_status,
        holdingCount: value.summary?.holding_count ?? null,
        portfolioHeat: value.summary?.portfolio_heat ?? null,
        weakestHoldingSymbol: value.summary?.weakest_holding_symbol ?? null,
        opportunities: (value.opportunities ?? []).map((item: any) => ({
          currentHoldingSymbol: item.current_holding_symbol ?? null, currentHoldingScore: item.current_holding_score ?? null,
          candidateSymbol: item.candidate_symbol, candidateScore: item.candidate_score ?? null,
          scoreAdvantage: item.score_advantage ?? null, candidateConfidence: item.candidate_confidence ?? null,
          holdingConfidence: item.holding_confidence ?? null, candidateRiskReward: item.candidate_risk_reward ?? null,
          sectorContext: item.sector_context ?? null, catalystContext: item.catalyst_context ?? null,
          freshness: item.freshness, executionEligibility: item.execution_eligibility,
          publicGateSummary: item.public_gate_summary ?? [], recommendedAction: item.recommended_action,
          rationale: item.rationale, invalidationSummary: item.invalidation_summary ?? null, warnings: item.warnings ?? [],
        })),
        warnings: value.warnings ?? [], message: value.message ?? null,
      },
    };
  }

  async getPortfolioSellSide(): Promise<ApiResponse<SellSideData>> {
    const response = await this.fetchWithTimeout<any>('/api/v1/portfolio/sell-side');
    if (!response.data) return response as ApiResponse<SellSideData>;
    const value = response.data;
    return {
      ...response,
      status: value.status === 'NO_CURRENT_CANONICAL_PORTFOLIO' ? 'EMPTY' : value.status === 'READY' ? 'READY' : 'PARTIAL',
      data: {
        status: value.status, portfolioSnapshotId: value.portfolio_snapshot_id ?? null,
        policyFingerprint: value.policy_fingerprint, warnings: value.warnings ?? [],
        decisions: (value.decisions ?? []).map((item: any) => ({
          holdingId: item.holding_id, action: item.action, thesisState: item.thesis_state,
          capitalEfficiencyState: item.capital_efficiency_state ?? null, rotationState: item.rotation_state ?? null,
          reasons: item.reasons ?? [], blockers: item.blockers ?? [], evidenceFreshness: item.evidence_freshness,
          policyFingerprint: item.policy_fingerprint,
        })),
      },
    };
  }

  async getStocksList(): Promise<ApiResponse<StockListItem[]>> {
    return this.fetchWithFallback<StockListItem[]>([
      '/api/v1/stocks',
      '/api/v2/stocks',
    ]);
  }

  async getStockDetail(symbol: string): Promise<ApiResponse<StockDetailData>> {
    return this.fetchWithFallback<StockDetailData>([
      `/api/v1/stocks/${encodeURIComponent(symbol)}`,
      `/api/v2/stocks/${encodeURIComponent(symbol)}`,
    ]);
  }

  async getSharedBrainAnalysis(symbol: string): Promise<ApiResponse<SharedBrainAnalysisData>> {
    const response = await this.fetchWithTimeout<any>(`/api/v1/stocks/${encodeURIComponent(symbol)}/shared-brain?context=DEEP_ANALYSIS`);
    if (!response.data) return response as ApiResponse<SharedBrainAnalysisData>;
    const value = response.data;
    const paperAggregate = (item: any) => ({
      evidenceSufficiency: item.evidence_sufficiency,
      scope: item.scope,
      cohortDefinition: item.cohort_definition ?? [],
      asOf: item.as_of,
      aggregationVersion: item.aggregation_version,
      sampleCount: item.sample_count,
      completedCount: item.completed_count,
      eligibleRealizedCount: item.eligible_realized_count,
      openCount: item.open_count,
      waitingCount: item.waiting_count,
      ambiguousCount: item.ambiguous_count,
      blockedCount: item.blocked_count,
      expiredUnfilledCount: item.expired_unfilled_count,
      missedDoNotChaseCount: item.missed_do_not_chase_count,
      winRate: item.win_rate ?? null,
      expectancyR: item.expectancy_r ?? null,
      medianR: item.median_r ?? null,
      averageR: item.average_r ?? null,
      averageGrossR: item.average_gross_r ?? null,
      medianGrossR: item.median_gross_r ?? null,
      profitFactor: item.profit_factor ?? null,
      medianMfeR: item.median_mfe_r ?? null,
      medianMaeR: item.median_mae_r ?? null,
      averageHoldingSessions: item.average_holding_sessions ?? null,
      targetHitRate: item.target_hit_rate ?? null,
      stopHitRate: item.stop_hit_rate ?? null,
      expiredUnfilledRate: item.expired_unfilled_rate ?? null,
      missedDoNotChaseRate: item.missed_do_not_chase_rate ?? null,
      sourceStudyIds: item.source_study_ids ?? [],
      sourceStudyFingerprints: item.source_study_fingerprints ?? [],
      policyVersions: item.policy_versions ?? [],
      executionModelVersions: item.execution_model_versions ?? [],
      directionValues: item.direction_values ?? [],
      fingerprint: item.fingerprint,
    });
    return {
      ...response,
      data: {
        canonicalInstrumentId: value.canonical_instrument_id,
        symbol: value.symbol,
        name: value.name ?? null,
        exchange: value.exchange,
        asOf: value.as_of,
        requestedContext: value.requested_context,
        evidenceStatus: value.evidence_status,
        evidenceDomains: (value.evidence_domains ?? []).map((item: any) => ({ domain: item.domain, availability: item.availability })),
        financialSemantics: (value.financial_semantics ?? []).map((item: any) => ({
          metric: item.metric,
          trajectoryBasis: item.trajectory_basis,
          previousPeriodLabel: item.previous_period_label ?? null,
          currentPeriodLabel: item.current_period_label ?? null,
          previousValue: item.previous_value ?? null,
          currentValue: item.current_value ?? null,
          absoluteDelta: item.absolute_delta ?? null,
          relativeDelta: item.relative_delta ?? null,
          signTransition: item.sign_transition ?? null,
          factualDisplayPhrase: item.factual_display_phrase ?? null,
          directionalityOrientation: item.directionality_orientation ?? null,
          directionalityRationaleCode: item.directionality_rationale_code ?? null,
          materialityGovernanceState: item.materiality_governance_state,
          trajectoryFingerprint: item.trajectory_fingerprint,
          directionalityFingerprint: item.directionality_fingerprint ?? null,
        })),
        blockers: value.blockers ?? [],
        warnings: value.warnings ?? [],
        snapshotFingerprint: value.snapshot_fingerprint,
        unifiedStateFingerprint: value.unified_state_fingerprint,
        brainResearchStateV2Fingerprint: value.brain_research_state_v2_fingerprint,
        contextProjectionFingerprint: value.context_projection_fingerprint,
        financialSemanticSectionFingerprint: value.financial_semantic_section_fingerprint,
        materialityPolicyId: value.materiality_policy_id,
        materialityPolicyVersion: value.materiality_policy_version,
        materialityPolicyFingerprint: value.materiality_policy_fingerprint,
        materialityCalibrationStatus: value.materiality_calibration_status,
        forwardPerformanceIntelligence: {
          instrumentHistory: paperAggregate(value.forward_performance_intelligence.instrument_history),
          relevantCohortHistory: paperAggregate(value.forward_performance_intelligence.relevant_cohort_history),
          warnings: value.forward_performance_intelligence.warnings ?? [],
        },
      },
    };
  }

  async getPaperTrading(): Promise<ApiResponse<PaperTradingData>> {
    return this.fetchWithFallback<PaperTradingData>([
      '/api/v1/paper-trading',
      '/api/v2/paper-trading',
    ]);
  }

  async getPerformance(): Promise<ApiResponse<PerformanceData>> {
    return this.fetchWithFallback<PerformanceData>([
      '/api/v1/performance',
      '/api/v2/performance',
    ]);
  }

  async getPrimaryMarket(): Promise<ApiResponse<PrimaryMarketData>> {
    return this.fetchWithFallback<PrimaryMarketData>([
      '/api/v1/primary-market',
      '/api/v2/primary-market',
    ]);
  }

  async getNews(): Promise<ApiResponse<NewsData>> {
    return this.fetchWithFallback<NewsData>([
      '/api/v1/news',
      '/api/v2/news',
    ]);
  }
}
