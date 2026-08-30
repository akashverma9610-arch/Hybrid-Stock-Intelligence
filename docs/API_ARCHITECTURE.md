# API architecture

## Runtime status

`GET /api/v1/runtime/status` exposes only safe process-lifetime scheduler health
(enabled/running flags, configured mode/universe, cycle timestamps/status,
failure count, and warnings). It neither runs nor controls a cycle. `/health`
continues to report API-process health independently of partial/failed runtime
cycles. No `POST /runtime/*` control API exists.

## Data-source status

`GET /api/v1/data-sources/status` reports only sanitized configured-source
priority, capability/readiness, validation/freshness/PIT metadata, and warnings.
It makes no credential, provider, runtime, or broker call and has no mutation
method. It is intended for a later Settings/Data Sources UI.

## Corporate filings

`GET /api/v1/filings` supports bounded symbol/type/date/limit filters and
`GET /api/v1/filings/{filing_id}` retrieves one stored filing. These injected
read models return document metadata only; no endpoint ingests filings, fetches
an attachment, or alters market/provider/account/strategy state.

The HTTP boundary is intentionally small and contains no domain-mutation
routes. `app.api.main:create_app()` builds a FastAPI application and exposes an
ASGI `app` for Uvicorn.

## Structure

- `app.api.settings` — typed `APP_ENV`, `APP_NAME`, `API_VERSION`, and
  `CORS_ORIGINS` settings.
- `app.api.dependencies` — overridable settings dependencies.
- `app.api.routes.system` — health and operational system endpoints.
- `app.api.routes.connections` — isolated local/private connection settings;
  it delegates to provider-neutral services and never returns credentials.
- `app.api.routes.portfolio` — thin read-only portfolio routes.
- `app.api.portfolio_query` — injectable snapshot query facade; it neither
  reconstructs a portfolio nor executes rotation logic.
- `app.api.routes.market` and `app.api.market_query` — injected read-only
  market-regime and sector diagnostic facades with no live-data dependency.
- `app.api.routes.stocks` and `app.api.stock_query` — injected aggregate stock
  analysis facade that maps existing records only.
- `app.api.routes.signals` and `app.api.signal_paper_query` — injected,
  read-only signal, simulated paper-trade, and stored-performance facades.
- `app.api.schemas` — stable public Pydantic response/error schemas.
- `app.api.middleware` — request ID and safe request-completion logging.
- `app.api.errors` — generic unexpected-error envelope.

## Endpoints

- `GET /health` is a lightweight liveness check and does not access SQLite,
  market data, or Phase 9B services.
- `GET /api/v1/system/status` exposes API metadata and the existing
  `FeatureSettings` capability status.
- `GET /api/v1/system/version` reports application/API version metadata, not a
  strategy version.
- `GET /api/v1/portfolio`, `/portfolio/holdings`, and `/portfolio/summary`
  render an existing immutable portfolio snapshot. The default application
  source is safely unavailable until a local state source is injected.
- `GET /api/v1/market/regime` and `/api/v1/sectors` render existing analytical
  records supplied by dependencies. They do not perform regime or sector
  calculations, modify rankings, or access provider APIs.
- `GET /api/v1/stocks/{symbol}/analysis` maps an existing aggregate result into
  nested identity, timing, diagnostics, score, gates, and optional analysis
  sections without rerunning any engine.
- `GET /api/v1/signals`, `/signals/{signal_id}`, `/paper-trades`,
  `/paper-trades/{trade_id}`, and `/paper-trades/performance` package existing
  immutable records only. The routes do not instantiate signal, paper-fill, or
  performance engines and have no POST execution counterpart.
- `GET /openapi.json` and `/docs` are supplied by FastAPI.
- Local/development-only connection routes are the narrow configuration-write
  exception. They use OS-backed credential storage and do not form a general
  domain mutation API.

The Phase 9B automated-self-improvement capability is read only through the
existing feature-settings boundary. It defaults to disabled, experimental, and
deferred. This API does not run research, OOS execution, market scans, or a
scheduler.

## Safety boundaries

There is no authentication, live market-data provider wiring, broker, demat account,
order API, real-portfolio mutation, or OpenAI integration. The API uses only
explicit CORS origins; wildcard origins are rejected. Unexpected errors return
a safe `INTERNAL_ERROR` envelope with a request ID and never expose stack traces
or filesystem paths.

Because connection-secret writes are unauthenticated, they reject non-local/
private environments and must not be publicly exposed before a separate
authentication/authorization design is approved.

Portfolio routes use a single/local application context only. They do not yet
provide user tenancy, broker synchronization, live marks, or a current rotation
selection endpoint.

Market and sector routes have no default current-data source. Their safe default
is `503`; tests or a later application composition layer may inject immutable
domain results. They preserve enum values, confidence, timestamps, warnings,
and provenance without triggering Phase 9B activity.

Stock analysis has the same default-unavailable contract. It uses only local
case/whitespace symbol normalization because no exchange-suffix mapping exists.
The facade never turns smart-money/liquidity proxies into claims of direct
institutional knowledge.

Signal and paper facades retain lifecycle enums and partial records exactly:
an unfinalized simulated trade can have no exit/P&L/R values. Decimal values
remain Decimal through the facade and serialize as JSON strings. Query
pagination is bounded `limit`/`offset`; the injected source is responsible for
retrieval, while routes only filter/package its immutable records.

Performance, benchmark, and governance routes use injected frozen-record
facades. They do not compute metrics or benchmarks, aggregate OOS windows,
evaluate eligibility, approve/activate a version, or roll back. Active status
requires an explicit activation record and never falls back to latest approval.

## Phase 10 freeze

All API-domain routes are GET-only and use injected read facades. Import and
startup do not open a database, start workers, call providers, run Phase 9B, or
invoke broker/live-account behavior. The local/private API foundation is stable;
authentication, provider wiring, mutations, PostgreSQL, and frontend work stay
in separate phases.

Database selection is a lifespan-only composition concern. Unless a test or
caller injects a query facade directly, `create_app()` builds repository-backed
facades from the immutable `CoreApiSnapshotRepository`: SQLite is local/default
and PostgreSQL is explicit. Routes remain unaware of the backend, open no
per-request connections, and never run migrations. `/health` remains independent
of database connectivity.

The repository-backed facades preserve existing response contracts, filtering,
and bounded pagination. Current portfolio/regime/stock reads select the latest
deterministically stored compatible snapshot; stock reads are constrained to the
exact normalized symbol. Governance composes only stored approved-version and
explicit activation records, so approved is never treated as active by default.
There are no snapshot writers, live providers, mutation endpoints, automated
research calls, or broker/account effects in this path.
## Fundamentals

The read-only fundamentals routes expose existing canonical facts and PIT snapshots only. They accept bounded series filters and an explicit `as_of` for snapshots. They do not ingest a filing, parse a document, call a provider, compute a decision score, or mutate a portfolio/governance record.
