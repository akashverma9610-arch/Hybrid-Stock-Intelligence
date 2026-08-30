# OOS Aggregation

Phase 8B.1 aggregates only immutable TEST `WalkForwardWindowResult` records. Independent TEST capital is rebased using `CHAIN_WINDOW_RETURNS`: each window return compounds the prior synthetic ending equity. Raw rupee equity from independently funded windows is never concatenated.

When a source `HistoricalEquitySeries` exists, each session is rebased to the prior aggregate end, preserving within-window return and drawdown shape. Gaps are not filled, overlapping TEST windows fail closed, and zero-trade, insufficient, failed, and benchmark-unavailable windows remain in coverage.

The aggregate result pools TEST trade outcomes where frozen reports exist, and reports stitched drawdown, Sharpe, Sortino, return, costs, and transparent window stability measures. It is evidence only, not promotion or optimisation.
