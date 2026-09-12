# Fundamental V2 Six Gates Provenance Repair

Status: **IMPLEMENTED_REJECTION_SAFETY / CLOSED_FOR_SHADOW_COMPATIBILITY / V2_NOT_ACTIVE**.
Baseline: `5da0111324707ff1f95543d598571463fe63522c`, branch `main`.
Authority: bounded input-provenance repair, not a gate/policy redesign or activation.

## Scope and reproducible evidence

- [Previous B08 compatibility receipt](FUNDAMENTAL_V2_SIX_GATES_VERSION_COMPATIBILITY_V1.md) is a frozen historical checkpoint; its optional-context description is superseded here at the current engine boundary.
- [Exact machine inventory](FUNDAMENTAL_V2_GATE_PROVENANCE_REPAIR_INVENTORY.json): every GateInput field, expanded nested field, producer, authority domain, required version dimensions and admission.
- [Deterministic repair receipt](FUNDAMENTAL_V2_GATE_PROVENANCE_REPAIR_RECEIPT.json).
- [Read-only isolated audit](../../scripts/audit_gate_provenance_repair.py).
- [Score source binding](../../app/gates/score_provenance.py), [domain binding](../../app/gates/version_compatibility.py), [unchanged six calculations](../../app/gates/engine.py).
- [Focused attacks and invariants](../../tests/unit/test_gate_provenance_repair.py).

No schema, DB migration, provider, API, UI, scheduler or runtime startup changes.
No real gate evaluation, financial acquisition, portfolio mutation or order is
executed. Existing analytical eligibility remains evidence only. No score,
rotation, heat, plan, blackout, horizon or investment policy changes.

## Admission contract

`GateScoreEvidence / gate-score-provenance/v1` retains a complete existing
`DecisionScorecard` or `CanonicalDecisionScorecard`, its deterministic content
fingerprint and, for an incumbent comparison, the original `ExecutionGateEvaluation`
plus its fingerprint. The factory accepts no numeric score argument. Canonical
cards retain and verify their original persisted artifact/policy fingerprints.
Generic cards preserve their complete original components, warnings, strategy,
configuration, registry and timestamps; no historical registry is inferred.

Before any gate method runs, each non-null candidate/incumbent numeric score
must match its source. Candidate identity, instrument, strategy, scoring config,
value and PIT must agree. Incumbent source card and original comparison result
must agree on identity, instrument, raw score, strategy and scoring config;
comparison policy, value and PIT must match the requested gate evaluation.
V2, mixed versions, unknown versions, missing provenance, changed content and
future sources reject before arithmetic. A raw Decimal with stripped metadata
cannot pass, even when accompanied by the older descriptive registry context.

`GateEvidenceLineage` and `GateEvidenceContext` are extended, not replaced.
Neutral references carry exact source identity, source-contract version, source
policy, source as-of, known-at, source fingerprints and field-value fingerprint.
They have **no diagnostic registry, mode or strategy stamp**. Neutral score and
portfolio-action eligibility are fixed false; execution eligibility here means
admissibility as analytical gate evidence, never authority to act. Missing,
contradictory, future, duplicate or tampered references reject.

Every populated neutral field now requires its correct domain reference and a
complete input/context binding. Absent values remain absent and retain their
existing gate-specific insufficiency/exemption behavior. No zero, boolean,
schedule time, plan or financial metric is fabricated.

| Gate / input | Authority and version requirements | Admission / remaining limitation |
| --- | --- | --- |
| 1 candidate score | Existing score producer/card; registry, strategy, scoring policy, full-source fingerprint and PIT | Required exact candidate source binding; no raw-score admission |
| 1 incumbent comparison | Linked incumbent card **and original gate result**; original registry/scoring/gate versions | Unlinked legacy strings reject; all supplied sources checked before the existing ordered selection |
| 1 expected return / friction | Explicit hypothetical replay scenario or user-approved context; source/risk-policy versions | Not a diagnostic score; no expected return is calculated or asserted as an observed fact |
| 2 holding entry date | Governed holding state, snapshot/version and source fingerprint | No fake V1 stamp; automatic live producer binding remains absent |
| 2 ATR expansion | Canonical market/technical source and calculation version | No fake V1 stamp; automatic live producer binding remains absent |
| 3 surveillance | Original surveillance identity/effective time/authoritative flag plus source/policy binding | Nominal booleans only; generic boolean/shadow substitutes reject; original ASM/GSM/circuit/freshness tests unchanged |
| 4 plan | Exact plan identity; native strategy/configuration values plus source/version/fingerprint | No plan, price or approval generated; external approval authenticity remains the producer's responsibility |
| 5 heat/allocation | Snapshot and risk-policy authority; full frozen scenario/state binding | Hypothetical replay only where used; no live risk authority inferred from active V1 |
| 6 scheduled / verified times | Original corporate-event schedule, source identity, known-at, source/policy versions and fingerprint | No financial period, filing or observation-time fallback; calendar-source governance still incomplete |

All 36 expanded inventory rows are recorded, including binding metadata that
does not itself provide gate clearance. Exchange-calendar identity and the
unchanged gate configuration retain their existing authority; they are not
diagnostic-registry evidence.

## Known internal producers and historical compatibility

1. Universe analysis binds its existing score output. Its existing internal
   input factory can return `(GateInput, GateEvidenceContext)` explicitly. Raw
   externally supplied neutral values do not acquire implicit provenance.
2. Historical analytical replay binds its frozen score and selected
   `MarketObservation` records. `MarketObservation/v1` identifies the existing
   source **contract**, not a newly invented historical provider approval.
   Explicit earnings verification is mandatory; absence stays unavailable.
   Financial source kinds/period/filing fields cannot masquerade as schedules.
3. Historical portfolio replay reads the original linked incumbent score and
   gate result through existing readers. Missing links, wrong instruments,
   duplicate contexts, mismatched values or versions block before writes.
   Risk/friction scenario values bind the existing run version, policy, frozen
   snapshot and supplied hypothetical scenario; their evaluation cutoff is a
   replay scenario boundary, **not a claim of historical real-world knowledge**.
4. Canonical activation binds and verifies its selected canonical score. Neutral
   context must be provided explicitly; no production source adapter is invented.

Existing stored rows are never rewritten. Replaying old unlinked values now
fails closed; this is an explicit admission limitation, not a newly computed
investment FAIL. Known complete V1 source fixtures retain identical outcomes.
Historical test fixtures were supplied isolated linked incumbent artifacts with
the same original scalar values and gate assertions. No production provenance
was backfilled. Direct arithmetic tests use a clearly named synthetic fixture
adapter, never imported by application code. No global test monkeypatch bypasses
the production firewall.

## Defensive review and closure limits

- Six gate method ASTs, gate order, arithmetic, outcomes, thresholds, exemptions
  and production policy remain unchanged. Same 21 isolated approved-policy
  scenarios replay identically against the prior frozen engine.
- Zero **accepted raw registry/score ingress** paths remain among four production
  callers. A missing-source caller is rejected, not considered verified.
- Full arbitrary-Python source authentication is **not** proven. A caller can
  construct an entire legacy card and recompute a self-declared content hash;
  generic scorecards lack independent persisted producer attestation.
- Neutral references prove content/PIT binding, not that a caller's claimed
  authority is genuine. Legacy calendar records still lack an independently
  approved earnings-calendar source/version registry. No assertion that every
  producer version dimension is independently verified is made.
- B08 stays `CLOSED_FOR_SHADOW_COMPATIBILITY`, **not** activation-compatible.
  The stricter raw-scalar boundary is useful without overstating those three
  remaining authority gaps. B09 and B14 remain `STILL_BLOCKING_ACTIVATION`.

No B03/B05/B06, B07 or BANK/NBFC/INSURER governance status is advanced. One
canonical 61 registry remains; V1 active, V2 inactive/shadow-only. No silent
registry rewrite, score-weight renormalization or synthetic reported facts.
AI decision authority remains false. Build-vs-Buy remains frozen and is not
triggered: this slice performs no acquisition.

## Validation

- New focused provenance tests plus the corrected persistence fixture:
  **35 passed / 0 failed / 2 warnings** (34 new tests and one existing fixture test).
- Affected gate, score, Brain/Portfolio, historical/backtest and universe paths:
  **888 passed / 0 failed / 2 warnings**.
- First complete backend run: **4,124 passed / 1 failed / 6 skipped / 2 warnings**,
  338.04 seconds, exit 1. The sole failure was
  `tests/integration/test_execution_gate_persistence.py::test_execution_gate_evaluation_is_immutable_persisted_and_audit_reconstructable`:
  its isolated fixture still submitted unversioned scores and did not bind its
  raw candidate value to the persisted card. Only that test fixture was changed;
  persistence/immutability/reconstruction assertions were retained.
- Conditional additional full run, announced before execution under the narrow
  fixture exception: **4,125 passed / 0 failed / 6 skipped / 2 warnings**,
  326.17 seconds, exit 0. This is **two completed full runs**, not an uninterrupted
  first-run green result. Source hashes were unchanged between the full runs;
  only the named fixture changed after the first full run.
- Warnings: existing Starlette/httpx and AnyIO deprecations. Six skips: existing
  opt-in provider/PostgreSQL tests. No live provider test was enabled.
- Read-only production SQLite: **integrity ok / FK violations 0**. DB size
  18,346,504,192 bytes and mtime 1789150260641346800 ns unchanged. FinancialFacts
  6,118; CorporateFilings 455; portfolio snapshots 1; canonical definitions 1;
  canonical diagnostics 2,074. Generic strategy/results, paper trades, trade
  plans and both generic/canonical gate-evaluation tables remain zero.
  Portfolio payload matches the previous checkpoint; cash remains `UNKNOWN`.
- Deterministic receipt replay: 21 isolated scenarios, all six gate results
  identical to the prior baseline. No writes, acquisition or orders.
- Markdown local targets/anchors, whitespace, text-only/private-path review and
  `git diff --check` passed. No credential-shaped literals were found in the
  reviewed files; no credential store or secret environment was accessed.

## Reviewed file set

The bounded commit contains 24 files: 7 application/admission files, 2 isolated
audit scripts, 11 test/fixture files, and 4 documentation/index artifacts.

- `README.md`
- `app/backtest/analytical.py`
- `app/backtest/portfolio_gates.py`
- `app/gates/engine.py`
- `app/gates/score_provenance.py`
- `app/gates/version_compatibility.py`
- `app/portfolio/canonical_six_gates_activation.py`
- `app/universe_analysis/service.py`
- `docs/architecture/FUNDAMENTAL_V2_GATE_PROVENANCE_REPAIR_INVENTORY.json`
- `docs/architecture/FUNDAMENTAL_V2_GATE_PROVENANCE_REPAIR_RECEIPT.json`
- `docs/architecture/FUNDAMENTAL_V2_SIX_GATES_VERSION_COMPATIBILITY_REPAIR.md`
- `scripts/audit_fundamental_v2_gates.py`
- `scripts/audit_gate_provenance_repair.py`
- `tests/fixtures/gate_provenance.py`
- `tests/integration/test_execution_gate_persistence.py`
- `tests/integration/test_historical_portfolio_gates.py`
- `tests/integration/test_historical_rotation_replay.py`
- `tests/unit/test_canonical_six_gates.py`
- `tests/unit/test_execution_gates.py`
- `tests/unit/test_fundamental_v2_gate_version.py`
- `tests/unit/test_gate_provenance_repair.py`
- `tests/unit/test_six_gates_e2e_isolated_canary.py`
- `tests/unit/test_six_gates_production_policy.py`
- `tests/unit/test_universe_analysis_coverage.py`

Receipt fingerprint:
`sha256:ed32144c91adb4e4ce63bd509e0f6f32569bfb2e63329f393f41d7b88af77ae7`.

## Exactly one next continuation

`FUNDAMENTAL_V2_SIX_GATES_VERSION_COMPATIBILITY_REPAIR_2`.

Not started. No push is authorized by this slice.
