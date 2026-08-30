import React, { useEffect, useState } from 'react';
import { Building2, Calendar, Sparkles } from 'lucide-react';
import { useDataClient } from '../api/context';
import { ApiResponse } from '../types/api';
import { PrimaryMarketItem, PrimaryMarketData } from '../types/primaryMarket';
import { SectionHeader } from '../components/common/SectionHeader';
import { DataTable, Column } from '../components/common/DataTable';
import { ApiStateWrapper } from '../components/common/ApiStateWrapper';
import { formatCr, formatINR, formatPercent, formatRatio } from '../utils/formatters';

export const PrimaryMarketPage: React.FC = () => {
  const { client, refreshTrigger } = useDataClient();
  const [ipoRes, setIpoRes] = useState<ApiResponse<PrimaryMarketData> | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let isMounted = true;
    const fetchIpo = async () => {
      setLoading(true);
      try {
        const res = await client.getPrimaryMarket();
        if (isMounted) setIpoRes(res);
      } catch (err) {
        console.error('Failed to load primary market:', err);
      } finally {
        if (isMounted) setLoading(false);
      }
    };

    fetchIpo();
    return () => {
      isMounted = false;
    };
  }, [client, refreshTrigger]);

  const columns: Column<PrimaryMarketItem>[] = [
    {
      key: 'issueName',
      header: 'Issue Name / Segment',
      render: (item) => (
        <div>
          <div className="font-bold text-slate-900 dark:text-slate-100">{item.issueName}</div>
          <div className="text-[11px] text-slate-400 flex items-center gap-1.5 font-mono">
            <span className="px-1.5 py-0.2 rounded bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300">
              {item.issueType.replace('_', ' ')}
            </span>
            <span>{item.sector}</span>
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
        const isUpcoming = item.status === 'UPCOMING';
        return (
          <span
            className={`text-[10px] font-bold px-2 py-0.5 rounded uppercase ${
              isOpen
                ? 'bg-emerald-500/15 text-emerald-700 dark:text-emerald-300 border border-emerald-500/30 animate-pulse'
                : isUpcoming
                ? 'bg-sky-500/15 text-sky-700 dark:text-sky-300 border border-sky-500/30'
                : 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400'
            }`}
          >
            {item.status}
          </span>
        );
      },
    },
    {
      key: 'priceBand',
      header: 'Price Band',
      align: 'right',
      render: (item) => (
        <span className="font-mono font-semibold text-slate-900 dark:text-slate-100">
          {item.priceBand ?? '—'}
        </span>
      ),
    },
    {
      key: 'issueSizeCr',
      header: 'Issue Size (Cr)',
      align: 'right',
      render: (item) => (
        <div className="font-mono">
          <div className="font-semibold text-slate-900 dark:text-slate-100">{formatCr(item.issueSizeCr)}</div>
          <div className="text-[11px] text-slate-400">Fresh: {formatCr(item.freshIssueCr)}</div>
        </div>
      ),
    },
    {
      key: 'overallSubscriptionTimes',
      header: 'Subscription (x)',
      align: 'center',
      render: (item) => (
        <div className="font-mono">
          <div className="font-bold text-slate-900 dark:text-slate-100">
            {formatRatio(item.overallSubscriptionTimes, 'x')}
          </div>
          {item.qibSubscriptionTimes && (
            <div className="text-[10px] text-slate-400">QIB: {item.qibSubscriptionTimes}x</div>
          )}
        </div>
      ),
    },
    {
      key: 'gmpEstimatedPremiumPct',
      header: 'Est. GMP Premium',
      align: 'right',
      render: (item) => (
        <span className="font-mono font-bold text-emerald-600 dark:text-emerald-400">
          {formatPercent(item.gmpEstimatedPremiumPct, { showSign: true })}
        </span>
      ),
    },
    {
      key: 'openDate',
      header: 'Bidding Dates',
      align: 'right',
      render: (item) => (
        <div className="text-[11px] font-mono text-slate-500">
          <div>Open: {item.openDate ?? '—'}</div>
          <div>Close: {item.closeDate ?? '—'}</div>
        </div>
      ),
    },
  ];

  return (
    <div id="primary-market-page" className="space-y-6">
      <SectionHeader
        title="Primary Market & IPO Pipeline"
        subtitle="Mainboard and SME IPO offerings, bidding windows, subscription levels, and GMP indicators"
        freshness={ipoRes?.freshness}
        timestamp={ipoRes?.timestamp}
      />

      <ApiStateWrapper<PrimaryMarketData>
        response={ipoRes}
        isLoading={loading}
        skeletonType="table"
        skeletonRows={4}
      >
        {(data: PrimaryMarketData) => {
          const allIssues = [...(data.openIssues || []), ...(data.upcomingIssues || []), ...(data.recentlyListed || [])];
          return (
            <div className="space-y-4">
              <DataTable
                id="ipo-table"
                columns={columns}
                data={allIssues}
                keyExtractor={(item) => item.id}
                emptyMessage="No active or upcoming IPO offerings found in pipeline."
              />
            </div>
          );
        }}
      </ApiStateWrapper>
    </div>
  );
};
