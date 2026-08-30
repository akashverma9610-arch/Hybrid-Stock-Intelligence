# Execution Gate Engine

`ExecutionGateEngine` is a pure analytical eligibility evaluator. It consumes an approved `GateInput` snapshot, a versioned `ExecutionGateConfig`, and an `ExchangeCalendar`, producing an immutable `ExecutionGateEvaluation` with exactly six `GateDecisionRecord`s.

Outcomes are `PASS`, `FAIL`, or `INSUFFICIENT_DATA`. Any fail is `BLOCKED`; otherwise any insufficient result is `INSUFFICIENT_DATA`; all passes are `EXECUTABLE`. `EXECUTABLE` is only permission for a future layer. It creates no order, allocation, broker instruction, or capital deployment.

The input snapshot timestamp must equal the requested as-of timestamp. A direct future-stamped input is rejected. Evaluations retain scorecard, strategy, registry, scoring and gate-config versions, action context, evidence/diagnostic references, raw score, separate velocity adjustment, and configuration parameters.

Gate dependencies are explicit: rotation needs score/comparison/friction data; velocity needs holding history and ATR expansion; surveillance needs fresh authoritative data; trade-plan needs stop/T1 policy data; heat needs risk and allocation data; blackout needs a verified schedule and calendar.
