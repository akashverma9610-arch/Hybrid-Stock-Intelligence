# Local backend setup

Install the declared application and test dependencies:

```sh
python -m pip install -e ".[dev]"
```

Copy `.env.example` to a local `.env`-equivalent environment configuration if
needed. The current application reads environment variables directly:

```text
APP_ENV=development
APP_NAME=NSE Stock Manager
API_VERSION=v1
CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
ENABLE_AUTOMATED_SELF_IMPROVEMENT_RESEARCH=false
```

Start the development server:

```sh
python -m uvicorn app.api.main:app --reload
```

Useful local URLs are `/health`, `/api/v1/system/status`,
`/api/v1/system/version`, `/api/v1/portfolio`,
`/api/v1/portfolio/holdings`, `/api/v1/portfolio/summary`, `/openapi.json`, and
`/docs`. The portfolio routes are read-only and return `503` until the local
application has an existing immutable portfolio snapshot source.

`/api/v1/market/regime`, `/api/v1/sectors`, and `/api/v1/sectors/{sector_id}`
are also read-only. They return `503` until compatible immutable snapshots are
available in the configured repository (or a test/local service is injected);
they do not fetch live NSE, BSE, quote, or news data.

`/api/v1/stocks/{symbol}/analysis` is the primary read-only stock-detail route.
It returns `503` until a compatible stored snapshot is available. It does not
fetch providers or create analysis; data may be partial or stale and retains its
stored timestamps and warnings.

`/api/v1/signals`, `/api/v1/signals/{signal_id}`, `/api/v1/paper-trades`,
`/api/v1/paper-trades/{trade_id}`, and `/api/v1/paper-trades/performance` are
also read only. They return stored/injected lifecycle, simulated-outcome, and
canonical performance evidence only; absent runtime sources safely return
`503`. They do not generate signals, simulate a fill, recompute MFE/MAE or
P&L, execute trades, or connect to a broker/demat account.

`/api/v1/performance`, `/api/v1/benchmarks`, and `/api/v1/governance/*` are
also injected read-only surfaces. They expose stored reports, benchmark states,
and immutable governance lineage without running research/OOS, a backtest,
benchmark, promotion, activation, or rollback.

`ENABLE_AUTOMATED_SELF_IMPROVEMENT_RESEARCH` is a future-runtime capability
only. It does not cause the current API to schedule or execute research. No
authentication, live market data, broker integration, or real-account behavior
is available in this skeleton.

This unauthenticated server is for local/private development only. Do not expose
it publicly; authentication/authorization, tenancy, PostgreSQL, provider/live
data wiring, mutations, broker integration, OpenAI runtime, and automatic Phase
9B runtime are deferred.

SQLite is the default local/test database backend. PostgreSQL configuration and
the opt-in migration/test workflow are documented in
`docs/POSTGRESQL_SETUP.md`; setting `DATABASE_BACKEND=postgresql` requires an
explicit `DATABASE_URL`. No connection opens simply by starting the API.

Current PostgreSQL migrations include immutable approved strategy versions and
versioned core API read snapshots. API query services remain injected until the
PostgreSQL contract has been exercised against a dedicated test database.

At FastAPI lifespan startup, unoverridden query facades now use the configured
core-snapshot repository; seeded SQLite snapshots serve the read endpoints
directly. There is intentionally no HTTP snapshot writer, live feed, or
automatic seeding. With an empty SQLite file, endpoints retain their established
safe unavailable/not-found behavior. The PostgreSQL contract still needs a
dedicated reachable test database.
