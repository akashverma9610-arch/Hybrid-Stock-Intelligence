# Financial Metric Trajectory Policy Proposal

**Policy family:** `financial-metric-trajectory-policy`  

> Historical proposal lineage is now `v1-proposed -> v1-approved`. The frozen
> approved policy is documented in `FINANCIAL_METRIC_TRAJECTORY_POLICY_APPROVED.md`;
> this proposal remains as its original reasoning record.
**Version:** `v1-proposed`  
**Status: PROPOSED — NOT APPROVED — NOT SELECTED — NOT ACTIVE.**

This U14D-6C document is a governance/design proposal only. It creates no
financial observation, trajectory, builder, policy artifact, directionality,
materiality, thesis, opportunity, alert, recommendation, signal, trade, or
execution behavior.

## 1. Existing period, PIT, and revision model

`FinancialFact` is immutable and holds exact `FinancialMetric`, Decimal value,
currency, unit, `NumericScale`, `FinancialPeriodType`, `FinancialValueBasis`,
optional period start, required timezone-aware period end, optional fiscal year
and fiscal quarter, `StatementScope`, source/filing identity, publication and
receipt timestamps, normalization version, provenance, revision parent, and
quality flags. `available_at` is the later of publication and receipt;
`FinancialFactStore` applies both timestamps to PIT reads.

This identifies an ordinary period strongly when source data supplies
period-start/end and fiscal fields. It can distinguish Q1 FY2026, Q2 FY2026,
Q1 FY2025, and FY2026 without labels. A point-in-time balance-sheet date is
the fact's `period_end`. There is no typed period-identity artifact, however,
and fiscal fields/start dates can be absent. Future construction must fail
closed rather than infer a calendar or duration.

The generic contract does not impose a March fiscal year. The BSE adapter
derives fiscal fields from its own source parser. `revision_of_fact_id` and
`REVISED` retain revision lineage, but do not distinguish a correction from a
formal restatement. Local BSE XBRL facts with an unknown publication timestamp
remain PIT-visible only from system first observation.

## 2. Current factual-comparison limitation

The normal `FinancialFactsEvidenceAdapter` contributes artifact lineage to
`BrainResearchComparisonState`, not automatic numeric financial
`ResearchMetricObservation` values. Explicit observations can be numeric, but
there is no canonical FinancialFact-to-numeric-observation materializer.

`ResearchStateDelta` matches observation semantic identity including metric,
unit, scale, basis, scope, **period identity**, methodology, and dependencies.
It can represent a same-period revision as `VALUE_CHANGED`; it cannot build
business movement across periods. A new eligible period is normally `ADDED`,
and residual mismatched periods are `NON_COMPARABLE`.

**Recommendation:** a future trajectory must be built directly from canonical
financial observations at one explicit `as_of`, not inferred from
`ResearchStateDelta`. The delta may later compare trajectory artifacts, but it
must remain a separate state-change/lineage boundary.

## 3. Proposed factual contracts

### `FinancialMetricPeriodIdentity`

Required future typed fields: period type, value basis, period start/end,
fiscal year, fiscal quarter, statement scope, currency, unit, scale,
normalization version, and fact kind. Fields required by a requested basis
must be present; no metadata bag or fiscal-calendar guess is allowed.

### `FinancialMetricObservation`

Materialize only from a durable `FinancialFact`: canonical instrument ID,
metric ID, factual Decimal value, value dimension, typed period identity,
source/filing reference, source fact ID/fingerprint, publication/receipt/
available-at timestamps, revision parent, quality flags, provenance, and a
deterministic fingerprint. No provider call, inferred scale/scope/quarter,
hidden ratio derivation, or fallback is allowed. Static schema validation is
sufficient for this copy/validation boundary; a policy is not needed merely to
materialize immutable fact fields.

### `FinancialMetricTrajectory`

Future fields: instrument and metric ID; metric temporal class; comparison
kind/basis; explicit `as_of`; prior/current observation IDs and fingerprints;
prior/current period identities and values; optional absolute/relative delta;
sign transition; numeric-domain status; revision relationship; parity and
corporate-action checks; availability; blockers/warnings; source schema/policy
lineage; deterministic fingerprint. It must contain no favorable/unfavorable,
materiality, causal, thesis, opportunity, or action field.

## 4. Comparison kind, basis, and status vocabulary

| Proposal vocabulary | Meaning |
| --- | --- |
| `SAME_PERIOD_REVISION` | Same metric/period identity with newer explicitly revision-linked knowledge. It is not a business trajectory. |
| `SAME_PERIOD_LINEAGE_CHANGE` | Same period with insufficient revision relationship; fail closed. |
| `PERIOD_TRAJECTORY` | Different explicitly comparable periods under a declared basis. |
| `NEW_PERIOD_OBSERVATION` | New eligible period but no requested comparable predecessor. |
| `SCOPE_CHANGED` / `BASIS_CHANGED` | Scope/value-basis drift; non-comparable. |
| `NON_COMPARABLE_PERIOD` | Period, duration, unit/scale, normalization, or semantic parity fails. |

Proposed bases: `SEQUENTIAL_QUARTER`, `YEAR_OVER_YEAR_QUARTER`,
`YEAR_OVER_YEAR_ANNUAL`, and `POINT_IN_TIME_SEQUENTIAL`. Revision is a
comparison kind, not a business-trajectory basis. Proposed factual availability
vocabulary: `AVAILABLE`, `INSUFFICIENT`, `NON_COMPARABLE`, `NOT_APPLICABLE`.

## 5. Pairing rules

| Basis | Required pair | Required parity | Reject/block |
| --- | --- | --- | --- |
| `SEQUENTIAL_QUARTER` | Adjacent quarters, including Q4→Q1 only when fiscal progression proves it. | Same instrument/metric/scope/currency/unit/scale/basis/normalization; quarterly, `QUARTER_ONLY`; compatible start/end duration; PIT vintage. | Unknown/non-adjacent fiscal identity, YTD cumulative value, scope/basis drift, overlap, revision ambiguity. |
| `YEAR_OVER_YEAR_QUARTER` | Same quarter in consecutive fiscal years. | Same parity and compatible duration. | Unknown/mismatched quarter, fiscal-year jump, shortened/extended period. |
| `YEAR_OVER_YEAR_ANNUAL` | Consecutive annual full-year periods. | Annual, `FULL_YEAR`, same parity and compatible year duration. | Transition year, missing fiscal identity, scope/basis/normalization drift. |
| `POINT_IN_TIME_SEQUENTIAL` | Ordered distinct stock-metric dates. | Stock class; same scope/currency/unit/scale/normalization and dates. | Treating it as flow growth; missing/overlapping dates or drift. |

QoQ and YoY describe factual relationship only. They never express growth
quality, seasonality adjustment, or favorable/unfavorable meaning.

## 6. Exact metric support matrix

Support means only that a trajectory could later be constructed from complete,
compatible canonical facts. It does not mean source coverage or directionality
is approved. `FinancialMetric` has no stored temporal-class field; this table
is a future closed mapping proposal.

| Exact metric IDs | Class | Observation | QoQ | Qtr YoY | Annual YoY | Revision | Relative delta | Primary blocker |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `REVENUE`, `OTHER_INCOME`, `EBITDA`, `OPERATING_PROFIT`, `EBIT`, `DEPRECIATION`, `FINANCE_COST`, `PBT`, `TAX`, `PAT`, `MINORITY_INTEREST` | FLOW | Conditional | Conditional | Conditional | Conditional | Conditional | Positive-base only | No numeric materializer; strict scope/basis/revision parity. |
| `EPS_BASIC`, `EPS_DILUTED` | PER_SHARE | Conditional | Conditional | Conditional | Conditional | Conditional | Positive-base only | Share-count and corporate-action basis unproven. |
| `CFO`, `CFI`, `CFF`, `CAPEX`, `FREE_CASH_FLOW` | FLOW | Conditional | `QUARTER_ONLY` only | Conditional only | Conditional | Conditional | Positive-base only | YTD/cumulative cash-flow ambiguity; FCF needs compatible CFO and negative-sign capex. |
| `TOTAL_ASSETS`, `TOTAL_LIABILITIES`, `TOTAL_EQUITY`, `NET_WORTH`, `TOTAL_DEBT`, `CASH_AND_EQUIVALENTS`, `CURRENT_ASSETS`, `CURRENT_LIABILITIES`, `INVENTORY`, `RECEIVABLES`, `PAYABLES` | STOCK | Conditional | No; point-in-time sequential | N/A | N/A | Conditional | Not initial v1 | Balance-sheet stock values are not flows. |
| `SHARES_OUTSTANDING` | SHARE_COUNT | Conditional | No; point-in-time only | N/A | N/A | Conditional | Not initial v1 | Split/bonus/issue lineage; denominator/reference only. |
| `FACE_VALUE` | OTHER / PER_SHARE reference | Conditional | N/A | N/A | N/A | Conditional | Not initial v1 | Corporate-action/reference identity, not performance. |

No canonical raw metric exists for ROCE, ROE, margins, D:E, interest coverage,
working-capital days, or growth. Generic `FinancialDerivationService` labels
are not a closed persisted metric registry and must not enter this contract.

## 7. TTM, cash flow, EPS, and corporate-action firewalls

`FinancialPeriodType.TRAILING_TWELVE_MONTHS` exists and the derivation service
can conservatively derive a fact from four compatible distinct
`QUARTER_ONLY` quarters. It is not an automatic persisted Brain numeric
observation or a durable TTM trajectory. TTM is outside initial scope.

`YEAR_TO_DATE` also exists. The service can derive Q4 from a compatible annual
and nine-month YTD fact, but does not generally decompose H1/YTD cash flow into
standalone Q2/Q3. CFO/CFI/CFF/capex must not get a QoQ trajectory unless both
facts are proven `QUARTER_ONLY`; no subtraction is authorized here.

EPS basic and diluted are distinct. Any per-share trajectory requires same
metric, comparable share basis, and explicit split/bonus/rights/dilution proof.
Current financial facts have no canonical corporate-action adjustment binding;
pre/post-action EPS is `NON_COMPARABLE` without future proof. Consolidated,
standalone, and unknown scopes are never normalized into one another. Merger,
demerger, acquisition, discontinued operation, value-basis change, shortened/
extended period, or absent period identity blocks comparison.

## 8. Delta and numeric-domain semantics

`absolute_delta = current_value - previous_value` is factual and is allowed
only after numeric and identity parity checks. It says nothing about economic
quality. Relative delta should be absent except in `STANDARD_POSITIVE_BASE`:
both values numeric and the prior value strictly positive. No formula is chosen
for a zero or negative base; `(current - previous) / abs(previous)` is not
silently allowed.

Proposed numeric-domain vocabulary: `STANDARD_POSITIVE_BASE`, `ZERO_BASE`,
`NEGATIVE_BASE`, `SIGN_TRANSITION`, `METRIC_DOMAIN_INVALID`, `NON_NUMERIC`.
Useful factual sign transitions are `POSITIVE_TO_POSITIVE`,
`POSITIVE_TO_ZERO`, `POSITIVE_TO_NEGATIVE`, `ZERO_TO_POSITIVE`,
`ZERO_TO_NEGATIVE`, `NEGATIVE_TO_NEGATIVE`, `NEGATIVE_TO_ZERO`,
`NEGATIVE_TO_POSITIVE`. Therefore PAT/EPS/CFO -100→20 is absolute delta plus
`NEGATIVE_TO_POSITIVE`, and 20→-100 is `POSITIVE_TO_NEGATIVE`; neither is
called favorable/unfavorable. Stock-metric v1 should use absolute delta only.

## 9. Vintage, conflict, reliability, and rebuildability

At a trajectory `as_of`, use only the latest unambiguous fact vintage visible
then. A later explicit revision may replace its parent at that later as-of, but
must never enter an earlier trajectory. The existing fundamentals adapter
already chooses an explicit revision and reports unresolved same-period
candidates as conflict; future construction must retain that fail-closed rule.

Reported financial facts are historically rebuildable **conditionally**:
immutable records, PIT timestamps, and revision links are stored. Local XBRL
remains visible only from first observation. TTM/Q4/FCF are conditional
derivations, not durable trajectory evidence. Financial evidence is
`AVAILABLE` for official BSE/NSE source lineage or `PARTIAL` for secondary/
ungoverned lineage; its freshness is currently `UNKNOWN`. Market-price
historical-integrity and market-style staleness semantics must not be copied
into financial trajectories.

Future construction must block unavailable/partial evidence where the selected
policy requires official evidence, unresolved same-period conflicts, missing
identity/quality, invalid numeric domain, and unproven corporate-action basis.
It must not create a new provider resolver.

## 10. Builder placement, future policy, and scope

The factual boundary should be:

```text
PIT-filtered FinancialFactStore
  -> FinancialMetricObservation
  -> select exact period pair under financial-metric-trajectory-policy
  -> FinancialMetricTrajectory(as_of)
  -> optional immutable reference from BrainResearchComparisonState
```

Trajectories must not be constructed secretly inside thesis interpretation. A
versioned `financial-metric-trajectory-policy` is justified because period
pairing, revision handling, share-basis rules, and numeric-domain/relative
delta rules alter factual output. It remains proposed, unapproved, unselected,
inactive, and without an approved fingerprint.

The safest eventual v1 is narrow: raw observation materialization,
same-period-revision classification, strict flow QoQ/quarterly YoY/annual YoY,
stock point-in-time sequential, absolute delta, sign domain, and positive-base
relative delta. TTM, cumulative cash-flow QoQ, unproven per-share adjustment,
ratios, growth, acceleration, materiality, persistence, attribution, and
contradiction aggregation remain out of scope.

**U14D-6D refinement:** [Financial Metric Observation Contract
Proposal](FINANCIAL_METRIC_OBSERVATION_CONTRACT_PROPOSAL.md) assigns revision
winner selection to a preceding PIT fact-vintage selector and keeps a pure
single-fact observation mapper separate from trajectory pairing. These are
proposed contracts only; no observation or trajectory implementation exists.

**Recommended next exact slice:** governance audit/proposal for typed
`FinancialMetricObservation` and `FinancialMetricPeriodIdentity` only,
including a complete fact-to-observation fail-closed mapping. It must not build
or persist trajectories, add a trajectory policy, or implement directionality.

## 11. Explicit exclusions and non-changes

This proposal excludes price, technicals, setup/candidates, sector/market,
ownership, valuation, Decision Score, diagnostics, news/macro semantics, and
absent metrics such as ROCE, ROE, margins, D:E, interest coverage, and growth.
No code, policy, schema, migration, persistence, API, provider/network call,
worker, scheduler, diagnostic, score, gate, scanner, alert, recommendation,
signal, order, or trade changed.
