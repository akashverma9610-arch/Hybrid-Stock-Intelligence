# HSI Agent V1 Dhan Whole-Market Shared Scan

Baseline: `9f75df98ada5c8f394da718996007f9a48bdd51a` on `main`.

Status: `IMPLEMENTED / PARTIAL_SOURCE_COVERAGE / WATCH_ONLY / NON_EXECUTABLE`.
Decision B: `HSI_AGENT_MARKET_SCAN_OPERATIONAL_WITH_DATA_GAPS`.
This is a local fixture-proven shared query path, not proof of a live whole-NSE
feed, fourteen active strategies, paid redistribution permission, or deployment.
V1 remains ACTIVE; V2 remains NOT_ACTIVE. No governance policy is activated.

## Existing foundations and exact gap

The [Agent facade](HSI_AGENT_V1_MINIMAL_OPENAPI_TOOL_FACADE_V1.md),
[whole-market runner](MULTI_FUNNEL_WHOLE_MARKET_ORCHESTRATION_V1.md),
[Dhan prospective foundation](PROSPECTIVE_DHAN_LIVE_BAR_FOUNDATION_V1.md) and
[prospective runtime](PROSPECTIVE_MARKET_DATA_RUNTIME_ORCHESTRATOR_V1.md) are reused,
not replaced. The registry, adapters, union, Radar orchestrator and canonical
61-rule runner remain unchanged.

The existing runner **adapts retained canonical funnel artifacts**; it does not
calculate five new detectors over arbitrary live ticks. Dhan ticker LTP does
not contain the volume/continuity evidence needed for prospective technical
evaluation. The separate Quote-mode runtime, one-minute builder and immutable
canonical fifteen-minute store remain operator-owned, disabled by default,
and unchanged. This slice reuses `DhanProspectiveInstrumentIdentity` validation
but does not start that runtime or subscribe additional securities.

| Concern | Actual binding | Limitation |
| --- | --- | --- |
| Universe | `CoreUniverseAnalysisStore.instruments_as_of`, bounded native store-envelope capture, `build_universe_snapshot` | Stored scope is not proof of complete current NSE membership; CAS/PIT gaps remain. |
| Eligibility | Exact NSE ISIN, native EQUITY/main-board rule, existing ACTIVE/tradable metadata boundary | Unknown main-board is not silently reclassified; no new history threshold. Non-active, unsupported and malformed rows remain in coverage accounting. |
| Mapping | One local stored mapping-family read; exact Dhan identity contract | Missing/inactive/future/ambiguous mapping or absent EQ/master evidence remains blocked; no master download or symbol resolution. |
| Market state | Existing backend Dhan runtime `quotes(now=explicit_cutoff)` | Native LIVE/STALE is quote freshness at scan time, not session-open proof or sufficient OHLCV evidence. |
| Volume/1m/15m | Existing prospective runtime and stores inspected, not duplicated | No automatic volume-to-discovery binding; explicit gap, never a zero-volume default. |
| Pre-Breakout | Stored canonical setup opportunity family into existing adapter | No setup calculation or policy activation. |
| Sector Rotation | Stored Top-3 run family into existing adapter | Exact stored constituent inspection leads, not fresh sector recomputation. |
| Inflection / Compounder / Policy Transmission | Existing native adapters remain available for injected canonical observations | Default production composition has no observation reader for these; SOURCE_UNAVAILABLE, not a successful empty whole-market scan. |
| Other nine funnels | Native unavailable adapters and registry classifications | Contextual holding/watchlist state never becomes an unconditional NSE scanner. |

## Shared computation and operator boundary

```text
existing shared Dhan feed/update path -> canonical live/bar stores (unchanged)
                                                    |
operator explicit cutoff -> local universe + mapping/quote coverage
                          + stored canonical funnel artifacts
                          -> existing 14-funnel orchestrator
                          -> existing candidate union
                          -> one immutable shared snapshot
Agent GET requests        -> retained snapshot only
selected finalist         -> existing governed Radar61 binding separately
```

`app.intelligence.shared_market_scan.SharedMarketScanService.refresh(as_of=...)`
is the bounded operator entry point. The opt-in Agent application exposes the
single instance as `application.state.agent_market_scan_service`. After its
existing lifespan initializes the canonical resources, host-owned Python code
can explicitly call:

```python
snapshot = application.state.agent_market_scan_service.refresh(as_of=cutoff)
```

`cutoff` must be an explicitly selected timezone-aware datetime. It is normalized
to UTC. The operator must execute this in the **serving application process**;
starting another Python interpreter does not refresh the serving cache. There
is no HTTP refresh route, startup scan, scheduler or new runtime launcher.

One nonblocking refresh lock prevents overlapping scans in that service. Native
family reads are paginated and capped at 20,000 stored records; input roster and
quotes are capped at 20,000, mappings at 40,000. Exceeding a bound fails rather
than silently truncating. These are resource bounds, not investment parameters.
Mapping/quote indexing avoids per-security repository/provider calls.

The latest eight immutable snapshots are retained in **process-local memory**.
This is an explicit V1 limitation: one serving worker shares snapshots across
all its users, but cross-worker/cross-host sharing and restart durability are
not implemented. No SQLite family is repurposed and no raw market data is
persisted again. Existing generic snapshot storage was inspected; a new durable
snapshot family is unnecessary for this bounded proof and is not added.

Same cutoff plus identical content returns the retained snapshot; changed
content at the same retained cutoff raises `MARKET_SCAN_SAME_CUTOFF_CONFLICT`
and preserves the first snapshot. Operators must use a new explicit cutoff for
new evidence. Retention eviction is not a freshness policy or historical archive.
Future-dated snapshots are excluded at read time. No synthetic TTL is introduced.

## Snapshot, API and evidence accounting

`GET /hsi/v1/market-scan`, operation ID `hsi_scan_market`, requires the existing
dedicated Agent Bearer key. It accepts an optional aware `as_of` read cutoff;
omission uses current UTC **only to select an already-computed snapshot**, never
to alter its identity or source interpretation. No key enters a snapshot.

- No snapshot: governed HTTP 200 BLOCKED / `SHARED_MARKET_SCAN_REFRESH_REQUIRED`.
- Valid stored snapshot: HTTP 200 PARTIAL with exact scan/source timestamps,
  native fourteen-funnel coverage, full canonical candidate union and origins,
  explicit blockers and `deep_diagnostics_run=false`.
- Malformed/tampered snapshot: BLOCKED with safe fixed code, no exception text.
- POST is not provided; missing/invalid authentication fails as before.

Shared scan ID/fingerprint covers the native batch fingerprint and per-security
coverage lineage. The native batch includes its universe, registry, executions,
source references and full union. Quote fingerprints cover exact mapping,
price and both timestamps without returning provider routing tokens or prices.
Snapshot verification detects changed nested content. Native union serialization
is preserved, not replaced with a second candidate contract.

Metrics distinguish source roster, eligible universe, exact mappings, fresh
quotes, quote insufficiency, identity blocks, exclusions, conflicts, proven
examined securities, unproven evaluation coverage, candidate count and blocked
funnels. Native adapters cannot prove evaluation of every eligible security:
`securities_examined_proven` counts only exact emitted identities;
`evaluation_coverage_unproven` exposes the remainder. Fresh LTP is **not** a
claim of data readiness for all funnels. Per-funnel source counts/leads and
outside-universe lead exclusions remain auditable in the retained native batch.
Operational elapsed duration uses a monotonic timer and is excluded from identity.

Market-closed/stale data retains exact source timestamps and native STALE state;
there is no historical-price fallback, invented session-completion claim or TTL.
The maximum market-data timestamp is a convenience summary; per-security times
remain visible and must not be interpreted as a common market snapshot time.

## Cost and authority firewall

Shared work: feed/update infrastructure, canonical NSE identity, stored funnel
evidence adaptation, candidate union and the snapshot. Later per-user work:
portfolio comparison, explicit stock diagnostics and bounded finalist reasoning.
That later work is not invoked here. One hundred Agent reads do not create one
hundred scans. No LLM, Lyzr, per-stock web search, fresh news acquisition or Dhan
REST call runs in the shared scan path. No token billing or monetary model is added.

Cached governed news remains the future source for a news adapter; fresh web
research belongs to finalists or explicit user questions, never an NSE loop.
No second Brain, feed, universe registry, funnel engine, union, diagnostic runner,
portfolio input, user preference, score bonus, broker/order call, V2 activation,
gate evaluation, automated action or frontend change occurs.

## Validation and remaining proof

Focused fixtures cover canonical source binding, native Dhan freshness, exact
mapping/ambiguity/revocation, future receipt exclusion, scope accounting,
immutable replay/conflict/retention, stable UTC identity, source isolation,
authenticated repeated HTTP reads, all-origin deduplication and cost guards.
A selected saved candidate separately passes the unchanged real Radar61 binding
and exactly 61 rules; the scan itself invokes zero diagnostics.

Verification and native union serialization occur during operator refresh;
Agent reads parse the retained immutable JSON, never rebuild the universe or
union. A regression test makes both native builders fail if called after refresh
and proves that repeated reads still work without mutating the stored response.

Completed validation for this slice:

| Validation | Result |
| --- | --- |
| Focused shared scan + Agent facade | 81 passed, 0 failed, 2 warnings |
| Discovery, Dhan/data, universe and API regressions | 215 passed, 0 failed, 2 warnings |
| Complete backend suite | 8,567 passed, 0 failed, 6 skipped, 2 warnings; 400.75 seconds |
| Local Markdown links / syntax / whitespace | Passed |
| `git diff --check` | Passed |

Warnings are the existing Starlette/httpx and AnyIO deprecations. Optional live
provider/PostgreSQL integration skips are not live validation claims.

Isolated HTTP canary: one eligible security, one exact Dhan mapping, one fresh
fixture quote, one proven examined security, one candidate, no identity blocks,
exclusions or conflicts, one executed Sector Rotation adapter and thirteen
blocked funnels. Quote insufficiency was zero for this fixture only. Measured
scan duration was approximately 0.0143 seconds. Two HTTP 200/PARTIAL reads were
identical after one refresh; missing authentication returned 401. This is not a
whole-market timing benchmark or a production coverage count.

No live Dhan connection, production refresh, production data mutation, paid-user
deployment, account change or credential operation was performed. Whole-market
currentness, prospective volume/technical source binding, research-observation
readers and cross-process snapshot sharing remain explicit gaps. This document
does not claim those capabilities merely from the successful fixture path.

Exactly one next continuation (not started):
`HSI_AGENT_V1_SETUP_TOOL_EXPOSURE_AND_END_TO_END_WORKFLOW_V1`.
