# PostgreSQL setup

Install production dependencies, configure an explicit PostgreSQL URL, then run
migrations against the intended database:

```sh
python -m pip install -e ".[dev]"
DATABASE_BACKEND=postgresql
DATABASE_URL=postgresql://user:password@host:5432/nse_stock_manager
python -m alembic upgrade head
```

Use a separate disposable database for the opt-in PostgreSQL contract test:

```sh
POSTGRES_TEST_DATABASE_URL=postgresql://user:password@host:5432/nse_test python -m pytest tests/integration/test_postgresql_approved_strategy_version_repository.py
```

The initial migration creates only the immutable `approved_strategy_versions`
table. It stores canonical enum values as checked strings, timestamps with time
zone, JSON payloads/collections, and unique immutable IDs, strategy/version,
and fingerprint values. Do not run migrations at API import or startup.

The next migration adds `core_api_snapshots` for the Phase 10 API read families.
It is immutable JSON/JSONB read-model storage with family/fingerprint uniqueness
and a family/timestamp/id index. It does not migrate every historical or
self-improvement table; the V1 API source uses this adapter only when PostgreSQL
is explicitly configured.

The V1 API read path now uses the same repository factory at FastAPI lifespan
startup. With `DATABASE_BACKEND=postgresql`, the factory chooses the PostgreSQL
core-snapshot adapter; it does not silently fall back to SQLite. The adapter is
lazy, so importing `app.api.main` does not connect. A reachable PostgreSQL
server and `POSTGRES_TEST_DATABASE_URL` are still required for the opt-in real
integration test; that validation has not been performed in this repository.
