# Financial Research Observation Bundle Proposal

**Status: PROPOSED — NOT APPROVED — NOT SELECTED — NOT ACTIVE.**

**Lineage update:** the proposed structural contract is now frozen as
`financial-research-observation-bundle-schema / v1-approved`, while remaining
not selected and not active. See
[FINANCIAL_RESEARCH_OBSERVATION_BUNDLE_SCHEMA_APPROVED.md](FINANCIAL_RESEARCH_OBSERVATION_BUNDLE_SCHEMA_APPROVED.md).

U14D-6K is a governance audit only. It does not implement a bundle or builder,
change Shared Brain, policy, delta, selector, materializer, persistence,
trajectory, directionality, thesis/opportunity interpretation, alert,
recommendation, or execution.

## 1. Purpose and boundary

The proposed `FinancialResearchObservationBundle` is a derived, immutable,
deterministic, portfolio-independent, non-persisted handoff at one exact
`canonical_instrument_id + as_of`. It answers only which already-selected,
already-materialized financial observations are valid at that knowledge cutoff,
and which upstream financial inputs failed.

It is neither canonical evidence nor another financial store, selector,
materializer, trajectory, Brain, confidence score, recommendation artifact, or
action boundary.

## 2. Target identity and same-as-of invariant

A future v1 bundle must retain canonical instrument ID, timezone-aware target
`as_of`, knowledge-at-the-time mode, observation-schema lineage,
fact-vintage-selection-policy lineage, bundle-schema identity/version, and a
deterministic fingerprint. It must contain no runtime creation timestamp.

**Required v1 invariant:** every included observation and every recorded
upstream failure must be attested to a selector result with
`selection_as_of == bundle.as_of` exactly. No `<=` exception is safe in v1:
an original fact selected at T1 may no longer be the winning vintage at T2
after a revision becomes visible. The bundle does not rerun selection to find
out.

This differs from factual visibility. An observation with `visible_as_of` Aug 1
is valid in a bundle at Aug 20 when its selector attestation says Aug 20;
`visible_as_of` must remain Aug 1.

## 3. Proposed minimal contracts

### `FinancialResearchObservationAttestation`

One immutable attestation per successful observation:

- observation fingerprint;
- source fact ID;
- selection-result fingerprint;
- timezone-aware `selection_as_of`;
- selection policy ID/version/fingerprint;
- observation schema ID/version/fingerprint; and
- deterministic attestation fingerprint.

It does not copy the observation and does not invent a materializer version.
The current materializer has no separate formal version identity; the frozen
observation schema and selector policy are the available contract lineage.

### `FinancialResearchInputFailure`

One immutable, typed factual summary per failed upstream input:

- `semantic_key: FinancialFactSemanticKey | None`;
- stage: `SELECTION` or `MATERIALIZATION`;
- upstream status/reason codes using existing selector/materializer vocabulary;
- timezone-aware selection as-of;
- source fact ID when available;
- relevant selection/materialization-result fingerprint; and
- deterministic failure fingerprint.

This distinguishes `UNAVAILABLE`, `CONFLICTED`, `INVALID_LINEAGE`,
`INSUFFICIENT_IDENTITY`, and materialization `REJECTED`; none becomes generic
“missing” or numeric zero.

### `FinancialResearchObservationBundle`

The future bundle contains canonical ordered `FinancialMetricObservation`
objects, their attestations, canonical failure summaries, target identity and
lineage, and a deterministic fingerprint. No generic `ResearchMetricObservation`
belongs in this pre-Brain contract.

The bundle need not have an overall availability/status. Foundational invalid
input fails construction; ordinary factual partiality and upstream failures are
preserved as entries.

## 4. Binding, schema, and period validation

For each observation/attestation pair, a future builder must validate exact
fingerprint integrity, source fact ID, selection-result fingerprint, instrument,
schema lineage, selector lineage, `selection_as_of == bundle.as_of`, and
`visible_as_of <= bundle.as_of`. No raw fact reconstruction is permitted.

v1 requires exactly:

- `financial-metric-observation-schema / v1-approved /
  6d55e73ee78f0074789165952a287d9b8b6ec801ce98703e9a136603f3da3caf`; and
- `financial-fact-vintage-selection-policy / v1-approved /
  862dc470ebd58abd2d066f2604440908eaf3aa9827e6c93b588b5f1bf806fc13`.

Mixed schema or selector-policy versions have no cross-version normalization.
`COMPLETE` and valid factual `PARTIAL` periods are retained; `INSUFFICIENT`
period identity cannot be admitted as an observation and is instead represented
only through an upstream failure summary.

The bundle retains all explicitly supplied periods. It must not impose latest,
four-quarter, multi-year, or other horizon before a trajectory policy governs
that decision.

## 5. Ordering, duplicates, conflicts, and tampering

Observation ordering must be deterministic:

```text
fact kind -> metric -> scope -> period type -> value basis -> period end
-> period start -> fiscal metadata -> period fingerprint -> observation fingerprint
```

Failure summaries use canonical semantic-key ordering, then stage/status/reason
and fingerprint. Exact duplicate observations, attestations, or failures should
be rejected as duplicate input rather than silently deduplicated: that makes
attempt count and upstream handoff errors explicit without changing a bundle
fingerprint. Duplicate policy can be reconsidered only under later governance.

Two different observations claiming the same complete financial identity
(metric, fact kind, scope, period identity, representation, normalization) but
different values/source semantic fingerprints are a foundational contradictory
input and fail whole-bundle construction. Likewise, a successful observation
and a failure for the same semantic key/as-of are contradictory unless a future
typed rule proves they refer to distinct source facts; v1 fails closed.

Tampered observation or attestation fingerprints, binding mismatch, foreign
instrument input, or mixed as-of input fail closed. The bundle never repairs,
reselects, or chooses between inputs.

## 6. Failure summaries and coverage

Option B is recommended: retain deterministic, lossless typed failure summaries
plus upstream fingerprints, rather than embedding complete failed selector and
materializer objects in every bundle. The objects are derived/non-persisted;
therefore the summary preserves their key, stage, status, reasons, as-of and
fingerprint—not a fingerprint-only reference that cannot explain a later state.

Canonical aggregate coverage counts are unnecessary because they are exactly
derivable from ordered observations and failure entries. A read-only caller may
derive materialized, unavailable, conflicted, invalid-lineage,
insufficient-identity, rejected, and partial-period counts without creating a
confidence, quality grade, or score.

## 7. Shared-Brain and delta handoff

Future `BrainResearchComparisonState` should accept exactly one validated
bundle matching its own instrument/as-of. It must not separately accept raw
facts, selections, materialization results, or a second financial path.

Existing Unified-State financial references may initially coexist: references
express evidence coverage/lineage, while bundle observations express normalized
numeric facts. Future consumers must not double-count them. A later lossless
adapter may map bundle observations to generic `ResearchMetricObservation`,
but must preserve metric, scope, full period fingerprint, representation,
normalization, source semantic fingerprint, observation schema, selector
lineage, and source observation fingerprint.

`ResearchStateDelta` changes nowhere in this slice. Its current matching can
distinguish multiple periods only if that future wrapper carries the full
identity. It cannot derive trajectories, QoQ, YoY, TTM, directionality, or
meaning from bundle contents.

## 8. Required future comparability-policy revision

Before Brain integration, a governed comparability-policy revision must cover:

- exact observation-schema parity;
- full financial period-identity parity;
- exact selector-as-of attestation and selector policy lineage;
- source semantic and source-observation fingerprint treatment;
- lossless wrapper identity;
- `PARTIAL` period disposition; and
- separation of existing financial artifact references from numeric wrappers.

The current approved `brain-research-comparability-policy / v1-approved`
remains unchanged and is insufficient for that integration.

## 9. Reconstructibility and explicit exclusions

Same explicit observations, attestations, failures, instrument, as-of and
schema must yield the same bundle fingerprint. The future boundary has no DB,
store, provider, network, filesystem, current-clock, mutable-global, cache, or
persistence dependency.

The bundle contains independent factual observations only: no pairing, QoQ,
YoY, annual YoY, TTM, numeric delta, growth, sign transition, directionality,
materiality, thesis/opportunity result, alert, recommendation, BUY/HOLD/SELL/
TRIM/ROTATE, order, or execution.

## 10. Recommended next sequence

The next exact slice should freeze an approved bundle schema proposal only,
including its attestation, failure-summary, duplicate, collision, and same-as-
of rules. It must not implement a bundle, revise comparability policy, modify
Brain state, or construct a trajectory.
