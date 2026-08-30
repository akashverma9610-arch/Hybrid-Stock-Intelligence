import React from 'react';
import { Brain, ShieldAlert } from 'lucide-react';
import { ApiResponse } from '../../types/api';
import { SharedBrainAnalysisData } from '../../types/stock';
import { ApiStateWrapper } from '../common/ApiStateWrapper';

/** Displays backend-projected facts only; it performs no financial inference. */
export const FinancialIntelligencePanel: React.FC<{
  response: ApiResponse<SharedBrainAnalysisData> | null;
  loading: boolean;
}> = ({ response, loading }) => (
  <section aria-label="Financial Intelligence" className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-5 shadow-xs space-y-4">
    <div className="flex items-start justify-between gap-4">
      <div>
        <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-slate-500">
          <Brain className="w-4 h-4 text-violet-500" />
          <span>Financial Intelligence</span>
        </div>
        <p className="mt-1 text-xs text-slate-500">Governed factual trajectories and metric-local directionality. This is not a recommendation.</p>
      </div>
    </div>
    <ApiStateWrapper<SharedBrainAnalysisData> response={response} isLoading={loading} skeletonType="card" skeletonRows={2}>
      {(value) => (
        <div className="space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs">
            <div><span className="text-slate-500">As-of</span><div className="font-mono mt-0.5">{value.asOf}</div></div>
            <div><span className="text-slate-500">Evidence</span><div className="font-semibold mt-0.5">{value.evidenceStatus}</div></div>
            <div><span className="text-slate-500">Materiality</span><div className="font-semibold mt-0.5">Calibration required</div></div>
          </div>
          {value.financialSemantics.length === 0 ? (
            <div className="rounded border border-slate-200 dark:border-slate-800 p-3 text-xs text-slate-500">No governed comparable financial trajectories available at this cutoff.</div>
          ) : (
            <div className="overflow-x-auto"><table className="w-full min-w-[760px] text-left text-xs"><thead className="text-slate-500 border-b"><tr><th className="py-2">Metric</th><th>Previous</th><th>Current</th><th>Factual change</th><th>Directionality</th><th>Materiality</th></tr></thead><tbody>{value.financialSemantics.map((item) => (
              <tr key={item.trajectoryFingerprint} className="border-b border-slate-100 dark:border-slate-800 align-top"><td className="py-3 font-semibold">{item.metric}<div className="font-normal text-slate-500 mt-0.5">{item.trajectoryBasis}</div></td><td className="py-3 font-mono">{item.previousPeriodLabel ?? '—'}<div>{item.previousValue ?? '—'}</div></td><td className="py-3 font-mono">{item.currentPeriodLabel ?? '—'}<div>{item.currentValue ?? '—'}</div></td><td className="py-3 font-mono">{item.absoluteDelta ?? '—'}<div className="font-sans text-slate-500">{item.factualDisplayPhrase ?? '—'}</div></td><td className="py-3 font-semibold">{item.directionalityOrientation ?? 'UNAVAILABLE'}<div className="font-normal text-slate-500">{item.directionalityRationaleCode ?? '—'}</div></td><td className="py-3">{item.materialityGovernanceState}</td></tr>
            ))}</tbody></table></div>
          )}
          {value.blockers.length > 0 && <div className="rounded border border-amber-200 dark:border-amber-900/60 bg-amber-50 dark:bg-amber-950/20 p-3 text-xs text-amber-800 dark:text-amber-200 flex gap-2"><ShieldAlert className="w-4 h-4 shrink-0"/><div><strong>Evidence blockers</strong><div className="mt-1 font-mono">{value.blockers.join(' · ')}</div></div></div>}
          <div className="text-[10px] text-slate-400 font-mono">Shared snapshot: {value.snapshotFingerprint} · Semantic section: {value.financialSemanticSectionFingerprint}</div>
        </div>
      )}
    </ApiStateWrapper>
  </section>
);
