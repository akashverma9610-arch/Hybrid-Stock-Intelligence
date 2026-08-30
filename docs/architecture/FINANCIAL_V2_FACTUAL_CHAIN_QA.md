# Financial v2 Factual-Chain QA

U14D-6V exercises the actual in-memory factual chain:

```text
FinancialFact -> PIT selector -> FinancialMetricObservation -> bundle
-> generic wrapper -> BrainResearchComparisonState v2 -> ResearchStateDelta
```

The QA fixtures prove PIT exclusion of future revisions, same-slot factual
value revision, new-period addition, multiple retained periods, wrapper and
failure determinism, PARTIAL preservation, failure-only/mixed bundles,
reference/numeric role separation, and fail-closed malformed bundle/wrapper
inputs. Existing selector/materializer/bundle/wrapper/state/delta regressions
cover conflicting candidates, invalid revision lineage, scope and cash-flow
basis isolation, and canonical identity handling.

| Boundary | Status | Evidence |
| --- | --- | --- |
| FinancialFact -> selector | PASS | U14D-6V chain + selector regressions |
| Selector -> observation | PASS | U14D-6V chain + materializer regressions |
| Observation -> bundle | PASS | U14D-6V chain + bundle regressions |
| Bundle -> wrapper | PASS | U14D-6V chain + wrapper regressions |
| Wrapper -> Brain v2 | PASS | U14D-6V chain + State-v2 regressions |
| Brain v2 -> delta | PASS | value revision and added-period QA |
| PIT / no backdating | PASS | future revision excluded at the earlier cutoff |
| Revision / slots / determinism | PASS | full-chain deterministic fixtures |
| Failure propagation | PASS | mixed and failure-only fixtures |
| v1 preservation / v1-v2 firewall | PASS | existing v1 and State-v2 regressions |
| Semantic and action firewall | PASS | static boundary tests and module audit |

No defects requiring a production fix were found by this QA slice. The known
limitations remain: no trajectory, directionality, thesis/opportunity meaning,
alerts, recommendations, execution, canonical valuation comparison, normalized
ownership comparison, or historical current-only sector comparison.

**Trajectory-readiness decision:** `READY_FOR_TRAJECTORY_GOVERNANCE`.
This is a governance-review readiness result only. It does not implement or
authorize FinancialMetricTrajectory or any downstream semantic/action layer.
