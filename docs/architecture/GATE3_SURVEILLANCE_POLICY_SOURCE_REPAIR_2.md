# Gate 3 Surveillance Source Semantics Repair 2

Status: `GOVERNANCE_AUDIT_ONLY / NOT_ACTIVE / NO_COLLECTOR`.

Baseline: `9aa1ca541d3ec7f3c0b32bfec85ce25d7018ae98`, `main`.
This final bounded audit supersedes the unresolved interpretations in the
[first repair](GATE3_SURVEILLANCE_POLICY_SOURCE_REPAIR_V1.md), not its immutable
[receipt](GATE3_SURVEILLANCE_POLICY_SOURCE_REPAIR_V1.json) or inherited measurements.
The [Repair-2 receipt](GATE3_SURVEILLANCE_POLICY_SOURCE_REPAIR_2.json) binds the
origin findings, frozen code hashes and synthetic proof. No broad source research
or new universe/production-database probe was performed.

## 1. Final decision

**C: `VERSIONED_GATE3_POLICY_V2_REQUIRED`.** The sole reason requiring a successor
is **the explicitly approved completed-session selection requirement conflicts
with safe current-session effective-state selection**. This is not a conclusion
that complete negative surveillance evidence is impossible, that status needs a
new predicate, or that missing collector implementation requires V2.

- **S1: `SECURITY_STATUS_IS_NOT_A_V1_FORMULA_INPUT`.** Original role:
  `DESCRIPTIVE_SOURCE_FAMILY`; no approved independent status predicate or guard.
- **T3: `V1_TIMING_SEMANTICS_REQUIRE_VERSIONED_POLICY_CHANGE`.** Classification:
  `MATERIAL_POLICY_CHANGE` in source-state selection, **not numeric thresholds**.
- ASM and GSM: `SECURITY_LEVEL_APPLIES_TO_EXECUTION_INSTRUMENT`, with exact NSE
  security/applicability proof; neither needs a fabricated surveillance-row series.
- The 0/314 finding is `REQUIRED_ONLY_FOR_PRICE_BAND` for actual V1 inputs,
  not a gate-wide security identity failure.

V1's formula remains viable: it can truthfully PASS at an appropriate completed
session as-of, or when no effective state change intervenes and that continuity
is actually evidenced. A safe **general current-session** producer cannot assume
the prior completed snapshot still describes the current state. V2 is required
for that temporal selection change, not because V1 can never return PASS.

Exact next continuation: **`GATE3_SURVEILLANCE_POLICY_V2_PROPOSAL`**.
It is not started. This document neither designs nor activates that successor.
No collector may silently reinterpret the old approval in the meantime.

## 2. Origin audit: source coverage is not a fourth formula

Repository history introduces `OfficialSourceContract` in
`9c9af08dd7fbd8f868e87131908f8d847bcd269e` (the V1 release source checkpoint).
[Production policy](../../app/gates/production_policy.py) is byte-identical to
that version. The original and current `_surveillance` method ASTs are identical.
Earlier [gate definitions](../EXECUTION_GATES.md) specify ASM/GSM and circuit
disqualification; [engine documentation](../EXECUTION_GATE_ENGINE.md) specifies
fresh authoritative evidence, not a security-status rule.

The user-supplied original **Six Gates Production Policy Approval & Persistence
V1** (attachment identity `ce4f2490-4f24-46f5-bbb0-4043f0a64006`; content hash in
the receipt) was read in full as corroborating approval provenance. Its Gate-3
section approves the three numeric/rule parameters and surveillance age, then
lists official source families including:

> applicable security-status/surveillance lists

Its separate source-contract instruction names official NSE ASM/GSM/price-band/
security-status evidence and keeps ingestion separate from gate decisions. It
contains no required status value, blocking-status set, status PASS test or
independent status-admission predicate. The preceding resolution request asked
to discover existing semantics, not invent restrictions. Neither a source label
nor an exchange's codebook supplies that absent policy authority.

Therefore retain all four source-family labels unchanged, but classify
`SECURITY_STATUS` as descriptive source coverage, not a V1 formula input,
execution prerequisite or non-formula guard. The first repair's inference that
four separately non-blocking components were necessarily mandatory is corrected.
No status predicate is added; missing status alone must not prevent **semantic**
closure of the three-input formula. Whole-surveillance producer unavailability
continues to prevent real admission independently.

| Runtime question | Audited answer / reference |
| --- | --- |
| Separate context field? | No `GateEvaluationContext` type in `app/gates`; actual `GateEvidenceContext` has as-of, policy version, input fingerprint and typed dependencies. No status field. |
| Observation field? | `SurveillanceObservation`, engine lines 95-103: `asm_stage`, `gsm_stage`, `circuit_limit` plus provenance only. |
| Missing/status FAIL/status PASS predicates? | None. `_surveillance`, lines 266-282, checks exactly the three substantive fields. |
| Indirect consumption before formula? | Nominal validation and typed domain lineage bind `surveillance`, not a fourth status value. `DOMAIN_FIELDS` defines no status domain. |
| Source-authority guard? | Default authority rejects the unimplemented whole surveillance producer; `RepositoryGateAuthority.verify_domain` delegates surveillance to that rejection. It does not inspect status. |
| Current production declaration? | Source coverage includes four families; its names are not required `GateInput` field names. |
| History/receipts/migrations? | Original policy/engine, later version/provenance inventories and immutable policy persistence provide no status-specific input or predicate. No status column was added to the gate carrier. |

Definitive substantive V1 input set: **`ASM / GSM / PRICE_BAND`**, represented by
`asm_stage / gsm_stage / circuit_limit`. Source authority, provenance, effective
time, freshness and configured thresholds remain mandatory validation, not extra
surveillance categories. Historical identity lifecycle checks elsewhere are not
a hidden Gate-3 status predicate and must not be presented as one.

## 3. Timing provenance: a real approval, not a generalized price rule

The original human approval says:

> The observation must correspond to the latest eligible official NSE surveillance state for the relevant completed trading session.

It immediately explains that weekends/holidays must not cause calendar-day false
staleness, and that max-age alone is insufficient. This wording is specifically
in **Gate 3**, not just an OHLCV, historical-replay or all-gate rule. The same
approval separately requires surveillance evidence at-or-before gate as-of.
Those are distinct constraints; PIT exclusion does not cancel session selection.

The implementation records
`surveillance_source.latest_eligible_completed_session_required=True` and
`absence_is_pass=False`. It also puts the completed-session flag on the earnings
source descriptor; that second usage is not evidence that the Gate-3 requirement
was accidental. It remains serialized and covered by the immutable policy hash.
`selected_production_gate_engine` passes the selected `gate_config` to the engine;
neither it nor `_surveillance` implements a completed-session selector.

The formula accepts `effective_at <= as_of`, counts eligible sessions, and checks
age <=4. Source admission is currently unavailable. **An unenforced approved
source constraint is not permission to delete or redefine it.** Tests show
changing the flag invalidates the retained fingerprint. The existing repository
rejects overwriting an approval ID even if a caller recomputes a different hash.
No such change is saved to production here.

### Open-session counterexample

Synthetic fixture only: as-of `2026-09-01T09:00:00Z` (14:30 IST). The supplied
fixture calendar marks 31 August as a holiday, making 28 August the prior
completed session. This calendar/date example is not a claim about a live NSE
holiday or source capture. Synthetic current restrictions have an explicit
effective instant earlier on 1 September, not a fabricated timestamp from an
official date-only record. All other five gates PASS under fixture authority.

| Effective change | Prior completed values | Current-effective values | Prior-only selection | Current-effective selection |
| --- | --- | --- | --- | --- |
| ASM restriction | ASM 0, GSM 0, band 10% | ASM 2, GSM 0, band 10% | PASS / EXECUTABLE | FAIL / BLOCKED |
| GSM restriction | ASM 0, GSM 0, band 10% | ASM 0, GSM 1, band 10% | PASS / EXECUTABLE | FAIL / BLOCKED |
| Circuit restriction | ASM 0, GSM 0, band 10% | ASM 0, GSM 0, band 5% | PASS / EXECUTABLE | FAIL / BLOCKED |

Both observations are within the four-session age limit. The issue is which
state applies, not the age threshold. An explicit current removal gives the
reverse divergence; ignoring timing affects both blocking and non-blocking
outcomes. These tests prove a selection hazard, not a live production false PASS:
the real source boundary still rejects unadmitted surveillance before formulas.

Accepted official evidence from the prior audit confirms that surveillance
notices can take effect the following session and members load the day's master
before trading. See the previously inspected [ASM FAQ Q7](https://nsearchives.nseindia.com//web/mediaattachment/2026-08/FAQs_-_Additional_Surveillance_Measure_ASM_20260812103311.pdf),
[GSM FAQ Q10](https://nsearchives.nseindia.com//web/mediaattachment/2026-06/FAQs_-_Graded_Surveillance_Measure_GSM_Version_1.1_20260612125858.pdf)
and [NSE master circular](https://nsearchives.nseindia.com/content/circulars/CMTR73927.zip).
No new broad source investigation was needed.

Safe current-session surveillance must mean latest authoritative state **effective
at evaluation as-of and already known to HSI**, not merely the last completed
state. But that is not the explicit frozen selection wording. Restricting V1 to
completed-session research would not deliver current-session pilot admission;
adding a new current-state veto or a second unpublished selection rule would
also change policy. Calling the change only an adapter fix would conceal the
material semantic change. Hence T3, not T1/T2/T4.

| Time | Preserved meaning |
| --- | --- |
| `OBSERVED_AT` | Immutable prospective HSI first observation; UTC instant; <= evaluation as-of |
| `SOURCE_PUBLISHED_AT` | Source-supported publication precision, optional if not known; never substituted by collection time |
| `EFFECTIVE_FROM/TO` | Official validity boundary, date-only when that is all the source supports; no invented midnight/end instant |
| `EVALUATION_AS_OF` | Explicit consumer cutoff, never runtime-clock inference |

Date-effective rows need a separately specified session-validity binding. This
audit does not fill the existing datetime carrier by inventing an intraday
instant. The future versioned proposal must handle that boundary; no polling,
expiry or stale carry-forward policy is introduced here.

## 4. Security grain versus execution grain

| Family | Proven identity grain | ASM/GSM decision or series need | V1 use |
| --- | --- | --- | --- |
| ASM | `SECURITY_ISIN`, validated NSE symbol and applicable framework | `SECURITY_LEVEL_APPLIES_TO_EXECUTION_INSTRUMENT`; no series field needed on list row | Required scalar |
| GSM | `SECURITY_ISIN`, validated NSE symbol and applicable framework | `SECURITY_LEVEL_APPLIES_TO_EXECUTION_INSTRUMENT`; no series field needed on list row | Required scalar |
| PRICE_BAND | `SYMBOL + SERIES` in explicit band CSV; `TOKEN + SERIES` through master | Exact execution series required; join to same security/ISIN through master | Required scalar |
| SECURITY_STATUS | Master `TOKEN + SERIES + market` | Exact row needed only if retaining descriptive status; no new guard/binding implementation here | Descriptive family, not required for PASS |

An issuer can have multiple ISINs. No company-name match, issuer-wide propagation,
same-symbol shortcut or cross-exchange authority is allowed. A security-level
classification may apply to an execution instrument only when its existing
canonical NSE identity proves it belongs to that exact classified security and
the official framework scope covers it. It does not legalize all series or turn
an unclassified issuer instrument into the same security.

### Existing execution identity, not an invented master

| Existing contract | Available keys | Important limitation |
| --- | --- | --- |
| [Domain Instrument](../../app/domain/models.py) | ID, symbol, exchange, optional ISIN | No series/token; a bare ID is insufficient for a price join |
| [InstrumentIdentity](../../app/market_data/models.py) | ID, exchange, symbol, optional ISIN/series; separate provider mappings | Has the required series slot already; a provider reference is not automatically an NSE token |
| [HistoricalSecurityIdentity](../../app/historical/security_master.py) | Canonical ID, ISIN, exchange, symbol, series, effective lineage, optional exchange security code | Use only genuine PIT evidence; do not promote a date-only current master into a historical interval |
| [NSE session-point identity](../../app/historical/nse_session_identity.py) | Exact session, symbol, ISIN, series, security code and source hashes | Existing resolver rejects ambiguous multi-series results; target-specific binding may reuse receipts, not silently choose a row |
| [Dhan prospective identity](../../app/market_data/dhan_live_bar.py) | Canonical security, ISIN, explicit EQ series and provider security ID | Market-data identity, not execution authorization or an interchangeable NSE master token |

Gate evaluation accepts `instrument_id`, not the full target object. A future
trusted producer must obtain the existing canonical execution identity and bind
it to effective official master evidence. If the actual target has a verified
series, use it; **do not demand that the ASM/GSM list invent it**. If absent,
return per-target UNKNOWN rather than defaulting to EQ. Require one exact
symbol+series+ISIN master match, then one explicit symbol+series price row.
Repeated/conflicting candidates are not resolved by input order. Retain token,
session and source lineage; missing target data is adapter readiness, not proof
that the source identity model is incoherent. No production targets were reread.

Inherited counts remain 239 ASM rows, 75 GSM rows, 35 notices, 37,676 master rows;
314 surveillance ISINs, 244 exact local matches and 70 outside scope. Surveillance
row series is **not required for ASM/GSM**. The earlier 0/314 result cannot be
reused as a current target-price join failure count: that target-specific join
has not been measured. No count is silently changed to 314 resolved.

## 5. Complete products, unfinished adapters, and PASS contract

For the documented official ASM and GSM list products:

```text
SOURCE_PRODUCT_COMPLETE = TRUE
CURRENT_ADAPTER_EXPORT_COMPLETENESS = UNPROVEN
PRODUCTION_ADAPTER_ACTIVE = FALSE
```

The first two statements concern different things. Accepted NSE documentation
establishes a complete product; no future collector may infer that its chosen
JSON response, display page or filtered download equals that product merely
because it succeeds. Full-export/all-section verification remains an adapter
acceptance test, **not an unresolved policy principle**.

For ASM: complete admitted applicable snapshot + exact security + valid effective
and knowledge boundary + no blocking stage -> `ASM_NON_BLOCKING`. Explicit stage
I is below threshold 2. For GSM the analogous condition yields non-blocking
evidence; stage-0 shortlisting remains distinct from absence. Never decode a
composite surveillance indicator as the GSM stage number. Unsupported/conflicting
decoding is UNKNOWN, not another surveillance family.

For PRICE_BAND, require an explicit official row for the actual execution
symbol/series. A valid static numeric percentage >5 is non-blocking; <=5 blocks.
Convert percent to the existing fractional decimal exactly. Row absence,
dynamic/non-numeric/blank values and unproven `PricRg` representations stay UNKNOWN.
No range or band is inferred from price movements. This reuses the accepted
[price-product findings](GATE3_SURVEILLANCE_POLICY_SOURCE_REPAIR_V1.md#price_band).

A truthful V1 formula PASS requires exactly the three substantive values present,
NSE source authority, exact scope-specific identity, admitted source/version and
raw/evidence lineage, PIT-safe first observation, no unresolved conflict, fresh
effective state for the governed boundary, and non-blocking values. It does
**not** require a new status PASS or fourth scalar. Under frozen approval that
state boundary is the relevant completed session. This cannot be relabelled a
general current-session clearance when a later effective state exists.

`GATE_RESULT_CONFIDENCE_ANNOTATION != SOURCE_COMPLETENESS_PROBABILITY`.
The constant PASS `1.0` is unchanged. Conflicting material source values at the
same identity/effective boundary remain `CONFLICTED / INSUFFICIENT_DATA` unless
existing explicit official supersession resolves them; no voting, favourable
source selection or newest-download guess. Source failure is UNKNOWN, never
absence-based clearance. Prior observations are retained without renewed freshness.

## 6. Final matrix and prospective boundary

| Family | V1 required? | Product complete? | Adapter complete? | Grain / series | Blocking possible? | Non-blocking possible? | Effective state | Pilot producer |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ASM | YES | TRUE, applicable complete product | UNPROVEN | Security/ISIN; no row series required | YES, verified stage >=2 | YES, complete applicable proof below 2 | Frozen completed-session rule; current-session timing needs V2 | NOT_READY |
| GSM | YES | TRUE, stage-wise product | UNPROVEN | Security/ISIN; no row series required | YES, actual stage >0 | YES, complete proof; stage 0 and absence distinguished | Same timing requirement | NOT_READY |
| PRICE_BAND | YES | TRUE, documented complete CSV/master product | UNPROVEN | Exact symbol+series/master token | YES, explicit static band <=5% | YES, explicit static band >5% | Exact effective instrument state; not HTTP freshness | NOT_READY |
| SECURITY_STATUS | NO, descriptive coverage retained | Daily master-reference product | UNPROVEN | Token/series/market if observed | NOT_APPLICABLE to V1 formula | NOT_APPLICABLE to V1 formula | Descriptive only; no new timing guard | NOT_REQUIRED for V1 formula |

Prospective pilot operation does not need a perfect historical archive. After
separate timing governance, it can use existing immutable snapshots/coverage
receipts, automatic UTC first observation, scoped canonical identity, effective
ASM/GSM state, exact static band and the existing gate envelope/authority/reducer.
No surveillance database, new clock, symbol master or second gate engine is
needed. No independent status producer is required to satisfy the current
three-field formula. Historical official replay may remain NOT_READY.

These are reuse constraints, not authorization to implement the producer now.
Research and independent scores continue; execution-source uncertainty is not
bearishness, weak fundamentals or a low score. No portfolio/action/order behavior.

## 7. Validation and preserved governance

The [Repair-2 audit tests](../../tests/unit/test_gate3_surveillance_policy_source_repair_2.py)
cover origin/usage, exact formula fields, policy fingerprint immutability, the
open-session selection counterexample, identity/series joins using existing
types, product-versus-adapter completeness, real source rejection and synthetic
six-gate liveness. Test-only join examples are not production adapters. Isolated
test databases never touch production. Prior audit fixtures retain their original
historical conclusions; this new receipt provides the adjudication.

No full backend suite is required because no runtime code changes. Focused and
relevant results, local Markdown links and whitespace checks are recorded with
the final checkpoint. No push; no next slice started.

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
