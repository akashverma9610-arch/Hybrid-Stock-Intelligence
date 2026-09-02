# NSE Stock Manager v2.1

NSE Stock Manager is a private, AI-assisted research and paper-trading system for Indian equities (NSE/BSE). Its purpose is to help assess whether capital is allocated to the strongest available **risk-adjusted** opportunities.

## Eligible NSE equity opportunity orchestration

The controlled opportunity pipeline uses canonical stored data only:
ingestion → eligible NSE equity universe → 61-diagnostic input assembly and
registry execution → existing Decision Score → confidence → six gates →
candidate qualification → existing portfolio rotation comparison → distilled
read-only output. It does not fetch providers per diagnostic, create a manual
shortlist, promote/activate a strategy, or place trades.

The supported population scope is **NSE main-board equity shares** imported from
an approved local official export or canonical instrument mapping. ETFs, bonds,
REITs, InvITs, preference shares, warrants, rights, suspended/delisted
instruments, and unsupported SME securities are excluded with retained reasons.
`FULL` coverage means the bound immutable universe snapshot completed its
eligibility, analysis, and candidate-materialization stages. Otherwise the UI
uses “best candidate among analyzed opportunity set,” never “best NSE stock.”

It is being built incrementally. The current repository contains a provider-independent Python foundation that uses fixed mock data only. It has no market-data provider, live-trading connection, autonomous order execution, or investment-performance guarantee.

## Guiding principles

- Treat facts, source data, interpretation, and inference as distinct layers.
- Retain provenance, timestamps, freshness, validation status, and data quality for material observations.
- Start with mock/test data and provider-independent boundaries.
- Keep diagnostic decisions, strategy versions, and paper-trade outcomes auditable.
- Validate proposed strategy changes before they can become a new production version.
- Treat future OOS results as immutable evidence, never as automatic promotion, approval, or activation.
- Cash is a valid portfolio allocation.

## Documentation

### Hardened brain architecture (canonical detailed specification)

- [Brain Architecture v2.2-hardened](docs/architecture/brain_architecture.md)
- [Brain contract](docs/architecture/brain_contract.md)
- [Defensive engines](docs/architecture/defensive_engines.md)
- [Data flow and failure propagation](docs/architecture/data_flow.md)
- [Decision flow](docs/architecture/decision_flow.md)
- [Model governance and drift](docs/architecture/model_governance.md)
- [Audit and reproducibility](docs/architecture/audit_reproducibility.md)
- [Versioning and change control](docs/architecture/versioning_and_change_control.md)
- [Post-V1 Product Architecture — One Brain, Multiple Signal Windows](docs/architecture/POST_V1_PRODUCT_ARCHITECTURE.md)
- [P1 Watch-only HSISignal Foundation proposal](docs/architecture/POST_V1_HSI_SIGNAL_P1_ACTIVATION_PROPOSAL.md)
- [Post-V1 Strategy and Signal-Window Catalogue](docs/architecture/POST_V1_STRATEGY_AND_SIGNAL_WINDOW_CATALOGUE.md)
- [Live-readiness hardening candidate (not approved)](docs/architecture/live_readiness_candidate.md)
- [Economic and news intelligence](docs/architecture/economic_news_intelligence.md)
- [Controlled real-Brain trial](docs/architecture/real_brain_trial.md)
- [Minimum viable real-data package](docs/architecture/minimum_real_data_package.md)

Repository documentation and tested code are authoritative over chat or memory.
The hardened architecture is additive: it reuses existing engines and never
turns a diagnostic, score, gate, rotation result, self-improvement observation,
or API read into autonomous execution.

- [Master specification](docs/NSE_STOCK_MANAGER_V2_1_MASTER_SPEC.md)
- [Development roadmap](docs/ROADMAP.md)
- [Foundation architecture](docs/ARCHITECTURE.md)
- [Strategy governance](docs/STRATEGY_GOVERNANCE.md)
- [Technical analysis](docs/TECHNICAL_ANALYSIS.md)
- [Market regime](docs/MARKET_REGIME.md)
- [Crisis and market-dislocation engine](docs/CRISIS_MARKET_DISLOCATION_ENGINE.md)
- [Market extremes and upside euphoria engine](docs/MARKET_EXTREMES_ENGINE.md)
- [Market-data architecture](docs/MARKET_DATA_ARCHITECTURE.md)
- [Data-provider integration boundary](docs/DATA_PROVIDER_INTEGRATION.md)
- [Streaming market-data boundary](docs/STREAMING_MARKET_DATA.md)
- [Historical market-data ingestion](docs/HISTORICAL_MARKET_DATA.md)
- [Market breadth aggregation](docs/MARKET_BREADTH.md)
- [Runtime pipeline](docs/RUNTIME_PIPELINE.md)
- [Data-source architecture](docs/DATA_SOURCE_ARCHITECTURE.md)
- [Corporate filings](docs/CORPORATE_FILINGS.md)
- [NSE official-export import](docs/NSE_OFFICIAL_IMPORT.md)
- [Global Datafeeds historical adapter](docs/GLOBAL_DATAFEEDS.md)
- [yfinance secondary historical adapter](docs/YFINANCE.md)
- [Canonical fundamentals](docs/FUNDAMENTALS.md)
- [Data freshness and quality](docs/DATA_FRESHNESS.md)
- [Relative strength](docs/RELATIVE_STRENGTH.md)
- [Diagnostic registry](docs/DIAGNOSTIC_REGISTRY.md)
- [Scoring policy](docs/SCORING_POLICY.md)
- [Execution gates](docs/EXECUTION_GATES.md)
- [Execution-gate engine](docs/EXECUTION_GATE_ENGINE.md)
- [Friction model](docs/FRICTION_MODEL.md)
- [Portfolio heat](docs/PORTFOLIO_HEAT.md)
- [Portfolio model](docs/PORTFOLIO_MODEL.md)
- [Portfolio accounting](docs/PORTFOLIO_ACCOUNTING.md)
- [Portfolio snapshots](docs/PORTFOLIO_SNAPSHOTS.md)
- [Capital rotation](docs/CAPITAL_ROTATION.md)
- [Public capital-rotation API contract](docs/FRONTEND_API_CONTRACT.md#endpoint-inventory)
- [Rotation matrix](docs/ROTATION_MATRIX.md)
- [Anti-churn](docs/ANTI_CHURN.md)
- [Signal lifecycle](docs/SIGNAL_LIFECYCLE.md)
- [Trade-plan orchestration](docs/TRADE_PLAN_ORCHESTRATION.md)
- [Paper trading](docs/PAPER_TRADING.md)
- [Paper fill model](docs/PAPER_FILL_MODEL.md)
- [Paper outcomes](docs/PAPER_OUTCOMES.md)
- [Earnings blackout](docs/EARNINGS_BLACKOUT.md)
- [Exchange calendar](docs/EXCHANGE_CALENDAR.md)
- [Backtest engine boundary](docs/BACKTEST_ENGINE.md)
- [Backtest replay clock](docs/BACKTEST_REPLAY_CLOCK.md)
- [Backtest run lifecycle](docs/BACKTEST_RUN_LIFECYCLE.md)
- [Backtest event log](docs/BACKTEST_EVENT_LOG.md)
- [Walk-forward validation](docs/WALK_FORWARD_VALIDATION.md)
- [Out-of-sample validation](docs/OUT_OF_SAMPLE_VALIDATION.md)
- [OOS aggregation](docs/OOS_AGGREGATION.md)
- [OOS stability analysis](docs/OOS_STABILITY_ANALYSIS.md)
- [Controlled strategy experiments](docs/CONTROLLED_STRATEGY_EXPERIMENTS.md)
- [Parameter robustness](docs/PARAMETER_ROBUSTNESS.md)
- [Candidate selection](docs/CANDIDATE_SELECTION.md)
- [Future OOS candidate queue](docs/FUTURE_OOS_CANDIDATE_QUEUE.md)
- [Future OOS execution](docs/FUTURE_OOS_EXECUTION.md)
- [Feature flags and runtime capabilities](docs/FEATURE_FLAGS.md)
- [API architecture](docs/API_ARCHITECTURE.md)
- [API reference](docs/API_REFERENCE.md)
- [Frontend API contract](docs/FRONTEND_API_CONTRACT.md)
- [Stock and portfolio frontend contract](docs/FRONTEND_API_CONTRACT.md#endpoint-inventory)
- [Google AI Studio frontend specification](docs/FRONTEND_GOOGLE_AI_STUDIO_SPEC.md)
- [Local backend setup](docs/LOCAL_BACKEND_SETUP.md)
- [Promotion evidence package](docs/PROMOTION_EVIDENCE_PACKAGE.md)
- [Strategy promotion governance](docs/STRATEGY_PROMOTION_GOVERNANCE.md)
- [Strategy versioning and activation](docs/STRATEGY_VERSIONING_AND_ACTIVATION.md)
- [Strategy rollback](docs/STRATEGY_ROLLBACK.md)
- [Historical execution timing](docs/HISTORICAL_EXECUTION_TIMING.md)
- [Historical capital allocation](docs/HISTORICAL_CAPITAL_ALLOCATION.md)
- [Historical paper-ledger integration](docs/HISTORICAL_PAPER_LEDGER_INTEGRATION.md)
- [Historical performance integration](docs/HISTORICAL_PERFORMANCE_INTEGRATION.md)
- [Historical benchmark integration](docs/HISTORICAL_BENCHMARK_INTEGRATION.md)
- [Historical equity series](docs/HISTORICAL_EQUITY_SERIES.md)
- [Historical analytical replay](docs/HISTORICAL_ANALYTICAL_REPLAY.md)
- [Historical backtest portfolio replay](docs/HISTORICAL_PORTFOLIO_REPLAY.md)
- [Historical portfolio-context gates](docs/HISTORICAL_PORTFOLIO_GATES.md)
- [Historical capital-rotation replay](docs/HISTORICAL_ROTATION_REPLAY.md)
- [Historical signal replay](docs/HISTORICAL_SIGNAL_REPLAY.md)
- [Historical paper-trade replay](docs/HISTORICAL_PAPER_TRADE_REPLAY.md)
- [Research policy](docs/RESEARCH_POLICY.md)
- [Benchmark policy](docs/BENCHMARK_POLICY.md)
- [Diagnostic evaluation](docs/DIAGNOSTIC_EVALUATION.md)
- [Sector analysis](docs/SECTOR_ANALYSIS.md)
- [Volume analysis](docs/VOLUME_ANALYSIS.md)
- [Ichimoku and multi-timeframe analysis](docs/ICHIMOKU.md)
- [VWAP and OBV](docs/VWAP_OBV.md)
- [Fundamental data](docs/FUNDAMENTAL_DATA.md)
- [Financial metrics](docs/FINANCIAL_METRICS.md)
- [Earnings acceleration](docs/EARNINGS_ACCELERATION.md)
- [Ownership analysis](docs/OWNERSHIP_ANALYSIS.md)
- [Order-book analysis](docs/ORDER_BOOK_ANALYSIS.md)
- [Research intelligence](docs/RESEARCH_INTELLIGENCE.md)
- [Source reliability](docs/SOURCE_RELIABILITY.md)
- [Claim model](docs/CLAIM_MODEL.md)
- [Guidance tracking](docs/GUIDANCE_TRACKING.md)
- [Catalyst engine](docs/CATALYST_ENGINE.md)
- [Valuation analysis](docs/VALUATION_ANALYSIS.md)
- [Pattern analysis](docs/PATTERN_ANALYSIS.md) — transparent V1 VCP, Flat Base, Cup & Handle, and Ascending Base approximations
- [Trade structures](docs/TRADE_STRUCTURE.md)
- [Risk/reward](docs/RISK_REWARD.md)
- [Thesis invalidation](docs/THESIS_INVALIDATION.md)
- [Liquidity and SMC proxies](docs/LIQUIDITY_SMC.md)
- [Wyckoff analysis](docs/WYCKOFF_ANALYSIS.md)
- [Smart-money proxies](docs/SMART_MONEY_PROXIES.md)
- [Trap detection](docs/TRAP_DETECTION.md)
- [Volume climax](docs/VOLUME_CLIMAX.md)
- [Crowd sentiment](docs/CROWD_SENTIMENT.md)
- [Crowd confidence](docs/CROWD_CONFIDENCE.md)
- [Contrarian engine](docs/CONTRARIAN_ENGINE.md)
- [Post-news reaction](docs/POST_NEWS_REACTION.md)
- [Risk engine](docs/RISK_ENGINE.md)
- [Trading thesis](docs/TRADING_THESIS.md)
- [Investment thesis](docs/INVESTMENT_THESIS.md)
- [Scenario engine](docs/SCENARIO_ENGINE.md)
- [Decision Score](docs/DECISION_SCORE.md)
- [Scoring components](docs/SCORING_COMPONENTS.md)

Decision Scorecards and execution-gate evaluations are persisted immutably with their dependencies and can be audit-reconstructed. They remain analytical artifacts only.

## Current status

The project uses Python 3.12+, frozen dataclasses and enums for domain models, SQLite from the Python standard library, and pytest for tests. No production dependency is required. Phase 9A is complete. Phase 9B is partially complete and deferred for automatic production orchestration: its future runtime capability defaults to disabled, while the reusable research/OOS services remain available for tests and controlled manual use.

The #027A market-data foundation is provider-neutral and currently includes only
a deterministic static/mock provider. It defines canonical identity, facts,
normalization, quality, freshness, provenance, capabilities, and local storage;
it does not call an external provider, open a WebSocket, use credentials, expose
a live-data endpoint, or connect to a broker.

Kotak Neo is the first read-only adapter behind that boundary. It is selected
only with `MARKET_DATA_PROVIDER=kotak_neo`, has no live market-data FastAPI route or background
activation, and supports only explicitly mapped current quote/index/VIX facts.
It cannot place/modify/cancel orders, access a portfolio/demat account, or open
a WebSocket. See [Kotak Neo integration](docs/KOTAK_NEO_INTEGRATION.md).

Normal local provider configuration can instead use the secret-free connection
profile API backed by the OS credential manager; PowerShell variables remain a
developer fallback. See [connection management](docs/CONNECTION_MANAGEMENT.md).
This local/private settings flow can save, test, and clear data-provider
credentials but cannot access an account, trade, promote/activate a strategy,
or mutate a portfolio.

Performance reports and benchmark inputs are immutable as-of artifacts: newer paper trades or market observations create newer reports rather than changing prior historical reports.

The implemented flow is:

`mock data → validated as-of snapshot → deterministic diagnostics → immutable Decision Scorecard → execution gates → portfolio state → rotation comparison → non-executable signal lifecycle → future paper-trading layer`

### Candidate strategy setup

The candidate setup layer has separate positional pre-breakout and fundamental
inflection modules. They consume frozen market/macro/sector/company/catalyst
evidence and can produce only a research candidate with Setup Quality,
structural trigger/invalidation/target, R:R, horizon, coverage, and warnings.
Setup Quality is not Decision Score, confidence, a gate, or a final action.
Every candidate still proceeds through the canonical 61 diagnostics, score,
confidence, gates, portfolio comparison, and execution boundaries. See
[pre-breakout and inflection architecture](docs/architecture/pre_breakout_inflection.md).

### Real-data taxonomy and coverage

The project distinguishes current NSE universe membership from historical
membership, sectors from macro themes, and code support from actually stored
data. The append-only taxonomy import is ISIN-first and local-file-only;
`python -m app.runtime coverage-report` shows evidence coverage and data-engineering
gaps without contacting a provider or scanning the universe. See
[taxonomy](docs/architecture/taxonomy.md) and
[data coverage](docs/architecture/data_coverage.md).

### Historical security integrity

Historical identity, universe membership, corporate actions, and price
adjustment basis are separate from today’s NSE universe. The historical security
master keeps effective-date provenance and rejects mixed or raw-across-split
price series as technical inputs rather than silently changing history. See
[historical security master](docs/architecture/historical_security_master.md).

The initial FastAPI boundary exposes `/health`, `/api/v1/system/status`,
`/api/v1/system/version`, and read-only portfolio snapshot, holdings, and
summary routes, plus injected read-only market-regime and sector routes.
OpenAPI is available at `/openapi.json` and `/docs`. It does not mutate
portfolios, start research, calculate new analytics, connect to live data, or
invoke a broker.

The primary stock-detail route is `/api/v1/stocks/{symbol}/analysis`. It maps
existing analysis only; its data can be partial/stale, preserves score and
confidence separately, and does not turn smart-money proxies into institutional
facts.

Read-only signal and simulated paper-trade views are available at
`/api/v1/signals`, `/api/v1/signals/{signal_id}`, `/api/v1/paper-trades`,
`/api/v1/paper-trades/{trade_id}`, and `/api/v1/paper-trades/performance` when
an application composition layer injects stored records. These routes never
generate, execute, fill, or exit a trade; output performance is stored
canonical simulated-paper evidence, and open trades can have legitimately
incomplete outcome fields.

Historical replay currently stops at deterministic calendar scheduling, immutable run metadata, and append-only placeholder events. It does not replay a strategy or execute analytical/trading layers.

Historical analytical replay can build frozen snapshots and persist diagnostic, Decision Scorecard, and gate artifacts. It creates no signals, orders, paper trades, performance reports, or benchmark results.

Historical replay regression fixtures verify that future market, index, sector, financial/restatement, research/crowd, surveillance, earnings-schedule, and universe records do not retrospectively change an earlier evaluation.

All 61-rule V1 diagnostic wrappers and the deterministic Decision Score are implemented. Gates determine analytical eligibility only; they do not execute orders or create signals.

## Install and run

Create and activate a virtual environment, then install the development test dependency:

```sh
python -m venv .venv
# Windows PowerShell
.venv\\Scripts\\Activate.ps1
python -m pip install -e ".[dev]"
```

Run the verification suite:

```sh
python -m pytest
```

Start the local HTTP backend:

```sh
python -m uvicorn app.api.main:app --reload
```

Run a small mock-data foundation demonstration:

```sh
python -m app.testing.foundation_demo
```

The local runtime boundary is explicit and disabled by default. Once a local
host has composed stored data plus an explicit universe, `python -m app.runtime
run-once --universe <id>` runs one cycle; add `--dry-run` to prevent snapshot
publication. `python -m app.runtime status` reads safe process-lifetime runtime
health only. The optional `worker` command requires an explicit enabled setting
and does not start from FastAPI.

`GET /api/v1/data-sources/status` exposes sanitized source readiness for local
development. It distinguishes stored data from live providers, labels mock only
when explicitly configured, and does not claim a Kotak historical endpoint.

## Current limitations

- The crisis/dislocation engine is a provider-neutral policy and domain
  foundation only. It has no live market/breadth/VIX/liquidity feed, calibrated
  thresholds, runtime activation, API endpoint, broker/order behavior, or
  automatic strategy change. It treats cash as deliberate optionality, not a
  missing BUY, and does not encode blanket liquidation or blind dip buying.
- The market-extremes upside tail is also architecture-only. Euphoria is
  evidence-based risk context, not proof of a top or an automatic sell. It has
  no live price/IPO/news/social inputs, calibrated thresholds, provider, broker,
  API endpoint, automatic rotation, or strategy mutation.

- Self-improvement observation is deterministic and association-only. It can summarize frozen recurring evidence but cannot claim causal attribution, generate a hypothesis or experiment, modify a strategy, approve/activate a version, or affect any account.
- Structured self-improvement hypotheses and human research reviews are immutable and research-only. A human `APPROVE_FOR_EXPERIMENT` review is not an experiment, candidate selection, strategy promotion, or activation.
- A reviewed hypothesis may create one immutable, budget-bounded `PLANNED` controlled-experiment draft. Draft creation does not execute an experiment, generate evidence, select a candidate, promote, or activate a strategy.
- There is no automatic self-improvement scheduler. `AUTOMATED_SELF_IMPROVEMENT_RESEARCH` is an experimental, deferred, disabled-by-default future-runtime capability; enabling it only permits a future orchestrator and does not itself start research or change strategy/governance records.

- SQLite is a local-development adapter only; PostgreSQL is intentionally deferred behind the repository interface.
- Fixtures are deterministic and contain mock values only.
- Technical analysis is limited to deterministic SMA, EMA, RSI, ATR, ADX, pivots, trend, market regime, relative performance, sector-return proxies, RVOL, Ichimoku, VWAP, and OBV using mock fixtures.
- Sector rotation and OBV/RVOL outputs are observable price-volume proxies, not factual fund-flow or institutional-activity conclusions. Value Area is unavailable unless real volume-at-price data is supplied.
- There are no data-provider adapters, position sizing, paper-trade fills/outcomes, broker APIs, real-money workflows, or autonomous trading.
- The HTTP API has no signal/paper mutation route, broker/demat access, live
  order behavior, or real-account mutation. Its paper-trade endpoints expose
  simulations only.
- Read-only performance, benchmark, and governance endpoints expose stored
  immutable records only. Benchmark unavailable states and TRAIN/VALIDATION/
  TEST/OOS identities remain visible; approved strategy is not active without
  an explicit activation. There is no API promotion, approval, activation,
  rollback, backtest, or benchmark execution endpoint.
- Validation fails closed: only explicitly `VALID` observations are eligible for downstream analysis.
- Strategy governance stores record structures and approval history only; it does not approve, activate, or calculate a real strategy automatically.
- Replay orchestration supports daily-close scheduling only. It has no chronological strategy replay, diagnostics/gates/signal integration, fills, outcomes, backtests, benchmarks, optimization, or walk-forward validation.

The next task should be selected from the roadmap; it must not introduce live execution until that capability is explicitly approved and safely designed.

## API foundation status

**PHASE 10 / #026A — PRODUCTION API FOUNDATION: COMPLETE.** The FastAPI
architecture and read-only domain endpoints are stable for local/private
development. This is not a public production deployment: SQLite is
development-oriented, and authentication/user tenancy, providers/current market
data, mutation APIs, broker integration, OpenAI runtime, automated Phase 9B
runtime, and frontend work remain deferred. Do not expose it publicly.

## Database foundation

SQLite remains the safe local/test default. PostgreSQL is now an explicit lazy
production-persistence option with Alembic infrastructure and one representative
immutable approved-strategy-version adapter. See
[`docs/POSTGRESQL_SETUP.md`](docs/POSTGRESQL_SETUP.md) and
[`docs/DATABASE_ARCHITECTURE.md`](docs/DATABASE_ARCHITECTURE.md). The app builds
the configured read repository lazily in its lifespan and no route runs a
migration; full repository migration, production PostgreSQL validation, provider
wiring, and live behavior remain deferred.

Core Phase 10 API read models are persisted as immutable versioned snapshots
through either SQLite or PostgreSQL adapters. At FastAPI lifespan startup, the
default read facades use that configured repository; explicit injected facades
remain supported for tests and local composition. SQLite is the local-safe
default, while PostgreSQL is explicit and lazy. Empty stores fail safely and
there is no API snapshot writer, live provider, research runner, governance
mutation, broker, or account effect. Broader normalized historical/Phase 9B
migrations and real PostgreSQL-server validation remain out of scope.

**#026B — PRODUCTION PERSISTENCE FOUNDATION: COMPLETE FOR V1 READ PATH.** This
is not a public deployment or a claim that every repository family is migrated.
### Optional secondary news

The backend can optionally ingest provider-returned GNews metadata for research context.  Configure it separately from `CURRENT_QUOTES` (Kotak Neo) and `HISTORICAL_OHLCV` (Global Datafeeds).  GNews is not a primary filing feed, does not fetch article pages, may be delayed depending on plan, and cannot change a score, gate, order, or active strategy.
### Primary-market evidence

Official NSE-supplied IPO/issue exports can be imported locally for factual issue, subscription, and listing context. Fresh issue and OFS are preserved separately. This is optional evidence for the existing Market Extremes input boundary—not a market-top, trading, or scoring engine.

### Dashboard market breadth, extremes, and crisis

The Dashboard consumes distilled, read-only persisted snapshots at
`/api/v1/market/breadth`, `/api/v1/market/extremes`, and
`/api/v1/market/crisis`. They expose only public canonical state and factual
summary fields plus timestamp/freshness/warnings; they never call a provider or
re-run market analytics on request. Missing data is shown as unavailable, not
NORMAL. Euphoria is elevated speculation/chase-risk context rather than a
market-top or SELL call, and crisis is a risk overlay rather than an automatic
liquidation or dip-buying instruction.

### Signals, paper trading, performance, and benchmark frontend

The remaining market-review pages consume only their read-only API contracts.
Signals and paper trades show public lifecycle, distilled plan or outcome fields,
warnings, and safe stock links; they cannot execute or change a trade.
Performance reports and benchmark comparisons require explicit selectors and
display backend-computed KPI summaries only. Browser code does not calculate
scores, indicators, performance metrics, or time series, and public responses
exclude audit provenance/evidence IDs and diagnostic/gate internals.

### Portfolio screenshot import

The Portfolio page accepts a bounded set of JPG/PNG/WebP broker screenshots as
a temporary extraction draft. Each row is provisional and must be reviewed and
explicitly confirmed before entering the canonical append-only portfolio
repository. Raw screenshots, unrelated account text, and OCR text are not kept
in the draft or exposed by the API. The default extractor is unavailable until
an approved server-side provider is configured; no provider key belongs in the
frontend. Screenshot LTP never replaces canonical market data. `MERGE` is not
supported yet; confirmation requires explicit `REPLACE`.

### Controlled portfolio analysis

After confirmation, `Analyze Portfolio` can queue a job pinned to the exact
portfolio snapshot. It is holdings-only and enters the existing backend
analysis/runtime boundary; it does not scan NSE, invent external candidates, or
place orders. Job completion is separate from diagnostic completeness. The
registry has 61 canonical definitions, but the current live orchestration does
not assemble every rule’s required inputs, so unavailable evidence remains
partial rather than being treated as a complete 61-diagnostic result.

### Stored NSE universe opportunity pipeline

The read-only opportunity workflow uses an official/stored NSE universe,
coverage preflight, eligibility, all-61 canonical analysis, Decision Score,
confidence, six gates, candidate materialization, and the existing capital
rotation engine. Data coverage is separate from stock scoring: missing history,
fundamentals, filings, research, ownership, market, or sector context remains
visible as `PARTIAL`/`MISSING`. A full-coverage claim is made only when the
entire intended eligible universe completed analysis and materialization;
otherwise candidates are explicitly “among the analyzed opportunity set.” This
workflow has no broker, order, demat, promotion, approval, or activation effect.

### Real-data readiness and controlled NSE imports

`python -m app.runtime import-nse-universe <official-local-csv> [--dry-run]`
accepts only an explicit local official NSE equity export.  It reports raw,
eligible, excluded, duplicate, and missing-sector/industry counts; a non-dry
run freezes an immutable `UniverseSnapshot`.  It never downloads or scrapes a
universe. `python -m app.runtime data-readiness` (or `universe-status`) reports
declared source configuration/readiness without testing a provider or printing
credentials. A configured source is not a validated source.

The intended real-data flow is: official NSE universe → canonical identity and
provider mappings → explicit provider/official ingestion → canonical stores →
coverage preflight → 61 diagnostics → score/confidence/gates → opportunity set
→ existing capital rotation. Kotak Neo remains the current-quote source and
Global Datafeeds and Upstox Historical Candle V3 remain independently
selectable historical-OHLCV sources. Upstox uses an exact official instrument
key and retains unknown adjustment semantics unless separate action evidence
proves more. Neither source is selected as a silent fallback.
Missing mappings, history, fundamentals, filings, ownership, news, or market
context block a full scan rather than being fabricated. No full live NSE scan,
broker action, or automatic strategy change is started by these commands.

For a first local dataset: (1) obtain an official NSE equity-universe CSV and
save it locally, (2) run `python -m app.runtime import-nse-universe <file>
--dry-run`, (3) rerun without `--dry-run`, then (4) run `python -m app.runtime
universe-status` and `python -m app.runtime data-readiness`. Runtime commands
default to the relative persistent SQLite path `data/nse_stock_manager.db`
unless an explicit `DATABASE_URL` selects SQLite or PostgreSQL. Neither command
contacts a provider or accepts credentials.
