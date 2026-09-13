# Gate 3 Surveillance Source Readiness V1

Follow-up: the [policy/source-semantics repair audit](GATE3_SURVEILLANCE_POLICY_SOURCE_REPAIR_V1.md)
adds official complete-list documentation, distinguishes security from series,
and clarifies the missing runtime status predicate and constant PASS annotation.
This earlier audit's measured counts and machine receipt remain unchanged.

**Status:** `GATE3_POLICY_SOURCE_SEMANTICS_REQUIRE_GOVERNANCE_REPAIR / DOCUMENTATION_ONLY / V1_ACTIVE / GATE_POLICY_V2_INACTIVE / NOT_ACTIVE`.

**Decision:** **C — `GATE3_POLICY_SOURCE_SEMANTICS_REQUIRE_GOVERNANCE_REPAIR`.** The bounded read-only probe proves that first-party NSE surfaces are reachable and structured for prospective positive observations. It does not prove the source semantics required to admit a fresh authoritative **clear** observation to production Gate 3. No collector, parser, storage, policy, gate, API, UI, runtime job, trade, order, portfolio mutation, or source state was changed by this audit. Its machine receipt is [the source-readiness receipt](GATE3_SURVEILLANCE_SOURCE_READINESS_V1.json).

This audit is governed by the frozen Gate 3 source contract in `app/gates/production_policy.py`, the exact carrier and evaluator in `app/gates/engine.py`, the source-authority checks in `app/gates/version_compatibility.py`, and the registry definition in `app/registry/canonical.py`. It does not amend any of them.

## 1. Exact current Gate 3 contract

| Contract element | Frozen V1 behavior | Audit conclusion |
| --- | --- | --- |
| Gate | `GATE_3_SURVEILLANCE` — Surveillance & Circuit Filter | Exactly one of six gates; unchanged. |
| Required carrier | `SurveillanceObservation(id, effective_at, source, authoritative, asm_stage, gsm_stage, circuit_limit, evidence_ids)` | All three substantive fields must be populated. `SECURITY_STATUS` is in the source contract but has no carrier field or evaluator semantics. |
| Authority | `OfficialSourceContract("official-nse-surveillance-v1", "NSE", ("ASM", "GSM", "PRICE_BAND", "SECURITY_STATUS"), latest_eligible_completed_session_required=True, absence_is_pass=False)` | `NSE_EXECUTION_VENUE_AUTHORITY`. BSE is optional official corroboration, not a hard Gate 3 authority; cross-exchange authority is not approved. |
| Fail condition | ASM stage `>= 2`; any GSM stage `> 0`; circuit limit `<= 0.05` | Exact V1 thresholds; no new calculation or exception. |
| Freshness | At most four NSE trading sessions; authoritative, aware `effective_at`, and not after gate as-of | Existing calendar and PIT validation remain owner. |
| Incomplete / missing / stale / future / non-authoritative | `INSUFFICIENT_DATA` | Never `PASS`; `absence_is_pass=False` is controlling. |
| Positive clearance | Only an explicit, fresh, authoritative observation with clear values can yield `PASS` | A list omission cannot be converted to zero/clear without a governed complete-snapshot contract. |
| Action scope | The current evaluator receives no `ActionContext` branch in Gate 3 | V1 behavior applies unchanged to every caller context, including risk-management and exit contexts; this audit creates no exemption. |
| Confidence and provenance | Gate decision has no Gate-3 confidence formula or threshold. Carrier `id` and `evidence_ids` bind source lineage through `GateEvidenceContext`. | No confidence or score is fabricated. |

The intended execution boundary remains analytical eligibility only: a `PASS` is not a signal, capital authorization, order, broker call, or portfolio operation.

## 2. Approved family scope and venue authority

Only the source-contract families below are in scope. `ESM`, trade-to-trade, IBC-receipt markers, and any other labels observed in a raw consolidated response are not new Gate 3 families. A future GSM parser may use source code/description to determine the existing GSM field, but may not promote composite markers to independent blocks without governance approval.

| Family | Current source-contract role | Current evidence | Raw-source handling boundary |
| --- | --- | --- |
| `ASM` | Required | NSE `reportASM` returns `longterm` and `shortterm` lists with `isin`, `symbol`, `asmSurvIndicator`, `asmTime`, `survCode`, and `survDesc` | Stage text must map only through an explicit source-code table; no numeric guessing. |
| `GSM` | Required | NSE `reportGSM` returns `isin`, `symbol`, `gsmStage`, `gsmTime`, `survCode`, and `survDesc` | `gsmStage` is not uniformly a GSM ordinal: live rows include `GSM 0`, Roman values, and composite IBC/ESM labels. Only an explicit extraction of the `GSM n` component may populate the frozen integer field. |
| `PRICE_BAND` | Required | NSE `eqsurvactions` reports incremental price-band actions; dated NSE CM-MII master includes current `PricRg` | Neither source is currently governed as `circuit_limit`. The action feed lacks ISIN and complete-state semantics; MII field semantics/admission need approval. |
| `SECURITY_STATUS` | Required source coverage | Dated NSE CM-MII master contains `SctyStsNrmlMkt` and exact security fields | No Gate 3 carrier/admission policy maps it to a pass/fail/insufficient outcome. Dropping it would violate the existing source contract. |

`NSE_EXECUTION_VENUE_AUTHORITY` applies because the frozen V1 source authority is `NSE`, and the current canonical cash-instrument population is NSE-identified. [SEBI’s surveillance curation](https://www.sebi.gov.in/curation/surviellance.html) links both NSE and BSE surveillance pages; that establishes BSE as an official research/corroboration source, not a current execution-gate authority.

## 3. Bounded official-source probe

At `2026-09-13T07:27:02.239215Z`, one bounded, read-only host-network probe fetched only public NSE report surfaces. Response bytes were not stored, no first-observed record was created, and this audit timestamp is not a source publication, effective, or HSI first-observed time.

| Official path | HTTP / shape | Current rows | Observed raw lineage | Readiness consequence |
| --- | --- | ---: | --- | --- |
| `https://www.nseindia.com/api/reportASM` | `200`, JSON object | 149 long-term + 90 short-term | response SHA-256 `8a26bf2815b5dbd1ae7061458d4fdc44cc8cd790f4adb727884682592e1f011f`; `asmTime` date-like | Structured positive membership is feasible; no stored complete-negative receipt. |
| `https://www.nseindia.com/api/reportGSM` | `200`, JSON array | 75 | response SHA-256 `7f56f4162fc3a934c67ca20a14d3f8e784573a43ff1a4725c82657c6f43f688c`; `gsmTime` source text | Structured positive membership is feasible; field-to-frozen-stage mapping must be explicit. |
| `https://www.nseindia.com/api/eqsurvactions` | `200`, JSON array | 35 | bounded response fingerprint was observed but no response was retained; fields include `effectiveDate`, `fromPriceBand`, `toPriceBand`, `symbol` | Incremental action evidence only; cannot certify a current price band or a negative state. |
| `https://nsearchives.nseindia.com/content/cm/NSE_CM_security_11092026.csv.gz` | `200`, dated gzip CSV | 37,676 | response SHA-256 `f5f57d64af5db378531c65b181cac7c0417effcd0b6c9c6fb299e493d909b0ab`; exact `ISIN`, `TckrSymb`, `SctySrs`, `FinInstrmId`, `SctyStsNrmlMkt`, `PricRg` | Exact current source fields exist, but the date-named artifact has no verified source publication instant and no approved Gate 3 mapping. |

NSE publishes the applicable [ASM information](https://www.nseindia.com/static/regulations/additional-surveillance-measure) and [GSM information](https://www.nseindia.com/static/regulations/graded-surveillance-measure). These pages support the regulatory context and lists, but do not themselves define a retained, versioned, machine-admission contract for a complete negative clearance.

The probe recorded no usable `Last-Modified` header or source revision identifier for the JSON responses. Transport success is `SOURCE_PARTIAL`, never a liveness, freshness, or absence certificate. Speculative non-allowlisted endpoints returning HTTP 404/403 were not treated as an official-source failure.

## 4. Positive, negative, effective, and lifecycle semantics

| Question | Required future evidence | Current state | Prohibited inference |
| --- | --- | --- | --- |
| Positive ASM/GSM membership | Retained official response, raw response/row fingerprints, exact identity, explicit source-field mapping, source family, and automatic aware-UTC HSI first observation | `PARTIAL` — live structured rows prove feasibility, no collector/receipt exists | List display alone is not an admitted gate observation. |
| Positive price-band/status change | Exact-source security identity and an approved mapping from source field/action to frozen carrier field | `PARTIAL` | `toPriceBand`, `PricRg`, or status text must not be silently relabelled `circuit_limit`, authoritative status, or clearance. |
| Negative / clear state | A retained complete-scope snapshot, query/window/completeness proof, source revision/lifecycle rules, exact in-scope identity reconciliation, and a governed zero/clear mapping | `NOT_READY` for Gate 3 clearance | Absence from ASM/GSM/action response, a failed request, empty response, or stale previous positive is never clear. |
| Effective state | Source-native date/time and timezone semantics retained separately from HSI time | `PARTIAL` — `asmTime`, `gsmTime`, `effectiveDate`, and MII report date have differing unproved semantics | No source date is assumed publication time, complete-session time, or effective timestamp. |
| First observed | Capture automatically at the future bounded I/O boundary immediately after response bytes; bind response fingerprint and sequence | `NOT_ACTIVE` | The audit/projection/processing clock cannot backdate or replace `HSI_FIRST_OBSERVED_AT`. |
| Lifecycle/removal | Immutable snapshots and exact revision/removal links across declared complete source scope | `NOT_READY` | A previously present row disappearing from an unproved or incremental response is not removal, clear status, or a zero stage. |

Future records must distinguish `SOURCE_PUBLICATION_TIME`, source-native `SOURCE_EFFECTIVE_FROM` / `SOURCE_EFFECTIVE_TO`, `HSI_FIRST_OBSERVED_AT`, and `HSI_PROCESSED_AT`. All are aware UTC only when the source semantics and timezone are actually proved; otherwise retain source text plus an explicit semantic/timezone state. Runtime wall-clock time may supply only prospective automatic first observation, never historic knowledge or effective time.

## 5. Identity, current-universe reconciliation, and history

The live ASM/GSM union contained 314 unique ISINs. In a read-only reconciliation against current local canonical NSE identity-bearing data, 244 exact ISINs were already present in the HSI local identity scope and 70 were outside that local scope; none required a name match. This proves neither eligibility nor a tradable-series admission.

All live surveillance rows lacked a usable series value. Each exact `(ISIN, symbol)` matched multiple dated MII candidates, so the current cash-equity series mapping was `0` resolved / `314` ambiguous in this bounded reconciliation. A future producer must reuse the existing exact `HistoricalSecurityIdentity` / selector and MII snapshot conventions to resolve a specifically approved cash-equity series. It must reject ambiguity, never choose a name, most-recent, or arbitrary series.

| Area | State | Boundary |
| --- | --- | --- |
| Exact security-level ISIN identity | `PARTIAL` | Exact ISIN/symbol joins are technically available; current source data alone does not identify series. |
| NSE cash-equity series scope | `NOT_READY` | Policy must declare the eligible series and existing selector inputs must resolve exactly. |
| Current source status / range fields | `PARTIAL` | MII can supply source-native fields only after exact series selection and a governed field mapping. |
| Historical replay | `PARTIAL` source documents; `NOT_READY` canonical complete Gate-3 state | Existing replay can consume frozen synthetic `MarketObservation` surveillance fields, but is not a source-backed official historical producer. Dated MII archives and static/circular pages do not alone establish complete, known-at ASM/GSM/price-band history. |

Historic replay is therefore a separate future workstream. Its absence does not block prospective evidence collection, but it does block historical clearance reconstruction.

## 6. Source-capability matrix

| Official source | Family | Positive observation | Complete negative | Exact identity / series | Effective / lifecycle | Historical PIT | Pilot liveness | Gate-3 admission now |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| NSE `reportASM` | ASM | `PARTIAL` | `NOT_READY` | `PARTIAL` / `NOT_READY` | `PARTIAL` / `NOT_READY` | `NOT_READY` | `PARTIAL` | `NOT_READY` |
| NSE `reportGSM` | GSM | `PARTIAL` | `PARTIAL` source-list capability, but `NOT_READY` for Gate 3 clearance | `PARTIAL` / `NOT_READY` | `PARTIAL` / `NOT_READY` | `NOT_READY` | `PARTIAL` | `NOT_READY` |
| NSE `eqsurvactions` | PRICE_BAND | `PARTIAL` | `NOT_READY` | `PARTIAL` / `NOT_READY` | `PARTIAL` / `NOT_READY` | `NOT_READY` | `PARTIAL` | `NOT_READY` |
| NSE dated CM-MII | PRICE_BAND, SECURITY_STATUS, identity | `PARTIAL` source fields | `NOT_READY` for surveillance clearance | `PARTIAL` / `NOT_READY` | `PARTIAL` / `PARTIAL` | `PARTIAL` artifacts; `NOT_READY` complete state | `PARTIAL` | `NOT_READY` |
| BSE official surveillance pages | Optional corroboration only | `PARTIAL` unprobed in this audit | `NOT_REQUIRED` for NSE hard authority | `NOT_REQUIRED` | `NOT_REQUIRED` | `NOT_REQUIRED` | `NOT_REQUIRED` | `NOT_REQUIRED` |
| SEBI curation / regulatory materials | Regulatory context | `NOT_REQUIRED` per-security observation | `NOT_REQUIRED` | `NOT_REQUIRED` | `NOT_REQUIRED` | `PARTIAL` framework context | `NOT_REQUIRED` | `NOT_REQUIRED` |

`PARTIAL` never means an admitted pass. It identifies bounded reusable evidence for the next governance repair only.

## 7. Reuse boundary and future data shape

The only permitted future shape is:

```text
official NSE response
  -> existing immutable raw snapshot / source receipt conventions
  -> automatic first-observed + bounded collection receipt
  -> existing exact NSE identity / series selector
  -> typed surveillance observation with source-native fields and lifecycle
  -> existing Gate 3 evidence adapter and version-compatibility binding
```

It must reuse `CoreApiSnapshotRepository` conventions, `HistoricalSecurityIdentity` / selector, NSE MII rows, known-at/PIT patterns, existing source-authority envelope, NSE calendar, and `GateEvidenceContext`. It must not create a surveillance Brain, score, second gate engine, generic identity helper, standalone raw store, or duplicate source authority.

The future pilot remains a short, bounded, source-aware read-only canary: one current NSE response per declared family, exact identity reconciliation, raw snapshot and receipt fingerprints, explicit source/HSI time separation, idempotent replay, revisions/conflicts retained, and no gate invocation. It must not scan market bars, select portfolio holdings, purchase data, run broadly, or infer a clear state.

## 8. Required governance repair before implementation

The exact next continuation is **`GATE3_SURVEILLANCE_POLICY_SOURCE_REPAIR_V1`**. It must make, but not silently implement, these decisions:

1. define the official source-to-carrier map for ASM, GSM, price band, and security status, including the exact GSM `survCode`/description extraction table;
2. decide how an NSE MII `PricRg` field, if at all, maps to the frozen `circuit_limit` decimal, and how `SECURITY_STATUS` is admitted despite no carrier field;
3. declare the exact cash-equity series scope and use the existing selector to fail on ambiguity;
4. define complete snapshot/query coverage, source revision, removal, and negative-clearance semantics compatible with `absence_is_pass=False`;
5. define source-native timestamp/timezone and latest eligible completed-session semantics without projecting HSI time backwards; and
6. decide whether V1’s all-`ActionContext` behavior stays unchanged or requires a separately approved policy amendment.

Only after that repair may one bounded prospective collector/admission slice be considered. No numerical Gate 3 threshold, six-gate composition, or runtime behavior is authorized to change in this audit.

## 9. Validation and protected state

Planned/required validation targets for a later implementation are: existing Gate 3 production tests; source-authority tests; exact identity and series mapping; source-parser feasibility; source-effective/lifecycle tests; positive-versus-absence tests; a bounded official live probe; current-universe reconciliation; Markdown links; and `git diff --check`. This documentation-only audit runs no new runtime producer and does not require the full backend suite.

The audit preserves:

```text
V1_ACTIVE = TRUE
GATE_POLICY_V2_ACTIVE = FALSE
SIX_GATES_EXACTLY_SIX = TRUE
NO_FABRICATED_SURVEILLANCE_CLEARANCE = TRUE
NO_UNVERIFIED_CALENDAR_CLEARANCE = TRUE
NO_FUTURE_LEAKAGE = TRUE
PILOT_SIMPLICITY_RULE = ACTIVE
AI_DECISION_AUTHORITY = FALSE
```
