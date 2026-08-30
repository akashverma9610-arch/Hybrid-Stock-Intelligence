# Relative Strength

## Calculation

For configured lookback `n`, the engine calculates each available series return as:

`latest close / close n bars earlier - 1`

It then records:

- absolute stock return;
- benchmark return;
- excess return: `stock return - benchmark return`;
- optional sector return; and
- optional sector excess return: `stock return - sector return`.

Stock and benchmark each need `n + 1` valid bars. A named sector is optional: when enough sector data is available, sector fields are populated; otherwise the benchmark-based result is retained with sector fields empty. Missing stock or benchmark data returns `INSUFFICIENT_DATA`.

## Classification

`RelativeStrengthRules` supplies every boundary:

- `LEADER` at or above the configured leader excess return;
- `EMERGING_LEADER` at or above the configured emerging-leader excess return;
- `LAGGARD` at or below the configured laggard excess return;
- `AVERAGE` otherwise.

No production threshold is built into the engine. Fixture values exist solely to test deterministic behavior.

## Evidence and limitations

Results retain source observation IDs, strategy version, calculation version, as-of/evaluation times, quality, status, and separate DATA, INTERPRETATION, and INFERENCE evidence. They measure historical relative price performance only. They do not include liquidity, valuation, earnings, sector methodology, survivorship controls, trading friction, or any claim about future returns.
