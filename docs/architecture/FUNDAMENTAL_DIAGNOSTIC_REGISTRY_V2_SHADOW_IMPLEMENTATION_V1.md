# Fundamental Diagnostic Registry V2 — Isolated Shadow Implementation V1

Status: `SHADOW_IMPLEMENTED / VALIDATED / NOT_ACTIVE`.

Parent checkpoint: `cf320613afb55d4f51abb54ffd6b1e71f201fc20`.
Authority: [conditional governance approval](FUNDAMENTAL_DIAGNOSTIC_REGISTRY_V2_GOVERNANCE_APPROVAL.md)
and its immutable [approval/blocker artifact](FUNDAMENTAL_DIAGNOSTIC_REGISTRY_V2_GOVERNANCE_APPROVAL.json).
The [original proposal](FUNDAMENTAL_DIAGNOSTIC_REGISTRY_V2_PROPOSED.json) remains unchanged.

## Exact version and authority boundary

The [version resolver](../../app/registry/versioned.py) exposes one canonical
registry family, not another Brain or 61-rule engine. Default and explicit V1
resolution return the existing `DIAGNOSTIC_RULES` objects. Explicit
`diagnostic-registry-v2-proposed` plus `SHADOW` resolves the pinned proposal and
approval. An ACTIVE request fails with `V2_REGISTRY_NOT_ACTIVE`; unknown versions
and modes fail rather than selecting a latest/default candidate.

Both versions contain exactly IDs 1–61. The same 55 V1 definition objects are
retained. Only 16, 17, 19, 25, 26 and 29 use approved shadow definitions.

Pinned proposal:
`sha256:668005237acd727ead86b19fca11a0fe9a1f640291dbe647a02cab989774a261`.

Pinned approval:
`sha256:316936ca62d8b10accae8034f7e00ea7c5b17bcface796d3b9d79dd30c641013`.

The resolver verifies both self-fingerprints against these exact approved pins,
the parent V1 semantic fingerprint, and every parent definition. Artifact files
are read only on explicit shadow resolution. No active caller is rewired.
The immutable component validation schema is derived from this same approved
definition set; it is not an independently maintained component registry.

## Reuse and input contract

The [bounded evaluator](../../app/fundamentals/diagnostic_v2_shadow.py) consumes
the existing [canonical financial input](../../app/fundamentals/diagnostic_input.py)
and [comparability contract](../../app/fundamentals/diagnostic_comparability.py).
It does not introduce an adapter, store, migration, acquisition path or provider.

Canonical vintage selection, filing checks, exact fiscal identity, single scope,
period continuity, unit/scale/currency/normalization comparability and
published/received PIT eligibility remain authoritative. No latest complete
period is substituted for a missing/conflicted current period. YTD never fills
quarter-only gaps; net worth never silently substitutes for total equity.

An explicit aware `as_of` must equal the canonical input cutoff. An explicit
NON_FINANCIAL request is insufficient by itself: the input must contain the
matching verified, classified canonical company-type receipt at that cutoff.
Missing/mismatched/unclassified evidence fails closed. BANK, NBFC, INSURER and
UNKNOWN_NON_COMPARABLE remain `POLICY_BLOCKED`; no names or sector guesses are
used. Receipt reasons and fingerprints remain visible.

For the corpus audit, existing approved canonical classification is recomputed
read-only at the supplied cutoff from its stored authoritative inputs. Existing
financial-period corrections are projected through their current approved PIT
contract. Neither classification nor period-correction records are created.

## Six rule implementations and deliberate unavailability

| Rule | Implemented descriptive measurement | Unavailable interpretation/context |
|---|---|---|
| 16 | Separate Revenue/PAT/EPS CAGR: six consecutive FULL_YEAR observations, five intervals, positive endpoints; `(last/first)^(1/5)-1` | No transfer of V1 four-metric classification or thresholds. Issuer EBITDA/standardized operating earnings remain independently policy-gated; their absence does not invalidate core. |
| 17 | Canonical annual PAT divided by exact average beginning/end TOTAL_EQUITY, matching fiscal boundaries and monetary representation, positive average; signed PAT retained | No ending-only fallback, ROCE numerator, issuer-ratio substitution or healthy-return verdict. |
| 19 | Direct canonical TOTAL_DEBT / same-end positive TOTAL_EQUITY | Net debt remains blocked pending the approved exact debt/cash boundary even if raw facts exist. Missing cash and conflicts are exposed independently. No EBIT/coverage invention; DSCR never substitutes. |
| 25 | Revenue/PAT/EPS exact YoY and QoQ from five consecutive QUARTER_ONLY observations; latest, previous and year-ago values must satisfy the existing positive-domain convention | No signed/zero-base growth convention, interpolation, EBITDA requirement or earnings-acceleration classification. |
| 26 | `NET_PROFIT_MARGIN = PAT / Revenue`, signed finite PAT, positive revenue, exact comparable five-quarter window; current/prior-year fractions and `100*(current-prior_year)` percentage-point difference | No operating/gross/EBITDA alias or legacy margin threshold. Directional classification remains `POLICY_BLOCKED_THRESHOLD_NOT_APPROVED`. Independently comparable PBT margin is before-tax context only. |
| 29 | P/E measurement reused from the existing certified V1 financial-input/valuation functions with aligned PIT market evidence and raw-INR EPS | P/B, EV/EBITDA, Forward P/E and PEG remain independently blocked under the approved proposal's missing share/EV/forecast/growth contracts. No duplicate formula or invented input; no valuation verdict. |

Rule 29 reuses the unchanged V1 routine with its existing runner parameters
`ValuationRules(15, 35)` solely to obtain its certified P/E measurement. Its
classification, price detail and confidence are discarded. These thresholds
are **not** adopted as V2 policy. The shadow output contains no favourable
whole-rule verdict. An available P/E is not erased by unavailable other multiples.

New approved arithmetic uses an explicit 34-digit Decimal context, independent
of ambient Decimal settings. Nonrepresentable arithmetic fails closed rather
than emitting infinity, zero-fill or a synthetic result. This is numerical
representation precision, not an investment threshold or calibration policy.

## Immutable result and isolation

Each result preserves registry/parent/evaluator versions, approved fingerprints,
Rule ID, canonical instrument, explicit entity/cutoff, canonical input and entity
fingerprints, optional market fingerprint, ordered component states, reasons,
source fact IDs, observation/series fingerprints and nested canonical series.
Those series retain the exact scope, fiscal period, basis, units, vintage
selection and immutable parent observation lineage. Supplied but rejected
evidence can remain identified for audit; it is not a qualified measurement.

Financial observations retain their existing bare SHA-256 representation;
other canonical fingerprints retain their `sha256:` prefix. Both are validated,
not renamed. Canonical JSON uses explicit UTC, ordered keys/tuples, finite
Decimal strings and deterministic content hashes. Identity derives from the
complete immutable content; no current time or environment configuration enters
interpretation. Fingerprints are tamper-evident identities, not signatures.

Component states remain READY, PARTIAL, INSUFFICIENT_DATA, POLICY_BLOCKED,
NOT_APPLICABLE and EVIDENCE_CONFLICTED. Unsupported financial branches are
blocked, not marked N/A. The evaluator does not invent new applicability
exclusions. `core_state` is separate from optional COMPLETE/INCOMPLETE/CONFLICTED
coverage. Rule 19 D/E-only therefore means ready core plus incomplete optional
coverage, never whole-rule HEALTHY. Optional conflict remains visible without
erasing an otherwise complete core. Confidence remains unavailable.

All outputs are unconditionally:

```text
SHADOW_ONLY = TRUE
score_eligible = FALSE
execution_eligible = FALSE
WATCH_ONLY / NON_EXECUTABLE
classification_state = POLICY_BLOCKED
```

The result is not an `EvaluatedDiagnostic` and has no legacy record conversion.
Its `eligibility` compatibility tripwire raises `V2_SHADOW_SCORE_FORBIDDEN`;
its `record` tripwire raises `V2_SHADOW_LEGACY_CONSUMER_FORBIDDEN`. Tests pass the
actual outputs to the existing score and thesis entry points and prove rejection.
No adapter or consumer wiring is added. The legacy positive-default and
supportive-fallthrough defects remain open for future downstream work; this
slice excludes the shadow type from those paths, not repairs their V1 semantics.

There is no signal, alert, Six-Gates computation, portfolio interpretation or
execution authority, and no BUY/SELL/HOLD output. The unchanged 55 definitions
are resolvable, not dispatched by this six-rule evaluator.

## Persistence and current-corpus audit

Decision: **in-memory evaluation; no shadow-result persistence**. No existing
store is extended or registered. Documentation records aggregate audit evidence
only, not a generic receipt subsystem.

The [read-only audit](../../scripts/audit_fundamental_v2_shadow.py) uses
SQLite `mode=ro`, `query_only=ON`, an explicit transaction/cutoff and fixed
population bounds (20,000 facts, 2,000 filings, bounded snapshot-family pages).
It reuses existing deserializers, period projection and the canonical classifier.
It evaluates only companies represented in the current financial corpus, not
the whole market, and repeats each evaluation to verify deterministic replay.
It performs no provider request or store writes and prints its receipt to stdout.

Audit cutoff: `2026-09-12T08:37:13+00:00` (explicit UTC).
Population: **6,118 FinancialFacts / 455 filings / 31 companies**.
Governed classifications: **10 NON_FINANCIAL, 2 BANK, 19 UNKNOWN_NON_COMPARABLE**.
No NBFC or INSURER occurs in this corpus; their blocking behavior is tested with
synthetic inputs, not claimed as observed production coverage.

| Rule | EVALUATED_CORE_READY | PARTIAL | INSUFFICIENT_DATA | POLICY_BLOCKED | EVIDENCE_CONFLICTED |
|---|---|---|---|---|---|
| 16 | 7 | 2 | 0 | 21 | 1 |
| 17 | 3 | 0 | 6 | 21 | 1 |
| 19 | 0 | 0 | 10 | 21 | 0 |
| 25 | 8 | 0 | 1 | 21 | 1 |
| 26 | 8 | 0 | 1 | 21 | 1 |
| 29 | 9 | 0 | 0 | 21 | 1 |

Every row sums to 31. Core-ready is measurement availability, not healthy,
favourable, scored, executable or fully covered evidence. All classification
outputs remain policy-blocked. Rule 19 lacks admitted direct total-debt evidence
for the non-financial corpus; borrowing components were not summed or substituted.

Final full audit fingerprint:
`sha256:63ef931bb7bfae588bb4c8f5931b20d24b313967b8469c0adb697bcdadab2f7f`.

Immutable source fingerprint:
`sha256:18d3eb596948570b5426d72db230d363247c3367d9c8c71f11b4433caa764a12`.

Canonical classification report fingerprint:
`sha256:794429f10497734e5cbfa3fbebad8ca0f6c569b414f199f15dd380b03a4829e4`.

The initial audit and final blocker-lineage replay used identical source content.
The final implementation repeated every company evaluation and produced identical
serialized results. No audit results were inserted into SQLite.

### Exact per-rule reason counts

Each count is the number of company/rule results retaining the reason. Reasons
overlap and must not be summed into company totals. Classification evidence labels
such as RBI_BANK_EXACT_EVIDENCE explain the blocked entity branch; they do not
claim an adverse financial event or severity.

| Rule | Retained reason | Count |
|---|---|---|
| 16 | COMPONENT_POLICY_NOT_APPROVED:HSI_STANDARDIZED_OPERATING_EARNINGS | 10 |
| 16 | COMPONENT_POLICY_NOT_APPROVED:ISSUER_REPORTED_EBITDA | 10 |
| 16 | ECONOMIC_CLASSIFICATION_POLICY_NOT_APPROVED | 31 |
| 16 | ENTITY_BRANCH_POLICY_BLOCKED:BANK | 2 |
| 16 | ENTITY_BRANCH_POLICY_BLOCKED:UNKNOWN_NON_COMPARABLE | 19 |
| 16 | EVIDENCE_CONFLICTED | 1 |
| 16 | MISSING_OR_NONCOMPARABLE_FISCAL_PERIOD | 1 |
| 16 | POSITIVE_ENDPOINT_OR_COMPARISON_DOMAIN_REQUIRED | 1 |
| 16 | RBI_BANK_EXACT_EVIDENCE | 2 |
| 16 | REGULATOR_LINKAGE_UNAVAILABLE | 3 |
| 16 | REQUIRED_FISCAL_PERIOD_MISSING_OR_AMBIGUOUS | 2 |
| 16 | TAXONOMY_EVIDENCE_UNAVAILABLE | 3 |
| 16 | UNRESOLVED_FACT_CONFLICT | 1 |
| 17 | COMPONENT_POLICY_NOT_APPROVED:ISSUER_REPORTED_ROE_ROCE | 10 |
| 17 | COMPONENT_POLICY_NOT_APPROVED:ROCE | 10 |
| 17 | DIRECT_COMPARABLE_METRIC_MISSING | 3 |
| 17 | ECONOMIC_CLASSIFICATION_POLICY_NOT_APPROVED | 31 |
| 17 | ENTITY_BRANCH_POLICY_BLOCKED:BANK | 2 |
| 17 | ENTITY_BRANCH_POLICY_BLOCKED:UNKNOWN_NON_COMPARABLE | 19 |
| 17 | EVIDENCE_CONFLICTED | 1 |
| 17 | RBI_BANK_EXACT_EVIDENCE | 2 |
| 17 | REGULATOR_LINKAGE_UNAVAILABLE | 3 |
| 17 | REQUIRED_FISCAL_PERIOD_MISSING_OR_AMBIGUOUS | 7 |
| 17 | TAXONOMY_EVIDENCE_UNAVAILABLE | 3 |
| 17 | UNRESOLVED_FACT_CONFLICT | 1 |
| 19 | COMPONENT_POLICY_NOT_APPROVED:INTEREST_COVERAGE | 10 |
| 19 | COMPONENT_POLICY_NOT_APPROVED:ISSUER_REPORTED_DEBT_EQUITY | 10 |
| 19 | COMPONENT_POLICY_NOT_APPROVED:NET_DEBT | 10 |
| 19 | DIRECT_COMPARABLE_METRIC_MISSING | 10 |
| 19 | ECONOMIC_CLASSIFICATION_POLICY_NOT_APPROVED | 31 |
| 19 | ENTITY_BRANCH_POLICY_BLOCKED:BANK | 2 |
| 19 | ENTITY_BRANCH_POLICY_BLOCKED:UNKNOWN_NON_COMPARABLE | 19 |
| 19 | RBI_BANK_EXACT_EVIDENCE | 2 |
| 19 | REGULATOR_LINKAGE_UNAVAILABLE | 3 |
| 19 | REQUIRED_FISCAL_PERIOD_MISSING_OR_AMBIGUOUS | 10 |
| 19 | TAXONOMY_EVIDENCE_UNAVAILABLE | 3 |
| 25 | COMPONENT_POLICY_NOT_APPROVED:HSI_STANDARDIZED_OPERATING_EARNINGS | 10 |
| 25 | COMPONENT_POLICY_NOT_APPROVED:ISSUER_REPORTED_EBITDA | 10 |
| 25 | ECONOMIC_CLASSIFICATION_POLICY_NOT_APPROVED | 31 |
| 25 | ENTITY_BRANCH_POLICY_BLOCKED:BANK | 2 |
| 25 | ENTITY_BRANCH_POLICY_BLOCKED:UNKNOWN_NON_COMPARABLE | 19 |
| 25 | EVIDENCE_CONFLICTED | 1 |
| 25 | MISSING_OR_NONCOMPARABLE_FISCAL_PERIOD | 2 |
| 25 | RBI_BANK_EXACT_EVIDENCE | 2 |
| 25 | REGULATOR_LINKAGE_UNAVAILABLE | 3 |
| 25 | REQUIRED_FISCAL_PERIOD_MISSING_OR_AMBIGUOUS | 1 |
| 25 | TAXONOMY_EVIDENCE_UNAVAILABLE | 3 |
| 25 | UNIT_CURRENCY_OR_NORMALIZATION_MISMATCH | 1 |
| 25 | UNRESOLVED_FACT_CONFLICT | 1 |
| 26 | COMPONENT_POLICY_NOT_APPROVED:GROSS_MARGIN | 10 |
| 26 | COMPONENT_POLICY_NOT_APPROVED:ISSUER_EBITDA_MARGIN | 10 |
| 26 | COMPONENT_POLICY_NOT_APPROVED:OPERATING_MARGIN | 10 |
| 26 | CROSS_METRIC_UNIT_CURRENCY_OR_BASIS_MISMATCH | 1 |
| 26 | ENTITY_BRANCH_POLICY_BLOCKED:BANK | 2 |
| 26 | ENTITY_BRANCH_POLICY_BLOCKED:UNKNOWN_NON_COMPARABLE | 19 |
| 26 | EVIDENCE_CONFLICTED | 1 |
| 26 | MISSING_OR_NONCOMPARABLE_FISCAL_PERIOD | 2 |
| 26 | POLICY_BLOCKED_THRESHOLD_NOT_APPROVED | 31 |
| 26 | RBI_BANK_EXACT_EVIDENCE | 2 |
| 26 | REGULATOR_LINKAGE_UNAVAILABLE | 3 |
| 26 | REQUIRED_FISCAL_PERIOD_MISSING_OR_AMBIGUOUS | 1 |
| 26 | TAXONOMY_EVIDENCE_UNAVAILABLE | 3 |
| 26 | UNIT_CURRENCY_OR_NORMALIZATION_MISMATCH | 1 |
| 26 | UNRESOLVED_FACT_CONFLICT | 1 |
| 29 | CANONICAL_PE_INPUT_UNAVAILABLE | 1 |
| 29 | COMPONENT_POLICY_NOT_APPROVED:EV_EBITDA | 10 |
| 29 | COMPONENT_POLICY_NOT_APPROVED:FORWARD_PE | 10 |
| 29 | COMPONENT_POLICY_NOT_APPROVED:PB | 10 |
| 29 | COMPONENT_POLICY_NOT_APPROVED:PEG | 10 |
| 29 | ECONOMIC_CLASSIFICATION_POLICY_NOT_APPROVED | 31 |
| 29 | ENTITY_BRANCH_POLICY_BLOCKED:BANK | 2 |
| 29 | ENTITY_BRANCH_POLICY_BLOCKED:UNKNOWN_NON_COMPARABLE | 19 |
| 29 | EVIDENCE_CONFLICTED | 1 |
| 29 | RBI_BANK_EXACT_EVIDENCE | 2 |
| 29 | REGULATOR_LINKAGE_UNAVAILABLE | 3 |
| 29 | REQUIRED_DIRECT_METRICS_UNAVAILABLE | 1 |
| 29 | REQUIRED_FISCAL_PERIOD_MISSING_OR_AMBIGUOUS | 1 |
| 29 | TAXONOMY_EVIDENCE_UNAVAILABLE | 3 |
| 29 | UNRESOLVED_FACT_CONFLICT | 1 |

### Completed validation receipt

- Focused shadow/evaluator/audit tests: **45 passed / 0 failed**.
- Affected comparability, period repair, V1 financial/valuation/score, registry,
  horizon and governance tests: **160 passed / 0 failed**.
- Combined targeted validation: **205 passed**.
- One final complete backend run: **3502 passed / 0 failed / 6 skipped /
  2 warnings**, exit 0. Warnings are the Starlette/httpx and AnyIO compatibility
  deprecations; no dependency changes were made to suppress them.
- SQLite integrity: **ok**; foreign-key violations: **0**.
- Read-only protected counts: FinancialFacts **6118**, corporate filings **455**,
  portfolio snapshots **1**, paper trades **0**, trade plans **0**, generic
  strategy_versions **0**, generic diagnostic_results **0**, canonical strategy
  definitions **1**, canonical diagnostic results **2074**.
- All **543** previously tracked production files retain their baseline Git
  content. V1 formulas, active constants, score, synthesis and gates are unchanged.
- New tests prove actual score/thesis rejection, UTC and Decimal-context
  determinism, tamper/schema rejection and SQL write denial in an isolated audit.
- Markdown validation passed: **251 local links**, including two anchors,
  zero broken links; table columns and whitespace passed. `git diff --check`
  passed. No runtime file changes followed the full suite.
- The production DB file size and last-write timestamp remained unchanged
  after the full suite; no WAL/SHM companion appeared. The integrity/FK results
  above refer to the same unchanged production DB, not a test copy.

## Activation blocker movement

The original [15-item approval register](FUNDAMENTAL_DIAGNOSTIC_REGISTRY_V2_GOVERNANCE_APPROVAL.json)
remains an immutable approval-time record. The following is this slice's scoped
progress receipt. No row denotes production activation closure.

Before: 15 OPEN items. After: four `CLOSED_FOR_SHADOW`, eight
`STILL_BLOCKING_ACTIVATION`, three `DEFERRED_NOT_REQUIRED_FOR_SHADOW`.

| ID | Prerequisite | After this slice | Remaining boundary |
|---|---|---|---|
| B01 | Explicit registry-version resolver | CLOSED_FOR_SHADOW | Exact V1/V2 resolution only; no production V2 dispatch. |
| B02 | V2 evaluators/component-state contract | CLOSED_FOR_SHADOW | Six bounded descriptive implementations; unapproved optional formulas/classification remain unavailable. |
| B03 | Score adapter | STILL_BLOCKING_ACTIVATION | No V2 scoring adapter exists. |
| B04 | Unknown-positive-default removal | STILL_BLOCKING_ACTIVATION | Shadow outputs rejected; unchanged legacy default is not repaired. |
| B05 | Higher-order adapters | STILL_BLOCKING_ACTIVATION | No V2 synthesis integration. |
| B06 | Thesis compatibility | STILL_BLOCKING_ACTIVATION | No supportive shadow/thesis mapping. |
| B07 | Portfolio/Brain propagation | STILL_BLOCKING_ACTIVATION | No integration or mutation. |
| B08 | Six Gates compatibility | STILL_BLOCKING_ACTIVATION | No gate calculation or threshold change. |
| B09 | Versioned horizon/applicability policy | STILL_BLOCKING_ACTIVATION | No horizon activation or timeframe reinterpretation. |
| B10 | Entity-contract compatibility | CLOSED_FOR_SHADOW | Exact existing governed receipt required; no new entity policy/classifier. |
| B11 | BANK policy | DEFERRED_NOT_REQUIRED_FOR_SHADOW | BANK remains policy-blocked. |
| B12 | NBFC policy | DEFERRED_NOT_REQUIRED_FOR_SHADOW | NBFC remains policy-blocked. |
| B13 | INSURER policy | DEFERRED_NOT_REQUIRED_FOR_SHADOW | INSURER remains policy-blocked. |
| B14 | Outcome/calibration compatibility | STILL_BLOCKING_ACTIVATION | No economic classification or score calibration approved. |
| B15 | Replay/backward compatibility | CLOSED_FOR_SHADOW | Deterministic in-memory replay and preserved V1 sources; production/persisted version rehydration still requires future work. |

The earlier governance tests are updated only at their phase-specific
"no V2 runtime anywhere" checks: they now permit these two explicit shadow
modules while continuing to forbid wiring elsewhere. The approval-time test
blob remains pinned in Git history. All original proposal/approval artifacts
and prior production files remain unchanged.

## Frozen architecture and next step

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

No acquisition occurs; Build-vs-Buy is not triggered by this slice.
Exactly one next continuation:
`FUNDAMENTAL_V2_DOWNSTREAM_FAIL_CLOSED_ADAPTER_V1`.

Existing data produced useful descriptive shadow measurements; downstream
score/higher-order fail-closed integration is the next blocking work, not
material financial acquisition. This continuation is identified, not started.
