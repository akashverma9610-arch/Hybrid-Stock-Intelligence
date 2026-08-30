# Brain Research Comparison State Proposal

**Status: PROPOSED — NOT APPROVED — NOT SELECTED — NOT ACTIVE.**

This is a contract audit and governance proposal only.  It creates no state,
delta, policy, interpreter, persistence, migration, provider call, score,
diagnostic run, gate evaluation, recommendation, alert, signal, or execution
path.  The existing frozen objective policy remains unchanged:

`intelligence-delta-interpretation-policy / v1-approved`

`2d0572f2d29daa7e322b6a91495b142fc13a84508573338a4cd9d91ab8239b57`

## 1. Purpose and architectural decision

U14D-5A correctly found that `IntelligenceDelta` and its objective
interpretation are insufficient to express thesis or opportunity meaning.  The
smallest sound next boundary is a portfolio-independent, read-only, derived
projection of the **one Shared Brain**:

```text
canonical stored evidence
  -> UnifiedIntelligenceState(as_of)
  -> validated Shared-Brain research projection/context
  -> BrainResearchComparisonState(as_of)
```

Only a later, independently governed layer may compare two such states and
consider thesis or opportunity meaning.  This is not a Thesis Brain,
Opportunity Brain, Sell Brain, Portfolio Brain, or Scanner Brain.

The recommended name is `BrainResearchComparisonState`: it describes a state
whose contract exists specifically to make prior/current comparison possible,
does not imply a second Brain, and matches the repository's explicit
`BrainOutput...` and `BrainResearch...` naming.

## 2. Existing contracts to reuse

| Existing contract | Reuse | Why it is not sufficient alone |
| --- | --- | --- |
| `UnifiedIntelligenceState` | Canonical instrument/as-of identity, state/evidence references, completeness, blocking/degraded domains, dependency/origin lineage and deterministic fingerprint. | Deliberately bounded: it has no raw/derived research values or cross-period comparison metadata. |
| `BrainOutputRequest` | Context identifier and validated source-state linkage. | Its context can be portfolio-specific and it is a request, not a reusable research state. |
| `BrainOutputEvaluationContext` | Exact state/request/score/gate lineage checks, temporal fail-closed behavior, requirement policy identity and blockers. | Context-specific and can include `PortfolioContextRef`; does not expose research dimensions or a historical comparison basis. |
| `BrainOutputProjection` | Deterministic, sectioned read-only Shared-Brain view and its policy lineage. | Sections hold grouped evidence references, not normalized facts or per-dimension comparability. |
| `BrainResearchHandoff` / `BrainResearchIntake` | Origin/candidate lineage and the explicit `PENDING_RESEARCH` / `RESEARCH_DIAGNOSTIC` boundary. | They are intake artifacts, not completed research outputs or prior/current states. |
| `DiagnosticResult` / `DecisionScorecard` | Existing immutable, timestamped diagnostic and score lineage. | There is no durable `ResearchSnapshot`; a score or diagnostic fingerprint has no higher-order direction by itself. |
| `GovernedPreBreakoutSetupAssessment` / `PreBreakoutCandidate` | Exact governed setup/candidate facts and policy/selection lineage. | Candidate formation remains `OPPORTUNITY_CANDIDATE`, `RESEARCH_PENDING`, and not an action or opportunity conclusion. |

The future contract should reference and validate these artifacts rather than
copy provider payloads or recreate their calculation engines.

## 3. Exact gap

There is no reconstructible artifact that currently combines, for a single
instrument and PIT as-of moment:

- raw canonical fact references and deterministic derived research facts;
- research methodology/policy lineage by dimension;
- period/scope/basis parity required for later financial comparisons;
- setup/sector/technical comparability metadata;
- exact reliability and historical-integrity typed lineage; and
- a non-portfolio Shared-Brain context suitable for use across all output
  contexts.

`UnifiedIntelligenceState` deliberately cannot fill this gap: it stores
references and availability only.  `BrainOutputProjection` is closer than a
handoff because it is a deterministic view of validated context, but it is
context-specific and bounded to evidence-reference sections.  Extending it
would contaminate the existing output contract with comparative-research
responsibilities.  A new derived contract that *references* it where suitable
is smaller and safer.

## 4. Proposed state identity (not implemented)

`BrainResearchComparisonState` should be immutable and deterministically
rebuilt from supplied existing artifacts and stored-as-of sources.  Its
identity should contain, at minimum:

- `state_id`, deterministic from every semantic field;
- `canonical_instrument_id`;
- timezone-aware `as_of` and optional evaluation session/cutoff identity;
- source `unified_state_id` and `unified_state_fingerprint`;
- source `BrainOutputProjection`/evaluation-context references only when they
  are instrument/research-centric and contain no portfolio context;
- research-state schema and research methodology identity/version/fingerprint;
- the applicable diagnostic, score, setup, sector/market, technical,
  news/catalyst, financial-normalization, and valuation methodology lineage;
- canonical evidence manifests/fingerprints and origin lineage; and
- deterministic `fingerprint`.

The identifier must never depend on `datetime.now()`.  Identical stored
evidence, policies, selections, methodology and `as_of` must reconstruct the
same state.

## 5. Proposed typed nested structures

Avoid a generic untyped dictionary.  A minimal future typed shape is:

| Proposed structure | Purpose | Contains | Does not contain |
| --- | --- | --- | --- |
| `ResearchMetricObservation` | One normalized raw or deterministic derived research fact. | Domain, metric identity, value or explicit missing status, value dimension/unit/scale/currency, period/window/scope/basis, source refs, available-at and revision lineage. | “Improving”, “bullish”, thesis or opportunity terms. |
| `ResearchDimensionState` | One named fact family. | Canonical sorted observations, availability/freshness/reliability/integrity refs, methodology lineage, warnings and dimension fingerprint. | A direction or recommendation. |
| `ResearchComparabilityDescriptor` | What must match before this dimension can be compared. | Identity, metric/basis/scope/window/methodology/schema/reference rules and status/rationale code. | A result of a future comparison. |
| `BrainResearchComparisonState` | One Shared-Brain research read projection at one as-of moment. | State identity, source Unified State lineage, sorted dimension states, descriptors, policy/methodology lineage, completeness/blockers and fingerprint. | Portfolio data, trade plan, score interpretation, thesis/opportunity/recommendation/action. |

Where existing evidence is only bounded lineage, the state must retain a
reference and an explicit unavailable/partial descriptor instead of copying or
inventing a value.

## 6. Thesis-relevant dimensions

The future state may expose factual, non-directional observations for:

- **Financial and business:** revenue, other income, EBITDA/operating profit
  only when directly reported, EBIT, PBT, PAT, EPS, assets, liabilities,
  equity/net worth, debt, cash, working-capital fields, CFO/CFI/CFF/capex and
  factual valuation inputs where a comparable canonical contract actually
  exists.
- **Earnings record:** quarterly, annual, TTM and point-in-time period
  identity; consolidated/standalone scope; value basis; quality flags;
  publication/receipt/revision lineage.  It may carry a deterministic
  multi-period input only when its calculation version and parent fact IDs are
  retained.
- **Ownership:** exact disclosed holdings only if they become normalized,
  PIT-visible facts.  Current Unified-State ownership projection is disclosure
  lineage and explicitly warns `SHAREHOLDING_FACTS_NOT_MATERIALIZED`.
- **Catalyst and corporate actions:** typed event/action identity, source
  quality, confirmation/filing-match facts, event/publication/retrieval dates,
  materiality observations, priced-in state and revision lineage.  These are
  facts, not causal or directional meanings.
- **Company/sector transmission context:** only typed macro/sector facts with
  explicit methodology and attributable company relation where such a contract
  exists.

There is no authority in this proposal to translate any of these values into a
business or thesis conclusion.

## 7. Opportunity-relevant dimensions

The state may separately expose factual, non-directional observations for:

- **Market context:** stored market-regime result, benchmark identity, as-of,
  rule/methodology lineage and input evidence references.
- **Sector context:** PIT taxonomy identity, sector membership, official
  constituent lineage, RS/breadth/Top-3 facts only when a durable as-of source
  exists, and exact benchmark/lookback/sector methodology.
- **Technical/RS/volume:** price-basis/integrity references, indicator
  identity/version/lookback/window, relative-strength benchmark and sector
  basis, official delivery/volume evidence where stored and PIT-visible.
- **Governed setup:** assessment status/blockers, selected policy/selection
  lineage, base/support/resistance/trigger/stop/target/tick/R:R and
  do-not-chase facts only from the existing governed structural artifact.
- **Candidate boundary:** candidate ID/fingerprint and research-pending state,
  never a converted opportunity direction.
- **Valuation/entry:** only canonical observations that already have a defined
  metric, scope, basis and methodology.  No valuation semantic is manufactured
  by this state.

## 8. Per-dimension comparability and version drift

Comparability must be **dimension-specific**.  An incompatible setup-policy
change must not erase a compatible financial comparison; it makes only setup
and dependent opportunity dimensions `NON_COMPARABLE`.

| Dimension | Must match before prior/current comparison | Drift behavior |
| --- | --- | --- |
| Financial/earnings | Instrument, metric, currency, value dimension, unit, scale, scope, value basis, fiscal-period alignment, normalization version, revision policy, corporate-action treatment where relevant. | Scope, basis, normalization/schema or unit/scale mismatch: that metric/dimension `NON_COMPARABLE`. |
| Deterministic derived facts | Exact parent facts, derivation/calculation version and window. | Changed parents/version/window: derived dimension `NON_COMPARABLE`; preserve raw facts separately. |
| Technical/price | Session basis, adjustment basis, price-integrity status, lookback/window, indicator version, calendar and corporate-action treatment. | Methodology, lookback or adjustment drift: technical dimension `NON_COMPARABLE`. |
| Sector/RS/breadth | Sector taxonomy, constituent membership PIT, benchmark, RS/breadth methodology, lookback/window and source coverage. | Benchmark/taxonomy/methodology drift: sector dimension `NON_COMPARABLE`. |
| Setup | Exact selected policy ID/version/fingerprint, selection lineage, tick-reference lineage and structural methodology. | Any policy/fingerprint change: setup dimension `NON_COMPARABLE`. |
| News/catalyst | Event identity, schema/type, source authority, publication/availability time, confirmation/filing link, revision treatment. | New event is an addition; changed schema/classification is not the same event and is `NON_COMPARABLE` unless later governance defines it. |
| Diagnostics/score | Strategy/registry/configuration version, component/rule identities, missing-evidence policy, score mapping/weights, confidence semantics and exact source bundle. | Policy/version/component/missing-data drift: score/diagnostic dimension `NON_COMPARABLE`. |

State-wide identity/source-state mismatch is state-invalid.  Methodology drift
within a dimension is a dimension-local non-comparability result by default;
future governance may declare dependent dimensions non-comparable explicitly.

## 9. Missing, stale, conflicted, unreliable, and invalid evidence

Each dimension must retain a typed availability and its evidence references:
`AVAILABLE`, `PARTIAL`, `UNAVAILABLE`, `STALE`, `CONFLICTED`, or
`NOT_APPLICABLE`, plus freshness policy, reliability reference, historical
integrity reference and warnings where present.  Missing evidence is never
zero.  Conflicts are never resolved by choosing a best guess.  Current evidence
must never be used to populate a historical `as_of` state.

`HistoricalIntegrityStatus.INVALID` is currently projected as Unified-State
`CONFLICTED`; a future state should preserve the native typed integrity artifact
when supplied, rather than reverse-engineering it.  Likewise, a reliability
availability projection is not a substitute for the stored typed reliability
decision.  Missing typed lineage yields `INSUFFICIENT` or `NON_COMPARABLE`, not
direction.

## 10. Decision Score treatment

Retain an existing `DecisionScorecard` as a **bounded typed reference plus its
factual contents**, but not as an overall research conclusion.  Where supplied
and matched to the Unified State, preserve final score, score status,
confidence, component IDs/statuses/scores/weights, available/missing rules,
diagnostic/evidence IDs, strategy/registry/configuration versions, as-of,
evaluated-at and the canonical scorecard fingerprint.

It is deliberately absent where no stored scorecard is supplied.  A scorecard
delta alone remains non-directional.  A policy or coverage mismatch makes the
score dimension non-comparable without invalidating compatible raw research
dimensions.

## 11. 61-diagnostic treatment

The state should retain a sorted typed bundle reference plus individual
`DiagnosticResult` identity/result/score/confidence/as-of/evaluated-at and
evidence/input IDs when an existing durable bundle is supplied.  It must also
carry registry and strategy version and whether the expected 61-rule bundle is
complete.  The current adapter explicitly warns both
`DIAGNOSTIC_61_BUNDLE_PARTIAL` where appropriate and
`RESEARCH_DURABLE_READ_BOUNDARY_MISSING`; it must not be represented as a
complete research conclusion.

The state must not launch a diagnostic run, rescore, select a subset to create
a hidden thesis signal, or treat diagnostic fingerprint change as direction.

## 12. Pre-Breakout treatment

Preserve the established chain exactly:

```text
GovernedPreBreakoutSetupAssessment
  -> candidate formation
  -> PreBreakoutCandidate
  -> BrainResearchHandoff
```

The state may carry objective assessment/candidate facts and their exact
policy/selection/tick lineage.  It must preserve the candidate's
`OPPORTUNITY_CANDIDATE`, `RESEARCH_PENDING`, `brain_evaluation_required`, and
`NOT_EVALUATED_AT_SCAN` execution boundary.  Candidate existence is never
encoded as `OPPORTUNITY_IMPROVED` and never as BUY.

## 13. Six Gates treatment

Do not include actual Six Gates outcomes in the core portfolio-independent
state.  The proposed state may retain the same bounded gate lineage/reference
already carried by Unified State only for audit completeness, marked
context-dependent and downstream-only.  It must not fabricate a gate result
or flatten outcome changes into research direction.

Portfolio-specific gates, including rotation, velocity, heat/allocation and
any evaluation bound to an input portfolio snapshot, remain downstream.

## 14. Portfolio firewall

`BrainResearchComparisonState` is instrument/research-centric.  It excludes
holding quantity, cost basis, weight, realized/unrealized P&L, replacement
candidate, tax/friction, capital availability, portfolio heat and concentration.
It must be usable unchanged by Opportunity Discovery, Deep Analysis, Portfolio
Review, Sell/Trim Review, Rotation Review, Entry Setup Review and Alert Review.

Only a later contextual recommendation/execution boundary may combine a
research-state reference with an independently fingerprinted
`PortfolioContextRef`.

## 15. Historical rebuildability

The state should be non-persisted and rebuilt at `as_of` from stored sources:

| Dimension/source | PIT rebuildability now |
| --- | --- |
| Official financial facts, filings, corporate actions, news metadata and eligible catalyst artifacts | Rebuildable only to facts whose publication/receipt/availability is at or before `as_of`; revision lineage remains explicit. |
| Historical identity, taxonomy, tick references and historical integrity | Rebuildable where the relevant as-of store/resolver has immutable source intervals/results. |
| Stored reliability decision | Rebuildable only when a durable decision with eligible observed/available/evaluation time exists. |
| Stored diagnostic results and explicitly supplied scorecard | Rebuildable only from durable exact artifacts and versions; current repository has no durable full `ResearchSnapshot`. |
| Governed setup assessment | Rebuildable where persisted assessment evidence exists; candidate is deliberately reconstructible rather than persistently materialized. |
| Current sector rotation, RS/breadth, and current technical materialization | **Not generally historical-rebuildable today**: the non-company adapter explicitly excludes current-only sector rotation/non-durable technical materialization from its stored-only boundary. |
| Ownership percentages and complete valuation facts | **Not generally rebuildable today**: current ownership projection is disclosure lineage, and no governed comparable valuation-state contract exists. |

A rebuilt historical state may therefore be partial.  It must never be filled
from later evidence to appear complete.

## 16. Persistence recommendation

**Do not persist this state.**  It should be a pure, immutable,
deterministically rebuildable projection like `UnifiedIntelligenceState` and
the existing output projection/context contracts.  Performance caching, if
ever needed, is a separate non-canonical concern and must not become an
authoritative database table merely for convenience.

The separately proposed
[`brain-research-comparability-policy`](BRAIN_RESEARCH_COMPARABILITY_POLICY_PROPOSAL.md)
owns future pairwise parity rules.  This state preserves factual observations
and methodology/dependency lineage; it must not independently define whether
two states are comparable.

## 17. Future comparison architecture

Introduce a future factual intermediate `ResearchStateDelta`, rather than
feeding prior/current state directly into a thesis/opportunity interpreter:

```text
previous BrainResearchComparisonState
  -> compare_brain_research_states(previous, current)
  -> ResearchStateDelta (factual per-dimension comparable deltas only)
  -> separately governed thesis/opportunity interpreter
```

This keeps comparability, missing/stale/conflicted handling, and version drift
objective and testable before a later policy adds semantic interpretation.  It
also prevents the thesis/opportunity layer from silently recomputing research
facts.  Neither the state nor delta is implemented or approved by this
proposal.

## 18. Proposed policy family

Create a separate future `brain-research-comparability-policy` family.  Its
first inactive draft is documented in
[`BRAIN_RESEARCH_COMPARABILITY_POLICY_PROPOSAL.md`](BRAIN_RESEARCH_COMPARABILITY_POLICY_PROPOSAL.md).
It should freeze schema version, dimension catalogue, source eligibility,
normalization/derivation versions, metric scope/basis alignment, lookbacks,
revision treatment, methodology-parity rules, missing/conflict handling and
dimension dependency rules.  It must not reuse the objective delta policy,
which governs unrelated availability/freshness/reliability/integrity semantics.

The future thesis/opportunity interpretation policy remains yet another policy
family layered only after this factual comparison boundary.

## 19. Unresolved questions requiring later governance

1. Exact canonical definition and source policy for valuation facts.
2. Whether and how shareholding percentages/pledges are normalized as
PIT-visible facts.
3. The durable as-of contract for sector RS/breadth/current technical evidence.
4. The canonical durable Shared-Brain research result/snapshot contract.
5. Which derived financial metrics and corporate-action basis are admissible.
6. The minimum corroboration required by each future thesis/opportunity rule.
7. How revisions/restatements are compared without hindsight.

## 20. Explicit non-changes

No Brain research state, research-state delta, thesis interpreter, opportunity
interpreter, policy approval/selection/activation, persistence, migration,
alert, recommendation, BUY/HOLD/SELL/TRIM/ROTATE, execution, portfolio field,
provider call, worker, scheduler, Decision Score run, 61-diagnostic run, Six
Gates run, scanner threshold, or Pre-Breakout semantic has been implemented or
modified.

## 21. Audit sources

This proposal is grounded in the current read-only/immutable boundaries:

- `app/intelligence/unified_state.py`
- `app/intelligence/unified_state_builder.py`
- `app/intelligence/intelligence_delta.py`
- `app/intelligence/output_evaluation_context.py`
- `app/intelligence/output_projection.py`
- `app/intelligence/company_evidence.py`
- `app/intelligence/non_company_evidence.py`
- `app/intelligence/governed_setup_evidence.py`
- `app/intelligence/macro_news_evidence.py`
- `app/intelligence/research_diagnostic_evidence.py`
- `app/intelligence/decision_score_evidence.py`
- `app/intelligence/six_gates_evidence.py`
- `app/fundamentals/models.py`, `app/analysis/fundamentals.py`
- `app/analysis/market_regime.py`, `app/analysis/relative_strength.py`
- `app/market_data/current_sector_rotation.py`, `app/market_data/current_prebreakout.py`
- `app/strategies/pre_breakout/setup_assessment.py`,
  `app/strategies/pre_breakout/candidate_assembly.py`
- `app/research/handoff.py`, `app/research/intake.py`
- `app/news/models.py`, `app/intelligence/catalysts/service.py`, and
  `app/gates/engine.py`

## 22. Financial observation integration follow-up

The existing `FINANCIAL_RAW` dimension still carries Unified-State artifact
references plus explicitly supplied generic observations only. The proposed,
non-active financial-observation handoff, selector-as-of attestation,
period-collision safeguards, and future state-version transition are documented
in [BRAIN_RESEARCH_FINANCIAL_OBSERVATION_INTEGRATION_PROPOSAL.md](BRAIN_RESEARCH_FINANCIAL_OBSERVATION_INTEGRATION_PROPOSAL.md).
