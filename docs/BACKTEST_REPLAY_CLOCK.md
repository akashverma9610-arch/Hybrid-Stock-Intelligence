# Backtest replay clock

The Phase 8A.2 replay clock is a deterministic scheduler, not a strategy evaluator. A `ReplaySchedule` is immutable and records its version, frequency, IANA timezone, exchange-calendar reference, cutoff semantics, execution-timing policy, window, and warnings.

V1 implements `DAILY_CLOSE` only. It emits exactly one evaluation timestamp at the configured session close for every weekday not listed as an exchange holiday. It excludes weekends and holidays, preserves ascending order, and intersects the schedule with the frozen run window and any supplied historical partition. Weekly, event-driven, and intraday frequency values are reserved; they do not implement behavior yet.

`evaluation_timestamp` means the configured trading-session close. The clock does not make information eligible. Every future data consumer must still use `BacktestLookaheadGuard` at that timestamp.

Historical execution timing additionally distinguishes the trigger's event and knowledge timestamps from the selected paper-entry window. The clock never allows a stored future bar to become usable early.

Execution timing is configuration only in this phase. `NEXT_BAR_OPEN` and `NEXT_ELIGIBLE_BAR` defer a future execution decision; `SIGNAL_CLOSE` is valid only when the signal, its inputs, and a fill at that close are all known and permitted before that close. No fills are produced here.
