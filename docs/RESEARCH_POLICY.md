# Research, Catalyst, and Self-Improvement Policy

Research-policy version: `research-policy-v1`.

## Source hierarchy

1. Primary/regulatory: NSE/BSE/regulatory filings, company results/disclosures, investor presentations, earnings-call material.
2. High-quality financial/news sources.
3. Social/community sources: sentiment evidence only; they cannot override verified primary filings.

Research records distinguish FACT, MATERIALITY, DURATION, EARNINGS_IMPACT, CATALYST_TIMING, EXPECTATION_VS_REALITY, and POST_NEWS_PRICE_REACTION.

Catalyst timing categories are IMMEDIATE (0–30 days), NEAR_TERM (1–3 months), and MEDIUM_TERM (3–12 months). Future catalyst records retain event, materiality, probability, expected business/earnings impact, timing, and whether the market may already reflect it.

## Improvement governance

Canonical lifecycle:

`Observation → hypothesis → experiment → historical backtest → walk-forward validation → out-of-sample validation → forward/paper validation → review → strategy promotion or rejection`

An experiment must retain ID, parent strategy, hypothesis, proposed change, rationale, affected diagnostics/weights/gates, training and validation samples, sample size, results, baseline comparison, approval/rejection, and new version if promoted. ACTIVE rules are never silently changed.
# Research intelligence extension

Deterministic mock research claims use the documented five-tier source hierarchy. Publication and retrieval timestamps control historical availability; structured claims must be attributable to an eligible document. No live provider, scraping, or LLM inference is used in this phase.

Mock crowd observations are lower-confidence sentiment/positioning evidence. They cannot override verified primary company or exchange facts, and duplicate/echo lineage is not independent corroboration.
