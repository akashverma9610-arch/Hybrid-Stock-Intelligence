# Gate-3 Surveillance Source Capture Completeness Repair V1

Status: **IMPLEMENTED / SOURCE_EVIDENCE_ONLY / NON_EXECUTABLE / NOT_GATE_ACTIVE**.

Decision **D: `GATE3_SOURCE_CAPTURE_COMPLETENESS_NOT_PROVABLE_FROM_CURRENT_OFFICIAL_PATH`**.
Baseline: `99e3f963c9a9901c6411da04ef08d42de881a2a9`, main.

This repair supplements, rather than rewrites, the historical
[prospective collector receipt](GATE3_SURVEILLANCE_PROSPECTIVE_COLLECTOR_V1.md).
It changes no Gate-3 threshold, production Gate-3/6 evaluation, reducer,
portfolio, signal, order, or broker behaviour. The proposed composite policy
remains governance-approved with activation blockers and is not active.

## Three intentionally separate conclusions

| Dimension | Meaning | This repair's result |
| --- | --- | --- |
| `OFFICIAL_PRODUCT_IS_COMPLETE` | NSE describes the named product as a complete list. | Documented for ASM, GSM, and the CM price-band list. |
| `COLLECTOR_CAPTURE_IS_COMPLETE` | This exact retained response mechanically proves that it captured the entire named product. | Proven only for the direct price-band CSV. ASM and GSM remain `UNPROVEN`. |
| `GATE_COMPONENT_IS_ADMISSIBLE` | A later adapter can establish exact identity, known-at, effective state, policy validity, and component semantics. | Not evaluated or activated here. |

Source documentation calls ASM and GSM complete lists, respectively on the
[ASM regulatory page](https://www.nseindia.com/static/regulations/additional-surveillance-measure)
and [GSM regulatory page](https://www.nseindia.com/static/regulations/graded-surveillance-measure).
The [daily price-band page](https://www.nseindia.com/static/regulations/daily-price-bands-reports)
identifies the direct CSV as the complete list. Documentation does not itself
bind an arbitrary report-API response to an independently identified complete
ASM/GSM export.

## Immutable product-capture receipt

`SurveillanceCaptureCompletenessReceipt` is an additive typed record in the
existing `NSE_SURVEILLANCE_PROSPECTIVE` snapshot family. It binds the poll and
evidence fingerprints, official product identity/reference, documented export
identity, exact capture endpoint, logical expected sections, raw-parent lineage,
row/rejection counts, row-admissibility counts, transfer/schema/pagination
states, first observation, capture known-at, processing time, unresolved
source/effective metadata, reason codes, and a content fingerprint. The raw
payload hash remains in the immutable raw parent referenced through the bound
poll/evidence chain; it is not copied into a second raw store.

`COMPLETE` is mechanically legal only for the direct documented price-band file
with the exact schema, EOF/full body, no pagination, all expected file coverage,
and zero rejected rows. It cannot create a Gate component, a clearance, an
effective interval, or an order. Row identity conflicts and unsupported source
values are counted separately and retained.

## One bounded canary and capture conclusion

The single repair canary made exactly one official request to each existing
allowlisted surveillance path. Its stored polls completed at
`2026-09-13T15:13:29Z`; identical payloads retained their earlier immutable
first observations from `2026-09-13T14:17:32Z`/`14:17:33Z` rather than renewing
them. The stored polls and repaired completeness receipts reopened with identical
IDs and fingerprints and no additional network request.

| Family | Official product / exact capture route | HTTP / rows / rejected | Capture proof | `COLLECTOR_CAPTURE_IS_COMPLETE` | Row classification |
| --- | --- | ---: | --- | --- | --- |
| ASM | `NSE_ASM_COMPLETE_LIST`; `reportASM` | 200 / 239 / 0 | Both returned `longterm` and `shortterm` sections parsed; full body EOF | `UNPROVEN` | 186 resolved; 53 outside retained HSI scope; 239 explicit stages |
| GSM | `NSE_GSM_COMPLETE_STAGEWISE_LIST`; `reportGSM` | 200 / 75 / 0 | Returned array parsed; full body EOF | `UNPROVEN` | 58 resolved; 17 outside scope; 39 explicit stages; 36 unsupported composites/legacy values |
| PRICE_BAND | `NSE_CM_PRICE_BAND_COMPLETE_LIST`; `sec_list.csv` | 200 / 3,538 / 0 | Exact five-column complete-file schema, EOF, all CSV rows consumed, no pagination | `COMPLETE` | 2,549 resolved; 986 outside scope; 3 conflicted; 2,998 explicit numeric values; 540 unsupported values |

ASM's documented export identity is
`List_of_securities_shortlisted_under_ASM.csv`. GSM's documented list identity
is `List_of_scrips_shortlisted_in_Graded_Surveillance_Measure`. The existing
JSON report paths expose neither a bound export identifier nor a declared
pagination/manifest contract that proves those API representations are the whole
official products. This is a product-capture limitation, not a row-count
heuristic: 239 or 75 rows, HTTP 200, and EOF never establish completeness.

The price-band documented export identity is `Complete_List_of_Price_Bands.csv`.
Its direct `sec_list.csv` product has no cursor or pagination stage, its exact
schema parsed through EOF, and it had no rejected row. Its product capture is
therefore complete even though individual values and identities can remain
unadmitted.

## Row-level limitations retained without corrupting file capture

### Price-band representations

All 540 unsupported values were the exact source form `No Band`. It is a valid
non-static representation, not malformed input and not a static numeric band.
It remains `ROW_VALUE_UNSUPPORTED`: a future static-band component must not
derive a value from it. The remaining source forms were `20` (2,081 rows), `5`
(658), `10` (206), `2` (52), and `40` (1); only those explicit positive numeric
percentages are preserved as static-source values. Nothing here makes a
threshold decision.

### GSM representations

The 36 unsupported records are preserved source indicators, not fabricated
numeric GSM stages: 21 `IBC - Receipt & GSM 0`, 4 `ESM I & GSM 0`, 3 `GSM - VI`,
3 `ESM II & GSM 0`, 2 `LTASM I & GSM 0`, and one each of `IBC I & GSM 0`,
`GSM III & IBC - Receipt`, and `GSM IV & IBC - Receipt`. They are valid
composite/legacy representations for capture purposes but `ROW_VALUE_UNSUPPORTED`
for the approved `gsm_stage` component until a separate governed source mapping
exists. No new surveillance family was promoted.

### Exact price-band identity audit

| Source row | Classification | Exact evidence and bounded conclusion |
| --- | --- | --- |
| `CORDELIA / EQ` | `SOURCE_ROW_CONFLICT` | Current canonical identity is `INE0LZF01013`; retained 2026-08-31 and partially retained 2026-09-11 MII rows both identify exact `CORDELIA/EQ` as `INE0LZF01039`. No corporate-action inference was made. |
| `ELECTCAST / W1` | `OUTSIDE_CURRENT_SCOPE` | Canonical equity identity is `INE086A01029`; exact MII `W1` identifies a warrant, `INE086A13016`, named `ELECTCAST WARRANTS`. It is not promoted to the canonical equity. |
| `TDPOWERSYS / EQ` | `UNRESOLVED` | Canonical identity is `INE419M01027`; the older 2026-08-31 MII row carries `INE419M01035`, while the retained 2026-09-11 master capture is incomplete and has no row persisted for this exact key. The evidence does not prove a corporate-action or series transition. |

These rows remain individual conflicted/unadmitted observations. They do not
downgrade the complete direct-file capture and they do not receive a fuzzy match,
identity repair, clearance, or numeric component value.

## Current-master and source-time boundary

The existing NSE MII adapter retrieved the official date-named 2026-09-11
master—the latest completed regular session before the Sunday canary; the
existing calendar classifies 12–13 September as weekend and 14 September as an
NSE holiday. The artifact declares 37,616 valid rows, but the retained
append-only checkpoint contains 21,352 rows. The reader therefore rejects that
incomplete newer master and selects the latest complete retained master,
2026-08-31 (37,155 rows), reporting
`PARTIAL_LATEST_MASTER_CAPTURE_INCOMPLETE`. This is separate from surveillance
product capture and creates no current-execution or effective-state claim.

ASM `asmTime` and GSM `gsmTime` remain exact raw source labels whose publication,
timezone, known-at, and effective semantics are not established. The price-band
CSV supplies no adopted source/effective date in this contract. Every family
therefore records source-date/effective state as unresolved; first-observed and
capture-known-at remain distinct prospective provenance only.

## Adapter-readiness matrix

| Required future input | State | Reason |
| --- | --- | --- |
| ASM official product / capture | `READY / NOT_READY` | Product documented complete; current report API not bound to its complete export. |
| GSM official product / capture | `READY / NOT_READY` | Product documented complete; current report API has no proven complete stagewise/export binding. |
| Price-band official product / file capture | `READY / READY` | Direct documented CSV mechanically complete. |
| Row-level mapping and value state | `PARTIAL` | Exact mappings/unsupported/conflicts retained, never coerced. |
| First-observed and immutable raw lineage | `READY` | Parent raw/poll/evidence/completeness IDs reopen deterministically. |
| Source/effective metadata | `PARTIAL` | Raw display labels retained; no approved publication/effective semantics. |
| Current execution identity master | `PARTIAL` | Latest master checkpoint incomplete; latest complete retained master is dated 2026-08-31. |
| Future Gate-3 evidence adapter | `NOT_READY` | Required ASM and GSM capture completeness is not proven. |

No absence, empty list, HTTP success, parser success, stale master, or current
row observation is a non-blocking surveillance conclusion. The active
six-gate policy is untouched; no `PASS`, `BUY`, `SELL`, `ROTATE`, or portfolio
mutation is produced.

## Completed follow-up feasibility decision

The completed official-path feasibility decision is:

[`GATE3_ASM_GSM_OFFICIAL_COMPLETE_EXPORT_IDENTITY_FEASIBILITY_DECISION_V1`](GATE3_ASM_GSM_OFFICIAL_COMPLETE_EXPORT_IDENTITY_FEASIBILITY_DECISION_V1.md).

It determined that the known official report pages expose client-side CSV
controls but no machine-verifiable export artifact, manifest, or API binding.
Its Decision D, `CURRENT_OFFICIAL_PATH_CANNOT_PROVE_COMPLETE_CAPTURE`, retains
the current APIs as discovery-only evidence and authorizes no collector or Gate
change. It did not activate Gate 3, change thresholds, or infer absence.

## Validation

- Focused prospective collector/completeness tests: **81 passed**.
- Affected storage, identity, master, Gate-governance, and API snapshot tests:
  **323 passed, 2 existing dependency deprecation warnings**.
- One bounded live surveillance canary: exactly three official source requests;
  the later proof reopened stored records with zero requests.
- `git diff --check` and Markdown-link validation are required before commit.
- No full backend suite is required: no shared production gate, policy, or API
  behaviour changed.

The companion machine audit is
[`GATE3_SURVEILLANCE_SOURCE_CAPTURE_COMPLETENESS_REPAIR_V1.json`](GATE3_SURVEILLANCE_SOURCE_CAPTURE_COMPLETENESS_REPAIR_V1.json).

**Final result: `GATE3_SOURCE_CAPTURE_COMPLETENESS_NOT_PROVABLE_FROM_CURRENT_OFFICIAL_PATH`.**
