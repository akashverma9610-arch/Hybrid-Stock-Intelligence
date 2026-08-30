# Minimum Viable Real Data Package

`#038D` defines the smallest evidence package that can improve the frozen
40-stock real-Brain cohort without widening it to the 2,553-stock universe:

1. canonical daily OHLCV for the exact frozen cohort;
2. canonical industry, sector, and super-sector taxonomy; and
3. canonical NIFTY 500 (or explicitly retained NIFTY 50 fallback) history.

The package is source-first. `global_datafeeds` and `upstox` are optional
historical adapters when their secure credential, exact provider mappings, and
explicit live validation are available. A missing/unvalidated profile is
reported as such; it never causes a credential guess, a network fallback, or a
history download. Existing `HistoricalIngestionService` remains the only
ingestion path: provider mapping → normalized canonical bars →
`HistoricalBarStore`.

Daily bars remain Decimal/timezone/provenance preserving, immutable, ordered,
quality validated, and carry `RAW`, `ADJUSTED`, or `UNKNOWN` adjustment status.
`AdjustSplits` is not a claim of complete corporate-action adjustment. In the
absence of a canonical corporate-action source, raw history can improve
technical coverage but price-adjustment integrity remains `PARTIAL` rather
than being silently called safe.

Coverage requires 252 daily bars before marking stock or benchmark history
`READY`; shorter history remains `PARTIAL`. NIFTY 500 is preferred for shared
market/relative-strength context. NIFTY 50 is an explicit existing fallback
for legacy context, never a fabricated substitute. Sector context stays
unavailable until an approved explicit sector-index mapping and matching index
history exist. Taxonomy uses exact ISIN, canonical ID, then unambiguous symbol;
it never uses company-name/LLM guessing and themes remain separate.

To repeat the original sample without allowing later taxonomy data to change
the cohort, run:

```powershell
python -m app.runtime real-brain-trial --sample-size 40 --frozen-cohort
```

or bind to a particular earlier report with `--frozen-cohort-trial <trial-id>`.
The command reads stores only and records zero provider calls during analysis.
It is not an ingestion command, does not run a full-universe scan, and makes no
alpha, ranking, gate, rotation, or trading claim.

At the current local state GDFL is `MISSING_CONFIGURATION`, the frozen cohort
has no approved taxonomy or historical OHLCV import, and NIFTY 500 context is
unavailable. The next external action is therefore to configure and explicitly
validate the secure GDFL profile plus load exact provider mappings, or provide
an approved local taxonomy/OHLCV source through the existing import boundaries.
