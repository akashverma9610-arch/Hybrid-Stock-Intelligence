# Old HSI — EOD First Operationalization Scope and Acceptance V1

Status: OWNER_SCOPE_APPROVED / IMPLEMENTATION_IN_PROGRESS / NO_RUNTIME_ACTIVATION
Owner decision: prioritize **Daily (1D), Weekly (1W), Monthly (1M)** operational end-to-end. Defer **5m, 15m, 1h, 4h** as subsequent expansion. This supersedes the ordering, but not the long-term interval target, in OLD_HSI_D61_L35_OPERATIONALIZATION_EXECUTION_PLAN.md and OLD_HSI_35_LENS_ROLES_AND_DATA_READINESS_V1.md.

## Binding constraints from current Old HSI code and documents

- `app.market_data.models.Timeframe` and `app.market_data.technical_bar_contract.CanonicalTechnicalInterval` currently support stored 1D and 1W; 1M has a typed readiness interval but **no underlying stored Timeframe value or retained canonical monthly OHLCV**. Never portray typed 1M as operational.
- The certified UDiFF Daily → Weekly derivation exists (scripts/derive_nse_udiff_weekly_technical_bars.py), with official NSE session completeness, corporate-action continuity, retained child evidence and replay-safe store. Strict historical PIT is still not proven by retrospective captured data.
- Monthly implementation must reuse the existing certified Daily child set, exchange calendar and integrity guards; **not** resample generic/unadjusted prices or create an independent provider feed. A calendar month in Asia/Kolkata includes every official NSE trading session, including special sessions; derive only after the last session is completed and accepted.
- Monthly OHLCV formulas: first complete Daily OPEN; maximum Daily HIGH; minimum Daily LOW; final Daily CLOSE; sum Daily VOLUME. Source-known-at is the latest source child known-at, never an invented historical publication time. If a mandatory child is missing/conflicted/adjustment-blocked, emit a NOT_READY receipt and no monthly bar.
- The technical 1M storage/enum and migration require backward-compatible, reviewed changes; preserve previous integer/string serialization and historical fingerprints. The existing 1W source-specific store and its fixture policies are precedents but not automatically reusable for 1M.
- All 61 diagnostics remain one canonical registry, and all 35 lenses are proposed evidence consumers: readiness by actual required domains and named evidence, not all 61 rules per lens. Do not activate horizon-specific scoring/fit solely because a bar exists.
- Source acquisition is independent of UI/discovery and updates one internal canonical database. There is no new funnel provider fan-out.

## Phase 0 — read-only audit and guardrails (now)
1. Pin actual local HEAD, remote HEAD, branch diff, database identity and backup before migrations, plus Full regression baseline.
2. Run `python -m app.runtime production-v1-status` and source-family/coverage audits at an explicit UTC cutoff; record inventory denominators per instrument and timeframe without leaking private facts.
3. Record EOD official latest completed session, target count, certified source-series count, technical windows, calendar continuity, corporate-action exceptions, full-financial/sector/filing source gaps and owner-approved freshness.
4. Run 35-lens planner over real certified 61-diagnostic/named source evidence, not test-state guesses, and produce per-lens blocked G01–G21 requirements.

## Phase 1 — Daily: source closure
- Keep original/normalized/bar readiness separate. Verify UDiFF daily current fetch and backfill reconciliation; address exact 20 unresolved + 1 ambiguous historical-target cases only with official identity evidence; never fuzzy patch.
- Fix effective-date security master and corporate-action continuity required by every chart horizon; preserve raw exchange/first-observed/processed timestamps.
- Generate full-universe Daily per-symbol READY/PARTIAL/MISSING/STALE/CONFLICTED source certifications with exact 20/60/120- and rule-specific actual lookback requirements, not a blanket ready label.

## Phase 2 — Weekly: certified child derivation
- Reuse existing canonical UDiFF Weekly operation, but only for stocks with fully certified Daily session spine, including special sessions, adjustment and identity proofs.
- Publish derived 1W coverage and diagnostic Rule 4/5/14 applicability per stock, with partial history and strict historical PIT explicitly separate.

## Phase 3 — Monthly: additive implementation
- Extend existing canonical timeframe model without changing historical enum values, add typed 1M persistence/replay/conflict and official-calendar month session resolution.
- Implement deterministic 1M aggregation from complete certified Daily only; reject open/current month, absent source children, unknown price adjustment, unresolved rights/renames, conflicting providers.
- Add golden tests: multi-day month, special NSE session, holiday, no session, incomplete last day, corporate action conflict, deterministic replay, late corrected child, chronological PIT, current month blocked.
- Add monthly technical consumer binding ONLY after agreed per-rule timeframe policy; no hypothetical monthly formula thresholds.

## Phase 4 — Nontechnical D61 + Lens data operationalization, parallel to EOD
- Official financial ingestion and certified fiscal comparisons are a separate critical path; the historical 2026-09-10 audit measured only 31 financial companies among 2,553 candidates, not whole-NSE readiness.
- Resolve missing official sector membership/peer cohorts, primary ownership/delivery evidence, audited event identity/company exposure, EV/share/debt accounting where needed, Rule 35 named VWAP and Rule 57 post-news reaction with approved semantics (they may need specific intraday inputs and must stay blocked if Daily is insufficient).
- For each of 35 lenses, preserve existing 350-cell matrix and 21 named gaps. Create a per-lens 1D/1W/1M sufficiency receipt; lens requiring deferred intraday series is EXPLICITLY DEFERRED/PARTIAL rather than mislabelled READY.
- Implement versioned lens-fit separately from availability only after normative policy and representative test approval.

## Phase 5 — End-to-end
- Bind one internal stored feature materialization, shared market scanner, deduplicated lens/funnel opportunity paths and existing canonical Shared Brain. No repeat provider scan per label.
- Present actual per-timeframe/per-rule/per-lens coverage in Dev Console and visible candidate screens; read requests do not start scans.
- Run frozen fixture parity, full regression, realistic market-session canary, recoverability and performance profiling before any activation or removing old code.

## Operational gate definition

- 1D READY only if each required current session is certified, adjusted/identity basis compatible and sufficient lookback is present.
- 1W READY only if all required official Daily sessions form a complete closed week and source receipts are valid.
- 1M READY only if all required official Daily sessions form a complete closed Asia/Kolkata calendar month; until the 1M model, derivation and store exist, it is NOT_OPERATIONAL.
- D61 READY per rule+instrument+cutoff only if rule-specific source and horizon are certified. A rule can be operational as a reliable fail-closed decision even when it has missing inputs; do not claim eligible all-NSE coverage.
- L35 READY per lens+instrument+cutoff only if all mandatory diagnostic and named sources, historical timing and governed lens policy are satisfied. Readiness does not imply MATCH or authority to trade.

## Immediate evidence-based risks

Historical 2026-09-10 D61 audit: 2,553 NSE records; 2,538 certified Daily/Weekly input scope; 1,940 Rule 4 daily+weekly READY; 2,007 Rule 5 weekly READY; only 354 Rule 2/3 sector-aligned inputs. Financial facts on only 31 companies. Rule 6 peer cohorts 0. Monthly 1M stored support absent in inspected current source. None are current live counts.

This scope decision is not authorization to create a new monthly market feed, activate execution gates, modify canonical indicators, synthesize historical known-at, touch portfolio/account state or silently migrate an unbacked production database. Local runtime remains unverified in this connector session.
