# Research Metric Directionality QA

U14D-7B is an end-to-end, deterministic acceptance gate for the passive
`research-metric-directionality-policy / v1-approved` and its pure
interpreter. It validates the real factual path:

`FinancialMetricObservation → FinancialResearchObservationBundle → FinancialMetricTrajectory → ResearchMetricDirectionalityInterpretation`.

The policy remains approved but unselected and inactive. The result is a
single metric-local orientation only; it is not a materiality, quality, thesis,
opportunity, score, recommendation, or action result.

## Scenario results

The QA covers positive, negative, zero, negative-base, and sign-crossing
trajectories. PAT loss narrowing and a loss-to-profit movement are both
`POTENTIALLY_FAVORABLE` because their governed absolute delta is positive;
relative delta and sign-transition description do not grant orientation.
Revenue, EBITDA, Operating Profit, EBIT, PAT, EPS Basic, and EPS Diluted are
potentially directional only on quarterly- or annual-YoY bases. Sequential
Revenue remains `CONTEXT_DEPENDENT`, including a zero change. PBT, CFO, FCF,
other income, finance cost, tax, depreciation, minority interest, and capex
remain context dependent. CFI/CFF and shares outstanding/face value remain
non-directional regardless of movement sign.

The quarterly fixture also proves an otherwise valid fiscal Q4→Q1 adjacency
does not bypass the sequential-quarter seasonality firewall.

The end-to-end multi-metric fixture proves four outcomes coexist without a
combined conclusion: favorable Revenue, favorable loss-narrowing PAT,
context-dependent debt, and non-directional CFF.

## Completeness and fail-closed checks

The policy has exactly 124 canonical rules: every one of 31 `FinancialMetric`
values crossed with all four frozen trajectory bases. Exact metric×basis lookup
is mandatory. Missing, duplicate, or fingerprint-tampered rules and tampered
policy or trajectory lineage fail closed; no contextual or metric-family
fallback is used. There are zero `LOWER_POTENTIALLY_FAVORABLE` rules in v1.
Consequently any future metric requires a complete explicit policy matrix
revision rather than inheriting another metric's semantics.

## Semantic and runtime firewall audit

The interpreter accepts AVAILABLE trajectories only and uses the explicit
trajectory and directionality lineage. Its source imports no selector,
materializer, bundle builder, trajectory builder, wrapper, Brain state, or
ResearchStateDelta. It has no database, provider, network, filesystem,
environment, current-clock, persistence, API, worker, scheduler, alert,
recommendation, execution, aggregation, acceleration, or materiality surface.

## Governance acceptance matrix

| Area | Status |
| --- | --- |
| AVAILABLE-only input and exact policy lineage | PASS |
| Exact metric×basis lookup and 124-rule completeness | PASS |
| Revenue YoY orientation / QoQ seasonality firewall | PASS |
| PAT loss narrowing and sign-crossing | PASS |
| EBITDA / Operating Profit / EBIT / EPS | PASS |
| PBT / CFO / FCF and balance-sheet context firewalls | PASS |
| CFI/CFF and shares/face-value non-directional rules | PASS |
| Zero-change, relative-delta, and sign-transition behavior | PASS |
| Future-metric, missing-rule, duplicate-rule, and tamper failure | PASS |
| Determinism and input immutability | PASS |
| Materiality, persistence, acceleration, aggregation firewall | PASS |
| Thesis, opportunity, Brain, score, Six-Gates firewall | PASS |
| Alert, recommendation, action, and runtime firewall | PASS |
| Purity and non-persistence | PASS |

## Intentional limitations

Only seven metrics have a higher-potentially-favorable rule, only on quarterly
and annual YoY bases. Sequential flows, balance-sheet movements, CFO/FCF, and
other context-dependent metrics deliberately do not acquire a directional
meaning. CFI/CFF and share/face-value representations deliberately remain
non-directional. No lower-potentially-favorable rule exists. None of these
limitations is a defect.

## Readiness

When the documented focused, regression, full-suite, and compilation gates
pass, this boundary is `READY_FOR_MATERIALITY_GOVERNANCE`. That label permits
only a subsequent human policy/governance discussion; it does not authorize a
materiality runtime implementation.
