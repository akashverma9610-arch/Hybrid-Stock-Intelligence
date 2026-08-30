# OOS Stability Analysis

`WalkForwardValidationConfig` freezes sufficiency and warning thresholds. The aggregate records profitable-window rate, return/expectancy/Sharpe dispersion, median/worst return and drawdown, and trade-count dispersion. Undefined metrics remain unavailable rather than being inferred.

Optional TRAIN or VALIDATION reports may be compared only when their end precedes the associated TEST start. These produce transparent degradation warnings such as `VALIDATION_TO_TEST_DEGRADATION`; TEST data is never selection evidence. Neutral statuses are `VALID`, `INSUFFICIENT_EVIDENCE`, `DEGRADED`, `UNSTABLE`, and `FAILED_AUDIT`—none promotes a strategy.
