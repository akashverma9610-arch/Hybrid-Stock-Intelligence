# Backtest event log

`BacktestEvent` and `BacktestReplayStep` are immutable, append-only records. Events retain the run, event/replay/evaluation timestamps, monotonic step number, referenced artifacts, message, metadata, and creation time. Event IDs and step IDs cannot be overwritten.

The foundational event vocabulary is `REPLAY_STARTED`, `REPLAY_STEP_STARTED`, `REPLAY_STEP_COMPLETED`, `DATA_INSUFFICIENT`, `LOOKAHEAD_REJECTED`, `ARTIFACT_RECORDED`, `REPLAY_COMPLETED`, `REPLAY_FAILED`, and `REPLAY_CANCELLED`. Signal, trade, rotation, and benchmark event enum values are reserved and are not emitted by this phase.

Historical analytical replay additionally appends `SNAPSHOT_BUILT`, `DIAGNOSTICS_EVALUATED`, `SCORECARD_CREATED`, `GATES_EVALUATED`, and an analytical-completed or analytical-insufficient event. These reference immutable analytical artifacts; they are not signal or execution events.

For each run, step numbers, event timestamps, and evaluation timestamps cannot move backwards. The first event must start the replay and no record can follow a terminal lifecycle event. Audit reconstruction reloads frozen configuration, regenerates the clock with the supplied matching calendar, verifies steps/events against it, derives the final state, and reports mismatches without changing stored history.

The data-gap policy is versioned. `FAIL_RUN` emits a data-insufficient record then fails; `SKIP_STEP` marks only that step skipped and continues; `MARK_INSUFFICIENT_DATA` stops in an explicit terminal insufficient-data state. No policy forward-fills, invents prices, or fabricates inputs.
