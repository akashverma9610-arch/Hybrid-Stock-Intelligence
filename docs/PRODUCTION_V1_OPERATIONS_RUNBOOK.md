# Production V1 operations runbook

1. Configure only approved source credentials and official-file staging paths.
2. Initialize storage, backfill required history, reconcile, and inspect
   `python -m app.runtime production-v1-status`.
3. Do not enable data or paper workers until P0 count is zero.
4. Run one explicit `production-v1-cycle`; it refreshes/reconciles before
   Shared Brain, setup, or paper callbacks.
5. Verify Deep Analysis remains read-only and paper activity has no broker
   traffic.

## Sector-index coverage limitation

`sector-universe-coverage-policy / v1-approved` is the selected, active
Production-V1 readiness policy for the current sector-ranking consumer. It is
approved by `human:Akash-Verma` and permits operation on an evidence-derived
subset only when the NIFTY 500 benchmark is ready and the existing Top-3
algorithm has at least three sectors with exact canonical index identity,
20/60/120 aligned RS evidence, and `READY` breadth. This is an algorithmic
necessity, not an 8-sector or percentage threshold.

The `INDEX_BARS` source family remains factual `PARTIAL` when exact sector
histories are absent. Production readiness may show `DEGRADED` rather than a
P0 block only under that selected policy; its reason lists the canonical count,
eligible Top-3 subset, and every excluded sector/index/reason. Excluded
sectors receive no proxy, synthetic index, zero RS, rank, Top-3 membership, or
top-down Pre-Breakout candidate path. A later exact, fresh canonical history
automatically recovers that sector; degraded or insufficient evidence removes
it again. This is current/forward evidence as of the stored cutoff, not a
claim of complete NIFTY 500 top-down evaluation.

Recovery: disable the relevant opt-in worker; retain immutable evidence;
inspect the family/run error; correct source/configuration; rerun
chronologically; reconcile; verify idempotency and reopen durability before
resuming. Malformed files remain quarantined by existing staging; corporate
action uncertainty blocks open paper studies rather than rewriting R.

There is no destructive reset recovery path, automatic policy update, or
live-order command in Production V1.
