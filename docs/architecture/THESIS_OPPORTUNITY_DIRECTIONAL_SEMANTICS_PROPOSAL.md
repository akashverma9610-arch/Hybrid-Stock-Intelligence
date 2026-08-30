# Thesis / Opportunity Directional Semantics Proposal

**Status: PROPOSED — NOT APPROVED — NOT SELECTED — NOT ACTIVE.**

This U14D-6A audit refines the historical U14D-5A proposal using the now
implemented `BrainResearchComparisonState` and `ResearchStateDelta`. It does
not create a policy artifact, interpreter, persistence, alert,
recommendation, signal, order, trade, or runtime wiring.

## 1. Actual factual substrate

```text
BrainResearchComparisonState(T1)
  + BrainResearchComparisonState(T2)
  + explicit brain-research-comparability-policy / v1-approved
  -> ResearchStateDelta
  -> future ThesisInterpretation / OpportunityInterpretation
```

`ResearchStateDelta` retains instrument and state lineage, PIT timestamps,
policy identity, a per-domain `COMPARABLE` / `INSUFFICIENT` /
`NON_COMPARABLE` / `NOT_APPLICABLE` result, metric pairings, factual old/new
values or references, and factual change kinds (`UNCHANGED`, `VALUE_CHANGED`,
`ADDED`, `REMOVED`, and lineage/methodology/dependency/eligibility drift).

It does not retain a governed explanation of whether an increase or decrease
is favourable, material, persistent, causally attributable, or contradictory.
Therefore it is necessary but not sufficient for directional semantics.

The explicit input policy remains:

| Field | Value |
| --- | --- |
| Policy | `brain-research-comparability-policy / v1-approved` |
| Fingerprint | `361a2f7e8cd9a5acd7a2731d10a56c32ae52227c7fd412fbd2f1967b37ca1bc2` |
| Governance | approved; selected `false`; active `false` |
| Mode | `KNOWLEDGE_AT_THE_TIME` |

## 2. Proposed meanings and separation

| Concept | Future meaning | Explicitly not |
| --- | --- | --- |
| Thesis | A sufficiently corroborated, material change in the underlying company/research case. | Price, technical timing, candidate formation, entry geometry, recommendation. |
| Opportunity | A sufficiently corroborated change in the quality/timeliness of a possible exposure under the Shared Brain. | Portfolio decision, trade instruction, or substitute for thesis. |

They must remain independent. A business case can strengthen while a setup is
overextended; a setup can improve while the thesis is unchanged; a temporary
technical setup can improve while the business evidence weakens. No later
aggregator may force these facts into the same direction.

## 3. Mandatory future interpretation gate

Any future directional rule must require, for every required input:

1. `ResearchStateDelta` status `COMPARABLE`.
2. Exact applicable metric/scope/basis/unit/scale/period/methodology/dependency
   parity already proven by the delta.
3. PIT visibility at each state; no restated-history reconstruction.
4. Required evidence neither conflicted nor invalid; unavailable, partial, or
   stale input is insufficient unless a future domain-specific exception is
   approved.
5. An approved metric-directionality mapping, materiality rule, and required
   persistence/confirmation rule.
6. A governed contradiction disposition.

`NON_COMPARABLE` and `INSUFFICIENT` cannot be directional evidence.
`NOT_APPLICABLE` is neutral only for a rule that explicitly declares the
dimension optional; it is never silently converted to unchanged or zero.

## 4. Thesis candidate audit

| Candidate factual bundle | Classification | Required future governance |
| --- | --- | --- |
| Multi-period comparable revenue, direct operating-profit/margin, PAT/EPS, and cash-flow corroboration | `NEEDS_MORE_GOVERNANCE` | Metric directionality, fiscal basis, materiality, persistence, one-off/revision treatment, contradiction handling. |
| Margin change alone | `REJECT` as a thesis rule | Margin may reflect mix, accounting, commodity, or base effects; may become corroborating input only. |
| Debt/liquidity/working-capital change alone | `REJECT` as a thesis rule | Financing context, asset-sale/dilution/business-shrinkage treatment are absent. |
| Comparable cash-flow plus earnings/balance-sheet confirmation | `NEEDS_MORE_GOVERNANCE` | Seasonality, capex/working-capital treatment, materiality, confirmation windows. |
| Normalized promoter/FII/DII/public/pledge percentage movement | `REJECT` | Frozen source policy marks normalized ownership comparison unsupported. |
| Split, bonus, ordinary dividend, or reference-only corporate action | `REJECT` | These are price/identity comparability facts, not thesis direction. |
| Material rights issue, demerger, acquisition, dilution, order, guidance, approval, or cancellation | `NEEDS_MORE_GOVERNANCE` | Event-specific typed taxonomy, attributable causal link, materiality, confirmation, supersession treatment. |
| Generic macro/sector/regime movement | `REJECT` as direct company-thesis direction | Requires a governed company transmission mechanism and horizon; regime alone is context. |
| Price, RSI, BBW, technical, setup, candidate, support, trigger, R:R, or Top-3 alone | `REJECT` | These are timing/context facts, not underlying business-case evidence. |

No thesis rule is currently a `SAFE_CANDIDATE`: the repository has comparable
facts but no approved directionality, materiality, persistence, or
contradiction policy.

## 5. Opportunity candidate audit

| Candidate factual bundle | Classification | Required future governance |
| --- | --- | --- |
| Same-policy governed setup eligibility changes | `NEEDS_MORE_GOVERNANCE` | Research admissibility, reliability/integrity, liquidity, market/sector context, and opportunity aggregation. |
| Same-policy structural support breach / setup invalidation | `NEEDS_MORE_GOVERNANCE` | Could support a narrow setup-status result, not thesis or SELL; requires exact structural/session lineage. |
| Same-policy do-not-chase boundary crossed | `NEEDS_MORE_GOVERNANCE` | Prefer narrow `ENTRY_ATTRACTIVENESS` semantics; requires price-session/tick/entry-methodology parity. |
| Comparable entry geometry/R:R change alone | `REJECT` as broad opportunity direction | Mechanical R:R change can be caused by a price fall, changed target, or damaged thesis. |
| Market regime change | `NEEDS_MORE_GOVERNANCE` | Context only; requires a governed combination with research/setup/reliability inputs. |
| Sector RS/breadth/rank/Top-3 transition | `REJECT` for historical delta today | Frozen policy categorizes them `CURRENT_ONLY`; no durable historical parity exists. |
| Comparable valuation change | `REJECT` today | Valuation comparison is explicitly unsupported. |
| Candidate creation/removal or fingerprint change alone | `REJECT` | Candidate remains `OPPORTUNITY_CANDIDATE` / `RESEARCH_PENDING`; fingerprint is lineage, not direction. |

No broad opportunity rule is presently safe. Narrow future subdimensions are
safer than one global direction: `SETUP_QUALITY`, `ENTRY_ATTRACTIVENESS`,
`MARKET_CONTEXT`, `SECTOR_CONTEXT`, `VALUATION_ATTRACTIVENESS`, and
`LIQUIDITY_EXECUTABILITY` should each prove their own policy requirements
before any optional governed aggregation.

## 6. Decision Score, diagnostics, news, and macro

| Input | Proposed initial role | Why it cannot direct semantics alone |
| --- | --- | --- |
| Decision Score | `NEEDS_MORE_GOVERNANCE` corroborating cross-check only | A comparable score change may hide deteriorating components; weights/configuration and missing-data policy need governance. |
| 61 diagnostics | `NEEDS_MORE_GOVERNANCE` corroborating lineage only | A pass-count/fingerprint/coverage change lacks factor-level directional governance. |
| News/catalyst | `NEEDS_MORE_GOVERNANCE` confirmation, invalidation, or `RESEARCH_REQUIRED` input | Existing typed event/source/confirmation data is factual, not bullish/bearish sentiment. |
| Macro/sector transmission | `NEEDS_MORE_GOVERNANCE` only where a typed company transmission contract exists | Generic macro/regime movement is not company direction. |

## 7. Reliability, integrity, and contradiction disposition

Future rules must not resolve uncertainty by best guess:

| Condition | Proposed disposition |
| --- | --- |
| Required evidence conflicted or native integrity invalid | `NON_COMPARABLE` / no directional interpretation |
| Required evidence unavailable, partial, or stale | `INSUFFICIENT` / no directional interpretation |
| Comparable inputs point in different governed metric directions | `MIXED` or `RESEARCH_REQUIRED`; never force strengthened/weakened |
| Directionality/materiality/persistence policy absent | `RESEARCH_REQUIRED` or `INSUFFICIENT` |

Minimum safe future thesis vocabulary: `THESIS_STRENGTHENED`,
`THESIS_WEAKENED`, `THESIS_UNCHANGED`, `MIXED`, `INSUFFICIENT`,
`NON_COMPARABLE`, `NOT_APPLICABLE`, `RESEARCH_REQUIRED`.

Minimum safe opportunity vocabulary should be dimension-specific first:
`SETUP_QUALITY_*`, `ENTRY_ATTRACTIVENESS_*`, `MARKET_CONTEXT_*`,
`SECTOR_CONTEXT_*`, `VALUATION_ATTRACTIVENESS_*`, `LIQUIDITY_EXECUTABILITY_*`,
plus `MIXED`, `INSUFFICIENT`, `NON_COMPARABLE`, `NOT_APPLICABLE`, and
`RESEARCH_REQUIRED`. A generic `OPPORTUNITY_IMPROVED` /
`OPPORTUNITY_DEGRADED` requires a separate aggregation policy.

## 8. Candidate decision tables

### Thesis

| Evidence pattern | Comparability | Materiality / confirmation | Contradiction | Proposed disposition |
| --- | --- | --- | --- | --- |
| Comparable multi-period business bundle | Required | `MATERIALITY_POLICY_REQUIRED`; confirmation policy required | None under governed rules | `NEEDS_MORE_GOVERNANCE` |
| Comparable single revenue/PAT/margin/debt change | Required | Not governed | May be present | `RESEARCH_REQUIRED` |
| Comparable confirmed material event with attributable claim | Required | Event materiality policy required | Must be checked | `NEEDS_MORE_GOVERNANCE` |
| Any required delta insufficient/non-comparable | Failed | N/A | N/A | `INSUFFICIENT` / `NON_COMPARABLE` |
| Mixed comparable evidence | Required | N/A | Present | `MIXED` / `RESEARCH_REQUIRED` |

### Opportunity

| Evidence pattern | Required context | Comparable? | Proposed disposition |
| --- | --- | --- | --- |
| Support breach under same governed setup lineage | Research admissibility, integrity, session/tick provenance | Required | Narrow future setup/entry semantic only; `NEEDS_MORE_GOVERNANCE` |
| Do-not-chase boundary crossed | Same setup/entry/tick policy and market session | Required | Narrow future entry-attractiveness semantic only; `NEEDS_MORE_GOVERNANCE` |
| Setup eligibility change | Same governed policy plus research/context bundle | Required | `NEEDS_MORE_GOVERNANCE` |
| R:R change alone / candidate appearance | N/A | Insufficient by itself | `REJECT` as broad opportunity direction |
| RS/breadth/Top-3 historical transition | Durable source absent today | No | `INSUFFICIENT` |

## 9. Required future policy families and contracts

Separate policies are recommended because thesis evidence and opportunity
context have different directionality, materiality, confirmation, and
aggregation requirements:

1. `research-metric-directionality-policy` — admissible metric/event meaning,
   applicable scope and context, no monotonic assumption by default.
2. `research-semantic-materiality-policy` — metric/event-specific thresholds
   or non-numeric materiality rules.
3. `thesis-interpretation-policy` — evidence bundles, corroboration,
   contradiction and persistence rules.
4. `opportunity-interpretation-policy` — subdimensions, setup/context
   dependencies, and optional aggregation rules.

Only after human approval should immutable, portfolio-independent contracts be
considered:

* `ThesisInterpretation`: source delta/state lineage, policy lineage,
  sufficiency, factual supporting/contradicting delta IDs, blockers and
  deterministic fingerprint.
* `OpportunityInterpretation`: source delta/state lineage, optional thesis
  interpretation lineage, dimension-specific results, blockers, policy
  lineage and deterministic fingerprint.

Neither future contract may contain recommendation, alert, allocation, order,
or execution fields.

## 10. Governance gaps matrix and next slice

| Gap | Blocks | Priority | Recommended governance slice |
| --- | --- | --- | --- |
| Metric/event directionality by context | Thesis and opportunity | Highest | `research-metric-directionality-policy` audit/proposal |
| Materiality | Thesis and opportunity | Highest | Materiality contract proposal after directionality |
| Confirmation/persistence windows | Thesis | High | Thesis evidence-bundle proposal |
| One-off, revision, and restatement treatment | Thesis | High | Financial semantic-evidence policy |
| Contradiction resolution | Thesis and opportunity | High | Shared semantic contradiction contract |
| Catalyst event taxonomy/attribution | Thesis | High | Catalyst semantic taxonomy audit |
| Canonical PIT valuation comparison | Opportunity | High | Valuation evidence contract |
| Durable sector RS/breadth/rank history | Opportunity | Medium | Sector historical-artifact governance |
| Opportunity subdimension aggregation | Opportunity | Medium | Opportunity aggregation policy |

**Recommended next exact slice:** governance audit/proposal for a separate
`research-metric-directionality-policy`, beginning with direct financial
metrics and explicitly excluding price, technical, ownership percentages,
valuation, score, candidate, and generic news shortcuts.

**U14D-6B refinement:** [Research Metric Directionality Policy
Proposal](RESEARCH_METRIC_DIRECTIONALITY_POLICY_PROPOSAL.md) establishes that
the current factual delta can represent same-period revisions but does not
construct a business trajectory. The eventual directionality-policy scope is
therefore empty pending separate factual trajectory governance; this is not a
frozen, selected, or active policy.

## 11. Firewalls and non-changes

The future dependency is factual delta → optional separate interpretation;
neither interpretation directly authorizes an alert. Alert authorization must
later evaluate materiality, relevance, freshness, suppression, and context.
Likewise, `THESIS_STRENGTHENED` is not BUY, `THESIS_WEAKENED` is not SELL,
`OPPORTUNITY_IMPROVED` is not BUY, and `OPPORTUNITY_DEGRADED` is not SELL.

Portfolio holdings, cost basis, P&L, taxes, concentration, cash, alternatives,
and allocation remain outside these research semantics. Six Gates remains
downstream of any future research/opportunity result and must not be used to
create thesis direction or a generic opportunity direction.

No code, frozen policy, selection, activation, persistence, migration, API,
provider/network call, worker, listener, scheduler, diagnostic run, score run,
gate execution, scanner threshold, recommendation, alert, signal, order, or
trade is changed by this proposal.
