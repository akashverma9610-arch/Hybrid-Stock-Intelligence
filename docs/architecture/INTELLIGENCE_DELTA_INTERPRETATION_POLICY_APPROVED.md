# Frozen Objective Intelligence-Delta Interpretation Policy

**Status: APPROVED — NOT SELECTED — NOT ACTIVE.**

This document records the first frozen objective-only policy. It is immutable
policy metadata, not a production interpreter. It does not evaluate an
`IntelligenceDelta`, create an alert, make a recommendation, or authorize any
portfolio or execution action.

## Identity and lineage

| Field | Value |
| --- | --- |
| Policy ID | `intelligence-delta-interpretation-policy` |
| Frozen version | `v1-approved` |
| Prior proposal | `intelligence-delta-interpretation-policy / v1-proposed` |
| Approval state | `APPROVED` |
| Governance identity | `human:Akash-Verma` |
| Selected for future interpreter | `false` |
| Active | `false` |
| Canonical artifact | `app/intelligence/intelligence_delta_interpretation_policy.py` |

The policy fingerprint is deterministically calculated from every semantic
field in the immutable artifact. No database record, selection record, or
activation record is created by this freeze.

## Approved objective transition rules

The policy stores independent dimension rules. A future interpreter must retain
coexisting results; it must not collapse them into `OVERALL_IMPROVED`,
`OVERALL_DEGRADED`, thesis, opportunity, investment-risk, or market-direction
language.

| Dimension | Previous → current | Frozen objective interpretation | Required typed condition |
| --- | --- | --- | --- |
| Freshness | `FRESH → STALE` | `FRESHNESS_DEGRADED` | None |
| Freshness | `STALE → FRESH` | `FRESHNESS_IMPROVED` | None |
| Intelligence availability | `UNAVAILABLE → AVAILABLE` | `INTELLIGENCE_AVAILABILITY_IMPROVED` | None |
| Intelligence availability | `AVAILABLE → UNAVAILABLE` | `INTELLIGENCE_AVAILABILITY_DEGRADED` | None |
| Reliability | `READY → DEGRADED` | `RELIABILITY_DEGRADED` | None |
| Reliability | `DEGRADED → READY` | `RELIABILITY_IMPROVED` | None |
| Reliability | selected usable route → `PRIMARY_UNAVAILABLE` | `RELIABILITY_DEGRADED` | Previous typed evidence proves the selected usable route. |
| Reliability | selected usable route → `UNAVAILABLE` | `RELIABILITY_DEGRADED` | Previous typed evidence proves the selected usable route. |
| Reliability | `PRIMARY_UNAVAILABLE` → selected usable route | `RELIABILITY_IMPROVED` | Current typed evidence proves the selected usable route. |
| Reliability | `UNAVAILABLE` → selected usable route | `RELIABILITY_IMPROVED` | Current typed evidence proves the selected usable route. |
| Historical integrity | `VALID → PARTIAL` | `HISTORICAL_INTEGRITY_DEGRADED` | Native typed status lineage required. |
| Historical integrity | `VALID → INVALID` | `HISTORICAL_INTEGRITY_DEGRADED` | Native typed status lineage required. |
| Historical integrity | `PARTIAL → VALID` | `HISTORICAL_INTEGRITY_IMPROVED` | Native typed status lineage required. |
| Historical integrity | `INVALID → VALID` | `HISTORICAL_INTEGRITY_IMPROVED` | Native typed status lineage required. |
| Historical integrity | `PARTIAL → INVALID` | `HISTORICAL_INTEGRITY_DEGRADED` | Native typed status lineage required. |
| Historical integrity | `INVALID → PARTIAL` | `HISTORICAL_INTEGRITY_IMPROVED` | Native typed status lineage required. |

Identical governed states map to `NO_DIRECTIONAL_CHANGE`. Evidence addition or
removal alone maps to `NON_COMPARABLE`; it is never automatically positive or
negative.

## Explicit non-comparable boundaries

The following remain frozen as `NON_COMPARABLE`:

- Unsupported or mixed freshness transitions.
- Unsupported availability transitions.
- Reliability `CONFLICTED` transitions.
- Reliability fallback/LKG transitions.
- Mixed reliability readiness, freshness, or route-tier transitions.
- `PRIMARY_UNAVAILABLE ↔ UNAVAILABLE`; these are different no-route causes,
  not an ordinal relationship.
- Reliability route-cause changes without typed proof of selected-route loss or
  recovery.
- Every native historical-integrity transition involving `UNAVAILABLE`.
- Historical Unified-State projected `CONFLICTED`; native `INVALID` is not
  carried as a typed status at that boundary.
- Historical-integrity fingerprint-only changes.

`STALE ↔ READY` stays exclusively within freshness interpretation unless a
separate approved reliability fact also changes. No duplicate reliability
meaning is frozen for freshness alone.

## Explicit exclusions

The policy does not contain thesis direction, opportunity direction, generic
investment-risk direction, bullish/bearish language, recommendations,
execution, Decision Score direction, news/catalyst direction, or Six Gates
direction. It includes no BUY, HOLD, SELL, TRIM, or ROTATE semantic.

## Runtime boundary

`UnifiedIntelligenceState`, `IntelligenceDelta`, state comparison, output
projection, scanner, portfolio review, sell review, alerts, APIs, and trading
remain unchanged. U14D-4C added a pure, explicitly invoked domain interpreter,
documented in
[`INTELLIGENCE_DELTA_OBJECTIVE_INTERPRETER.md`](INTELLIGENCE_DELTA_OBJECTIVE_INTERPRETER.md).
It has no operational wiring, does not activate this policy, and requires the
typed evidence needed for each conditional rule.
