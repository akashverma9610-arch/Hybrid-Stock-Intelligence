# Ichimoku and Multi-Timeframe Analysis

Rule 12 calculates Tenkan-sen, Kijun-sen, Senkou Span A, and Senkou Span B as high/low midpoints over configured periods. The current visible cloud uses values from the configured displacement earlier, avoiding an implicit same-bar cloud substitution. Price relative to the cloud and Tenkan/Kijun ordering produces strong bullish, strong bearish, or neutral-cloud output.

Rule 13 evaluates Chikou as the current close compared directly with the close exactly `displacement` bars earlier. The implementation requires sufficient history and has dedicated indexing tests.

Rule 14 evaluates Rule-12-style structure separately for explicitly supplied timeframe snapshots using the supplied Ichimoku configuration. It reports full alignment only when all configured timeframes agree; otherwise it reports partial, conflicting, or neutral alignment. It never resamples bars or invents a timeframe.

Rules 12–14 map only to `ichimoku_mtf` component eligibility. No score is generated.
