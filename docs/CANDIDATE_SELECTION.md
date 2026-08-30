# Candidate Selection

Selection is a frozen TRAIN/VALIDATION-only decision. It compares a candidate with the baseline across expectancy, Sharpe, drawdown, costs, trade-count sufficiency, and a transparent parameter-count complexity penalty. Tiny improvements, excessive drawdown, fragile sensitivity, or insufficient samples retain the baseline or return an inconclusive status.

`CANDIDATE_SELECTED` means only that the immutable candidate may be used for a future clean TEST window. It never promotes, deploys, or mutates the approved strategy.

Deterministic bootstrap/resampling uncertainty intervals and automated selection-result handoff into `WalkForwardWindow` are deliberately deferred. A caller must presently supply the already-frozen selected candidate to the existing walk-forward boundary; it must not reselect during TEST.
# Self-improvement bridge boundary

A bridge-created candidate is a complete frozen candidate snapshot plus a bounded delta. It cannot be selected automatically: candidate evaluation, robustness, and selection remain the existing later Phase 8B.2 process.
