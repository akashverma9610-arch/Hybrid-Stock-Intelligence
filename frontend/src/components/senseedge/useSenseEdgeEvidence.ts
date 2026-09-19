import { useEffect, useState } from 'react';
import { useDataClient } from '../../api/context';
import type { ApiResponse } from '../../types/api';
import type { MarketWideWatchData, PortfolioRuntimeHolding } from '../../types/devConsole';
import { readCanonicalPortfolioSummary, type CanonicalPortfolioSummary } from '../../api/canonicalPortfolioSummary';
import type { NewsData } from '../../types/news';
import type { MarketStateData } from '../../types/market';

export interface SenseEdgeEvidence {
  watch: ApiResponse<MarketWideWatchData> | null;
  holdings: ApiResponse<PortfolioRuntimeHolding[]> | null;
  portfolio: ApiResponse<CanonicalPortfolioSummary> | null;
  news: ApiResponse<NewsData> | null;
  market: ApiResponse<MarketStateData> | null;
}
const empty: SenseEdgeEvidence = { watch: null, holdings: null, portfolio: null, news: null, market: null };
const failed = <T>(): ApiResponse<T> => ({ data: null, status: 'UNAVAILABLE', freshness: 'UNKNOWN', timestamp: null });
export function useSenseEdgeEvidence() {
  const { client, refreshTrigger, apiBaseUrl, isMockMode } = useDataClient();
  const [data, setData] = useState<SenseEdgeEvidence>(empty);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    let current = true;
    const controller = new AbortController();
    setData(empty); setLoading(true);
    async function read() {
      const [watch, holdings, portfolio, news, market] = await Promise.all([
        client.getMarketWideWatch().catch(failed<MarketWideWatchData>),
        client.getPortfolioRuntimeHoldings().catch(failed<PortfolioRuntimeHolding[]>),
        isMockMode ? Promise.resolve(failed<CanonicalPortfolioSummary>())
          : readCanonicalPortfolioSummary(apiBaseUrl,controller.signal).catch(failed<CanonicalPortfolioSummary>),
        client.getNews().catch(failed<NewsData>),
        client.getMarketState().catch(failed<MarketStateData>),
      ]);
      // A successful retained read is not a live observation or a coherent
      // cross-domain snapshot. Do not inherit the legacy transport's LIVE/now defaults.
      const retained = <T>(response: ApiResponse<T>, asOf: string | null): ApiResponse<T> => ({
        ...response, freshness:response.freshness === 'STALE' ? 'STALE' : 'UNKNOWN', timestamp:asOf,
        warnings:[...(response.warnings ?? []), ...(response.data ? ['RETAINED_SOURCE_FRESHNESS_NOT_VERIFIED'] : [])],
      });
      const holdingTimes = [...new Set<string>((holdings.data ?? []).map(row=>row.dataAsOf))];
      if (current) {
        setData({watch:retained(watch,watch.data?.watchAsOf ?? null),
          holdings:retained(holdings,holdingTimes.length === 1 ? holdingTimes[0] : null),portfolio,
          news:retained(news,null),market:retained(market,null)});
        setLoading(false);
      }
    }
    void read();
    return () => { current = false; controller.abort(); };
  }, [client, refreshTrigger, apiBaseUrl, isMockMode]);
  return { data, loading };
}
