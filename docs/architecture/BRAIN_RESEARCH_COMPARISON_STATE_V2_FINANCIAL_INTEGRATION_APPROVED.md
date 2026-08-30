# Brain Research Comparison State v2 Financial-Integration Contract

**Status: APPROVED — NOT SELECTED — NOT ACTIVE.**

This is a passive contract.  It defines the only permitted future integration
boundary for a financial-integrated Shared-Brain state; it does not implement
that state builder or change the existing v1 builder.

## Frozen identity

| Field | Value |
| --- | --- |
| Schema | `brain-research-comparison-state-schema / v2-approved` |
| State identity | `brain-research-comparison-state / v2` |
| Methodology | `shared-brain-research-comparison / v2` |
| Approver | `human:Akash-Verma` |
| Selected / active | `false / false` |
| Comparison mode | `KNOWLEDGE_AT_THE_TIME` |
| Proposal lineage | `v2-proposed -> v2-approved` |
| Schema fingerprint | `1ce9329f7c45201625ec0f96a0949e8bfad5f65e0027f9f74c19f47301a7b7e4` |

State v1 remains `brain-research-comparison-state-v1` under
`shared-brain-research-comparison / v1` and is valid historical governance.
v1 and v2 are foundationally `NON_COMPARABLE`; no compatibility shim or
cross-version comparator is authorized.

## Required future builder boundary

The future API is frozen as:

```python
build_brain_research_comparison_state_v2(
    unified_state,
    *,
    comparability_policy,
    financial_bundle,
    financial_wrappers,
    financial_failures,
)
```

All three financial inputs are required and explicit.  The bundle is required
even when it is empty or failure-only, so every v2 state has one unambiguous
financial methodology boundary.  The future builder must not accept raw
`FinancialFact`, selection results, materialization results,
`FinancialMetricObservation`, provider payloads, or an alternate financial
route.  It must not call the selector, materializer, bundle builder, wrapper
adapter, store, or provider.

The required parity chain is:

```text
selection_as_of == financial_bundle.as_of == UnifiedIntelligenceState.as_of
                 == BrainResearchComparisonState v2.as_of
```

The bundle instrument, Unified State instrument, and every financial wrapper
must match exactly.  A wrapper's preserved `visible_as_of` must be no later
than the state `as_of`; it is not rewritten or required to equal that cutoff.

## Frozen lineage

The v2 state must bind exactly to:

```text
Comparability: brain-research-comparability-policy / v2-approved /
1e6926fd84dcf82958a831674701afb28bf3a76a15e9fe19bbfe5d5f28df79d3
Bundle: financial-research-observation-bundle-schema / v1-approved /
aba6123afc78781b4ac011fe048ed10d91b7e8af3f10944f25558be5f2036a89
Observation: financial-metric-observation-schema / v1-approved /
6d55e73ee78f0074789165952a287d9b8b6ec801ce98703e9a136603f3da3caf
Wrapper: financial-research-observation-wrapper-schema / v1-approved /
62ce6dc13dab80a3a468307f24b88d888a8d42226a7506c671d00c86e1b4f95c
Selector: financial-fact-vintage-selection-policy / v1-approved /
862dc470ebd58abd2d066f2604440908eaf3aa9827e6c93b588b5f1bf806fc13
```

Every successful bundle observation must have exactly one already-created
financial numeric wrapper; a wrapper must bind exactly one successful bundle
observation through frozen source-artifact, lineage, and slot contracts.  No
missing, extra, orphan, duplicate, or tampered wrapper is allowed.  Duplicate
full generic observation slots fail closed.  Multiple accounting periods with
the same metric label are permitted because full slot identity—not metric
label—governs uniqueness and deterministic ordering.

## FINANCIAL_RAW and failures

Numeric wrappers enter only `FINANCIAL_RAW`.  Existing factual financial
evidence references remain.  Their roles are distinct:

```text
FINANCIAL_EVIDENCE_REFERENCE != FINANCIAL_NUMERIC_OBSERVATION
```

They cannot pair in `ResearchStateDelta` and must never be aggregated as two
independent corroborating signals.  Stored `FinancialFact` / canonical
evidence remains the source of truth; neither a wrapper nor a Brain state is
canonical financial storage.

`COMPLETE` and `PARTIAL` financial observations are factual and admitted;
`PARTIAL` is later numeric-comparison `INSUFFICIENT` under policy v2.
`INSUFFICIENT` cannot appear as a valid wrapped observation.  Typed selection
(`UNAVAILABLE`, `CONFLICTED`, `INVALID_LINEAGE`, `INSUFFICIENT_IDENTITY`) and
materialization (`REJECTED`) failures stay as deterministic FINANCIAL_RAW
dimension-local blockers/warnings and input-sufficiency lineage—never fake
numeric observations or generic missing-data replacements.  Failure-only
bundles with an empty wrapper tuple are valid factual partial states.

Financial dimension availability retains existing factual availability
semantics for numeric-wrapper-present, references-only, failures-only, and
no-selected-facts cases.  This contract authorizes no quality, score, or
investment interpretation.

## State fingerprint and comparison

The future state fingerprint must canonically include the source Unified State
lineage, v2 schema/methodology, policy-v2 identity, all dimensions, bundle
lineage, numeric wrappers, and typed financial failure lineage.  Wrapper
ordering uses generic full observation-slot identity; failures order by
semantic key, stage, status, reasons, and upstream fingerprint.

Within valid v2 states, ordinary financial input failures are dimension-local;
they do not invalidate unrelated dimensions.  Existing full-slot matching
therefore retains same-period revision `VALUE_CHANGED` / `LINEAGE_CHANGED`,
new-period `ADDED`, removed-period `REMOVED`, and reference/numeric separation
without a delta implementation change.

## Boundaries retained

No v2 builder, FINANCIAL_RAW runtime population, wrapper execution, selector
or materializer call, `ResearchStateDelta` change, persistence, cache,
provider/API call, worker, or scheduler is implemented here.  The contract
does not create trajectory, QoQ/YoY/TTM, directionality, thesis/opportunity
semantics, Six Gates outcomes, portfolio semantics, alerts, recommendations,
BUY/HOLD/SELL/TRIM/ROTATE, signals, orders, or trades.
