import React, { useEffect, useState } from 'react';
import { ArrowRight, CircleAlert, Search } from 'lucide-react';
import { useDataClient } from '../api/context';
import { ApiResponse } from '../types/api';
import { DecisionTrustEnvelopeData, MarketWideWatchData, OpportunitySnapshotData, PortfolioRuntimeHolding } from '../types/devConsole';
import { MarketStateData } from '../types/market';
import { NewsData } from '../types/news';
import { PortfolioSummaryData } from '../types/portfolio';
import { SellSideData } from '../types/sellSide';
import { StockListItem } from '../types/stock';
import { LiveMarketOverviewData, LivePortfolioData, StockLiveMarketData } from '../types/liveMarket';
import { StatusBadge } from '../components/common/StatusBadge';
import { useNavigation } from '../context/NavigationContext';

const NOT_EXPOSED = 'NOT_EXPOSED';
const when = (value: string | null | undefined) => value || NOT_EXPOSED;
const value = (item: string | number | null | undefined) => item === null || item === undefined ? NOT_EXPOSED : String(item);
const domain = (envelope: DecisionTrustEnvelopeData | null | undefined, key: string) => envelope?.domains.find((item) => item.domain === key);

type Evidence = {
  market: ApiResponse<MarketStateData> | null;
  opportunities: ApiResponse<OpportunitySnapshotData> | null;
  holdings: ApiResponse<PortfolioRuntimeHolding[]> | null;
  portfolio: ApiResponse<PortfolioSummaryData> | null;
  sellSide: ApiResponse<SellSideData> | null;
  news: ApiResponse<NewsData> | null;
  stocks: ApiResponse<StockListItem[]> | null;
  envelopes: Record<string, ApiResponse<DecisionTrustEnvelopeData>>;
};

const empty: Evidence = { market: null, opportunities: null, holdings: null, portfolio: null, sellSide: null, news: null, stocks: null, envelopes: {} };

const useEvidence = () => {
  const { client, refreshTrigger } = useDataClient();
  const [evidence, setEvidence] = useState<Evidence>(empty);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    let current = true;
    const load = async () => {
      setLoading(true);
      const [market, opportunities, holdings, portfolio, sellSide, news, stocks] = await Promise.all([
        client.getMarketState(), client.getOpportunitySnapshot(), client.getPortfolioRuntimeHoldings(),
        client.getPortfolioSummary(), client.getPortfolioSellSide(), client.getNews(), client.getStocksList(),
      ]);
      if (!current) return;
      const ids = holdings.data?.map((holding) => holding.instrumentId) ?? [];
      const records = await Promise.all(ids.map(async (id) => [id, await client.getDecisionTrustEnvelope(id)] as const));
      if (!current) return;
      setEvidence({ market, opportunities, holdings, portfolio, sellSide, news, stocks, envelopes: Object.fromEntries(records) });
      setLoading(false);
    };
    void load();
    return () => { current = false; };
  }, [client, refreshTrigger]);
  return { evidence, loading };
};

const useLiveOverview = () => {
  const { client, refreshTrigger } = useDataClient();
  const [response, setResponse] = useState<ApiResponse<LiveMarketOverviewData> | null>(null);
  useEffect(() => {
    let current = true;
    void client.getLiveMarketOverview().then((value) => { if (current) setResponse(value); });
    return () => { current = false; };
  }, [client, refreshTrigger]);
  return response;
};

const useLivePortfolio = () => {
  const { client, refreshTrigger } = useDataClient();
  const [response, setResponse] = useState<ApiResponse<LivePortfolioData> | null>(null);
  useEffect(() => {
    let current = true;
    void client.getLivePortfolioValuation().then((value) => { if (current) setResponse(value); });
    return () => { current = false; };
  }, [client, refreshTrigger]);
  return response;
};

const Surface: React.FC<{ children: React.ReactNode; className?: string }> = ({ children, className = '' }) => <section className={`rounded-xl border border-[#dfe4de] bg-white shadow-[0_1px_2px_rgba(23,32,28,.04)] ${className}`}>{children}</section>;
const SectionTitle: React.FC<{ eyebrow?: string; title: string; detail?: string; action?: React.ReactNode }> = ({ eyebrow, title, detail, action }) => <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-end"><div>{eyebrow && <p className="text-[11px] font-semibold uppercase tracking-[.16em] text-[#668675]">{eyebrow}</p>}<h1 className="mt-1 text-2xl font-semibold tracking-tight text-[#17201c] sm:text-3xl">{title}</h1>{detail && <p className="mt-2 max-w-2xl text-sm leading-6 text-[#637068]">{detail}</p>}</div>{action}</div>;
const DataState: React.FC<{ response: ApiResponse<unknown> | null; children: React.ReactNode | (() => React.ReactNode) }> = ({ response, children }) => response?.data ? <>{typeof children === 'function' ? children() : children}</> : <Surface><div className="p-5"><StatusBadge status={response?.status || NOT_EXPOSED} /><p className="mt-3 text-sm text-[#637068]">{response?.message || 'This evidence is not currently exposed by the HSI backend.'}</p></div></Surface>;
const LinkToStock: React.FC<{ instrumentId: string; children: React.ReactNode }> = ({ instrumentId, children }) => { const { navigate } = useNavigation(); return <button onClick={() => navigate(`/stocks/${encodeURIComponent(instrumentId)}`)} className="inline-flex items-center gap-1.5 text-left font-medium text-[#1e6550] hover:underline">{children}<ArrowRight className="h-3.5 w-3.5" /></button>; };

const EnvelopeSummary: React.FC<{ envelope: DecisionTrustEnvelopeData }> = ({ envelope }) => <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4"><Fact label="Decision Score" value={<span className="flex flex-wrap items-center gap-2">{value(envelope.decisionScore.value)} <StatusBadge status={envelope.decisionScore.state} /></span>} /><Fact label="Evidence Domain Coverage" value={`${envelope.coverageCount} / ${envelope.coverageTotal} domains available — ${envelope.coveragePct}%`} /><Fact label="Shared Brain" value={<StatusBadge status={envelope.sharedBrainState} />} /><Fact label="Execution readiness" value={<StatusBadge status={envelope.sixGates.state} />} /></div>;
const Fact: React.FC<{ label: string; value: React.ReactNode }> = ({ label, value: item }) => <div><p className="text-[10px] font-semibold uppercase tracking-[.12em] text-[#829087]">{label}</p><div className="mt-1.5 break-words text-sm text-[#26362e]">{item}</div></div>;
const Blockers: React.FC<{ values: string[] }> = ({ values }) => values.length ? <ul className="space-y-2">{values.slice(0, 5).map((item, index) => <li key={`${item}-${index}`} className="rounded-md bg-[#fbf5e9] px-3 py-2 text-xs text-[#765819]"><CircleAlert className="mr-2 inline h-3.5 w-3.5" />{item}</li>)}</ul> : <p className="text-sm text-[#637068]">No primary blocker is exposed by the current evidence.</p>;

export const ProductionHomePage: React.FC = () => {
  const { evidence, loading } = useEvidence();
  const qualified = evidence.opportunities?.data?.qualifiedCandidateCount ?? null;
  const attention = evidence.holdings?.data?.filter((holding) => evidence.envelopes[holding.instrumentId]?.data?.blockers.length).slice(0, 3) ?? [];
  return <div className="space-y-8"><SectionTitle eyebrow="Market Intelligence" title="What matters now" detail="A decision-first view of currently governed HSI evidence." />
    <div className="grid gap-4 lg:grid-cols-[1.35fr_.65fr]"><Surface className="overflow-hidden"><div className="p-6 sm:p-8"><p className="text-[11px] font-semibold uppercase tracking-[.16em] text-[#668675]">Current actionability</p>{qualified === 0 || qualified === null ? <><h2 className="mt-3 text-2xl font-semibold text-[#17201c]">NO CURRENT HIGH-CONVICTION SETUP</h2><p className="mt-3 max-w-xl text-sm leading-6 text-[#637068]">No setup currently satisfies HSI’s production policy. This is a healthy governed state, not an error.</p></> : <><h2 className="mt-3 text-2xl font-semibold text-[#17201c]">{qualified} current governed opportunity{qualified === 1 ? '' : 'ies'}</h2><p className="mt-3 text-sm text-[#637068]">Review the evidence, setup state, and Six Gates before considering any execution.</p></>}</div><div className="border-t border-[#e6ebe7] bg-[#f7faf8] p-5"><div className="grid gap-4 sm:grid-cols-3"><Fact label="Market regime" value={evidence.market?.data ? <><StatusBadge status={evidence.market.data.regime} /> <span className="ml-2 text-xs text-[#637068]">{evidence.market.data.regimeLabel}</span></> : <StatusBadge status={evidence.market?.status || NOT_EXPOSED} />} /><Fact label="Market freshness" value={evidence.market?.data ? <><StatusBadge status={evidence.market.data.freshness} /> <span className="ml-2 text-xs text-[#637068]">{when(evidence.market.data.lastUpdated)}</span></> : NOT_EXPOSED} /><Fact label="Opportunity scan cutoff" value={when(evidence.opportunities?.data?.asOf)} /></div></div></Surface>
      <Surface><div className="p-6"><p className="text-[11px] font-semibold uppercase tracking-[.16em] text-[#668675]">Portfolio attention</p><div className="mt-4 space-y-3">{attention.length ? attention.map((holding) => { const envelope = evidence.envelopes[holding.instrumentId]?.data; return <div key={holding.instrumentId} className="border-b border-[#edf0ee] pb-3 last:border-0"><LinkToStock instrumentId={holding.instrumentId}>{envelope?.symbol || holding.symbol || holding.instrumentId}</LinkToStock><p className="mt-1 text-xs text-[#637068]">{envelope?.blockers[0] || NOT_EXPOSED}</p></div>; }) : <p className="text-sm text-[#637068]">{loading ? 'Loading current portfolio evidence…' : 'No portfolio attention item is exposed.'}</p>}</div></div></Surface></div>
    <div className="grid gap-4 lg:grid-cols-2"><Surface><div className="p-6"><h2 className="text-lg font-semibold">Opportunity Finder</h2><p className="mt-1 text-sm text-[#637068]">Current pipeline from HSI’s governed scan.</p><DataState response={evidence.opportunities}>{() => <div className="mt-5 space-y-3">{evidence.opportunities!.data!.opportunities.slice(0, 4).map((item) => <div key={`${item.symbol}-${item.sector}`} className="flex items-center justify-between gap-3 border-b border-[#edf0ee] pb-3 last:border-0"><div><p className="text-sm font-medium">{item.symbol}</p><p className="text-xs text-[#637068]">{item.sector || NOT_EXPOSED} · {item.warnings.join(', ') || 'No blocker exposed.'}</p></div><StatusBadge status={item.candidateStatus} /></div>)}{!evidence.opportunities!.data!.opportunities.length && <p className="text-sm text-[#637068]">No candidate assessment is currently exposed.</p>}</div>}</DataState></div></Surface>
      <Surface><div className="p-6"><h2 className="text-lg font-semibold">Material intelligence</h2><p className="mt-1 text-sm text-[#637068]">Normalized HSI news evidence; external event metadata appears only when safely exposed.</p><DataState response={evidence.news}>{() => <div className="mt-5 space-y-3">{evidence.news!.data!.items.slice(0, 3).map((item) => <div key={item.id} className="border-b border-[#edf0ee] pb-3 last:border-0"><div className="flex flex-wrap justify-between gap-2"><p className="text-sm font-medium">{item.title}</p><StatusBadge status={item.eventCategory} /></div><p className="mt-1 text-xs text-[#637068]">{item.publisher} · {when(item.timestamp)}</p></div>)}{!evidence.news!.data!.items.length && <p className="text-sm text-[#637068]">No material intelligence item is currently exposed.</p>}</div>}</DataState></div></Surface></div>
  </div>;
};

export const ProductionOpportunitiesPage: React.FC = () => {
  const { evidence } = useEvidence();
  return <div className="space-y-7"><SectionTitle eyebrow="Opportunity Finder" title="Governed opportunity pipeline" detail="Candidates are grouped by backend state. No rejected or data-blocked item is presented as a recommendation." /><DataState response={evidence.opportunities}>{() => <><Surface><div className="grid gap-4 p-6 sm:grid-cols-2 lg:grid-cols-5"><Fact label="Scan cutoff" value={when(evidence.opportunities!.data!.asOf)} /><Fact label="Universe" value={evidence.opportunities!.data!.universeCount} /><Fact label="Valid opportunities" value={evidence.opportunities!.data!.qualifiedCandidateCount} /><Fact label="Data blocked" value={evidence.opportunities!.data!.unavailableCount} /><Fact label="Coverage" value={<StatusBadge status={evidence.opportunities!.data!.coverageStatus} />} /></div></Surface><CandidateGroup title="VALID SETUP" detail="Only candidates with a backend-governed valid state." candidates={evidence.opportunities!.data!.opportunities.filter((item) => item.candidateStatus === 'VALID_SETUP' || item.executionStatus === 'EXECUTION_READY')} /><CandidateGroup title="WATCH / CONDITION NOT MET" detail="Monitored evidence only — not actionable." candidates={evidence.opportunities!.data!.opportunities.filter((item) => item.candidateStatus !== 'VALID_SETUP' && item.executionStatus !== 'EXECUTION_READY' && item.executionStatus !== 'BLOCKED_DATA')} /><CandidateGroup title="DATA BLOCKED" detail="Missing or unavailable evidence prevents a governed decision." candidates={evidence.opportunities!.data!.opportunities.filter((item) => item.executionStatus === 'BLOCKED_DATA')} /></>}</DataState></div>;
};

const EvidenceDomainCoverage = ({ coverage }: { coverage: string[] }) => (
  <div className="flex max-w-xs flex-wrap gap-1" aria-label="Evidence domain coverage">
    {coverage.map((entry) => <StatusBadge key={entry} status={entry} />)}
  </div>
);

export const ProductionMarketWideWatchPage: React.FC = () => {
  const { client, refreshTrigger } = useDataClient();
  const [response, setResponse] = useState<ApiResponse<MarketWideWatchData> | null>(null);
  useEffect(() => {
    let current = true;
    void client.getMarketWideWatch().then((value) => { if (current) setResponse(value); });
    return () => { current = false; };
  }, [client, refreshTrigger]);
  const watch = response?.data;
  const candidates = watch?.records.filter((item) => item.archetypes.length) ?? [];
  return <div className="space-y-7">
    <SectionTitle eyebrow="Discovery layer" title="Market-Wide Quality & Inflection Watch" detail="This discovers material governed evidence across the eligible market. It is separate from the strict Setup, Decision Score, and Six Gates execution funnel." />
    <Surface><div className="border-l-4 border-[#b48726] bg-[#fffaf0] p-5"><p className="text-sm font-semibold text-[#735719]">WATCH — NOT ACTIONABLE</p><p className="mt-1 text-sm text-[#735719]">A Watch classification is neither BUY, ADD, ROTATE, nor a valid setup. Actionability remains owned by the existing downstream policy.</p></div></Surface>
    <DataState response={response}>{() => <>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
        <Surface><div className="p-5"><Fact label="NIFTY 500 universe" value={`${watch!.eligibleCount} / ${watch!.universeCount}`} /></div></Surface>
        <Surface><div className="p-5"><Fact label="Evidence ready" value={watch!.evidenceReadyCount} /></div></Surface>
        <Surface><div className="p-5"><Fact label="Watch candidates" value={watch!.watchCandidateCount} /></div></Surface>
        <Surface><div className="p-5"><Fact label="Top-3 context only" value={watch!.top3EligibleCount} /></div></Surface>
        <Surface><div className="p-5"><Fact label="Current valid setups" value={watch!.validSetupCount} /></div></Surface>
      </div>
      <Surface><div className="p-6"><h2 className="text-lg font-semibold">Signal funnel by archetype</h2><p className="mt-1 text-sm text-[#637068]">Discovery is broad; actionability remains deliberately strict and is not inferred here.</p><div className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-4"><Fact label="Eligible market" value={watch!.eligibleCount} /><Fact label="Watch candidates" value={watch!.watchCandidateCount} /><Fact label="Policy-led" value={watch!.archetypeCounts.find(([name]) => name === 'POLICY_LED_INFLECTION')?.[1] ?? 0} /><Fact label="Turnaround" value={watch!.archetypeCounts.find(([name]) => name === 'TURNAROUND_INFLECTION_WATCH')?.[1] ?? 0} /><Fact label="Decision Score ready" value={watch!.decisionScoreReadyCount} /><Fact label="Valid setup" value={watch!.validSetupCount} /><Fact label="Six Gates evaluated / pass" value={`${watch!.sixGatesEvaluatedCount} / ${watch!.sixGatesPassCount}`} /><Fact label="Rotation challengers" value={watch!.rotationChallengerCount} /></div></div></Surface>
      <Surface><div className="overflow-x-auto p-6"><div className="mb-5 flex flex-wrap items-end justify-between gap-3"><div><h2 className="text-lg font-semibold">Archetype-routed candidates</h2><p className="mt-1 text-sm text-[#637068]">Quality, earnings, policy-led, turnaround, order-book, and risk evidence remain distinct from the Pre-Breakout policy.</p></div><StatusBadge status="WATCH_NOT_ACTIONABLE" /></div>{candidates.length ? <table className="w-full min-w-[1150px] text-left text-sm"><thead className="border-b border-[#e3e8e4] text-[10px] uppercase tracking-[.12em] text-[#829087]"><tr><th className="pb-2">Company</th><th className="pb-2">Archetypes</th><th className="pb-2">Policy / historical state</th><th className="pb-2">Decision Score</th><th className="pb-2">Setup / Gates</th><th className="pb-2">Comparison / blocker</th></tr></thead><tbody>{candidates.map((item) => <tr key={item.watchId} className="border-b border-[#edf0ee] align-top"><td className="py-4"><LinkToStock instrumentId={item.canonicalInstrumentId}>{item.symbol}</LinkToStock><p className="mt-1 text-xs text-[#637068]">{item.companyName || item.canonicalInstrumentId}</p></td><td className="py-4"><div className="flex max-w-xs flex-wrap gap-1">{item.archetypes.map((archetype) => <StatusBadge key={archetype} status={archetype} />)}</div><p className="mt-2"><StatusBadge status={item.status} /></p></td><td className="py-4"><StatusBadge status={item.policyMaturity || NOT_EXPOSED} /><p className="mt-1 text-xs text-[#637068]">Historical {item.historicalQualityState} · {item.currentInflectionState}</p></td><td className="py-4">{value(item.decisionScoreValue)}<p className="mt-1"><StatusBadge status={item.decisionScoreStatus} /></p></td><td className="py-4"><div className="flex flex-wrap gap-1"><StatusBadge status={item.setupState} /><StatusBadge status={item.sixGatesState} /></div><p className="mt-2 text-xs text-[#637068]">{item.setupPolicyRoutes.map(([archetype, route]) => `${archetype}: ${route}`).join('; ')}</p></td><td className="py-4 text-xs text-[#637068]"><StatusBadge status={item.comparisonReadiness} /><p className="mt-2">{item.blockerCodes[0] || 'No primary blocker exposed.'}</p></td></tr>)}</tbody></table> : <p className="text-sm text-[#637068]">No material Watch candidate is present in the latest immutable scan.</p>}</div></Surface>
      <div className="grid gap-4 lg:grid-cols-2"><Surface><div className="p-6"><h2 className="text-lg font-semibold">Archetype sections</h2><div className="mt-4 space-y-2 text-sm">{watch!.archetypeCounts.map(([archetype, count]) => <div key={archetype} className="flex justify-between border-b border-[#edf0ee] py-2"><span>{archetype}</span><span className="font-mono">{count}</span></div>)}</div><p className="mt-4 text-xs text-[#637068]">Unresolved: {watch!.unsupportedClassifications.join(', ')}</p></div></Surface><Surface><div className="p-6"><h2 className="text-lg font-semibold">Rotation funnel</h2><p className="mt-1 text-sm text-[#637068]">Comparison is read-only. Watch never authorizes ROTATE.</p><div className="mt-4 space-y-2 text-sm">{watch!.rotationFunnel.map(([reason, count]) => <div key={reason} className="flex justify-between border-b border-[#edf0ee] py-2"><span className="font-mono text-xs">{reason}</span><span className="font-mono">{count}</span></div>)}</div></div></Surface></div>
      <Surface>
        <div className="p-6">
          <h2 className="text-lg font-semibold">Evidence Domain Coverage</h2>
          <p className="mt-1 text-sm text-[#637068]">Coverage remains descriptive; it does not grant a Setup, score, Six Gates pass, or trading authority.</p>
          <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {watch!.evidenceReadinessCounts.map(([state, count]) => <Fact key={state} label={state} value={count} />)}
          </div>
          <div className="mt-4 grid gap-3 lg:grid-cols-2">
            <div><p className="text-xs font-semibold uppercase tracking-[.12em] text-[#829087]">Domain coverage</p>{watch!.evidenceDomainCounts.filter(([key]) => key.endsWith(':READY')).map(([key, count]) => <p key={key} className="mt-1 text-xs text-[#637068]">{key}: {count}</p>)}</div>
            <div><p className="text-xs font-semibold uppercase tracking-[.12em] text-[#829087]">Top blockers</p>{watch!.evidenceBlockerAttribution.slice().sort((a, b) => b[1] - a[1]).slice(0, 5).map(([key, count]) => <p key={key} className="mt-1 font-mono text-xs text-[#637068]">{key}: {count}</p>)}</div>
          </div>
          <div className="mt-4 space-y-3">
            {candidates.map((item) => <div key={item.watchId} className="flex flex-wrap items-center gap-3 border-b border-[#edf0ee] py-3"><LinkToStock instrumentId={item.canonicalInstrumentId}>{item.symbol}</LinkToStock><EvidenceDomainCoverage coverage={item.evidenceDomainCoverage} /><StatusBadge status={item.reliabilityState} /></div>)}
          </div>
        </div>
      </Surface>
    </>}</DataState>
  </div>;
};

const CandidateGroup: React.FC<{ title: string; detail: string; candidates: OpportunitySnapshotData['opportunities'] }> = ({ title, detail, candidates }) => <Surface><div className="p-6"><div className="flex flex-wrap items-end justify-between gap-2"><div><h2 className="text-lg font-semibold">{title}</h2><p className="mt-1 text-sm text-[#637068]">{detail}</p></div><span className="font-mono text-xs text-[#637068]">{candidates.length} items</span></div>{candidates.length ? <div className="mt-5 overflow-x-auto"><table className="w-full min-w-[650px] text-left text-sm"><thead className="border-b border-[#e3e8e4] text-[10px] uppercase tracking-[.12em] text-[#829087]"><tr><th className="pb-2">Symbol</th><th className="pb-2">Sector</th><th className="pb-2">Candidate state</th><th className="pb-2">Exact blocker codes</th></tr></thead><tbody>{candidates.map((item) => <tr key={`${item.symbol}-${item.sector}`} className="border-b border-[#edf0ee]"><td className="py-3 font-medium">{item.symbol}</td><td>{item.sector || NOT_EXPOSED}</td><td><StatusBadge status={item.candidateStatus} /></td><td className="font-mono text-xs text-[#637068]">{item.warnings.join(', ') || 'None exposed.'}</td></tr>)}</tbody></table></div> : <p className="mt-5 text-sm text-[#637068]">No item is currently in this backend state.</p>}</div></Surface>;

export const ProductionPortfolioPage: React.FC = () => {
  const { evidence } = useEvidence();
  const live = useLivePortfolio();
  const valuations = new Map<string, LivePortfolioData['holdings'][number]>((live?.data?.holdings ?? []).map((item) => [item.canonicalInstrumentId, item]));
  return <div className="space-y-7"><SectionTitle eyebrow="Portfolio Intelligence" title="Current canonical portfolio" detail="Canonical completed-session evidence remains separate from informational live-market observations. Cash stays UNKNOWN until HSI has a canonical value." /><div className="grid gap-4 sm:grid-cols-3"><Surface><div className="p-5"><Fact label="Cash" value={evidence.portfolio?.data?.cashStatus || NOT_EXPOSED} /></div></Surface><Surface><div className="p-5"><Fact label="Portfolio heat" value={value(evidence.portfolio?.data?.portfolioHeatScore)} /></div></Surface><Surface><div className="p-5"><Fact label="Live market" value={<StatusBadge status={live?.data?.health.health || live?.status || NOT_EXPOSED} />} /></div></Surface></div><DataState response={evidence.holdings}>{() => <Surface><div className="border-b border-[#e6ebe7] bg-[#f7faf8] p-5"><p className="text-[11px] font-semibold uppercase tracking-[.16em] text-[#668675]">Live Market</p><p className="mt-1 text-sm text-[#637068]">Live LTP and valuation are in-memory observations. They never overwrite canonical / completed-session evidence or decision policy.</p></div><div className="overflow-x-auto p-6"><table className="w-full min-w-[1240px] text-left text-sm"><thead className="border-b border-[#e3e8e4] text-[10px] uppercase tracking-[.12em] text-[#829087]"><tr><th className="pb-2">Holding</th><th className="pb-2">Quantity / average</th><th className="pb-2">Canonical value</th><th className="pb-2">Live LTP / freshness</th><th className="pb-2">Live value / P&amp;L</th><th className="pb-2">Decision Score</th><th className="pb-2">Evidence Coverage</th><th className="pb-2">Brain / setup</th></tr></thead><tbody>{evidence.holdings!.data!.map((holding) => { const envelope = evidence.envelopes[holding.instrumentId]?.data; const quote = valuations.get(holding.instrumentId); return <tr key={holding.instrumentId} className="border-b border-[#edf0ee] align-top"><td className="py-4"><LinkToStock instrumentId={holding.instrumentId}>{envelope?.symbol || holding.symbol || holding.instrumentId}</LinkToStock><p className="mt-1 font-mono text-[10px] text-[#829087]">{holding.instrumentId}</p></td><td className="py-4">{holding.quantity} / {holding.averagePrice}</td><td className="py-4">{value(holding.currentValue)}<p className="mt-1 text-xs text-[#829087]">{value(holding.unrealizedPnl)}</p></td><td className="py-4">{value(quote?.ltp)}<p className="mt-1"><StatusBadge status={quote?.state || NOT_EXPOSED} /></p><p className="mt-1 text-[10px] text-[#829087]">{when(quote?.receivedAt)}</p></td><td className="py-4">{value(quote?.marketValue)}<p className="mt-1 text-xs text-[#829087]">{value(quote?.unrealizedPnl)}</p>{quote?.blocker && <p className="mt-1 text-[10px] text-[#8a4c39]">{quote.blocker}</p>}</td><td className="py-4">{envelope ? <>{value(envelope.decisionScore.value)} <StatusBadge status={envelope.decisionScore.state} /></> : <StatusBadge status={evidence.envelopes[holding.instrumentId]?.status || NOT_EXPOSED} />}</td><td className="py-4">{envelope ? `${envelope.coverageCount} / ${envelope.coverageTotal}` : NOT_EXPOSED}</td><td className="py-4">{envelope ? <div className="flex flex-wrap gap-1"><StatusBadge status={envelope.sharedBrainState} /><StatusBadge status={envelope.setup.state} /></div> : NOT_EXPOSED}</td></tr>; })}</tbody></table></div></Surface>}</DataState></div>;
};

export const ProductionRotationPage: React.FC = () => {
  const { evidence } = useEvidence();
  const { client, refreshTrigger } = useDataClient();
  const [watchResponse, setWatchResponse] = useState<ApiResponse<MarketWideWatchData> | null>(null);
  useEffect(() => { let current = true; void client.getMarketWideWatch().then((item) => { if (current) setWatchResponse(item); }); return () => { current = false; }; }, [client, refreshTrigger]);
  const challengers = watchResponse?.data?.records.filter((item) => item.rotationChallengerState === 'CHALLENGER_WATCH_ONLY') ?? [];
  return (
    <div className="space-y-7">
      <SectionTitle eyebrow="Sell / Profit / Rotation" title="Governed portfolio decision support" detail="Watch challengers are read-only and cannot authorize ROTATE." />
      <DataState response={evidence.sellSide}>{() => (
        <Surface><div className="p-6"><div className="flex flex-wrap items-center justify-between gap-3"><div><h2 className="text-lg font-semibold">Current sell-side state</h2><p className="mt-1 text-sm text-[#637068]">Policy fingerprint: {evidence.sellSide!.data!.policyFingerprint}</p></div><StatusBadge status={evidence.sellSide!.data!.status} /></div>{evidence.sellSide!.data!.decisions.length ? <div className="mt-5 space-y-4">{evidence.sellSide!.data!.decisions.map((decision) => <div key={decision.holdingId} className="rounded-lg border border-[#e3e8e4] p-4"><div className="flex flex-wrap items-center justify-between gap-3"><p className="font-mono text-sm">{decision.holdingId}</p><StatusBadge status={decision.action} /></div><div className="mt-3 grid gap-3 sm:grid-cols-3"><Fact label="Thesis state" value={decision.thesisState} /><Fact label="Rotation state" value={decision.rotationState || NOT_EXPOSED} /><Fact label="Evidence freshness" value={decision.evidenceFreshness} /></div><details className="mt-3 text-xs text-[#637068]"><summary className="cursor-pointer font-medium">Why?</summary><Blockers values={[...decision.reasons, ...decision.blockers]} /></details></div>)}</div> : <p className="mt-5 text-sm text-[#637068]">No persisted sell-side decision is available. No rotation is forced.</p>}</div></Surface>
      )}</DataState>
      <DataState response={watchResponse}>{() => (
        <Surface><div className="overflow-x-auto p-6"><div className="flex flex-wrap items-end justify-between gap-3"><div><h2 className="text-lg font-semibold">Market Challenger Queue</h2><p className="mt-1 text-sm text-[#637068]">Comparison is read-only; existing rotation policy remains the sole authority.</p></div><StatusBadge status="WATCH_NOT_ACTIONABLE" /></div>{challengers.length ? <table className="mt-5 w-full min-w-[1100px] text-left text-sm"><thead className="border-b border-[#e3e8e4] text-[10px] uppercase tracking-[.12em] text-[#829087]"><tr><th className="pb-2">Challenger</th><th className="pb-2">Archetypes</th><th className="pb-2">Decision Score</th><th className="pb-2">Setup / Gates</th><th className="pb-2">Evidence Domain Coverage / reliability</th><th className="pb-2">Comparison / blocker</th></tr></thead><tbody>{challengers.map((item) => <tr key={item.watchId} className="border-b border-[#edf0ee] align-top"><td className="py-3"><LinkToStock instrumentId={item.canonicalInstrumentId}>{item.symbol}</LinkToStock><p className="mt-1 text-xs text-[#637068]">{item.sector || NOT_EXPOSED}</p></td><td className="py-3"><div className="flex flex-wrap gap-1">{item.archetypes.map((kind) => <StatusBadge key={kind} status={kind} />)}</div></td><td className="py-3">{value(item.decisionScoreValue)} <StatusBadge status={item.decisionScoreStatus} /></td><td className="py-3"><StatusBadge status={item.setupState} /> <StatusBadge status={item.sixGatesState} /></td><td className="py-3"><EvidenceDomainCoverage coverage={item.evidenceDomainCoverage} /><p className="mt-2"><StatusBadge status={item.reliabilityState} /></p></td><td className="py-3 text-xs text-[#637068]"><StatusBadge status={item.comparisonReadiness} /><p className="mt-2">{item.blockerCodes[0] || 'No rotation comparison is authorized.'}</p></td></tr>)}</tbody></table> : <p className="mt-5 text-sm text-[#637068]">No market challenger is currently exposed. No rotation is forced.</p>}</div></Surface>
      )}</DataState>
    </div>
  );
};

export const ProductionLivePage: React.FC = () => {
  const overview = useLiveOverview();
  const live = overview?.data;
  return <div className="space-y-7"><SectionTitle eyebrow="Live Monitor" title="Provider-neutral market observations" detail="Live data is informational only. It cannot overwrite completed-session technical evidence, Decision Score, Setup policy, or Six Gates." /><DataState response={overview}>{() => <><div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5"><Surface><div className="p-5"><Fact label="Connection" value={<StatusBadge status={live!.health.health} />} /></div></Surface><Surface><div className="p-5"><Fact label="Subscription" value={`${live!.health.subscribedTargets} / ${live!.health.requestedTargets}`} /></div></Surface><Surface><div className="p-5"><Fact label="Mapped / rejected packets" value={`${live!.health.mappedPackets} / ${live!.health.rejectedPackets}`} /></div></Surface><Surface><div className="p-5"><Fact label="Reconnects" value={live!.health.reconnectCount} /></div></Surface><Surface><div className="p-5"><Fact label="Last packet" value={when(live!.health.lastPacketAt)} /></div></Surface></div><Surface><div className="p-6"><div className="flex flex-wrap items-center justify-between gap-3"><div><h2 className="text-lg font-semibold">Governed mapped targets</h2><p className="mt-1 text-sm text-[#637068]">Backend-owned Dhan session; the browser receives only safe provider-neutral observations.</p></div><StatusBadge status={live!.health.state} /></div>{live!.targets.length ? <div className="mt-5 overflow-x-auto"><table className="w-full min-w-[720px] text-left text-sm"><thead className="border-b border-[#e3e8e4] text-[10px] uppercase tracking-[.12em] text-[#829087]"><tr><th className="pb-2">Instrument</th><th className="pb-2">Live LTP</th><th className="pb-2">Freshness</th><th className="pb-2">Last update</th><th className="pb-2">Exchange time</th></tr></thead><tbody>{live!.targets.map((target) => <tr key={target.canonicalInstrumentId} className="border-b border-[#edf0ee]"><td className="py-3">{target.symbol}<p className="mt-1 font-mono text-[10px] text-[#829087]">{target.canonicalInstrumentId}</p></td><td>{target.ltp}</td><td><StatusBadge status={target.freshness} /></td><td className="text-xs text-[#637068]">{when(target.receivedAt)}</td><td className="text-xs text-[#637068]">{when(target.providerTradeTimestamp)}</td></tr>)}</tbody></table></div> : <p className="mt-5 text-sm text-[#637068]">No current safe live quote is available. This does not alter canonical evidence status.</p>}</div></Surface><Surface><div className="p-6"><div className="flex flex-wrap items-center justify-between gap-3"><div><h2 className="text-lg font-semibold">Setup monitoring</h2><p className="mt-1 text-sm text-[#637068]">Exact persisted setup levels only. No near-entry threshold is invented here.</p></div><StatusBadge status={live!.setupState} /></div>{live!.setupMonitoring.length ? <div className="mt-5 overflow-x-auto"><table className="w-full min-w-[800px] text-left text-sm"><thead className="border-b border-[#e3e8e4] text-[10px] uppercase tracking-[.12em] text-[#829087]"><tr><th className="pb-2">Instrument</th><th className="pb-2">Entry</th><th className="pb-2">Stop</th><th className="pb-2">Target</th><th className="pb-2">Maximum entry</th><th className="pb-2">Observation</th></tr></thead><tbody>{live!.setupMonitoring.map((setup) => <tr key={setup.canonicalInstrumentId} className="border-b border-[#edf0ee]"><td className="py-3">{setup.symbol}</td><td>{value(setup.entry)}</td><td>{value(setup.stop)}</td><td>{value(setup.target)}</td><td>{value(setup.maximumEntry)}</td><td><StatusBadge status={setup.state} /></td></tr>)}</tbody></table></div> : <p className="mt-5 text-sm text-[#637068]">NO_ACTIVE_SETUP</p>}</div></Surface></>}</DataState></div>;
};

export const ProductionIntelligencePage: React.FC = () => {
  const { evidence } = useEvidence();
  return <div className="space-y-7"><SectionTitle eyebrow="Intelligence" title="HSI evidence feed" detail="A normalized research/news view. External Intelligence event semantics are shown only where the backend exposes them." /><DataState response={evidence.news}>{() => <div className="grid gap-4 lg:grid-cols-2">{evidence.news!.data!.items.map((item) => <Surface key={item.id}><div className="p-6"><div className="flex flex-wrap items-start justify-between gap-3"><div><p className="text-[10px] font-semibold uppercase tracking-[.14em] text-[#668675]">FACT</p><h2 className="mt-2 text-lg font-semibold">{item.title}</h2></div><StatusBadge status={item.eventCategory} /></div><p className="mt-3 text-sm leading-6 text-[#637068]">{item.catalystContext || 'No public-safe interpretation is exposed.'}</p><div className="mt-4 grid gap-2 border-t border-[#edf0ee] pt-3 text-xs text-[#637068]"><span>Source: {item.publisher}</span><span>Published: {when(item.timestamp)}</span><span>Affected sector: {item.sectors.join(', ') || NOT_EXPOSED}</span><span>Company exposure verification: {NOT_EXPOSED}</span><span>Reevaluation status: {NOT_EXPOSED}</span></div></div></Surface>)}{!evidence.news!.data!.items.length && <Surface><div className="p-6 text-sm text-[#637068]">No HSI intelligence evidence is currently exposed.</div></Surface>}</div>}</DataState></div>;
};

export const ProductionStocksPage: React.FC = () => {
  const { evidence } = useEvidence();
  return <div className="space-y-7"><SectionTitle eyebrow="Stock Intelligence" title="Choose a canonical instrument" detail="HSI fails closed on ambiguous aliases. Select a current canonical portfolio instrument or enter an exact canonical ID." /><Surface><div className="p-6"><p className="text-sm text-[#637068]">Current portfolio instruments</p><DataState response={evidence.holdings}>{() => <div className="mt-4 flex flex-wrap gap-2">{evidence.holdings!.data!.map((holding) => <LinkToStock key={holding.instrumentId} instrumentId={holding.instrumentId}>{holding.symbol || holding.instrumentId}</LinkToStock>)}</div>}</DataState><p className="mt-6 text-xs text-[#829087]">The stock-list endpoint does not publish canonical IDs, so symbol aliases are not silently resolved in the production UI.</p></div></Surface></div>;
};

export const ProductionStockDetailPage: React.FC<{ canonicalInstrumentId: string }> = ({ canonicalInstrumentId }) => {
  const { client, refreshTrigger } = useDataClient();
  const [input, setInput] = useState(canonicalInstrumentId);
  const [response, setResponse] = useState<ApiResponse<DecisionTrustEnvelopeData> | null>(null);
  const [liveResponse, setLiveResponse] = useState<ApiResponse<StockLiveMarketData> | null>(null);
  const canonical = canonicalInstrumentId.includes(':');
  useEffect(() => { setInput(canonicalInstrumentId); }, [canonicalInstrumentId]);
  useEffect(() => {
    let current = true;
    if (!canonical) { setResponse(null); return; }
    void client.getDecisionTrustEnvelope(canonicalInstrumentId).then((data) => { if (current) setResponse(data); });
    return () => { current = false; };
  }, [canonical, canonicalInstrumentId, client, refreshTrigger]);
  useEffect(() => {
    let current = true;
    if (!canonical) { setLiveResponse(null); return; }
    void client.getStockLiveMarket(canonicalInstrumentId).then((data) => { if (current) setLiveResponse(data); });
    return () => { current = false; };
  }, [canonical, canonicalInstrumentId, client, refreshTrigger]);
  const { navigate } = useNavigation();
  const envelope = response?.data || null;
  const live = liveResponse?.data || null;
  const search = <form onSubmit={(event) => { event.preventDefault(); if (input.includes(':')) navigate(`/stocks/${encodeURIComponent(input.trim())}`); }} className="flex gap-2"><label className="sr-only" htmlFor="canonical-id">Canonical instrument ID</label><input id="canonical-id" value={input} onChange={(event) => setInput(event.target.value)} placeholder="NSE:INE…" className="w-44 rounded-md border border-[#cfd8d1] bg-white px-3 py-2 font-mono text-xs outline-none focus:border-[#1e6550]" /><button className="rounded-md bg-[#173c31] px-3 py-2 text-xs font-semibold text-white"><Search className="h-4 w-4" /></button></form>;
  return <div className="space-y-7">
    <SectionTitle eyebrow="Stock Intelligence" title={envelope ? `${envelope.symbol} decision view` : 'Canonical stock analysis'} detail="Evidence-backed context, not a trading instruction." action={search} />
    {!canonical ? <Surface><div className="p-6"><StatusBadge status="IDENTITY_AMBIGUITY" /><p className="mt-3 text-sm text-[#637068]">Canonical identity is required. HSI will not resolve a legacy or ambiguous symbol alias in the frontend.</p></div></Surface> : (
      <><StockLivePanel live={live} response={liveResponse} />
      <DataState response={response}>
        {envelope && <>
          <Surface><div className="p-6 sm:p-8"><div className="flex flex-wrap items-start justify-between gap-4"><div><p className="font-mono text-xs text-[#668675]">{envelope.canonicalInstrumentId}</p><h2 className="mt-2 text-3xl font-semibold">{envelope.symbol}</h2><p className="mt-2 text-sm text-[#637068]">Intelligence as-of {when(envelope.intelligenceAsOf)} · Latest completed market session {when(envelope.latestCompletedMarketSession)}</p></div><div><p className="text-[10px] uppercase tracking-[.12em] text-[#829087]">Live price</p><p className="mt-1 text-2xl font-semibold">{value(live?.quote?.ltp)}</p><StatusBadge status={live?.quote?.freshness || live?.health.health || NOT_EXPOSED} /></div></div><div className="mt-7 border-t border-[#e6ebe7] pt-5"><EnvelopeSummary envelope={envelope} /></div></div></Surface>
          <div className="grid gap-4 lg:grid-cols-[1.25fr_.75fr]"><Surface><div className="p-6"><h2 className="text-lg font-semibold">Decision Summary</h2><div className="mt-5 grid gap-4 sm:grid-cols-2"><Fact label="Business Quality" value={<><StatusBadge status={domain(envelope, 'FUNDAMENTALS_EARNINGS')?.availability || NOT_EXPOSED} /> <span className="ml-2 text-xs">Fundamentals / earnings</span></>} /><Fact label="Opportunity Quality" value={<><StatusBadge status={envelope.decisionScore.state} /> <span className="ml-2 text-xs">Score + sector + setup evidence</span></>} /><Fact label="Execution Readiness" value={<><StatusBadge status={envelope.sixGates.state} /> <span className="ml-2 text-xs">Setup + Six Gates</span></>} /><Fact label="Reliability / Integrity" value={<StatusBadge status={domain(envelope, 'RELIABILITY_INTEGRITY')?.availability || NOT_EXPOSED} />} /></div></div></Surface><Surface><div className="p-6"><h2 className="text-lg font-semibold">What Changed</h2><p className="mt-3 text-sm leading-6 text-[#637068]">The current envelope is the exposed point-in-time evidence. A prior-envelope comparison read model is {NOT_EXPOSED}.</p><p className="mt-3 font-mono text-xs text-[#637068]">Fingerprint: {envelope.fingerprint}</p></div></Surface></div>
          <StockSections envelope={envelope} />
        </>}
      </DataState>
      </>
    )}
  </div>;
};

const StockLivePanel: React.FC<{ live: StockLiveMarketData | null; response: ApiResponse<StockLiveMarketData> | null }> = ({ live, response }) => <Surface><div className="p-6"><div className="flex flex-wrap items-center justify-between gap-3"><div><p className="text-[11px] font-semibold uppercase tracking-[.16em] text-[#668675]">Live Market</p><h2 className="mt-1 text-lg font-semibold">Backend-owned live observation</h2></div><StatusBadge status={live?.health.health || response?.status || NOT_EXPOSED} /></div>{live?.quote ? <div className="mt-5 grid gap-4 sm:grid-cols-4"><Fact label="LTP" value={live.quote.ltp} /><Fact label="Freshness" value={<StatusBadge status={live.quote.freshness} />} /><Fact label="Last packet" value={when(live.quote.receivedAt)} /><Fact label="Exchange time" value={when(live.quote.providerTradeTimestamp)} /></div> : <p className="mt-4 text-sm text-[#637068]">LIVE_VALUE_UNAVAILABLE — no fresh or stale in-memory quote is available for this exact canonical instrument.</p>}<p className="mt-4 text-xs text-[#829087]">This observation does not change the Decision Score, diagnostic evidence, Setup policy, Six Gates, or completed-session technical evidence.</p></div></Surface>;

const StockSections: React.FC<{ envelope: DecisionTrustEnvelopeData }> = ({ envelope }) => <div className="grid gap-4 lg:grid-cols-2"><Surface><div className="p-6"><h2 className="text-lg font-semibold">Business / Fundamental Intelligence</h2><div className="mt-4"><StatusBadge status={domain(envelope, 'FUNDAMENTALS_EARNINGS')?.availability || NOT_EXPOSED} /></div><p className="mt-3 text-sm text-[#637068]">Underlying financial evidence is available in the Trust Envelope domain matrix and audit references.</p></div></Surface><Surface><div className="p-6"><h2 className="text-lg font-semibold">Opportunity / Technical Intelligence</h2><div className="mt-4 flex flex-wrap gap-2"><StatusBadge status={domain(envelope, 'MARKET_TECHNICAL')?.availability || NOT_EXPOSED} /><StatusBadge status={domain(envelope, 'SECTOR_ROTATION')?.availability || NOT_EXPOSED} /></div><p className="mt-3 text-sm text-[#637068]">Sector rank and score-component detail are {NOT_EXPOSED} unless included in a backend artifact.</p></div></Surface><Surface className="lg:col-span-2"><div className="p-6"><h2 className="text-lg font-semibold">Setup</h2><SetupVisual envelope={envelope} /></div></Surface><Surface><div className="p-6"><h2 className="text-lg font-semibold">Thesis & Invalidation</h2><div className="mt-4 space-y-3"><Fact label="Trading thesis" value={envelope.thesis.tradingThesis || NOT_EXPOSED} /><Fact label="Investment thesis" value={envelope.thesis.investmentThesis || NOT_EXPOSED} /><Fact label="Invalidation" value={envelope.thesis.invalidationStatus || envelope.thesis.structuralInvalidation || NOT_EXPOSED} /></div></div></Surface><Surface><div className="p-6"><h2 className="text-lg font-semibold">Risks / Blockers</h2><div className="mt-4"><Blockers values={envelope.blockers} /></div></div></Surface><Surface><div className="p-6"><h2 className="text-lg font-semibold">Ownership / Institutional Evidence</h2><div className="mt-4"><StatusBadge status={domain(envelope, 'OWNERSHIP')?.availability || NOT_EXPOSED} /></div><p className="mt-3 text-sm text-[#637068]">Exact institutional contribution is {NOT_EXPOSED} in the current public read model.</p></div></Surface><Surface><div className="p-6"><h2 className="text-lg font-semibold">News / Catalysts</h2><div className="mt-4"><StatusBadge status={domain(envelope, 'EXTERNAL_INTELLIGENCE_NEWS')?.availability || NOT_EXPOSED} /></div><p className="mt-3 text-sm text-[#637068]">Canonical company event detail is {NOT_EXPOSED} in the current stock read model.</p></div></Surface><Surface className="lg:col-span-2"><details className="p-6"><summary className="cursor-pointer text-lg font-semibold">Full Evidence / Audit</summary><div className="mt-5 grid gap-3 sm:grid-cols-2">{envelope.domains.map((item) => <div key={item.domain} className="rounded-md border border-[#e3e8e4] p-3"><div className="flex items-center justify-between gap-2"><span className="text-xs font-medium">{item.domain}</span><StatusBadge status={item.availability} /></div><p className="mt-2 font-mono text-[10px] text-[#637068]">{item.freshness} · {when(item.evidenceAsOf)}</p><p className="mt-2 break-words font-mono text-[10px] text-[#829087]">{item.artifactIds.join(', ') || NOT_EXPOSED}</p></div>)}</div></details></Surface></div>;

const SetupVisual: React.FC<{ envelope: DecisionTrustEnvelopeData }> = ({ envelope }) => {
  const setup = envelope.setup;
  if (!setup.setupId) return <div className="mt-4 rounded-lg border border-dashed border-[#d4ddd6] bg-[#f7faf8] p-5"><p className="font-semibold text-[#26362e]">NO CURRENT SETUP</p><p className="mt-2 text-sm text-[#637068]">{setup.blockers.join(', ') || envelope.blockers.join(', ') || 'No current setup is exposed.'}</p></div>;
  const levels = [
    ['Extended Target', setup.extendedTarget], ['T2', setup.target2], ['T1', setup.target1], ['E_max / DO NOT CHASE', setup.maximumExecutableEntry], ['Entry / Trigger', setup.entry], ['Current Price', envelope.liveMarket.ltp], ['SL / Structural Invalidation', setup.structuralInvalidation],
  ].filter(([, amount]) => amount !== null) as Array<[string, string]>;
  return <div className="mt-5 rounded-lg border border-[#d7e0d9] bg-[#f8fbf8] p-5"><div className="space-y-2">{levels.map(([label, amount], index) => <div key={label} className="flex items-center gap-3"><span className="w-40 shrink-0 text-xs font-medium text-[#526058]">{label}</span><span className="h-px flex-1 bg-[#a8bdb0]" /><span className={`w-28 text-right font-mono text-sm ${index === levels.length - 1 ? 'text-[#8a4c39]' : 'text-[#173c31]'}`}>₹ {amount}</span></div>)}</div><div className="mt-4 flex flex-wrap gap-3 border-t border-[#dfe6e0] pt-3"><StatusBadge status={setup.state} /><span className="text-xs text-[#637068]">Setup as-of {when(setup.setupAsOf)} · {setup.setupType || NOT_EXPOSED}</span></div></div>;
};
