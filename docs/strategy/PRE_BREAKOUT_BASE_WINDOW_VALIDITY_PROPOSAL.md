# Pre-Breakout Base Window Validity and Base Top Proposal

**Status: PROPOSED — NOT APPROVED — NOT SELECTED — NOT ACTIVE.**

This governance proposal does not alter selected `pre-breakout-policy-v1` / `v1.1-draft`, create a successor, authorize materialization, or create candidates, signals, orders, or activation.

## Scope

This proposal defines only prospective `BASE_WINDOW_VALIDITY_RULE` and `BASE_TOP_DEFINITION`. It deliberately leaves `BASE_WINDOW_SELECTION_RULE`, `SUPPORT_PIVOT_SELECTION_RULE`, and `NSE_TICK_SIZE_SOURCE` unresolved.

## Candidate-window construction

For evaluation session `E`, evaluate exactly the suffix windows of 20 through 60 inclusive canonical daily sessions ending at `E`:

```text
last 20 canonical sessions through E
last 21 canonical sessions through E
...
last 60 canonical sessions through E
```

- Evaluation session is included; every candidate ends at it.
- Windows ending before `E` are ineligible.
- Calendar-day length is irrelevant.
- A 19-session window is ineligible; a 61-session candidate is not evaluated.

The base is the current structure being evaluated, not an older disconnected historical structure.

## Session continuity and gaps

Candidates must use consecutive eligible canonical trading sessions from stored OHLCV/session chronology. Do not infer continuity from calendar days. If a required canonical session is missing or unusable, the candidate is `INVALID` / `DATA_UNAVAILABLE`: do not compress across gaps, fill them, or substitute provider-specific bars manually.

## Pivot/PIT rule

Use the existing strict 3-left / 3-right pivot semantics. A pivot at session `P` is eligible only once all three following eligible sessions are visible and PIT-eligible at the requested `as_of`.

```text
P+1 and P+2 visible; P+3 absent -> not confirmed
P+3 PIT-visible                 -> may be confirmed
```

No historical evaluation may use a pivot before confirmation is knowable. This is a policy requirement for future base materialization; it does not change the current technical helper.

## Proposed structural validity

A candidate base is valid only when all conditions hold:

1. `20 <= canonical_session_count <= 60`.
2. It ends at and includes evaluation session `E`.
3. Session continuity/data eligibility is valid.
4. It has at least two PIT-confirmed pivot highs.
5. It has at least two PIT-confirmed pivot lows.
6. The latest confirmed pivot low is greater than or equal to the immediately preceding confirmed pivot low.
7. Evaluation-session close is less than or equal to the governed base top.

No range-width percentage, ATR cap, BBW threshold, volume threshold, RSI threshold, high-distance threshold, or delivery threshold is part of base validity. These remain independent governed setup conditions. In particular, V1.1's evaluation-session versus previous-20-valid-volume rule does not define a base window.

## Proposed `BASE_TOP_DEFINITION`

`BASE_TOP` is the maximum **high** among all eligible PIT-confirmed pivot highs contained in the candidate base window.

Required evidence is `base_top`, `base_top_source_pivot_session`, and `eligible_confirmed_pivot_highs`.

If eligible confirmed pivot highs share the exact maximum high, numeric base top remains the shared value and the **most recent** such pivot supplies the lineage session. Base top is not a raw session maximum, latest pivot alone, close, manual line, or arbitrary resistance line.

The pre-breakout close condition is inclusive: close below or equal to base top passes this criterion; close above base top invalidates the window as pre-breakout.

## Edge cases

| Case | Proposed outcome |
| --- | --- |
| Exactly 20 / 60 sessions | Duration-eligible |
| 19 sessions | Ineligible |
| 61 sessions | Not evaluated |
| One pivot high or one pivot low | Invalid base |
| Latest low equals or exceeds prior low | Passes low-progression criterion |
| Latest low below prior low | Invalid base |
| Evaluation close equals/below base top | Passes close criterion |
| Evaluation close above base top | Invalid pre-breakout base |
| Equal highest pivot highs | Shared top; most recent supplies lineage |
| No valid windows | `BASE_WINDOW_VALIDITY = NO_VALID_WINDOW`, fail closed |

## Multiple windows, support, and ticks

If multiple suffix windows are valid, report all of them and retain `BASE_WINDOW_SELECTION_RULE` as unresolved. Shortest and longest window are selection alternatives, not validity semantics.

The required pivot lows evidence structure only. They do not select support, define a stop, or resolve `SUPPORT_PIVOT_SELECTION_RULE`. `NSE_TICK_SIZE_SOURCE` remains unresolved; no trigger or tick adjustment is proposed.

## Conceptual typed representation

```text
BaseWindowValidityRule
  min_sessions = 20; max_sessions = 60
  include_evaluation_session = true
  must_end_at_evaluation_session = true
  require_contiguous_canonical_sessions = true
  pivot_left = 3; pivot_right = 3
  min_confirmed_pivot_highs = 2; min_confirmed_pivot_lows = 2
  pivot_low_progression = NON_DECREASING_LAST_TWO
  evaluation_close_relation_to_base_top = LESS_THAN_OR_EQUAL
  zero_match_behavior = FAIL_CLOSED

BaseTopDefinition
  source = MAX_CONFIRMED_PIVOT_HIGH
  tie_break = MOST_RECENT_EQUAL_MAX_PIVOT
```

This is documentation, not a request to implement these types in this slice.

## Alternatives not adopted

| Alternative | Reason |
| --- | --- |
| One pivot high / one pivot low | Insufficient repeated structural evidence. |
| Raw maximum session high | Allows isolated spikes and ignores confirmed-pivot semantics. |
| Shortest / longest valid window | Separate selection decision, intentionally deferred. |
| Arbitrary maximum range percentage | Explicitly excluded by the existing human V1 decision. |

## Rationale and required human decisions

This is deterministic, PIT-safe, explainable, minimally parameterized, and separates base structure from BBW, ATR, volume, RSI, delivery, and high-proximity gates. It does not claim statistical superiority or backtest proof.

Before a successor draft can be created, humans must independently decide: (1) approve/reject/modify this validity and base-top proposal; (2) a deterministic multiple-window selection rule; (3) support-pivot selection; and (4) NSE tick-size source.
