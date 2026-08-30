# NSE official-export import

The application supports manual, local import of official NSE-exported CSV files and safely recognized XBRL-converted CSV/XLSX files. It never downloads from NSE, scrapes a website, uses undocumented endpoints, automates a browser, or watches a directory.

1. Download an official NSE export yourself.
2. Use a locally composed `python -m app.runtime import-nse <file> --type ...` command (or dry run first).
3. Review accepted, duplicate, conflict, rejected, and unresolved-symbol counts.
4. Imported immutable primary-exchange filings and, where a recognized structured metric exists, financial facts become PIT-eligible.
5. The existing fundamentals adapter/runtime/API can consume those records.

V1 supports announcements, financial-result metadata, actions, Regulation 30, Regulation 31, and deterministically recognized XBRL-converted values. Timestamp parsing preserves NSE broadcast time plus local import receipt time. Unknown schemas, remote URLs, unsupported extensions, excessive sizes/rows, unknown symbols, and malformed rows fail safely; a malformed row does not erase accepted rows. Reimports are checksum-idempotent.

## Frozen real-Brain cohort import

The local runtime command is deliberately limited to the most recently
persisted compatible **40-stock frozen real-Brain cohort**. It does not import
financial evidence for the full NSE universe. Run validation before any write:

```powershell
python -m app.runtime import-nse <official-file.csv> --type xbrl-converted-results --dry-run
python -m app.runtime import-nse <official-file.csv> --type xbrl-converted-results
```

For structured results, the minimum columns are `Symbol`, `Broadcast Date`,
`Period End`, `Metric`, and `Value`. `ISIN` is strongly preferred. Mapping is
exact ISIN first, then an explicitly supplied canonical instrument ID, then a
unique exact frozen-cohort symbol; a row whose supplied ISIN does not match is
unresolved rather than rebound by name. `Scope`, `Period Type`, `Value Basis`,
`Scale`, fiscal period metadata, revision reference, and document reference
are retained when present. Consolidated remains the preferred analytical scope;
standalone is an explicit adapter fallback only.

An official Reg 31/shareholding export may be imported using
`--type regulation-31`; it remains filing evidence and is never fabricated as
promoter-pledge data. Corporate-action exports remain distinct from the
historical price-integrity action store.

Automatic NSE fetching and document/XBRL parsing remain unimplemented.
