# Brain Research Comparability Policy Proposal

**Policy family:** `brain-research-comparability-policy`  
**Suggested draft version:** `v1-proposed`  
**Status: PROPOSED — NOT APPROVED — NOT SELECTED — NOT ACTIVE.**

This is a governance proposal for factual comparison only. It creates no
policy artifact, fingerprint, state, delta, engine, persistence, provider call,
alert, recommendation, signal, order, or execution behavior. It does not
define thesis, opportunity, investment risk, bullish/bearish, or any action.

The separate frozen objective policy remains unchanged:
`intelligence-delta-interpretation-policy / v1-approved`, fingerprint
`2d0572f2d29daa7e322b6a91495b142fc13a84508573338a4cd9d91ab8239b57`.

This proposal is superseded as governance input by the immutable, inactive
approved artifact documented in
[BRAIN_RESEARCH_COMPARABILITY_POLICY_APPROVED.md](BRAIN_RESEARCH_COMPARABILITY_POLICY_APPROVED.md).
The proposal itself remains historical proposal lineage and is not rewritten as
an approved policy.

## Purpose and core rule

This future policy answers only whether two research observations are
semantically comparable. Equal field names or numeric types do not establish
equivalence. A later `ResearchStateDelta` may emit a factual difference only
after this policy establishes parity; a later thesis/opportunity policy remains
a separate consumer.

Default rule: different identity, scope, basis, methodology, policy, schema,
window, normalization, or unresolved dependency means `NON_COMPARABLE` unless
a future, explicitly approved dimension-specific cross-version comparator says
otherwise. None exists today.

## Proposed source eligibility vocabulary

| Status | Meaning |
| --- | --- |
| `PIT_REBUILDABLE` | Exact state can be reconstructed from canonical stored evidence eligible by its historical `as_of`. |
| `DURABLE_ARTIFACT_ONLY` | Comparable only when exact immutable prior/current artifacts are stored or supplied; do not recompute it from current-only state. |
| `CURRENT_ONLY` | Current reporting/operation input only; never historical T1↔T2 comparison evidence. |
| `REFERENCE_ONLY` | Identity, integrity, normalization, or methodology evidence; not a directional research metric. |
| `UNSUPPORTED` | No current safe governed comparison boundary. |

These future statuses do not alter existing Unified-State availability values.

## PIT and revision rule

For `as_of = T`, use only evidence visible under its existing publication,
receipt, availability, effective, known-at, or revision contract by T. Never
backfill historical state with today's sector rank, technical result, news,
valuation fact, or later filing revision.

Default mode is **knowledge-at-the-time**: compare what was eligible at T1 with
what was eligible at T2. Restated-history comparison requires a separate
explicit mode, policy and output identity. It must never be mixed silently.

## Common observation identity

Every proposed future `ResearchMetricObservation` needs canonical instrument
identity (or explicit market-wide identity), research dimension, metric ID,
source artifact type/ID/fingerprint, applicable as-of/effective/observed/
published/available timestamps, eligibility status, methodology/schema/
normalization identity/version, warnings, and deterministic fingerprint.

Dimension-specific identity must be added rather than hidden in a generic map:
financial scope/basis/unit/scale/period; price exchange/series/session/provider
basis; indicator lookback/calendar/formula; sector taxonomy/benchmark/membership;
setup policy/selection/tick lineage; event schema/entity; or score/diagnostic
registry/configuration.

## Exact source inventory and eligibility

| Source / actual contract | Canonical or derived | Eligibility today | Required lineage for comparison |
| --- | --- | --- | --- |
| `FinancialFact`, `FinancialFactStore`, `FundamentalSnapshot`, `FundamentalEngineInput` | Canonical reported facts; deterministic derived metrics with parents | `PIT_REBUILDABLE` | Metric, period, scope, basis, currency/unit/scale/dimension, source, normalization, publication/receipt, revision, quality. |
| `app/analysis/fundamentals.py` trend, ratios, cash flow, leverage, margins, acceleration helpers | Derived analysis | `DURABLE_ARTIFACT_ONLY` unless parents/version/window are retained | Parent facts, calculation/version, missing-data treatment, period/scope/basis. |
| `CorporateFiling` shareholding evidence | Canonical disclosure lineage; no normalized holdings in Unified State | `REFERENCE_ONLY` disclosure; `UNSUPPORTED` percentage comparison | Filing/disclosure period, holder category, denominator/share count, source, revision, corporate-action treatment. |
| `HistoricalCorporateAction` / `actions_as_of` | Canonical reference and normalization evidence | `PIT_REBUILDABLE`, `REFERENCE_ONLY` | Action ID/kind, announcement/record/ex/effective/as-of dates, source, revision, identity linkage. |
| `CanonicalOHLCVBar`, provider-versioned `HistoricalBarStore` | Canonical stored price history | `PIT_REBUILDABLE` subject to integrity | Mapping, exchange/series, timeframe/session, provider identity/version, bar ID, adjustment status, provenance, integrity. |
| `MarketRegimeResult` | Derived result | `DURABLE_ARTIFACT_ONLY` when exact result exists; otherwise `UNSUPPORTED` historically | Result ID, methodology/strategy, as-of, input observation IDs, classification/status. |
| `InstrumentTaxonomyClassification` and historical membership/mapping | Canonical/reference identity | `PIT_REBUILDABLE` where effective/known intervals exist | Taxonomy/version/source, effective interval, mapping/membership fingerprints. |
| `CurrentSectorRotationService` RS/breadth/rank/Top-3 | Current stored-only derived composition | `CURRENT_ONLY` | Future durable as-of artifact must retain benchmark, membership, bars, windows, formula and ranking policy. |
| `TechnicalAnalysisEngine` current materialization | Derived technical values | `CURRENT_ONLY` absent durable exact artifact | Bars/basis, calendar, lookback/minimum periods, method version, integrity. |
| `NseDeliveryObservation` / `NseDeliveryStore` | Official canonical observation | `PIT_REBUILDABLE` | Report/observation ID, identity mapping, trade date, available-at, percent and source. |
| `GovernedPreBreakoutSetupAssessment` | Governed deterministic artifact | `DURABLE_ARTIFACT_ONLY` | Assessment/policy/selection fingerprints, bars, delivery, tick, structural semantics and integrity. |
| `PreBreakoutCandidate` | Deterministic candidate from assessment | `DURABLE_ARTIFACT_ONLY` | Candidate/assessment/policy/selection fingerprint, pending-research boundary. |
| `DiagnosticResult` | Durable immutable result | `DURABLE_ARTIFACT_ONLY` | Rule/registry/strategy, as-of/evaluated-at, eligibility, result/score/confidence, evidence/input IDs. |
| `DecisionScorecard` | Durable immutable scorecard | `DURABLE_ARTIFACT_ONLY` | Strategy/registry/configuration, components, weights, missing rules, score status/confidence, evidence/diagnostics. |
| `NewsArticleEvidence`, `CatalystEvent`, filings | Stored factual metadata | `PIT_REBUILDABLE` for eligible stored artifacts | Event/article/filing ID, schema/type/entity, publication/receipt/effective time, source, confirmation, correction. |
| `MacroEvidence` / first-observed `MacroState` | Stored raw evidence / derived state | Raw `PIT_REBUILDABLE` only with release vintage; state `DURABLE_ARTIFACT_ONLY` | Family/component/geography, source tier, observed/published/effective/available time, revision/schema. |
| Valuation | No governed comparable valuation contract | `UNSUPPORTED` | Future metric, price timestamp/basis, financial scope/basis, source/methodology. |
| `StoredReliabilityDecision` | Durable route/availability decision | `DURABLE_ARTIFACT_ONLY` | Native status, family, route/tier, fallback/LKG/conflict flags, observed/available/evaluation timing. |
| `HistoricalPriceIntegrity` | Stored integrity assessment | `PIT_REBUILDABLE` where as-of assessment exists | Native status, basis, bar/action IDs, warnings and assessment fingerprint. |

## Financial and earnings rules

Two financial observations are conditionally `COMPARABLE` only when they have:

1. Same canonical instrument and `FinancialMetric`.
2. Same statement scope. Consolidated versus standalone is `NON_COMPARABLE`.
3. Same currency, value dimension, unit and scale, unless a future policy
freezes a lossless source-metadata conversion. EPS/per-share is never subject
to monetary conversion.
4. Same period type and value basis. Quarterly-only, annual/full-year, TTM and
point-in-time values are distinct comparison classes.
5. Governed fiscal-period alignment and comparable period length.
6. Same normalization/methodology version and explicit revision treatment.
7. PIT-eligible published/received lineage and acceptable quality flags.

Therefore consolidated revenue versus standalone revenue, quarterly OPM versus
annual OPM, raw INR versus crore presentation without an approved conversion,
and EPS across an unproven split adjustment are `NON_COMPARABLE`. Original
filing versus later restatement is non-comparable in knowledge-at-the-time mode
unless a future revision comparator is explicitly selected.

Derived margin, acceleration, leverage and cash-flow facts also require exact
parent facts, calculation version, window and missing-data treatment.

## Ownership, corporate action, market-price and technical rules

Current ownership has disclosure lineage but not durable normalized historical
percentages. It is `REFERENCE_ONLY`; promoter/FII/DII/public/pledge percentage
comparison is `UNSUPPORTED` until exact category, period, denominator,
share-count, source/revision, corporate-action and PIT-normalized values exist.

Corporate actions are primarily identity/normalization conditions. Their
event/type/date/revision facts can be compared, but they do not convey thesis
direction. Price comparison requires canonical security identity,
exchange/series/timeframe/session, provider identity/version, adjustment basis,
provenance/quality and historical integrity. A price series crossing a
price-transforming action without a proven common basis fails closed.

BBW, ATR, RSI, SMA/EMA, relative volume, delivery inputs, support/resistance
and structural base facts require matching price basis, integrity, calendar,
lookback, minimum-session rule, formula/method version, corporate-action
treatment and selected policy. Different window or policy is
`NON_COMPARABLE`; insufficient history is `INSUFFICIENT`, not zero.

## Sector, RS, breadth and Top-3 rules

Sector identity is reconstructible only from taxonomy/membership/mapping
intervals eligible at each as-of time. RS, breadth, rank and Top-3 additionally
require exact benchmark, index mapping, PIT constituents, constituent history,
adjustment bases, calendar, lookback, RS/breadth formula, coverage threshold,
ranking policy and tie treatment.

The existing `CurrentSectorRotationService` is current stored-only composition.
No durable historical RS/breadth/Top-3 artifact exists today, so all three are
`CURRENT_ONLY` and `NON_COMPARABLE` for historical T1↔T2 state comparison.

## Pre-Breakout and entry-economics rules

Two governed setup assessments are factually comparable only with identical
canonical instrument, policy ID/version/fingerprint, selection lineage,
evaluation as-of/session, structural-base semantics, price basis, PIT-safe bars,
delivery input, tick resolution and adequate integrity. Policy fingerprint drift
is `NON_COMPARABLE` unless a later approved cross-version comparator exists.

Entry reference price, trigger, support, stop, target, maximum acceptable/
executable entry and reference R:R are factual geometry under that lineage only.
Actual fills are excluded: they depend on execution context and must never be
fabricated. Candidate remains `OPPORTUNITY_CANDIDATE` and `RESEARCH_PENDING`;
its existence is not opportunity direction.

## Score and diagnostic rules

Scorecards are numerically comparable only with identical strategy, registry,
configuration/score policy, component definitions, weights/state mapping,
normalization, missing-evidence treatment, completeness basis, confidence
semantics, as-of discipline and evidence/diagnostic lineage. A numerical change
is only a factual score delta. Fingerprint change is identity/tamper lineage,
never direction.

Diagnostic comparison is separately governed for: whole bundle (same registry,
strategy, expected rule set and completeness policy); individual rule (same
rule/version/input semantics); coverage (same expected catalogue and eligibility
meaning); and fingerprint (identity only). This proposal authorizes no run,
rescore, or hidden subset selection.

## News, catalysts and macro rules

Event comparison needs stable event/article/filing identity, entity, type/schema,
source/quality, publication/effective/receipt time, confirmation/filing match,
materiality fields when present, and correction/supersession lineage. Factual
states may be event added, confirmed, corrected or superseded; none has
investment meaning.

Macro requires metric/family/component, geography, period, release vintage,
source tier, revision and methodology parity. Raw `MacroEvidence` can compare
only with PIT release lineage. First-observed derived `MacroState` must not be
retrojected and is artifact-only; absent vintages mean `INSUFFICIENT` or
`NON_COMPARABLE`.

## Reliability and integrity preconditions

| Condition | Proposed comparison result |
| --- | --- |
| `CONFLICTED` evidence or native historical integrity `INVALID` | `NON_COMPARABLE`; no best guess. |
| Required evidence `UNAVAILABLE` | `INSUFFICIENT`. |
| `PARTIAL` evidence/integrity | `INSUFFICIENT` unless a later policy admits the exact partial basis. |
| `STALE` evidence | Not automatic rejection; use only if the relevant dimension defines stale-but-same-basis eligibility, otherwise `INSUFFICIENT`. |
| Reliability `DEGRADED`, fallback or LKG | Retain native durable decision; default `INSUFFICIENT` for dependent comparison. |

Native integrity `INVALID` projects to Unified-State `CONFLICTED`; it is not
safe to reverse that projection. A future comparator must require native typed
integrity/reliability lineage instead of inferring it.

## Comparability result and failures

Propose `ResearchComparabilityStatus`:

| Value | Meaning |
| --- | --- |
| `COMPARABLE` | Required factual parity and eligibility are proven. No direction. |
| `INSUFFICIENT` | Necessary eligible source facts/lineage are absent or partial. |
| `NON_COMPARABLE` | Facts exist but identity, basis, method, policy, version, scope or conflict forbids comparison. |
| `NOT_APPLICABLE` | Dimension does not apply to the requested instrument/context. |

Failure should be dimension-local: comparable financial facts may coexist with
non-comparable sector RS and comparable setup geometry. State-level failure is
reserved for different canonical instruments, invalid timezone/temporal order,
source Unified-State identity/fingerprint inconsistency, absent/tampered
research-state schema/methodology identity, or mismatched comparison modes.

## Dependency and version rules

Every derived observation must retain a sorted immutable dependency manifest of
upstream artifact/observation IDs and fingerprints plus its methodology/version.
Sector breadth, for example, depends on taxonomy/membership, constituent set,
price histories and bases, moving-average methodology, calendar/session and
coverage threshold. A changed dependency makes the derived result
non-comparable even if its field name is unchanged.

Diagnostic, score, setup, RS, breadth, valuation, technical and all other
derived metric version drift defaults to `NON_COMPARABLE`. There is no silent
cross-version equivalence.

## Historical rebuildability matrix

| Dimension | PIT rebuildable now? | Required lineage | Status today |
| --- | --- | --- | --- |
| Financials / earnings / balance sheet / cash flow | Yes for raw facts | scope/basis/unit/scale/period/revision/PIT | Conditional `COMPARABLE` |
| Ownership percentages | No | normalized disclosure denominator/category facts absent | `UNSUPPORTED` |
| Corporate actions | Yes | action dates/source/revision | `REFERENCE_ONLY` |
| Market price | Yes, subject to integrity | mapping/basis/provider/provenance/integrity | Conditional |
| Market regime | Exact stored artifact only | result/method/input/as-of | `DURABLE_ARTIFACT_ONLY` |
| Sector identity | Yes when PIT intervals exist | taxonomy/membership mapping | Conditional |
| Sector RS, breadth, Top-3 | No general historical artifact | durable sector result missing | `CURRENT_ONLY` |
| Technical values | Exact governed/durable artifact only | bar basis/lookback/version | Artifact-only otherwise current-only |
| Delivery | Yes | official report/observation/available-at | Conditional |
| Pre-Breakout assessment/candidate/entry economics | Exact durable/reconstructible governed lineage only | policy/selection/tick/bars/delivery | `DURABLE_ARTIFACT_ONLY` |
| Diagnostics / Decision Score | Exact durable artifacts only | registry/config/components/coverage | `DURABLE_ARTIFACT_ONLY` |
| News/catalysts | Yes for eligible stored records | identity/schema/PIT/revision | Conditional factual events |
| Macro raw / state | Raw with release vintage / exact state artifact | source/vintage/revision | Conditional / artifact-only |
| Valuation | No | canonical contract absent | `UNSUPPORTED` |

## Relation to future state and policy layers

`BrainResearchComparisonState` is a factual state at one as-of moment.
`brain-research-comparability-policy` defines whether its observations pairwise
compare. A future `ResearchStateDelta` retains factual deltas, this status and
rationale only. A later thesis/opportunity policy may consume it but may not
recompute comparison validity. The objective delta policy governs separate
availability/freshness/reliability/integrity semantics and is not extended.

## Explicit exclusions

This proposal contains no thesis strengthened/weakened, opportunity improved/
degraded, risk, bullish/bearish, BUY/HOLD/SELL/TRIM/ROTATE, recommendation,
alert authorization, execution decision, portfolio context, threshold change,
provider call, persistence, migration, worker, scheduler, or runtime behavior.

## Audit sources

- `app/fundamentals/models.py`, `app/fundamentals/store.py`,
  `app/fundamentals/adapter.py`, `app/fundamentals/service.py`
- `app/historical/security_master.py`, `app/market_data/historical.py`,
  `app/market_data/models.py`, `app/market_data/nse_delivery.py`
- `app/analysis/models.py`, `app/analysis/fundamentals.py`,
  `app/analysis/market_regime.py`, `app/analysis/relative_strength.py`,
  `app/analysis/technical.py`
- `app/market_data/current_sector_rotation.py`,
  `app/market_data/current_prebreakout.py`
- `app/strategies/pre_breakout/materialization.py`,
  `app/strategies/pre_breakout/setup_assessment.py`,
  `app/strategies/pre_breakout/candidate_assembly.py`
- `app/intelligence/unified_state.py`, `app/intelligence/company_evidence.py`,
  `app/intelligence/non_company_evidence.py`, `app/intelligence/macro_news_evidence.py`,
  `app/intelligence/research_diagnostic_evidence.py`,
  `app/intelligence/decision_score_evidence.py`, `app/intelligence/six_gates_evidence.py`
- `app/research/handoff.py`, `app/scoring/engine.py`, and
  `app/storage/sqlite_governance_repository.py`
