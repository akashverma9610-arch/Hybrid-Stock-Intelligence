# NSE UDiFF Final Bhavcopy Archive and Basis Proof V1

**Status:** `NSE_UDIFF_CANONICAL_DAILY_SOURCE = READY / DOCUMENTED_SOURCE_PROOF / NO_BACKFILL / NO_TECHNICAL_ACTIVATION`.

## Decision

The official NSE **CM-UDiFF Common Bhavcopy Final** is an independently
versioned, first-party, reproducibly retrievable source of canonical Daily
**historical market facts** for its own era:

```text
source family:        NSE_CM_UDIFF_FINAL_BHAVCOPY
effective trade-date: >= 2024-07-08
source basis state:   EXCHANGE_EOD_TRADE_PRICE
identity state:       ISIN + FinInstrmId + TckrSymb + SctySrs in each CM row
daily volume state:   READY
historical known-at:  NOT_READY
```

`READY` means that the source facts below satisfy the bounded source-proof
criteria: historical archive access, NSE authority, exact row identity,
Daily-date/session facts, OHLC/previous-close EOD semantics, trade quantity /
value / count semantics, and reproducible provenance. It does **not** mean
that HSI has backfilled a bar, certified action-free price continuity, proved
historical publication time, activated a technical diagnostic, or approved a
weekly/monthly derivation.

The legacy source family remains separate and unpromoted:

```text
LEGACY_NSE_BHAVCOPY
  trade_date < 2024-07-08
  daily technical readiness = NOT_READY
```

The [NSE All Reports page](https://www.nseindia.com/all-reports) marks the
legacy CM Common Bhavcopy as discontinued from 08-Jul-2024 and points to the
CM-UDiFF Common Bhavcopy Final. UDiFF certification does not back-propagate to
legacy Full/Common Bhavcopy artifacts.

## Scope and non-goals

This is a read-only archive/source-semantics receipt. It retained no payload in
the repository or production database. It changes no OHLCV row, schema,
importer, adjustment status, corporate-action receipt, technical policy,
indicator, diagnostic, score, signal, portfolio, broker/order, or execution
behavior.

The source proof maintains the evidence boundary:

```text
FACT -> DATA -> INTERPRETATION -> INFERENCE
```

The UDiFF source facts are not an inference that a historical technical window
is action-free, PIT-backtest eligible, or comparable with a benchmark.

## First-party sources and reproducible archive evidence

Only NSE-operated sources were used:

- [NSE All Reports](https://www.nseindia.com/all-reports), for the legacy to
  UDiFF report-family transition and the distinction between adjusted 52-week
  high/low output and Bhavcopy's actual (unadjusted) 52-week high/low source;
- [NSE Forms & Formats](https://www.nseindia.com/static/resources/forms-formats-members),
  which publishes the UDiFF Bhavcopy format workbook;
- [NSE EOD and historical-data documentation](https://www.nseindia.com/static/market-data/eod-historical-data-subscription),
  which identifies Bhavcopy/security-and-trade material as EOD data; and
- direct public NSE archive artifacts under
  `https://nsearchives.nseindia.com/content/cm/`.

No vendor, mirror, blog, forum, or secondary market-data service was used.
The following Final UDiFF archive files were retrieved directly from NSE. Each
row count is the CSV member's data-row count (header excluded). `observed_at`
is an HSI retrieval fact only, not an asserted NSE dissemination time.

| Requested trade date | Direct artifact URL / filename | SHA-256 of ZIP response | `observed_at` | ZIP bytes | CSV rows | Result |
| --- | --- | --- | --- | ---: | ---: | --- |
| 2024-07-08 | `https://nsearchives.nseindia.com/content/cm/BhavCopy_NSE_CM_0_0_0_20240708_F_0000.csv.zip` | `0ef55b77c30c8a57d5451cd371424242ad515f708630736ea6dc44c38d6e1e85` | `2026-09-05T20:00:41.881597+00:00` | 166,236 | 2,815 | HTTP 200 / ZIP |
| 2025-01-03 | `https://nsearchives.nseindia.com/content/cm/BhavCopy_NSE_CM_0_0_0_20250103_F_0000.csv.zip` | `b7953f44c6c50ec038b0453d96bc6b9f9e6d4b98536e9b25078b7078b9a3db70` | `2026-09-05T20:00:42.057262+00:00` | 171,293 | 2,922 | HTTP 200 / ZIP |
| 2026-08-20 | `https://nsearchives.nseindia.com/content/cm/BhavCopy_NSE_CM_0_0_0_20260820_F_0000.csv.zip` | `b49662236ee29614f6b39506f0b32507682c7327ef9718a19efb026ec3ba7f9c` | `2026-09-05T20:00:42.444933+00:00` | 203,415 | 3,638 | HTTP 200 / ZIP |

The ZIP member is the same basename without `.zip`, for example
`BhavCopy_NSE_CM_0_0_0_20240708_F_0000.csv`. These three artifacts establish
retrievability immediately at the transition, in the middle of the UDiFF era,
and in the recent retained period. They do **not** establish uninterrupted
coverage between them. No untested weekday is claimed missing, and no holiday
or non-session is classified from these probes.

### Actual payload schema

All three actual historical files had this exact comma-delimited header:

```text
TradDt,BizDt,Sgmt,Src,FinInstrmTp,FinInstrmId,ISIN,TckrSymb,SctySrs,
XpryDt,FininstrmActlXpryDt,StrkPric,OptnTp,FinInstrmNm,OpnPric,HghPric,
LwPric,ClsPric,LastPric,PrvsClsgPric,UndrlygPric,SttlmPric,OpnIntrst,
ChngInOpnIntrst,TtlTradgVol,TtlTrfVal,TtlNbOfTxsExctd,SsnId,NewBrdLotQty,
Rmks,Rsvd1,Rsvd2,Rsvd3,Rsvd4
```

For CM equities, the official UDiFF workbook defines the applicable names
without inventing aliases:

| Required market fact | Actual UDiFF field |
| --- | --- |
| Trade date | `TradDt` |
| Business date | `BizDt` |
| Exchange instrument ID | `FinInstrmId` |
| ISIN | `ISIN` |
| Symbol / scrip code | `TckrSymb` |
| Series | `SctySrs` |
| Session ID | `SsnId` |
| Previous close | `PrvsClsgPric` |
| Open / high / low | `OpnPric` / `HghPric` / `LwPric` |
| Last traded price / close | `LastPric` / `ClsPric` |
| Total traded quantity / value / trade count | `TtlTradgVol` / `TtlTrfVal` / `TtlNbOfTxsExctd` |

The UDiFF CM schema has no field named VWAP and no delivery-quantity or
delivery-percentage field. No average-price field was relabelled as VWAP.

## Exact security, date, and session proof

The `ICICIBANK/EQ` CM row appears in every representative payload with the
same self-contained identity: `ISIN=INE090A01021`, `FinInstrmId=4963`,
`TckrSymb=ICICIBANK`, `SctySrs=EQ`, `Sgmt=CM`, `Src=NSE`, and
`FinInstrmTp=STK`. This is an exact row identity from the artifact, not a
current-symbol backward map or company-name match.

| `TradDt` / `BizDt` | `SsnId` | Open | High | Low | Close | Last | Previous close | Quantity | Value | Trades |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 2024-07-08 / 2024-07-08 | `F1` | 1228.90 | 1239.50 | 1216.90 | 1235.05 | 1237.00 | 1233.40 | 6,617,190 | 8,157,945,587.70 | 141,803 |
| 2025-01-03 / 2025-01-03 | `F1` | 1286.20 | 1288.00 | 1262.25 | 1265.05 | 1265.60 | 1290.60 | 11,194,997 | 14,210,918,649.70 | 219,218 |
| 2026-08-20 / 2026-08-20 | `F1` | 1407.80 | 1413.00 | 1403.30 | 1411.90 | 1411.90 | 1402.00 | 8,425,049 | 11,867,275,973.20 | 108,431 |

`TradDt`, `BizDt`, and `SsnId` remain three distinct source fields even where
the first two values agree in these CM equity rows. The UDiFF specification
uses trade date, business date (the date on which the session starts), and
session ID independently; `F1` is the Final-session-1 source code. They are
sufficient to retain a Daily source-date/session identity. They do not create
an exchange close instant, prove an ordinary-session calendar state, or prove
the time at which NSE published the file.

Accordingly, a future source adapter may retain `TradDt` as the exact
`TRADING_DATE` fact and preserve `BizDt` and `SsnId` as source fields under
the existing [Daily Source Session and Publication Semantics V1](CANONICAL_DAILY_SOURCE_SESSION_AND_PUBLICATION_SEMANTICS_V1.md)
contract. It must not collapse them into a fabricated `end_time` or historical
`known_at` value.

## Price, volume, and trade-count basis proof

The resulting source-basis state is:

```text
NSE_CM_UDIFF_FINAL_BHAVCOPY price basis = EXCHANGE_EOD_TRADE_PRICE
```

That classification has a deliberately narrow meaning: the UDiFF final-file
OHLC, prior close, quantity, value, and count are exchange-published EOD
market observations. It does not mean an action-free series, a total-return
series, a back-adjusted series, or a technical-continuity certificate.

The first-party reasoning chain is:

1. The actual historical artifacts are labelled `NSE`, `CM`, `STK`, and
   `F1`, and their CM rows carry the exact price and trade fields above.
2. The NSE UDiFF workbook defines `OpnPric`, `HghPric`, `LwPric`, `ClsPric`,
   `LastPric`, and `PrvsClsgPric` as the opening, high-for-the-day,
   low-for-the-day, closing, last-traded, and prior-day-closing prices;
   `TtlTradgVol`, `TtlTrfVal`, and `TtlNbOfTxsExctd` are total traded quantity,
   value, and executed-trade count.
3. NSE's EOD/historical documentation identifies Bhavcopy and security/trade
   material as EOD output. This gives the UDiFF field set its exchange EOD
   market-statistics context.
4. NSE separately tells users that its adjusted 52-week high/low display is
   adjusted for corporate actions and that actual (unadjusted) 52-week
   high/low values should be referred to Bhavcopy. This is independent
   first-party evidence that Bhavcopy is the exchange's actual-market-price
   reference, rather than a provider-normalized price product.

This is not an assertion that NSE literally says every column is
"unadjusted", nor is the 52-week-high/low note alone used as proof for all
OHLC fields. The conclusion follows the combined, exact field definitions and
Bhavcopy EOD/actual-market reference. A future action-aware continuity gate
remains mandatory before a multi-session technical consumer can use the data.

The existing `ProviderPriceBasisState` vocabulary has `RAW`, `UNKNOWN`,
`PROVIDER_ADJUSTED_UNKNOWN_METHOD`, and `INDEX_SOURCE_SPECIFIC`; it has no
source-specific `EXCHANGE_EOD_TRADE_PRICE` member. This document therefore
does **not** relabel any retained bar as `RAW` or modify code. If a later,
separately approved UDiFF adapter maps this proof into `RAW`, it must document
that `RAW` means immutable exchange-observed values without a provider
back-adjustment and must retain the UDiFF source-family/version evidence. The
present proof does not promote Upstox:

```text
UPSTOX_HISTORICAL_PRICE_BASIS = UNKNOWN
```

The direct UDiFF `TtlTradgVol`, `TtlTrfVal`, and `TtlNbOfTxsExctd` definitions
make source authority for daily quantity, value, and trade count `READY` for
this era. Corporate-action volume comparability remains a separate gate.

## Corporate-action sanity case and composition

A read-only sanity observation used the existing immutable official NSE action
receipt `historical-action:nse-action:85aa4f53a2a95c9cafc449e84c7d7ff0`:

```text
canonical instrument: NSE:INE111A01025 (CONCOR)
official action:       BONUS 1:4
effective / ex date:   2025-07-04
```

The direct final UDiFF artifacts for the immediately preceding and ex-date
sessions both retain the exact same `ISIN=INE111A01025`,
`FinInstrmId=4749`, `TckrSymb=CONCOR`, `SctySrs=EQ`, and `SsnId=F1` identity:

| Trade date | Close | Previous close | Open | High | Low | Quantity | Value | Trades | Artifact SHA-256 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 2025-07-03 | 745.25 | 744.25 | 748.00 | 753.65 | 743.05 | 1,421,722 | 1,061,362,911.50 | 35,946 | `01fd171a2a212c24470efc6b63a17fc41ad166ccf2ecaa3086f71e3c5e7c5bf8` |
| 2025-07-04 | 599.65 | 745.25 | 597.00 | 606.50 | 595.00 | 2,351,859 | 1,411,045,838.85 | 56,786 | `c192a96cb9788cbdbdebd250161be4f2c69378bf2b38c6754d024057eea97bcc` |

The two direct URLs are
`https://nsearchives.nseindia.com/content/cm/BhavCopy_NSE_CM_0_0_0_20250703_F_0000.csv.zip`
and
`https://nsearchives.nseindia.com/content/cm/BhavCopy_NSE_CM_0_0_0_20250704_F_0000.csv.zip`.
They were observed at `2026-09-05T20:04:04.551299+00:00` and
`2026-09-05T20:04:05.010320+00:00`, respectively; they contain 3,050 and
3,037 data rows.

The observed ex-date discontinuity is consistent with why a retained action
receipt and an immutable source-price observation must compose rather than be
silently rewritten. It is **not** used to infer UDiFF price semantics or to
apply any adjustment. Existing composition remains unchanged: split/bonus
derivation has its separate contract; rights, dividends, demergers, other
complex actions, and lifecycle discontinuities fail closed. The 3,886
immutable NSE corporate-action receipts improve event evidence but do not
turn current standalone action-free certification from zero into a positive
claim.

## Time, provenance, and era coverage boundaries

Every retrieval records `HSI_OBSERVED_AT`; that proves only present access to a
hashable artifact. The original NSE publication/dissemination time is absent:

```text
HISTORICAL_SOURCE_KNOWN_AT = NOT_READY
```

It must not be backfilled from the file's trade date, business date, download
time, URL, or filename. This blocks strict historical PIT-backtest eligibility,
but it does not negate an exact descriptive canonical historical market fact.
A future post-close official retrieval can retain HSI observation time under
the forward-only temporal contract; that too is distinct from a source
publication claim.

The exact archive coverage proved here is the three tested dates above, from
the transition date `2024-07-08` through `2026-08-20`. No continuous series,
missing-session list, or holiday calendar is asserted. The UDiFF era is about
two years old by August 2026. Even after a future approved backfill, that is
insufficient by itself for long monthly history such as 52-period
monthly/Ichimoku-style or longer regime lookbacks.

## Readiness matrix

| Gate | State | Exact reason |
| --- | --- | --- |
| A. `UDIFF_HISTORICAL_ARCHIVE_ACCESS` | `READY` | Three real Final UDiFF ZIP artifacts, including 08-Jul-2024, were directly retrieved from NSE with reproducible URL, member, hash, observed-at, schema, and row-count receipts. Continuity is not implied. |
| B. `UDIFF_EXCHANGE_SOURCE_AUTHORITY` | `READY` | NSE hosts the direct archives, source workbook, All Reports transition notice, and EOD documentation. |
| C. `UDIFF_SECURITY_IDENTITY` | `READY` | Each CM row carries `ISIN`, `FinInstrmId`, `TckrSymb`, and `SctySrs`; representative ICICIBANK and CONCOR rows prove the exact composite is present in actual payloads. Lifecycle discontinuity remains separate. |
| D. `UDIFF_TRADE_DATE` | `READY` | `TradDt` is directly present and equals each requested source-date in the sampled CM rows. |
| E. `UDIFF_SESSION_IDENTITY` | `READY` | `TradDt`, `BizDt`, and `SsnId=F1` are separate source facts and sufficient for a Daily row/session identity. They do not prove a historical close or publication instant. |
| F. `UDIFF_OHLC_BASIS` | `READY` | Actual Final UDiFF rows plus first-party UDiFF field definitions, Bhavcopy EOD context, and NSE's actual/unadjusted Bhavcopy reference establish `EXCHANGE_EOD_TRADE_PRICE`; this is not a continuity or total-return claim. |
| G. `UDIFF_VOLUME_AUTHORITY` | `READY` | The actual field and UDiFF definition for `TtlTradgVol` establish total traded quantity authority. Volume continuity across actions remains separate. |
| H. `UDIFF_TRADE_COUNT_AUTHORITY` | `READY` | The actual field and UDiFF definition for `TtlNbOfTxsExctd` establish executed-trade-count authority; `TtlTrfVal` is also defined as total traded value. |
| I. `UDIFF_HISTORICAL_KNOWN_AT` | `NOT_READY` | None of the artifacts supplies an immutable original NSE publication/dissemination timestamp. |
| J. `UDIFF_FORWARD_OBSERVED_AT` | `PARTIAL` | Each retrieval has an HSI observation time and can support a future post-close observation rule, but this proof did not implement capture or prove source publication. |
| K. `UDIFF_CORPORATE_ACTION_COMPOSITION` | `PARTIAL` | UDiFF exact identity composes with 3,886 immutable NSE action receipts; one BONUS sanity case preserves the action/source distinction. Complete per-window action/lifecycle coverage and non-split/bonus policies remain unavailable. |
| L. `UDIFF_DAILY_TECHNICAL_READINESS` | `NOT_READY` | Descriptive Daily market facts are source-ready, but no UDiFF backfill or adapter exists; action-free/lifecycle coverage, historical known-at for strict PIT, and technical activation remain independently blocked. |
| M. `LEGACY_DAILY_TECHNICAL_READINESS` | `NOT_READY` | Pre-08-Jul-2024 Full/Common Bhavcopy has separate unresolved identity/basis/temporal coverage and is not promoted by this proof. |
| N. `WEEKLY_DERIVATION_GATE` | `NOT_READY` | UDiFF daily bars have not been ingested or completeness/action-window certified, and no weekly derivation policy is activated. |
| O. `MONTHLY_DERIVATION_GATE` | `NOT_READY` | Weekly prerequisites remain absent; moreover the UDiFF era alone is roughly two years and insufficient for long monthly lookbacks. |

`DAILY_VWAP_FROM_UDIFF = NOT_APPLICABLE`: the authoritative CM UDiFF schema
contains no VWAP field. A later cross-source formula is not approved here.

## Result and exact next continuation

```text
NSE_UDIFF_CANONICAL_DAILY_SOURCE = READY
```

Historical-source archaeology is complete for this decision. The one next
continuation is:

```text
NSE_UDIFF_CANONICAL_DAILY_PRICE_HISTORY_BACKFILL_V1
```

It must be limited to `NSE_CM_UDIFF_FINAL_BHAVCOPY` and its effective era,
retain artifact/source-era/hash/observed-at/identity/session evidence per
receipt, make no legacy promotion, and leave historical publication time and
action/lifecycle gates explicit. It must be separately approved before any
database write. It must not activate indicators, Rule × horizon × timeframe
policy, multi-timeframe orchestration, signals, portfolio authority, orders,
or execution.

The live architecture remains unchanged:

```text
Dhan/live feed
  -> HSI-owned prospective bars
  -> HSI internal lightweight whole-market radar
  -> discovery leads
  -> canonical technical verification
  -> same 61 diagnostics
```

Historical NSE Daily evidence supports context and research. It never replaces
the HSI internal radar.

```text
ONE_CANONICAL_61_DIAGNOSTIC_REGISTRY = TRUE
SEPARATE_TECHNICAL_BRAIN = FALSE
PRIMARY_TECHNICAL_DISCOVERY = HSI_INTERNAL_RADAR
EXTERNAL_SCREENER_AUTHORITY = OPTIONAL_DISCOVERY_ONLY
NO_INDICATOR_EXPANSION = TRUE
HORIZON_SPECIFIC_TECHNICAL_POLICY = NOT_ACTIVE
MULTI_TIMEFRAME_TECHNICAL_ORCHESTRATOR = NOT_ACTIVE
```
