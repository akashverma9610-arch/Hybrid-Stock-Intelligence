# Old HSI — Canonical 61 + 35 Lens Operationalization Execution Plan

Status: IMPLEMENTATION_IN_PROGRESS / NO_LIVE_SOURCE_CERTIFICATION / NO_POLICY_ACTIVATION
Scope: Old Hybrid-Stock-Intelligence only. Reviewed: Canonical 61 operational coverage audit, financial comparability closure, 35-lens crosswalk, existing canonical lens binding, shared market scan and canonical input requirements.

## Evidence: do not confuse implemented evaluators with operational all-NSE inputs

Historical accepted diagnostic coverage audit at 2026-09-10: universe 2,553, technical certified scope 2,538, Rule 4 daily/weekly 1,940 ready, Rule 5 2,007 ready, Rule 10 2,439 ready; aligned sector Rule 2/3 354, Rule 6 peer cohorts zero, prospective 15m bars zero, Rule 35 named VWAP semantics unavailable, Rule 57 event evidence unavailable. 4,067 financial facts and 362 filings cover only 31 companies. Direct EBITDA/EBIT/CAPEX/debt/share-count inputs had zero records in that audit. Financial comparability follow-up found zero fully certified inputs among 31 companies for rules 16/17/18/19/20/24/25/26/29; Rules 24/25 had partial prospectively replayable inputs for 18 companies and historical usable was zero. These are historical evidence, NOT current measurements.

Existing `app/lens_knowledge/assessment.py` always returns UNKNOWN fit; existing canonical coverage is isolated/current-descriptive and does not establish live data readiness. New `readiness_planner.py` is planning-only; certification states must come from actual owner checks, never invented from an eligible diagnostic row.

## Required source families and owning contracts

1. **NSE instrument master / listing/taxonomy** — full eligible denominator, NSE:ISIN exact identity, membership effective dates and exclusions. Existing `app.universe_analysis`, `app.taxonomy`, historical security master.
2. **Price/volume/history** — completed EOD OHLCV; raw/adjusted basis, splits/rights and 5m/15m/1h/4h where required. Existing NSE UDiFF, native binding and historical stores. Explicitly certify actual available windows, no synthesized bars.
3. **Benchmarks and sectors** — point-in-time Nifty 50/500, official sector indices, aligned return windows, current constituent membership and peer cohorts. No guessed sector mapping.
4. **Corporate financial statements** — consolidated/standalone, fiscal period basis, units/currency, publication/receipt/revisions, full year and quarter-only separation, cash flow, debt, balance joins, EBITDA/EBIT and share metrics where directly authoritative. Reuse existing `app.fundamentals` fact/vintage/materialization owner.
5. **Ownership, delivery, trade microstructure** — official institutional category shareholding histories, delivery ratios, market/volume liquidity and actual exitability evidence. Institutional activity inferred from price-volume is only proxy.
6. **Company events and external evidence** — dated primary filings/results, verified order book/capex, awards, contracts, new products, promoter/corporate actions, policy events and exact company exposure. Deduplicate identical event IDs across media.
7. **Market/macro and market stress** — relevant regime/breadth, commodity exposure, weak-market and persistence definitions with tested source timelines.
8. **Governance & normative policy** — exact technical pattern geometry, investment-quality, valuations, event materiality, expiry, setup timeframes, risk and gates; preserve existing V1 ownership. Approvals cannot be manufactured by a data import.

## Dependency priority / work packages

P0 A. Run latest local read-only audit and baseline regression. Compare local vs GitHub commits, code flags, stock denominator and database source watermarks. Freeze source and policy version.
P0 B. Build a per-(instrument, rule, as_of, input-vintage) certification ledger from existing `DIAGNOSTIC_INPUT_REQUIREMENTS` and audited named-evidence contracts. No new 61-rule formulas. Outputs: READY/PARTIAL/MISSING/STALE/CONFLICTED/POLICY_BLOCKED plus exact blocking inputs and counts by universe.
P0 C. Build a per-(instrument, lens, as_of) readiness view over the pinned 35x10 matrix and all 21 G01–G21 labels. New `app.lens_knowledge.readiness_planner` is the initial fail-closed pure planner; bind only verified owner certificates to it.
P1 D. Repair official daily/weekly/multi-timeframe history and sector membership joins; certify technical/sector rules including rule 6 peer cohorts, named rule 35 data and strict PIT replay.
P1 E. Expand factual NSE/BSE/issuer financial coverage from 31 historical companies toward entire eligible population; normalize statement facts with authoritative basis; repair per-rule financial input sufficiency and company-type applicability; do not approximate EBITDA/debt.
P1 F. Establish official delivered volume, ownership changes, orderbook/capex, news event company exposure and source timestamps. Repair rule 57 source-level event relation and dependent named lens evidence.
P1 G. Establish approved G01–G21 evidence/policy contracts individually. Some are sourcing tasks (e.g., G07/G20), others governance tasks (G04/G06/G10); do not equate data to policy.
P1 H. Build lens-fit evaluators per strategy/archetype with formal positive/negative/inconclusive outcome and falsifying evidence. Shadow-test first; one versioned interface, no duplicate scoring.
P1 I. Wire canonical stored feature materialization + immutable candidate union -> existing Shared Brain, canonical diagnostics/score/confidence/gates -> read-only portfolio and UI; preserve `hsi_scan_market` compatibility.
P2 J. Pilot with sector/financial/event/technical examples; cross-sectional coverage, strict historical replay, performance profiling and continuous future capture. After signed regression and provenance parity, retire duplicated implementations, never old audit records.

## Safe scheduling
- End-of-day after completed official session: daily price bars + benchmark/sector refresh, certification, feature invalidation, then bounded discovery.
- Intraday when available and licensed: bars and verified event deltas, selective recompute of only dependent timeframes/lenses; a quote does not certify OHLCV or delivery.
- Filing/event arrival: ingest exact document/version, update company-specific evidence and affected lens readiness.
- Quarterly financial/shareholding: official publication/receipt-aware refresh and per-company incremental recompute.
- Nightly: read-only completeness, gap aging, source failures, conflict queue and audit artifacts.
No scheduler should activate without certified provider and storage access; UI/API reads never trigger acquisitions.

## Acceptance gates

GATE-D61: For every Rule D01–D61 publish current tested input owner, exact named source contract, instrument denominator, eligible/partial/unavailable counts, as-of, source freshness and anti-lookahead. No unreported gaps.
GATE-L35: For every lens, publish all PRIMARY, OPTIONAL and CONFIRMATION diagnostic references, named evidence, 21 gap references, time horizon, applicability, known-at/freshness, activation policy and positive/negative/inconclusive shadow fixtures.
GATE-CACHE: Same canonical feature requested by multiple rules/lenses derives once per compatible input fingerprint/policy/cutoff; changes invalidate selectively.
GATE-FLOW: 2+ lens matches on the same NSE:ISIN yield one candidate, with full origin lineage and independent Brain/gate authority.
GATE-OPS: Background source jobs achieve prescribed timeliness and availability over sufficient market sessions; backup/restore, retry, replay, error containment tested.
GATE-PRODUCT: Consumer UI shows truthful denominators, per-rule/lens blocked explanations, rejects unsupported readiness and does not issue orders.

## Explicit owner questions / outside-code dependencies
- Which authoritative and licensed sources are available to pull full NSE company filings/financials, shareholding, official delivery and corporate-action history on the required cadence? Prefer existing connected NSE/BSE ingestion paths; human must authorize providers, logins, paid licenses and credentials where needed.
- Is the required initial coverage EOD + daily/weekly research or also production intraday 5m/15m/1h/4h? The latter requires sufficient bars/provider budget and temporal tests.
- How should new lens policies be validated/promoted? Default: research shadow only until backtesting and explicit owner approval.
- What disk, memory and scheduled-runtime availability exist on the Windows laptop? Determine DB/storage choice after benchmarking, not from guessed size.

## Current implementation receipt

`app/lens_knowledge/readiness_planner.py` and `tests/test_lens_readiness_planner.py` added to main as fail-closed planning and unit-test code. No tools executed the test suite in this connector session; no database migration, live refresh, approvals, activation, deletions or runtime source repair have occurred. Do not claim 61 diagnostic or 35 lens operational completion from this plan.
