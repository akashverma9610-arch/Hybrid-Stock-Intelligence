# Financial Metric Observation Contract Proposal

**Schema identity:** financial-metric-observation-schema / v1-proposed  
**Status: PROPOSED — NOT APPROVED — NOT SELECTED — NOT ACTIVE.**

This U14D-6D document is governance/design only. It creates no financial
observation, period class, materializer, selector, trajectory, policy artifact,
directionality, materiality, thesis, opportunity, alert, recommendation,
signal, trade, or execution behavior.

## 1. Exact FinancialFact field inventory

| Group | Existing exact fields / semantics | Required or optional |
| --- | --- | --- |
| Identity | fact_id; instrument: InstrumentIdentity; metric: FinancialMetric; fact_kind; source; filing_id; source_reference; normalization_version; provenance; parent_fact_ids. | fact_id, instrument, metric, fact kind, source and normalization version are field-required. Reported facts require filing_id; source reference and parent IDs can be absent. |
| Numeric | value: Decimal; currency; unit; scale: NumericScale; computed value_dimension. | Value, currency, unit, and scale are present by contract. Value dimension is monetary except EPS/face value (PER_SHARE) and shares outstanding (COUNT). |
| Scope | statement_scope: StatementScope with CONSOLIDATED, STANDALONE, UNKNOWN. | Field is present; UNKNOWN is an explicit value, not evidence of comparability. |
| Period | period_type: FinancialPeriodType; value_basis: FinancialValueBasis; period_start; period_end; fiscal_year; fiscal_quarter. | Period end is required/timezone-aware. Start, fiscal year, and fiscal quarter can be absent. Quarterly quarter, when supplied, must be 1–4. |
| PIT | published_at; received_at; computed available_at = max(published_at, received_at). | Both are required/timezone-aware; receipt cannot precede publication. |
| Revision / quality | revision_of_fact_id; quality_flags using COMPLETE, PARTIAL, INCONSISTENT, REVISED, INSUFFICIENT_HISTORY, UNKNOWN_BASIS. | Revision parent is optional. No typed correction-versus-restatement distinction exists. |
| Source lineage | Exact source/filing/provenance plus company-evidence artifact lineage. | FinancialFact has no fingerprint property. A future observation must calculate its own semantic fingerprint. |

The fact ID is source/fact identity, not a complete semantic fingerprint. The
company-evidence artifact fingerprint is bounded lineage and does not replace a
full numeric-observation identity.

## 2. Observation admission and period identity

A future FinancialMetricObservation may materialize only from one already
PIT-selected FinancialFact vintage with canonical instrument identity, exact
FinancialMetric, finite Decimal value, non-empty currency/unit, exact scale,
period type, value basis, explicit scope enum, timezone-aware period end,
available_at not after as_of, source fact ID, and a recomputed source-fact
semantic fingerprint. The prior fact-vintage selector owns revision-winner,
duplicate, provider-conflict, and PIT lineage closure; this mapper must not
repeat or replace those decisions.

Missing values must never become zero, NaN, false, or an observation that later
looks unchanged. Non-finite Decimal, missing base identity, future-visible fact,
or unresolved source conflict produces non-materialization with an explicit
reason. The mapper may not fetch, infer, convert, or select a different fact.

### Proposed FinancialMetricPeriodIdentity

The minimal nested typed identity is period type, value basis, period start/end,
fiscal year/quarter, statement scope, currency, unit, scale, value dimension,
normalization version, fact kind, and deterministic fingerprint. No generic
metadata bag or fiscal-calendar guess is permitted.

| Strength | Observation admission | Later trajectory eligibility |
| --- | --- | --- |
| COMPLETE | Base identity plus all category-specific identity required for its declared basis. | Potentially eligible, subject to later trajectory parity. |
| PARTIAL | Base factual identity exists but fiscal/start/duration/scope-normalization detail is insufficient. | Blocked; retain blockers for audit. |
| INSUFFICIENT | Base metric/value/PIT/period-end identity is missing or invalid. | No observation; retain typed non-materialization reason. |

A quarterly revenue fact with fiscal year, quarter, start/end, scope, and
QUARTER_ONLY can be complete. A fact with only Q2 or no fiscal year cannot be
complete; fiscal year must not be inferred from publication time. Missing start
date may allow a partial factual observation but blocks duration-sensitive use.

## 3. Metric-class admission matrix

| Actual FinancialMetric members | Observation date/period requirement | Special dependency | Later trajectory consequence |
| --- | --- | --- | --- |
| REVENUE, OTHER_INCOME, EBITDA, OPERATING_PROFIT, EBIT, DEPRECIATION, FINANCE_COST, PBT, TAX, PAT, MINORITY_INTEREST | Period end plus period type/basis/scope/PIT; fiscal/start fields retained where supplied. | No hidden derivation. | Start/end and fiscal parity required for flow pairing. |
| EPS_BASIC, EPS_DILUTED, FACE_VALUE | Same factual period fields; per-share dimension preserved exactly. | Share-basis/corporate-action normalization is not currently bound to facts. | Observation may exist; trajectory blocks without parity proof. |
| TOTAL_ASSETS, TOTAL_LIABILITIES, TOTAL_EQUITY, NET_WORTH, TOTAL_DEBT, CASH_AND_EQUIVALENTS, CURRENT_ASSETS, CURRENT_LIABILITIES, INVENTORY, RECEIVABLES, PAYABLES, SHARES_OUTSTANDING | Period end is accounting observation date, not filing publication date. | Scope and same-date conflict identity. | Future point-in-time sequential only; not flow growth. |
| CFO, CFI, CFF, CAPEX, FREE_CASH_FLOW | Exact value basis is mandatory. | YEAR_TO_DATE versus QUARTER_ONLY remains explicit; derived FCF needs parent IDs. | Cumulative cash flow may be observed but QoQ blocks without quarter-only proof. |

SHARES_OUTSTANDING and FACE_VALUE remain valid factual observations even though
they are non-directional. They can support denominator and corporate-action
lineage, not performance semantics.

## 4. PIT, revision, quality, and conflict rules

The future visible_as_of rule is the existing FinancialFact.available_at: the
later of stored publication and receipt. A fact cannot appear in a state before
that timestamp. Local BSE XBRL without a verified official publication time
uses existing system-first-observed semantics; never backdate it to period end,
filename, or a later discovered date.

Observation lineage preserves revision_of_fact_id, source/filing identity,
quality flags, and a possible revision-parent fingerprint. Use only a broad
factual revision relationship. The repository cannot reliably label a
correction versus formal restatement.

The fact store is insert-only by fact ID: identical writes are idempotent and
a different payload under that ID conflicts. Distinct same-period facts can
still exist through provider/revision history. Existing fundamentals assembly
selects a newer fact only where it explicitly revises an older one; otherwise
it emits an unresolved conflict warning. Future materialization must consume a
preselected, unambiguous PIT fact vintage and never choose first/latest
arbitrarily.

Quality is retained for audit. A PARTIAL, UNKNOWN_BASIS, INCONSISTENT, or
REVISED fact is not discarded automatically; it may become a partial
observation, but is not trajectory-ready unless later governance allows it.
FinancialFact has no native reliability object. Company evidence marks official
BSE/NSE lineage AVAILABLE and secondary/ungoverned lineage PARTIAL, while
freshness is UNKNOWN. No second reliability model or market-integrity rule is
proposed.

## 5. Minimal observation schema and result design

A future immutable FinancialMetricObservation should contain:

- observation ID, canonical instrument ID, metric, temporal class;
- factual Decimal value, currency, unit, scale, value dimension;
- exact scope and nested FinancialMetricPeriodIdentity;
- visible_as_of, publication, and receipt timestamps;
- source fact ID and semantic source-fact fingerprint;
- filing/source identity, revision parent identity/fingerprint, quality and
  source-lineage references;
- period-identity strength, blockers/warnings, schema ID/version, and
  deterministic observation fingerprint.

It must contain no favorability, trajectory, materiality, thesis, opportunity,
recommendation, portfolio, or execution field. Its fingerprint includes every
semantic field above except the stored fingerprint and excludes runtime
construction time, user, and portfolio context.

A separate observation-status enum is unnecessary. A valid observation exists;
identity strength and existing availability/quality lineages explain future
blockers. Batch processing may later return a typed
FinancialObservationMaterializationResult containing source fact ID,
observation-or-none, and sorted reason codes.

Proposed fail-closed reason codes:

MISSING_CANONICAL_INSTRUMENT, MISSING_METRIC, INVALID_NUMERIC_VALUE,
MISSING_CURRENCY, MISSING_UNIT, MISSING_SCALE, MISSING_SCOPE,
MISSING_PERIOD_TYPE, MISSING_VALUE_BASIS, MISSING_PERIOD_END,
MISSING_PIT_VISIBILITY, FACT_NOT_VISIBLE_AS_OF,
AMBIGUOUS_PERIOD_IDENTITY, UNRESOLVED_FACT_CONFLICT,
UNSUPPORTED_PERIOD_BASIS, SOURCE_FACT_IDENTITY_INVALID.

## 6. Period-type and provider boundary matrix

| Actual period type / basis | Observation | Required identity | Later trajectory use |
| --- | --- | --- | --- |
| QUARTERLY / QUARTER_ONLY | Conditional | End, scope, fiscal year/quarter; start required for duration-complete identity. | Possible QoQ and quarterly YoY only after future policy. |
| QUARTERLY / YEAR_TO_DATE | Conditional / normally partial | End, scope, exact cumulative basis; fiscal fields when supplied. | Not QoQ without later canonical decomposition. |
| ANNUAL / FULL_YEAR | Conditional | End, scope, fiscal year, compatible annual duration. | Possible annual YoY only after future policy. |
| TRAILING_TWELVE_MONTHS / QUARTER_ONLY | Conditional derived fact | Parent lineage and four compatible quarter identities. | No initial trajectory use. |
| POINT_IN_TIME with an actual supported basis | Conditional | Accounting observation/end date, scope, base numeric identity. | Future stock sequential only. |
| UNKNOWN basis | Partial only with other valid base identity. | Unknown basis is explicit quality lineage. | Blocked. |

Provider convenience cannot weaken the canonical contract. BSE official XBRL
currently materializes only a subset of direct metrics and records scale/PIT
provenance; other structured providers may populate different fields. The
observation schema remains provider-neutral and retains provider identity only
as lineage.

## 7. Rebuild pipeline and state relationships

The future factual pipeline should be:

```text
Canonical FinancialFactStore
  -> PIT fact-vintage selector (latest unambiguous fact known at as_of)
  -> pure single-fact FinancialMetricObservation materializer
  -> deterministic observation collection at as_of
  -> later FinancialMetricTrajectory builder
```

Revision-winner selection belongs in the PIT fact-vintage selector/upstream
canonical evidence boundary, not inside the single-fact mapper. The mapper is
pure: one selected fact becomes one observation or a fail-closed result.
The selection boundary is specified separately by the U14D-6E Financial Fact-
Vintage Selection Proposal; that proposal remains proposed and non-active.

BrainResearchComparisonState should later retain existing financial artifact
lineage plus references to immutable observations, rather than copy the
financial source of truth or select period pairs internally. A specialized
financial observation may later adapt into ResearchMetricObservation, without
duplicating fact values/fingerprints. FinancialMetricTrajectory consumes only
materialized observations: no provider lookup, scope inference, scale
conversion, fact repair, or hidden pair selection.

## 8. Policy, schema, and next slice

No separate financial-metric-observation-policy is justified. Mapping a complete
immutable fact to a typed observation is structural, so a versioned
financial-metric-observation-schema / v1-proposed is sufficient. A later
financial-metric-trajectory-policy owns period pairing, revision treatment,
numeric-domain handling, and relative-delta rules because those alter factual
results.

**Recommended next exact slice:** governance audit/proposal for the PIT
fact-vintage selector only: revision-chain winner selection, conflict closure,
and batch reason aggregation. It must not implement the selector, observation
model/materializer, trajectory, or directionality.

## 9. Explicit non-changes

The proposal remains preserved as historical governance input. Its first
approved successor is recorded in
[FINANCIAL_METRIC_OBSERVATION_SCHEMA_APPROVED.md](FINANCIAL_METRIC_OBSERVATION_SCHEMA_APPROVED.md):
financial-metric-observation-schema / v1-approved. The schema is approved but
not selected or active, and it adds no observation materializer.

No observation contract, materializer, PIT selector, period parser, trajectory,
directionality/materiality/persistence rule, schema migration, canonical-data
mutation, provider/network call, diagnostic, score, gate, scanner, API, worker,
scheduler, alert, recommendation, signal, order, or trade is created or changed.
