# Pre-Breakout Support Pivot Selection Proposal

**Status: PROPOSED — NOT APPROVED — NOT SELECTED — NOT ACTIVE.**

This governance-only proposal does not alter selected `pre-breakout-policy-v1` / `v1.1-draft`, create a successor, materialize support, calculate stop/target/R:R, create candidates, or activate a strategy.

## Existing support semantics audit

| Concern | Classification | Finding |
| --- | --- | --- |
| Pre-Breakout structural support / swing low / invalidation pivot | Undefined | `SUPPORT_PIVOT_SELECTION_RULE` remains explicitly unresolved. |
| Base validity pivot lows | Approved governance prerequisite | The selected-base chain requires two confirmed lows and non-decreasing final two lows; it does not select support. |
| Pre-Breakout engine input | Existing implementation only | Caller-supplied structural invalidation is accepted; no pivot low is derived. |
| Technical pivot lows | Existing implementation only | Strict 3-left/3-right pivots can identify lows in a bounded snapshot, but assign no Pre-Breakout support meaning. |
| Governed materializer | Existing implementation only | It does not construct a selected base, invoke pivots, or derive support. |
| Generic `valuation_trade` support/stop | Generic/unrelated | Separate diagnostic `TradeRules`, base boundaries, and stop-buffer logic are not inherited by Pre-Breakout. |

## Alternatives

| Alternative | Decision |
| --- | --- |
| Most recent confirmed pivot low inside selected base | Recommended: newest confirmed demand structure; no extra parameter. |
| Lowest confirmed pivot low | Rejected: may preserve stale/deep structure and widen downstream risk. |
| Previous of final two lows | Rejected: ignores newer non-decreasing structure. |
| Latest of final two lows | Equivalent to most recent confirmed pivot low in chronological pivot order. |
| Lowest of final two lows | Rejected: normally chooses older pivot under non-decreasing-low validity. |
| Lowest raw session low | Rejected: can be an isolated spike rather than structural demand. |
| Stop, target, R:R, or candidate optimized choice | Prohibited: circular trade-economics optimization. |

## Recommended `SUPPORT_PIVOT_SELECTION_RULE`

**CURRENT_STRUCTURAL_SUPPORT**: select the most recent PIT-confirmed pivot low contained inside the already-selected governed base. Support price is the **low** of that pivot session.

### Exact deterministic algorithm

1. Receive one already-selected valid base and its as-of-bounded confirmed pivot lows.
2. Exclude pivots outside the selected base.
3. Exclude pivots without current 3-right PIT confirmation.
4. Order remaining pivots by canonical pivot-session timestamp; immutable observation identity is only a same-session representation guard.
5. Select the latest pivot session; its low is `structural_invalidation_price`.
6. Preserve pivot session and confirmation lineage.
7. If no eligible pivot exists, return unavailable/fail closed; never invent a fallback.

No distance-from-price, percentage cushion, ATR allowance, range cap, extra pivot-count requirement, or quality score is proposed.

## PIT and selected-base boundary

A pivot at `P` is selectable only when `P+3` is visible and PIT-eligible at the requested `as_of`. An earlier historical as-of retains previously eligible support; a later-confirmed low cannot leak backward.

Support comes strictly from the selected base. A deeper older pivot outside it is ineligible, regardless of apparent stop convenience or R:R.

## Structural invalidation and current-price breach

This proposal permits only the conceptual reference:

```text
structural_invalidation_price = selected_support_pivot_low
```

It does not create `final_stop_price`: `NSE_TICK_SIZE_SOURCE` remains unresolved.

Support selection and invalidation-state evaluation are distinct. The recommended future eligibility behavior is fail closed when evaluation-session close is below selected support:

```text
evaluation close < structural_invalidation_price
  -> BASE_STRUCTURE_BROKEN / not pre-breakout eligible
```

Equality is not a breach under this proposal. This is neither exit nor trade-management behavior. `PRE_BREAKOUT_SUPPORT_BREACH_BEHAVIOR` is a separate ambiguity that a successor must state explicitly.

## Edge cases

| Case | Outcome |
| --- | --- |
| Pivot lows 400, 420 | Select 420. |
| Pivot lows 400, 420, 430 | Select 430. |
| Pivot lows 400, 420, 410 | Selected base is already invalid; support selection is not reached. |
| Final two lows 420, 420 | Select most recent 420 session; value unchanged. |
| New pivot low confirms later | Earlier as-of retains prior support; later eligible as-of selects new latest low if base remains valid. |
| Latest confirmed low outside selected base | Ineligible. |
| One pivot low | Upstream base invalid; no fallback. |

## Future lineage and human decision

Future materialization should retain selected-base start/end, support pivot session/low, support confirmation lineage, policy fingerprint, base-selection lineage, and evaluation as-of.

Before a successor resolves this field, a human must approve, reject, or modify `CURRENT_STRUCTURAL_SUPPORT` and decide whether close-below-support fail-closed eligibility belongs in the same policy. Tick-size, final-stop, target, and R:R remain separate decisions.
