# Old HSI — Database-First Discovery Consolidation (implementation plan)

Status: DESIGN_RECOrD / IMPLEMENTATION_NOT_ACTIVE / NO_POLICY_CHANGE
Scope: Hybrid-Stock-Intelligence repository only. This document neither activates discovery nor deprecates existing code.

## Decision
The authoritative candidate population is the eligible NSE main-board equity snapshot built from the internal canonical instrument master. Structured, source-attributed data is ingested centrally and incrementally. Discovery must read only frozen, point-in-time-eligible internal records. It must not initiate provider calls, per-funnel acquisition, per-funnel recomputation of identical indicators, or competing candidate stores.

Existing `app.universe_analysis` owns canonical universe/evidence/Canonical61/Decision Score pathways; existing `app.intelligence.multi_funnel_orchestration` and its five adapters already read retained source records and union exact-security leads. Reuse these, do not recreate their algorithms or change scoring weights or gate policy.

## Required logical flow

Approved source acquisition (separate jobs)
 -> canonical identity, PIT, freshness, corporate-action and conflict certification
 -> versioned structured internal data stores
 -> one reusable derived-feature materialization per (instrument, as_of, timeframe, input fingerprint, model/policy version)
 -> one frozen NSE universe snapshot
 -> one central DB-only discovery evaluation over all eligible instruments
 -> criterion/lens/funnel *labels* over shared features and stored evidence
 -> one exact-security deduplicated candidate pool (retain all distinct qualifying reasons and lineages)
 -> one existing Shared Brain evidence assembly / Canonical61 / Decision Score / confidence / setup / six-gates handoff
 -> governed read-only opportunity and portfolio comparison projections
 -> API / UI.

Funnel labels are views over canonical results, not independent provider pipelines. Context-bound holding/watchlist/event/regime routes remain scoped and cannot be claimed to examine every listed security.

## Duplication retirement matrix
1. Provider reads from any discovery/diagnostic/funnel path: prohibited; route to centralized ingestion jobs.
2. Repeat feature calculations (RS, technical, valuation, liquidity etc.) per label: replace with immutable feature cache; fingerprint and version keyed; never reuse across an incompatible as-of/adjustment basis.
3. Funnel-specific broad NSE scans: replace with a single bound NSE universe evaluation; share one per-instrument result across criteria.
4. Multiple candidate queues/stores: route through existing exact-security union; preserve source origins, evidence and reason codes.
5. Duplicate Brain/scoring/gates implementations: prohibited; call existing canonical implementations once per immutable evaluation version.
6. Frontend-triggered scan/provider acquisition: prohibited; UI reads persisted snapshots and explicit coverage state.

## Guardrails
- Missing, stale, conflicted, unsupported, policy-blocked or unqualified inputs stay explicitly distinguishable. No imputation or score promotion.
- Store both derived feature version and exact upstream input fingerprints. Incremental recomputation only when dependent evidence/version changes.
- All NSE coverage claims must be supported by snapshot membership and per-instrument readiness. Partial means PARTIAL, not best-in-market.
- Do not change Core V1 policy/61-rule identity/score weights/Gate V1, activate Gate V2, enable trading or mutate portfolio.
- Existing discovery union currently stops before Brain. The production evidence assembler and downstream handoff are missing; this design does not claim they work.
- Keep existing fourteen funnel names as optional typed detection facets and explicit context-specific statuses; no duplicate source engines.

## Staged implementation and acceptance
A. Inventory every producer, consumer and stored feature key; identify duplicate codepaths with call-site and job evidence.
B. Build/verify one indexed canonical structured read facade over existing stores; one frozen snapshot with as-of and coverage manifest.
C. Add derived-feature memoization with deterministic keys and invalidation; unit-test identical repeated criteria require only one calculation.
D. Migrate each funnel's qualifying predicate to shared read-only features; compare prior and new decisions on frozen fixtures; maintain old fail-closed statuses where policy absent.
E. Bind exact-security candidate union to existing Shared Brain through one concrete, PIT-safe evidence assembler; assert exactly-once per candidate-and-version evaluation (idempotent retries).
F. Persist one governed output snapshot and provide read-only UI; prove no HTTP read performs scanning or acquisition.
G. Shadow-run old/new against same frozen data; diff population, origin lineage, labels, scores, gates, costs and latency. Retire duplicate implementations only after parity and regression sign-off.

## Minimum regression requirements
- 2+ funnels matching one ISIN -> one candidate, all distinct origin reasons retained.
- Unchanged features requested by 3 labels -> one underlying derivation.
- Changed financial filing, corporate action or model version -> correct selective invalidation.
- Historical PIT replay cannot see future news, bars or constituents.
- Same frozen input -> same ordered output and fingerprints.
- Missing mandatory data blocks promotion but does not fabricate a negative result.
- Contextual funnels do not accidentally become full-universe security scanners.
- No provider/network calls and no broker/portfolio mutation inside discovery.
- Existing V1 paths remain unchanged until shadow parity passes.

## Out of scope / unresolved
Current database source coverage, performance, historical PIT sufficiency, provider licensing, production schedule and local unpushed changes have not been verified here. No percentage of runtime duplication removed can be asserted without profiling and a passing full regression suite.
