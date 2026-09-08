# Canonical Sector-Index Identity and Close Lineage Completion V1

**Status:** `COMPLETE / CURRENT_DESCRIPTIVE_TECHNICAL / STRICT_HISTORICAL_PIT_NOT_READY`

## Scope and preserved boundary

This closure completes only the retained first-party source-query identity and
Daily price-return OHLC lineage for two exact current sector-index mappings:
Consumer Durables and Healthcare. It does **not** reopen the separately
blocked all-listed NSE taxonomy coverage, classify a security, alter a mapping,
or infer an index relation. It does not use a provider, ETF, proxy, synthetic
bar, TRI series, or equity OHLCV source.

`INDEX != EQUITY_SECURITY` and `PRICE_RETURN_INDEX != TOTAL_RETURN_INDEX`
remain enforced. The evidence is current descriptive: no observation is a
claim that the information was known at a historical backtest cutoff.

## First-party identity and source-query resolution

The existing [source-name reconciliation receipt](OFFICIAL_NSE_INDEX_OHLC_SOURCE_NAME_RECONCILIATION_V1.md)
recorded that its later *cross-lineage* comparison could not run because there
was no pre-existing canonical close series. Requiring that missing target
series as a prerequisite to create the first canonical series was a bootstrap
deadlock; it was not evidence that either first-party product identity was
ambiguous.

This slice keeps that exact normalized-close comparison as a stricter later
source-to-source verification. Initial current-descriptive canonicalization
instead requires the independently retained exact first-party product chain
below. The pure resolver accepts no heuristic names, string normalisation, or
alternate products.

| Canonical HSI index | Stored exact mapping name | Official historical-report query name | First-party identity chain | Return family | Alias resolution fingerprint |
| --- | --- | --- | --- | --- | --- |
| `NSE_SECTOR_INDEX:CONSUMER_DURABLES` | `Nifty Consumer Durables Index` | `Nifty Consumer Durables` | sectoral catalogue; dedicated index page; factsheet; equity-index methodology; historical-data report | `PRICE_RETURN_INDEX` | `6dd8b0b978b1d260054f9e60909e77532df590ec1083d171436008a87884e2f8` |
| `NSE_SECTOR_INDEX:HEALTHCARE` | `Nifty Healthcare Index` | `Nifty Healthcare` | sectoral catalogue; dedicated index page; factsheet; equity-index methodology; historical-data report | `PRICE_RETURN_INDEX` | `b94f11948ecc3809fd5f8db40050b5a45882a389ed4def6d4e4a917cc1d4f754` |

The resolver is `official-nse-index-source-query-alias-v1`. It requires the
persisted mapping to be `EXACT_OFFICIAL`, its canonical sector to derive the
same HSI index identifier, and its stored name to equal the explicit canonical
mapping name above. Consumer Durables without `Index`, a Healthcare mapping
for another canonical ID, `Nifty500 Healthcare`, `Nifty MidSmall Healthcare`,
a TRI, or any other similarly named value fails closed.

The underlying first-party references are the [NSE Indices sectoral catalogue](https://www.niftyindices.com/indices/equity/sectoral-indices), the [Consumer Durables index page](https://www.niftyindices.com/indices/equity/sectoral-indices/nifty-consumer-durables-index), the [Healthcare index page](https://www.niftyindices.com/indices/equity/sectoral-indices/nifty-healthcare-index), the [Consumer Durables factsheet](https://www.niftyindices.com/Factsheet/Factsheet_nifty_consumer_durables.pdf), the [Healthcare factsheet](https://www.niftyindices.com/Factsheet/Factsheet_Nifty_Healthcare_Index.pdf), and the [NSE Indices equity-index methodology](https://www.niftyindices.com/Methodology/Method_NIFTY_Equity_Indices.pdf).

## Immutable official OHLC lineage

The bounded command is:

```text
python -m app.runtime ingest-official-nse-sector-index-alias-ohlc
```

It selects exactly the two resolver-approved target records and calls the
existing `NseIndicesOfficialOhlcClient`; it runs the same bounded target set
twice for replay proof. The query parameter is parsed by exact returned
`INDEX_NAME`, while the resulting canonical observation retains the stored
canonical mapping display name. A target carries the validated resolver
object, not a free-form hash-shaped alias string.

Raw response artifacts record `source_query_name` and the alias-resolution
fingerprint. Each canonical observation carries that fingerprint in its source
reference, along with the raw-artifact SHA-256. Thus the report parameter,
first-party identity proof, raw response, canonical session, and semantic
observation identity remain independently inspectable.

| Canonical HSI index | Sessions / UTC close range | First-run canonical observations | Second-run observations | Canonical conflicts | Retained raw artifact SHA-256 values |
| --- | --- | ---: | ---: | ---: | --- |
| `NSE_SECTOR_INDEX:CONSUMER_DURABLES` | 249 / 2025-09-08T10:00:00Z–2026-09-08T10:00:00Z | 249 inserted | 249 identical | 0 | `4f0f3f4e1690597d5943a756026aea0dcd59e12d2a653f05d0e09d1c6307a344`; `7aa2f601cd24098257bb454860c9dfc1d77fd0de13d09e2ba1073da0d0f4c037` |
| `NSE_SECTOR_INDEX:HEALTHCARE` | 249 / 2025-09-08T10:00:00Z–2026-09-08T10:00:00Z | 249 inserted | 249 identical | 0 | `f655fa0d62dbe684aaa1a29272dd9bce8a2d3e08be341aa3fffc6596e398139e`; `c979e30ce489e969ff38e80639720fdeb5c2c638d717b031b3b9fc965f28cd58` |

The second read produced distinct raw artifacts, which were preserved rather
than discarded. Their economic session values matched the first read, so the
append-only canonical store recorded no duplicate canonical observations and
no conflict. The final snapshot families are:

| Snapshot family | Before | After | Delta |
| --- | ---: | ---: | ---: |
| `CANONICAL_INDEX_OHLC_OBSERVATION` | 1,482 | 1,980 | +498 |
| `OFFICIAL_INDEX_OHLC_ARTIFACT` | 18 | 22 | +4 |

No close-only record was reinterpreted as OHLC, and no pre-existing canonical
observation or raw artifact was overwritten.

## Current-descriptive technical coverage effect

The direct deterministic sector-mapping audit at
`2026-09-08T15:32:23.598802+00:00` consumed the existing current technical
scope, taxonomy selections, exact mappings, and supplied canonical PRI-OHLC
session counts. It does not create a diagnostic result.

| Current mapping-lineage measure | Before | After |
| --- | ---: | ---: |
| exact-mapped securities with canonical sector-index OHLC | 207 | 318 |
| exact-mapped securities without canonical sector-index OHLC | 394 | 283 |
| Rule 2 sector-health source input coverage | 207 | 318 |
| Rule 3 sector-rotation source input coverage | 207 | 318 |
| Rule 6 exact sector-context coverage | 207 | 318 |
| Rule 6 full per-security readiness | unchanged / separately assembled |

The 111 gained current-descriptive sector contexts are `41` Consumer Durables
and `70` Healthcare. The remaining exact-mapped OHLC blockers are `112`
Capital Goods, `45` Chemicals, `23` Construction, `46` Consumer Services,
`36` Information Technology, and `21` Power. Those series remain fail-closed:
existing close-only evidence is not promoted to OHLC and no fallback is
permitted.

Rule 6 still requires each supplied certified equity Daily session to align
with `NIFTY_50`; its existing peer cohort remains `NOT_APPLICABLE`. The new
exact sector context does not create a peer policy, change a Rule 6
classification, or claim that all 318 securities have full Rule 6 inputs.

The all-listed taxonomy access limitation remains an independent frozen
boundary. This closure neither acquires per-security quote taxonomy nor
changes classification coverage, technical scope, mappings, diagnostic rules,
scores, Watch logic, setup/Six Gates, portfolio state, broker authority, or
order behavior.

## Verification and retained boundaries

- Focused alias/official-OHLC tests and relevant mapping/technical-input tests
  pass with exact-name, PRI-only, alias-provenance, replay, conflict, and
  fail-closed coverage.
- The production SQLite `foreign_key_check` reported `0` violations after the
  four immutable artifacts and 498 canonical observations were written.
- The production SQLite `integrity_check` reported `ok` after the same
  bounded ingestion and replay.
- `STRICT_HISTORICAL_PIT = NOT_READY`; the source is usable only after both
  session close and retrieval time in a current-descriptive assembly.
- No generic diagnostic records, portfolio snapshots, orders, broker records,
  or source fallback data were written by this operation.

This completes the bounded canonical sector-index identity/OHLC lineage
closure for the two evidence-backed aliases. It does not close any broader
taxonomy, sector-mapping, historical-PIT, peer-cohort, or trading-activation
workstream.
