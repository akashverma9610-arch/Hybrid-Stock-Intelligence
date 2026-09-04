# BRSR Issuer Anchor Session-Master Backfill V1

**Status: `IMPLEMENTED_BOUNDED_PRIMARY_EVIDENCE_ACQUISITION / PARTIAL_COVERAGE / APPROVED_SEMANTICS / NOT_ACTIVE / NON_EXECUTABLE`.**

## Purpose and exact boundary

This bounded backfill retains an immutable, same-date primary-evidence anchor
only when an existing official NSE BRSR General filing provides exact
`symbol + CIN + submission timestamp` and an exact official NSE CM-MII security
file for that same labelled session provides one or more matching `symbol + ISIN`
rows that all retain one exact ISIN. Every matching source row is retained; the
identity is ambiguous only if those exact-symbol rows contain more than one
ISIN.

```text
official BRSR filing (S, C, T)
  + exact official NSE MII session file D (S, I)
  → ISSUER_ANCHOR_READY (I ↔ C evidence, known no earlier than T)
```

The result is primary anchor readiness for the separately governed
[`ISIN ↔ Issuer Bridge Continuity Policy`](ISIN_ISSUER_BRIDGE_CONTINUITY_POLICY_PROPOSAL_V1.md).
It is not an active bridge, a timeless issuer master, a forward-continuity
observation, company-type classification, financial-comparability conclusion,
screen, rank, signal, setup, score, portfolio change, or execution authority.

`anchor_known_at` is always the exact BRSR submission timestamp. The date-only
MII file cannot make an issuer relationship known at session open, and no
intraday usability conclusion is made.

## Official source and validation

The operation requests only the fixed official archive form:

```text
https://nsearchives.nseindia.com/content/cm/NSE_CM_security_DDMMYYYY.csv.gz
```

For every requested BRSR filing date it requires the exact path/filename date,
HTTPS official host, successful gzip decoding, expected CSV schema, a
deterministic raw-file fingerprint, and exact source-date binding. HTML,
404/unavailable response, wrong date, invalid gzip, schema mismatch, malformed
identity row, absent exact symbol, and ambiguous same-symbol identity fail
closed. There is no nearest-date, current-master, BSE, legal-name, alias, or
fuzzy substitute.

The repository has no durable NSE holiday dataset or intraday session
boundary. A successful date-labelled, validated official MII report is retained
as direct primary evidence for that labelled session; a missing exact report is
not repaired with a weekday assumption or nearby date. The supplied calendar
boundary remains the policy guard for any caller that has an independently
governed session calendar.

## Immutable receipt representation

The implementation adds the narrow
`HISTORICAL_ISSUER_ANCHOR_EVIDENCE` snapshot family. It avoids broad storage of
every row in every acquired MII file. Instead it stores only:

- one deterministic terminal checkpoint per BRSR source date;
- one immutable assessment per BRSR filing, including the validated source
  snapshot lineage and every exact-symbol candidate row's ID, raw-row
  fingerprint, ISIN, and source-provided series/status/type fields;
- `ISSUER_ANCHOR_READY` records for BRSR-relevant exact rows; and
- BRSR evidence ID/fingerprint, exact symbol/CIN/submission time, session date,
  MII source reference/snapshot ID/raw-file and schema fingerprints, exact row
  ID/raw-row fingerprint, ISIN, and source-provided series/status/type fields.

Receipt and anchor identities exclude acquisition/runtime time. The content
fingerprints include all retained lineage needed to reproduce the record.
Replaying equal source evidence is append-only/idempotent; changed content at an
existing identity fails closed as an immutable collision.

## Calendar, PIT, and conflict rules

| Condition | Result | Prohibited shortcut |
| --- | --- | --- |
| Exact BRSR date is not an affirmed session | `ANCHOR_SESSION_UNAVAILABLE` | Previous/next session substitution. |
| Exact official MII file is absent or invalid | terminal session receipt / `ANCHOR_SESSION_SECURITY_EVIDENCE_MISSING` | Current or later security master. |
| One or more source rows for the exact BRSR symbol, all with one exact ISIN | `ISSUER_ANCHOR_READY`, retaining every candidate row, subject to existing-anchor conflict check. | Legal-name or approximate symbol match. |
| Exact symbol rows with more than one ISIN | `EVIDENCE_CONFLICTED`, retaining every candidate row lineage. | Row-order selection or an unapproved series/status filter. |
| Same exact ISIN is already anchored to a different CIN | `EVIDENCE_CONFLICTED` | Last-write or source-priority resolution. |

The date-labelled MII artifact has no verifiable historical publication time.
The anchor therefore states only that issuer evidence is known no earlier than
the BRSR timestamp `T`; it does not assert prior same-day availability. It
never creates an observation for `2024-02-05` from later FY23-24 BRSR evidence.

## Backfill scope and restart safety

The first bounded operation obtains the five named target files, then processes
the existing FY23-24 BRSR date groups one date at a time. A stored terminal
checkpoint prevents repeat downloads for the same BRSR date. One valid MII
source file serves only the BRSR rows from its exact same date. Individual
unavailable/invalid files remain explicit terminal receipts; they do not halt
unrelated dates. Transport failure is not converted to a terminal result.

The date group is the acquisition bound. No parallel workers, broad MII row
fan-out, continuity activation, or company-type/backtest processing is part of
this slice.

## Production checkpoint — FY23-24 partial coverage

The bounded production run retained only the required evidence family and is
intentionally incomplete. The first strict receipt rendition treated every
multi-row exact-symbol group as ambiguous. Review of the retained primary rows
showed that the named targets had multiple source rows but one exact ISIN per
group. Contract `v2` therefore retains all same-ISIN rows and rejects only
multi-ISIN groups; the earlier `v1` assessments remain immutable audit history.
No series, status, or security-type preference was introduced.

| Production fact | Durable result |
| --- | ---: |
| FY23-24 BRSR direct CIN+symbol rows in scope | 1,199 |
| Candidate filing-date groups | 138 |
| `v2` date groups terminally processed | 55 |
| Validated official MII files acquired | 52 |
| Exact-date reports unavailable | 3 |
| BRSR rows assessed by `v2` | 401 |
| `ISSUER_ANCHOR_READY` assessments / retained anchors | 358 |
| `EVIDENCE_CONFLICTED` assessments | 25 |
| Exact-session security evidence missing | 18 |
| Distinct anchored CINs / ISINs | 347 / 349 |
| Remaining candidate date groups | 83 (55 weekdays; next unprocessed weekday `2024-07-19`) |

The five named targets are all anchor-ready: `DEEPINDS` → `INE0FHS01024`,
`APARINDS` → `INE372A01015`, `ICICIBANK` → `INE090A01021`, `GLAND` →
`INE068V01023`, and `GENUSPOWER` → `INE955D01029`. Their exact BRSR timestamps
remain their `anchor_known_at`; no anchor supplies identity to an earlier date.

An immediate durable replay inserted zero anchors and created zero session
receipts (358 anchors and 55 `v2` receipts were already present). SQLite
integrity was `ok` and foreign-key violations were `0`. The broad producer was
stopped at this bounded checkpoint rather than treating partially observable
transport execution as permission for further requests. A later controlled
resume must begin from the retained date receipts and must not replay them.

The non-active 2026-08-31 same-ISIN read-only audit found 332 same-symbol and
9 changed-symbol potentials, with 17 anchored ISINs absent from that session.
These are not forward bridges, continuity results, or issuer classifications.

### FY22-23 and 2023 readiness boundary

The exact official FY22-23 artifact reference is
[`BRSR Data Dump FY 22-23.xlsx`](https://nsearchives.nseindia.com/web/sites/default/files/inline-files/BRSR%20Data%20Dump%20FY%2022-23.xlsx).
A bounded `HEAD` check returned HTTP `200`, the XLSX content type,
`168,247,583` bytes, and byte-range support. It was not downloaded or parsed:
the current exact BRSR adapter has a 64 MiB archive and 16 MiB workbook safety
bound. Consequently, the FY22-23 labelled-field layout, direct target rows,
submission timestamps, five-target pre-2024-02-05 evidence, and required 2023
MII dates are all `NOT_PROVEN`. No 2023 MII probe was made, because no exact
target filing-session date was obtained without parsing that primary artifact.
This is a bounded primary-source readiness result, not a claim of source
absence or a substitute date.

## Explicit non-goals

This slice must not:

- infer same-symbol or same-name continuity;
- propagate a CIN backward or create an interval;
- activate the approved forward-continuity policy;
- access RBI/IRDAI/company taxonomy data or classify company type;
- execute Compounder/backtest grids, ranks, or investment eligibility;
- alter Discovery, Holding, Sell, Harvest, Rotation, Decision Score, or Six
  Gates; or
- access a portfolio, broker, order, API, UI, runtime clock, or execution path.

## Required production evidence receipt

The implementation report records the five named targets, FY23-24 date/file
and anchor counts, direct same-ISIN appearance in the already retained
2026-08-31 session population, exact FY22-23 archive readiness, bounded 2023
date probes, replay/idempotency, SQLite integrity/FK checks, and the test
results. Those facts are a production receipt, not policy activation.

## Next governed step

Only if meaningful exact anchor evidence is retained, the next permitted
continuation is `ISIN_ISSUER_BRIDGE_CONTINUITY_ACTIVATION_V1`. It must consume
only the receipts above plus the approved policy semantics, remain PIT-safe,
and make no company-type or investment conclusion.
