# Research Metric Directionality Policy Proposal

**Policy family:** `research-metric-directionality-policy`  
**Version:** `v1-proposed`  
**Status: PROPOSED — NOT APPROVED — NOT SELECTED — NOT ACTIVE.**

> Historical proposal lineage is now `v1-proposed -> v1-approved`. The frozen
> v1 policy is documented in
> [RESEARCH_METRIC_DIRECTIONALITY_POLICY_APPROVED.md](RESEARCH_METRIC_DIRECTIONALITY_POLICY_APPROVED.md).
> U14D-6W through U14D-6Y supplied the factual trajectory prerequisite that
> this original proposal identified as missing.

This U14D-6B document is governance analysis only. It introduces no runtime
policy artifact, enum, interpreter, trajectory builder, persistence, API,
provider call, alert, recommendation, signal, trade, or execution behavior.
It refines the U14D-6A thesis/opportunity directional-semantics proposal.

## 1. Actual financial evidence and comparison boundary

`FinancialFact` is the canonical immutable financial record. It has an exact
`FinancialMetric`, Decimal value, currency, unit, `NumericScale`, period type,
value basis, period start/end, fiscal year/quarter, statement scope, fact kind,
source/filing reference, publication/receipt timestamps, normalization version,
revision parent, provenance, and quality flags. `available_at` is the later of
publication and first receipt. `FinancialFactStore` is PIT-filtered by both
publication and receipt time and retains revisions as separate facts.

The current `FinancialFactsEvidenceAdapter` contributes financial-fact
**artifact lineage** to `UnifiedIntelligenceState`; the normal
`BrainResearchComparisonState` therefore contains `ARTIFACT_REFERENCE`
observations, not automatic numeric `FACTUAL_VALUE` observations. Explicit
`ResearchMetricObservation` supports a numeric factual value, but no production
FinancialFact-to-numeric-observation materializer currently supplies one.

`ResearchStateDelta` pairs observations only when their semantic identity
matches: metric, dimension, unit, scale, basis, scope, **period identity**,
window, benchmark, methodology, and identity components. It reports factual
`VALUE_CHANGED`, `ADDED`, `REMOVED`, or lineage/methodology/dependency/source
eligibility drift. It does not know whether a value change is favorable.

This makes a same-period revision (for example, Q1 revenue corrected from X to
Y) eligible to appear as `VALUE_CHANGED`. A later Q2 is not a Q1-to-Q2
trajectory: with retained Q1 it is `ADDED`; if a replacement observation is
paired, period identity differs and it is `NON_COMPARABLE`. Thus no existing
delta outcome is a governed business-period growth/decline fact.

## 2. Exact canonical metric inventory

All listed identifiers are values of `FinancialMetric`, usable by
`FinancialFact` and the canonical store. `FinancialValueDimension` currently
returns `MONETARY` for every item except EPS/face value (`PER_SHARE`) and shares
outstanding (`COUNT`); `PERCENTAGE` and `RATIO` exist in the vocabulary but are
not emitted by the current `FinancialFact.value_dimension` property.

| Exact metric IDs | Type | Current canonical form / source boundary | In ordinary Brain state / direct delta | Proposed disposition |
| --- | --- | --- | --- | --- |
| `REVENUE`, `OTHER_INCOME`, `EBITDA`, `OPERATING_PROFIT`, `EBIT`, `DEPRECIATION`, `FINANCE_COST`, `PBT`, `TAX`, `PAT`, `MINORITY_INTEREST` | Flow; monetary | Raw reported/derived `FinancialFact`; quarterly, annual, TTM or point-in-time type with explicit value basis/scope. The BSE XBRL importer currently maps only revenue, other income, PBT, PAT, finance cost and depreciation. | Artifact reference only by default; numeric comparison requires explicit observation. Same-period only. | `TRAJECTORY_REQUIRED`, except other income/tax/minority interest: `CONTEXT_DEPENDENT`. |
| `EPS_BASIC`, `EPS_DILUTED`, `FACE_VALUE` | Per-share | Raw `FinancialFact`; no statement-wide monetary scale is allowed to change the per-share dimension. BSE maps basic EPS only. | Same as above. | `TRAJECTORY_REQUIRED`; share-count and corporate-action parity required. |
| `TOTAL_ASSETS`, `TOTAL_LIABILITIES`, `TOTAL_EQUITY`, `NET_WORTH`, `TOTAL_DEBT`, `CASH_AND_EQUIVALENTS`, `CURRENT_ASSETS`, `CURRENT_LIABILITIES`, `INVENTORY`, `RECEIVABLES`, `PAYABLES` | Stock; monetary point-in-time balance-sheet value | Raw `FinancialFact`; BSE XBRL currently maps total assets and total liabilities only. | Same as above. | `CONTEXT_DEPENDENT`; raw stock movement is not monotonic business meaning. |
| `CFO`, `CFI`, `CFF`, `CAPEX`, `FREE_CASH_FLOW` | Flow; monetary cash-flow value | `FREE_CASH_FLOW` exists as a metric and conservative derivation output only when compatible CFO plus negative-sign capex is unambiguous. BSE importer intentionally does not derive/import EBITDA or cash flow. | Same as above; derived facts retain parent references but are not automatically numeric Brain observations. | CFO/FCF `TRAJECTORY_REQUIRED` and corroboration required; CFI/CFF/capex `CONTEXT_DEPENDENT`. |
| `SHARES_OUTSTANDING` | Count | Raw fact, distinct `COUNT` dimension. | Same as above. | `NON_DIRECTIONAL`; identity/denominator context only. |

There are no canonical `FinancialMetric` IDs for ROCE, ROE, operating/net
margin, debt/equity, net debt, interest coverage, receivable days, inventory
days, cash-conversion cycle, or revenue/PAT/EPS growth. `FinancialDerivationService`
can produce non-persisted `FinancialDerivedMetric` labels for growth, margins,
balances, and FCF, but only FCF is also an enumerated canonical metric. These
generic labels have no fixed registry, source policy, stored canonical fact, or
automatic `BrainResearchComparisonState` representation. Those requested ratios
and growth measures are therefore `UNSUPPORTED` for a directionality policy now.

## 3. Proposed metric-level vocabulary

The following vocabulary is proposal-only and deliberately does not contain
`POSITIVE`, `NEGATIVE`, thesis, opportunity, risk, or action language:

| Term | Proposed meaning |
| --- | --- |
| `DIRECTIONALITY_CANDIDATE` | A future factual trajectory might receive a narrowly defined `HIGHER_POTENTIALLY_FAVORABLE` or `LOWER_POTENTIALLY_FAVORABLE` factor label after all rule prerequisites are governed. |
| `TRAJECTORY_REQUIRED` | Raw level/revision deltas cannot carry semantic direction; a separate comparable-period factual artifact is required first. |
| `CONTEXT_DEPENDENT` | Higher/lower has no stable generic economic meaning without attributable context or a governed multi-metric bundle. |
| `NON_DIRECTIONAL` | The value is denominator, reference, or lineage evidence and should not receive favorable/unfavorable direction. |
| `UNSUPPORTED` | The existing canonical contract does not supply a governed, comparable metric. |
| `HIGHER_POTENTIALLY_FAVORABLE` / `LOWER_POTENTIALLY_FAVORABLE` | Future policy output only; never a thesis, opportunity, recommendation, or action. |

## 4. Candidate analysis by financial family

| Metric/family | Raw-delta meaning | Required factual form | Candidate direction | Main disqualifiers | Disposition |
| --- | --- | --- | --- | --- | --- |
| `REVENUE` | Same-period revision is knowledge correction, not growth. | YoY, sequential, annual, or TTM trajectory must be distinct and named. | A future trajectory may be a candidate only with scope/basis parity. | Acquisitions, demergers, currency, inflation, scope/accounting changes, low base. | `TRAJECTORY_REQUIRED` |
| `OTHER_INCOME` | May be investment/asset-sale/non-operating movement. | Event/line-item attribution. | None in raw form. | Non-operating or one-off income. | `CONTEXT_DEPENDENT` |
| `EBITDA`, `OPERATING_PROFIT`, `EBIT` | Absolute increase alone does not establish operating-quality improvement. | Comparable trajectory plus revenue and exceptional-item context. | May become a corroborating candidate, not standalone. | Shrinking revenue, mix, exceptional costs/income, definition drift. | `TRAJECTORY_REQUIRED` |
| `PBT` | Mixed operating, finance, other-income, and tax-predecessor effects. | Comparable trajectory plus constituent context. | No standalone monotonic rule. | Other income, finance cost, exceptionals. | `CONTEXT_DEPENDENT` |
| `PAT` | Same-period revision or new period may include non-operating effects. | Comparable trajectory, scope parity, profit-quality evidence. | Potential corroborating candidate only. | Tax, exceptionals, discontinued operations, minority interest, accounting changes. | `TRAJECTORY_REQUIRED` |
| `EPS_BASIC`, `EPS_DILUTED` | Per-share numerator and denominator both matter. | Comparable per-share trajectory plus shares/corporate-action lineage. | Potential corroborating candidate only. | Split/bonus, issuance, buyback, dilution, basic-vs-diluted mismatch. | `TRAJECTORY_REQUIRED` |
| `DEPRECIATION`, `FINANCE_COST`, `TAX`, `MINORITY_INTEREST` | Accounting/financing/ownership components, not generic quality direction. | Explicit event and constituent attribution. | None in raw form. | Capitalization, refinancing, tax rates, entity mix. | `CONTEXT_DEPENDENT` |
| `TOTAL_ASSETS`, `TOTAL_LIABILITIES`, `TOTAL_EQUITY`, `NET_WORTH` | Balance-sheet magnitude is not quality direction. | Same-date balance-sheet trajectory plus transaction attribution. | None in raw form. | Asset sale, acquisition, write-off, issuance, reclassification. | `CONTEXT_DEPENDENT` |
| `TOTAL_DEBT` | Lower debt can be contraction; higher debt can fund productive investment. | Comparable trajectory plus use-of-funds, cash flow, and equity context. | No standalone rule. | Refinancing, acquisition/capex, asset sale, equity dilution. | `CONTEXT_DEPENDENT` |
| `CASH_AND_EQUIVALENTS` | More cash can arise from debt, equity, asset sale, or operations. | Cash-flow and financing attribution. | None in raw form. | Funding source/uses absent. | `CONTEXT_DEPENDENT` |
| `CURRENT_ASSETS`, `CURRENT_LIABILITIES`, `RECEIVABLES`, `INVENTORY`, `PAYABLES` | Raw working-capital balances scale with business volume. | Governed normalized days/cycle metric, if later canonically created. | None for raw balances. | Growth, seasonality, channel/commodity cycles. | `CONTEXT_DEPENDENT` |
| `CFO` | Higher single-period CFO can be working-capital release/timing. | Comparable trajectory with earnings and balance-sheet corroboration. | Potential corroborating candidate only. | Receivables/inventory/payables changes; tax/one-offs. | `TRAJECTORY_REQUIRED` |
| `FREE_CASH_FLOW` | Only constructible when capex sign is unambiguous. | Compatible CFO/capex trajectory with capex classification. | Potential corroborating candidate only. | Underinvestment, growth capex, acquisition spending, sign ambiguity. | `TRAJECTORY_REQUIRED` |
| `CFI`, `CFF`, `CAPEX` | Spending/financing levels have no generic good/bad direction. | Typed use-of-funds/capex context. | None in raw form. | Growth versus maintenance, acquisition, financing mix. | `CONTEXT_DEPENDENT` |
| `SHARES_OUTSTANDING`, `FACE_VALUE` | Denominator/reference changes; neither measures underlying performance. | Corporate-action and issuance lineage. | None. | Split/bonus/issue/reclassification. | `NON_DIRECTIONAL` |

## 5. Ratios, growth, and numeric edge cases

ROCE/ROE/OPM/net margin/D:E/interest coverage are not canonical stored metric
IDs. They must not be reconstructed ad hoc for this policy. If a later
canonical ratio contract exists, its rules must reject zero, near-zero, and
negative denominators; undefined/infinite values; sign changes; and mixed
scope/period/scale. A percentage movement from a negative base, such as PAT
from -100 to -20, must not be equated with ordinary positive-profit growth.

Likewise, `FinancialDerivationService.growth` accepts a caller-supplied kind
and only rejects a zero prior value; it has no governed YoY/sequential/annual
semantic registry. Its output must not become a policy input until a later
trajectory contract freezes the comparison basis and sign-domain handling.

## 6. Revision and trajectory separation

The proposed default is: **same-accounting-period revision/restatement is a
knowledge correction, never a business-trajectory direction.** A revision may
later become thesis-relevant through separately governed materiality,
attribution, and contradiction treatment, but not through raw numerical sign.

An eventual factual `FinancialMetricTrajectory` (name provisional) is required
before any metric directionality rule can operate. It should contain exact
metric ID; previous/current fact IDs and fingerprints; prior/current accounting
period identity; explicit comparison basis (`YOY`, `SEQUENTIAL`, `ANNUAL`, or
`TTM`); scope, currency, unit, scale, value basis, normalization and revision
lineage; source observations; factual absolute/relative change; numeric-domain
status; PIT timestamps; warnings/blockers; and deterministic fingerprint. It
would remain factual and have no directionality, materiality, thesis, or
opportunity result.

## 7. Mandatory future rule prerequisites

Every eventual rule must require a comparable factual trajectory, exact
instrument/metric/scope/currency/unit/scale/value-basis/period parity, stable
normalization/methodology, PIT-visible facts, explicit revision treatment,
acceptable quality, no conflict, valid numeric domain, and applicable
corporate-action/share-count parity. Missing, partial, stale, conflicted,
invalid, restated-without-policy, or non-comparable evidence must block the
metric-level result.

Directionality is not materiality: a future `OPM`-style value moving from
12.00% to 12.01% could have a mathematical direction yet remain immaterial.
Directionality is not persistence: one favorable-period candidate might be
one-off. Directionality is not attribution: it does not identify why a metric
moved. Contradictory factor candidates must remain separately listed; this
policy must never create an aggregate financials, thesis, or opportunity
result.

## 8. Recommended eventual v1 scope and policy shape

The safe eventual v1 scope is **empty** until the factual trajectory contract
and its materiality, persistence, attribution, and contradiction dependencies
are separately governed. It must not use raw `ResearchMetricDelta` directly.

**U14D-6C refinement:** [Financial Metric Trajectory Policy
Proposal](FINANCIAL_METRIC_TRAJECTORY_POLICY_PROPOSAL.md) specifies why a
same-period revision is not a business trajectory and proposes a separate
factual observation/period identity boundary. The directionality-policy scope
therefore remains empty; no trajectory policy is frozen, selected, or active.

After that work, a proposed `ResearchMetricDirectionRule` could contain metric
ID, statement/domain, metric type, required trajectory basis, allowed scopes,
numeric-domain constraints, provisional factor vocabulary, prerequisites,
disqualifiers, attribution requirement, rationale, and rule version. This is a
design sketch only; no such contract, rule, fingerprint, or runtime policy now
exists.

## 9. Relationship to later policies and exclusions

Metric directionality may someday provide factor-level inputs to separate
materiality, persistence/confirmation, contradiction, thesis-interpretation,
and opportunity-interpretation policies. It cannot produce
`THESIS_STRENGTHENED`, `THESIS_WEAKENED`, `OPPORTUNITY_IMPROVED`,
`OPPORTUNITY_DEGRADED`, risk, bullish/bearish, alert, recommendation, or any
BUY/HOLD/SELL/TRIM/ROTATE/execution result.

This proposal expressly excludes stock price/returns, RSI, BBW, ATR, moving
averages, support/resistance, breakout, volume/delivery, sector RS/breadth/rank
or Top-3, market regime, setup/candidate eligibility, R:R/do-not-chase,
ownership percentages, valuation, Decision Score, diagnostic pass counts,
generic news sentiment, and generic macro direction.

**Recommended next exact slice:** governance audit/proposal for the factual
`FinancialMetricTrajectory` contract only, including revision-versus-period
classification and numeric-domain semantics. It must not implement a
directionality policy or any thesis/opportunity interpretation.

## 10. Explicit non-changes

No financial metric directionality rule, policy artifact, frozen fingerprint,
selection, activation, engine, trajectory builder, persistence, migration,
provider/network request, API, worker, listener, scheduler, alert,
recommendation, signal, order, trade, score, gate, or scanner behavior is
created or changed by this proposal.
