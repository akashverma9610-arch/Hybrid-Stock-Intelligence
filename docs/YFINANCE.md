# yfinance secondary historical provider

`yfinance` is an optional, non-authoritative secondary source for bounded NSE
daily OHLCV research. It is not an NSE/BSE filing, corporate-action,
constituent-history, delivery, ownership, or fundamental-data source.

The adapter requests `Ticker.history()` explicitly with `interval="1d"`,
`auto_adjust=False`, `back_adjust=False`, and `actions=False`. Canonical Open,
High, Low, and Close therefore retain the returned raw OHLC values; `Adj Close`
is never substituted for Close. The canonical adjustment status is `RAW`, but
historical-integrity remains partial without official corporate-action evidence.

NSE shares use the dedicated exact-symbol `SYMBOL.NS` mapping service. Mappings
are stored through the normal provider-mapping store with yfinance provenance;
there is no fuzzy name match. A NIFTY 500 Yahoo candidate is accepted only when
the provider response verifies it as NIFTY 500. It never silently falls back to
NIFTY 50.

Operator workflow, after an existing frozen 40-stock real-Brain cohort exists:

```powershell
python -m app.runtime validate-yfinance-frozen-stock --years 3
python -m app.runtime ingest-yfinance-frozen-cohort --years 3
python -m app.runtime coverage-report
python -m app.runtime real-brain-trial --sample-size 40 --frozen-cohort
```

The first command makes one bounded request. The second is explicitly limited
to the already-frozen 40 stocks plus an independently verified NIFTY 500 only;
it never scans the NSE universe. Diagnostics consume stored canonical bars and
make zero provider calls. Later primary providers must reconcile against Yahoo
through the existing reconciliation layer; bars are never averaged or silently
promoted to primary truth.

Yahoo Finance/yfinance availability, coverage, and adjustment semantics are
external limitations. This adapter must not be used to claim corporate-action-
safe backtests or production-grade authoritative market history.

## Secondary enrichment snapshots

The explicit, paced operator command below can collect additional Yahoo
research observations for the already frozen cohort. It is deliberately a
different boundary from historical OHLCV ingestion:

```powershell
python -m app.runtime enrich-yahoo-secondary-frozen-cohort --phase anchors
python -m app.runtime enrich-yahoo-secondary-frozen-cohort --phase frozen-40
```

It stores immutable `YAHOO_SECONDARY_ENRICHMENT` snapshots only. Every dataset
is labelled `provider=YAHOO_FINANCE`, `source_class=SECONDARY_RESEARCH`,
`pit_semantics=OBSERVED_AT_FETCH_ONLY`, and `canonical=false`. Raw provider
labels, values, periods, mapping confidence, fetch time, and a deterministic
fingerprint are retained. Empty, unsupported, rate-limited, transient, and
provider-error datasets remain explicit records rather than zero-filled facts.

Yahoo sector and industry are only `SECONDARY_HINT` values: they cannot write
or unblock canonical NSE taxonomy. Yahoo statements, estimates, holders,
analyst data, news, and corporate actions neither create `FinancialFact`/
filing records nor enter the stored-data Brain, Decision Score, confidence,
six gates, rotation, promotion, activation, or live execution. Official NSE/BSE
records retain authority. The generated `reports/yahoo_bse_reconciliation.*`
files identify exact-period comparison availability and corporate-action
date/ratio differences without silently reconciling or transforming anything.
