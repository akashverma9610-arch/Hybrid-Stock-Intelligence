# Decision Score

The Phase 5A Decision Score is a separate long-candidate analytical product on a 0.0–10.0 scale. It is the weighted sum of ten component scores: `sum(component score × component weight)`. It is not diagnostic coverage, data confidence, probability of success, expected return, a signal, an order, an allocation, or gate authorization.

Missing mandatory diagnostics produce `SCORE_INCOMPLETE` with no final comparable score. Weights are never silently renormalized. Confidence is reported separately and never silently multiplies the raw score. Analytical warnings remain separate from the score.

Decision scorecards are append-only persisted records: diagnostics → scoring configuration → complete component records → Decision Scorecard → audit reconstruction. Persistence validates strategy, diagnostic IDs, instrument, and as-of compatibility. Recomputed historical inputs must match the stored card; a mismatch is an audit failure and never overwrites history.
