# Defensive Engines

## Reliability & Fallback

`app.reliability.DataReliabilityService` consumes declared
`DataSourceReadiness`-compatible health facts. It selects only an available
primary, approved fallback, or explicitly marked last-known-good source. Its
outputs are `ReliabilityDecision` and `DataAvailability`; no provider fetch or
market payload is produced. Conflicting available fingerprints fail closed as
`CONFLICTED`; no usable source produces `PRIMARY_UNAVAILABLE` or `UNAVAILABLE`.

## Historical Integrity

`app.historical_integrity.HistoricalIntegrityService` delegates point-in-time
checks to `BacktestLookaheadGuard`. Publication/effective/retrieval timestamps,
restatements, membership windows, delistings, and corporate events are handled
as historical facts. `UniverseMembershipAsOf` never substitutes today’s
universe. Outputs are `VALID`, `PARTIAL`, `INVALID`, or `UNAVAILABLE`.

## Governance & Drift

`app.governance` stores immutable observation and assessment snapshots. It
compares already-produced performance facts and can recommend HEALTHY, WATCH,
DEGRADED, or DISABLE_RECOMMENDED. It has no dependency that writes promotion,
approval, activation, rollback, score, gate, or rotation records.

## Audit & Reproducibility

`app.audit` records frozen decision references and append-only outcome links.
`reconstruct_decision(audit_id)` reads those exact references; it does not rerun
today’s data or expose proprietary internals. Existing `AuditReconstructionService`
continues to reconstruct canonical persisted artifacts.

## Live-readiness candidate safeguards

The candidate layer adds deterministic reconciliation, evidence coverage,
friction/feasibility simulation, calibration/redundancy/ablation measurement,
rotation-hurdle measurement, factor exposure, emergency restrictions, news
event clustering, and schema-bound AI containment. They are internal,
append-only where persisted, and do not alter 61 diagnostics, scores,
confidence, gate policies, rotation thresholds, provider selection, or trading.
