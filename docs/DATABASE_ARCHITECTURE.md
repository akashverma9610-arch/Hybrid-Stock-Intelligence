# Database architecture

SQLite remains the default local/test backend and the current full-repository
regression authority. PostgreSQL is an explicit production persistence
foundation selected with `DATABASE_BACKEND=postgresql` and `DATABASE_URL`; no
connection is opened at application import. The local SQLite snapshot adapter is
opened lazily during FastAPI lifespan, while the PostgreSQL adapter remains lazy
until an operation needs a connection.

`app.storage.database` owns typed configuration, explicit connections,
transaction commit/rollback, and an opt-in readiness probe. Liveness does not
query the database. Future API composition can inject repositories backed by
either backend without placing database logic in HTTP routes.

The first PostgreSQL representative family is immutable
`ApprovedStrategyVersion` storage. It proves insert-only persistence, typed
retrieval, deterministic listing, timezone-aware timestamps, enum-as-string
storage, fingerprints, and duplicate rejection. Promotion/review/activation,
portfolio, signal, paper, performance, backtest, OOS, and self-improvement
tables remain SQLite-only until separately migrated.

## Core API repository migration

The V1 production path adds `core_api_snapshots`, an immutable versioned
read-model table shared by SQLite and PostgreSQL adapters. It covers portfolio,
signals, paper trades, performance reports, benchmark comparisons, market
regime, sector analysis, stock analysis, and governance API read families.
Complex aggregates remain a lossless schema-versioned JSON payload rather than
being prematurely decomposed into domain tables. Each snapshot has a family,
record type, schema version, fingerprint, timezone-aware creation timestamp,
and deterministic family/timestamp/id ordering.

These are immutable records, not mutable current views. A future API source can
derive current data through an explicit deterministic query/pointer. Historical,
Phase 9B/OOS, and non-API storage families remain deferred.

## V1 API read-path wiring

`create_app()` now constructs a `CoreApiSnapshotRepository` lazily during its
lifespan when a query facade was not explicitly injected. SQLite is the default
local backend; PostgreSQL is selected only by explicit database settings. The
repository is retained in application state and an application-owned adapter is
closed at shutdown. An injected repository remains caller-owned.

`app.api.repository_query_services` is the sole mapping from API read facades
to snapshot families: portfolio, market regime, sector analysis, stock
analysis, signals, paper trades, performance reports, benchmark comparisons,
approved strategy versions, promotion records, and explicit activations.
Records are listed by deterministic `(created_at, snapshot_id)` ordering.
Current single-record views take the latest compatible payload only; stock views
also require the exact normalized symbol. No API route writes a snapshot,
recalculates domain state, or falls back to a latest approved version when an
active-strategy activation is absent.

An empty database keeps the existing safe unavailable/not-found responses. A
schema version that cannot be decoded returns a safe unavailable response rather
than selecting a different record. PostgreSQL adapters and migrations exist, but
real PostgreSQL server validation remains a deployment gate.

## Canonical market-data storage boundary

#027A introduces a provider-neutral `MarketDataStore` and append-only local/test
writer for normalized quotes, bars, index/breadth, and session facts. It does
not force high-volume bars or ticks into `core_api_snapshots`; a dedicated
time-series storage adapter is a future deployment task. The existing immutable
core API snapshot repository remains reserved for versioned API read models.

#027D now supplies that dedicated historical-bar adapter: local SQLite uses a
normalized indexed table, while the PostgreSQL migration/adaptor use the same
identity with exact numeric values and timezone-aware time bounds. Historical
bars are mutable data storage only under explicit conflict policy, not immutable
API snapshots or event history. Real PostgreSQL-server validation remains opt-in.
