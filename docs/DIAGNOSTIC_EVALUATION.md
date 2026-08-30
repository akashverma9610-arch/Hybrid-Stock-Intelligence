# First Deterministic Diagnostic Evaluators

This phase evaluates canonical Rules 1, 2, 3, 4, 5, 6, 10, 11, 12, 13, 14, 35, 36, and 39. Each wrapper references immutable canonical metadata and retains registry/strategy versions, as-of time, evidence, input IDs, confidence, and separate eligibility. Missing data returns `INSUFFICIENT_DATA`, not `FAIL`.

Rule 1 reuses `MarketRegimeEngine`; Rule 4 uses explicit weekly and daily `TrendEngine` inputs and returns `MIXED` on disagreement; Rule 5 is a versioned long-MA/slope approximation; Rule 6 reuses `RelativeStrengthEngine`; Rule 10 reuses confirmed pivots; Rule 39 consumes RSI, ADX, and ATR without recalculating them.

Eligibility maps implemented rules to score components without creating a numerical score. All evaluators consume as-of snapshots only, preserving anti-look-ahead behavior.

Rules 2/3 reuse the sector-return engine; Rule 11 reuses RVOL; Rules 12/13 reuse Ichimoku and Chikou calculations; Rule 14 aggregates explicit timeframe outputs without resampling; Rule 35 reuses VWAP; and Rule 36 reuses OBV/divergence. Sector rotation and volume interpretations are explicitly labelled as observable proxies/inferences, not factual fund-flow or institutional claims. Value Area remains unavailable without volume-at-price input.

The regression suite builds each evaluator's snapshot before and after material future observations are ingested, then proves the earlier result, evidence, inputs, and confidence are unchanged for Rules 1, 2, 3, 4, 5, 6, 10, 11, 12, 13, 14, 35, 36, and 39. Evaluators accept no raw-observation argument; a manually contaminated snapshot is rejected by the shared price-bar boundary as invalid rather than allowing future bars into calculation.

Phase 4C.1 additionally evaluates Rules 16–22 and 24–27 from validated mock financial filings. Publication timestamp, rather than reporting period end, controls as-of availability. Each result carries immutable input/evidence IDs, independent confidence, and component eligibility only—never a Decision Score.

The Rule 20 canonical accounting method uses average balances where both beginning and ending values are available, COGS for DIO/DPO, and an explicit partial result when COGS is unavailable. Rule 17 records the configured ROCE denominator method and whether average or ending balances were used. These details are deterministic audit inputs, not implicit accounting assumptions.

Phase 4C.2 adds Rules 15, 23, 28, and 30. They use structured published research claims and maintain evidence/input IDs, confidence, source tier, and as-of limits. They do not use an LLM or infer unreferenced qualitative conclusions.

Phase 4D adds Rules 29, 37, 38, and 40–46. Valuation joins as-of price with filings known by that time; trade-plan structures depend on validated base/support information and remain analysis only, never signals or orders.

Rule 37 now distinguishes configured VCP, Flat Base, Cup & Handle, and Ascending Base candidates. It preserves duration, depth, support/resistance, base height, contraction, support consistency, pivot clarity, volume availability, breakout readiness, quality metadata, candidate list, and deterministic resolution policy separately from the pattern type.

Phase 4E.1 adds Rules 7–9, 50–54, and 58 through deterministic price/volume/liquidity proxies. Pool formation, event confirmation, traps, Wyckoff, stop clusters, and smart-money language remain explicitly inferred/observable, never direct institutional or broker-order claims.

Phase 4E.2 adds Rules 47–49, 55–57, and 59–61 with mock crowd data. Crowd score, positioning, and confidence stay separate; all post-news and contrarian outputs are as-of constrained diagnostic evidence, not executable signals.

Phase 4F adds Rules 31–34 through `HigherOrderDiagnosticContext`, which accepts only eligible as-of upstream diagnostics. Risk, theses, and scenarios retain upstream IDs and configuration version; none calculates the separate 0–10 Decision Score or executes a trade.
