# Technical Diagnostic Timeframe & Data Readiness V1

**Status: `TECHNICAL_DIAGNOSTIC_TIMEFRAME_DATA_READINESS = ACTIVE / ONE_CANONICAL_61_DIAGNOSTIC_REGISTRY = TRUE / SEPARATE_TECHNICAL_BRAIN = FALSE / HYBRID_TECHNICAL_ARCHITECTURE = FROZEN / EXTERNAL_SCREENER_AUTHORITY = DISCOVERY_ONLY / HORIZON_SPECIFIC_TECHNICAL_POLICY = NOT_ACTIVE / MULTI_TIMEFRAME_TECHNICAL_ORCHESTRATOR = NOT_ACTIVE`.**

## Purpose and hard boundary

This is a read-only architecture and evidence audit of the existing canonical
61-diagnostic implementation, the provider-neutral historical-bar contracts,
and the production SQLite store at `data/nse_stock_manager.db`.  It is not a
new diagnostic registry, a technical score, a horizon policy, a resampling
engine, a provider integration, a Watch materialisation, an API/UI change, or
an execution path.

The canonical 61 registry (`diagnostic-registry-v1`) remains the only
production diagnostic registry.  Its technical rules remain components of the
same evidence graph as fundamentals, governance, research, risk and thesis
rules.  A technical result is evidence, not a BUY/SELL/ROTATE instruction;
Six Gates remain evidence-only and have no broker, order or portfolio-write
authority.

`app.signals` is not this architecture's contract.  No second technical Brain,
parallel score, duplicate Watch lifecycle or synthetic stored evidence is
authorised by this audit.

## Audit method and evidence cutoff

The audit inspected the current code and performed read-only SQLite queries on
the production database at the repository workspace.  It made no provider
request and wrote no data.  Counts below are retained-evidence facts, not a
claim that a provider could supply the missing interval today.

At this audit the historical store contains **1,545,139** canonical OHLCV bars
for **2,561** instruments, all with `timeframe = 1D`, from
`2023-08-21T18:30:00+00:00` through `2026-08-31T18:30:00+00:00`.  Its latest
date is consequently stale relative to the audit date, `2026-09-05`.  The
store retains **11** provider-conflict artifacts.  Immutable provider lineage
is valuable, but it does not make an unknown adjustment basis or a bar-close
fact known.

## Current technical dependency classification

The following labels describe actual evaluator input dependency, not an
investment recommendation:

- `NON_TECHNICAL` — no OHLC/volume/benchmark technical input is required.
- `TECHNICAL_PRIMARY` — a direct market-data evaluator consumes canonical
  price/volume/benchmark observations.
- `TECHNICAL_DEPENDENT` — a higher-order evaluator depends on one or more
  technical outputs but does not independently calculate a new indicator.
- `TECHNICAL_EXECUTION_RISK` — direct price-structure evidence for a
  descriptive entry/risk structure; never execution authority.
- `HYBRID_WITH_TECHNICAL_INPUT` — technical market observations are combined
  with another evidence domain.

| Rules | Canonical rule(s) | Classification | Actual current dependency |
| --- | --- | --- | --- |
| 1 | Market Regime Classification | `TECHNICAL_PRIMARY` | Benchmark OHLC observations. |
| 2–3 | Sector Index Health; Sector Rotation | `TECHNICAL_PRIMARY` | Sector and benchmark OHLC observations. |
| 4–14 | Primary Trend through Multi-Timeframe Alignment | `TECHNICAL_PRIMARY` | Instrument OHLC/volume; Rules 6 and 14 also claim benchmark/sector/timeframe inputs. |
| 15–28 | Moat through Management Execution | `NON_TECHNICAL` | Financial, ownership, governance and research/filing evidence. |
| 29 | Valuation Multiples | `HYBRID_WITH_TECHNICAL_INPUT` | Market-price observation plus financial facts; it is not an indicator calculation. |
| 30 | Fundamental Catalysts | `NON_TECHNICAL` | Research evidence. |
| 31 | Comprehensive Risk Engine | `TECHNICAL_DEPENDENT` | Higher-order inputs include Rules 1, 2 and 46 alongside non-technical risk evidence. |
| 32 | Trading Thesis | `TECHNICAL_DEPENDENT` | Higher-order inputs include Rules 43, 45 and 46 and supporting technical structure. |
| 33 | Investment Thesis | `NON_TECHNICAL` | Its current synthesis consumes fundamental/risk evidence, not a technical input. |
| 34 | Bull/Base/Bear Scenarios | `TECHNICAL_DEPENDENT` | Higher-order synthesis of Rules 31–33. |
| 35–39 | VWAP through RSI/ADX/ATR | `TECHNICAL_PRIMARY` | Instrument OHLCV. |
| 40–46 | Entry levels through Thesis Invalidation | `TECHNICAL_EXECUTION_RISK` | Instrument price structure and dependent Rule 40/43/44 outputs; descriptive only. |
| 47–49 | Retail Sentiment; Crowd Positioning; Crowd Confidence | `NON_TECHNICAL` | Crowd/research evidence. |
| 50–54 | Accumulation/Distribution through Bear Trap | `TECHNICAL_PRIMARY` | Instrument OHLCV proxies; not order-book or institutional observations. |
| 55–56 | Crowd Trap Probability; Price/Crowd Divergence | `TECHNICAL_DEPENDENT` | Crowd evidence plus market observations. |
| 57 | Post-News Price Reaction | `HYBRID_WITH_TECHNICAL_INPUT` | Crowd/news evidence plus market observations; no approved event-session return policy. |
| 58 | Volume Climax | `TECHNICAL_PRIMARY` | Instrument OHLCV. |
| 59–61 | Contrarian Ichimoku; Quality; Verdict | `TECHNICAL_DEPENDENT` | Rules 12–14, 47, 49, 55 and 56. |

## Actual rule dependency map

All direct technical evaluators are called by
`app.universe_analysis.service.Canonical61DiagnosticRunner._evaluate` and use
`app.diagnostics.evaluators.DeterministicDiagnosticEvaluators`, which in turn
uses `app.analysis.*`.  A `price_bar_series` accepts generic validated OHLC
observations in an as-of snapshot and rejects future market/retrieval
timestamps.  It carries **no** typed bar timeframe, session-close certificate,
known-at timestamp, corporate-action continuity or resample provenance.

`D` below means the current assembled daily-style snapshot.  It is not proof
that a requested interval is a native, completed interval.

| Rule | Actual evaluator / direct inputs | OHLC / volume / benchmark / sector dependency and current lookback | Current timeframe and session assumption | Binding and readiness |
| --- | --- | --- | --- | --- |
| 1 | `market_regime` | Benchmark price bars; `MarketRegimeRules(2,3,2,3,...)`. | `D`; generic as-of bars, no completed-session proof. | Stored daily benchmark exists; `PARTIAL` because freshness/known-at and adjustment semantics are not unified. |
| 2–3 | `sector_health`, `sector_rotation` | Sector and benchmark closes; return lookback 3. | `D`; if sector identity is absent runner falls back to the instrument, which is not sector-index proof. | Eight stored sector indices; `PARTIAL`, no PIT historical sector-membership/close completeness contract. |
| 4 | `primary_trend(weekly, daily)` | Fast/slow SMA 3/5 and pivot window 1. | **The runner passes `s, s`: the same snapshot is labelled weekly and daily.** | `PARTIAL`; no independent weekly bar set is assembled. |
| 5 | `weinstein` | Price bars; MA period 3, slope lookback 2. | `D` generic bars. | `PARTIAL`; daily series exists but basis/completeness is unresolved. |
| 6 | `relative_strength` | Stock, `NIFTY_50`, sector, peers; lookback 3; peers are currently `()`. | `D`. | `PARTIAL`; NIFTY 50/sector daily stores exist, but no peer set and no PIT sector mapping parity. |
| 7–9 | `smart_money`, `pools`, `wyckoff` | Instrument OHLCV; `LiquidityRules(.01,2,1.5,1.5)`. | `D`. | `PARTIAL`; price/volume proxy only, no depth/order-flow or institutional ownership feed. |
| 10 | `market_structure` | Instrument OHLC; strict pivot window 1 on both sides. | `D`; pivot confirmation needs later bars, but no bar-known-at rule records when confirmation became eligible. | `PARTIAL`. |
| 11 | `volume_rvol` | Instrument volume; lookback 3, high/low ratios 1.5/0.5. | `D`. | `PARTIAL`; volume is stored but 11,279 rows are zero/null and turnover/trade-count coverage is narrow. |
| 12–13 | `ichimoku`, `chikou` | Instrument OHLC; tenkan 2, kijun 3, span-B 4, displacement 1. | `D`. | `PARTIAL`; no independently defined interval/session semantics. |
| 14 | `multi_timeframe_alignment` | Named daily/weekly inputs; Ichimoku 2/3/4/1. | **`{"daily": s, "weekly": s}`: one identical snapshot twice.  No 4H, 1H or 15m input is supplied.** | `NOT_READY` for true MTF. |
| 31 | `synthesis_risk` | Higher-order Rules 23,19,29,46,55,30,1,2. | Inherits those rule inputs. | `PARTIAL`; no new direct bar logic. |
| 32 | `synthesis_trading` | Requires 43,45,46; supports 4,6,10,37,38,41,45. | Inherits direct price-rule inputs. | `PARTIAL`; descriptive thesis only. |
| 34 | `synthesis_scenarios` | Higher-order Rules 31,32,33. | Inherits upstream availability. | `PARTIAL`. |
| 35–36 | `vwap`, `obv` | Instrument OHLCV; OBV lookback 3.  “Value area” is not a separate current computation. | `D`. | `PARTIAL`; no intraday session/value-area profile and volume basis is incomplete. |
| 37–38 | `base_pattern`, `pullback` | Instrument OHLC; `TradeRules(5,.35,.03,.02,2)`. | `D`. | `PARTIAL`; generic daily bars only. |
| 39 | `rsi`, `adx`, `atr` | RSI/ATR period 3 need 4 bars; ADX period 3 needs 6 bars; thresholds 70/30/20 and trend period 2. | `D`. | `PARTIAL`; storage has daily history but not an approved interval/adjustment policy. |
| 40–44 | Aggressive/confirmation/retest entry, stop, targets | Instrument OHLC; same `TradeRules`; outputs are descriptive levels. | `D`. | `PARTIAL`; no action or order capability. |
| 45 | `risk_reward` | Prior Rule 40 entry, 43 stop, 44 T1; minimum structural R:R 2. | Inherits `D` structure. | `PARTIAL`; invalid/missing upstream outputs fail closed. |
| 46 | `invalidation` | Instrument price structure and `TradeRules`. | `D`. | `PARTIAL`; cannot convert to automatic sale. |
| 50–54 | Accumulation/distribution, stops, events, bull/bear traps | Instrument OHLCV and `LiquidityRules`. | `D`. | `PARTIAL`; observable price/volume proxy, no order-book/stop-book evidence. |
| 55–56 | `trap_probability`, `divergence` | Crowd evidence plus instrument/market observations and `CrowdRules`. | Inherits `D` bars. | `PARTIAL`; requires crowd evidence, no new price calculation. |
| 57 | `post_news` | Crowd/news and market snapshot. | Inherits `D` bars. | `NOT_READY` for an event reaction: exact event timing and post-event completed sessions are not generally available. |
| 58 | `volume_climax` | Instrument OHLCV and `LiquidityRules`. | `D`. | `PARTIAL`; same volume-basis limit as Rule 11. |
| 59 | `ichimoku_confluence` | Prior Rules 47,12,13,14. | Inherits false weekly/MTF limitation. | `NOT_READY` for genuine MTF confluence. |
| 60–61 | `contrarian_quality`, `contrarian_verdict` | Prior Rules 55,56,59,49. | Inherits technical/crowd availability. | `PARTIAL`/`NOT_READY` whenever Rule 59 is unavailable; never trade authority. |

Rules not shown in the map have no direct technical dependency under the
current input-requirements contract.  Their canonical missing-data behaviour
remains `INSUFFICIENT_DATA`/`UNVERIFIED`, never a fabricated neutral or pass.

## Timeframe and storage inventory

| Interval / source | Repository contract | Production stored evidence | Provider/code reality | Readiness category |
| --- | --- | --- | --- | --- |
| 1m | `Timeframe.ONE_MINUTE` | None. | Global Datafeeds adapter maps it, but no configured production transport, mapping coverage or retained bars. | `CONTRACT_ONLY` |
| 5m | `Timeframe.FIVE_MINUTES` | None. | Same Global Datafeeds adapter limitation. | `CONTRACT_ONLY` |
| 15m | `Timeframe.FIFTEEN_MINUTES` | None. | Same Global Datafeeds adapter limitation.  Dhan Live is LTP packets, not canonical closed candles. | `CONTRACT_ONLY` |
| 30m | `Timeframe.THIRTY_MINUTES` | None. | Same Global Datafeeds adapter limitation. | `CONTRACT_ONLY` |
| 1H | `Timeframe.SIXTY_MINUTES` | None. | Same Global Datafeeds adapter limitation. | `CONTRACT_ONLY` |
| 4H | No `Timeframe` member. | None. | No provider adapter mapping, session composition, resampler or close policy. | `UNAVAILABLE` |
| 1D | `Timeframe.DAILY` | 1,545,139 bars / 2,561 instruments. | Upstox is production-bound daily only; official NSE bhavcopy is daily; all retained bars are daily. | `CANONICAL_STORED_NATIVE` |
| 1W | `Timeframe.WEEKLY` | Certified UDiFF Daily-derived Weekly artifacts from 2024-07-08 onward. | Current-descriptive only; no native provider binding, strict historical PIT, or diagnostic assembly. | `CANONICAL_DERIVED_CURRENT_DESCRIPTIVE` |
| 1M | No `Timeframe` member. | None. | No provider map, resampler or stored series. | `UNAVAILABLE` |
| Dhan Live LTP | Separate `LiveMarketState`. | No historical OHLCV persistence. | Bounded in-memory current tick state only; it has no candle builder. | `LIVE_ONLY` |
| Daily→weekly/monthly or intraday→4H | No resampling contract. | None. | No interval boundaries, partial-bar rule, session calendar join, aggregation lineage or adjustment policy. | `UNAVAILABLE` |

`GlobalDatafeedsHistoricalProvider.capabilities()` declares several interval
forms in code, but it requires configuration, exact mappings and an injected
transport.  It is not a production proof.  It is therefore deliberately not
classified as `PROVIDER_NATIVE_AVAILABLE`.

### Explicit 4H conclusion

`4H_NSE_TECHNICAL_SEMANTICS = UNRESOLVED`.

The repository has no 4H timeframe identity and no rule for composing NSE cash
sessions into 4H bars.  Normal-market timing is not itself a 4H composition
rule: a 09:15–15:30 regular continuous session cannot be silently treated as
an even sequence of four-hour bars.  There is also no exact special-session,
holiday, early-close, partial-bar, known-at, adjustment or resample-lineage
rule for that interval.  A 4H value must remain unavailable until a separately
approved canonical contract resolves all of those facts.

## Production coverage and quality reality

### Equity, broad-market and sector coverage

| Population / evidence | Retained daily coverage | Meaning and limitation |
| --- | ---: | --- |
| NSE equity instruments | 2,551 IDs; 2,134 have at least 252 daily bars; 2,189 have at least 200 | Against the last frozen 2,553-eligible discovery snapshot, nominal ID coverage is **99.92%** (2,551/2,553).  Exact PIT membership is not re-proven by this storage query. |
| Latest daily equity dates | 73 IDs reach 2026-08-30; 2,471 reach 2026-08-27 | Broad retained history is not current-daily readiness at this audit. |
| NIFTY 50 | 746 daily bars, 2023-08-27 through 2026-08-30 | Stored benchmark input for Rule 6; all volume values are zero/unavailable for this index series. |
| NIFTY 500 | 1,673 daily bars, 2023-08-21 through 2026-08-30 | Stored broad index evidence; 941 rows have zero/null volume. |
| Sector indices | Eight daily sector-index IDs | Chemicals has 399 bars; Consumer Durables, Financial Services and Healthcare have 747; FMCG, Media, Metals and Realty have 1,493.  They are daily-only and do not prove PIT sector-membership parity. |
| Candidate/deep-analysis intraday | No canonical 1m–1H/4H closed bars | Candidate/on-demand intraday remains `NOT_READY`; an LTP packet is not an OHLCV bar. |

### Bar completeness, PIT and corporate-action facts

| Requirement | Current truth | Readiness consequence |
| --- | --- | --- |
| Input PIT cutoff | `price_bar_series` excludes market/retrieval timestamps after snapshot as-of. | Useful generic PIT input guard, but not a per-bar known-at/close certificate. |
| Closed/partial bar state | `CanonicalOHLCVBar` has start/end timestamps but no closed/partial state or canonical bar-known-at field. | `PARTIAL_BAR_KNOWNNESS = NOT_READY`. |
| Session calendar | A bounded canonical NSE session/event-time contract has partial first-party coverage; ordinary historical timing is intentionally not backfilled. | It cannot certify every stored daily/intraday bar close or resample boundary. |
| Native/derived provenance | Historical rows carry provider provenance and provider-version conflict artifacts. | No derived-bar parent lineage exists because no resampling path exists. |
| Adjustment basis | 1,518,652 bars are `UNKNOWN`; 26,487 are `RAW`; none are represented as universally adjusted. | Technical continuity across corporate actions is `PARTIAL`, not assumed. |
| Corporate action linkage | `portfolio_corporate_actions` has zero rows and the market-data series has no canonical corporate-action continuity policy. | Do not infer split/dividend-adjusted comparability. |
| Volume / liquidity | Volume is retained, but 11,279 rows are zero/null.  Turnover/trade count is retained only for the 48 official-NSE rows. | RVOL/VWAP/OBV and liquidity proxy rules may fail closed; no depth/order-book conclusion is permitted. |
| Benchmark/sector RS | NIFTY 50/500 and eight sector daily series exist. | Daily relative comparisons are partial; intraday/higher-timeframe RS, PIT sector mapping and peer cohort parity are unavailable. |
| Freshness | Latest retained bars end 2026-08-31 and most equities end 2026-08-27. | A consumer must apply a separately approved freshness threshold; this audit does not select one. |

## Rule × timeframe feasibility matrix

This is a data-feasibility matrix, not an applicability or horizon policy.
`P` means daily evidence is `PARTIAL`; `NR` means `NOT_READY`; `—` means no
direct market interval.  A native bar would still need a completed-bar,
known-at, adjustment and freshness contract before use.

| ID | Rule | Class | 15m | 30m | 1H | 4H | 1D | 1W | 1M | Current evaluator / binding | Dominant blocker and next data action |
| ---: | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Market Regime | `TECHNICAL_PRIMARY` | NR | NR | NR | NR | P | NR | NR | Daily benchmark; `REAL_PARTIAL` | Certified benchmark bars plus known-at/adjustment contract. |
| 2 | Sector Index Health | `TECHNICAL_PRIMARY` | NR | NR | NR | NR | P | NR | NR | Daily sector/benchmark; `REAL_PARTIAL` | PIT sector mapping and certified sector/benchmark bars. |
| 3 | Sector Rotation | `TECHNICAL_PRIMARY` | NR | NR | NR | NR | P | NR | NR | Daily sector/benchmark; `REAL_PARTIAL` | Same as Rule 2. |
| 4 | Primary Trend | `TECHNICAL_PRIMARY` | NR | NR | NR | NR | P | NR | NR | Same `D` snapshot labelled daily/weekly; `DATA_BLOCKED` for genuine weekly/daily | Independent weekly series and timeframe-aware assembly. |
| 5 | Weinstein Stage | `TECHNICAL_PRIMARY` | NR | NR | NR | NR | P | NR | NR | Daily price series; `REAL_PARTIAL` | Approved interval/adjustment/known-at basis. |
| 6 | Relative Strength | `TECHNICAL_PRIMARY` | NR | NR | NR | NR | P | NR | NR | Daily stock/NIFTY 50/sector; no peers; `REAL_PARTIAL` | PIT peer/sector cohort and aligned benchmarks. |
| 7 | Smart-Money Proxies | `TECHNICAL_PRIMARY` | NR | NR | NR | NR | P | NR | NR | Daily OHLCV proxy; `HYBRID_PROXY` | Certified bars; depth/order flow unavailable. |
| 8 | Liquidity Pools | `TECHNICAL_PRIMARY` | NR | NR | NR | NR | P | NR | NR | Daily OHLCV proxy; `HYBRID_PROXY` | Same as Rule 7. |
| 9 | Wyckoff Phase | `TECHNICAL_PRIMARY` | NR | NR | NR | NR | P | NR | NR | Daily OHLCV proxy; `HYBRID_PROXY` | Same as Rule 7. |
| 10 | Market Structure | `TECHNICAL_PRIMARY` | NR | NR | NR | NR | P | NR | NR | Daily generic pivots; `REAL_PARTIAL` | Pivot-confirmation known-at and closed-bar rule. |
| 11 | RVOL | `TECHNICAL_PRIMARY` | NR | NR | NR | NR | P | NR | NR | Daily volume lookback 3; `REAL_PARTIAL` | Zero/missing volume and comparable unit/basis contract. |
| 12 | Ichimoku | `TECHNICAL_PRIMARY` | NR | NR | NR | NR | P | NR | NR | Daily generic OHLC; `REAL_PARTIAL` | Independent interval series. |
| 13 | Chikou | `TECHNICAL_PRIMARY` | NR | NR | NR | NR | P | NR | NR | Daily generic OHLC; `REAL_PARTIAL` | Independent interval series. |
| 14 | Multi-Timeframe Alignment | `TECHNICAL_PRIMARY` | NR | NR | NR | NR | NR | NR | NR | Same snapshot twice; `DATA_BLOCKED` | Canonical timeframe/completeness contract then real interval data. |
| 29 | Valuation Multiples | `HYBRID_WITH_TECHNICAL_INPUT` | — | — | — | — | P | — | — | Market price + financial facts; `REAL_PARTIAL` | Financial PIT parity and explicit price basis. |
| 31 | Comprehensive Risk | `TECHNICAL_DEPENDENT` | NR | NR | NR | NR | P | NR | NR | Synthesises 1/2/46; `HYBRID_PROXY` | Exact upstream availability. |
| 32 | Trading Thesis | `TECHNICAL_DEPENDENT` | NR | NR | NR | NR | P | NR | NR | Synthesises 43/45/46; `HYBRID_PROXY` | Horizon policy plus valid descriptive structure. |
| 34 | Bull/Base/Bear Scenarios | `TECHNICAL_DEPENDENT` | NR | NR | NR | NR | P | NR | NR | Synthesises 31/32/33; `HYBRID_PROXY` | Upstream data; no forecast authority. |
| 35 | VWAP | `TECHNICAL_PRIMARY` | NR | NR | NR | NR | P | NR | NR | Daily OHLCV; `REAL_PARTIAL` | Session-volume contract; value area remains unavailable. |
| 36 | OBV | `TECHNICAL_PRIMARY` | NR | NR | NR | NR | P | NR | NR | Daily volume lookback 3; `REAL_PARTIAL` | Volume quality/adjustment contract. |
| 37 | Base Pattern | `TECHNICAL_PRIMARY` | NR | NR | NR | NR | P | NR | NR | Daily price structure; `REAL_PARTIAL` | Timeframe policy and closed-bar/pivot semantics. |
| 38 | Pullback Quality | `TECHNICAL_PRIMARY` | NR | NR | NR | NR | P | NR | NR | Daily price structure; `REAL_PARTIAL` | Same as Rule 37. |
| 39 | RSI / ADX / ATR | `TECHNICAL_PRIMARY` | NR | NR | NR | NR | P | NR | NR | Daily generic indicators; `REAL_PARTIAL` | Interval bar sufficiency and closed-bar contract. |
| 40 | Aggressive Entry | `TECHNICAL_EXECUTION_RISK` | NR | NR | NR | NR | P | NR | NR | Daily descriptive structure; `REAL_PARTIAL` | Approved horizon/setup policy; no execution activation. |
| 41 | Confirmation Entry | `TECHNICAL_EXECUTION_RISK` | NR | NR | NR | NR | P | NR | NR | Daily descriptive structure; `REAL_PARTIAL` | Same as Rule 40. |
| 42 | Retest Entry | `TECHNICAL_EXECUTION_RISK` | NR | NR | NR | NR | P | NR | NR | Daily descriptive structure; `REAL_PARTIAL` | Same as Rule 40. |
| 43 | Structural Stop | `TECHNICAL_EXECUTION_RISK` | NR | NR | NR | NR | P | NR | NR | Daily descriptive structure; `REAL_PARTIAL` | Horizon/corporate-action continuity policy. |
| 44 | Target Hierarchy | `TECHNICAL_EXECUTION_RISK` | NR | NR | NR | NR | P | NR | NR | Daily descriptive structure; `REAL_PARTIAL` | Horizon/setup policy; no target-price authority. |
| 45 | Risk/Reward | `TECHNICAL_EXECUTION_RISK` | NR | NR | NR | NR | P | NR | NR | Needs 40/43/44; `REAL_PARTIAL` | Valid upstream levels and horizon policy. |
| 46 | Thesis Invalidation | `TECHNICAL_EXECUTION_RISK` | NR | NR | NR | NR | P | NR | NR | Daily price structure; `REAL_PARTIAL` | Horizon/corporate-action continuity; never automatic sale. |
| 50 | Accumulation/Distribution Proxy | `TECHNICAL_PRIMARY` | NR | NR | NR | NR | P | NR | NR | Daily OHLCV; `HYBRID_PROXY` | Depth/order-flow unavailable; volume basis partial. |
| 51 | Stop-Cluster Proxy | `TECHNICAL_PRIMARY` | NR | NR | NR | NR | P | NR | NR | Daily OHLCV; `HYBRID_PROXY` | Actual stop-book unavailable. |
| 52 | Liquidity Event Proxy | `TECHNICAL_PRIMARY` | NR | NR | NR | NR | P | NR | NR | Daily OHLCV; `HYBRID_PROXY` | Intraday/depth data unavailable. |
| 53 | Bull-Trap Proxy | `TECHNICAL_PRIMARY` | NR | NR | NR | NR | P | NR | NR | Daily OHLCV; `HYBRID_PROXY` | Closed-bar/pivot/volume semantics. |
| 54 | Bear-Trap Proxy | `TECHNICAL_PRIMARY` | NR | NR | NR | NR | P | NR | NR | Daily OHLCV; `HYBRID_PROXY` | Closed-bar/pivot/volume semantics. |
| 55 | Crowd-Trap Probability | `TECHNICAL_DEPENDENT` | NR | NR | NR | NR | P | NR | NR | Crowd + daily market; `HYBRID_PROXY` | Crowd evidence and upstream price availability. |
| 56 | Price/Crowd Divergence | `TECHNICAL_DEPENDENT` | NR | NR | NR | NR | P | NR | NR | Crowd + daily market; `HYBRID_PROXY` | Crowd evidence and upstream price availability. |
| 57 | Post-News Reaction | `HYBRID_WITH_TECHNICAL_INPUT` | NR | NR | NR | NR | NR | NR | NR | News/crowd + market; `DATA_BLOCKED` | Exact event timing and completed post-event sessions. |
| 58 | Volume Climax Proxy | `TECHNICAL_PRIMARY` | NR | NR | NR | NR | P | NR | NR | Daily OHLCV; `HYBRID_PROXY` | Volume quality and close/known-at semantics. |
| 59 | Contrarian Ichimoku | `TECHNICAL_DEPENDENT` | NR | NR | NR | NR | NR | NR | NR | Needs 12/13/14 + crowd; `DATA_BLOCKED` | Genuine MTF inputs, not duplicated daily data. |
| 60 | Contrarian Quality | `TECHNICAL_DEPENDENT` | NR | NR | NR | NR | NR | NR | NR | Needs 55/56/59/49; `DATA_BLOCKED` | Rule 59 plus crowd evidence. |
| 61 | Contrarian Verdict | `TECHNICAL_DEPENDENT` | NR | NR | NR | NR | NR | NR | NR | Needs 60/49; `DATA_BLOCKED` | Rule 60 plus crowd confidence; no action authority. |

The generic indicator engine is technically timeframe-agnostic because it
accepts supplied bars, but its production assembly is daily-only.  Its actual
maximum current lookbacks are: SMA 5; Ichimoku span-B 4 plus displacement; ADX
6; base/entry structure 5; RVOL/OBV 3; and liquidity proxies 2–3.  These are
frozen implementation parameters, not recommended values for another interval.

## Broad ownership, on-demand verification and pilot design

| Capability | State | Compatible frozen ownership model |
| --- | --- | --- |
| Broad internal daily | `PARTIAL` | Retain canonical daily bars, subject to the future closed-bar/adjustment contract. |
| Broad internal weekly | `PARTIAL` | Certified UDiFF Daily-derived artifacts exist for eligible source-era subsets; no diagnostics are activated. |
| Broad internal monthly | `NOT_READY` | No stored/derived monthly series exists. |
| Broad intraday discovery | `NOT_READY` internally | Keep external-provider assistance as a future replaceable discovery layer only. |
| Candidate/holding/watchlist 15m–1H verification | `NOT_READY` | Desired on-demand model is compatible, but no production canonical intraday-bar path exists. |
| Candidate 4H verification | `NOT_READY` | Deferred until 4H semantics are explicitly approved. |

For a 25–30 user SenseEdge pilot, the least-risk architecture remains **C**:
external breadth discovery, then HSI on-demand canonical verification.  It is
not presently operational for intraday intervals and must degrade cleanly.

| Mode | Storage / compute | Auditability and recall | Provider resilience | Pilot judgement |
| --- | --- | --- | --- | --- |
| A. Full-universe intraday storage/calculation | Highest data, API and compute load; needs a complete session/resample/retention contract. | Strong only if every evidence receipt is retained; breadth non-alert proof requires complete provider receipts. | Highest provider/operations burden. | Not justified. |
| B. Rolling internal intraday cache | Bounded storage, but expiry limits reproducibility and recall without immutable receipts. | Partial; cache absence cannot prove no trigger. | Operationally lighter, not evidentially complete. | Not selected. |
| C. External breadth discovery + HSI on-demand deep verification | Lowest broad HSI load; future HSI stores/recomputes only inspected canonical evidence. | Alert is positive discovery evidence; non-alert remains `PER_SECURITY_NEGATIVE_EVALUATION_UNKNOWN`. | A screener outage degrades one funnel only. | **Frozen target / recommended.** |

The smallest practical pilot is daily canonical evidence first;
external-assisted intraday radar only after a separately approved adapter; and
candidate/holding verification only after a closed-intraday-bar contract.  No
provider outage may become a Brain-wide dependency.

## Final readiness dimensions

| Dimension | State | Exact reason |
| --- | --- | --- |
| `INTRADAY_BROAD_DISCOVERY` | `NOT_READY` | No external adapter is authorised or integrated. |
| `INTRADAY_ON_DEMAND_VERIFICATION` | `NOT_READY` | No production canonical 15m/30m/1H/4H closed-bar path. |
| `DAILY_OHLCV` | `PARTIAL` | 1.545M retained bars; stale coverage, unknown adjustments and incomplete close/known-at semantics remain. |
| `WEEKLY_OHLCV` | `PARTIAL` | Certified UDiFF source-era Daily-derived Weekly artifacts exist, current-descriptive only. |
| `MONTHLY_OHLCV` | `NOT_READY` | No stored/derived monthly bars. |
| `PRICE_ADJUSTMENT` | `PARTIAL` | 1,518,652 rows are `UNKNOWN`; remaining rows are RAW. |
| `CORPORATE_ACTION_INTEGRITY` | `NOT_READY` | No market-series continuity policy links actions to technical history. |
| `VOLUME` | `PARTIAL` | Daily volume exists, but zero/null rows and narrow turnover/trade-count coverage remain. |
| `BENCHMARK` | `PARTIAL` | NIFTY 50/500 daily data exists; no interval completeness/return-basis/intraday contract. |
| `SECTOR` | `PARTIAL` | Eight daily sector indices; no PIT membership/breadth/intraday parity. |
| `SESSION_ALIGNMENT` | `PARTIAL` | Bounded calendar/phase facts, no general ordinary-session historical timing rule. |
| `PARTIAL_BAR_KNOWNNESS` | `NOT_READY` | Canonical OHLCV has no closed/in-progress or bar-known-at field. |
| `4H_SEMANTICS` | `UNRESOLVED` | No identity, session composition, provider mapping or resampling rule. |
| `TECHNICAL_EVALUATOR_REAL_DATA_BINDING` | `PARTIAL` | Daily generic-bar evaluators can consume stored snapshots; true MTF and event reaction are blocked. |
| `WHOLE_UNIVERSE_TECHNICAL_COVERAGE` | `PARTIAL` | 99.92% nominal daily equity IDs against the last frozen universe; not a current PIT-ready assertion. |
| `HYBRID_ARCHITECTURE_READINESS` | `PARTIAL` | Boundary is coherent, but the future on-demand intraday verification capability is absent. |

## External technical discovery boundary

An external screener can, at most, later emit a versioned
`TECHNICAL_DISCOVERY_EVENT` with source identity, retrieval/observation time,
claimed timeframe, exact canonical-instrument mapping status, raw criterion
reference, and an explicit evidence-confidence/reason state.  It is a
discovery cue only.

It must never be treated as a canonical diagnostic result, evidence override,
or substitute for provider-neutral recomputation from canonical stored bars.
An absent external alert is **not** negative technical evidence.  A mismapped,
late, stale, unsupported-timeframe or unverified external observation remains
unavailable; it cannot silently create PASS/FAIL, a score, a setup, a Six-Gates
outcome, or execution authority.  No external-screener integration is
authorised by this audit.

## Required test and implementation boundary before any activation

The current generic technical unit tests prove formula behaviour on supplied
snapshots; they do not prove production timeframe provenance.  Before a
horizon-specific evaluator or any external discovery adapter is activated, the
following tests are required:

1. **Benchmark input test:** exact `NIFTY_50`/`NIFTY_500` and sector identity,
   matching as-of, source/adjustment basis, and fail-closed absence/conflict.
2. **4H NSE session test:** normal, holiday and special-session boundaries;
   no partial or synthetic final bar; exact parent-bar lineage.
3. **Hybrid technical compare test:** a stored canonical result and a
   recomputed result from the same supplied bars agree; mismatch preserves the
   external observation as discovery-only and does not overwrite canonical
   evidence.
4. **Known-at and adjustment test:** a bar/revision unavailable at as-of,
   unknown adjustment basis across a corporate action, or unclosed bar cannot
   enter a time-sensitive rule.
5. **No-side-effect test:** a technical result cannot create a score, order,
   broker call, portfolio mutation, API/UI activation or persistence write.

## Recommendation

The evidence is **not** sufficient to begin
`HORIZON_SPECIFIC_TECHNICAL_DIAGNOSTIC_POLICY_V1`: the names weekly, 4H, 1H and
15m do not yet bind to independently completed canonical bar sets, and the
current Rule 14 input is a duplicated daily snapshot.

The single smallest next repair is:

`CANONICAL_TECHNICAL_BAR_TIMEFRAME_AND_COMPLETENESS_CONTRACT_V1`

It should be a bounded, provider-neutral contract and focused tests only.  It
must define timeframe vocabulary (including whether 4H/1M are supported), NSE
session-aligned interval boundaries, closed-versus-partial state, `known_at`,
source/adjustment/resample lineage, benchmark/sector identity parity and
fail-closed freshness.  It must not acquire data, enable a provider, resample
production bars, alter canonical Rule 14, create a technical Brain, or activate
a strategy.  After that contract is approved and an actual interval has
canonical evidence, a horizon-specific policy can be proposed without inventing
data.

## Final readiness verdict

| Area | Verdict |
| --- | --- |
| Existing daily technical inputs | `PARTIAL`: stored daily OHLCV/benchmark/sector evidence exists, but freshness, bar completeness and adjustment continuity are not universally proven. |
| Genuine weekly technical analysis | `NOT_ACTIVE`: certified current-descriptive Weekly bars exist, but no diagnostic binding or horizon policy is activated. |
| Genuine monthly technical analysis | `NOT_READY`: no stored/derived canonical monthly series. |
| Genuine 15m / 30m / 1H / 4H technical analysis | `NOT_READY`: no retained canonical closed bars; 4H semantics are unresolved. |
| Multi-timeframe Rules 4 and 14 as labelled | `NOT_READY`: same snapshot is passed under daily and weekly labels. |
| Technical discovery from an external screener | `FUTURE_DISCOVERY_ONLY`: no provider integration or canonical authority. |
| Canonical 61 registry and evidence-only boundary | `UNCHANGED / FROZEN`: this audit creates no second registry or action path. |

`TECHNICAL_DIAGNOSTIC_TIMEFRAME_DATA_READINESS_V1 = COMPLETED_READ_ONLY_AUDIT`
