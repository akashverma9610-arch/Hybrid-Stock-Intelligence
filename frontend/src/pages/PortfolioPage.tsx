import React, { useEffect, useState } from 'react';
import { Filter, Search } from 'lucide-react';
import { useDataClient } from '../api/context';
import { useNavigation } from '../context/NavigationContext';
import { ApiResponse } from '../types/api';
import { HoldingItem, PortfolioSummaryData } from '../types/portfolio';
import { SellSideData } from '../types/sellSide';
import { SectionHeader } from '../components/common/SectionHeader';
import { MetricCard } from '../components/common/MetricCard';
import { ScoreBadge } from '../components/common/ScoreBadge';
import { ConfidenceBadge } from '../components/common/ConfidenceBadge';
import { RiskBadge } from '../components/common/RiskBadge';
import { DataTable, Column } from '../components/common/DataTable';
import { ApiStateWrapper } from '../components/common/ApiStateWrapper';
import { formatINR, formatPercent } from '../utils/formatters';

export const PortfolioPage: React.FC = () => {
  const { client, refreshTrigger } = useDataClient();
  const { navigateToStock } = useNavigation();

  const [portfolioRes, setPortfolioRes] = useState<ApiResponse<PortfolioSummaryData> | null>(null);
  const [sellSideRes, setSellSideRes] = useState<ApiResponse<SellSideData> | null>(null);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [sectorFilter, setSectorFilter] = useState('ALL');

  useEffect(() => {
    let isMounted = true;
    const fetchPortfolio = async () => {
      setLoading(true);
      try {
        const [res, sellSide] = await Promise.all([client.getPortfolioSummary(), client.getPortfolioSellSide()]);
        if (isMounted) { setPortfolioRes(res); setSellSideRes(sellSide); }
      } catch (err) {
        console.error('Failed to load portfolio:', err);
      } finally {
        if (isMounted) setLoading(false);
      }
    };

    fetchPortfolio();
    return () => {
      isMounted = false;
    };
  }, [client, refreshTrigger]);

  const columns: Column<HoldingItem>[] = [
    {
      key: 'symbol',
      header: 'Symbol / Company',
      render: (item) => (
        <div>
          <div className="font-mono font-bold text-slate-900 dark:text-slate-100 hover:text-emerald-500">
            {item.symbol}
          </div>
          <div className="text-[11px] text-slate-400 truncate max-w-[150px] sm:max-w-xs">
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
      key: 'quantity',
      header: 'Qty & Avg Price',
      align: 'right',
      render: (item) => (
        <div className="font-mono">
          <div>{item.quantity ?? '—'}</div>
          <div className="text-[11px] text-slate-400">{formatINR(item.avgPrice)}</div>
        </div>
      ),
    },
    {
      key: 'currentPrice',
      header: 'LTP & Value',
      align: 'right',
      render: (item) => (
        <div className="font-mono">
          <div className="font-semibold text-slate-900 dark:text-slate-100">{formatINR(item.currentPrice)}</div>
          <div className="text-[11px] text-slate-500">{formatINR(item.currentValue)}</div>
        </div>
      ),
    },
    {
      key: 'unrealizedPnL',
      header: 'Unrealized P&L',
      align: 'right',
      render: (item) => {
        const isPos = (item.unrealizedPnL ?? 0) > 0;
        const isNeg = (item.unrealizedPnL ?? 0) < 0;
        return (
          <div className="font-mono">
            <div className={`font-bold ${isPos ? 'text-emerald-600 dark:text-emerald-400' : isNeg ? 'text-rose-600 dark:text-rose-400' : 'text-slate-500'}`}>
              {formatINR(item.unrealizedPnL, { showSign: true })}
            </div>
            <div className={`text-[11px] ${isPos ? 'text-emerald-600 dark:text-emerald-400' : isNeg ? 'text-rose-600 dark:text-rose-400' : 'text-slate-400'}`}>
              {formatPercent(item.unrealizedPnLPct, { showSign: true })}
            </div>
          </div>
        );
      },
    },
    {
      key: 'weightPct',
      header: 'Weight',
      align: 'right',
      render: (item) => (
        <span className="font-mono text-slate-700 dark:text-slate-300">
          {formatPercent(item.weightPct)}
        </span>
      ),
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
      key: 'riskContribution',
      header: 'Risk Heat',
      align: 'center',
      render: (item) => <RiskBadge risk={item.riskContribution} />,
    },
  ];

  return (
    <div id="portfolio-page" className="space-y-6">
      <SectionHeader
        title="Portfolio Capital & Holdings"
        subtitle="Read-only view of equity allocation, position health, and distilled Decision Scores"
        freshness={portfolioRes?.freshness}
        timestamp={portfolioRes?.timestamp}
      />

      <div className="rounded-lg border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900">
        <div className="flex items-center justify-between gap-3">
          <div><div className="text-sm font-semibold text-slate-900 dark:text-slate-100">Sell-side intelligence</div><div className="text-xs text-slate-500">Read-only policy output. TRIM: NOT AUTHORIZED IN V1.</div></div>
          <span className="font-mono text-xs text-slate-500">{sellSideRes?.data?.status ?? 'UNAVAILABLE'}</span>
        </div>
        {sellSideRes?.data?.decisions?.map((item) => <div key={item.holdingId} className="mt-3 text-xs text-slate-600 dark:text-slate-300">{item.holdingId}: <span className="font-semibold">{item.action}</span> · thesis {item.thesisState} · {item.evidenceFreshness}</div>)}
      </div>

      <ApiStateWrapper<PortfolioSummaryData>
        response={portfolioRes}
        isLoading={loading}
        skeletonType="table"
        skeletonRows={5}
      >
        {(portfolio: PortfolioSummaryData) => {
          const sectors = Array.from(new Set(portfolio.holdings.map((h) => h.sector)));
          const filteredHoldings = portfolio.holdings.filter((h) => {
            const matchesQuery =
              h.symbol.toLowerCase().includes(searchQuery.toLowerCase()) ||
              h.companyName.toLowerCase().includes(searchQuery.toLowerCase());
            const matchesSector = sectorFilter === 'ALL' || h.sector === sectorFilter;
            return matchesQuery && matchesSector;
          });

          return (
            <div className="space-y-6">
              {/* Portfolio Stats Cards */}
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                <MetricCard
                  id="port-invested"
                  label="Invested Value"
                  value={portfolio.investedValue !== null ? formatINR(portfolio.investedValue) : '—'}
                  subtext={portfolio.cashAvailable !== null ? `Cash Reserve: ${formatINR(portfolio.cashAvailable)}` : portfolio.cashStatus === 'UNKNOWN' ? 'Cash: Unknown' : undefined}
                />
                <MetricCard
                  id="port-current"
                  label="Current Value"
                  value={portfolio.currentValue !== null ? formatINR(portfolio.currentValue) : '—'}
                  subtext={`Holdings Count: ${portfolio.holdingsCount ?? portfolio.holdings.length}`}
                />
                <MetricCard
                  id="port-total-pnl"
                  label="Total Unrealized P&L"
                  value={portfolio.totalPnL !== null ? formatINR(portfolio.totalPnL, { showSign: true }) : '—'}
                  change={portfolio.totalPnLPct}
                  subtext="Net portfolio gain"
                />
                <MetricCard
                  id="port-risk"
                  label="Portfolio Risk Level"
                  value={portfolio.portfolioRiskLevel}
                  badge={<ScoreBadge score={portfolio.portfolioHeatScore} size="sm" showLabel />}
                  subtext={`Deployed Capital: ${formatPercent(portfolio.capitalDeployedPct)}`}
                />
              </div>

              {/* Filter & Search Bar */}
              <div className="flex flex-col sm:flex-row items-center justify-between gap-3 p-3 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg">
                <div className="relative w-full sm:w-72">
                  <Search className="w-4 h-4 text-slate-400 absolute left-3 top-2.5" />
                  <input
                    id="portfolio-search-input"
                    type="text"
                    placeholder="Search by symbol or name..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="w-full pl-9 pr-3 py-1.5 text-xs bg-slate-50 dark:bg-slate-800/80 border border-slate-200 dark:border-slate-700 rounded-md focus:outline-hidden focus:ring-1 focus:ring-emerald-500 text-slate-900 dark:text-slate-100 placeholder-slate-400"
                  />
                </div>

                <div className="flex items-center gap-2 w-full sm:w-auto">
                  <Filter className="w-3.5 h-3.5 text-slate-400" />
                  <span className="text-xs text-slate-500">Sector:</span>
                  <select
                    id="portfolio-sector-filter"
                    value={sectorFilter}
                    onChange={(e) => setSectorFilter(e.target.value)}
                    className="text-xs bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-md py-1.5 px-2 text-slate-900 dark:text-slate-100"
                  >
                    <option value="ALL">All Sectors ({sectors.length})</option>
                    {sectors.map((sec) => (
                      <option key={sec} value={sec}>
                        {sec}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              {/* Holdings Table */}
              <div className="space-y-2">
                <div className="flex justify-between items-center px-1">
                  <span className="text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                    Individual Holdings ({filteredHoldings.length})
                  </span>
                  <span className="text-xs text-slate-400">
                    Click row to view distilled stock intelligence
                  </span>
                </div>

                <DataTable
                  id="portfolio-holdings-table"
                  columns={columns}
                  data={filteredHoldings}
                  keyExtractor={(item) => item.symbol}
                  onRowClick={(item) => navigateToStock(item.symbol)}
                  emptyMessage="No holdings match the active search or sector filter."
                />
              </div>
            </div>
          );
        }}
      </ApiStateWrapper>
    </div>
  );
};
