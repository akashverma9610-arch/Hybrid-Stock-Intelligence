export interface NewsItem {
  id: string;
  timestamp: string | null;
  timeAgo: string | null;
  symbols: string[];
  sectors: string[];
  title: string;
  publisher: string;
  sourceQuality: 'TIER_1_EXCHANGE' | 'TIER_1_FINANCIAL' | 'REGULATORY' | 'MAINSTREAM_PRESS' | 'AGGREGATOR';
  eventCategory: 'EARNINGS' | 'CORPORATE_ACTION' | 'REGULATORY_POLICY' | 'MACRO' | 'ORDER_WIN' | 'MANAGEMENT_CHANGE' | 'GEOPOLITICAL';
  catalystContext: string;
  sentimentImpact: 'POSITIVE' | 'NEUTRAL' | 'NEGATIVE' | 'HIGH_VOLATILITY';
}

export interface NewsData {
  items: NewsItem[];
  totalCount: number | null;
  filterCategories: string[];
}
