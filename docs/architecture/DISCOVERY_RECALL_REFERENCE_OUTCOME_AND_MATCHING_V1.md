# Discovery Recall Reference Outcome and Matching V1

**Status:** `ACTIVE / CONTRACT_AND_MATCHING_ONLY / POLICY_NOT_ACTIVE / NON_EXECUTABLE`.

```
DISCOVERY_RECALL_REFERENCE_CONTRACT = ACTIVE
DISCOVERY_RECALL_MATCHING = ACTIVE
DISCOVERY_RECALL_REFERENCE_POLICY = NOT_ACTIVE
DISCOVERY_RECALL_MEASUREMENT = NOT_ACTIVE
DISCOVERY_RECALL_PERFORMANCE_CLAIM = NONE
```

This contract complements the active [Discovery Recall Audit Contract and Outcome
Classification V1](DISCOVERY_RECALL_AUDIT_CONTRACT_AND_OUTCOME_CLASSIFICATION_V1.md).
It defines independent reference ground truth and factual matching to frozen
discovery evidence. It does not define an active opportunity policy, calculate a
recall percentage, change the multi-funnel runner, invoke the Brain, or create a
portfolio/action/order authority.

## Independence boundary

A reference outcome answers a future independent question: what opportunity,
non-opportunity, or insufficiency existed under a pre-registered specification?
It contains no discovery lead, funnel count, Decision Score, Brain verdict, Six
Gates result, HSI recommendation, portfolio, action, broker, price, return, or
performance field. Removing or changing HSI discovery cannot change the reference
outcome. Matching occurs only after the independent record has been frozen.

`REFERENCE_OPPORTUNITY` is not equivalent to a future stock return exceeding a
convenient threshold. A forward return, MFE/MAE, benchmark-relative movement, or
business metric may be a future policy input, but none is ground truth unless an
independent, versioned policy pre-registers its semantics before observation.

Reference outcomes bind to the exact historical universe ID/fingerprint and a
timely historical membership receipt. They cannot use today's surviving universe.
All specification provenance must predate its effective time; active policy
parameters must be frozen; required evidence must be known by the outcome-horizon
end; and reference policy effective time must precede observation. These are
structural anti-look-ahead and anti-optimization guards.

## Immutable reference contract

`app.intelligence.discovery_recall_reference_matching` defines:

| Contract | Required immutable content |
| --- | --- |
| `ReferenceOpportunitySpecification` | ID/version/fingerprint; one horizon and measurement family; historical-universe ID/fingerprint; effective time; observation/deadline/outcome-horizon semantics IDs; required inputs; explicit frozen or `UNSELECTED` parameter states; exclusions; policy status; provenance. |
| `IndependentReferenceOutcome` | Exact canonical security; specification; historical-universe membership proof; observation/onset/deadline/horizon-end times; maturity; independent outcome state; required future evidence; explicit reason codes; deterministic ID/fingerprint. |
| `ReferenceFunnelEligibility` | A separately supplied, versioned-evidence-backed relevance assertion for one funnel and reference horizon. It does not hardcode a global funnel map. |
| `PerSecurityDiscoveryEvaluation` | Optional future immutable receipt for exact batch/security/funnel non-emission state. It is required before a true `NO_DISCOVERY_MATCH` can be asserted where the frozen batch lacks that evidence. |
| `ReferenceDiscoveryMatch` | Reference/batch IDs and fingerprints, exact security, horizon, factual system state, matching/timely/late lead IDs, matching funnels, discovery postures, relevant-funnel coverage, audit-readiness state, deterministic ID/fingerprint. |

Canonical serialization sorts collections and normalizes all timestamps to UTC.
Duplicate/conflicting IDs, ambiguous funnel eligibility, tampered fingerprints,
late policy/mapping/per-security evidence, inexact identity, and incompatible
timelines fail closed.

### Policy and parameter states

`ReferencePolicyStatus` is `PROPOSED`, `RESEARCH_ONLY`, or `ACTIVE`. Only an
`ACTIVE` specification with every parameter `FROZEN` may emit a mature positive,
negative, or inconclusive independent reference result. `UNSELECTED` is explicit:
it is permitted for proposed/research specifications but blocks activation.

No repository policy currently supplies the required independent parameters for
any horizon. The generic contract and matching engine are active; a reference
opportunity policy is not.

### Independent outcome states

The outcome contract deliberately preserves non-binary evidence:

- `REFERENCE_OPPORTUNITY`, `REFERENCE_NON_OPPORTUNITY`, `INCONCLUSIVE` require
  mature evidence under an active, pre-registered policy;
- `IMMATURE`, `DATA_MISSING`, and `NON_COMPARABLE` retain the exact maturity
  limitation without inventing a binary conclusion; and
- `UNIVERSE_INELIGIBLE`, `IDENTITY_UNRESOLVED`, and `POLICY_NOT_ACTIVE` require
  `NOT_EVALUATED` maturity.

An immature long-term observation is not a non-opportunity. An unknown/unsafe
market-price basis cannot be upgraded to a market outcome.

## Horizon-specific reference families

| Horizon | Candidate family | Future independent inputs | Current policy/readiness |
| --- | --- | --- | --- |
| `SHORT_TERM` | `SHORT_TERM_CATALYST` | Exact catalyst identity/public-known time, tradable session, event-relative path, liquidity, price integrity, and policy-defined outcome window. | `NOT_ACTIVE`: exact intraday/public-time and market-reference policy are not ready. |
| `POSITIONAL` | `POSITIONAL_MARKET_PATH` | Pre-registered forward excursion/adverse path, canonical benchmark and sector benchmark where required, duration, liquidity/tradability, market regime, and coherent price basis. | `NOT_ACTIVE`: no frozen objective parameters, benchmark/sector selection, or approved price-basis policy. |
| `LONG_TERM` | `LONG_TERM_BUSINESS_PERSISTENCE` | Revenue/PAT durability, return-ratio persistence where canonical, CFO/PAT quality, balance-sheet evidence, and thesis/business persistence; market path is secondary. | `NOT_ACTIVE`: Compounder/Inflection prospective concepts are reusable but are still immature and do not form a second fundamental engine. |

The family-to-horizon pairing is exact, but no funnel is globally declared
relevant. A future `ReferenceFunnelEligibility` receipt must state whether a
particular funnel is `RELEVANT`, `IRRELEVANT`, or `UNRESOLVED` for a specified
reference horizon. Thus a Pre-Breakout funnel is not silently penalized for a
long-term business reference, nor a Compounder funnel for a short catalyst.

## Factual matching semantics

`match_reference_outcome` consumes an `IndependentReferenceOutcome`, a verified
`WholeMarketDiscoveryBatch`, explicit relevant-funnel mapping, and optional
per-security receipts. It never invokes the runner and never emits
`DISCOVERY_FAILURE`; that classification remains owned by the active audit
classifier, which has additional eligibility/capability/maturity requirements.

| Match state | Exact meaning |
| --- | --- |
| `TIMELY_DISCOVERY_MATCH` | A valid lead from an explicitly relevant funnel exists in the frozen batch at/before the reference discovery deadline. |
| `LATE_DISCOVERY_MATCH` | Relevant lead exists, but the frozen discovery batch is after the deadline. It is not timely success and not never-discovered. |
| `NO_DISCOVERY_MATCH` | No matched lead and an exact, timely `EVALUATED_NO_TRIGGER` per-security receipt exists. Current batch aggregation alone cannot create this state. |
| `PER_SECURITY_EVALUATION_UNKNOWN` | No matched lead, but current retained coverage cannot prove the security was evaluated/no-trigger. |
| `FUNNEL_NOT_CAPABLE` / `FUNNEL_NOT_EVALUATED` | Relevant funnel was respectively non-executable or not evaluated. These are capability facts, not algorithmic misses. |
| `DISCOVERY_NOT_AUDITABLE` / `IDENTITY_CONFLICTED` | Data/inconclusive/non-comparable reference or exact per-security identity evidence blocks matching. |
| `REFERENCE_OUTCOME_IMMATURE` / `REFERENCE_POLICY_NOT_ACTIVE` | The independent outcome/policy is not ready; discovery quality is not judged. |
| `SECURITY_NOT_IN_UNIVERSE` / `REFERENCE_NON_OPPORTUNITY` | The reference itself excludes the security or does not establish an opportunity. |

Research-shadow canonical leads count for factual system discovery when they are
timely and valid, but their `RESEARCH_SHADOW_DISCOVERY` posture is retained
separately. This is neither a recommendation nor a tradability assertion.

## Current readiness matrix

| Horizon | Historical universe | Canonical identity | Reference inputs | Price integrity | Event time | Benchmark / sector benchmark | Business outcome | Maturity | Reference policy | Matching data |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Short-term | `PARTIAL` | `PARTIAL` | `NOT_READY` | `NOT_READY` | `NOT_READY` | `PARTIAL` / `NOT_READY` | `NOT_READY` | `NOT_READY` | `NOT_ACTIVE` | `PARTIAL` contract; no policy/trace |
| Positional | `PARTIAL` | `PARTIAL` | `NOT_READY` | `NOT_READY` | `PARTIAL` | `PARTIAL` / `NOT_READY` | `NOT_READY` | `NOT_READY` | `NOT_ACTIVE` | `PARTIAL` contract; no policy/trace |
| Long-term | `PARTIAL` | `PARTIAL` | `PARTIAL` | `PARTIAL` secondary input | `PARTIAL` | `PARTIAL` / `NOT_READY` | `PARTIAL` prospective evidence | `NOT_READY` | `NOT_ACTIVE` | `PARTIAL` contract; no policy/trace |

Existing reusable boundaries are historical identity/universe and price-integrity
guards, canonical adjusted/raw basis semantics, exchange-calendar/PIT replay,
benchmark observations and alignment, paper MFE/MAE outcomes, prospective
Compounder/Inflection outcomes, and immutable thesis lifecycle evidence. They do
not yet supply an approved independent reference outcome policy or complete
per-security discovery trace. In particular, unknown adjustment basis must remain
`MARKET_REFERENCE_OUTCOME_NOT_READY`, not be normalized in this slice.

The matching contract is compatible with the existing confidence ladder:
historical sanity -> walk-forward -> untouched OOS -> paper/shadow -> forward
SenseEdge pilot -> calibrated performance confidence. It is one attribution layer,
not a competing performance engine.

## Scope and next continuation

No production recall percentage, missed-opportunity count, precision, alpha, or
claim is produced from the current 2,553-security / 73-candidate batch. Its 2,480
non-pool securities remain only `NO_CURRENT_DISCOVERY_POOL_ITEM`.

No anecdotal security is classified as a reference opportunity. No registry,
adapter, union, runner, Brain, Six-Gates, signal/action, holding/harvest/sell/
rotation, execution, or provider behavior changes.

The active [Per-Security Evaluation Trace V1](DISCOVERY_RECALL_PER_SECURITY_EVALUATION_TRACE_V1.md)
now supplies the bounded provenance boundary without changing discovery
intelligence. A real audit runner remains blocked until an independent active
reference policy, adequate historical universe/price data, and mature comparable
outcomes also exist.
