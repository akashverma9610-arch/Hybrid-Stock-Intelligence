# Pre-Breakout Base Window Selection Proposal

**Status: PROPOSED — NOT APPROVED — NOT SELECTED — NOT ACTIVE.**

This is a governance-only proposal for `BASE_WINDOW_SELECTION_RULE`. It does not alter selected `pre-breakout-policy-v1` / `v1.1-draft`, create a successor, approve or select a policy, implement a materializer, or produce candidates, trade structures, signals, or orders.

## Preconditions and scope

Selection operates only after the U13B-3B proposed validity/base-top semantics have been human approved and materialized in a future bounded implementation. The admissible set is only the 20–60 inclusive, current-evaluation-session suffix windows that are already structurally valid at the requested `as_of`.

An invalid window, a window with PIT-ineligible pivots, or a window ending before evaluation is never eligible for selection. `SUPPORT_PIVOT_SELECTION_RULE`, `NSE_TICK_SIZE_SOURCE`, trigger, stop, target, and R:R are intentionally outside selection.

## Alternatives evaluated

| Alternative | Deterministic/PIT-safe | Structural concern | Decision |
| --- | --- | --- | --- |
| Shortest valid window | Yes | Can exclude an older, higher confirmed pivot high that remains structural resistance in a longer current valid window. | Not selected alone. |
| Longest valid window | Yes | Always retains maximum history and can preserve stale structural highs merely because 60 sessions remains valid. | Not selected. |
| Most recent/latest-start | Yes | For suffix windows it is exactly equivalent to shortest duration; it is not an independent rule. | Not selected alone. |
| Highest base-top only | Yes | Preserves highest confirmed resistance but leaves unnecessary stale-history breadth among equal-high windows. | Not selected alone. |
| Maximum pivot count/density | Potentially | Requires additional definitions for counting, density, ties, and quality; adds hidden parameters. | Not selected. |
| Minimal current structure | Potentially | Without a separate definition it is merely shortest-valid. | Captured by the secondary tie-break below. |
| Discretionary pattern-quality score | No | Requires subjective chart interpretation and non-governed scoring. | Rejected. |

## Recommended rule

**CONSERVATIVE_RECENT_STRUCTURE_SELECTION**

The rule preserves the highest confirmed structural resistance represented by any valid current base, then minimizes structure age without discarding that resistance.

### Exact deterministic algorithm

1. Build all approved-valid suffix candidate windows of duration 20 through 60 at requested `as_of`.
2. If no valid windows exist, return `NO_VALID_WINDOW` and select none.
3. If exactly one valid window exists, select it.
4. For multiple valid windows, calculate `maximum_base_top` as the exact maximum of their governed `base_top` decimal values.
5. Retain only windows whose `base_top == maximum_base_top` exactly. No floating tolerance is used.
6. Select the retained window with the smallest canonical session count.
7. Candidate suffix lengths are unique, so the final selected duration is unique. A future implementation must treat duplicate windows with the same start, end, and duration as an invariant violation rather than relying on insertion, database, or provider order.

This is a structural rule only. It cannot choose a window for a nearer stop, a higher target, better R:R, a passing downstream candidate, selected support, or tick adjustment.

## Resistance preservation and stale-history treatment

Because base top is the greatest eligible confirmed pivot-high high in the selected window, selection changes resistance when an older high is included in one valid suffix but excluded in another.

The proposed primary `maximum_base_top` filter prevents a short valid window from hiding a higher confirmed resistance that remains inside another valid 20–60 session base. The secondary shortest-duration rule prevents automatic retention of the longest historical formation after the same governing resistance is retained in a more recent valid base. This is conservative with respect to overhead supply without always carrying stale structure to 60 sessions.

It does not decide whether an aged pivot should cease to be meaningful before it exits the approved 60-session universe. That would require a separate human-governed aging/validity semantic and is not introduced here.

## Output lineage proposal

A future selection result must preserve, at minimum:

- `selected_window_start`
- `selected_window_end`
- `selected_window_sessions`
- `selected_duration`
- `selected_base_top`
- `base_top_source_pivot_session`
- `eligible_confirmed_pivot_highs`
- `eligible_confirmed_pivot_lows`

These are proposed output requirements, not an implementation in this slice.

## Zero, one, and multiple valid windows

| Valid-window state | Proposed result |
| --- | --- |
| Zero | `NO_VALID_WINDOW`; fail closed; no fallback to invalid or 60-session window. |
| One | Select the sole valid window. |
| Multiple | Apply `CONSERVATIVE_RECENT_STRUCTURE_SELECTION`. |

## Required edge cases

| Case | Valid windows/base top | Result |
| --- | --- | --- |
| A | 20, 25, 31; all `500` | Select 20: same maximum top, shortest duration. |
| B | 20=`500`, 35=`520`, 60=`520` | Select 35: preserve `520`, then shortest among equal-top windows. |
| C | 20 valid=`500`, 40 invalid, 60 valid=`530` | Select 60: only valid window preserving maximum `530`. |
| D | Only 43 valid | Select 43. |
| E | None valid | `NO_VALID_WINDOW`, no selection. |
| F | Newly PIT-confirmed pivot high raises top | Recalculate valid windows at the new `as_of`; select by the same maximum-top then shortest rule. |

## PIT/as-of behavior and session-to-session stability

Selection receives only windows already valid at the requested `as_of`; it cannot admit a pivot until P+3 confirmation is visible and eligible. It therefore adds no lookahead.

Expected deterministic transitions when a new session arrives:

- With unchanged valid pivots/base tops, the earliest suffix may age out and candidates roll by one session; the selected result changes only if the set that survives the maximum-top/shortest rule changes.
- If an old highest pivot falls outside the 60-session candidate universe, its window can no longer contribute a base top; selection moves deterministically to the current maximum.
- If a newly confirmed pivot high exceeds the old maximum, qualifying windows containing it become preferred at the next eligible `as_of`.
- If a newly confirmed pivot low causes a candidate to violate non-decreasing-low validity, that candidate leaves the valid set; no hysteresis or fallback is implied.

No hysteresis is proposed. Any stability layer would be a separate governed decision.

## Rationale, limitations, and remaining decisions

The rule is deterministic, PIT-safe, reproducible, backtestable/versionable, free of hidden numeric quality scores, and independent of support/tick/trade-economics semantics. It is not a claim of statistical superiority and was not tuned on current stocks or candidate count.

Before successor-policy creation, human governance must explicitly approve, reject, or modify both the U13B-3B validity/base-top proposal and this selection proposal. Independent decisions are still required for `SUPPORT_PIVOT_SELECTION_RULE` and `NSE_TICK_SIZE_SOURCE`.
