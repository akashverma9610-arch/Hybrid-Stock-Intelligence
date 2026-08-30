# Frozen Financial Research Observation Bundle Schema

**Status: APPROVED — NOT SELECTED — NOT ACTIVE.**

## Identity

| Field | Value |
| --- | --- |
| Schema ID | `financial-research-observation-bundle-schema` |
| Version | `v1-approved` |
| Proposal lineage | `v1-proposed -> v1-approved` |
| Approval | `APPROVED` |
| Approver | `human:Akash-Verma` |
| Selected for future bundle | `false` |
| Active | `false` |
| Knowledge mode | `KNOWLEDGE_AT_THE_TIME` |
| Fingerprint | `aba6123afc78781b4ac011fe048ed10d91b7e8af3f10944f25558be5f2036a89` |

## Frozen passive contracts

`FinancialResearchObservationAttestation` binds one canonical
`FinancialMetricObservation` fingerprint and source fact ID to its
selection-result fingerprint, exact selection as-of, selector-policy lineage,
observation-schema lineage, and own deterministic fingerprint. It contains no
financial value, raw fact, or full selection.

`FinancialResearchInputFailure` retains one factual upstream failure: canonical
instrument, optional existing `FinancialFactSemanticKey`, `SELECTION` or
`MATERIALIZATION` stage, exact selection as-of, existing typed status/reasons,
available source/upstream fingerprints, required selector/schema lineage, and
its deterministic fingerprint. It preserves selector `UNAVAILABLE`,
`CONFLICTED`, `INVALID_LINEAGE`, `INSUFFICIENT_IDENTITY`, and materializer
`REJECTED` as distinct facts.

`FinancialResearchObservationBundle` retains one instrument, exact timezone-
aware as-of, knowledge mode, frozen schema/policy lineage, ordered actual
financial observations, ordered attestations, ordered failures, and a
deterministic fingerprint. It has no global quality, completeness, degraded,
or confidence status.

## Frozen v1 invariants

- Every admitted observation and failure has `selection_as_of == bundle.as_of`.
  No mixed selector cutoffs or v1 exception is allowed.
- `observation.visible_as_of <= bundle.as_of`; visibility remains the original
  fact-availability time and is never rewritten to the bundle cutoff.
- Only exact observation-schema v1-approved and selector-policy v1-approved
  lineage is admitted. No mixed version or cross-schema normalization exists.
- `COMPLETE` and factual `PARTIAL` observations are admitted; `INSUFFICIENT`
  observations are not.
- Multiple periods of the same metric remain separate. No latest-only field or
  history-horizon policy is present.
- Duplicate observation, attestation, or failure input is invalid. A same-full-
  semantic financial identity with incompatible observations, or a same-key
  observation/failure contradiction, is invalid rather than resolved here.
- Fingerprint, instrument, schema/policy, binding, temporal, and ordering
  violations fail closed. No repair, store lookup, selector rerun, or
  materialization rerun is part of this contract.

## Ordering and fingerprint

Observation order is canonical by fact kind, metric, scope, period type/basis,
period end/start, fiscal metadata, period fingerprint, then observation
fingerprint. Failures are canonically ordered by semantic key, stage, status,
reasons, and fingerprint. Bundle identity includes target identity/lineage and
ordered entry fingerprints only; it contains no runtime timestamp or insertion
order.

## Future comparability requirements

Before any Shared-Brain integration, future comparability governance must
address observation-schema parity, full financial period identity,
same-as-of selector attestation, source semantic and observation fingerprints,
future wrapper identity, `PARTIAL` period treatment, and the separation between
existing financial artifact references and numeric wrappers.

## Explicit non-activation

This schema introduces no bundle builder, selector/materializer invocation,
comparability-policy revision, Brain-state or delta integration, generic
wrapper, trajectory, directionality, thesis/opportunity interpretation, alert,
recommendation, execution, persistence, provider/network/API, worker, or
scheduler behavior.
