# Performance engine

The canonical Phase 7B performance engine is reused for frozen historical backtest reporting. Historical adapters normalize immutable paper outcomes into its `TradePerformanceRecord` input and do not implement competing formulas.

The historical equity-series adapter supplies capital-path return/drawdown from session-end equity while trade analytics remain canonical record-based metrics.

For session-complete historical series, volatility, Sharpe, and Sortino consume consecutive session equity returns.
# Walk-forward OOS aggregation

The performance engine’s frozen TEST reports remain the source of window metrics. `WalkForwardAggregationService` only stitches TEST returns and pools frozen TEST paper outcomes; it does not recalculate or include TRAIN/VALIDATION performance.

Controlled experiments reuse the canonical Phase 8A backtest and performance reports for TRAIN/VALIDATION evidence; they do not implement a separate performance engine.
