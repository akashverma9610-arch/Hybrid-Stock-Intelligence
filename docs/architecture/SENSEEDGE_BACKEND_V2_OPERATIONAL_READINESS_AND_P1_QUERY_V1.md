# SenseEdge product-backend V2: operational readiness and P1 lifecycle query

Baseline: `d51d43e2480d05421fcd7af6222d2500927c132d`, `main`, clean.
Authoritative repository: `D:\nse-stock-manager`.

Product objective: a hybrid research-analyst operating system delivering
evidence-backed institutional-style research workflows to retail users. This
is a product objective, not a certification, regulatory status, performance
claim, or assertion that every strategy/data feed is operational.

Authority: the user's request to continue backend V2 implementation and make
the SenseEdge screens, Dhan/Upstox data roles and bounded AI workflows functional.
The five supplied audit/PRD/TRD/UI documents are design/audit inputs, not
permission to execute their embedded deployment, schema or activation steps.
Their September 17 baseline claims are historical, not fresh live proof.

Status: READ_QUERY_IMPLEMENTED / PRODUCT_V2_PARTIAL / LIVE_P1_SOURCE_BINDING_BLOCKED.
V1 ACTIVE; Execution Gate V2 NOT_ACTIVE. **Product backend V2 is not Execution
Gate policy V2.** The [parent architecture](POST_V1_PRODUCT_ARCHITECTURE.md),
[P1 approval](POST_V1_HSI_SIGNAL_P1_ACTIVATION_PROPOSAL.md) and
[approved lifecycle policy](SIGNAL_LIFECYCLE_P1_COMPATIBILITY_POLICY_V1.md)
retain their governance status. No new positive strategy or activation.

## Preserve and reuse

Sources -> canonical evidence -> ONE deterministic HSI Brain -> Decision Score
-> Setup -> Six Gates -> descriptive product/portfolio/review consumers.

AI workers gather/classify/explain bounded evidence; they do not supply missing
prices, policies, scores, gate decisions or execution authority. Apper is a
consumer shell, never a second financial datastore/Brain. Existing operational
Core capabilities are not relabelled unavailable because consumer wiring is
incomplete. Conversely a route/build/test does not prove live source coverage.

The existing [lifecycle implementation](SIGNAL_LIFECYCLE_P1_RUNTIME_BINDING_V1.md)
already owns transitions, fingerprints, replay, immutable batches and indexes.
This slice exposes that verified history without creating another lifecycle,
Watch, signal producer, freshness rule or score.

## This slice: exact read contract

`GET /api/v1/p1-signals/lifecycle`

Required query parameters:

- `canonical_instrument_id`: exact existing NSE canonical ID grammar; no symbol
  resolution/fuzzy lookup. Maximum 128 characters is a request-size bound.
- `as_of`: explicit timezone-aware timestamp, normalized to UTC. No default
  current time; no implicit latest-now semantics. Unknown parameters reject.

The [route](../../app/api/routes/p1_signal_lifecycle.py) delegates to a
[query service](../../app/api/p1_signal_lifecycle_query.py), which opens the
configured persistent SQLite file through a dedicated
[read-only reader](../../app/storage/readonly_p1_signal_lifecycle.py).
It does not accept a database path/token/source payload from HTTP callers.
No production writer constructor, migration, reconciliation, scan or provider
call runs on GET or on application startup for this feature.

The [response schema](../../app/api/schemas/p1_signal_lifecycle.py) is
`p1-lifecycle-query/v1`. It returns canonical instrument, explicit cutoff,
availability, native outcome/reason, last transition identity/fingerprint and
time/linkage fields, ordered transition IDs, and P1 observation ID/fingerprint
pairs. It deliberately omits raw setup geometry, prices, policy payloads,
credentials, holdings, quantities and source documents.

| Condition | HTTP / body | Meaning |
| --- | --- | --- |
| Verified retained chain | 200 / VERIFIED_HISTORY | Native replay at query cutoff; not refreshed provider evidence. |
| CURRENT at later unconfirmed cutoff | 200 / VERIFIED_HISTORY, SOURCE_BLOCKED, REEVALUATION_REQUIRED | Last confirmed CURRENT is retained, never shown as freshly revalidated. |
| Existing complete schema, no visible chain | 200 / NO_HISTORY, SOURCE_BLOCKED | No retained history for this identity/cutoff, not no market opportunities. |
| Corrupt/tampered chain or indexes | 200 / CONFLICTED, CHAIN_CONFLICT | No transition published; query never repairs indexes. |
| Missing lifecycle schema | 503 / P1_LIFECYCLE_SCHEMA_UNAVAILABLE | Deployment/storage unavailable, not an empty list. |
| Missing/unreadable DB, in-memory or unsupported backend | 503 / P1_LIFECYCLE_STORE_UNAVAILABLE | No alternate DB/fallback or file creation. |
| Resource bound reached | 503 / P1_LIFECYCLE_READ_LIMIT_EXCEEDED | No truncated chain promoted into a valid result. |
| Missing/naive/invalid cutoff, noncanonical ID, unexpected fields | 422 / existing safe INVALID_REQUEST | Rejected before database access; request values not echoed by Core handler. |
| POST/PUT/PATCH/DELETE | 405 | No lifecycle write surface. |

Every successful response is WATCH_ONLY / NON_EXECUTABLE, with
EXPIRY_NOT_GOVERNED_FOR_THIS_PATH. An INVALIDATED state is not a sell instruction.
The legacy `/signals` analytical/paper contract is unchanged.

## Read safety and boundedness

The reader opens `mode=ro`, enables SQLite `query_only`, and permits only read,
function and transaction authorizer operations. It has no submit/save/rebuild
methods. Connections close on success and failure. Missing paths and schema are
never created. Existing writer/read verification is shared via a read-only
mixin; writer transaction and transition behavior is unchanged.

Before body decoding: at most 2,000 eligible family batches and 16 MiB aggregate
payload are allowed. The SQL VM budget is 5,000,000 steps, with a two-second
SQLite lock timeout. These are infrastructure bounds, not financial thresholds
or a latency SLA. The family-wide bound is conservative: a large other-symbol
history can block a read, rather than trusting an incomplete index to select a
partial history. Scaling/index optimization needs separate invariant proof.

Newer batches are excluded before decoding. Payload class tags are restricted
to the exact existing immutable P1/native domain types before the generic
snapshot decoder runs; unexpected service/repository tags fail closed. Nested
payload depth is bounded. The public response is a whitelist, not raw snapshot
serialization. Stored native fingerprints are verified, never repaired.

This is an existing local API surface, **not a public ingress grant**. No CORS,
auth, HTTPS, firewall, listener, Agent/Lyzr mount or client credential handling
changes. Public consumer access remains blocked until authenticated restricted
read access and the end-user/private-data boundary are configured and tested.
Do not put a backend master token into Apper browser code.

## Production observations and remaining P1 prerequisite

Read-only production inspection on September 18 local time found:

- `core_api_snapshots` exists;
- `p1_signal_lifecycle_batch_index` and `p1_signal_lifecycle_heads` absent;
- P1_SIGNAL_LIFECYCLE_BATCH rows: 0;
- existing local live-market health: enabled=false,
  LIVE_MARKET_DISABLED / DISCONNECTED, mapped_packets=0.

No new authentication, WebSocket or historical-refresh attempt was made. These
observations do not establish a credential failure. Research Mode deliberately
keeps Dhan disabled. The previous successful backend startup/integrity proof is
historical; a new full production integrity scan is not claimed here.

Bounded GET checks against the running local backend returned `/health` 200,
`/api/v1/market-wide-watch` 200, and market/regime, sectors, opportunities 503.
Direct read-only counts confirm MARKET_REGIME, SECTOR_ANALYSIS and
UNIVERSE_OPPORTUNITY snapshot families are each empty. These counts do not mean
the underlying financial/history/sector evidence is absent. In particular,
current-sector ranking is a different canonical artifact, not an interchangeable
SECTOR_ANALYSIS payload. The legacy runtime cycle marks regime/sector adapters
deferred and publishes a dictionary runtime-market-state receipt, not the
MarketRegimeResult required by the regime query. Running that cycle alone is
therefore not a justified fix for the missing API result. No cycle was run.

The new P1 query service was also exercised directly against the production
file in read-only mode at an explicit cutoff; it returned the expected safe
503 P1_LIFECYCLE_SCHEMA_UNAVAILABLE. The existing backend process was not
restarted/deployed with the new route in this slice. HTTP response and router
registration proof uses isolated TestClient fixtures, not a claimed live P1 API.

The owning-store `CanonicalSourceReader` still needs verifiable dependency
closure, native eligibility and retained known-at for every source. Watch
evaluation time/snapshot creation time is not a substitute for evidence receipt
time. Production admission cannot be enabled simply by applying the migration.
Missing historical timing must remain blocked; prospective capture must use
real observations, not reconstructed/backdated timestamps. No migration,
production emission or production-data mutation is performed by this slice.

## Screen-to-capability completion map

Page inventory comes from the supplied PRD/UI report. This is not a claim that
the original screenshots or all Apper screens were visually retested here.
CORE_PRESENT below means reusable code exists; LIVE_UNVERIFIED means this slice
has not proved current production coverage/permissions/end-to-end UI behavior.

| Product screen/workflow | Existing canonical owner to reuse | Consumer operational gap |
| --- | --- | --- |
| Home / command centre | Market, sectors, Watch, opportunities and runtime read services | CORE_PRESENT; bounded summary mapping, coverage/freshness and UI E2E pending. |
| Market Regime | `/api/v1/market/regime`, breadth/crisis/extremes routes | CORE_PRESENT; LIVE_UNVERIFIED; preserve canonical confidence and constraints. |
| Sector Intelligence | `/api/v1/sectors`, current-sector ranking/rotation stores | CORE_PRESENT; consumer mapping and current coverage proof pending. |
| Opportunity Scanner | `/api/v1/opportunities`, `/api/v1/market-wide-watch` | CORE_PRESENT; analyzed-universe coverage, canonical filters/pagination and E2E pending. |
| Pre-Breakout | Governed assessment/candidate/opportunity, existing selection repositories | CORE_PRESENT conditionally; no valid setup if policy/data absent; no new strategy. |
| Stock Research / Deep Analysis | `/api/v1/stocks/{symbol}/analysis`, shared-brain, decision-trust-envelope | CORE_PRESENT; canonical ID adapters, dossier tabs/lineage and no-mock E2E pending. |
| Fundamentals | Financial facts, diagnostic registry, fundamentals query | CORE_PRESENT; metric/accounting/PIT gaps stay explicit, not estimated. |
| Technical / live prices | Dhan live read model; canonical technical/Upstox historical evidence | CORE_PRESENT; Dhan disabled in observed Research runtime; bounded live proof pending. |
| Catalysts / news / risks | External-intelligence -> News -> existing Brain; news query | CORE_PRESENT; workflow liveness/source coverage and UI evidence traversal LIVE_UNVERIFIED. |
| Signals | P1 projector plus approved lifetime journal and this GET | READ_QUERY_IMPLEMENTED; production source binding/storage rollout blocked; demo not live. |
| Portfolio / Intelligence | Existing portfolio, holding intelligence, analysis read services | CORE_PRESENT; private-user authorization, dataset mapping and E2E pending; no mutation. |
| Rotation | Existing comparison/challenger and capital-rotation reads | CORE_PRESENT; V2 economics/policies remain separately blocked; never automatic ROTATE. |
| Sell/Risk / Exit Monitor | Existing sell-side analysis and bounded review policies | CORE_PRESENT; descriptive review mapping only; draft TRIM/EXIT wording grants no action authority. |
| Alerts | Retained event/lifecycle provenance | Delivery, deduplication, permissions and acknowledgement require a bounded contract; not claimed implemented by this GET. |
| Evidence / Decision Audit | Canonical references, trust envelope, audit reconstruction | CORE_PRESENT; consumer traversal, access filtering and missing-reference E2E pending. |
| Data Health | Data-source/data-operation/runtime and provider status | CORE_PRESENT; screen integration must distinguish liveness from freshness/completeness. |
| Agent / Workflow Health | Existing local AI worker, ingestion/reevaluation and runtime receipts | CORE_PRESENT; end-to-end worker/inbox/runtime proof pending, no new Agent-first Brain. |
| Watchlists / notes / saved filters | Presentation/user state, not HSI canonical facts | USER_STATE_APPROVAL_REQUIRED for store/ownership/irreversible Apper connection; no schema created. |
| Settings | Existing safe connection status and local controls | CORE_PRESENT; consumer roles/secrets boundary and screen E2E pending. |
| MF / IPO discovery | Separate product-specific contracts required | No equity-score reuse; broader product strategy activation remains out of scope. |

## Provider and AI roles

- Dhan: reuse existing exact mapping and live-market runtime/read models;
  market-hours freshness/disconnect/reconnect proof before LIVE labelling. No
  broker/order calls or new sockets from a screen GET.
- Upstox: reuse existing governed historical ingestion, normalization, provider
  versions and conflict retention. It is not a silent fallback for unavailable
  Dhan live evidence. No credential rotation or acquisition in this slice.
- AI: reuse canonical external-intelligence ingress, factual layer separation,
  provenance, deduplication and bounded reevaluation; tools select/explain
  deterministic capabilities. No invented evidence/thresholds or authority.

Additional strategies are considered only after a specific missing product
capability is established. Primary-source methodology research, canonical-data
feasibility, exact versioned policy, isolated tests and shadow evidence precede
any positive classification. Internet research is not empirical validation or
automatic strategy approval. Unavailable policies remain unavailable.

## End-to-end operational acceptance, not a design-only finish

1. Close source provenance and migration/recovery prerequisites without
   modifying historical evidence; test prospective and stale/conflict cases.
2. Verify local market -> opportunity -> stock -> evidence/audit reads on real
   retained data. No provider refresh or whole-universe scan during GET.
3. Configure an approved restricted HTTPS read ingress and server-side
   authentication/user access. Accounts, credentials and irreversible app-state
   provisioning require the owner's external setup/choice, not guessed values.
4. Replace Apper demo data one verified screen at a time. Loading, unavailable,
   partial, stale, conflict and unauthorized states are first-class. No mixed
   demo/live metrics or fabricated zeroes.
5. Validate Dhan, Upstox and AI workflow health/recovery in their separate
   operational contexts, with no trading action or undisclosed data fallback.
6. Validate private portfolio read access and then bounded alerts/personal
   state only under their approved ownership contract.
7. Full regression, UI build/E2E, source freshness, restore/recovery and security
   proof are required before declaring the complete product operational.

## Validation and review receipt

Tests: [query proof](../../tests/unit/test_p1_signal_lifecycle_query.py) plus
existing lifecycle, P1A/B/C, governance, setup, storage and API hardening tests.
The 31 new cases are included in 902 passing focused/relevant cases with two
existing dependency warnings. Complete backend regression: **8,758 passed,
0 failed, 6 skipped, 2 warnings**, 482.45 seconds. The six skips are opt-in live
provider and PostgreSQL tests; this is not a live-provider validation claim.

Existing repository frontend production build passed. Its `npm run lint`
(TypeScript check) fails at PortfolioScreenshotImportModal.tsx line 72 with
three existing contract errors: `include`, `instrumentId`, `averagePrice` are
not fields of Partial<ReviewedPortfolioHolding>. This screen references a
different review/draft shape from the currently declared portfolio types; do
not hide the mismatch with casts or guessed portfolio mappings. No frontend
file changed here. A dedicated import-review contract repair/E2E proof remains
required before claiming all screens functional. No real import was attempted.

All nine local Markdown links pass. New-file whitespace and `git diff --check`
pass. No production migration, data write, provider call, AI run, background
refresh, broker/order call, portfolio mutation, public bind or secret change.

Review corrections include rejecting unexpected stored class tags before
dynamic decoding and distinguishing schema absence from empty history. The
source-pin conformance helper permits exactly the new router import/mount;
historical governance artifacts remain unchanged and all other pinned source
bytes are still compared. No investment policy, provider, source timestamp,
auth/CORS configuration, portfolio or execution boundary was changed.

## September 19 continuation: local read consumer and cloud boundary

The local Stock Intelligence page now includes a dedicated
[P1 retained-history panel](../../frontend/src/components/production/P1LifecyclePanel.tsx).
Its [read client](../../frontend/src/api/p1Lifecycle.ts) calls only the existing
P1 GET contract; it does not reuse the legacy `/signals` mapper, which marks
generic successful requests LIVE and supplies a current timestamp. There is
no new backend policy, writer, migration, source binding or production activation.

The operator explicitly supplies a timezone-aware cutoff for the exact current
canonical instrument. No runtime timestamp is substituted. The client preserves
microsecond cutoff distinctions, checks the returned identity/cutoff and fixed
Watch-only authority, rejects malformed/contradictory envelopes, and forwards
only whitelisted display fields. It does not independently recalculate backend
fingerprints or claim that browser validation establishes source authenticity.

Requests are GET-only, bounded at six seconds, cancelled on unmount/context
change, omit credentials, reject redirects, and never fall back to mock data.
This local operator transport is not a future authenticated cloud transport.
HTTP is permitted only for loopback origins. No secret or provider configuration
is read, generated or changed. No history is requested in demo mode.

`NO_HISTORY`, `CONFLICTED`, `SOURCE_BLOCKED`, schema absence and transport failure
are distinct. A retained CURRENT is last confirmed qualification, not continuous
freshness; a later blocked result retains the native reevaluation reason. The
page displays no prices, targets, quantities or trading commands in this panel.

The existing Apper Signals screen was updated through its connected plugin to
show this integration boundary and response meanings. Apper build commit
`c426acb63c96abfc32aca04da9e764a83b7bfcbf` completed successfully. It remains a
demo: no HSI data, private portfolio, credentials or local database were uploaded.
The owner confirmed no public HTTPS HSI origin is configured. A private read
authentication/access design and explicitly configured ingress are prerequisites;
the existing ingestion token is not permission to expose arbitrary read APIs.
No account, tunnel, firewall rule, Apper database or public listener was created.

A read-only SQLite metadata check confirmed `core_api_snapshots` exists but
`p1_signal_lifecycle_batch_index` and `p1_signal_lifecycle_heads` are absent in
the current production database. This is a concrete deployment prerequisite,
not empty market history. No schema was created and no payload was read or
uploaded by that check. The existing runtime-binding document also requires
verified owning-store known-at provenance before production admission; merely
creating those tables would not complete the source-binding prerequisite.

Focused frontend validation:
`node --experimental-strip-types --test tests/p1Lifecycle.test.ts` from
`frontend/`: 20 passed, zero failures. Node 22 reports experimental type-stripping
and mock-timer warnings. The preinstalled `tsx` loader failed before test loading
with Windows `uv_os_get_passwd / ENOMEM`; native type stripping runs the same
tests without installing dependencies or altering environment configuration.
Backend query reconfirmation: 31 passed, two existing dependency warnings.
Post-correction API/source-governance regression: 631 passed, two existing
dependency warnings. The first consumer full-suite run found two source-pin
failures (8,756 passed, 2 failed, 6 skipped, 2 warnings): mounting the panel
inside the frozen ProductionPages file violated its byte-for-byte contract.
The panel now mounts in the outer App composition; ProductionPages is unchanged.
No frozen source-pin test or historical artifact was weakened. A frontend test
also checks the original page fingerprint and the additive mount.
Frontend production build passed. Type checking still reports only the three
pre-existing portfolio-import contract errors described above; they are not
suppressed or patched by this P1 slice.

Browser smoke: the built local page renders the explicit-cutoff panel; submitting
a historical cutoff with the backend offline shows
`UNAVAILABLE / P1_TRANSPORT_OR_RESPONSE_UNAVAILABLE`, not mock/empty/live history.
No positive production-chain or fresh-provider proof is claimed. Final corrected
full backend regression completed: **8,758 passed, 0 failed, 6 skipped,
2 warnings**, 503.06 seconds, exit code zero. The skips remain opt-in live
provider/PostgreSQL checks; the warnings remain existing TestClient dependency
deprecations. This does not validate live Dhan/Upstox connectivity.

Final frontend build passed (1,691 modules); 20 frontend checks passed. All
11 local Markdown links resolve, whitespace checks and `git diff --check`
pass. Local changes remain uncommitted; no Git push was performed. Apper's
separate saved build is identified above. V1 remains ACTIVE; Execution Gate
V2 remains NOT_ACTIVE. The complete consumer product is still PARTIAL.

## Follow-up: private-access decision and screenshot review contract repair

The owner chose an initial owner-only, browser-based domain/login deployment,
not retail multi-user activation or a device VPN. No domain or Cloudflare
account is presently configured. Proposed names supplied by the owner are
`hybridstockintelligence.com` and `hybridstockintelligence.co.in`; these are
not registered/owned/available-domain claims. No purchase, account creation,
login, tunnel installation or public exposure has been performed.

The three earlier frontend type errors are now resolved in the unused
[screenshot review modal](../../frontend/src/components/portfolio/PortfolioScreenshotImportModal.tsx).
Inspection found missing general-client methods and a draft shape unrelated to
the canonical screenshot API, not merely three misspelled keys. The separate
[review contract](../../frontend/src/api/portfolioImportContract.ts) maps exact
backend snake_case fields into a bounded view, retains Decimal strings/nulls,
rejects malformed/duplicate rows, and does not invent a canonical identity.
Existing general portfolio summary types and read clients remain unchanged.

The modal now requires an explicitly injected import capability; none is wired
in production. Missing capability and demo mode disable upload/confirmation.
It is not mounted on a route by this repair. Review edits retain decimal text;
duplicate/unresolved/non-positive included rows block confirmation. Unknown
confirmation outcomes lock further confirmation rather than blindly retrying.
Only an explicitly confirmed result can notify the parent of a snapshot.
No HTTP writer, OCR provider, source upload, persistence or portfolio update
was added or exercised. The pure mapping function has no network side effects.

A distinct blocker remains before enabling imports: the legacy
`GovernancePortfolioImportPersister` constructs zero-valued cash, unlike the
existing manual-import path's explicit `CashState`. This inspection is not
permission to assume the owner's cash is zero. A separately reviewed canonical
cash/provenance contract and end-to-end confirmation proof are required before
the screenshot write capability can be wired. No backend behavior was changed.

Validation: 29 frontend tests passed (20 P1 plus 9 review-contract/render cases),
`npm run lint` passed, frontend production build passed, and 6 existing isolated
portfolio screenshot API tests passed with 2 existing dependency warnings.
The render proof checks the actual React modal in both no-adapter and demo
states, without uploading a file or confirming an import. Full backend was not
rerun for this frontend-only follow-up; the preceding completed 8,758-pass
result remains the latest backend result, not a new run claim. This follow-up
changes only the modal, its contract/tests and this documentation. Existing
uncommitted P1 work is preserved; no commit or push has been made.

Private browser ingress is still a setup/design prerequisite. Cloudflare's
[private web application guide](https://developers.cloudflare.com/cloudflare-one/setup/secure-private-apps/private-web-app/)
describes browser access with owner email authentication and a tunnel. Any HSI
deployment must additionally restrict exact read paths, deny unrelated routes,
verify access enforcement at the origin, avoid browser service secrets, and
prove unauthenticated access fails. Existing intake-token authority is not
extended. Separate-origin Apper requests must not bypass login or receive a
privileged token as a CORS workaround. No such deployment has been activated.
