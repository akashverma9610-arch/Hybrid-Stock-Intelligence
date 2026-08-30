# Out-of-Sample Validation

Each V1 TEST window is a clean, independently capitalised Phase 8A backtest. `INDEPENDENT_WINDOW_CAPITAL` starts every window from its frozen configured capital; capital, signals, open paper trades, holdings, and ledger state from TRAIN or VALIDATION are not inherited.

The coordinator accepts only a TEST-scoped `BacktestRun`: its partition and start/end must exactly equal the frozen TEST partition. Phase 8A remains the only source of replay, PIT guards, analytics, portfolio, signal/paper, allocation, equity, performance, and benchmark work.

Benchmark linkage is optional. If frozen point-in-time benchmark data is unavailable, a valid strategy result is retained with `BENCHMARK_UNAVAILABLE`; no latest-data fallback is permitted.

Aggregate OOS results use `CHAIN_WINDOW_RETURNS`, not a single cross-window portfolio. A timestamped benchmark path must have matching TEST sessions before a direct path comparison is considered aligned.

Candidate experimentation is prohibited inside TEST execution. The selected candidate must already be represented by a frozen `CandidateSelectionResult` or the normal fixed-strategy selection.

For research-selected candidates, `FutureOOSExecutionService` verifies the immutable queue, assignment policy, exact candidate fingerprint, selection timestamp, and TEST partition before delegating to this same coordinator. A positive OOS result is evidence only; it does not create promotion, approval, activation, or any live-account action.
