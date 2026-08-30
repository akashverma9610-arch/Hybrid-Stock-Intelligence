# Financial Research Observation Wrapper Schema v1

**Status: APPROVED — NOT SELECTED — NOT ACTIVE.**

## Identity

| Field | Value |
| --- | --- |
| Schema | `financial-research-observation-wrapper-schema` |
| Version | `v1-approved` |
| Fingerprint | `62ce6dc13dab80a3a468307f24b88d888a8d42226a7506c671d00c86e1b4f95c` |
| Proposal lineage | `v1-proposed -> v1-approved` |
| Approver | `human:Akash-Verma` |
| Selected / active | `false / false` |

This is a passive mapping contract. It does not construct a wrapper or
integrate any financial observation into Shared Brain.

## Frozen future mapping

A future pure whole-bundle adapter may map exactly one admitted
`FinancialMetricObservation` to one generic factual observation in
`FINANCIAL_RAW`:

```text
metric_id                    = FinancialMetric.value
value_type                   = FACTUAL_VALUE
value                        = exact Decimal
unit / scale / basis / scope = exact financial representation
period_identity              = financial period fingerprint
source_artifact_type         = FINANCIAL_METRIC_OBSERVATION
source_artifact_fingerprint  = FinancialMetricObservation.fingerprint
source role                  = FINANCIAL_NUMERIC_OBSERVATION
```

`FINANCIAL_EVIDENCE_REFERENCE` remains a distinct source role. A reference and
a numeric wrapper must have distinct full observation slots and are not two
automatic confirmations of a later semantic conclusion.

## Slot identity

The future wrapper must put only accounting/representation semantics in generic
slot identity: financial fact kind, currency, value dimension, period type and
basis, period dates, fiscal metadata, period strength, normalization identity,
period fingerprint, observation-schema identity, and source role. Currency,
fact kind, value dimension, and all fields without an exact generic first-class
representation remain canonical identity components.

Thus Q1 and Q2 revenue are distinct slots, while a same-Q1 revision remains
the same slot. `PARTIAL` remains a factual wrapper input; future v2 numeric
comparison treats it as insufficient. `INSUFFICIENT` is inadmissible.

## Non-slot lineage

The generic observation contract now has canonical immutable
`lineage_components`. It is included in generic artifact/delta lineage identity
but intentionally excluded from `research_observation_slot_key()`.

The frozen financial wrapper keys preserve selector, bundle, source, filing,
revision, quality, provenance, availability, and source-fact lineage:

```text
financial_source_fact_id
financial_source_semantic_fingerprint
financial_selection_result_fingerprint
financial_selection_as_of
financial_selector_policy_id / version / fingerprint
financial_bundle_schema_id / version / fingerprint
financial_bundle_fingerprint
financial_bundle_as_of
financial_visible_as_of
financial_received_at
financial_source_name / filing_id / source_reference
financial_revision_of_fact_id / parent_fact_ids
financial_quality_flags / provenance
```

All future values must use canonical UTC ISO-8601 timestamps, enum values, and
deterministic canonical tuple serialization—never Python `repr` or locale
formatting. Observation schema ID/version/fingerprint, bundle schema lineage,
and selector policy lineage remain exact; the future adapter validates
`selection_as_of == bundle.as_of` before construction.

## Revision and boundary guarantees

Changing non-slot lineage alone keeps the same observation slot and can produce
a factual `LINEAGE_CHANGED`. A value plus lineage change retains the current
single primary delta kind `VALUE_CHANGED`; both source artifact fingerprints
remain in the delta for audit. No multiple-kind redesign is introduced here.

The eventual adapter API is frozen only as a design:

```text
wrap_financial_research_observation_bundle(bundle, *, wrapper_schema)
  -> tuple[ResearchMetricObservation, ...]
```

It must consume an already validated bundle, never raw facts, selection
collections, provider payloads, or materialization requests. Bundle failures
remain typed input-sufficiency lineage and are never fake numeric metrics.

## Explicit exclusions

No wrapper execution, bundle adapter, Brain-state v2, `FINANCIAL_RAW`
projection, `ResearchStateDelta` slot-matching change, trajectory, QoQ/YoY/TTM,
directionality, thesis/opportunity interpretation, alert, recommendation,
execution, persistence, provider/API, worker, or scheduler behavior is
authorized or implemented by this schema.
