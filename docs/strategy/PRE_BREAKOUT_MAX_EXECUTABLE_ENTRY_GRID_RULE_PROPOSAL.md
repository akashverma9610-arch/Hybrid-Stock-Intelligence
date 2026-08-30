# Pre-Breakout Maximum Executable Entry Grid Rule Proposal

**Status: PROPOSED — NOT APPROVED — NOT IMPLEMENTED — NOT SELECTED — NOT ACTIVE.**

This governance proposal does not modify selected v1.2 policy, create a successor, calculate an entry, floor or round a runtime value, create a candidate/signal/trade, or access a provider.

## Problem

The human-approved maximum acceptable entry is an economic ceiling:

```text
E_max = (2T + 2S - 3k) / 4
```

It may be off the exchange tick grid. For `T=500`, `S=450`, and `k=0.05`, `E_max=474.9625`, while `474.95` and `475.00` are tick-grid prices. The system needs a deterministic way to state the greatest executable price that does not violate `actual_execution_price <= E_max`.

## Existing semantics audit

| Concern | Classification | Finding |
| --- | --- | --- |
| Tick resolution | Explicitly governed infrastructure | `TickSizeReferenceResolver` selects only PIT-eligible immutable reference evidence and fails closed on absence/conflict. |
| Grid validation | Explicitly governed infrastructure | `validate_price_on_tick_grid` requires positive finite `Decimal` values and exact `price % tick_size == 0`. It allows no epsilon, nearest rounding, floor, or ceiling. |
| Grid origin | Explicitly governed for current NSE cash contract | The existing contract uses a zero-origin modulo grid. No retained NSE cash evidence establishes a non-zero origin. |
| Price-floor/ceil/nearest helper | Undefined | No project-standard executable-price normalizer exists. |
| Broker/provider price normalization | Broker-specific/unavailable | No broker adapter price-normalization rule is an authority for strategy economics. |
| `ROUND_FLOOR` in audit reconstruction | Generic/unrelated | It floors paper quantity under `FLOOR_INTEGER`; it is not price/tick logic. |

The zero-origin rule is sufficient within the present NSE cash-only reference contract. If another exchange or instrument class with a documented non-zero grid origin is introduced, it needs a separate `EXCHANGE_PRICE_GRID_ORIGIN_RULE`; none is invented here.

## Alternatives

| Alternative | Result |
| --- | --- |
| `EXACT_GRID_ONLY` | Reject off-grid ceilings entirely. Safe but unnecessarily discards lower valid prices that remain under the economic ceiling. |
| `FLOOR_TO_VALID_TICK` | Recommended for human approval: conservatively returns the greatest zero-origin grid price not exceeding the ceiling. |
| Nearest tick | Rejected: can round upward and violate 3R. |
| Ceiling to tick | Rejected: directly raises the permitted price above the economic ceiling. |
| Broker-normalized price | Rejected: provider-dependent, non-deterministic strategy semantics. |

## Recommended outcome: A — `CONSERVATIVE_TICK_FLOOR`

Proposed rule name: `MAX_EXECUTABLE_ENTRY_GRID_RULE`.

```text
maximum_executable_entry_price =
    greatest valid price on the governed tick grid
    where price <= E_max
```

Conceptually, for positive finite `Decimal` values only:

```text
units = floor(E_max / tick_size)
maximum_executable_entry_price = units * tick_size
```

A future implementation must use exact `Decimal` arithmetic, for example an explicit `ROUND_FLOOR` integral conversion after validation. It must never use `float`, `round`, epsilon tolerance, banker’s rounding, nearest-tick behavior, or an upward ceiling. This document does not implement that operation.

The result remains a ceiling. It is not a limit order, recommended buy price, synthetic entry, or assumed fill. A later observed/paper/live execution price must independently satisfy:

```text
final_stop < actual_execution_price < breakout_confirmation_trigger
actual_execution_price <= maximum_executable_entry_price
actual_execution_price is exactly on the governed tick grid
```

## Boundary behavior

- If `E_max` is already grid-aligned, retain it exactly; do not subtract a tick.
- If the floored value is at or below final stop, return `NO_VALID_PRE_BREAKOUT_ENTRY_PRICE`.
- If it is at or above trigger, return `PRE_BREAKOUT_ENTRY_NOT_AVAILABLE`; do not substitute breakout entry. Under valid current geometry this should be unreachable, but the guard remains required for invalid or future semantics.
- If tick reference data is absent, conflicting, invalid, or the ceiling is not finite, fail closed using the existing relevant status; no price is inferred.
- If a later executable/fill price is greater than the ceiling, return `ENTRY_PRICE_TOO_HIGH` / `DO_NOT_CHASE`. Do not change target, stop, or R:R.

## R:R conservatism proof

With fixed target and stop:

```text
R(E) = (target - E) / (E - stop)
dR/dE = -(target - stop) / (E - stop)^2 < 0
```

For valid `E > stop` and `target > stop`, R:R decreases as entry rises. Therefore a floored executable price less than or equal to `E_max` has R:R at least the R:R at `E_max`; the floor cannot weaken the retained gross 3R condition.

## Exact Decimal examples

| Case | Inputs | Proposed result | Outcome |
| --- | --- | --- | --- |
| A | `E_max=474.9625`, `k=0.05` | `474.95` | Valid ceiling; R:R is `3.002`. |
| B | `E_max=474.95`, `k=0.05` | `474.95` | Already on grid; no decrement. |
| C | `E_max=474.951`, `k=0.05` | `474.95` | Off-grid conservative floor. |
| D | `E_max=0.03`, `k=0.05`, `stop=0.01` | `0.00` | `NO_VALID_PRE_BREAKOUT_ENTRY_PRICE`. |
| E | floor result equals stop | no usable result | `NO_VALID_PRE_BREAKOUT_ENTRY_PRICE`. |
| F | floor result equals trigger | no usable result | `PRE_BREAKOUT_ENTRY_NOT_AVAILABLE`. |

Cases E and F are explicit fail-closed guards. In valid present one-height geometry, positive tick normally makes the derived ceiling strictly below trigger, but no runtime may rely on that fact to omit the check.

## Friction boundary

`E_max` is derived from the current gross-price R:R semantics. Existing execution/gate infrastructure separately owns spread, slippage, impact, fees, taxes, and actual fills. No friction adjustment is introduced here. If human governance later requires net-of-friction 3R, it must define a separate `FRICTION_ADJUSTED_MAX_ENTRY_RULE`; the gross ceiling cannot be silently reinterpreted as net economics.

## Human decision required

Approve, reject, or modify Outcome A: `CONSERVATIVE_TICK_FLOOR` as a future `MAX_EXECUTABLE_ENTRY_GRID_RULE`, including its strict stop/trigger boundaries, zero-origin NSE-cash scope, and do-not-chase execution constraint. This decision does not approve an entry materializer, an order type, or a successor policy.

## Non-effects

- Proposal not approved; no successor policy draft exists.
- No policy, governance, materializer, candidate, signal, trade, activation, promotion, broker, or provider behavior changed.
- No provider or network request occurred.
