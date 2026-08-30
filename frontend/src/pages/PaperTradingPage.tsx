import React, { useEffect, useState } from 'react';
import {
  CheckCircle2,
  Clock,
  Layers,
  Percent,
  Play,
  ShieldCheck,
  TrendingUp,
} from 'lucide-react';
import { useDataClient } from '../api/context';
import { useNavigation } from '../context/NavigationContext';
import { ApiResponse } from '../types/api';
import { PaperTradeItem, PaperTradingData } from '../types/paperTrading';
import { SectionHeader } from '../components/common/SectionHeader';
import { MetricCard } from '../components/common/MetricCard';
import { DataTable, Column } from '../components/common/DataTable';
import { ApiStateWrapper } from '../components/common/ApiStateWrapper';
import { formatINR, formatPercent, formatRatio } from '../utils/formatters';

export const PaperTradingPage: React.FC = () => {
  const { client, refreshTrigger } = useDataClient();
  const { navigateToStock } = useNavigation();

  const [paperRes, setPaperRes] = useState<ApiResponse<PaperTradingData> | null>(null);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState('ALL');

  useEffect(() => {
    let isMounted = true;
    const fetchPaper = async () => {
      setLoading(true);
      try {
        const res = await client.getPaperTrading();
        if (isMounted) setPaperRes(res);
      } catch (err) {
        console.error('Failed to load paper trading:', err);
      } finally {
        if (isMounted) setLoading(false);
      }
    };

    fetchPaper();
    return () => {
      isMounted = false;
    };
  }, [client, refreshTrigger]);

  const columns: Column<PaperTradeItem>[] = [
    {
      key: 'symbol',
      header: 'Symbol / Thesis',
      render: (item) => (
        <div>
          <div className="font-mono font-bold text-slate-900 dark:text-slate-100 hover:text-emerald-500">
            {item.symbol}
          </div>
          <div className="text-[11px] text-slate-400 truncate max-w-[150px] sm:max-w-xs">
            {item.thesis}
          </div>
        </div>
      ),
    },
    {
      key: 'status',
      header: 'Status',
      align: 'center',
      render: (item) => {
        const isOpen = item.status === 'OPEN';
        const isTarget = item.status === 'TARGET_REACHED';
        const isStopped = item.status === 'STOPPED_OUT';
        return (
          <span
            className={`text-[10px] font-bold px-2 py-0.5 rounded uppercase font-mono ${
              isOpen
                ? 'bg-sky-500/15 text-sky-700 dark:text-sky-300 border border-sky-500/30'
                : isTarget
                ? 'bg-emerald-500/15 text-emerald-700 dark:text-emerald-300 border border-emerald-500/30'
                : isStopped
                ? 'bg-rose-500/15 text-rose-700 dark:text-rose-400 border border-rose-500/30'
                : 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400'
            }`}
          >
            {item.status.replace('_', ' ')}
          </span>
        );
      },
    },
    {
      key: 'entryPrice',
      header: 'Entry & LTP',
      align: 'right',
      render: (item) => (
        <div className="font-mono">
          <div className="text-slate-900 dark:text-slate-100 font-semibold">{formatINR(item.currentPrice)}</div>
          <div className="text-[11px] text-slate-400">Entry: {formatINR(item.entryPrice)}</div>
        </div>
      ),
    },
    {
      key: 'stopLoss',
      header: 'Stop / Target',
      align: 'right',
      render: (item) => (
        <div className="font-mono text-[11px]">
          <div className="text-rose-600 dark:text-rose-400">SL: {formatINR(item.stopLoss)}</div>
          <div className="text-emerald-600 dark:text-emerald-400">T1: {formatINR(item.target1)}</div>
        </div>
      ),
    },
    {
      key: 'mfePct',
      header: 'MFE / MAE',
      align: 'right',
      render: (item) => (
        <div className="font-mono text-[11px]">
          <div className="text-emerald-600 dark:text-emerald-400">+{formatPercent(item.mfePct)}</div>
          <div className="text-rose-600 dark:text-rose-400">-{formatPercent(item.maePct)}</div>
        </div>
      ),
    },
    {
      key: 'rMultiple',
      header: 'R-Multiple',
      align: 'center',
      render: (item) => {
        const isPos = (item.rMultiple ?? 0) > 0;
        const isNeg = (item.rMultiple ?? 0) < 0;
        return (
          <span
            className={`font-mono font-bold text-xs ${
              isPos ? 'text-emerald-600 dark:text-emerald-400' : isNeg ? 'text-rose-600 dark:text-rose-400' : 'text-slate-500'
            }`}
          >
            {item.rMultiple !== null ? `${item.rMultiple > 0 ? '+' : ''}${item.rMultiple.toFixed(2)}R` : '—'}
          </span>
        );
      },
    },
    {
      key: 'unrealizedPnL',
      header: 'P&L',
      align: 'right',
      render: (item) => {
        const pnl = item.status === 'OPEN' ? item.unrealizedPnL : item.realizedPnL;
        const isPos = (pnl ?? 0) > 0;
        const isNeg = (pnl ?? 0) < 0;
        return (
          <div className="font-mono">
            <div className={`font-bold ${isPos ? 'text-emerald-600 dark:text-emerald-400' : isNeg ? 'text-rose-600 dark:text-rose-400' : 'text-slate-500'}`}>
              {formatINR(pnl, { showSign: true })}
            </div>
            <div className="text-[10px] text-slate-400">{item.status === 'OPEN' ? 'Unrealized' : 'Realized'}</div>
          </div>
        );
      },
    },
  ];

  return (
    <div id="paper-trading-page" className="space-y-6">
      <SectionHeader
        title="Forward Paper Trading Validation"
        subtitle="Live simulated trade tracking to validate backend signals, execution rules, and stop/target adherence"
        freshness={paperRes?.freshness}
        timestamp={paperRes?.timestamp}
      />

      <ApiStateWrapper<PaperTradingData>
        response={paperRes}
        isLoading={loading}
        skeletonType="table"
        skeletonRows={4}
      >
        {(data: PaperTradingData) => {
          const filteredTrades = data.trades.filter((t) => {
            if (statusFilter === 'ALL') return true;
            if (statusFilter === 'OPEN') return t.status === 'OPEN';
            if (statusFilter === 'CLOSED') return t.status !== 'OPEN';
            return true;
          });

          return (
            <div className="space-y-6">
              {/* Stats Bar */}
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                <MetricCard
                  id="paper-open-trades"
                  label="Active Trades"
                  value={data.openTradesCount ?? '—'}
                  subtext={`Closed Trades: ${data.closedTradesCount ?? '—'}`}
                />
                <MetricCard
                  id="paper-win-rate"
                  label="Simulated Win Rate"
                  value={formatPercent(data.winRatePct)}
                  subtext="Based on closed trades"
                />
                <MetricCard
                  id="paper-avg-r"
                  label="Average R-Multiple"
                  value={data.averageRMultiple !== null ? `${data.averageRMultiple > 0 ? '+' : ''}${data.averageRMultiple.toFixed(2)}R` : '—'}
                  subtext="Risk-adjusted return per trade"
                />
                <MetricCard
                  id="paper-strategy"
                  label="Validation Rule"
                  value="Systematic"
                  badge={<span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-600 dark:text-emerald-400">Strict SL</span>}
                  subtext="Deterministic rule enforcement"
                />
              </div>

              {/* Trades Table */}
              <div className="space-y-3">
                <div className="flex flex-col sm:flex-row items-center justify-between gap-3 p-3 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg">
                  <span className="text-xs font-bold uppercase tracking-wider text-slate-500">
                    Forward Simulation Log ({filteredTrades.length})
                  </span>

                  <div className="flex items-center gap-2">
                    <span className="text-xs text-slate-500">Filter:</span>
                    <select
                      value={statusFilter}
                      onChange={(e) => setStatusFilter(e.target.value)}
                      className="text-xs bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-md py-1.5 px-2 text-slate-900 dark:text-slate-100"
                    >
                      <option value="ALL">All Positions</option>
                      <option value="OPEN">Open Only</option>
                      <option value="CLOSED">Closed Only</option>
                    </select>
                  </div>
                </div>

                <DataTable
                  id="paper-trades-table"
                  columns={columns}
                  data={filteredTrades}
                  keyExtractor={(item) => item.id}
                  onRowClick={(item) => navigateToStock(item.symbol)}
                  emptyMessage="No paper trades currently matching the filter."
                />
              </div>
            </div>
          );
        }}
      </ApiStateWrapper>
    </div>
  );
};
