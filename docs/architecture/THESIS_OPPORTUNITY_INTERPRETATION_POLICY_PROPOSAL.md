# Thesis and Opportunity Interpretation Policy Proposal

**Status: PROPOSED — NOT APPROVED — NOT SELECTED — NOT ACTIVE.**

> **Historical lineage.** U14D-6A refines this earlier proposal against the
> implemented factual `ResearchStateDelta`; see
> [Thesis / Opportunity Directional Semantics Proposal](THESIS_OPPORTUNITY_DIRECTIONAL_SEMANTICS_PROPOSAL.md).
> This document remains historical governance lineage and neither document
> freezes, selects, or activates an interpretation policy.

This is a governance audit and design proposal only.  It creates no policy
artifact, interpreter, persistence, alert, recommendation, signal, order, or
runtime wiring.  It does not modify the frozen objective interpretation policy:

`intelligence-delta-interpretation-policy / v1-approved`

`2d0572f2d29daa7e322b6a91495b142fc13a84508573338a4cd9d91ab8239b57`

That policy remains approved, not selected, and not active.

## 1. Architectural finding

Neither `IntelligenceDelta` nor `IntelligenceDeltaInterpretation` is a safe
source for `THESIS_STRENGTHENED`, `THESIS_WEAKENED`,
`OPPORTUNITY_IMPROVED`, or `OPPORTUNITY_DEGRADED`.

`UnifiedIntelligenceState` intentionally retains bounded domain references,
availability, timestamps, freshness, provenance, integrity references, and
fingerprints; it does not copy raw facts, a research conclusion, a score, a
decision, or portfolio ownership.  The objective interpreter intentionally
emits only objective availability/freshness/reliability/integrity vocabulary.
It has no thesis, opportunity, risk, recommendation, or execution semantic.

The existing `BrainResearchHandoff` makes the missing boundary explicit: it is
only a `PENDING_RESEARCH` request for `RESEARCH_DIAGNOSTIC`.  It is not a
durable prior/current Brain research state.  Therefore a future higher-order
interpreter needs a separately governed, immutable, reconstructible research
comparison contract.  It must not be appended to the objective interpreter or
inferred from a fingerprint change.

## 2. Meaning boundary

| Concept | Proposed meaning | Explicitly not the concept |
| --- | --- | --- |
| Thesis | Change in the material underlying research/business case, supported by comparable company, sector, and durable-catalyst evidence. | Price movement, a technical indicator, scanner visibility, entry geometry, or a candidate alone. |
| Opportunity | Change in the attractiveness or timeliness of research exposure under a governed Brain context. | A trade instruction, a substitute for thesis, or a generic positive/negative result. |

The model must support independent results.  A comparable improvement in
fundamental evidence can coexist with an overextended price/setup and hence a
worse opportunity.  Conversely, unchanged research evidence can coexist with
a better governed setup.  Neither combination carries a recommendation.

## 3. Actual evidence inventory

### Potential thesis-comparison inputs

| Existing boundary | What exists | Present sufficiency for directional thesis |
| --- | --- | --- |
| `app/fundamentals/models.py` | Immutable reported/derived facts for revenue, operating profit/EBITDA, PBT/PAT/EPS, assets, liabilities, debt, cash, working-capital items, CFO/CFI/CFF/capex; period, scope, scale, dimension, publication/receipt, revision and quality lineage. | Raw facts are potentially suitable only after exact same-metric/scope/basis/unit/scale/PIT comparison is governed. |
| `app/analysis/fundamentals.py` | Existing analysis helpers for trends, ratios, cash flow, leverage, working capital, ownership, earnings acceleration, latest quarter and margins. | Existing diagnostic-facing analysis, not a persisted thesis state or governed directional comparison. |
| `app/intelligence/company_evidence.py` | Stored-only FUNDAMENTALS/EARNINGS references and official-source availability; corporate-action and filing lineage. | Bounded metadata only; it deliberately does not carry values or materialize shareholding percentages. |
| `app/news/models.py` and `app/intelligence/catalysts/service.py` | Typed event categories/types, source quality, dates, primary confirmation, filing match, materiality observation and unknown/not-assessed priced-in state. | Semantic event evidence, not positive/negative market direction or a thesis conclusion. |
| `app/intelligence/macro_news_evidence.py` | PIT-visible official disclosures, news metadata and catalyst lineage. | Evidence authority/availability only; no causal impact verdict. |

There is no present governed research/thesis snapshot with prior/current
conclusions, comparison policy, or a durable adjudication of causality.

### Potential opportunity-comparison inputs

| Existing boundary | What exists | Present sufficiency for directional opportunity |
| --- | --- | --- |
| `app/analysis/market_regime.py` | Typed market-regime result with as-of evidence and status. | A market input only; regime changes are not an exposure instruction. |
| `app/analysis/relative_strength.py` | Benchmark/sector return, excess return and leader/emerging/laggard classification. | A comparable technical input only when benchmark, lookback, history and methodology match. |
| `app/market_data/current_sector_rotation.py` | Stored-only sector RS, breadth and existing Top-3 scan composition. | Sector context only; a Top-3 change is not sufficient candidate-level opportunity meaning. |
| `app/strategies/pre_breakout/setup_assessment.py` | Governed setup status, blockers, sector membership, technical and structural inputs. | A candidate-formation boundary, not a recommendation or Brain conclusion. |
| `app/strategies/pre_breakout/candidate_assembly.py` | Immutable candidate with base, trigger, support, stop, target, R:R, tick/policy lineage.  It enforces `CANDIDATE_GENERATED`, `RESEARCH_PENDING`, `brain_evaluation_required`, and no evaluated execution price. | The strongest existing setup input, but deliberately still a research-pending opportunity candidate. |
| `app/market_data/current_prebreakout.py` | Stored-only delivery/technical scan reporting. | Convenience reporting; it does not govern a thesis or exposure decision. |

No durable canonical Brain opportunity state currently combines these inputs
with research quality, valuation comparability, liquidity, reliability, and
context requirements.

### Diagnostic, score, and gate lineage

`DiagnosticResult` is typed and timestamped.  The current research adapter
projects only a selected durable diagnostic bundle and explicitly warns that a
durable research read model is missing.  `DecisionScorecard` has components,
diagnostic/evidence lineage, configuration/registry/strategy versions, score
status and confidence.  The Unified State adapter projects only bounded score
lineage and marks incomplete scores `PARTIAL`.

The Six Gates adapter deliberately projects a `PARTIAL`,
`SIX_GATES_CONTEXT_DEPENDENT`, downstream-only artifact.  The gate engine's
rotation, velocity, heat, and earnings-blackout decisions depend respectively
on existing holdings, portfolio risk/allocation, replacement economics, or
execution timing; those are not thesis facts and are not universally
portfolio-independent opportunity facts.

## 4. Mandatory comparison validity

Every future rule must first emit `NON_COMPARABLE` or `INSUFFICIENT` unless all
applicable requirements are proven by immutable source references:

1. Same canonical instrument and unambiguous identity.
2. Prior and current evidence are visible at their respective as-of times;
   publication, receipt, revision, and first-observed lineage preserve PIT.
3. Exact metric/definition, value dimension, currency, unit and scale parity;
   EPS/per-share data must never be compared as monetary data.
4. Same report scope and value basis (for example, consolidated quarterly-only
   versus consolidated quarterly-only), with governed fiscal-period alignment.
5. A frozen comparison methodology, data-window definition, source policy and
   schema version are equal.  Any change to diagnostic registry, Decision Score
   configuration, fundamental normalization/model, setup policy, sector model,
   evidence schema, or source methodology is `NON_COMPARABLE` by default.
6. Required corroborating domains are sufficiently available, fresh, reliable,
   and historically intact under separately governed policy.  Objective
   freshness/reliability/integrity results do not supply a thesis/opportunity
   direction by themselves.
7. Required evidence is not conflicted, partial, stale, revised without a
   governed revision treatment, or missing for the particular rule.

Recommended future evidence-sufficiency values are the existing vocabulary:
`SUFFICIENT`, `INSUFFICIENT`, `NON_COMPARABLE`, and `NOT_APPLICABLE`.  A
single-domain observation must not be promoted to a thesis/opportunity
conclusion where the future rule requires corroboration.

## 5. Thesis rule-candidate audit

| Candidate | Necessary evidence and comparison preconditions | Corroboration / risk | Disposition |
| --- | --- | --- | --- |
| Durable earnings acceleration/deceleration | Multi-period, PIT-visible, same-scope quarterly or annual facts; explicit YoY/QoQ/TTM rule; direct metrics and revision treatment. | Multi-period and at least profitability/cash-flow or balance-sheet corroboration.  One quarter risks base effects and accounting timing. | NEEDS_MORE_GOVERNANCE |
| Margin/profitability change | Same revenue and operating-profit/EBITDA definition, period basis, scale and scope; no derived EBITDA unless the future policy expressly permits it. | Needs earnings trend and quality/revision corroboration; definition drift is material. | NEEDS_MORE_GOVERNANCE |
| Leverage improvement/deterioration | Same balance-sheet date/scope and directly reported debt, cash/equity/liabilities facts. | Needs cash-flow and financing-context corroboration; debt changes may fund value-creating investment. | NEEDS_MORE_GOVERNANCE |
| Cash-flow confirmation/failure | Comparable CFO/capex/free-cash-flow facts with period basis and working-capital treatment. | Needs earnings and balance-sheet confirmation; a single period can be seasonal. | NEEDS_MORE_GOVERNANCE |
| Corporate-action event | Exact official action, PIT dates and revision lineage. | Corporate actions primarily affect identity/price comparability; event type itself is not a thesis direction. | REJECT as direct thesis direction |
| Promoter/FII/DII/public/pledge change | Current store has disclosure lineage but does not materialize normalized holding percentages in the Unified-State adapter. | Requires exact normalized ownership facts, period alignment, disclosure revisions and a human-governed interpretation. | NEEDS_MORE_GOVERNANCE |
| Sector structural change | Comparable sector/macro evidence, company transmission mechanism and time horizon. | Sector movement alone may not describe the company. | NEEDS_MORE_GOVERNANCE |
| Material catalyst/adverse event | Primary issuer/exchange confirmation, filing match, exact event/PIT lineage, financial materiality, horizon and causal link to the pre-existing research claim. | Generic news, `UNCERTAIN` impact and `UNKNOWN` priced-in state are insufficient. | NEEDS_MORE_GOVERNANCE |
| Price/technical/setup-only transition | Price, BBW, RS, base, trigger or candidate only. | Not underlying business-case evidence. | REJECT |

No current thesis candidate is safe to approve: the repository has valuable
typed inputs but no approved research-state/comparison semantics.

## 6. Opportunity rule-candidate audit

| Candidate | Minimum additional Brain context | Main false-positive / leakage risk | Disposition |
| --- | --- | --- | --- |
| Governed Pre-Breakout assessment becomes eligible | Exact selected setup policy and assessment lineage, plus current reconstructible Brain research state, research completeness, liquidity/valuation and reliability eligibility. | `ELIGIBLE_TO_FORM_CANDIDATE` only permits formation; candidate assembly explicitly requires later Brain research. | NEEDS_MORE_GOVERNANCE |
| Setup loses eligibility / support breach / do-not-chase breach | Same selected setup policy, structural provenance, comparable price session and current research state. | A technical failure is not automatically a thesis failure or sell recommendation. | NEEDS_MORE_GOVERNANCE |
| Trigger proximity / entry R:R enters or exits range | Same tick reference, entry economics, policy version, session and no execution-price substitution. | Can leak an execution instruction; it must remain pre-execution analytic context. | NEEDS_MORE_GOVERNANCE |
| Sector enters/leaves Top-3 or RS changes | Comparable official membership, benchmark, lookback, breadth coverage and sector model/version, plus company-level research context. | Sector rank alone ignores company evidence and may not be comparable after universe/model changes. | NEEDS_MORE_GOVERNANCE |
| Market regime changes | Same regime policy, data coverage and as-of context, combined with company/setup/reliability context. | Regime is market context, not a candidate decision. | NEEDS_MORE_GOVERNANCE |
| Valuation becomes more/less favorable | A future governed valuation evidence contract with comparable basis, price timestamp and estimate/fundamental scope. | No present governed valuation-comparison state. | NEEDS_MORE_GOVERNANCE |
| Candidate/fingerprint appears, disappears, or changes | Artifact identifier/fingerprint alone. | Fingerprints describe identity/tamper lineage, not direction. | REJECT |

No present opportunity candidate is safe to approve as a higher-order
interpretation.  The existing candidate is intentionally a bounded research
handoff input, not a substitute for the requested Brain context.

## 7. Decision Score treatment

`Decision Score 8.1 → 8.7` alone means neither `THESIS_STRENGTHENED` nor
`OPPORTUNITY_IMPROVED`.  It can be compared only after a future policy proves:

- identical strategy, registry and score-configuration versions;
- equal score normalization and component weights/state mapping;
- equal or explicitly governed missing-evidence treatment;
- equal coverage/completeness and comparable confidence semantics;
- component-level predecessor/current lineage; and
- no unsupported change in source methodology, diagnostic meaning or policy.

A scorecard fingerprint change is identity/provenance information only.  It is
non-directional, and a partial or incomplete score is not silently comparable.

## 8. News and catalyst treatment

The repository has `NewsEventCategory`, `CatalystType`, source quality,
filing-match/primary-confirmation flags, materiality observations and
PIT-visible timestamps.  It has no approved bullish/bearish or
positive/negative classifier.  A future thesis policy may allow a confirmed,
material, attributable event to corroborate an already-defined research fact,
invalidate a claim, or create a `RESEARCH_REQUIRED` state.  It must not infer
market direction from generic news, a headline, an event type, unknown
priced-in state, or secondary-source metadata.

## 9. Six Gates treatment

Six Gates should not participate in thesis interpretation.  They may be
downstream inputs to a future contextual recommendation or execution
authorization boundary only after a separate governed opportunity/research
result exists.  The actual gate result carries action context and can depend
on portfolio holdings, rotation comparison, heat/allocation, surveillance,
trade plan and earnings timing.  Therefore no generic gate pass/fail transition
is a reusable opportunity direction, and no Six Gates result authorizes an
action here.

## 10. Proposed future contracts (not implemented)

Create a **separate policy family**, not an extension of the frozen objective
policy, only after later human governance.  The minimal design should use two
independent immutable artifacts:

### `ThesisInterpretation`

Required future inputs: prior/current reconstructible `BrainResearchState`,
their exact evidence manifests and policy/methodology fingerprints, approved
objective interpretation references, immutable typed comparison evidence,
comparison as-of timestamps, sufficiency/comparability outcome, and the
separate thesis-policy identity/fingerprint.  It should be portfolio-independent.

### `OpportunityInterpretation`

Required future inputs: prior/current reconstructible governed opportunity or
candidate/setup state, the same research-state boundary, market/sector/RS and
technical/entry-economics references, selected setup-policy lineage, data
freshness/reliability/integrity eligibility, and a separate opportunity-policy
identity/fingerprint.  It should remain portfolio-independent through research
and setup interpretation.  A later recommendation/rotation/execution layer,
not this contract, may attach a separately fingerprinted portfolio context.

Both future contracts must preserve prior/current identities, instrument,
as-of timestamps, typed supporting references, objective interpretation
references, evidence sufficiency, non-comparable rationale, policy lineage,
and deterministic fingerprints.  Neither contract should contain a BUY, HOLD,
SELL, TRIM, ROTATE, alert, target allocation, order, or execution field.

## 11. Recommendation and alert firewall

The following equivalences are prohibited:

- `THESIS_STRENGTHENED = BUY`
- `THESIS_WEAKENED = SELL`
- `OPPORTUNITY_IMPROVED = BUY`
- `OPPORTUNITY_DEGRADED = SELL`

Evidence change, objective interpretation, thesis/opportunity interpretation,
alert authorization, contextual recommendation and execution authorization are
separate future stages.  No stage may be silently skipped.  A stronger thesis
can still have adverse valuation, poor R:R, overextension, a failed gate or a
portfolio-concentration constraint; a weaker thesis may still only require
monitoring or further research.  This proposal authorizes none of those
outcomes or alerts.

## 12. Explicit non-changes

No code, policy artifact, persistence, selection, activation, objective
interpreter behavior, state builder, Brain output, diagnostic execution,
Decision Score, Six Gates, scanner, portfolio logic, provider call, worker,
scheduler, alert, recommendation, signal, trade, order, or strategy threshold
is changed by this proposal.

## 13. Audit sources

The proposal was derived from the bounded existing contracts in:

- `app/intelligence/unified_state.py`
- `app/intelligence/intelligence_delta.py`
- `app/intelligence/intelligence_delta_interpretation.py`
- `app/intelligence/company_evidence.py`
- `app/intelligence/macro_news_evidence.py`
- `app/intelligence/research_diagnostic_evidence.py`
- `app/intelligence/decision_score_evidence.py`
- `app/intelligence/six_gates_evidence.py`
- `app/fundamentals/models.py` and `app/analysis/fundamentals.py`
- `app/analysis/market_regime.py` and `app/analysis/relative_strength.py`
- `app/market_data/current_sector_rotation.py` and `app/market_data/current_prebreakout.py`
- `app/strategies/pre_breakout/setup_assessment.py` and `app/strategies/pre_breakout/candidate_assembly.py`
- `app/research/handoff.py`
- `app/news/models.py`, `app/intelligence/catalysts/service.py`, and `app/gates/engine.py`

## 14. Required future governance before implementation

Before any implementation, a human-approved proposal must freeze: the exact
thesis and opportunity vocabularies; each admissible metric/event transition;
minimum corroboration; comparison windows; source/quality/revision handling;
methodology parity; conflict/partial/stale behavior; evidence-sufficiency
rules; portfolio boundary; audit/reconstruction requirements; and explicit
non-action wording.  That is a new governance task, not an implication of this
document.
