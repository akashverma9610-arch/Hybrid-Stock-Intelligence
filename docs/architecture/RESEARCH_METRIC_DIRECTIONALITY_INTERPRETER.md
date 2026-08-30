# Research Metric Directionality Interpreter

The interpreter is a pure derived step:

`AVAILABLE FinancialMetricTrajectory` + explicit frozen
`research-metric-directionality-policy / v1-approved`
→ one immutable `ResearchMetricDirectionalityInterpretation`.

It validates the exact trajectory-policy and directionality-policy identities,
uses the exact `metric × trajectory basis` rule, and has no default, family, or
nearest-rule fallback. Its result is only one of `POTENTIALLY_FAVORABLE`,
`POTENTIALLY_UNFAVORABLE`, `NO_DIRECTIONAL_CHANGE`, `CONTEXT_DEPENDENT`,
`NON_DIRECTIONAL`, or `NOT_APPLICABLE`.

For higher-potentially-favorable rules, exact `absolute_delta` determines the
orientation; `relative_delta` and sign transition do not. Context-dependent
and non-directional rules remain so regardless of movement. The approved v1
registry contains no lower-potentially-favorable rule.

Directionality is not materiality, persistence, acceleration, attribution,
quality, thesis, opportunity, scoring, recommendation, or execution. The
interpreter does not build trajectories, access selectors/materializers/bundles,
use wrappers or Brain state, access storage/providers/network, persist results,
or look up a global policy.
