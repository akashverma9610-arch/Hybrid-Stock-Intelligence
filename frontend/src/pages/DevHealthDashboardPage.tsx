import React, { useEffect, useMemo, useState } from 'react';
import { RefreshCw } from 'lucide-react';
import { useDataClient } from '../api/context';
import { ApiResponse } from '../types/api';
import { ConnectionsState } from '../types/connections';
import {
  DataOperationsHealthData,
  DecisionTrustDomain,
  DecisionTrustEnvelopeData,
  LocalRuntimeReadinessData,
  OpportunitySnapshotData,
  PortfolioRuntimeHolding,
  RuntimeStatusData,
} from '../types/devConsole';
import { LiveMarketOverviewData } from '../types/liveMarket';
import { PortfolioSummaryData } from '../types/portfolio';
import { SystemHealthData } from '../types/systemHealth';
import { StatusBadge } from '../components/common/StatusBadge';

type Focus =
  | 'system-health'
  | 'data-providers'
  | 'external-intelligence'
  | 'brain-inspector'
  | 'opportunity-setup'
  | 'portfolio-runtime'
  | 'policies-audit';

interface DevHealthDashboardPageProps {
  focus?: Focus;
}

type DashboardState = {
  health: ApiResponse<SystemHealthData> | null;
  runtime: ApiResponse<RuntimeStatusData> | null;
  localRuntime: ApiResponse<LocalRuntimeReadinessData> | null;
  operations: ApiResponse<DataOperationsHealthData> | null;
  connections: ApiResponse<ConnectionsState> | null;
  portfolio: ApiResponse<PortfolioSummaryData> | null;
  holdings: ApiResponse<PortfolioRuntimeHolding[]> | null;
  opportunities: ApiResponse<OpportunitySnapshotData> | null;
  liveMarket: ApiResponse<LiveMarketOverviewData> | null;
};

const NOT_EXPOSED = 'NOT_EXPOSED';

const initialState: DashboardState = {
  health: null,
  runtime: null,
  localRuntime: null,
  operations: null,
  connections: null,
  portfolio: null,
  holdings: null,
  opportunities: null,
  liveMarket: null,
};

const timestamp = (value: string | null | undefined) => value || 'NOT_EXPOSED';
const number = (value: string | number | null | undefined) => value === null || value === undefined ? 'NOT_EXPOSED' : String(value);
const statusOf = (response: ApiResponse<unknown> | null) => response?.data ? response.status : response?.status || 'LOADING';
const errorOf = (response: ApiResponse<unknown> | null) => response?.message || 'No backend read model is available.';

const Panel: React.FC<{ id: string; title: string; children: React.ReactNode; subtitle?: string }> = ({ id, title, subtitle, children }) => (
  <section id={id} className="rounded-lg border border-[#272727] bg-[#111] scroll-mt-24">
    <div className="border-b border-[#272727] px-4 py-3 sm:px-5">
      <h3 className="text-sm font-semibold text-gray-100">{title}</h3>
      {subtitle && <p className="mt-1 text-xs text-gray-500">{subtitle}</p>}
    </div>
    <div className="p-4 sm:p-5">{children}</div>
  </section>
);

const Datum: React.FC<{ label: string; value: React.ReactNode }> = ({ label, value }) => (
  <div className="min-w-0">
    <div className="text-[10px] uppercase tracking-wider text-gray-500">{label}</div>
    <div className="mt-1 break-words text-xs font-mono text-gray-200">{value}</div>
  </div>
);

const EmptyReadModel: React.FC<{ response: ApiResponse<unknown> | null; label: string }> = ({ response, label }) => (
  <div className="rounded border border-dashed border-[#363636] bg-[#0d0d0d] p-3 text-xs text-gray-400">
    <div className="flex items-center gap-2"><StatusBadge status={response?.status || NOT_EXPOSED} /> <span>{label}</span></div>
    <p className="mt-2 font-mono text-[11px] text-gray-500">{errorOf(response)}</p>
  </div>
);

const domainByName = (domains: DecisionTrustDomain[], name: string) => domains.find((domain) => domain.domain === name);

export const DevHealthDashboardPage: React.FC<DevHealthDashboardPageProps> = ({ focus }) => {
  const { client, refreshTrigger, triggerRefresh } = useDataClient();
  const [state, setState] = useState<DashboardState>(initialState);
  const [trustByInstrument, setTrustByInstrument] = useState<Record<string, ApiResponse<DecisionTrustEnvelopeData>>>({});
  const [selectedInstrumentId, setSelectedInstrumentId] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    const load = async () => {
      setLoading(true);
      const [health, runtime, localRuntime, operations, connections, portfolio, holdings, opportunities, liveMarket] = await Promise.all([
        client.getSystemHealth(),
        client.getRuntimeStatus(),
        client.getLocalRuntimeReadiness(),
        client.getDataOperationsHealth(),
        client.getConnectionsState(),
        client.getPortfolioSummary(),
        client.getPortfolioRuntimeHoldings(),
        client.getOpportunitySnapshot(),
        client.getLiveMarketOverview(),
      ]);
      if (!active) return;
      setState({ health, runtime, localRuntime, operations, connections, portfolio, holdings, opportunities, liveMarket });
      const instrumentIds = holdings.data?.map((holding) => holding.instrumentId) ?? [];
      const trustEntries = await Promise.all(instrumentIds.map(async (instrumentId) => [
        instrumentId,
        await client.getDecisionTrustEnvelope(instrumentId),
      ] as const));
      if (!active) return;
      setTrustByInstrument(Object.fromEntries(trustEntries));
      setSelectedInstrumentId((current) => instrumentIds.includes(current) ? current : instrumentIds[0] || '');
      setLoading(false);
    };
    void load();
    return () => { active = false; };
  }, [client, refreshTrigger]);

  useEffect(() => {
    if (focus) document.getElementById(focus)?.scrollIntoView({ block: 'start', behavior: 'smooth' });
  }, [focus]);

  const selectedTrust = selectedInstrumentId ? trustByInstrument[selectedInstrumentId] : undefined;
  const selectedEnvelope = selectedTrust?.data || null;
  const providerRows = useMemo(() => {
    const families = state.operations?.data?.families || [];
    const upstox = state.connections?.data?.providers.find((provider) => provider.id === 'upstox');
    const operationFor = (terms: string[]) => families.find((family) => terms.some((term) => family.family.toLowerCase().includes(term)));
    return [
      ['NSE Official EOD', operationFor(['nse', 'eod'])],
      ['NSE Delivery', operationFor(['delivery'])],
      ['NSE Tick Evidence', operationFor(['tick'])],
      ['NSE Indices', operationFor(['index', 'indices'])],
      ['Upstox', upstox ? { status: upstox.status, lastRun: upstox.lastValidatedTimestamp ? { completedAt: upstox.lastValidatedTimestamp, warnings: upstox.warnings } : null, reasons: upstox.warnings } : undefined],
      ['BSE', operationFor(['bse'])],
      ['NSE Reg31', operationFor(['reg31', 'ownership'])],
      ['RBI / Macro', operationFor(['macro', 'rbi'])],
      ['Dhan', undefined],
      ['External Intelligence / Supabase', undefined],
    ];
  }, [state.connections, state.operations]);

  const allBlockers = selectedEnvelope ? [
    ...selectedEnvelope.blockers,
    ...selectedEnvelope.domains.flatMap((domain) => domain.blockers.map((blocker) => `${domain.domain}: ${blocker}`)),
  ] : [];

  return (
    <div className="space-y-6">
      <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-end">
        <div>
          <p className="font-mono text-[11px] uppercase tracking-[0.16em] text-blue-400">HSI</p>
          <h1 className="mt-1 text-xl font-semibold text-white sm:text-2xl">Development Health Dashboard</h1>
          <p className="mt-1 text-sm text-gray-400">Hybrid Stock Intelligence — Development Console. Backend read models only.</p>
        </div>
        <button onClick={triggerRefresh} className="inline-flex items-center justify-center gap-2 rounded border border-blue-500/40 bg-blue-500/10 px-3 py-2 text-xs font-semibold text-blue-300 hover:bg-blue-500/20">
          <RefreshCw className={loading ? 'h-4 w-4 animate-spin' : 'h-4 w-4'} /> Refresh read models
        </button>
      </div>

      <Panel id="system-health" title="A. System Health" subtitle="Reachability and runtime state as exposed by HSI; no inferred database or live-feed state.">
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <Datum label="API backend reachable" value={<StatusBadge status={statusOf(state.health)} />} />
          <Datum label="Runtime scheduler" value={<StatusBadge status={state.runtime?.data ? (state.runtime.data.schedulerRunning ? 'ACTIVE' : state.runtime.data.schedulerEnabled ? 'IDLE' : 'PAUSED') : statusOf(state.runtime)} />} />
          <Datum label="Latest completed session" value={timestamp(selectedEnvelope?.latestCompletedMarketSession || state.runtime?.data?.lastDataAsOf)} />
          <Datum label="SQLite/database health" value={<StatusBadge status={state.localRuntime?.data?.sqliteIntegrity === 'ok' ? 'READY' : state.localRuntime?.data?.warnings.length ? 'DEGRADED' : statusOf(state.localRuntime)} />} />
          <Datum label="Database storage / path" value={state.localRuntime?.data ? `${state.localRuntime.data.storageMode} · ${state.localRuntime.data.databasePath || NOT_EXPOSED}` : NOT_EXPOSED} />
          <Datum label="Sector-ranking artifact / as-of" value={selectedEnvelope ? `${domainByName(selectedEnvelope.domains, 'SECTOR_ROTATION')?.artifactIds.join(', ') || NOT_EXPOSED} · ${timestamp(domainByName(selectedEnvelope.domains, 'SECTOR_ROTATION')?.evidenceAsOf)}` : NOT_EXPOSED} />
          <Datum label="Dhan live state" value={<StatusBadge status={state.liveMarket?.data?.health.health || statusOf(state.liveMarket)} />} />
          <Datum label="Dhan subscription / packets" value={state.liveMarket?.data ? `${state.liveMarket.data.health.subscribedTargets} / ${state.liveMarket.data.health.requestedTargets} · ${state.liveMarket.data.health.mappedPackets}` : NOT_EXPOSED} />
          <Datum label="External-intelligence bridge" value={<StatusBadge status={NOT_EXPOSED} />} />
          <Datum label="Last cycle status" value={state.runtime?.data ? <StatusBadge status={state.runtime.data.lastCycleStatus || 'NOT_STARTED'} /> : <StatusBadge status={statusOf(state.runtime)} />} />
          <Datum label="Last cycle completed" value={timestamp(state.runtime?.data?.lastCompletedAt)} />
          <Datum label="Runtime mode" value={state.runtime?.data?.runtimeMode || NOT_EXPOSED} />
          <Datum label="Consecutive failures" value={state.runtime?.data ? state.runtime.data.consecutiveFailures : NOT_EXPOSED} />
        </div>
        {state.health?.data?.systemWarnings?.length ? <div className="mt-4"><Blockers values={state.health.data.systemWarnings} /></div> : null}
      </Panel>

      <Panel id="data-providers" title="B. Data & Providers" subtitle="Provider metadata is backend-normalized. This view never accesses provider credentials or transport secrets.">
        <div className="overflow-x-auto"><table className="w-full min-w-[700px] text-left text-xs"><thead className="border-b border-[#2b2b2b] text-[10px] uppercase tracking-wider text-gray-500"><tr><th className="pb-2 pr-3">Provider / data family</th><th className="pb-2 pr-3">State</th><th className="pb-2 pr-3">Last run / validation</th><th className="pb-2">Blocker / reason</th></tr></thead><tbody>
          {providerRows.map(([name, item]) => <tr key={name as string} className="border-b border-[#1f1f1f]"><td className="py-3 pr-3 font-medium text-gray-200">{name as string}</td><td className="py-3 pr-3"><StatusBadge status={(item as any)?.status || NOT_EXPOSED} /></td><td className="py-3 pr-3 font-mono text-gray-400">{timestamp((item as any)?.lastRun?.completedAt)}</td><td className="py-3 text-gray-500">{((item as any)?.reasons || (item as any)?.lastRun?.warnings || []).join(', ') || ((item as any) ? 'No blocker exposed.' : 'BACKEND_READ_ENDPOINT_REQUIRED')}</td></tr>)}
        </tbody></table></div>
      </Panel>

      <Panel id="local-runtime" title="Local Runtime Readiness" subtitle="Read-only local process and database evidence; this panel never starts jobs or resumes BSE acquisition.">
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <Datum label="SQLite integrity" value={<StatusBadge status={state.localRuntime?.data?.sqliteIntegrity === 'ok' ? 'READY' : statusOf(state.localRuntime)} />} />
          <Datum label="FK violations" value={number(state.localRuntime?.data?.foreignKeyViolations)} />
          <Datum label="Financial facts / filings" value={state.localRuntime?.data ? `${number(state.localRuntime.data.financialFacts)} / ${number(state.localRuntime.data.corporateFilings)}` : NOT_EXPOSED} />
          <Datum label="BSE status / receipts" value={state.localRuntime?.data ? <><StatusBadge status={state.localRuntime.data.bseStatus} /> {number(state.localRuntime.data.bseReceipts)}</> : NOT_EXPOSED} />
          <Datum label="Portfolio snapshots" value={number(state.localRuntime?.data?.portfolioSnapshots)} />
          <Datum label="Market-Wide Watch" value={<StatusBadge status={state.localRuntime?.data?.marketWideWatchStatus || NOT_EXPOSED} />} />
          <Datum label="Dhan safe health" value={<StatusBadge status={state.liveMarket?.data?.health.health || NOT_EXPOSED} />} />
          <Datum label="Dhan mode" value={state.liveMarket?.data?.enabled ? 'LIVE' : 'RESEARCH_ONLY'} />
        </div>
        {state.localRuntime?.data?.warnings.length ? <div className="mt-4"><Blockers values={state.localRuntime.data.warnings} /></div> : null}
      </Panel>

      <Panel id="external-intelligence" title="C. External Intelligence" subtitle="Canonical ingestion is backend-authenticated. This console intentionally never accesses Supabase from the browser.">
        <div className="grid gap-3 md:grid-cols-3">
          <ReadCard label="Canonical event listing" detail="POST ingestion exists; a GET event-list read model is not exposed." />
          <ReadCard label="Bridge / delivery health" detail="No normalized backend transport-health endpoint is exposed." />
          <ReadCard label="Company exposure verification" detail="No browser-readable external-intelligence projection endpoint is exposed." />
        </div>
      </Panel>

      <Panel id="brain-inspector" title="D. Shared Brain Inspector" subtitle="Decision Trust Envelope V1 is the primary read model. The selector uses canonical instrument IDs returned by the current portfolio endpoint.">
        {!state.holdings?.data?.length ? <EmptyReadModel response={state.holdings} label="No current canonical portfolio holding is available for inspection." /> : <>
          <label className="block max-w-xl text-xs text-gray-400">Canonical stock
            <select value={selectedInstrumentId} onChange={(event) => setSelectedInstrumentId(event.target.value)} className="mt-1 block w-full rounded border border-[#363636] bg-[#0c0c0c] px-3 py-2 font-mono text-xs text-gray-100">
              {state.holdings.data.map((holding) => <option key={holding.instrumentId} value={holding.instrumentId}>{holding.symbol || holding.instrumentId} — {holding.instrumentId}</option>)}
            </select>
          </label>
          {!selectedEnvelope ? <div className="mt-4"><EmptyReadModel response={selectedTrust || null} label="Decision Trust Envelope unavailable for this canonical instrument." /></div> : <div className="mt-5 space-y-5">
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <Datum label="Decision Score" value={<>{number(selectedEnvelope.decisionScore.value)} <StatusBadge status={selectedEnvelope.decisionScore.state} /></>} />
              <Datum label="Evidence Domain Coverage" value={`${selectedEnvelope.coverageCount} / ${selectedEnvelope.coverageTotal} (${selectedEnvelope.coveragePct}%)`} />
              <Datum label="Shared Brain state" value={<StatusBadge status={selectedEnvelope.sharedBrainState} />} />
              <Datum label="Decision readiness" value={<StatusBadge status={selectedEnvelope.decisionReadiness} />} />
              <Datum label="Reliability / Integrity" value={<StatusBadge status={domainByName(selectedEnvelope.domains, 'RELIABILITY_INTEGRITY')?.availability || NOT_EXPOSED} />} />
              <Datum label="Sector" value={<StatusBadge status={domainByName(selectedEnvelope.domains, 'SECTOR_ROTATION')?.availability || NOT_EXPOSED} />} />
              <Datum label="Setup" value={<StatusBadge status={selectedEnvelope.setup.state} />} />
              <Datum label="Six Gates" value={<StatusBadge status={selectedEnvelope.sixGates.state} />} />
            </div>
            <div className="grid gap-4 lg:grid-cols-2"><Datum label="Intelligence as-of" value={timestamp(selectedEnvelope.intelligenceAsOf)} /><Datum label="Score / setup / gates as-of" value={`${timestamp(selectedEnvelope.decisionScore.scoreAsOf)} / ${timestamp(selectedEnvelope.setup.setupAsOf)} / ${timestamp(selectedEnvelope.sixGates.evaluationAsOf)}`} /></div>
            <div className="grid gap-4 lg:grid-cols-2"><TextValue label="Trading thesis" value={selectedEnvelope.thesis.tradingThesis} /><TextValue label="Investment thesis" value={selectedEnvelope.thesis.investmentThesis} /><TextValue label="Invalidation" value={selectedEnvelope.thesis.invalidationStatus || selectedEnvelope.thesis.structuralInvalidation} /><TextValue label="Live market context" value={selectedEnvelope.liveMarket.ltp ? `LTP ${selectedEnvelope.liveMarket.ltp}; ${timestamp(selectedEnvelope.liveMarket.receivedAt)}; ${selectedEnvelope.liveMarket.freshness || 'UNKNOWN'}` : 'NOT_EXPOSED'} /></div>
          </div>}
        </>}
      </Panel>

      <Panel id="domain-matrix" title="Evidence Domain Matrix" subtitle="Categorical domain availability and freshness; no numerical confidence is inferred.">
        {!selectedEnvelope ? <EmptyReadModel response={selectedTrust || null} label="Select a holding with a readable Decision Trust Envelope." /> : <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-4">{selectedEnvelope.domains.map((domain) => <details key={domain.domain} className="rounded border border-[#2d2d2d] bg-[#0c0c0c] p-3"><summary className="cursor-pointer list-none"><div className="flex items-center justify-between gap-2"><span className="text-[11px] font-medium text-gray-200">{domain.domain}</span><StatusBadge status={domain.availability} /></div><div className="mt-2 text-[10px] font-mono text-gray-500">{domain.freshness} · {timestamp(domain.evidenceAsOf)}</div></summary><div className="mt-3 space-y-2 text-[10px] font-mono text-gray-500"><div>Artifacts: {domain.artifactIds.join(', ') || NOT_EXPOSED}</div><div>Fingerprints: {domain.artifactFingerprints.join(', ') || NOT_EXPOSED}</div><div>Blockers: {domain.blockers.join(', ') || 'None exposed.'}</div></div></details>)}</div>}
      </Panel>

      <Panel id="portfolio-runtime" title="F. Portfolio Runtime" subtitle="Read-only current portfolio snapshot and stored market marks. A shared live valuation endpoint is not exposed.">
        <div className="grid gap-4 sm:grid-cols-3"><Datum label="Cash" value={state.portfolio?.data?.cashStatus || NOT_EXPOSED} /><Datum label="Portfolio snapshot status" value={<StatusBadge status={statusOf(state.portfolio)} />} /><Datum label="Live valuation" value={<StatusBadge status={NOT_EXPOSED} />} /></div>
        {!state.holdings?.data ? <div className="mt-4"><EmptyReadModel response={state.holdings} label="Portfolio holdings are unavailable." /></div> : <div className="mt-5 overflow-x-auto"><table className="w-full min-w-[920px] text-left text-xs"><thead className="border-b border-[#2b2b2b] text-[10px] uppercase tracking-wider text-gray-500"><tr><th className="pb-2">Instrument</th><th className="pb-2">Quantity</th><th className="pb-2">Average price</th><th className="pb-2">Persisted market price</th><th className="pb-2">Current value</th><th className="pb-2">Unrealized P&L</th><th className="pb-2">As-of</th></tr></thead><tbody>{state.holdings.data.map((holding) => <tr key={holding.instrumentId} className="border-b border-[#1f1f1f] text-gray-300"><td className="py-3 font-mono">{holding.symbol || holding.instrumentId}</td><td>{holding.quantity}</td><td>{holding.averagePrice}</td><td>{number(holding.marketPrice)}</td><td>{number(holding.currentValue)}</td><td>{number(holding.unrealizedPnl)}</td><td className="font-mono text-gray-500">{timestamp(holding.dataAsOf)}</td></tr>)}</tbody></table></div>}
      </Panel>

      <Panel id="portfolio-quick-view" title="Current Portfolio Quick View" subtitle="Current holdings only. Coverage, scores, and blocker lists are rendered directly from each holding's envelope.">
        {!state.holdings?.data?.length ? <EmptyReadModel response={state.holdings} label="No current holdings returned." /> : <div className="overflow-x-auto"><table className="w-full min-w-[1040px] text-left text-xs"><thead className="border-b border-[#2b2b2b] text-[10px] uppercase tracking-wider text-gray-500"><tr><th className="pb-2">Holding</th><th className="pb-2">Decision Score</th><th className="pb-2">Domain Coverage</th><th className="pb-2">Brain</th><th className="pb-2">Reliability</th><th className="pb-2">Sector</th><th className="pb-2">Setup</th><th className="pb-2">Six Gates</th><th className="pb-2">Blockers</th></tr></thead><tbody>{state.holdings.data.map((holding) => { const trust = trustByInstrument[holding.instrumentId]?.data; return <tr key={holding.instrumentId} className="border-b border-[#1f1f1f]"><td className="py-3 font-mono text-gray-200">{trust?.symbol || holding.symbol || holding.instrumentId}</td><td>{trust ? <>{number(trust.decisionScore.value)} <StatusBadge status={trust.decisionScore.state} /></> : <StatusBadge status={trustByInstrument[holding.instrumentId]?.status || NOT_EXPOSED} />}</td><td>{trust ? `${trust.coverageCount} / ${trust.coverageTotal}` : NOT_EXPOSED}</td><td>{trust ? <StatusBadge status={trust.sharedBrainState} /> : NOT_EXPOSED}</td><td>{trust ? <StatusBadge status={domainByName(trust.domains, 'RELIABILITY_INTEGRITY')?.availability || NOT_EXPOSED} /> : NOT_EXPOSED}</td><td>{trust ? <StatusBadge status={domainByName(trust.domains, 'SECTOR_ROTATION')?.availability || NOT_EXPOSED} /> : NOT_EXPOSED}</td><td>{trust ? <StatusBadge status={trust.setup.state} /> : NOT_EXPOSED}</td><td>{trust ? <StatusBadge status={trust.sixGates.state} /> : NOT_EXPOSED}</td><td className="font-mono text-gray-400">{trust ? trust.blockers.length : NOT_EXPOSED}</td></tr>; })}</tbody></table></div>}
      </Panel>

      <Panel id="opportunity-setup" title="E. Opportunity / Setup Inspector" subtitle="The Opportunity Finder snapshot and setup fields are backend-owned; the console performs no setup reconstruction.">
        {!state.opportunities?.data ? <EmptyReadModel response={state.opportunities} label="No governed Opportunity Finder snapshot is available." /> : <><div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4"><Datum label="As-of" value={timestamp(state.opportunities.data.asOf)} /><Datum label="Universe / analyzed" value={`${state.opportunities.data.universeCount} / ${state.opportunities.data.analyzedCount}`} /><Datum label="Qualified candidates" value={state.opportunities.data.qualifiedCandidateCount} /><Datum label="Coverage" value={<StatusBadge status={state.opportunities.data.coverageStatus} />} /></div><div className="mt-5 overflow-x-auto"><table className="w-full min-w-[680px] text-left text-xs"><thead className="border-b border-[#2b2b2b] text-[10px] uppercase tracking-wider text-gray-500"><tr><th className="pb-2">Symbol</th><th className="pb-2">Sector</th><th className="pb-2">Execution</th><th className="pb-2">Candidate</th><th className="pb-2">Exact blockers</th></tr></thead><tbody>{state.opportunities.data.opportunities.map((item) => <tr key={`${item.symbol}-${item.sector || ''}`} className="border-b border-[#1f1f1f]"><td className="py-3 font-mono text-gray-200">{item.symbol}</td><td>{item.sector || NOT_EXPOSED}</td><td><StatusBadge status={item.executionStatus} /></td><td><StatusBadge status={item.candidateStatus} /></td><td className="font-mono text-gray-500">{item.warnings.join(', ') || 'None exposed.'}</td></tr>)}</tbody></table></div></>}
        <div className="mt-5 rounded border border-[#2d2d2d] bg-[#0c0c0c] p-4"><h4 className="text-xs font-semibold text-gray-200">Selected holding setup</h4>{selectedEnvelope?.setup.setupId ? <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-4"><Datum label="Entry" value={number(selectedEnvelope.setup.entry)} /><Datum label="Structural SL / invalidation" value={number(selectedEnvelope.setup.structuralInvalidation)} /><Datum label="T1 / T2" value={`${number(selectedEnvelope.setup.target1)} / ${number(selectedEnvelope.setup.target2)}`} /><Datum label="Extended / R:R / E_max" value={`${number(selectedEnvelope.setup.extendedTarget)} / ${number(selectedEnvelope.setup.riskReward)} / ${number(selectedEnvelope.setup.maximumExecutableEntry)}`} /><Datum label="Setup as-of" value={timestamp(selectedEnvelope.setup.setupAsOf)} /><Datum label="Setup policy identity" value={selectedEnvelope.setup.setupType || NOT_EXPOSED} /></div> : <p className="mt-2 font-mono text-xs text-gray-400">NO CURRENT SETUP</p>}</div>
      </Panel>

      <Panel id="policies-audit" title="G. Policies & Audit" subtitle="Read-only policy identity and envelope lineage. No policy editing is available in this console.">
        {!selectedEnvelope ? <EmptyReadModel response={selectedTrust || null} label="Select a portfolio holding to inspect current envelope lineage." /> : <><div className="grid gap-4 md:grid-cols-2"><Datum label="Decision Trust Envelope version" value={selectedEnvelope.version} /><Datum label="Decision Score policy" value={`${selectedEnvelope.decisionScore.policyVersion || NOT_EXPOSED} · ${selectedEnvelope.decisionScore.policyFingerprint || NOT_EXPOSED}`} /><Datum label="Six Gates production policy" value={`${selectedEnvelope.sixGates.policyId || NOT_EXPOSED} · ${selectedEnvelope.sixGates.policyFingerprint || NOT_EXPOSED}`} /><Datum label="Canonical 61 / Pre-Breakout / Reliability policy" value="BACKEND_READ_ENDPOINT_REQUIRED" /></div><div className="mt-5 rounded border border-[#2d2d2d] bg-[#0c0c0c] p-4"><div className="flex flex-wrap items-center gap-2"><span className="text-xs font-semibold text-gray-200">Six Gates evaluation</span><StatusBadge status={selectedEnvelope.sixGates.state} /></div>{selectedEnvelope.sixGates.gateResults.length ? <ul className="mt-3 grid gap-2 sm:grid-cols-2">{selectedEnvelope.sixGates.gateResults.map(([gate, result]) => <li key={gate} className="flex justify-between gap-2 font-mono text-[11px] text-gray-400"><span>{gate}</span><StatusBadge status={result} /></li>)}</ul> : <p className="mt-2 font-mono text-xs text-gray-500">NOT_EVALUATED — no production evaluation is exposed for this holding.</p>}</div></>}
      </Panel>

      <Panel id="blockers" title="Conflicts & Blockers" subtitle="Exact blocker codes and domain context as returned by the selected envelope.">
        {selectedEnvelope ? <div className="overflow-x-auto"><table className="w-full min-w-[720px] text-left text-xs"><thead className="border-b border-[#2b2b2b] text-[10px] uppercase tracking-wider text-gray-500"><tr><th className="pb-2">Instrument</th><th className="pb-2">Domain / component</th><th className="pb-2">Blocker code</th><th className="pb-2">As-of</th><th className="pb-2">Evidence / artifact</th></tr></thead><tbody>{selectedEnvelope.blockers.map((blocker, index) => <BlockerRow key={`envelope-${blocker}-${index}`} instrument={selectedEnvelope.canonicalInstrumentId} component="DECISION_TRUST_ENVELOPE" blocker={blocker} asOf={selectedEnvelope.intelligenceAsOf} artifacts={[selectedEnvelope.fingerprint]} />)}{selectedEnvelope.domains.flatMap((domain) => domain.blockers.map((blocker, index) => <BlockerRow key={`${domain.domain}-${blocker}-${index}`} instrument={selectedEnvelope.canonicalInstrumentId} component={domain.domain} blocker={blocker} asOf={domain.evidenceAsOf || domain.observedAt} artifacts={domain.artifactIds} />))}</tbody></table>{!allBlockers.length && <p className="mt-3 font-mono text-xs text-gray-500">No blocker is exposed by the current backend read model.</p>}</div> : <EmptyReadModel response={selectedTrust || null} label="No selected envelope is available for blocker inspection." />}
      </Panel>
    </div>
  );
};

const ReadCard: React.FC<{ label: string; detail: string }> = ({ label, detail }) => <div className="rounded border border-dashed border-[#363636] bg-[#0c0c0c] p-4"><div className="flex items-center justify-between gap-2"><span className="text-xs font-semibold text-gray-200">{label}</span><StatusBadge status={NOT_EXPOSED} /></div><p className="mt-2 text-xs text-gray-500">{detail}</p></div>;

const TextValue: React.FC<{ label: string; value: string | null }> = ({ label, value }) => <div className="rounded border border-[#2d2d2d] bg-[#0c0c0c] p-3"><div className="text-[10px] uppercase tracking-wider text-gray-500">{label}</div><p className="mt-2 whitespace-pre-wrap text-xs text-gray-300">{value || NOT_EXPOSED}</p></div>;

const Blockers: React.FC<{ values: string[] }> = ({ values }) => values.length ? <ul className="space-y-2">{values.map((blocker, index) => <li key={`${blocker}-${index}`} className="rounded border border-amber-500/20 bg-amber-500/5 px-3 py-2 font-mono text-[11px] text-amber-200">{blocker}</li>)}</ul> : <p className="font-mono text-xs text-gray-500">No blocker is exposed by the current backend read model.</p>;

const BlockerRow: React.FC<{ instrument: string; component: string; blocker: string; asOf: string | null; artifacts: string[] }> = ({ instrument, component, blocker, asOf, artifacts }) => <tr className="border-b border-[#1f1f1f]"><td className="py-3 font-mono text-gray-300">{instrument}</td><td className="py-3 text-gray-300">{component}</td><td className="py-3 font-mono text-amber-200">{blocker}</td><td className="py-3 font-mono text-gray-500">{timestamp(asOf)}</td><td className="py-3 font-mono text-gray-500">{artifacts.join(', ') || NOT_EXPOSED}</td></tr>;
