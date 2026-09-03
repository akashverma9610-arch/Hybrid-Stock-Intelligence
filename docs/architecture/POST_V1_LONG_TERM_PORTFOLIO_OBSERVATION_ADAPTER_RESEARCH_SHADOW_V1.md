# Long-Term Portfolio Observation Adapter — Research Shadow V1

**Status: `APPROVED_FOR_IMPLEMENTATION / RESEARCH_SHADOW_V1 / WATCH_ONLY / NON_EXECUTABLE / NOT_PRODUCT_ACTIVE`.**

## Purpose and boundary

This is a pure, deterministic association boundary between the existing immutable
`PortfolioSnapshot` contract and existing Long-Term Thesis Invalidation Lifecycle
research-shadow receipts. It answers only: for each canonically identified
holding in a snapshot, which compatible long-term research receipt can be
associated as of that same portfolio point in time?

It is not a holding scorer, holding review, sell-side evaluator, harvesting
policy, rotation engine, allocation optimiser, or execution interface. It does
not calculate value, P&L, return, price, quality, valuation, thesis strength,
priority, or recommendation. In particular, an observation state is never BUY,
SELL, HOLD, ADD, TRIM, EXIT, ROTATE, a target allocation, a weakest-holding
label, or a capital-authorisation result.

All output is fixed to `WATCH_ONLY / NON_EXECUTABLE / RESEARCH_SHADOW_V1`.
The adapter creates no persistence, API, UI, provider, broker, order, setup,
Six-Gates, Decision Score, paper-trade, or portfolio mutation behaviour.

## Canonical inputs

The adapter accepts only an existing immutable
`app.portfolio.models.PortfolioSnapshot` and zero or more already-created,
verified `LongTermThesisInvalidationResearchShadow` receipts.

The snapshot remains the only portfolio fact source. It establishes its
identity, portfolio identity, UTC-normalized `as_of_timestamp`, retained
holding identities, and existing `CashPosition` state. The adapter does not
recreate a portfolio, accept a screenshot/chat import, or synthesize a holding
from a name or ticker.

The lifecycle receipt remains the only long-term research/lifecycle source. The
adapter never recomputes Compounder, Inflection, Policy Transmission, or
Lifecycle conclusions. Receipt identity, fingerprint, source lifecycle as-of,
state, and descriptive business-branch provenance are preserved only when that
receipt is selected.

## Canonical association and PIT rule

1. A holding is eligible only when its existing `instrument_id` is a valid
   canonical identifier. No name similarity, ticker guessing, text matching,
   LLM inference, or provider lookup is permitted.
2. A verified lifecycle receipt is considered only when its canonical
   instrument identifier exactly equals the holding identifier.
3. Its lifecycle as-of must be at or before the snapshot as-of. A later
   receipt, including later evidence, earnings, policy evidence, or lifecycle
   observation, is excluded and cannot be attached to the older snapshot.
4. This repository has no approved historical lifecycle-version selector. A
   single eligible receipt can be associated; two or more distinct eligible
   receipts are an explicit `LIFECYCLE_RECEIPT_AMBIGUOUS` state. The adapter
   must not choose an arbitrary or merely latest receipt.
5. Duplicate lifecycle receipt identity/fingerprint inputs are malformed and
   rejected, rather than silently deduplicated. A tampered or unverifiable
   lifecycle input is rejected before association.

The adapter uses no current/runtime clock. UTC normalization, deterministic
sorting, stable JSON serialization, and SHA-256 identities/fingerprints make
identical canonical input reproducible.

## Per-holding observation states

| State | Meaning | Never means |
| --- | --- | --- |
| `DATA_INSUFFICIENT` | The associated lifecycle says its research evidence is insufficient. | A bad, weak, or sell-worthy holding. |
| `EVIDENCE_CONFLICTED` | The associated lifecycle preserves unresolved evidence conflict. | A sell instruction or resolved adverse fact. |
| `POLICY_DEFINITION_MISSING` | Evidence is associated but the lifecycle has no approved definition for its next research conclusion. | Weakness, thesis failure, or invalidation. |
| `NOT_APPLICABLE` | The associated receipt is not applicable, or its existing supplied business classification is unknown. | A failed company or cash-equivalent. |
| `NON_COMPARABLE` | The selected receipt explicitly retains a structurally non-comparable business branch. | A negative investment conclusion. |
| `IDENTITY_UNAVAILABLE` | The portfolio line has no valid canonical instrument identity. | A guessed company association. |
| `LIFECYCLE_RECEIPT_UNAVAILABLE` | No exact, PIT-compatible lifecycle receipt can be associated. | Negative evidence. |
| `LIFECYCLE_RECEIPT_AMBIGUOUS` | Multiple distinct PIT-compatible receipts exist without a governed selector. | A choice of the latest receipt. |

The exact lifecycle state is retained when a receipt is associated. Lifecycle
`DATA_INSUFFICIENT`, `POLICY_DEFINITION_MISSING`, and
`EVIDENCE_CONFLICTED` remain descriptive research/readiness states. Even a
future lifecycle state such as an approved invalidation state would be observed
only; it could not become a portfolio action in this adapter.

## Cash, non-equity, and comparability

Cash is a valid allocation. The adapter preserves the existing `CashState` and
records cash as `NOT_APPLICABLE` with `CASH_IS_VALID_ALLOCATION`; it never
forces an equity thesis onto cash, treats unknown cash as a thesis failure, or
uses cash to rank the portfolio.

`PortfolioHolding` does not carry an approved security-type or company-type
taxonomy. The adapter therefore does not infer one. Where the selected
lifecycle's already-supplied research shadow explicitly says
`STRUCTURALLY_NON_COMPARABLE`, it exposes `NON_COMPARABLE`; where it says
`UNKNOWN`, it exposes `NOT_APPLICABLE`. A future security taxonomy or an
approved instrument/entity resolver is required before unsupported security
types can be positively identified rather than left without an associated
receipt.

## Contract and lineage

The portfolio observation identity includes the contract version, portfolio
snapshot identity and as-of, retained holding identity, selected lifecycle
identity/fingerprint/as-of, and cash state. Its content fingerprint also
includes every output state and canonical reason. Holding observations are
sorted by holding identity and reasons are sorted by stable code. No mutable
maps or unordered collections are accepted.

The adapter validates snapshot ID, portfolio ID, aware timestamps, unique
holding IDs, source-cutoff timing, and cash timing. It preserves only snapshot
facts needed for association; it does not expose or interpret cost, value,
P&L, prices, analytics, risk, or allocation fields.

## Known gaps deliberately surfaced

- There is no governed lifecycle receipt selection/versioning rule. Multiple
  eligible receipts fail closed as ambiguous.
- There is no approved portfolio security/company-type taxonomy on
  `PortfolioHolding`; no security type is guessed.
- There is no portfolio-to-long-term product decision policy. Holding review,
  profit harvesting, sell-side, rotation, and authority remain separate future
  boundaries.

## Verification scope

Focused tests prove exact identity association, snapshot/receipt PIT exclusion,
ambiguous-version failure closure, cash handling, non-comparable/unknown branch
handling, lifecycle-state preservation, deterministic identity/serialization,
tamper rejection, immutable output, and the absence of action, portfolio
mutation, persistence, provider, API/UI, broker, order, Decision Score, or
Six-Gates dependencies.
