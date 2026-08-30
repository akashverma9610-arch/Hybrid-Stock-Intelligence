# Pre-Breakout Entry Price and Execution Price Rule Proposal

**Status: PROPOSED — NOT APPROVED — NOT IMPLEMENTED — NOT SELECTED — NOT ACTIVE.**

This is a governance proposal only. It does not alter selected
`pre-breakout-policy-v1` / `v1.2-draft`
(`c297513b6edd2da8e85dc5ceebd31c882527b8165118e964531c93d6dfdb5aef`),
create a successor, materialize an entry, create a candidate or signal, or
perform a paper/live execution.

## Audit of existing concepts

| Concept | Classification | Evidence and boundary |
| --- | --- | --- |
| Resistance / breakout trigger | Explicitly governed for Pre-Breakout | v1.2 defines selected base top as resistance and trigger, with no buffer. |
| Structural support, stop, target, and minimum 3R | Explicitly governed for Pre-Breakout | Current support minus one tick; one base-height target; 3R minimum. |
| Entry reference / planned entry / maximum entry | Undefined for Pre-Breakout | v1.2 has no entry field or semantic. |
| Legacy `structural_resistance` R:R input | Implementation assumption | The prior candidate engine calculates R:R from caller-supplied resistance. It is not selected-v1.2 entry governance. |
| `TradePlan.entry_price` and entry zones | Reusable execution infrastructure | Generic trade plans retain a planned price/zone and trigger conditions, but must not be inherited automatically. |
| `EntryType` (`AGGRESSIVE`, `CONFIRMATION`, `PULLBACK_RETEST`) | Generic/unrelated | It provides a vocabulary only; no Pre-Breakout mapping is governed. |
| Trigger observation and historical timing | Reusable execution infrastructure | Trigger observation, timing eligibility, and fill price are already distinct in the historical path. |
| Actual/paper fill, gaps, slippage, and costs | Reusable execution infrastructure | Paper execution can model timing-approved fills, gaps, slippage, and costs; it is not an authority for a Pre-Breakout entry rule. |
| Six-Gate friction and intended tranche scaling | Generic/unrelated | Friction is a later execution/gate concern; tranche wording does not govern a Pre-Breakout tranche or weighted-entry rule. |

## Required model: multi-stage entry semantics

**`MULTI_STAGE_ENTRY_MODEL_REQUIRED`.** One `ENTRY_PRICE` field cannot honestly
represent setup valuation, an economic ceiling, and a later observed fill.

The proposed concepts are deliberately separate:

1. **Entry reference price** — factual EOD price used to evaluate a stored
   setup's economics.
2. **Maximum acceptable entry price** — a mathematical ceiling derived from
   already governed stop, target, and minimum R:R.
3. **Actual execution/fill price** — a later observed or simulated price, never
   presumed to equal the reference price.
4. **Breakout confirmation trigger** — selected base-top resistance, retained
   as confirmation rather than the initial fill price.

## Proposed entry-reference rule

### `PRE_BREAKOUT_EOD_REFERENCE_ENTRY`

For a current stored EOD scan:

```text
entry_reference_price = canonical close of the evaluation session
breakout_confirmation_trigger = selected_base_top
```

The reference close is deterministic, present in the governed materializer,
and point-in-time available when the EOD setup is observed. It is independent
of the R:R ceiling; the system does not search for a price that passes 3R.

It is **not** an actual fill. The close has already occurred when the stored
scan is evaluated, and the next executable price can gap or otherwise differ.
Current live price and next-session open are not valid historical EOD reference
prices: the former is continuously changing and the latter is future data at
the original decision timestamp.

The proposal requires, for an economically eligible pre-breakout setup:

```text
final_stop < entry_reference_price < breakout_confirmation_trigger
entry_reference_price <= maximum_acceptable_entry_price
```

Strict `< trigger` is required. Equality means the factual close is already at
the confirmation level, not a pre-breakout initial-entry reference. The base
may remain structurally valid, but entry status should be
`PRE_BREAKOUT_ENTRY_NOT_AVAILABLE` rather than silently reclassifying it as an
entry at the trigger.

If the reference is at or below stop, use `ENTRY_BELOW_OR_AT_STOP`. If it is
above stop but at or below structural support, use
`ENTRY_AT_OR_BELOW_STRUCTURAL_SUPPORT`. Both fail closed; non-positive risk is
not favourable economics.

## Maximum acceptable entry rule

Let `T` be selected base top/trigger, `S` current structural support, and `k`
the governed tick. The retained policy gives:

```text
stop   = S - k
target = 2T - S
risk   = E - S + k
reward = 2T - S - E
```

For the retained minimum R:R of 3:

```text
(2T - S - E) / (E - S + k) >= 3
E <= (2T + 2S - 3k) / 4
```

Proposed name:

```text
PRE_BREAKOUT_MAX_ENTRY_RULE
maximum_acceptable_entry_price = (2T + 2S - 3k) / 4
```

This is an **economic ceiling**, not a synthetic planned entry. Setting entry
equal to this value merely to produce exactly 3R would be circular and is
prohibited. A factual independent reference is tested against the ceiling.

## Execution and gap boundary

A later paper/execution layer may determine an actual executable/fill price,
but must revalidate:

```text
actual_execution_price <= maximum_acceptable_entry_price
```

before creating a trade. If a next-session price gaps above the ceiling, the
principle is **do not chase**: execution eligibility fails as
`PRE_BREAKOUT_EXECUTION_PRICE_ABOVE_MAXIMUM`, while the stored structural setup
may remain informative. This is a future `PRE_BREAKOUT_EXECUTION_PRICE_RULE`,
not an instruction to manufacture a fill or to change structural inputs.

Setup-level R:R remains raw reference-price economics. Existing execution
feasibility/gate infrastructure owns spread, slippage, impact, fees, taxes,
and actual-fill treatment. No duplicate friction formula is proposed. If 3R is
later required *net* of friction, a distinct governed net-R:R integration is
required.

## Tick-grid finding

Canonical EOD close is an observed exchange price. The mathematical ceiling
need not be on tick grid. No rounding is permitted by this proposal.

For example, with a ceiling of `474.9625` and a `0.05` tick, `474.95` is
eligible while `475.00` is not. Turning the ceiling into a displayed/executable
price by flooring it would require a separate approved
`MAX_EXECUTABLE_ENTRY_GRID_RULE` (for example, an explicit
`FLOOR_TO_VALID_TICK` semantic). Until then, actual execution must simply be a
valid exchange price no greater than the unrounded ceiling.

## Worked evidence matrix

For `T=500`, `S=450`, `k=0.05`:

```text
stop = 449.95
target = 550
maximum acceptable entry = 474.9625
```

| Factual/conceptual E | Risk | Reward | R:R | Relation to trigger | 3R result |
| ---: | ---: | ---: | ---: | --- | --- |
| 470 | 20.05 | 80 | 3.9900249377 | pre-breakout | PASS |
| 474.95 | 25.00 | 75.05 | 3.002 | pre-breakout; grid-valid at 0.05 | PASS |
| 474.9625 | 25.0125 | 75.0375 | 3 | conceptual ceiling; not grid-valid at 0.05 | PASS exactly |
| 475 | 25.05 | 75 | 2.9940119760 | pre-breakout | `ENTRY_RR_FAIL` |
| 480 | 30.05 | 70 | 2.3294509151 | pre-breakout | `ENTRY_RR_FAIL` |
| 500 | 50.05 | 50 | 0.9990009990 | at trigger; not pre-breakout | `PRE_BREAKOUT_ENTRY_NOT_AVAILABLE` and R:R fail |

## Breakout confirmation after early entry

Resistance remains a breakout-confirmation/validation level after an early
entry; it is not the initial fill price. A later breakout may strengthen the
thesis, while a close below support invalidates it. This proposal creates no
add-on, tranche, signal, or management action. A staged initial entry plus
breakout add-on remains a future optional strategy variant requiring its own
allocation, timing, and per-tranche/weighted-R:R governance.

## Rejected or deferred sources

| Source | Result |
| --- | --- |
| Evaluation-session canonical close | Recommended as factual setup reference only. |
| Latest pivot low plus arbitrary offset | Rejected: unsupported offset and circular structural manipulation risk. |
| Base midpoint | Deferred/rejected: no governed reason to make it an entry. |
| Anchored VWAP | Deferred: not a selected-policy source or availability contract. |
| Maximum 3R price as entry | Rejected: target-derived circular synthetic entry. |
| Discretionary entry zone | Rejected: no deterministic bounds or PIT contract. |
| Next open/current live quote | Rejected for EOD setup reference; may only be considered by future execution semantics. |

## Policy-conflict resolution path

The current `POLICY_GEOMETRY_CONFLICT` is correct because v1.2 has no entry
semantic and its materializer uses trigger as the only available R:R basis. A
future successor with both approved rules above can calculate R:R from the
factual `entry_reference_price`, leaving trigger, stop, target, and the 3R
threshold unchanged. It would return `ENTRY_RR_FAIL` where a factual reference
is above the ceiling, rather than treating every structure as a trigger-entry
conflict.

## Human decisions required

Before any successor or implementation, human governance must approve, reject,
or modify all of the following:

1. whether canonical evaluation-session close is the initial-entry reference;
2. strict `entry_reference < trigger` and the named fail-closed states;
3. the derived maximum-entry ceiling as an acceptance constraint, not an entry;
4. the actual-execution revalidation rule and do-not-chase behavior;
5. whether a tick-floor rule is needed for any future executable maximum-entry
   representation; and
6. whether future staged-entry semantics are in scope (they are not proposed
   here).

## Non-effects

- Proposal not approved; no successor policy draft exists.
- No selected policy, approval, selection, fingerprint, or governance state is
  mutated.
- No materializer, candidate, signal, paper trade, activation, or promotion is
  changed.
- No provider or network request occurs.
