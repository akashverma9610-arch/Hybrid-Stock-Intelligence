# Post-V1 Sell/Risk, Profit-Harvesting, and Fast-Rotation Policy Approval Pack

**Status: `RESEARCH_SHADOW_POLICY_IMPLEMENTED / REVIEW_ONLY / WATCH_ONLY / NON_EXECUTABLE / NOT_CONSUMER_ACTIVE`.**

Profit-Harvesting and Fast-Rotation remain
`POLICY_UNAPPROVED / STRATEGY_UNAVAILABLE / NOT_ACTIVE`.

## Scope and reuse

This single approval pack governs three separate future product windows. It
creates no evaluator, signal, persistence, API/UI, portfolio mutation,
broker/order authority, or trade instruction.

| Core V1 boundary | Reusable evidence | Not a Post-V1 product policy |
| --- | --- | --- |
| Rule 46 and risk/thesis diagnostics | Existing price-structure invalidation and risk context | No fundamental/catalyst/governance invalidation may be invented. |
| Portfolio sell-side policy/runtime | Existing portfolio-bound analytical outputs | Not a general consumer Sell/Risk or Profit-Harvesting policy. |
| Capital Rotation Engine | Immutable candidate/holding comparison, friction and cash-unknown handling | Not Fast-Rotation discovery, bucket policy, or execution authority. |
| Shared Brain / Deep Analysis | PIT-safe financial, reliability, technical, news, sector and diagnostic lineage | No output is re-labelled as approved action. |
| Market Extremes / sector context | Risk and context evidence | Euphoria and current-only sector RS are not automatic triggers. |

All future outputs remain `WATCH_ONLY / NON_EXECUTABLE`. They may request a
governed review but never call a broker, create an order or mutate a portfolio.

## A. Sell/Risk approval decisions

| Decision | Required evidence | Prohibited inference | Exact approval needed |
| --- | --- | --- | --- |
| Thesis invalidation | Rule 46 plus separately defined financial/catalyst/policy evidence | Missing metric, news or price move is an exit | Taxonomy, confirmation, timing and staleness. |
| Governance/legal escalation | Canonical reliability, official disclosure, legal/regulatory evidence and verified mapping | Narrative allegation is fraud conclusion | Severity, source hierarchy, conflict and review/block handling. |
| Earnings/cash/leverage/dilution risk | Comparable PIT financial facts and approved calculations | Raw fact proves structural deterioration | Metrics, scope, lookback, financial-company exceptions and boundaries. |
| Technical breakdown | Exact structural evidence and price basis | One unverified bar proves breakdown | Session/confirmation, adjustment and integrity rules. |
| Evidence degradation | Availability, freshness, conflict and reliability lineage | Insufficiency means weak thesis or sell | Blocker/escalation vocabulary. |

Initial product output, after later approval, may only be descriptive risk or
review state with lineage and blockers. It cannot select EXIT, SELL or TRIM.

### A1. Approved narrow policy: `SELL_RISK_REVIEW_POLICY / v1-research-shadow`

This approval replaces the evidence-dossier-only recommendation for this
narrow policy only.  It does not approve a complete Sell/Risk evaluator,
Profit-Harvesting, or Fast-Rotation.

**Implementation status:** `SELL_RISK_REVIEW_POLICY / v1-research-shadow` is
implemented as a pure deterministic, PIT-bound internal policy. It has no
persistence, API/UI, portfolio, broker, order, setup, Six-Gates, or capital
authorization integration; its statuses remain descriptive only.

#### Scope and required inputs

The policy may consume only exact, canonical, PIT-eligible adverse
Event/Catalyst evidence already classified by an approved upstream contract;
existing immutable `HIGH` or `CRITICAL` materiality; exact verified canonical
instrument mapping; verified official/primary governance, legal, regulatory,
audit, default, or enforcement evidence where the existing canonical event
taxonomy supports that family; canonical evidence availability, freshness,
reliability, and conflict state; existing Rule 46 price-structure
invalidation context without reinterpretation; and existing event
identity/fingerprint and deduplication lineage.

The policy must never infer adverse polarity, event family, fraud, liability,
materiality, or company exposure from narrative text.  If the upstream
canonical contract does not explicitly provide a required classification, the
event is `EVIDENCE_UNAVAILABLE` for this policy.

#### Immutable review vocabulary

| Status | Exact meaning |
| --- | --- |
| `NO_QUALIFYING_RISK_EVIDENCE` | Permitted only when all required V1 evidence domains were evaluated with sufficient, fresh, non-conflicting data and no qualifying evidence exists. |
| `PRIORITY_EVIDENCE_REVIEW` | Exact verified primary adverse event with existing `HIGH` materiality. |
| `URGENT_EVIDENCE_REVIEW` | Exact verified primary adverse event with existing `CRITICAL` materiality. |
| `CONFLICTED_EVIDENCE_REVIEW` | Qualifying adverse evidence exists but canonical counterevidence/conflict prevents a conclusion. |
| `TECHNICAL_STRUCTURE_REVIEW` | Existing Rule 46 context is present under its own currently governed semantics. |
| `MULTI_DOMAIN_EVIDENCE_REVIEW` | Both qualifying adverse primary evidence and Rule 46 technical context are present. |
| `EVIDENCE_UNAVAILABLE` | Required identity, mapping, source, freshness, reliability, materiality, polarity, family, PIT, or Rule 46 data is missing, stale, unverified, non-comparable, or temporally invalid. |

These labels describe review priority/context only.  They are not risk
severity, thesis invalidation, a fraud or legal conclusion, SELL/EXIT/TRIM,
portfolio action, capital authorization, a setup, or a Six-Gates result.

When `CRITICAL` adverse evidence is conflicted, the result is
`CONFLICTED_EVIDENCE_REVIEW` and preserves `CRITICAL` materiality in its
lineage.  Conflict is neither exoneration nor confirmed harm.  A
`MULTI_DOMAIN_EVIDENCE_REVIEW` preserves the original event materiality and
Rule 46 state; it neither increases severity nor implies stronger action.

#### Source, confirmation, and categorical boundaries

- One exact verified official/primary source is sufficient for a review state.
- Secondary media, social sentiment, rumour, inferred exposure, and
  unverified narrative cannot create `PRIORITY_EVIDENCE_REVIEW` or
  `URGENT_EVIDENCE_REVIEW`; they remain contextual lineage only where the
  existing evidence contract permits them.
- Repeated reports of one canonical event are not two-source confirmation.
- Conflicting canonical primary evidence produces
  `CONFLICTED_EVIDENCE_REVIEW`.
- Allegation, investigation, show-cause notice, charge, order, and final
  adjudication retain their exact canonical categories.  No category may be
  silently promoted into another, and no output may state fraud, misconduct,
  or liability is proven unless retained primary evidence explicitly
  establishes that fact under an approved upstream classification.

#### PIT, freshness, resolution, and recurrence

The policy creates no duration.  Only evidence canonically eligible at the
evaluation `as_of` may be read; only canonically fresh/current qualifying
evidence may create a priority/urgent state.  Stale evidence cannot create a
new priority/urgent state, though it may remain lineaged context where
permitted.  Missing freshness/lifecycle is `EVIDENCE_UNAVAILABLE`.

Explicit canonical cancellation, correction, supersession, or resolution is
retained.  Absence of a later update is not resolution, and time alone never
downgrades a review.  If the upstream contract cannot represent cancellation,
supersession, or resolution, expose `RESOLUTION_UNAVAILABLE` rather than
inventing a transition.

The policy uses immutable producer-event identity, evidence fingerprint, and
canonical lineage.  Reingesting the same event cannot escalate a result.  A
corrected/superseding primary event is distinct only when canonical lineage
explicitly links it.  A genuinely new event about the same company/category
may create a new review item but cannot raise priority beyond its own
canonical materiality.  Input order cannot affect resolution.

#### Rule 46 boundary and deferrals

Rule 46 is reused only as existing descriptive technical/price-structure
context.  Its formula, confirmation, price basis, adjustment, integrity, and
version semantics are neither duplicated nor changed.  Rule 46 never maps to
SELL, EXIT, thesis invalidation, or portfolio action.  Missing, stale,
non-comparable, or unverifiable Rule 46 data cannot fabricate technical risk;
Rule 46 alone may produce only `TECHNICAL_STRUCTURE_REVIEW`.

V1 explicitly defers revenue/earnings, margin, cash-conversion, leverage,
refinancing/liquidity, dilution, order-book/execution, promoter-quality,
adverse policy-transmission, valuation/euphoria, thesis invalidation,
financial-company ratios, persistence scoring, risk-downgrade scoring, and
trade-performance shadow outcomes.  They require separately approved
formulas, periods, accounting bases, sector variants, thresholds, and
calibration.

#### Determinism and safety

Every evaluation requires exact canonical instrument, evaluation `as_of`,
`received_at/available_at <= as_of`, exact source/event/evidence identities,
immutable deterministic ordering, and tamper verification.  Runtime/current
time, future evidence, fuzzy mapping, and silent fallback are prohibited.
Serialization and fingerprints must be stable.

The policy is `WATCH_ONLY / NON_EXECUTABLE`.  It has no persistence migration,
API/UI, portfolio access or mutation, broker/order authority, automatic
BUY/SELL/ADD/TRIM/EXIT/ROTATE action, or performance claim.

## B. Profit-Harvesting approval decisions

The first approved implementation is limited to the immutable
Market-Extremes Assurance mapping in
`POST_V1_PROFIT_HARVESTING_IMPLEMENTABILITY_CORRECTION.md`. It is
`WATCH_ONLY / NON_EXECUTABLE`; euphoria is review evidence, never a sell,
trim, exit, target, or portfolio instruction. All other rows below remain
separately governed and unavailable.

| Decision | Required evidence | Prohibited inference | Exact approval needed |
| --- | --- | --- | --- |
| Valuation excess | Comparable valuation method, price basis and denominator | Price rise equals overvaluation | Method, scope, boundary/band, freshness and exceptions. |
| Euphoria/exhaustion | PIT-valid market-extremes, technical and liquidity evidence | Euphoria alone is a top/sell | Context/review role, confirmation and staleness. |
| Concentration | Read-only portfolio context and concentration policy | Stock intelligence can inspect/mutate holdings | Separate portfolio-consumer authority and thresholds. |
| Catalyst/milestone completion | Approved family milestone and event lifecycle policy | News narrative means completion | Milestone/source verification and cancellation timing. |
| Reward/risk / maturity | Valuation, thesis and structure methodology | Existing paper/backtest metrics determine live action | Formula, horizon, taxes, liquidity and remaining-thesis policy. |

No numerical profit target, concentration limit, tax/liquidity threshold, partial
profit rule or full-exit rule is selected.

## C. Fast-Rotation approval decisions

Fast Rotation consumes governed strategy outputs; it is not a second discovery
Brain. It compares a candidate only to a comparable holding or cash after both
have independently governed evidence. Cash remains valid.

| Decision | Required evidence | Prohibited inference | Exact approval needed |
| --- | --- | --- | --- |
| Candidate eligibility | Approved strategy/policy, lineage and setup/gate state where required | Watch/archetype alone is replacement candidate | Eligible strategies and exact states. |
| Comparable buckets | Core Compounder, Emerging/Satellite, Thematic and Tactical classification | Cross-bucket holdings are interchangeable | Bucket taxonomy, assignment source and higher cross-bucket hurdle. |
| Improvement hurdle | Candidate/holding evidence, risk/reward, friction, taxes, liquidity, correlation/concentration | Existing score gap is universally sufficient | Comparable economics and boundary policy. |
| Freshness / expiry | Policy-owned signal/evidence lifecycle | Current-only rank serves historical comparison | Freshness, expiry, session and PIT rules. |
| Cash/unavailable | Cash validity, known-state and explicit insufficiency | Unknown cash is deployable or a recommendation | Cash context and no-action semantics. |

Existing Capital Rotation labels do not grant a Post-V1 action, broker operation
or holding mutation.

## Shared safety and shadow requirements

- Inputs must be canonical, PIT-eligible, exact-identity matched and lineaged;
  current-only/future evidence cannot repair historical state.
- Missing, stale, conflicted, unreliable, non-comparable, unapproved or
  temporally invalid evidence fails closed to explicit review/unavailable state.
- Every family needs approved chronology, context, outcome, friction, tax,
  liquidity, concentration and prospective shadow semantics. A required durable
  record needs a separate persistence approval.

## Decisions required for approval

1. Any Sell/Risk categories beyond the approved narrow
   `SELL_RISK_REVIEW_POLICY / v1-research-shadow` scope: financial
   deterioration, policy transmission, persistence, downgrade, thesis
   invalidation, and their source hierarchy, severity, confirmation,
   staleness, and evidence-insufficiency semantics.
2. Profit-Harvesting valuation, euphoria, concentration, milestone,
   reward/risk, tax and liquidity review definitions.
3. Fast-Rotation bucket taxonomy, comparable-pair and cross-bucket hurdle,
   candidate/holding eligibility, friction/tax/liquidity/correlation,
   freshness and cash/no-action rules.
4. Policy-specific PIT replay and prospective shadow methodology.

## Approval statement required to resume unapproved broader policies

> Approve exact versioned Watch-only/non-executable policies for Post-V1
> Sell/Risk, Profit-Harvesting and Fast-Rotation as specified in
> `POST_V1_SELL_PROFIT_ROTATION_POLICY_PROPOSAL.md`, including required
> evidence, source hierarchy, formulas or categorical boundaries, confirmation,
> freshness, invalidation, evidence insufficiency, portfolio-bucket and
> comparability rules, cash handling, friction/tax/liquidity treatment, and
> PIT/replay/shadow methodology. Authorize only isolated read-only policy
> implementation. No persistence migration, API/UI, portfolio mutation,
> broker/order authority, automatic BUY/SELL/ADD/TRIM/EXIT/ROTATE action, or
> performance claim is approved.
