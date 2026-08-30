# Future OOS execution

A research-selected candidate follows this immutable chain:

`CandidateSelectionResult → FutureOOSCandidateQueueEntry → FutureOOSAssignment → WalkForwardWindowResult → FutureOOSExecutionResult`.

An assignment freezes the exact candidate fingerprint, selection ID, policy/version, TEST partition, and TEST timestamps. It is accepted only while the queue is `QUEUED`, selection and assignment are strictly before TEST start, the TEST begins no earlier than the queue boundary, and policy lead-time, plan, expiration, and concurrency rules hold.

`FutureOOSExecutionService` delegates to the existing `WalkForwardExecutionService`; it does not reselect the candidate, execute TRAIN/VALIDATION state, or create a second OOS engine. TEST starts with the existing independent-window capital methodology. Zero-trade, insufficient, failed, and benchmark-unavailable outcomes are retained as terminal evidence.

All records are insert-only and audit reconstruction verifies the frozen queue, candidate, policy, selection timestamp, TEST window, backtest run, and canonical window result. No lookup may replace any reference with a later candidate, policy, price, or window.

Positive OOS evidence is not a promotion, human approval, activation, broker action, or real-account action.

Lifecycle is append-only: the queue and assignment remain their original frozen records, while `FutureOOSExecutionResult` records the terminal TEST outcome. Queued `STALE`, `EXPIRED`, or `CANCELLED` records are not executable; cancellation lifecycle records are not yet introduced. A completed historical result is never rebased onto a later strategy or policy.

## Runtime capability boundary

`FutureOOSAssignmentService` and `FutureOOSExecutionService` are direct,
reusable services and are intentionally not feature-guarded. A future automatic
runtime must explicitly inspect the disabled-by-default experimental
`AUTOMATED_SELF_IMPROVEMENT_RESEARCH` capability before invoking this flow.
Manual and test invocation remains available while automatic production
orchestration is absent.
