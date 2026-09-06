# NSE UDiFF Daily technical eligibility and continuity certification V1

Status: `IMPLEMENTED_CERTIFICATION_CONTRACT / NON_SCORING / NOT_TECHNICAL_ANALYSIS_ACTIVE`

This document records the bounded `NSE_UDIFF_DAILY_TECHNICAL_ELIGIBILITY_AND_CONTINUITY_CERTIFICATION_V1` slice. It is a pure, deterministic, per-window evidence certification contract. It does **not** calculate an indicator, score, setup, signal, horizon, or action; it does not write SQLite; and it does not activate the frozen generic technical-analysis path.

The slice preserves the following boundaries:

- FACT → DATA → INTERPRETATION → INFERENCE.
- Storage identity is not technical-series selection; security identity is not price continuity; price continuity is not volume continuity; raw history is not a derived-adjusted series.
- `ONE_CANONICAL_61_DIAGNOSTIC_REGISTRY = TRUE`, `SEPARATE_TECHNICAL_BRAIN = FALSE`, and `NO_INDICATOR_EXPANSION = TRUE`.
- `BL` and `T0` are retained source facts, never silent substitutes for ordinary Daily technical history.
- Current descriptive use and strict historical point-in-time (PIT) use are distinct.

## Purpose and exact window

`DailyTechnicalEligibilityReceipt` certifies precisely one:

```text
canonical instrument + start session + end session + requirement profile
```

There is deliberately no permanent instrument-level technical boolean. A security can have a recent eligible window, an older blocked window, a price-only window, or a volume-sensitive blocked window. The receipt is in-memory evidence only; it has no repository, persistence, API, UI, portfolio, broker, order, or provider-fetch dependency.

The contract is implemented in `app.market_data.nse_udiff_daily_technical_eligibility` with:

- `DailyTechnicalRequirement`: versioned `PRICE_ONLY`, `PRICE_AND_VOLUME`, and `RAW_EXCHANGE_HISTORY_ONLY` profiles;
- `NseUdiffDailyTechnicalSeriesPolicy`: immutable `nse-udiff-ordinary-daily-technical-series-selection / v1`;
- deterministic receipt identity and SHA-256 fingerprint over every selected evidence reference and decision state; and
- `read_eligible_udiff_daily_bars`, which returns only receipt-selected raw UDiFF Daily bars after a `READY` receipt.

The read contract never chooses a provider, does not fetch, falls back to neither Upstox nor another provider, and does not merge observations. An `UNKNOWN` Upstox adjustment basis cannot satisfy this UDiFF boundary.

## First-party NSE source-series policy

The policy is based on NSE's [Legend of series](https://www.nseindia.com/static/market-data/legend-of-series), the [Block Deal FAQ](https://nsearchives.nseindia.com/web/sites/default/files/inline-files/FAQs_Block_Deal_Window.pdf), and the [T+0 FAQ](https://nsearchives.nseindia.com/web/sites/default/files/inline-files/Trading_in_T%2B0_Security.pdf). They distinguish ordinary rolling-settlement equity, trade-for-trade/surveillance series, block-deal evidence, and T+0 settlement evidence. Same ISIN therefore does not make all source series technically interchangeable.

| Source series evidence | V1 ordinary Daily decision | Consequence |
|---|---|---|
| `EQ` | `SERIES_CONTINUITY_READY` | The exact, single EQ source row for each required session may be assessed further. |
| A single uninterrupted `BE` or `BZ` window | `SERIES_CONTINUITY_READY` | It may be independently assessed; it is not silently merged with EQ or the other surveillance series. |
| `EQ` ↔ `BE`/`BZ`, or `BE` ↔ `BZ`, in one window | `SERIES_REGIME_CHANGED` | Identity can remain continuous, but price and volume continuity are blocked as `SERIES_TRANSITION_BLOCKED` / `VOLUME_REGIME_CHANGED` until a separately approved transition policy exists. |
| `BL` only | `SERIES_NON_COMPARABLE` | `BL_NOT_ORDINARY_DAILY_TECHNICAL_PRICE_SERIES`; retain for future block-deal intelligence only. |
| `T0` only | `SERIES_NON_COMPARABLE` | `T0_DISTINCT_SETTLEMENT_SERIES`; it is not a T+1/EQ replacement. |
| `BL` or `T0` alongside exactly one ordinary EQ/BE/BZ row on the same session | Ordinary row selected; special-series row excluded from this technical candidate | The raw special-series fact remains stored. It neither contaminates nor substitutes for ordinary selection. |
| Competing ordinary rows for one security/session | Fail closed | `AMBIGUOUS_SECURITY_SESSION`; neither insertion order, volume, nor price chooses a winner. |
| Any other/unknown series | `SERIES_POLICY_UNRESOLVED` | No fallback or inferred equivalence. |

This is a selection rule only. It does not alter source storage, source identities, price values, volume values, or previously frozen technical readers. The generic source bridge still fails closed on UDiFF unless a later, separately authorized integration consumes a `READY` receipt.

## Exact session, source, and identity evidence

Expected sessions come from the immutable reconciled UDiFF session manifest, not a guessed weekday calendar. At the audited 2026-09-06 state it contains **532** `ARTIFACT_VALID_SESSION` entries from 2024-07-08 through 2026-08-31 and **29** `CONFIRMED_NON_TRADING_DAY` entries, with **0** unresolved entries. Any unresolved historical entry, missing expected session, invalid UDiFF row, unexpected security/session, or unresolved same-provider conflict fails closed.

A valid zero-volume exchange observation is retained as a source fact. It can pass a price-only assessment but blocks `PRICE_AND_VOLUME` with `VOLUME_REQUIRED_BUT_ZERO_OR_MISSING`.

Every selected bar must match exactly one approved `NseUdiffHistoricalSourceIdentityInterval` by canonical instrument, source observation identity, historical source symbol, source series, and observed trade date. Current symbol/ISIN lookup is never used as backward historical inference. A proven symbol change can therefore remain addressable without claiming that price or volume continuity follows automatically.

### Production identity finding

The effective-dated identity mechanism is operational, but its current coverage is intentionally limited to the prior reconciliation population: **201** intervals covering **14,723** distinct UDiFF source observations (`EQ` 88 intervals, `BE` 98, `BL` 15), out of **1,118,660** stored UDiFF observations. It is not an all-history identity certificate.

For the current 2,553-security universe, the latest exact Daily short windows have source/session and ordinary-series evidence but **zero** windows with every selected row covered by an effective-dated interval:

| Existing Daily requirement family | Required observations from current code | Raw complete | Ordinary-series ready | Every selected row identity-ready | Result |
|---|---:|---:|---:|---:|---|
| RSI / ATR short window | 4 | 2,527 | 2,509 | 0 | `NOT_READY` |
| Trend, Weinstein, Ichimoku/Chikou, OBV/RVOL, base/pattern | 5 | 2,524 | 2,500 | 0 | `NOT_READY` |
| ADX and short price-and-volume continuity | 6 | 2,523 | 2,495 | 0 | `NOT_READY` |

The configured values were extracted from `app.universe_analysis.service`: trend slow period 5, Weinstein 3/2, relative-strength 3, RVOL/OBV 3 (four observations including comparison), Ichimoku/Chikou 2/3/4/1 (five observations including displacement), base period 5, and indicator period 3 (ADX requires six observations). This is an audit of existing requirements, not an indicator activation or a new 20/50/100-day policy.

## Corporate-action, price, and volume continuity

Each non-raw-continuity assessment requires a `CorporateActionCoverageAssertion` whose source evidence covers the exact window and was known by the receipt's caller-supplied evaluation-as-of time. Absence of a receipt never means absence of an action. The certified action set is filtered by canonical instrument, effective date within the exact window, and action/as-of time no later than the evaluation-as-of time. Duplicate action IDs and unresolved same-provider conflicts fail closed.

| Intersection | Raw price state | Volume state | Rule |
|---|---|---|---|
| No blocking action and coverage complete | `PRICE_CONTINUITY_READY` | `VOLUME_CONTINUITY_READY` for price-and-volume, otherwise `VOLUME_NOT_REQUIRED` | Raw source facts are directly comparable only for that exact window. |
| Split | `ACTION_ADJUSTMENT_REQUIRED` | `VOLUME_ADJUSTMENT_REQUIRED` | Existing split transformation is not materialized here. |
| Bonus | `ACTION_ADJUSTMENT_REQUIRED` | `VOLUME_ADJUSTMENT_REQUIRED` | Existing bonus transformation is not materialized here. |
| Rights | `COMPLEX_ACTION_NON_COMPARABLE` | `VOLUME_ADJUSTMENT_REQUIRED` | No rights formula is approved. |
| Demerger, merger, delisting, suspension, relisting | `COMPLEX_ACTION_NON_COMPARABLE` | `VOLUME_ADJUSTMENT_REQUIRED` | No lifecycle/reorganization equivalence is inferred. |
| Dividend | `INSUFFICIENT_HISTORY` | `VOLUME_NOT_READY` | `DIVIDEND_PRICE_POLICY_NOT_APPROVED`; raw history is not converted to total-return history. |
| Incomplete action coverage or duplicate action ID | `INSUFFICIENT_HISTORY` | `VOLUME_NOT_READY` | A coverage gap is not a no-action claim. |

`RAW_EXCHANGE_HISTORY_ONLY` carries the exact action evidence but makes no price- or volume-continuity claim (`NOT_APPLICABLE`). It still requires source, session, identity, ambiguity/conflict, series, and action-coverage evidence before becoming an eligible technical read; this prevents a raw-read certificate from implying unknown action history is clear.

At the production checkpoint, **3,886** immutable canonical action receipts exist, but the sole current 2,553-security action-coverage assessment reports `LIFECYCLE_SOURCE_REQUIRED` for all 2,553 securities (450 identity-unresolved, 604 successful queries with no actions, 1,499 successful queries with actions). It is not the required per-window `CorporateActionCoverageAssertion`. Consequently, there are **0** current production `PRICE_CONTINUITY_READY`, **0** current production `VOLUME_CONTINUITY_READY`, and **0** technical-eligible Daily reads. This is fail-closed, not a claim that every security had an action.

An action does not invalidate the entire source era: a future caller can request a post-action segment and, after complete action coverage and identity evidence are available, certify that later exact window independently. No bulk adjusted history is created by this slice.

## Current descriptive use versus strict historical PIT

A receipt uses only caller-supplied immutable evidence and a caller-supplied `evaluation_as_of`; it never calls a runtime clock. If all certification gates eventually pass, an archive-backed UDiFF window can be read for **current descriptive** analysis. The source archive does not establish original historical HSI availability/publication time for its backfilled periods, so every receipt explicitly retains:

```text
STRICT_HISTORICAL_PIT_TECHNICAL_HISTORY = NOT_READY
HISTORICAL_SOURCE_AVAILABILITY_UNAVAILABLE
```

The contract never backdates HSI knowledge. It creates neither a historical replay authorization nor a strict-PIT technical bar.

## Five-holding evidence audit

This is source and continuity evidence only. It contains no technical calculation or investment conclusion.

| Holding | Raw UDiFF Daily source rows / sessions | Ordinary series after same-session exclusion | Series/lifecycle observation | Canonical action intersections in source era | Current eligibility blocker |
|---|---:|---|---|---|---|
| APARINDS | 532 / 532 | EQ 532 | No observed series transition | Dividends 2024-08-20, 2025-07-29 | Every selected bar lacks promoted effective identity; per-window action coverage unavailable. |
| DEEPINDS | 532 / 532 | EQ 532 | No observed series transition | None in stored receipt set | Every selected bar lacks promoted effective identity; per-window action coverage unavailable. |
| GENUSPOWER | 534 / 532 | EQ 522, BE 10; BL is excluded on 2026-06-29 and 2026-08-27 where EQ coexists | EQ↔BE window crosses a technical regime change | Demerger 2026-02-06 | Identity/action coverage block all current reads; transition and demerger additionally block intersecting windows. |
| GLAND | 532 / 532 | EQ 532 | No observed series transition | Dividends 2024-08-16, 2025-08-14, 2026-08-11 | Every selected bar lacks promoted effective identity; per-window action coverage unavailable. |
| ICICIBANK | 540 / 532 | EQ 532; BL is excluded on eight EQ-coexisting sessions | No observed ordinary-series transition | None in stored receipt set | Every selected bar lacks promoted effective identity; per-window action coverage unavailable. |

The BL coexistence cases prove why source-preserving storage and ordinary technical selection must remain separate: BL was retained as first-party evidence, while the exact ordinary EQ row remains the only candidate for this policy.

## Readiness matrix

| Boundary | State | Exact evidence/reason |
|---|---|---|
| A. `TECHNICAL_SERIES_SELECTION_POLICY` | `READY` | Immutable v1 policy; deterministic EQ/BE/BZ/BL/T0 states. |
| B. `EQ_DAILY_SERIES` | `READY` | Exact single EQ rows are eligible for further certification. |
| C. `BE_BZ_SERIES_SEMANTICS` | `PARTIAL` | Same uninterrupted BE or BZ windows can be assessed; transitions remain blocked. |
| D. `BL_EXCLUSION` | `READY` | BL-only fails closed and coexisting BL cannot replace/contaminate EQ. |
| E. `T0_EXCLUSION` | `READY` | T0-only fails closed and cannot be a T+1/EQ fallback. |
| F. `EXACT_SESSION_WINDOW_COMPLETENESS` | `READY` | 532 valid sessions, 29 confirmed non-trading days, zero unresolved; per-security gaps remain explicit. |
| G. `EFFECTIVE_DATED_IDENTITY_USE` | `PARTIAL` | Enforcement is operational; 14,723/1,118,660 source rows are promoted and none covers the current short-window matrix. |
| H. `CORPORATE_ACTION_WINDOW_COMPOSITION` | `NOT_READY` | Action facts exist, but all current universe coverages require lifecycle source evidence and no qualifying per-window assertion exists. |
| I. `PRICE_CONTINUITY_CERTIFICATION` | `PARTIAL` | The deterministic contract is implemented; zero current production windows pass identity plus action coverage. |
| J. `VOLUME_CONTINUITY_CERTIFICATION` | `PARTIAL` | Separate deterministic state is implemented; zero current production windows pass the prerequisite evidence. |
| K. `TECHNICAL_ELIGIBLE_DAILY_READ` | `PARTIAL` | Read boundary is implemented and provider-closed; no current `READY` production receipt exists. |
| L. `CURRENT_DESCRIPTIVE_DAILY_TECHNICAL_DATA` | `NOT_READY` | Per-window architecture is available, but current coverage yields zero eligible reads. |
| M. `STRICT_HISTORICAL_PIT_TECHNICAL_HISTORY` | `NOT_READY` | Archive backfill has no original source-availability timestamp. |
| N. `EXISTING_DIAGNOSTIC_LOOKBACK_COVERAGE` | `NOT_READY` | 0 identity-ready current 4/5/6-session windows; no 61-rule materialization is authorized. |
| O. `WEEKLY_DERIVATION_GATE` | `NOT_READY` | Requires eligible Daily reads with action/series/identity lineage; no such production window exists. |
| P. `MONTHLY_LONG_HISTORY_READINESS` | `NOT_READY` | UDiFF era is about two years and Daily eligibility remains blocked. |

## Downstream boundaries and exact next repair

No weekly or monthly bar is derived here. A future weekly derivation must retain selected Daily IDs, exact sessions, source series, identity/action continuity, derived provenance, and known-at distinctions; it must reject any week crossing a blocked action or series transition. Successful weekly subset certification would still not imply sufficient monthly long history.

`PROSPECTIVE_CANONICAL_TECHNICAL_BAR_CAPTURE_V1` remains independently required for 15-minute, 30-minute, 1-hour, live-radar, and observed-at truth. No Dhan implementation is added here.

The next bounded repair is:

```text
NSE_UDIFF_EFFECTIVE_DATED_IDENTITY_AND_ACTION_WINDOW_COVERAGE_COMPLETION_V1
```

It must complete exact effective-dated identity coverage for source rows selected by prospective Daily windows and produce/reconcile canonical per-window action-coverage evidence. It must preserve raw source rows and receipts, avoid retroactive source-availability claims, and not activate indicators, 61 diagnostics, Weekly/Monthly derivation, portfolio behavior, or execution. Only if that repair yields a material set of `READY` Daily receipts may the weekly gate be reconsidered.

## Preserved status

```text
NSE_UDIFF_CANONICAL_DAILY_SOURCE = READY
NSE_UDIFF_CANONICAL_DAILY_HISTORY_BACKFILL = READY
UDIFF_SESSION_COVERAGE = READY
UDIFF_SERIES_AWARE_STORAGE = READY
EFFECTIVE_DATED_HISTORICAL_IDENTITY = OPERATIONAL
UPSTOX_HISTORICAL_PRICE_BASIS = UNKNOWN
ONE_CANONICAL_61_DIAGNOSTIC_REGISTRY = TRUE
SEPARATE_TECHNICAL_BRAIN = FALSE
PRIMARY_TECHNICAL_DISCOVERY = HSI_INTERNAL_RADAR
EXTERNAL_SCREENER_AUTHORITY = OPTIONAL_DISCOVERY_ONLY
NO_INDICATOR_EXPANSION = TRUE
LOCAL_STORAGE_HYGIENE_DEBT = OPEN
```
