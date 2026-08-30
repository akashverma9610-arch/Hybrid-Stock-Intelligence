# Unified Continuous Intelligence State

Canonical market, filing, fundamental, news, taxonomy, and reference-data
stores remain the source of truth. `UnifiedIntelligenceState` is an immutable,
as-of bounded, versioned projection that references their eligible artifacts
and provenance rather than copying raw bars, filings, articles, or provider
payloads.

`canonical evidence → derived state → future delta intelligence → one shared
Brain → multiple output views`

The state is not a scanner cache, mutable current-truth blob, portfolio record,
recommendation, score, gate result, signal, or trade. If a derived state is
lost, it must be rebuildable from canonical evidence and governed derivation
contracts. Its dependency and invalidation metadata is lineage only; this slice
does not add listeners, change detection, persistence, or a state builder.

Each evidence-domain reference carries availability, artifact references,
as-of/observed timestamps, existing freshness semantics, provenance fingerprint,
historical-integrity reference, and warnings. Missing, stale, and conflicted
evidence remain explicit. The projection has an explicit `as_of` and never
permits future evidence into historical use.

## Governed Pre-Breakout setup evidence

`GovernedPreBreakoutSetupAssessment` is the single durable, insert-only source
for governed technical/setup evidence. It has a canonical full-semantic
fingerprint and is stored as a validated JSON payload. The unified-state adapter
reads only the latest eligible assessment at or before its `as_of`; it does not
rerun technical materialization, sector rotation, setup assessment, or a
scanner. Both eligible and blocked assessments are meaningful technical
evidence. An eligible assessment can deterministically reconstruct a
`PreBreakoutCandidate`, and then a `BrainResearchHandoff`; candidates therefore
are deliberately not persisted as duplicate state. No unified states, caches,
reliability decisions, recommendations, scores, gates, signals, or trades are
persisted by this boundary.

## Durable reliability decisions

`StoredReliabilityDecision` is the strategy-agnostic, immutable record of an
already-computed source-routing conclusion. Durable writes require an explicit,
timezone-aware evaluation boundary and a verified semantic fingerprint; the
payload contains only typed outcome, source lineage, timestamps, warnings, and
evidence metadata—never clients, credentials, exceptions, retry state, or raw
provider data. The repository is insert-only and the unified-state adapter
reads only decisions eligible at its `as_of`. It never reruns routing or
provider fallback logic. Existing typed semantics remain intact: primary/ready
is available, fallback and LKG are partial, unavailable stays unavailable, and
a valid source conflict stays conflicted rather than being treated as storage
corruption.

Portfolio facts stay separate. A `PortfolioContextRef` can be attached only to
a `BrainOutputRequest`; quantity, average cost, P&L, tax, heat, and allocation
facts cannot alter shared stock intelligence. The same state can therefore be
requested for opportunity discovery, deep analysis, portfolio review,
sell/trim review, rotation review, entry setup, or alerts without creating
separate scanner, portfolio, or sell Brains.

## Context-bound output evaluation

`BrainOutputEvaluationContext` is a pure, immutable attachment validation
contract, not an output decision. It binds one reconstructed state, its exact
`BrainOutputRequest`, an optional `PortfolioContextRef`, and supplied immutable
Decision Score/Six Gates artifacts only when instrument, state fingerprint,
as-of, scorecard, policy, action-context, and (where stored) portfolio snapshot
lineage match exactly.

```
UnifiedIntelligenceState + BrainOutputRequest + optional PortfolioContextRef
  + persisted DecisionScorecard + matching ExecutionGateEvaluation
  -> BrainOutputEvaluationContext -> future output decision layer
```

Six Gates remain context-dependent: Entry Setup accepts only `FRESH_ENTRY` and
Rotation Review only `ROTATE_IN`; a gate snapshot reference requires the exact
portfolio snapshot ID. Deep Analysis is currently informational and can use
state alone. This layer executes no score or gate, does not persist
state/context, and produces no recommendation, signal, order, or trade.

## Governed output-context requirements

`BrainOutputRequirementPolicy` is the versioned, immutable source of truth for
which existing artifacts a review context needs. It separates a broad review
from a concrete `ActionContext`; readiness still means only coherent inputs.

| Brain output context | Informational only | Score | Portfolio context | Six Gates | Exact action context | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| Opportunity Discovery | No | Yes | No | Yes | `FRESH_ENTRY` | Existing qualified universe opportunities retain score and entry-gate lineage; this is not a recommendation. |
| Deep Analysis | Yes | No | No | No | — | Shared research/intelligence view only. |
| Portfolio Review | Yes | No | Yes | No | — | Broad ownership review; it is not equivalent to Hold/Add/Reduce/Exit. |
| Sell/Trim Review | Yes | No | Yes | No | — | Broad review; concrete Reduce/Exit evaluation needs a later exact mapping. |
| Rotation Review | No | Yes | Yes | Yes | `ROTATE_IN` | Existing rotation gate context. |
| Entry Setup Review | No | Yes | Conditional on stored gate lineage | Yes | `FRESH_ENTRY` | Exact gate input lineage remains required. |
| Alert Review | Yes | No | No | No | — | Generic alerts are heterogeneous; a later actionable alert must reference a concrete context. |

The policy fingerprint is included in every `BrainOutputEvaluationContext`.
Changing an artifact requirement or action-context mapping therefore creates a
different immutable downstream context without changing shared state. No
output-context policy executes a gate, calculates a score, or emits an action.

## Read-only context-bound output projections

`BrainOutputProjection` is a deterministic, bounded view created only from a
ready `BrainOutputEvaluationContext`. The context retains the state’s existing
evidence references—not provider payloads—so the projector does not rebuild
state, read a repository, fetch data, calculate a score, or execute Six Gates.

```
Canonical evidence -> UnifiedIntelligenceState -> BrainOutputRequest
  -> BrainOutputEvaluationContext -> BrainOutputProjection
  -> future contextual decision layer
```

The projection policy is complete and versioned for every output context. It
changes only visible reference sections; the shared state identity is unchanged.
`PARTIAL`, `STALE`, `CONFLICTED`, and `UNAVAILABLE` evidence references remain
visible in their selected sections. A blocked evaluation context cannot be
projected.

| Context | Bounded projection sections |
| --- | --- |
| Opportunity Discovery | Market, sector, technical/setup, reliability, research, score, gate lineage, entry context |
| Deep Analysis | Market, sector, company research, technical/setup, news, reliability, research |
| Portfolio Review | Market, sector, company research, technical/setup, news, reliability, research, portfolio reference |
| Sell/Trim Review | Company research, technical/setup, news, reliability, research, portfolio reference |
| Rotation Review | Market, sector, technical/setup, reliability, research, score, gate lineage, portfolio reference |
| Entry Setup Review | Technical/setup, reliability, score, gate lineage, entry context |
| Alert Review | Market, sector, technical/setup, news, reliability, research, alert context |

Projection is not a recommendation, action, signal, order, trade, or execution
permission. It carries only contextual evidence references and validated
lineage. It has no persistence or change-detection mechanism.
