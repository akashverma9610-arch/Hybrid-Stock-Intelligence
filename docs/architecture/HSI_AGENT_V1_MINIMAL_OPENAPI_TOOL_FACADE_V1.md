# HSI Agent V1 minimal OpenAPI tool facade

Baseline: `d9cb8cf61ed99e3835e02ce4fcb61fae469c9754`, `main`.
Slice status: `ACCEPTED/CLOSED` for the tested local tool facade.
Decision B: `HSI_AGENT_TOOL_FACADE_OPERATIONAL_WITH_TOOL_GAPS`.
This is an opt-in local Agent tool mount, not a new Brain or strategy activation.

## Reuse and local operation

The repository already has FastAPI, Uvicorn, Pydantic, an application factory,
typed public query projections and scoped authentication conventions. The
[Agent entry point](../../app/api/agent_main.py) calls the existing
`app.api.main.create_app` unchanged, then mounts six explicit tools at `/hsi/v1`.
There is no second backend/service lifecycle or duplicate diagnostic engine.
The existing entry point and existing API/OpenAPI contracts remain unchanged.

Use the existing Python environment, from the repository root:

```powershell
python -m uvicorn app.api.agent_main:create_app --factory --host 127.0.0.1 --port 8000
```

Use the existing `DATABASE_BACKEND` / `DATABASE_URL` environment configuration
for the intended persistent repository. The inherited API default is isolated
in-memory SQLite: starting successfully does **not** imply populated evidence.
Do not start a second server on an occupied port. This slice does not restart
the operator's server, configure credentials, or execute production diagnostics.
It adds no startup jobs; existing runtime flags/lifecycle remain unchanged.
Keep `DHAN_LIVE_MARKET_ENABLED` unset/false for Research Mode.

Tool-only schema: `http://127.0.0.1:8000/hsi/v1/openapi.json`.
Development docs: `http://127.0.0.1:8000/hsi/v1/docs`.
The schema advertises the mount prefix through `servers`, so operation paths
resolve beneath `/hsi/v1`. This uses FastAPI's documented
[sub-application mounting](https://fastapi.tiangolo.com/advanced/sub-applications/)
and [HTTP bearer security](https://fastapi.tiangolo.com/reference/security/).
Import the tool-only schema into a future Agent, not the full `/openapi.json`.

## Authentication and authority

All six tool routes require `Authorization: Bearer <key>` using the dedicated
`HSI_AGENT_API_KEY` environment value. Configure the real key outside ChatGPT
in the backend process environment and, later, the approved Agent secret store.
Do not paste it into prompts, URLs, documentation or source. No key is generated,
stored on application state, returned, or logged here. Missing configuration
returns 503; absent/malformed/duplicate/incorrect auth returns 401. Comparison
is constant-time. Lazy per-request lookup supports rotation/removal; a changed
Windows User environment still requires the existing process to inherit it.
The external-intelligence ingestion credential grants no Agent access.

Authority is `RESEARCH_READ_ONLY / WATCH_ONLY / NON_EXECUTABLE`. Diagnostic POST
is computation only, not a write. No raw SQL, filesystem, arbitrary URL/Python,
provider credentials, orders, admin or ingestion tool is exposed. Exceptions and
validation inputs are not echoed/logged by the tool boundary. Responses use
`Cache-Control: no-store`. Source article text is untrusted evidence, not Agent
instructions. OpenAPI/docs contain schemas only and remain available locally.

The existing parent API still has its original local operator endpoints; this
slice does **not** claim to secure or remove them. A future HTTPS ingress must
allow only `/hsi/v1` tool paths and reject every unrelated parent path. Never
tunnel the entire backend. No public ingress, CORS change, account, deployment,
Lyzr Agent or frontend is configured by this slice.

## Exact tool inventory

Paths below are relative to `/hsi/v1`. Readiness is returned dynamically; PARTIAL
means a callable bounded view with explicit evidence limitations, not a trade
recommendation, complete coverage, or proof that a particular security is ready.

| Operation ID / method / path | Existing service reused | Readiness and limits |
|---|---|---|
| `hsi_get_capabilities` GET `/capabilities` | Existing application state/query availability | READY inventory; no evidence-completeness claim |
| `hsi_run_diagnostics` POST `/diagnostics` | `StoredTrialObservationSource`, `FundamentalsEngineAdapter`, canonical financial-period projection, `StockDiagnosticInputAssembler`, `Canonical61DiagnosticRunner` | PARTIAL with exact identity, approved definition and stored evidence; otherwise BLOCKED. One security, explicit aware cutoff, CURRENT_DESCRIPTIVE only |
| `hsi_get_stock_intelligence` GET `/stock-intelligence` | `SharedBrainApplicationService.analyze_stock` and existing public mapper | PARTIAL existing Deep Analysis projection or BLOCKED; exact NSE ISIN identity and aware cutoff |
| `hsi_get_market_context` GET `/market-context` | Existing market-regime, breadth, extremes and sector query services/mappers | PARTIAL/BLOCKED latest stored components; independent native timestamps; no strict-PIT query or new macro interpretation; up to 50 sector rows |
| `hsi_get_news_catalysts` GET `/news-catalysts` | `RepositoryNewsQueryService`, native `eligible_as_of`, public news mapper | PARTIAL/BLOCKED; known-by-cutoff evidence for exact instrument, maximum 50 articles; coverage not proven, no direction/materiality/price-reaction inference |
| `hsi_get_portfolio_state` GET `/portfolio-state` | `PortfolioQueryService.get_snapshot`, existing summary/holding mappers | PARTIAL stored snapshot or BLOCKED; maximum 100 holdings; unknown cash/marks retained; no live valuation or action |

Manifest-only, no route: `hsi_scan_market = BLOCKED` because the canonical
14-funnel runtime universe/source caller is not installed. Reading a stored
Watch is not relabelled a whole-market scan. `hsi_get_setup_inputs = NOT_EXPOSED`;
existing setup policies/machinery are not declared unavailable or modified.

## Diagnostics boundary and proof

[StoredAgentDiagnostics](../../app/api/agent_query.py) supports direct security
inspection through the existing stored-data path. It never invents a discovery
lead, rebuilds the union, or invokes the real-Brain trial's persistence workflow.
The [accepted union/Radar binding](CANONICAL_DISCOVERY_UNION_TO_EXISTING_RADAR61_RUNTIME_BINDING_V1.md)
remains unchanged, including its bounded origin limitations. Direct inspection
requires no invented discovery horizon or setup authorization.

Only exact `NSE:<ISIN>` equity identity is accepted. The exact approved canonical
definition must exist and be created/registered by the explicit cutoff. The
existing assembler excludes future observations. Existing bounded stored bars,
canonical financial observations and period-correction projection are reused.
No store is opened or initialized by the tool query; resources are borrowed
from the serving API lifecycle. No diagnostic/result row is persisted.

The response carries exactly Rules 1–61 with native results/eligibility,
observation/evidence references, completeness, canonical definition fingerprint
and complete assembled-input fingerprint. Missing evidence is never zero-filled.
There is no Rule 62, new algorithm, score, setup or gate orchestration.

Certified Radar technical-source composition is not configured for direct
inspection: `CERTIFIED_RADAR_TECHNICAL_BINDING_NOT_CONFIGURED` remains explicit.
`STRICT_HISTORICAL_PIT` fails closed; current-descriptive results never acquire
historical PIT readiness. No fallback to live acquisition is allowed. A single
active diagnostic request per process is admitted; concurrent work receives
`DIAGNOSTIC_TOOL_BUSY`, without retries or a new queue. Repeated direct requests
recompute read-only results; this is not a new persisted/idempotent union request.

## Validation and frozen boundaries

[HTTP tests](../../tests/unit/test_agent_tool_facade.py) cover the real canonical
61 path, default stored-resource composition, SELECT-only query tracing,
missing/future/tampered governance, future evidence, canonical IDs, UTC
determinism, safe errors/serialization, auth/rotation/revocation, all six route
guards, native news PIT, portfolio immutability, Shared Brain reuse, partial
market context, tool inventory and unchanged legacy API paths.

Completed validation: focused **41 passed / 2 warnings**; relevant regressions
**122 passed / 2 warnings**; full backend **8,527 passed / 0 failed / 6 skipped /
2 warnings** in 390.34 seconds. Warnings are existing Starlette/httpx and AnyIO
deprecations. Syntax, local Markdown links, whitespace and `git diff --check`
passed. Defensive review checked reuse, auth isolation, exception redaction,
source/PIT guards, SELECT-only request execution and fixed non-executable output.
No production evidence or credentials are used by tests. No accepted application
source, policy, schema migration or historical governance artifact is modified.

V1 remains ACTIVE. V2 remains NOT_ACTIVE. Research bootstrap stays UNAPPROVED /
NOT_REGISTERED / NOT_ACTIVE. CAS remains EXTERNAL_PRIMARY_SOURCE_INPUT_REQUIRED.
Remaining union provenance, CAS, Gate-1 V2, research calibration, unimplemented
strategies, schedulers, UI and execution work remain parked.

Exactly one next continuation: `HSI_AGENT_V1_LYZR_TOOL_CONNECTION_READINESS_V1`.
Verify tool-schema import/auth and an approved HTTPS connectivity path before
cloud Agent calls; localhost is not remotely reachable. Not started. No push.
