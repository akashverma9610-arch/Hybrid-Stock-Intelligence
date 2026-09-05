# Canonical NSE Ordinary Session Identity and Close Evidence V1

**Status: `CANONICAL_NSE_ORDINARY_SESSION_IDENTITY_AND_CLOSE_EVIDENCE = IMPLEMENTED_FORWARD_ONLY / FIRST_PARTY / EFFECTIVE_DATED / WATCH_ONLY / NON_EXECUTABLE`.**

## Purpose

This is the smallest extension needed to let the existing canonical NSE
Capital-Market calendar establish an ordinary daily session and its **regular
continuous** close when first-party evidence permits. It adds no exchange
calendar, provider, database table, runtime clock, API, UI, technical rule,
score, portfolio access, broker/order surface, or execution authority.

It reuses, without changing their semantics:

- `CanonicalMarketSessionCalendar`;
- `WeekdayTradingConvention`;
- `EffectiveSessionPhaseTiming`; and
- the pure daily temporal receipt and source-temporal bridge.

`ordinary trading day != all exchange phases`
`regular continuous close != post-close activity`
`calendar close != source publication`
`HSI observation != historical source availability`

## Retained first-party evidence and scope

The retained [NSE Market Timings & Holidays page](https://www.nseindia.com/resources/exchange-communication-holidays)
states that equities trade on all days except Saturdays, Sundays, and Exchange
holidays, and states the regular normal/limited-physical market window as
09:15–15:30 IST. The page has no stable publication timestamp. The catalogue
therefore records its immutable HSI `known_at` as
`2026-09-05T16:47:00+00:00`; this is the retained-source knowledge cutoff, **not**
a claimed NSE publication instant.

The page is a current source. Its ordinary rule is deliberately effective only
from `2026-09-05` through the bounded catalogue end `2026-12-31`:

| Retained rule | Value | Source scope |
| --- | --- | --- |
| `nse-cm-ordinary-weekdays-2026-09-05-current` | Monday–Friday (`0..4`) are ordinary trading dates after holidays and exact overrides | Current/forward only, and only after `known_at` |
| `nse-cm-ordinary-regular-2026-09-05-current` | `REGULAR_CONTINUOUS`, 09:15–15:30 `Asia/Kolkata` | `REGULAR_TRADING_DAY` only; current/forward only |

The existing [CMTR72349](https://nsearchives.nseindia.com/content/circulars/CMTR72349.pdf)
records 09:15–15:30 normal-market timing for the source-backed 2026 Budget
Sunday. It remains an exact `SPECIAL_TRADING_DAY` record; it does not prove a
weekday convention or backfill regular-session timing. The current NSE page
also identifies 2026-11-08 as Muhurat Trading but says its timing will be
notified later. The calendar retains its `MUHURAT_TRADING` day state and no
phase timing.

No current-page rule is used for 2022–2025, for 2026 dates before the rule's
effective date, or at an `as_of` earlier than the recorded `known_at`.

## Deterministic day and close resolution

For an in-range date, the existing calendar resolves in this order:

1. an exact PIT-visible special/Muhurat override;
2. a PIT-visible annual holiday schedule;
3. the effective, PIT-visible weekday convention; then
4. the effective, PIT-visible `REGULAR_CONTINUOUS` phase.

Thus holidays and exact special sessions win over the ordinary weekday rule.
Conflicting schedules, weekday records, or phase records remain
`EVIDENCE_CONFLICTED`; missing evidence remains `UNKNOWN` or has no phase.
No source order selects a winner. A weekend is `WEEKEND_NON_TRADING` only when
the weekday rule itself is PIT-visible; an unproved historical weekday remains
`UNKNOWN`, not an inferred weekend or regular day.

The daily boundary is exactly the end of the one
`REGULAR_CONTINUOUS` phase: `15:30:00+05:30` (`10:00:00+00:00`). It is
exclusive. Closing auction, closing session, block deals, trade-modification,
and post-close activity are not substituted for that close.

## Daily temporal integration

`resolve_daily_technical_bar_temporal_evidence` already requires all of the
following before a daily bar can be strict PIT-usable:

1. a source-supplied session date;
2. this calendar resolving the date and exactly one regular-continuous close;
3. evaluation at or after that close; and
4. either a qualifying source availability contract or an immutable HSI
   observation at/after the close.

For corrected forward Upstox V4 and official NSE bhavcopy source facts, the
existing bridge emits `HSI_OBSERVED_AT_FORWARD_ONLY`. It may yield
`KNOWN_AT_FROM_HSI_OBSERVATION` only after this calendar proves the session
and close. It is a forward HSI-use boundary, not a source-publication claim.
Legacy Upstox V3 remains ambiguous and cannot enter the bridge. No retained
historical row is retrospectively certified because this session rule is now
known.

The same pure source-fact, calendar, close, and observation path applies to
equities, broad benchmarks, and sector indices. That is interface parity only:
the retained benchmark/sector population is V3/yfinance and therefore has no
currently eligible forward row. Weekly/monthly materialization is still not
authorised.

## Bounded readiness audit

| Period / gate | Ordinary day identity | Regular close | Strict daily historical PIT | Forward HSI-observed daily receipt |
| --- | --- | --- | --- | --- |
| 2022 | `NOT_READY` for ordinary dates; annual holidays/specials retained | Exact specials only | `NOT_READY` | `NOT_READY` |
| 2023 | `NOT_READY` for ordinary dates; amendment and specials retained | Exact specials only | `NOT_READY` | `NOT_READY` |
| 2024 | `NOT_READY` for ordinary dates; annual holidays/specials retained | Exact specials only | `NOT_READY` | `NOT_READY` |
| 2025 | `NOT_READY` for ordinary dates; annual holidays/specials retained | Exact specials only | `NOT_READY` | `NOT_READY` |
| 2026 through 2026-09-04 | `NOT_READY` for ordinary dates; source has not become applicable | Exact Budget special only | `NOT_READY` | `NOT_READY` |
| 2026-09-05 through 2026-12-31, after `known_at` | `READY` for non-holiday Monday–Friday dates, with exact overrides | `READY` at 15:30 IST for regular days | `NOT_READY` | `PARTIAL`: only corrected forward source facts with post-close immutable observation |
| 2026-11-08 Muhurat | `READY` descriptive special day | `NOT_READY`; NSE said timing is pending | `NOT_READY` | `NOT_READY` |
| Future beyond 2026-12-31 | `NOT_READY` / `DATE_OUTSIDE_COVERAGE` | `NOT_READY` | `NOT_READY` | `NOT_READY` |
| Equity, benchmark, sector rule parity | Same calendar rule | Same close rule | Legacy data remains blocked | Corrected future rows use the same gate |
| Weekly/monthly | `NOT_READY` | `NOT_READY` | `NOT_READY` | `NOT_READY`; adjustment and complete-period prerequisites remain absent |

## Tests and exclusions

Focused tests prove the current effective-dated ordinary rule, source
visibility cutoff, 2022–2026 historical non-backfill, holiday/special override
precedence, the pending 2026 Muhurat timing, corrected Upstox V4/NSE bhavcopy
forward observations, legacy V3 isolation, and equity/benchmark/sector parity.

This evidence does **not** prove source publication time, intraday
completeness, price adjustment, historical backtest usability, weekly/monthly
derivation, a technical score, a horizon policy, a signal, a trade, or an
order. Existing diagnostic and execution boundaries remain unchanged.

`ONE_CANONICAL_61_DIAGNOSTIC_REGISTRY = TRUE`
`SEPARATE_TECHNICAL_BRAIN = FALSE`
`HYBRID_TECHNICAL_ARCHITECTURE = FROZEN`
`EXTERNAL_SCREENER_AUTHORITY = DISCOVERY_ONLY`
`NO_INDICATOR_EXPANSION = TRUE`
`HORIZON_SPECIFIC_TECHNICAL_POLICY = NOT_ACTIVE`
`MULTI_TIMEFRAME_TECHNICAL_ORCHESTRATOR = NOT_ACTIVE`
