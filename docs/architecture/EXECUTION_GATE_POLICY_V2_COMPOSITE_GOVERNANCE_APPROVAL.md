# Composite Execution Gate Policy V2 — Conditional Governance Approval

Decision **A: `COMPOSITE_V2_GOVERNANCE_APPROVED_WITH_ACTIVATION_BLOCKERS`**.
Scope: **semantic governance only; V1 active, composite V2 NOT_ACTIVE**.
Baseline: `5787f37a45b77ab8fc2ca0227d4c7056dd560bae`, `main`.

This separate [approval artifact](EXECUTION_GATE_POLICY_V2_COMPOSITE_GOVERNANCE_APPROVAL.json)
governs the exact [composite .3 proposal](GATE3_SURVEILLANCE_POLICY_V2_PROPOSAL.md)
and [machine definition](GATE3_SURVEILLANCE_POLICY_V2_PROPOSAL.json).
The proposal's `PROPOSED` status, empty approval reference, historical next-step
label and bytes remain the original reviewed input, not the current approval
decision. No active registry or production approval/selection repository is changed.

## 1. Authority, single successor and immutable parent

| Field | Verified decision |
| --- | --- |
| Governed future candidate | `execution-gate-policy-v2-proposed / v2-proposal.3` |
| Parent, still active | `six-gates-production-v1 / v1` |
| Composite proposal fingerprint | `sha256:57bbd7af01fe14fa95ae419187302d5dcc353e3cbd98181e43b5f691cb97ab3d` |
| Approval identity | `execution-gate-policy-v2-composite-governance-approval/v1` |
| Approval fingerprint | `sha256:caad6fb766fbcf93ea4859a94454c78d57ba59551274601eba9741486ae7d30e` |
| Authority | User-delegated bounded governance review, directive `3e26e7db-91b3-423e-a597-17fa9ee56ea5` |
| Reviewer | Codex governance reviewer; no human signature or named-person attestation claimed |
| Runtime effectiveness / activation | None / NOT_ACTIVE |

There is one future whole-policy line, not an independent surveillance V2 and an
independent earnings V2. The .2 Gate-6 proposal and approval are pinned component
governance and historical proposal evidence; neither is overwritten, revoked or
silently selected as a competing whole-policy successor. This receipt supplies
the **new composite semantic approval**, not an automatic transfer of .2 approval.
Runtime registration, effective-time selection and activation remain separate.

Exactly six ordered IDs remain:

```text
GATE_1_ROTATION
GATE_2_VELOCITY
GATE_3_SURVEILLANCE
GATE_4_TRADE_PLAN
GATE_5_HEAT
GATE_6_EARNINGS
```

The .3 proposal pins Gates 1/2/4/5 definitions and method fingerprints. Approval
tests independently compare those pins against current canonical definitions and
source methods; the immutable production configuration and authority file pins
also match. Gate-3 V1 and Gate-6 V1 source/method definitions remain unchanged.
The existing [engine and reducer](../../app/gates/engine.py) remain the only
Six-Gate composition path. No Gate 7, duplicate gate or parallel reducer.

## 2. Gate-3 approval — temporal selection only

Approved change: from relevant **completed-session** state to
**`LATEST_PIT_VISIBLE_EFFECTIVE_SURVEILLANCE_STATE`** for the execution context.
The exact proposal's source admission, precision, supersession, identity and
completeness contracts are approved without semantic overrides.

| Review | Binding approval |
| --- | --- |
| Thresholds | ASM >=2; GSM >0; explicit valid static price band <=5%. Unchanged. |
| Inputs | Exactly ASM, GSM, PRICE_BAND. |
| SECURITY_STATUS | `DESCRIPTIVE_SOURCE_FAMILY / NOT_A_GATE3_FORMULA_INPUT`; no hidden PASS field, predicate or independent admission guard. |
| Authority | NSE execution venue is hard authority; BSE remains corroborative. |
| ASM/GSM identity | Exact classified NSE security membership and applicable framework; no fabricated list-row series or issuer-name propagation. |
| Price-band identity | Exact actual NSE execution symbol+series and verified instrument/master linkage; no EQ default or provider-token substitution. |
| 0/314 | Prior list-series measurement is not a gate-wide identity failure or a measured target-price join count. |
| Complete products | Official ASM/GSM complete-product semantics are established; actual collector/export completeness remains unproven. HTTP 200 or documentation is not runtime proof. |
| Freshness | Existing four-trading-session inclusive cap retained; age alone does not prove current applicability, and refetch does not renew effective age. |

`SOURCE_PUBLICATION`, `HSI_FIRST_OBSERVED`, `EFFECTIVE_FROM`, `EFFECTIVE_TO` and
`EVALUATION_AS_OF` remain separate. Known-at is inclusive and must prove completed
payload availability by the decision cutoff. Request start, file date, public
timestamp or effective date cannot be used to backdate local knowledge. The
target session must be bound through PIT-visible canonical calendar evidence.
Date-only source evidence stays date/session precision, not an invented clock.

The central repair is expressly approved: if yesterday's completed state was
non-blocking but an officially effective current-session restriction has been
truthfully observed by evaluation, yesterday's state cannot continue to govern.
The admitted current state governs. If only observed later, an earlier decision
is **not retroactively invalid**. Future evidence is excluded before revision
and conflict selection, including its identifiers in historical output.
Removals/reschedules require their own visible effective lineage; no timestamp
voting, assumed indefinite validity or old-clearance fallback for unresolved
current state. These constraints accept no new surveillance source-gap clearance.

### Gate-3 outcome contract

| Condition | Approved result |
| --- | --- |
| All three admitted, current, fresh, conflict-free non-blocking components | PASS |
| Common admission and complete vector, with any unchanged blocking threshold | FAIL |
| Required evidence missing, failed, partial, stale, conflicted, identity/effectiveness unresolved, source-version invalid or capture completeness unproven | INSUFFICIENT_DATA, or existing pre-formula admission rejection; never eligibility |
| Blocking component plus another required field missing | INSUFFICIENT_DATA: completeness-first precedence intentionally retained |

PASS requires NSE authority, correct per-family scope, effective source/policy
versions, immutable first-observation/raw lineage, current applicability, complete
required captures, freshness and no unresolved conflict. Bare absence cannot
become zero; explicit static price band is required. Dynamic, blank, unsupported
or ambiguous band evidence remains unknown. No independent-component veto is
introduced into Gate 3.

`GATE_RESULT_CONFIDENCE_ANNOTATION != SOURCE_COMPLETENESS_PROBABILITY`.
Its existing PASS annotation 1.0 is not an empirical completeness or reliability
estimate. No runtime confidence change is made by this approval.

## 3. Gate-6 carry-forward and separate residual risk

Pinned [Gate-6 proposal](EARNINGS_BLACKOUT_POLICY_V2_PROPOSAL.json):
`sha256:36c80f2ea561a4411b252e6b4749f9c73275d6e434b257e89bdeb24d83de0e21`.
Pinned [Gate-6 approval](EARNINGS_BLACKOUT_POLICY_V2_GOVERNANCE_APPROVAL.json):
`sha256:0d2bd690a9b5cec347437163cbc7ad88cadec940b0546549ce40361b833414d0`.

Both content fingerprints and proposal-pinned normalized file hashes verify.
All Gate-6 semantics, approved residual risk and constraints are retained, not
only the three output labels. The exact identity, purpose, trusted observation,
PIT-before-lifecycle, horizon, freshness and integrity conjunction is unchanged.
Global invalid admission cannot be bypassed. An independent valid event veto
can survive another observed source failure; an unresolved retained event cannot
be erased to obtain no veto. Missing producer receipts are not observed failures.

| Future Gate-6 state | Composition outcome | Required distinction |
| --- | --- | --- |
| VETO | FAIL | Fully verified eligible event in the approved effective window |
| NO_VETO_ESTABLISHED | PASS | Not CLEAR, SAFE, NO_EARNINGS_SOON or authoritative negative evidence |
| UNDETERMINED | INSUFFICIENT_DATA | Missing/unresolved admission or retained-event requirements |

The mandatory no-veto metadata guard remains open: `evaluation_mode=VERIFIED_EVENT_VETO`,
`earnings_clearance=UNVERIFIED`, `confidence=None`, source warnings, coverage
limitations, policy ID/version/fingerprint, as-of and receipt lineage must survive
end-to-end. Required warning: `EARNINGS_CLEARANCE_UNVERIFIED`. Missing metadata
rejects compatibility. Do not use the generic PASS=1.0 helper for this future
meaning, or change Gate-3's annotation to repair Gate 6.

The prior conditional `VERIFIED_EVENT_VETO_RESIDUAL_SOURCE_RISK / v1` acceptance
is retained: a real official event may remain unobserved/unverified until later.
Admitted no-veto composition accepts that exposure without claiming calendar
clearance. This is visible, versioned semantic risk acceptance, not activation,
performance evidence or transfer of that uncertainty behavior into Gate 3.

`EVENT_RISK_HORIZON = POLICY_UNSET`; calibration required; value/unit/precision
and boundaries absent. Neither V1 five sessions nor regulatory two working days
is selected. Governance approval does not approve a horizon.

Accepted [collector](EARNINGS_BLACKOUT_PROSPECTIVE_RECEIPT_COLLECTOR_V1.md) and
[prospective shadow](EARNINGS_BLACKOUT_HORIZON_PROSPECTIVE_SHADOW_V1.md) structures
remain ready; live positive event and live outcome proof remain `PENDING_EVENT`.
This receipt inherits those checkpoints, without rerunning acquisition or
remeasuring production. They need not complete to approve semantics. The
existing shadow's conservative completed-observation handling remains intact;
structural readiness is not proof of an admitted runtime source or calibrated
window. No existing collector/shadow work is duplicated or restarted.

## 4. Cross-gate interaction, liveness and historical truth

Each gate retains its evidence authority and meaning. The single reducer applies:
any FAIL -> BLOCKED; otherwise any INSUFFICIENT_DATA -> INSUFFICIENT_DATA;
otherwise all six PASS -> EXECUTABLE. Mixed FAIL/insufficient remains BLOCKED
while preserving **both** component results. No voting, confidence averaging,
cross-gate evidence override or generic insufficient-data bypass.

Synthetic governed outcomes prove a future logical path with Gates 1/2/4/5 PASS,
Gate 3 complete admitted non-blocking PASS, and Gate 6 admitted no-veto composition
PASS -> EXECUTABLE. Tests also enumerate all nine Gate-3/Gate-6 outcome pairs and
each unchanged gate's independent failure/insufficiency. Gate-3 failure blocks;
Gate-6 veto blocks; insufficiency without any failure remains insufficient.
This is conditional policy liveness, **not** live-source readiness, complete
entry readiness or broker/capital authority. The real admission boundary remains.

Source uncertainty affects execution eligibility, not a company's fundamentals,
technical direction, quality or Decision Score. Independent research continues.
No score penalty, automatic portfolio action, sell instruction or forced exit.

V1 policy/history remain immutable: completed-session surveillance semantics and
five-session earnings semantics are retained with their original lineage. This
does not manufacture a missing official historical archive. V2 replay requires
its own explicit effective policy, source/calendar versions, local known-at and
effective-state evidence. No latest-policy fallback, V1 relabel, current-data
backfill or retroactive surveillance/earnings violation.

## 5. One reconciled activation register

IDs below are scoped to this approval, **not** project-global blocker IDs.
`g3:*` references .3 proposal G3A entries; `g6:*` references the prior Gate-6
approval's B entries. Every original blocker has a traceable destination. No
operational item is marked closed. Only composite semantic approval itself is
satisfied; the remaining registration/compatibility part of G3A08 stays open.

| ID | Deduplicated requirement | Origins | Classification |
| --- | --- | --- | --- |
| CV2B01 | Complete applicable ASM export | g3:G3A01 | BLOCKING |
| CV2B02 | Complete applicable GSM export | g3:G3A02 | BLOCKING |
| CV2B03 | Exact execution symbol+series static band | g3:G3A03 | BLOCKING |
| CV2B04 | Trusted prospective payload receipts, exact identity and source admission | g3:G3A04; g6:B02 | BLOCKING |
| CV2B05 | Surveillance effective-state selector and session precision | g3:G3A05 | BLOCKING |
| CV2B06 | Shared source conflict/lifecycle infrastructure, separate gate semantics | g3:G3A06; g6:B03 | BLOCKING |
| CV2B07 | Gate-3 and Gate-6 component adapters under one engine | g3:G3A07; g6:B04 | BLOCKING |
| CV2B08 | Prospective surveillance canary | g3:G3A09 | BLOCKING |
| CV2B09 | Earnings horizon/calibration approval | g6:B01 | BLOCKING |
| CV2B10 | Gate-6 no-veto PASS/confidence guard | g6:B05 | BLOCKING |
| CV2B11 | Lossless gate/Brain/Signals metadata propagation | g3:G3A08; g6:B06 | BLOCKING |
| CV2B12 | One Signal/Portfolio/entry-ready interpretation review | g3:G3A08; g6:B07 | BLOCKING |
| CV2B13 | Outcome/calibration methodology and lineage | g6:B09 | BLOCKING |
| CV2B14 | Composite runtime version selection, identities and compatibility | g3:G3A08; g6:B04 | BLOCKING |
| CV2B15 | Historical policy-version isolation | g3:G3A10; g6:B10 | BLOCKING |
| CV2B16 | Complete historical surveillance archive | g3:G3A11 | DEFERRED_FOR_REPLAY |
| CV2B17 | Complete historical earnings/outcomes | g6:B11 | DEFERRED_FOR_SHADOW |
| CV2B18 | Authoritative negative calendar clearance | g6:B12 | DEFERRED_FOR_SHADOW |
| CV2B19 | Optional alerts, disabled | g3:G3A12; g6:B08 | NON_BLOCKING |
| CV2B20 | Optional results-season context, disabled | g6:B13 | NON_BLOCKING |

The machine register gives exact closure criteria per row. Shared infrastructure
is counted once, but closure must prove each affected gate separately: one gate's
admitted receipts or conflict policy cannot satisfy the other's proof. Broad
G3A08 is split into transport (CV2B11), interpretation (CV2B12) and selection
(CV2B14); Gate-6 B04's version-admission requirement contributes to that same
selection proof, not a duplicate implementation. Confidence guarding is distinct
from transporting the guarded metadata. Historical surveillance evidence and
earnings outcome cohorts retain separate deferred requirements, reusing the same
storage/lineage infrastructure rather than commissioning duplicate stores.

The register therefore has **15 BLOCKING, 1 DEFERRED_FOR_REPLAY,
2 DEFERRED_FOR_SHADOW and 2 NON_BLOCKING** entries. Optional entries are non-blocking
only while disabled; no optional feature is activated here. Perfect historical
archives are not prospective-pilot prerequisites, but version isolation is.
Negative calendar clearance remains unsupported, not an extra prerequisite that
would negate the approved no-veto model.

## 6. Reconciled downstream impact and reuse

| Consumer | Composite impact | Register |
| --- | --- | --- |
| Six-Gates orchestration | ADAPTER_UPDATE_REQUIRED | CV2B07, CV2B14 |
| Brain | ADAPTER_UPDATE_REQUIRED | CV2B11 |
| Signals | ADAPTER_UPDATE_REQUIRED; POLICY_REVIEW_REQUIRED | CV2B11, CV2B12 |
| Portfolio | POLICY_REVIEW_REQUIRED | CV2B12 |
| Entry-ready lifecycle | POLICY_REVIEW_REQUIRED | CV2B12 |
| Backtest/replay | ADAPTER_UPDATE_REQUIRED; REPLAY_UPDATE_REQUIRED | CV2B15 |
| Outcome ledger | ADAPTER_UPDATE_REQUIRED; CALIBRATION_REQUIRED | CV2B13 |
| Alerts | POLICY_REVIEW_REQUIRED; disabled | CV2B19 |
| Decision Score | NO_CHANGE | None |
| TradePlan | NO_CHANGE | None |
| Gate-3 numeric thresholds | CALIBRATION_NOT_REQUIRED | None |
| Gate-6 earnings horizon | CALIBRATION_REQUIRED | CV2B09 |

Outcome calibration remains the Gate-6 observation/counterfactual requirement;
Gate-3 timing/source lineage must be recorded without inventing a new threshold
calibration project. No synthetic fills, fabricated performance or automatic
action follows from a gate result.

Reuse exactly the proposal's existing canonical identity, NSE symbol/series
master, immutable snapshot store, first-observed/PIT and coverage patterns,
source authority, gate envelope, trading calendar and reducer. Existing earnings
collector/shadow remain their owners. No new surveillance/earnings Brain, gate
engine, timestamp framework, identity system or competing policy authority.
Existing storage/envelopes still need future lossless versioned compatibility;
the current gate identifier and in-memory context must not be assumed collision
safe across policies without CV2B14/CV2B15 proof.

## 7. Validation, pilot boundary and next continuation

The [approval tests](../../tests/unit/test_execution_gate_policy_v2_composite_governance_approval.py)
verify proposal/Gate-6 fingerprints, current definition/method/configuration pins,
unique successor and exact six gates, both temporal contracts, independent
cross-gate composition, retained V1 history, complete deduplicated blocker origin
coverage, deterministic approval serialization and semantic tamper rejection.
Existing proposal and Gate-6 governance tests remain unchanged and are rerun.
Synthetic reducer outcomes are not a new V2 runtime evaluator. No full backend
suite is needed because no runtime file changes.

The approval fingerprint uses existing canonical JSON/content hashing, excluding
only `approval_fingerprint`; file pins are LF-normalized. It is content identity,
not a human signature. No runtime approval timestamp, activation date or secret
is invented. Documentation links and whitespace are checked before the local
commit; no push.

Governance approval does **not** make pilot execution ready. Each operational
blocker must close before prospective activation. The next concrete source work
is **`GATE3_SURVEILLANCE_PROSPECTIVE_COLLECTOR_V1`**, as a separate bounded slice.
Existing Gate-6 prospective shadow may continue independently while its horizon
is unset. This approval starts neither a collector nor a shadow job and does not
require an external live event merely to govern semantics.

```text
V1_ACTIVE = TRUE
GATE_POLICY_V2_ACTIVE = FALSE
SIX_GATES_EXACTLY_SIX = TRUE
NO_FABRICATED_SURVEILLANCE_CLEARANCE = TRUE
NO_UNVERIFIED_CALENDAR_CLEARANCE = TRUE
NO_FUTURE_LEAKAGE = TRUE
NO_RETROACTIVE_SURVEILLANCE_STATE = TRUE
NO_RETROACTIVE_BLACKOUT = TRUE
NO_HORIZON_GUESS = TRUE
PILOT_SIMPLICITY_RULE = ACTIVE
AI_DECISION_AUTHORITY = FALSE
```

Exact one next continuation: **`GATE3_SURVEILLANCE_PROSPECTIVE_COLLECTOR_V1`**.
It is **not started** by this slice.
