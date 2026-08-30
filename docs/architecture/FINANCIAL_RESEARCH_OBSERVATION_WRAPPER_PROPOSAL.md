# Financial → Generic Research Observation Wrapper Proposal

**Status: HISTORICAL PROPOSAL — SUPERSEDED BY APPROVED v1 SCHEMA — NOT SELECTED — NOT ACTIVE.**

This U14D-6Q audit defines the required lossless boundary for a future numeric
financial representation in Shared Brain. It implements no wrapper, generic
contract change, Brain-state v2, or integration.

## Current generic capacity

`ResearchMetricObservation` currently provides: dimension, `metric_id`, typed
factual/artifact/limitation value, exact `Decimal` support, unit, scale, basis,
scope, one string `period_identity`, effective/published timestamps, window and
benchmark, methodology ID/version, source-artifact type/fingerprint, one
dependency-manifest fingerprint, source eligibility, freshness/integrity
lineage, canonical `identity_components`, warnings, and blockers. Its enclosing
`ResearchDimensionState` owns the generic state fingerprint; the observation
does not have an exposed standalone fingerprint. `ResearchStateDelta` derives a
deterministic observation fingerprint internally.

The current full slot is the generic first-class fields plus
`identity_components`. It deliberately excludes value, timestamps, source
artifact fingerprint, dependency manifest, freshness, and warnings/blockers.
This supports multiple `REVENUE` periods and revision pairing, but means
`identity_components` cannot carry mutable source/bundle/selection lineage.

## Losslessness matrix and current gap

| Financial factual field | Future generic representation | Current status |
| --- | --- | --- |
| Instrument | enclosing bundle and future Brain state; validate equality | available only at container level |
| Fact kind, metric | `financial_fact_kind` component; `metric_id = FinancialMetric.value` | available |
| Exact value | `value_type=FACTUAL_VALUE`, `value: Decimal` | available |
| Value dimension, currency | `financial_value_dimension`, `financial_currency` components | available, but not first-class |
| Unit, scale, scope, basis | generic `unit`, `scale`, `scope`, `basis` | available |
| Period type/start/end/fiscal data/strength | `period_identity=period.fingerprint` plus typed canonical components | available for slot data |
| Normalization version and period fingerprint | canonical slot components | available |
| `visible_as_of`, received/published timestamps | explicit non-slot lineage fields | **missing**: only published/effective fields exist |
| Source fact ID and source semantic fingerprint | explicit non-slot lineage fields | **missing** |
| Observation fingerprint | `source_artifact_fingerprint` | available |
| Observation schema lineage | schema identity in slot; full lineage in non-slot lineage | partially available |
| Selector policy/result/as-of | explicit non-slot lineage fields | **missing** |
| Bundle schema/fingerprint/as-of | explicit non-slot lineage fields | **missing** |
| Quality, provenance, filing/source/revision lineage | explicit non-slot lineage fields | **missing** |

The missing items are blocking generic-contract gaps. They must not be hidden
in warnings, blockers, a display label, or `identity_components`: those choices
would either be lossy or make same-accounting-period revisions become different
slots. No wrapper is safe until a future governed generic contract adds a
canonical, deterministically ordered `lineage_components` field (or an
equivalent separate immutable lineage contract) that is included in generic
observation/state fingerprints and lineage-change detection, but excluded from
`research_observation_slot_key()`.

## U14D-6R resolution

U14D-6R added the minimal backward-compatible generic
`lineage_components: tuple[tuple[str, str], ...] = ()` contract. It is
immutable, canonically ordered, duplicate-key-free, and contributes to generic
artifact/delta lineage identity when non-empty; it is deliberately excluded
from full observation-slot matching. Empty lineage retains the legacy serialized
observation shape for existing callers.

The wrapper mapping is now frozen as
`financial-research-observation-wrapper-schema / v1-approved`, fingerprint
`62ce6dc13dab80a3a468307f24b88d888a8d42226a7506c671d00c86e1b4f95c`,
approved by `human:Akash-Verma`, selected=false, active=false. Details are in
[FINANCIAL_RESEARCH_OBSERVATION_WRAPPER_SCHEMA_APPROVED.md](FINANCIAL_RESEARCH_OBSERVATION_WRAPPER_SCHEMA_APPROVED.md).
No wrapper function or Brain-state integration was added.

## Proposed future wrapper semantics

Use a one-to-one pure whole-bundle adapter, not a standalone fact adapter:

```text
wrap_financial_research_observation_bundle(bundle, *, wrapper_schema)
    -> tuple[ResearchMetricObservation, ...]
```

The adapter receives one already-validated immutable
`FinancialResearchObservationBundle`; it creates exactly one generic numeric
observation for every admitted financial observation and no generic numeric
observation for a `FinancialResearchInputFailure`. Whole-bundle input preserves
the exact instrument, one `as_of`, attestation coverage, selector cutoff, and
bundle lineages without selector/materializer reruns. It performs no storage,
provider, clock, trajectory, or interpretation work.

Proposed wrapper schema family:

```text
financial-research-observation-wrapper-schema / v1-proposed
PROPOSED, NOT APPROVED, NOT SELECTED, NOT ACTIVE
```

The wrapper schema needs its own identity because a mapping/slot change is
methodology drift even when the source financial observation schema is stable.
Future generic `methodology_id/version` should identify this wrapper schema;
the wrapper fingerprint belongs in non-slot lineage. A wrapper schema revision
must be methodologically non-comparable unless a separately governed bridge is
introduced.

## Exact future mapping

| Generic field | Required future financial mapping |
| --- | --- |
| `dimension` | existing `FINANCIAL_RAW` |
| `metric_id` | exact `FinancialMetric.value`; never embed period |
| `value_type`, `value` | `FACTUAL_VALUE`, exact Decimal; no conversion/rounding |
| `unit`, `scale`, `basis`, `scope` | exact financial unit, `NumericScale.value`, value basis, statement scope |
| `period_identity` | exact financial period fingerprint |
| `effective_at`, `published_at` | accounting period end; financial `published_at` respectively, without replacing visible-as-of |
| `source_artifact_type` | `FINANCIAL_NUMERIC_OBSERVATION` |
| `source_artifact_fingerprint` | exact `FinancialMetricObservation.fingerprint` |
| `source_eligibility` | `PIT_REBUILDABLE` only after future v2 state validation |
| methodology | future wrapper schema identity/version |
| dependency/lineage | governed exact lineage components; not a convenience hash-only replacement |

Required slot `identity_components` use stable keys:

```text
financial_fact_kind
financial_value_dimension
financial_currency
financial_period_type
financial_period_basis
financial_period_start
financial_period_end
financial_fiscal_year
financial_fiscal_quarter
financial_period_strength
financial_normalization_identity
financial_period_fingerprint
financial_observation_schema_identity
financial_source_role
```

All are semantic slot fields required by approved comparability policy v2.
`COMPLETE` and `PARTIAL` remain explicit; `PARTIAL` is factual but later numeric
comparison is `INSUFFICIENT`. `INSUFFICIENT` cannot be wrapped.

Required non-slot lineage components are:

```text
financial_observation_schema_fingerprint
financial_selector_policy_id
financial_selector_policy_version
financial_selector_policy_fingerprint
financial_selection_result_fingerprint
financial_selection_as_of
financial_bundle_schema_id
financial_bundle_schema_version
financial_bundle_schema_fingerprint
financial_bundle_fingerprint
financial_bundle_as_of
financial_visible_as_of
financial_received_at
financial_source_fact_id
financial_source_fact_semantic_fingerprint
financial_filing_id
financial_source
financial_source_reference
financial_revision_of_fact_id
financial_parent_fact_ids
financial_quality_flags
financial_provenance
```

The adapter must validate each wrapper input against the bundle's attestation,
exact `selection_as_of == bundle.as_of`, and the frozen observation/selector/
bundle lineages. It must not manufacture an attestation or reconstruct an
upstream source fact.

## Source role and double-count firewall

Use the already frozen v2 vocabulary:

```text
FINANCIAL_EVIDENCE_REFERENCE
FINANCIAL_NUMERIC_OBSERVATION
```

Future numeric wrappers use the latter. Existing Unified-State financial
artifact references are coverage/provenance evidence; a future v2 projection
must give them the former role. Role and source-artifact type must participate
in the full slot, so an earnings/filing reference never pairs with a numeric
PAT or revenue observation. Their co-existence does not authorize counting two
independent confirmations; semantic aggregation/deduplication remains a later
governed layer.

## Full-slot and revision compatibility

For a future numeric wrapper, `research_observation_slot_key()` will distinguish
Q1 revenue from Q2 revenue through period identity/components while retaining
the same `metric_id=REVENUE`. A same-Q1 revision may change value, source fact
ID, source semantic fingerprint, observation fingerprint, selection/bundle
lineage, or quality/provenance without changing the slot. Therefore a future
v2 comparison can factually report `VALUE_CHANGED` and/or `LINEAGE_CHANGED`;
it cannot infer QoQ, YoY, directionality, or investment meaning.

The current delta hardening is compatible with this structure, but current
Brain state and delta validation accept only policy v1. No financial wrapper
may enter them until a separately authorized Brain-state v2 integration
validates policy v2 and the proposed generic lineage extension.

## Comparability-v2 requirement mapping

| v2 requirement | Future wrapper location |
| --- | --- |
| Instrument | bundle/state container binding |
| Bundle schema, fingerprint, as-of | non-slot lineage components |
| Observation schema identity | slot component; fingerprint in non-slot lineage |
| Selector policy/result/as-of | non-slot lineage components; local exact-cutoff validation |
| `visible_as_of` | non-slot lineage component; validate `<= state.as_of` |
| Fact kind, metric, scope | slot component / `metric_id` / generic scope |
| Period identity and fingerprint | generic period fingerprint plus slot components |
| Dimension, currency, unit, scale, normalization | slot components and generic representation fields |
| Source role | slot component and source-artifact type |
| Observation/source-semantic/source-fact identities | source-artifact fingerprint and non-slot lineage components |

## Failure, ordering, and rebuildability

`FinancialResearchInputFailure` is not a numeric wrapper. Future Brain-state
v2 must carry failures as typed dimension-local input-sufficiency lineage; the
current generic warnings/blockers fields are insufficient for lossless typed
failure preservation. Numeric wrappers order deterministically by `metric_id`,
full slot fingerprint, then financial observation fingerprint. Given the same
bundle and future frozen wrapper schema, outputs must be identical.

## Preconditions and recommended next slice

Before implementation, govern and freeze the wrapper schema and the minimal
generic non-slot lineage contract. Then implement only a pure whole-bundle
adapter with focused losslessness/slot/revision tests. Brain-state v2
integration, failure projection, trajectory, comparison activation, and all
interpretation/action layers remain separate later slices.

## Explicit non-changes

No Python runtime code, generic observation contract, bundle builder/schema,
Brain state, FINANCIAL_RAW projection, comparability policy, ResearchStateDelta,
selector, materializer, persistence, migration, provider/API/worker, trajectory,
directionality, thesis/opportunity, alert, recommendation, or execution logic
was changed by U14D-6Q.
