# NSE Stock Manager v2.1 — Master Specification

## 1. Purpose and boundaries

NSE Stock Manager is a private AI-assisted system for NSE/BSE equity research, swing/positional paper trading, portfolio review, and capital rotation. Its core objective is to continuously determine whether invested capital is allocated to the best available risk-adjusted opportunities in the Indian equity market.

The intended operating loop is:

`data → analyze → score → filter → signal → paper trade → measure → learn → validate → improve`

The product must not promise guaranteed returns, a fixed win rate, or 99.99% accuracy. It is a decision-support and validation system, not a claim of investment certainty.

### Explicitly out of scope for the initial build

- Market-data integrations
- Assumed or invented provider APIs
- Live brokerage integration
- Autonomous order execution
- Automatic production-strategy changes

Initial implementations use mock/test data behind provider-independent interfaces.

## 2. Architectural principles

### 2.1 Evidence and provenance

Information has a strict hierarchy:

1. **Fact** — a directly observed, source-supported assertion.
2. **Data** — raw or normalized observations supporting facts.
3. **Interpretation** — an analytical reading of the data.
4. **Inference** — a reasoned conclusion, signal, or recommendation.

The system must never fabricate prices, volume, financial results, order-book data, institutional holdings, delivery data, corporate actions, news, or technical indicators. Every material observation must retain:

- source and source identifier where available;
- retrieval timestamp and market/event timestamp;
- freshness;
- data-quality assessment;
- validation status.

Derived values must additionally identify their inputs, calculation/version, and derivation time so conclusions remain reproducible.

### 2.2 Provider independence

Market-data sources are isolated behind stable domain interfaces. The rest of the system consumes normalized, timestamped observations rather than provider-specific response formats. A provider adapter may be mocked, replaced, or supplemented without changing analysis, portfolio, or paper-trading rules.

### 2.3 Auditability and reproducibility

Signals, diagnostics, scorecards, execution-gate decisions, trades, experiments, backtests, and strategy versions are immutable or versioned records. A historical result must be reproducible using the data snapshot/as-of time, configuration, and strategy version available at that time. Corrections create a superseding record rather than silently overwriting history.

### 2.4 Safe automation

The system may generate research, paper-trade records, alerts, and strategy-change proposals. It must not silently promote experiments or place orders. Any strategy release follows the validation lifecycle in section 12 and requires explicit review/approval outside the automated engine.

## 3. High-level architecture

### 3.1 Ingestion and data-quality layer

Responsibilities:

- ingest mock data first, then future approved providers;
- normalize instrument identifiers, prices, volume, fundamentals, corporate events, holdings, index/sector data, and research/news items;
- preserve raw payload references where permitted;
- validate schema, time ordering, completeness, duplicates, and obvious outliers;
- label freshness, quality, validation result, and known limitations;
- make as-of snapshots available for analysis and testing.

No downstream engine may treat stale, failed-validation, or missing data as reliable without explicitly recording that exception and lowering or withholding confidence.

### 3.2 Analysis engines

The eventual system contains the following independently testable engines:

1. Market Regime Engine
2. Sector Rotation Engine
3. Fundamental/Earnings Engine
4. Technical Analysis Engine
5. Relative Strength Engine
6. Volume/OBV/VWAP Engine
7. Ichimoku + Multi-Timeframe Engine
8. Smart Money / Institutional Proxy Engine
9. Liquidity / SMC Engine
10. Crowd vs Smart Money Engine
11. News & Research Engine
12. 61-Point Diagnostic Engine
13. 10-Point Scoring Engine
14. 6 Mandatory Execution Gates
15. Portfolio Engine
16. Capital Rotation Engine
17. Signal Engine
18. Paper Trading Engine
19. Benchmark Engine
20. Backtesting Engine
21. Walk-Forward Validation Engine
22. Self-Improvement Engine
23. Strategy Versioning Engine
24. Risk Management Engine
25. Alert Engine
26. Dashboard/API

Each engine receives versioned, timestamped inputs and returns a structured output containing result/status, confidence, evidence, data-source references, evaluation time, applicable market time, and strategy version. It must express insufficient or invalid data explicitly instead of synthesizing a confident result.

### 3.3 Orchestration flow

1. Obtain a validated as-of market-data snapshot.
2. Determine market regime and eligible universe.
3. Analyze sectors and individual instruments using available engines.
4. Produce 61-point diagnostic records and the weighted 10-point scorecard.
5. Apply risk controls and all six execution gates.
6. Compare eligible candidates against current holdings and cash.
7. Create an auditable signal and a paper-trade record for each eligible signal.
8. Monitor paper trades, portfolio state, and outcome metrics.
9. Evaluate performance against benchmarks and validation sets.
10. Propose, validate, review, and version improvements; never deploy them silently.

## 4. Research and analysis requirements

### 4.1 Market regime and sector rotation

The Market Regime Engine classifies the market context using only data valid as of the evaluation time. The Sector Rotation Engine identifies relative sector strength, weakness, and trends. Their outputs constrain confidence, risk posture, and candidate interpretation rather than being hidden overrides.

### 4.2 Fundamental, technical, and relative-strength analysis

The system evaluates earnings acceleration, valuation/risk-reward, price structure, technical indicators, relative strength, volume, OBV, VWAP, Ichimoku, and multiple timeframes as data permits. Indicator calculations must retain parameter values, observation windows, and source bars/inputs. Missing data must prevent or qualify the relevant conclusion.

### 4.3 Institutional, liquidity, and research proxies

Smart-money, institutional, crowd, liquidity, and SMC modules may only use defined, sourced proxy evidence. The engine must label a proxy as a proxy and preserve its limitations; it must not claim direct institutional or order-book knowledge where it lacks it. News/research observations remain attributed and timestamped, with factual reporting kept separate from model interpretation.

## 5. 61-point diagnostic engine

The eventual diagnostic engine implements all 61 defined diagnostic rules. Every diagnostic evaluation is auditable and records:

- rule ID;
- result/status;
- score;
- confidence;
- evidence and input references;
- data sources;
- timestamps;
- strategy version.

Rules must be deterministic for a given snapshot and strategy version. Rule definitions, thresholds, dependencies, score ranges, and missing-data behavior are version-controlled configuration. The exact 61 rule definitions are not present in this brief and must be supplied and approved before this engine can be fully implemented.

## 6. 10-point scoring engine

The overall score combines these weighted dimensions:

| Dimension | Weight |
| --- | ---: |
| Earnings Acceleration | 15% |
| Market Regime | 10% |
| Sector Rotation | 10% |
| Smart Money Evidence | 10% |
| Relative Strength | 10% |
| Price Structure | 10% |
| Volume / OBV / VWAP | 10% |
| Ichimoku & MTF | 10% |
| Valuation & Risk/Reward | 10% |
| Liquidity & SMC | 5% |

The scorecard stores each component score, weight, confidence, evidence, missing-data treatment, aggregate score, and strategy version. The system must not substitute invented component values. Score normalisation, aggregation, confidence treatment, and thresholds require explicit specification and versioning.

### Canonical definition status

`diagnostic-registry-v1` defines 61 diagnostic checkpoints; they are not a 61-point score or a coverage-derived Decision Score. `decision-score-policy-v1` separately defines the ten components and weights. Data Confidence—including source reliability, freshness, completeness, validation, corroboration, and input coverage—remains distinct from the Decision Score, with Crowd Data Confidence separately represented where applicable. The default missing-data policy is no silent weight renormalization.

## 7. Portfolio and capital rotation

The Portfolio Engine maintains holdings, cash, exposure, risk, portfolio heat, factor/sector concentration, and relevant trade history. The Capital Rotation Engine ranks eligible candidates against current holdings.

A candidate normally replaces an existing holding only when all of these are true:

- `candidate score − weakest holding score` is at least +0.7 to +1.0 (the chosen threshold must be strategy-versioned);
- structural risk/reward is at least 1:2; and
- all six mandatory execution gates pass.

Cash is a valid position. The system can retain cash when no qualified opportunity exceeds the required hurdle.

## 8. Risk management and mandatory execution gates

Risk Management manages position sizing, per-position risk, stops, targets, portfolio heat, sector/factor limits, liquidity constraints, and invalidation handling. Its calculations must be explicit and auditable.

Before an eligible signal may be treated as executable in paper trading, every gate must pass:

1. Net friction/tax hurdle
2. Capital velocity/time-stop
3. Surveillance/circuit filter
4. Tranche scaling/de-risking
5. Portfolio heat/factor limits
6. Five-trading-day pre-earnings blackout

Each gate produces pass/fail/insufficient-data status, rationale, source evidence, parameters, timestamp, and strategy version. A failure or insufficient-data state blocks eligibility unless a future, explicitly versioned policy specifies otherwise.

`execution-gate-registry-v1` is the canonical definition set for these gates. It preserves intended parameter ranges and required authoritative inputs without treating unresolved ranges, tax costs, or market restrictions as permanent hard-coded production values.

## 9. Signal and paper-trading engine

An eligible signal creates a paper-trade record. Required creation fields are:

- signal ID and timestamp;
- market regime, sector, and stock;
- diagnostic scores and overall score;
- data confidence;
- catalyst and setup;
- entry, stop, targets, and risk/reward;
- position size and risk;
- thesis and invalidation;
- strategy version.

After creation, the record tracks maximum favourable excursion (MFE), maximum adverse excursion (MAE), exit, result, R multiple, holding period, and exit reason. All status changes are timestamped and traceable to observed data and the applicable rule version.

Google Sheets may later be supported as a human-readable paper-trading interface. It is not a system of record until synchronization, ownership, and conflict behavior are designed.

## 10. Benchmarking and testing

The Benchmark Engine eventually compares the system with:

1. Nifty 50 buy-and-hold
2. Nifty 500
3. Relevant sector indices
4. Simple momentum
5. Simple moving-average strategy
6. Randomized stock selection
7. Previous NSE Stock Manager versions
8. Trader-like baseline

For each comparable strategy and eligible period, report returns, CAGR, maximum drawdown, Sharpe, Sortino, volatility, expectancy, profit factor, win rate, R multiple, turnover, friction, capital efficiency, and regime-specific performance. Benchmark assumptions, universe, date range, rebalancing, transaction cost, and data version must be retained.

Backtesting and walk-forward validation must prevent look-ahead bias, data leakage, survivorship bias, hindsight bias, unrealistic fills, excessive optimization, and overfitting. Tests must use as-of data, realistic signal/execution timing, versioned universes where possible, explicit friction/slippage assumptions, out-of-sample periods, and results separated by market regime.

## 11. Alerts and dashboard/API

The Alert Engine notifies users about data-quality issues, eligibility/gate decisions, material portfolio risk, paper-trade lifecycle events, and review-required proposals. Alerts must cite their evidence and avoid presenting inference as fact.

The dashboard/API eventually provides research views, provenance, diagnostics, scorecards, portfolio state, paper-trade history, benchmarks, experiments, and strategy versions. It must expose data freshness and confidence clearly. External API contracts must not be invented before integration requirements are agreed.

## 12. Self-improvement and strategy governance

The Self-Improvement Engine analyzes historical paper trades for successful and failed setups, regime/sector failures, entry/stop/target failures, diagnostic usefulness, redundant diagnostics, scoring weaknesses, and rotation mistakes. It may create a hypothesis and propose an experiment.

No proposal changes the production strategy automatically. Every change follows this lifecycle:

`hypothesis → backtest → walk-forward validation → out-of-sample validation → paper trading → review → new strategy version`

The Strategy Versioning Engine records the immutable strategy configuration, rule definitions, scoring/gate settings, approval/review metadata, activation period, and validation artifacts. Historical signals and trades remain associated with the version that created them.

## 13. Cross-cutting quality requirements

- **Correctness:** calculations and decisions are deterministic for a specified snapshot and version.
- **Traceability:** users can navigate from conclusion to evidence and sources.
- **Observability:** record ingestion, validation, engine, and decision failures without exposing sensitive data.
- **Security/privacy:** keep the system private; use least privilege when future data or sheet integrations are approved.
- **Testing:** use unit tests for rules/calculations, integration tests for the pipeline, fixture-based tests for data validation, and reproducible backtest/validation tests.
- **Operational safety:** failures fail closed for execution eligibility; a data failure never becomes a fabricated market observation.

## 14. Initial implementation boundary

The present milestone creates only this specification, the development roadmap, and a minimal project README. The next implementation task should establish a small, testable foundation using mock data and should not introduce a provider integration, live trading, autonomous order execution, or undocumented APIs.
