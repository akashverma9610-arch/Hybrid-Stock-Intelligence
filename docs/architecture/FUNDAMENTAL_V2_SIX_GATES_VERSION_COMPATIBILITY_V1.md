# Fundamental V2 Six Gates Version Compatibility V1

Status: **IMPLEMENTED_SHADOW_COMPATIBILITY / V1_ACTIVE / V2_SHADOW_ONLY / V2_NOT_ACTIVE**.
Baseline: `c182b6421303f5f1cb8df3517be36872e72d5602`
(`feat(governance): propagate fundamental v2 version lineage`).
Authority: bounded B08 compatibility and fail-closed repair, not gate activation.

## References and actual input paths

- [Previous Brain/Portfolio lineage](FUNDAMENTAL_V2_BRAIN_PORTFOLIO_VERSION_PROPAGATION_V1.md).
- [Canonical V2 approval](FUNDAMENTAL_DIAGNOSTIC_REGISTRY_V2_GOVERNANCE_APPROVAL.md).
- [Machine-readable source inventory](FUNDAMENTAL_V2_SIX_GATES_VERSION_INVENTORY.json).
- [Deterministic six-gate receipt](FUNDAMENTAL_V2_SIX_GATES_VERSION_RECEIPT.json).
- [Pure admission boundary](../../app/gates/version_compatibility.py).
- [Existing gate engine](../../app/gates/engine.py).
- [Unchanged production policy](../../app/gates/production_policy.py).
- [Executable isolated audit](../../scripts/audit_fundamental_v2_gates.py).
- [Focused regression](../../tests/unit/test_fundamental_v2_gate_version.py).

The only production gate evaluator remains `ExecutionGateEngine.evaluate`.
The six private gate methods, decision aggregation, adjustment, configuration,
thresholds, policy fingerprints, gate order and action-context exemptions are
unchanged. An existing analytical `EXECUTABLE` result is not broker authority.
The new code only admits or rejects input; it creates no gate decision or action.

| Gate | Actual inputs and semantics retained | Added rejection boundary |
| --- | --- | --- |
| 1 Rotation/friction | Raw candidate score, incumbent comparison score, optional expected incremental return and modeled friction; existing hurdle | Reject incompatible source before extraction, mixed score dependencies, shadow/non-numeric scores; no manufactured differential |
| 2 Capital velocity | Holding entry date, ATR expansion, exchange sessions; existing separate velocity adjustment | Reject shadow duration/ATR and action-ineligible context before calculation; no new penalty or priority |
| 3 Surveillance/circuit | Nominal `SurveillanceObservation`, authoritative flag, effective time, ASM/GSM, circuit limit; existing freshness basis | Reject research/financial substitute or truthy non-boolean authority; absent/stale inputs remain insufficient |
| 4 Trade plan | Nominal `TradeManagementPlan`, tranche, T1 reduction, stop/T1 booleans, breakeven conditions | Reject wrappers and shadow nested values; no generated price, stop, target, tranche or de-risking action |
| 5 Heat/allocation | Nominal `PortfolioExposure`, equity, risk amounts, candidate and sector allocation | Reject shadow at object and nested numeric fields; unchanged heat/allocation calculation |
| 6 Earnings | Explicit scheduled and verified timestamps, calendar and existing-position exemptions | Reject shadow timestamps and financial filings masquerading as schedule observations; five-session policy unchanged |

The actual upstream paths are universe analysis, historical analytical replay,
historical portfolio gate replay and canonical portfolio gate activation.
They now inspect supplied registry/mode/eligibility **before** extracting scalar
scores or selecting from source rows. Historical incumbent references are checked
through the existing repository reader. No new repository method is introduced.
Canonical scores reuse their existing integrity verification. The stored gate
artifact and Six Gates evidence adapter reject foreign/shadow registries before
rehydration/projection. Existing PIT selection within V1 remains unchanged;
there is no latest-registry fallback.

## Minimum typed, non-persistent compatibility context

`GateEvidenceLineage` is an immutable descriptive dependency reference:

- exact `GateInput` field name;
- canonical registry version, explicit ACTIVE/SHADOW mode;
- original strategy reference and source policy version, explicitly nullable
  when the legacy source does not carry them (no invented lineage);
- timezone-aware UTC source as-of;
- nonempty, unique, deterministically ordered source fingerprints;
- explicit score, execution and portfolio-action eligibility flags.

`GateEvidenceContext` binds an immutable ordered tuple of these references to
the complete supplied `GateInput` fingerprint, execution as-of and gate-policy
version. Its own fingerprint covers every field except itself. Duplicate or
conflicting field references, malformed fingerprints, future evidence, tampered
bindings and contradictory shadow-authority flags fail closed. Equivalent aware
times normalize to UTC. A holding date remains a date, not an invented timestamp.
This context is an optional keyword on the existing evaluator. It cannot replace
any input, infer missing evidence, or grant approval. All supplied incompatible
references, including optional ones, are rejected rather than silently dropped.

No fields are added to stored `GateInput` or `ExecutionGateEvaluation` schemas.
No audit table, migration, result rewrite, API, UI or runtime wiring is added.
The context is **not automatically populated from production storage** in this
slice. Its fingerprint is a content-integrity binding, not an attestation that
an arbitrary caller has supplied an authentic upstream source.

## Fail-closed behavior and V1 compatibility

`GateVersionBlocked` is a controlled `ValueError` with compatibility state
`VERSION_BLOCKED`. No gate result is emitted on admission failure. The state is
not PASS, an investment FAIL, NEUTRAL or NOT_APPLICABLE.

Stable principal reasons:

- `V2_SHADOW_GATE_CONSUMPTION_FORBIDDEN` (existing B07 spelling retained).
- `CROSS_REGISTRY_GATE_CONSUMPTION_FORBIDDEN`.
- `GATE_EVIDENCE_TYPE_UNVERIFIED` / `GATE_NUMERIC_EVIDENCE_INVALID`.
- `GATE_LINEAGE_BINDING_MISMATCH` / `GATE_LINEAGE_FINGERPRINT_MISMATCH`.
- `GATE_LINEAGE_FUTURE_EVIDENCE`.
- `GATE_LINEAGE_DUPLICATE_OR_CONFLICTING_DEPENDENCY`.

Raw V2 results, diagnostic envelopes, Brain research sidecars and portfolio
observations are rejected before all six gate methods. READY core/component
states and valid measurements never grant eligibility. Mixed required evidence
cannot drop its shadow dependency and proceed. Ambiguous research-shaped inputs,
shadow metadata dictionaries, nonfinite numbers, unknown numeric states and
non-nominal wrappers are not converted to valid values. Known component and
diagnostic dependency tuples are inspected; cycles fail closed.

The canonical production version remains `diagnostic-registry-v1`. The exact
pre-existing engine fixture label `v1` is retained without rewriting returned
lineage; it is not accepted by the new canonical lineage contract. Empty, None,
unknown, V2 and latest/prefer-newer selectors do not select a registry.

Previous B03–B07 scoring, synthesis, thesis, Brain/portfolio and immutable
approval/receipt artifacts remain unchanged. Historical source-scope tests are
pinned to their completed checkpoints; this slice independently checks its
exact permitted source set and compares every existing gate method AST.

## Earnings/source limitation and conservative B08 status

Historical replay previously selected a generic payload containing an
`earnings_scheduled_at` key. It now refuses typed financial observations,
fundamental-kind observations and payloads marked by `period_end`, `filing_date`
or `publication_timestamp` as a schedule source. Those dates alone produce no
schedule. Disclosed shadow metadata is rejected before timestamp parsing.
The existing non-financial schedule path and verified-time fallback to its
observation market timestamp are **not redefined** in this compatibility slice.

Consequently, a bare datetime already mislabeled by an upstream producer cannot
have its true origin recovered at the scalar gate boundary. Likewise, legacy
stored comparison-score strings lack mandatory diagnostic-registry lineage.
Their absence must not be disguised as a complete provenance guarantee.
This slice prevents disclosed and typed cross-version substitution and provides
the new binding contract, but does not retroactively authenticate legacy scalars
or introduce a new official earnings-calendar data contract.

**B08 = CLOSED_FOR_SHADOW_COMPATIBILITY**, not
`CLOSED_FOR_ACTIVATION_COMPATIBILITY`. Production V2 activation remains blocked.
The remaining repair is to bind required inputs to verified source lineage at
the existing producers/readers (including scheduled-event origin), with explicit
legacy unavailable behavior, before claiming activation compatibility. Do not
create another gate engine, silently migrate records or invent official evidence.

| Other blocker | Status retained |
| --- | --- |
| B03 / B05 / B06 | PARTIALLY_CLOSED |
| B04 | CLOSED_FOR_ACTIVATION_SAFETY (prior scoped closure only) |
| B07 | Shadow propagation implemented; production activation blocked |
| B09 / B14 | STILL_BLOCKING_ACTIVATION |
| B11–B13 BANK/NBFC/INSURER | DEFERRED / POLICY_BLOCKED |

## Audit and validation

The deterministic receipt executes 21 synthetic scenarios against the exact
frozen baseline and current gate engine under the existing approved production
policy. Every six-gate result is equal. Each gate has an original policy version,
policy fingerprint, accepted registry, required families, shadow rejection,
V1 replay fingerprint and executable-case fingerprint. No real portfolio is
evaluated, no gate result is persisted and no provider is called.

- New focused tests: **96 passed / 0 failed / 2 warnings**.
- Final expanded affected regression: **732 passed / 0 failed / 2 warnings**.
- First complete backend run: **4090 passed / 1 failed / 6 skipped / 2 warnings**,
  exit 1, 334.52 seconds. The sole failure was
  `test_economic_intelligence_has_no_decision_engine_or_action_imports`: its broad
  textual package prohibition also rejected the new pure admission helper.
- The only correction after that run was test-only: permit the one exact
  `require_gate_source` import in the stored Six Gates adapter while retaining
  all engine/scoring/action prohibitions and explicitly forbidding evaluation
  calls. No application code changed. This narrow correction and the additional
  full run were reported before execution under the continuation's exception.
- Additional final full backend run: **4091 passed / 0 failed / 6 skipped /
  2 warnings**, exit 0, 280.57 seconds. There were two full runs total, not one
  uninterrupted green run. Source/test hashes stayed unchanged during the final
  run. Warnings are the existing Starlette/httpx and AnyIO deprecations; skips
  are existing opt-in provider/PostgreSQL integration checks.
- SQLite read-only integrity: **ok**; FK violations: **0**. Database size and
  modification time unchanged. FinancialFacts=6118; CorporateFilings=455;
  portfolio snapshots=1; paper trades=0; trade plans=0; generic strategy/result
  tables=0; canonical definitions=1; canonical diagnostics=2074; canonical and
  generic gate evaluations=0. No production gate result was created.
- Deterministic receipt:
  `sha256:81943ad5cf3645f222887f640d5b9f6becd22ccadba3e187578bf9ac408c75d4`.
- **272** local Markdown links/anchors passed; whitespace, text-only/private-path
  checks and `git diff --check` passed.

Defensive review retained exact existing gate method ASTs and production policy
bytes. It added rejection before nested numeric conversion and before source
selection, avoided re-reading a repository iterable, and preserved the nullable
legacy provenance gap explicitly. The two existing static source-boundary tests
now allow only the pure admission import, never the engine; historical snapshot
tests remain pinned to their original completed scope. No threshold, calendar,
score, rotation, portfolio or action policy was changed.

Preserved: ONE_CANONICAL_61_DIAGNOSTIC_REGISTRY=TRUE; V1_ACTIVE=TRUE;
V2_ACTIVE=FALSE; V2_SHADOW_ONLY=TRUE; NO_SILENT_REGISTRY_REWRITE=TRUE;
NO_SYNTHETIC_REPORTED_FACTS=TRUE; UNKNOWN_V2_STATE_MUST_NEVER_DEFAULT_POSITIVE=TRUE;
NO_SILENT_SCORE_WEIGHT_RENORMALIZATION=TRUE; AI_DECISION_AUTHORITY=FALSE.
HSI_DATA_BUILD_VS_BUY_PRINCIPLE_V1 remains FROZEN. The mandatory Build-vs-Buy
audit is not triggered because no acquisition occurs.
HSI_EFFICIENT_VALIDATION_EXECUTION_POLICY_V1 remains ACTIVE.

Exactly one next continuation:
**FUNDAMENTAL_V2_SIX_GATES_VERSION_COMPATIBILITY_REPAIR**. Not started.

## Checkpoint files

- [README.md](../../README.md)
- [app/backtest/analytical.py](../../app/backtest/analytical.py)
- [app/backtest/portfolio_gates.py](../../app/backtest/portfolio_gates.py)
- [app/gates/engine.py](../../app/gates/engine.py)
- [app/intelligence/six_gates_evidence.py](../../app/intelligence/six_gates_evidence.py)
- [app/portfolio/canonical_six_gates.py](../../app/portfolio/canonical_six_gates.py)
- [app/portfolio/canonical_six_gates_activation.py](../../app/portfolio/canonical_six_gates_activation.py)
- [app/universe_analysis/service.py](../../app/universe_analysis/service.py)
- [tests/unit/test_fundamental_v2_brain_lineage.py](../../tests/unit/test_fundamental_v2_brain_lineage.py)
- [tests/unit/test_fundamental_v2_downstream.py](../../tests/unit/test_fundamental_v2_downstream.py)
- [tests/unit/test_unified_intelligence_six_gates_evidence.py](../../tests/unit/test_unified_intelligence_six_gates_evidence.py)
- [app/gates/version_compatibility.py](../../app/gates/version_compatibility.py)
- [docs/architecture/FUNDAMENTAL_V2_SIX_GATES_VERSION_COMPATIBILITY_V1.md](../../docs/architecture/FUNDAMENTAL_V2_SIX_GATES_VERSION_COMPATIBILITY_V1.md)
- [docs/architecture/FUNDAMENTAL_V2_SIX_GATES_VERSION_INVENTORY.json](../../docs/architecture/FUNDAMENTAL_V2_SIX_GATES_VERSION_INVENTORY.json)
- [docs/architecture/FUNDAMENTAL_V2_SIX_GATES_VERSION_RECEIPT.json](../../docs/architecture/FUNDAMENTAL_V2_SIX_GATES_VERSION_RECEIPT.json)
- [scripts/audit_fundamental_v2_gates.py](../../scripts/audit_fundamental_v2_gates.py)
- [tests/unit/test_fundamental_v2_gate_version.py](../../tests/unit/test_fundamental_v2_gate_version.py)
- [tests/unit/test_economic_news_intelligence.py](../../tests/unit/test_economic_news_intelligence.py)
