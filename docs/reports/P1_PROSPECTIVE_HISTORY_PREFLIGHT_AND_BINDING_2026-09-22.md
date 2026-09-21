# P1 prospective history preflight and binding

Baseline: `f3c17fd136ab281a46bc23aad84c932f004bb6bb`, `main`, clean.
Slice: `P1_PROSPECTIVE_HISTORY_PREFLIGHT_AND_BINDING`.
Decision: **PARTIAL**. Safe persistence provisioning is distinct from a verified
prospective recorder. **No prospective recorder is activated by this slice.**
V1 ACTIVE; Execution Gate V2 NOT_ACTIVE. No push or public deployment.

## Root cause, established before edits

The [read-only reader](../../app/storage/readonly_p1_signal_lifecycle.py) emits
`P1_LIFECYCLE_SCHEMA_UNAVAILABLE` because the canonical SQLite database contains
`core_api_snapshots` but neither `p1_signal_lifecycle_batch_index` nor
`p1_signal_lifecycle_heads`. This is missing schema rollout, not a missing P1
domain contract or a JWT/identity failure.

The [existing migration](../../migrations/versions/20260917_11_p1_signal_lifecycle.py)
and [writer](../../app/storage/sqlite_p1_signal_lifecycle.py) already exist.
The database has no Alembic version table: it is constructor-managed SQLite.
Running the entire Alembic migration chain or stamping unexecuted predecessors
would not be an appropriate targeted repair.

There is a separate, genuine **source/runtime binding gap**. The existing
[runtime specification](../architecture/SIGNAL_LIFECYCLE_P1_RUNTIME_BINDING_V1.md)
explicitly requires an owning-store `CanonicalSourceReader` verifying native
eligibility, retained known-at and the full dependency closure. No production
implementation/caller of that protocol is installed. The test `Ledger` is not
authority and must not be wired into production.

Read-only canonical inventory at this checkpoint:

| Evidence | Observed state | Interpretation |
| --- | --- | --- |
| Watch runs | 12; latest `2026-09-02T07:55:42.939690+00:00` | Retained, not live |
| Latest verified Watch records | 500: 434 NOT_EVALUATED; 66 NO_CURRENT_SETUP | Zero CURRENT_VALID_SETUP |
| Canonical setup-opportunity snapshot family | 0 | Positive lifecycle bundle unavailable |
| Setup assessments | 729 | Presence does not establish present qualification or full source timing |
| Pre-Breakout approvals / selections | 4 / 4 | Records alone do not establish P1 availability |
| Decision audit / outcome-link snapshots | 43 / 43 | Existing distinct decision history, not P1 history |
| P1 lifecycle batch snapshots | 0 | No independently proven prior recorder |
| Portfolio snapshots / paper trades / trade plans | 1 / 0 / 0 | Not migrated into P1 |
| Canonical diagnostic results | 2,074 | Retained diagnostics, not signal timestamps |

No current positive bundle can be assembled from this inventory without either
new legitimate canonical evaluations or inventing timing/qualification. Neither
old Watch re-dating nor source acquisition is performed here. This is a data and
binding limitation, not permission to weaken the approved policy.

## Contract reuse and field inventory

The [approved compatibility policy](../architecture/SIGNAL_LIFECYCLE_P1_COMPATIBILITY_POLICY_V1.md)
remains authoritative; no predecessor semantics or fingerprint is changed.

| Requirement | Existing owner / treatment |
| --- | --- |
| Observation ID, fingerprint, instrument, Watch ID/as-of | [P1A](../../app/intelligence/hsi_signal.py); deterministic immutable identity, UTC normalization, distinct content fingerprint |
| Strategy selection/approval and policy version | [P1B registry](../../app/intelligence/hsi_signal_strategy_registry.py); exact CURRENT_VALID_SETUP + PRE_BREAKOUT_POLICY routing, PIT approval/selection, verified canonical governance |
| Watch-to-observation conversion | [P1C](../../app/intelligence/hsi_signal_projection.py); reproduced native serialization, no new detector |
| Lifetime ID, slot, transition/batch IDs, supersession | [Lifecycle reducer](../../app/intelligence/p1_signal_lifecycle.py); existing CURRENT/INVALIDATED/SUPERSEDED states and immutable linked batches |
| Evidence timing | SourceReference evidence_as_of / evidence_known_at / effective_at; owning-store verification required; no runtime-time substitution |
| Detection / observation time | Watch as-of retained; distinct detection time unavailable in P1C. No new claimed generated-at or observed-at is fabricated |
| Strategy/runtime identity | Existing P1, registry, lifecycle contract IDs and policy/approval/selection fingerprints retained. New deployment/Brain version attribution is unavailable absent a verified source link; this commit is not injected as historical engine identity |
| Brain decision/version audit | [DecisionAuditRecord](../../app/audit/decision.py) already owns engine, diagnostic, confidence, gate and scoring identities. It can include private portfolio context; do not copy it into shared P1 or create fake audit links |
| Multiple archetypes | Original Watch retains archetypes and routes. P1 projects per archetype; this lifetime policy admits only PRE_BREAKOUT. No destructive single-label rewrite or invented lifecycle for other strategies |
| Freshness / blockers | Canonical source eligibility and reason codes; unconfirmed CURRENT at later cutoff becomes REEVALUATION_REQUIRED, not fresh/live |
| Horizon / direction / confidence / strength / materiality | Remain unavailable under existing P1 projection; no score or numerical default |
| Entry / stop / targets / allocation | No new P1 fields. Native candidate structural geometry retained for verified identity linkage only; no T1/T2/extended-target or executable plan synthesis |
| Invalidation | Only existing eight native predicate mappings / verified security cessation; missing data is not invalidation |
| Expiry | EXPIRY_NOT_GOVERNED_FOR_THIS_PATH; no synthetic TTL |
| Portfolio/user context | No portfolio lookup/import/binding added. P1 relevance remains NOT_EVALUATED |
| Outcomes | Existing [paper contracts](../../app/paper/models.py) and DecisionOutcomeLink are separate. No P1-to-paper adapter or MFE/MAE/benchmark result is manufactured |

Legacy [signal models](../../app/signals/models.py) contain executable-plan,
confidence, expiry and portfolio vocabulary incompatible with P1. They remain
unchanged and are not used to fill unavailable P1 fields.

## Schema rollout and recovery

New explicit operator helper:
[sqlite_p1_lifecycle_migration.py](../../app/storage/sqlite_p1_lifecycle_migration.py).
It reuses the exact existing two-table `SCHEMA`, validates columns, uniqueness
and foreign keys, and never invokes a projector or saves a snapshot. Partial
or inconsistent schemas are rejected, not repaired silently. Matching schema
is a read-only `ALREADY_PROVISIONED` no-op. Existing P1 payloads without indexes
require separate review rather than retrospective reconstruction during rollout.

Backup mechanism follows the approved SQLite backup pattern already used by
[UDiFF migration](../../app/market_data/sqlite_udiff_series_migration.py): exclusive
backup-file creation, SQLite backup API, full backup integrity/FK verification,
and explicit transactional DDL. No unverified filesystem copy of a live database.
A writer lock prevents concurrent modification during backup/provisioning;
the backup source uses a separate read connection to avoid a backup-API deadlock.
Canonical integrity is checked before and after rollout. Only the two existing
index tables are added; no historical rows, portfolio records, auth sidecar,
Alembic ledger, scheduler or application configuration are changed.

DDL failures roll back and retain the backup for operator inspection. Do not
blindly restore an old whole-database backup after unrelated new writes. For
recovery, stop/identify the affected owned writers, inspect the backup and newer
evidence first. The existing downgrade removes only disposable P1 indexes; after
future history exists, preserve immutable batches and use the existing verified
index-rebuild mechanism, not re-admission/backfill. No automatic downgrade,
restore, deletion or cleanup is performed by this helper.

Operator rollout began at `2026-09-21T19:18:29.927047+00:00` (22 September IST).
The protected local backup is
`data/backups/nse_stock_manager.pre-p1-lifecycle.20260921T191829Z.db`,
18,529,284,096 bytes. It is Git-excluded and is not part of the source commit.
The pre-rollout canonical integrity/FK checks and full backup integrity/FK
verification completed before DDL. Post-rollout full integrity completion is
recorded in the final receipt below, not inferred from the successful read.

The actual existing query service, pointed read-only at canonical SQLite at
`2026-09-21T19:37:47.650129+00:00`, returned `NO_HISTORY / SOURCE_BLOCKED /
REEVALUATION_REQUIRED`, null last transition, empty transition/observation
references, WATCH_ONLY / NON_EXECUTABLE and ungoverned expiry. This was a direct
operator service probe, **not** a live authorized pilot HTTP session, a fixture
emission, or producer activation. The pilot middleware remains unchanged.

Both new tables contain zero rows; P1 batch snapshots remain zero. Existing
core snapshots remain 265,923; financial facts 6,118; corporate filings 455;
canonical diagnostics 2,074; portfolio snapshots 1; paper trades 0; trade plans 0.
The read probe did not change the DB mtime; FK violations were zero. The identity
sidecar independently returned integrity `ok`, FK zero, one user, one ownership
binding and two audit events, unchanged from the accepted identity checkpoint.

## Prospective boundary and runtime limitation

**Prospective start: NOT_ACTIVE / UNSET.** Schema readiness is not the start of
signal recording. Operation timestamps in the rollout receipt are infrastructure
timestamps only, not canonical evidence timing or P1 observation identity.

Records before a future verified recorder boundary are **not prospective P1
signal history** unless independently proven by an already-existing valid
recorder. No such production recorder is proven here. Historical fixture/replay
tests remain explicitly synthetic; they do not establish a September 2 start.

Before activation, a bounded source adapter must resolve exact retained source
IDs/fingerprints, native price/freshness/identity checks and every dependency's
known-at. It must consume legitimate canonical Watch/assessment/candidate/
opportunity evaluations at the same cutoff through the existing registry and
projector, not accept caller timing assertions. Capture an actual auditable
recorder-start boundary and prevent pre-boundary admission separately from
research replay. Keep the authorized prospective collection scope at the
existing five holdings; do not start a broader collector. No worker is enabled
here and no zero-result polling is presented as runtime emission proof.

## Append-only, isolation and outcome boundaries

Existing writer tests prove BEGIN IMMEDIATE serialization, unique input/cutoff,
idempotent retries, atomic replacement, rollback, original source retention,
terminal non-resurrection and PIT replay. Native P1 is reproduced and hashes
are verified. This is application-level append-only behavior and tamper
detection, not a claim that a privileged SQLite administrator cannot modify
the file. No accepted transition is written during this slice.

Shared source records must come from canonical shared Watch records, not
`portfolio_records` or private decision-audit payloads. A future source adapter
must verify that distinction; copying the complete Watch run into a public
response is not authorized. Existing pilot middleware continues denying the
P1 lifecycle route, including for OWNER, pending a separately proven safe read
contract. No new API or private resource is exposed by schema provisioning.
Existing identity/IDOR regressions remain required and unchanged.

WATCH_ONLY / NON_EXECUTABLE remains unconditional. No Six-Gates authorization,
broker/order operation, portfolio mutation, alert, AI workflow or outcome-based
weight adjustment is added. Profit/return statistics remain unavailable without
their existing governed source and linkage contracts.

## Validation and remaining closure

Completed test commands use the existing host Python runtime with process-only
`DHAN_LIVE_MARKET_ENABLED=false`, `RUNTIME_SCHEDULER_ENABLED=false` and
`HSI_LOCAL_OPERATOR_RUNTIME=false`. No saved runtime configuration was changed.

| Check | Exact result |
| --- | --- |
| Focused provisioning, lifecycle runtime/query and historical/governance audit integration | 121 passed / 0 failed / 0 skipped / 2 warnings (63.84 s) |
| Relevant P1A/P1B/P1C, lifecycle policy, Pre-Breakout governance, identity and existing migration regression | 196 passed / 0 failed / 0 skipped / 2 warnings (27.96 s) |
| Separate identity/canary isolation regression | 77 passed / 0 failed / 0 skipped / 2 warnings (16.42 s) |
| Full backend `python -m pytest -q --tb=short` | 8,862 passed / 0 failed / 6 skipped / 2 warnings (593.38 s) |
| Frontend | Not rerun: no frontend/API contract change |
| Markdown links | 14 local links valid |

Counts overlap across focused/relevant/full runs; do not sum them. Skips are
four opt-in provider live tests (GDFL, GNews, Kotak, Upstox) and two unconfigured
PostgreSQL integration tests. Warnings are existing Starlette/httpx and anyio
BlockingPortal deprecations, not ignored test failures.

| Required proof | Evidence and limit |
| --- | --- |
| Explicit migration, preservation, repeat no-op | New provisioning tests; verified backup, exact additive schema, no snapshot inserted |
| Rollback / no overwrite | Injected DDL failure retains backup and rolls back schema; existing backup never replaced |
| Append-only / supersession / idempotency | Existing real SQLite writer tests; independent writers, linked replacement, rollback and tamper detection |
| PIT / source fingerprints / registry | Existing source-closure, future exclusion, native P1 reproduction and policy lineage tests |
| Multi-strategy | Existing P1 projection/router semantics retained; additional lifetime strategies NOT supported or activated |
| Inactive strategy / stale evidence | Existing registry and lifecycle fail-closed tests; no permissive adapter added |
| Private/shared isolation | 77 identity/canary regressions; pilot P1 route remains denied, no private payload exposed |
| No backfill / prospective start | Provisioning writes no batch and returns prospective_start=null; existing orphan history rejected. Live anti-backfill recorder binding still absent |
| Brain identity / outcomes | No invented engine version or outcome; existing decision-audit contracts inspected but not joined into P1 |

Canonical operation completed at `2026-09-21T19:41:20.403576+00:00`, returning
`p1-lifecycle-sqlite-provision/v1 / PROVISIONED_NOT_ACTIVE / prospective_start=null`.
Canonical pre/post full integrity and backup full integrity returned exactly
`ok`; all FK checks returned zero violations. The canonical DB grew by 24,576
bytes to 18,529,308,672 bytes, solely for the two empty index tables. A subsequent
provision call returned ALREADY_PROVISIONED and preserved canonical/backup size
and mtime. These checks prove schema readiness, not signal recording.

Defensive review: only the new operator helper, its focused tests and this
report are release changes. No predecessor source/model/migration was edited.
No API, UI, identity, scheduler, provider, strategy, Brain or portfolio behavior
is wired or changed. The backup stays ignored. Markdown links and whitespace
checks pass; `git diff --check` passes. Only these three intended files are to
be committed locally; no push is authorized.

Remaining: verified owning-store dependency/known-at adapter; legitimate current
qualifying canonical source bundle; anti-backfill recorder/start binding; safe
pilot lifecycle read exposure; later governed outcome linkage. These are not
closed by the schema rollout. No market/provider call or broad refresh is made.

Next exact slice: **P1_PROSPECTIVE_HISTORY_PREFLIGHT_AND_BINDING** (remaining
canonical-source/runtime-binding closure, not a new roadmap slice). Do not
advance to portfolio ingestion while claiming this P1 node is CLOSED.
