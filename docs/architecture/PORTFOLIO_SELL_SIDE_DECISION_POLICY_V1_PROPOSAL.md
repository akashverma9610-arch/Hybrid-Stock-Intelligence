# Portfolio Sell-Side Decision Policy V1 Proposal

**Status: PROPOSED — NOT APPROVED — NOT IMPLEMENTED — NOT ACTIVE.**

**Policy identity:** portfolio-sell-side-decision-policy / v1-proposed  
**Proposed human reviewer:** human:Akash-Verma

This is governance design only. It creates no action producer, persistence,
alert, recommendation, signal, sell/trim order, short position, strategy or
scoring change, or live-paper mutation. Existing portfolio and rotation
components remain read-only analysis.

## 1. Existing semantics reused

| Existing contract | Reused meaning | Not repurposed as |
| --- | --- | --- |
| HoldingAnalytics | PIT score, confidence, gate, trading/investment thesis, invalidation, stop, targets, sector, and regime references. | Recommendation or automatic sell. |
| PortfolioSnapshot | Allocation, concentration, cash, sector exposure, total heat, and data status. | Reduction percentage. |
| RotationHoldingState.invalidated | TRIGGERED, BROKEN, SEVERE_CONCERN, or trading thesis BROKEN. | An order. |
| Higher-order trading thesis | VALID/STRONG, MIXED, INVALIDATED, and insufficient evidence semantics. | A P&L conclusion. |
| Decision Score and Six Gates | Versioned analytical and portfolio/rotation constraints. | A thesis state or an automatic exit. |
| CapitalRotationEngine | KEEP_EXISTING, ROTATE_CANDIDATE_PREFERRED, CASH_PREFERRED, NO_ACTION, and INSUFFICIENT_DATA. | Transaction or capital movement. |
| capital_velocity_adjustment / Gate 2 | Comparison-score adjustment for inactivity. | Permission to rotate, trim, or exit. |
| DecisionAuditRecord | Frozen evidence/version references and fingerprint. | Existing holding-action persistence. |

No new score, indicator, target, threshold, or parallel thesis model is
introduced.

## 2. Canonical thesis-state contract

| State | Allowed evidence transition | Prohibited transition |
| --- | --- | --- |
| INTACT | Current, internally consistent evidence has invalidation_status=INTACT (or no invalidation concern), trading thesis VALID or STRONG, and no required thesis evidence missing. | Positive P&L, target touch, score increase, or a better candidate alone. |
| WEAKENED | Not invalidated, but the existing thesis is MIXED or WEAK, or a non-fatal evidence conflict is retained with a complete review record. | Price decline, valuation level, or paper outcome alone. |
| INVALIDATED | Current invalidation is TRIGGERED, BROKEN, or SEVERE_CONCERN; or trading thesis is INVALIDATED or BROKEN. PRICE_STRUCTURE_INVALIDATION is the currently machine-testable source. | Fundamental/catalyst invalidation inferred from price, news, or P&L without a separately approved policy. |
| INSUFFICIENT | Required evidence is absent, stale, non-comparable, conflicted without a governed disposition, or reports INSUFFICIENT_DATA. | Treating unknown as intact or weakened. |

Evaluate only frozen evidence at the requested as_of. INVALIDATED dominates
WEAKENED. INSUFFICIENT is a data-validity blocker for any future action
producer. P&L never determines thesis state.

## 3. Action semantics

### HOLD

HOLD is appropriate only with INTACT thesis, no governed invalidation, no
approved profit-taking condition, no hard portfolio rule expressly requiring
reduction, and no eligible superior rotation. A winner may remain HOLD; a loser
may remain HOLD under the same conditions.

An eligible rotation is only the existing complete rotation result. Raw score,
candidate rank, or velocity adjustment alone is insufficient.

### TRIM

TRIM is **not deterministically available** in this proposal. The repository
has concentration and heat observations, targets, and generic
TradeManagementPlan.t1_reduction input, but no approved holding-lifecycle
contract joining a factual target/extension event or existing-position risk
breach to a reduction quantity.

The following are POLICY_NOT_YET_GOVERNED:

- concentration/heat breach requiring an existing-position reduction;
- factual target-hit or extension observation requiring a reduction;
- reward/risk deterioration requiring a reduction;
- valuation/euphoria condition permitting a reduction; and
- reduction quantity, sequencing, tax treatment, and re-entry semantics.

A later policy may use them only with exact evidence, trigger, quantity, and
precedence rules. Profit alone never produces TRIM.

### EXIT_TO_CASH

EXIT_TO_CASH is available only when current, non-conflicted evidence is
INVALIDATED and no valid replacement has won the existing rotation process. It
is not caused by a falling price, high valuation, weak forward-paper result, or
a merely higher-scoring candidate.

This is a future public action name. It does not alter CASH_PREFERRED and does
not create a sell instruction.

### ROTATE

ROTATE requires a completed existing rotation evaluation returning
ROTATE_CANDIDATE_PREFERRED for the holding/candidate at the same approved
as-of context. The existing engine remains authoritative for complete score,
confidence, executable gate/portfolio constraints, structural R:R, valid
entry/stop/invalidation, sector policy, friction/economics, confirmations, and
cooldown.

| Existing rotation state | Future public action |
| --- | --- |
| KEEP_EXISTING | HOLD when holding evidence is complete and intact; otherwise REVIEW_REQUIRED. |
| ROTATE_CANDIDATE_PREFERRED | ROTATE, subject to higher-priority validity/invalidation rules. |
| CASH_PREFERRED | EXIT_TO_CASH only when holding is INVALIDATED; otherwise REVIEW_REQUIRED. |
| NO_ACTION | HOLD when evidence is complete and intact; otherwise NO_ACTION or REVIEW_REQUIRED. |
| INSUFFICIENT_DATA | REVIEW_REQUIRED. |

### NO_ACTION / REVIEW_REQUIRED

NO_ACTION means complete evidence supports no policy action and does not
affirmatively qualify for HOLD. REVIEW_REQUIRED is the mandatory fail-closed
result where required evidence, context, or governance is absent.

## 4. Capital-efficiency and profit-taking states

### CAPITAL_INEFFICIENT

This is descriptive, not an action. It may be attached only where an existing
holding has non-zero capital_velocity_adjustment or a failed existing-position
Gate 2 velocity result, and the thesis is not INVALIDATED. It authorizes no
TRIM, EXIT_TO_CASH, or ROTATE. Rotation still requires a valid replacement and
every existing rotation control. With no valid replacement, result is HOLD if
evidence is complete, otherwise REVIEW_REQUIRED.

| Winner label | Meaning |
| --- | --- |
| HOLD_WINNER | Positive-P&L holding whose complete evidence qualifies for HOLD. |
| TRIM_WINNER | Requires future approved trim trigger and quantity rule; currently POLICY_NOT_YET_GOVERNED. |
| EXIT_WINNER | Positive-P&L holding independently qualifying for EXIT_TO_CASH or ROTATE; profit is incidental. |

target_1, target_2, and extended_target remain analytical references. They do
not prove target hit, extension, profit protection, or reduction semantics.

## 5. Portfolio context and fail-closed rules

Portfolio context may contribute evidence or a blocker; it never silently
overrides thesis/invalidation governance.

| Context | Permitted effect | Not permitted |
| --- | --- | --- |
| Concentration, heat, sector crowding, cash | Evidence/constraint inputs to a reviewed future action; existing Gate 5 and portfolio data remain authoritative. | Implicit trim percentage or automatic exit. |
| Replacement candidate | Supports ROTATE only through existing engine. | Replacing an intact holding only because the candidate score is higher. |
| Friction/tax | Existing rotation economics can block rotation. Missing economics means REVIEW_REQUIRED. | Assuming zero cost or forcing a switch. |
| Capital velocity | May make CAPITAL_INEFFICIENT descriptive. | Automatic rotation or exit. |

Stale, missing, non-comparable, unresolved, or conflicted required evidence;
missing portfolio context; missing replacement evidence; or unresolved policy
configuration results in REVIEW_REQUIRED, never TRIM, EXIT_TO_CASH, or ROTATE.

## 6. Forward-paper intelligence firewall

Forward-paper intelligence is descriptive reliability context only. It may be
retained as warning/evidence lineage, but must not change HOLD to TRIM or
EXIT_TO_CASH, force ROTATE, change thresholds, or mutate this policy. Its
DESCRIPTIVE_ONLY_NO_POLICY_MUTATION warning remains authoritative.

## 7. Deterministic action priority

Apply the first matching row; all inputs must share the approved as_of boundary.

| Priority | Condition | Future result |
| ---:| --- | --- |
| 1 | Required evidence/context stale, missing, non-comparable, unresolved, or conflicted without approved disposition. | REVIEW_REQUIRED |
| 2 | Thesis INVALIDATED and existing completed rotation selects eligible replacement. | ROTATE |
| 3 | Thesis INVALIDATED and no eligible replacement selected. | EXIT_TO_CASH |
| 4 | A future approved, complete trim rule is satisfied. | TRIM |
| 5 | Thesis INTACT and existing completed rotation selects eligible replacement. | ROTATE |
| 6 | Thesis INTACT; no governed profit/risk reduction condition; no valid rotation. | HOLD |
| 7 | Complete evidence has no action-supporting state but does not meet HOLD. | NO_ACTION |

Thus invalidation plus valid replacement maps to ROTATE; concentration alone is
review-required until a trim policy exists; friction failure blocks rotation and
leaves an otherwise intact holding HOLD; and capital inefficiency without a
replacement is HOLD or REVIEW_REQUIRED according to completeness.

## 8. Proposed immutable future action contract

This is a future value contract only; no model, serializer, repository, API,
or producer is created.

~~~
PortfolioHoldingActionProposal
  canonical_holding_id: str
  as_of: timezone-aware datetime
  action: HOLD | TRIM | EXIT_TO_CASH | ROTATE | NO_ACTION | REVIEW_REQUIRED
  thesis_state: INTACT | WEAKENED | INVALIDATED | INSUFFICIENT
  capital_efficiency_state: EFFICIENT | CAPITAL_INEFFICIENT | INSUFFICIENT
  portfolio_context_state: COMPLETE | CONSTRAINED | INSUFFICIENT
  rotation_state: KEEP_EXISTING | ROTATE_CANDIDATE_PREFERRED | CASH_PREFERRED | NO_ACTION | INSUFFICIENT_DATA
  reasons: tuple[str, ...]
  blockers: tuple[str, ...]
  evidence_fingerprints: tuple[str, ...]
  shared_brain_fingerprint: str
  policy_id: portfolio-sell-side-decision-policy
  policy_version: v1-proposed
  policy_fingerprint: str
  audit_fingerprint: str
~~~

It must retain the canonical portfolio snapshot, rotation evaluation, and
version references required for reconstruction. Future persistence must create
immutable audit records and never re-evaluate "latest" data.

## 9. Proposed identity and fingerprint

The canonical policy manifest is compact UTF-8 JSON with lexicographically
sorted keys. The fingerprint is SHA-256 of those exact bytes:

~~~json
{"action_vocabulary":["HOLD","TRIM","EXIT_TO_CASH","ROTATE","NO_ACTION","REVIEW_REQUIRED"],"capital_efficiency":{"does_not_authorize":"ROTATE","requires":"VALID_ROTATION","state":"CAPITAL_INEFFICIENT"},"fingerprint_scheme":"sha256:utf8:canonical-json-v1","human_reviewer":"human:Akash-Verma","policy_id":"portfolio-sell-side-decision-policy","priority_stages":["REVIEW_REQUIRED","INVALIDATED_WITH_VALID_REPLACEMENT","INVALIDATED_TO_CASH","APPROVED_TRIM","VALID_ROTATION","HOLD","NO_ACTION"],"status":{"active":false,"approved":false,"proposed":true},"thesis_states":["INTACT","WEAKENED","INVALIDATED","INSUFFICIENT"],"version":"v1-proposed"}
~~~

**Proposed policy fingerprint:** `a11e84973ca19f4e0e23a4afc1ca989a9cfe4add1e8451750f333327651d6253`

Status remains PROPOSED, NOT APPROVED, and NOT ACTIVE. No approved/selected
record is created for human:Akash-Verma.

## 10. Human decisions required before implementation

1. Approve, reject, or amend vocabulary and action priority.
2. Define PIT-safe trim evidence, trigger/threshold, quantity, sequencing,
   tax/friction treatment, and re-entry; or permanently exclude trim.
3. Decide whether an existing-position concentration/heat breach mandates a
   reduction and bind it to exact evidence.
4. Decide whether target/extension/valuation/euphoria inputs are admissible,
   including source, freshness, conflict, and quantity rules.
5. Approve future immutable contract and audit/persistence linkage.
6. Approve a separate alert boundary if ever desired.

## 11. Non-effects

No runtime action, trim, exit, rotation execution, short sale, score/gate
change, strategy change, threshold, live signal, portfolio transaction,
snapshot, audit record, selected/active policy, provider call, or network
operation is created by this document.
