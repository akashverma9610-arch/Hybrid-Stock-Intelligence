# Foundation Architecture

## Eligible NSE equity opportunity orchestration

`app.universe_analysis` is the bounded cooperative full-universe orchestration
layer. It uses imported/stored NSE equity identities and canonical stored facts,
applies a point-in-time guard before assembly, iterates the canonical 61-rule
registry, and reports COMPLETE/PARTIAL/UNAVAILABLE truthfully. Missing data
stays missing. Decision Score, confidence, six gates, and Capital Rotation stay
separate existing engines. Public opportunity snapshots exclude diagnostic and
evidence IDs, gate IDs, thresholds, and configuration. Reads never start scans.

`OfficialNseUniverseImporter` accepts only an explicit local official CSV and
deduplicates by NSE+ISIN, then canonical instrument ID, then a safe normalized
symbol. Analysis jobs bind to immutable `UniverseSnapshot` records.
`PortfolioUniverseRotationService` converts only persisted analyzed candidates
and coherent immutable portfolio holdings into existing `CapitalRotationEngine`
inputs; it excludes holdings as self-candidates and fails closed on stale
holding analysis. It persists no order or portfolio mutation.

## HTTP API boundary

`app/api` is a FastAPI-only application boundary around the stable Python
engine. It has a testable factory, versioned `/api/v1` system routes, explicit
Pydantic schemas, request-ID middleware, safe unexpected-error responses, and
explicit CORS origins. Its lightweight lifespan initializes no scheduler,
database migration, market scan, or research/OOS execution. No write-domain
routes, authentication, provider, broker, or real-account interface are exposed.

The initial portfolio API adds only an injected read-only query facade over an
existing immutable `PortfolioSnapshot`. It does not reconstruct holdings,
calculate P&L/heat, select a rotation, mutate a ledger, or open a database
connection. The default local source is unavailable rather than fabricated;
future authenticated tenancy may replace this single/local context.

The market/sector API is likewise an injected read-only facade. It maps existing
`MarketRegimeResult` and sector rotation diagnostics to public schemas without
classifying markets, calculating relative strength, changing ranks, touching
providers, or starting self-improvement/OOS workflows. No current live-data
query contract exists, so the default source fails safely as unavailable.

The capital-rotation API is a separate public read projection of an already
persisted `PortfolioRotationEvaluation`. It never invokes `CapitalRotationEngine`
from HTTP, recomputes rankings, scans candidates, modifies a portfolio, or
creates a signal/order. It deliberately strips configuration thresholds, the
six-gate inventory, diagnostic/rule/evidence identifiers, component weights,
ranking inputs, and proprietary reasons; only distilled comparison outcomes and
public-safe context reach `/api/v1/capital-rotation`.

The stock-detail API uses an injected aggregate read model rather than an API
orchestrator that reruns diagnostics. It maps existing registry coverage,
Decision Scorecard components, canonical execution gates, and optional grouped
technical/fundamental/research/valuation/trade/liquidity diagnostics. It makes
no inference beyond its inputs; in particular, liquidity/smart-money outputs
remain price-volume proxies, not direct institutional-order knowledge.

`GET /stocks` is a separate persisted-summary read model over the existing
stock-analysis snapshot family. It returns one latest public-safe record per
stored symbol and performs no universe scan, provider call, runtime work, or
analysis calculation. The list and detail routes intentionally omit diagnostic
inventories, weights, gate identifiers, evidence/provenance IDs, and thresholds.

## Walk-forward OOS orchestration

`app/backtest/walk_forward.py` persists immutable plans, candidates, windows, runs, and results through the existing governance repository. It freezes FIXED_STRATEGY references before TEST, validates exact TEST bounds, and delegates execution to Phase 8A. Audit reconstruction verifies the plan/window/candidate/configuration/report chain and rejects tampered references or metrics without modifying stored history.

`app/backtest/oos_aggregation.py` is the immutable TEST-only aggregation boundary. It stores sufficiency configuration, rebased stitched OOS equity, degradation analyses, timestamped benchmark observations, and aggregate results in the same repository. Audit rebuilds the frozen chain and fails on altered points, metrics, ordering, or references.

`app/backtest/experiments.py` adds a governed pre-TEST experiment boundary. It persists hypotheses, candidate deltas, bounded budgets, canonical TRAIN/VALIDATION evidence, robustness findings, policies, and frozen selections. It has no promotion, live, or strategy-mutation path.

## Scope

The current implementation contains the deterministic local data foundation, Phase 2 strategy governance, and a narrow Phase 3 analytical slice. It contains no live market-data provider, brokerage connection, order workflow, signals, full 61-point diagnostics, final score calculations, or execution-gate logic.

## Flow

`mock input → domain record → validation/freshness → repository → as-of snapshot → immutable governance records → audit reconstruction`

## Explicit runtime-cycle and scheduler boundary — `app/runtime`

`RuntimeCycleCoordinator` constructs one deterministic stored-data or mock
cycle from an explicit universe and existing market-data stores. The #028B
`RuntimeScheduler` only serializes explicit `run_once()` calls to that existing
boundary. Its typed, non-secret settings default to disabled; `start()` creates
no thread/timer, and FastAPI lifespan does not create or start a scheduler.

The scheduler emits safe in-memory lifecycle events, skips `CLOSED` sessions
without marking a failure, prevents in-instance overlap, and records a
read-only `RuntimeHealth` state. It does not retry a failure immediately or
fall back to mock mode. Runtime health is deliberately separate from API
process health. No control endpoint, CLI, network/provider operation, broker,
account, order, portfolio, promotion, activation, or Phase 9B operation is
added. See [runtime pipeline](RUNTIME_PIPELINE.md).

#028C adds a local `python -m app.runtime` command boundary and an optional
single-threaded, interruptible worker. The worker is CLI-only: FastAPI remains
passive regardless of scheduler settings. The versioned read-only runtime-status
route reports health but cannot start, stop, or execute a cycle.

## Source readiness and runtime composition — `app/data_sources`

The source registry maps each market/fundamental/filing/research/IPO family to
an explicitly ordered source list and emits immutable sanitized readiness
reports. It separates stored data from live-source readiness, makes PIT,
adjustment, freshness, provenance, requirement, and validation state explicit,
and has no fallback to mock. It neither fetches data nor composes an implicit
universe/coordinator; future host composition must provide those dependencies.

## Primary-source corporate filings — `app/filings`

Corporate disclosures are immutable source facts with source/exchange identity,
attachments, revisions, time-aware visibility, and normalized indexed storage.
NSE/BSE adapters only normalize supplied records; no external fetch, parsing,
or interpretation runs inside the package. Filing records are future high-tier
research/evidence inputs but do not modify diagnostics, scores, gates, runtime,
portfolio, or strategy behavior.

The application service is the only component that composes these steps. Analytical engines can later consume snapshots, but cannot use observations whose validation result is not `VALID`.

## Domain layer — `app/domain`

Frozen dataclasses and enums define provider-independent records:

- `Instrument`, `Provenance`, `Freshness`, `ValidationResult`, and `AsOfSnapshot`;
- `MarketObservation` plus typed observation models for price bars, volume, fundamentals, corporate events, indices, sectors, and research items;
- `Evidence` and `DerivedObservationMetadata`.

Every observation retains its ID, instrument, source/source identifier, market and retrieval timestamps, quality label, raw/original record when supplied, validation result, and optional derivation metadata. Derived records include input references, calculation name, parameters, version, and derivation timestamp.

## Validation and freshness — `app/validation`, `app/config`

`ObservationValidator` is deterministic for an observation, evaluation timestamp, existing IDs, and freshness policy. It reports one explicit primary status and preserves all issues; it never fills, repairs, or guesses values.

It detects required-field failures, malformed records, invalid timestamps, future timestamps, duplicates, negative/non-numeric prices, invalid volume, incomplete price/volume data, stale data, and low/unknown quality warnings.

`FreshnessEngine` receives a `FreshnessPolicyConfig`. Thresholds are configuration values by observation kind, not assertions about real data-provider service levels. Its result records observed time, evaluation time, age, maximum configured age, and freshness status.

## Data and storage layer — `app/data`, `app/storage`

`MarketDataRepository` is the storage boundary. `SQLiteMarketDataRepository` is its initial local adapter and uses only the Python standard-library `sqlite3` module. It persists instruments, observations, validation results, evidence, snapshots, snapshot membership, and audit events.

Observations and validation results are separate records. Invalid and duplicate submissions remain persisted/auditable, but only a `VALID` result is eligible for snapshots. This isolates business logic from SQLite and permits a later PostgreSQL adapter without changing the domain objects or services.

## Production market-data contracts — `app/market_data`

The provider-neutral market-data boundary adds canonical instrument identity,
provider token mappings, quote/OHLCV/index/breadth/participation/session facts,
quality validation, session-aware freshness, provenance, capabilities, safe
errors, normalization, a registry, deterministic static provider, and an
append-only local/test store. It performs no network operation and cannot emit
analytics, strategy decisions, crisis/euphoria states, gates, portfolio actions,
or trades. Only canonical facts may later be transformed into the existing
validated domain observations/snapshots.

`KotakNeoMarketDataProvider` is the first real-provider implementation. It is
read-only and uses injectable HTTP transport, redacted typed credentials,
explicit TOTP/MPIN/dynamic-baseUrl session state, exact instrument mappings, and
canonical normalization. It has no FastAPI dependency and no trading/order,
portfolio/account, WebSocket, worker, polling, or automatic ingestion path.

## Streaming market-data boundary — `app/market_data/streaming.py`

The streaming boundary is an explicitly driven provider-neutral state machine
over injected transports. It manages immutable subscriptions, reconnect/backoff
calculation, heartbeat/feed health, and canonical quote writes through the
existing normalizer/store; it creates no thread, scheduler, provider network
client, strategy artifact, account action, or trade. The Kotak adapter currently
normalizes mocked/injected frames only. Real WebSocket transport is explicit
opt-in and deliberately pending provider-contract validation. See
[streaming market data](STREAMING_MARKET_DATA.md).

## Historical OHLCV ingestion — `app/market_data/historical.py`

Historical provider responses use existing canonical bars and flow through a
dedicated normalized historical-bar store. Ingestion validates quality,
chronology, duplicates/conflicts, conservative coverage/gaps, and provenance;
range/latest queries enforce optional received-time and bar-time as-of bounds
for replay. The layer has no provider network client, calendar scheduler,
analytics, strategy, portfolio, or trading action. See
[historical market data](HISTORICAL_MARKET_DATA.md).

## Local provider connection management — `app/connections`

`ConnectionProfile`, `CredentialStore`, `ProviderConnectionService`, and
provider-specific testers separate non-secret connection metadata from OS-backed
secret storage. Kotak Neo supports quote-only/session-read form metadata,
runtime-only TOTP/session handling, safe audit events, and a local/private
settings route. Saving/testing triggers no analysis, account read, market scan,
trading, or strategy/governance mutation. See
[connection management](CONNECTION_MANAGEMENT.md).

## Snapshot service — `app/services`

`FoundationService.build_as_of_snapshot` selects only observations that:

1. have `VALID` validation status;
2. have market timestamps at or before the requested as-of time; and
3. had already been retrieved at or before that time.

The final condition prevents later-received information from entering historical snapshots. Candidates are ordered deterministically, and the snapshot ID is a hash of its as-of time, policy, and included source records. Rebuilding the same data at the same time yields the same snapshot ID and contents.

## Strategy governance and audit — `app/services`, `app/storage`

Strategy definitions are immutable records identified by `(strategy_id, version)`. A changed configuration creates a successor version that names its parent; the original definition and analytical records remain untouched. Lifecycle changes (validation, approval, activation) are append-only events rather than edits to the definition.

The SQLite governance extension persists strategy versions/configurations, lifecycle events, evidence, diagnostic-result structures, scorecard structures, gate-decision structures, and audit events. `AuditReconstructionService` assembles a deterministic decision record from a strategy version, snapshot, evidence, diagnostics, scorecard, and gates. It does not calculate indicators, diagnostic scores, or gate outcomes.

Only strategies that have passed validation and received explicit approval can be activated. Only a record with both a strategy version and as-of timestamp may be persisted as a historical analytical result.

## Initial analytical slice — `app/analysis`

The analytical layer consumes snapshots only. It validates that bars are eligible, chronological, and available by the snapshot's as-of time before calculating deterministic SMA, EMA, RSI, ATR, ADX, pivot structure, trend, market regime, or relative strength. Periods and classification boundaries are supplied by explicit rule objects; no production trading threshold is hard-coded.

Each analysis result includes its calculation version, parameters, source observation IDs, strategy version, as-of/evaluation timestamps, data quality, status, confidence, and separately typed evidence. `AnalysisAuditService` persists generated evidence and an immutable diagnostic record so existing audit reconstruction can retrieve the decision inputs without rerunning calculations.

## Canonical registry and policies — `app/registry`

`app/registry/canonical.py` is the version-controlled source for exactly 61 diagnostic definitions, the separate 10-component Decision Score policy, data-confidence policy, missing-data policy, six gate definitions, research/catalyst hierarchy, benchmark registry, and self-improvement lifecycle. It defines no production diagnostic evaluator, component-scoring formula, gate execution, portfolio action, or trade action.

Every rule definition declares evidence constraints and whether its intended future evaluation is deterministic, hybrid, or interpretive. Strategy definitions already retain immutable rule/scoring/gate/risk/benchmark version references, allowing a later approved version to supersede rather than mutate historical configuration.

## Deterministic diagnostic evaluators — `app/diagnostics`

The approved deterministic subset wraps, rather than duplicates, existing market-regime, trend, relative-strength, pivot, RSI, ADX, ATR, sector-return, RVOL, Ichimoku, VWAP, and OBV engines. It implements Rules 1, 2, 3, 4, 5, 6, 10, 11, 12, 13, 14, 35, 36, and 39 only. Each output preserves canonical registry version, eligibility separate from result, confidence, source evidence, inputs, as-of time, and strategy version. Component eligibility can report eligibility without producing a numerical score.

`price_bar_series` is the sole price-bar input boundary for these engines. It fails closed when any supplied snapshot bar is unvalidated, malformed, or has market/retrieval time after the snapshot as-of time. This structurally prevents evaluators from accepting raw observations outside the snapshot boundary.

## Financial filing boundary

`FinancialObservation` provides an explicit typed representation for mock quarterly, annual, and derived TTM filing periods. Filing payloads retain reported period and publication time. `FoundationService` excludes fundamental observations until their declared publication timestamp, independently of period end, and financial engines repeat that fail-closed check. Superseding restatements are separate observations; prior reports are never rewritten.

## Research intelligence boundary

`app/research` is an independent deterministic research-document and claim boundary. It constructs as-of research snapshots from publication/retrieval times, validates claim-to-document provenance and tier consistency, and supplies structured inputs to four hybrid diagnostic wrappers. Future parser or LLM outputs must still provide attributable source references; they cannot bypass this boundary.

## Valuation and trade-structure boundary

`app/analysis/valuation_trade.py` combines validated as-of bars and filings for raw valuation metrics, and derives transparent base/support, candidate entry, stop, target, R:R, and invalidation structures. It has no order, signal, sizing, gate, portfolio, or broker interface.

## Liquidity proxy boundary

`app/analysis/liquidity.py` derives only timestamped price/volume proxies from the common validated bar boundary. It has no level-2/order-book feed and cannot observe institutions, order absorption, or actual stop quantities.

## Crowd and contrarian boundary

`app/crowd` retains timestamped mock sentiment, positioning, source lineage, sample availability, and news events. Its as-of filter excludes future observations/events; contrarian logic consumes existing diagnostic outputs rather than recreating their calculations.

## Higher-order synthesis boundary

`app/diagnostics/synthesis.py` accepts only eligible, timestamp-compatible diagnostic records in an immutable higher-order context. It synthesizes risk, trading thesis, investment thesis, and scenarios without creating new facts or accessing raw claims, scores, gates, orders, or portfolio state.

## Decision Score boundary

`app/scoring/engine.py` accepts eligible as-of diagnostics and explicit component configuration to construct a deterministic scorecard. It records component coverage, weights, raw scores, contributions, evidence, confidence, contradictions, and warnings. It has no execution, signal, gate, broker, or portfolio interface.

`StrategyGovernanceRepository` persists Decision Scorecards through an abstract boundary; the SQLite adapter stores full immutable component explanations and validates persisted diagnostic references. `AuditReconstructionService.reconstruct_decision_scorecard` recomputes from historical diagnostics and reports mismatch without altering stored truth.

## Execution eligibility boundary

`app/gates/engine.py` takes an approved as-of gate-input snapshot, an explicit exchange calendar, and an exact versioned gate configuration. It emits six independent analytical decisions and an immutable `ExecutionGateEvaluation`; its outcome is not an order, allocation, portfolio action, or signal. The repository persists these evaluations immutably with their Decision Scorecard dependency, and audit reconstruction validates that dependency and all six stored decisions.

## Portfolio state boundary

`app/portfolio/engine.py` replays an append-only mock ledger and separately stored corporate actions as-of a requested historical timestamp. It selects only eligible prices and analytics records, computes weighted-average cost, cash, holdings, P&L, allocation, sector exposure, and heat coverage, and emits an immutable snapshot. It has no candidate comparison, rotation, signal, sizing, order, broker, paper-trade, or provider interface.

## Capital-rotation boundary

`app/rotation/engine.py` compares only as-of eligible holdings and candidates, ranks transparent score/confidence/R:R tie-breaks, applies exact hurdle, anti-churn, friction, gate, sector, and portfolio-constraint checks, and persists an immutable comparison matrix. It has no portfolio mutation, signal, sizing, order, broker, or live-provider interface.

## Signal lifecycle boundary

`app/signals/engine.py` turns sufficient existing analysis into immutable non-executable setups and append-only lifecycle events. Trade plans contain explicit Rule 40–46-derived structures and machine-testable trigger conditions. Trigger detection only records `TRIGGERED_ANALYTICALLY`; it cannot create a transaction, mutate a portfolio, reserve cash, size a position, or contact a broker.

## Paper-trade boundary

`app/paper/engine.py` simulates configured hypothetical fills and outcomes from timestamped mock OHLC bars. It applies explicit slippage, costs, gap, same-bar ambiguity, target, stop, invalidation, expiry, and tranche semantics. It consumes only bars known by the requested as-of time and has no real portfolio, broker, or order interface.

## Read-only signals and paper API boundary

`app/api/signal_paper_query.py` is a thin application-facing read facade over
already-created immutable signal, trade-plan, paper-trade, paper-outcome, fill,
and PerformanceReport records. It does not import a signal/paper/performance
engine or recreate gates, prices, fills, P&L, MFE/MAE, R, or metrics. The HTTP
routes have GET endpoints only and return safe unavailable errors until a later
local runtime injects an explicit source. This does not create broker, demat,
order, live-account, promotion, or activation behavior.

## Historical replay-orchestration boundary

`app/backtest` freezes dataset/configuration references in an immutable `BacktestRun`, derives daily-close timestamps from an explicit exchange calendar, and records immutable replay steps plus append-only events. It injects the existing `BacktestLookaheadGuard` into a placeholder step context; the clock itself grants no data eligibility. The coordinator intentionally has no dependency on diagnostics, scoring, gates, portfolio, rotation, signals, paper trading, performance, or benchmarks. Audit reconstruction verifies persisted configuration, regenerated clock timestamps, step history, ordered events, and derived final lifecycle status without rewriting history.

Historical signal/paper replay adds a narrow execution-timing boundary: immutable trigger and timing contexts select when a canonical paper simulation can first consider entry, while retaining later eligible bars for trade management. It does not mutate a backtest ledger or create execution artifacts.

Historical capital allocation is the later backtest-only boundary that may translate a funded paper fill into the existing hypothetical portfolio ledger. It is isolated from real portfolios, brokers, performance reports, and benchmarks.

Its immutable sizing specification is part of the paper-config snapshot fingerprint and supplies all capital/risk inputs required to reconstruct quantity.

Historical performance integration adapts completed, frozen backtest paper outcomes to the existing Phase 7B performance and benchmark engines; it does not create an alternate metrics implementation.

Historical equity-series records bridge frozen backtest portfolio states to portfolio-level return and drawdown without introducing a second accounting engine.

The session-complete path uses `ReplayClock` and valuation-only portfolio-state reconstruction to retain no-trade day mark movements.

`app/backtest/analytical.py` is the historical replay composition boundary. It builds guard-eligible historical snapshots, uses the existing diagnostic/scoring/gate engines, and persists immutable provenance/evaluation references. It creates no execution artifacts.

`app/backtest/portfolio_gates.py` is a narrow historical contextual-gate adapter. It reads frozen analytical evaluations, holding contexts, and a backtest portfolio state, then delegates to `ExecutionGateEngine`; its immutable result retains the contextual economic/risk inputs needed for audit reconstruction. It does not select a holding, decide rotation, or create an execution artifact.

`app/backtest/rotation.py` is the corresponding historical adapter for the existing Phase 6B `CapitalRotationEngine`. It persists frozen candidate, holding, contextual-gate, portfolio, history, and configuration references, then records an analytical ranking/stance only. It has no dependency on signals, paper trades, or performance.

## Self-improvement observation boundary

`app/self_improvement` is an immutable research-only layer. It accepts only frozen source-typed observations, applies a persisted evidence policy and attribution ruleset, and writes immutable associations, recurring patterns, and summaries. Audit reconstruction verifies the same frozen chain without a latest-record fallback. It has no dependency path to strategy mutation, experiment generation, promotion, activation, brokerage, or live portfolios.

Its hypothesis sublayer may create immutable structured research proposals, rankings, and human reviews from frozen patterns. Review approval is not strategy approval and does not create an experiment; frozen target-version references become stale rather than silently retargeting after later activation.

The narrow self-improvement experiment bridge reuses the existing controlled `StrategyExperiment`, `StrategyCandidateDelta`, and complete `StrategyCandidate` records. It may create only an immutable `PLANNED` draft after exact human review and budget validation; it cannot execute, evaluate, select, promote, or activate.

The automated research cycle is the separate TRAIN/VALIDATION-only executor boundary. It rejects TEST references, preserves baseline comparability, and queues a research-selected candidate only for a later OOS scheduler.

`app/self_improvement/future_oos.py` is that scheduler's narrow handoff boundary. It validates an immutable assignment against its queued selection, candidate fingerprint, policy, and exact TEST window, then delegates to the existing Phase 8A walk-forward executor. Its result is immutable evidence only and cannot promote, approve, activate, or affect a broker or real account.

`app/feature_settings.py` is a deliberately small future-runtime capability
boundary. Its disabled-by-default `AUTOMATED_SELF_IMPROVEMENT_RESEARCH`
capability is API-ready but has no dependency on Phase 9B internals. It is not
wired into the reusable research/OOS services: a future scheduler must invoke
the guard before automatic orchestration. Reading the capability never writes
research, governance, or account records.

## Future provider adapters

Future approved adapters belong outside the domain and strategy layers. An adapter may translate a provider response into a `MarketObservation`, retain the raw source record/reference in `Provenance`, then submit it to `FoundationService`. The adapter must not bypass validation or synthesize missing provider values. No provider API shape is defined in this repository.

## Read-only performance, benchmark, and governance API boundary

`app/api/performance_governance_query.py` maps supplied immutable
`PerformanceReport`, benchmark-comparison, and promotion/activation/rollback
records. It preserves sparse and unavailable states, OOS source mode, Decimal
values, timestamps, and provenance. Routes cannot run performance/benchmark
engines, automate research/OOS, create approvals, activate/rollback a strategy,
or write broker/account data.

## Phase 10 API freeze

**PHASE 10 / #026A — PRODUCTION API FOUNDATION: COMPLETE.** The HTTP boundary
is stable and safely callable through read services. It is not yet production
deployable: SQLite remains development-oriented, authentication/tenancy and
providers/live data are absent, and no frontend is supplied.

## PostgreSQL production-persistence foundation

`app/storage/database.py` adds a lazy SQLite/PostgreSQL connection and
transaction boundary. Alembic currently migrates only immutable approved
strategy-version storage as a representative PostgreSQL contract. This is not a
full repository migration and does not change API query wiring, strategy
semantics, live-data behavior, or SQLite's role as the local/test default.

The incremental core migration uses immutable `core_api_snapshots` payloads for
current API read models. This retains exact nested structures while deferring
large normalized migrations for diagnostics, historical replay, and Phase 9B.

## #026B V1 persisted API read path

The FastAPI lifespan lazily selects a SQLite or explicitly configured PostgreSQL
`CoreApiSnapshotRepository`, then supplies repository-backed read facades unless
the application caller injected an override. The family mapping is centralized
in `app.api.repository_query_services`; HTTP routes retain their existing
contracts and do not know storage details. Deterministic stored ordering selects
current/latest compatible portfolio, regime, and symbol-scoped stock snapshots;
governance requires an explicit activation and does not infer activity from the
latest approved version. This is read-only composition: no snapshot writer,
provider, research, promotion, activation, broker, or account mutation is
introduced.

**#026B — PRODUCTION PERSISTENCE FOUNDATION: COMPLETE FOR V1 READ PATH.** This
means persisted snapshots can be served through the API and both backend
adapters/migrations exist. It does not mean all historical/research repositories
are migrated, live market data exists, PostgreSQL has been server-validated, or
the application is ready for public deployment.

## Crisis and market-dislocation architecture

`app.crisis` is a provider-neutral emergency layer over, not inside, the normal
Market Regime Engine. It consumes frozen multi-factor signals and emits an
immutable crisis assessment, a separate analytical execution override, optional
portfolio review, opportunity-watch classifications, gap-aware slippage
assumptions, and versioned future paper-trade/event contexts. It does not alter
Decision Score formulas, confidence, six gate outputs, portfolio accounting,
paper outcomes, strategy configuration, approval, activation, or live accounts.
Its snapshot families are reserved for future immutable assessment/event/context
records; no HTTP endpoint or writer is introduced.

`app.crisis.extremes` adds the independent upside tail to this composition:
market/sector/stock excess state, cycle stage, evidence confidence, leadership,
price/earnings divergence, distribution/top-confirmation semantics, and a
non-selling entry/profit-protection overlay. The combined effective policy takes
the most restrictive compatible entry/sizing constraints from upside and
downside without changing scores, gates, rotation logic, portfolio accounting,
or trade management. Events and paper contexts remain immutable snapshot-ready
contracts; no provider, endpoint, broker, or strategy mutation path exists.
## Canonical financial facts

`app.fundamentals` is a provider-neutral data-normalization layer between immutable primary filings and future analytical consumers. Its dedicated SQLite/PostgreSQL repositories preserve source, filing, revision, scope, units, basis, publication/receipt timestamps, and derived-parent lineage. Queries are point-in-time safe; financial facts do not alter diagnostic score formulas, promotion, activation, runtime, or trading.

`FundamentalsEngineAdapter` now adapts those stored facts to the existing fundamental-analysis observation contract. It is a data/input boundary: the existing diagnostic implementations, Decision Score component weights, and six gates continue to own their formulas and outcomes.
Global Datafeeds is an optional historical REST adapter. Its access key is a secure credential-store secret, readiness is not `READY` until explicit validation, and default tests make no live call.

Upstox Historical Candle V3 is an independent optional historical adapter. Its
access token is stored by the same local secure connection boundary, its V3
daily-candle values are normalized only through `HistoricalIngestionService`,
and its adjustment basis remains `UNKNOWN` unless documented action evidence
proves otherwise. It has no trading, account, or automatic-ingestion path.
## Secondary news boundary

The `app.news` package is provider-neutral.  Its GNews adapter accepts only bounded Search API JSON and persists immutable metadata in `news_evidence`.  It has a read-only API and a separate PostgreSQL-compatible store.  Publisher pages are never fetched.  News can supply factual context to the existing research/catalyst contracts but cannot directly force Crisis, Euphoria, market-regime, or scoring state.
## Primary-market facts

`app.primary_market` owns dedicated immutable issue, subscription-history, and listing-outcome storage rather than reusing generic snapshots.  Its source is local official NSE export data, with explicit provenance and no browser/network scraper.

## Public review frontend boundary

The Signals, Paper Trading, Performance, and Benchmark pages consume existing
FastAPI GET projections only. They call no lifecycle, broker, account,
promotion, approval, or activation mutation API. Performance and benchmark
detail lookup is keyed by an explicit user-selected immutable ID; the browser
does not infer a latest record or combine unrelated reports. Public schemas
omit audit provenance/evidence IDs, diagnostic and gate internals, score
weights, and secret strategy configuration. Summary-only performance contracts
are shown as KPI/table data rather than reconstructed time series.

## Public market-context read boundary

`/market/breadth`, `/market/extremes`, and `/market/crisis` are distilled GET
projections over already persisted runtime/core snapshots. Breadth reuses the
canonical breadth observation and participation snapshot; extremes reuse a
market-level `UpsideExcessAssessment`; crisis reuses `CrisisAssessment`. The
routes do not invoke aggregation, providers, state machines, or execution
policy. Their public contracts omit evidence/provenance IDs, factor lists,
weights, thresholds, diagnostics, and configuration. No stored record is an
unavailable state, never a fabricated NORMAL state; euphoria and crisis remain
environment/risk context rather than trading instructions.

## Portfolio screenshot import boundary

`app.portfolio_import` is a provider-neutral, extraction-only intake boundary.
Raw image bytes are passed only to a configured extractor during the request;
the transient draft contains only permitted candidate fields and is cleared on
confirmation, cancellation, or expiry. The default extractor is unavailable
rather than silently using third-party OCR. Confirmation requires reviewed,
resolved, positive-quantity rows and writes append-only canonical portfolio
records through the existing repository. It creates no broker action, score,
gate, diagnostic, promotion, approval, activation, or analysis run. Screenshot
LTP never becomes a canonical price mark.

## Controlled portfolio analysis jobs

`app.portfolio_analysis` records immutable revisions of explicit,
snapshot-pinned holdings-only analysis jobs in the existing core snapshot store.
HTTP only queues or reads jobs; a controlled runtime/worker must invoke
`run_next`, with no request-thread analysis, new thread, or infinite loop.
The adapter boundary is limited to the existing canonical stock-analysis/runtime
pipeline. It cannot invent candidates, so capital rotation remains unavailable
unless a separately analyzed candidate universe already exists. The internal
registry audit finds 61 definitions and wrappers, but the currently wired
historical replay executes only rules 1, 4, 5, 6, 10, and 39; therefore a live
portfolio job cannot claim 61-diagnostic completion today.

## NSE universe evidence coverage and candidate discovery

The stored-data universe path is `UniverseSnapshot → COVERAGE_PREFLIGHT →
eligibility → registry-wide analysis → score/confidence → six gates →
candidate materialization → portfolio comparison → CapitalRotationEngine`.
`UniverseInstrumentCoverage` is an immutable readiness-only record for current
quotes, historical bars, fundamentals, filings, news, ownership, market
context, and sector context. It contains no score, rank, diagnostic IDs, or
candidate decision. Jobs persist immutable stage revisions and can resume after
coverage or candidate materialization without refetching providers or creating
duplicate candidates. A candidate is derived only from that job's stored
analysis result; a held instrument is excluded from replacement candidates.
`PARTIAL` coverage means only “among the analyzed opportunity set,” never a
claim about all NSE equities. This remains analytical only: it cannot place an
order, mutate a portfolio, promote a strategy, or activate a strategy.

## Real-data readiness boundary

`app.universe_analysis.readiness.DataReadinessService` is an observational
aggregation layer. It records source readiness, provider-symbol mapping status,
stored coverage, historical lookback, and a descriptive full-scan decision.
It has no provider client and cannot run a diagnostic, import data, mutate a
strategy, or place an order. `READY_FOR_FULL_SCAN` is possible only when the
immutable universe, mappings, stored coverage, and declared source readiness
contain no explicit blockers; otherwise `NOT_READY_FOR_FULL_SCAN` names the
blockers. It deliberately uses no invented numeric completeness threshold.

The local runtime command `import-nse-universe` requires an explicit persistent
database URL for a non-dry import, and accepts only a local official CSV. The
separate `data-readiness` command performs no network validation. Provider
validation remains opt-in through the existing secure connection services and
their tiny live harnesses.

Explicit local runtime data commands use `DatabaseSettings.local_runtime()`.
Without an operator-supplied database URL it selects the relative persistent
SQLite database `data/nse_stock_manager.db`; opening the core snapshot
repository creates the parent directory and schema. API/test construction
retains its in-memory default, preserving test isolation. Status reports the
storage mode as `PERSISTENT_SQLITE`, `IN_MEMORY_SQLITE`, or `POSTGRESQL` and
checks writability without exposing a database URL or secret.
# Hardened architecture authority

The canonical detailed architecture is [Brain Architecture
v2.2-hardened](architecture/brain_architecture.md). Repository documentation and
tested implementation are authoritative over chat/memory. The hardened flow
formalizes reliability, point-in-time integrity, governance/drift, and audit
facades around existing engines; it does not replace diagnostics, scoring,
confidence, gates, capital rotation, or trading safeguards.
