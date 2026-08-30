# Intelligence Delta Interpretation Policy Proposal

**Status: PROPOSED — NOT APPROVED — NOT ACTIVE.**

This historical proposal remains unchanged. Its first approved, immutable,
objective-only successor is documented in
[`INTELLIGENCE_DELTA_INTERPRETATION_POLICY_APPROVED.md`](INTELLIGENCE_DELTA_INTERPRETATION_POLICY_APPROVED.md):
`intelligence-delta-interpretation-policy / v1-approved`. The successor is
**APPROVED — NOT SELECTED — NOT ACTIVE** and does not implement an interpreter.

This is a governance design, not a production interpreter. It must not create
alerts, recommendations, actions, signals, orders, trades, persistence, or
automation.

## Existing-language audit

`ACCELERATING`/`DETERIORATING` and crisis/euphoria terminology are existing
domain-specific artifact language. They are not a generic IntelligenceDelta
interpretation vocabulary. No existing cross-domain `THESIS_STRENGTHENED`,
`OPPORTUNITY_IMPROVED`, or generic `RISK_INCREASED` contract was found; those
remain unsafe for automatic interpretation.

## Proposed layers

1. Objective quality: freshness, reliability, integrity, and intelligence
   availability transitions only.
2. Domain intelligence: only when a future delta carries comparable, governed
   bounded domain values.
3. Thesis/opportunity/risk: deferred; requires multi-domain governed evidence.
4. Actions: permanently outside this proposal.

## Proposed model and policy

Future immutable `IntelligenceDeltaInterpretation` and per-domain
`IntelligenceDomainInterpretation` would retain delta lineage, policy lineage,
typed interpretation kind, supporting change kinds, evidence sufficiency, and
comparability status. Proposed policy identity:

`intelligence-delta-interpretation-policy / v1-proposed`.

It is not authorized for construction or production use until explicit human
approval freezes its exact fingerprint and transition rules.

Evidence sufficiency: `SUFFICIENT`, `INSUFFICIENT`, `NON_COMPARABLE`, or
`NOT_APPLICABLE`. No percentage confidence is proposed.

| Raw transition | Direction inferable now? | Proposed result | Evidence / comparability |
| --- | --- | --- | --- |
| FRESH → STALE | Yes | `FRESHNESS_DEGRADED` | exact existing FreshnessStatus |
| STALE → FRESH | Yes | `FRESHNESS_IMPROVED` | exact existing FreshnessStatus |
| READY/PRIMARY → FALLBACK | Not yet | `NON_COMPARABLE` | reliability ordering must be human-governed |
| FALLBACK → LKG | Not yet | `NON_COMPARABLE` | same |
| LKG → UNAVAILABLE | Not yet | `NON_COMPARABLE` | same |
| CONFLICTED → READY | Not yet | `NON_COMPARABLE` | conflict is non-ordinal |
| VALID → PARTIAL | Not yet | `NON_COMPARABLE` | integrity ordering must be approved |
| PARTIAL → INVALID | Not yet | `NON_COMPARABLE` | same |
| UNAVAILABLE → AVAILABLE | Yes, quality only | `INTELLIGENCE_AVAILABILITY_IMPROVED` | availability only, not investment direction |
| AVAILABLE → UNAVAILABLE | Yes, quality only | `INTELLIGENCE_AVAILABILITY_DEGRADED` | availability only |
| Decision Score artifact replaced | No | `NO_DIRECTIONAL_INTERPRETATION` | no bounded old/new score values in delta |
| News artifact added | No | `NO_DIRECTIONAL_INTERPRETATION` | no sentiment/materiality comparison |
| Earnings artifact replaced | No | `NO_DIRECTIONAL_INTERPRETATION` | no comparable governed metric transition |
| Setup assessment replaced | No | `NON_COMPARABLE` | delta lacks setup status lineage |
| Six Gates artifact replaced | No | `NON_COMPARABLE` | action/portfolio/score context comparability absent |
| Version changed | No | `NON_COMPARABLE` | no cross-version semantics |

Evidence added or removed alone is never positive or negative. Mixed objective
changes remain separate; they are not weighted into a global label. Delta impact
contexts are retained only as possible future reevaluation lineage.

## Reliability and historical-integrity ordering audit (U14D-4A)

**Status: PROPOSED — NOT APPROVED — NOT ACTIVE.** This section supersedes the
earlier placeholder reliability and integrity rows in the table above. It is an
audit of existing contracts, not an implementation of an
`IntelligenceDelta` interpreter.

### Exact reliability inventory

`app/reliability/models.py` defines `ReliabilityStatus`:

| Status | Current contract meaning | Dimension | Ordinal by itself? |
| --- | --- | --- | --- |
| `READY` | A usable selected source is tier 1, readiness is `READY`, and the selected health is not marked stale. | Current routing/source health | Only against `DEGRADED` when the same selected-routing shape is preserved. |
| `DEGRADED` | A usable tier-1 source was selected with `SourceReadinessStatus.DEGRADED`. | Source health/readiness | Partially: `READY → DEGRADED` is objectively worse source health. |
| `STALE` | A usable tier-1 source was selected but its `SourceHealth.freshness` is `STALE`. | Freshness | No separate reliability order; the existing freshness proposal owns this comparison. |
| `PRIMARY_UNAVAILABLE` | Declared candidates existed, but none was usable and no LKG route was selected. | Route availability/cause | Not rankable against `UNAVAILABLE`; it says candidates existed, not that data quality is higher. |
| `FALLBACK_USED` | A usable non-primary source (tier greater than 1) was selected; the decision preserves source/tier and a primary-unavailable warning. | Source-routing tier; may mask a simultaneous freshness/readiness detail because routing takes precedence in the status expression. | Not a total ordinal state. |
| `LAST_KNOWN_GOOD` | No usable current source was selected; an explicitly designated historical last-known-good observation was selected. | Fallback availability and stale lineage | Not rankable against a current fallback from the status alone. |
| `UNAVAILABLE` | No declared source candidate exists. | Route availability/cause | Not rankable against `PRIMARY_UNAVAILABLE`; both have no selected source for different reasons. |
| `CONFLICTED` | More than one usable declared source supplied distinct non-null value fingerprints; routing refuses to choose a source. | Contradictory evidence/no canonical selection | No. |

This contract is deliberately composite. `SourceHealth` separately carries a
numeric `tier`, `SourceReadinessStatus`, `data_available`, and a freshness
field; `ReliabilityDecision` separately carries `selected_source_id`,
`selected_tier`, `fallback_used`, `last_known_good_used`, and
`conflict_detected`. `PRIMARY` is not a `ReliabilityStatus`: it means declared
source tier 1 in `app/reliability/service.py`. The same service only considers
`SourceReadinessStatus.READY` and `DEGRADED` usable; its other independent
readiness values are `CONFIGURED_NOT_VALIDATED`, `MISSING_CONFIGURATION`,
`UNSUPPORTED`, and `UNAVAILABLE` (`app/data_sources/models.py`). None of those
configuration states is a reliability-direction ladder.

The Unified State adapter deliberately projects rather than preserves this
entire composite: `READY → AVAILABLE`; `DEGRADED`, `FALLBACK_USED`, and
`LAST_KNOWN_GOOD → PARTIAL`; `STALE → STALE`; `PRIMARY_UNAVAILABLE` and
`UNAVAILABLE → UNAVAILABLE`; and `CONFLICTED → CONFLICTED`
(`app/intelligence/non_company_evidence.py`). The state reference retains
fingerprints and warnings, not a typed `ReliabilityStatus`; current
`IntelligenceDelta` can report `RELIABILITY_CHANGED` but cannot safely decode
or interpret a raw routing transition.

### Reliability comparability and proposed matrix

There is no total reliability ordering. The only currently safe proposed
directional subset is source-health deterioration/recovery when the explicit
status is exactly `READY` or `DEGRADED`, plus the objective loss/recovery of a
selected route when neither side is conflicted. Staleness remains a separate
freshness result so an interpreter cannot double-count it as reliability.

| Previous → current | Proposed result | Repository-grounded rationale |
| --- | --- | --- |
| same `ReliabilityStatus` | `NO_DIRECTIONAL_CHANGE` | No status transition. |
| `READY → DEGRADED` | `RELIABILITY_DEGRADED` | The service selected a tier-1 source whose readiness became `DEGRADED`. |
| `DEGRADED → READY` | `RELIABILITY_IMPROVED` | The same bounded readiness dimension recovered. |
| `STALE → READY` | `NO_DIRECTIONAL_CHANGE` in this matrix; `FRESHNESS_IMPROVED` under the existing freshness mapping | This is a freshness comparison, not a second generic reliability label. |
| `READY → STALE` | `NO_DIRECTIONAL_CHANGE` in this matrix; `FRESHNESS_DEGRADED` under the existing freshness mapping | Same boundary as above. |
| any selected-route status (`READY`, `DEGRADED`, `STALE`, `FALLBACK_USED`, `LAST_KNOWN_GOOD`) → `PRIMARY_UNAVAILABLE` or `UNAVAILABLE` | `RELIABILITY_DEGRADED` | The decision changes from a selected source to no selected source. |
| `PRIMARY_UNAVAILABLE` or `UNAVAILABLE` → any selected-route status (`READY`, `DEGRADED`, `STALE`, `FALLBACK_USED`, `LAST_KNOWN_GOOD`) | `RELIABILITY_IMPROVED` | A bounded selected route again exists; this says nothing about investment direction or freshness. |
| `PRIMARY_UNAVAILABLE ↔ UNAVAILABLE` | `NON_COMPARABLE` | Candidate presence and no-candidate absence are different causes of no routing decision, not quality ranks. |
| any transition involving `CONFLICTED` | `NON_COMPARABLE` | Conflicting usable values deliberately prevent canonical routing. |
| all remaining changes, including `PRIMARY ↔ FALLBACK`, `FALLBACK ↔ LAST_KNOWN_GOOD`, and mixed `STALE`/`DEGRADED`/fallback changes | `NON_COMPARABLE` | The status expression collapses independent tier, readiness, and freshness fields; a status pair alone cannot establish one direction. |

`PRIMARY → FALLBACK`, `FALLBACK → LKG`, and their inverses therefore remain
non-comparable in this proposal. A later policy could compare the preserved
structured fields (`selected_tier`, freshness, selected-source identity, and
LKG flag) only after a separate human-approved comparability contract defines
how mixed dimensions are handled.

### Exact historical-integrity inventory

`app/historical/security_master.py` defines `HistoricalIntegrityStatus`:

| Status | Current contract meaning | Dimension | Ordinal by itself? |
| --- | --- | --- | --- |
| `VALID` | Bars have one non-unknown adjustment state, a known compatible declared basis, and no raw series crossing a known price-transforming action. `HistoricalPriceIntegrity.technical_eligible` is true only here. | Price-basis integrity | Yes, as the only technically eligible state. |
| `PARTIAL` | The basis is unknown, or raw bars span a known price-transforming corporate action; historical-universe membership can also be partial when its source is incomplete. | Known limitation/incomplete coherent basis | Partially, relative to `VALID` and `INVALID` for the explicit assessment rules. |
| `INVALID` | Bar adjustment states conflict or are unknown, or a declared adjusted basis conflicts with raw bars. | Explicit integrity violation | Partially, relative to `VALID` and `PARTIAL` under the existing fail-closed gate. |
| `UNAVAILABLE` | No bars exist for a price assessment, or no usable historical membership source exists for a universe result. | No integrity assessment/evidence | Not a quality rank over `PARTIAL` or `INVALID`. |

`PriceAdjustmentBasis` (`RAW`, `SPLIT_ADJUSTED`,
`CORPORATE_ACTION_ADJUSTED`, `TOTAL_RETURN_ADJUSTED`, `UNKNOWN`) is a separate
input dimension, not an integrity status ordering. The backtest gate gives
`INVALID`, then `UNAVAILABLE`, then `PARTIAL`, then `VALID` fail-closed
precedence when combining component assessments. That is a blocking/precondition
rule; it is not an authorization to treat every pair as a global quality score.

Historical integrity has **no** `CONFLICTED` member. At the Unified-State
boundary, the stored-only adapter maps `VALID → AVAILABLE`, `PARTIAL → PARTIAL`,
`INVALID → CONFLICTED`, and `UNAVAILABLE → UNAVAILABLE`. Its
`historical_integrity_reference` is a fingerprint, not a typed status value.
Consequently, the current delta identifies `INTEGRITY_CHANGED` but cannot
reconstruct a reliable raw-status transition from a state reference alone.

### Historical-integrity comparability and proposed matrix

| Previous → current | Proposed result | Repository-grounded rationale |
| --- | --- | --- |
| same `HistoricalIntegrityStatus` | `NO_DIRECTIONAL_CHANGE` | No status transition. |
| `VALID → PARTIAL` | `HISTORICAL_INTEGRITY_DEGRADED` | Technical eligibility is lost through a known incomplete/coherence limitation. |
| `PARTIAL → VALID` | `HISTORICAL_INTEGRITY_IMPROVED` | The explicit limitation is resolved and technical eligibility is restored. |
| `VALID → INVALID` | `HISTORICAL_INTEGRITY_DEGRADED` | A direct adjustment-state/basis contradiction replaces a valid coherent assessment. |
| `INVALID → VALID` | `HISTORICAL_INTEGRITY_IMPROVED` | The direct contradiction is resolved into the only technically eligible state. |
| `PARTIAL → INVALID` | `HISTORICAL_INTEGRITY_DEGRADED` | Existing gate precedence distinguishes an explicit integrity violation from a partial/known limitation. |
| `INVALID → PARTIAL` | `HISTORICAL_INTEGRITY_IMPROVED` | The explicit contradiction is removed, while the remaining limitation still prevents technical eligibility. |
| any transition to or from `UNAVAILABLE` | `NON_COMPARABLE` | It means no assessment/evidence, not a demonstrated integrity quality; generic availability semantics, if later approved, must remain separate. |
| any transition expressed only as Unified-State `CONFLICTED` availability or changed integrity fingerprint | `NON_COMPARABLE` | The raw `HistoricalIntegrityStatus` is not carried as a typed state field. |

### Treatment of `CONFLICTED`

For reliability, `CONFLICTED` has an exact meaning: multiple otherwise usable
declared sources have different non-null value fingerprints. It is neither a
fallback tier nor ordinary unavailability. Routing fails closed rather than
choosing a canonical source; every transition to or from it remains
`NON_COMPARABLE`.

For historical integrity, `CONFLICTED` is not a native status. The Unified
State projects native `INVALID` to availability `CONFLICTED` so a state consumer
does not mistake an integrity violation for ordinary partial data. That
projection is not sufficient to infer a directional transition from an
aggregate delta; transitions involving the projected value remain
`NON_COMPARABLE` until a later approved, typed raw-status lineage is present.

### Implementation boundary and unresolved governance decisions

No production enum, interpreter, serializer, persistence record, listener,
alert, recommendation, action, signal, order, trade, scan, or provider call is
introduced by this audit. `IntelligenceDelta` remains a change detector only.

Before any implementation, a human must approve this exact matrix under
`intelligence-delta-interpretation-policy / v1-proposed`, decide whether the
selected-route recovery subset should coexist with the generic availability
vocabulary, and approve any future typed reliability/integrity lineage needed
to make currently non-comparable composite transitions comparable.

## Human decisions required before implementation

1. Approve the U14D-4A exact reliability and integrity ordinal/non-ordinal transition maps.
2. Approve the proposed vocabulary and policy fingerprint.
3. Decide whether setup/score/gate artifacts gain comparable bounded status/value
   lineage in a later governed contract.
4. Explicitly authorize any production interpreter separately from any future
   alert, recommendation, or action layer.
