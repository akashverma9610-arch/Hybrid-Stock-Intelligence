# Gate-3 Prospective Official Surveillance Collector V1

Status: **IMPLEMENTED / SOURCE_EVIDENCE_ONLY / NON_EXECUTABLE / NOT_GATE_ACTIVE**.
Historical result **C: `GATE3_SOURCE_CAPTURE_COMPLETENESS_BLOCKED`**.
Baseline: `1f1a4bbd358afee822c145b774841f0cb3620c5b`, main.

The later [source-capture-completeness repair](GATE3_SURVEILLANCE_SOURCE_CAPTURE_COMPLETENESS_REPAIR_V1.md)
is the current authoritative follow-up. It retains this document's original
measurements as immutable history, separates direct price-band file capture from
row admissibility, and concludes Decision D without changing Gate policy or
activation.

The [composite governance approval](EXECUTION_GATE_POLICY_V2_COMPOSITE_GOVERNANCE_APPROVAL.md)
remains authoritative for the future `execution-gate-policy-v2-proposed / v2-proposal.3`.
This collector neither changes that approval nor closes its runtime activation
register. Parent `six-gates-production-v1 / v1` stays active. Exactly six gates,
all thresholds and the reducer remain unchanged.

## Implementation and reused ownership

| Component | Reuse / bounded addition |
| --- | --- |
| Raw acquisition | [Fixed-route capture](../../app/market_data/surveillance_prospective.py): three sequential public HTTPS GETs; no redirect, cookie jar, auth, retry or scheduler |
| Time | Existing `CollectorClock / SystemUtcClock` from the [prospective earnings collector](../../app/filings/earnings_schedule_prospective_receipt_collector.py); no new clock framework |
| Persistence | Existing [CoreApiSnapshotRepository](../../app/storage/core_api_snapshot_repository.py) and SQLite serializer; one additive `NSE_SURVEILLANCE_PROSPECTIVE` family, no table/migration/database |
| Source parsing | [Surveillance observations](../../app/market_data/surveillance_observations.py), immutable raw fields and deterministic source/evidence receipts |
| Canonical security | Existing [exact identity bridge](../../app/filings/earnings_schedule_identity.py), used only for its read-only NSE security resolver; no earnings purpose/calendar semantics imported |
| Symbol/series/token | Existing [NSE MII master rows](../../app/historical/nse_mii_security_master.py), parent and row fingerprints verified; no new master or identity promotion |
| Coverage | Existing complete/partial/failed/unproven/conflicted receipt convention; surveillance-specific closure proof, not an earnings coverage receipt or new generic coverage framework |
| Source/gate authority | Existing [source authority](../../app/gates/source_authority.py), [envelope](../../app/gates/version_compatibility.py) and [calendar](../../app/historical/canonical_market_session_event_time.py) remain future adapter owners; none invoked or replaced |
| Operator | [One-shot command](../../scripts/collect_gate3_surveillance.py), existing database required; network-free stored-poll replay supported |

No second Surveillance Brain, score, gate engine, identity resolver, snapshot
store or timestamp framework. The small snapshot wrapper performs insert/get
and verifies stored type/identity/content fingerprints. It never updates or
deletes source observations. Only the family enum is added to shared storage;
existing storage behavior, schema and consumers are unchanged.

## Exact source and representation boundaries

Sources were reviewed against NSE's [ASM page](https://www.nseindia.com/static/regulations/additional-surveillance-measure),
[ASM report page](https://www.nseindia.com/reports/asm),
[GSM page](https://www.nseindia.com/static/regulations/graded-surveillance-measure)
and [price-band page](https://www.nseindia.com/static/regulations/daily-price-bands-reports).
The earlier [source repair](GATE3_SURVEILLANCE_POLICY_SOURCE_REPAIR_V1.md) retains
the FAQ/circular research. No new surveillance category or threshold is approved.

| Family | Fixed current source | Interpretation |
| --- | --- | --- |
| ASM | `https://www.nseindia.com/api/reportASM` | Require both `longterm.data` and `shortterm.data`, preserve their scopes. Explicit `asmSurvIndicator` stage I–IV must agree with the single-framework `survCode`. No fabricated row series. |
| GSM | `https://www.nseindia.com/api/reportGSM` | Retain every array row. Decode only corroborated single-GSM labels 0/I/II/III/IV. Composite indicators and unsupported representations remain unavailable, with raw description/code intact. |
| PRICE_BAND | `https://nsearchives.nseindia.com/content/equities/sec_list.csv` | Exact five-column CSV: Symbol, Series, Security Name, Band, Remarks. Positive numeric percentages convert by exact Decimal division by 100; blank is UNKNOWN; dynamic/special/unsupported values are unavailable. |

**`gsmStage` is not universally a stage number.** The captured payload contains
`LXII` for an IBC/GSM composite, among other composite indicators. The collector
does not convert Roman surveillance indicators into a numeric GSM stage, extract
parenthetical codes as stages, or infer a zero from text/absence. Even a single
legacy VI representation remains unsupported under this bounded decoder; this is
an explicit interpretation gap, not an inferred new stage policy.

ASM/GSM official products are documented complete, but equivalence of these JSON
reports to the entire applicable downloadable products has **not** been proven.
Their capture remains UNPROVEN even with all returned sections parsed. Empty
arrays cannot prove removal, absence or a non-blocking component.

The price-band source is the documented complete, unfiltered CSV. Transfer EOF,
exact schema, all-row consumption and no pagination establish mechanical full
export capture. Declared length is checked when supplied. Row/identity conflicts
are still preserved and the receipt becomes CONFLICTED; full capture does not
prove valid identity or current effective applicability. Unsupported band values
remain raw evidence, not parser-fabricated static bands.

No band derives from prices, volatility, file absence or another exchange.
SECURITY_STATUS is descriptive only and is not a mandatory field, gate predicate
or reason to suppress otherwise valid component evidence. NSE remains the hard
execution-venue source; there is no BSE fallback or corroborative promotion.

## Time, raw lineage and durability

Production `collect_once()` accepts **no observation-time argument**. The
injectable test clock is the existing system UTC boundary; the CLI offers no
historical clock override. Request start and completed body observation remain
separate. Raw bytes are checkpointed immediately after receipt and before parsing.

Raw identity binds source family, exact public path, adapter version and payload
SHA-256. Identical bytes reuse the original immutable first observation across
restarts. A changed payload has a new identity. Each request has its own poll
receipt, including a failed/partial retrieval, with status, transfer completeness,
size and safe failure code. Processing has its own timestamp and parser version.

Publication/effective-from/effective-to remain explicitly **unresolved** in V1:
`asmTime` and `gsmTime` are retained as exact raw strings but are not documented
local known-at or effective-interval proofs. Date-only fields receive no invented
intraday clock. Refetch does not renew the raw observation or establish validity.
The latest retained master report date is descriptive—not a current session.

Future admission must verify **both** source effectiveness and knowledge. It
must also respect poll-completion and processing availability, not use an older
raw first-observation stamp to admit a later completeness/identity assertion.
There is no active latest-effective selector or GateEvidenceContext construction
here. Calendar/session binding and admitted component envelopes are later work.

Evidence identity binds poll, parser and the PIT-visible canonical input snapshot
set. Future identities are excluded before hashing or resolving. Stored receipt
replay preserves original processing/fingerprints. Fingerprints are integrity
checks, not signatures or defense against a privileged rewrite of all evidence.
Signed-ingestion/host-clock attestation remains later pilot-security hardening.

For changed complete products, previous complete receipt references are retained
as `COMPLETE_REPLACEMENT_CANDIDATE_EFFECTIVITY_UNRESOLVED`, **not** an admitted
effective supersession. Unknown intervals do not become forever-valid intervals.
Partial/failed captures never establish removals or supersede complete truth.
Duplicate rows are retained and prevent completeness certification; conflicting
values/identities stay conflicted. No vote or largest-timestamp winner is chosen.

## One bounded canary — 2026-09-13

Exactly one live poll per family; no retry, historical bars, backfill or master
download. Subsequent work replayed the three stored responses with zero network
requests. [Machine audit](GATE3_SURVEILLANCE_PROSPECTIVE_COLLECTOR_V1.json).

| Measurement | ASM | GSM | PRICE_BAND |
| --- | --- | --- | --- |
| HTTP / raw bytes | 200 / 63,673 | 200 / 18,756 | 200 / 172,850 |
| Rows parsed / rejected | 239 / 0 | 75 / 0 | 3,538 / 0 |
| Mechanical capture | All returned API sections, full-export equivalence unproven | Full returned array, full-export equivalence unproven | Complete exact CSV parsed to EOF |
| Collector evidence state | UNPROVEN | UNPROVEN | CONFLICTED |
| Resolved row mappings | 186 | 58 | 2,549 |
| Outside retained HSI scope | 53 | 17 | 986 |
| Unresolved row mappings | 0 | 0 | 0 |
| Conflicted row mappings | 0 | 0 | 3 |
| Explicit stage/static-band values | 239 | 39 | 2,998 |
| Unsupported value representations | 0 | 36 | 540 |
| Effective metadata | UNRESOLVED | UNRESOLVED | UNRESOLVED |

Mapping and value counts are independent dimensions and are **source-row counts**,
not unique security counts or claims of current execution coverage. The bounded
read used 10,212 retained NSE universe snapshots and 37,155 master rows from
**2026-08-31**. ASM/GSM resolve at security grain through the existing canonical
bridge. Band joins additionally require exact symbol+series/ISIN against that
dated official master and preserve its token/parent lineage. They do not prove
today's tradable series, an effective interval or historical PIT continuity.
No old ASM/GSM list series was invented or reused as execution identity.

The three price-band identity conflicts are `CORDELIA/EQ`, `ELECTCAST/W1`
and `TDPOWERSYS/EQ`: canonical security resolution alone does not establish
agreement with the exact retained execution-master ISIN. No mapping was repaired
or chosen by the collector.

Automatic raw observations (UTC): ASM `2026-09-13T14:17:32.300020+00:00`,
GSM `2026-09-13T14:17:32.640777+00:00`, PRICE_BAND
`2026-09-13T14:17:33.253458+00:00`. Disk reopen preserved raw first observations
and all three evidence fingerprints. A second production check submitted the
same stored bytes to raw retention without a network request: all three original
timestamps were retained and the nine stored rows remained unchanged. Isolated
repeated-payload collection also proves original stamps survive new polls/processes;
changed bytes remain new. Read-only foreign-key verification returned zero violations.

The production write footprint is three raw snapshots, three poll receipts and
three source-evidence receipts in the existing snapshot table. No schema or
other snapshot-family change was observed during acquisition. No credentials,
cookies or sensitive headers are persisted; sensitive-labelled bodies are
discarded with a safe rejection receipt, not redacted into false raw evidence.

## Readiness and remaining blockers

| Area | Readiness | Exact limit |
| --- | --- | --- |
| ASM collector | PARTIAL | Live rows captured; complete-product equivalence not certified |
| GSM collector | PARTIAL | Capture equivalence and composite/legacy indicator interpretation unresolved |
| PRICE_BAND collector | PARTIAL | Full CSV captured; three identity conflicts, unsupported bands, stale dated master |
| Automatic first observation | READY | Persistent payload-bound automatic UTC capture; no CLI override |
| Capture completeness | PARTIAL | CSV proof present; ASM/GSM full-product proof absent |
| Identity scope | PARTIAL | Exact security/dated symbol-series joins; current execution continuity not proven |
| Effective-state metadata | PARTIAL | Raw time labels retained; authoritative effective interval unavailable |
| Idempotency/restart | READY | Original raw timestamps and typed receipts survive reopen/replay |
| Conflict evidence | READY | Duplicate/conflicting rows and identity conflicts retained without voting |
| Coverage receipts | READY | Every bounded poll preserved, including failures/partials |
| Gate-evidence compatibility | PARTIAL | Source/identity/hash/time/value fields present; no admitted envelope or activation |
| Historical replay | NOT_READY | Prospective first observations cannot be backdated |
| Production Gate-3 V2 activation | NOT_READY | Explicitly out of scope; active V1 unchanged |

The approval register is not rewritten or optimistically closed. Complete-source
capture proof, actual effective dates/current master identity, unsupported GSM
interpretation and later adapter admission remain separate limits. Collector
success, HTTP 200, row absence or product documentation never yields gate success.

## Operator and validation

```powershell
python scripts/collect_gate3_surveillance.py --database data/nse_stock_manager.db
```

This explicitly performs one three-source poll. To replay existing receipts,
use `--replay-poll <ASM-poll-id> <GSM-poll-id> <PRICE_BAND-poll-id>` instead; no
network call or second canary is performed. No daemon, scheduler or runtime hook.
Bounds: 5 MiB per source, 15-second socket timeout with elapsed-time checks,
20,000 universe snapshots, 100 master headers and 50,000 master rows. Parsing
reads existing identity inputs once; reopen proof does not rescan the universe.

[Focused tests](../../tests/unit/test_surveillance_prospective.py) cover strict
representations, partial/failed/duplicate/conflicted captures, no false absence,
exact identity, first observation/reopen, raw tampering, PIT exclusion, fixed
URLs/TLS/redaction/cleanup and CLI network-free replay. Affected storage, identity,
master, gate-governance and API snapshot integration tests passed: **316 passed,
0 failed, 0 skipped, 2 dependency deprecation warnings**, including **73 focused
collector tests**. Reopen integrity checks remain enforced under optimized Python,
and descriptive master status cannot become a surveillance predicate. No full
backend suite was run: shared production behavior has not materially changed.

V1_ACTIVE = TRUE; GATE_POLICY_V2_ACTIVE = FALSE; SIX_GATES_EXACTLY_SIX = TRUE.
NO_FABRICATED_SURVEILLANCE_CLEARANCE = TRUE; NO_UNVERIFIED_CALENDAR_CLEARANCE = TRUE.
NO_FUTURE_LEAKAGE = TRUE; NO_RETROACTIVE_SURVEILLANCE_STATE = TRUE;
NO_RETROACTIVE_BLACKOUT = TRUE; PILOT_SIMPLICITY_RULE = ACTIVE;
AI_DECISION_AUTHORITY = FALSE.

The historic next continuation was
**`GATE3_SURVEILLANCE_SOURCE_CAPTURE_COMPLETENESS_REPAIR_V1`**. It is now
completed as a separate Decision-D repair artifact; unit-test success still does
not upgrade either historic collector measurement to Gate readiness.
