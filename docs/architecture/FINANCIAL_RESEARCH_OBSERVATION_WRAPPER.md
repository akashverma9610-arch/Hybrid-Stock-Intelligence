# Financial Research Observation Wrapper

`wrap_financial_research_observation_bundle(bundle, *, wrapper_schema)` is a
pure one-to-one compatibility adapter. It accepts an already validated
`FinancialResearchObservationBundle` and the explicit frozen
`financial-research-observation-wrapper-schema / v1-approved` artifact.

For every successful financial observation it returns exactly one generic
`ResearchMetricObservation` in `FINANCIAL_RAW`. The wrapper preserves the exact
Decimal value, unit, scale, scope, basis, period identity, financial fact kind,
currency, value dimension, normalization, observation fingerprint, and all
frozen bundle/selector/source/revision/quality/provenance lineage.

Accounting semantics are placed in canonical generic slot components. Mutable
provenance is placed in canonical non-slot `lineage_components`, so same-period
revisions preserve their observation slot while retaining a distinct artifact
identity. `PARTIAL` periods wrap as valid factual observations; input failures
produce no fake numeric metrics.

The wrapper is not vintage selection, materialization, bundle construction,
Brain-state integration, trajectory construction, comparison, directionality,
thesis/opportunity interpretation, alerting, recommendation, persistence, or
execution. It has no database, store, provider, network, filesystem, clock, or
environment dependency.
