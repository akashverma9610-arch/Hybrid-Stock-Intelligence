# Volume Analysis

Rule 11 calculates relative volume (RVOL) as:

`current-bar volume / arithmetic mean of the preceding configured lookback volumes`

It returns `EXPANSION`, `CONTRACTION`, or `NORMAL` from explicit high/low thresholds. All required bars must carry volume and be valid in the supplied as-of snapshot. High RVOL is activity only; it does **not** establish institutional accumulation, buying pressure, or fund flow.

Rules 11, 35, and 36 map to component eligibility for `volume_obv_vwap`. This phase does not calculate a component or aggregate score.
