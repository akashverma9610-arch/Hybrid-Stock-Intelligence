import { ApiResponse } from '../types/api';
import { MarketBreadthData, MarketExtremesData, MarketStateData, SectorLeadershipData } from '../types/market';
import { PortfolioSummaryData } from '../types/portfolio';
import { SignalsData } from '../types/signals';
import { CapitalRotationData } from '../types/rotation';
import { SharedBrainAnalysisData, StockDetailData, StockListItem } from '../types/stock';
import { PaperTradingData } from '../types/paperTrading';
import { PerformanceData } from '../types/performance';
import { PrimaryMarketData } from '../types/primaryMarket';
import { NewsData } from '../types/news';
import { SystemHealthData } from '../types/systemHealth';
import { ConnectionsState } from '../types/connections';
import { DataClientInterface } from './clientInterface';
import {
  mockCapitalRotation,
  mockConnectionsState,
  mockMarketBreadth,
  mockMarketExtremes,
  mockMarketState,
  mockNews,
  mockPaperTrading,
  mockPerformance,
  mockPortfolioSummary,
  mockPrimaryMarket,
  mockSectorLeadership,
  mockSignals,
  mockStockDetail,
  mockStocksList,
  mockSystemHealth,
} from '../mocks/mockData';

const SIMULATED_LATENCY_MS = 250;

function delayed<T>(data: ApiResponse<T>): Promise<ApiResponse<T>> {
  return new Promise((resolve) => {
    setTimeout(() => {
      resolve({
        ...data,
        timestamp: new Date().toISOString(),
      });
    }, SIMULATED_LATENCY_MS);
  });
}

export class MockDataClient implements DataClientInterface {
  async getMarketState(): Promise<ApiResponse<MarketStateData>> {
    return delayed(mockMarketState);
  }

  async getMarketExtremes(): Promise<ApiResponse<MarketExtremesData>> {
    return delayed(mockMarketExtremes);
  }

  async getMarketBreadth(): Promise<ApiResponse<MarketBreadthData>> {
    return delayed(mockMarketBreadth);
  }

  async getSectorLeadership(): Promise<ApiResponse<SectorLeadershipData>> {
    return delayed(mockSectorLeadership);
  }

  async getPortfolioSummary(): Promise<ApiResponse<PortfolioSummaryData>> {
    return delayed(mockPortfolioSummary);
  }

  async getSignals(): Promise<ApiResponse<SignalsData>> {
    return delayed(mockSignals);
  }

  async getCapitalRotation(): Promise<ApiResponse<CapitalRotationData>> {
    return delayed(mockCapitalRotation);
  }

  async getStocksList(): Promise<ApiResponse<StockListItem[]>> {
    return delayed({
      status: 'READY',
      freshness: 'LIVE',
      timestamp: new Date().toISOString(),
      data: mockStocksList,
    });
  }

  async getStockDetail(symbol: string): Promise<ApiResponse<StockDetailData>> {
    const stock = mockStockDetail[symbol.toUpperCase()] || {
      ...mockStockDetail['M&M'],
      symbol: symbol.toUpperCase(),
      companyName: `${symbol.toUpperCase()} Enterprise Ltd`,
    };
    return delayed({
      status: 'READY',
      freshness: 'LIVE',
      timestamp: new Date().toISOString(),
      data: stock,
    });
  }

  async getSharedBrainAnalysis(): Promise<ApiResponse<SharedBrainAnalysisData>> {
    return delayed({
      status: 'UNAVAILABLE', freshness: 'UNKNOWN', timestamp: new Date().toISOString(), data: null,
      message: 'Governed Shared Brain financial intelligence is unavailable in mock mode.',
    });
  }

  async getPaperTrading(): Promise<ApiResponse<PaperTradingData>> {
    return delayed(mockPaperTrading);
  }

  async getPerformance(): Promise<ApiResponse<PerformanceData>> {
    return delayed(mockPerformance);
  }

  async getPrimaryMarket(): Promise<ApiResponse<PrimaryMarketData>> {
    return delayed(mockPrimaryMarket);
  }

  async getNews(): Promise<ApiResponse<NewsData>> {
    return delayed(mockNews);
  }

  async getSystemHealth(): Promise<ApiResponse<SystemHealthData>> {
    return delayed(mockSystemHealth);
  }

  async getConnectionsState(): Promise<ApiResponse<ConnectionsState>> {
    return delayed(mockConnectionsState);
  }

  async validateConnection(
    providerId: string,
    credentials?: Record<string, string>
  ): Promise<ApiResponse<{ success: boolean; message: string; stageResults?: any }>> {
    await new Promise((resolve) => setTimeout(resolve, 600));
    return {
      status: 'READY',
      freshness: 'LIVE',
      timestamp: new Date().toISOString(),
      data: {
        success: true,
        message: `Provider ${providerId} validated successfully against mock harness (no secrets stored).`,
        stageResults: {
          credentials: 'VALIDATED',
          instrumentResolution: 'VALIDATED',
          historicalAccess: 'VALIDATED',
          normalization: 'VALIDATED',
          persistence: 'VALIDATED',
          lastTestedTimestamp: new Date().toLocaleTimeString('en-IN') + ' IST',
        },
      },
    };
  }

  async saveConnectionCredentials(
    providerId: string,
    credentials: Record<string, string>
  ): Promise<ApiResponse<{ success: boolean; message: string }>> {
    await new Promise((resolve) => setTimeout(resolve, 400));
    return {
      status: 'READY',
      freshness: 'LIVE',
      timestamp: new Date().toISOString(),
      data: {
        success: true,
        message: `Credentials for ${providerId} saved and encrypted on mock backend session.`,
      },
    };
  }

  async testHistoricalData(
    providerId: string
  ): Promise<ApiResponse<{ success: boolean; message: string; flow?: any }>> {
    await new Promise((resolve) => setTimeout(resolve, 800));
    return {
      status: 'READY',
      freshness: 'LIVE',
      timestamp: new Date().toISOString(),
      data: {
        success: true,
        message: `Historical OHLCV pipeline test passed for ${providerId}. 10-year candle resolution operational.`,
        flow: {
          credentials: 'VALIDATED',
          instrumentResolution: 'VALIDATED',
          historicalAccess: 'VALIDATED',
          normalization: 'VALIDATED',
          persistence: 'VALIDATED',
          lastTestedTimestamp: new Date().toLocaleTimeString('en-IN') + ' IST',
        },
      },
    };
  }

  async clearConnectionCredentials(
    providerId: string
  ): Promise<ApiResponse<{ success: boolean; message: string }>> {
    await new Promise((resolve) => setTimeout(resolve, 300));
    return {
      status: 'READY',
      freshness: 'LIVE',
      timestamp: new Date().toISOString(),
      data: {
        success: true,
        message: `Credentials for ${providerId} purged from backend session.`,
      },
    };
  }

  async getDataCoverage(): Promise<ApiResponse<any>> {
    return delayed({
      status: 'READY',
      freshness: 'LIVE',
      timestamp: new Date().toISOString(),
      data: mockConnectionsState.data?.dataCoverage,
    });
  }

  async getBrainReadiness(): Promise<ApiResponse<any>> {
    return delayed({
      status: 'READY',
      freshness: 'LIVE',
      timestamp: new Date().toISOString(),
      data: mockConnectionsState.data?.brainReadiness,
    });
  }

  async getRealBrainTrial(): Promise<ApiResponse<any>> {
    return delayed({
      status: 'READY',
      freshness: 'LIVE',
      timestamp: new Date().toISOString(),
      data: mockConnectionsState.data?.realBrainTrial,
    });
  }
}
