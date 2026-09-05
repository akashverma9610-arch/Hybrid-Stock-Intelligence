# NSE UDiFF Canonical Daily Price-History Backfill V1

**Status:** `IMPLEMENTED_INGESTION_BOUNDARY / ADDITIVE_RAW_EXCHANGE_FACTS / NO_TECHNICAL_SOURCE_SELECTION / NO_INDICATOR_ACTIVATION`.

This document records the bounded implementation following the accepted
[UDiFF archive and basis proof](NSE_UDIFF_FINAL_BHAVCOPY_ARCHIVE_AND_BASIS_PROOF_V1.md).
It implements data acquisition only. It does not close historical-session,
lifecycle, corporate-action-continuity, canonical source-selection, or Daily
technical-readiness gates.

## Frozen source and era boundary

| Fact | Value |
| --- | --- |
| Source family | `NSE_CM_UDIFF_FINAL_BHAVCOPY` |
| Source version / schema | `nse-udiff-final-bhavcopy-v1` / `udiff-final-bhavcopy-34-fields-v1` |
| Official archive | `https://nsearchives.nseindia.com/content/cm/BhavCopy_NSE_CM_0_0_0_YYYYMMDD_F_0000.csv.zip` |
| Accepted era | `2024-07-08` through `2026-08-31` |
| Legacy boundary | A request before `2024-07-08` is rejected as `NSE_UDIFF_LEGACY_ERA_NOT_READY`. No legacy Common Bhavcopy is parsed or promoted. |
| Source basis | `EXCHANGE_EOD_TRADE_PRICE` |
| Source bar provider identity | `NSE_UDIFF_OFFICIAL` |

The 34-column header must exactly equal the proven UDiFF schema. Any changed,
reordered, omitted, or added header is retained as raw evidence and classified
`SOURCE_SCHEMA_DRIFT`; no positional normalization occurs.

## Immutable source evidence and restart safety

The established `core_api_snapshots` repository is reused with three additive
families:

- `NSE_UDIFF_DAILY_SOURCE_ARTIFACT`: one exact base64-encoded ZIP, its source
  URL, archive member name, SHA-256, byte size, parsed row count, exact header,
  retrieval `observed_at`, schema state, and tamper-evident fingerprint;
- `NSE_UDIFF_DAILY_ACQUISITION_RECEIPT`: one date-specific acquisition/import
  outcome, including source failures and row/identity/write counts; and
- `NSE_UDIFF_DAILY_ACQUISITION_MANIFEST`: a deterministic request-window and
  replay-state receipt whose requested weekdays are deliberately not claimed to
  be a proven historical NSE trading calendar.

The artifact identifier is deterministic for acquisition identity plus request
date. A retained valid artifact is reused and its completed receipt prevents a
redownload/rewrite. Source failures are distinct from no-session evidence;
they never imply an exchange holiday. Attempts are bounded to two per requested
date. `403`/`429` is `SOURCE_BLOCKED` and stops that run without retries.

Raw archives preserve every original row and field. A normalized OHLCV bar
therefore links to `artifact_id`, raw row index, and raw-row fingerprint; fields
that have no canonical OHLCV column—`BizDt`, `SsnId`, previous close, last
price, exact source symbol/series, value, and trade count—remain verifiable in
the immutable raw archive. No VWAP is derived:

`DAILY_VWAP_FROM_UDIFF = NOT_APPLICABLE`.

## Row identity, normalization, and dates

The current eligible universe is a *target population*, not a historical
security master. A row is written only when its source `ISIN` exactly maps to
the current canonical `NSE:<ISIN>` target **and** source `TckrSymb` equals that
target's current symbol. A mismatching source symbol is retained in raw evidence
as `IDENTITY_DISCONTINUITY`; it is not backward-mapped. A missing source
instrument/series is `IDENTITY_UNRESOLVED`; a non-target ISIN is
`OUT_OF_ELIGIBLE_UNIVERSE`. `FinInstrmId` and `SctySrs` are retained in source
lineage; the importer does not assume `EQ` only and reports series from raw
artifacts separately.

`TradDt` and `BizDt` must both equal the requested source date for a normalized
cash-market stock row (`Sgmt=CM`, `Src=NSE`, `FinInstrmTp=STK`). The canonical
daily interval uses the labelled Asia/Kolkata trading-day boundary solely as a
logical date interval; it is explicitly warned as
`LOGICAL_NSE_TRADING_DAY_INTERVAL_NOT_MARKET_CLOSE` and is not a fabricated
close instant. `exchange_timestamp` is the source trading-date boundary;
`provider_timestamp` stays absent.

The source observed trade-price basis maps to the existing canonical
`AdjustmentStatus.RAW` representation only for this separate provider lineage.
That mapping means exchange-observed / unadjusted market fact; it does not
relabel, mutate, or select any retained `UNKNOWN`-basis Upstox observation.

## Time and PIT boundary

Each artifact retains its actual HSI retrieval instant as `received_at`:

```text
TRADE_DATE_KNOWN = source row TradDt
HISTORICAL_SOURCE_PUBLICATION_TIME_UNKNOWN = true
HSI_OBSERVED_AT = artifact observed_at
```

The acquired records can be descriptive exchange facts after later integrity
closure. They cannot be treated as known to HSI at their 2024/2025 trade date
in a strict historical PIT backtest. This implementation performs no
historical-known-at repair or backtest promotion.

## Existing-store integration and preserved boundaries

`SQLiteHistoricalBarStore.upsert_many` is only a transaction-bounded throughput
form of its established provider-versioned immutable `upsert` behavior. The
same `(instrument, timeframe, start, end, provider)` unique identity, equality
comparison, and same-provider conflict ledger remain in force. Cross-provider
observations coexist. A conflicting UDiFF revision preserves the first bar and
writes the existing conflict artifact; it is never overwritten.

`NSE_UDIFF_OFFICIAL` intentionally has no new ranking in
`market_bar_source_priority`. Existing canonical reads continue to use their
previously selected source—typically Upstox where present—until the separate
`NSE_UDIFF_DAILY_HISTORY_INTEGRITY_AND_CONTINUITY_CLOSURE_V1` decides source
preference safely. No Upstox, yfinance, benchmark/index, portfolio, API/UI,
broker, order, setup, Six-Gates, indicator, weekly, or monthly behavior is
changed.

Corporate-action receipts remain compose-only evidence. UDiFF raw prices and
raw volume are immutable; no split, bonus, rights, dividend, or other action
multiplier is calculated here.

## Explicit command

The only live acquisition surface is an explicit local command:

```powershell
python -m app.runtime backfill-nse-udiff-daily-history
```

`--max-sessions N` makes one sequential resumable batch. Omitting it processes
the bounded full accepted UDiFF-era weekday request set. It cannot make broker
or portfolio calls and does not launch technical computation.

## Readiness after this slice

### Production receipt audit — 2026-09-06

The bounded production run reached a durable terminal receipt for all 561
requested weekdays. It retained 532 exact, schema-valid source artifacts and
recorded 29 dates as `SOURCE_UNAVAILABLE` after their bounded attempts. Those
29 records are source states, **not** asserted NSE holidays or no-session
evidence. No source-blocked or schema-drift receipt was produced.

| Audited item | Result |
| --- | --- |
| Immutable source artifacts | 532 ZIPs / 94,273,777 bytes / 1,659,029 source rows |
| Exact current-target identity rows observed | 1,103,937 |
| Additive UDiFF raw bars inserted | 1,103,153 across 2,553 canonical instruments |
| Identity discontinuities | 14,723; retained only in raw source evidence |
| Invalid normalized rows | 194; rejected without repair |
| Same-provider conflicts | 784 immutable conflict-ledger artifacts; existing UDiFF bars were not overwritten |
| SQLite checks | `integrity_check = ok`; foreign-key violations = 0 |

The receipt proves bounded artifact acquisition and additive raw-bar storage;
it is deliberately not a historical trading-calendar proof, a lifecycle
continuity proof, a corporate-action adjustment, or a technical-source
selection decision. Instruments with a same-provider conflict remain
fail-closed for downstream technical readiness under the existing conflict
ledger.

| Readiness | State | Reason |
| --- | --- | --- |
| `UDIFF_RAW_ARTIFACT_BACKFILL` | `READY` | Every requested weekday has a durable terminal receipt; this is not a trading-calendar proof. |
| `UDIFF_SCHEMA_INTEGRITY` | `READY` per valid artifact; `NOT_READY` for a drifted artifact | Exact header comparison is fail-closed. |
| `UDIFF_DAILY_ROW_INGESTION` | `READY` for additive exact-identity raw observations | Identity discontinuities, invalid rows, and same-provider conflicts remain explicit rather than repaired. |
| `UDIFF_SECURITY_IDENTITY_COVERAGE` | `PARTIAL` | Current target identity does not establish full historical lifecycle continuity. |
| `UDIFF_DATE_COVERAGE` | `PARTIAL` | Missing artifact is an explicit source state, never an inferred holiday. |
| `UDIFF_SESSION_COMPLETENESS` | `PARTIAL` | Historical expected-session calendar reconciliation is deferred. |
| `UDIFF_PRICE_BASIS` | `READY` | Proven `EXCHANGE_EOD_TRADE_PRICE` raw source facts. |
| `UDIFF_VOLUME_AUTHORITY` | `READY` | `TtlTradgVol` is retained; continuity across actions is separate. |
| `UDIFF_HISTORICAL_KNOWN_AT` | `NOT_READY` | Original publication/dissemination time is absent. |
| `UDIFF_CURRENT_DESCRIPTIVE_HISTORY` | `PARTIAL` | Awaiting full acquisition, continuity, and source-selection closure. |
| `UDIFF_STRICT_HISTORICAL_PIT` | `NOT_READY` | A 2026 retrieval cannot backdate HSI knowledge. |
| `CORPORATE_ACTION_COMPOSITION` | `PARTIAL` | Existing immutable actions are not applied in this slice. |
| `VOLUME_CONTINUITY` | `NOT_READY` | Raw volume is retained, but action/share-count continuity is deferred. |
| `DAILY_TECHNICAL_HISTORY_READINESS` | `NOT_READY` | No integrity/continuity/source-selection closure or indicator activation. |
| `WEEKLY_DERIVATION_GATE` | `NOT_READY` | Daily integrity must close first. |
| `MONTHLY_DERIVATION_GATE` | `NOT_READY` | Daily integrity must close first. |

The frozen architecture remains unchanged:

```text
ONE_CANONICAL_61_DIAGNOSTIC_REGISTRY = TRUE
SEPARATE_TECHNICAL_BRAIN = FALSE
PRIMARY_TECHNICAL_DISCOVERY = HSI_INTERNAL_RADAR
EXTERNAL_SCREENER_AUTHORITY = OPTIONAL_DISCOVERY_ONLY
NO_INDICATOR_EXPANSION = TRUE
HORIZON_SPECIFIC_TECHNICAL_POLICY = NOT_ACTIVE
MULTI_TIMEFRAME_TECHNICAL_ORCHESTRATOR = NOT_ACTIVE
```

The next exact continuation after a production receipt is
`NSE_UDIFF_DAILY_HISTORY_INTEGRITY_AND_CONTINUITY_CLOSURE_V1`.
