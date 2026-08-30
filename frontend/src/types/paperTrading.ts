export interface PaperTradeItem {
  id: string;
  symbol: string;
  entryDate: string | null;
  entryPrice: number | null;
  currentPrice: number | null;
  quantity: number | null;
  stopLoss: number | null;
  target1: number | null;
  target2: number | null;
  status: 'OPEN' | 'CLOSED' | 'STOPPED_OUT' | 'TARGET_REACHED' | 'INVALIDATED';
  mfePct: number | null; // Maximum Favorable Excursion
  maePct: number | null; // Maximum Adverse Excursion
  exitPrice: number | null;
  exitDate: string | null;
  rMultiple: number | null; // e.g. +2.4R
  realizedPnL: number | null;
  unrealizedPnL: number | null;
  thesis: string;
  invalidationCriteria: string;
}

export interface PaperTradingData {
  openTradesCount: number | null;
  closedTradesCount: number | null;
  winRatePct: number | null;
  averageRMultiple: number | null;
  trades: PaperTradeItem[];
}
