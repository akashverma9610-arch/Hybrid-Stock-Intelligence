# Controlled Strategy Experiments

Experiments are immutable, hypothesis-driven comparisons of explicitly supplied complete candidate snapshots. Each experiment retains its approved baseline, deltas, frozen budget, permitted TRAIN/VALIDATION partitions, and forbidden TEST partitions. It cannot change point-in-time safety, audit, six-gate governance, or real-account boundaries.

The V1 budget limits candidate count, changed parameters, permitted numeric ranges, and repeated evaluations. It is not an optimiser or a source-code mutation system.
# Hypothesis boundary

Controlled experiments remain downstream of human-reviewed research hypotheses. This repository currently records hypotheses and human reviews only; Phase 9A.2 does not create `StrategyExperiment`, `StrategyCandidateDelta`, candidate selection, promotion, or activation records.

Phase 9A.3 may now create the existing immutable `StrategyExperiment` and `StrategyCandidateDelta` through a human-approved bridge. Such a record is `PLANNED` only; experiment creation is not execution, candidate selection, strategy promotion, or activation.
