# Frozen Financial Metric Observation Schema

**Status: APPROVED — NOT SELECTED — NOT ACTIVE.**

This is an immutable passive schema contract, not an observation pipeline. It
governs what a future factual FinancialMetricObservation must retain after an
already-selected FinancialFact vintage is supplied. It does not select facts,
read storage, materialize observations, build trajectories, calculate QoQ/YoY/
TTM, interpret financial direction, or authorize an action.

## Identity and lineage

| Field | Value |
| --- | --- |
| Schema ID | financial-metric-observation-schema |
| Frozen version | v1-approved |
| Prior proposal | financial-metric-observation-schema / v1-proposed |
| Approval | APPROVED |
| Governance identity | human:Akash-Verma |
| Selected for future materializer | false |
| Active | false |
| Schema fingerprint | 6d55e73ee78f0074789165952a287d9b8b6ec801ce98703e9a136603f3da3caf |
| Upstream selector policy | financial-fact-vintage-selection-policy / v1-approved |

Lineage is:

    v1-proposed -> v1-approved

The schema requires the frozen selector-policy fingerprint
862dc470ebd58abd2d066f2604440908eaf3aa9827e6c93b588b5f1bf806fc13,
but does not select or activate that policy.

## Period identity

FinancialMetricPeriodIdentity separates accounting period meaning from PIT
knowledge visibility. It retains exact FinancialPeriodType,
FinancialValueBasis, optional period start, optional period end for an
insufficient descriptor, fiscal year/quarter where supplied, StatementScope,
FinancialValueDimension, currency, unit, NumericScale, normalization version,
strength, and deterministic period fingerprint.

| Strength | Meaning |
| --- | --- |
| COMPLETE | Sufficient category-specific accounting identity for a complete factual period contract. Quarterly flow requires start, fiscal year, and fiscal quarter; annual flow requires start and fiscal year; point-in-time requires its accounting end. |
| PARTIAL | A factual accounting end exists but trajectory-relevant metadata is incomplete. It is not a quality ranking. |
| INSUFFICIENT | The descriptor cannot support FinancialMetricObservation admission. |

Period end is the economic accounting date for point-in-time metrics. Publication
and receipt remain PIT lineage, never a substitute for accounting period end.
Cash-flow basis remains exact: quarter-only, year-to-date, and full-year are
not collapsed or subtracted. No fiscal calendar, reporting interval, scope,
unit, scale, currency, or normalization identity is inferred.

## Observation contract

FinancialMetricObservation is an immutable factual representation with:

- canonical instrument, FinancialMetric, fact kind, exact Decimal value;
- currency, unit, NumericScale, StatementScope, and embedded period identity;
- published_at, received_at, and visible_as_of;
- source fact ID, source, filing/reference, revision parent, parent IDs,
  quality flags, provenance, and normalization lineage;
- selector-policy and selection-result lineage;
- source-fact semantic fingerprint; and
- schema identity plus deterministic observation fingerprint.

Visible-as-of is exactly the later of published_at and received_at. It is
separate from the economic period and cannot be backdated. Decimal is preserved
without float conversion, rounding, currency conversion, unit conversion, or
scale conversion. UNKNOWN scope remains UNKNOWN.

EPS, face value, and shares outstanding are valid factual observations with
their exact PER_SHARE or COUNT value dimensions. The schema neither adjusts EPS
nor derives share basis. Corporate-action lookup is not hidden in this contract;
future trajectory work must bind such dependencies explicitly.

## Source-fact semantic fingerprint ownership

This schema owns the single frozen source-fact semantic fingerprint definition.
It uses semantic source content — instrument, metric, fact kind, Decimal value,
representation, period identity, source/filing identity, PIT timestamps,
revision lineage, quality flags, provenance, and normalization version — and
does not include storage fact ID. Source fact ID remains explicit observation
lineage, so two storage rows with the same semantic source contents have the
same source-fact semantic fingerprint but distinct observation fingerprints.

The static fingerprint functions canonicalize supplied schema values only. They
do not accept FinancialFact, query a selector/store, or construct an
observation from raw evidence.

## Admission and future materialization

A future materializer must require canonical instrument, metric, fact kind,
finite Decimal value, representation, scope, period type/basis/end, valid PIT
visibility, source fact ID, source-fact semantic fingerprint, and successful
selected-vintage lineage. An INSUFFICIENT period identity must fail observation
admission; PARTIAL remains a valid factual observation.

No observation status enum was added. A valid object represents a successfully
admitted fact; a later materializer should return a typed per-fact result with
reasons for non-materialization and reserve exceptions for foundational misuse.
The future materializer should consume one selected FinancialFact, its matching
successful selection lineage, and this schema, verifying source-fact ID binding.
It must not rerun fact-vintage selection.

## Explicit exclusions

No materializer, batch materializer, selector rerun, trajectory, numeric
comparison, directionality, materiality, thesis/opportunity interpretation,
recommendation, alert, action, persistence, migration, API, provider/network
activity, BrainResearchComparisonState integration, ResearchStateDelta change,
worker, listener, or scheduler is introduced by this schema.

