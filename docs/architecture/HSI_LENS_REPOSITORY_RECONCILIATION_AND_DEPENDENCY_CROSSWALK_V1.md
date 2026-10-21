# HSI lens repository reconciliation and dependency crosswalk V1

Status: `AUDIT_ONLY / INTEGRATION_NOT_EXECUTED / NOT_ACTIVE`

## Scope and authority

This is a pinned integration audit, not a replacement strategy registry, approval, source-readiness certificate, or implementation receipt. The paired [machine-readable crosswalk](HSI_LENS_REPOSITORY_RECONCILIATION_AND_DEPENDENCY_CROSSWALK_V1.json) inventories every Lite lens and D01–D61 reference. It has no runtime consumer. Definitions remain in their existing authorities; no copied calculation or new Brain is introduced.

Preserve [Post-V1 architecture](POST_V1_PRODUCT_ARCHITECTURE.md), [approved product catalogue](POST_V1_STRATEGY_AND_SIGNAL_WINDOW_CATALOGUE.md), and [historical funnel audit](HSI_BRAIN_FUNNEL_RUNTIME_RECONCILIATION_AUDIT_V1.md). Core V1 remains ACTIVE; Execution Gate V2 remains NOT_ACTIVE. P1 prospective start remains UNSET and recorder NOT_ACTIVE. Existing approved Pre-Breakout policy does not automatically approve Lite's PRE_BREAKOUT_ACCUMULATION identifier. Similar names are not identity/policy equivalence.

Target dependency direction: controlled acquisition → canonical evidence → existing deterministic diagnostics/shared calculations → proposed lens evidence consumers → constrained Analytics AI interpretation. Matching reads stored evidence; provider acquisition is a separate controlled operation. Diagnostics may share materializations without making all 61 mandatory for every lens. Missing, unsupported, conflicted, and not-applicable evidence must remain distinguishable; none means a negative investment conclusion or an executable action.

## Pinned repository state

| Source | Observed revision | Meaning |
|---|---|---|
| core_local | `f88b44d514fc9a2654040aa04e5350fc9e8660fe` | Clean local main before this documentation change |
| common_base | `810590be84d483f02be0a6518cf84fba02d8bab9` | Shared ancestor |
| github_main_observed | `6f80be689029008e02c9232badb66aace28e40a1` | GitHub API observation; not the stale local remote-tracking ref |
| draft_pr_1_head | `243b20eae80e3c3d76803549c41500c7fa016821` | Open draft PR, not merged |
| lite | `fcf288918591b0b6383dbc66bac70d7e9a4010fc` | Clean local Lite source |

Local main has two commits after the common ancestor: `df563ad4fc7f76ad2564ad523d760cfdf64cfa28` (current EOD/source handoff) and `f88b44d514fc9a2654040aa04e5350fc9e8660fe` (native technical binding). GitHub main has one separate commit. A direct push is not a clean fast-forward. No fetch, merge, cherry-pick, reset, rebase, commit, or push was performed for this audit. Recheck remote heads immediately before any eventual integration.

[Draft PR #1](https://github.com/akashverma9610-arch/Hybrid-Stock-Intelligence/pull/1) adds 47 files/changes, including 35 lens definitions, a 350-row design matrix and research coverage composition. Its body reports 29 tests including 3 subtests; that is author-reported validation of its branch, not validation against local source-binding work. GitHub's mergeable flag is not a security or operational approval.

## Remote-main file disposition before any integration

| File | Finding | Proposed treatment; nothing applied here |
|---|---|---|
| `alembic.ini` | Replaces placeholder with localhost PostgreSQL URL | Do not adopt as deployment configuration; retain controlled environment selection. |
| `migrations/versions/20260828_06_news_evidence.py` | Parent changed to `20260827_05`; local financial-facts migration declares exactly that revision | Valid static parent-reference repair candidate; test migration graph independently before accepting. |
| `migrations/versions/20260830_08_provider_versioned_historical_bars.py` | Parent changed to `20260829_07_primary_market`; local predecessor declares exactly that revision | Valid static parent-reference repair candidate; not proof an upgrade is safe for a production DB. |
| `seed_db.py` | Top-level synthetic portfolio/stock snapshot writes; hardcoded score, regime, six PASS gates and EXECUTABLE state | Exclude from production integration. Never execute/import it against canonical state. Fixtures belong only in an explicitly isolated test namespace. |
| `stock_canonical.db` | Binary database introduced in remote commit | Content not inspected; do not import or overwrite local canonical DB. No assertion about its contents or privacy is made. |

The seed includes a synthetic BUY transaction as data; this is not evidence a broker was called. Its hardcoded PASS/EXECUTABLE records are not canonical proof. No source data, gate passage or portfolio state may be inferred from the remote commit's 'production ready' subject. The local AST scan found the two missing parent references above; no migration was executed.

## Draft foundation: reuse and integration gaps

| Area | Existing/reusable capability | Remaining proof or correction before production binding |
|---|---|---|
| Catalog | 35 pinned proposed definitions; source matrix 35 × 10 | Reconcile exact IDs with governed HSI catalogue; do not register aliases or approve policies by name. |
| Coverage | Supplied diagnostic results shared across lens assessments; all lens outcomes UNKNOWN | Availability is not fit. Verify canonical record identity/version/fingerprint, source lineage and availability semantics. |
| Stored cycle | Validates supplied frozen universe and computes once per selected stock per call | Inject certified native technical/benchmark-sector/financial inputs and existing governance authorization. Generic assembler injection alone does not prove stored-only/PIT-safe inputs. |
| Existing assembler | Supports technical, benchmark-sector and financial contracts; financial source hook exists | Preserve source fallback behavior only where approved. Explicitly prove the bound source, no network access, exact as-of and fingerprint agreement. |
| Replay | Immutable coverage store accepts exact repeat and rejects conflicting content | PR recomputes diagnostics before replay acceptance; do not claim compute-once across runs. Define reuse key and stale-input invalidation before adding caching. |
| Storage | Existing Core API snapshot repository extended with draft coverage family | Keep prospective ingestion/known-at separate from research as-of. A snapshot created_at copied from as-of is not acquisition-time proof. No DB changes in this slice. |
| Universe | Frozen supplied universe, bounded page size | Demonstrate eligibility/denominator and source completeness; never advertise all-NSE coverage from a small supplied set. |
| Analytics AI | Existing architecture constrains AI to interpretation | No Analytics AI integration is implemented by the draft foundation or this audit. Require evidence-linked explanations and no invented numbers/authority. |

## Exact design dependencies: all 35 lenses

R/O/C below are copied from Lite's `required_diagnostics` / `optional_diagnostics` / `context_diagnostics`, preserving source order and labels, not approved runtime requirements. All 35 are `PROPOSED_NOT_ACTIVE / NOT_ACTIVE / NOT_IMPLEMENTED_IN_LITE`. Every live-readiness value is NOT_VERIFIED. Required evidence families and source hashes are included in the JSON. Gap labels describe Lite design omissions, not a finding that the entire Core capability is absent.

| Proposed lens identifier | R | O | C | Unresolved labels |
|---|---|---|---|---|
| ASSET_MONETISATION | D30, D29, D18, D19, D20 | D15, D16, D23, D28, D08, D52 | D04, D06, D10, D37 | G07, G06, G01, G04, G08, G03 |
| BREAKOUT_RETEST | D04, D06, D10, D37, D07, D11, D36, D50, D08, D52 | D01, D02, D03 | D15, D16, D24, D25, D26 | G10, G09, G03, G02 |
| CAPACITY_EXPANSION | D30, D15, D16, D24, D25, D26 | D18, D19, D20, D23, D28, D01, D02, D03 | D29, D04, D06, D10, D37 | G07, G04, G05, G01, G08, G02 |
| CASH_FLOW_INFLECTION | D18, D19, D20, D24, D25, D26 | D15, D16, D23, D28, D29 | D04, D06, D10, D37 | G01, G05, G04, G08, G06 |
| COMMODITY_UPCYCLE | D01, D02, D03, D24, D25, D26 | D15, D16, D18, D19, D20, D29, D30 | D04, D06, D10, D37, D08, D52 | G02, G05, G04, G01, G06, G07 |
| CONFIRMED_BREAKOUT | D04, D06, D10, D37, D07, D11, D36, D50 | D01, D02, D03, D08, D52 | D15, D16, D24, D25, D26, D29 | G10, G09, G02, G03 |
| CYCLICAL_RECOVERY | D01, D02, D03, D15, D16, D24, D25, D26 | D18, D19, D20, D29, D30 | D04, D06, D10, D37 | G02, G04, G05, G01, G06, G07 |
| DEEP_VALUE_MEAN_REVERSION | D29, D15, D16 | D18, D19, D20, D04, D06, D10, D37, D08, D52 | D30, D23, D28 | G06, G04, G01, G10, G03 |
| DELEVERAGING | D18, D19, D20, D15, D16 | D24, D25, D26, D29, D23, D28 | D04, D06, D10, D37 | G01, G04, G05, G06, G08 |
| DEMERGER_VALUE_UNLOCK | D30, D29, D15, D16 | D23, D28, D18, D19, D20, D08, D52 | D04, D06, D10, D37 | G07, G06, G04, G08, G01, G03 |
| DOMESTIC_CAPEX_BENEFICIARY | D01, D02, D03, D30, D15, D16 | D24, D25, D26, D18, D19, D20, D23, D28 | D29, D04, D06, D10, D37 | G02, G07, G04, G05, G01, G08 |
| EARLY_EMERGING_LEADER_SMALL_MIDCAP | D15, D16, D24, D25, D26, D23, D28, D08, D52 | D01, D02, D03, D18, D19, D20, D29 | D04, D06, D10, D37, D30 | G04, G05, G08, G03, G02, G01, G06 |
| EARNINGS_MOMENTUM | D24, D25, D26, D15, D16 | D04, D06, D10, D37, D07, D11, D36, D50 | D29, D01, D02, D03 | G05, G04, G10, G09 |
| EARNINGS_SURPRISE_POST_RESULT_DRIFT | D24, D25, D26, D30 | D04, D06, D10, D37, D07, D11, D36, D50, D08, D52 | D29 | G05, G07, G10, G09, G03, G21, G12 |
| EVENT_CATALYST | D30 | D15, D16, D01, D02, D03, D24, D25, D26, D23, D28 | D04, D06, D10, D37, D29, D08, D52 | G07, G04, G02, G05, G08, G15, G20, G13 |
| EXPORT_SCALING | D15, D16, D24, D25, D26, D01, D02, D03 | D18, D19, D20, D23, D28, D29 | D04, D06, D10, D37 | G04, G05, G02, G01, G08, G06 |
| FUNDAMENTAL_INFLECTION | D15, D16, D24, D25, D26 | D18, D19, D20, D30, D29 | D04, D06, D10, D37, D23, D28, D01, D02, D03, D08, D52 | G04, G05, G01, G07, G06 |
| GARP | D15, D16, D29, D24, D25, D26 | D18, D19, D20, D23, D28 | D04, D06, D10, D37, D01, D02, D03 | G04, G06, G05, G01, G08 |
| IMPORT_SUBSTITUTION | D01, D02, D03, D15, D16, D30 | D24, D25, D26, D23, D28, D29 | D04, D06, D10, D37 | G02, G04, G07, G05, G08, G06 |
| INSTITUTIONAL_ACCUMULATION | D07, D11, D36, D50, D04, D06, D10, D37, D08, D52 | D01, D02, D03, D15, D16 | D24, D25, D26, D29 | G09, G10, G03, G02, G04, G11 |
| LONG_TERM_STRUCTURAL_COMPOUNDER | D15, D16, D18, D19, D20, D23, D28 | D24, D25, D26, D01, D02, D03, D29 | D04, D06, D10, D37, D08, D52 | G04, G01, G08, G05, G02, G06 |
| MARGIN_EXPANSION | D24, D25, D26, D15, D16 | D18, D19, D20, D29 | D04, D06, D10, D37, D23, D28 | G05, G04, G01, G06 |
| MARKET_RED_RESILIENCE | D01, D02, D03, D04, D06, D10, D37, D08, D52 | D07, D11, D36, D50, D15, D16 | D24, D25, D26, D29 | G02, G10, G03, G09, G04, G14, G16, G18 |
| MARKET_SHARE_GAINER | D15, D16, D24, D25, D26, D01, D02, D03 | D23, D28, D18, D19, D20, D29 | D04, D06, D10, D37 | G04, G05, G02, G08, G01, G06 |
| MID_TERM_COMPOUNDER | D15, D16, D24, D25, D26, D18, D19, D20 | D23, D28, D29, D01, D02, D03 | D04, D06, D10, D37, D08, D52 | G04, G05, G01, G08, G06, G02 |
| NEW_PRODUCT_NEW_CUSTOMER_INFLECTION | D30, D15, D16, D24, D25, D26 | D23, D28, D01, D02, D03, D18, D19, D20 | D29, D04, D06, D10, D37 | G07, G04, G05, G08, G02, G01 |
| ORDER_BOOK_CAPEX_CYCLE | D30, D24, D25, D26, D15, D16 | D01, D02, D03, D23, D28, D18, D19, D20 | D29, D04, D06, D10, D37 | G07, G05, G04, G02, G08, G01 |
| POLICY_REGULATORY_BENEFICIARY | D30, D01, D02, D03 | D15, D16, D24, D25, D26, D23, D28 | D29, D04, D06, D10, D37 | G07, G02, G04, G05, G08 |
| PRE_BREAKOUT_ACCUMULATION | D04, D06, D10, D37, D07, D11, D36, D50, D01, D02, D03 | D15, D16, D24, D25, D26, D08, D52 | D29, D30 | G10, G09, G02, G04, G05, G03, G19, G17 |
| PROMOTER_MANAGEMENT_TRANSFORMATION | D23, D28, D15, D16 | D18, D19, D20, D24, D25, D26, D29 | D30, D04, D06, D10, D37 | G08, G04, G01, G05, G06 |
| QARP | D15, D16, D29, D23, D28 | D18, D19, D20, D24, D25, D26 | D04, D06, D10, D37, D01, D02, D03 | G04, G06, G08, G01, G05 |
| RERATING_CANDIDATE | D29, D15, D16 | D24, D25, D26, D23, D28, D30 | D04, D06, D10, D37 | G06, G04, G05, G08, G07 |
| SECTOR_ROTATION_LEADER | D01, D02, D03, D04, D06, D10, D37, D07, D11, D36, D50 | D15, D16, D24, D25, D26, D08, D52 | D29 | G02, G10, G09, G04, G05, G03 |
| SPECIAL_SITUATION | D30, D29 | D15, D16, D23, D28, D08, D52 | D04, D06, D10, D37, D18, D19, D20 | G07, G06, G04, G08, G03 |
| TURNAROUND_RECOVERY | D15, D16, D18, D19, D20, D24, D25, D26 | D23, D28, D04, D06, D10, D37, D29 | D30, D07, D11, D36, D50 | G04, G01, G05, G08, G10, G06 |

| Gap | Exact Lite label |
|---|---|
| G01 | `PIT_financial_scope_and_cash_comparability` |
| G02 | `PIT_sector_breadth_and_mapping` |
| G03 | `actual_exitability_liquidity_policy` |
| G04 | `approved_business_quality_policy` |
| G05 | `comparable_earnings_period_and_revision_proof` |
| G06 | `comparable_valuation_method_and_scope` |
| G07 | `exact_event_identity_known_at_and_transmission` |
| G08 | `governance_and_execution_policy` |
| G09 | `official_delivery_and_flow_proxy_authority` |
| G10 | `strategy_specific_setup_and_geometry_policy` |
| G11 | `actual_institutional_identity_not_inferable_from_proxies` |
| G12 | `approved_post_result_reaction_window` |
| G13 | `approved_price_reaction_method` |
| G14 | `calibrated_weak_market_definition` |
| G15 | `event_family_materiality_and_expiry_policy` |
| G16 | `historical_breadth_and_aligned_benchmark_sector` |
| G17 | `official_delivery_tick_and_BBW_semantics` |
| G18 | `persistence_and_expiry_policy` |
| G19 | `selected_prebreakout_policy_asof_and_complete_P1_known_at` |
| G20 | `verified_company_exposure` |
| G21 | `verified_surprise_baseline` |

`ORDER_BOOK_CAPEX_CYCLE` does not list D27 in R/O/C despite its order-book objective. This is an explicit taxonomy/policy review gap, not permission to insert D27 or invent a threshold. Earnings-surprise requires pre-result expectations; price-volume proxies cannot prove institutional buyer identity; market-share requires comparable industry evidence. Policy transmission requires legal/implementation, eligibility, orders, execution, revenue and cash-flow evidence rather than narrative association.

The matrix contributes 10 unresolved dimension labels; five lens files add 11 further lens-specific labels. All 21 are retained, including expectations, reaction-window, company-exposure, institutional-identity, persistence and selected-policy gaps. They must not disappear when importing the dimension matrix.

The matrix references 25 distinct diagnostic IDs; that does not obsolete the other 36. Its 350 strengths are 91 PRIMARY, 98 SECONDARY, 63 OPTIONAL and 98 NOT_REQUIRED. They are design emphasis labels, not numerical weights or permission to skip a safety constraint.

## D01–D61 crosswalk and evidence ownership

The following names/evidence families are preserved from Lite extraction. Full historical input descriptions, exact Core evaluator symbols, hashes and reverse lens-consumer lists are in JSON. The historical coverage audit is dated 2026-09-10; it is not a current whole-universe data audit. No production database was opened for this slice.

| Diagnostic | Canonical name | Evidence families |
|---|---|---|
| D01 | Market Regime Classification | market_regime |
| D02 | Sector Index Health & Trend | sector_health |
| D03 | Sector Rotation Phase | sector_health, sector_rotation |
| D04 | Primary Trend Direction — Weekly & Daily | trend_daily, trend_weekly |
| D05 | Weinstein Market Stage | moving_average_structure, trend_weekly |
| D06 | Relative Strength Rank vs Nifty 50, Sector Index & Peers | relative_strength |
| D07 | Institutional / Smart Money Observable Proxies | accumulation_distribution |
| D08 | Liquidity Pool Mapping — Buy-side & Sell-side | liquidity_pools |
| D09 | Wyckoff Phase Classification | liquidity_pools, liquidity_events, wyckoff_phase |
| D10 | Classical Market Structure — Dow HH/HL vs LH/LL | market_structure |
| D11 | Volume Behavior & Relative Volume (RVOL) | rvol |
| D12 | Ichimoku Cloud Structure | ichimoku |
| D13 | Chikou Span Confirmation | ichimoku |
| D14 | Multi-Timeframe Alignment — Weekly, Daily, 4H/1H, 15M where data permits | ichimoku |
| D15 | Business Model & Moat Sustainability | business_moat_claims |
| D16 | Five-Year Financial Trend — Revenue, EBITDA, PAT, EPS CAGR | financial_growth_series, financial_comparability |
| D17 | Return Ratios — ROCE and ROE | return_ratios, financial_comparability |
| D18 | Operating Cash Flow & Free Cash Flow Health | cash_flow_quality, financial_comparability |
| D19 | Balance Sheet Leverage — Debt/Equity, Net Debt, Interest Coverage | leverage, financial_comparability |
| D20 | Working Capital & Cash Conversion Cycle | working_capital, financial_comparability |
| D21 | Ownership Structure — Promoter Holding & Pledge | ownership |
| D22 | Institutional Holding Shifts — DII/MF/FII | institutional_holdings |
| D23 | Corporate Governance & Auditor Cleanliness | governance_claims |
| D24 | Earnings Acceleration Status — Organic vs One-Off | quarterly_growth, financial_comparability |
| D25 | Latest Quarterly Results — YoY & QoQ | quarterly_growth, financial_comparability |
| D26 | Operating Margin & Gross Margin Trajectory | margins, financial_comparability |
| D27 | Order Book & Book-to-Bill Ratio | order_book, financial_comparability |
| D28 | Management Execution Track Record — Guidance vs Delivery | guidance_delivery, financial_comparability |
| D29 | Valuation Multiples — P/E, Forward P/E, PEG, EV/EBITDA, P/B | valuation, financial_comparability |
| D30 | Fundamental Catalysts — High/Medium/Low Impact | catalysts |
| D31 | Comprehensive Risk Engine — Probability × Impact | diagnostic_results |
| D32 | Trading Thesis | diagnostic_results |
| D33 | Investment Thesis | diagnostic_results |
| D34 | Bull / Base / Bear Probability Scenarios | diagnostic_results |
| D35 | VWAP & Value Area Acceptance | named_vwap_value_area |
| D36 | OBV Trend & Divergence | obv |
| D37 | Base Pattern Quality — VCP, Cup & Handle, Flat Base, Ascending Base | base_pattern |
| D38 | Pullback Quality & Support Confluence | base_pattern, pullback |
| D39 | Technical Indicator Layer — RSI, ADX, ATR | rsi, adx, atr |
| D40 | Aggressive Entry Level | base_pattern, entry_geometry |
| D41 | Confirmation Entry Level | base_pattern, entry_geometry |
| D42 | Pullback / Retest Entry Level | base_pattern, pullback, entry_geometry |
| D43 | Structural Stop-Loss | base_pattern, pullback, stop_geometry |
| D44 | Target Hierarchy — T1, T2, Extended Target | base_pattern, target_geometry |
| D45 | Risk/Reward Calculation — minimum structural R:R normally 1:2 | entry_geometry, stop_geometry, target_geometry, risk_reward |
| D46 | Exact Thesis Invalidation Conditions | base_pattern, stop_geometry |
| D47 | Retail / Public Sentiment Score — 0 to 100 | crowd_sentiment |
| D48 | Crowd Positioning Tier | crowd_positioning |
| D49 | Crowd Data Confidence | crowd_data_confidence |
| D50 | Institutional Accumulation vs Distribution Proxy | accumulation_distribution, liquidity_events, wyckoff_phase |
| D51 | Major Stop-Loss Cluster Mapping | liquidity_pools |
| D52 | Liquidity Event Detection — Sweep, Absorption, Breakout Acceptance | liquidity_pools, liquidity_events |
| D53 | Bull Trap Identification | liquidity_pools, trap_evidence |
| D54 | Bear Trap Identification | liquidity_pools, trap_evidence |
| D55 | Crowd Trap Probability | crowd_sentiment, crowd_data_confidence, crowd_divergence, crowd_trap |
| D56 | Price vs Crowd Sentiment Divergence | crowd_sentiment, crowd_divergence |
| D57 | Post-News Price Reaction — Absorption vs Sell-the-News | post_news_reaction |
| D58 | Volume Climax & Distribution Signs | rvol, volume_climax |
| D59 | Contrarian Ichimoku Confluence | diagnostic_results, ichimoku, crowd_sentiment |
| D60 | Contrarian Signal Quality — Strong / Moderate / Weak | diagnostic_results, crowd_trap, crowd_divergence, crowd_data_confidence |
| D61 | Contrarian Action Verdict — Buy / Sell / Hold / Avoid / Wait | diagnostic_results, crowd_data_confidence |

## Shared computation and funnel preservation

Reuse [Canonical61DiagnosticRunner and assembler](../../app/universe_analysis/service.py), [native technical binding](../../app/data_operations/native_technical_binding.py), and [existing read-only funnel adapters](../../app/intelligence/multi_funnel_discovery_adapters.py). The adapters validate already materialized PIT records; they do not fetch providers or calculate a new diagnostic. Keep candidate identity, reason, coverage and lineage. A sector shortlist must not silently become the entire 35-lens universe.

Static duplicate candidates: sector_rotation calls sector_health; multi-timeframe Ichimoku invokes per-timeframe Ichimoku; several valuation/trade helpers call base_pattern; liquidity helper chains may reuse pool/event calculations. These are candidates, not proof that every invocation has identical inputs. Different timeframe, adjustment, parameters or as-of require distinct results. Existing market-regime caching must be preserved and reviewed before another cache is introduced.

Any later shared-materialization key must bind canonical instrument/index/sector/cohort identity, as-of, timeframe/session and adjustment basis, exact source-vintage/content fingerprints and approved calculation/policy version. Use immutable typed results; demonstrate bit-for-bit or explicitly governed numerical parity, unknown/conflict behavior, no future evidence and call-count reduction before removing an old computation. Do not delete all funnel code.

## Evidence limits and validation

Source pins are SHA-256 of inspected bytes, not credentials. They detect drift; they do not prove market truth or policy approval. Other audit reports mention limited financial/diagnostic stock coverage, but their database counts are not reproduced here as current measurements. No provider connectivity, current-market acquisition, strategy fit, security rollout or operational closure was tested.

Validation for this documentation slice: exact 35/61 membership; source hashes; 350 matrix cells/10 dimensions; literal dependency and reverse-consumer correspondence; local-link existence; migration-parent static inspection; documentation-only worktree and git diff --check. Backend tests are not required for an audit-only document and were not run. Historical audit states and PR-reported tests are not new runtime validation.

## One next bounded continuation

`HSI_LENS_FOUNDATION_ISOLATED_RECONCILIATION_AND_CANONICAL_BINDING_V1`

First preserve local source commits in an isolated review checkout. Reconcile the remote change set without importing its synthetic seed/database/default deployment configuration; validate the two parent-reference corrections separately. Any later merge must preserve both histories and record the reviewed exclusion explicitly, not reset/rewrite main. Recheck SHAs first and do not push divergent main.

Then integrate only reviewed draft coverage modules/definitions/tests with exact provenance, bind existing canonical native inputs and governance authorization, and prove stored-only bounded execution, source timestamp/known-at separation, replay/conflict safety and all-UNKNOWN policy-unavailable outputs. Run focused plus relevant/full backend regression for code changes. Do not activate lenses, connect providers per matching call, replace funnels, implement Analytics AI, mutate portfolios or grant order authority in that continuation. It has not started.
