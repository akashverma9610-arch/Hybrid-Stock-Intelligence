# Backtest engine boundary

Phase 8A.2 provides replay orchestration only: immutable run configuration, a daily-close clock, append-only replay steps/events, data-gap policies, persistence, and audit reconstruction.

The placeholder handler receives a `ReplayStepContext` with the existing `BacktestLookaheadGuard`. `require_eligible` delegates eligibility to that guard and rejects future facts fail-closed, recording `LOOKAHEAD_REJECTED` followed by replay failure.

Signal/paper coordination applies the frozen schedule execution policy through `HistoricalExecutionTimingAdapter` before invoking the canonical paper engine.

Historical signal and paper events are append-only in chronological order: lifecycle trigger, timing resolution, paper creation/opening, any partial event, then closure where applicable. These events do not mutate the real portfolio, broker, order system, performance reporting, or benchmarks.

Where capital allocation is enabled, open-trade management is recorded before same-step entry funding. Backtest-only fill, partial-exit, exit, and allocation-rejection events explain the ledger effects.

Sizing inputs are read only from the immutable paper-config snapshot; later configuration versions cannot resize an earlier fill.

Completed runs may feed frozen paper outcomes into the existing performance and benchmark engines through a narrow historical adapter. Incomplete runs are explicitly ineligible.

Session-end historical equity is sampled after eligible ledger and valuation effects for the replay state, using only that state's frozen marks.

Daily-close equity building includes valuation-only sessions in the frozen replay-clock schedule; it does not add ledger events for them.

Phase 8A.3 adds an optional historical analytical adapter to this lifecycle. It uses the existing diagnostic, Decision Score, and execution-gate engines against a frozen historical snapshot. It still does not call portfolio, rotation, signal, paper-trading, performance, benchmark, optimization, or walk-forward engines.

The separate backtest portfolio adapter reconstructs cash and holdings only from its own append-only fixture ledger. It emits immutable portfolio reconstruction/value/insufficiency events and does not create rotation, signals, or trades.

Its gate-input adapter selects surveillance and earnings schedules only from the frozen snapshot. A later ASM/GSM record or earnings reschedule cannot change an earlier Gate 3 or Gate 6 artifact.

The portfolio-context gate adapter records only `PORTFOLIO_GATES_EVALUATED` or `PORTFOLIO_GATES_INSUFFICIENT` events. It uses frozen portfolio, candidate, incumbent, and gate-config references, and does not invoke rotation or downstream execution layers.

Historical rotation replay adds only analytical rotation/cash/rejection events, backed by frozen references and the Phase 6B engine. It creates no execution event or ledger movement.
# Walk-forward OOS boundary

The walk-forward coordinator does not introduce another backtest engine. It invokes the existing Phase 8A replay pipeline with a `BacktestRun` that is exactly bounded by the immutable TEST partition. A TEST run declares `INDEPENDENT_WINDOW_CAPITAL`; it cannot consume TRAIN signals, paper trades, holdings, cash, or observations outside that interval.
