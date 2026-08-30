# Official NSE Sector Indices

The sector-index registry is populated only from retained, visible official
NSE Indices pages and their documented static constituent downloads. The local
import command has no network fallback:

```text
python -m app.runtime import-nse-sector-indices <source-dir> --dry-run
python -m app.runtime import-nse-sector-indices <source-dir>
```

The source directory contains `sectoral_indices_page.html`, selected individual
pages under `pages/`, and any downloaded constituent CSV files under
`constituents/`. Every raw source has an immutable SHA-256 source snapshot.
The resulting current registry, mapping records, and constituent records are
append-only Core snapshots. Mapping reconciliation is written to
`reports/nse_sector_index_mapping.json` and `.csv`.

## Mapping safety

An `EXACT_OFFICIAL` mapping requires all of the following:

1. A current official sectoral-index page identifies the index.
2. Its retained official description explicitly establishes the relevant
   canonical NSE sector relationship.
3. The target sector is present in the official NSE Indices classification
   hierarchy.

Name resemblance alone is not evidence. Broader or narrower products remain
unmapped—examples include Bank/Private Bank versus Financial Services, and
Pharma/Hospitals versus Healthcare—unless the official page gives a
deterministic relationship. The importer records `AMBIGUOUS`,
`NO_OFFICIAL_SECTOR_INDEX`, or `UNRESOLVED` instead of choosing a proxy.

## Current versus historical use

The existing Pre-Breakout sector scan uses its unchanged Mansfield 20/60/120
calculations, then current breadth above the 50- and 200-session moving
averages, and selects the top three lexicographically. It requires three
separate inputs: an official sector-index series, the NIFTY 500 benchmark
series, and a current official constituent snapshot.

Current constituent membership may support **current/forward** breadth only.
It is never used to recreate historical sector breadth. Likewise, Task #037
stock taxonomy is a `FIRST_OBSERVED_OFFICIAL_SNAPSHOT`; it cannot be backdated
into an earlier frozen Brain trial or historical backtest.

## Historical-export boundary

The official [Historical Data report](https://www.niftyindices.com/reports/historical-data)
currently presents interactive index and date selectors but does not expose an
ordinary static historical CSV download URL in the public page. The application
therefore records `NSE_INDICES_HISTORICAL_EXPORT_UNAVAILABLE` and does not call
or reverse-engineer an undocumented UI endpoint. No Yahoo index fallback is
permitted. The missing static NSE archive is never used to fabricate OHLC;
only separately governed canonical sector-index bars may support current
selection. A sector without that evidence remains excluded, and historical
sector rotation remains unavailable.

## Current partial-sector consumer boundary

Current/forward sector rotation may consume a partial evidence set only under
the immutable selected `sector-universe-coverage-policy / v1-approved`
(approved by `human:Akash-Verma`). It requires the canonical NIFTY 500
benchmark plus at least three sectors that independently satisfy the existing
20/60/120 aligned-RS and `READY` breadth requirements. The threshold is solely
the existing Top-3 algorithm's logical minimum; it is not a coverage target.

Each unavailable official sector remains visible with its exact index identity
and reason. It has no substituted index, fabricated OHLC, zero score, inferred
rank, Top-3 eligibility, or top-down Pre-Breakout candidate route. Mapping and
bar snapshots are evaluated at the requested `as_of`; later mapping imports do
not rewrite earlier coverage. This narrowly permits current consumer readiness
with a limitation—it does not make historical breadth PIT-valid or claim a
complete NIFTY 500 sector evaluation.
