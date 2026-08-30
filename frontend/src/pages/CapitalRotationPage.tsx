import React, { useEffect, useState } from 'react';
import { ArrowLeftRight, ShieldAlert } from 'lucide-react';
import { useDataClient } from '../api/context';
import { ApiResponse } from '../types/api';
import { CapitalRotationData } from '../types/rotation';
import { SectionHeader } from '../components/common/SectionHeader';
import { ApiStateWrapper } from '../components/common/ApiStateWrapper';

/** Displays only the backend's published, immutable rotation comparison. */
export const CapitalRotationPage: React.FC = () => {
  const { client, refreshTrigger } = useDataClient();
  const [response, setResponse] = useState<ApiResponse<CapitalRotationData> | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let mounted = true;
    const load = async () => {
      setLoading(true);
      const result = await client.getCapitalRotation();
      if (mounted) {
        setResponse(result);
        setLoading(false);
      }
    };
    load();
    return () => { mounted = false; };
  }, [client, refreshTrigger]);

  return <div id="capital-rotation-page" className="space-y-6">
    <SectionHeader
      title="Capital Rotation Analysis"
      subtitle="Read-only published comparison of existing holdings and governed candidates"
      freshness={response?.freshness}
      timestamp={response?.timestamp}
    />
    <section className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-5 shadow-xs space-y-4">
      <div className="flex gap-2 text-xs text-slate-500">
        <ArrowLeftRight className="w-4 h-4 text-violet-500 shrink-0" />
        <span>Rotation is analytical only. This view creates no order, capital movement, or new threshold.</span>
      </div>
      <ApiStateWrapper<CapitalRotationData>
        response={response}
        isLoading={loading}
        skeletonType="card"
        skeletonRows={3}
        emptyTitle="No published rotation evaluation"
        emptyDescription="No current holding/candidate comparison is available."
      >
        {(value) => <div className="space-y-4">
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
            <Metric label="Status" value={value.overallStatus} />
            <Metric label="As-of" value={value.dataAsOf ?? '—'} mono />
            <Metric label="Holdings" value={value.holdingCount ?? '—'} mono />
            <Metric label="Portfolio heat" value={value.portfolioHeat ?? '—'} mono />
          </div>
          {value.opportunities.length === 0 ? (
            <div className="rounded border border-slate-200 dark:border-slate-800 p-3 text-xs text-slate-500">
              {value.message ?? 'No eligible rotation comparison is currently available.'}
            </div>
          ) : value.opportunities.map((item) => (
            <div key={`${item.currentHoldingSymbol ?? 'cash'}:${item.candidateSymbol}`} className="rounded border border-slate-200 dark:border-slate-800 p-4 text-xs space-y-3">
              <div className="flex justify-between gap-3"><span className="font-mono">{item.currentHoldingSymbol ?? 'CASH'} → {item.candidateSymbol}</span><span className="font-bold">{item.recommendedAction}</span></div>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                <Metric label="Score advantage" value={item.scoreAdvantage ?? '—'} mono />
                <Metric label="Candidate R:R" value={item.candidateRiskReward ?? '—'} mono />
                <Metric label="Eligibility" value={item.executionEligibility} />
                <Metric label="Sector context" value={item.sectorContext ?? '—'} />
              </div>
              <p className="text-slate-600 dark:text-slate-400">{item.rationale}</p>
              {item.publicGateSummary.length > 0 && <p className="text-slate-500">{item.publicGateSummary.join(' · ')}</p>}
            </div>
          ))}
          {(value.warnings.length > 0 || value.message) && <div className="rounded border border-amber-200 dark:border-amber-900/60 bg-amber-50 dark:bg-amber-950/20 p-3 text-xs text-amber-800 dark:text-amber-200 flex gap-2"><ShieldAlert className="w-4 h-4 shrink-0" /><span>{[...value.warnings, value.message].filter(Boolean).join(' · ')}</span></div>}
        </div>}
      </ApiStateWrapper>
    </section>
  </div>;
};

const Metric: React.FC<{ label: string; value: string | number; mono?: boolean }> = ({ label, value, mono }) => (
  <div><span className="text-slate-500">{label}</span><div className={`${mono ? 'font-mono' : 'font-semibold'} mt-0.5`}>{value}</div></div>
);
