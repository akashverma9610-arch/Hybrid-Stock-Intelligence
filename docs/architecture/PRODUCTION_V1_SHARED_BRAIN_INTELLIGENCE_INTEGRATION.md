# Production-v1 Shared Brain Intelligence Integration

U15 connects the existing governed factual financial chain to one read-only
production artifact: `SharedBrainProductionSnapshot`. It is not a new Brain;
it is a deterministic assembly of the existing Shared Brain at one exact
instrument and as-of cutoff.

## Assembly flow

`UnifiedIntelligenceState → BrainResearchComparisonState v2 → FinancialResearchObservationBundle → bounded FinancialMetricTrajectory collection → ResearchMetricDirectionalityInterpretation collection → SharedBrainProductionSnapshot`.

The builder accepts explicit immutable artifacts and policies only. It calls
the existing Brain v2, trajectory, and directionality builders rather than
duplicating their validation, arithmetic, or metric×basis rules. It has no
store, provider, API, network, clock, persistence, or live-data dependency.

## Exact policies

- Trajectory: `financial-metric-trajectory-policy / v1-approved`
- Directionality: `research-metric-directionality-policy / v1-approved`
- Materiality: `research-semantic-materiality-policy / v1-approved`

All three fingerprints are retained in the snapshot. Materiality remains
globally `CALIBRATION_REQUIRED`: the snapshot does not evaluate a movement as
`MATERIAL` or `IMMATERIAL`.

## Bounded trajectory enumeration

Enumeration uses complete period identities and representationally compatible
groups only. It asks the existing trajectory builder to validate each bounded
candidate before retaining it:

- adjacent fiscal quarterly pairs, including Q4→Q1 only with fiscal proof;
- same-quarter consecutive-fiscal-year pairs;
- consecutive full-year pairs;
- adjacent point-in-time pairs ordered by economic period end.

It does not create all-vs-all comparisons, skipped-quarter pairs, TTM, YTD
subtraction, cumulative cash-flow reconstruction, partial-period trajectories,
same-period revision pairs, or cross-representation pairs.

## Shared context views

`project_shared_brain_production_snapshot(snapshot, output_context=...)` makes
the same canonical financial semantic section available for all current
`BrainOutputContext` values: Opportunity Discovery, Deep Analysis, Portfolio
Review, Sell/Trim Review, Rotation Review, Entry Setup Review, and Alert
Review. A context projection changes only context identity and presentation
lineage; trajectory, directionality, failure, and materiality-policy
fingerprints are identical across views.

## Read-only boundary and limitations

The snapshot preserves successful metric-local artifacts and typed
financial-failure lineage independently. It remains valid with no trajectories
or directionality interpretations when a valid underlying Brain state has only
financial failures.

There is no cross-metric conclusion, materiality runtime, persistence,
acceleration, quality/attribution conclusion, thesis/opportunity semantic,
score/Six-Gates change, alert, recommendation, execution, or provider lookup.
