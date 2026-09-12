# Final Six Gates authority routing closure

Status: `CLOSED_FOR_ACTIVATION_COMPATIBILITY / GATE_SOURCE_DATA_NOT_READY`.
Baseline: `c76affb4dad6521a031ebdd4f294d396aee04216`, clean `main`.
This is the last generic B08 repair; **no Repair 4** is proposed.

## Governance meaning

B08_VERSION_COMPATIBILITY is closed because actual score/holding producers
are independently verified and every other populated source dependency is
rejected before arithmetic. This is **compatibility of enforcement**, not
approval to consume V2 scores or evidence in V1 gates, not a claim that missing
sources exist, and not execution clearance. It does not lift B09 or B14.
V2 remains rejected, shadow-only and inactive. Any future V2 activation still
requires its separately approved policies and the remaining activation gates.

`V1_ACTIVE=TRUE / V2_ACTIVE=FALSE / V2_SHADOW_ONLY=TRUE`.
`AI_DECISION_AUTHORITY=FALSE`. One canonical 61-rule registry; no score-weight
renormalization, caller-self-attested authority, cross-registry laundering,
fabricated producer, unverified calendar clearance or positive unknown state.
Six Gates remain analytical/evidence-only; no order or portfolio operation.
`HSI_EFFICIENT_VALIDATION_EXECUTION_POLICY_V1=ACTIVE`.

The [Repair 2 matrix](FUNDAMENTAL_V2_GATE_SOURCE_AUTHORITY_MATRIX.json) and
[receipt](FUNDAMENTAL_V2_GATE_SOURCE_AUTHORITY_RECEIPT.json) are frozen BEFORE
evidence and replay unchanged. The new [two matrices plus 36-field inventory](FUNDAMENTAL_V2_GATE_AUTHORITY_CLOSURE_MATRICES.json)
and [closure receipt](FUNDAMENTAL_V2_GATE_AUTHORITY_CLOSURE_RECEIPT.json) distinguish
source readiness explicitly. They supersede the prior B08 conclusion only;
they do not rewrite prior findings or evidence.

## Exact 36-field baseline

Every dotted member is a separate row in the machine inventory. Five metadata
fields are binding/audit data, not five additional admitted producers.

| Gate | Exact fields (36 total) | BEFORE authority |
| --- | --- | --- |
| Binding only (5) | `scorecard_id`, `snapshot_id`, `snapshot_as_of_timestamp`, `evidence_ids`, `diagnostic_ids` | NOT_CLEARANCE_AUTHORITY |
| 1 (2 admitted) | `raw_decision_score`, `comparison_score` | INDEPENDENT_SCORE_ATTESTATION_READY |
| 1 (2 blocked) | `expected_incremental_return`, `modeled_switching_friction` | PRODUCER_ADAPTER_UNAVAILABLE |
| 2 (1 admitted) | `holding_entry_date` | STORED_HOLDING_BINDING_READY |
| 2 (1 blocked) | `atr_expansion` | PRODUCER_ADAPTER_UNAVAILABLE |
| 3 (8 blocked) | `surveillance.id`, `.effective_at`, `.source`, `.authoritative`, `.asm_stage`, `.gsm_stage`, `.circuit_limit`, `.evidence_ids` | PRODUCER_ADAPTER_UNAVAILABLE |
| 4 (9 blocked) | `trade_plan.id`, `.initial_tranche`, `.t1_reduction`, `.stop_defined`, `.t1_defined`, `.breakeven_conditions`, `.structural_conditions`, `.strategy_version`, `.configuration_version` | PRODUCER_ADAPTER_UNAVAILABLE |
| 5 (6 blocked) | `exposure.portfolio_equity`, `.existing_risk_amount`, `.candidate_risk_amount`, `.candidate_allocation`, `.sector_allocation`, `.evidence_ids` | PRODUCER_ADAPTER_UNAVAILABLE |
| 6 (2 blocked) | `earnings_scheduled_at`, `earnings_schedule_verified_at` | EARNINGS_CALENDAR_AUTHORITY_NOT_READY |

The **exact eight blocked top-level inputs** remain:
`expected_incremental_return`, `modeled_switching_friction`, `atr_expansion`,
`surveillance`, `trade_plan`, `exposure`, `earnings_scheduled_at`,
`earnings_schedule_verified_at`. No suitable new producer was found for any of
them. Existing score (two paths) and stored holding-date authority are reused
unchanged; **zero new adapters/producers** were invented.

## Producer discovery and exact remaining work

| Gate / input | Existing canonical capability and missing admission semantics | Readiness / exact blocker | One future bounded source slice |
| --- | --- | --- | --- |
| 1 expected return | Replay/rotation accept hypothetical expected-benefit values. They have no independently approved scenario, horizon or advantage provenance. No return forecast is authorized here. | SOURCE_GOVERNANCE_REQUIRED / GATE1_FRICTION_POLICY_AUTHORITY_NOT_READY | GATE1_FRICTION_POLICY_AUTHORITY_V1 |
| 1 modeled friction | Immutable effective-dated `SixGatesProductionPolicy` and `NseCashDeliveryFrictionModel` already define statutory formula, score advantage and economic hurdle. User turnover, brokerage, slippage, tax and taxable services are not fixed approved assumptions. No scenario approval/known-at carrier exists. | SOURCE_GOVERNANCE_REQUIRED / GATE1_FRICTION_POLICY_AUTHORITY_NOT_READY | GATE1_FRICTION_POLICY_AUTHORITY_V1 |
| 2 ATR expansion | `TechnicalAnalysisEngine.atr` returns versioned Wilder ATR with observation IDs, as-of, evidence and validation status. Governed Pre-Breakout materialization consumes daily ATR14 contraction. Neither defines holding-period displacement measured in ATRs: timeframe, anchor and normalization are not established. | SOURCE_GOVERNANCE_REQUIRED / GATE2_ATR_AUTHORITY_NOT_READY | GATE2_ATR_EXPANSION_SOURCE_GOVERNANCE_V1 |
| 3 surveillance | Approved `official-nse-surveillance-v1` declaration requires ASM/GSM/price-band/security-status coverage. `SurveillanceObservation` is a carrier; replay wraps generic metadata. No official observation producer proves source, coverage, time, revision and eligibility. | SOURCE_NOT_IMPLEMENTED / GATE3_SURVEILLANCE_SOURCE_AUTHORITY_NOT_READY | GATE3_SURVEILLANCE_SOURCE_AUTHORITY_V1 |
| 4 plan | Stored `app.signals.TradePlan` and governed Pre-Breakout assessment exist. The plan lacks its own instrument/as-of/policy fingerprint, tranche/reduction and breakeven management terms. Assessment eligibility is pre-candidate, not Gate 4 plan approval. Linking a SignalRecord that already requires gates would be circular. | SOURCE_GOVERNANCE_REQUIRED / GATE4_TRADE_PLAN_AUTHORITY_NOT_READY | TRADE_PLAN_AUTHORITY_CONTRACT_V1 |
| 5 exposure | `PortfolioSnapshot` has identity/cutoff, risk/heat and exposure; holding acquisition binding already works. It does not contain an independently approved candidate risk/allocation/sector scenario. Replay caller amounts do not supply that authority. Production cash, equity and heat are unknown. | SOURCE_GOVERNANCE_REQUIRED / GATE5_RISK_ALLOCATION_AUTHORITY_NOT_READY | PORTFOLIO_RISK_SCENARIO_AUTHORITY_V1 |
| 6 scheduled time | `CorporateFiling`, `BoardMeetingMetadata`, primary-source adapters and PIT/revision storage exist. Results-purpose scheduling, canonical date/session semantics and source verification/cancellation handling are not admitted. Candidate `VerifiedEarningsScheduleEvidence` explicitly remains UNVERIFIED_SOURCE_AUTHORITY. | SOURCE_AVAILABLE_ADAPTER_MISSING / EARNINGS_CALENDAR_AUTHORITY_NOT_READY | EARNINGS_CALENDAR_SOURCE_GOVERNANCE_V1 |
| 6 verification time | Must belong to the same admitted future-schedule source and cover receipt/known-at/revision eligibility. Cannot use a historical filing time, period end, inferred cadence or forecast. | SOURCE_AVAILABLE_ADAPTER_MISSING / EARNINGS_CALENDAR_AUTHORITY_NOT_READY | EARNINGS_CALENDAR_SOURCE_GOVERNANCE_V1 |

Code references: [production policy](../../app/gates/production_policy.py),
[technical engine](../../app/analysis/technical.py), [indicator lineage](../../app/analysis/models.py),
[Pre-Breakout materializer](../../app/strategies/pre_breakout/materialization.py),
[setup assessment](../../app/strategies/pre_breakout/setup_assessment.py),
[TradePlan](../../app/signals/models.py), [portfolio contracts](../../app/portfolio/models.py),
[historical gate adapter](../../app/backtest/portfolio_gates.py),
[filing contracts](../../app/filings/models.py), [filing providers](../../app/filings/providers.py),
[filing store](../../app/filings/store.py), [candidate calendar](../../app/gates/earnings_schedule_evidence.py).

Approved fixed policy is already bound by `selected_production_gate_engine`
through `selected_six_gates_production_policy(as_of=...)` and integrity checks.
Its complete gate configuration is reused exactly, with an isolated test of
the inclusive effective-time boundary. No market-data attestation is required
for fixed approved constants. **Policy existence/hash does not approve a
caller scenario**, and fixed rates alone cannot determine total switching cost.
No friction/tax/ATR formula or version is changed in this slice.

`CONTRACT_EXISTS_DATA_ABSENT` would be appropriate only for a fully adequate
authority contract lacking rows. It is **not** used for the incomplete Gate 4
mapping merely because `trade_plans=0`. Likewise canonical bars and ATR are not
declared absent: it is the exact Gate 2 expansion producer that is missing.

## Bounded official-calendar feasibility

Research date: 2026-09-12. No HSI provider acquisition or bulk data operation.

- The [official NSE board-meeting filings surface](https://www.nseindia.com/companies-listing/corporate-filings-board-meetings)
  exposes company/meeting filters and board-meeting detail. Indexed result
  headings include purpose, meeting date and broadcast timestamp; the opened
  dynamic page did not supply a complete downloadable row set.
- NSE's own [issuer board-meeting disclosures](https://www.nseindia.com/static/investor-relations/board-meetings)
  explicitly distinguish announcement date from meeting date: for example,
  17-Jul-2026 announcement for a 30-Jul-2026 results meeting. This proves that
  a primary notice can announce a future meeting; it does not prove that the
  event remained unchanged, provide all-company coverage, or authorize an
  automated HSI feed.

Conclusion: `CAN_CURRENT_OFFICIAL_SOURCE_PROVE_FUTURE_EARNINGS_SCHEDULE` is
**yes for an explicitly announced results-meeting date**, not for an inferred
release time, absence of a meeting, or guaranteed occurrence.
`SOURCE_AVAILABLE_ADAPTER_MISSING`. A cited third-party issuer PDF search hit
could not be opened (cache miss); it is not relied on for admission.

The next source-governance slice must settle exact instrument identity,
results-purpose classification, date-only versus instant/session handling,
exchange timestamp timezone, local receipt/known-at, notice identity/content
hash, corrections/postponements/cancellations, conflict handling and coverage
freshness. General board meetings are not automatically earnings meetings.
Historical result/period/filing dates and AI predictions remain forbidden.
No retrospective observation timestamp is fabricated from this web research.

## Matrix 1: compatibility, not current evidence readiness

| Gate | Version compatibility | Authority enforcement | Caller spoof resistance | V2 rejection | V1 replay |
| --- | --- | --- | --- | --- | --- |
| 1 | CLOSED_FOR_ACTIVATION_COMPATIBILITY | Independent score producer/reader; scenario rejects | Enforced | VERSION_BLOCKED | Unchanged |
| 2 | CLOSED_FOR_ACTIVATION_COMPATIBILITY | Exact stored holding; expansion rejects | Enforced | VERSION_BLOCKED | Unchanged |
| 3 | CLOSED_FOR_ACTIVATION_COMPATIBILITY | Unadmitted source rejects, not caller bool | Enforced | VERSION_BLOCKED | Unchanged |
| 4 | CLOSED_FOR_ACTIVATION_COMPATIBILITY | Unadmitted management plan rejects | Enforced | VERSION_BLOCKED | Unchanged |
| 5 | CLOSED_FOR_ACTIVATION_COMPATIBILITY | Unadmitted candidate scenario rejects | Enforced | VERSION_BLOCKED | Unchanged |
| 6 | CLOSED_FOR_ACTIVATION_COMPATIBILITY | Unadmitted calendar rejects | Enforced | VERSION_BLOCKED | Unchanged |

The threat model is unchanged: trusted Python application composition and
canonical store, not malicious replacement of code, injected readers or DB
contents. No PKI/HMAC claim. Synthetic 21-case replay verifies arithmetic only;
it is not source authenticity or real production clearance proof. Real
producer/SQLite-reader tests run separately from synthetic fixture authority.

## Matrix 2: frozen production source readiness

Read-only production observation: 2026-09-12, unchanged DB size/mtime. This
receipt is not a live status monitor or a freshness guarantee after that audit.

| Gate | Required producer | Current data | Freshness proven? | Real-evidence clearance now? | SenseEdge impact |
| --- | --- | --- | --- | --- | --- |
| 1 | Exact scores + approved economic scenario | 3 V1 COMPLETE cards at 2026-08-31; 1 approved gate policy; no scenario authority | No current candidate/incumbent freshness asserted | No for rotation; existing non-rotation exemption retained | Economic rotation clearance unavailable |
| 2 | Stored holding date + canonical expansion | 1 snapshot; existing ATR infrastructure; no expansion result | No current expansion proof | No velocity evidence; existing context exemptions retained | Velocity review/adjustment cannot be substantiated |
| 3 | Fresh official surveillance | No admitted producer/data | No | No | Fresh entry cannot receive surveillance clearance |
| 4 | Governed management plan | 0 plans; generic plan/setup contracts are incomplete for admission | No | No | Candidate cannot become ENTRY_READY |
| 5 | Approved candidate/portfolio risk scenario | 1 PARTIAL snapshot; cash UNKNOWN, equity/heat null | No complete current risk evidence | No | Allocation/execution readiness blocked |
| 6 | Verified future results notice with revision coverage | 455 filings: 425 results, 30 ownership; 0 board-schedule metadata rows | No | No fresh-entry clearance; risk-management exemption retained | Earnings-blackout clearance unavailable |

These are execution-readiness blockers, **not stock bearishness**. A missing
populated source fails with `VERSION_BLOCKED`; absent inputs retain original
gate semantics. In particular Gate 4 already returns `FAIL` for no plan, so
the aggregate is `BLOCKED`; this is stricter than insufficiency and unchanged.
Other missing inputs can be `INSUFFICIENT_DATA`, while authorized context
exemptions remain exempt. No test converts those exemptions into data readiness.

## Bounded implementation and validation

Only [source-readiness descriptors](../../app/gates/source_readiness.py) and
the absent-source branch in [existing authority](../../app/gates/source_authority.py)
change application code. `GateSourceNotReady` subclasses `GateVersionBlocked`,
preserves its legacy string/compatibility state and adds immutable `source_gap`
classification. Callers cannot supply readiness to `evaluate`; descriptors
never register or admit producers. Existing API messages and prior receipts
remain compatible. No gate arithmetic, policy, source adapter, selection
repository, schema, API/UI or production runtime is modified.

New [closure tests](../../tests/unit/test_gate_authority_closure.py) cover exact
eight/36-field enumeration, deterministic replay, named rejection before every
formula, real-reader no-write rejection, all seven action contexts, fake READY
descriptors, policy/PIT/tamper binding, no-plan versus incomplete-contract
distinction, unknown capital, and historical/predicted calendar attacks.
Prior real-source tests retain identity/version/fingerprint/PIT positive and
negative coverage for the three admitted fields. Positive admission tests for
genuinely absent producers are **not applicable**, not mocked successes.

One initial focused expectation incorrectly assumed all missing inputs were
insufficient; seven parameter cases exposed the existing Gate 4 FAIL. Only
the new test was corrected to assert that stricter existing behavior.

Validation:

| Check | Completed result |
| --- | --- |
| Final closure + real-source focused bundle | 75 passed, 0 failed, 2 warnings; 9.78 s after EOF-only cleanup (37 new closure cases plus 38 existing source-authority cases) |
| Affected 25-module regression | 841 passed, 0 failed, 2 warnings; 101.10 s; final three raw-plan rejection cases subsequently included in focused/full validation |
| ONE full backend suite | 4200 passed, 0 failed, 6 skipped, 2 warnings; exit 0; 370.31 s |
| JUnit completion | 4206 tests, 0 failures, 0 errors, 6 skips |
| Frozen arithmetic and prior receipts | 21 V1 scenarios identical; Repair 2 matrix and receipt replay unchanged |
| Admission attack replay | 0 unsafe inputs admitted; no caller receipt/source label grants authority |
| Scope/secret-shape check | Exactly eight intended files; no private/runtime paths or credential-shaped literals |
| Full-suite content freeze | All eight SHA256 hashes identical during full suite; afterward final documentation results added and one EOF blank line removed from the readiness module with identical Python AST and focused revalidation |
| Local Markdown links/anchors | 267 checked, 0 errors |
| Whitespace / git diff --check | Passed |

The two warnings are existing Starlette/httpx and AnyIO deprecations. Skips are
the opt-in GDFL/GNews/Kotak/Upstox integrations and two PostgreSQL tests; no
test was disabled or weakened. B03-B07 regression includes the exact 31 V1
score mappings and unknown/shadow non-scoring, shadow non-support for thesis,
unchanged holding/sell/rotation outputs, rejection before portfolio ledger
work and rejection before any gate formula. The old frozen policy, technical,
portfolio and source-provenance modules are source-content checked against the
accepted baseline in the focused suite.

The stored production policy was independently decoded and passed its existing
integrity verifier with zero connection changes. The production connection used
SQLite URI `mode=ro` plus `PRAGMA query_only=ON`, never the repository's
schema-initializing constructor. Complete integrity result: `ok`; FK violations:
`0`. Database size `18346504192` and mtime-nanoseconds `1789150260641346800`
were identical before/after the scan and to the initial audit. Portfolio payload
fingerprint remained `sha256:4fe5ca7f9cc36706367b269efff559c9a9ba54a46ee54e98815420cfdb0c1889`.

| Production invariant | Final read-only result |
| --- | --- |
| FinancialFacts / CorporateFilings | 6118 / 455, unchanged |
| Portfolio snapshots / cash | 1 / UNKNOWN, unchanged |
| Trade plans / paper trades | 0 / 0 |
| Generic strategy_versions / diagnostic_results | 0 / 0 |
| Canonical strategy definitions / diagnostic results | 1 / 2074, unchanged |
| Canonical / generic execution-gate evaluations | 0 / 0 |
| Approved production gate policies | 1, existing integrity check passed |
| Broker/order records | No broker/order tables exist; no such calls performed |

No acquisition, plan creation, portfolio mutation, per-tick write, provider
execution, credential operation or trading side effect occurred. All temporary
test databases/JUnit output remain Git-excluded. No remote push is authorized.

## Exact next continuation (not started)

**EARNINGS_CALENDAR_SOURCE_GOVERNANCE_V1** only. Priority: hard fresh-entry
blocker, an explicitly approved NSE source declaration, existing filing/PIT
infrastructure and demonstrated primary future-notice evidence. It should
precede an acquisition adapter; timestamp/date and revision/cancellation
semantics must be governed first. The other field-specific slices remain
named backlog, not parallel work. No generic Repair 4 and no V2 activation.
