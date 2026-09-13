# NSE Execution Master Current Capture Continuity Repair V1

**Status: `IMPLEMENTED / SOURCE_EVIDENCE_ONLY / NON_EXECUTABLE / NOT_GATE_ACTIVE`.**

This repair addresses only `EXECUTION_MASTER_CONTINUITY`. It does not reopen the
separate ASM/GSM complete-export blocker, activate Gate 3 or V2, alter a
threshold, or create a gate result, signal, portfolio action, broker call, or
order.

## Proven V1 persistence failure

The official source is the fixed direct NSE MII gzip file:

```text
https://nsearchives.nseindia.com/content/cm/NSE_CM_security_DDMMYYYY.csv.gz
```

The historical `2026-09-11` parent has raw fingerprint
`sha256:f5f57d64af5db378531c65b181cac7c0417effcd0b6c9c6fb299e493d909b0ab`,
37,616 canonical-eligible rows and 60 identity-ineligible rows. Its 21,352
retained children are exactly the first row-write page (ordinals 12--21,395),
created at one checkpoint instant. Repository evidence therefore proves an
**interrupted V1 persistence operation after full parse**, not raw transport
truncation, parser termination, source filtering, duplicate collapse, or schema
rejection. No V1 complete-admission receipt existed.

| Count | V1 11 September state | Meaning |
| --- | ---: | --- |
| `SOURCE_DECLARED_ROWS` | unavailable | The gzip/CSV has no source-native count or manifest. |
| `RAW_CAPTURED_ROWS` / `PARSED_ROWS` | unavailable | V1 did not retain these transfer counters. |
| `RETAINED_ROWS` | 21,352 | Durable page checkpoint only. |
| `CANONICAL_ELIGIBLE_ROWS` | 37,616 | Full extraction count; not admission proof by itself. |

The partial snapshot is never overwritten, deleted, or retrospectively marked
complete. The old reader fallback remains safe.

## Additive complete-capture contract

The existing `HISTORICAL_NSE_SECURITY_MASTER_SNAPSHOT` family now also stores an
additive `v2-prospective-complete-capture` snapshot and
`NseMiiCurrentMasterCaptureReceipt`; no generic audit store, identity resolver,
or parallel master store exists. V2 snapshot identity includes automatic
`HSI_FIRST_OBSERVED_AT`, so a later recovery of identical bytes is distinct
immutable evidence and cannot change a V1 partial capture.

`COMPLETE` requires: fixed official source/date/filename; full gzip EOF; exact
`Content-Length` equality when supplied; required schema; direct single-file
scope with no pagination; zero structural rejects; every source row parsed; and
every canonical-eligible deterministic row durably present before the receipt.
Identity-ineligible records are counted separately and are neither repaired nor
treated as file truncation. The receipt binds content/schema/snapshot/extraction
fingerprints, all count stages, transfer/pagination state and first observation.

## One bounded production capture

Exactly one official request was made through
`scripts/collect_nse_execution_master_current.py`. The existing first-party
calendar selected the latest completed session, `2026-09-11`; weekend dates and
the `2026-09-14` NSE holiday were not substituted as sessions.

| Field | Receipt value |
| --- | --- |
| Source/business date | `2026-09-11` (date precision only) |
| `HSI_FIRST_OBSERVED_AT` | `2026-09-13T16:18:38.157825+00:00` |
| Source declared rows | unavailable |
| Raw captured / parsed rows | 37,676 / 37,676 |
| Retained / canonical eligible rows | 37,616 / 37,616 |
| Identity-ineligible / structural rejected | 60 / 0 |
| Bytes / declared length | 1,254,862 / 1,254,862 |
| Transfer / pagination | `FULL_GZIP_EOF` / `SINGLE_FILE_NO_PAGINATION` |
| Completeness | `COMPLETE` |
| Raw source fingerprint | `sha256:f5f57d64af5db378531c65b181cac7c0417effcd0b6c9c6fb299e493d909b0ab` |
| Receipt ID | `nse-mii-current-master-capture:648df000bae29e6de5320495bf162549` |
| Receipt fingerprint | `sha256:9327ec8f4ae07a470146c16a1938b3346e7ba3705aab256c90ae415b7bdb6e33` |

Source date, first observation and processing remain distinct. No source
time-of-day is invented or backdated into HSI knowledge time.

## Selection, exact joins and replay

The existing reader now prefers the latest eligible V2 `COMPLETE` receipt and
verifies parent and row coverage. It retains the legacy complete-master fallback
only when there is no prospective admission; a newer partial master still cannot
supersede an older complete master. Equal-date independent candidates are a
conflict, never input-order selection.

V2 preserves exact symbol, series, ISIN, `FinInstrmId` (retained as the exact
source `security_code`), security type, instrument type and CM-product lineage
for existing PRICE_BAND joins. The file does not provide a separate
broker token or exchange-segment field, so neither is fabricated or mapped. It
does not evaluate Gate 3 or turn a join into a pass.

| Source key | Current exact disposition |
| --- | --- |
| `CORDELIA / EQ` | `SOURCE_ROW_CONFLICT`: V2 ISIN `INE0LZF01039` differs from canonical `INE0LZF01013`. |
| `ELECTCAST / W1` | `OUTSIDE_CURRENT_SCOPE`: V2 is warrant `INE086A13016`, not canonical equity `INE086A01029`. |
| `TDPOWERSYS / EQ` | `SOURCE_ROW_CONFLICT`: complete V2 ISIN `INE419M01035` differs from canonical `INE419M01027`; no transition is inferred. |

`--replay-capture RECEIPT_ID` reopens the complete receipt with no network or
clock refresh, preserving first observation, completeness and fingerprints.

## Readiness matrix

| Requirement | State | Basis |
| --- | --- | --- |
| Official source / machine access | `READY` | Fixed NSE archive path; one bounded direct HTTPS request. |
| Raw capture, parsing and retention | `READY` | EOF/length proof; 37,676 parsed; 37,616 admitted; zero structural rejects. |
| First observed and source date | `READY` | Immutable V2 observation plus exact date-only source label. |
| Current execution-master continuity | `READY` | Latest completed-session V2 admission; no later observed master. |
| Symbol / series / ISIN / token lineage | `READY` | Exact fields retained; individual conflicts stay explicit. |
| PRICE_BAND identity input | `READY` | Exact symbol+series/security/ISIN lineage available; row admission is separate. |
| Historical replay | `READY` | Network-free receipt reopening. |
| Gate-3 overall readiness | `NOT_READY` | ASM/GSM machine-complete capture remains blocked. |

No MII session-knownness policy, historical identity interval, corporate-action
project, Price Band policy, ASM/GSM collector, portfolio, signal, broker,
order, API, UI, or Gate evaluator changes in this repair.

**Final result: `CURRENT_EXECUTION_MASTER_CONTINUITY_CLOSED`.**

Next continuation: **`GATE1_ROTATION_SOURCE_READINESS_V1`**. Gate-3 ASM/GSM
remains `GATE3_ASM_GSM_MACHINE_COMPLETENESS_BLOCKED` and is not reopened.
