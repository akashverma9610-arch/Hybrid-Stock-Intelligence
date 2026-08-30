# Self-improvement experiment bridge

The bridge is deliberately narrow:

`human-approved research hypothesis → existing StrategyExperiment draft + StrategyCandidateDelta + provenance link`

It accepts only an immutable actionable hypothesis, exact human `APPROVE_FOR_EXPERIMENT` review, matching evidence fingerprint, current approved target baseline, complete existing baseline candidate, and existing `ExperimentBudget`. The review must contain `EXPERIMENT_VALUE=<decimal>`; direction alone cannot invent a numeric candidate delta.

The bridge uses the existing Phase 8B.2 records and validation service. It creates one complete immutable candidate snapshot, one bounded delta, and one `PLANNED` experiment. It performs no train/validation run, no TEST/OOS work, no evidence generation, no candidate selection, promotion, or activation.

`HypothesisExperimentLink` is immutable provenance. Audit reconstruction checks the complete chain and recomputes candidate/delta/experiment/link identities from frozen inputs. Later observations, strategy versions, budgets, and policies cannot rewrite an existing bridge artifact.
