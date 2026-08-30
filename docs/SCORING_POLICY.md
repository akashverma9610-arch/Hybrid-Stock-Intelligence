# Canonical Decision Score and Confidence Policy

Policy version: `decision-score-policy-v1`. The Decision Score is a separate 0.0–10.0 weighted model. The 61 diagnostics are checkpoints and must not be summed as a score or coverage proxy unless a future approved report explicitly labels diagnostic coverage.

| Component | Weight | Component scale |
| --- | ---: | --- |
| Earnings Acceleration | 15% | 0.0–10.0 |
| Market Regime | 10% | 0.0–10.0 |
| Sector Rotation | 10% | 0.0–10.0 |
| Smart Money Evidence | 10% | 0.0–10.0 |
| Relative Strength | 10% | 0.0–10.0 |
| Price Structure | 10% | 0.0–10.0 |
| Volume / OBV / VWAP | 10% | 0.0–10.0 |
| Ichimoku & MTF | 10% | 0.0–10.0 |
| Valuation & Risk/Reward | 10% | 0.0–10.0 |
| Liquidity & SMC Traps | 5% | 0.0–10.0 |
| **Total** | **100%** | |

No production component-scoring formula is approved or implemented in this phase.

## Data confidence

Data confidence remains independent from the Decision Score. It retains source reliability, freshness, completeness, validation status, corroboration, and input coverage. Crowd Data Confidence is separately supported by diagnostic 49. No policy transforms a Decision Score and Data Confidence into a combined arithmetic value.

## Missing data

The default policy is `NO_SILENT_WEIGHT_RENORMALIZATION`. Missing required evidence must surface the component and reduce score eligibility/confidence. Missing evidence cannot be converted to neutral or positive, and remaining weights cannot be silently rescaled. A future strategy version may define a different treatment only through explicit approval and validation.
# Phase 5A implementation

The canonical 10-component policy is now implemented as an immutable analytical scorecard configuration. It does not create Decision Score weights beyond the canonical registry, silently renormalize missing components, or execute any gate/order action.
