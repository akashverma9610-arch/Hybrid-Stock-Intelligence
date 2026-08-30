import { ApiResponse } from '../types/api';
import { MarketBreadthData, MarketExtremesData, MarketStateData, SectorLeadershipData } from '../types/market';
import { PortfolioSummaryData } from '../types/portfolio';
import { SignalsData } from '../types/signals';
import { CapitalRotationData } from '../types/rotation';
import { SellSideData } from '../types/sellSide';
import { SharedBrainAnalysisData, StockDetailData, StockListItem } from '../types/stock';
import { PaperTradingData } from '../types/paperTrading';
import { PerformanceData } from '../types/performance';
import { PrimaryMarketData } from '../types/primaryMarket';
import { NewsData } from '../types/news';
import { SystemHealthData } from '../types/systemHealth';
import {
  ConnectionsState,
  DataCoverageData,
  BrainDataReadinessData,
  RealBrainTrialData,
  UpstoxValidationFlow,
} from '../types/connections';

export interface DataClientInterface {
  getMarketState(): Promise<ApiResponse<MarketStateData>>;
  getMarketExtremes(): Promise<ApiResponse<MarketExtremesData>>;
  getMarketBreadth(): Promise<ApiResponse<MarketBreadthData>>;
  getSectorLeadership(): Promise<ApiResponse<SectorLeadershipData>>;
  getPortfolioSummary(): Promise<ApiResponse<PortfolioSummaryData>>;
  getSignals(): Promise<ApiResponse<SignalsData>>;
  getCapitalRotation(): Promise<ApiResponse<CapitalRotationData>>;
  getPortfolioSellSide(): Promise<ApiResponse<SellSideData>>;
  getStocksList(): Promise<ApiResponse<StockListItem[]>>;
  getStockDetail(symbol: string): Promise<ApiResponse<StockDetailData>>;
  getSharedBrainAnalysis(symbol: string): Promise<ApiResponse<SharedBrainAnalysisData>>;
  getPaperTrading(): Promise<ApiResponse<PaperTradingData>>;
  getPerformance(): Promise<ApiResponse<PerformanceData>>;
  getPrimaryMarket(): Promise<ApiResponse<PrimaryMarketData>>;
  getNews(): Promise<ApiResponse<NewsData>>;
  getSystemHealth(): Promise<ApiResponse<SystemHealthData>>;
  getConnectionsState(): Promise<ApiResponse<ConnectionsState>>;
  validateConnection(
    providerId: string,
    credentials?: Record<string, string>
  ): Promise<ApiResponse<{ success: boolean; message: string; stageResults?: Partial<UpstoxValidationFlow> }>>;
  saveConnectionCredentials?(
    providerId: string,
    credentials: Record<string, string>
  ): Promise<ApiResponse<{ success: boolean; message: string }>>;
  testHistoricalData?(
    providerId: string
  ): Promise<ApiResponse<{ success: boolean; message: string; flow?: UpstoxValidationFlow }>>;
  clearConnectionCredentials?(
    providerId: string
  ): Promise<ApiResponse<{ success: boolean; message: string }>>;
  getDataCoverage?(): Promise<ApiResponse<DataCoverageData>>;
  getBrainReadiness?(): Promise<ApiResponse<BrainDataReadinessData>>;
  getRealBrainTrial?(): Promise<ApiResponse<RealBrainTrialData>>;
}
