# NSE Canonical Daily Price-History Source Feasibility V1

**Status:** `NSE_CANONICAL_DAILY_HISTORY_PARTIAL / PRIMARY_SOURCE_RESEARCH / NO_BACKFILL / NO_TECHNICAL_ACTIVATION`.

## Decision

NSE makes a useful first-party daily-equity evidence path publicly accessible,
but the path cannot yet be made HSI's canonical historical technical foundation
for the entire retained period.  The bounded conclusion is:

```text
NSE_CANONICAL_DAILY_HISTORY_PARTIAL
```

The public Full Bhavcopy archive demonstrably supplies date-labelled daily
OHLCV, turnover, trade-count, and delivery fields.  Its price fields are
first-party exchange facts.  The [NSE All Reports page](https://www.nseindia.com/all-reports)
also tells users to refer to bhavcopy for the actual (unadjusted) 52-week high
and low values, contrasting it with its separately adjusted 52-week report.
That is material support for the Bhavcopy price-display family, but it is not
an approved statement that every historical `OPEN_PRICE`, `HIGH_PRICE`,
`LOW_PRICE`, and `CLOSE_PRICE` column in every public archive variant has one
complete, immutable raw-price/adjustment contract.  HSI therefore does **not**
change `NSE_HISTORICAL_PRICE_BASIS_UNRESOLVED`, existing
`AdjustmentStatus.UNKNOWN` rows, or any technical readiness gate in this
slice.

The decisive remaining constraints are exact historical security identity for
the whole retained window, source-family-wide all-OHLC adjustment semantics,
and historical publication time.  They are separate constraints:

```text
official exchange source != automatically proven adjustment basis
price basis != source-known-at
historical archive availability != redistribution licence
```

## Scope and non-goals

This is a read-only source-feasibility proof.  It does not download a
production history, write SQLite, change the existing Full Bhavcopy importer,
relable retained bars, create a parser for UDiFF, derive weekly/monthly bars,
calculate indicators, alter Rule 61 diagnostics, introduce technical voting,
or activate a horizon policy.  It has no portfolio, signal, sell, rotation,
broker, order, or execution surface.

`FACT -> DATA -> INTERPRETATION -> INFERENCE` remains mandatory.  The source
facts below are not an inference that a retrospective technical window is
usable.

## Official source-family catalogue

| Family | Official surface / access mode | Date and identity facts | Daily market fields confirmed from official material | Basis / known-at finding | Feasibility use |
| --- | --- | --- | --- | --- | --- |
| Full Bhavcopy and Security Deliverable data | Public direct dated CSV archive: `https://archives.nseindia.com/products/content/sec_bhavdata_full_DDMMYYYY.csv` | File name and `DATE1`; `SYMBOL` + `SERIES`, no ISIN in the sampled schema | Previous close, open, high, low, last, close, `AVG_PRICE`, traded quantity, turnover in lakhs, trade count, delivery quantity and delivery percent | First-party price report; official 52-week note supports actual/unadjusted Bhavcopy high/low. Historical publication instant absent. | Best public broad daily-file candidate; exact historical ISIN binding is incomplete before matching MII coverage. |
| Security-wise Price Volume Archives (Equities) | Public web form requiring a symbol, series, and date range; CSV download described by the [Historical Reports page](https://www.nseindia.com/static/resources/historical-reports-capital-market-daily-monthly-archives) | Public table documents symbol/series/date; old-symbol history is exposed by the UI, so it must never be used as an automatic current-symbol backward map | Previous close, open, high, low, last, close, **VWAP**, traded quantity, turnover, and number of trades | UI table is first-party, but the bounded programmatic probe was rejected (`403` bootstrap / `503` archive response). No durable query contract is adopted. | Per-security corroboration only until reproducible access and identity lineage are proved. |
| CM Bhavcopy / CM Common Bhavcopy | Public all-reports entries; the page marks both CSV reports discontinued from 08-Jul-2024 and directs users to UDiFF | Historic format transition is explicit | Legacy Bhavcopy fields are predecessor data; a future import must carry source/version lineage rather than merge variants implicitly | No new basis conclusion in this slice | Do not select as an unversioned canonical path. |
| CM-UDiFF Common Bhavcopy Final | Public report family and [NSE UDiFF format workbook](https://www.nseindia.com/static/resources/forms-formats-members) | UDiFF CM schema specifies trade date, business date, exchange instrument ID, ISIN, symbol, series, and session ID | Required CM fields include open, high, low, close, LTP, previous close, total traded quantity, total traded value, total number of trades, and market lot | UDiFF documentation provides exact field semantics but this bounded proof did not establish a stable public historical archive URL or an all-OHLC corporate-action basis statement. It has no named daily VWAP or delivery field. | Strongest future identity-capable daily candidate; still requires a narrow archive-and-basis proof. |
| CM security-deliverable report | Public daily report family on All Reports | Separate dated security report; no cross-source identity shortcut is approved | Delivery is available in sampled Full Bhavcopy; independent deliverable report was not acquired here | No adjustment or source-known-at implication | May corroborate delivery only after exact same-session identity is independently proved. |
| Paid EOD / Historical Data | [NSE Data & Analytics EOD/Historical subscription](https://www.nseindia.com/static/market-data/eod-historical-data-subscription) | Capital Market EOD/Historical products, including order-and-trade data, delivered through subscription/SFTP | EOD specification describes Bhavcopy plus security/trade details; historical order-and-trade product is distinct | Commercial product, not a replacement for public-source provenance; publication timing/access depend on subscription delivery | Potential licensed production-data path; licensing, redistribution, and commercial use are out of scope. |
| NIFTY / sector index history | [NSE Indices Historical Data](https://www.niftyindices.com/reports) linked by NSE Historical Reports | Index selector plus date range; separate index methodology/source family | Public UI schema: date, open, high, low, close. NIFTY 50 is also shown by NSE All Reports with shares traded and turnover. | Index values are not equity bars and must retain index-specific methodology/action semantics; historical publication time is not supplied. | Separate benchmark/sector candidate, not an equity-price substitute. |

The 2024 NSE circular on UDiFF confirms the predecessor Bhavcopy format was
available in parallel with UDiFF only through the stated transition window; it
does not erase the source/version identity of direct Full Bhavcopy artifacts.
A future importer must distinguish Full Bhavcopy, UDiFF Final Bhavcopy, and
any paid EOD product rather than treat the generic word “bhavcopy” as one
unversioned feed.

## Bounded representative proof

No response was written to the repository or HSI database.  The proof used
three public Full Bhavcopy artifacts and two public MII availability probes:

| Probe | Result | What it proves | What it does not prove |
| --- | --- | --- | --- |
| `sec_bhavdata_full_21082023.csv` | `200`, 2,425 rows, 15-column schema | Public full-file access at the beginning of the retained price window | ISIN identity, historical source publication time, or all-OHLC raw semantics |
| `sec_bhavdata_full_28062024.csv` | `200`, 2,589 rows, same 15-column schema | Direct archive continuity before the public CSV/UDiFF transition | Full coverage of every session |
| `sec_bhavdata_full_28082026.csv` | `200`, 3,460 rows, same schema | Direct archive access after the UDiFF transition; all five prescribed holdings appear as `EQ` rows | A stable future archive contract or a historic known-at time |
| 28-Aug-2026 `ICICIBANK` row | `ICICIBANK/EQ`; full OHLC, quantity, turnover, trade count, and delivery fields present | Exact price/volume/delivery row shape for a current five-target symbol | ISIN from the Full Bhavcopy row itself |
| `NSE_CM_security_28082026.csv.gz` | `200` gzip; `ICICIBANK/EQ/INE090A01021`, NSE instrument ID `4963` | Same-date exact symbol/series/ISIN binding is possible when the MII file exists | PIT availability or an identity interval |
| `NSE_CM_security_21082023.csv.gz` | `404` | The tested early retained date lacks that MII exact-identity artifact | That no other first-party historic identity source could ever exist |
| Security-wise archive API candidate | `403` bootstrap / `503` response | Public UI access is not equivalent to a reproducible unattended API contract | A negative statement about browser/manual downloads |

The direct Full Bhavcopy schema is:

```text
SYMBOL, SERIES, DATE1, PREV_CLOSE, OPEN_PRICE, HIGH_PRICE, LOW_PRICE,
LAST_PRICE, CLOSE_PRICE, AVG_PRICE, TTL_TRD_QNTY, TURNOVER_LACS,
NO_OF_TRADES, DELIV_QTY, DELIV_PER
```

`AVG_PRICE` must not be renamed to VWAP: no inspected official Full Bhavcopy
field definition supplied an average-price formula.  UDiFF also contains no
named VWAP or delivery field in its published CM Bhavcopy schema.  The
security-wise archive table does name `VWAP`, but its public query access was
not reproducibly available in this proof.

## Identity, session, and time boundaries

### Exact security identity

Full Bhavcopy records have exact `SYMBOL + SERIES` but no ISIN.  A current
instrument master cannot be projected backwards.  The public MII master,
when available for the exact report date, carries `TckrSymb`, `SctySrs`, ISIN,
and NSE instrument ID and can support an exact descriptive same-date bind.
Its tested availability is:

```text
2023-08-21: unavailable in the tested MII path
2024-06-28 and later sampled dates: available
```

This is not a claim of uninterrupted MII coverage from 28-Jun-2024 onward;
only a full receipt can prove it.  It is enough to reject current-symbol
backward leakage for the earlier retained period.  UDiFF is more promising
because its published CM schema carries ISIN directly, but public historical
artifact access remains unproved here.

### Exact session identity

`DATE1` matches the date embedded in the direct Full Bhavcopy filename and is
an NSE source trade-date marker.  It is therefore a useful date-labelled EOD
fact.  The active daily source-temporal contract already preserves it as
`TRADING_DATE`; it does not manufacture a session end.  Existing ordinary
NSE session/close evidence is forward-effective only.  Consequently a
historical Full Bhavcopy row is not yet a strict completed-session or
historical-PIT certificate.

### Known-at and forward observation

The inspected public artifacts do not provide their historical dissemination
or publication instant.  Downloading one now establishes only immutable
`HSI_OBSERVED_AT` for this retrieval; it cannot backdate source availability.
For a future post-close official retrieval within the effective session
calendar, `HSI_OBSERVED_AT` can supply a forward use boundary.  It remains
different from an exchange publication timestamp and does not repair strict
historical backtesting.

## Corporate-action and technical implications

The 3,886 immutable NSE corporate-action receipts are usable evidence to
assess discontinuities, but they do not rewrite the official daily source.
Their current per-security coverage remains partial and every security retains
`LIFECYCLE_SOURCE_REQUIRED`.  Therefore:

- raw daily price access would remove the *provider* ambiguity only after a
  source-family-wide all-OHLC basis decision;
- it would not certify action-free windows;
- split/bonus derivation remains separately governed and unimplemented here;
- rights, dividends, demergers, mergers, symbol changes, delisting,
  suspension, and relisting remain continuity blockers rather than adjustment
  inputs; and
- no NSE equity action transformation may be applied to NIFTY or sector-index
  series.

If a future raw Daily path is approved, it could materially improve the
available input history for long-lookback daily, weekly, and monthly analysis.
It cannot activate those diagnostics until daily basis, exact identity,
session/completeness, known-at, and action/lifecycle gates are separately
satisfied.

## Operational and licensing assessment

The three sampled Full Bhavcopy CSVs were about 276 KB, 298 KB, and 392 KB and
contained 2,425, 2,589, and 3,460 rows.  At roughly 250 trading sessions, a
full raw-artifact retention design is on the order of 70–100 MB per year of
CSV evidence and approximately 0.6–0.9 million parsed rows per year before
immutable provenance, indexes, and delivery artifacts.  This is tractable,
but no storage or parser change is authorised by this feasibility slice.

The public archive is suitable for bounded internal research only to the
extent NSE permits that use.  The NSE Data & Analytics EOD/Historical product
is explicitly a paid/SFTP product.  Any public SenseEdge/display,
redistribution, or scaled production service must obtain a separate licensing
and data-sharing decision; archive availability is not permission to
redistribute.

## Readiness matrix

| Gate | State | Exact reason |
| --- | --- | --- |
| A. `NSE_SECURITY_WISE_ARCHIVE_ACCESS` | `PARTIAL` | Official UI and schema exist; bounded unattended query received `403/503`, so no reproducible archive API is approved. |
| B. `NSE_BHAVCOPY_HISTORICAL_ACCESS` | `PARTIAL` | Public Full Bhavcopy files were retrieved for sampled 2023, 2024, and 2026 dates; full-session continuity is not yet receipted. |
| C. `NSE_PRICE_BASIS_AUTHORITY` | `PARTIAL` | Official note supports actual/unadjusted Bhavcopy high/low, but an all-OHLC, archive-variant-specific adjustment statement is not retained. |
| D. `NSE_SECURITY_IDENTITY` | `PARTIAL` | Full Bhavcopy lacks ISIN; same-date MII exact mapping works for sampled later dates, while tested 2023 MII is unavailable. |
| E. `NSE_SESSION_IDENTITY` | `PARTIAL` | `DATE1`/filename establish an NSE trade-date label; historical ordinary-session/close proof is not complete. |
| F. `NSE_HISTORICAL_KNOWN_AT` | `NOT_READY` | No historic artifact publication/dissemination timestamp was found. |
| G. `NSE_FORWARD_OBSERVED_AT` | `PARTIAL` | Future official retrieval can retain HSI observation time after a source/session gate; it is not a source-publication claim. |
| H. `NSE_VOLUME_AUTHORITY` | `READY` | Full Bhavcopy and UDiFF publish total traded quantity, value, and trade-count fields. Volume continuity still depends on the action gate. |
| I. `NSE_DAILY_VWAP_AUTHORITY` | `PARTIAL` | Security-wise table names VWAP, but its query was not reproducible; Full Bhavcopy `AVG_PRICE` is not promoted to VWAP and UDiFF has no VWAP field. |
| J. `CORPORATE_ACTION_INTEGRATION` | `PARTIAL` | 3,886 immutable receipts exist, but lifecycle and action-free coverage remain fail-closed. |
| K. `BENCHMARK_HISTORY` | `PARTIAL` | Official NSE Indices UI documents public daily OHLC for selected indices; a bounded NIFTY 50/NIFTY 500 retrieval and history receipt are deferred. |
| L. `SECTOR_HISTORY` | `PARTIAL` | Same official index-history family exists, but sector selections/methodology and a direct historical receipt are deferred. |
| M. `HISTORICAL_DAILY_TECHNICAL_READINESS` | `NOT_READY` | Price-basis, full-period exact identity, historic known-at, session/completeness, and action/lifecycle gates are not jointly ready. |
| N. `WEEKLY_DERIVATION_GATE` | `NOT_READY` | Daily technical integrity is not ready; no resampling is authorised. |
| O. `MONTHLY_DERIVATION_GATE` | `NOT_READY` | Same daily prerequisite gap as weekly. |

## One narrow continuation

The next bounded repair is:

```text
NSE_UDIFF_FINAL_BHAVCOPY_ARCHIVE_AND_BASIS_PROOF_V1
```

It must establish, without broad backfill: (1) a reproducible first-party
historical Final UDiFF Bhavcopy retrieval; (2) one actual CM payload carrying
the documented ISIN/symbol/series/OHLCV/session fields; and (3) retained
authoritative evidence that applies the actual/unadjusted price semantics to
the complete OHLC family.  It must then assess date-level MII/UDiFF identity
coverage across the retained window.  If that proof fails, historical-source
archaeology stops and the next implementation becomes
`PROSPECTIVE_CANONICAL_TECHNICAL_BAR_CAPTURE_V1`.

## Preserved architecture

```text
ONE_CANONICAL_61_DIAGNOSTIC_REGISTRY = TRUE
SEPARATE_TECHNICAL_BRAIN = FALSE
PRIMARY_TECHNICAL_DISCOVERY = HSI_INTERNAL_RADAR
EXTERNAL_SCREENER_AUTHORITY = OPTIONAL_DISCOVERY_ONLY
NO_INDICATOR_EXPANSION = TRUE
HORIZON_SPECIFIC_TECHNICAL_POLICY = NOT_ACTIVE
MULTI_TIMEFRAME_TECHNICAL_ORCHESTRATOR = NOT_ACTIVE
```
