# Historical analytical replay

Phase 8A.3 is a point-in-time analytical adapter:

`ReplayClock timestamp → validated and guard-eligible snapshot → canonical diagnostics → Decision Scorecard → six-gate evaluation → immutable artifacts/events`.

The snapshot builder reads only domain records already valid and available as-of the replay timestamp, then applies `BacktestLookaheadGuard` again. It retains eligible historical bar history for existing engines and separately records latest eligible input IDs for audit. Later stored observations never rewrite a persisted replay artifact.

Each historically eligible universe member is processed in stable instrument-ID order. The adapter checks the frozen strategy, registry, scoring, and gate versions on `BacktestRun`. It invokes existing evaluator methods where historical inputs exist and records other canonical rules explicitly as insufficient. Missing rules reach the existing scorecard unchanged: no renormalization occurs, and data confidence stays separate from score.

Portfolio replay is deliberately absent. Rotation comparison and heat inputs are not invented, so the existing gates return insufficient where they require unavailable context. No signal, rotation action, trade, fill, performance report, or benchmark result is created.

When a separately frozen portfolio state is available, the portfolio-context adapter may re-evaluate only Gates 1 and 5 through the existing gate engine. The analytical-only gate artifact and raw Decision Scorecard are never overwritten; this remains a gate evaluation, not a rotation decision.

The later historical rotation adapter consumes these immutable analytical references; it does not use newer scorecards or diagnostic outputs.

Historical snapshot/evaluation records are immutable. Audit reconstruction checks the run, snapshot provenance, selected input IDs, diagnostic references, scorecard, gates, and data confidence without mutating history.

## Anti-look-ahead regression matrix

Integration fixtures pass future stock/index/sector bars, financial publications and restatements, research and crowd payloads, authoritative surveillance payloads, earnings reschedules, and universe memberships through `HistoricalSnapshotBuilder` and the replay adapter. At the original timestamp they are absent from selected input IDs, 61-rule artifacts, score/data-confidence values, and gate outputs. A later timestamp may use newly published data; earlier immutable evaluations are not rebuilt or overwritten. Gate 3 remains insufficient without an earlier authoritative surveillance record, Gate 1 has no fabricated comparison holding, and Gate 5 has no fabricated portfolio exposure.
