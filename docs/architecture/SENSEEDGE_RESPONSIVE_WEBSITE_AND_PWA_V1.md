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
