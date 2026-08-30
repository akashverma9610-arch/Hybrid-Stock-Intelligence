# Frozen Financial Fact-Vintage Selection Policy

**Status: APPROVED — NOT SELECTED — NOT ACTIVE.**

This document records the first frozen policy governing factual, point-in-time
selection of a canonical stored FinancialFact vintage. It is immutable policy
metadata only. It does not query a fact store, traverse revision links, select a
fact, materialize an observation, construct a trajectory, calculate
directionality, interpret thesis/opportunity, create an alert or
recommendation, or authorize execution.

## Identity and lineage

| Field | Value |
| --- | --- |
| Policy ID | financial-fact-vintage-selection-policy |
| Frozen version | v1-approved |
| Prior proposal | financial-fact-vintage-selection-policy / v1-proposed |
| Approval state | APPROVED |
| Governance identity | human:Akash-Verma |
| Selected for future selector | false |
| Active | false |
| Selection mode | KNOWLEDGE_AT_THE_TIME |
| Canonical artifact | app/fundamentals/financial_fact_vintage_selection_policy.py |
| Deterministic fingerprint | 862dc470ebd58abd2d066f2604440908eaf3aa9827e6c93b588b5f1bf806fc13 |

The policy lineage is:

    v1-proposed -> v1-approved

The fingerprint covers every semantic field in the immutable artifact and has
no volatile runtime timestamp. No database record, selection record, activation
record, or policy persistence is created by this freeze.

## PIT and semantic identity

PIT eligibility is fixed as:

    available_at = max(published_at, received_at)
    available_at <= as_of

All timestamps must be timezone-aware. Future facts, later revisions, and later
received evidence are excluded from earlier knowledge states. When official
publication time is unknown, existing first-observed visibility remains the
earliest permitted availability; no earlier publication time is inferred.

A future semantic key must retain exact canonical instrument, FinancialMetric,
fact kind, StatementScope, FinancialPeriodType, FinancialValueBasis, period
end, period start where supplied, fiscal year/quarter where supplied, value
dimension, currency, unit, NumericScale, and normalization version. These are
identity safeguards, not conversion instructions. CONSOLIDATED, STANDALONE, and
UNKNOWN scope remain distinct; UNKNOWN is never promoted. No selector scope
preference, unit/scale/currency conversion, provider priority, or latest-time
shortcut is permitted.

## Revision, duplicate, and conflict governance

A valid revision relation must be explicit, parent-linked, within one semantic
key, parent-present, acyclic, linear or explicitly resolved, chronologically
valid, and have a unique terminal eligible candidate. A child may become
available at the same timestamp as its explicit parent, but never earlier.

For one key and as-of time, future runtime behavior must filter PIT-eligible
facts, validate identity and lineage, remove only facts explicitly superseded
by eligible valid descendants, and choose exactly one terminal candidate. A
later revision never rewrites a prior as-of result.

A revised fact without an explicit parent cannot supersede another candidate.
If it is the sole otherwise-valid candidate, the frozen warning
REVISED_WITHOUT_EXPLICIT_PARENT may be retained. If it competes with another
candidate, no implicit ancestry may be assumed and resolution fails closed.

An asserted but missing parent, a cross-semantic parent, invalid chronology,
unresolved branch, or cycle is invalid lineage. Facts are exact duplicate
provenance only where same underlying filing/source identity, semantic key,
Decimal value, representation, compatible PIT lineage, and retained auditable
provenance are all proven. Numeric equality alone is insufficient. Unresolved
same-key non-revision candidates are CONFLICTED; neither row order, insertion
order, provider name, timestamp, nor legacy scope preference may choose a
winner.

## Frozen outcomes

| Status | Factual meaning |
| --- | --- |
| SELECTED | One unique governed fact vintage is selected. |
| UNAVAILABLE | No PIT-eligible fact exists. |
| CONFLICTED | Eligible facts remain unresolved after revision/duplicate handling. |
| INVALID_LINEAGE | Revision/supersession structure violates an invariant. |
| INSUFFICIENT_IDENTITY | Base semantic identity cannot be deterministically formed. |

The frozen typed reasons are NO_PIT_ELIGIBLE_FACT,
UNRESOLVED_FACT_CONFLICT, REVISION_PARENT_MISSING,
CROSS_SEMANTIC_REVISION, INVALID_REVISION_CHRONOLOGY,
REVISION_BRANCH_CONFLICT, REVISION_CYCLE, AMBIGUOUS_SEMANTIC_KEY, and
INVALID_SELECTOR_INPUT. Outcomes are factual provenance states, not ordered
quality levels.

## Batch and safety boundary

A future batch operates per semantic key, uses deterministic sorted ordering,
retains per-key reasons and warnings, and may aggregate reason counts. A
conflicted debt fact or unavailable cash fact is metric-local; safely selected
revenue and PAT remain explicit partial-batch results. Only foundational request
or contract defects — invalid canonical instrument request, naive as-of,
malformed/tampered policy, unsupported mode, or invalid source collection
contract — may invalidate a whole request.

The future observation/schema boundary owns the source-fact semantic
fingerprint. This policy intentionally does not duplicate that fingerprint
algorithm. FinancialMetricObservation must consume an already selected vintage;
BrainResearchComparisonState must consume downstream materialized lineage and
must not rerun financial vintage selection.

## Explicit exclusions

The policy excludes observation materialization, trajectory calculation,
financial directionality, materiality/confirmation, thesis/opportunity
interpretation, alerts/recommendations, BUY/HOLD/SELL/TRIM/ROTATE, and
execution. It authorizes no operational runtime selector, persistence change, migration,
provider/network activity, API, worker, listener, scheduler, or trading path.

U14D-6G later introduced a pure, explicitly invoked stored-only domain
selector under this exact supplied policy. It does not select or activate this
policy operationally and has no store, API, provider, observation, trajectory,
or action-layer wiring. Its boundary is documented in
[FINANCIAL_FACT_VINTAGE_SELECTOR.md](FINANCIAL_FACT_VINTAGE_SELECTOR.md).
