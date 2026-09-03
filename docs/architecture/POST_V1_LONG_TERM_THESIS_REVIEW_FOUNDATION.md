# Post-V1 Long-Term Thesis Review Foundation

**Status: `APPROVED_FOR_IMPLEMENTATION / RESEARCH_SHADOW / WATCH_ONLY / NON_EXECUTABLE / NOT_ACTIVE`.**

## Scope

This bounded foundation is an immutable, deterministic review of an already
materialized Core V1 `BrainOutputProjection` for `DEEP_ANALYSIS`. It does not
create a second dossier, select a long-term strategy, calculate a score,
interpret financial facts, evaluate valuation, create milestones, or access a
portfolio. It stores nothing and has no API, UI, provider, runtime-clock,
broker, order, or capital-authority dependency.

The sole positive foundation result is that the supplied dossier provenance is
exact, PIT-valid, and suitable for future policy-specific research. It never
means that any long-term thesis family is eligible.

## Canonical source boundary

The existing Core `BrainOutputProjection` is the only dossier boundary. Its
`DEEP_ANALYSIS` projection retains canonical instrument identity, requested
as-of, projection/evaluation/unified-state identities and fingerprints,
section references, availability, freshness, warnings and blockers. The
foundation receives an immutable, injected reference to those facts; it does
not query, copy, rebuild, or extend the Core dossier.

Each candidate must carry canonical instrument ID; Core dossier projection ID
and content fingerprint; `DEEP_ANALYSIS` context, requested as-of, and source
availability time; non-empty exact diagnostic/evidence references with
fingerprints and availability times; and an explicit dossier evidence state
(`AVAILABLE`, `UNAVAILABLE`, `STALE`, `CONFLICTED`, or `NON_COMPARABLE`).

Every timestamp must be timezone-aware and not later than the requested review
`as_of`. The review normalizes timestamps to UTC. It rejects empty, duplicate,
or conflicting references and rejects a candidate whose stored content
fingerprint, source version, or dossier identity cannot be verified. No
current/latest lookup or runtime time is allowed.

## Family and availability contract

The contract recognizes exactly `LONG_TERM_QUALITY_FAIR_VALUE`,
`LONG_TERM_FUNDAMENTAL_COMPOUNDER`, `LONG_TERM_FUNDAMENTAL_INFLECTION`,
`LONG_TERM_POLICY_TRANSMISSION`, and
`LONG_TERM_ASYMMETRIC_EMERGING_COMPOUNDER`.

Every family returns a deterministic review. The common review state may be
`DOSSIER_OBSERVED`, `DATA_INSUFFICIENT`, `CONFLICTED`,
`TEMPORALLY_INVALID`, or `UNVERIFIABLE`. A verified dossier produces
`DOSSIER_OBSERVED` only. Its family policy availability remains
`POLICY_UNAVAILABLE` for all five identifiers until a later exact family
policy and data contract are accepted.

The foundation retains explicit blockers and unavailable reasons but must not
fabricate horizon, cadence, valuation, scenario, milestone, invalidation,
quality, growth, cash, leverage, or financial-sector result.

## Determinism and safety

A review identity uses contract version, canonical instrument, thesis family,
requested as-of, dossier ID, dossier fingerprint, and source policy version.
A distinct content fingerprint covers every serialized field, including
lineage, state, and blockers. Collections are sorted deterministically;
duplicate or conflicting logical references are rejected rather than silently
dropped. Tampering is fail-closed.

All outputs are `WATCH_ONLY / NON_EXECUTABLE`. No output may contain an
investment instruction, price, target, quantity, allocation, portfolio object,
order, broker interface, score, or performance claim.

## Acceptance and later work

Focused tests must prove immutability, all five identities, UTC equivalence,
future-evidence exclusion, duplicate/conflicting lineage rejection, tamper
detection, stable serialization, policy unavailability, and no forbidden
dependencies.

The five family evaluators remain separate later slices. Their requirements in
[the Long-Term policy pack](POST_V1_LONG_TERM_THESIS_FAMILY_POLICY_PROPOSAL.md)
and [dossier readiness receipt](POST_V1_LONG_TERM_EVIDENCE_DOSSIER_REUSE_AND_READINESS.md)
remain binding; no common-contract result upgrades an unavailable family.
