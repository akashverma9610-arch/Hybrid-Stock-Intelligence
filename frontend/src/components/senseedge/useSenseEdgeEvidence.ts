import { useEffect, useState } from 'react';
import { useDataClient } from '../../api/context';
import type { ApiResponse } from '../../types/api';
import type { MarketWideWatchData, PortfolioRuntimeHolding } from '../../types/devConsole';
import type { PortfolioSummaryData } from '../../types/portfolio';
import type { NewsData } from '../../types/news';
import type { MarketStateData } from '../../types/market';

export interface SenseEdgeEvidence {
  watch: ApiResponse<MarketWideWatchData> | null;
  holdings: ApiResponse<PortfolioRuntimeHolding[]> | null;
  portfolio: ApiResponse<PortfolioSummaryData> | null;
  news: ApiResponse<NewsData> | null;
  market: ApiResponse<MarketStateData> | null;
}
const empty: SenseEdgeEvidence = { watch: null, holdings: null, portfolio: null, news: null, market: null };
const failed = <T>(): ApiResponse<T> => ({ data: null, status: 'UNAVAILABLE', freshness: 'UNKNOWN', timestamp: null });
export function useSenseEdgeEvidence() {
  const { client, refreshTrigger } = useDataClient();
  const [data, setData] = useState<SenseEdgeEvidence>(empty);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    let current = true;
    setData(empty); setLoading(true);
    async function read() {
      const [watch, holdings, portfolio, news, market] = await Promise.all([
        client.getMarketWideWatch().catch(failed<MarketWideWatchData>),
        client.getPortfolioRuntimeHoldings().catch(failed<PortfolioRuntimeHolding[]>),
        client.getPortfolioSummary().catch(failed<PortfolioSummaryData>),
        client.getNews().catch(failed<NewsData>),
        client.getMarketState().catch(failed<MarketStateData>),
      ]);
      if (current) { setData({ watch, holdings, portfolio, news, market }); setLoading(false); }
    }
    void read();
    return () => { current = false; };
  }, [client, refreshTrigger]);
  return { data, loading };
}
