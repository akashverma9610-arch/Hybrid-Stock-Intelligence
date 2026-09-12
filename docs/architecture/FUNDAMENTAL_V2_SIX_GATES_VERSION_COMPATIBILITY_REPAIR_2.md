# Fundamental V2 Six Gates Source Authority Repair 2

Status: `IMPLEMENTED / V1_ACTIVE / V2_SHADOW_ONLY / ACTIVATION_BLOCKED`.

Baseline: `4027fb63b63000bd9437845d8199ffaa30d2f3dd`.
This bounded repair supersedes the authority limitations (not the frozen
receipts or arithmetic) in [Repair 1](FUNDAMENTAL_V2_SIX_GATES_VERSION_COMPATIBILITY_REPAIR.md).
See the [machine authority matrix](FUNDAMENTAL_V2_GATE_SOURCE_AUTHORITY_MATRIX.json)
and [deterministic receipt](FUNDAMENTAL_V2_GATE_SOURCE_AUTHORITY_RECEIPT.json).

## Authority is independent of submitted evidence

`GateInput`, `GateScoreEvidence` and `GateEvidenceContext` are data, not trust
roots. A caller cannot supply an attestation or authority to `evaluate`.
The engine's separately configured `source_authority` is an application
composition dependency. The default has no authority. A content hash, a V1
label, `authoritative=True`, or a claimed NSE source cannot establish trust.
All previous type, registry, fingerprint, PIT and value bindings run first;
authority admission then runs before any of the six arithmetic methods.

This is deterministic in-process provenance, not cryptographic authentication.
Replacing application code, monkeypatching the configured adapter, substituting
the canonical repository, or compromising its contents is outside this trust
boundary. No PKI, HMAC, secrets, signatures, network authentication, registry
registration endpoint or caller-controlled trust switch is added.

## Score attestation

The immutable `ScoreEvidenceAttestation` records score value, scorecard identity,
instrument, exact V1 registry, scoring **configuration** version, canonical
scoring **policy** version and its existing fingerprint, strategy reference,
UTC as-of, completeness/eligibility, execution-path eligibility, shadow=false,
producer identity, complete source fingerprint, diagnostic fingerprints,
optional original comparison-result fingerprint, contract version and its own
content fingerprint. It is audit output, never an admission credential.
The existing policy's bare hexadecimal fingerprint convention is retained;
the new content-attestation fingerprint uses the existing `sha256:` convention.

Two concrete adapters are implemented:

1. `ScoringRunGateAuthority`: the existing universe scoring boundary supplies
   its exact canonical runner output and scoring parameters independently of
   `GateInput`. The adapter invokes the unchanged `build_scorecard`, compares
   the entire resulting card, rejects duplicate/mixed/future diagnostic inputs,
   and detects mutation of its frozen input binding. It accepts no numeric
   score or claimed producer as constructor input. This neither changes the
   score formula nor evaluates new diagnostics.
2. `RepositoryGateAuthority`: independently reads the exact generic/canonical
   scorecard, checks its complete content against the submitted proof, admits
   only the existing scoring configuration, verifies linked diagnostic
   identity/instrument/strategy/PIT and canonical diagnostic fingerprints,
   and verifies the original stored gate result for incumbent comparisons.
   Missing historical linkage is rejected; nothing is rehashed to repair a
   source, inserted, backfilled, or retrospectively stamped V1.

An absent/None numeric score keeps the original missing-score/exemption policy;
it does not receive a positive score attestation. Receipt construction alone
is not proof of issuance: gate admission asks the independent adapter anew.

## Neutral authority and the exact remaining gaps

| Gate | Evidence | Implemented authority / remaining blocker |
| --- | --- | --- |
| 1 | Candidate/incumbent scores | Independent scoring/reader attestation; incumbent original gate must be stored and match. Hurdle arithmetic unchanged. |
| 1 | Expected return/friction scenario | Self-declared hypothetical numbers are rejected. The existing approved friction formula is not approval of a particular user scenario. Independent scenario adapter remains missing. |
| 2 | Score | Same score authority as Gate 1. No numeric fallback. |
| 2 | Holding duration | Exact stored `PortfolioSnapshot`, one active matching holding, its acquisition date, content fingerprint, snapshot as-of, transaction cutoff and existing cost-basis methodology version. No diagnostic registry is attached. |
| 2 | ATR | Canonical market evidence exists, but no exact admitted gate-ATR projection is established here. Populated unverified values are blocked. |
| 3 | Surveillance | Official NSE contract is declared in the approved policy. Generic `MarketObservation` payload/source-name/boolean is not an admitted authoritative producer. Blocked. |
| 4 | Trade plan | Existing stored `app.signals.models.TradePlan` and gate `TradeManagementPlan` are distinct contracts. No lossless approved producer mapping is invented. Caller-created plan values remain blocked. |
| 5 | Heat/allocation | Existing canonical portfolio exposure/risk is not approval of caller-created candidate risk/allocation. The exact governed frozen scenario adapter remains missing. Blocked. |
| 6 | Earnings schedule | Approved source declaration exists; a verified future-event producer/revision adapter does not. `EARNINGS_CALENDAR_AUTHORITY_NOT_READY`. |

The holding adapter uses `PortfolioHolding.acquisition_at.date()` descriptively
from the stored object. It does not invent a start date or holding-day count.
The lineage `known_at` must match the existing `source_transaction_cutoff`:
this is an internal portfolio transaction cutoff, **not** an external receipt
or publication timestamp. Snapshot as-of and cutoff must both be PIT-valid.
The source version is the stored cost-basis methodology version, not an
invented diagnostic registry or portfolio schema version. Snapshot mutations,
wrong instruments, multiple matching holdings, future state and mismatched
acquisition dates fail closed. No portfolio reconstruction or mutation runs.

Eight neutral fields still lack admitted production adapters (two belong to
the same calendar domain). No blanket “trusted internal” label admits them.
The matrix expands all 16 GateInput fields, including nested fields, into
36 rows. Snapshot IDs, evidence IDs and diagnostic IDs remain descriptive
binding/audit metadata; none independently authorizes a gate clearance.

## Future earnings calendar: declared is not operational

Repository evidence:

- [Approved production policy](../../app/gates/production_policy.py) already
  declares `official-nse-earnings-calendar-v1`, authority NSE, coverage
  `BOARD_MEETING` / `FINANCIAL_RESULTS`, and absence-is-pass=false.
- [Historical adapter](../../app/backtest/analytical.py) reads generic
  `corporate_event` payloads. That does not prove approved source acquisition,
  verification, completeness, or revision/supersession authority.
- Historical financial period ends, publication/filing timestamps and V2
  shadow financial timestamps are never future schedule evidence.

The candidate `VerifiedEarningsScheduleEvidence` is **not** an admitted source.
It describes instrument, future scheduled timestamp, event type, source
authority/reference, received time, known-at, source/policy version,
optional revision/supersession identities, source and content fingerprints.
Its only allowed verification state is `UNVERIFIED_SOURCE_AUTHORITY`; it
cannot self-upgrade to VERIFIED or clear Gate 6. Received <= known < scheduled
is required. No timestamp fallback, calendar acquisition, absence certificate,
new freshness/blackout threshold or calendar-policy activation is added.

## Compatibility and validation interpretation

The four production callers now use independent score adapters. Unsupported
neutral claims are intentionally blocked, including generic historical
calendar payloads and unapproved hypothetical risk scenarios. This is not
claimed as successful production source operationalization.

Frozen arithmetic and historical persistence tests contain explicitly
synthetic observations/scenario values. Their scoped test-only authority
composition preserves their original assertions and results. It is absent
from application code, and is not proof of production authenticity. New
authority tests run the real, unpatched producer/readers, including SQLite
reopen, canonical diagnostics, a stored holding snapshot and rejection of the
real historical adapter's unapproved calendar. No global test bypass exists.

The 21 frozen V1 Gate 1–6 scenarios remain identical. The six formula methods,
decision aggregation/order, exemptions, thresholds, policy files and scoring
weights are unchanged. Two old AST boundary tests now exclude the constructor
as well as `evaluate`; explicit dependency injection is the only constructor
change. All private method comparisons remain intact.

Completed validation:

| Check | Completed result |
| --- | --- |
| New source-authority tests | 38 passed / 0 failed / 2 warnings |
| Final authority/provenance/version bundle | 168 passed / 0 failed / 2 warnings |
| Affected score/Brain/portfolio/rotation/universe/gate regression | 1,052 passed / 0 failed / 2 warnings |
| Additional consumer/API checks | 38 passed / 0 failed / 2 warnings |
| **One full backend run** | **4,163 passed / 0 failed / 6 skipped / 2 warnings**, exit 0, 424.09 seconds |
| Frozen V1 arithmetic | 21 scenarios identical; all six private gate methods unchanged |
| Deterministic matrix / receipt | Replayed exactly; 11 explicit self-attestation attempts rejected |
| Edited Markdown local links / anchors | 252 checked, passed |
| Whitespace / git diff --check | Passed |
| Source/private-file scan | Intended text source/tests/docs only; no credential-shaped literals |

The warnings are the existing Starlette/httpx and AnyIO deprecations. The six
skips are opt-in GDFL/GNews/Kotak/Upstox validation and two unconfigured
PostgreSQL tests. No second full run was performed. Earlier focused/affected
iterations exposed receipt convention/fixture issues and the constructor AST
scope assertion; these were resolved before the single final full run.
All 20 files matched pre-full-run hashes after completion. Only this final
validation narrative was updated afterward; implementation/test hashes stayed
unchanged. No source content changed while the full suite ran.

Production SQLite was opened with `mode=ro` and `query_only=ON`:

- Integrity: `ok`; FK violations: **0**.
- FinancialFacts **6,118**; CorporateFilings **455**; portfolio snapshots **1**.
- Cash **UNKNOWN**; paper trades **0**; trade plans **0**.
- Generic strategy_versions **0**; generic diagnostic_results **0**.
- Canonical strategy definitions **1**; canonical diagnostic results **2,074**.
- Generic/canonical execution-gate evaluations both **0**.
- Size **18,346,504,192 bytes** and modification timestamp unchanged throughout
  the audit; the portfolio payload fingerprint matches the prior checkpoint.
- No production acquisition, live gate materialization or order was executed.

Receipt fingerprint:
`sha256:457ed0db9347e8a5996d201a7fb0f03895c8e46a0e51a3a21a1ec5d7e7438884`.

## Files in this bounded repair

Exactly 20 intended files (seven application files, one audit script, eight
test/fixture files, and four documentation/index artifacts):

```text
README.md
app/backtest/analytical.py
app/backtest/portfolio_gates.py
app/gates/earnings_schedule_evidence.py
app/gates/engine.py
app/gates/source_authority.py
app/portfolio/canonical_six_gates_activation.py
app/universe_analysis/service.py
docs/architecture/FUNDAMENTAL_V2_GATE_SOURCE_AUTHORITY_MATRIX.json
docs/architecture/FUNDAMENTAL_V2_GATE_SOURCE_AUTHORITY_RECEIPT.json
docs/architecture/FUNDAMENTAL_V2_SIX_GATES_VERSION_COMPATIBILITY_REPAIR_2.md
scripts/audit_gate_source_authority.py
tests/fixtures/gate_provenance.py
tests/integration/test_historical_analytical_replay.py
tests/integration/test_historical_portfolio_gates.py
tests/unit/test_fundamental_v2_brain_lineage.py
tests/unit/test_fundamental_v2_gate_version.py
tests/unit/test_gate_provenance_repair.py
tests/unit/test_gate_source_authority.py
tests/unit/test_universe_analysis_coverage.py
```

## Governance and next continuation

- B08 before/after: `CLOSED_FOR_SHADOW_COMPATIBILITY`, **not** fully activation-compatible.
- B09 / B14: `STILL_BLOCKING_ACTIVATION`.
- Measured caller-self-attested inputs accepted: **0** across the explicit
  score/domain attack matrix. This does not mean all producers are available.
- V1_ACTIVE=true; V2_ACTIVE=false; V2_SHADOW_ONLY=true.
- No cross-registry laundering, self-attested authority, unverified calendar
  clearance, unknown-V2-positive default, or score-weight renormalization.
- AI_DECISION_AUTHORITY=false. No action/order/provider execution, application
  API/UI activation, schema migration, production acquisition or portfolio write.

Exactly one next continuation:
`FUNDAMENTAL_V2_SIX_GATES_VERSION_COMPATIBILITY_REPAIR_3`.
It is **not started**. Non-calendar producer gaps remain, so neither horizon
activation compatibility nor a calendar-only next slice is claimed.
