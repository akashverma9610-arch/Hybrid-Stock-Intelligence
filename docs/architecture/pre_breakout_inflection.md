# Pre-Breakout and Inflection Candidate Engines

## Role and boundary

`app.strategies.pre_breakout` and `app.strategies.inflection` are immutable,
point-in-time candidate-generation modules. Their only positive outcome is
`CANDIDATE_GENERATED`; it is a handoff to the existing Brain, not an action.
They do not compute Decision Score or confidence, evaluate a gate, compare
portfolio holdings, submit an order, or mutate strategy governance.

The required path is:

`Macro Intelligence → Sector Rotation → Strategy Scanner → 61-point Research → Catalyst Validation → Decision Score → Confidence → Six Gates → Portfolio / Rotation → Execution`.

Setup Quality is an independent 0–100 measure of strategy-fit components only.
It is not a final score and is never supplied to Decision Score twice.

## Pre-breakout

The versioned `PreBreakoutConfig` defaults to NIFTY 500, MRS lookbacks of
20/60/120, top three sectors, BBW percentile ≤10 over a 120-session history,
five-session mean ATR contraction versus the preceding five sessions,
consolidation volume below 50% of volume SMA20, delivery >60%, 3–6% below the
52-week high, RSI14 55–65, and R:R ≥3. There are no hidden sector weights:
sector selection is lexicographic by 20D, 60D, 120D MRS then 50/200DMA breadth.

`MRS_L = 100 * (relative_line[-1] / mean(relative_line[-L:]) - 1)`, where
`relative_line = sector / benchmark`. Historical membership must be frozen at
the scan `as_of`. Delivery is source-backed only; absent delivery remains
`DELIVERY_DATA_UNAVAILABLE`, never a pass.

Trigger, stop, and target are supplied by actual structural evidence. The stop
is never moved to a preferred percentage. A 7% structural stop remains 7%; the
existing risk/execution layer may reject feasibility. A target is never inflated
to satisfy R:R, and insufficient structure remains partial.

## Inflection

The versioned `InflectionConfig` defaults to a ₹1,000–₹25,000 crore universe,
ROCE >15%, D/E <0.8, gross-block YoY growth >15%, OPM expansion ≥200 bps,
combined FII+DII change ≥+1.0 percentage point over two quarters, and a zero or
declining promoter pledge. Comparisons require like statement scope/period and
point-in-time official facts; missing ownership or fundamentals stays research
incomplete.

Themes are evidence references from macro and sector intelligence, never a
hard-coded sector list. Company sensitivity can contradict a sector tailwind;
a negative company transmission prevents an inflection candidate. Catalyst
records are contextual, with primary-source precedence and their existing
materiality contract. Market-integrity evidence stays a warning/proxy boundary,
not an unsupported manipulation assertion.

## Persistence, attribution, and privacy

The existing append-only Core snapshot repository stores strategy config,
sector scan, candidates, setup quality, and separate swing/inflection outcome
attribution families. Attribution is not a pooled performance series: swing
uses MFE/MAE/R style fields, while inflection uses 6/12/18-month alpha and
drawdown fields. Calibration and ablation may assess versioned parameters but
cannot alter production thresholds without existing governed human approval.

Public views may eventually show strategy tag, setup quality, horizon,
trigger/structural stop/target/R:R, evidence coverage, Decision Score, and
confidence. They must not reveal diagnostic IDs, weights, gate IDs, private
ranking mechanics, or internal calibration evidence.

## Current data limits

Production eligibility requires approved canonical delivery, ownership,
financial, historical-membership, and corporate-action sources. Prototype
price history is not authoritative delivery or ownership evidence. No automatic
trading, broker/account operation, frontend endpoint, or full-universe runtime
scan is introduced by this package.
