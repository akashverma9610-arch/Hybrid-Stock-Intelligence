# Frontend API contract

Base path: `/api/v1`. JSON decimals are serialized as strings. All timestamps
are timezone-aware ISO-8601 values. A `404` means a requested record is absent;
a `503` means the backing read service is unavailable. List endpoints use an
empty `items`/`sectors` array for a valid empty state. `null` is unavailable or
not applicable—not numeric zero.

`GET /api/v1/capital-rotation` may include public-safe opportunity coverage and
universe/eligible/analyzed/qualified counts when its persisted evaluation is
bound to an analyzed immutable universe snapshot. `PORTFOLIO_ONLY` means no
such bridge exists; it is not a full-market claim.

## Endpoint inventory

| Method and path | Consumer | Public response / notable fields | Empty, partial, freshness |
| --- | --- | --- | --- |
| `GET /health` | boot check | `{status:"ok"}` | Always lightweight; no source claim. |
| `GET /system/status`, `/system/version` | System Health | app/environment/version and feature capability states | Feature status is independent of provider readiness. |
| `GET /runtime/status` | Dashboard/System Health | scheduler and last-cycle state, `last_data_as_of`, warnings | Null cycle timestamps are an idle/empty state. |
| `GET /data-sources/status` | Dashboard/System Health | source family/provider/readiness, validation, freshness policy, warnings | `MISSING_CONFIGURATION`, degraded, and unavailable are valid operational states. |
| `GET /portfolio`, `/portfolio/summary`, `/portfolio/holdings` | Portfolio/Dashboard | cash/value/P&L/heat, holdings, `data_as_of`, warnings | Nullable marked values/P&L mean incomplete marks. |
| `GET /capital-rotation` | Capital Rotation | distilled stored holding/candidate comparison, published score advantage, confidence, R:R, sector/catalyst context, eligibility, action, rationale, `data_as_of`, warnings | `READY`, `PARTIAL`, `EMPTY`, and `UNAVAILABLE` are normal read states. It never runs a scan or makes an allocation. |
| `GET /market/regime` | Dashboard/Stocks | regime, confidence, status, `data_as_of`, conditions/warnings | Returns service error if no public regime record exists. |
| `GET /market/breadth` | Dashboard | persisted canonical breadth/participation facts, coverage/freshness, warnings | No stored breadth returns unavailable; no data is never rendered as NORMAL. |
| `GET /market/extremes` | Dashboard | market-level canonical upside-excess state, cycle stage, top-confirmation flag, public context and warnings | A state is environmental risk context, not a trade instruction; no scores, factors, thresholds, or provenance are public. |
| `GET /market/crisis` | Dashboard | persisted canonical crisis state, timestamps, distilled transition rationale and warnings | No data returns unavailable. Crisis is a risk overlay, never an automatic liquidation or dip-buying instruction. |
| `GET /sectors`, `/sectors/{sector_id}` | Dashboard/Sectors/Stocks | phase, rank, RS/score/confidence, `data_as_of`, warnings | Empty `sectors` is valid; fields may be null under partial coverage. |
| `GET /stocks` | Stocks | persisted stock-analysis summaries: identity, public score/confidence/status, `data_as_of`, freshness, warnings | It reads stored public snapshots only; it never scans the universe, fetches providers, or runs analysis. Empty is valid. |
| `GET /stocks/{symbol}/analysis` | Stock detail | identity, data/as-of/status, market context, **distilled** score/confidence, public category status, gate status, warnings | Score/gates and sections can be null/partial. No diagnostics/rules/weights/gate internals or audit provenance IDs are returned. |
| `GET /signals`, `/signals/{id}` | Signals | lifecycle, public score/confidence, distilled trade structure, timestamps, public warnings | Empty list is valid. No diagnostic, gate, evidence, or provenance IDs are returned. |
| `GET /paper-trades`, `/paper-trades/{id}`, `/paper-trades/performance` | Paper Trading | lifecycle, plan/fill/outcome/MFE/MAE/P&L, timestamps and warnings | Missing outcome values remain null; unavailable performance is 503. No source/evidence/provenance IDs are public. |
| `GET /performance`, `/performance/{id}` | Performance | stored strategy metrics, sample status, warnings | Pagination: `limit`, `offset`; nullable metrics are unavailable. The UI requires explicit report selection because no current/latest ordering is part of this contract. |
| `GET /benchmarks`, `/benchmarks/{id}` | Performance | stored benchmark comparison/alignment/classification/warnings | Pagination/filter params: benchmark/report/mode. The UI requires explicit comparison selection and does not merge unrelated reports. |
| `GET /governance/strategy-versions`, `/governance/active-strategy`, `/governance/promotions`, `/governance/promotions/{id}` | Settings/System Health | public version/promotion state and dates | Read-only governance state; no approval/activation mutations exist. |
| `GET /filings`, `/filings/{id}` | Stock/News | factual filing metadata, attachments, announced/effective/reporting timestamps | Empty list valid; query params are backend-defined. |
| `GET /fundamentals/{symbol}`, `/fundamentals/{symbol}/series` | Stock | canonical facts/snapshot `data_as_of`, scope, quality/provenance | Null latest periods and quality flags communicate incomplete data. |
| `GET /news`, `/news/{id}` | News/Stock | title/description/URL/publisher/source quality/category/timestamps | Empty list valid; show supplied description only. |
| `GET /primary-market/issues`, `/{id}`, `/primary-market/summary` | Primary Market/Dashboard | factual issue sizes/types/dates, summary coverage and `data_as_of` | Use query `from`, `to`, `type`, sector, or `as_of`; absent outcome is not a zero return. |
| `GET /connections`, `/connections/{provider}` | Settings | redacted configured/validated/status/capability/last test/warnings | Never includes a credential value. |
| `PUT /connections/{provider}`, `POST .../test`, `DELETE .../credentials` | Settings only | redacted profile/test response | Only allowed configuration mutations; request secrets use password inputs and must not be retained by client. |

## Contract rules

- Query pagination defaults are backend-owned; list response `total`, `limit`,
  and `offset` must drive pagination.
- Display `data_as_of`, `calculated_at`, `generated_at`, and source freshness
  whenever returned. Never make a browser-side freshness calculation.
- Render `warnings` without suppressing the base result. A partial value is
  still distinct from a fabricated zero.
- Use only the response fields documented by the Pydantic OpenAPI schema. Raw
  persistence/domain objects are not frontend contracts.
- Capital rotation uses only `GET /capital-rotation`. It is a projection of an
  already persisted canonical evaluation, not a browser or API-side rotation
  calculation. Optional `holding_symbol`, `candidate_symbol`, and bounded
  `limit` filters narrow published comparisons only.
- Rotation responses deliberately exclude diagnostic/rule IDs and lists,
  component weights, gate IDs/formulas, internal thresholds/hurdles, ranking
  inputs, evidence IDs, configuration versions, and friction internals. Public
  `ROTATE`, `WATCH`, `HOLD`, and `NO_ACTION` labels are analytical only.
- No API route creates broker orders, real-account activity, promotion approval,
  or strategy activation.
- Market breadth, extremes, and crisis are snapshot read models. Requests never
  call providers, aggregate market data, run an engine, or alter runtime state.
- Signals, paper trades, reports, and benchmarks are read-only public
  projections. The browser must not render or reconstruct diagnostics, score
  components/weights, gate formulas/IDs, evidence IDs, provenance, or secret
  strategy configuration.
- Portfolio screenshot intake uses `POST /portfolio/import/screenshots` for
  multipart extraction only, followed by explicit `POST
  /portfolio/import/{import_id}/confirm`. Draft rows are provisional and never
  mutate holdings until a user submits reviewed `REPLACE` rows. Screenshot
  current price is informational only. The API omits raw OCR text, image bytes,
  account data, and proprietary diagnostic or gate internals.
- `POST /portfolio/analysis-jobs` explicitly queues a job for an exact persisted
  portfolio snapshot. `GET /portfolio/analysis-jobs` and `GET
  /portfolio/analysis-jobs/{job_id}` expose only status, actual holding progress,
  timestamps, safe warnings, and `analysis_completeness`. They do not expose the
  diagnostic inventory, evidence IDs, score weights, thresholds, or gate logic.

## CORS and client configuration

Set `VITE_API_BASE_URL` to the backend origin. Set backend `CORS_ORIGINS` to
explicit frontend origins; `*` is rejected by API settings and CORS credentials
are disabled. Provider keys and backend database URLs are never frontend
configuration.
# Opportunity set (read-only)

`GET /api/v1/opportunities` reads the latest persisted bounded universe
opportunity snapshot. Optional `limit` and `sector` filters never initiate a
scan. `GET /api/v1/universe-analysis/jobs/{job_id}` reads public-safe progress.
Neither response exposes the 61-rule inventory, individual outcomes, evidence,
gate IDs, thresholds, or ranking formula.

The response carries only safe aggregate coverage (`universe_count`, eligible,
complete/partial/unavailable analysis counts, and qualified-candidate count).
`GET /api/v1/universe-analysis/jobs/{job_id}` includes the literal durable
backend stage and coverage counts. `GET /api/v1/capital-rotation` includes
opportunity coverage plus complete/partial analysis counts and rotation status;
the browser must use these values verbatim and must not infer full NSE coverage.

## Data-source and real-data readiness

`GET /api/v1/data-sources/status` is the backend-declared source readiness
contract used by Settings/System Health. `configured` and `validated` are
separate fields; the UI must never label a configured provider as live or ready
without `validated=true`. It contains no credential values. The current public
API has no endpoint that starts an NSE import or a full scan; those are explicit
local runtime commands only.
