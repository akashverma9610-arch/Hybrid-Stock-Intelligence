# Gate 3 Surveillance Policy / Source Semantics Repair V1

Status: `GOVERNANCE_AUDIT_ONLY / NOT_ACTIVE / NO_COLLECTOR`.

Baseline: `d4f39dcee5cf29c9b663065bab97c70ee85c4277`, `main`.
This follows the [source-readiness audit](GATE3_SURVEILLANCE_SOURCE_READINESS_V1.md)
and retains its [immutable measurement receipt](GATE3_SURVEILLANCE_SOURCE_READINESS_V1.json).
The [repair receipt](GATE3_SURVEILLANCE_POLICY_SOURCE_REPAIR_V1.json) is a new,
separately fingerprinted audit, not an admitted surveillance observation.

## 1. Decision and remaining boundary

**D: `GATE3_POLICY_REMAINS_UNRESOLVED`.** Internal conclusion:
`CURRENT_V1_PASS_PARTIALLY_DEFENSIBLE`.

Official complete-state sources exist. It is therefore **not justified** to
replace Gate 3 with a Gate-6-style event veto merely because list absence is
involved. Nevertheless, source feasibility is not an approved four-component
PASS contract. Three precise gaps prevent choosing A or B now:

1. The approved source descriptor names `SECURITY_STATUS`, but the frozen
   observation and evaluator have **no status field, blocking-status mapping,
   or missing-status check**. Calling that rule already implemented would be
   false. A source admission guard cannot silently change a required status FAIL
   into an unavailable-source result or encode it as a fictitious ASM stage.
2. The descriptor requires the latest eligible completed session, while NSE
   members load the day's effective master before trading. The four-session
   numerical age allowance is not proof that yesterday's state remains effective
   today. The evaluation-session/source-effective binding needs explicit resolution.
3. The precise ASM subframework scope, full-export/API equivalence, effective
   revision proof, supported series and unusual price-band representations are
   not yet an approved source-to-carrier mapping.

These are bounded policy/source-contract gaps, not proof of an NSE-wide outage
or an inherently impossible mandatory gate. The exact next continuation is
**`GATE3_SURVEILLANCE_POLICY_SOURCE_REPAIR_2`**. It must resolve these gaps before
selecting a scope-governance repair or a separately approved semantic successor.
It is **not started** here. No threshold, category, active policy or reducer changes.

## 2. Actual evaluator and reducer liveness

Inspected [engine](../../app/gates/engine.py),
[production policy](../../app/gates/production_policy.py),
[source authority](../../app/gates/source_authority.py), and
[source readiness](../../app/gates/source_readiness.py).

| Input condition after synthetic admission | Gate 3 result | Existing aggregate when other five gates PASS |
| --- | --- | --- |
| Missing `asm_stage` | `INSUFFICIENT_DATA` | `INSUFFICIENT_DATA` |
| Missing `gsm_stage` | `INSUFFICIENT_DATA` | `INSUFFICIENT_DATA` |
| Missing `circuit_limit` | `INSUFFICIENT_DATA` | `INSUFFICIENT_DATA` |
| Observation missing, non-authoritative, future-effective, or older than four eligible sessions | `INSUFFICIENT_DATA` | `INSUFFICIENT_DATA` |
| Complete three fields; ASM >= 2, GSM > 0, or circuit <= 0.05 | `FAIL` | `BLOCKED` |
| Complete three fields; ASM < 2, GSM = 0, circuit > 0.05 | `PASS` | `EXECUTABLE` |
| `SECURITY_STATUS` missing | Not representable; no runtime check | The same three-field synthetic PASS is possible; **not four-family official proof** |
| All four families reportedly non-blocking | Only three can be represented | Official four-family admission is unavailable; no live PASS established |

Missing-field checks precede the threshold checks: ASM 2 plus missing GSM still
returns insufficiency. Gate 3 has no action-context exemption. The reducer has
exactly six decisions: any FAIL dominates insufficiency; otherwise any
insufficiency prevents EXECUTABLE. Neither result calls an order interface.

The real source authority rejects an unadmitted populated surveillance carrier
before formulas with `GATE_DOMAIN_AUTHORITY_UNAVAILABLE:surveillance`;
readiness remains `SOURCE_NOT_IMPLEMENTED`. Synthetic fixture authority proves
arithmetic liveness only. It does not prove an official-source producer exists.
The earlier receipt's `gate3_confidence_formula=NONE` means no evidence-confidence
calculation; more precisely, `_decision` annotates every PASS with constant `1.0`
and every other outcome with `None`. This is not measured source reliability.

## 3. Authoritative source evidence

Public materials inspected on 2026-09-13; no production receipt was persisted.
NSE circulars prevail over explanatory FAQs where inconsistent. BSE remains
corroborative; this audit grants no cross-exchange blocking authority.

| ID | Official source and locator | Source fact / bounded verification |
| --- | --- | --- |
| S1 | [ASM FAQ v1.2, August 2026](https://nsearchives.nseindia.com//web/mediaattachment/2026-08/FAQs_-_Additional_Surveillance_Measure_ASM_20260812103311.pdf), Q6-Q7 p18; indicators pp19-20 | NSE explicitly identifies the complete ASM CSV and directs users to effective applicability circulars. Notices are typically after-hours before their effective day; this is not an exact timestamp guarantee. |
| S2 | [GSM FAQ v1.1, June 2026](https://nsearchives.nseindia.com//web/mediaattachment/2026-06/FAQs_-_Graded_Surveillance_Measure_GSM_Version_1.1_20260612125858.pdf), Q5, Q7-Q10 pp7-9; indicators pp9-10 | Complete stage-wise GSM list; initial shortlisting and later stages differ. In/out and stage reviews are distinct. Effective notices accompany changes. |
| S3 | [NSE price-band page](https://www.nseindia.com/static/regulations/daily-price-bands-reports) and linked [complete CSV](https://nsearchives.nseindia.com/content/equities/sec_list.csv) | Numeric band is percentage on either side of the reference close, not total range width. Derivative-eligible securities have dynamic operating ranges, not a static band. CSV HTTP 200; header `Symbol,Series,Security Name,Band,Remarks`; three sampled rows had numeric `2`, including EQ and BE series. No universe recount. |
| S4 | [NSE CM consolidated circular, 28 April 2026](https://nsearchives.nseindia.com/content/circulars/CMTR73927.zip), `CMTR73927.pdf` pp56,92-93; `PART-D.xlsx`, Annexures 1 and 10 | Daily effective master loading; exact field definitions and symbol-series token grain. Archive and workbook read in memory, with hashes in the repair receipt. |
| S5 | [NSE surveillance consolidated circular](https://nsearchives.nseindia.com/content/circulars/SURV74008.pdf), ASM/GSM frameworks and trade-for-trade discussion around p26 | Classification concerns a security; applicable trading arrangements can change to BE series. Mainboard/SME frameworks must not be indiscriminately combined. |

The public price CSV has no effective-date column in its observed header. HTTP
200 and a current download are not an effective-date certificate. Earlier direct
host requests without suitable public-page headers timed out; a bounded official
archive request succeeded. The price-page host probe failed while the official
CSV succeeded. No retry loop, proxy bypass, secret, browser session or installed
collector was used. Public-document hashes identify bytes, not freshness.
S4 is the inspected published base layout, not a certificate that no later
effective circular amended any field; admission must bind applicable amendments.

## 4. Component contracts: different semantics within one gate

### ASM

S1 identifies `List_of_securities_shortlisted_under_ASM.csv` on the
[ASM page](https://www.nseindia.com/static/regulations/additional-surveillance-measure).
Its documented role is `COMPLETE_SNAPSHOT_STATE` for its applicable framework,
not merely the latest additions. The previously probed `reportASM` response has
long-term and short-term sections; **239 rows alone does not establish that the
API is an exact, unfiltered, complete rendition of the official export**.
Future verification must bind both applicable sections, complete transfer/all
pages, schema, scope and effective revision. A displayed page/filter is insufficient.

Under that verified contract, exact in-scope absence supports a *non-blocking ASM
component*, not Gate PASS and not automatically a canonical stage zero. Explicit
stage I is below frozen threshold 2. Stage II or higher supports blocking when
valid. Indicator codes 11/12 mean short-term stages I/II and 13-16 long-term
I-IV; they are not stage numbers. Do not fold ASM-IBC/ICA or other composite
labels into a newly invented category or silently assert their exclusion.
The approved scalar's exact subframework interpretation remains to be settled.

### GSM

S2 identifies the stage-wise list on the
[GSM page](https://www.nseindia.com/static/regulations/graded-surveillance-measure)
as complete. The old `reportGSM` JSON capture must still be bound to that complete
published product; no parser/page-count certificate was retained in the audit.
Verified applicable absence can support a non-blocking component. **Stage 0
shortlisting is also non-blocking under GSM > 0 but is not absence from GSM.**
Retain those distinct source meanings; never call a shortlisted security clear
of all surveillance. Actual positive stages, not a composite `survCode`/Roman
rendering of that code, supply the scalar. For example indicator 50 combines
LTASM I with GSM 0; 62 combines an IBC disclosure with GSM 0. Neither is GSM
stage 50/62. Only the existing ASM/GSM components may be extracted after an
approved exact decoding map; unrelated markers confer no new gate authority.

### PRICE_BAND

`sec_list.csv` is a documented complete current list with explicit symbol and
series, but its session binding still needs retained authoritative effective
evidence. For a verified **static numeric percent** `Band=5`, the representation
conversion is exactly `Decimal("5") / 100 = Decimal("0.05")`; it is not 10%.
Non-numeric/dynamic/not-applicable/blank bands are UNKNOWN to the current numeric
carrier, never zero, infinity or a fallback 10%. An absent row is UNKNOWN.

S4 maps MII `PricRg` (CHAR[19]) to legacy `CreditRating`, described as daily price
range. That description **does not define a universal percent decoder for every
text value**. `PricRgTp`, `MaxPric`, `MinPric` appear as filler entries in that
published MII layout, not an approved HSI circuit computation. Do not derive a
percentage from market movement, upper/lower prices or a corporate-action price.
For new/relisted/corporate-action/changed-ISIN instruments, require the applicable
official range and exact session identity; otherwise retain UNKNOWN.

### SECURITY_STATUS

S4, Annexure 10 maps `SctyStsNrmlMkt` to normal-market status and
`ElgbltyNrmlMkt` to eligibility. Annexure 1 describes status 1 preopen, 2 open,
3 suspended, 4 extended preopen, 5 stock-open-with-market, 6 price discovery;
eligibility 0 means ineligible and 1 eligible. These are **exchange source codes,
not newly approved Gate-3 categories**. `PrtdToTrad` is a listing/permission
classification (0 listed, 1 permitted, 2 BSE-listed), not a boolean. The circular
also describes alternative-venue restrictions: eligibility alone is not a
universal permission to trade.

Source-native suspension/ineligibility can be evidenced exactly; open/eligible
values describe that row/market/session, not blanket execution permission.
Missing, unrecognised or contradictory fields are UNKNOWN. The exact set the
current gate expects is **undefined beyond the coverage label**. Mapping any of
these values to a status FAIL/PASS would be a new governance decision, not reuse
of an existing production predicate. The current MII row preserves raw status
but not typed price-band/eligibility outputs. A row hash cannot recover discarded
columns. No four-family adapter is implemented or authorized here.

## 5. Identity scope and the 0/314 result

**Series decision C: MIXED, with explicit applicability constraints.** ASM/GSM
lists classify the named security; the master token identifies symbol+series.
This follows S1/S2/S4/S5, not an assumption that an issuer's every instrument or
every exchange/series inherits the same classification.

| Identity | Meaning / reuse | Permitted join |
| --- | --- | --- |
| Issuer/company | May issue several distinct securities | Never a substitute for security identity |
| ISIN/security | Exact security identity in the canonical NSE mapping | ASM/GSM membership only within source framework applicability |
| NSE symbol | Exchange label, session-sensitive | Validate with ISIN; no name/symbol-only continuity shortcut |
| NSE series | Trading arrangement; not a separate issuer | Required for band and normal-market status |
| Tradable instrument | NSE segment + exact token + symbol + series + session identity | Bind master and price row; require equality and reject multiple candidates |

Minimum future join: requested existing canonical instrument -> exact ISIN and
NSE symbol at the evaluation session -> one explicitly requested/approved series
and master token -> source security-level classification whose applicability
covers that instrument -> band/status for that exact token/series/session.
No default EQ, arbitrary first row, fuzzy match, issuer fan-out or BSE authority.
The [session-point identity reader](../../app/historical/nse_session_identity.py)
already rejects ambiguity and other-session substitutions. Its current public
resolver does not accept a series selector: reuse its verified receipt semantics,
but do not pretend it already resolves a multi-series request. Any later narrow
selector adaptation must be separately specified, not create a second master.

The inherited audit measured 239 ASM rows, 75 GSM rows, 35 action notices,
37,676 MII rows; 314 unique surveillance ISINs, 244 exact local matches and 70
outside local scope. All 314 lacked an explicit resolved target series, not a
valid ISIN. All 314 security-level memberships are candidates for the upper-grain
join; none has proved blanket all-series applicability. Every eventual target's
band/status still needs exact series. **0/314 is an unresolved execution-scope
measurement, not 314 failed security identities.** Resolved gate-ready counts
remain zero; per-target eligible-series count is unmeasured. No new universe
query, historical-bar read, database change or scope expansion was performed.

## 6. Negative, positive, temporal and conflict evidence

For ASM/GSM only, a prospective non-blocking fact requires: official list
authority and version; documented applicable complete scope; full file/all
pages and all applicable sections; valid schema; exact security and instrument
applicability; effective state known at the requested session; fresh verified
state; immutable raw/row/coverage lineage; automatic first observation no later
than as-of; no unresolved conflict; approved admission mapping; and no blocking
classification. Missing any premise leaves UNKNOWN / `INSUFFICIENT_DATA`.
`absence_is_pass=False` remains unchanged: this is a conditional component fact,
not permission to substitute missing observations with scalar zeros.

Price/status non-blocking evidence needs an **explicit** admissible exact row,
not list absence. All four components must share a governed compatible state
boundary. No document in this slice grants that final admission.

Positive membership/blocking evidence does not require negative-list
completeness. It does require NSE authority, source/list version, exact canonical
security and applicable series scope, explicit decoded classification, source
publication/effective semantics, HSI first observation, raw/row fingerprint and
admission-policy version. An individually proven blocker cannot supply the other
missing carrier fields: frozen Gate 3 still checks all three first.

| Time | Exact boundary |
| --- | --- |
| `SOURCE_PUBLISHED_AT` | Only an officially supported instant/timezone; absent if unproved |
| `HSI_FIRST_OBSERVED_AT` | Automatic aware-UTC capture at future ingestion; never backdated to the file date |
| `EFFECTIVE_FROM` / `EFFECTIVE_TO` | Preserve source precision, including date-only validity; unknown end stays unknown |
| `PROCESSED_AT` | Audit/processing metadata only; never knowledge or effective time |
| Gate `effective_at` | Current datetime carrier cannot be filled with invented midnight for a date-only source |

Current age arithmetic counts eligible sessions with start excluded and end
included; four is accepted and five rejected. It uses the supplied datetime
dates without NSE timezone conversion. This is an observed implementation fact,
not approval to reinterpret dates or freshness. A current-session complete master
is source-feasible; official date precision does not create historical intraday
known-at. Exact latest-completed versus decision-session governance is unresolved.
No new expiry, polling interval or carry-forward grace is proposed. Source failure
cannot refresh an older observation: current clearance is UNKNOWN when current
effective state cannot be established, while prior historical evidence is retained.

Snapshot transitions are prospective: newer **complete, same-scope, effective,
known-at-admissible** evidence may add/remove/change a stage; unchanged rows keep
both observation receipts without duplicate logical effects. Removal from a
partial/failed/different-scope response is not removal. Never rewrite old first
observation, erase old membership or apply a future revision to a past as-of.

`eqsurvactions` and applicability circulars are `INCREMENTAL_NOTICE` evidence.
A notice establishes its explicit change, not universe-wide non-membership.
Reconstruction needs a complete anchored baseline plus every effective amendment
through the boundary; absent that bounded chain, negative reconstruction is
`NOT_READY`. No unbounded archive acquisition is authorized.

Conflicting list/master/notice values are compared at identical identity,
scope and effective boundary. Different effective dates may explain a transition;
an explicit official supersession may settle it. Otherwise retain
`CONFLICTED / INSUFFICIENT_DATA`, never majority vote, averaging, newest-download
guessing or a favourable-source pick. No cross-family conflict resolver is
implemented by this audit. A stale positive is not current clearance or proof of
removal; unresolved negative risk remains visible as historical evidence.

## 7. Readiness, reuse and pilot minimum

Ratings describe source feasibility separately from actual admission.

| Family | Authority | Source type | Complete snapshot? | Positive | Negative/non-blocking | Identity grain | Series | Effective date | First observation | Current state | Historical replay | Pilot admission |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ASM | READY: NSE | COMPLETE_SNAPSHOT_STATE + notices | PARTIAL: official product documented; exact API completeness unbound | PARTIAL: stage decode/admission needed | PARTIAL: conditional absence only | READY: security within framework | PARTIAL: applicability, not issuer fan-out | PARTIAL: notices vs live-list revision | READY: existing receipt pattern | PARTIAL | NOT_READY | NOT_READY |
| GSM | READY: NSE | COMPLETE_SNAPSHOT_STATE + notices | PARTIAL: official product documented; API equivalence unbound | PARTIAL: distinguish stage 0/composites | PARTIAL: absent or explicit stage 0, different meanings | READY: security within framework | PARTIAL: applicability | PARTIAL | READY: pattern only | PARTIAL | NOT_READY | NOT_READY |
| PRICE_BAND | READY: NSE | COMPLETE_SNAPSHOT_STATE / MASTER_REFERENCE_STATE + notices | PARTIAL: complete CSV/daily master; exact session proof needed | PARTIAL: numeric static percent | PARTIAL: explicit row >5%, not absence | READY: symbol+series/token | READY: mandatory | PARTIAL: CSV date absent, master date available | READY: pattern only | PARTIAL: dynamic/text values unsupported | NOT_READY | NOT_READY |
| SECURITY_STATUS | READY: NSE | MASTER_REFERENCE_STATE | PARTIAL: daily master; operational mapping missing | PARTIAL: raw status/eligibility | NOT_READY: no approved gate predicate | READY: token+series+market | READY: mandatory | PARTIAL: dated master, session states | READY: pattern only | PARTIAL: raw truth, no gate status | NOT_READY | NOT_READY |

The 25-30-user pilot needs no fabricated historical archive. It does need exact
NSE scope, complete effective snapshots for absence-derived facts, explicit
instrument-level price/status evidence, immutable first-observed receipts,
approved temporal/status/component admission and fail-closed source/conflict
handling. No collector can be authorized merely by this readiness table.

Reuse [MII extraction](../../app/historical/nse_mii_security_master.py),
[session-point identity](../../app/historical/nse_session_identity.py), existing
[historical identity](../../app/historical/security_master.py),
[snapshot repository](../../app/storage/core_api_snapshot_repository.py),
[gate envelopes](../../app/gates/version_compatibility.py), source authority,
NSE calendar and the unchanged reducer. Reuse the prospective observation and
coverage-proof principles tested in
[earnings collection](../../tests/unit/test_earnings_schedule_prospective_receipt_collector.py);
do not copy earnings policy, repurpose its event type or create another clock.
Existing date-point identity approval does not approve historical intraday
surveillance knowledge or an inferred listing interval. Existing MII snapshots
do not by themselves retain every original byte/ignored column: a future raw
receipt design must use existing storage conventions without claiming missing
raw evidence already exists. No surveillance database, Brain, master, score or
parallel gate is created.

Execution uncertainty must not lower research scores or label a security bearish,
fundamentally weak or technically weak. Research/deep analysis remains available
on independent evidence. AI has no decision authority.

## 8. Options and validation

| Option | Finding |
| --- | --- |
| A: keep current mandatory gate | Not established: four-family admitted PASS and status semantics absent |
| B: keep gate with source-scope clarification | Plausible, but insufficiently established while status FAIL mapping and temporal contract are unresolved |
| C: versioned Gate 3 V2 required | Not established: complete-state sources contradict the premise that negative proof is necessarily impossible |
| D: policy unresolved | **Selected**; settle exact remaining source/policy seams, not a wholesale re-audit or veto redesign |

The [audit tests](../../tests/unit/test_gate3_surveillance_policy_source_repair.py)
pin the frozen formula, synthetic six-gate liveness, real source rejection,
schema/identity limitations and a **test-only** conditional completeness truth
table. Those fixtures are acceptance examples, not live ASM/GSM parsers or source
certificates. Existing master/session/PIT/conflict tests run alongside them.
No full backend run is required because no runtime file changes. Markdown links,
receipt fingerprint and `git diff --check` must pass before the documentation/test
commit. Test totals are reported with the checkpoint, not invented here.

Completed validation: 58 audit tests passed; 189 relevant tests passed with two
dependency deprecation warnings, no failures or skips. The edited-document check
resolved 281 local Markdown links and found no table/whitespace errors. External
links were source-checked as described above, not represented as an exhaustive
automated availability check. No full backend suite was run for this non-runtime
slice.

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
