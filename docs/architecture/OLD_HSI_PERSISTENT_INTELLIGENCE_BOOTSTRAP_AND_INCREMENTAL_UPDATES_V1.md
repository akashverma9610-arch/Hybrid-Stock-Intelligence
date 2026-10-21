# Old HSI — Persistent Internal Stock Intelligence and Incremental Refresh Architecture V1

Status: OWNER_ARCHITECTURE_DECISION / DOCUMENTED_ONLY / IMPLEMENTATION_NOT_COMPLETE
Authority: Old Hybrid-Stock-Intelligence. Complements OLD_HSI_DATABASE_FIRST_DISCOVERY_CONSOLIDATION_PLAN.md and OLD_HSI_EOD_FIRST_OPERATIONALIZATION_SCOPE_V1.md. Does not alter existing governance, six gates, scoring formulas or live state.

## Owner decision

On first installation/bootstrap, HSI should progressively acquire and persist the available required structured evidence for **all eligible NSE equities** in its own internal canonical database. It should certify sources, then derive durable reusable calculation products, diagnostic outputs and 35 lens dependency/readiness/fit records only when their respective evidence and policy requirements are met. Every later verified source revision or event should incrementally update only the affected feature/diagnostic/lens/stock intelligence nodes.

Candidate discovery should search and rank the **internal stock intelligence index and canonical internal NSE security master**. There is no separately acquired or re-created external NSE universe and no repeated provider-driven per-funnel scan. The internal NSE eligibility/instrument master is nevertheless mandatory and must be updated for listings/delistings, ISIN changes, symbol events, status, sector/membership histories and coverage denominator. Market-wide internal evaluations remain resumable and coverage-aware. Initial bootstrap can be partial; never call missing data ready.

## Persisted layers (one database authority; physically normalized collections/tables allowed)

0. `instrument_master`: canonical NSE:ISIN identity, effective-dated eligibility, corporate identities, sector mappings, symbols, lifecycle.
1. `source_evidence`: immutable source-versioned EOD OHLCV, disclosure, financial facts, cash flow, shareholding, official delivery/volume, sector/benchmark index, macro/policy and news/event facts, timestamps and exact source fingerprints.
2. `data_certification`: source identity, period/calendar completeness, PIT availability/known-at, financial period/basis/unit comparisons, corporate-action adjustment, data freshness, conflict and missing reasons.
3. `derived_feature`: keyed by security or market/sector, timeframe (1D/1W/1M first), evaluation cutoff, source-vintage fingerprint, calculation owner/version and adjustment basis. Includes technical indicators, returns, relative strength, financial ratios, normalized fundamental series, valuation/liquidity etc. Prefer content-addressed shared outputs, not duplicate lens-specific computations.
4. `diagnostic_result`: canonical D01–D61 outputs and eligibility states, named input proofs, calculation policy, version and artifact fingerprint; no new registry.
5. `lens_assessment`: 35 definitions and each security's readiness, policy state, verified lens-fit status, thesis reasons, constraints and source evidence lineage; never infer MATCH from eligible diagnostics alone. Preserve 21 missing-gap labels G01–G21 until resolved.
6. `stock_intelligence_snapshot`: per canonical security and explicit as-of, small summary/reference set of verified facts, regime/sector, quality, technical/financial valuation, catalyst/thesis, contradictions, missing-domain flags, current accepted feature+diagnostic+lens versions. Distilled record must point to details rather than copy all raw evidence.
7. `discovery_index`: queryable internal feature predicates, latest certified lens matches and typed facets, one candidate identity per security, all match reasons and per-domain completeness; no separate full-NSE external funnel, no second scoring engine.
8. `refresh_manifest`: incremental job checkpoints, affected dependencies, source watermarks, idempotency fingerprint, retry/quarantine and observability. Strict historical snapshots remain queryable.

All these are *logical* schema layers; reconcile against actual existing HSI DB tables before migrating anything. Preserve existing repository/data owners and immutable historical evidence; no giant one-column object, no LLM memory as primary fact store.

## First-time bootstrap stages

B0. Verify and back up actual local DB; baseline all migrations/tests; pin code policy and source approvals.
B1. Build exact official NSE eligible instrument master internally; maintain effective-time membership. Do not assume historical 2553 population is today's exact denominator.
B2. Ingest available historical Daily OHLCV, indices, sector/taxonomy and corporate actions with license-compliant official source APIs/files and throttled checkpointing. Treat unavailable sessions/conflicts as such.
B3. From certified Daily evidence derive Weekly; add canonical Monthly interval and month-complete derived artifacts with official trading-session calendar, adjustment/known-at/fingerprint checks. No made-up source-available timestamps.
B4. Acquire historical issuer financials/filings, orders/capex, delivery, ownership and macro/events as available; tag partial coverage per stock, source, fiscal basis and publication time.
B5. Build durable source certifications, then compute shared features, all applicable D01–D61 results where supported, and per-lens readiness. Do NOT mark entire 61/35 ready based on a partial input population.
B6. Populate stock intelligence and internal discovery index. Index query produces same single canonical stock identity across multiple lenses. Governed Brain/score/gates remain separate stage and independent of lens match.
B7. Verify total source counts, current/stale/absent evidence, historical PIT replay, cost, API/UI binding, and go-live constraints. Bootstrap complete is not data-complete; all current blockers are explicit.

## Incremental event processing (no universal recalc)

Official daily completed session -> upsert source version + certify -> recompute affected instrument's 1D feature descendants and any completed 1W/1M periods -> D61 dependencies -> lens readiness and fit -> stock intelligence -> discovery snapshot.

Filing/result/earnings revision -> ingest with exact issuer, fiscal scope, period start/end, publication/receipt/version -> update matching financial/valuation features -> downstream diagnostics and relevant lens families only.

Verified order/catalyst/policy news -> normalize one event identity; deduplicate exact/semantically equivalent reports preserving provenance; verify issuer exposure, effective time/materiality and contradiction -> recompute affected catalyst, thesis and sector/stock dependencies; **no** automatic buy/sell.

Corporate action / symbol or ISIN change -> certify security lineage, market series and adjustment basis -> invalidate all affected historical feature windows and descendants; do not overwrite historical immutable facts.

Sector mapping/regime revision -> recompute shared sector/benchmark node once, then only its downstream affected securities and lenses.

Governance/diagnostic/lens-definition version changed -> invalidate all affected compatible results by content-addressed version dependency, without changing unrelated facts.

## Dependency execution identity and safety

Use a DAG of canonical feature owners. Store each dependency edge `producer_record_fingerprint -> consumer_versioned_artifact` or equivalent manifest, and input vector fingerprint for caching. Idempotent job key = owner + target + timeframe + evaluation cutoff + input fingerprint + code/policy version. If inputs unchanged, reuse old output; if changed, generate a new version and retain old one; if source availability conflicted, quarantine/flag rather than publishing readiness. Watermarks must distinguish the latest observed market time from source publication/received/known-at. Do not use future records in historical replay.

A published stock index is a materialized read model, not authority to override underlying evidence. Query at an explicit as-of and respect incomplete market coverage; fast search must not silently exclude stocks without the requested data. Store the small intelligence summary and refer to original evidence records, keeping disk usage and index efficiency manageable. Authentication, backups, retention, licensing, job failure recovery, source rate limits, disk budget and operational health remain deployment gates.

## Timetable and scope

Phase 1: **1D, 1W, 1M** market evidence and parallel eligible fundamental/event sources.
Phase 2: certified D61 source readiness, L35 named evidence and shadow fit, internal index and SenseEdge.
Phase 3: deferred **5m/15m/1h/4h** without refactoring the stock index or duplicate first-run bootstrap.

News and catalysts may be detected by allowed controlled source acquisition workers. The candidate *search* itself is internal-only. Do not claim exchange/issuer records can all be fetched by an unlicensed API or that all NSE companies have ten years of every type of history. Some sources may not exist or require permissions.

## Acceptance tests / proof

1. Bootstrap restart resumes from checkpoints without duplicate records or repeating completed expensive derivations.
2. For one NSE:ISIN matching five lens labels, exactly one discovery entry retains five distinct certified evidence reasons.
3. Reapplying identical official file/event is idempotent and preserves original publication/received timestamps.
4. A new quarterly result changes only affected company financial descendants; unaffected symbols' feature fingerprints remain constant.
5. A sector-wide update changes one shared sector node and precisely its dependent stock/lens results.
6. Corporate action changes invalidate impacted 1D/1W/1M windows, not unrelated companies.
7. Strict historical cutoff cannot retrieve later known-at revisions; current-descriptive backfills cannot be represented as originally available in that historical period.
8. All D01–D61 and all L35 publish real readiness/blocked coverage per source/timeframe; missing input is never silent negative fit.
9. Query internal DB while providers are offline still produces last-captured certified results clearly labeled with their as-of/freshness.
10. API request never initiates network acquisition or independent whole-universe funnel; no order execution or portfolio mutation.
11. All stored secrets absent from data snapshots and Git; robust backups, restore and basic storage performance measured.

## Existing code ownership and work remaining

Reuse `app.universe_analysis` for canonical universe and diagnostics, `app.data_coverage` for readiness, `app.fundamentals`, `app.market_data`, `app.lens_knowledge`, `app.intelligence.shared_market_scan` for compatible read models. Existing process-local shared market scan snapshots are not a permanent cross-restart stock intelligence index; persistent index implementation is outstanding. Technical 1M enum/storage and producer are missing. The 35-lens planner remains fail-closed planning only. Existing 61 evaluator count does not indicate all-source readiness. This commit is documentation of owner direction, not claim of completed bootstrap or migration.
