# Strategy Governance and Audit

## Scope

This phase defines and stores strategy governance records. It does not calculate diagnostics, scores, execution gates, signals, position sizes, or trades.

## Immutable strategy versions

A `StrategyDefinition` is identified by `strategy_id` and `version`. Once stored, it cannot be overwritten. A changed configuration requires a new version with a `parent_strategy_version` reference; for example, `0.1 → 0.2`. Historical diagnostics, scorecards, and gate decisions retain their original version reference.

The structured configuration captures scoring weights, rotation threshold, minimum risk/reward, gate parameters, portfolio/sector/position limits, capital velocity, earnings blackout, and risk parameters. Undecided values are explicitly `UNSPECIFIED` or `REQUIRES_APPROVAL`; no trading-relevant default is inferred.

## Lifecycle and approval

The permitted lifecycle names are `DRAFT`, `EXPERIMENT`, `VALIDATION`, `APPROVED`, `ACTIVE`, `RETIRED`, and `REJECTED`. The definition retains its creation state, while append-only lifecycle events record validation and approval progression.

The required promotion sequence is:

`draft/experiment → validation passed → approved → active`

The governance service rejects activation unless the latest lifecycle state has both `APPROVED` approval status and `PASSED` validation status. Lifecycle events and audit events are insert-only; attempting to reuse an ID fails rather than overwriting history.

## Evidence hierarchy

Evidence explicitly has one type: `FACT`, `DATA`, `INTERPRETATION`, or `INFERENCE`. Each evidence record carries its own source, source identifier, timestamp, observation IDs, factual-content reference, confidence, and provenance. This makes the four information layers distinguishable rather than interchangeable.

## Analytical record structures

`DiagnosticResult`, `Scorecard`, and `GateDecision` are record structures only in this phase. Each requires an existing strategy version and an as-of timestamp before persistence. No diagnostic rule, score aggregation, or gate logic is implemented.

## Deterministic audit reconstruction

`AuditReconstructionService` retrieves a strategy version, as-of snapshot, evidence, diagnostics, optional scorecard, and gate decisions. It sorts each record set by ID and creates a SHA-256 fingerprint from their immutable identifiers. The same records therefore produce the same decision ID and fingerprint. Missing referenced evidence, missing strategy versions, missing snapshots, or a scorecard from another strategy/time cause reconstruction to fail.

## Experiment-to-approval workflow

An experiment can be represented by an immutable strategy version and lifecycle events. It must complete validation before it can be approved, and must be approved before it can become active. Future phases will attach backtest, walk-forward, out-of-sample, and paper-trading validation artifacts to this workflow; this phase deliberately does not claim those calculations exist.
# Decision Scorecard audit chain

Decision Scorecards are immutable governance artifacts linked to an existing strategy version, canonical registry version, scoring-configuration version, as-of time, persisted diagnostics, components, confidence, contradictions, and warnings. Configuration changes create a new scorecard; earlier cards are never rewritten.
