# Historical Security Master and Corporate-Action Integrity

## Purpose

Historical identity is not the current NSE universe. The security master keeps
stable canonical instrument identity/ISIN, symbol intervals, listing/trading
intervals, lifecycle status, source, `as_of`, and version. A rename retains one
canonical identity; a delisted security remains eligible historical evidence
before its delisting date. No historical query substitutes today's universe.

Historical universe membership reuses the existing point-in-time
`UniverseMembership` contract. `HistoricalUniverseService.get_universe()`
returns only memberships known and effective at the requested time, with
`VALID`, `PARTIAL`, or `UNAVAILABLE` integrity status. Partial membership data
must not be presented as survivorship-safe backtest evidence.

## Corporate actions and price basis

`HistoricalCorporateAction` records split, bonus, rights, dividend, merger,
demerger, symbol change, delisting, suspension, and relisting events with
announcement/record/ex/effective dates, details/ratio, source, revision, and
`as_of`. An event is eligible only when it was announced, effective, and known
by the evaluation time.

Price series declare one basis: `RAW`, `SPLIT_ADJUSTED`,
`CORPORATE_ACTION_ADJUSTED`, `TOTAL_RETURN_ADJUSTED`, or `UNKNOWN`.
`HistoricalPriceIntegrityService` rejects mixed/unknown adjustment states and
marks a raw series spanning a known split/bonus/rights/merger/demerger/symbol
change as partial and not technically eligible. It does not rewrite a price,
invent an adjusted bar, or alter indicator formulas. This prevents a raw split
from being interpreted as a technical crash, ATR spike, false 52-week high, or
breakout.

Provider differences are passed to the existing #035 reconciliation service.
Raw-versus-adjusted bars are an explicit `MATERIAL_CONFLICT` with
`ADJUSTMENT_POLICY_MISMATCH`; values are never averaged.

## Local import boundary and coverage

The optional local identity import requires at minimum:

```text
SYMBOL,EFFECTIVE_FROM,STATUS,SOURCE
```

Recommended fields are `CANONICAL_INSTRUMENT_ID`, `ISIN`, `EXCHANGE`, `SERIES`,
`LISTED_FROM`, `LISTED_UNTIL`, `TRADABLE_FROM`, `TRADABLE_UNTIL`,
`EFFECTIVE_TO`, `VERSION`, and `SOURCE_REFERENCE`. It is append-only and
local-file-only; no historical security or corporate-action fact is inferred.

Coverage now separately reports `HISTORICAL_MEMBERSHIP`, `SYMBOL_HISTORY`,
`CORPORATE_ACTIONS`, and `PRICE_ADJUSTMENT_INTEGRITY`. Until approved historical
membership/security-master/corporate-action files are imported, they remain
missing and historical backtests must stay partial/unavailable.

`HistoricalBacktestIntegrityGate` composes the historical universe and frozen
price-integrity records into one `VALID`, `PARTIAL`, `INVALID`, or
`UNAVAILABLE` precondition. It is deliberately a non-executing gate: it does
not start a backtest, substitute data, or modify a stored run.
