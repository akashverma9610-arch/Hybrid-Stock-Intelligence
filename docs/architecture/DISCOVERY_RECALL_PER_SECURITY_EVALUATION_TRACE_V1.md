# Discovery Recall Per-Security Evaluation Trace V1

**Status:** `ACTIVE / READ_ONLY_TRACE_ONLY / NON_EXECUTABLE / NO_MEASUREMENT`.

```text
DISCOVERY_RECALL_PER_SECURITY_TRACE = ACTIVE
DISCOVERY_RECALL_REFERENCE_POLICY = NOT_ACTIVE
DISCOVERY_RECALL_MEASUREMENT = NOT_ACTIVE
DISCOVERY_RECALL_PERFORMANCE_CLAIM = NONE
```

This is the next factual layer after the active [Discovery Recall Audit
Contract](DISCOVERY_RECALL_AUDIT_CONTRACT_AND_OUTCOME_CLASSIFICATION_V1.md) and
[Reference Outcome and Matching Contract](DISCOVERY_RECALL_REFERENCE_OUTCOME_AND_MATCHING_V1.md).
It records what a frozen batch can prove about one exact
`batch × funnel × NSE:<ISIN>` path. It is neither a funnel, score, ranking,
Brain decision, recommendation, performance report, nor an order/portfolio
surface.

## Proof boundary

`NO DISCOVERY LEAD` is never converted to `EVALUATED_NO_TRIGGER` merely because
the lead is absent. That state requires all of: exact in-scope security,
affirmative adapter/source attempt, timely sufficient individual inputs,
completed evaluation, an explicit factual no-trigger reason, and no emitted
lead or blocker. V1's batch factory does not currently manufacture that state.

The immutable `PerSecurityDiscoveryTrace` binds batch ID/fingerprint, UTC as-of,
canonical instrument/ISIN, issuer IDs only where known, registry funnel and
adapter version, posture/horizons, universe and scope state, trace basis,
evaluation state, input readiness/freshness, existing lead IDs, source lineage,
reason codes, deterministic ID and fingerprint. Timestamps are UTC and every
source lineage reference must be known at or before the frozen batch cutoff.

`DiscoveryFunnelCapabilityTrace` is deliberately separate. It retains compact
batch/funnel execution, adapter/coverage state, source references and blockers;
it does not pretend that all 2,553 securities were inspected. The read-only
audit materializes exact positive traces only and reports aggregate unknown-query
space rather than writing a `14 × 2,553` receipt expansion.

## Evaluation states

| State | Required proof / meaning |
| --- | --- |
| `LEAD_EMITTED` | Exact eligible security has one or more existing, timely canonical leads from this funnel. Lead IDs and immutable lineage are retained. |
| `EVALUATED_NO_TRIGGER` | Exact individual proof standard above. Aggregate adapter `EVALUATED_NO_LEADS` is insufficient. |
| `NOT_IN_FUNNEL_SCOPE` | Explicit contextual scope proof; it is not a failed trigger. |
| `SOURCE_NOT_OPERATIONAL`, `ADAPTER_NOT_AVAILABLE`, `NOT_IMPLEMENTED`, `POLICY_BLOCKED` | Batch/funnel capability facts, never a claimed individual evaluation. |
| `DATA_INSUFFICIENT`, `IDENTITY_BLOCKED`, `EVIDENCE_CONFLICTED`, `STALE` | Exact individual state only when source evidence permits it; otherwise a compact capability receipt retains the aggregate condition. |
| `PER_SECURITY_EVALUATION_UNKNOWN` | The frozen batch lacks individual source/adapter evidence. Unknown is not negative evaluation. |
| `UNIVERSE_INELIGIBLE` | Exact batch universe excludes the NSE security; it is not auditable as a miss. |

The trace has no score, qualification, setup, Decision Score, 61-rule
diagnostic, Six-Gates, signal/action, price, return, entry/exit, portfolio,
broker, order, persistence, API, UI, source fetch or runtime-clock dependency.

## Current adapter truth

The five executed adapters retain only the following per-security facts in the
existing frozen batch:

- **Pre-Breakout:** stored governed opportunity inputs are positive-only.
  A successful empty read does not prove every security was evaluated/no-trigger.
- **Sector Rotation:** each retained Top-3 run identifies exact selected
  constituent IDs, which become positive inspection leads. A security absent
  from a retained candidate list is not automatically out of sector scope or a
  no-trigger; the batch does not retain a universal constituent-evaluation map.
- **Fundamental Inflection:** positive accounting observations are exact and
  reusable. Existing accounting readiness can later strengthen a trace only
  when supplied as exact per-security source evidence; aggregate batch coverage
  cannot prove a negative outcome for every other security.
- **Compounder:** prospective observation/readiness contracts are reusable, but
  the frozen batch's successful empty observation read is not a whole-universe
  no-trigger result.
- **Policy Transmission:** exact research-shadow policy/exposure observations
  can be positive lineage, but missing positive exposure observation is neither
  universal evaluation nor policy qualification.

Contextual Holding/Watchlist funnels are never converted into 2,553 negative
rows. Current whole-market orchestration has no contextual membership receipt,
so V1 preserves their global capability state rather than asserting
`NOT_IN_FUNNEL_SCOPE` for any particular security.

## Frozen-cutoff read-only trace audit

The accepted frozen batch cutoff is
`2026-09-04T19:30:59.533938+00:00`, with 2,553 eligible NSE securities and
batch ID `whole-market-discovery:5cf887c7bdfddb5698ebe4dba13239e1`.
`WholeMarketDiscoveryBatch` itself was intentionally pure/in-memory and was not
persisted. Accordingly, this V1 audit consumes its accepted immutable receipt
facts from the prior read-only orchestration audit; it does **not** rebuild a
new batch from current source snapshots and does not claim a new production
runner execution.

| Funnel | Evaluated? | Exact positive trace securities | `EVALUATED_NO_TRIGGER` | Remaining eligible security queries | Compact capability / dominant gap |
| --- | ---: | ---: | ---: | ---: | --- |
| PRE_BREAKOUT | Yes | 0 | 0 | 2,553 unknown | Positive-only stored opportunity path. |
| SECTOR_ROTATION | Yes | 68 | 0 | 2,485 unknown | Retained Top-3 constituents prove positives, not non-candidate negatives. |
| FUNDAMENTAL_INFLECTION | Yes | 6 | 0 | 2,547 unknown | Eight raw research leads consolidate to six exact security/funnel traces; no retained negative observation path in batch. |
| COMPOUNDER | Yes | 0 | 0 | 2,553 unknown | Successful empty prospective-observation read. |
| POLICY_TRANSMISSION | Yes | 0 | 0 | 2,553 unknown | Successful empty retained eligible-source read. |
| EARNINGS_ACCELERATION, MARKET_DISLOCATION, MOMENTUM, ORDERBOOK_CAPEX, HOLDING_STATE_CHANGE | No | 0 | 0 | Not materialized | `SOURCE_NOT_OPERATIONAL` capability receipts. |
| EMERGING_COMPOUNDER, WATCHLIST_STATE_CHANGE | No | 0 | 0 | Not materialized | `NOT_IMPLEMENTED` capability receipts. |
| NEWS_CATALYST, VALUATION_RECOVERY | No | 0 | 0 | Not materialized | `POLICY_BLOCKED` capability receipts. |

There are **74** exact security/funnel positive traces (68 Sector Rotation and
6 Fundamental Inflection), backed by **356** raw lead origins. This is an audit
observability fact, not discovery recall. A per-security completeness ratio is
not calculated because non-emitted relevant scope denominators are not retained.

The current 2,480 securities with no candidate-pool item remain
`NO_CURRENT_DISCOVERY_POOL_ITEM` only. For an executable funnel they can be
queried as `PER_SECURITY_EVALUATION_UNKNOWN`; blocked funnels retain only their
compact capability state. They are not misses, false negatives, or
`DISCOVERY_FAILURE` records.

### Five-target factual trace view

| Security | Executed-funnel factual state at frozen cutoff |
| --- | --- |
| APARINDS (`NSE:INE372A01015`) | Fundamental Inflection `LEAD_EMITTED` with two retained observation origins; all other executed-funnel non-emission remains unknown. |
| DEEPINDS (`NSE:INE0FHS01024`) | No pool item; all five executed funnels remain per-security unknown. |
| GENUSPOWER (`NSE:INE955D01029`) | No pool item; all five executed funnels remain per-security unknown. |
| GLAND (`NSE:INE068V01023`) | Fundamental Inflection `LEAD_EMITTED` with two retained observation origins; all other executed-funnel non-emission remains unknown. |
| ICICIBANK (`NSE:INE090A01021`) | No pool item; all five executed funnels remain per-security unknown. |

The sole multi-funnel security, `NSE:INE010B01027`, has two factual positive
trace states: Sector Rotation `LEAD_EMITTED` with eight existing sector-run
origins, and Fundamental Inflection `LEAD_EMITTED` with one existing accounting
origin. Multiple origins are lineage, not votes, ranking, confidence, or action.

## Matching and Recall boundary

`as_reference_matching_evaluation` narrows an already verified trace to the
active reference matcher only: exact `EVALUATED_NO_TRIGGER`, data insufficiency,
identity block, or not-evaluated state. It creates no reference opportunity,
no `DISCOVERY_FAILURE`, and no recall metric. Active matching can therefore
distinguish timely lead, proven no-trigger, global capability block and unknown
evaluation when an independently mature reference outcome exists.

No active horizon-specific reference policy, price-integrity basis, mature
outcome population or eligible per-security scope denominator exists yet.
Discovery Recall is therefore contractually ready but measurement remains
policy/data blocked.

## Next boundary

```text
DISCOVERY_RECALL_INFRASTRUCTURE = READY
DISCOVERY_RECALL_MEASUREMENT = DATA/POLICY_BLOCKED
NEXT = TECHNICAL_DIAGNOSTIC_TIMEFRAME_DATA_READINESS_V1
```

No further Recall infrastructure is authorized by this document. The next
technical lane must retain one canonical 61-Diagnostic Registry and is not
started here.
