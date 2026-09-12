# Earnings Calendar Known-at Semantics V1

**Status:** `PROSPECTIVE_FIRST_OBSERVED_READY_HISTORICAL_SOURCE_PIT_PARTIAL / GATE6_NOT_READY / NON_EXECUTABLE`.

This bounded policy answers two different questions without treating them as
interchangeable:

1. When did an official exchange source make an exact schedule record public?
2. When did HSI first have the exact official record available locally?

It does not add a source-discovery loop, create schedule records, activate
Gate 6, establish an absence clearance, or change blackout arithmetic. Frozen
state remains `V1_ACTIVE=TRUE / V2_ACTIVE=FALSE / V2_SHADOW_ONLY=TRUE / B08=CLOSED_FOR_ACTIVATION_COMPATIBILITY`.

## Primary-source finding and timestamp inventory

SEBI requires listed entities to disclose material information promptly and
requires exchanges to disseminate it quickly; that legal timing obligation does
not document the timezone or exact public-visibility meaning of any particular
NSE/BSE screen field. The current NSE announcement detail labels separate
**Exchange Received Time** and **Exchange Dissemination Time**; it is evidence
that the two fields are distinct, not a timezone rule. The primary findings are
therefore deliberately narrower than an “obviously IST” assumption.

| Family / exact observed surface | Field / representative raw value | Semantic classification | Generator / public meaning | Timezone and historical availability | Revision handling |
| --- | --- | --- | --- | --- | --- |
| [NSE corporate-announcement detail](https://www.nseindia.com/corporate/corporate-announcements/FIRSTCRY/Brainbees%20Solutions%20Limited?ann_dt=29082026232618&segtype=AGM&seqid=106761714) | `Exchange Received Time`; the observed page labels `29-Aug-2026 23:26:18` | `EXCHANGE_RECEIPT_TIME` | Exchange intake timestamp; not automatically public availability. | Field-local timezone authority was not recovered; `TIMEZONE_UNPROVEN`. No historical continuity is asserted. | A later row is a distinct source record; it does not rewrite the earlier receipt. |
| Same NSE surface | `Exchange Dissemination Time`; observed field label/value `29-Aug-2026 23:26:19` | `PUBLIC_DISSEMINATION_TIME` *field role candidate* | Exchange dissemination label supports public-facing role; source-field semantic proof and timezone proof must both be attached before strict PIT. | `TIMEZONE_UNPROVEN`; the page does not state a field timezone. Legal dissemination requirements do not fill that gap. | Retain each source record and time separately. |
| NSE corporate-filings surface | `Broadcast Date/Time` | `PUBLIC_DISSEMINATION_TIME` *candidate only* | Display label suggests broadcast, but no field-level publication contract was recovered in this slice. | `TIMEZONE_UNPROVEN`; no strict use. | Independent receipt / later amendment only through explicit source lineage. |
| [NSE APARINDS Prior Intimation](https://nsearchives.nseindia.com/corporate/ixbrl/PRIOR_INTIMATION_59958_16072025195757_iXBRL_WEB.html) | `Date of Report* = 2025-07-16`; `Proposed Meeting Date = 2025-07-29` | `ISSUER_DOCUMENT_TIME` / `EVENT_SCHEDULE_TIME` | Issuer document/report date and scheduled event date; neither states public availability. | Date-only; no time or timezone. Never `known_at`. | A reschedule/cancellation has a distinct record and its own temporal evidence. |
| [NSE APARINDS Integrated Filing](https://nsearchives.nseindia.com/corporate/ixbrl/INTEGRATED_FILING_INDAS_163124_28052026205114_iXBRL_WEB.html) | Results-approved `2026-05-28`; prior-intimation date `2026-04-28`; board clock `13:50–14:20` | `ISSUER_DOCUMENT_TIME` / `EVENT_SCHEDULE_TIME` | Later filing describes dates and meeting clock; it is not the original schedule-publication receipt. | No stated timezone for these source fields; it cannot backdate the prior notice. | Later corroboration is not a revision link without exact source lineage. |
| BSE mobile announcement detail already admitted by the bounded parser | `Exchange Received Time`, `Exchange Disseminated Time` when exposed | `EXCHANGE_RECEIPT_TIME` / `PUBLIC_DISSEMINATION_TIME` *field role candidate* | Parser retains the labelled raw values as separate fields. | `TIMEZONE_UNPROVEN`; the existing public detail fetch can be access-limited and no BSE field-timezone contract was recovered. | Each exact `newsid` is retained independently; no same-company/date inference. |
| BSE official results page/archive | `Filing Date Time` / `Revised Date Time`; examples retained in the existing timestamp provenance audit include `01-08-2026 10:00:00` and `5/28/2026 6:31:40 PM` | `UNKNOWN_SEMANTIC` pending exact source contract | Existing filing timestamp, not an admitted earnings-schedule public time. | `TIMEZONE_UNPROVEN`; raw legacy values were not retained in canonical production filings. | `Revised Date Time` is not a source-parent link on its own. |
| HSI source batch / future ingestion boundary | `retrieved_at` / `first_observed_at` | `SYSTEM_FIRST_OBSERVED_TIME` | HSI-local availability only; never relabelled exchange publication. | Must be automatically captured as aware UTC at an immutable boundary. Current `SourceBatch.retrieved_at` is caller-supplied, so it is **not yet** an admitted first-observed receipt. | One immutable first-observed receipt per exact source payload; revised payloads receive their own receipts. |

The existing [filing timestamp provenance contract](CANONICAL_FILING_TIMESTAMP_TIMEZONE_PROVENANCE_V1.md) continues to retain raw timestamp text, field path, source document/payload identity, source fingerprint and parse/timezone outcome. Unzoned raw values are retained as `TIMEZONE_UNRESOLVED`; this slice neither adds a NSE/BSE timezone rule nor changes that contract.

## Temporal classes and minimal contract

`app/filings/earnings_schedule_known_at.py` is a pure, unwired contract. It
reuses `FilingTimestampProvenanceReceipt`; it does not alter the current
candidate’s `known_at` field or its admission state.

| Class | Exact meaning | Permitted use |
| --- | --- | --- |
| `STRICT_SOURCE_PIT` | An exact source record has a `PUBLIC_DISSEMINATION_TIME`, first-party field-role evidence, authoritative timezone resolution, exact source identity/payload fingerprint, and `source_public_at <= as_of`. | Source-public historical/research PIT only, subject to a separately approved replay/admission policy. |
| `PROSPECTIVE_FIRST_OBSERVED_PIT` | An exact official source record has a trusted immutable HSI first-observed receipt at `T`, and `T <= as_of`. | Conservative HSI-local prospective PIT. It does not assert market-first knowledge. |
| `CURRENT_DESCRIPTIVE_ONLY` | Evidence can be shown descriptively, but no permitted temporal fact is visible at the selected perspective/as-of. | Current descriptive research only; no historical availability claim. |
| `TEMPORAL_AUTHORITY_UNAVAILABLE` | No usable temporal evidence exists for the selected perspective/as-of, or a required fact lies after that as-of. | Fail closed. |

`SourceTimestampEvidence` keeps the source timestamp’s exact existing receipt
and separately records its field semantic, immutable evidence identifiers and
fingerprints, and the time that field-semantic evidence became known. A strict
public result additionally requires that semantic proof not post-date the
claimed public instant; later documentation cannot retroactively promote an
older record in this contract.
`SystemFirstObservedReceipt` binds canonical instrument, filing identity,
payload fingerprint, observed UTC instant, ingestion run identity and sequence
into a deterministic fingerprint. It is fixed `WATCH_ONLY / NON_EXECUTABLE`.

The following are hard invariants:

- A schedule date, Date of Report, board-meeting clock, issuer date, or exchange-received time cannot become `known_at`.
- A `STRICT_SOURCE_PIT` result requires *both* `PUBLIC_DISSEMINATION_TIME` field-role proof and exact timezone resolution; an offset/timezone parse alone is not public-time authority.
- A first-observed receipt must be aware UTC, immutable, tied to exact source payload lineage, and marked as created by an automatic ingestion boundary. The current caller-supplied source-batch time does not satisfy this operational admission condition.
- The contract has no runtime clock. `as_of` and every candidate time are explicit inputs and normalize to UTC.
- Evidence after `as_of` is omitted from the resolution output. No later source record, revision, cancellation, or local observation leaks backward.
- No synthetic expiry, freshness, completeness, clearance, source preference, order, broker, portfolio, provider, AI, API, UI, or database behavior exists here.

### Public market time versus HSI availability

The resolver requires a perspective:

```text
PUBLIC_MARKET -> source_public_at only, when strict source requirements hold
HSI_LOCAL     -> system_first_observed_at only, when trusted prospective requirements hold
```

Both facts are preserved when they are visible, but this policy intentionally
does **not** introduce a default `max(source_public_at, hsi_available_at)`.
That maximum is appropriate only when an explicitly HSI-local reproducibility
policy is later approved for a particular consumer. It is not a substitute for
the public-market answer, and a public historical replay must never substitute
HSI receipt time for source dissemination time.

## Selection, replay and lifecycle policy

For `PUBLIC_MARKET`, select `STRICT_SOURCE_PIT` only when authoritative public
time is exact and visible by `as_of`; otherwise return descriptive/unavailable
state. For `HSI_LOCAL`, select `PROSPECTIVE_FIRST_OBSERVED_PIT` only at or after
the trusted first-observed instant. A later 2026 observation of a 2025 notice
is unavailable in a 2025 replay. A raw unzoned timestamp cannot be repaired by
attaching `Asia/Kolkata`, midnight, market open, exchange location, or event
date.

Every original, revision, reschedule and cancellation must carry its own source
or first-observed known-at evidence. At `T1 <= as_of < T2`, an original remains
the existing lifecycle policy’s effective evidence; the revision/cancellation
at `T2` cannot leak backward. The known-at contract does not infer a parent
link, decide whether two scheduled dates conflict, or override the existing
append-only schedule/reconciliation policy.

NSE and BSE times remain independent, even for the same schedule. Different
dissemination instants alone are temporal lineage, not an event conflict. A
future reconciler may consider an earliest **proven** public dissemination for
a defined market-wide answer, but that requires a separate reconciliation
policy; it is not activated here.

## Gate 6 and absence boundary

The recommendation is deliberately asymmetric:

- A future separately admitted, exact official schedule with
  `PROSPECTIVE_FIRST_OBSERVED_PIT` can be a conservative *positive* input to a
  future Gate 6 blackout block, after source authority, identity, purpose,
  lifecycle, and time-validity policies are all satisfied.
- It cannot produce an entry clearance, and `NO SCHEDULE FOUND` is not a
  negative fact. Absence continues to require complete window coverage,
  revision coverage, freshness and a separately approved absence policy.

This slice neither wires a producer nor changes Gate 6, blackout length,
trading-calendar arithmetic, thresholds or exemptions.

## Read-only 31-company feasibility audit

Audit cutoff: `2026-09-12T10:00:00+00:00`; historical comparison cutoff:
`2025-07-16T14:27:57+00:00`. The existing identity audit confirms 31/31 exact
current NSE identities and 31/31 exact current BSE identities, with 0 current
conflicts. The tested historical cutoff remains 0/31 effective for each
exchange, correctly refusing current-master backdating.

Production SQLite has no `earnings_schedule_*` table and no admitted schedule
rows. Therefore this audit does **not** manufacture an event observation and
records the following zero-count temporal coverage:

| Measure over the current 31 resolved identities | Count | Meaning |
| --- | ---: | --- |
| Exact current NSE / BSE identity | 31 / 31 | `CURRENT_EARNINGS_IDENTITY = READY`; not a schedule or temporal proof. |
| Admitted schedule source records | 0 | No source acquisition is run in this slice. |
| Retained schedule dissemination timestamps | 0 | No schedule rows exist to inspect. |
| Field-timezone authority proofs | 0 | NSE/BSE field timezone remains unproven. |
| Trusted automatic HSI first-observed receipts | 0 | Existing batch retrieval time is not admitted as automatic boundary capture. |
| `STRICT_SOURCE_PIT` potential | 0 | No exact schedule record has both field semantic and timezone authority. |
| `PROSPECTIVE_FIRST_OBSERVED_PIT` potential | 0 | No trusted automatic first-observed schedule receipt has been persisted. |
| `CURRENT_DESCRIPTIVE_ONLY` schedule records | 0 | No schedule records were manufactured. |
| `TEMPORAL_AUTHORITY_UNAVAILABLE` for a hypothetical schedule query | 31 | Identity does not establish a temporal schedule fact. |

The identity audit fingerprint is
`sha256:41d67388f45a2232c8d9454e458aea65cd06d348ad008732fd75414322126ad2`.
No schedule table, candidate, filing, portfolio, broker/order record, provider
call, or external query was created by this audit.

The [machine-readable read-only receipt](EARNINGS_CALENDAR_KNOWN_AT_SEMANTICS_V1_RECEIPT.json)
has fingerprint `sha256:a000c6d32f47ac67c0c21300953e7fddb0820d61bcfbaede23391f60735f9934`.

## Validation and scope

Focused tests cover strict zoned-public proof, date/report/receipt separation,
no guessed timezone, automatic/aware first observation, prospective visibility,
historical no-backdating, revision/cancellation timing, dual-exchange lineage,
event-versus-time conflict separation, absence boundary, deterministic replay,
tamper rejection and static no-side-effect boundaries. The existing source,
candidate, timestamp-provenance, identity and Gate tests remain the owners of
their respective behavior.

`EARNINGS_CALENDAR_KNOWN_AT_SEMANTICS_V1` result:

`PROSPECTIVE_FIRST_OBSERVED_READY_HISTORICAL_SOURCE_PIT_PARTIAL`

Exact next continuation, not started: `EARNINGS_CALENDAR_COVERAGE_WINDOW_POLICY_V1`.
Source-field timezone authority remains a separate evidence task; coverage and
freshness remain separate from the positive-event semantics defined here.
