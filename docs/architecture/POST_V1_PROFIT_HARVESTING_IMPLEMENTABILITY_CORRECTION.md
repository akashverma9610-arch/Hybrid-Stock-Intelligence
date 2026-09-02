# Post-V1 Profit-Harvesting Review — Implementability Correction

**Status: `POLICY_CORRECTION_REQUIRED / DOCUMENTATION_ONLY / IMPLEMENTATION_NOT_AUTHORIZED / NOT_ACTIVE`.**

This correction applies to the Profit-Harvesting section of
`POST_V1_POLICY_RESEARCH_PACK.md`. It does not alter Core V1, the implemented
Sell/Risk Review Policy, or any strategy activation status.

## Finding

The research pack supplies useful research-shadow *candidate grids*, but it
does not yet define a complete deterministic input and classification contract
for a Profit-Harvesting evaluator. A candidate grid is not an approved rule
selection. Implementing an evaluator that emits `MONITOR_PROFIT`,
`PRIORITY_PROFIT_REVIEW`, or `THESIS_REALIZATION_REVIEW` would therefore
invent at least one policy decision.

The initial instrument-only scope correctly excludes concentration, purchase
price, unrealized gain, tax, quantity, portfolio replacement, and allocation.
Those concepts remain `NOT_EVALUATED`; no portfolio reader is authorized.

## Deterministic-semantics audit

| Domain | Existing exact rule or candidate | Missing implementation-critical definition | Frozen-Core feasibility | Required outcome today |
| --- | --- | --- | --- | --- |
| Valuation extension | Requires an approved sector-specific method, price, denominator, peer/historical universe, and scope. | Method family, comparable universe, lookback, currency/unit, consolidation rule, band, freshness, conflict handling, and status mapping. | Valuation/scenario evidence exists, but no approved sector valuation contract or complete PIT peer history. | `PROFIT_REVIEW_UNAVAILABLE` only; no positive classification. |
| Price extension / euphoria | Candidate excess return: `stock total-return - NIFTY500 total-return` over `{20,60,120}` sessions and peer percentiles `{80,90,95}`. | Core performance benchmark contract is `PRICE_RETURN unless supplied total-return series`; no approved total-return source, PIT peer-universe snapshot, corporate-action/return normalization, selected grid combination, confirmation, persistence, freshness, or output mapping. | Historical bars and Market Extremes context are reusable; the stated total-return and PIT-peer contracts are not. | No evaluator or implied price-extension classification. |
| Milestone/catalyst realization | Requires approved family milestone and verified primary completion/correction lifecycle. | No approved family milestone schema, completion states, cancellation/supersession semantics, or mapping to a Profit Review status. | External intelligence lineage exists; family contract does not. | `PROFIT_REVIEW_UNAVAILABLE`. |
| Forward reward/risk / improvement priced in | Requires approved valuation/upside and structural-risk methods. | Forecast, remaining-upside, risk denominator, horizon, exceptional-item, and sector treatment. | No approved inputs/calculation. | `PROFIT_REVIEW_UNAVAILABLE`. |
| Partial / complete realization | Requires thesis target/milestone and portfolio authority. | Target definition and any non-action interpretation; portfolio authority is expressly out of scope. | Not authorized. | `NOT_EVALUATED` / `PROFIT_REVIEW_UNAVAILABLE`. |
| Freshness, confirmation, persistence, resolution | Evidence must align at `as_of`; conflict maps to `CONFLICTED_PROFIT_REVIEW`; no universal duration/count is selected. | Per-source freshness windows, confirmation count, persistence count, resolution/supersession transition, and no-evidence versus unavailable distinction. | Canonical timestamps/lineage are reusable; policy values are not selected. | No positive classification; conflict can be descriptive only after a typed input contract is approved. |
| Evidence insufficiency / conflict | Missing, stale, conflicted, unreliable, non-comparable, or unapproved evidence fails closed. | A complete typed required-input set and canonical conflict vocabulary for this family. | Availability/reliability conventions are reusable. | Explicit blocker only. |

## Non-negotiable correction

No initial evaluator is authorized merely to return an unavailable result. A
useful initial evaluator must be able to derive at least one descriptive,
non-executable review state from an approved, PIT-complete canonical contract
without selecting a grid, default, duration, or interpretation at runtime.

`MarketExtremes` may be reused as descriptive evidence, but its euphoria
context must not be relabelled as a Profit-Harvesting result without an
approved cross-policy mapping. Existing euphoria context is not a top, sell,
or profit-taking instruction.

## Required amendment before implementation

The human approval must choose one of the following bounded paths.

1. **Price-return shadow path.** Amend the candidate formula to use explicitly
   defined provider-versioned *price returns* for both instrument and NIFTY
   500, or authorize a canonical total-return data contract. Define the exact
   PIT peer universe, corporate-action basis, session completeness rule,
   selected `{window, percentile}` grid treatment, minimum peer count,
   missing/zero-base behavior, confirmation/persistence/freshness rules, and
   deterministic mapping to `MONITOR_PROFIT` or
   `PRIORITY_PROFIT_REVIEW`. This is research-shadow only and remains
   `WATCH_ONLY / NON_EXECUTABLE`.
2. **Market-Extremes descriptive path.** Define an exact, versioned mapping
   from an existing canonical Market Extremes state and its lineage to one
   descriptive Profit Review status. The mapping must define all required
   source states, conflicts, PIT/freshness, supersession, and resolution.
   It cannot infer a price target, action, or portfolio outcome.
3. **Defer evaluation.** Retain the researched proposal, collect PIT-complete
   return/peer and milestone data, and implement no Profit-Harvesting
   evaluator until a path above is approved.

All paths leave valuation extension, milestone/catalyst realization, forward
reward/risk, fundamental-improvement-priced-in, partial/complete realization,
concentration, friction/tax/liquidity, and every portfolio-dependent concept
unavailable until their separately governed contracts are approved.

## Selected Market-Extremes mapping — canonical-contract audit

The selected product-policy intent is
`MARKET_EXTREMES_EUPHORIA_MAPPING_APPROVED / RESEARCH_SHADOW_V1 / WATCH_ONLY /
NON_EXECUTABLE`. It is approved only as a proposed mapping, not as an
implementation authorization, because the currently implemented Market
Extremes contract cannot faithfully represent all required input states.

| Requested Profit-Harvesting mapping | Actual Core V1 enum / field | Exact finding | Implementation disposition |
| --- | --- | --- | --- |
| Confirmed upside-euphoria → `MONITOR_PROFIT` | `UpsideExcessState.EUPHORIA` | The state exists. However, `top_confirmed` is not an euphoria-confirmation flag: it is true only when structural breakdown forces `UpsideExcessState.BREAKDOWN`. Euphoria assessments explicitly carry `EUPHORIA_IS_NOT_TOP_CONFIRMATION`. | Cannot use `top_confirmed` to create the requested mapping; no replacement interpretation is authorized. |
| Neutral / downside / no upside euphoria → `NO_PROFIT_REVIEW_EVIDENCE` | `NORMAL`, `OPTIMISM`, `CROWDING`, `SPECULATION`, `DISTRIBUTION`, `BREAKDOWN` | These exact `UpsideExcessState` values exist. They do not encode freshness, conflict, verification, or an instrument-specific Profit-Harvesting domain. | A future wrapper may map them only after the same typed input envelope exists. |
| Conflicted / ambiguous extremes → `CONFLICTED_PROFIT_REVIEW` | No `UpsideExcessState` or assessment field | `UpsideExcessAssessment` has supporting, contradicting, unavailable factors and warnings, but no typed conflict status, conflict lineage, or deterministic conflict semantics. | Fail closed; do not infer conflict from a warning or factor list. |
| Unavailable / stale / temporally invalid / unverifiable → `PROFIT_REVIEW_UNAVAILABLE` | Query-level `MARKET_EXTREMES_UNAVAILABLE` only | The raw assessment has `assessed_at`, `data_as_of`, `evidence_ids`, and `provenance_ids`, but no source availability, staleness, verification, or tamper-validation state. | Fail closed; query absence is not a typed evidence contract. |
| PIT-valid immutable lineage | `CoreApiSnapshotFamily.UPSIDE_EXCESS_ASSESSMENT` and generic `CoreApiSnapshot` | The family exists, but its generic wrapper does not validate its fingerprint against the payload. `RepositoryMarketExtremesQueryService` selects the final listed payload rather than performing canonical as-of selection. | Not a stable, tamper-evident PIT source for this evaluator. |

The required mapping cannot be implemented by adding a local interpretation of
warnings, assessment order, snapshot creation time, or factor lists. That
would create a duplicate Market-Extremes availability/conflict policy and
would violate the selected no-invention boundary.

### Required canonical-contract prerequisite

Before the mapping can resume, a separate approved Core-adjacent contract must
provide an immutable, fingerprint-verified, as-of-selected Market-Extremes
projection with exact canonical states for `READY`, `CONFLICTED`,
`UNAVAILABLE`, `STALE`, `TEMPORALLY_INVALID`, and `UNVERIFIABLE`; preserved
evidence/provenance lineage; and a defined relation between the existing
`EUPHORIA` state and any confirmation vocabulary. This is not authorized in
the Profit-Harvesting slice.

That prerequisite is now specified, but not activated, in
[`POST_V1_MARKET_EXTREMES_ASSURANCE_PROJECTION.md`](POST_V1_MARKET_EXTREMES_ASSURANCE_PROJECTION.md).
It intentionally remains separate from every Profit-Harvesting evaluator.

## Approved first evaluator: assurance euphoria mapping

**Status:** `APPROVED_FOR_IMPLEMENTATION / EUPHORIA_MAPPING_ONLY / WATCH_ONLY /
NON_EXECUTABLE / NOT_ACTIVE`.

`profit-harvesting-review-policy / market-extremes-euphoria-shadow-v1` may
consume only a verified Market-Extremes Assurance Projection. The exact,
read-only mapping is:

| Assurance state | Core regime | Profit Review status |
| --- | --- | --- |
| `READY` | `EUPHORIA` | `MONITOR_PROFIT` |
| `READY` | any other valid regime | `NO_PROFIT_REVIEW_EVIDENCE` |
| `CONFLICTED` | any or none | `CONFLICTED_PROFIT_REVIEW` |
| `UNAVAILABLE`, `STALE`, `TEMPORALLY_INVALID`, `UNVERIFIABLE` | any or none | `PROFIT_REVIEW_UNAVAILABLE` |

`EUPHORIA` is evidence for this descriptive review only. It is not “confirmed
euphoria,” a top, an exit, a target, or an instruction to book profit.
`top_confirmed`, warnings, and factors are not interpreted. Assurance lineage
and blocker codes are preserved unchanged.

Valuation, return/percentile, volume, milestone, catalyst, reward/risk,
fundamental-priced-in, realization, purchase-price, concentration, sizing,
quantity, tax, slippage, friction, replacement, and rotation domains remain
explicitly unavailable or not evaluated.

## Exact resume statement

> Approve one named Profit-Harvesting implementation path in
> `POST_V1_PROFIT_HARVESTING_IMPLEMENTABILITY_CORRECTION.md`, including its
> versioned canonical input contract, PIT return/peer or Market-Extremes
> basis, selected candidate-grid semantics, output-status mapping, freshness,
> confirmation, persistence, conflict, supersession, and resolution rules.
> Authorize only that isolated deterministic Watch-only/non-executable
> evaluator. No portfolio access or mutation, capital authorization,
> BUY/SELL/ADD/TRIM/EXIT/ROTATE output, persistence, API/UI, broker/order
> authority, or performance claim is approved.
