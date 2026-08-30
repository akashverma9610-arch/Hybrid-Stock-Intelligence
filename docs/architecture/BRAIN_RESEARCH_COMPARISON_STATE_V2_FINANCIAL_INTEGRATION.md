# Brain Research Comparison State v2 Financial Integration

`build_brain_research_comparison_state_v2(...)` is the pure, explicit v2
Shared-Brain integration boundary.  It consumes only:

```text
UnifiedIntelligenceState
+ validated FinancialResearchObservationBundle
+ prebuilt generic financial ResearchMetricObservation wrappers
+ the exact typed FinancialResearchInputFailure tuple
→ BrainResearchComparisonState v2
```

The returned state uses `brain-research-comparison-state / v2`,
`shared-brain-research-comparison / v2`, and the frozen
`brain-research-comparability-policy / v2-approved` artifact.  It validates
exact instrument and as-of parity, the complete bundle/observation/wrapper/
selector lineage, wrapper-to-bundle one-to-one binding, full-slot uniqueness,
and exact typed failure binding.  It is deterministic and has no clock, store,
provider, network, filesystem, or persistence dependency.

Numeric wrappers enter only `FINANCIAL_RAW`. Existing financial evidence
references are retained as their distinct `FINANCIAL_EVIDENCE_REFERENCE` role;
numeric wrappers retain `FINANCIAL_NUMERIC_OBSERVATION`. They are factual
representations, not two corroborating investment signals. No score,
confidence, or aggregation behavior is added.

`COMPLETE` and `PARTIAL` wrappers remain observations. An `INSUFFICIENT`
period cannot enter a valid prepared bundle/wrapper. Typed selection and
materialization failures remain `FINANCIAL_RAW`-local warnings/blockers and
lineage. A failure-only bundle is a valid partial factual state; an empty
bundle is also valid and retains its explicit v2 methodology lineage.

The existing v1 builder remains unchanged. v1 and v2 methodology identities
are foundationally non-comparable. Valid v2-to-v2 deltas use existing full-slot
matching: a same-period revision is factual `VALUE_CHANGED` or
`LINEAGE_CHANGED`, a new period is `ADDED`, and a removed period is `REMOVED`.
With policy v2, a matched `PARTIAL` financial period is numerically
`INSUFFICIENT`.

This builder does not invoke fact-vintage selection, observation materializing,
bundle building, or wrapper creation. It has no raw FinancialFact input route
and does not create trajectory, QoQ/YoY/TTM, directionality, thesis/opportunity
meaning, alerts, recommendations, execution, portfolio behavior, Six Gates
execution, persistence, APIs, workers, or schedulers.
