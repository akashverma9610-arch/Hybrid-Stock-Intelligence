# Pre-Breakout Entry, Trigger, and R:R Semantics Audit

**Status: AUDIT + GOVERNANCE PROPOSAL ONLY — NOT APPROVED — NOT IMPLEMENTED — NOT ACTIVE.**

This document does not modify `pre-breakout-policy-v1` / `v1.2-draft`, its
selection, any materializer, a candidate, signal, trade, order, or provider
integration. The selected policy remains fingerprint
`c297513b6edd2da8e85dc5ceebd31c882527b8165118e964531c93d6dfdb5aef`.

## Evidence audit

| Artifact | Classification | Finding |
| --- | --- | --- |
| Selected v1.2 `ResistanceTriggerRule` | Explicitly governed | Resistance is the selected governed base top; trigger is resistance with zero buffer. It does not define an entry price. |
| Selected v1.2 stop/target/R:R rules | Explicitly governed | Stop is current structural support minus one governed tick; target is one base-height measured move; formula labels refer to `TRIGGER`, not `ENTRY`. |
| `PreBreakoutStructuralSuccessorDraft` | Explicitly governed omission | It has no `entry_price`, entry-zone, fill, confirmation-to-entry, or tranche field. |
| `docs/strategy/PRE_BREAKOUT_POLICY_V1_DRAFT.md` | Historical intent only | It says price is below the 52-week high, recommends resistance as trigger, and rejects a sub-3R result. It does not state that a trade enters at the trigger. |
| `app/strategies/pre_breakout/service.py` | Implementation assumption | The legacy candidate engine supplies `structural_resistance` to its R:R helper. It accepts caller-supplied structural levels and contains no governed entry materialization. It is not proof that selected v1.2 means `entry = trigger`. |
| `docs/RISK_REWARD.md` | Existing general contract | Risk and reward are based on `entry`, stop, and target; required entry is never fabricated. |
| `docs/TRADE_STRUCTURE.md` and `docs/TRADE_PLAN_ORCHESTRATION.md` | Existing generic, not inherited | They distinguish aggressive, confirmation, and pullback/retest entries from machine-testable trigger conditions. Their generic semantics are not silently imported into Pre-Breakout. |
| `docs/EXECUTION_GATES.md` | Historical intent only | It mentions tranche scaling as an intended execution-gate policy, but it supplies no Pre-Breakout tranche or weighted-entry rule. |

## Answer: is breakout trigger the entry price?

**C — UNDEFINED.** The selected policy explicitly governs the breakout trigger,
but does not govern a `PRE_BREAKOUT_ENTRY_PRICE_RULE`. U13B-7A used trigger as
the R:R basis only because the selected target rule names `TARGET_MINUS_TRIGGER`
and `TRIGGER_MINUS_FINAL_STOP`; that is the exact current governed geometry, not
evidence that an executable entry must occur at trigger.

## Original strategy execution intent

The retained Pre-Breakout material says discovery happens while price is below
the relevant high/resistance, and it retains a breakout-confirmation concept.
That supports **setup discovery before breakout with a later confirmation
condition**. It does **not** establish either of these execution rules:

- entry on the breakout; or
- entry before the breakout.

Accordingly, the original execution model is **not sufficiently specified to
choose A, B, or C as an entry model**. The missing rule is
`PRE_BREAKOUT_ENTRY_PRICE_RULE`; a related future rule must state whether
breakout is confirmation, an entry event, or both.

## Independent geometry proof

Let:

```text
T = selected base top / trigger
S = current structural support
k = positive governed tick
stop = S - k
target = T + (T - S) = 2T - S
```

For breakout entry (`E = T`):

```text
reward = target - T = T - S
risk   = T - stop = T - S + k
R:R    = (T - S) / (T - S + k) < 1
```

Therefore the retained one-base-height target, support-minus-tick stop, and
minimum R:R of 3 are internally contradictory if `entry = trigger`. The
U13B-7A `POLICY_GEOMETRY_CONFLICT` is correct and must remain fail-closed.

For arbitrary planned entry `E`:

```text
risk   = E - (S - k) = E - S + k
reward = (2T - S) - E
```

With positive risk, `R:R >= 3` requires:

```text
(2T - S - E) / (E - S + k) >= 3
E <= (2T + 2S - 3k) / 4
```

For `T=500`, `S=450`, `k=0.05`, the highest entry consistent with exactly 3R
is **474.9625**. At that boundary, risk is `25.0125`, reward is `75.0375`, and
R:R is exactly `3`. This is materially below the trigger of `500`; it is not a
permitted entry rule.

## Alternatives considered

### A. Breakout entry

`entry = trigger = T` is not explicitly governed. If a human later confirms it
as the intended model, the retained target, stop, or minimum-R:R rule must be
changed by separate governance. This audit does not choose a change.

### B. Pre-breakout entry

An entry below resistance can make 3R mathematically feasible while preserving
the existing stop and one-height target. Candidate sources are all **undefined
for Pre-Breakout**: evaluation close, scan-time market price, a governed entry
zone, anchored VWAP, base midpoint, and latest pullback structure. None may be
adopted from generic trade diagnostics or current market data without a new
governance decision.

This would require distinct PIT-safe concepts for setup discovery, planned
entry, breakout confirmation, invalidation before trigger, and execution/
friction treatment.

### C. Staged entry

The generic execution-gate documentation contains intended tranche scaling, and
the generic trade-plan model supports multiple entry types. Neither governs a
Pre-Breakout initial tranche, confirmation tranche, allocation weights, or
whether R:R is per tranche or weighted-average. Treat staged entry as a future
strategy variant, not as a correction to v1.2.

### D. Change the target

With breakout entry and a target `T + m(T-S)`, minimum 3R requires:

```text
m >= 3 * (T - S + k) / (T - S)
```

For the example, `m >= 3.003`; a one-height target has `m=1`. Selecting a
larger multiplier merely to pass 3R would violate the retained prohibition on
moving the target to manufacture R:R. No multiplier is proposed.

### E. Change the stop

With breakout entry and one-height target, 3R requires:

```text
T - stop <= (T - S) / 3
stop >= T - (T - S) / 3
```

For the example, the stop must be at least `483.333333…`, rather than the
governed `449.95`. That is incompatible with the approved current-structural-
support-minus-one-tick rule unless a human changes the structural stop policy.

### F. Lower the R:R threshold

For breakout entry, R:R approaches but never reaches 1 with a positive tick.
Lowering the threshold below 1 would not be a minor repair of the retained 3R
strategy design; it would be a substantive strategy change. It is not proposed.

## Recommended governance direction

Preserve the structural stop, measured-move target, and 3R requirement while
first resolving the missing entry semantic. The recommended next task is a
**governance-only proposal for `PRE_BREAKOUT_ENTRY_PRICE_RULE`**, not a
successor draft or implementation. It must specify:

1. exact entry price or deterministic price-zone source;
2. source availability and explicit `as_of`/PIT rules;
3. whether entry is allowed before breakout;
4. whether the trigger remains confirmation, an entry event, or both;
5. invalidation between discovery and trigger;
6. R:R basis (planned entry versus trigger) and execution/friction semantics;
7. whether any staged-tranche semantics apply and, if so, how R:R is measured.

Only after human approval of that rule can a successor policy be assessed. If
human review instead establishes that entry must equal trigger, a separate
proposal must explicitly reconsider target, stop, or the 3R minimum.

## Policy status finding

`unresolved_fields = ()` correctly reports no *declared* unresolved field, but
it does not prove cross-field satisfiability. The selected v1.2 semantics have
a demonstrated **`POLICY_SEMANTIC_CONFLICT`** for the trigger-as-entry R:R
interpretation. This is a conceptual status finding only; no stored policy,
approval, selection, or fingerprint is changed by this audit.

## Non-effects

- No policy mutation or successor draft was created.
- No governance approval or selection was executed.
- No materializer, scanner, candidate, signal, paper trade, promotion, or
  activation behavior changed.
- No provider or network call occurred.
