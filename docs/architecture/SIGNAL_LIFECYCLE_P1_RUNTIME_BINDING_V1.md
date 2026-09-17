# P1 Signal Lifecycle runtime binding V1

Baseline: `3a932eb6cb31be18f637bcf83701addc10e38251`, `main`.

Status: IMPLEMENTED_ISOLATED / VALIDATED / NOT_PRODUCTION_WIRED.
This is implementation of the approved [P1 compatibility policy](SIGNAL_LIFECYCLE_P1_COMPATIBILITY_POLICY_V1.md),
not strategy activation. V1 ACTIVE; Execution Gate V2 NOT_ACTIVE.
ONE Brain; WATCH_ONLY / NON_EXECUTABLE. No expiry policy is invented.

## Implemented boundary

- [Reducer](../../app/intelligence/p1_signal_lifecycle.py): immutable evaluation,
  native P1 projection verification, setup/provenance linkage, exact geometry
  keys, CURRENT/INVALIDATED/SUPERSEDED transitions and historical replay.
- [SQLite binding](../../app/storage/sqlite_p1_signal_lifecycle.py): explicitly
  constructed repository reusing SQLiteCoreApiSnapshotRepository and its
  snapshot encoding/database. No default application factory or provider wiring.
- [Additive migration](../../migrations/versions/20260917_11_p1_signal_lifecycle.py):
  two disposable concurrency indexes; immutable batches are stored under the
  new P1_SIGNAL_LIFECYCLE_BATCH family. No legacy SIGNAL payload/table reuse.
  Migration exists as source only; it has not been applied to production.
- [Fixtures](../../tests/unit/test_p1_signal_lifecycle_runtime.py): synthetic
  official-source/governance records and temporary SQLite databases only.

The existing P1A/P1B/P1C, MarketWideWatch, setup assessment, candidate assembly,
opportunity, security master and governance validation code remain unchanged.
Positive admission reproduces P1 through its existing projector and compares
the exact serialized result. Native source fingerprints are checked, not healed.
Negative assessments resolve canonical selected-policy authority without
fabricating a CURRENT_VALID_SETUP Watch or a new candidate/opportunity.

## Strict source trust boundary and live limitation

`CanonicalSourceReader` is a required, injected owning-store reader. It must
verify the exact source ID/fingerprint, canonical identity, native eligibility,
source freshness/price basis, and retained known-at ledger at the explicit
evaluation cutoff. It must enumerate the full source dependency closure.
Neither a user-supplied timestamp nor a snapshot's creation time is an
acceptable replacement for source known-at. Missing timing or dependency
provenance blocks admission. Dependency cycles/conflicting references reject.

There is deliberately no permissive production adapter. Existing Watch and
assessment records alone do not prove every upstream source's known-at.
Test Ledger is a synthetic test double, not production authority. Consequently
this checkpoint proves isolated lifecycle mechanics and durable replay, not
live production emissions or complete production data availability. A verified
owning-store adapter and production migration rollout require a separate bounded
deployment step. No new source truth, ledger store or evidence acquisition is
created here.

## Persistence and replay

`submit` takes BEGIN IMMEDIATE before reading the current head. Independent
writers serialize, verify the immutable chain/indexes and recompute on the
latest committed head. Identical input retries return NO_CHANGE without writes.
Different input at equal cutoff conflicts; older input is rejected. Atomic
supersession contains closure and replacement admission in one snapshot/transaction.
No exception is treated as a successful duplicate. Transaction failure rolls
back snapshot, unique batch index and head update together.

Loading verifies stored envelope metadata, predecessor links, content hashes,
native source linkage, P1 reproduction and regenerated transitions. Queries use
only batches at/before the explicit cutoff; newer payloads are not decoded as
historical authority. Index rebuild is explicit and derives from verified
immutable batches; it cannot repair corrupt history. Terminal lifetime IDs never
reactivate. Later qualification links a new lifetime to the terminal predecessor.

Known canonical timestamps normalize to UTC for new lifecycle hashes. Decimal
encoding uses fixed-point text without float conversion or Decimal-context
rounding. Existing native source fingerprints are preserved even where their
legacy encoding differs; no silent source rehashing/normalization is performed.

## Current-state meaning

CURRENT means last confirmed qualification, not a present-day executable setup.
At an unconfirmed later query cutoff, CURRENT is SOURCE_BLOCKED /
REEVALUATION_REQUIRED. There is no synthetic TTL or EXPIRED transition.
Invalidation only maps the eight approved native failure predicates or verified
security cessation. Missing data, policy outage, sector/entry-economics failures,
Watch absence and raw news/gap changes do not become terminal facts.

## Safety and validation

No provider call, live acquisition, portfolio access/mutation, broker/order,
Decision Score computation, Six Gates authorization, API/UI route, scheduler,
Alerts delivery or automatic startup has been added. Original research and
execution-policy activation states are unchanged.

Focused and relevant validation: 619 passed, 2 dependency-deprecation warnings
(59 lifecycle cases and 560 existing P1/governance/setup/storage/downstream
cases). Final full backend validation: 8,727 passed, 0 failed, 6 skipped,
2 existing TestClient/httpx/anyio deprecation warnings (460.22 seconds).
Local Markdown links and whitespace checks passed. No production database
migration or lifecycle emission was executed as part of this validation.

Review corrections: governance test fixtures use retained records rather than
command receipts; the new snapshot family is appended to preserve enum order;
negative policy lookup creates no fake positive routing context; historical
queries exclude newer payloads; native PARTIAL_POLICY_BLOCKED status is not
misread as missing data when the resolved policy and evidence are complete.
Source timing/availability failures are retained while supplied native facts
and policy are inspected, so conflicts outrank policy blockers, which outrank
source blockers. The source-pin regression test permits exactly the one new
enum line and continues comparing every other byte to the historical baseline;
no historical governance receipt or fingerprint was changed.

Apper SenseEdge integration is a later consumer boundary. This lifecycle is not
exposed through legacy `/signals` and the prototype must not claim live P1
history until a separately verified read contract/source binding exists.
