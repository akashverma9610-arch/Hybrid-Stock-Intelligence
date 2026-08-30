# Brain Research Financial Observation Integration Proposal

**Status: PROPOSED — NOT APPROVED — NOT SELECTED — NOT ACTIVE.**

U14D-6J is a governance audit only. It does not build a financial bundle,
modify `BrainResearchComparisonState` or `ResearchStateDelta`, select or
materialize facts, construct trajectories, or create directional, thesis,
opportunity, alert, recommendation, or execution semantics.

## Current state and gap

`BrainResearchComparisonState` already includes the `FINANCIAL_RAW` domain.
Its normal content is Unified-State fundamentals/earnings artifact references;
it can also receive explicitly supplied generic `ResearchMetricObservation`
values. The generic contract preserves a factual value, representation,
period/scope/basis identity, temporal fields, artifact/dependency fingerprints,
eligibility, lineage, warnings, and blockers. It receives no numeric values
from the financial selector/materializer chain today.

`FinancialMetricObservation` is now the canonical financial-domain derived
artifact. It owns exact Decimal value, typed period identity, source fact ID,
source semantic fingerprint, filing/source/revision/quality/provenance,
visibility, selector-policy/result lineage, and frozen schema lineage. It must
remain the sole owner of those financial semantics.

## Options and recommendation

| Option | Audit result |
| --- | --- |
| Specialized nested financial values | Preserves lineage but makes `ResearchDimensionState` a mixed container and duplicates generic state/delta mechanics. Not recommended. |
| Deterministic generic wrapper | Recommended only when it is losslessly derived from one `FinancialMetricObservation`. No independent financial value or identity reconstruction. |
| References only | Retains audit identity but loses values and periods required for a later trajectory boundary. Insufficient. |

`FinancialMetricObservation` remains the financial canonical derived artifact.
The future state may use a generic wrapper only to join the existing dimension
and delta contracts. The wrapper must set its source-artifact fingerprint to the
financial observation fingerprint and retain complete financial identity in
canonical `identity_components`; it is not a competing representation.

## Proposed input boundary

The future state builder must not accept raw facts, selections, provider
payloads, or selector/materializer engines. It should accept one explicit,
immutable `FinancialResearchObservationBundle`, conceptually:

```text
canonical_instrument_id + state_as_of + observation-schema lineage
+ ordered financial observations
+ selector-as-of attestations bound to selection-result fingerprints
+ typed selector/materializer absence, conflict, and rejection summaries
+ deterministic bundle fingerprint
```

The bundle is necessary because the existing observation retains a
`selection_result_fingerprint` but not the selector's `as_of`. Neither the
observation nor its materialization result can prove that it was selected at
the target Brain-state time. The bundle must carry a timezone-aware
`selection_as_of` bound to the exact result fingerprint. This is provenance,
not a re-selection mechanism.

## Future validation and lineage

Each future supplied observation must be validated as follows:

- Its instrument equals the bundle/state instrument; mixed input fails closed.
- Its own fingerprint validates; `INSUFFICIENT` period identity is invalid.
- Its schema equals `financial-metric-observation-schema / v1-approved /
  6d55e73ee78f0074789165952a287d9b8b6ec801ce98703e9a136603f3da3caf`.
- Its selector lineage equals `financial-fact-vintage-selection-policy /
  v1-approved /
  862dc470ebd58abd2d066f2604440908eaf3aa9827e6c93b588b5f1bf806fc13`.
- `visible_as_of <= state_as_of`; neither publication time nor state as-of may
  replace accounting-period identity.
- Initial safe rule: every bound `selection_as_of == state_as_of`, preventing
  a stale earlier selection from entering a later state after a possible
  revision.
- Source fact ID/semantic fingerprint, metric, fact kind, value dimension,
  scope, currency/unit/scale, normalization, period, filing/source,
  revision, quality, and provenance remain represented.

## Period multiplicity, collision, and ordering

One state may retain Q2 FY2026, Q1 FY2026, Q2 FY2025, and FY2025 revenue. It
must never flatten them to “latest revenue.” The required history horizon must
wait for the future approved trajectory policy; this proposal sets no arbitrary
count and does not create a duplicate financial database.

A generic wrapper may use `financial:<metric>` as its metric ID only when its
full `period_identity` is the financial period-identity fingerprint. Its
identity components must include the period fingerprint, fact kind, source
semantic fingerprint, scope, representation, normalization, observation-schema
lineage, selector-policy lineage, and source-observation fingerprint.

Canonical ordering is:

```text
fact kind/domain -> metric -> scope -> period end -> value basis
-> period identity fingerprint -> source observation fingerprint
```

Exact duplicate observation fingerprints must be deduplicated once or rejected
under a future frozen bundle rule. Distinct observations claiming one full
semantic/period identity with conflicting values fail closed; the Brain boundary
must not re-resolve facts.

## Existing generic and delta compatibility

`ResearchMetricObservation` accepts `Decimal` and its containing tuple permits
multiple same-metric entries. `ResearchStateDelta` groups by `metric_id` and
then matches semantic identity including period identity, unit, scale, basis,
scope, methodology, dependency, and identity components. Therefore it can
safely distinguish Q1 from Q2 only if the future wrapper supplies the exact
full financial period identity and lineage.

It cannot construct a financial trajectory: a new period is `ADDED`, while
period mismatch is non-comparable. It can report same-period factual revision
or lineage change under parity. No QoQ, YoY, TTM, numeric trajectory,
directionality, or thesis conclusion is authorized in the delta.

## Failure and coverage treatment

The future bundle needs stable typed summaries distinguishing:

- no PIT-eligible fact;
- selector unavailable/conflicted/invalid-lineage/insufficient-identity;
- materialization rejection, including invalid Decimal or insufficient period;
- factual `PARTIAL` period identity.

Successful observations and failure summaries remain separate. Absence is not
numeric zero; rejected attempts do not disappear. `PARTIAL` observations remain
factual with a trajectory blocker. `INSUFFICIENT` observation input fails
closed. Existing `ResearchDimensionState` warnings/blockers are sufficient for
initial factual summary; no quality/confidence score is authorized.

## Dimension, version, and policy impact

Use the single existing `FINANCIAL_RAW` domain initially. Do not add statement
subdimensions until future governance proves that metric/fact-kind identity is
insufficient.

The frozen comparability policy already classifies raw financial facts as
`PIT_REBUILDABLE` and requires financial parity, but does not explicitly cover
observation-schema lineage, source semantic fingerprints, or selector-as-of
attestations. A future governed policy revision is required before integration;
the approved v1 artifact remains unchanged.

Numeric wrapper integration changes Brain-state contents. It therefore requires
an explicit state-schema and research-methodology version transition, not a
silent reuse of `brain-research-comparison-state-v1`. Existing Unified-State
financial artifact references should initially coexist as coverage lineage;
wrappers are values and later consumers must not double-count them.

## Rebuildability and firewalls

A future state must be reconstructible only from the explicit Unified State,
explicit immutable bundle, and frozen policies/schema. Same inputs must yield
the same state fingerprint. Bundle, wrapper, and enhanced state remain derived
and non-persisted.

Financial integration remains portfolio-independent and changes no holdings,
P&L, allocation, Six Gates result, scan, diagnostic, score, provider access,
API, worker, scheduler, alert, recommendation, or trade. Trajectory creation
belongs later as a separate pure derivation adjacent to/after state, never
inside the state builder.

## Recommended future sequence

1. Governance proposal for `FinancialResearchObservationBundle`, including
   selector-as-of attestation and typed upstream failure summaries.
2. Freeze an approved comparability-policy revision recognizing this lineage.
3. Implement the pure bundle only; no Brain integration.
4. Govern and implement lossless wrapper plus an explicit Brain-state v2.
5. Independently govern trajectory policy and trajectory builder.

**Recommended next exact slice:** governance proposal for the
`FinancialResearchObservationBundle` contract only. It must not implement the
bundle, change the Brain state, revise policy, or construct trajectories.

The resulting same-as-of handoff contract is proposed in
[FINANCIAL_RESEARCH_OBSERVATION_BUNDLE_PROPOSAL.md](FINANCIAL_RESEARCH_OBSERVATION_BUNDLE_PROPOSAL.md).

## U14D-6M comparability-revision dependency

The approved passive bundle schema does not make numeric Brain integration safe
under immutable v1 comparability governance. U14D-6M records the required
successor-policy audit in
[BRAIN_RESEARCH_COMPARABILITY_POLICY_FINANCIAL_REVISION_PROPOSAL.md](BRAIN_RESEARCH_COMPARABILITY_POLICY_FINANCIAL_REVISION_PROPOSAL.md).

Before a wrapper or Brain-state v2 exists, the future policy must govern exact
bundle/observation-schema/selector-policy lineage, exact selector-as-of
attestation, complete accounting-period slot identity, `PARTIAL` disposition,
source-role separation, and non-order-based matching. The audit also identifies
required delta hardening: the current same-`metric_id` fallback zips unmatched
observations and cannot express a new Q2 period as `ADDED` while Q1 remains
separately present. This reference changes no code; the successor policy
remains proposed and inactive.

## Explicit non-changes

No Brain-state/builder, generic observation, delta, financial
selector/materializer/schema, comparability-policy, persistence, migration,
provider/network/API/worker/scheduler, trajectory, directionality,
thesis/opportunity, alert, recommendation, or execution implementation changed.

## U14D-6Q wrapper-governance addendum

U14D-6Q audited the future lossless financial-to-generic wrapper boundary only.
The audit found that the existing `ResearchMetricObservation` can represent
exact Decimal values and full financial slot fields, but has no distinct,
canonical non-slot lineage field. Source fact, selector cutoff, bundle, and
quality/provenance lineage cannot be placed in `identity_components` without
making same-period revisions become different slots. This is a blocking generic
contract gap; no wrapper or Brain integration was implemented.

The proposed resolution is a future versioned
`financial-research-observation-wrapper-schema / v1-proposed` plus a governed
canonical non-slot lineage representation. The future pure adapter should take
one validated `FinancialResearchObservationBundle`, map each successful
observation one-to-one into `FINANCIAL_RAW`, retain failures as typed
dimension-local sufficiency lineage, and use separate
`FINANCIAL_EVIDENCE_REFERENCE` versus `FINANCIAL_NUMERIC_OBSERVATION` source
roles. Details are in
[FINANCIAL_RESEARCH_OBSERVATION_WRAPPER_PROPOSAL.md](FINANCIAL_RESEARCH_OBSERVATION_WRAPPER_PROPOSAL.md).
