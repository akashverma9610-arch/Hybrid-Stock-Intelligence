# Fundamental V2 downstream fail-closed adapter V1

Status: **IMPLEMENTED_SAFETY_BOUNDARY / V1_ACTIVE / V2_SHADOW_ONLY / V2_NOT_ACTIVE**.
Baseline: `c2b47b4473b79bc9444a39812eac2bd6d0e33930`.
Authority: user-authorized bounded downstream safety repair, not a V2 economic
policy, effective-time registration, calibration, or activation approval.

## Authority and evidence

- [Immutable V2 proposal](FUNDAMENTAL_DIAGNOSTIC_REGISTRY_V2_PROPOSAL.md).
- [Immutable governance approval](FUNDAMENTAL_DIAGNOSTIC_REGISTRY_V2_GOVERNANCE_APPROVAL.md).
- [Prior isolated shadow implementation](FUNDAMENTAL_DIAGNOSTIC_REGISTRY_V2_SHADOW_IMPLEMENTATION_V1.md).
- [Machine-readable consumer inventory](FUNDAMENTAL_V2_DOWNSTREAM_FAIL_CLOSED_INVENTORY.json).
- [Deterministic safety receipt](FUNDAMENTAL_V2_DOWNSTREAM_FAIL_CLOSED_RECEIPT.json).
- [Pre-change replay fixtures](../../tests/fixtures/fundamental_v2_downstream_baseline.json).
- [Read-only audit harness](../../scripts/audit_fundamental_v2_downstream.py).

The original proposal/approval JSON, fingerprints and blocker histories are not
rewritten. Historical source-pin tests now inspect the historical Git blobs of
the two specifically authorized runtime repairs. New tests pin all 543 other
pre-existing application files, numeric mappings, weights, and V1 output replay.
Source hash checks normalize checkout line endings, not program content.

## Exact legacy defect and repair

`app/scoring/engine.py::build_scorecard` accepted `EvaluatedDiagnostic` whenever
eligibility was ELIGIBLE and result as-of was not future. It did not verify the
registry version. It then used
`cfg.state_scores.get(x.record.result, Decimal("5"))`.
Unknown strings consequently received neutral-positive five-point contributions.
This was not an approved interpretation of those states.

The existing ten-component engine now admits each diagnostic through
`app/diagnostics/downstream.py::classify_score_input`. Exactly one typed result
is returned: `SCORE_ELIGIBLE_EXPLICIT_STATE`, or
`SCORE_INELIGIBLE_INSUFFICIENT_DATA`, `SCORE_INELIGIBLE_POLICY_BLOCKED`,
`SCORE_INELIGIBLE_CONFLICTED`, `SCORE_INELIGIBLE_NOT_APPLICABLE`,
`SCORE_INELIGIBLE_SHADOW`, `SCORE_INELIGIBLE_UNKNOWN_STATE`.
Every ineligible result carries **None**, never zero, five, or a neutral label.
Empty, malformed and unmapped state values are unknown, not exceptions that
propagate through ordinary score assembly.

All 31 literal V1 state-score entries are unchanged. Thirty eligible-state full
scorecards replay identically. The 31st entry, `INSUFFICIENT_DATA: 0`, is retained
as historical vocabulary but deliberately cannot contribute a number even if a
caller incorrectly labels its record ELIGIBLE. This explicit contradictory-input
repair is not a revaluation of recognized economic states. Legitimately missing
V1 records were already ineligible.

No case folding or new numeric mapping is introduced. Existing emitted labels
without an explicit numeric mapping (for example `STRONG_ACCUMULATION_PROXY`,
`MAPPED`, lower-case market labels and some valuation/technical labels) now remain
unscored; their former five points were the unsafe fallback. The rich universe
fixture accordingly has an incomplete score rather than invented neutral points.
This can reduce current score availability and is intentional fail-closed behavior.

### Missing data, conflicts and weights

The exact ten weights, mandatory/optional rule sets, numeric scale, arithmetic
mean and weighted sum remain unchanged. A missing required rule makes its
component INELIGIBLE and the final score SCORE_INCOMPLETE. Its weight is not
redistributed. Optional absence retains the existing PARTIAL/available-evidence
policy; rejected input reasons are visible in score warnings. No unknown value
participates in that average. Exact duplicate V1 inputs are idempotent; conflicting
same-rule records are excluded independently of input order. Cross-registry or
shadow contamination makes the score incomplete without falling back to
co-present V1 results.

## Rule 29 and changed-rule dependency graph

| Consumer | Actual upstream dependency | Prior unsafe behavior | New boundary |
| --- | --- | --- | --- |
| Valuation/risk-reward score component, weight 0.10 | mandatory 29,45; optional 43,44,31 | unmapped Rule 29 text got 5 | only explicit V1 scores; every V2 result forbidden |
| Earnings-acceleration score component, weight 0.15 | mandatory 24; optional 25,26,16,27,28 | unmapped text got 5 | explicit V1 admission; missing optional visible |
| Rule 31 risk | 1,2,19,23,29,30,46,55 | unknown mapped to MODERATE severity | registry guard plus finite V1 state vocabulary |
| Rule 32 trading thesis | mandatory 43,45,46; support 4,6,10,37,38,41,45 | exclusion list could count unknown as support | same V1 semantics after explicit admission |
| Rule 33 investment thesis | mandatory 16,17,18,19,23 | unknown outside weak list could yield STRONG | same V1 semantics after explicit admission |
| Rule 34 scenarios | 31,32,33; transitively 16,17,19,29 | unknown could select default 30/50/20 | no scenario values on unsupported/cross-version input |

Rules 25/26 do not directly drive Rules 31–34 in current code; they can be carried
among descriptive input IDs. Rule 33's text mentions 15/20 but does not require
them. The guard checks actual synthesis read dependencies, not every unrelated
label in the 61-rule collection. Registry checks cover the entire supplied set.

V2 P/E READY with missing P/B, EV/EBITDA, Forward P/E or PEG remains descriptive
measurement availability only. Both raw shadow results and verified shadow
envelopes yield `V2_SHADOW_SCORE_FORBIDDEN`, even if every component is READY.
No EV/EBITDA value or favorable aggregate classification is created.

## Higher-order and thesis boundary

`HigherOrderDiagnosticContext` is the narrow common guard for risk, trading
thesis, investment thesis and Bull/Base/Bear synthesis. Non-V1 contexts, mixed
versions and nominal shadow results return INSUFFICIENT_DATA with
`CROSS_REGISTRY_DIAGNOSTIC_CONSUMPTION_FORBIDDEN`; they cannot produce STRONG,
VALID, supportive classifications or scenario weights. Unknown, policy-blocked,
conflicted, NA, shadow-only and contradictory eligible/missing states on actual
dependencies fail closed. `AnalysisStatus.VALID` or a truthy result object is not
authority. Existing ineligible/future V1 evidence remains excluded.

Eighty-seven preserved V1 state labels were replayed at every upstream position for
all four functions: 348 state/function cases, **7,656 position replays**. Exact
pre-change state, details, input lineage, status and confidence fingerprints agree.
This preserves existing V1 interpretation; it does not validate those economic
policies anew or claim that every known V1 state is favorable.

Direct score callers and portfolio, Brain, gate and crowd consumers are listed
in the inventory. `app/crowd/engine.py` contains separate non-financial
eligibility/substring/exclusion behavior in Rules 59–61, and raw-observation
confidence/model defaults. None consumes the six changed fundamental rules;
none is newly wired to V2. They are recorded, not silently relabeled repaired or
calibrated. B04 closure refers to diagnostic-to-Decision-Score numeric defaults,
not every unrelated model/default in the repository.

## Versioned, non-scoring shadow envelope

`shadow_diagnostic_envelope` accepts only a verified nominal
`FundamentalV2ShadowResult`, never unversioned data or V1. It retains the entire
immutable source and exact registry, evaluator/policy version, pinned approval
fingerprint, UTC source as-of and source result fingerprint. Strategy version is
explicitly unavailable (`None`): the isolated source has no strategy binding.
The adapter's own fingerprint covers that reference identity and authority flags;
source validation separately verifies all nested source content. Neither hash is
repaired from a tampered value. Future source results are rejected at audit as-of.

The envelope is audit-only, score_eligible=false and execution_eligible=false.
It does not masquerade as a V1 record. Source WATCH_ONLY/NON_EXECUTABLE flags
remain unchanged. No latest-version or cross-version translation exists.

## Measured blocker movement

| Blocker | Current classification | Still required |
| --- | --- | --- |
| B03 scoring adapter | PARTIALLY_CLOSED | rejection/lineage adapter complete; no constructive V2 scoring or calibration |
| B04 unknown positive score default | CLOSED_FOR_ACTIVATION_SAFETY | explicit score mapping tests must remain; this alone authorizes nothing |
| B05 higher-order adapters | PARTIALLY_CLOSED | active V1 rejects V2; constructive V2 higher-order contracts deferred |
| B06 thesis compatibility | PARTIALLY_CLOSED | active thesis rejects V2; constructive V2 thesis semantics deferred |
| B07 portfolio/Brain propagation | STILL_BLOCKING_ACTIVATION | persisted rehydration still stamps V1; explicit end-to-end version lineage needed |
| B08 Six Gates | STILL_BLOCKING_ACTIVATION | unchanged; no V2 gate integration |
| B09 horizon reference | STILL_BLOCKING_ACTIVATION | unchanged governed candidate |
| B14 calibration | STILL_BLOCKING_ACTIVATION | no new score values, calibration or probability claims |

B01/B02/B10/B15 remain closed for isolated shadow only. BANK/NBFC/INSURER remain
policy-blocked; B11/B12/B13 remain deferred, not approved or activated.

## Validation and non-mutation

Final validation completed:

- New focused cases: **438 passed**, within the **710 passed / 2 warnings**
  final combined focused/affected run (272 other affected cases).
- The initially authorized full run completed **3,939 passed / 1 failed /
  6 skipped / 2 warnings**. The sole failure was
  `test_historical_rotation_replay.py::test_rotation_approved_and_cash_deployment_event_paths_are_append_only`.
  Its synthetic score override inherited `confidence=None` from a now correctly
  incomplete diagnostic replay. The unchanged rotation engine rejected it with
  `INSUFFICIENT_CONFIDENCE` against its existing 0.7 fixture requirement.
- The test-only repair appends a separately identified synthetic scorecard with
  explicit 0.8 confidence and asserts that the original incomplete scorecard
  remains unchanged. No rotation/gate/portfolio implementation or threshold was
  changed. Post-repair focused/integration verification: **453 passed**.
- The user explicitly authorized **one additional full run** after that narrow
  correction. Its completed result: **3,940 passed / 0 failed / 6 skipped /
  2 warnings**, exit code 0, 257.59 seconds. The two warnings are the existing
  Starlette/httpx and AnyIO BlockingPortal deprecations. No dependency changes.
- SQLite `PRAGMA integrity_check`: **ok**; FK violations: **0**, using mode=ro
  plus query_only. Database bytes (18,346,504,192) and modification timestamp are
  unchanged. FinancialFacts=6,118; filings=455; portfolio snapshots=1;
  paper trades=0; trade plans=0; generic strategy_versions=0;
  generic diagnostic_results=0; canonical strategy definitions=1;
  canonical diagnostic results=2,074, all unchanged.
- Markdown: **250 local links** checked, including local anchors; no missing
  targets or malformed table rows. Whitespace, binary/private-path inspection,
  credential-pattern scan and `git diff --check` passed.
- Receipt replay is stable across processes. The synthetic gzip fixture header
  is pinned to mtime=0, avoiding generated source-byte variation without changing
  any canonical production evidence or provider behavior.

Final deterministic safety receipt fingerprint:
`sha256:99f348dc513695a2c319a9b43ecb5196a4052daa0be9f5ca984e8b84c959bd23`.

The deterministic receipt is replayed from code, not populated with assumed
production evidence. It uses synthetic fixtures and never opens SQLite. Production
integrity checks are separate read-only operations. No acquisition, provider probe,
portfolio/gate execution, migration, stored diagnostic rewrite, API/UI/runtime
wiring or trading operation is part of this task.

Preserved: ONE_CANONICAL_61_DIAGNOSTIC_REGISTRY=TRUE; V1_ACTIVE=TRUE;
V2_ACTIVE=FALSE; NO_SILENT_REGISTRY_REWRITE=TRUE;
NO_SYNTHETIC_REPORTED_FACTS=TRUE; UNKNOWN_V2_STATE_MUST_NEVER_DEFAULT_POSITIVE=TRUE;
NO_SILENT_SCORE_WEIGHT_RENORMALIZATION=TRUE; AI_DECISION_AUTHORITY=FALSE.
HSI_DATA_BUILD_VS_BUY_PRINCIPLE_V1 remains FROZEN;
DATA_BUILD_VS_BUY_AUDIT_V1 remains mandatory before material financial acquisition;
HSI_EFFICIENT_VALIDATION_EXECUTION_POLICY_V1 remains ACTIVE.

Exactly one next slice: **FUNDAMENTAL_V2_BRAIN_PORTFOLIO_VERSION_PROPAGATION_V1**.
It is not started here. This receipt is not production activation.
