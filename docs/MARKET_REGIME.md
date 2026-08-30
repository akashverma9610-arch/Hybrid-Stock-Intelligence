# Market Regime

## Inputs and requirements

`MarketRegimeEngine` evaluates one mock benchmark/index price-bar series inside an as-of snapshot. It requires configurable fast/slow SMA periods, ATR period, return lookback, return thresholds for each regime boundary, and panic ATR-percent threshold. Missing benchmark bars, invalid snapshot data, or insufficient indicator history returns `INSUFFICIENT_DATA`.

## Transparent rules

The engine calculates benchmark return over the configured lookback, benchmark trend from configured moving averages, and ATR as a percentage of the latest close. It records all contributing conditions in the result.

- `PANIC`: return is at or below configured panic return and ATR percentage is at or above configured panic volatility.
- `STRONG_BULL`: configured strong-bull return is met and trend is up.
- `BULL`: configured bull return is met and trend is up.
- `SELECTIVE_BULL`: configured selective-bull return is met.
- `BEAR`: configured bear return is met and trend is down.
- `SELECTIVE_BEAR`: configured selective-bear return is met.
- `NEUTRAL`: sufficient data exists but no preceding rule matches.

Rule order is intentional: panic has priority, then strong/bull, then selective bull, then bear/selective bear, then neutral. All thresholds must be supplied by configuration; the repository contains no claim that the mock thresholds are suitable for a production strategy.

## Evidence and auditability

Each result creates distinct DATA, INTERPRETATION, and INFERENCE evidence records. The result includes input observation IDs, calculation version, strategy version, as-of/evaluation timestamps, data quality, confidence/status, and the conditions used. The audit bridge can persist these as immutable evidence and diagnostic records for reconstruction.

## Limitations

This is a small rule framework, not a predictive model. It has no breadth, sector rotation, news, macro data, real index feed, or production calibration. It must not be used as a trading decision by itself.
