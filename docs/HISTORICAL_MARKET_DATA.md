# Historical market-data ingestion and storage

Historical ingestion accepts canonical `HistoricalBarsResponse`/bar contracts
from a future explicitly configured source. The data-source layer currently
provides only the slot and PIT/freshness/adjustment metadata; it does not claim
that Kotak Neo supplies historical bars.

Historical OHLCV flows through one provider-neutral path:

`MarketDataProvider.get_historical_bars → HistoricalIngestionService → HistoricalBarStore`.

Providers return only existing canonical `CanonicalOHLCVBar` facts. The service
sorts provider results, validates OHLCV quality and intervals, detects identical
duplicates and material conflicts, calculates conservative coverage/gap status,
and returns an immutable ingestion report. It does not calculate indicators,
market regime, Crisis/Euphoria, scores, signals, portfolio changes, or trades.

## Same-provider revisions are durable conflict evidence

When an already accepted bar and a later normalized bar have the same canonical
instrument, timeframe, session, and provider identity but differ in one or more
of `open`, `high`, `low`, `close`, `volume`, `turnover`, `trade_count`, or
`adjustment_status`, ingestion keeps the accepted bar unchanged and appends one
`HistoricalBarConflictArtifact`. The artifact records both normalized values,
their fingerprints, exact differing fields, provider/mapping/normalizer/source
lineage, first detection time, and operations run identity. It does not decide
which value is correct.

The conflict fingerprint is deterministic. Re-observing the exact same revision
is idempotent; a different incoming revision for that same session gets a new
immutable artifact. Cross-provider observations still coexist as separate raw
provider-versioned bars and are not converted into same-provider conflicts.

Read the ledger without fetching a provider or changing a bar:

```powershell
python -m app.runtime historical-bar-conflicts
python -m app.runtime historical-bar-conflicts --instrument NSE:INE220G01021
```

`has_conflict_artifact(instrument_id)` is intentionally factual only. Current
Production-v1 readiness remains unchanged until a separately governed
per-instrument readiness policy decides how such artifacts should be used.

`SQLiteHistoricalBarStore` is a dedicated normalized candle table for local
development; it is not a Core API snapshot table. Raw observation identity is
instrument, timeframe, start/end session timestamps, and provider identity.
An identical same-provider retrieval is idempotent; a later differing
same-provider session is an explicit `PROVIDER_REVISION_CONFLICT` and never
silently overwrites history. Yahoo and Upstox observations for the same session
coexist immutably in `historical_bar_observations`.

The PostgreSQL migration retains existing single-source `historical_bars` rows
unchanged and copies them non-destructively to its provider-versioned table.
Provider identity is derived only from stored provenance; missing provenance
becomes `unknown_existing_source`, never a guessed provider.
`PostgreSQLHistoricalBarStore` uses the same contract with `NUMERIC` OHLC
values and timezone-aware timestamps. Persistent local SQLite uses the
explicit migration below and conservatively tags every pre-U06R row
`unknown_existing_source` without trusting legacy provenance as source
authority.

## Local SQLite provider-version migration

The interactive local runtime uses persistent SQLite and does not run Alembic.
An older local `historical_bars` table has a four-column session key and must be
upgraded explicitly before it can receive multi-provider evidence. This command
makes a byte-for-byte SQLite backup under `data/backups/`, performs a single
`BEGIN IMMEDIATE` table rebuild, preserves every original value, tags legacy
rows as `unknown_existing_source`, validates row counts and integrity, and
writes a sanitized report at `reports/sqlite_provider_versioned_migration.json`.
It refuses PostgreSQL and in-memory SQLite, is idempotent once current, and
does not load credentials or make provider requests:

```powershell
python -m app.runtime migrate-sqlite-provider-versioned-bars
```

The upgraded local key is
`(instrument_id, timeframe, start_time, end_time, provider_identity)`. A failed
copy or verification rolls back the database transaction; the pre-migration
backup is retained for recovery. The PostgreSQL Alembic migration remains a
separate production path.

Canonical range/latest reads still return one bar per session. Selection is
centralized: official exchange evidence ranks above licensed production history
(including Upstox), which ranks above Yahoo/yfinance secondary research. An
unknown source ranks last. Selection also respects the requested completeness:
a no-volume index candle may supply close-only technical consumers, but cannot
satisfy a volume-required consumer. Raw observations remain available through
the store's `raw_range` audit method; reconciliation never alters them.

Range and latest-N queries return chronological canonical bars. Optional `as_of`
restricts both bar completion and provider received time, so replay consumers
cannot receive future bars. This supports technical indicators, stock/index
relative-strength alignment, regime inputs, Crisis/Euphoria feature derivation,
and historical replay without provider-specific code.

Coverage is explicit (`COMPLETE`, `PARTIAL`, `UNAVAILABLE`, `UNKNOWN`). Gaps are
conservative: same-session discontinuities are `POSSIBLE_GAP`; overnight,
weekend, and calendar uncertainty are not fabricated into missing intraday
bars. Range chunk plans are deterministic and advance by canonical timeframe to
avoid boundary duplication; failed chunks remain represented through report
warnings and partial/unavailable coverage.

`RAW`, `ADJUSTED`, and `UNKNOWN` adjustment state is retained on every bar.
Corporate-action adjustment remains separate. Multi-provider reconciliation is
informational only: matching, rounding, volume, adjustment-basis, and value
differences never cause a raw observation to be changed or averaged.

Imported-file providers may use the same contract. Required canonical columns
are instrument identity, timeframe, timezone-aware start/end timestamps, open,
high, low, close, volume (when available), adjustment status, and provenance.
No CSV/Parquet UI importer, scheduler, worker, Kotak historical endpoint, or
continuous ingestion is implemented in this phase.
## Optional Global Datafeeds source

Historical bars may be requested from the optional Global Datafeeds adapter while Kotak Neo remains the current-quote source. Provider selection is explicit; no fallback changes a provider family silently. GDFL's `AdjustSplits` is not a guarantee of full corporate-action-adjusted history.

## Optional Upstox Historical Candle V3 source

Upstox can be selected independently as `HISTORICAL_DATA_PROVIDER=upstox` for
the documented V3 `days/1` endpoint. The provider uses exact official
`instrument_key` mappings, preferring an exact NSE ISIN match. It provides
canonical OHLCV only through `HistoricalIngestionService`; no strategy or
diagnostic directly imports the provider. Adjustment semantics are recorded as
unknown because V3 documentation does not prove full corporate-action
adjustment. See `UPSTOX_HISTORICAL.md`.

The optional frozen-cohort command is intentionally bounded to the already
persisted 40-stock real-Brain cohort plus exact NIFTY 500. It does not perform
a 2,553-security population or any provider access from diagnostics:

```powershell
python -m app.runtime ingest-upstox-frozen-cohort --years 3
```
# Secondary yfinance research history

The optional `yfinance` adapter is bounded to an existing frozen 40-stock
cohort and is strictly secondary/research data. It requests daily raw OHLC
explicitly (`auto_adjust=False`, `back_adjust=False`, `actions=False`), never
substitutes adjusted close, and retains `RAW` adjustment status with partial
corporate-action integrity until stronger official evidence is available. See
[yfinance secondary historical provider](YFINANCE.md).
