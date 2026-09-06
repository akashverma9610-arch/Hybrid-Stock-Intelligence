# Canonical Weekly Technical Bar Derivation V1

**Status: `WEEKLY_DERIVATION_GATE = READY / CURRENT_DESCRIPTIVE_ONLY / STRICT_HISTORICAL_PIT = NOT_READY / NO_INDICATOR_ACTIVATION`.**

## Purpose

This slice materialises a bounded, immutable canonical `1W` technical-bar
artifact from the existing certified `nse-udiff-daily-technical-read / v1`
boundary.  It covers only the NSE UDiFF source era beginning on 2024-07-08.
It does not read generic historical bars as technical input, merge providers,
fetch data, create indicators, alter the canonical-61 registry, or create a
portfolio, order, broker, API, UI, setup or Six-Gates path.

`ONE_CANONICAL_61_DIAGNOSTIC_REGISTRY = TRUE` and
`SEPARATE_TECHNICAL_BRAIN = FALSE` remain unchanged.

## Governed weekly identity and session policy

- A weekly interval is Monday through Sunday in `Asia/Kolkata`; membership is
  determined by official NSE session evidence, never by a UTC week or a fixed
  five-bar assumption.
- The UDiFF daily-session coverage manifest is the historical source-era
  spine.  A manifest `CONFIRMED_NON_TRADING` date is a holiday/non-session,
  not a missing bar.
- An official special or Muhurat session from the canonical NSE calendar is a
  required child even when it falls outside Monday–Friday.  If its UDiFF
  manifest evidence is absent, the entire week is unavailable.
- A completed weekly artifact requires every required session to be present in
  the applicable certified Daily read.  An open, partial, missing or blocked
  week is represented only by a fail-closed receipt; no partial weekly candle
  exists in this slice.

The deterministic weekly ID binds the canonical instrument, canonical `1W`
interval, week period/session-plan fingerprint and aggregation policy.  The
content fingerprint additionally binds the exact child reads, observations,
artifacts, action/identity coverage, policy version and source lineage.

## Certified-Daily-only derivation

The sole technical input is a `NseUdiffDailyTechnicalRead` with:

- the exact canonical instrument and exact required session range;
- `PRICE_AND_VOLUME` requirements;
- `CURRENT_DESCRIPTIVE_TECHNICAL` use mode;
- the current UDiFF series/identity/action/continuity certificate; and
- all expected sessions marked `READY`.

The weekly layer does not repeat Daily series selection or corporate-action
logic.  A blocked Daily child—such as one caused by BL/T0 contamination,
identity ambiguity, EQ↔BE/BZ transition, conflict, rights/de-merger action,
price discontinuity or volume discontinuity—blocks the week.  A clean
post-action week may derive independently.

`STRICT_HISTORICAL_PIT_TECHNICAL` always returns
`STRICT_HISTORICAL_PIT_SOURCE_AVAILABILITY_UNAVAILABLE`: UDiFF backfill receipt
time is not original historical source availability and is never synthesized.

## OHLCV and temporal semantics

For an exchange-session-ordered complete child set:

```text
open   = first certified Daily open
high   = maximum certified Daily high
low    = minimum certified Daily low
close  = final certified Daily close
volume = sum certified Daily traded quantity
```

Trade count is summed only when every certified child supplies one.  Weekly
VWAP, turnover and any indicator are intentionally unavailable.  A derived
artifact's `known_at`/`received_at` is the maximum child receipt time; pure
derivation never obtains runtime wall-clock time.  This remains current
descriptive availability, not a historical-PIT assertion.

## Lineage, persistence and replay

`NseUdiffWeeklyTechnicalBar` retains the exact Daily read/certification,
selected observation, UDiFF artifact, identity/action coverage and canonical
technical-child lineage.  A Weekly artifact without that lineage is invalid.

The additive, source-specific SQLite tables
`nse_udiff_weekly_technical_bars` and
`nse_udiff_weekly_technical_bar_conflicts` are in the existing production
database; they do not copy Daily source data or create another database.
They are insert-only, payload-fingerprint checked and replay-safe.  An
identical replay is `IDENTICAL`; a changed payload for the same weekly identity
preserves an immutable conflict artifact rather than overwriting evidence.

The explicit local operation
`scripts/derive_nse_udiff_weekly_technical_bars.py` reconstructs the accepted
UDiFF structural-conflict proof before deriving.  It performs no network I/O
or provider fallback.  It is intentionally bounded to the retained UDiFF era.

## Readiness and non-goals

| Dimension | State | Reason |
| --- | --- | --- |
| Weekly timeframe contract | `READY` | Existing `1W` interval and derived-bar contract are used. |
| Expected sessions and completeness | `READY` | UDiFF coverage manifest plus canonical special-session evidence. |
| Series/action continuity | `READY` for certified subsets | Daily certification remains authoritative; individual weeks may block. |
| Weekly OHLCV and lineage | `READY` for certified subsets | Deterministic certified-child aggregation. |
| Current descriptive weekly availability | `READY` | Retained UDiFF receipt lineage is explicit. |
| Strict historical PIT weekly availability | `NOT_READY` | Original historical source availability is unavailable. |
| Indicator/diagnostic activation | `NOT_ACTIVE` | Weekly creation alone does not bind Rule 4, Rule 14 or any indicator. |
| Monthly derivation | `NOT_APPLICABLE` here | Mechanically feasible from complete Daily sessions, but not derived or activated. |

The prospective live/intraday capture path remains separate.  This EOD weekly
layer does not replace it and makes no claim about adjustment basis beyond the
certified Daily input.  `UPSTOX_HISTORICAL_PRICE_BASIS = UNKNOWN` and
`LOCAL_STORAGE_HYGIENE_DEBT = OPEN` remain unchanged.

## Success boundary

Certified Daily read → derived Weekly bar.  A derived Weekly bar is not a
native NSE Weekly source; a holiday is not a missing session; BL/T0 are not
EQ; identity continuity is not series equivalence; and weekly availability is
not indicator, portfolio or execution authority.
