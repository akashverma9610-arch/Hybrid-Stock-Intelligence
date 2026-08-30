# Financial Metric Trajectory

`FinancialMetricTrajectory` is a pure, immutable factual derivation:

``FinancialResearchObservationBundle(as_of=T)`` + explicit trajectory request
+ `financial-metric-trajectory-policy / v1-approved`
→ one factual period-pair artifact.

Only observations already inside the supplied same-as-of bundle are eligible.
The builder does not select facts, materialize observations, rebuild the bundle,
use generic wrappers, consume Brain state or `ResearchStateDelta`, or access a
store, provider, network, clock, or runtime configuration.

The v1 policy permits only sequential-quarter, YoY-quarter, YoY-annual, and
point-in-time sequential bases. It requires COMPLETE period identities, exact
representation parity, explicit unique pair targeting when a bundle has more
than one possible pair, and exact Decimal arithmetic. Same-period revisions are
knowledge-vintage changes, not trajectories.

An AVAILABLE artifact preserves prior/current values, absolute delta, optional
relative delta (only for a strictly positive prior value), numeric-domain and
sign-transition facts. Zero and negative prior bases never produce an invented
percentage. It does not label any movement good, bad, material, persistent,
accelerating, or investment-relevant.

Trajectory is not directionality. Trajectory is not thesis or opportunity
interpretation. No persistence, alert, recommendation, signal, or execution
behavior is attached to this derived artifact.
