# Technical Analysis

## Scope and inputs

The Phase 3 technical engine uses only validated `price_bar` observations already present in an as-of snapshot. It sorts bars by market timestamp and rejects malformed or ineligible bars. It never fetches data, fabricates bars, fills gaps, or calculates from an observation received after the snapshot's as-of time.

All indicator calls require a strategy-version reference, as-of snapshot, evaluation time, configurable period, calculation version, input observation IDs, data-quality label, status, confidence, and evidence IDs.

## Formulas

### SMA

For period `n`, SMA is the arithmetic mean of the latest `n` closing prices. Fewer than `n` bars returns `INSUFFICIENT_DATA`.

### EMA

EMA is seeded with the first `n`-bar SMA and updated through each remaining close using multiplier `2 / (n + 1)`. This deterministic initialization is documented so replayed results are identical.

### RSI

RSI uses Wilder smoothing. It requires `n + 1` closes to obtain `n` changes. Initial average gain/loss is the arithmetic mean of the first `n` gains/losses; later values use Wilder's recursive average. `RSI = 100 - 100 / (1 + average_gain / average_loss)`. A zero loss and positive gain yields 100; no gains and no losses yields 50.

### ATR

True Range for a bar is `max(high-low, |high-previous_close|, |low-previous_close|)`. ATR seeds from the first `n` true ranges and then uses Wilder smoothing. It requires `n + 1` bars.

### ADX

ADX uses Wilder DMI. It calculates True Range, positive directional movement, and negative directional movement from successive bars; Wilder-smooths them; calculates `+DI`, `-DI`, and `DX`; then seeds and smooths ADX from DX values. It requires at least `2n` bars. A zero DX denominator is treated deterministically as zero, not guessed.

### Price structure

Price pivots use a configured strict local-extrema window. A pivot high is higher than every high in the configured number of bars on both sides; a pivot low is lower than every corresponding low. Two confirmed highs and two confirmed lows are required before classifying higher high, higher low, lower high, or lower low. Equal values do not form strict pivots.

## Trend classification

`TrendRules` provides the fast/slow SMA periods, whether price structure is required, and—when it is required—the pivot window. An uptrend requires `close > fast SMA > slow SMA` and, if configured, a higher high and higher low. A downtrend is the inverse. With enough data that meets neither configured condition, the result is `SIDEWAYS`; missing indicators or pivots produce `INSUFFICIENT_DATA`.

No production period or threshold is embedded in the engine. The test values are mock-only configuration.

## Limitations

The engine has no corporate-action adjustment, session/calendar logic, intraday handling, volume indicators, statistical confidence model, or production market-data adapter. Indicator values are calculations, not trade signals or recommendations.
