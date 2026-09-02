# Post-V1 Product Architecture — One Brain, Multiple Signal Windows

**Status: `APPROVED_FOR_FUTURE_IMPLEMENTATION / DOCUMENTATION_ONLY / NOT_ACTIVE`.**

## Authority and scope

This is the canonical product-layer architecture specification after the frozen
HSI Core V1 release.  It is a future implementation contract only.  It creates
no runtime model, migration, API, UI route, provider integration, strategy,
score, order authority, or portfolio mutation.

HSI Core V1 remains complete and frozen.  Its canonical Brain, evidence,
diagnostics, Decision Score, Six Gates, portfolio analysis, governance, and
read-only operational surfaces remain authoritative.  Existing Production UI
and Dev Console surfaces are internal/read-model operational interfaces; they
are **not** the completed consumer product described here.

This document complements, and does not replace, the [Brain architecture]
(brain_architecture.md), [Signal Lifecycle](../SIGNAL_LIFECYCLE.md), [Strategy
Governance](../STRATEGY_GOVERNANCE.md), and existing frontend specifications.
Where this document conflicts with an implemented Core V1 contract, Core V1
and its tested source prevail until a separately governed implementation slice
is approved.

The first approved implementation boundary is recorded in the
[P1 Watch-only `HSISignal` Foundation acceptance]
(POST_V1_HSI_SIGNAL_P1_ACTIVATION_PROPOSAL.md). It is implemented only as an
internal on-demand projection; it is Watch-only, non-executable, and does not
alter this architecture, its consumer-product status, or frozen Core V1.

The approved product scope, window vocabulary, and required fail-closed
strategy statuses are catalogued in the [Post-V1 Strategy and Signal-Window
Catalogue](POST_V1_STRATEGY_AND_SIGNAL_WINDOW_CATALOGUE.md). It does not
activate a strategy or alter this architecture's status.

The Batch 1 Event/Catalyst and Market-Red Resilience [policy
boundaries](POST_V1_BATCH_1_EVENT_CATALYST_AND_RESILIENCE_POLICY_PROPOSAL.md)
are documentation-only. Their retained-data [historical calibration research
receipt](POST_V1_BATCH_1_HISTORICAL_CALIBRATION_RESEARCH.md) found no
defensible operational parameters, so neither strategy can activate.

The Long-Term Thesis Family has a single [policy approval
pack](POST_V1_LONG_TERM_THESIS_FAMILY_POLICY_PROPOSAL.md). It identifies the
reusable Core V1 inputs and all unresolved normative definitions; it does not
implement or activate a long-term product strategy.

## One Brain, multiple signal windows

The future consumer product has one canonical Brain.  It reads the same
canonical market data, evidence, news, macro, sector, governance, and portfolio
state already owned by HSI.  It must not introduce a second Brain, duplicate
stores, parallel provider truth, or a product-specific source of truth.

Different product windows are projections over relevant evidence and explicit
policies, not separate intelligence systems:

| Signal window | Future consumer purpose | Required boundary |
| --- | --- | --- |
| Intraday / event | Time-sensitive event visibility | Requires its own freshness, session, and event policy. |
| Tactical | Short-to-medium horizon research | Uses only its approved horizon policy and evidence. |
| Positional | Multi-session opportunity context | Does not infer a trade from an archetype. |
| Investment | Longer-horizon thesis and fundamentals | Requires product-specific financial/research sufficiency. |
| Sell / risk | Invalidation and risk visibility | Remains governed analysis, not an order instruction. |
| Profit-taking | Review of potential realization conditions | Requires a separately approved policy; no automatic action. |
| Rotation | Relative replacement context | Preserves cash validity and the existing rotation hurdle. |

## Signal is not trade authorization

The future product must preserve this sequence:

`detection → classification → actionability assessment → capital authorization`

Each stage is independent and may fail closed.  A useful signal can therefore
exist when a Decision Score is incomplete, a setup is unavailable, or a
Strategy Registry entry is unavailable.  Such a signal is descriptive only.

Six Gates remain evidence-only.  They neither call a broker nor place an order,
reserve capital, mutate holdings, or convert a signal into a BUY, SELL, or
ROTATE instruction.  Existing analytical/paper-trading lifecycle semantics are
unchanged by this proposed product projection.

## Future information architecture

The future consumer product may expose the following information areas, each as
a read/query projection of the one canonical Brain:

| Area | Future role | Current status |
| --- | --- | --- |
| Home / Intelligence Command Centre | Cross-window overview, freshness, blockers, and signal summaries | `PROPOSED` |
| Deep Analysis | Instrument, evidence, thesis, diagnostic, and lineage exploration | `PARTIAL` — internal/read-model surfaces exist, consumer information architecture does not |
| Portfolio Analysis | Portfolio relevance, risk, invalidation, and governed review context | `PARTIAL` — Core analysis exists; consumer product is not implemented |
| Strategies | Registry-visible strategy availability and policy provenance | `PARTIAL` — internal P1 registry resolves only governed Pre-Breakout provenance; no consumer surface |
| Trades | Read-only analytical/paper lifecycle and controlled future review | `PARTIAL` — no consumer product or execution authority |
| Settings | Consumer-facing configuration and connection explanations | `PARTIAL` — internal settings/connections exist |
| Stocks discovery | Promotional/discovery entry point for equity intelligence | `PROPOSED` |
| Mutual Fund discovery | Promotional/discovery entry point for future MF intelligence | `UNAVAILABLE` |
| IPO discovery | Promotional/discovery entry point for future IPO intelligence | `UNAVAILABLE` |
| Other future products | Explicitly separate product discovery areas | `NOT_ACTIVE` |

`IMPLEMENTED` means a tested Core V1 capability exists; `PARTIAL` means a
related internal/read-model capability exists but not the consumer product;
`PROPOSED` means documented only; `UNAVAILABLE` means no supported capability;
and `NOT_ACTIVE` means intentionally outside the active product surface.

## Canonical `HSISignal`: implemented internal P1 boundary and future extensions

`HSISignal` is now implemented only as an immutable, internal P1 on-demand
projection over one verified Market-Wide Watch and read-only strategy
provenance. It must not be confused with the existing analytical signal
lifecycle or represented as a consumer product. It has no persistence, API,
UI, runtime activation, portfolio access, or execution authority. Future
consumer use still requires separately approved query/API, UI, lifecycle, and
activation decisions.

P1 implements the immutable fields and fixed unavailable states defined in its
[acceptance record](POST_V1_HSI_SIGNAL_P1_ACTIVATION_PROPOSAL.md). The broader
future-capable field surface below is not implemented beyond that bounded P1
subset; it must not be used to infer a future actionability state, consumer
API, or product activation.

Future-capable fields:

| Field | Meaning |
| --- | --- |
| `signal_id` | Deterministic identity from canonical instrument, signal type, horizon, detected/as-of time, routing/strategy policy versions, and lineage fingerprints. |
| `canonical_instrument_id` | Exact canonical instrument identity. |
| `signal_type` | A typed product classification; never an execution side effect. |
| `strategy_reference` | Versioned Strategy Registry reference or `STRATEGY_UNAVAILABLE`. |
| `horizon` / `direction` | Explicit, policy-owned horizon and descriptive direction. |
| `strength` / `confidence` / `materiality` | Separately typed values with their source policy; none substitutes for a Decision Score. |
| `actionability` | `WATCH_ONLY`, `RESEARCH_READY`, `SETUP_REQUIRED`, `GATES_REQUIRED`, or another future fail-closed state. |
| `evidence_lineage` | Canonical diagnostic, evidence, Watch, policy, and provenance references/fingerprints. |
| `detected_at` / `expires_at` | Timezone-aware detection and explicit expiry semantics. |
| `portfolio_relevance` | Read-only relationship to current portfolio context, if any; no holding mutation. |

Identity must be deterministic and collision-safe, must retain exact PIT/as-of
lineage, and must not use a latest-record fallback.  Missing, stale, conflicted,
or unavailable evidence remains explicit; it must never be normalized into
strength, readiness, or actionability.

## Strategy Registry architecture

The P1 internal Strategy Registry is a versioned, read-only policy-provenance
lookup. It does not create strategies, activate policies, construct signals,
or authorize execution. Consumer registry visibility remains future work.

The existing approved Pre-Breakout policy may be referenced where its exact
governed identity and suitability apply.  Every unimplemented strategy or
archetype must resolve deterministically to `STRATEGY_UNAVAILABLE`.  In
particular, the presence of an Opportunity Archetype must never imply that it
has an executable strategy, complete setup, Decision Score, or capital
authorization.

## Product-specific calculation boundaries

Equity, IPO, and Mutual Fund intelligence may share the HSI intelligence
platform, canonical identity discipline, evidence lineage, PIT controls, and
governance conventions.  They require separate data contracts, data-quality
rules, horizons, scoring/interpretation policies, and sufficiency conditions.
A universal equity score must not be reused blindly for IPO or Mutual Fund
products.

## Non-goals and safety invariants

- No BUY, SELL, or ROTATE automation.
- No order placement or broker execution authority.
- No portfolio, cash, holdings, or trade-plan mutation.
- No additional Brain, provider truth, or duplicated source of truth.
- No policy-threshold loosening, implied actionability, or latest-record
  fallback.
- No consumer product implementation, activation, or execution authority.

## Future implementation sequence

Future work is deliberately staged and requires separate approval at each
boundary:

1. Completed internal signal projection foundation and fail-closed Strategy
   Registry, retained as Watch-only/non-executable.
2. Horizon-specific policy contracts.
3. Product API/query layer.
4. Consumer UI sections over those read models.
5. Shadow and paper-trading evaluation where separately approved.
6. Controlled product activation with explicit governance and no execution
   authority unless independently approved.

No stage authorizes a later stage by implication.
