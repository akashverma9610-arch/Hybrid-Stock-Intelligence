export interface LiveMarketHealthData {
  enabled: boolean;
  state: string;
  health: string;
  requestedTargets: number;
  subscribedTargets: number;
  mappedPackets: number;
  rejectedPackets: number;
  lastPacketAt: string | null;
  tokenState: string;
  reconnectCount: number;
}

export interface LiveMarketTargetData {
  canonicalInstrumentId: string;
  symbol: string;
  ltp: string | null;
  freshness: string;
  receivedAt: string | null;
  providerTradeTimestamp: string | null;
}

export interface LiveSetupMonitorData {
  canonicalInstrumentId: string;
  symbol: string;
  entry: string | null;
  stop: string | null;
  target: string | null;
  maximumEntry: string | null;
  state: string;
}

export interface LiveMarketOverviewData {
  health: LiveMarketHealthData;
  targets: LiveMarketTargetData[];
  setupMonitoring: LiveSetupMonitorData[];
  setupState: string;
}

export interface LivePortfolioValuationData {
  canonicalInstrumentId: string;
  symbol: string;
  quantity: string;
  averagePrice: string;
  ltp: string | null;
  marketValue: string | null;
  unrealizedPnl: string | null;
  providerTimestamp: string | null;
  receivedAt: string | null;
  state: string;
  blocker: string | null;
}

export interface LivePortfolioData {
  health: LiveMarketHealthData;
  holdings: LivePortfolioValuationData[];
}

export interface StockLiveMarketData {
  canonicalInstrumentId: string;
  health: LiveMarketHealthData;
  quote: LiveMarketTargetData | null;
}
