# Canonical Sector, Industry, and Theme Taxonomy

## Separate identities

The canonical hierarchy is `Instrument → Industry → Sector → Super-sector`.
It is deliberately separate from many-to-many economic or macro theme
membership. A cable company can be in Electrical Equipment / Industrials and be
a member of a Power T&D theme without turning that theme into its sector or a
claim about attractiveness.

`InstrumentTaxonomyClassification` and `ThemeMembership` are append-only Core
snapshots. Every record retains source, source type, effective dates, `as_of`,
confidence, classification version, and warnings. Allowed source states are
`OFFICIAL`, `PROVIDER_DERIVED`, `PRIMARY_SOURCE_DERIVED`,
`MANUALLY_REVIEWED`, and `UNKNOWN`. Unknown data remains unknown.

Historical consumers must use a classification eligible at their exact `as_of`.
Current taxonomy cannot be substituted in a historical backtest.

## Local import boundary

No network scraping or company-name matching is used. The optional local CSV
import accepts `ISIN` first, then an exact symbol only when unambiguous. Required
headers are:

```text
ISIN,SYMBOL,INDUSTRY,SECTOR,SUPER_SECTOR,SOURCE,EFFECTIVE_FROM
```

Optional headers: `SOURCE_TYPE`, `EFFECTIVE_TO`, `CONFIDENCE`,
`CLASSIFICATION_VERSION`, and `SOURCE_REFERENCE`. `EFFECTIVE_FROM` must be an
ISO-8601 timezone-aware timestamp. Use `python -m app.runtime import-taxonomy
<file> --dry-run` before the non-dry import. In the absence of a reliable local
source, coverage reports `TAXONOMY_SOURCE_REQUIRED`; no classification is
fabricated.

## NSE Indices official current snapshots

`import-nse-indices-taxonomy` is the bounded, provider-neutral import path for
official NSE Indices constituent exports and the NSE Indices industry
classification structure. It accepts locally retained, byte-preserved official
files only; it does not fetch Yahoo, broker, or market-data-provider metadata.

```text
python -m app.runtime import-nse-indices-taxonomy <official-source-directory> --dry-run
python -m app.runtime import-nse-indices-taxonomy <official-source-directory>
```

The directory contains `nifty500.csv`, `nifty_total_market.csv`, the official
classification page capture, and the official structure PDF. Each source
artifact is fingerprinted and retained as an immutable source snapshot. Source
constituents are joined to the canonical universe by exact ISIN, with an exact
unique NSE symbol allowed only when ISIN is absent. Company-name matching and
fuzzy label matching are prohibited.

The constituent export's `Industry` column is interpreted only after comparing
its values with the official hierarchy. For the currently imported official
exports, it is an exact **sector-level** label. Therefore the import populates
only macro-economic sector and sector where supported by an exact official
match; it does not invent industry or basic-industry values. Unrecognised or
ambiguous labels remain unresolved and are reported in
`reports/nse_taxonomy_reconciliation.json` and `.csv`.

These files are current snapshots, not historical revision history. Their
availability is recorded as `FIRST_OBSERVED_OFFICIAL_SNAPSHOT`, so a taxonomy
classification cannot appear before its local observed timestamp. This means a
newly imported classification may be used by forward/current composition but
cannot alter an earlier frozen trial or backtest.

## Historical assignment acquisition boundary

Historical taxonomy **structure** is not a historical company assignment. The
completed, bounded [Historical NSE Taxonomy Assignment Acquisition V1](HISTORICAL_NSE_TAXONOMY_ASSIGNMENT_ACQUISITION_V1.md)
audit recovered historical NSE Indices code-structure documents but no
date-labelled, official company/security-to-taxonomy assignment artifact. The
result is `HISTORICAL_TAXONOMY_ASSIGNMENT_COVERAGE = UNAVAILABLE`; no current
classification may be backfilled into 2024 or another earlier cutoff.

Sector labels alone do not create sector-rotation evidence. The existing
sector-rotation path also requires a canonical sector-index mapping and
point-in-time sector price history. Until those official index series are
stored, sector rotation remains unavailable/partial rather than deriving a
sector time series from constituent labels.
