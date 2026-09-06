# Official NSE Index OHLC Availability Feasibility V1

**Status:** `COMPLETE / FEASIBILITY_ONLY / NOT_ACTIVE`

## Scope and source boundary

This is a first-party-only source-discovery receipt for the seven exact sector indexes absent from the current descriptive sector-index OHLC set. It does not activate a source, alter a mapping, persist a provider response, write an index observation, change Rule 2/3 readiness, repair the 1,973 separately ineligible/unmapped securities, or make a historical PIT claim. No third-party, vendor, broker, Yahoo, or provider fallback was queried.

| Contract field | Observed value |
| --- | --- |
| Authority / source family | NSE Indices / Nifty Indices; `NSE_INDICES_HISTORICAL_INDEX_DATA` |
| First-party report / identity directory | [Historical data](https://www.niftyindices.com/reports/historical-data) / [sectoral indexes](https://www.niftyindices.com/indices/equity/sectoral-indices) |
| Bounded endpoint / request | `https://www.niftyindices.com/BackPage/getHistoricaldatatabletoString`; exact name, 2025-09-08 through 2026-09-04 only |
| Returned columns | `HistoricalDate`, `INDEX_NAME`, `OPEN`, `HIGH`, `LOW`, `CLOSE`; some values are `-` |
| Reference calendar | 247 immutable stored `NIFTY_50` sessions, 2025-09-08 through 2026-09-04 |
| Pacing / retry / retention | One second between alternate exact-name requests; no retry loop; no raw response retained or committed |
| Return family | `PRICE_RETURN_INDEX` under the existing official-index-level contract; no TRI source queried |

The report labels its historical table `Open`, `High`, `Low`, and `Close`. It is the sole source family tested. The feasibility transport bounds dates to 365 days and has no filesystem, cache, or database write path.

## Exact target receipt

Configured names are existing persisted exact mapping names. Alternate full-OHLC names prove only a source-parameter mismatch; they are not permission to activate or merge a source. Hashes identify the observed response bytes only; raw payloads were not retained.

| Canonical sector / index | Configured official name | Query name(s) | Usable fields | Sessions / range | Dup / conflict / missing | Family | Classification / warning | Affected / potential Rule 2/3 gain | Response SHA-256 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Capital Goods / `NSE_SECTOR_INDEX:CAPITAL_GOODS` | `Nifty Capital Goods` | `Nifty Capital Goods` | Date, Close | 247 / 2025-09-08–2026-09-04 | 0 / 0 / 0 | PRI | `OFFICIAL_CLOSE_ONLY`; `NSE_INDICES_HISTORICAL_FULL_OHLC_UNAVAILABLE` | 112 / 0 | `00af092f3f9374f34c4f22315bce26b4eca0c61939b14a357a8cbe2385178efc` |
| Chemicals / `NSE_SECTOR_INDEX:CHEMICALS` | `Nifty Chemicals` | `Nifty Chemicals` | Date, O/H/L/C columns; at least one O/H/L/C session value unavailable | 247 / 2025-09-08–2026-09-04 | 0 / 0 / 0 | PRI | `OFFICIAL_INDEX_EXISTS_OHLC_NOT_FOUND`; `NSE_INDICES_HISTORICAL_FULL_OHLC_UNAVAILABLE` | 45 / 0 | `acfac2030237cd314d7d0f73bfa3639f523852a932a9dcba3a8ccebb9dc1ea56` |
| Construction / `NSE_SECTOR_INDEX:CONSTRUCTION` | `Nifty Construction` | `Nifty Construction` | Date, Close | 247 / 2025-09-08–2026-09-04 | 0 / 0 / 0 | PRI | `OFFICIAL_CLOSE_ONLY`; `NSE_INDICES_HISTORICAL_FULL_OHLC_UNAVAILABLE` | 23 / 0 | `60fc0346b1197cb0fedb86cfc3dc66f1d51d270ce883630707226dc2f9ee80fb` |
| Consumer Durables / `NSE_SECTOR_INDEX:CONSUMER_DURABLES` | `Nifty Consumer Durables Index` | configured: no rows; alternate `Nifty Consumer Durables` | Date, Open, High, Low, Close | 247 / 2025-09-08–2026-09-04 | 0 / 0 / 0 | PRI | `OFFICIAL_NAME_OR_PARAMETER_MISMATCH`; `NSE_INDICES_HISTORICAL_CONFIGURED_NAME_NOT_RETRIEVABLE_ALTERNATE_VERIFIED`; not activated | 41 / 41 potential only | `8cdfaa473d0abab4d5dbd54d6b5245be6aa2a3db7d3c33e793b916ad68e3eb24` |
| Consumer Services / `NSE_SECTOR_INDEX:CONSUMER_SERVICES` | `Nifty Consumer Services` | `Nifty Consumer Services` | Date, Close | 247 / 2025-09-08–2026-09-04 | 0 / 0 / 0 | PRI | `OFFICIAL_CLOSE_ONLY`; `NSE_INDICES_HISTORICAL_FULL_OHLC_UNAVAILABLE` | 46 / 0 | `847797e07c2b64aef3a69c2e5ea48fb7fb013565cbba04150df07ab1015ee0cb` |
| Healthcare / `NSE_SECTOR_INDEX:HEALTHCARE` | `Nifty Healthcare Index` | configured: no rows; alternate `Nifty Healthcare` | Date, Open, High, Low, Close | 247 / 2025-09-08–2026-09-04 | 0 / 0 / 0 | PRI | `OFFICIAL_NAME_OR_PARAMETER_MISMATCH`; `NSE_INDICES_HISTORICAL_CONFIGURED_NAME_NOT_RETRIEVABLE_ALTERNATE_VERIFIED`; not activated | 70 / 70 potential only | `b2dfb40cf4ff96c9e9d8ce3ca7b5396fa57ccadac5e9b5ee6b23933d2984d21f` |
| Power / `NSE_SECTOR_INDEX:POWER` | `Nifty Power` | `Nifty Power` | Date, Close | 247 / 2025-09-08–2026-09-04 | 0 / 0 / 0 | PRI | `OFFICIAL_CLOSE_ONLY`; `NSE_INDICES_HISTORICAL_FULL_OHLC_UNAVAILABLE` | 21 / 0 | `aba74ba5fe27d4a8b1323154fe58064e7a33127f73dbd1a83fcf900e9b93deb0` |

## Interpretation and next boundary

All seven exact indexes exist. Four are close-only. Chemicals has the four OHLC columns but not valid O/H/L/C for every aligned session. Consumer Durables and Healthcare are the only aligned full-OHLC candidates, both behind a configured-name versus historical-parameter mismatch. The 247 aligned sessions and zero duplicate, conflict, and missing-reference observations are a bounded current-descriptive receipt only; they do not prove historical known-at, publication, archival, or revision semantics.

| Measure | Result |
| --- | --- |
| Exact mapped coverage in seven sectors | 358 securities |
| Full aligned OHLC at configured mapping name | 0 |
| Full aligned alternate-name candidate coverage | 111 (41 Consumer Durables + 70 Healthcare) |
| Exact mapped coverage unavailable here | 247 |
| Separately ineligible/unmapped coverage | 1,973 |
| Rule 2 / Rule 3 now | 207 evaluable / 2,331 missing — unchanged |
| Hypothetical after separately approved reconciliation | 318 evaluable / 2,220 missing — not applied |
| Strict historical PIT | `NOT_READY` — unchanged |

`app/market_data/official_nse_index_ohlc_feasibility.py` is a read-only injected-transport contract. It validates exact identity, normalized dates, field availability, duplicate/conflict evidence, reference-session alignment, deterministic ordering, return family, and stable serialization. It has no observation store, repository, API, UI, broker, portfolio, order, fallback, or runtime-clock dependency. `tests/unit/test_official_nse_index_ohlc_feasibility.py` is fixture-only and covers full/partial/close-only results, alternate-name non-activation, missing-session and duplicate conflict rejection, malformed/wrong-index failure, stable serialization, bounded pacing, invalid inputs, and static dependency boundaries. No test uses the network.

The smallest next slice is `OFFICIAL_NSE_INDEX_OHLC_SOURCE_NAME_RECONCILIATION_V1`: assess only Consumer Durables and Healthcare alternate query parameters against their persisted exact index identities, source semantics, and lineage. It must remain non-activating unless separately proved and approved. It must not repair the 247 unavailable exact-mapped securities or the 1,973 separately ineligible/unmapped securities.

No canonical historical equity bar, index observation, source artifact, or readiness record was written. No Rule 2/3, technical diagnostic, Watch, strategy, setup, Six Gates, portfolio, broker, order, or trading behavior changed.
