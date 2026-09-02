# Post-V1 Long-Term Thesis Family — Policy Approval Pack

**Status: `PROPOSED_FOR_APPROVAL / DOCUMENTATION_ONLY / STRATEGY_POLICIES_NOT_APPROVED / NOT_ACTIVE`.**

The constrained foundation reuses Core V1 Deep Analysis rather than creating a
second dossier. Actual retained-data gaps are in the [reuse and readiness
receipt](POST_V1_LONG_TERM_EVIDENCE_DOSSIER_REUSE_AND_READINESS.md).

## Purpose and boundary

This proposal defines the approval decisions required before any Post-V1
long-term product strategy is implemented. It preserves one canonical HSI Brain
and reuses its exact identity, PIT, diagnostics, financial facts, reliability,
governance, market, sector, external-intelligence, portfolio-analysis, and
audit boundaries. It creates no thesis model, persistence, API, UI, strategy,
score, setup, gate, portfolio mutation, broker authority, order, or trade.

All future outputs, if separately approved and implemented, begin
`WATCH_ONLY / NON_EXECUTABLE`. Detection and a long-term thesis review never
authorize capital or execution.

## Existing Core V1 reuse and limits

| Existing capability | Reuse | Boundary / limitation |
| --- | --- | --- |
| Canonical identity, facts, filings, earnings, diagnostics, reliability and PIT | Exact instrument/evidence/as-of lineage and fail-closed eligibility | Coverage and financial comparability can remain partial. |
| Rule 33 investment thesis and Rule 46 invalidation | Existing higher-order analytical context and price-structure invalidation | Rule 33 is not a product strategy; Rule 46 does not invent fundamental/catalyst invalidations. |
| Fundamental/earnings/governance/risk diagnostics | Evidence inputs and documented insufficiency states | No approved long-term policy-specific quality, growth, cash, leverage, or dilution thresholds. |
| Market, sector and external intelligence | Read-only context and policy-transmission evidence | Current sector RS/breadth cannot be retrojected; event narratives need exact verified exposure. |
| Valuation/trade analysis and scenarios | Existing analytical components and explicit unavailable states | No governed comparable valuation contract; coarse existing scenario weights are not calibrated probabilities. |
| Portfolio analysis / rotation comparison | Read-only portfolio relevance and opportunity-cost context | No bucket semantics or long-term rotation policy is approved; no portfolio access is authorized for this family. |

No current Core V1 result is relabelled as a complete Quality, Compounder,
Inflection, Policy Transmission, or Asymmetric Emerging Compounder strategy.

## Proposed common thesis contract

The following is a future contract outline, not a runtime schema. It must be
immutable, deterministic, versioned, PIT-safe, lineage-complete, and
fail-closed:

| Field group | Proposed requirement | Unapproved / unavailable boundary |
| --- | --- | --- |
| Identity | Deterministic thesis ID from canonical instrument, thesis archetype, approved policy version, as-of, and canonical lineage fingerprints | No runtime identity or persistence is authorized. |
| Evidence | Financial facts/filings, diagnostics, governance/reliability, market/sector, external evidence, and source as-of references | Missing or non-comparable evidence remains explicit; no current-only substitution. |
| Drivers and milestones | Structural drivers plus quarterly/annual milestones traceable to source facts | No forecast, management-guidance adoption, or estimated cash flow without policy. |
| Valuation | Method/status/lineage and explicit unavailable state | No target, fair-value range, multiple, DCF, or universal valuation method is approved. |
| Scenarios | Bear/base/bull availability and source lineage | No probabilities, return forecasts, or synthetic scenario values. |
| Risks and invalidation | Governance, leverage, dilution, liquidity, execution, policy, evidence-quality, and price-structure review conditions | No automatic sell/exit or fabricated fundamental invalidation. |
| Review and portfolio relevance | Policy-owned review schedule and read-only bucket relevance | No review cadence, bucket taxonomy, allocation, add/hold/trim/exit action, or portfolio access is approved. |
| Output | Watch/research state, blockers, and unavailable fields | Never BUY/SELL/ADD/TRIM/ROTATE, gate authorization, broker, order, or trade. |

## Separate policy families

Every family needs a separate versioned policy, required evidence, insufficiency
state, historical/shadow method, and approval. One universal long-term score is
prohibited.

| Identifier | Objective / required evidence | Prohibited inference | Required approval decisions |
| --- | --- | --- | --- |
| `LONG_TERM_QUALITY_FAIR_VALUE` | Durable business quality, governance, balance sheet, cash conversion, financial comparability, and a policy-owned valuation method | “High quality” without specified evidence; fair value or upside from an unapproved method | Quality/cash/leverage/governance rules; valuation method, scope, price basis, horizon, review and invalidation. |
| `LONG_TERM_FUNDAMENTAL_COMPOUNDER` | Durable growth, returns/cash conversion, reinvestment, balance sheet and governance evidence across defined periods | Persistence of growth or compounding from a single period | Growth duration, financial metrics/scope, milestones, deterioration/invalidation and evidence sufficiency. |
| `LONG_TERM_FUNDAMENTAL_INFLECTION` | PIT-visible financial/earnings change with durable confirming evidence | A one-period improvement as a durable inflection | Baseline window, confirmation periods, revision/restatement handling, milestone and invalidation semantics. |
| `LONG_TERM_POLICY_TRANSMISSION` | Exact primary policy evidence and verified exposure through `announcement → legal/rule approval → funding → tender/orders → eligible company capacity → execution → revenue → cash flow` | Direct beneficiary, revenue, or cash-flow effect before supported stages | Stage evidence, direct/supplier/indirect/narrative-only mapping, timing/freshness, risk/cancellation, review and invalidation rules. |
| `LONG_TERM_ASYMMETRIC_EMERGING_COMPOUNDER` | Evidence of an emerging business/growth pathway, governance, balance sheet, liquidity and risk context | “Multibagger” forecast, promise, or guaranteed classification | Asymmetry definition, risk/uncertainty disclosures, dilution/liquidity gates, milestones, valuation availability, review and invalidation. |

“Asymmetric” and “multibagger-type” describe a possible payoff shape only; they
are never forecasts, promises, rankings, or guarantees.

## Common safety, PIT and shadow requirements

- Select only evidence received/available on or before the thesis as-of;
  later filings, restatements, mappings, sector ranks, or news cannot repair an
  earlier thesis.
- Preserve `FACT → DATA → INTERPRETATION → INFERENCE`; a policy may not turn
  narrative association into a verified company driver.
- Retain financial period, statement scope, reporting/publication/receipt time,
  revision lineage, adjustment basis, canonical identity and methodology.
- Fail closed for missing, conflicted, stale, unreliable, non-comparable,
  unapproved, ambiguous, or temporally invalid inputs.
- A later policy must predeclare chronological research/validation/holdout and
  prospective shadow evidence. Historical return maximisation alone cannot
  select a policy.
- No proposed output may be used by Six Gates, paper trades, a broker, an
  order, allocation, or a portfolio mutation without separate authority.

## Decisions required for approval

1. Approve the common contract’s exact statuses, blocker taxonomy, policy
   identity inputs, review cadence semantics, and which fields are allowed to
   be unavailable.
2. Approve each family’s financial-quality, growth, cash-conversion,
   balance-sheet, governance, dilution, liquidity, valuation, horizon,
   milestone, evidence-sufficiency, and invalidation definitions.
3. For Policy Transmission, approve exact accepted evidence at every stage and
   exposure-type eligibility; for Asymmetric Emerging Compounder, approve a
   non-promissory risk/uncertainty framework.
4. Approve the historical replay and prospective shadow design before any
   outcome/performance claim or persistence change.
5. Defer portfolio bucket, add/hold/trim/exit review vocabulary until a
   separately approved portfolio-consumer policy; it is not required for the
   initial Watch-only family contracts.

## Proposed implementation sequence after approval

1. Immutable common thesis domain contract with no persistence, API, UI,
   portfolio, or execution dependency; rollback is deletion of its isolated
   unreferenced module before later wiring.
2. One pure, separately tested policy evaluator per approved family; every
   output is Watch-only/non-executable and uses only approved evidence.
3. Policy-specific PIT/replay/shadow compatibility audit. If durable shadow
   records require a migration, stop for persistence approval.
4. Separate read/query and consumer-surface proposal only after the policy
   contracts and shadow semantics exist.

## Approval statement required to resume implementation

> Approve the exact versioned common Long-Term Thesis contract and the policy
> definitions for the selected named families in
> `POST_V1_LONG_TERM_THESIS_FAMILY_POLICY_PROPOSAL.md`, including required
> evidence, insufficiency/blocker states, financial and valuation methodology,
> horizon, milestones, review cadence, invalidation, PIT/replay and shadow
> requirements. Authorize only isolated Watch-only/non-executable policy
> implementation. No persistence migration, API/UI, portfolio access or
> mutation, broker/order authority, trade authorization, BUY/SELL/ADD/TRIM/EXIT
> output, or performance claim is approved.
