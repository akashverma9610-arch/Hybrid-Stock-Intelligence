# Google AI Studio frontend specification

## Product boundary

Build a desktop-first, responsive research dashboard for a private NSE research
and paper-trading application. The frontend is a presentation and interaction
client only. It talks to the FastAPI REST API through `VITE_API_BASE_URL` (for
example, `http://127.0.0.1:8000`) and contains no analysis, scoring, provider,
or broker credentials.

The backend is authoritative for every calculation: decision score, confidence,
market regime, market extremes, sector state, technical/fundamental summaries,
capital-rotation result, gates, paper outcomes, performance, and source health.
The frontend must format and display supplied values only.

The Capital Rotation view must show opportunity coverage and public-safe counts.
Under `PARTIAL`, it uses “best candidate among analyzed opportunity set”; only
an immutable fully processed supported NSE equity universe may be described as
the analyzed NSE equity universe. API mode never substitutes mock opportunities.

## Target user and design language

Target a serious individual investor/researcher who needs an auditable overview
of stored and optionally connected data. Use a clean institutional dashboard:
compact cards and tables, clear typography, restrained charts, accessible labels
and icons, and no crypto-style flashing or dense terminal clone. Support light
and dark themes with semantic tokens: `primary`, `positive`, `negative`,
`warning`, `critical`, `neutral`, `muted`, `surface`, and `border`. Do not convey
an action only by colour.

Desktop is the primary target. Collapse card grids to two columns for tablet and
one for mobile; tables should become scrollable or card rows without hiding a
status, warning, timestamp, or risk field.

## App map

Primary navigation:

1. Dashboard
2. Portfolio
3. Capital Rotation
4. Stocks
5. Signals
6. Paper Trading
7. Performance
8. Primary Market
9. News
10. Settings / Connections

Optional secondary navigation: System Health.

All pages need the same explicit visual states:

| API state | UI behaviour |
| --- | --- |
| loading | Skeletons; do not substitute zeros. |
| empty | Explain that no stored record is available. |
| ready | Render supplied fields and their `data_as_of` / freshness. |
| partial | Render known fields plus warnings and coverage limitation. |
| degraded / unavailable | Show safe API error or source status; retain unaffected cards. |
| error | Show a retry affordance for the read request only; never retry a mutation automatically. |

Freshness badges use backend values only: `LIVE`, `DELAYED`, `EOD`, `STALE`, or
`UNKNOWN`. The browser clock must not infer data freshness.

## Page requirements and API mapping

### Dashboard

Compose existing read endpoints; no dashboard aggregation endpoint is required
in V1. Use market regime, sectors, portfolio summary, signals, runtime status,
and source status. Render cards for Market State, Market Extremes when an
approved backend field is later available, breadth/participation when supplied,
sector leadership, portfolio summary, and latest signals. Missing market-extreme
or breadth values are `unavailable`, not neutral or zero.

### Portfolio

Use `/portfolio`, `/portfolio/summary`, and `/portfolio/holdings`. Show cash,
marked value, P&L, heat, holdings, and warnings. Existing holdings do not yet
include decision score, action, or execution state; show these only after a
future explicitly approved distilled portfolio view model is provided. No order
buttons belong in this UI.

Holding rows navigate only to `/stocks/{symbol}`. A Portfolio link may open the
separate read-only Capital Rotation page; it must not construct a comparison.

### Capital Rotation

Use `GET /capital-rotation` in a separate tab. Render its backend-published
overall state, snapshot freshness/as-of time, optional market regime, portfolio
summary, and distilled comparison cards. Show only the supplied holding/candidate
labels, score advantage, risk/reward, confidence, sector/catalyst context,
public eligibility summary, rationale, and `HOLD`, `WATCH`, `ROTATE`, or
`NO_ACTION` label. Do not reconstruct a comparison, compute thresholds, or add
an order button. `ROTATE` is analytical only and never executes rotation.

### Stocks

Use `GET /stocks` for the persisted bounded list, then `/stocks/{symbol}/analysis`
for a selected record. The list is never a request to scan or analyse the
market. The detail payload deliberately includes only
identity, data status, distilled analysis coverage, score/confidence, high-level
gate state, per-category availability, and warnings. It does not return raw
diagnostics, rule identifiers, component weights, or gate internals. Build the
overview, market context, technical/fundamental/research/risk section status
from these backend fields. The current API has no approved public text summary
for support/resistance, momentum, valuation, or six-gate details; show category
status rather than inventing it. Audit provenance/evidence IDs are not frontend
fields.

### Signals and Paper Trading

Use `/signals`, `/signals/{id}`, `/paper-trades`, `/paper-trades/{id}`, and
`/paper-trades/performance`. Display lifecycle, score, confidence, trade-plan
prices, invalidation/catalyst text where provided, outcome, MFE/MAE, P&L, and
warnings. These are read-only paper records; do not create, fill, or execute
trades from the frontend.

### Performance

Use `/performance` and `/benchmarks`, including detail endpoints when needed.
Show returned return/CAGR/drawdown/Sharpe/Sortino/expectancy/profit-factor,
turnover/cost/capital efficiency, sample status, and comparison warnings. Null
metrics mean unavailable, not zero.

### Primary Market and News

Use `/primary-market/issues`, `/primary-market/issues/{id}`, and
`/primary-market/summary` for factual issue data. Use `/news` and `/news/{id}`
for title, publisher, source quality, event category, filing linkage, and
timestamps. Do not create an IPO score or reproduce copyrighted full article
text.

### Settings / Connections and System Health

Use `/connections` plus each provider-specific profile. Password fields are
never prefilled and must never be placed in localStorage. A submitted secret is
sent only to the existing explicit connection route; response rendering uses
configured booleans and redacted status only. System Health composes
`/system/status`, `/system/version`, `/runtime/status`, and
`/data-sources/status`.

## Reusable components

Create typed components around the API contract: `ApiClient`, `StatusBadge`,
`FreshnessBadge`, `WarningList`, `MetricCard`, `DataStatePanel`, `CompactTable`,
`ConnectionCard`, `EmptyState`, and `ErrorState`. The API client owns base URL,
timeout, JSON parsing, request error handling, and abort handling. Pages must
not implement fetch or error parsing individually.

## Privacy and safety constraints

Never expose or calculate the proprietary 61-point diagnostic framework. In
particular, do not expose diagnostic/rule IDs, diagnostic lists, rule results,
component weights, weighted contributions, internal gate IDs, gate parameters,
or backend provenance intended for audit internals. Do not calculate decision
score, confidence, regime, crisis/euphoria, sector phase, rotation thresholds,
technical indicators, earnings acceleration, or six-gate outcomes in the
frontend.

Do not store backend/provider secrets in source code, browser storage, analytics,
logs, error reports, or mock data. Do not add broker, order, funds, holdings,
demat, real-cash, or live-account UI flows. The only initial mutations are the
existing local connection credential routes.

## Signals, paper trading, performance, and benchmark views

Signals and paper-trade records are informational-only: display only their
public distilled fields and link symbols to stock detail. There are no BUY,
SELL, execute, create, close, or lifecycle mutation controls. Performance and
benchmark contracts contain summary metrics, not an equity curve or benchmark
time series; use KPI/table views rather than fabricating charts. The report and
benchmark list contracts do not designate a current record or guarantee a
latest ordering, so both views require explicit keyboard-accessible selection
before fetching their detail endpoint. In API mode, a backend error is shown as
unavailable/error—never as a mock value.

## Dashboard market context

The Dashboard displays exact read-only `/market/breadth`, `/market/extremes`,
and `/market/crisis` projections when persisted data exists. It renders the
backend status, freshness, timestamps, and warnings literally and never derives
participation, euphoria, or crisis values in TypeScript. Absence is
unavailable—not NORMAL. EUPHORIA is elevated speculation/chase-risk context;
it is neither a confirmed market top nor a SELL instruction. Crisis likewise is
context only, not an instruction to liquidate or buy a dip.

## Mock-data and connection rules

During UI development a synthetic fixture may be used only behind an explicit
`MOCK` flag and banner. Mock values must be visibly synthetic and must not use
diagnostic internals. In normal mode, calls use the configured base URL and
backend errors remain safely classified. No provider secret belongs in a Vite or
other frontend environment variable; `VITE_API_BASE_URL` is the only required
frontend setting.

For local development, the backend allows only explicit origins. Configure its
`CORS_ORIGINS` to the actual dev origin (for example `http://localhost:5173`);
wildcard origins are rejected.

## Portfolio screenshot intake

The Portfolio page provides a browser-only bounded JPG/PNG/WebP upload modal
with drag/drop, picker, clipboard input, previews, and explicit review. Files
are never put into browser storage. API mode has no extracted-holdings fallback;
mock mode is visibly synthetic. The user must edit/review rows and explicitly
confirm `REPLACE`; unmatched or ambiguous symbols are never guessed. The UI
does not calculate diagnostics, scores, gates, or analysis from screenshot LTP.

## Portfolio analysis job

After a confirmed portfolio, the user can explicitly queue `Analyze Portfolio`.
The browser sends only a persisted snapshot reference and displays backend job
status/progress. `COMPLETED` and diagnostic completeness are shown separately:
an operationally completed job can truthfully remain `PARTIAL` when providers
or rule inputs are unavailable. The browser never runs diagnostics or chooses a
candidate universe; full NSE scanning is outside this feature.
# Opportunity set

Capital Rotation may show a backend-derived Full Opportunity Set panel. It must
distinguish portfolio holdings from intended-universe coverage and show an
explicit partial warning. The frontend never calculates scores, diagnostics,
confidence, gates, candidates, or rotation decisions, and API mode has no mock
opportunity fallback.

Show backend-provided opportunity coverage, universe/eligible counts, analyzed
complete and partial counts, qualified-candidate count, and rotation comparison
status. When coverage is `PARTIAL`, show the explicit “analyzed opportunity
set” warning. A job stage, if displayed, is a literal backend value such as
`COVERAGE_PREFLIGHT`, `ANALYZING`, `CANDIDATES_MATERIALIZED`, or `COMPLETED`.

## Real-data source status

Settings and System Health consume the exact backend data-source status route.
Show `configured`, `validated`, status, freshness, and safe warnings verbatim.
Do not store credentials in the browser, infer live validation from an HTTP
success, or display a fake quote/feed when a provider is missing or unvalidated.
