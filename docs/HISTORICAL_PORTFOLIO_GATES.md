# Historical portfolio-context gates

The portfolio-context gate adapter is separate from the immutable analytical-only gate artifact created by historical analytical replay. It accepts frozen candidate/holding analytical references, a frozen backtest portfolio state, and the gate configuration version recorded by the backtest run, then invokes the existing `ExecutionGateEngine`.

For Gate 1, a missing incumbent comparison remains insufficient; the adapter never assumes a zero incumbent score. Candidate raw Decision Score is read from the frozen scorecard and remains unchanged. For Gate 5, equity, heat, sector exposure, and supplied incremental risk/allocation come only from the frozen portfolio state/context. Missing risk coverage remains insufficient.

Candidate, holding, and portfolio timestamps must not be after the replay timestamp. A configuration version mismatch is rejected. The resulting contextual evaluation is immutable and audit reconstruction verifies its frozen dependency chain. This phase does not make a rotation decision or create signals, orders, fills, trades, performance, or benchmark artifacts.

The persisted contextual record freezes its candidate sector, incremental risk, allocation, expected incremental return, and modeled switching friction as well as all artifact IDs. Audit reconstruction re-invokes the canonical `ExecutionGateEngine` using those stored values and the supplied frozen gate configuration/calendar; any result, reference, timestamp, or configuration mismatch is an audit error. No latest-artifact or latest-configuration lookup is permitted.

Historical rotation replay may consume this immutable contextual gate artifact. It never recomputes it from current observations.
