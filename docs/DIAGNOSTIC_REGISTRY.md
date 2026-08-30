# Canonical 61-Diagnostic Registry

Registry version: `diagnostic-registry-v1`. This registry is a version-controlled definition set, not 61 implemented calculations and not a 61-point score. Each rule has mandatory metadata in `app/registry/canonical.py`: inputs, statuses, dependencies, data requirements, missing-data behavior, confidence policy, evaluation mode, permitted evidence classes, version, and limitations.

All rules use `PASS`, `FAIL`, `NEUTRAL`, `INSUFFICIENT_DATA`, `NOT_APPLICABLE`, and `UNVERIFIED`. Missing data must never silently become neutral, pass, or a positive score.

| ID | Canonical diagnostic | Category |
| ---: | --- | --- |
| 1 | Market Regime Classification | Market/technical |
| 2 | Sector Index Health & Trend | Market/technical |
| 3 | Sector Rotation Phase | Market/technical |
| 4 | Primary Trend Direction — Weekly & Daily | Market/technical |
| 5 | Weinstein Market Stage | Market/technical |
| 6 | Relative Strength Rank vs Nifty 50, Sector Index & Peers | Market/technical |
| 7 | Institutional / Smart Money Observable Proxies | Market/technical |
| 8 | Liquidity Pool Mapping — Buy-side & Sell-side | Market/technical |
| 9 | Wyckoff Phase Classification | Market/technical |
| 10 | Classical Market Structure — Dow HH/HL vs LH/LL | Market/technical |
| 11 | Volume Behavior & Relative Volume (RVOL) | Market/technical |
| 12 | Ichimoku Cloud Structure | Market/technical |
| 13 | Chikou Span Confirmation | Market/technical |
| 14 | Multi-Timeframe Alignment — Weekly, Daily, 4H/1H, 15M where data permits | Market/technical |
| 15 | Business Model & Moat Sustainability | Fundamental/thesis |
| 16 | Five-Year Financial Trend — Revenue, EBITDA, PAT, EPS CAGR | Fundamental/thesis |
| 17 | Return Ratios — ROCE and ROE | Fundamental/thesis |
| 18 | Operating Cash Flow & Free Cash Flow Health | Fundamental/thesis |
| 19 | Balance Sheet Leverage — Debt/Equity, Net Debt, Interest Coverage | Fundamental/thesis |
| 20 | Working Capital & Cash Conversion Cycle | Fundamental/thesis |
| 21 | Ownership Structure — Promoter Holding & Pledge | Fundamental/thesis |
| 22 | Institutional Holding Shifts — DII/MF/FII | Fundamental/thesis |
| 23 | Corporate Governance & Auditor Cleanliness | Fundamental/thesis |
| 24 | Earnings Acceleration Status — Organic vs One-Off | Fundamental/thesis |
| 25 | Latest Quarterly Results — YoY & QoQ | Fundamental/thesis |
| 26 | Operating Margin & Gross Margin Trajectory | Fundamental/thesis |
| 27 | Order Book & Book-to-Bill Ratio | Fundamental/thesis |
| 28 | Management Execution Track Record — Guidance vs Delivery | Fundamental/thesis |
| 29 | Valuation Multiples — P/E, Forward P/E, PEG, EV/EBITDA, P/B | Fundamental/thesis |
| 30 | Fundamental Catalysts — High/Medium/Low Impact | Fundamental/thesis |
| 31 | Comprehensive Risk Engine — Probability × Impact | Fundamental/thesis |
| 32 | Trading Thesis | Fundamental/thesis |
| 33 | Investment Thesis | Fundamental/thesis |
| 34 | Bull / Base / Bear Probability Scenarios | Fundamental/thesis |
| 35 | VWAP & Value Area Acceptance | Technical/risk |
| 36 | OBV Trend & Divergence | Technical/risk |
| 37 | Base Pattern Quality — VCP, Cup & Handle, Flat Base, Ascending Base | Technical/risk |
| 38 | Pullback Quality & Support Confluence | Technical/risk |
| 39 | Technical Indicator Layer — RSI, ADX, ATR | Technical/risk |
| 40 | Aggressive Entry Level | Technical/risk |
| 41 | Confirmation Entry Level | Technical/risk |
| 42 | Pullback / Retest Entry Level | Technical/risk |
| 43 | Structural Stop-Loss | Technical/risk |
| 44 | Target Hierarchy — T1, T2, Extended Target | Technical/risk |
| 45 | Risk/Reward Calculation — minimum structural R:R normally 1:2 | Technical/risk |
| 46 | Exact Thesis Invalidation Conditions | Technical/risk |
| 47 | Retail / Public Sentiment Score — 0 to 100 | Contrarian |
| 48 | Crowd Positioning Tier | Contrarian |
| 49 | Crowd Data Confidence | Contrarian |
| 50 | Institutional Accumulation vs Distribution Proxy | Contrarian |
| 51 | Major Stop-Loss Cluster Mapping | Contrarian |
| 52 | Liquidity Event Detection — Sweep, Absorption, Breakout Acceptance | Contrarian |
| 53 | Bull Trap Identification | Contrarian |
| 54 | Bear Trap Identification | Contrarian |
| 55 | Crowd Trap Probability | Contrarian |
| 56 | Price vs Crowd Sentiment Divergence | Contrarian |
| 57 | Post-News Price Reaction — Absorption vs Sell-the-News | Contrarian |
| 58 | Volume Climax & Distribution Signs | Contrarian |
| 59 | Contrarian Ichimoku Confluence | Contrarian |
| 60 | Contrarian Signal Quality — Strong / Moderate / Weak | Contrarian |
| 61 | Contrarian Action Verdict — Buy / Sell / Hold / Avoid / Wait | Contrarian |

Evaluation modes are deliberately mixed: indicators such as RSI are deterministic; business moat and thesis work are interpretive; many proxy/sentiment and pattern rules are hybrid. An interpretation is never stored as a raw FACT.

## Efficiency principle

More diagnostics do not automatically mean a better strategy. Future validation must measure predictive contribution, redundancy, regime-specific usefulness, false positives, false negatives, and whether a simpler set performs as well or better. Rule removal/reweighting can only enter a versioned experiment and validation workflow.
# Implementation coverage

All 61 canonical Rule IDs are now accounted for by an explicit implementation-maturity classification. Maturity indicates current V1 deterministic or hybrid scope only; it does not imply equal sophistication, live-data support, a Decision Score, or execution capability.
