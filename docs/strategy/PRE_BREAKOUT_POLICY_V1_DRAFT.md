# Pre-Breakout Policy V1 — Draft Requiring Human Approval

Status: `DRAFT_REQUIRES_HUMAN_APPROVAL`. **No production strategy behavior changed in U12.**

## Retain existing rules

- BBW percentile <= 10, trailing 120 sessions.
- Delivery percentage > 60; volume dry-up < 50% of SMA20.
- Price is 3–6% below the 52-week high; RSI14 is 55–65; minimum R:R is 3.

## Proposed rules requiring individual approval

1. ATR: recommend ATR14 below the mean of the preceding five ATR14 values. Alternatives: ATR14 below its value five sessions ago; majority decline across five sessions.
2. Base: recommend 20–60 sessions, confirmed pivots, and a highest confirmed base boundary as resistance.
3. Trigger: recommend resistance only, with no implicit buffer.
4. Stop: structural invalidation below base support; any buffer must be explicitly approved. Never force a percentage stop.
5. Target: measured move equal to base height. If resulting R:R is below 3, reject; never reverse-engineer a target.

Each proposal requires historical backtest, walk-forward, OOS, and paper-trading validation after explicit human approval. Generic `TradeRules` defaults are not inherited.

## Human checklist

- [ ] RETAIN existing BBW, delivery, volume, 52-week, RSI, and 3R thresholds.
- [ ] APPROVE / REJECT / MODIFY ATR contraction rule.
- [ ] APPROVE / REJECT / MODIFY base and resistance rule.
- [ ] APPROVE / REJECT / MODIFY trigger, stop, and target rules.
- [ ] Confirm the required validation sequence.

## V1.1 successor draft — consolidation-volume statistic only

`pre-breakout-policy-v1` / `v1.1-draft` is a separate immutable successor
draft. It is not approved, selected, active, promoted, or consumed by the
current stored-data materializer.

It resolves only `CONSOLIDATION_VOLUME_STATISTIC` as: evaluation-session volume
is strictly less than 50% of the SMA of the preceding 20 valid canonical
session volumes. The evaluation session is excluded from that reference; fewer
than 20 prior valid observations or a missing current volume is unavailable,
not a pass. Exactly 50% fails.

This is a deterministic, PIT-safe policy-definition rationale: it retains the
proposed `<50% of SMA20` threshold, removes self-reference, and does not claim
that volume alone establishes a consolidation. It is not backtest proof.
`BASE_WINDOW_SELECTION_RULE`, `SUPPORT_PIVOT_SELECTION_RULE`, and
`NSE_TICK_SIZE_SOURCE` remain unresolved in this successor.
