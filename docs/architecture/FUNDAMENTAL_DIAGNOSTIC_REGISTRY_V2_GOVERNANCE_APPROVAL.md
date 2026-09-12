# Fundamental Diagnostic Registry V2 — Governance Approval Receipt

**Decision B: `GOVERNANCE_APPROVED_WITH_ACTIVATION_BLOCKERS`.**
**V1 active: true. V2 active: false.**

This is the human-readable governance review of the immutable
[V2 proposal](FUNDAMENTAL_DIAGNOSTIC_REGISTRY_V2_PROPOSAL.md) and its
[machine definition](FUNDAMENTAL_DIAGNOSTIC_REGISTRY_V2_PROPOSED.json).
The [approval artifact and blocker register](FUNDAMENTAL_DIAGNOSTIC_REGISTRY_V2_GOVERNANCE_APPROVAL.json)
records the exact conditions. The original proposal remains `PROPOSED` with
its original bytes and fingerprint; this separate receipt records the decision.

## Authority, identity and scope

| Field | Verified value |
|---|---|
| Accepted source commit | 60e8529249961d8eb8fa8a287fd81ea8c0f0bce6 |
| Candidate | diagnostic-registry-v2-proposed |
| Parent | diagnostic-registry-v1 |
| Candidate fingerprint | sha256:668005237acd727ead86b19fca11a0fe9a1f640291dbe647a02cab989774a261 |
| Approver policy/version | fundamental-diagnostic-registry-v2-governance-review / v1 |
| Review authority | User-delegated bounded governance review; directive c0933e5a-e8b1-4cd6-8b47-b22345ec46d2 |
| Reviewer | Codex architecture/governance reviewer |
| Signature status | No human signature or named-person attestation is claimed |
| Approval scope | The six semantic definitions and the conditions in this receipt |
| Runtime approval/registration | None; active=false; runtime_effective_at=null |
| Universe | Exactly IDs 1–61; changes limited to 16, 17, 19, 25, 26, 29; 55 inherit exact V1 |

The user's directive authorizes this governance determination. This receipt
does not impersonate the human reviewer named in older Core V1 approvals.
It is not a database approval event, strategy selection, runtime effective-time
record, or authorization to activate V2. Its fingerprint is content identity,
not a digital signature.

## Independent integrity result

The candidate fingerprint was recomputed using explicit UTF-8, canonical JSON,
sorted keys, compact separators, ASCII escaping and `allow_nan=false`.
Exactly 61 unique ordered IDs exist, with no Rule 62. All 61 parent-definition
fingerprints match the full V1 dataclass metadata; the 55 inherited rows have
no semantic override. The V1 registry, evaluators, score, synthesis and horizon
source pins still match their parent Git blobs.

The original proposal's two documentation files and test file are separately
pinned in the approval artifact. The tracked production `app/` tree contains
543 files at this checkpoint; their physical content was captured before this
review for the final no-change check. No proposal is wired to runtime.

## Rule-by-rule governance decisions

### Rule 16 — APPROVE

Candidate name: **Five-Year Financial Trend — Revenue, PAT and EPS CAGR**.

The explicit Revenue/PAT/EPS name matches the three core measurements and preserves true five-year mathematics.

- Six consecutive comparable FULL_YEAR observations per metric, spanning five fiscal intervals; five observations never suffice.
- Positive endpoints are required for this CAGR convention; invalid-domain signed values remain descriptive, never zero-filled or N/A.
- Source-qualified EBITDA stays optional; V1 four-component verdicts and thresholds are not transferred.

Not approved by this receipt: operating-earnings derivation; automatic V1 four-to-three scoring/threshold transfer.

Activation prerequisites: `B01`, `B02`, `B03`, `B04`, `B10`, `B14`, `B15`.

### Rule 17 — APPROVE

Candidate name: **Entity-Aware Return Efficiency — ROE and Qualified ROCE**.

Independent standard ROE preserves return-efficiency evidence while qualified ROCE cannot be inferred from a missing or issuer-specific numerator.

- Annual PAT and exact beginning/end equity must have compatible attribution, scope and periods; mean equity positive; no ending-only fallback.
- Missing ROCE is policy/data unavailable, never N/A for absence alone; ready ROE does not establish complete ROCE/ROE coverage.
- Financial-sector branches remain blocked; reported ROE/ROCE require formula-matched corroboration contracts.

Not approved by this receipt: new ROCE formula; industrial ROCE for BANK/NBFC/INSURER; name-based reported ratio equivalence.

Activation prerequisites: `B01`, `B02`, `B03`, `B04`, `B05`, `B06`, `B10`, `B14`, `B15`.

### Rule 19 — APPROVE

Candidate name: **Entity-Aware Leverage — Debt/Equity, Net Debt and Qualified Interest Coverage**.

Debt/equity core, net debt and interest coverage answer different questions; explicit completeness prevents debt/equity alone implying financial health.

- Debt/equity alone yields CORE_READY_OPTIONAL_INCOMPLETE when net debt or coverage is unavailable; full_rule_ready=false and economic_verdict=null.
- Exact debt definition and same-end positive equity remain prerequisites; ready observations do not invent unavailable debt/cash/interest facts.
- Net debt and interest coverage retain their own policy/data states; adverse or conflicting optional evidence stays visible.
- DSCR is a separate measure and can never replace interest coverage.

Not approved by this receipt: whole-rule HEALTHY from core readiness; new net-debt boundary policy; new interest-coverage numerator/denominator policy; DSCR substitution.

Activation prerequisites: `B01`, `B02`, `B03`, `B04`, `B05`, `B06`, `B10`, `B14`, `B15`.

### Rule 25 — APPROVE

Candidate name: **Latest Quarterly Results — Revenue, PAT and EPS YoY & QoQ**.

Complete Revenue/PAT/EPS comparisons preserve quarterly-results purpose; optional EBITDA is not a universal core prerequisite.

- Five consecutive QUARTER_ONLY observations establish exact q/q-1 and q/q-4 comparisons; YTD and nearest-quarter substitutions are forbidden.
- All three positive-domain YoY/QoQ pairs are needed for core completeness; one surviving component remains partial.
- Missing optional EBITDA reduces optional coverage only; no zero-fill or score renormalization.

Not approved by this receipt: organic/one-off inference; negative-base growth convention; automatic earnings-acceleration verdict.

Activation prerequisites: `B01`, `B02`, `B03`, `B04`, `B10`, `B14`, `B15`.

### Rule 26 — APPROVE

Candidate name: **Profitability Margin Trajectory — Net Profit Core, Qualified Margin Context**.

The explicit Net Profit Core name describes PAT/revenue and discloses the change from V1 operating/gross wording.

- PAT / Revenue means NET_PROFIT_MARGIN only, with finite signed PAT, positive revenue, exact period/scope/attribution and compatible units.
- Net margin is a fraction; YoY percentage-point change is 100 * (margin_q - margin_q_minus_4). Five consecutive quarter-only observations remain the contract.
- Operating margin, gross margin and issuer EBITDA margin are distinct optional/future contexts with their own source-qualified numerator definitions.
- No V1 0.02 margin classification threshold or operating-efficiency conclusion is inherited.

Not approved by this receipt: NET_PROFIT_MARGIN as OPERATING_MARGIN; NET_PROFIT_MARGIN as GROSS_MARGIN; NET_PROFIT_MARGIN as EBITDA_MARGIN; operating/gross derived numerator; economic classification thresholds.

Activation prerequisites: `B01`, `B02`, `B03`, `B04`, `B10`, `B14`, `B15`.

### Rule 29 — APPROVE

Candidate name: **Entity-Aware Valuation Multiples — Independently Qualified Components**.

Independent qualified multiples preserve valid evidence without manufacturing a complete valuation view or a favourable score.

- P/E uses its exact annual EPS/PIT price definition; price session and per-share basis remain explicit.
- P/B requires approved book/share/price alignment; EV/EBITDA requires an approved EV bridge and source-qualified positive denominator; both remain gated where unavailable.
- Forward P/E requires governed forward EPS; PEG requires governed positive growth/horizon/unit definitions. No forecast or growth fill.
- Missing EV/EBITDA never erases P/E or independently valid P/B; financial-sector cells remain policy blocked.
- NOT_READY retains underlying INSUFFICIENT_DATA or EVIDENCE_CONFLICTED reasons; no optional-component reweighting.

Not approved by this receipt: new forecast; new PEG growth definition; missing debt/cash zero defaults; automatic ATTRACTIVE verdict.

Activation prerequisites: `B01`, `B02`, `B03`, `B04`, `B10`, `B14`, `B15`.

## Rule 19 completeness condition

**Debt/equity alone cannot make Rule 19 fully READY or HEALTHY.**

The existing proposal already distinguishes core completeness from optional
coverage. This receipt gives that distinction an explicit presentation label:

| Component evidence | Core complete | Coverage label | Full-rule ready | Economic verdict / score |
|---|---|---|---|---|
| D/E ready; net debt or interest coverage unavailable | true | CORE_READY_OPTIONAL_INCOMPLETE | false | null / ineligible |
| D/E ready; optional evidence conflicted | true | CORE_READY_OPTIONAL_CONFLICTED | false | null / ineligible; conflict remains visible |
| D/E missing; another component ready | false | PARTIAL | false | null / ineligible |
| All core and applicable optional components ready, no conflict | true | CORE_AND_OPTIONAL_COMPLETE | measurement coverage only | No favourable economic verdict or score follows automatically |

These are contract examples, not production observations. A ready optional
component presupposes its separately approved policy and verified inputs; the
examples do not resolve the currently blocked optional component contracts.

This is a binding clarification of the proposal's existing distinction, not
a new component state, formula, threshold, canonical ID or required-input
change. `READY_STANDARD_BRANCH` and `READY_ENTITY_SPECIFIC_BRANCH` mean
**core** readiness only and must carry the separate coverage label. They may
not be consumed as unqualified whole-rule readiness. Optional corroboration
that remains unimplemented is unavailable; it is not silently excluded as N/A.

A source-qualified adverse or conflicted optional observation remains visible.
No risk severity, HEALTHY/STRESSED rule or BLOCKING_COMPONENT threshold is
invented. Positive/core-ready measurements do not grant a favourable verdict.

## Rule 26 terminology ruling

`PAT / Revenue = NET_PROFIT_MARGIN` for the exact compatible accounting
basis specified by the proposal. It is **not** `OPERATING_MARGIN`,
`GROSS_MARGIN` or `EBITDA_MARGIN`. Net profit reflects financing, tax and
non-operating effects, so this evidence cannot establish operational efficiency.

The name “Profitability Margin Trajectory — Net Profit Core, Qualified Margin
Context” sufficiently discloses the actual measurement and the changed purpose.
The approved semantic scope includes the proposal's dimensionless net-margin
level and YoY percentage-point change; it does not approve legacy or new
classification thresholds. PAT attribution, revenue scope and period
comparability still gate any future measurement.

PBT margin remains explicitly before-tax context. Operating margin, gross
margin and issuer EBITDA margin each require their own numerator/definition
contracts and remain optional/future where those contracts are absent.
`HSI_STANDARDIZED_OPERATING_EARNINGS` remains `PLACEHOLDER_ONLY`, formula
null, with no EBIT/EBITDA alias or reported-fact status.

## Entity matrix governance

| Rule | NON_FINANCIAL | BANK | NBFC | INSURER | UNKNOWN_NON_COMPARABLE |
|---|---|---|---|---|---|
| 16 | STANDARD_BRANCH | POLICY_BLOCKED | POLICY_BLOCKED | POLICY_BLOCKED | POLICY_BLOCKED |
| 17 | STANDARD_BRANCH | POLICY_BLOCKED | POLICY_BLOCKED | POLICY_BLOCKED | POLICY_BLOCKED |
| 19 | STANDARD_BRANCH | POLICY_BLOCKED | POLICY_BLOCKED | POLICY_BLOCKED | POLICY_BLOCKED |
| 25 | STANDARD_BRANCH | POLICY_BLOCKED | POLICY_BLOCKED | POLICY_BLOCKED | POLICY_BLOCKED |
| 26 | STANDARD_BRANCH | POLICY_BLOCKED | POLICY_BLOCKED | POLICY_BLOCKED | POLICY_BLOCKED |
| 29 | STANDARD_BRANCH | POLICY_BLOCKED | POLICY_BLOCKED | POLICY_BLOCKED | POLICY_BLOCKED |

Decision: **APPROVE**. The matrix is appropriately conservative.
A standard-branch definition is not evidence readiness or production readiness.
Reuse the canonical PIT classification contract and authoritative issuer/security
bridge. Regulator/statutory/exchange/taxonomy evidence must be exact and
temporally valid. Unknown defaults and company-name heuristics are forbidden.
Conflicting classification remains conflicted. The current 19 unknown companies
were not classified.

Separate BANK, NBFC and INSURER policies remain open. They are deferred for
isolated non-financial shadow work, but block their respective branch activation.
Deferred does not mean approved, resolved or automatically not applicable.

## Component-readiness decision

Decision: **APPROVE**, with the completeness qualification above.

The six states remain `READY`, `PARTIAL`, `INSUFFICIENT_DATA`,
`POLICY_BLOCKED`, `NOT_APPLICABLE`, `EVIDENCE_CONFLICTED`.
They feed one canonical result per Rule ID. There is no second score, registry,
Brain or weighted vote.

Mandatory-core completeness, optional coverage, confidence and blockers remain
separate. Missing mandatory data cannot produce complete core. Missing optional
data does not invalidate a complete core, but cannot be omitted from coverage.
A partial or N/A mandatory component cannot silently satisfy the core.
Confidence remains unavailable unless supplied by an exact governed canonical
source; it is separate from Decision Score. No unavailable value defaults to zero.

## Mandatory score and higher-order safety

The [legacy score engine](../../app/scoring/engine.py) currently uses
`cfg.state_scores.get(result, Decimal("5"))`, and maps `PARTIAL` to 5.
This source inspection confirms an unsafe compatibility path for unrecognized
V2 readiness labels. It does not prove that a V2 result has reached production.

```text
UNKNOWN_V2_STATE_MUST_NEVER_DEFAULT_POSITIVE = TRUE
NO_V2_RESULT_MAY_BECOME_SUPPORTIVE_BY_UNKNOWN_STATE_FALLTHROUGH = TRUE
```

Before any V2 score or higher-order integration:

- Every accepted V2 state must be mapped explicitly under the exact version.
- Unknown/unrecognized states fail closed with no positive contribution or
  supportive interpretation.
- `POLICY_BLOCKED`, `INSUFFICIENT_DATA`, `EVIDENCE_CONFLICTED` and incomplete
  readiness are non-scoring. Required missing contributions keep the score
  incomplete; null is not a zero economic rating.
- Even `READY` is measurement readiness, not an economic verdict. A future
  scored verdict needs separate interpretation and calibration approval.
- Missing optional evidence cannot trigger weight renormalization, neutral
  defaults or unapproved changes to the averaging of available evidence.
- The correction must apply to the future V2 path while preserving reproducible
  V1 behavior. This slice does not edit the score engine.

[Thesis synthesis](../../app/diagnostics/synthesis.py) has a related hazard:
a result outside the finite “weak” list can become supportive through presence
alone. Rules 31/33/34, thesis synthesis, Decision Score, Six Gates, long-term
shadows, portfolio/Brain composition and research outputs must all preserve
incompleteness and exact version lineage. No downstream consumer may treat an
unknown state as evidence of health.

## Machine-readable activation blocker register

All 15 items are OPEN. Twelve are global/integration blockers; three financial
branch policies are scoped deferrals for non-financial shadow only.

| ID | Prerequisite | Classification | Activation scope | Closure proof |
|---|---|---|---|---|
| B01 | Explicit registry-version resolver | BLOCKING | ALL_V2_RUNTIME | Exact registry/strategy/policy/as_of binding and fingerprints; mixed/unknown/future versions rejected; historical V1 lookup proven. |
| B02 | V2 evaluator implementations | BLOCKING | ALL_V2_RUNTIME | Separate version-bound evaluators over approved measurements; six/quarter observation and signed-domain tests; no V1 in-place edits. |
| B03 | Fail-closed score adapter | BLOCKING | ALL_V2_SCORING | Exhaustive state schema and versioned adapter; ineligible/conflicted/missing/policy-blocked values yield no contribution and incomplete required score. |
| B04 | Unknown-state positive-default removal on the V2 path | BLOCKING | ALL_V2_DOWNSTREAM | Explicit dispatch with fail-closed unknown state; no V2 route to the V1 default. Preserve V1 replay. Prove unknown, POLICY_BLOCKED, INSUFFICIENT_DATA and EVIDENCE_CONFLICTED never contribute positively. |
| B05 | Higher-order rule adapters | BLOCKING | ALL_V2_SYNTHESIS | Version-bound accepted state vocabulary; unknown/partial sources cannot become supportive; exact source coverage preserved. |
| B06 | Thesis synthesis compatibility | BLOCKING | ALL_V2_SYNTHESIS | No positive-by-absence-of-weak-label behavior; incomplete core and coverage remain incomplete through thesis synthesis. |
| B07 | Portfolio and Brain version propagation | BLOCKING | ALL_V2_CONSUMER_INTEGRATION | Exact immutable strategy/registry/policy identity propagation, PIT alignment and no mutation of existing V1 receipts; portfolio action remains outside authority. |
| B08 | Six Gates compatibility | BLOCKING | ALL_V2_GATE_INTEGRATION | Compatible approved scorecard/evidence binding; incomplete or unknown state cannot satisfy a gate; evidence-only boundary and thresholds unchanged. |
| B09 | Versioned horizon-policy reference | BLOCKING | ALL_V2_RUNTIME | Explicit V2-compatible horizon/applicability version with entity branch awareness; no automatic activation or timeframe change. |
| B10 | Exact entity-classification contract compatibility | BLOCKING | ALL_V2_INTERPRETATION | Reuse existing exact PIT classifier; unknown/conflict/missing never default to NON_FINANCIAL; statement scope and regulatory branch checked. |
| B11 | BANK policy | DEFERRED_NOT_REQUIRED_FOR_SHADOW | BANK_BRANCH_ONLY | Separate bank policy/data/measurement approval and evidence; no industrial ROCE override. |
| B12 | NBFC policy | DEFERRED_NOT_REQUIRED_FOR_SHADOW | NBFC_BRANCH_ONLY | Separate NBFC approval with finance-cost/debt/equity and valuation basis. |
| B13 | INSURER policy | DEFERRED_NOT_REQUIRED_FOR_SHADOW | INSURER_BRANCH_ONLY | Separate insurer reporting/solvency/valuation approval and evidence. |
| B14 | Outcome and calibration compatibility | BLOCKING | ALL_V2_ECONOMIC_CLASSIFICATION | Versioned descriptive/economic outcome schema; no inherited growth/margin/healthy/valuation thresholds; comparative V1/V2 shadow evidence, no performance claim. |
| B15 | Replay and backward compatibility | BLOCKING | ALL_V2_RUNTIME | Retain V1 strategy/registry/policy/source artifacts; replay V1 unchanged; V2 replay explicitly requested and separately identified; no historical relabelling. |

The JSON additionally records current evidence and the prerequisite for isolated
shadow work. `NON_BLOCKING` and `NOT_APPLICABLE` were evaluated as available
register classifications but are not justified for any of these unresolved
items. No item has been marked closed.

The first shadow slice may produce only isolated deterministic descriptive
measurements/readiness using current canonical evidence and fixtures. It must
not call legacy scoring, synthesis, gates, portfolio or persistence, so those
integration prerequisites remain open. It must establish explicit candidate/
approval identity, PIT/entity checks and tests before emitting any measurement.
A missing metric or policy remains unavailable rather than creating a synthetic
input. A scoped deferral cannot bypass a blocker for the scope it protects.

## Version, horizon and historical replay conditions

Future execution requires exact `registry_version`, `strategy_version`,
`policy_version`, `as_of` and their fingerprints. V1 historical results must
rehydrate as V1. The current
[rehydration path](../../app/portfolio/canonical_diagnostics_orchestration.py)
uses the global registry constant; simply changing that constant cannot become
a migration strategy.

There is no global “latest registry” fallback, implicit V2 replay, retroactive
replacement, or backdated approval. V1's unversioned dependency limitations
remain documented and must be pinned for replay. An explicitly requested V2
research replay creates distinct labelled results while retaining V1 history.

The existing
[horizon policy](RULE_HORIZON_TIMEFRAME_APPLICABILITY_POLICY_V1.md)
remains `CANDIDATE_NOT_ACTIVE`; its semantics/timeframes are unchanged.
Before horizon-aware V2 execution, a versioned applicability reference must
understand entity branching. No horizon policy is activated here.

## Source basis and evidence-contract boundary

The review relies on the accepted
[policy research](FUNDAMENTAL_DIAGNOSTIC_POLICY_UNRESOLVED_V1.md)
and the exact source IDs retained in the original proposal: MCA Schedule III
and Ind AS presentation, ICAI guidance, SEBI issuer definitions, RBI bank/NBFC
context, IRDAI reporting, and official NSE/BSE filing structures. These establish
accounting distinctions and applicability; they do not validate HSI outcomes.

`ISSUER_REPORTED_FINANCIAL_RATIO` remains unimplemented. Same ratio name does
not imply the same formula. The allowed initial role is formula-matched
corroboration; mandatory-core substitution or stronger canonical use requires
separate explicit policy approval. DSCR is never silently interest coverage.

No data was acquired, no ratio/operating-earnings contract was implemented and
no providers were compared. Before a future material financial acquisition,
`DATA_BUILD_VS_BUY_AUDIT_V1` is mandatory. Existing evidence and synthetic
isolated fixtures are sufficient to start the next descriptive shadow slice;
they are not a claim of complete real-company coverage.

## Validation and exact next continuation

The [governance artifact tests](../../tests/unit/test_fundamental_diagnostic_registry_v2_governance_approval.py)
check candidate identity, all six decisions, terminology, entity/core coverage,
explicit score-state exclusions, blocker completeness, source pins and approval
replay. Existing proposal tests preserve the 61-ID and 55-rule proofs.
No production runtime change is authorized; full backend regression is not
required for this documentation/artifact/test slice.

Validation receipt for this bounded review:

- New approval-artifact tests: **40 passed / 0 failed / 0 skipped / 0 warnings**.
- Existing proposal, canonical-registry and horizon-policy tests:
  **35 passed / 0 failed / 0 skipped / 0 warnings**.
- Proposal and approval fingerprint replay: passed; 61 exact IDs and 55
  inherited definitions verified; all 13 source-preservation pins matched.
- All 543 tracked `app/` files match the pre-review physical content;
  production app diff is empty. Original proposal documentation/tests unchanged.
- Edited Markdown: 250 local links, including two anchors, resolve; table
  columns and new-document whitespace checks passed. `git diff --check` passed.
- Full backend suite intentionally not run: no production runtime changes.

Approval fingerprint:
`sha256:316936ca62d8b10accae8034f7e00ea7c5b17bcface796d3b9d79dd30c641013`.
This matches `approval_fingerprint` in the separate JSON. It is SHA-256 of
canonical UTF-8 JSON excluding only that field. No runtime timestamp or
machine-local path is part of the payload.

**Exactly one next continuation:**
`FUNDAMENTAL_DIAGNOSTIC_REGISTRY_V2_SHADOW_IMPLEMENTATION_V1`.
It is identified but not started by this approval.

```text
ONE_CANONICAL_61_DIAGNOSTIC_REGISTRY = TRUE
SEPARATE_TECHNICAL_BRAIN = FALSE
V1_ACTIVE = TRUE
V2_ACTIVE = FALSE
NO_SILENT_REGISTRY_REWRITE = TRUE
NO_SYNTHETIC_REPORTED_FACTS = TRUE
UNKNOWN_V2_STATE_MUST_NEVER_DEFAULT_POSITIVE = TRUE
NO_V2_RESULT_MAY_BECOME_SUPPORTIVE_BY_UNKNOWN_STATE_FALLTHROUGH = TRUE
AI_DECISION_AUTHORITY = FALSE
HSI_DATA_BUILD_VS_BUY_PRINCIPLE_V1 = FROZEN
DATA_BUILD_VS_BUY_AUDIT_V1 = MANDATORY_BEFORE_MATERIAL_FINANCIAL_ACQUISITION
HSI_EFFICIENT_VALIDATION_EXECUTION_POLICY_V1 = ACTIVE
```
