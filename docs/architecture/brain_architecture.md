# Brain Architecture v2.2-hardened

## Purpose and authority

The Brain is the internal, evidence-first research, paper-trading, and governance architecture of NSE Stock Manager v2.1. Repository documentation and tested code are authoritative over chat or memory. This document is the
canonical detailed architecture specification; product branding remains v2.1.

The approved live-readiness architecture includes an economic/news intelligence context flow: `Sources → Reliability/Reconciliation → Historical Integrity → Validation → Macro Intelligence → Economic Regime → Sector Transmission → Sector Intelligence → Opportunity Discovery → Company Sensitivity → Stock Research → Catalyst Intelligence → Market Integrity → Setup → Decision Score/Confidence → Gates → Portfolio/Rotation`. It remains evidence/context, not a separate score or action engine.

`v2.2-hardened` remains approved. The additive post-#035 candidate is documented
in [v2.3-live-readiness candidate](live_readiness_candidate.md); it is not an
approved architecture version or an authorization for autonomous deployment.

## Canonical hardened flow

`Data Sources → Data Reliability & Fallback → Historical Integrity → Data Validation → Market Regime → Sector Intelligence → Opportunity Discovery → Pre-Breakout / Inflection Candidate Setup → Stock Research → Market Integrity → Setup Engine → Decision Engine → Hard Execution Gates → Portfolio Brain → Capital Rotation → Risk & Execution → Monitoring → Outcomes → Benchmark Engine → Model Governance & Drift → Self-Improvement → Audit & Reproducibility → Validated Deployment`

No downstream engine may silently bypass Reliability, Historical Integrity, or
Validation when its input depends on external or historical data.

## Existing-code map

| Hardened engine | Existing package/service | Status | Gap / action |
|---|---|---|---|
| Data Sources | `app.data_sources`, `app.market_data`, filings, fundamentals, news | IMPLEMENTED | Provider-specific validation stays opt-in. |
| Reliability & Fallback | readiness composition + `app.reliability` | IMPLEMENTED | Routing facade reports, never fetches or fabricates. |
| Historical Integrity | `app.historical`, PIT guards + `app.historical_integrity` | IMPLEMENTED | Historical source coverage can remain PARTIAL. |
| Data Validation | canonical market-data validators, domain validation | IMPLEMENTED | Kept separate from scoring. |
| Market Regime / Sector Intelligence | `app.analysis`, diagnostics, sector engines | IMPLEMENTED | Input coverage remains explicit. |
| Opportunity Discovery / Stock Research | `app.universe_analysis`, stock-analysis services | IMPLEMENTED | Never calls a provider per diagnostic. |
| Market Integrity | Crisis, extremes, liquidity/SMC proxy engines | IMPLEMENTED | Evidence/proxies are not factual fund-flow claims. |
| Setup / Decision | diagnostic registry, scorecard, confidence | IMPLEMENTED | Formula ownership remains unchanged. |
| Hard Gates | execution-gate services | IMPLEMENTED | Gates are separate from score/confidence. |
| Portfolio / Rotation / Risk | portfolio, rotation, risk, paper trade | IMPLEMENTED | Analytical result is not an order. |
| Monitoring / Outcomes / Benchmark | paper outcomes, performance, benchmark engines | IMPLEMENTED | Incomplete samples remain visible. |
| Governance & Drift | promotion governance + `app.governance` | IMPLEMENTED | Drift recommendations cannot activate a strategy. |
| Self-Improvement | `app.self_improvement` | IMPLEMENTED | Research/OOS stays governed and non-deploying. |
| Audit & Reproducibility | reconstruction service + `app.audit` | IMPLEMENTED | Internal records are not public diagnostic disclosure. |
| Validated Deployment | approved versions, activation, rollback | PARTIAL | No autonomous production deployment. |

## Engine engineering contract and operational mapping

Every engine is documented with the same contract: purpose; canonical inputs
and outputs; models/repository; public vs internal boundary; dependencies;
failure/degraded state; PIT/freshness requirement; privacy boundary; tests; and
implementation status. The compact mapping below records the current
implementation rather than inventing a duplicate package for each name.

| Engine | Purpose; inputs → outputs | Store / boundary | Dependencies, failure, PIT/privacy, tests | Status |
|---|---|---|---|---|
| Data Sources | normalize provider facts → canonical data | market-data, filing, fundamental stores; provider adapters internal | provenance/validation; unavailable remains unavailable; adapter tests | IMPLEMENTED |
| Taxonomy / Coverage | canonical classification and stored-evidence counts → readiness facts | `app.taxonomy`, `app.data_coverage`; append-only snapshots | ISIN-first, effective-date/PIT safe; code support is not data ready; no taxonomy guess | IMPLEMENTED |
| Controlled Real-Brain Trial | frozen 30–50 cohort + canonical stores → availability/blocker audit | `app.real_brain`; append-only internal snapshots | zero provider calls during analysis; 61 execution does not make missing evidence complete; no alpha/action output | IMPLEMENTED |
| Reliability | source health → explicit routing decision | `app.reliability`; no public writer | readiness facts; fallback/stale/conflict explicit; no secrets; unit tests | IMPLEMENTED |
| Historical Integrity | fact + membership + as_of → integrity decision | `app.historical_integrity`; immutable historical records | PIT guard; future/unknown membership blocks or partials; anti-look-ahead tests | IMPLEMENTED |
| Historical Security Master | stable identity, membership/action intervals, price basis → technical/backtest integrity | `app.historical.security_master`; append-only snapshots | no present-universe substitution; raw/adjusted conflicts fail closed; PIT/reconciliation tests | IMPLEMENTED |
| Data Validation | canonical facts → valid/partial/invalid data | canonical stores; internal validation | identity/numeric/time/freshness checks; no scoring; validation tests | IMPLEMENTED |
| Regime / Sector | bars, indices, breadth → typed context | analysis snapshots/read models | validated stored inputs; partial evidence visible; diagnostic tests | IMPLEMENTED |
| Opportunity / Research | eligible universe + stored evidence → candidates/research | universe snapshots/jobs; distilled read APIs | coverage gate; no hard-coded shortlist; PIT/coverage tests | IMPLEMENTED |
| Candidate Strategies | sector/macro plus frozen technical/fundamental evidence → research candidate setup | `app.strategies`; append-only snapshots | no final score/action; Setup Quality separate; PIT/missing-data tests | IMPLEMENTED |
| Market Integrity / Setup | crisis, extremes, price-volume and research evidence → context/setup | immutable assessments; internal engines | proxy policy; missing evidence partial; no unsupported claims; tests | IMPLEMENTED |
| Decision / Gates | diagnostics → score/confidence → six gate decisions | governance repository / snapshots | versioned frozen inputs; score, confidence, gates separate; regression tests | IMPLEMENTED |
| Portfolio / Rotation / Risk | snapshots and candidates → analytical allocation/risk | portfolio, rotation, paper records | cash valid; no execution side effect; replay/audit tests | IMPLEMENTED |
| Monitoring / Outcomes / Benchmark | paper outcomes → performance/comparisons | immutable reports/benchmark records | frozen window/cost inputs; sample warnings; persistence tests | IMPLEMENTED |
| Governance / Drift | performance facts → review recommendation | promotion repository + drift snapshots; internal only | human governance owns deployment; no self-promotion; governance tests | IMPLEMENTED |
| Self-Improvement | frozen evidence → hypotheses/experiment draft | immutable research records; internal only | OOS/human-review boundary; no active-model mutation; tests | IMPLEMENTED |
| Audit / Deployment | frozen references → internal reconstruction / governed activation | audit snapshots + existing reconstruction/governance records | no latest fallback; proprietary details private; audit/tamper tests | IMPLEMENTED / PARTIAL deployment |

## Dependency and privacy rules

Dependencies flow left to right through immutable references; a later layer may
read a frozen predecessor but must not rewrite it. Diagnostics are not Decision
Score; confidence is not score; gates are not rotation; rotation is not
execution; self-improvement is not deployment. Public APIs expose only distilled
read models and never 61-rule inventory, evidence IDs, weights, thresholds, or
gate IDs.

## Prohibited shortcuts

- No latest-record fallback for a historical decision.
- No silent mock fallback in API/live mode.
- No fabricated quote, bar, score, or missing-data pass.
- No provider fan-out per diagnostic or scan-on-GET.
- No automatic order, promotion, approval, activation, or broker/account call.
- No claim of best NSE opportunity under partial universe coverage.
