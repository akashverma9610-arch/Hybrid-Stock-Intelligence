# Rule Horizon / Timeframe Applicability Policy V1

**Status:** `RULE_HORIZON_TIMEFRAME_APPLICABILITY_POLICY_V1_CANDIDATE / DOCUMENTATION_AND_DATA_POLICY_ONLY / NOT_ACTIVE`.

## Scope, non-activation, and preserved invariants

This is a candidate policy over the existing canonical 61-rule registry.  It
does not create a horizon-specific copy of a Rule, calculate an indicator,
change a threshold or lookback, bind an evaluator to a new interval, create a
technical Brain, operate an Internal Radar, acquire taxonomy/peer data, create
a setup/signal/alert, change a portfolio, or call a broker or order interface.
It is not a Multi-Timeframe Technical Orchestrator.

```text
ONE_CANONICAL_61_DIAGNOSTIC_REGISTRY = TRUE
SEPARATE_TECHNICAL_BRAIN = FALSE
NO_INDICATOR_EXPANSION = TRUE
PRIMARY_TECHNICAL_DISCOVERY = HSI_INTERNAL_RADAR
EXTERNAL_SCREENER_AUTHORITY = OPTIONAL_DISCOVERY_ONLY
HORIZON_SPECIFIC_TECHNICAL_POLICY = NOT_ACTIVE
MULTI_TIMEFRAME_TECHNICAL_ORCHESTRATOR = NOT_ACTIVE
HSI_EFFICIENT_VALIDATION_EXECUTION_POLICY_V1 = ACTIVE
```

The candidate records semantic relevance and a fail-closed role vocabulary.
It is not an eligibility, scoring, capital-authorisation, or setup policy.
The current runner, its `canonical-universe-analysis / v1` definition, and
existing rule-specific missing-data behaviour remain authoritative until a
separate human approval and implementation slice activates any part of this
candidate.

## A. Canonical policy artifact and deterministic coverage

The companion [machine-readable candidate](RULE_HORIZON_TIMEFRAME_APPLICABILITY_POLICY_V1_CANDIDATE.json)
is the canonical representation for this document.  It has exactly these
fixed, ordered vocabularies:

```text
policy_id  = rule-horizon-timeframe-applicability-policy
version    = v1-candidate
horizons   = SHORT_TERM, POSITIONAL, LONG_TERM
timeframes = 15m, 30m, 1H, 4H, 1D, 1W, 1M
```

Its content fingerprint is the SHA-256 of UTF-8 canonical JSON formed by
lexicographically sorting object keys, retaining array order, using compact
JSON separators, and excluding only the `policy_fingerprint` field.  The
candidate is invalid if a Rule ID is missing, duplicated, outside 1–61, uses a
fourth horizon, references a nonexistent technical profile, or changes a
profile without a corresponding fingerprint change.  Its normalized model
contains exactly **61 × 3 = 183** Rule×Horizon rows and, for the 42 rules with
a technical/technical-dependent profile, exactly **42 × 3 × 7 = 882**
Rule×Horizon×Timeframe role cells.  Profile expansion is a storage
normalization only; it does not omit an individual Rule×Horizon×Timeframe
semantic.

```text
policy_fingerprint = sha256:bc1f7548b372738d69b72c2e54afdc34c9f10929aee9a10d834ce99cb8d43d8a
```

`HORIZON_DURATION_BOUNDARIES = UNSET`.  Horizons describe investment intent,
evidence cadence, and setup lifecycle; they are not calendar-day holding
limits in this candidate.  `MID_TERM` is not a fourth canonical ID.  The only
canonical horizons are:

| ID | Semantic purpose | Fundamental/governance contract |
| --- | --- | --- |
| `SHORT_TERM` | Time-sensitive technical or catalyst context, subject to a future genuine completed intraday-bar path where a strategy needs it. | Material governance, legal, balance-sheet, and event-risk review remains required where applicable; a technical trigger does not erase red flags. |
| `POSITIONAL` | Multi-session company and technical context, normally using the existing Daily evidence as the candidate primary technical input. | Deeper earnings, margin, debt, cash-flow, ownership, business-state, and material-risk evidence is relevant; diagnostic breadth does not itself become one universal hard gate. |
| `LONG_TERM` | Structural business/investment-thesis context. | Business quality, multi-period growth, cash flow, capital structure, governance, ownership, valuation, and structural thesis evidence are central. |

`SETUP_TYPE != HORIZON`.  For example, `PRE_BREAKOUT`, `BREAKOUT_SETUP`,
`TECHNICAL_SETUP`, `POSITIONAL_TRADE`, `CATALYST_NEWS_DRIVEN`, and
`LONG_TERM_BIG_SETUP` answer why a setup exists; a separate canonical horizon
answers the interpretation context.  This candidate creates neither field on a
setup or Trade UI.

## B. Research receipts — context only, not imported parameters

The policy records the following external research separately from HSI
semantics.  It does **not** import their numerical lookbacks, holding periods,
thresholds, or performance claims into HSI.

| Source | Research-only finding used | Explicit non-transfer |
| --- | --- | --- |
| [CFA Institute, *Company Analysis: Forecasting*](https://www.cfainstitute.org/insights/professional-learning/refresher-readings/2026/company-analysis-forecasting) | A forecast horizon should be selected for the investment strategy, while considering industry cyclicality and company-specific facts. | No forecast, duration boundary, valuation method, or company recommendation is introduced. |
| [CFA Institute, *Technical Analysis: Modern Perspectives*](https://rpc.cfainstitute.org/research/foundation/2017/technical-analysis) | Technical analysis is used alongside, rather than as a replacement for, fundamental and macro analysis. | No validation of an HSI signal, indicator, or timeframe choice. |
| [Moskowitz, Ooi and Pedersen, *Time Series Momentum*](https://doi.org/10.1016/j.jfineco.2011.11.003) | The study distinguishes formation/lookback and holding horizons in time-series momentum research. | Its evaluated month horizons and volatility sizing are not HSI policy. |
| [NSE India market timings](https://www.nseindia.com/static/market-data/market-timings) | NSE cash-market session boundaries are exchange-specific and include pre-open, normal, auction, and closing sessions. | The page does not select a 4H composition, intraday signal timeframe, or completed-bar policy for HSI. |

The literature supports the need to keep comparison periods and trading intent
explicit.  It does not justify treating Daily as Weekly/Monthly/4H or creating
a number merely to complete a horizon matrix.  In particular, 20/60/125/250
session and 3/6/12-month values remain research context unless already frozen
inside a separate, governed HSI policy such as Pre-Breakout.

## C. Timeframe role vocabulary

| Role/state | Exact candidate meaning |
| --- | --- |
| `PRIMARY` | Existing canonical evidence is the intended leading observation interval for this Rule/Horizon candidate. It does not activate a result. |
| `CONFIRMING` | Existing canonical evidence can corroborate a primary interval; it cannot silently become primary. |
| `CONTEXT` | Relevant descriptive evidence only; it cannot create a setup, score, action, or override a required source. |
| `EXECUTION` | Reserved future role. No cell uses it to authorise execution in V1. |
| `NOT_USED` | The interval has no role for that Rule/Horizon under this candidate. |
| `POLICY_UNSET` | The rule is semantically relevant but no approved interval-role choice exists. |
| `DATA_NOT_READY` | A genuine interval would be relevant to the stated context, but canonical closed/PIT-safe evidence is not operational. |

`1D != 1W != 1M != 4H`.  An independently certified Weekly artifact is not a
Daily snapshot under a new label.  A genuine 4H identity has no approved NSE
session composition.  15m/30m/1H and 1M have no production-operational
canonical input path for this candidate.  Where a profile reports
`DATA_NOT_READY`, no substitute interval is permitted.

The retained UDiFF-era Daily source span may mechanically cover portions of
calendar months, but there is no canonical Monthly artifact, Monthly storage
timeframe, long-history sufficiency receipt, or historical PIT availability
proof.  That mechanical source span is therefore not Monthly evidence and
cannot change any `1M` cell from `DATA_NOT_READY`.

## D. Full 61-rule archaeology

`Current interval` and `lookback` below report existing evaluator/input facts,
not recommended horizon parameters.  All rules retain the registry's existing
`INSUFFICIENT_DATA`/`UNVERIFIED` fail-closed behaviour when required inputs are
missing; no row is an execution gate unless noted as downstream only.

| ID | Canonical rule | Class / evaluator | Current inputs, interval and lookback | Current applicability / missing-data fact |
| ---: | --- | --- | --- | --- |
| 1 | Market Regime Classification | technical; `market_regime` | exact `NIFTY_50`; 1D; return 3, SMA 2/3, ATR 2 | benchmark alignment required; no horizon language; not a gate |
| 2 | Sector Index Health & Trend | technical; `sector_health` | exact sector index + `NIFTY_50`; 1D; return 3 | sector mapping/OHLC fail closed; not a gate |
| 3 | Sector Rotation Phase | technical; `sector_rotation` | exact sector index + `NIFTY_50`; 1D; return 3 | sector mapping/OHLC fail closed; not a gate |
| 4 | Primary Trend Direction — Weekly & Daily | technical; `primary_trend` | distinct 1D + 1W; `TrendRules(3,5,pivot=1)` | both genuine inputs required; no horizon binding |
| 5 | Weinstein Market Stage | technical; `weinstein` | 1W; MA 3, slope 2 | genuine Weekly required; no horizon binding |
| 6 | Relative Strength Rank vs Nifty 50, Sector Index & Peers | technical; `relative_strength` | 1D stock/`NIFTY_50`, optional sector; return 3 | peer tuple unused; peer leg partial; not a gate |
| 7 | Institutional / Smart Money Observable Proxies | technical proxy; `smart_money_proxies` | 1D OHLCV; liquidity lookback 3 | no order-flow claim; volume absence fails closed |
| 8 | Liquidity Pool Mapping — Buy-side & Sell-side | technical proxy; `liquidity_pools` | 1D OHLCV; touches 2 | no order-book claim; missing volume/price fails closed |
| 9 | Wyckoff Phase Classification | technical proxy; `wyckoff_phase` | 1D OHLCV; lookback 3 | no institutional-flow inference |
| 10 | Classical Market Structure — Dow HH/HL vs LH/LL | technical; `market_structure` | 1D; 6 observations, pivot 1 | confirmed pivots required |
| 11 | Volume Behavior & Relative Volume (RVOL) | technical; `volume` | 1D OHLCV; lookback 3; frozen 1.5/0.5 settings | volume continuity required |
| 12 | Ichimoku Cloud Structure | technical; `ichimoku` | 1D OHLC; 2/3/4/1 | genuine interval evidence required |
| 13 | Chikou Span Confirmation | technical; `chikou` | 1D OHLC; 2/3/4/1 | genuine interval evidence required |
| 14 | Multi-Timeframe Alignment — Weekly, Daily, 4H/1H, 15M where data permits | technical; `mtf` | distinct 1D + 1W required; 5/5 input gate | duplicate-timeframe rejection; 4H/1H/15m unavailable |
| 15 | Business Model & Moat Sustainability | fundamental/research; `business_model_moat` | verified research/disclosure lineage | no market interval; research insufficiency fails closed |
| 16 | Five-Year Financial Trend — Revenue, EBITDA, PAT, EPS CAGR | fundamental; `financial_trend` | financial snapshot; frozen annual/quarter constants | no market interval; financial gaps fail closed |
| 17 | Return Ratios — ROCE and ROE | fundamental; `return_ratios` | financial snapshot; frozen return-ratio method | no market interval; no universal financial-company substitution |
| 18 | Operating Cash Flow & Free Cash Flow Health | fundamental; `cash_flow` | financial snapshot | no market interval; missing cash facts fail closed |
| 19 | Balance Sheet Leverage — Debt/Equity, Net Debt, Interest Coverage | fundamental | financial snapshot; frozen leverage 1.5 | no market interval; material risk remains relevant in all horizons |
| 20 | Working Capital & Cash Conversion Cycle | fundamental | financial snapshot | no market interval; comparability required |
| 21 | Ownership Structure — Promoter Holding & Pledge | ownership | ownership snapshot | no market interval; source/PIT validity required |
| 22 | Institutional Holding Shifts — DII/MF/FII | ownership | ownership snapshot | no market interval; source/PIT validity required |
| 23 | Corporate Governance & Auditor Cleanliness | governance/research | verified research/disclosure lineage | no market interval; material governance concern remains relevant |
| 24 | Earnings Acceleration Status — Organic vs One-Off | fundamental | financial snapshot | no market interval; source/period comparability required |
| 25 | Latest Quarterly Results — YoY & QoQ | fundamental | financial snapshot; quarter semantics | no market interval; missing comparable period fails closed |
| 26 | Operating Margin & Gross Margin Trajectory | fundamental | financial snapshot; frozen margin change .02 | no market interval; comparability required |
| 27 | Order Book & Book-to-Bill Ratio | fundamental | financial snapshot/disclosure | no market interval; evidence missing remains insufficient |
| 28 | Management Execution Track Record — Guidance vs Delivery | research | verified research/disclosure lineage | no market interval; no unsupported management conclusion |
| 29 | Valuation Multiples — P/E, Forward P/E, PEG, EV/EBITDA, P/B | mixed; `valuation_multiples` | 1D price + financial snapshot; frozen 15/35 | price context is not a valuation forecast |
| 30 | Fundamental Catalysts — High/Medium/Low Impact | research | verified research/disclosure lineage | no market interval; existing impact semantics only |
| 31 | Comprehensive Risk Engine — Probability × Impact | mixed synthesis | prior canonical 1/2/46 and risk context | upstream states required; no direct timeframe |
| 32 | Trading Thesis | mixed synthesis | prior 43/45/46 | upstream descriptive results required; no gate |
| 33 | Investment Thesis | fundamental synthesis | prior 16–19,23 | upstream facts required; no direct timeframe |
| 34 | Bull / Base / Bear Probability Scenarios | mixed synthesis | prior 31–33 | no forecast authority; no direct timeframe |
| 35 | VWAP & Value Area Acceptance | technical | named session VWAP/value-area semantics absent | canonical path intentionally returns insufficient data |
| 36 | OBV Trend & Divergence | technical | 1D OHLCV; lookback 3 | volume continuity required |
| 37 | Base Pattern Quality — VCP, Cup & Handle, Flat Base, Ascending Base | technical execution context | 1D price; `TradeRules` base 5 | descriptive only, not a setup/order |
| 38 | Pullback Quality & Support Confluence | technical execution context | 1D price; `TradeRules` | descriptive only |
| 39 | Technical Indicator Layer — RSI, ADX, ATR | technical | 1D OHLC; frozen 3/70/30/20/2 | no new indicator/horizon parameter |
| 40 | Aggressive Entry Level | technical execution context | 1D price; `TradeRules` | descriptive level, never order authority |
| 41 | Confirmation Entry Level | technical execution context | 1D price; `TradeRules` | descriptive level, never order authority |
| 42 | Pullback / Retest Entry Level | technical execution context | 1D price; `TradeRules` | descriptive level, never order authority |
| 43 | Structural Stop-Loss | technical execution context | 1D price; `TradeRules` | descriptive risk fact, never automatic exit |
| 44 | Target Hierarchy — T1, T2, Extended Target | technical execution context | 1D price; `TradeRules` | descriptive level, never automatic action |
| 45 | Risk/Reward Calculation — minimum structural R:R normally 1:2 | technical execution context | existing 40/43/44 outputs; `TradeRules` | upstream levels required; downstream gate remains separate |
| 46 | Exact Thesis Invalidation Conditions | technical execution context | 1D price; `TradeRules` | structural invalidation fact, never automatic sell |
| 47 | Retail / Public Sentiment Score — 0 to 100 | crowd | crowd evidence | no direct interval; source confidence separate |
| 48 | Crowd Positioning Tier | crowd | crowd evidence | no direct interval |
| 49 | Crowd Data Confidence | crowd | crowd evidence | no direct interval |
| 50 | Institutional Accumulation vs Distribution Proxy | technical proxy | 1D OHLCV; lookback 3 | proxy only; no flow claim |
| 51 | Major Stop-Loss Cluster Mapping | technical proxy | 1D OHLCV; lookback 3 | proxy only; no stop-book claim |
| 52 | Liquidity Event Detection — Sweep, Absorption, Breakout Acceptance | technical proxy | 1D OHLCV; lookback 3 | proxy only; intraday/depth absent |
| 53 | Bull Trap Identification | technical proxy | 1D OHLCV; lookback 3 | proxy only; closed-bar evidence required |
| 54 | Bear Trap Identification | technical proxy | 1D OHLCV; lookback 3 | proxy only; closed-bar evidence required |
| 55 | Crowd Trap Probability | mixed technical/crowd | crowd + 1D context | upstream crowd and price lineage required |
| 56 | Price vs Crowd Sentiment Divergence | mixed technical/crowd | crowd + 1D context | upstream crowd and price lineage required |
| 57 | Post-News Price Reaction — Absorption vs Sell-the-News | event/mixed | exact event + completed post-event market context | event/session evidence absent; no price-reaction inference |
| 58 | Volume Climax & Distribution Signs | technical proxy | 1D OHLCV; lookback 3 | volume continuity required |
| 59 | Contrarian Ichimoku Confluence | technical/crowd synthesis | 47,12,13,14 | genuine MTF and crowd inputs required |
| 60 | Contrarian Signal Quality — Strong / Moderate / Weak | technical/crowd synthesis | 55,56,59,49 | upstream inputs required |
| 61 | Contrarian Action Verdict — Buy / Sell / Hold / Avoid / Wait | technical/crowd synthesis | 60,49 | existing diagnostic label is not product trade authority |

No canonical Rule currently invokes Six Gates.  The execution-gate registry is
downstream of diagnostics.  Rules 40–46 and 61 may contain legacy
execution-shaped *descriptive diagnostic vocabulary*, but this policy cannot
convert any of it into an order, capital allocation, or portfolio mutation.

## E. Full Rule×Horizon applicability matrix

The following is the human-readable rendering of all 183 rows in the
candidate artifact.  `APPLICABLE` means the Rule's existing evidence category
is relevant to that horizon; it does not make the Rule data-ready or a hard
gate.  `CONTEXT` means it can inform interpretation but is not promoted to a
universal mandatory pass.  `POLICY_UNSET` exposes a material unapproved
semantic.  `NOT_APPLICABLE` is reserved for a genuinely unsuitable role.

| Rule | Short-Term | Positional | Long-Term |
| ---: | --- | --- | --- |
| 1 | CONTEXT | CONTEXT | CONTEXT |
| 2 | CONTEXT | CONTEXT | CONTEXT |
| 3 | CONTEXT | APPLICABLE | CONTEXT |
| 4 | CONTEXT | APPLICABLE | CONTEXT |
| 5 | CONTEXT | APPLICABLE | CONTEXT |
| 6 | CONTEXT | APPLICABLE | CONTEXT |
| 7 | APPLICABLE | APPLICABLE | CONTEXT |
| 8 | APPLICABLE | APPLICABLE | CONTEXT |
| 9 | APPLICABLE | APPLICABLE | CONTEXT |
| 10 | APPLICABLE | APPLICABLE | CONTEXT |
| 11 | APPLICABLE | APPLICABLE | CONTEXT |
| 12 | APPLICABLE | APPLICABLE | CONTEXT |
| 13 | APPLICABLE | APPLICABLE | CONTEXT |
| 14 | POLICY_UNSET | POLICY_UNSET | POLICY_UNSET |
| 15 | CONTEXT | APPLICABLE | APPLICABLE |
| 16 | CONTEXT | APPLICABLE | APPLICABLE |
| 17 | CONTEXT | APPLICABLE | APPLICABLE |
| 18 | CONTEXT | APPLICABLE | APPLICABLE |
| 19 | APPLICABLE | APPLICABLE | APPLICABLE |
| 20 | CONTEXT | APPLICABLE | APPLICABLE |
| 21 | CONTEXT | APPLICABLE | APPLICABLE |
| 22 | CONTEXT | APPLICABLE | APPLICABLE |
| 23 | APPLICABLE | APPLICABLE | APPLICABLE |
| 24 | CONTEXT | APPLICABLE | APPLICABLE |
| 25 | CONTEXT | APPLICABLE | APPLICABLE |
| 26 | CONTEXT | APPLICABLE | APPLICABLE |
| 27 | CONTEXT | APPLICABLE | APPLICABLE |
| 28 | CONTEXT | APPLICABLE | APPLICABLE |
| 29 | CONTEXT | APPLICABLE | APPLICABLE |
| 30 | CONTEXT | APPLICABLE | APPLICABLE |
| 31 | APPLICABLE | APPLICABLE | APPLICABLE |
| 32 | APPLICABLE | APPLICABLE | CONTEXT |
| 33 | CONTEXT | CONTEXT | APPLICABLE |
| 34 | CONTEXT | CONTEXT | CONTEXT |
| 35 | APPLICABLE | APPLICABLE | NOT_APPLICABLE |
| 36 | APPLICABLE | APPLICABLE | CONTEXT |
| 37 | APPLICABLE | APPLICABLE | CONTEXT |
| 38 | APPLICABLE | APPLICABLE | CONTEXT |
| 39 | APPLICABLE | APPLICABLE | CONTEXT |
| 40 | APPLICABLE | APPLICABLE | POLICY_UNSET |
| 41 | APPLICABLE | APPLICABLE | POLICY_UNSET |
| 42 | APPLICABLE | APPLICABLE | POLICY_UNSET |
| 43 | APPLICABLE | APPLICABLE | CONTEXT |
| 44 | APPLICABLE | APPLICABLE | POLICY_UNSET |
| 45 | APPLICABLE | APPLICABLE | POLICY_UNSET |
| 46 | APPLICABLE | APPLICABLE | APPLICABLE |
| 47 | CONTEXT | CONTEXT | CONTEXT |
| 48 | CONTEXT | CONTEXT | CONTEXT |
| 49 | CONTEXT | CONTEXT | CONTEXT |
| 50 | APPLICABLE | APPLICABLE | CONTEXT |
| 51 | APPLICABLE | APPLICABLE | CONTEXT |
| 52 | APPLICABLE | APPLICABLE | CONTEXT |
| 53 | APPLICABLE | APPLICABLE | CONTEXT |
| 54 | APPLICABLE | APPLICABLE | CONTEXT |
| 55 | CONTEXT | CONTEXT | CONTEXT |
| 56 | CONTEXT | CONTEXT | CONTEXT |
| 57 | APPLICABLE | CONTEXT | CONTEXT |
| 58 | APPLICABLE | APPLICABLE | CONTEXT |
| 59 | POLICY_UNSET | POLICY_UNSET | NOT_APPLICABLE |
| 60 | POLICY_UNSET | POLICY_UNSET | NOT_APPLICABLE |
| 61 | POLICY_UNSET | POLICY_UNSET | NOT_APPLICABLE |

## F. Technical timeframe-role matrix

The JSON profiles expand the complete 882-cell technical matrix.  This table
names every Rule assignment; each profile has an explicit role for all three
horizons and all seven canonical timeframes.  The complete profile cells are
in the machine-readable artifact, rather than repeated here as a misleading
fake-MTF narrative.

| Profile | Rule IDs | Short-Term | Positional | Long-Term |
| --- | --- | --- | --- | --- |
| `BENCHMARK_SECTOR_DAILY` | 1–3 | intraday/4H `DATA_NOT_READY`; 1D `CONTEXT` | 1D `PRIMARY`; 4H `DATA_NOT_READY`; 1W `CONTEXT` | 1D/1W `CONTEXT`; 1M `DATA_NOT_READY` |
| `TREND_DAILY_WEEKLY` | 4 | intraday/4H `DATA_NOT_READY`; 1D/1W `CONTEXT` | 1D and 1W `POLICY_UNSET` despite both current inputs being required | 1W `PRIMARY`, 1D `CONFIRMING`, 1M `DATA_NOT_READY` |
| `WEEKLY_STRUCTURE` | 5 | 1D/1W `CONTEXT` | 1W `PRIMARY`, 1D `CONTEXT` | 1W `PRIMARY`, 1D `CONFIRMING`, 1M `DATA_NOT_READY` |
| `RELATIVE_STRENGTH_DAILY` | 6 | intraday/4H `DATA_NOT_READY`; 1D `CONTEXT` | 1D `PRIMARY`; 1W `POLICY_UNSET` | 1D `CONTEXT`; 1W `POLICY_UNSET`; 1M `DATA_NOT_READY` |
| `DAILY_PRICE_VOLUME` | 7–9,11,36,50–54,58 | intraday/4H `DATA_NOT_READY`; 1D `CONTEXT` | 1D `PRIMARY`; 1W `CONTEXT` | 1D/1W `CONTEXT`; 1M `DATA_NOT_READY` |
| `DAILY_PRICE` | 10,12,13,39 | intraday/4H `DATA_NOT_READY`; 1D `CONTEXT` | 1D `PRIMARY`; 1W `CONTEXT` | 1D/1W `CONTEXT`; 1M `DATA_NOT_READY` |
| `MTF_ROLES_UNSET` | 14 | genuine intraday unavailable; 1D/1W `POLICY_UNSET` | 4H unavailable; 1D/1W `POLICY_UNSET` | 1D/1W `POLICY_UNSET`; 1M unavailable |
| `VALUATION_PRICE_CONTEXT` | 29 | 1D `CONTEXT` only | 1D `CONTEXT` only | 1D `CONTEXT` only; financial evidence carries valuation meaning |
| `UPSTREAM_SYNTHESIS` | 31,32,34,45 | all intervals `NOT_USED` | all intervals `NOT_USED` | all intervals `NOT_USED` |
| `NAMED_VWAP_UNAVAILABLE` | 35 | 15m–1D `DATA_NOT_READY` | 15m–1D `DATA_NOT_READY` | all intervals `NOT_USED` |
| `DAILY_EXECUTION_CONTEXT` | 37,38,40–44,46 | intraday/4H `DATA_NOT_READY`; 1D `CONTEXT` | 1D `PRIMARY`; 1W `CONTEXT` | 1D/1W `CONTEXT`; 1M `DATA_NOT_READY` |
| `CROWD_PRICE_CONTEXT` | 55–56 | 1D `CONTEXT` | 1D `CONTEXT` | 1D `CONTEXT` |
| `EVENT_REACTION_UNAVAILABLE` | 57 | 15m–1D `DATA_NOT_READY` | 1D `DATA_NOT_READY` | 1D `CONTEXT` only |
| `CONTRARIAN_MTF_UNAVAILABLE` | 59–61 | intraday/4H `DATA_NOT_READY`; 1D/1W `POLICY_UNSET` | 4H unavailable; 1D/1W `POLICY_UNSET` | all intervals `NOT_USED` |

`PRIMARY` in this table is an intended observation role over already-existing
rule inputs; it does not select a strategy or make a horizon active.  No profile
uses the `EXECUTION` role.  A future MTF policy must specify what the currently
`POLICY_UNSET` cells mean rather than silently deciding them through the
adapter.

## G. Fundamental, governance, and material-risk check contract

For any future actionable setup, the downstream-compatible invariant is:

```text
FUNDAMENTAL_CHECK_REQUIRED = TRUE
```

This is a check contract, not an accidental universal all-fields hard gate.

| Horizon | Mandatory review boundary | Applicable canonical Rules | Not implied |
| --- | --- | --- | --- |
| `SHORT_TERM` | Material legal/governance, balance-sheet, and event red flags must be assessed where relevant. | 19, 23, 31, 46 are `APPLICABLE`; 15–18,20–22,24–30 are context unless a separately governed setup policy elevates them. | Every missing financial field blocks every short-term descriptive diagnostic. |
| `POSITIONAL` | Deeper operating, earnings, margin, debt, cash-flow, ownership, business-state, and risk review. | 15–30 and 31 are applicable; 33 is investment context. | A new score, a universal threshold, or an automatic gate. |
| `LONG_TERM` | Multi-period business quality, growth, cash flow, capital structure, governance, ownership, valuation, and investment-thesis review. | 15–30, 31, 33 and 46 are applicable; technical rules remain context unless separately approved. | A fair-value formula, forecast, target, or automatic long-term qualification. |

Existing hard Execution Gates retain their own explicit prerequisites.  This
candidate neither adds a gate nor promotes a diagnostic's relevance to a hard
block.  Rule 6 peer absence, Rule 35 named-VWAP absence, Rule 57 event-session
absence, or a Monthly/intraday gap therefore remains a rule-/strategy-specific
readiness fact, not a global fundamental bypass or universal rejection.

## H. Horizon disagreement, setup compatibility, and downstream consumers

Horizon outputs may legitimately disagree.  The candidate permits
`HORIZON_CONSISTENT`, `HORIZON_DIVERGENT`, and `HORIZON_CONFLICTED` only as
future descriptive aggregation vocabulary; it creates no aggregator and does
not average the three horizon states into a false consensus.  A divergence is
not an order, a negative result, or a portfolio instruction.

| Existing/future setup type | Candidate horizon compatibility | Current truth |
| --- | --- | --- |
| `PRE_BREAKOUT` | `POSITIONAL` context is the only existing documented discovery association. | It is a setup/discovery strategy, not a fourth horizon. Existing Pre-Breakout thresholds, policy selection and governance remain unchanged. |
| `CATALYST_NEWS_DRIVEN` | `SHORT_TERM` may be relevant; `POSITIONAL` is context only until exact event/freshness policy supports it. | Rule 57 event evidence is separately partial; no catalyst evaluator is added. |
| `LONG_TERM_BIG_SETUP` | normally `LONG_TERM` as a user-facing strategy label. | The name does not replace rule-level applicability; full quality/fundamental review remains central and no multibagger guarantee is implied. |

The stable canonical IDs in this candidate can later be consumed by a
horizon-aware, sleeve-aware, user-risk-aware Rotation policy and by a future
Setup/Trades projection.  Neither consumer exists here.  Rotation, catalyst,
positional, multibagger-candidate, and long-term-compounder sleeves must not
infer a user-specific risk policy, action, or portfolio change from this
candidate.

## I. Current evidence readiness and denominators

Each denominator below has a distinct retained meaning.  Equal numeric values
are not proof that populations are interchangeable.

| Population / denominator | Exact meaning | Count / evidence state |
| --- | --- | --- |
| Current selected security universe | latest persisted technical selection used by the preceding peer audit | 2,553 |
| Certified current-descriptive technical inputs | instruments examined by the retained UDiFF Daily/Weekly technical-readiness audit | 2,538 |
| Difference | selected securities not represented in that certified input audit | 15; never silently dropped or added |
| Earlier taxonomy source-audit population | frozen external classification source-audit population | 2,538; same numeral, different evidence purpose |
| Rule 4 | current-descriptive technical input audit | 1,940 ready / 499 Weekly partial / 99 Daily not ready |
| Rule 5 | current-descriptive technical input audit | 2,007 ready / 531 Weekly not ready |
| Rule 14 | current-descriptive technical input audit | 2,007 genuine D/W ready / 531 Weekly partial; no fake MTF |
| Direct Daily technical gate families | current-descriptive technical input audit | 2,538 ready for 7–9,11–13,29,36–46,50–54,58; readiness only |
| Rule 10 | current-descriptive technical input audit | 2,439 ready / 99 Daily not ready |
| Rule 35 | current-descriptive technical input audit | 2,538 not ready: `NAMED_VWAP_SEMANTICS_UNAVAILABLE` |
| Rule 57 | current-descriptive technical input audit | 2,538 partial: `EVENT_EVIDENCE_NOT_READY` |
| Sector mappings/OHLC | exact current peer-policy receipt | 601 mappings; 354 usable sector contexts; 247 `FULL_OHLC_CONTRACT_NOT_SATISFIED` |
| Authoritative peer cohorts | exact current peer-policy receipt | 0; Rule 6 remains `APPLICABLE / PARTIAL` |

### Current-descriptive versus strict historical PIT

`CURRENT_DESCRIPTIVE` Daily/Weekly evidence can be assessed only with its
retained certified lineage and as-of guard.  It is not historical
availability proof.  The UDiFF source archive does not prove original HSI
availability at every historical decision time, and current taxonomy labels
have no effective/known-at peer history.  Therefore:

```text
STRICT_HISTORICAL_PIT = NOT_READY
STRICT_HISTORICAL_PIT_PEER_READINESS = NOT_READY
```

No current horizon classification, sector label, or context role may be
back-projected into historical evaluation.

## J. Explicit unresolved parameters and activation boundary

The following remain intentionally unresolved:

```text
exact Short-Term / Positional / Long-Term duration boundaries
minimum required intraday timeframe and primary-role choice
4H NSE session composition and completed-bar contract
Monthly-history sufficiency and production storage/lineage
minimum evidence-count requirements beyond existing rule gates
cross-timeframe conflict-resolution semantics
rule-specific horizon weights
Rule 14 Daily-versus-Weekly role priority
Rule 6 peer membership, denominator, minimum cohort size, and comparison math
named session VWAP/value-area semantics
event-time / post-event completed-session semantics for Rule 57
future execution-refinement policy
```

The candidate is therefore **not active**.  It cannot silently convert a
`POLICY_UNSET` or `DATA_NOT_READY` cell into `PRIMARY`, `CONFIRMING`, or an
actionable setup.

## K. Validation and next boundary

Validation must check the candidate JSON against `diagnostic-registry-v1`,
expand all 183 applicability rows and all 882 technical role cells, reject
duplicate/unknown Rule IDs, reject a fourth horizon, verify the canonical
fingerprint, and preserve Rule 14 duplicate-timeframe protection and Rule 6's
partial peer state.  It must not run a provider, write SQLite, or rerun a
full-universe acquisition.

The next dominant internal boundary is
`PROSPECTIVE_DHAN_LIVE_BAR_FOUNDATION_V1`: Short-Term cannot acquire genuine
intraday primary evidence until a prospective, completed, exchange-session
aligned bar path is specified.  If that work first exposes a necessary role
contract, the only permissible precursor is a bounded
`MULTI_TIMEFRAME_TECHNICAL_ORCHESTRATOR_POLICY_V1` design slice.  Neither path
reopens peer/taxonomy archaeology.
