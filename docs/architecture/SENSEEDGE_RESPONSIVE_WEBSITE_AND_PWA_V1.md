# SenseEdge responsive website and PWA presentation V1

Status: `LOCAL_PRESENTATION_IMPLEMENTED / LIVE_EVIDENCE_PARTIAL / PRIVATE_DEPLOYMENT_PENDING`

This presentation slice follows the owner's three Opportunities, Signals and
My Portfolio design images and decision to build a responsive website plus
PWA before a separate native app. It does not activate strategies, Execution
Gate V2, trading authority, AI automation or a completed consumer product.
Core V1, the frozen ProductionPages implementation and all governance remain
unchanged. Existing uncommitted work is preserved.

## Visual and behavioral reconciliation

| Reference | Implemented presentation | Evidence/activation boundary |
| --- | --- | --- |
| SenseEdge dark shell, cyan accent, sidebar and search | New scoped shell, exact-ID search or canonical-directory navigation | No guessed company identity; owner badge is not authentication |
| Opportunities metrics, filters, selected card and intelligence rail | Existing Watch counts, archetype/text filtering, selected lineage/blockers and explicit CSV export | No artificial horizon, return, confidence, entry zone or eligibility |
| My Portfolio summary/table/sector panel/review tabs | Existing read-only summary and holdings; exact Decimal text in holdings; sector counts | Cash UNKNOWN remains UNKNOWN; no invented health score, price, cash or value allocation |
| Signals metrics, selected signal and lifecycle | Explicit canonical ID and explicit cutoff into the existing P1 reader | No bulk signal-list fallback, legacy actionable feed, invented accuracy or synthetic expiry |
| Snapshot BUY/SELL, strength, targets and rotation hurdle | Not reproduced as authority or fact | Only governed evidence; P1 remains WATCH_ONLY / NON_EXECUTABLE |
| Mobile layout | Two-column metrics, scrollable tables, collapsible menu and fixed bottom navigation | Same evidence semantics; no separate mobile Brain |
| PWA | Manifest, vector icon, secure production-only worker registration, install control and offline fallback | Browser/device installation remains to be verified; not an App Store release |
| Ask HSI, online profile and notifications | Explicit pending-state notices | No fake chat, fake login or fabricated unread count |
| Portfolio History / Rotation | Explanation and links to existing evidence views | No fabricated transaction history, forecast, replacement instruction or portfolio writer |

Home reuses the Watch research overview, not a new detection engine. Legacy
Stock/Live/Rotation/Intelligence pages remain available in a neutral light
content surface within the new shell. Dev Console retains its existing shell.
Existing Apper cloud output is separate and is not updated by this local slice.

## Source and safety rules

The [read hook](../../frontend/src/components/senseedge/useSenseEdgeEvidence.ts)
calls only existing Watch, portfolio holdings/summary, news and market read
methods. It clears prior display on refresh/client change and ignores stale
completion after unmount. No acquisition, provider reconnect, portfolio
import, strategy computation or broker operation is called.

The source panel exposes envelope availability/freshness/warnings. Its response
timestamp is explicitly *not* canonical evidence as-of. Watch timestamps and
fingerprints remain source fields. Counters may overlap; decorative rings are
labelled as non-score illustrations, never confidence or market performance.
Displayed records may be retained/stale; no runtime time promotes them to live.

The [Signals view](../../frontend/src/components/senseedge/SenseEdgePages.tsx)
reuses the [P1 reader](../../frontend/src/components/production/P1LifecyclePanel.tsx)
without changing its explicit-cutoff, timeout, schema-validation, cancellation
or demo-unavailable behavior. Production native P1 persistence/provenance gaps
remain as recorded in the [earlier readiness audit](SENSEEDGE_BACKEND_V2_OPERATIONAL_READINESS_AND_P1_QUERY_V1.md).

CSV export is an explicit local user action, retains unavailable values, and
neutralizes spreadsheet formula prefixes. It does not publish a report.
No secrets, authentication tokens, sample people, screenshots or portfolio
data are embedded in the new source assets.

## Offline and installation boundary

The [worker](../../frontend/public/senseedge-sw.js) caches **only** public
`offline.html` and the SenseEdge icon. It never caches app HTML, JSON, API
responses, financial models, holdings, credentials or private evidence.
Only root navigation without query parameters gets an offline fallback;
API/cross-origin/non-GET requests are not intercepted. Activation cleans only
the worker's own versioned public-fallback cache prefix, not unrelated caches.
Registration occurs only in secure production contexts, never Vite development.

This does not claim that all browser/HTTP storage is disabled; the guarantee
concerns this PWA's explicitly bounded cache. On loss of connectivity an open
screen flags that values are not live. A cold offline visit shows no financial
data, only a reconnect page. Native push and offline trading are not included.

Private owner-only HTTPS/domain/login is still unconfigured. No tunnel, public
binding, third-party account, credential or firewall change was made. The
phone cannot reach the owner's PC by using `127.0.0.1`; secure private browser
deployment is required before remote phone use. Installation menu availability
depends on the actual browser/device. A separate Android/iOS app is deferred.

## Validation

- Frontend regression: 41 passed / 0 failed (20 P1, 9 screenshot review, 12 presentation/PWA).
- TypeScript check and production build passed.
- Browser: Opportunities, Portfolio and Signals navigation verified; 390 × 844
  viewport has no document-level horizontal overflow. Tables scroll internally.
- Portfolio History truthfully reports its missing query contract. Signals
  rejects a symbol-only input; canonical identity reveals the existing cutoff
  form with Read history disabled until a cutoff is entered.
- Desktop 1600 × 1000 layout checked; final default viewport restored.
- Backend unavailable during browser proof: no live financial result, device
  installation, authentication or provider connectivity is claimed.
- Full backend suite was not rerun for this frontend-only slice. The previous
  completed 8,758 passed / 0 failed / 6 skipped / 2 warnings is historical,
  not fresh validation of an active backend.
- Frozen ProductionPages fingerprint is checked by the existing frontend test.
- Documentation links, whitespace and `git diff --check` checked before handoff.

Implementation remains uncommitted. No push. No backend, database, credentials,
provider or investment-policy changes in this responsive/PWA slice.

## Follow-up: retained backend mapping and five-holding capture scope

The preceding presentation and P1 read work was committed and normally pushed
to `origin/main` as `2d4906b6051a80f04f49738d74fc0a8e0a0171c9` on September 19.
The earlier uncommitted/offline validation statements describe that earlier
checkpoint, not the current local runtime.

The existing local launcher was started with Dhan disabled. No provider refresh,
external acquisition, lifecycle writer, broad diagnostic run or trading workflow
was invoked. Local reads were checked against the existing persistent database.
These checks prove retained-data access, not current market completeness.

| Screen / dependency | Observed result | Remaining boundary |
| --- | --- | --- |
| Backend health | HTTP 200 | Process liveness only |
| Opportunities / native Watch | HTTP 200; 500 evaluated universe records, 2 active native Watch records, 0 valid setups | Source as-of `2026-09-02T07:55:42.939690Z`; not fresh market coverage |
| Portfolio summary / holdings | Both HTTP 200; five holdings; explicit UNKNOWN cash | Retained snapshot; missing marks/unrealized P&L stay unavailable |
| News | HTTP 200 with retained articles | No continuous worker/current-news completeness proof |
| Market regime | HTTP 503, `MARKET_REGIME_UNAVAILABLE` | No canonical regime snapshot; do not fabricate from a generic runtime receipt |
| P1 lifecycle | HTTP 503, `P1_LIFECYCLE_SCHEMA_UNAVAILABLE` | No production source adapter/admission or retained journal schema |
| Dhan live health | Disabled / disconnected, zero mapped packets | Research Mode; no authentication or market-hours packet proof attempted |
| Public browser / mobile access | Not configured | Owner domain, private authentication and restricted HTTPS ingress still required |

### Exact mapping correction

The new [portfolio reader](../../frontend/src/api/canonicalPortfolioSummary.ts)
maps `marked_value`, `invested_value`, `unrealized_pnl`, `cash`, `cash_status`
and `as_of` from the existing summary contract. Decimal strings remain exact;
null never falls back to an unrelated alias or becomes zero. Unrealized P&L
is not labelled as total/day/realized return. No portfolio-health score is
computed. Demo mode does not request or synthesize the private summary.

The reader is additive: frozen `httpClient.ts`, its interface and mock client
remain unchanged. It uses one exact GET, no route fallback, no-store,
redirect rejection, omitted credentials, a bounded six-second timeout and
unmount cancellation. Non-loopback plaintext origins and credential-bearing
origins reject. This is a local operator transport, not a private cloud-auth
implementation. Raw error bodies/exceptions are not displayed.

The presentation hook no longer promotes legacy HTTP-success `LIVE`/wall-clock
metadata into evidence freshness. Retained reads expose UNKNOWN freshness
(an explicit source STALE state is preserved);
Watch and holding cutoffs remain canonical where present. Different domains
are independent reads, not a newly synthesized coherent Brain snapshot.
The market panel does not display the legacy client's internal LIVE/now defaults.

Only native `WATCH_ACTIVE` records appear in the default Watch list. The optional
all-record view is labelled **Evaluated records (includes blocked)** and exposes
the exact native Watch state. Evaluated coverage is not opportunity eligibility,
and Watch activity is not a valid setup or P1 qualification.

### Approved prospective scope, not capture activation

The owner selected **only the existing five portfolio holdings** for the first
prospective lifecycle-history collection scope. This authorizes neither
whole-universe collection nor backdated history. Their exact canonical identities
must be obtained from the existing owning records, never fuzzy symbol matching.
At this audit cutoff the inspected native records for APARINDS, DEEPINDS,
GENUSPOWER, GLAND and ICICIBANK all report `NO_CURRENT_SETUP`. Some native Watch
records remain active; that does not satisfy the approved P1 setup predicate.

Production P1 admission remains blocked until the existing `CanonicalSourceReader`
can verify every owning-store reference, retained known-at timestamp and complete
dependency closure. Snapshot/evaluation time cannot replace missing evidence
receipt time. Creating lifecycle tables alone would not solve this. No schema,
source ledger, historical timestamp, admission result or lifecycle batch was
created by this mapping follow-up. Capture is **not yet running**.

The next bounded implementation is the prospective owning-source/provenance
adapter and admission preflight for that five-holding scope, reusing the existing
P1 journal and predicate. Missing provenance/setup must remain SOURCE_BLOCKED or
otherwise fail closed under the native contract, never fabricate a CURRENT signal.

### Defensive validation

The first mapping regression run completed with 8,756 passed, 2 failed, 6 skipped
and 2 warnings. Both failures pinned frozen `httpClient.ts` bytes. The attempted
additive method was removed from that frozen file and placed in the separate
reader above. No source-pin test, historical artifact or Core behavior was
relaxed. The exact two affected governance suites then passed all 595 tests
with two existing dependency warnings.

Frontend regression after correction: 53 passed, zero failed. TypeScript check
and production build passed. Browser proof used the built app with the local
backend: exact retained portfolio fields/UNKNOWN cash, native active Watch
filter and labelled 500-record view, and the precise P1 missing-schema blocker.
At phone width the document does not overflow horizontally; tables scroll
inside their own containers. No private data was uploaded to Apper or GitHub.
Corrected complete backend regression: **8,758 passed, 0 failed, 6 skipped,
2 warnings**, exit code zero, 689.46 seconds. Opt-in provider/PostgreSQL skips
are not live-feed proof. Both warnings are existing TestClient dependency
deprecations. No intermediate percentage was treated as completed validation.

Read-only SQLite verification completed: `integrity_check = ok`, foreign-key
violations = 0; FinancialFacts = 6,118; CorporateFilings = 455; PORTFOLIO
snapshots = 1; generic strategy_versions = 0; generic diagnostic_results = 0;
P1 lifecycle batches = 0; PAPER_TRADE and TRADE_PLAN snapshot families = 0.
P1 indexes remain absent; MARKET_REGIME and SECTOR_ANALYSIS snapshot families
remain empty. The summary reports cash UNKNOWN. Database size and modification
timestamp remained unchanged during this follow-up; no production write,
schema rollout, source refresh, broker/order or portfolio operation was invoked.
Private database contents, operational logs and generated build output are
excluded from the source commit. The scope decision does not change activation:
Core V1 ACTIVE, Execution Gate V2 NOT_ACTIVE, product live-evidence coverage PARTIAL.
