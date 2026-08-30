# Sector Analysis

Rules 2 and 3 consume validated sector-index and benchmark price-bar series from one immutable as-of snapshot. Rule 2 calculates sector and benchmark lookback returns, then classifies their difference (excess return) using supplied strong and weak thresholds.

Rule 3 maps that observable price/relative-strength proxy to `ROTATING_IN`, `ACCUMULATING`, `ROTATING_OUT`, `DISTRIBUTING`, or `NEUTRAL`. It is an **inference**, not a factual claim of capital movement, fund flow, holdings, or institutional activity. Volume is not currently part of its formula because only OHLCV mock fixtures are available.

Both rules retain the precise input observation IDs, evidence, as-of time, registry version, and strategy version. They contribute eligibility only to the `sector_rotation` component; no Decision Score is calculated.
