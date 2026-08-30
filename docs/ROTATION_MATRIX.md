# Rotation Matrix

Each eligible candidate is compared with each comparable holding. A matrix row retains holding/candidate scores, score gap, exact hurdle, sectors, holding current-price forward R:R, candidate fresh-entry R:R, confidence, invalidation/risk context, gate status, friction result, reasons, warnings, and analytical result.

Original-entry R:R and current-price forward R:R are separate fields. The V1 comparison uses the holding's current forward R:R when available, so it does not silently compare a candidate's fresh-entry R:R with stale entry economics. Missing forward R:R remains unavailable.

Ranking is transparent: score, then confidence, then R:R, then the configured stable instrument identifier. These are tie-breakers, not a hidden composite score.
