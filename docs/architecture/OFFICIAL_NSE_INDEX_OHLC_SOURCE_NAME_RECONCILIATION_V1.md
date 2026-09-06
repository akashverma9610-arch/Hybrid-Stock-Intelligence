# Official NSE Index OHLC Source-Name Reconciliation V1

**Status:** `COMPLETE / RECONCILIATION_ONLY / NOT_ACTIVE`

## Scope and immutable boundaries

This bounded receipt reconciles only the alternate NSE Indices historical-report
parameters discovered by [Official NSE Index OHLC Availability Feasibility
V1](OFFICIAL_NSE_INDEX_OHLC_AVAILABILITY_FEASIBILITY_V1.md). It examines
Consumer Durables and Healthcare only. It does not write an OHLC observation,
change an exact sector mapping, alter Rule 2/3 readiness, activate a security,
merge a provider, synthesize an OHLC field, or change diagnostics, portfolio,
strategy, broker, or order behavior.

The following remain true:

| Boundary | State |
| --- | --- |
| `INDEX != EQUITY_SECURITY` | preserved |
| `PRI != TRI` | preserved |
| `STRICT_HISTORICAL_PIT_READY` | `FALSE` |
| provider fallback / merge | absent |
| synthetic OHLC | absent |
| indicator or Rule 2/3 expansion | absent |

## First-party identity evidence chain

The chain uses only NSE Indices materials and the existing exact canonical HSI
mapping receipt. Names are compared case-insensitively only to accommodate the
historical endpoint's `NIFTY HEALTHCARE` casing; no fuzzy or economic name
matching is allowed.

| Canonical HSI identity | Existing mapped name | Official catalogue / dedicated / factsheet identity | Historical report parameter and observed `INDEX_NAME` | Return family | Separate product guard |
| --- | --- | --- | --- | --- | --- |
| `NSE_SECTOR_INDEX:CONSUMER_DURABLES` | `Nifty Consumer Durables Index` | catalogue: `Nifty Consumer Durables`; dedicated page and factsheet: `Nifty Consumer Durables Index` | `Nifty Consumer Durables` → `Nifty Consumer Durables` | `PRICE_RETURN_INDEX` | no alternate product is accepted by this target |
| `NSE_SECTOR_INDEX:HEALTHCARE` | `Nifty Healthcare Index` | catalogue: `Nifty Healthcare`; dedicated page and factsheet: `Nifty Healthcare Index` | `Nifty Healthcare` → `NIFTY HEALTHCARE` / `Nifty Healthcare` | `PRICE_RETURN_INDEX` | `Nifty500 Healthcare` and `Nifty MidSmall Healthcare` are distinct, rejected products |

Primary references are the [NSE Indices sectoral catalogue](https://www.niftyindices.com/indices/equity/sectoral-indices), the [Consumer Durables index page](https://www.niftyindices.com/indices/equity/sectoral-indices/nifty-consumer-durables-index), the [Healthcare index page](https://www.niftyindices.com/indices/equity/sectoral-indices/nifty-healthcare-index), the [Consumer Durables factsheet](https://www.niftyindices.com/Factsheet/Factsheet_nifty_consumer_durables.pdf), the [Healthcare factsheet](https://www.niftyindices.com/Factsheet/Factsheet_Nifty_Healthcare_Index.pdf), and the [NSE Indices equity-index methodology](https://www.niftyindices.com/Methodology/Method_NIFTY_Equity_Indices.pdf). The methodology separately lists `Nifty500 Healthcare`; it is not a substitute for `Nifty Healthcare`.

The factsheets identify the two target index levels as price-return indexes and
list their total-return variants separately. A TRI response is rejected before
any numeric comparison.

## Bounded historical-report receipt

The existing feasibility receipt established that the configured mapped report
parameters `Nifty Consumer Durables Index` and `Nifty Healthcare Index` returned
no rows. This reconciliation performed one read-only query for each exact
alternate parameter against the same first-party historical endpoint, over
2025-09-08 through 2026-09-04. Raw responses were not retained.

| Canonical identity | Working parameter | Rows / session range | Duplicate sessions / missing Close | Response SHA-256 | Result |
| --- | --- | --- | --- | --- | --- |
| `NSE_SECTOR_INDEX:CONSUMER_DURABLES` | `Nifty Consumer Durables` | 247 / 2025-09-08–2026-09-04 | 0 / 0 | `8cf31cc959eb379ceda7a3f51e40ad897c8c6165a827f1eb623032f9b55814f2` | complete alternate close series, not activated |
| `NSE_SECTOR_INDEX:HEALTHCARE` | `Nifty Healthcare` | 247 / 2025-09-08–2026-09-04 | 0 / 0 | `095be4047aa0fba612016e2ebb3db003c22f6f73d4660c35b06a34e579517fc3` | complete alternate close series, not activated |

## Mandatory close-lineage result

The persisted `CANONICAL_INDEX_CLOSE_OBSERVATION` family was read directly in
SQLite read-only mode. There are zero observations for each target canonical ID.
The two observed alternate close series cannot therefore be lineage-compared to
an existing HSI canonical close-only series. Decimal values are normalized with
`Decimal.normalize()` and compared exactly; there is no tolerance. A future
reconciliation requires the same session set and exact Close values—no partial
overlap threshold is invented here.

| Canonical identity | Canonical sessions | Alternate sessions | Overlap range / sessions | Missing canonical / alternate | Duplicates | Exact matches / conflicts | Max absolute / relative difference | Classification |
| --- | ---: | ---: | --- | --- | ---: | ---: | --- | --- |
| `NSE_SECTOR_INDEX:CONSUMER_DURABLES` | 0 | 247 | unavailable / 0 | 247 alternate sessions lack canonical counterpart / 0 | 0 | 0 / 0 | unavailable | `IDENTITY_AMBIGUOUS`; `CANONICAL_CLOSE_LINEAGE_ABSENT` |
| `NSE_SECTOR_INDEX:HEALTHCARE` | 0 | 247 | unavailable / 0 | 247 alternate sessions lack canonical counterpart / 0 | 0 | 0 / 0 | unavailable | `IDENTITY_AMBIGUOUS`; `CANONICAL_CLOSE_LINEAGE_ABSENT` |

Accordingly, neither alternate parameter is classified
`SOURCE_PARAMETER_ALIAS_CONFIRMED`. First-party naming and PRI evidence are
necessary but insufficient without the mandatory numeric canonical lineage.
Neither result is a source activation or an identity repair.

## Deterministic reconciliation contract

`app/market_data/official_nse_index_ohlc_reconciliation.py` is an injected-data,
pure reconciliation contract. It has no HTTP client, storage, mapping writer,
readiness dependency, Rule 2/3 dependency, runtime clock, API, UI, portfolio,
broker, order, or fallback dependency. It checks:

1. exact canonical HSI ID and selected first-party labels;
2. PRI-only return-family identity;
3. hard rejection of separately catalogued product names;
4. duplicate session rejection without arbitrary row selection;
5. absent or non-identical session sets as `IDENTITY_AMBIGUOUS`;
6. exact normalized-Decimal Close equality, with any value difference rejected;
7. a stable SHA-256 reconciliation fingerprint over target identity, supplied
   evidence references, and both ordered input lineages.

The focused fixture-only suite covers exact names, an approved parameter alias,
Healthcare versus Nifty500 Healthcare, PRI/TRI separation, mismatch, missing
overlap, duplicates, incomplete identity, deterministic fingerprints, and static
non-persistence/non-activation boundaries. It never makes a network request.

## Impact and next bounded boundary

| Measure | Value |
| --- | ---: |
| Actual current Rule 2/3 readiness | 207 |
| Consumer Durables potential only | 41 |
| Healthcare potential only | 70 |
| Maximum later readiness if both identities reconcile **and** a separately approved operationalization succeeds | 318 |
| Mapped OHLC blocker potentially remaining | 247 |
| Separate no-eligible-exact-sector-mapping blocker | 1,973 |

`318` is potential future coverage only. Current readiness remains `207`.
No OHLC data, source artifact, mapping, technical bar, diagnostic result, or
readiness receipt was written.

This closes Branch C of the source-name question: the mandatory HSI close-series
lineage does not currently exist for either target, so no forced workaround is
permitted. The one measured next bounded recommendation is an exact-sector-
mapping coverage/governance audit for the separate 1,973-security blocker; it
must not use either unresolved alternate index parameter as a fallback.
