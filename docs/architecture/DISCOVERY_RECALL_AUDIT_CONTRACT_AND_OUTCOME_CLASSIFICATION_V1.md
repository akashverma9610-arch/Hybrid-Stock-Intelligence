# Discovery Recall Audit Contract and Outcome Classification V1

**Status:** `ACTIVE / CONTRACT_ONLY / ATTRIBUTION_NOT_MEASUREMENT / NON_EXECUTABLE`.

```
DISCOVERY_RECALL_AUDIT_CONTRACT = ACTIVE
DISCOVERY_RECALL_MEASUREMENT = NOT_ACTIVE
DISCOVERY_RECALL_PERFORMANCE_CLAIM = NONE
```

This is the audit boundary for [Whole-Market Multi-Funnel Orchestration
V1](MULTI_FUNNEL_WHOLE_MARKET_ORCHESTRATION_V1.md). It does not change
discovery, approve a reference opportunity, calculate recall, invoke the
Shared Brain, create an action, mutate a portfolio, or place an order.

## Causal boundary

Discovery quality, decision quality, and action quality are separate questions.
Later market/business outcomes are usable for attribution only after a separately
governed, pre-registered reference-outcome definition exists. They can never
rewrite or inform the original historical discovery decision.

```text
eligible security
  -> discovery funnel evidence
  -> discovered / not discovered / unauditable
  -> Shared HSI Brain decision reference
  -> action-layer reference
  -> future reference-outcome receipt
  -> derived attribution
```

The contract preserves `FACT -> DATA -> INTERPRETATION -> INFERENCE`:

- immutable batch, lead, candidate, decision, action, and outcome artifacts are
  facts/data references;
- orthogonal lifecycle states describe recorded facts;
- a future pre-registered outcome receipt is a governed interpretation; and
- the derived classification is an inference, not a performance claim.

Accordingly, a later rally is not automatically a `DISCOVERY_FAILURE`; no
current union item is not a failure; a blocked funnel is not an operational
miss; `DISCOVERED_BUT_REJECTED` is not a wrong decision; an immature outcome is
not a failure; `DECISION_FAILURE` is not discovery failure; and `ACTION_FAILURE`
is not decision failure.

## Immutable audit contract

`app.intelligence.discovery_recall_audit` is pure, immutable, and deterministic.
It accepts artifact references only and imports no repository, SQLite, API, UI,
portfolio, paper-trading, broker, order, runtime clock, score, ranking, price,
return, benchmark, or persistence capability.

Each `DiscoveryRecallAuditRecord` binds:

- a `DiscoveryBatchReference`: batch ID/fingerprint, UTC discovery as-of,
  universe snapshot ID/fingerprint, and discovery registry ID/version/fingerprint;
- canonical instrument identity and `UniverseMembershipState`; `ELIGIBLE`
  requires an immutable membership proof available at/before the cutoff;
- one funnel and intended horizon with canonical execution, coverage, capability,
  and per-security evaluation state;
- emitted lead references and a candidate-pool-item reference only for a trigger;
- optional immutable Brain/action artifact references; and
- an optional future `ReferenceOpportunityOutcome` receipt.

Identity is deterministically derived from contract version, frozen batch and
fingerprint, instrument, universe-membership provenance, funnel, horizon,
discovery as-of, lead IDs, and candidate-pool ID. A separate content fingerprint
uses canonical serialization of all factual and derived fields. UTC normalization
and ordered tuples are mandatory; duplicate lead IDs are rejected, not collapsed.
Every emitted lead and candidate-pool reference must be available at/before the
frozen discovery cutoff; a later record cannot be relabelled as timely discovery.

The original batch remains frozen. Future outcomes must have an observation and
artifact-availability time strictly after the discovery cutoff, and must match
the audit's exact instrument and horizon. This contract contains no timing
window, benchmark, price/return, alpha, threshold, materiality, or formula.

`DiscoveryRecallAuditBatch` is an immutable horizon-specific envelope over
deterministically ordered records. It retains the frozen discovery-batch
identity, reference-definition availability/reference, auditable and
unauditable record counts, classification counts, missing-dependency counts, a
deterministic batch ID, and a separate content fingerprint. Here `auditable`
means that the record's discovery/eligibility evidence is not classified
`UNAUDITABLE`; it does not imply an outcome is mature or that recall can be
measured.

### Orthogonal factual dimensions

| Dimension | Vocabulary | Contract meaning |
| --- | --- | --- |
| `DISCOVERY_STATE` | `DISCOVERED`, `NOT_DISCOVERED`, `DISCOVERY_NOT_EVALUABLE`, `DISCOVERY_COVERAGE_INCOMPLETE`, `IDENTITY_BLOCKED` | What frozen funnel evidence proves, not an outcome judgment. |
| `BRAIN_DECISION_STATE` | `NOT_EVALUATED_BY_BRAIN`, `ACCEPTED`, `REJECTED`, `INSUFFICIENT_DATA`, `GATE_BLOCKED`, `UNRESOLVED` | Audit-normalized downstream reference; this module calculates none. |
| `ACTION_STATE` | `NOT_APPLICABLE`, `NO_ACTION`, `ACTION_TAKEN`, `ACTION_BLOCKED`, `ACTION_NOT_YET_AVAILABLE` | Descriptive reference only; it creates no action. |
| `OUTCOME_MATURITY` | `IMMATURE`, `PARTIALLY_MATURE`, `MATURE`, `DATA_MISSING`, `NON_COMPARABLE` | Maturity of a future governed outcome receipt, never a price rule. |
| universe membership | `ELIGIBLE`, `INELIGIBLE`, `UNRESOLVED` | Eligibility must be proven before attribution. |
| funnel capability | `CAPABILITY_AVAILABLE`, `DISCOVERY_CAPABILITY_GAP`, `CAPABILITY_UNRESOLVED` | Distinguishes an evaluated engine from an unavailable/unknown capability. |
| per-security evidence | `TRIGGER_EMITTED`, `EVALUATED_NO_TRIGGER`, `PER_SECURITY_EVALUATION_UNKNOWN`, `PER_SECURITY_DATA_BLOCKED`, `IDENTITY_BLOCKED`, `FUNNEL_NOT_EVALUATED` | Prevents reconstruction of source evidence that was never retained. |

`TRIGGER_EMITTED` requires lead and candidate provenance. `EVALUATED_NO_TRIGGER`
requires an actually evaluated capable funnel. A capability gap requires canonical
`NOT_EXECUTABLE`. A blocked/non-operational funnel is never reclassified as an
evaluated no-trigger miss.

## Derived classifications and evidence gates

| Classification | Exact conditions | Never infer it from |
| --- | --- | --- |
| `DISCOVERY_SUCCESS` | Eligible instrument with valid lead and candidate-pool provenance. | Profit, qualification, Brain result, action, or future outcome. |
| `DISCOVERED_BUT_REJECTED` | `DISCOVERED` plus Brain `REJECTED` or `GATE_BLOCKED`. | Correctness of the Brain decision. |
| `DISCOVERY_FAILURE` | Eligible; `NOT_DISCOVERED`; relevant funnel was `CAPABILITY_AVAILABLE` and `EVALUATED_NO_TRIGGER`; no timely valid lead; matching `MATURE` future outcome is `REFERENCE_OPPORTUNITY_CONFIRMED`. | Rally, anecdote, blocked funnel, missing/unknown coverage, or immature outcome. |
| `CORRECTLY_REJECTED` | Eligible; discovered; Brain rejected/blocked; matching mature future outcome is `REJECTION_SUPPORTED`. | Neutral process classification. |
| `DECISION_FAILURE` | Eligible; discovered; Brain rejected/blocked; matching mature future outcome is `REFERENCE_OPPORTUNITY_CONFIRMED`. | Outcome without decision provenance. |
| `ACTION_FAILURE` | Eligible; discovered; Brain accepted; immutable `ACTION_TAKEN` reference; matching mature future outcome is `ACTION_FAILURE_SUPPORTED`. | Discovery, decision, or price history alone. |
| `NOT_YET_ATTRIBUTABLE` | No sufficient mature matching reference outcome. | Preliminary recall. |
| `UNAUDITABLE` | Identity, eligibility, capability, per-security, source, or outcome evidence blocks attribution. | Guessing a missing state. |

`DISCOVERED_BUT_REJECTED` is a process classification. `CORRECTLY_REJECTED` and
`DECISION_FAILURE` are later attributions available only through mature,
pre-registered outcome evidence. A preliminary outcome can be recorded but
cannot derive a failure.

### Fail-closed reason codes

The contract preserves deterministic insufficiency reasons:

- `REFERENCE_OUTCOME_NOT_DEFINED`, `OUTCOME_IMMATURE`,
  `OUTCOME_DATA_MISSING`, `OUTCOME_NON_COMPARABLE`;
- `FUNNEL_NOT_OPERATIONAL`, `FUNNEL_NOT_EVALUATED`,
  `PER_SECURITY_EVALUATION_UNKNOWN`, `DATA_BLOCKED`,
  `IDENTITY_UNRESOLVED`, `UNIVERSE_MEMBERSHIP_UNRESOLVED`,
  `UNIVERSE_NOT_ELIGIBLE`;
- `DISCOVERY_CAPABILITY_GAP`, `BRAIN_NOT_EVALUATED`, and
  `ACTION_LAYER_NOT_AVAILABLE`.

These describe missing evidence. They do not repair it, impose policy, or turn
an unauditable state into success/failure.

## Reference opportunity/outcome boundary

`ReferenceOutcomeDefinitionReference` reserves
`DISCOVERY_RECALL_REFERENCE_OUTCOME_AND_MATCHING_V1`. The future definition must
be versioned, fingerprinted, horizon-specific, and independently governed before
a matcher emits a `ReferenceOpportunityOutcome`.

It will define what counts as an opportunity and a timely discovery match. This
slice expressly approves no return threshold, price move, benchmark, materiality
test, maturity duration, or lookback. Future outcomes must use the historical
eligible universe rather than today's survivors, occur after the cutoff, and
never modify discovery. There is no universal recall truth across short-term,
positional, and long-term horizons.

## Repository readiness audit

| Required evidence | Status | Repository truth and limitation |
| --- | --- | --- |
| Frozen discovery batches | `READY` | `WholeMarketDiscoveryBatch` retains deterministic cutoff, universe/registry identity, executions, leads, and union provenance. This slice adds no persistence. |
| Per-funnel coverage | `PARTIAL` | Execution and coverage exist for all funnels; complete per-security non-emission explanations do not. |
| Candidate-pool identity | `READY` | Existing union has exact canonical security IDs, origins, and fingerprints. |
| Brain decision linkage | `NOT_READY` | Active runner does not invoke or link Shared Brain candidate evaluation. |
| Six-Gates linkage | `NOT_READY` | Six Gates remain evidence-only and discovery contains no link. |
| Signal/action linkage | `NOT_READY` | No action or signal lifecycle is invoked; contract only reserves references. |
| Paper outcomes | `PARTIAL` | Existing `PaperOutcome` is a downstream paper-trade outcome, not a discovery matcher. |
| Benchmark outcomes | `PARTIAL` | PIT-guarded historical replay exists, without discovery-outcome matching. |
| Portfolio-action outcomes | `PARTIAL` | Portfolio/rotation/sell-side records are separate, not causally linked to discovery. |
| Horizon-specific reference opportunity | `NOT_READY` | No approved definition, matcher, horizon rules, or denominator. |

Existing diagnostic/decision audit boundaries, evidence-only Six Gates,
immutable paper outcomes, PIT-protected historical replay/analytical snapshots,
calibration samples, thesis-invalidation receipts, and portfolio sell/rotation
evidence may be referenced later. None duplicates or already supplies a governed
discovery reference opportunity plus causal linkage.

## Current frozen-batch demonstration

At `2026-09-04T19:30:59.533938+00:00`, the frozen batch reported:

| Fact | Value |
| --- | ---: |
| Eligible NSE securities | 2,553 |
| Registered funnels | 14 |
| Executable/evaluated / blocked-not-evaluated funnels | 5 / 9 |
| Raw leads / distinct origins | 356 / 356 |
| Exact-security candidate pool | 73 |
| Single-funnel / multi-funnel pool members | 72 / 1 |
| Eligible securities with no current union item | 2,480 |

`2,480 = 2,553 - 73`. Its only factual present label is
`NO_CURRENT_DISCOVERY_POOL_ITEM`. It is neither an audited `NOT_DISCOVERED`
state nor a `DISCOVERY_FAILURE`, because no complete per-security
no-trigger/no-evaluation/data-blocked explanation was retained for every such
security. A future audit may use `EVALUATED_NO_TRIGGER` only where a bounded
per-security coverage receipt actually proves it.

Historical anecdotes are not encoded as failures. They can become controlled
future cases only with exact batch/cutoff, eligible identity, relevant funnel
capability, pre-registered reference outcome, and maturity.

## Metrics and next slice

Future code may calculate versioned, denominator-explicit overall/funnel/horizon
recall, capability-adjusted recall, valid-ground-truth precision, lead rate,
time-to-discovery, and unauditable rate. This contract calculates none and does
not call raw candidate hit rate precision.

It does not modify the discovery registry, adapters, union, or runner; start
technical-diagnostic operationalization; implement holding/harvest/sell/rotation,
catalyst, signal-lifecycle, alert/orchestration, calibration-ledger, SenseEdge,
or broker-execution work.

The exact next bounded proposal is:

`DISCOVERY_RECALL_REFERENCE_OUTCOME_AND_MATCHING_V1`

It must define an objective, horizon-specific, versioned reference opportunity
set and matching rules before any recall percentage is attempted.
