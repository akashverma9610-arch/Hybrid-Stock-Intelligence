# Old HSI — 35 Lens Roles and Data Readiness Architecture V1

Status: DESIGN_APPROVED_BY_OWNER / IMPLEMENTATION_NOT_ACTIVE / NO_POLICY_ACTIVATION
Repository: Hybrid-Stock-Intelligence only.
Companion: OLD_HSI_DATABASE_FIRST_DISCOVERY_CONSOLIDATION_PLAN.md

## Decision

All eligible NSE main-board equities enter a canonical, versioned, PIT-consistent internal data platform. Existing centrally calculated features and canonical 61 diagnostic outputs are reused. Thirty-five lenses are typed thesis/detection consumers over this evidence, not 35 data collectors, 35 independent whole-market scans, 35 scoring engines, or a replacement Shared Brain. The result of each lens is distinct from the existing Decision Score, confidence, governed setups, Six Gates and portfolio rotation authorization.

Preserve existing `app/lens_knowledge` draft taxonomy and matrix, `app/universe_analysis` calculation ownership, `app/intelligence/shared_market_scan.py` and `hsi_scan_market` API current consumer, as well as exact existing opportunity origins. Avoid removing active routes before parity. This proposal defines future role and readiness contracts, not a claim that current draft coverage assessments establish lens applicability or operational readiness.

## Six logical research families and all 35 exact identifiers

These are presentation and scheduling families, not policy/version aliases:

1. Technical & Market Structure: PRE_BREAKOUT_ACCUMULATION; CONFIRMED_BREAKOUT; BREAKOUT_RETEST; INSTITUTIONAL_ACCUMULATION; SECTOR_ROTATION_LEADER; MARKET_RED_RESILIENCE.
   Responsibility: inspect canonical price-volume, technical, relative strength, breadth and sector evidence. Institutional accumulation must remain a price/volume PROXY; actual institutional ownership cannot be inferred without verified identity.
2. Growth, Earnings & Fundamental Change: EARNINGS_MOMENTUM; EARNINGS_SURPRISE_POST_RESULT_DRIFT; FUNDAMENTAL_INFLECTION; CASH_FLOW_INFLECTION; MARGIN_EXPANSION; CAPACITY_EXPANSION; NEW_PRODUCT_NEW_CUSTOMER_INFLECTION; MARKET_SHARE_GAINER; EXPORT_SCALING.
   Responsibility: source-comparable financial growth/acceleration, cash conversion, expansion, and verified event/result impact; any surprise baseline and reaction window need separate approved semantics.
3. Compounders & Quality: LONG_TERM_STRUCTURAL_COMPOUNDER; MID_TERM_COMPOUNDER; EARLY_EMERGING_LEADER_SMALL_MIDCAP; GARP; QARP.
   Responsibility: longevity, business quality, growth and valuation fit; no multibagger probability without tested calibration.
4. Valuation, Recovery & Balance Sheet: DEEP_VALUE_MEAN_REVERSION; RERATING_CANDIDATE; CYCLICAL_RECOVERY; TURNAROUND_RECOVERY; DELEVERAGING.
   Responsibility: compatible historical valuation, financial repair and balance-sheet improvement; no price-target promotion without policy approval.
5. Macro, Industry & Strategic Opportunities: COMMODITY_UPCYCLE; DOMESTIC_CAPEX_BENEFICIARY; ORDER_BOOK_CAPEX_CYCLE; IMPORT_SUBSTITUTION; POLICY_REGULATORY_BENEFICIARY.
   Responsibility: transmission from verified economy/industry/capex/policy to exact company exposure; theme membership alone is not beneficiary proof.
6. Events, Corporate Change & Special Situations: EVENT_CATALYST; SPECIAL_SITUATION; DEMERGER_VALUE_UNLOCK; ASSET_MONETISATION; PROMOTER_MANAGEMENT_TRANSFORMATION.
   Responsibility: unique dated source events, economic materiality, supersession and company linkage; news repetitions do not multiply event weight.

## Each lens has one typed, versioned contract

- `lens_id`, `family`, immutable `definition_version`, governed `policy_ref`, explicit `activation_status`.
- `universe_scope`, `instrument_applicability`, `timeframe/horizon`, `as_of`, calendar/corporate-action adjustment basis.
- `required_diagnostic_ids`, `optional_diagnostic_ids`, `confirmation_diagnostic_ids` resolved from the existing 35-by-10 matrix and canonical D01–D61. Design references ARE NOT sufficient policy approval.
- `required_named_evidence`: financial comparable periods, official delivery, event identity, capex/order book, company exposure, and other evidence that cannot be replaced by a generic diagnostic.
- `freshness_policy_ref` per domain; numeric TTLs are NOT assigned by this document.
- `readiness_result`, `lens_fit_result`, `contradicting_evidence`, `reason_codes`, exact input fingerprints, selected domain/vintage and proof of PIT visibility.
- `output`: one immutable per-security per-lens assessment with eligible match, non-match, missing/blocked and inconclusive distinct; no order or portfolio mutation.

## Readiness assessment: two separate axes

A. DATA/INPUT readiness: READY, PARTIAL, MISSING, STALE, CONFLICTED, POLICY_BLOCKED, NOT_APPLICABLE, UNSUPPORTED. Treat source identity/known-at, adjustment basis, history depth, temporal alignment and named evidence as separate domain checks. A diagnostic READY does not imply named business evidence READY.
B. LENS ACTIVATION: DESIGN_ONLY, RESEARCH_SHADOW, VALIDATED, APPROVED_NOT_ACTIVE, ACTIVE_READ_ONLY. Exact governance approves transition. Never auto-promote because diagnostics exist.
C. LENS FIT: NOT_EVALUATED, MATCH, NO_MATCH, INCONCLUSIVE. Determine only when the lens policy is approved for evaluation and every mandatory evidence item is ready. Otherwise retain unavailable/partial without interpreting missing data as NO_MATCH.

A lens is data-ready only if all policy-required inputs are certified at the same explicit eligible cutoff, with matching canonical instrument identity, compatible reference windows, sources, financial basis and historical known-at. Optional/confirmatory missing values remain reported and may lower completeness; they never fabricate required evidence.

## Canonical dependency gaps that must be resolved before lens activation

The existing crosswalk records 21 unresolved exact labels, G01–G21. Preserve all:
G01 PIT_financial_scope_and_cash_comparability
G02 PIT_sector_breadth_and_mapping
G03 actual_exitability_liquidity_policy
G04 approved_business_quality_policy
G05 comparable_earnings_period_and_revision_proof
G06 comparable_valuation_method_and_scope
G07 exact_event_identity_known_at_and_transmission
G08 governance_and_execution_policy
G09 official_delivery_and_flow_proxy_authority
G10 strategy_specific_setup_and_geometry_policy
G11 actual_institutional_identity_not_inferable_from_proxies
G12 approved_post_result_reaction_window
G13 approved_price_reaction_method
G14 calibrated_weak_market_definition
G15 event_family_materiality_and_expiry_policy
G16 historical_breadth_and_aligned_benchmark_sector
G17 official_delivery_tick_and_BBW_semantics
G18 persistence_and_expiry_policy
G19 selected_prebreakout_policy_asof_and_complete_P1_known_at
G20 verified_company_exposure
G21 verified_surprise_baseline

These labels are dependency requirements, not new 21 score components. R/O/C matrix is proposed required/optional/confirmation; review and approve exact semantics per lens before relying on it.

## Computation, ordering and performance

1. Separate approved ingestion jobs continuously maintain raw, canonical and versioned facts, with source first-seen time preserved.
2. Compute shared market/sector features once per compatible cutoff/version, stock technical/fundamental features once per instrument/timeframe/cutoff/basis/source-fingerprint/definition-version. Persist or selectively invalidate materializations when upstream evidence changes.
3. Freeze a vetted universe snapshot with true covered/eligible/blocked denominators; schedule one bounded/resumable market evaluation, prioritizing only cheap reusable predicates in the broad scan.
4. Group the 35 lenses by actual shared dependencies; execute lightweight readiness and matches over cached features. Run high-cost dossier/event research only for relevant stocks, changed evidence, and holdings/watchlist, not 35x all stocks every minute.
5. A single exact-ISIN candidate identity aggregates all matching lens IDs, discovery-funnel origins, evidence and blocker reasons. Do not sum duplicate labels into score or confidence.
6. Candidate handoff invokes canonical Deep Research/61/Decision Score/confidence/setup/Six-Gates only under correct existing ownership and evidence contracts. A lens cannot shortcut these steps.
7. Existing read-only market scan and UI consume materialized snapshots; explicit operator/scheduler refresh is distinct from reads. Preserve internal status and exact provenance; no provider fan-out in discovery.
8. Portfolio runs separately over genuine holdings/cash, governed risk/rotation and comparisons; never infer BUY/SELL action from lens matches.

## UI roles

Home: aggregate coverage, fresh changes and lens family counts with partial denominator.
Opportunities: selectable 35-lens facets, multiple matches per security, sort by separately governed score and data readiness; maintain a single stock row.
Stock Detail: 35-lens results, dependencies, original source citations/known-at, timeframes, contradictions and thesis changes.
Market-Wide Watch and Signals: read-only detection, de-duplicated event and trigger provenance, expiry and separate policy status.
Portfolio: apply same lenses to current holdings; thesis watch/invalidation, not auto liquidation.
Dev Console: per-lens input readiness by domain, blocked G01–G21, source vintage, mismatch reports, materialization hit/miss, coverage by stock and family.

## Minimum acceptance tests

- Exactly 35 IDs and six disjoint presentation families; no missing/duplicate ID. Existing 35x10 design matrix remains reference, not an activated policy.
- A stock qualifying for 4 lenses appears once in candidate pool and retains all 4 evidence-backed matches.
- Each required dependency missing/stale/conflicted -> not MATCH; all mandatory readiness READY only with exact PIT/source proof.
- Core 61 diagnostic result computed at most once per compatible instrument+cutoff+source/model version and reused by multiple lenses; source revision invalidates selectively.
- G11 institutional identity cannot be claimed from proxy price-volume.
- G07/G20 material event cannot claim affected stock without certified company exposure.
- Strict historical run cannot use current-descriptive data, future event, adjusted price with missing corporate action, or stale/unverified sector membership.
- Existing `hsi_scan_market` route remains functional and read-only through replacement; prior origin/coverage parity tested on frozen dataset.
- Separate lens fit from Decision Score, six gates, trade execution; no network fetch or portfolio mutation in lens evaluation.
- Version mismatch and output replay conflict fail closed; snapshot-based resumability and full-NSE denominator validated.
- Pilot with distinct technical, fundamental, event, market-red, company-quality and holding examples; compare old/new outputs, performance and missing-data states before activation.

## Implementation sequence

L1. Pin repo branch and run baseline tests; enumerate current actual consumer paths, 35 catalog definitions and 21 gap labels.
L2. Add canonical `LensInputReadiness` typed ledger over certified internal structured data; define per-lens normative evidence and policy requirements.
L3. Implement one canonical derived-feature cache with exact keys, invalidation and shared 61 diagnostic evaluation. Preserve old fingerprints and history.
L4. Implement governed per-lens fit evaluation, initially shadow-only; cover the six families with independently verified examples.
L5. Integrate with existing `SharedMarketScanService` and unified candidate pool, without deleting or breaking `hsi_scan_market`.
L6. Bind canonical shared Brain evaluation and immutable opportunity projections, then stock detail, portfolios and dev diagnostics.
L7. Cross-sectional and historical PIT parity, load/performance, regression, staging canary, governance approval and staged activation.

No existing lens-policy, scoring, gate, provider or execution activation is changed by this document. Current 35-lens assessment coverage is draft, UNKNOWN fit; local production DB readiness and post-change integration remain unverified.
