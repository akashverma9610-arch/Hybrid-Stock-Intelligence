# P1 prospective history runtime closure — 22 September 2026

Slice: **P1_PROSPECTIVE_HISTORY_PREFLIGHT_AND_BINDING** (same bounded slice).
Baseline: `f422052165ed861158cf5a3600ac31c4e04adf2d`, `main`, verified clean.
Decision: **PARTIAL**. No push, deployment, provider activation or next slice.

V1 remains **ACTIVE**; Execution Gate V2 remains **NOT_ACTIVE**. P1 admission
continues to use the existing approved Pre-Breakout path. Gate V2 is not the
cause of the remaining source-provenance blocker. All exposed P1 states remain
**WATCH_ONLY / NON_EXECUTABLE**. No trading authority is introduced.

## Source audit: implemented components versus missing proof

| Owning contract | Available canonical semantics | Remaining limitation |
| --- | --- | --- |
| [Historical market data](../../app/market_data/historical.py) and [provenance](../../app/market_data/models.py) | Exact instrument/bar identity, bar interval, provider/exchange timestamp, received-at, quality, warnings and adjustment context; the existing historical reader filters bar end and recorded received-at at the requested cutoff | Received-at is the historical reader's recorded availability, not necessarily original exchange publication; it must not replace another source's explicit known-at. A fresh quote cannot prove a complete daily setup history |
| [Official delivery](../../app/market_data/nse_delivery.py) | Native `available_at`, trade date, report/observation identity, exact instrument, official provider/authority and daily frequency | Existing observations are retained historical inputs; retrieval today does not refresh them |
| [Prospective intraday evidence](../../app/market_data/prospective_fifteen_minute_bar.py) | Explicit minute/15-minute receipt known-at, underlying lineage and finalization boundary | Not an approved replacement for the daily Pre-Breakout source window; its runtime was not enabled |
| [Pre-Breakout materialization](../../app/strategies/pre_breakout/materialization.py) and [assessment](../../app/strategies/pre_breakout/setup_assessment.py) | Existing deterministic technical/structural evaluation, policy/selection fingerprints, instrument, evaluation cutoff, some pivot/tick references and blockers | The persisted assessment does not retain a complete per-input dependency and verified availability receipt. Calculated values and evaluation time cannot reconstruct that missing ledger |
| [Canonical setup projection](../../app/production_v1/canonical_setup_activation.py) | Existing native assessment-to-candidate/opportunity assembly | Its decision/evaluation timestamp is not independent proof that every upstream input was available |
| [P1 lifecycle source-reader contract](../../app/intelligence/p1_signal_lifecycle.py) | Owning reader must verify every reference, fingerprint, native eligibility and full dependency closure at the canonical cutoff | No production owning-store adapter proving the whole assessment/Watch closure was found. Fixture membership checking is not a production adapter |

The required production adapter must verify instrument/security identity,
observation and source timestamps, native available/known-at, provider identity,
fingerprints, freshness/warnings and complete dependencies from owning stores.
These fields cannot be manufactured from a Watch timestamp or a newly fetched
copy. The adapter itself is **NOT IMPLEMENTED/NOT VERIFIED** in this checkpoint;
only the existing interface and unchanged source-time transport are tested.

The smallest remaining source work is a lossless provenance receipt around the
existing daily input-read/materialization path, followed by an owning-store
verification adapter. It must not recalculate a parallel setup policy or treat
retained computed values as a complete input ledger. No such downstream repair
has been started under the cover of a permissive placeholder adapter.

## Actual source/runtime readiness

Bounded read-only SQLite inventory found:

- 12 `MARKET_WIDE_QUALITY_INFLECTION_WATCH` snapshots; latest stored cutoff
  `2026-09-02T07:55:42.939690+00:00`.
- 9,122 delivery observations and 4 delivery reports; latest snapshot timestamp
  `2026-09-01T14:20:31.675000+00:00` (not a fresh-source assertion).
- 729 stored Pre-Breakout assessments, 4 approvals and 4 selections. Record
  existence alone is neither current eligibility nor a complete known-at proof.
- The accepted retained Watch snapshot had no qualifying setup. It has not
  been promoted into a current real-market evaluation.
- Bounded latest-row inventory for the five approved holdings (APARINDS,
  DEEPINDS, GENUSPOWER, GLAND, ICICIBANK) found retained `1D` rows from
  `nse_udiff_official`, interval end `2026-08-31T18:30:00+00:00`, received-at
  `2026-09-05T21:05:05.485765+00:00`, quality `high`. This is raw stored metadata,
  not a new canonical series-selection or freshness decision. The existing
  governed reader's series/PIT checks remain mandatory; high quality is not
  currentness, and these old intervals cannot be relabelled prospective.

The existing local backend returned HTTP 200/status `ok` at `/health` on port
8000. The response did not establish pilot identity configuration. The isolated
8766 canary was not reachable. No restart, credential read, authentication
refresh, provider market-data request, acquisition or scheduler change occurred.
Provider credential validity/current connection readiness is **NOT_VERIFIED**,
not assumed valid or falsely classified as REAUTH_REQUIRED.

Real-market prospective evaluation: **SOURCE_BLOCKED — complete owning-source
dependency/known-at closure unavailable; retained evidence is not fresh proof**.
No current positive or negative real-market setup result is claimed.

## Runtime/dry-run boundary

New [pure admission rehearsal](../../app/intelligence/p1_prospective_dry_run.py)
reuses native lifecycle `evaluate`, `qualify` and source-closure validation,
which already reproduce the approved Registry/projector and native setup path.
It does not create a new Pre-Breakout evaluator, register a producer or call a
writer. It returns a deterministic evaluation fingerprint, explicitly
hypothetical boundary, status/reason and `DRY_RUN_NOT_ACTIVE / writes_performed=0`.

| Input | Non-writing result |
| --- | --- |
| Verified qualifying native fixture | `WOULD_ADMIT`; no persisted signal |
| Verified complete native negative assessment, no prior lifetime | `EVALUATED_NO_CURRENT_VALID_SETUP`; zero signal records, a valid evaluation |
| Unverified/stale source, incomplete closure or reader outage | Native `SOURCE_BLOCKED`, never healthy zero |
| Missing/inactive policy or contradictory retained projection | Native `POLICY_BLOCKED` or higher-priority `CONFLICTED`, never healthy zero |
| Missing start / evaluation before start / input known before start | Explicit prospective boundary blocker |

The existing reducer correctly does not create an invalidation without a prior
lifetime. The rehearsal recognizes a fully verified native negative assessment
as healthy zero without weakening that reducer or manufacturing a lifetime.
It does not turn source failure into evidence of a negative setup. No arbitrary
freshness duration or new strategy threshold is introduced.

Fixtures prove logic only. They do not prove current provider availability or
production source verification. A separate isolated test invokes the **existing**
writer after rehearsal to prove accepted admission and duplicate idempotency;
the rehearsal itself never writes. Existing tests retain supersession, rollback,
tamper and PIT reconstruction coverage.

## Prospective start and activation

Production start: **UNSET**. Recorder: **NOT_ACTIVE**. No durable start, worker,
scheduler, activation API or producer registration was created.

The supplied requirement is enforced literally in rehearsal: every supplied
source known-at must be at or after the hypothetical boundary; missing known-at
is unavailable, and evaluation must not precede the boundary. Native PIT checks
also reject future input availability. Equivalent aware times normalize to UTC.
The fixture boundary is explicitly hypothetical and never recorded as a real
production activation.

A future real marker must be explicit, durable, auditable and bound to the
verified owning source and approved path before any accepted production write.
No time selected during this audit is an activation marker. Earlier policy,
security and historical context remain earlier: re-reading or re-projecting
them does not make them newly known. Any exception allowing pre-boundary context
would require explicit approved semantics, not a silent implementation change.
Until the source and start prerequisites are satisfied the writer stays unarmed,
even though legitimately fresh nonqualifying evaluations are valid zero output.

## Minimum authenticated pilot read

New exact GET `/api/v1/pilot/p1-history` is installed only inside the existing
pilot Auth0 boundary. [Query/response](../../app/api/pilot_p1_history.py) uses
the existing exact-instrument, aware-as-of validator and the existing bounded
[read-only SQLite reader](../../app/storage/readonly_p1_signal_lifecycle.py).

- Contract `pilot-p1-unarmed-history/v1` returns genuine `NO_HISTORY`, empty
  observations/transitions, `NOT_ACTIVE`, null start, `SOURCE_BLOCKED`, and
  `SOURCE_KNOWN_AT_ADAPTER_UNAVAILABLE / PROSPECTIVE_START_UNSET` warnings.
- It proves all three existing journal/index/head stores are empty in a read
  transaction. Missing schema/store is 503, not fabricated empty history.
- **Any** P1 batch/index/head causes 503 `P1_PROSPECTIVE_ORIGIN_UNVERIFIED`.
  Until prospective origin and private/shared classification exist, even a
  structurally valid research/history batch is not published. No payload is
  decoded; no portfolio-dependent history or protected strategy internals leak.
- OWNER and invited TESTER use the same safe empty shared result; private
  portfolio routes retain existing ownership checks. JWT verification, role
  derivation, invitation enforcement and no-store behavior are unchanged.
- Anonymous/invalid token: 401. Mutation requests: 403. Duplicate/extra authority
  query fields, malformed identity, naive or future cutoff: 422 without echoing
  supplied values. The API's current clock only bounds the query, never source
  identity, source time or historical interpretation.
- Legacy `/api/v1/p1-signals/lifecycle` remains denied in the pilot, including
  OWNER. There is no fall-through to global/private history or a write endpoint.

This is a deliberately unarmed empty-history surface, **not** complete nonempty
pilot history publication. No frontend switch, public Apper connection or live
pilot deployment is claimed. Existing frontend tests are rerun because a new
read contract exists; frontend files and existing clients remain unchanged.

An actual direct read-only call against the canonical DB at
`2026-09-21T19:59:01.589831Z` returned the documented empty/unarmed/source-blocked
response for `NSE:INE372A01015`. This was a local service-read proof, not a live
Auth0 login or real-market evaluation. HTTP/identity proofs use isolated signed
JWTs and synthetic private records in tests, never live tokens in reports.

## Validation

| Check | Result |
| --- | --- |
| Focused source-time/dry-run, authenticated history, lifecycle writer/query/provisioning, delivery and prospective-bar tests | 171 passed / 0 failed / 0 skipped / 2 warnings (43.89 s) |
| Relevant P1A/B/C, lifecycle policy, Pre-Breakout governance, identity/canary and canonical-query regression | 198 passed / 0 failed / 0 skipped / 2 warnings (43.08 s) |
| Frontend existing tests | 53 passed / 0 failed / 0 skipped (2.86 s) |
| Full backend `python -m pytest -q --tb=short` | 8,907 passed / 0 failed / 6 skipped / 2 warnings (582.04 s) |
| Canonical and identity DB full integrity | Both `ok`; both FK violation counts 0 |
| Markdown/whitespace | 11 local links valid; seven intended files whitespace-clean; `git diff --check` passed |

Two initial **new fixture** failures were corrected: missing policy with a
retained positive P1 projection correctly has native conflict priority, and
the canonical SQLite JSON index correctly rejects malformed-JSON inserts.
The tests now respect those existing rules. No Core validation was weakened.
Frontend's first sandbox launch failed before tests loaded with Node
`uv_os_get_passwd ENOMEM`; the same command passed all 53 tests on the approved
host run. Existing backend warnings are Starlette/httpx and anyio deprecations.
Focused/relevant/full counts overlap and must not be summed.

Tests use process-only disabled provider/scheduler/operator flags. No saved
configuration or production state is changed by testing. The full suite above
completed successfully, rather than being inferred from progress. Its six skips
are the opt-in GDFL, GNews, Kotak and Upstox live tests plus two unconfigured
PostgreSQL integration tests; they are not provider-readiness proof.

Read-only canonical audit completed: 265,923 core snapshots; P1 batches 0,
P1 batch-index rows 0, P1 head rows 0; portfolio snapshots 1. Separate exact
table counts are paper trades 0 and trade plans 0. Canonical DB size and mtime
were unchanged across the full integrity audit. Both DB connections used
SQLite `mode=ro` and `query_only=ON`; no migration was rerun. The predecessor's
verified backup was retained untouched and no new backup was created.

## Defensive review and remaining closure

Only the rehearsal, restricted pilot read, bounded empty-store reader method,
exact pilot GET allowlist/router registration, focused tests and this report
are changed. Native P1A/B/C/lifecycle, writer, strategy policy, Brain, governance,
portfolio, provider and historical artifacts remain unchanged. No new DB schema,
backfill, positive setup fabrication, order/broker path, alerts or AI workflow.

Remaining: production owning-source dependency/availability adapter, legitimate
current source evaluation, durable start/armed runtime binding, then classified
nonempty shared/private history publication. Zero qualifying setups alone is
**not** a blocker; unverifiable freshness/closure is. No credential action is
requested until a real provider authentication failure is safely established.

Next exact slice: **P1_PROSPECTIVE_HISTORY_PREFLIGHT_AND_BINDING** — remaining
owning-source provenance and prospective runtime closure. It is not started
as another slice here; no later deployment-closure node is advanced.
