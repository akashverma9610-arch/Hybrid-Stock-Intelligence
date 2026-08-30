import React from 'react';
import { FlaskConical, ShieldAlert } from 'lucide-react';
import { ApiResponse } from '../../types/api';
import { ForwardPaperAggregate, SharedBrainAnalysisData } from '../../types/stock';
import { ApiStateWrapper } from '../common/ApiStateWrapper';

const display = (value: string | null) => value ?? '—';
const percentage = (value: string | null) => value === null ? '—' : `${(Number(value) * 100).toFixed(1)}%`;

const Aggregate: React.FC<{ value: ForwardPaperAggregate; title: string }> = ({ value, title }) => (
  <div className="rounded-lg border border-slate-200 dark:border-slate-800 p-4 space-y-3 text-xs">
    <div className="flex justify-between gap-3"><div className="font-bold text-slate-800 dark:text-slate-100">{title}</div><div className="font-mono text-slate-500">{value.evidenceSufficiency}</div></div>
    {value.evidenceSufficiency === 'NO_EVIDENCE' ? (
      <div className="text-slate-500">No forward-paper evidence is known at this as-of cutoff.</div>
    ) : (
      <>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3"><div><span className="text-slate-500">Studies</span><div className="font-mono">{value.sampleCount}</div></div><div><span className="text-slate-500">Completed</span><div className="font-mono">{value.completedCount}</div></div><div><span className="text-slate-500">Open / waiting</span><div className="font-mono">{value.openCount} / {value.waitingCount}</div></div><div><span className="text-slate-500">Ambiguous / blocked</span><div className="font-mono">{value.ambiguousCount} / {value.blockedCount}</div></div></div>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 border-t border-slate-100 dark:border-slate-800 pt-3"><div><span className="text-slate-500">Net expectancy</span><div className="font-mono font-semibold">{display(value.expectancyR)} R</div></div><div><span className="text-slate-500">Median MFE / MAE</span><div className="font-mono">{display(value.medianMfeR)} / {display(value.medianMaeR)} R</div></div><div><span className="text-slate-500">Win / target / stop</span><div className="font-mono">{percentage(value.winRate)} / {percentage(value.targetHitRate)} / {percentage(value.stopHitRate)}</div></div><div><span className="text-slate-500">Avg hold</span><div className="font-mono">{display(value.averageHoldingSessions)} sessions</div></div></div>
        <div className="text-slate-500">Scope: {value.cohortDefinition.join(' · ')} · Net R is headline realized performance; gross R remains preserved separately.</div>
      </>
    )}
    <div className="text-[10px] font-mono text-slate-400">Aggregate: {value.fingerprint} · Policy: {value.policyVersions.join(', ') || '—'} · Execution: {value.executionModelVersions.join(', ') || '—'}</div>
  </div>
);

/** Displays U18 outcome evidence only; no recommendation or policy action is derived. */
export const ForwardPerformanceIntelligencePanel: React.FC<{ response: ApiResponse<SharedBrainAnalysisData> | null; loading: boolean }> = ({ response, loading }) => (
  <section aria-label="Forward Performance Intelligence" className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-5 shadow-xs space-y-4">
    <div className="flex items-start gap-2"><FlaskConical className="w-4 h-4 text-sky-500 mt-0.5"/><div><div className="text-xs font-bold uppercase tracking-wider text-slate-500">Forward Performance Intelligence</div><p className="mt-1 text-xs text-slate-500">Descriptive outcomes from governed paper studies. Not a recommendation and never a policy change.</p></div></div>
    <ApiStateWrapper<SharedBrainAnalysisData> response={response} isLoading={loading} skeletonType="card" skeletonRows={2}>{value => <div className="space-y-3"><Aggregate title="Instrument paper history" value={value.forwardPerformanceIntelligence.instrumentHistory}/><Aggregate title="Relevant sector cohort" value={value.forwardPerformanceIntelligence.relevantCohortHistory}/>{value.forwardPerformanceIntelligence.warnings.length > 0 && <div className="rounded border border-amber-200 dark:border-amber-900/60 bg-amber-50 dark:bg-amber-950/20 p-3 text-xs text-amber-800 dark:text-amber-200 flex gap-2"><ShieldAlert className="w-4 h-4 shrink-0"/><div>{value.forwardPerformanceIntelligence.warnings.join(' · ')}</div></div>}</div>}</ApiStateWrapper>
  </section>
);
