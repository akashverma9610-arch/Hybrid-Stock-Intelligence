# HSI / SenseEdge — Master Engineering Instructions V2.1
**Status:** PROPOSED — review and approve before application-code changes.
**Authoritative development repository:** `akashverma9610-arch/Hybrid-Stock-Intelligence`
**Secondary source:** `akashverma9610-arch/HSI-Agent-Lite` is read-only reference/migration knowledge, not a separate product, runtime or calculation authority.
**Purpose:** Extend and reconcile the existing HSI, not replace it. This is a target engineering directive, not proof that every feature is already operational.

## 1. Single-repository law
All accepted PRD, TRD, architecture, database migrations, implementation, frontend, tests, research evidence, analytical AI integration, pattern intelligence and deployment instructions belong in this repository. Prefer `docs/master/` for new master specifications; link to existing authoritative docs instead of duplicating or silently overwriting them. No new competing HSI repository or independent Lite service.

**Local Windows copy:** The owner's D: working tree is a local clone of this GitHub repository, not a separately editable environment accessible from ChatGPT. Before local integration, Claude Code must inspect `git status --short`, `git branch -vv`, `git remote -v`, `git fetch origin`, and `git log --oneline --left-right --cherry-pick HEAD...origin/main`. Preserve uncommitted changes. Never blindly pull, reset, force-push or assume local and GitHub are synchronized. Prefer reviewed PR -> merge -> fast-forward local branch, only after checking divergence.

## 2. Source authority and approvals
1. Owner's latest explicit decisions, with conflicts escalated.
2. Approved, active Core V1 runtime contracts: canonical 61 diagnostics, decision score, six execution gates, strategy governance, portfolio protections.
3. Verified implementation, migrations, executable tests and source receipts at inspected commit.
4. Historical audits with their original dates/commit pins.
5. Lite PRD/TRD, 35-lens taxonomy and crosswalk: **proposed, not automatically active**.
6. This V2 target design for changes requiring implementation and acceptance.

Never promote V2 gate policies, proposed Lite strategies or draft lenses based on matching names. Do not interpret audit-only records as current production certification.

## 3. Include — scope of unified HSI
- **Universe and identity:** eligible NSE main-board equities, official universe snapshot, ISIN/symbol/corporate-action mapping, explicit excluded instruments and reasons; coverage denominator and FULL/PARTIAL status.
- **Data lifecycle:** controlled source adapters; market OHLCV, delivery, fundamental statements, filings, corporate actions, macro, sector and catalysts; initial backfill as permitted and available; daily/intraday/event incremental acquisition; retries, deduplication, checkpoints, lineage, freshness, reconciliation and PIT known-at guards.
- **Persistent intelligence database:** raw immutable observations, normalized evidence, derived indicators, diagnostic outcomes, strategy matches, provenance, versioned cache, snapshots and audit receipts. PostgreSQL is a target where supported; do not presume migration completeness.
- **Deterministic shared engines:** technicals (including Ichimoku), fundamentals, valuation, sector/regime, relative strength, liquidity, smart-money/SMC, risk geometry, event evidence. One authoritative owner per primitive; compute once for identical source/version/timeframe/as-of keys; invalidate when inputs change.
- **Pattern Intelligence:** candlestick geometry and named single/multi-candle patterns; chart bases, flags, pennants, triangles, wedges, channels, VCP, cup-and-handle, head-and-shoulders, double tops/bottoms; bullish/bearish continuation and reversal; confirmation, breakout/retest, traps, failed patterns, multi-timeframe confluence, calibrated historical performance. Avoid look-ahead and overlapping-pattern double-counting. Pattern presence is not an order signal.
- **61 diagnostics:** retain existing canonical registry and governed availability semantics. D35 and D57 require special reconciliation; do not silently replace them with Lite definitions.
- **35 lenses:** import only verified canonical dependencies and proposed taxonomy, six families, shared diagnostic outputs and strategy evidence; each lens has required/optional/context dependencies and activation status. Missing required evidence blocks a confident verdict, not all unrelated lenses.
- **Score, confidence and gates:** preserve approved V1 10-point score weights and six gates. Keep score, confidence, source coverage, policy readiness and actionable status distinct.
- **Discovery:** whole-universe eligibility -> inexpensive deterministic candidate detection -> candidate union -> bounded deep research -> strategy confluence -> risk and portfolio-fit evaluation; no expensive AI per NSE stock.
- **Independent Analytical AI:** separate from legacy shared Brain, uses evidence-grounded RAG/agent tools for qualitative synthesis, conflicting-source analysis and citations. Deterministic code owns indicators, score, gates and numerical risk. No hallucinated facts, hidden policy changes or autonomous orders.
- **User experience:** Home, Scan, Analyse, Watch, Portfolio, data health, explainable pattern displays, provenance, risk flags, mobile-responsive views, alerts and accessible Hindi/English descriptions where supported.
- **Portfolio intelligence:** holdings, cash, concentration, sector heat, thesis breaks, liquidity/exitability, scenario and rotation comparisons, tax/cost awareness and explicit human approval. No forced sale solely to rebalance.
- **Validation and operations:** security/auth/roles, migrations, backups, observability, regression, source-contract tests, deterministic replay, performance/load, PIT backtests, walk-forward OOS, paper/prospective tracking, slippage/fees/taxes, drawdown and benchmark comparisons.

## 4. Exclude / do not implement without a separate approved change
- A new second HSI backend, second shared Brain, duplicate diagnostic registry, duplicate scoring/gate policy, or duplicate indicator calculations.
- External NSE funnel as the authoritative *research selection* path; source providers may still be used for lawful acquisition and freshness. Retire legacy funnel paths only after verified parity and migration.
- Mandatory execution of all 61 diagnostics for every lens when the dependency graph does not require them.
- 35 independently coded indicator engines; lenses must consume shared canonical evidence.
- Unverified or obsolete diagnostics and unused code retained merely for historical symmetry. **Removal requires a proven consumer audit, compatibility test, archival/rollback plan and approval.**
- Synthetic PASS, fake source readiness, fabricated pattern win rates, invented expected returns, unsupported whole-NSE coverage, or treating missing data as zero.
- Live broker orders, leverage, auto-trading, unapproved strategy activation, or claims of guaranteed profit.
- Automatic deletion/archival of HSI-Agent-Lite, the original D: folder, historical branches, migrations or user data.

## 5. Mandatory Stage 0: read-only baseline before implementation
Produce six reviewable artifacts with file/commit/test evidence:
1. `REPO_BASELINE.md` — exact GitHub/local refs, divergence, clean/dirty state, runtime boot and tests.
2. `FEATURE_INVENTORY.md` — implemented/tested/source-verified/PIT-certified/not-implemented states, by module.
3. `CALCULATION_OWNER_MAP.md` — primitive -> canonical owner -> diagnostic/lens/UI consumers -> duplicate candidates.
4. `DATA_AND_SCHEMA_AUDIT.md` — migrations, current source coverage, retention, identity, freshness, recovery and security.
5. `LENS_DIAGNOSTIC_GAP_MATRIX.md` — D01-D61, 35 lenses, required evidence, missing sources, D35/D57 conflicts, active status.
6. `EXECUTION_PLAN.md` — ordered small PRs, acceptance tests, risks, rollback and approvals.

No application-code changes before review of Stage 0. Do not use an old dated audit as current branch evidence.

## 6. Delivery sequence
**Phase A:** repository reconciliation, master PRD/TRD/ADRs, current baseline and acceptance traceability.
**Phase B:** canonical NSE universe, ingestion, data integrity, historical/PIT and incremental update readiness.
**Phase C:** canonical deterministic computation registry, evidence persistence, deduplication and parity.
**Phase D:** diagnostics coverage, pattern engine, shared risk geometry and calibrated tests.
**Phase E:** governed 35-lens execution, discovery and confluence, keeping drafts inactive until approved.
**Phase F:** independent Analytical AI, explainable UX, portfolio/watch/alerts.
**Phase G:** complete E2E pilot, security, reliability, historical OOS and prospective paper validation.

Each phase must be independently testable and rollback-capable. Phase letters are planning order, not evidence of completion.

## 7. Technical contracts and acceptance
- Every material result identifies `instrument_id`, `timeframe`, `source_version`, `observed_at`, `published_at`/`known_at` as applicable, `as_of`, calculation/policy version, quality status and lineage.
- Distinguish `UNKNOWN`, `UNAVAILABLE`, `STALE`, `CONFLICTED`, `NOT_APPLICABLE`, `PARTIAL` and validated observations.
- Never reuse cached outputs when source fingerprints, parameter versions, PIT context or corporate-action basis differ.
- Every detector has positive/negative/boundary cases, no-lookahead tests, split/bonus tests, multi-timeframe tests and failed-breakout cases.
- Never label `FULL NSE` unless an immutable eligible-universe snapshot has a reconciled denominator and all required pipeline stages are complete.
- Research profitability metrics must use net costs and benchmark comparison; distinguish in-sample, OOS, walk-forward and prospective paper results. No guaranteed returns.

## 8. Claude Code execution discipline
Work only in the verified local clone of `Hybrid-Stock-Intelligence`, on a dedicated feature branch or worktree. Inspect relevant files first; avoid reading the entire repository into context. State the hypothesis and affected owners before editing. Keep diffs small, add tests, run targeted tests then regressions, report exact commands and outcomes. Do not conceal failing tests or overwrite uncommitted work. Commit and push only to reviewed feature branches; open PRs for owner review; do not merge to main without approval. Do not expose secrets or private portfolio data in logs.

**Per-task report:** task ID, original behavior, new behavior, files changed, reused calculations, test results, unresolved evidence, migration/rollback and approval needed.

## 9. Definition of done
A module is not complete because a document exists or code imports. It must pass contractual tests, real-source readiness where required, provenance/PIT validation, regression and integration tests, user acceptance and security checks. Entire HSI is complete only after agreed end-to-end pilot criteria pass; positive trading expectancy is a separately evaluated empirical outcome.

## 10. Immediate instruction to Claude Code
> Audit the local D: clone of `akashverma9610-arch/Hybrid-Stock-Intelligence` against this document and the existing authoritative architecture. Treat `HSI-Agent-Lite` as read-only reference. Produce the six Stage-0 artifacts without modifying application code or databases. Explicitly identify which legacy paths can be reused, which can eventually be retired after parity, and which new capabilities must be built. Do not assume local Git state matches GitHub. Stop for owner review before Phase A implementation.
