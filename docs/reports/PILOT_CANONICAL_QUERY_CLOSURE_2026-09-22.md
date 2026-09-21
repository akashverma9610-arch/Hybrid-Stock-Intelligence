# PILOT_CANONICAL_QUERY_CLOSURE

Baseline: `0edda3ea55e518f5bcd92bdc602342bd759d8d53`, `main`, clean.
Phase 1 inventory below was recorded before application edits. V1 ACTIVE;
Execution Gate V2 NOT_ACTIVE. No acquisition, migration, deployment or next slice.
Decision: **CLOSED — bounded canonical query plumbing proven, with explicit
governed-unavailable/degraded dependencies**. This does not close source freshness,
full compound/private research, prospective history or public pilot deployment.

Inspected contracts: [identity](../architecture/PILOT_IDENTITY_AND_OWNERSHIP.md),
[accepted login/binding receipt](PILOT_IDENTITY_MANAGED_LOGIN_CLOSURE_2026-09-22.md),
[legacy query adapters](../../app/api/repository_query_services.py),
[Watch store/router composition](../../app/intelligence/market_wide_watch.py),
[stored sector ranking](../../app/market_data/current_sector_rotation.py),
[P1 read service](../../app/api/p1_signal_lifecycle_query.py), and
[new canonical facade](../../app/api/pilot_canonical_query.py).

## Inventory and dependency map (before modification)

All paths below have `/api/v1` prefix unless stated otherwise. Pilot requires
verified Auth0 identity plus HSI invitation; OWNER is not a private-data bypass.
Local-only behavior must not be confused with the authenticated pilot facade.

| Surface / implemented entry | Runtime / canonical dependency | Policy, freshness and ownership | Observed cause / pilot disposition |
|---|---|---|---|
| `/market/regime` | RepositoryMarketRegimeQueryService; MARKET_REGIME typed MarketRegimeResult | Existing regime calculation only; result/evaluation timestamps; shared | 0 snapshots: MARKET_REGIME_UNAVAILABLE, not an auth or startup fix. |
| `/market/breadth` | RepositoryBreadthQueryService; MARKET_REGIME breadth/participation payload | Retains canonical breadth freshness and observation time; shared | Same family absent; governed unavailable. |
| `/market/extremes`, `/market/crisis` | Existing market-context services; UPSIDE_EXCESS_ASSESSMENT / CRISIS_ASSESSMENT | Existing risk evidence only; shared | Both families absent; do not derive from prices or Watch. |
| `/sectors`, `/sectors/{id}` | RepositorySectorQueryService; SECTOR_ANALYSIS | Legacy EvaluatedDiagnostic DTO | 0 legacy rows. Not equivalent to retained CURRENT_SECTOR_RANKING. |
| Current sector ranking | CurrentSectorRankingStore; CURRENT_SECTOR_RANKING | Stored approved current-sector-rotation-v1; no recalculation | 5 artifacts, latest 2026-09-01 14:38:33 UTC; last completed session 2026-08-30 18:30 UTC. Missing pilot presentation binding. |
| `/opportunities`, `/universe-analysis/jobs/{id}` | CoreUniverseAnalysisStore / UniverseOpportunitySnapshot | Existing universe job/candidate contract; not Watch | UNIVERSE_OPPORTUNITY count 0; OPPORTUNITY_SET_UNAVAILABLE locally, route denied at pilot ingress. No Watch-to-executable-opportunity coercion. |
| `/market-wide-watch` | MarketWideWatchStore / MarketWideWatchService | Existing canonical diagnostics/router; multi-archetype evidence | 12 runs, latest 2026-09-02 07:55:42.939690 UTC, 500 records. Broad DTO includes portfolio_records/comparison context: correctly denied in pilot. Need a shared allowlisted projection, not broad route exposure. |
| `/stocks`, `/{symbol}/analysis` | RepositoryStockAnalysisQueryService; STOCK_ANALYSIS | Legacy diagnostic/score/gates DTO | 0 snapshots; unavailable, and pilot route not authorized. |
| `/stocks/{id}/shared-brain`, `/decision-trust-envelope` | Existing SharedBrainApplicationService; diagnostic/governance/fact/news/taxonomy/setup stores | On-demand canonical read; trust envelope includes global holding lookup | Pilot denied: compound private context not yet scoped. No direct exposure of global services. Shared Watch evidence can be read without claiming full Deep Analysis. |
| Strategy eligibility | Watch archetypes/setup_policy_routes; existing HSI strategy registry and canonical approval/selection repositories | Routing is not strategy activation; PRE_BREAKOUT requires exact approved CURRENT_VALID_SETUP path; no universal horizon | Preserve multiple recorded routes, report eligibility/activation not evaluated by the query. No new strategy selection. |
| `/signals`, `/{id}` | OwnedSnapshotReader + RepositorySignalQueryService; SIGNAL | Exact ownership, existing signal timestamps/lifecycle | 0 snapshots, no fabricated legacy signals. |
| `/p1-signals/lifecycle` | ReadOnlyP1SignalLifecycleReader; prospective P1 journal schema | Explicit PIT cutoff, no backfill; pilot not yet authorized | No P1 lifecycle tables. Local P1_LIFECYCLE_SCHEMA_UNAVAILABLE; pilot denied. DC04 owns migration/source/tenant binding, not this slice. |
| Setup evidence | CanonicalSetupOpportunityStore / governed Pre-Breakout approvals | Exact source policy/as-of; Six Gates evidence-only | Do not turn stored Watch setup_state into executable setup, new gate or price. |
| `/news`, `/filings`, `/fundamentals/{symbol}` | Existing evidence query adapters; news_evidence / filings / financial facts | Shared source timestamps/provenance/warnings; canonical exact identity | Authenticated shared routes already allowed. Data existence does not establish current coverage. |
| `/portfolio`, `/holdings`, `/summary`, `/sell-side` | Request-owned snapshot adapter; PORTFOLIO | Explicit exact snapshot/fingerprint binding; no global-latest fallback | 1 OWNER-bound five-holding snapshot, dated 2026-08-30. Cash UNKNOWN. Last-known portfolio, not live valuation. |
| `/capital-rotation` | Owned rotation query; CAPITAL_ROTATION / PORTFOLIO_UNIVERSE_ROTATION | Private, comparable evidence only; no action authority | No CAPITAL_ROTATION; advanced Gate-1 V2 remains inactive. |
| Exit/sell monitoring | Existing portfolio sell-side projection; separate SELL_SIDE_DECISION | Private historical conclusions, not sell authority | 43 separate records are not implicitly adopted by the portfolio binding. Keep unavailable where no reviewed binding exists. |
| Paper/performance/benchmarks | Existing request-owned snapshot services | Private, no trading or synthetic history | No paper trades/trade plans. Missing/unbound records unavailable. |
| Provider/data/workflow health | `/data-sources/status`, `/data-operations/health`, `/runtime/status`, `/live-market/health`, `/connections/upstox` | Operator metadata can contain scope/private details; not ordinary shared research | Pilot denied unless separately audited. Preflight: Research feed/scheduler/bridge disabled; configured credentials do not prove provider validity. No provider call here. |
| Decision/audit history | Trust envelope/governance endpoints; `/pilot/admin/audit` | Protected internals and user-private decisions not shared; HSI auth audit admin-only | Auth audit operational; compound financial audit exposure remains denied. No formulas/weights exposed. |

```text
canonical stores (unchanged) -> existing typed PIT readers
                              -> allowlisted pilot read DTOs
                                 -> authenticated shared research
authorization sidecar -> request-owned reader -> existing private DTOs
```

The legacy adapters are already runtime-bound during FastAPI lifespan; missing
families are not repaired by restarting or changing provider configuration.
Retained ranking/Watch artifacts decode and verify; they require a distinct
projection because their semantics differ from the legacy diagnostic/opportunity
DTOs. Source dates are historical; do not label them fresh on read.

## Bounded implementation decision

Add an authenticated read-only canonical pilot facade for market, retained sector
ranking, Watch opportunities, and exact-instrument Watch research. Reuse existing
PIT stores and immutable verification. Explicitly omit portfolio-only records,
comparison readiness, rotation aggregates and holding context. Keep old route
contracts and deny-by-default restrictions unchanged. No new scanner/materializer.

Freshness has no universal approved TTL for these artifacts: do not invent one.
Expose canonical source/as-of/known-at references; UNKNOWN freshness is DEGRADED,
not READY. Existing breadth retains its own canonical freshness state; new retained
Watch/ranking/regime projections preserve stale/partial warnings without inventing
an age-to-STALE rule. Missing source is 503
UNAVAILABLE. Retained Watch output remains WATCH_ONLY / NON_EXECUTABLE, with
recorded multi-archetype/routing evidence, no fabricated horizon or activation.

## Implemented API / freshness contract

New routes exist only within the installed pilot identity boundary. They use the
application's existing canonical snapshot repository after normal lifespan binding:

| Authenticated GET | Data contract / missing state |
|---|---|
| `/api/v1/pilot/canonical/market` | Existing MarketRegimeResult projection; internal conditions omitted. Missing typed record: 503 MARKET_REGIME_UNAVAILABLE. |
| `/api/v1/pilot/canonical/sectors` | CurrentSectorRankingArtifact: retained benchmark, completed session, ranked sectors, Top-3, RS and breadth. Missing artifact: 503 CURRENT_SECTOR_RANKING_UNAVAILABLE. No new ranking/breadth calculation. |
| `/api/v1/pilot/canonical/opportunities` | Shared `records` of the existing Watch run, explicitly STORED_WATCH_EVIDENCE_ONLY; not UniverseOpportunitySnapshot or a new candidate detector. Missing Watch: 503 MARKET_WIDE_WATCH_UNAVAILABLE. |
| `/api/v1/pilot/canonical/stocks/{canonical_id}` | Exact canonical identity within the shared Watch run. No symbol guessing or inclusion of portfolio-only records. Missing identity: 503 CANONICAL_INSTRUMENT_WATCH_UNAVAILABLE; malformed namespace: 422. This is Watch research, not a completed Deep Analysis dossier. |

Optional timezone-aware `as_of` is the explicit read cutoff. Future/naive cutoffs
are rejected. Without it, UTC request time is used solely as the read cutoff, not
as evidence time, detection time or identity. Equal historical cutoff/input yields
stable serialized output. Publication/receipt time and source evaluation/as-of must
be eligible; evidence later than the Watch's own as-of is rejected. Pagination
reads beyond the first 100 records; a 10,000-record per-family safety bound fails
closed instead of returning a silently truncated apparent latest result.

`pilot-canonical-query/v1` returns query_as_of, status, freshness, reason_codes,
warnings, typed data and source artifact ID/fingerprint/as_of/known_at/policy.
No raw storage path, secret, private holding payload or formula/weight is returned.
Stock evidence references, diagnostic fingerprints, external-event references,
record lifecycle and blockers survive the allowlisted projection. Unknown extra
storage fields are not automatically published.

| State | Exact meaning |
|---|---|
| 200 DEGRADED / UNKNOWN | Verified retained source exists, but this source contract does not establish current freshness. FRESHNESS_POLICY_UNAVAILABLE and RETAINED_EVIDENCE_NOT_LIVE are explicit. |
| 503 UNAVAILABLE / UNAVAILABLE | Required source absent, unsupported/unverifiable provenance, identity conflict, late evidence or storage unavailable. No demo fallback. |
| READY / FRESH | Vocabulary reserved for genuinely established canonical freshness; **not emitted** by these three retained source contracts. |
| STALE | Explicit canonical freshness may be presented by existing breadth; no synthetic expiry/TTL was approved for the new views. A historical source cannot become fresh because it was just read. |

Legacy routes and schemas are unchanged. They are not silently redirected to a
different intelligence contract. Their unavailable states continue to identify
their missing required families. Future frontend binding must explicitly consume
the pilot canonical DTOs, not infer freshness from HTTP 200. Existing portfolio
timestamps, data-status and cash/mark warnings remain intact; their pre-existing
frontend tests reject transport LIVE/now substitution for source freshness.

## Strategy, horizon, identity and P1 compatibility

The stored Watch's tuple of archetypes and setup-policy routes is preserved; there
is no destructive single-strategy label, evidence rescoring or confluence engine.
Strategy eligibility is explicitly NOT_EVALUATED by this read projection, not
approval. Every Watch record remains WATCH_ONLY / NON_EXECUTABLE. Existing P1
registry resolution and Pre-Breakout governance semantics are unchanged; new
positive strategy availability is not inferred from a route or policy's existence.
Horizons/directions absent from this Watch contract stay null, without replacing
or merging separate canonical horizon-specific conclusions elsewhere.

The broad Watch DTO remains denied. Shared projections omit portfolio_records,
comparison_readiness, global score/gate values, rotation aggregates and holding
context. Original artifact IDs/fingerprints are opaque lineage references; their
inclusion does not publish the omitted source payload. Both testers receive the
same shared projection at the same cutoff. All private routes retain the existing
request-owned adapter; OWNER is not an automatic private-resource owner. Unknown
routes and non-GET methods remain denied; no token bypass or public route added.

P1_LIFECYCLE_SCHEMA_UNAVAILABLE is real: the prospective tables are absent.
The new shared Watch query does not depend on that journal and does not pretend
to supply transition/history proof. Schema/source/tenant binding remains DC04,
with five-holdings-only scope and no historical timestamp backfill. Full compound
Deep Analysis/trust envelopes, runtime health and private-derived aggregate routes
remain denied where their existing adapter is not tenant-safe; this is not a claim
that every product feature is complete.

V2 is not required to read retained shared Watch/ranking evidence. Advanced Gate-1
economic comparison and other genuinely inactive V2 dependencies remain blocked;
neither a query response nor a Watch route activates them. V1 stays ACTIVE.

## Read-only retained-data canary

Direct invocation of the new service through a read-only SQLite adapter, with
no application repository initialization, provider connection or DB write:

| Surface | Actual result |
|---|---|
| Market | UNAVAILABLE / MARKET_REGIME_UNAVAILABLE; zero typed source records. |
| Sectors | DEGRADED / UNKNOWN; source as-of 2026-09-01T14:38:33.871931Z. Warnings preserved: CURRENT_MEMBERSHIP_ONLY, HISTORICAL_BREADTH_NOT_PIT_VALID, DELIVERY_DATA_UNAVAILABLE, INFLECTION_INPUTS_NOT_MATERIALIZED. |
| Opportunities | DEGRADED / UNKNOWN; verified Watch as-of 2026-09-02T07:55:42.939690Z. Explicit retained/non-executable/eligibility-not-evaluated warnings. |

HTTP/auth wiring is independently exercised with temporary persisted canonical
fixtures and real RSA verification, not a mocked authenticated-user override.
This is **not** a new live-provider, public-frontend or managed-login canary; the
accepted preceding identity proof is retained. No live data refresh is claimed.

## Source/provider and deployment blockers

No source acquisition was required to identify missing query families. Dhan,
Upstox, NSE/BSE and AI/news provider validity was not retested and is not inferred
from credential presence or installed adapters. Preflight's disabled Research
feed/scheduler/bridge findings remain historical operational evidence, not a new
current-health claim. Fresh canonical materialization and cadence require DC07;
there is no authority here to resume BSE acquisition or enable a live feed.
CAS and advanced research/Gate-1 blockers stay parked. No provider data, formula,
policy parameter, expiry, confidence or opportunity was invented.

Controlled HTTPS hosting, frontend/auth handoff, P1 history, source cadence,
tenant-safe compound research/workspace queries and inactive V2 features remain
explicit later deployment/product work. This slice improves query plumbing, not
source coverage or global pilot activation.

## Validation / closure

- Focused new tests: 18 passed / 0 failed / 0 skipped / 2 warnings.
- Affected API/service/identity/P1 tests: 153 passed / 0 failed / 0 skipped / 2 warnings.
- Frontend contracts: 53 passed / 0 failed / 0 skipped. Sandbox attempt failed
  during OS-user lookup before assertions; identical host-context run passed.
- First focused attempt: 15 passed / 1 failed. New route used positional arguments
  for keyword-only APIRequestError, yielding guarded 503 instead of intended 422.
  Corrected only the new route; focused/relevant reruns above passed.
- Defensive checks cover future receipt/evaluation exclusion, multiple archetypes,
  no activation, fingerprint tampering, private-only records, IDOR/admin/auth
  regression, pagination, deterministic serialization and zero projection writes.
- Completed full backend: **8,853 passed / 0 failed / 6 skipped / 2 warnings**, exit
  code 0, 600.21 seconds. Skips are opt-in GDFL/GNews/Kotak/Upstox live checks and
  two PostgreSQL tests without a configured test database; not source readiness.
- Seven Markdown relative links, whitespace, secret-pattern and staged/unstaged
  `git diff --check` checks passed. No data/log/credential file is staged.
- Authorization sidecar integrity ok, FK 0; original OWNER_BOOTSTRAP and one
  OWNERSHIP_BOUND audit/binding unchanged.
- Canonical full read-only integrity_check **ok**, FK violations **0**, 593.88s.
  File metadata unchanged: 18,529,284,096 bytes, mtime_ns 1789316418469731900.
  Portfolios 1, paper trades 0, trade plans 0, canonical diagnostic results 2,074,
  generic diagnostic results 0, generic strategy versions 0; no pilot tables in
  canonical DB. No schema, source acquisition, portfolio or per-tick mutation.

Files: new `app/api/pilot_canonical_query.py`, `app/api/routes/pilot_canonical.py`,
`tests/unit/test_pilot_canonical_query.py`; four-line allowlist/router addition to
`app/api/pilot_boundary.py`; this report. Main application composition, Core
intelligence, policies, P1 modules, frontend, providers, existing schemas, credentials and
authorization/canonical DB content remain unchanged.

Next audited slice after successful DC03: **P1_PROSPECTIVE_HISTORY_PREFLIGHT_AND_BINDING**;
not started. Cadence/provider refresh remains DC07; public frontend/staging later.
