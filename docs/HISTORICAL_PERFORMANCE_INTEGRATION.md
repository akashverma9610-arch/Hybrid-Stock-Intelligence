# Historical performance integration

A completed frozen `BacktestRun` can be adapted into the existing Phase 7B performance engine. The adapter requires the persisted dataset manifest, completed run status, and frozen paper trades/outcomes. It maps those outcomes to canonical `TradePerformanceRecord` values; open trades remain open and are not silently classified as wins or losses.

Portfolio-return metrics remain the performance engine's capital-based outputs; trade expectancy and R metrics come from normalized frozen outcomes. Benchmark series are accepted only as supplied point-in-time historical inputs. Missing series produce explicit unavailable warnings rather than fabricated returns.

When a frozen historical equity series is supplied, portfolio return, ending equity, and drawdown use its session-end cash-plus-marked-holdings path. This captures interim unrealized drawdowns and recoveries while preserving trade metrics separately.

Session-complete equity observations, rather than trade-close-only observations, supply portfolio volatility, Sharpe, and Sortino where sufficient data exists.
# Walk-forward linkage

A completed clean-OOS TEST run may link its canonical frozen `PerformanceReport` to an immutable `WalkForwardWindowResult`. Window metrics are copied from report outputs rather than recalculated. A zero-trade cash window remains a retained result; incomplete or failed windows remain explicit records rather than being dropped.
