import React, { useEffect, useState } from 'react';
import { Filter, Layers, Search } from 'lucide-react';
import { useDataClient } from '../api/context';
import { useNavigation } from '../context/NavigationContext';
import { ApiResponse } from '../types/api';
import { StockListItem } from '../types/stock';
import { SectionHeader } from '../components/common/SectionHeader';
import { DataTable, Column } from '../components/common/DataTable';
import { ScoreBadge } from '../components/common/ScoreBadge';
import { ConfidenceBadge } from '../components/common/ConfidenceBadge';
import { ActionBadge } from '../components/common/ActionBadge';
import { RiskBadge } from '../components/common/RiskBadge';
import { ApiStateWrapper } from '../components/common/ApiStateWrapper';
import { formatCr, formatINR, formatPercent, formatScore } from '../utils/formatters';

export const StocksPage: React.FC = () => {
  const { client, refreshTrigger } = useDataClient();
  const { navigateToStock } = useNavigation();

  const [stocksRes, setStocksRes] = useState<ApiResponse<StockListItem[]> | null>(null);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [sectorFilter, setSectorFilter] = useState('ALL');
  const [actionFilter, setActionFilter] = useState('ALL');

  useEffect(() => {
    let isMounted = true;
    const fetchStocks = async () => {
      setLoading(true);
      try {
        const res = await client.getStocksList();
        if (isMounted) setStocksRes(res);
      } catch (err) {
        console.error('Failed to load stocks:', err);
      } finally {
        if (isMounted) setLoading(false);
      }
    };

    fetchStocks();
    return () => {
      isMounted = false;
    };
  }, [client, refreshTrigger]);

  const columns: Column<StockListItem>[] = [
    {
      key: 'symbol',
      header: 'Symbol & Company',
      render: (item) => (
        <div>
          <div className="font-mono font-bold text-slate-900 dark:text-slate-100 hover:text-emerald-500">
            {item.symbol}
          </div>
          <div className="text-[11px] text-slate-400 truncate max-w-[160px] sm:max-w-xs">
            {item.companyName}
          </div>
        </div>
      ),
    },
    {
      key: 'sector',
      header: 'Sector',
      render: (item) => <span className="text-slate-600 dark:text-slate-400">{item.sector}</span>,
    },
    {
      key: 'marketCapCr',
      header: 'Market Cap',
      align: 'right',
      render: (item) => (
        <span className="font-mono text-slate-700 dark:text-slate-300">
          {formatCr(item.marketCapCr)}
        </span>
      ),
    },
    {
      key: 'price',
      header: 'LTP & 1D Change',
      align: 'right',
      render: (item) => {
        const isPos = (item.changePct ?? 0) > 0;
        const isNeg = (item.changePct ?? 0) < 0;
        return (
          <div className="font-mono">
            <div className="font-semibold text-slate-900 dark:text-slate-100">{formatINR(item.price)}</div>
            <div className={`text-[11px] ${isPos ? 'text-emerald-600 dark:text-emerald-400' : isNeg ? 'text-rose-600 dark:text-rose-400' : 'text-slate-400'}`}>
              {formatPercent(item.changePct, { showSign: true })}
            </div>
          </div>
        );
      },
    },
    {
      key: 'decisionScore',
      header: 'Decision Score',
      align: 'center',
      render: (item) => (
        <div className="flex items-center justify-center gap-1.5">
          <ScoreBadge score={item.decisionScore} size="sm" />
          <ConfidenceBadge confidence={item.confidence} />
        </div>
      ),
    },
    {
      key: 'action',
      header: 'Action',
      align: 'center',
      render: (item) => <ActionBadge action={item.action} />,
    },
    {
      key: 'riskRating',
      header: 'Risk',
      align: 'center',
      render: (item) => <RiskBadge risk={item.riskRating} />,
    },
  ];

  return (
    <div id="stocks-page" className="space-y-6">
      <SectionHeader
        title="NSE Equity Universe Intelligence"
        subtitle="Search and explore distilled intelligence, Decision Scores, and risk ratings across equities"
        freshness={stocksRes?.freshness}
        timestamp={stocksRes?.timestamp}
      />

      <ApiStateWrapper<StockListItem[]>
        response={stocksRes}
        isLoading={loading}
        skeletonType="table"
        skeletonRows={6}
      >
        {(stocks: StockListItem[]) => {
          const sectors = Array.from(new Set(stocks.map((s) => s.sector)));
          const filtered = stocks.filter((s) => {
            const matchesQuery =
              s.symbol.toLowerCase().includes(searchQuery.toLowerCase()) ||
              s.companyName.toLowerCase().includes(searchQuery.toLowerCase());
            const matchesSector = sectorFilter === 'ALL' || s.sector === sectorFilter;
            const matchesAction = actionFilter === 'ALL' || s.action === actionFilter;
            return matchesQuery && matchesSector && matchesAction;
          });

          return (
            <div className="space-y-4">
              {/* Search & Filter bar */}
              <div className="flex flex-col sm:flex-row items-center justify-between gap-3 p-3 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg">
                <div className="relative w-full sm:w-80">
                  <Search className="w-4 h-4 text-slate-400 absolute left-3 top-2.5" />
                  <input
                    id="stocks-search-input"
                    type="text"
                    placeholder="Search stock symbol, company..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="w-full pl-9 pr-3 py-1.5 text-xs bg-slate-50 dark:bg-slate-800/80 border border-slate-200 dark:border-slate-700 rounded-md focus:outline-hidden focus:ring-1 focus:ring-emerald-500 text-slate-900 dark:text-slate-100 placeholder-slate-400"
                  />
                </div>

                <div className="flex flex-wrap items-center gap-3 w-full sm:w-auto">
                  <div className="flex items-center gap-1.5">
                    <span className="text-xs text-slate-500">Sector:</span>
                    <select
                      id="stocks-sector-filter"
                      value={sectorFilter}
                      onChange={(e) => setSectorFilter(e.target.value)}
                      className="text-xs bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-md py-1.5 px-2 text-slate-900 dark:text-slate-100"
                    >
                      <option value="ALL">All Sectors ({sectors.length})</option>
                      {sectors.map((s) => (
                        <option key={s} value={s}>
                          {s}
                        </option>
                      ))}
                    </select>
                  </div>

                  <div className="flex items-center gap-1.5">
                    <span className="text-xs text-slate-500">Action:</span>
                    <select
                      id="stocks-action-filter"
                      value={actionFilter}
                      onChange={(e) => setActionFilter(e.target.value)}
                      className="text-xs bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-md py-1.5 px-2 text-slate-900 dark:text-slate-100"
                    >
                      <option value="ALL">All Actions</option>
                      <option value="BUY">BUY</option>
                      <option value="ACCUMULATE">ACCUMULATE</option>
                      <option value="HOLD">HOLD</option>
                      <option value="TRIM">TRIM</option>
                      <option value="AVOID">AVOID</option>
                    </select>
                  </div>
                </div>
              </div>

              {/* Table */}
              <DataTable
                id="stocks-list-table"
                columns={columns}
                data={filtered}
                keyExtractor={(item) => item.symbol}
                onRowClick={(item) => navigateToStock(item.symbol)}
                emptyMessage="No stocks found matching search query."
              />
            </div>
          );
        }}
      </ApiStateWrapper>
    </div>
  );
};
