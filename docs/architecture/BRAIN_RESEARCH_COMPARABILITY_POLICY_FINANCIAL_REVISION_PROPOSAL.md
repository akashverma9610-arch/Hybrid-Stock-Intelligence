# Brain Research Comparability Policy — Financial Observation Revision Proposal

**Policy family:** `brain-research-comparability-policy`  
**Proposed successor:** `v2-proposed`  
**Historical proposal status: FROZEN AS APPROVED GOVERNANCE INPUT BY U14D-6N.**

This is a governance audit and proposal only. It does not alter the immutable
`v1-approved` policy, create a v2 artifact or fingerprint, change the Brain
state or `ResearchStateDelta`, build a financial wrapper or bundle, select
facts, build trajectories, interpret direction, or perform persistence,
provider, API, worker, alert, recommendation, or execution work.

## 1. Audit result and policy lineage

The current financial chain is `FinancialFact -> PIT selection ->
FinancialMetricObservation -> FinancialResearchObservationBundle -> future
Brain input`. The existing Shared-Brain chain is `UnifiedIntelligenceState ->
BrainResearchComparisonState -> ResearchStateDelta`.

`brain-research-comparability-policy / v1-approved` correctly classifies
`FINANCIAL_RAW` as `PIT_REBUILDABLE`. Its general financial identity covers
instrument, metric, scope, currency, value dimension, unit, scale, period type,
value basis, fiscal alignment, normalization, revision, PIT, and quality. It
does not define the canonical financial-observation artifact, a complete
accounting-period slot, exact selector-cutoff attestation, bundle lineage, or
multiple-period matching. It must not govern numeric financial integration.

The correct successor proposal is `brain-research-comparability-policy /
v2-proposed`, with future immutable lineage:

```text
v1-proposed -> v1-approved -> v2-proposed -> future v2-approved
```

`v1-approved` remains immutable and historically valid for v1 states. No v1
state is silently reinterpreted under v2. The approved inactive successor is
documented in [BRAIN_RESEARCH_COMPARABILITY_POLICY_V2_APPROVED.md](BRAIN_RESEARCH_COMPARABILITY_POLICY_V2_APPROVED.md).

## 2. Exact v1 gap matrix

| Required financial fact | v1 / current generic contract | v2 proposal |
| --- | --- | --- |
| Financial observation/schema | Not named or mandatory | Exact observation-schema ID/version/fingerprint parity. |
| Bundle/schema lineage | Not represented | Exact bundle-schema ID/version/fingerprint parity. |
| Period fingerprint | Generic string possible, not financial contract | Require exact `FinancialMetricPeriodIdentity.fingerprint` plus expanded field consistency. |
| Type/basis/dates/fiscal metadata | Broad v1 terms only | Complete financial semantic slot; conflict fails closed. |
| Selector policy/mode | No selected-vintage lineage | Exact policy ID/version/fingerprint and knowledge mode. |
| Selector cutoff | No attestation | Exact cutoff equals the state `as_of`. |
| Source semantic/observation fingerprints | Not specified | Mandatory tamper and lineage evidence, never slot key. |
| Multiple same-metric periods | Tuple permits them | Full period slot matching; no latest-only or order matching. |
| `PARTIAL` period identity | No disposition | Factual artifact allowed; numeric comparison `INSUFFICIENT`. |
| Selector/materializer failures | Not a numeric role | Separate typed input-sufficiency lineage. |

## 3. Backward compatibility and Brain-version coupling

v2 retains every v1 source rule, domain rule, precondition, non-comparable
case, and exclusion unchanged for setup, diagnostics, scorecards, macro,
technicals, sector, and every other existing domain. It adds explicit
financial-observation semantics only to the existing `FINANCIAL_RAW` domain.

Financial numeric wrappers change Brain-state contents and methodology. A
future `BrainResearchComparisonState` v2 and methodology v2 must bind to v2
comparability governance. A v1-to-v2 comparison is foundationally
`NON_COMPARABLE`; the current state validator requires both states to bind one
exact policy triple and no cross-version equivalence exists. Within two future
v2 states, financial parity failures remain dimension-local.

## 4. Required bundle, schema, selector, and PIT parity

Both financial inputs must prove identical approved lineage:

```text
bundle schema ID / version / fingerprint
observation schema ID / version / fingerprint
selector policy ID / version / fingerprint
knowledge mode = KNOWLEDGE_AT_THE_TIME
```

Different schema, bundle, selector policy, selector mode, or state methodology
is `NON_COMPARABLE`; no cross-schema or cross-policy conversion exists.

`visible_as_of` and `selection_as_of` have different jobs. `visible_as_of` is
when a source fact first became knowable and must be no later than its state.
`selection_as_of` is the exact cutoff used to select a vintage and must satisfy:

```text
previous selection_as_of == previous bundle.as_of == previous state.as_of
current  selection_as_of == current  bundle.as_of == current  state.as_of
previous/current visible_as_of <= their respective state as_of
```

They must not be equated. Missing exact cutoff attestation is `INSUFFICIENT`,
not an inference from `visible_as_of`.

## 5. Financial semantic observation-slot identity

The future wrapper and v2 policy must use this exact deterministic slot key:

```text
canonical instrument ID
fact kind / statement domain
financial metric
statement scope
period type and value basis
period start and period end
fiscal year and fiscal quarter where supplied
value dimension
currency, unit, and scale
normalization identity/version
FinancialMetricPeriodIdentity fingerprint
observation-schema ID / version / fingerprint
```

The period fingerprint is mandatory as compact integrity evidence. Expanded
period fields are retained to detect a wrapper whose claimed fingerprint and
fields conflict. This intentional duplication performs validation, not
conversion.

`source_fact_id`, source-fact semantic fingerprint, observation fingerprint,
selection-result fingerprint, filing/source/revision-parent, quality,
provenance, and artifact IDs are deliberately not slot fields. They remain
mandatory lineage and tamper evidence. A changed source fact for revised Q1
revenue can therefore be the same accounting slot with changed value/lineage.

## 6. Representation, scope, period, and `PARTIAL` rules

* Scope is exact: consolidated, standalone, and unknown only pair with
  themselves; unknown is never promoted.
* Period type and basis are exact. Quarterly, annual, point-in-time,
  quarter-only, cumulative/YTD, and full-year facts have no implied bridge.
* `COMPLETE` periods require exact economic dates and supplied fiscal metadata.
  Conflicting date/fiscal claims are `NON_COMPARABLE`.
* Currency, unit, scale, value dimension, and normalization identity/version
  are exact. No conversion is authorized.
* EPS/per-share values need exact representation and explicit equal
  normalization/share-basis identity. An unproven relevant share basis is
  `INSUFFICIENT`; a contradictory basis is `NON_COMPARABLE`.
* Shares outstanding and face value may be factually compared under full parity;
  comparability has no favorable/unfavorable meaning.
* Cash-flow quarter-only, YTD/cumulative, and annual bases never pair across
  bases. H1-minus-Q1 and implied-Q2 reconstruction are prohibited.
* `PARTIAL` observations remain auditable bundle artifacts and may be present,
  added, removed, or lineage-replaced, but their numeric comparison is
  `INSUFFICIENT`. `INSUFFICIENT` identity is already barred by the frozen
  observation and bundle schemas.

## 7. Multiple-period, revision, and delta requirements

Matching must join only on the full slot key, never metric name, arrival order,
period end alone, or a latest-only field. One state may contain Q1 FY2025, Q1
FY2026, Q2 FY2026, and FY2025 revenue. If Q2 is new while Q1 persists, Q2 is
`ADDED`; Q1 must not be paired to Q2 as `VALUE_CHANGED`.

A same-period selected revision may be factual `VALUE_CHANGED` and/or
`LINEAGE_CHANGED`. A change to source-fact semantic fingerprint or observation
fingerprint alone is not non-comparability: those fingerprints are lineage and
tamper identities, not pairing keys. This is evidence replacement, never a
financial trajectory or business improvement claim.

## 8. Current generic-wrapper and delta audit

`ResearchMetricObservation` can technically carry a future lossless wrapper:
it includes Decimal value, unit, scale, basis, scope, period identity,
effective/published timestamps, methodology ID/version, source artifact
fingerprint, dependency fingerprint, eligibility, lineage, and canonical
`identity_components`. `ResearchDimensionState` stores an ordered tuple, so
repeated `metric_id` values are supported.

That is not yet a safe wrapper contract. A future frozen wrapper must require
all slot fields, selector/bundle/observation lineage, source role, source
artifact fingerprint equal to the financial observation fingerprint, source
semantic fingerprint as lineage, and financial period fingerprint as generic
period identity. Display labels cannot reconstruct the accounting slot.

`ResearchStateDelta` groups by `metric_id`, attempts exact `_semantic_identity`
matches (including period identity and identity components), then **zips
remaining same-label observations**. That fallback avoids false value changes
but cannot represent unmatched Q1/Q2 records as independent `ADDED`/`REMOVED`:
it emits a non-comparable pair. A separate hardening slice must replace that
fallback for future financial wrappers with full-slot joins plus independent
unmatched additions/removals. It must not change v1 behavior without explicit
governance.

## 9. Reference, failure, and overlap ownership

Existing Unified-State financial artifact references and future numeric wrappers
are distinct roles. A future wrapper contract must mark, for example,
`FINANCIAL_EVIDENCE_REFERENCE` versus `FINANCIAL_NUMERIC_OBSERVATION` in a
canonical role field or identity component. They cannot collide or be compared
as one metric, and later semantic consumers must not double count them.

Bundle selector/materializer failures are typed financial input-sufficiency
lineage, not numeric observations. Future v2 may report their factual
transitions dimension-locally but must never convert them to zero or pair a
failure with a number as `VALUE_CHANGED`.

`IntelligenceDelta` remains owner of broad Unified-State
availability/freshness/reliability/integrity transitions. A future financial
research delta may own only selected-vintage/bundle input sufficiency and
numeric lineage. Those outputs can describe related evidence but must retain
provenance; no later layer may aggregate them twice. This proposal creates no
new output.

## 10. Proposed v2 rule structure and firewalls

Future v2 should extend the existing frozen-policy architecture with immutable
rules for: schema parity; bundle/selector/mode parity; exact selector cutoff;
semantic slot identity; period fingerprint consistency; representation and
normalization parity; per-share disposition; `PARTIAL` disposition; numeric
wrapper source role; full-slot added/removed behavior; and typed input-failure
ownership. Outcomes and reason codes must be versioned policy data, not hidden
financial special cases in a comparator. No v2 fingerprint is created here.

This policy governs accounting-observation comparability only. Q1 and Q2 are
different slots; a trajectory engine must later and explicitly define temporal
pairing. `VALUE_CHANGED` is factual only: it is not growth, directionality,
thesis/opportunity, risk, alert, recommendation, action, or execution.

**U14D-6N closure:** this proposal is frozen as
`brain-research-comparability-policy / v2-approved`; the immutable artifact,
fingerprint, and approved rules are recorded in
[BRAIN_RESEARCH_COMPARABILITY_POLICY_V2_APPROVED.md](BRAIN_RESEARCH_COMPARABILITY_POLICY_V2_APPROVED.md).
The next required slice is ResearchStateDelta full-slot matching hardening only.
It must not alter v1, integrate the Brain state, create a wrapper or bundle
builder, or implement trajectory or operational behavior.

## 11. Audit sources and explicit non-changes

Audited actual sources: `app/intelligence/brain_research_comparability_policy.py`,
`app/intelligence/brain_research_comparison_state.py`,
`app/intelligence/research_state_delta.py`,
`app/fundamentals/financial_fact_vintage_selector.py`,
`app/fundamentals/financial_metric_observation_schema.py`,
`app/fundamentals/financial_research_observation_bundle_schema.py`, and their
focused unit tests.

No frozen policy, approved v2 artifact, policy implementation, Brain state,
state builder, delta matcher, financial wrapper, bundle builder, selector,
materializer, trajectory, directionality, thesis/opportunity interpretation,
alert, recommendation, action, persistence, migration, provider/API/worker,
or scheduler behavior changed.
