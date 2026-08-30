# Runtime pipeline

`RuntimeCycleCoordinator` is the explicit #028A boundary for one stored-data or
mock runtime cycle. `RuntimeScheduler` (#028B) is a small in-process guard
around that boundary; it does not duplicate cycle execution logic.

## Safe defaults

`RUNTIME_SCHEDULER_ENABLED=false` is the default. FastAPI startup does not
construct, start, or schedule a runtime worker. `start()` records enabled
in-process scheduler intent only; it creates no thread or timer. A future host
or CLI may call `run_once()` explicitly, including while continuous scheduling
is disabled.

`RUNTIME_CYCLE_INTERVAL_SECONDS` is typed and must be positive. `RUNTIME_MODE`
is `STORED_DATA` or `MOCK`; a failed configured mode is visible and never falls
back silently to mock. `RUNTIME_UNIVERSE_ID` is status metadata only; the
coordinator continues to require its explicit point-in-time universe.

## Operational behaviour

Only one `run_once()` may execute per scheduler instance. A concurrent request
is skipped with an auditable safe event. `CLOSED` market sessions are skipped,
not failures. `POST_CLOSE` is left to the existing stored-data coordinator
semantics. A cycle exception increments `consecutive_failures` once and returns;
this foundation owns no immediate retry loop or reconnect behaviour.

`RuntimeHealthService` exposes immutable read-only operational status:
configuration/running flags, most recent cycle timestamps/status/data-as-of,
failure count, and safe warnings. It is intentionally separate from `/health`,
so a partial or failed data cycle cannot make the API process unhealthy.

Before a host composes a coordinator, `DataSourceCompositionService` can report
whether requested runtime inputs are ready, degraded, or missing. It retains
stored-data capability separately from live-provider capability and never
substitutes mock data unless mock mode/source is explicitly selected. See
[data-source architecture](DATA_SOURCE_ARCHITECTURE.md).

Safe in-memory audit events record scheduler start/stop, skips, and failures;
they contain no credentials or raw provider payloads.

## Boundaries and deferrals

`python -m app.runtime run-once --universe <id>` is the local explicit command
boundary. `--dry-run` calls the same coordinator with `publish=False`, so no
snapshot is written. `status` reads health only; it never triggers a cycle.
`worker` is a local opt-in interval loop and refuses to start unless
`RUNTIME_SCHEDULER_ENABLED=true`. It waits after every synchronous cycle, so a
slow cycle cannot overlap the next one; Ctrl+C requests cooperative shutdown.

FastAPI deliberately remains worker-free. It exposes only
`GET /api/v1/runtime/status`, a safe read-only view of in-process status; there
are no run/start/stop control routes. Runtime status is process-lifetime only.

There is no automatic market-data ingestion, provider/network call, WebSocket,
broker/account action, order, portfolio mutation, Phase 9B operation,
promotion, or activation. A host-integrated worker remains deliberately
deferred until an explicit data/universe composition is approved. Real provider
validation is still pending.
## Canonical fundamentals to stock analysis

The STOCK stage remains skipped by default. An explicitly composed stored-data runtime may supply `FundamentalsEngineAdapter` and an existing stock-analysis builder. For each instrument the adapter produces PIT-safe, scope-consistent legacy financial observations and factual filing context; the supplied builder may then publish its normal immutable stock-analysis snapshot. This hook starts no provider, scheduler, broker, promotion, activation, or account workflow.
Historical ingestion remains an explicit composition operation. GDFL bars, once validated and stored, are consumed through the normal historical-bar store; runtime analytics do not import provider-specific code.
## Optional news enrichment

Runtime analysis can remain operational when no news provider is configured.  News absence is reported as optional/research incompleteness, never as evidence that no news exists.  A future opt-in ingestion stage may persist normalized evidence before an existing stock-analysis/research adapter reads it; it performs no network access by default and cannot create scores, signals, promotions, approvals, activations, or live-account effects.
## Optional primary-market context

Runtime can compose stored primary-market facts into the existing Market Extremes IPO input when supplied.  Missing IPO data remains optional/unavailable and never fails a runtime cycle.
# Optional bounded yfinance ingestion

The `validate-yfinance-frozen-stock` and `ingest-yfinance-frozen-cohort`
commands are explicit operator actions, not scheduler stages. They write only
canonical daily bars and provider mappings for the pre-existing frozen 40-stock
cohort. The later stored-data Brain run does not call yfinance or any provider.
