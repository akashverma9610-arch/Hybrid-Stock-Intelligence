import React, { useEffect, useState } from 'react';
import { Filter, Search } from 'lucide-react';
import { useDataClient } from '../api/context';
import { useNavigation } from '../context/NavigationContext';
import { ApiResponse } from '../types/api';
import { SignalItem, SignalsData } from '../types/signals';
import { SectionHeader } from '../components/common/SectionHeader';
import { ScoreBadge } from '../components/common/ScoreBadge';
import { ConfidenceBadge } from '../components/common/ConfidenceBadge';
import { ActionBadge } from '../components/common/ActionBadge';
import { DataTable, Column } from '../components/common/DataTable';
import { ApiStateWrapper } from '../components/common/ApiStateWrapper';
import { formatINR, formatRatio } from '../utils/formatters';

export const SignalsPage: React.FC = () => {
  const { client, refreshTrigger } = useDataClient();
  const { navigateToStock } = useNavigation();

  const [signalsRes, setSignalsRes] = useState<ApiResponse<SignalsData> | null>(null);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [actionFilter, setActionFilter] = useState('ALL');

  useEffect(() => {
    let isMounted = true;
    const fetchSignals = async () => {
      setLoading(true);
      try {
        const res = await client.getSignals();
        if (isMounted) setSignalsRes(res);
      } catch (err) {
        console.error('Failed to load signals:', err);
      } finally {
        if (isMounted) setLoading(false);
      }
    };

    fetchSignals();
    return () => {
      isMounted = false;
    };
  }, [client, refreshTrigger]);

  const columns: Column<SignalItem>[] = [
    {
      key: 'symbol',
      header: 'Symbol / Sector',
      render: (item) => (
        <div>
          <div className="font-mono font-bold text-slate-900 dark:text-slate-100 hover:text-emerald-500">
            {item.symbol}
          </div>
          <div className="text-[11px] text-slate-400">{item.sector}</div>
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
      key: 'score',
      header: 'Decision Score',
      align: 'center',
      render: (item) => (
        <div className="flex items-center justify-center gap-1.5">
          <ScoreBadge score={item.score} size="sm" />
          <ConfidenceBadge confidence={item.confidence} />
        </div>
      ),
    },
    {
      key: 'signalState',
      header: 'State',
      align: 'center',
      render: (item) => (
        <span className="text-[11px] font-mono font-semibold px-2 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300">
          {item.signalState}
        </span>
      ),
    },
    {
      key: 'entryPrice',
      header: 'Entry Level',
      align: 'right',
      render: (item) => (
        <span className="font-mono font-semibold text-slate-900 dark:text-slate-100">
          {formatINR(item.entryPrice)}
        </span>
      ),
    },
    {
      key: 'stopLoss',
      header: 'Stop Loss',
      align: 'right',
      render: (item) => (
        <span className="font-mono text-rose-600 dark:text-rose-400 font-semibold">
          {formatINR(item.stopLoss)}
        </span>
      ),
    },
    {
      key: 'target1',
      header: 'Targets',
      align: 'right',
      render: (item) => (
        <div className="font-mono text-emerald-600 dark:text-emerald-400 font-semibold">
          <div>T1: {formatINR(item.target1)}</div>
          {item.target2 && <div className="text-[11px] text-emerald-700 dark:text-emerald-500">T2: {formatINR(item.target2)}</div>}
        </div>
      ),
    },
    {
      key: 'riskRewardRatio',
      header: 'R:R',
      align: 'center',
      render: (item) => (
        <span className="font-mono font-bold text-slate-800 dark:text-slate-200">
          {formatRatio(item.riskRewardRatio, '')}
        </span>
      ),
    },
    {
      key: 'timestamp',
      header: 'Assessed',
      align: 'right',
      render: (item) => <span className="text-slate-500 text-[11px]">{item.timestamp}</span>,
    },
  ];

  return (
    <div id="signals-page" className="space-y-6">
      <SectionHeader
        title="Actionable Investment Signals"
        subtitle="Backend-generated signals, execution stops, targets, and distilled rationales (Read-Only)"
        freshness={signalsRes?.freshness}
        timestamp={signalsRes?.timestamp}
      />

      <ApiStateWrapper<SignalsData>
        response={signalsRes}
        isLoading={loading}
        skeletonType="table"
        skeletonRows={5}
      >
        {(signals: SignalsData) => {
          const filtered = signals.activeSignals.filter((s) => {
            const matchesQuery =
              s.symbol.toLowerCase().includes(searchQuery.toLowerCase()) ||
              s.sector.toLowerCase().includes(searchQuery.toLowerCase());
            const matchesAction = actionFilter === 'ALL' || s.action === actionFilter;
            return matchesQuery && matchesAction;
          });

          return (
            <div className="space-y-4">
              {/* Filter controls */}
              <div className="flex flex-col sm:flex-row items-center justify-between gap-3 p-3 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg">
                <div className="relative w-full sm:w-80">
                  <Search className="w-4 h-4 text-slate-400 absolute left-3 top-2.5" />
                  <input
                    id="signals-search-input"
                    type="text"
                    placeholder="Search signals by symbol or sector..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="w-full pl-9 pr-3 py-1.5 text-xs bg-slate-50 dark:bg-slate-800/80 border border-slate-200 dark:border-slate-700 rounded-md focus:outline-hidden focus:ring-1 focus:ring-emerald-500 text-slate-900 dark:text-slate-100 placeholder-slate-400"
                  />
                </div>

                <div className="flex items-center gap-2 w-full sm:w-auto">
                  <Filter className="w-3.5 h-3.5 text-slate-400" />
                  <span className="text-xs text-slate-500">Action:</span>
                  <select
                    id="signals-action-filter"
                    value={actionFilter}
                    onChange={(e) => setActionFilter(e.target.value)}
                    className="text-xs bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-md py-1.5 px-2 text-slate-900 dark:text-slate-100"
                  >
                    <option value="ALL">All Actions ({signals.activeSignals.length})</option>
                    <option value="BUY">BUY</option>
                    <option value="ACCUMULATE">ACCUMULATE</option>
                    <option value="HOLD">HOLD</option>
                    <option value="TRIM">TRIM</option>
                  </select>
                </div>
              </div>

              {/* Signals Table */}
              <DataTable
                id="signals-table"
                columns={columns}
                data={filtered}
                keyExtractor={(item) => item.id}
                onRowClick={(item) => navigateToStock(item.symbol)}
                emptyMessage="No active signals matching search criteria."
              />
            </div>
          );
        }}
      </ApiStateWrapper>
    </div>
  );
};
