# Development Roadmap

## #036 — Economic and News Intelligence (complete)

- Added immutable, point-in-time macro-state, economic-regime, sector transmission, company-sensitivity, and catalyst-context boundaries.
- The layer is evidence/context only: no Macro Score, News Score, score/gate change, direct action, provider scraping, promotion, or trading behaviour.

## #037 — Pre-Breakout and Inflection Strategy Engines (complete)

- Added versioned, deterministic candidate/setup contracts for positional
  pre-breakout and long-horizon fundamental-inflection research.
- MRS/breadth, technical filters, structural trigger/invalidation/target,
  execution-feasibility handoff, macro/sector/company/catalyst lineage, and
  separate strategy outcome-attribution contracts are append-only evidence.
- Candidates must still traverse the existing 61-diagnostic, Decision Score,
  confidence, six-gate, portfolio, rotation, and execution path. No final
  strategy action, score/gate policy change, provider call, UI, or trading was
  introduced.

## #038A — Real Data Coverage and Canonical Taxonomy (complete foundation)

- Added an append-only, provenance/effective-date taxonomy hierarchy and a
  separate evidence-backed theme-membership model with ISIN-first local import.
- Added stock-level data coverage, strategy-specific readiness, aggregate gap
  reports, and safe local CLI reporting. This is observational coverage only:
  it does not infer missing sectors, generate fundamentals, start a universe
  scan, alter any decision engine, or contact a provider.

## #038B — Historical Security Master and Corporate-Action Integrity (complete foundation)

- Added append-only historical identity/symbol interval, membership, and
  corporate-action records plus a fail-closed price-adjustment-basis guard.
- The layer preserves delisted/renamed identities and exposes missing
  historical membership/action sources in coverage. It does not rewrite bars,
  run a backtest, modify indicators, or alter trading/scoring logic.

## #038C — Controlled Real-Brain Trial (complete)

- Added one explicit 30–50 stock, snapshot-bound, stored-evidence-only trial
  with deterministic taxonomy-aware/hash fallback selection and append-only
  audit records.
- It measures coverage, canonical 61-diagnostic execution, valid existing
  score/confidence availability, readiness, blockers, and observed runtime.
  Missing domains remain partial/unavailable; it performs no provider fan-out,
  full-universe scan, alpha claim, strategy tuning, candidate selection,
  rotation, gate execution, or trading.

## #038D — Minimum Viable Real Data Package (complete, source-blocked)

- Added frozen-cohort replay support so evidence ingestion can be compared
  against exactly the original 40 instruments, even after later taxonomy data.
- Coverage now recognizes stored NIFTY 500 (with explicit legacy NIFTY 50
  fallback) as shared market context and keeps raw history `PARTIAL` when
  corporate-action provenance remains absent.
- The local implementation is intentionally source-blocked rather than
  fabricated: GDFL, taxonomy, and historical cohort data must be supplied and
  validated through existing canonical boundaries before the real trial can
  improve.

## #035 — Live-Readiness Risk Hardening (candidate)

- Adds measurement and fail-closed research/safety facades for reconciliation,
  evidence coverage, friction/feasibility, calibration, redundancy/ablation,
  factor concentration, event clustering, and structured AI containment.
- `Brain Architecture v2.2-hardened` remains the approved version pending full
  validation and review of the `v2.3-live-readiness` candidate.

## #032 — Full NSE opportunity orchestration

Registry-wide NSE equity orchestration is backed by canonical stored data with
bounded/resumable batches and explicit partial coverage. Universe, market data,
fundamentals, filings, news/ownership, market context, diagnostic execution,
and opportunity-set readiness remain separate; no automatic trading or
strategy governance mutation is introduced.

## #032B — Universe population and portfolio-to-universe rotation

Supported scope is imported NSE main-board equities only. Immutable universe,
candidate, and portfolio-universe rotation snapshots bind the current portfolio
to its exact analyzed universe. `PARTIAL` results are never presented as the
best NSE opportunity.

## #028B — Scheduler and runtime-health foundation (complete)

- Added a disabled-by-default, synchronous in-process scheduler facade around
  the existing explicit runtime-cycle coordinator.
- `run_once()` is manually invocable; FastAPI startup remains inert. Safe
  session skips, overlap prevention, bounded failure recording, and read-only
  runtime health are implemented without network, broker, account, control API,
  CLI, or Phase 9B automation.
- Timer/worker/CLI orchestration remains deferred to #028C.

## #028C — CLI, controlled worker, and runtime-status closure (complete)

- Added local `run-once`, `status`, `validate-config`, and opt-in `worker`
  commands. Dry runs use the existing no-publication cycle path.
- Added one cooperative local timer worker and read-only versioned runtime
  status. FastAPI still starts no worker and exposes no runtime control route.
- Host data/universe composition and real-provider runtime validation remain
  deferred; no broker/trading or strategy automation was added.

## #029A — Real data composition and source readiness (complete)

- Added provider-neutral source-family capability, explicit-priority, freshness,
  PIT, provenance, readiness, and runtime-composition contracts.
- Added a sanitized read-only source-status endpoint. Kotak historical remains
  explicitly unsupported, while future fundamentals/filings/news/IPO sources
  remain unconfigured slots.
- No provider fetch, scrape, credential mutation, broker, frontend, or strategy
  automation was added.

## #029B — Primary-source filings and announcements foundation (complete)

- Added immutable NSE/BSE/issuer-ready filing facts, attachment metadata,
  revisions, PIT queries, deterministic mock ingestion, SQLite/PostgreSQL store
  contracts, and a dedicated migration.
- Added read-only filing list/detail views and source-readiness boundaries.
  Live NSE/BSE validation, document retrieval, XBRL parsing, and statement
  extraction remain deferred.

## Phase 8B.1 — Walk-forward OOS execution foundation (complete)

- Immutable deterministic ROLLING/EXPANDING plan, candidate, window, run, and window-result records.
- Clean OOS V1 TEST runs reuse Phase 8A and start independently; no TRAIN state inheritance.
- Fixed-candidate freeze, optional frozen benchmark linkage, coverage derivation, and audit checks are in scope.
- Aggregate OOS metrics, optimisation, promotion, and self-improvement remain out of scope.

### OOS aggregation and stability closure (complete)

- TEST-only chained-return equity stitching, coverage accounting, pooled frozen trade metrics, stability diagnostics, and optional pre-TEST degradation evidence.
- Immutable aggregate persistence, configuration, benchmark-session provenance, and audit reconstruction.
- Parameter search, candidate promotion, and self-improvement remain out of scope.

## Phase 8B.2 — Controlled candidate experiments (complete)

- Explicit bounded candidate variants, transparent deltas, TRAIN/VALIDATION evidence, local robustness checks, and frozen candidate selection.
- TEST leakage is rejected; no automatic promotion or self-improvement is implemented.

This roadmap builds NSE Stock Manager incrementally. Each phase must have testable acceptance criteria and must preserve the safety boundaries in the master specification.

## Phase 0 — Project foundation (current)

- Create the master specification, roadmap, and minimal README.
- Confirm the repository contains no market-data integration, live trading, autonomous execution, or assumed external APIs.
- Identify unresolved requirements before implementation begins.

**Exit criterion:** planning documents are present and internally consistent.

## Phase 1 — Domain model and mock-data foundation

- Choose the implementation stack and test framework.
- Define provider-independent domain models for instruments, market observations, provenance, freshness, data quality, validation, and as-of snapshots.
- Add deterministic mock/test fixtures covering valid, stale, incomplete, and invalid data.
- Implement ingestion validation and audit-friendly storage abstractions.

**Exit criterion:** mocked observations can be validated, versioned, retrieved as-of a timestamp, and rejected/qualified when insufficient.

## Phase 2 — Strategy governance and audit records

- Define strategy-version, evidence, diagnostic-result, scorecard, gate-decision, signal, and paper-trade record models.
- Establish immutable/superseding record behavior and traceability links.
- Add configuration/version checks and test audit reconstruction from fixtures.

**Exit criterion:** a decision record can be reconstructed from data snapshot, evidence, and strategy version.

## Phase 3 — Initial analytical slice

- Implement a narrow, mock-data analysis slice: market regime, basic technical/relative-strength calculations, and explicit missing-data behavior.
- Add parameter/version metadata to every derived indicator.
- Do not claim or implement the full 61-point diagnostic engine until all rules are defined.

**Exit criterion:** deterministic analysis outputs with source evidence, confidence, and unit tests.

## Phase 4A — Canonical diagnostic registry and scoring policy (current)

- Define and version the exact 61 diagnostic checkpoints, their metadata, and evaluation classification.
- Define the distinct 10-component 0.0–10.0 Decision Score policy, separate data confidence, and default no-renormalization missing-data policy.
- Define six execution gates, research/catalyst hierarchy, benchmarks, and improvement governance without implementing their calculations.

**Exit criterion:** canonical definitions are complete, internally validated, and immutable strategy versions can reference their version identifiers.

## Phase 4B — Diagnostics and scoring evaluation

### Phase 4B.1 — First deterministic evaluators (complete)

- Implement only Rules 1, 4, 5, 6, 10, and 39 by reusing Phase 3 deterministic engines.
- Preserve separate eligibility, outcome, confidence, evidence, and no-look-ahead controls.
- Provide component contribution eligibility only; do not calculate component or aggregate scores.

**Exit criterion:** approved diagnostic outputs are deterministic, auditable, and fail closed on unavailable inputs.

### Phase 4B.2 — Sector, volume, and Ichimoku evaluators (complete)

- Implement Rules 2, 3, 11, 12, 13, 14, 35, and 36 through reusable pure analysis engines.
- Preserve as-of-only input, deterministic evidence, separate component eligibility, unavailable volume-at-price handling, and proxy-safe sector/volume wording.
- Test determinism, exact Chikou displacement, explicit anti-look-ahead, and raw-snapshot contamination failure for every new rule.

**Exit criterion:** all eight outputs are deterministic and auditable from mock OHLCV inputs; Decision Scores, fundamentals, and earnings remain out of scope.

### Phase 4C.1 — Deterministic fundamentals and earnings (complete)

- Implement mock filing-only Rules 16–22 and 24–27 with publication-time as-of controls, restatement lineage, evidence, and component eligibility.
- Preserve annual/quarterly period semantics, explicit missing/not-applicable behavior, and no numerical Decision Score.

**Exit criterion:** fundamental outputs are reproducible from filings known at the requested as-of time; qualitative moat, governance, management, and valuation remain out of scope.

### Phase 4C.2 — Research intelligence and first qualitative diagnostics (complete)

- Add deterministic mock research documents, claims, source tiers, research as-of snapshots, guidance ledgers, and catalyst records.
- Implement only Rules 15, 23, 28, and 30 with evidence-driven hybrid outputs.

### Phase 4D — Valuation and trade structures (complete)

- Implement Rules 29, 37, 38, and 40–46 as deterministic, as-of analytical plans only.
- Keep entries, stops, targets, and R:R distinct from signals, orders, gates, and portfolio decisions.

### Phase 4E.1 — Smart money, liquidity, and Wyckoff foundation (complete)

- Implement Rules 7–9, 50–54, and 58 from deterministic mock price/volume proxies only.
- Preserve as-of event sequencing and prohibit claims of direct institutional activity, observed stops, or factual absorption.

### Phase 4E.2 — Crowd versus smart money / contrarian engine (complete)

- Implement Rules 47–49, 55–57, and 59–61 using deterministic mock crowd, news, market, and existing diagnostic evidence.
- Preserve duplicate control, low-confidence restraint, post-publication reaction timing, and non-executable verdicts.

### Phase 4F — Final higher-order diagnostics (complete)

- Implement Rules 31–34 as traceable synthesis of eligible upstream diagnostics.
- Keep risk matrices/scenario weights as model constructs and keep all theses non-executable and separate from the future Decision Score.

### Phase 5A — Canonical Decision Score engine (complete)

- Implement the configured ten-component 0.0–10.0 analytical scorecard with separate confidence, warnings, and no-renormalization missing-data handling.
- Preserve scorecard non-execution boundaries; gates and portfolio decisions remain future work.

- Use the approved canonical registry and implement/test diagnostic evaluators incrementally.
- Implement the 10 weighted scoring dimensions, confidence/missing-data policy, and score aggregation.

**Exit criterion:** every score is traceable to diagnostic evidence and an approved strategy version.

## Phase 5B — Six analytical execution gates (complete)

- Implemented versioned score-advantage/friction, capital-velocity, surveillance, trade-plan, heat, and trading-session earnings-blackout gates.
- Persisted and audit-reconstructed immutable eligibility evaluations while retaining raw Decision Scores separately from velocity adjustments.
- No portfolio rotation, signals, sizing, paper trading, broker, or provider integration is part of this phase.

## Phase 6A — Portfolio state and holdings foundation (complete)

- Implemented immutable portfolios, cash, append-only mock ledger/corporate actions, weighted-average cost reconstruction, as-of valuation, P&L, exposures, and heat coverage.
- Kept portfolio state strictly descriptive. Rotation, signals, sizing, paper trading, brokers, and live data remain future work.

## Phase 6B — Capital rotation decision engine (complete)

- Implemented immutable candidate/holding comparisons, transparent matrix/ranking, cash alternative, friction and anti-churn controls, and non-executing rotation stances.
- No signal, sizing, portfolio mutation, paper-trade, broker, or provider work is included.

## Phase 6C — Signal lifecycle and trade-plan orchestration (complete)

- Implemented immutable analytical signals, Rule 40–46 trade-plan records, machine-testable triggers, append-only lifecycle events, WAIT/CASH behavior, and as-of revalidation.
- No fill, outcome, sizing, portfolio mutation, broker, or provider capability is included.

## Phase 7A — Deterministic paper-trading lifecycle (complete)

- Implemented provider-independent hypothetical setup, trigger, fill, stop/target, expiry, gap, ambiguity, MFE/MAE, and outcome simulation.
- No real fill, portfolio mutation, broker, live data, benchmark, or self-improvement capability is included.

## Phase 7B — Future performance and benchmark evaluation

- Implement portfolio state, cash allocation, position-risk calculations, and exposure/heat limits.
- Implement the six mandatory execution gates with pass/fail/insufficient-data states.
- Add candidate-vs-holding rotation logic, including versioned +0.7 to +1.0 threshold and minimum 1:2 structural risk/reward.

**Exit criterion:** only candidates meeting all gates and rotation requirements become eligible signals in test fixtures.

## Phase 6 — Signal and paper-trading lifecycle

- Create eligible-signal and paper-trade records with all required fields.
- Implement fixture-based monitoring for MFE, MAE, exits, R multiples, holding period, and exit reasons.
- Add reports for signals blocked by risk or gates.

**Exit criterion:** an end-to-end mock paper trade is auditable from signal creation through closure.

## Phase 7 — Benchmarking and validation

- Implement reproducible backtesting, realistic friction/fill assumptions, and anti-bias safeguards.
- Add walk-forward and out-of-sample validation.
- Add the defined benchmark comparisons and regime-specific reporting.

**Exit criterion:** a versioned strategy can be evaluated against documented benchmarks without look-ahead or data leakage.

## Phase 8 — Improvement workflow

- Analyze paper-trade history for setup, regime, sector, diagnostic, scoring, and rotation weaknesses.
- Generate reviewable hypotheses and experiment records.
- Enforce the validation-to-review-to-new-version promotion workflow.

**Exit criterion:** the system can propose an improvement but cannot silently alter production behavior.

## Phase 8A.2 — Replay clock and event-log foundation (complete)

- Implemented immutable run/schedule/data-gap records, deterministic daily-close timestamps, partition boundaries, append-only replay steps/events, lifecycle validation, and audit reconstruction.
- The placeholder coordinator is explicitly non-analytical and non-trading. It only demonstrates guard rejection and data-gap behavior with deterministic fixtures.
- Chronological strategy replay, backtest outcomes, walk-forward validation, optimization, and all analytical/trading integrations remain future work.

## Phase 8A.3 — Historical analytical replay (complete)

- Added point-in-time snapshot orchestration through canonical diagnostic artifacts, Decision Scorecards, and execution-gate evaluations.
- Missing history remains explicit; portfolio-dependent gates remain insufficient pending a separately approved portfolio replay.
- Signals, rotation, trades, performance, benchmarks, optimization, and walk-forward validation remain out of scope.

## Phase 8A.4A — Historical portfolio context gates (verification complete)

- Added immutable contextual re-evaluation of canonical Gates 1 and 5 from frozen analytical and portfolio references, including audit reconstruction and append-only events.
- No capital-rotation, weakest-holding, cash-selection, signal, trade, or benchmark decision has been added.

## Phase 8A.4C — Historical capital rotation replay (complete)

- Added frozen historical adaptation to the canonical Phase 6B capital-rotation engine, immutable rotation context/history/evaluation persistence, and audit reconstruction.
- The output remains analytical only: no ledger movement, signal, paper trade, fill, performance, benchmark, optimization, or walk-forward behavior.

## Phase 9 — Human-facing interfaces

## Phase 9A.1 — Deterministic self-improvement observation (complete)

- Added frozen deterministic association, recurring-pattern, and descriptive summary records.
- The result remains research-only: no hypothesis creation, experiments, strategy mutation, promotion, activation, broker, or live-account action.

## Phase 9A.2 — Structured hypothesis generation and review (complete)

- Added immutable policy-qualified research hypotheses, rankings, and human review records.
- `APPROVE_FOR_EXPERIMENT` remains a review of research only; controlled experiments, candidates, promotion, and activation are deferred.

## Phase 9A.3 — Human-approved hypothesis bridge (complete)

- Added a bounded bridge from exact human-reviewed hypotheses to existing `PLANNED` controlled-experiment drafts.
- Execution, evidence, selection, promotion, and activation remain deferred.

## Phase 9B.1 — Automated controlled research (complete)

- Frozen human-approved experiment drafts execute only on permitted TRAIN/VALIDATION partitions and may queue a selected candidate for later OOS work.

## Phase 9B.2 — Future OOS assignment and execution (partially complete / deferred)

- Immutable assignment policies and assignments enforce an exact research-selected candidate/configuration fingerprint and strict pre-TEST chronology.
- The handoff reuses the existing clean TEST walk-forward executor and retains immutable OOS evidence plus audit reconstruction.
- OOS results remain evidence only: no automatic promotion, approval, activation, broker access, or real-account effect.

- Automatic Phase 9B production orchestration is not currently present. Its
  future runtime capability is disabled by default and is non-blocking for
  production app development.
- Remaining deferred closure: exact-run performance-integration verification,
  lifecycle closure, tamper matrix, future-input immutability matrix, and final
  documentation closure.

- Added immutable TRAIN/VALIDATION research runs, cycle results, and future-OOS queue records.
- TEST/OOS execution, promotion, activation, and live behavior remain prohibited.

- Build dashboard/API views for provenance, scores, trades, benchmarks, alerts, and strategy versions.
- Optionally design a Google Sheets paper-trading view after authentication, ownership, synchronization, and conflict rules are approved.

**Exit criterion:** users can inspect the full evidence chain and current paper-trading state.

## Phase 10 — Approved external integrations (future)

### Phase 10A.1 — FastAPI application skeleton (complete)

- Added a provider-independent FastAPI application factory with liveness and
  versioned system-status routes only.
- API settings and the existing disabled-by-default Phase 9B feature setting
  are exposed safely without invoking research or OOS services.
- Authentication, domain APIs, live providers, brokers, and external
  integrations remain future work.

### Phase 10A.2 — Read-only portfolio API (complete)

- Added injected, read-only endpoints for an existing immutable portfolio
  snapshot, holdings, and dashboard summary.
- No portfolio mutation, broker/demat synchronization, live marks, auth/user
  tenancy, or rotation execution was introduced. Current-rotation querying is
  deferred until a coherent local query contract exists.

### Phase 10A.3 — Read-only market-regime and sector API (complete)

- Added injected API representations of existing market-regime and sector
  diagnostics, preserving enum states, confidence, timestamps, and provenance.
- No live provider, market/sector calculation, configuration override, ranking
  mutation, automated research, or OOS execution was introduced.

### Phase 10A.4 — Read-only stock analysis API (complete)

- Added an injected stock-detail presentation of existing diagnostics, Decision
  Scorecard, gate evaluation, and optional grouped analytical evidence.
- No live provider, analytical recomputation, strategy/portfolio mutation,
  research execution, broker integration, or exchange-symbol mapping was added.

### Phase 10A.5 — Read-only signals and paper-trading API (complete)

- Added injected signal list/detail, simulated paper-trade list/detail, and
  stored paper-performance GET endpoints.
- Existing signal/paper lifecycle and outcome values, including partial/open
  records and Decimal evidence, are presented unchanged. No signal generation,
  fill/exit operation, live execution, broker/demat integration, promotion, or
  activation behavior was introduced.

- Select and approve data providers, then implement tested provider adapters.
- Monitor freshness, quality, rate limits, provider failures, and reconciliation.
- Consider brokerage or order-execution capabilities only under a separate, explicit security and operational design; autonomous execution remains out of scope unless separately authorized.

**Exit criterion:** integrations meet the provider-independent, provenance, validation, and safety requirements.

## Decisions required before later phases

- Full definitions of the 61 diagnostic rules.
- Score scale, normalization, confidence aggregation, and missing-data policy.
- Exact rotation threshold within +0.7 to +1.0 and when exceptions are allowed.
- Instrument universe, liquidity thresholds, timeframes, trading calendar, and market-session conventions.
- Position-sizing, stop/target, friction/tax, slippage, and fill-assumption models.
- Definition/data source for surveillance, circuits, earnings dates, institutional proxies, SMC, and trader-like benchmark.
- Data retention, privacy, authentication, deployment, and review/approval ownership.
# Historical execution timing

Historical signal/paper replay now freezes trigger knowledge and execution-window selection. Ledger mutation, allocation, performance, benchmark, optimization, and walk-forward work remain outside this boundary.

Historical paper-fill allocation and ledger integration is now backtest-only. Performance, benchmark, optimization, and walk-forward work remain out of scope.

Frozen fixed-notional and fixed-risk-R sizing is available for historical allocation; later configuration changes cannot rewrite prior quantities.

Frozen historical backtest outputs can now be reported through the existing performance and benchmark engines. This remains in-sample reporting, not walk-forward validation or optimization.

Historical session-end mark-to-market equity series now provide portfolio capital-path reporting for completed backtest runs.

Session-complete daily valuation now includes no-trade market-movement days in return and drawdown paths.

### Phase 10A.6 — Read-only performance, benchmark, and governance API (complete)

- Added injected list/detail views for stored performance reports, benchmark
  comparisons, immutable strategy versions, explicit activations, promotion
  review lineage, and rollback references.
- No API route runs metrics, benchmarks, OOS/research, promotion, activation,
  rollback, broker, or real-account behavior.

### Phase 10A.7 — API hardening and freeze (complete)

- Verified GET-only routes, safe errors/request IDs/CORS/OpenAPI, injected
  dependencies, enum/Decimal/timestamp preservation, and isolation from live
  providers, brokers, accounts, and Phase 9B runtime.
- **PHASE 10 / #026A — PRODUCTION API FOUNDATION: COMPLETE.**

## Phase 10B — PostgreSQL production persistence

### Phase 10B.1 — PostgreSQL persistence foundation (complete)

- Added lazy typed database settings, explicit transaction/readiness boundary,
  Alembic infrastructure, and an initial immutable approved-strategy-version
  PostgreSQL migration/adapter.
- SQLite remains the default and full-suite authority. All other repository
  families, API repository wiring, and PostgreSQL integration validation await
  later explicitly scoped migrations.

### Phase 10B.2 — Core production repository migration (complete)

- Added a backend-agnostic immutable, schema-versioned core API read-snapshot
  contract and SQLite/PostgreSQL adapters for portfolio, analysis, signal,
  paper, performance, benchmark, and governance read families.
- API routes remain injected/read-only; PostgreSQL server validation and wider
  normalized/historical/Phase 9B repository migrations remain deferred.

### Phase 10B.3 — API query-source wiring and database freeze (complete)

- The existing read-only FastAPI facades now default to the immutable core API
  snapshot repository through lifespan/DI, while direct test/caller overrides
  remain supported.
- SQLite is the local default and PostgreSQL is explicit/lazy. No writer,
  migration-on-startup, provider, research, promotion/activation mutation, or
  broker/live-account behavior was added.
- **#026B — PRODUCTION PERSISTENCE FOUNDATION: COMPLETE FOR V1 READ PATH.**
  Real PostgreSQL-server validation and broader repository migration remain
  deployment/future-scope gates.

### #026C — Crisis and market-dislocation engine architecture foundation (complete)

- Added provider-neutral crisis states, multifactor assessment/transition
  contracts, analytical execution overlay, opportunity/portfolio/slippage/paper
  context records, versioned crisis events, and frontend-safe dashboard data.
- The engine is architecture-only: no live input, threshold calibration, API
  endpoint, execution, strategy mutation, or Phase 9B runtime activation.

### #027A — Production market-data contracts and canonical foundation (complete)

- Added provider-neutral canonical identity, explicit provider mappings,
  quote/OHLCV/index/breadth/participation/session contracts, quality/freshness/
  provenance metadata, capability/error/settings/registry boundaries,
  deterministic static provider, normalization, and append-only local/test
  store/writer.
- No real provider, network, broker, WebSocket, scheduler, API endpoint,
  strategy formula, Crisis/Euphoria calculation, or runtime activation was
  introduced.

### #027B — Real/current provider adapter integration

#### #027B — Kotak Neo V1 read-only adapter (complete)

- Added a current-Neo consumer-key/TOTP/MPIN/dynamic-baseUrl adapter for
  explicitly mapped instruments and documented single/batch quote data.
- Historical/intraday bars, direct breadth/session endpoints, WebSocket runtime,
  scheduler/ingestion, and all account/trading capability remain deferred.

#### #027B.2 — Kotak Neo connection profile and secure credential adapter (complete)

- Added a provider-neutral local/private connection profile, OS-keyring
  credential store, redacted status/audit contract, and quote-only/session-read
  form metadata. Normal user setup no longer requires environment variables.
- Isolated settings endpoints only save/test/clear credentials. They create no
  scan, account query, order, strategy promotion, or activation and are not
  publicly deployable before authentication is designed.

### #027C — Mocked streaming market-data runtime foundation (complete)

- Added provider-neutral subscription, explicit reconnect/backoff, heartbeat
  health, and canonical quote-write contracts with deterministic mocked feed
  tests.
- Kotak streaming payload normalization is available through an injected-frame
  boundary only. Real WebSocket transport is opt-in and deliberately pending
  provider-contract and credential-runtime validation; no network, scheduler,
  account, order, strategy, or portfolio effect was added.

### #027D — Historical OHLCV ingestion and storage foundation (complete)

- Added provider-neutral canonical historical-bar ingestion, validation,
  deterministic chunk plans, coverage/gap reporting, conflict handling, and
  SQLite/PostgreSQL dedicated bar-store contracts/migration.
- No historical provider endpoint, file-import UI, scheduler, worker, analysis,
  signal, portfolio, governance, broker, or live-account action was added.

### #027E — Index, VIX, and market-breadth aggregation foundation (complete)

- Added provider-neutral index/VIX access, point-in-time universe membership,
  deterministic breadth/sector-compatible aggregation, coverage/freshness, and
  raw participation/leadership inputs.
- No provider, scheduler, public endpoint, regime/crisis/euphoria score, or
  account/trading/governance mutation was added.

- Future validated, point-in-time market, breadth, volatility, liquidity, and
  exchange-status feeds may supply the crisis contracts.
- It must also support future timestamped/provenanced OHLCV, indices, breadth,
  VIX, valuation/fundamental, ownership/OFS, IPO/primary-market, narrative, and
  retail/participation inputs for the upside market-extremes contracts.
- Crisis production calibration/runtime activation occurs only after those feeds
  and historical validation are separately approved.

### #026D — Market extremes upside excess/euphoria foundation (complete)

- Added market/sector/stock upside assessment, euphoria/distribution/breakdown
  lifecycle, leadership/divergence/IPO/narrative contracts, non-selling overlay,
  combined downside/upside policy, and immutable event/paper-context records.
- No live input, provider choice, calibration claim, automatic sell, rotation,
  strategy mutation, endpoint, or execution behavior was added.
### #029C — Canonical financial statements and fundamentals (complete foundation)

- Structured filing/result inputs now normalize into immutable PIT-safe reported facts plus conservative derived metrics/snapshots.
- The dedicated fact store, migration, PostgreSQL adapter boundary, source-readiness declaration, and read-only API are in place.
- XBRL/PDF extraction, live fundamental providers, consensus estimates, and scoring integration remain separate future work.

### #029D — Canonical fundamentals to existing stock analysis (complete wiring)

- Added the sole PIT-safe, scope-consistent adapter from stored financial facts/filings to existing financial-observation diagnostics and an opt-in runtime STOCK-stage publication hook.
- No score, diagnostic, gate, catalyst-strength, valuation, provider, or trading formula changed. Missing/conflicting facts remain partial rather than fabricated.
### #029F — Global Datafeeds historical provider (complete)

- Optional documented GDFL historical OHLCV adapter, secure profile, explicit provider selection, canonical ingestion, and offline validation are available. Live credentials and validation remain opt-in; GDFL fundamentals are deferred.
## #029G — News/research evidence V1

Optional machine-readable GNews metadata is integrated as secondary evidence with PIT controls, provenance, deduplication, and primary-filing precedence.  Live validation remains opt-in because an API key and plan entitlement are external prerequisites.  No web scraping, scoring change, or trading behavior is introduced.
## #029H — Primary-market evidence

Official local NSE IPO/issue exports now flow into immutable, PIT-aware primary-market records and the pre-existing IPO intensity input boundary.  Automatic live ingestion, PDF parsing, and any IPO/euphoria scoring are intentionally out of scope.

## #031D — Public capital-rotation read model (complete)

- Added a read-only public projection over stored canonical capital-rotation
  evaluations and the `/api/v1/capital-rotation` endpoint.
- The response is explicitly distilled: it contains published comparison values
  and analytical labels, never diagnostic internals, gate IDs, component
  weights, threshold derivations, or execution capability.
- The frontend now renders backend-provided READY/PARTIAL/EMPTY/UNAVAILABLE
  states without mock fallback in API mode and has no order controls.

## #031E — Portfolio and stock intelligence frontend (complete)

- Portfolio renders the exact summary/holdings read contract, including public
  realized P&L, warnings, and a read-only Capital Rotation link.
- Added a minimal persisted `GET /stocks` read endpoint and exact frontend
  mapping; neither list nor detail runs analysis or scans the market.
- Stock detail renders only public distilled status/context and section
  availability. Audit provenance and proprietary diagnostic/gate details remain
  excluded.

## #031F — Signals, paper trading, performance, and benchmark frontend (complete)

- Exact read-only frontend bindings now cover public signal, paper-trade,
  performance-report, and benchmark-comparison contracts.
- Report and comparison selection is explicit; summary-only contracts do not
  produce fabricated charts or browser-calculated analytics.
- Public API projections exclude diagnostic/evidence/provenance IDs and no
  trading, promotion, approval, or activation mutation path was introduced.

## #031G — Dashboard market context (complete)

- Added read-only, distilled snapshots for canonical market breadth,
  market-extremes/euphoria, and crisis/dislocation outputs.
- Dashboard consumes exact GET routes and preserves unavailable, partial, and
  stale semantics. No market analytics run in the browser.
- Euphoria is not a market-top/SELL signal, and crisis is not an automatic
  liquidation instruction.

## #031H — Portfolio screenshot import + backend analysis intake (complete)

- Added a review-first temporary screenshot draft flow with conservative
  duplicate/symbol handling and explicit user confirmation before append-only
  portfolio persistence.
- Import remains data ingestion only: it does not supply canonical market data
  or trigger diagnostics, scoring, gates, rotation, broker, or account actions.
  Portfolio analysis remains a separate backend-cycle concern.

## #031I — Controlled portfolio analysis job (complete)

- Added explicit, idempotent, snapshot-pinned holdings-only job records and
  public-safe status routes. Jobs are queued and executed only through a
  controlled runtime boundary; no browser or HTTP request executes analysis.
- The canonical registry contains 61 definitions, but the current end-to-end
  orchestration does not execute all 61 for a live portfolio. Completeness stays
  `PARTIAL`/`UNAVAILABLE` rather than being manufactured. Full NSE universe
  scanning remains a separate future phase.

## #032B.2 — Evidence coverage + true universe candidate discovery (complete)

- Added immutable per-instrument coverage preflight and durable universe job
  stages through candidate materialization and portfolio comparison.
- A stored canonical fixture now proves all applicable 61 diagnostic wrappers
  can complete when every supported canonical evidence domain is present; an
  absent domain remains `PARTIAL`, not neutral.
- Candidate records are materialized solely from a completed universe job and
  handed to the existing capital-rotation engine. No shortlist, order, broker,
  strategy-promotion, or activation path was added.

## #033 — Real data readiness + live universe population (in progress)

- Local official-NSE universe CSV import and dry-run validation are available.
- Stored-data readiness aggregates source declaration, canonical mappings,
  coverage, and historical lookback without provider fan-out.
- A bounded real sample/full scan remains explicitly blocked until local
  imports, mappings, provider validation, and stored canonical coverage prove
  readiness. No full live scan is automatic.

## #033B — Persistent database + first official universe import (in progress)

- Explicit local data commands now default to persistent relative SQLite and
  report storage mode/readiness across a restart.
- Official universe imports are dry-run capable and checksum-idempotent; no
  official file is bundled or downloaded. A real import awaits a user-supplied
  official NSE CSV.
# #034 — Hardened Brain Architecture (complete)

- Added repository-authoritative architecture specification and change-control
  documents under `docs/architecture/`.
- Formalized thin reliability/fallback, historical-integrity, governance/drift,
  and internal decision-audit facades using existing snapshots and guards.
- No diagnostic formula, Decision Score, confidence, gate, rotation, provider,
  broker, or deployment behavior changed.
