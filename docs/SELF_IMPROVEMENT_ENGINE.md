# Self-improvement observation engine

The engine is intentionally one-way:

`frozen observation → deterministic association → recurring pattern → descriptive summary`

It consumes only source-typed, auditable, point-in-time eligible observations inside a frozen `SelfImprovementRun`. The immutable `AttributionRuleSet` and `SelfImprovementEvidencePolicy` retain all thresholds, permitted source classes, recurrence requirements, source weights, and breadth requirements. OOS and paper evidence have explicit persisted weights; the engine never uses invisible weighting.

Recurring patterns retain source/regime/sector/score/confidence splits. A single observation remains `ANECDOTAL`; configured minimum sample and OOS coverage are required before `ELIGIBLE`. Counterevidence is retained as `MIXED`; narrow regime or sector support is warned rather than generalized.

Phase 9A.2 may turn eligible patterns into immutable research hypotheses and a ranking. It may also retain `REQUEST_MORE_EVIDENCE` or `NO_CHANGE_RECOMMENDED`. It still creates no experiments, candidate changes, promotion records, strategy configuration changes, or activation effects.

Phase 9A.3 is the only exception to candidate-artifact creation: an exact human-reviewed actionable hypothesis may create a bounded existing `StrategyExperiment` draft and `StrategyCandidateDelta`. Creation remains non-executing and cannot select, promote, or activate anything.

Phase 9B.1 may execute that already-approved draft only on frozen TRAIN and VALIDATION partitions, persist evidence/robustness, and make an existing research-selection result. Research selection is not OOS validation, strategy promotion, or activation.

Phase 9B.2 may freeze that selection into a future TEST assignment and run the canonical clean-OOS executor. The TEST result is new evidence and never feeds back into its own selection record or mutates research artifacts.

## Feature setting

Phase 9A is complete. Phase 9B remains partially complete and deferred for
automatic production use. `FeatureSettings` exposes the future-runtime
capability `AUTOMATED_SELF_IMPROVEMENT_RESEARCH`; its default is disabled with
`EXPERIMENTAL` maturity, `DEFERRED` lifecycle status, and no production-blocking
effect. This only controls a future automatic runtime. It does not disable the
underlying immutable research and OOS services for manual or test use.
