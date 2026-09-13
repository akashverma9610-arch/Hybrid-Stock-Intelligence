# Gate-3 ASM/GSM Official Complete-Export Identity Feasibility Decision V1

Status: **DECIDED / GOVERNANCE_AND_SOURCE_FEASIBILITY_ONLY / NON_EXECUTABLE / NOT_GATE_ACTIVE**.

Decision **D: `CURRENT_OFFICIAL_PATH_CANNOT_PROVE_COMPLETE_CAPTURE`**.
Baseline: `f59ce5e5356d1bf8ce8481c4404ec1e969c4cca7`, main.

This bounded decision follows the accepted [source-capture-completeness repair](GATE3_SURVEILLANCE_SOURCE_CAPTURE_COMPLETENESS_REPAIR_V1.md). It examines only whether the already-known NSE ASM and GSM products expose a machine-verifiable prospective *complete-product* identity. It does not alter the existing collector, raw snapshot store, Gate 3, Gate 6, the six active gate contract, thresholds, execution-master selection, portfolio, signals, orders, or brokers.

`V1_ACTIVE = TRUE`; `GATE_POLICY_V2_ACTIVE = FALSE`; `SIX_GATES_EXACTLY_SIX = TRUE`; `NO_FABRICATED_SURVEILLANCE_CLEARANCE = TRUE`; `NO_FUTURE_LEAKAGE = TRUE`; `NO_RETROACTIVE_SURVEILLANCE_STATE = TRUE`; `PILOT_SIMPLICITY_RULE = ACTIVE`; `AI_DECISION_AUTHORITY = FALSE`.

## Decision boundary

NSE documents a named ASM and GSM list. That proves the official products exist; it does not prove that HSI's `reportASM` or `reportGSM` response is the same complete logical product. HTTP success, EOF, parsed shape, or an equal row count cannot supply the missing binding.

| Dimension | ASM | GSM |
| --- | --- | --- |
| Official documented complete product | `NSE_ASM_COMPLETE_LIST` | `NSE_GSM_COMPLETE_STAGEWISE_LIST` |
| Current HSI API | `https://www.nseindia.com/api/reportASM` | `https://www.nseindia.com/api/reportGSM` |
| Current capture result | `UNPROVEN` | `UNPROVEN` |
| This decision's export result | `EXPORT_EXISTS_BUT_MACHINE_ACCESS_UNPROVEN` | `EXPORT_EXISTS_BUT_MACHINE_ACCESS_UNPROVEN` |
| API-to-complete-product relationship | `UNPROVEN` | `UNPROVEN` |

The official [ASM regulatory page](https://www.nseindia.com/static/regulations/additional-surveillance-measure) links its named list to the official [ASM report page](https://www.nseindia.com/reports/asm). The official [GSM regulatory page](https://www.nseindia.com/static/regulations/graded-surveillance-measure) does the same for the official [GSM report page](https://www.nseindia.com/reports/gsm). Both report pages present a client-side `Download (.csv)` control. Neither page exposes a direct download URL, export identifier, manifest, source-list date, effective date, pagination contract, or response filename in its static HTML. A UI label alone is not a machine-verifiable export artifact.

## Known official-path inventory

| Family | Official documentation and product label | Report/list path | Current API form | Stable official identity | Missing or incidental-only fields |
| --- | --- | --- | --- | --- | --- |
| ASM | `List of scrips shortlisted in Additional Surveillance Measure` | `/reports/asm` | `/api/reportASM`; object sections `longterm` and `shortterm` | Official page/path, label, two required report sections, documented identity `List_of_securities_shortlisted_under_ASM.csv` | Direct CSV URL/ID, response filename, list/effective date, content hash, schema/version contract, cursor/manifest, API/export binding |
| GSM | `List of scripts shortlisted in Graded Surveillance Measure` | `/reports/gsm` | `/api/reportGSM`; one reported array | Official page/path, label, documented identity `List_of_scrips_shortlisted_in_Graded_Surveillance_Measure` | Direct CSV URL/ID, response filename, list/effective date, whether one combined file or required stage-component set, manifest, schema/version contract, API/export binding |

The regulatory-page update date is page metadata only. It is not adopted as a source-list date, known-at time, or effective date. No known path disclosed a query parameter, pagination token, content-disposition filename, compressed-file identity, workbook/sheet name, or stable download/export ID. No broader source search, alternate provider, archive, historical collection, or browser automation was performed.

## One bounded direct-fetch observation per candidate

For each report-page candidate, one direct HTTPS GET used TLS verification, a 15-second timeout, no request cookies or authorization, no redirect following, and bounded metadata inspection. It retained no response body or production data. These observations prove only the report-page transport shape, not a complete export.

| Candidate | HTTP / redirect | Response identity | Export metadata | Parse / component conclusion | Access classification |
| --- | --- | --- | --- | --- | --- |
| ASM `/reports/asm` | `200`; no redirect | `text/html; charset=utf-8`; HTML; content length absent | no content disposition, direct CSV href, or `reportASM` marker in inspected response | UI contains `Long Term`, `Short Term`, and a CSV control, but no machine-addressable file or manifest | `UNPROVEN` for export access; report page itself is public without a cookie |
| GSM `/reports/gsm` | `200`; no redirect | `text/html; charset=utf-8`; HTML; content length absent | no content disposition, direct CSV href, or `reportGSM` marker in inspected response | UI contains a CSV control, but no stage manifest or machine-addressable file | `UNPROVEN` for export access; report page itself is public without a cookie |

The report-page result does not establish a homepage bootstrap, cookie, referer, anti-bot, or browser requirement for a *file*, because no distinct file request was exposed. Therefore `SESSION_COOKIE_DEPENDENCY = UNPROVEN` for each export. The existing `OfficialSurveillanceTransport` already makes bounded public HTTPS requests without authentication, but its fixed API-only contract cannot claim to retrieve an undisclosed client-side export. A future direct-file path would require a separately reviewed bounded adapter extension only after NSE exposes a stable official request identity; browser automation is not authorized.

## API relationship and conditional comparison contract

The API is not certified as a direct export, an equivalent rendering, or a partial view. Its relationship is `UNPROVEN` for both families: the official pages show report/UI controls but provide no evidence binding `reportASM` or `reportGSM` to the named complete product. Existing product contracts correctly retain `api_to_documented_export_bound = False`.

If NSE later exposes a direct complete artifact or manifest, a future bounded implementation may compare it only after retaining an exact official product/export ID and request identity, raw bytes and SHA-256 content hash, first-observed UTC time, source/list date if supplied, schema clues, component/stage coverage, a normalized identity set, and a receipt fingerprint. It must prove complete transfer and no undeclared pagination/cursor. It must compare normalized content, never row count alone.

The conditional ASM comparison key is the source-supported security identity (`ISIN` where supplied, with exact source symbol retained), report section (`longterm` or `shortterm`), exact ASM stage/source indicator, and any supplied list/effective metadata. Both sections are required. The conditional GSM comparison key is the source-supported security identity, exact raw GSM/source indicator, and any supplied list/effective metadata. GSM cannot be certified until NSE proves either one combined current list or an exact stage-component manifest with every required component fetched. No missing date, stage, symbol, or identity may be inferred; duplicates and conflicts must be retained rather than silently collapsed.

This is a future comparison shape, not a current comparison implementation: no complete export bytes, export schema, component manifest, or API/export binding are available. It therefore cannot attest a current API capture.

## GSM row-admissibility separation

The existing prospective capture retained 36 exact composite/legacy/unsupported GSM source representations. They are not transformed into numeric stages and do not establish capture completeness or incompleteness. The available evidence proves only that the parser retained source values; it does not prove whether they are current-product rows, legacy categories, or another officially defined category. Their classification remains `ROW_VALUE_UNSUPPORTED / SOURCE_SEMANTICS_UNPROVEN`; no numeric mapping or admissibility decision is authorized here.

## Feasibility and retention matrix

| Requirement | ASM | GSM |
| --- | --- | --- |
| Official complete product documented | `READY` | `READY` |
| Direct complete export exposed to UI | `PARTIAL` | `PARTIAL` |
| Machine-fetchable export artifact | `UNPROVEN` | `UNPROVEN` |
| Stable complete-product identity | `PARTIAL` | `PARTIAL` |
| All required sections/components known | `READY` — long/short | `UNPROVEN` — no combined-file or stage manifest proof |
| API/export content equivalence testable today | `NOT_READY` | `NOT_READY` |
| Existing adapter can access complete product | `UNPROVEN` | `UNPROVEN` |
| Raw evidence auditable for current API | `READY` | `READY` |
| Raw evidence auditable for complete export | `NOT_READY` | `NOT_READY` |
| Prospective complete capture feasible today | `NOT_READY` | `NOT_READY` |
| Future current-API retention | `KEEP_AS_DISCOVERY_ONLY` | `KEEP_AS_DISCOVERY_ONLY` |

`KEEP_AS_DISCOVERY_ONLY` is a governance retention recommendation, not a collector change. Existing API snapshots continue to be immutable source evidence with unresolved completeness; they cannot yield non-blocking Gate-3 evidence, absence, clearance, a Gate PASS, or a portfolio/trading result.

## No-row-count proof and reuse

The static prospective test `test_api_row_count_never_certifies_documented_complete_export` covers both ASM and GSM at multiple row counts. It proves that a parsed count and EOF leave the API pagination/completeness state `UNPROVEN`. This is deliberately separate from row parsing, row identity, and row-value admissibility.

The decision reuses the existing fixed NSE HTTP transport, surveillance collector, immutable raw/evidence/completeness receipts, content fingerprints, first-observed clock, and approved identity normalization. It creates no HTTP framework, database, snapshot family, scheduler, browser path, or clock. The current execution master is expressly out of scope: `EXECUTION_MASTER_CONTINUITY = SEPARATE_OPEN_BLOCKER`.

## Exact result and next continuation

At least one required family—and in fact both—lack a defensible machine-verifiable complete-product path on the known official endpoints. The exact final decision is:

**D. `CURRENT_OFFICIAL_PATH_CANNOT_PROVE_COMPLETE_CAPTURE`**

The exact and only next continuation is:

**`GATE3_ASM_GSM_COMPLETENESS_GOVERNANCE_FALLBACK_V1`**

It is not started by this decision. No historical ASM/GSM acquisition, Gate-3 activation, V2 activation, Gate-6 change, execution-master repair, or production policy change is authorized.

## Validation

- Known source identity, ASM product-shape, GSM raw-stage, current completeness, immutable receipt/auditability, transport, and reuse tests are in `tests/unit/test_surveillance_prospective.py`.
- The bounded direct-fetch observations above made one direct request per report-page candidate and retained no response body.
- Markdown local-link validation and `git diff --check` are required before commit.
- No full backend suite is required: this slice adds no runtime implementation, database, API, Gate, or policy behaviour.

The companion machine receipt is [`GATE3_ASM_GSM_OFFICIAL_COMPLETE_EXPORT_IDENTITY_FEASIBILITY_DECISION_V1.json`](GATE3_ASM_GSM_OFFICIAL_COMPLETE_EXPORT_IDENTITY_FEASIBILITY_DECISION_V1.json).
