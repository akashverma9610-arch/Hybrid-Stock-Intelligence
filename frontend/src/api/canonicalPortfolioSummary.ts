/** Exact public /portfolio/summary contract, not the legacy dashboard estimate. */
import type { ApiResponse } from '../types/api';
export interface CanonicalPortfolioSummary {
  portfolioId: string;
  asOf: string;
  investedValue: string;
  currentValue: string | null;
  unrealizedPnL: string | null;
  cashAvailable: string | null;
  cashStatus: 'KNOWN' | 'UNKNOWN';
  holdingCount: number;
  dataStatus: 'COMPLETE' | 'PARTIAL' | 'INSUFFICIENT_DATA';
  warnings: string[];
}

/** Local-operator read transport; no credentials, fallback route or mock summary. */
export async function readCanonicalPortfolioSummary(
  origin: string, signal?: AbortSignal,
): Promise<ApiResponse<CanonicalPortfolioSummary>> {
  const unavailable = (message: string): ApiResponse<CanonicalPortfolioSummary> => ({
    status:'UNAVAILABLE',freshness:'UNKNOWN',timestamp:null,data:null,message,
  });
  let url: URL;
  try {
    url = new URL(origin);
    if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password
      || url.search || url.hash || url.pathname !== '/') throw new Error();
    if (url.protocol !== 'https:' && !['localhost', '127.0.0.1', '[::1]'].includes(url.hostname)) throw new Error();
    url.pathname = '/api/v1/portfolio/summary';
  } catch { return unavailable('INVALID_BACKEND_ORIGIN'); }
  const controller = new AbortController();
  const cancel = () => controller.abort();
  signal?.addEventListener('abort',cancel,{once:true});
  if (signal?.aborted) cancel();
  const timer = setTimeout(cancel,6000);
  try {
    if (controller.signal.aborted) return unavailable('REQUEST_CANCELLED');
    const response = await fetch(url,{method:'GET',signal:controller.signal,cache:'no-store',redirect:'error',
      credentials:'omit',headers:{Accept:'application/json'}});
    if (!response.ok) return unavailable(`HTTP_${response.status}`);
    const data = parseCanonicalPortfolioSummary(await response.json());
    if (!data) return unavailable('PORTFOLIO_RESPONSE_CONTRACT_INVALID');
    return {status:data.dataStatus === 'COMPLETE' ? 'READY' : data.dataStatus === 'INSUFFICIENT_DATA' ? 'DEGRADED' : 'PARTIAL',freshness:'UNKNOWN',timestamp:data.asOf,data,
      warnings:[...data.warnings,'RETAINED_PORTFOLIO_FRESHNESS_NOT_VERIFIED']};
  } catch {
    return unavailable(controller.signal.aborted ? signal?.aborted ? 'REQUEST_CANCELLED' : 'PORTFOLIO_QUERY_TIMEOUT'
      : 'PORTFOLIO_TRANSPORT_OR_RESPONSE_UNAVAILABLE');
  } finally { clearTimeout(timer); signal?.removeEventListener('abort',cancel); }
}
const decimal = (v: unknown): v is string => typeof v === 'string' && /^-?\d+(?:\.\d+)?$/.test(v);
const nullableDecimal = (v: unknown): v is string | null => v === null || decimal(v);
export function parseCanonicalPortfolioSummary(value: unknown): CanonicalPortfolioSummary | null {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return null;
  const v = value as Record<string, unknown>;
  if (typeof v.portfolio_id !== 'string' || !v.portfolio_id.trim() || typeof v.as_of !== 'string'
    || !/^\d{4}-\d{2}-\d{2}T.+(?:Z|[+-]\d{2}:\d{2})$/.test(v.as_of) || !Number.isFinite(Date.parse(v.as_of))
    || !decimal(v.invested_value) || !nullableDecimal(v.marked_value) || !nullableDecimal(v.unrealized_pnl)
    || !nullableDecimal(v.cash) || typeof v.cash_status !== 'string' || !['KNOWN','UNKNOWN'].includes(v.cash_status)
    || (v.cash_status === 'UNKNOWN' ? v.cash !== null : v.cash === null)
    || !Number.isSafeInteger(v.holding_count) || (v.holding_count as number) < 0
    || typeof v.data_status !== 'string' || !['COMPLETE','PARTIAL','INSUFFICIENT_DATA'].includes(v.data_status)
    || !Array.isArray(v.warnings) || !v.warnings.every(w=>typeof w === 'string')) return null;
  return {portfolioId:v.portfolio_id,asOf:v.as_of,investedValue:v.invested_value,currentValue:v.marked_value,
    unrealizedPnL:v.unrealized_pnl,cashAvailable:v.cash,cashStatus:v.cash_status as 'KNOWN'|'UNKNOWN',
    holdingCount:v.holding_count as number,dataStatus:v.data_status as CanonicalPortfolioSummary['dataStatus'],warnings:[...v.warnings]};
}
