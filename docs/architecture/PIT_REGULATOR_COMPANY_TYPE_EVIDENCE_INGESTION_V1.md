# PIT Regulator Company-Type Evidence Ingestion V1

**Status: `IMPLEMENTED / EVIDENCE_ONLY / CLASSIFICATION_NOT_ACTIVE / NON_EXECUTABLE`.**

## Scope and non-activation boundary

This slice preserves immutable, public primary-regulator entity facts and
reuses the canonical NSE Indices taxonomy records so a later approved policy
can assess company-type evidence. It does **not** activate
`PIT_COMPANY_TYPE_CLASSIFICATION_RESEARCH_AND_CONTRACT_V1`, create a
company-type receipt, select `BANK`, `NBFC`, `INSURER`, or `NON_FINANCIAL`, or
change any Long-Term Thesis, Compounder, portfolio, broker, order, API, UI, or
runtime state.

The only persistence boundary is the existing immutable
`HISTORICAL_REGULATOR_ENTITY_EVIDENCE` family in `core_api_snapshots`.
It is separate from the active `HISTORICAL_ISSUER_SECURITY_BRIDGE` lineage and
from taxonomy persistence. An entity receipt is not an issuer bridge and a
regulator category is not an HSI company type.

```text
official regulator or NSE taxonomy source
  -> immutable source artifact and exact source row
  -> exact identifiers only where the source actually supplies them
  -> exact active-CIN / exact-ISIN compatibility audit
  -> evidence readiness report
```

No name, alias, ticker, group, parent, subsidiary, LLM, or fuzzy matching step
exists in this flow.

## Primary-source families and retained data

| Family | Official source | Retained entity facts | Current result |
| --- | --- | --- | --- |
| RBI scheduled commercial banks | [RBI list of Scheduled Commercial Banks](https://www.rbi.org.in/Scripts/BS_viewcontent.aspx?Id=3657) | Legal bank name, exact RBI table category, source artifact/row fingerprint, source observation semantics | 121 rows; exact category retained, including nationalised, private, small-finance, payments, regional-rural and foreign-bank categories. |
| RBI registered NBFCs / ARCs | [RBI NBFC list directory](https://www.rbi.org.in/Scripts/BS_NBFCList.aspx) and its official linked XLSX | Legal name, CoR, RBI category, CIN, address, registration/snapshot date *only if supplied by a valid official XLSX* | No entity rows acquired: both linked XLSX document requests failed closed with `ConnectionError`; no HTML denial page was parsed as a list. |
| RBI cancelled NBFC / ARC CoR | [RBI NBFC list directory](https://www.rbi.org.in/Scripts/BS_NBFCList.aspx) and its official linked XLSX | Exact cancelled entity, CoR, category, CIN, address, cancellation date and source date *only if supplied* | No entity rows acquired for the same fail-closed source-access result. A future retrieved cancellation is a separate lifecycle fact, never a backwards registration inference. |
| IRDAI Life insurers | [IRDAI Life insurers](https://irdai.gov.in/list-of-life-insurers1) | Legal insurer name, registration number where shown, address, explicit `LIFE` subtype and source lineage | 26 rows. |
| IRDAI General insurers | [IRDAI General insurers](https://irdai.gov.in/list-of-general-insurers) | Legal insurer name, address, explicit `GENERAL` subtype and source lineage | 28 rows; the page does not expose a registration-number column, so none is fabricated. |
| IRDAI Health insurers | [IRDAI Health insurers](https://irdai.gov.in/list-of-health-insurers) | Legal insurer name, address, explicit `HEALTH` subtype and source lineage | 8 rows; the page does not expose a registration-number column, so none is fabricated. |
| NSE taxonomy | [NSE Indices industry classification](https://www.niftyindices.com/resources/industry-classification) | Existing exact instrument ID, hierarchy codes, source hash, first-observed/as-of semantics | Existing 711 records reused; no duplicate acquisition. |

The regulatory pages acquired on 2026-09-05 did not declare a list/snapshot
date in the parsed entity table. Their records therefore carry
`SOURCE_DATE_UNAVAILABLE`: source observation is retained, but it is not
retroactively treated as historical availability. The RBI NBFC directory
shows a dated list directory, but an accessible, valid official row document
is still required before NBFC or ARC row evidence can be stored.

## Exact issuer compatibility

The compatibility auditor joins an active forward issuer observation only on
an exact CIN that is present in the regulator row. It returns either
`EXACT_CIN_LINKED` or `ISSUER_LINKAGE_UNRESOLVED`; no legal name participates
in the join.

Textually identical legal names are separately reportable as
`POTENTIAL_EXACT_NAME_CORRESPONDENCE`, but are non-authoritative research
diagnostics. They cannot create an issuer link, resolve a CIN, or enable a
classification. For example, RBI contains `ICICI Bank Limited`, while the
active target issuer has CIN `L65190GJ1994PLC021012`; the RBI list supplies no
CIN for that row. The result is retained bank evidence with
`ISSUER_LINKAGE_UNRESOLVED`, not a special ICICIBANK link.

## PIT and taxonomy rules

Regulator source observation time and an explicitly supplied source/effective
or cancellation date are retained independently. A current page is never used
for 2024, and a cancellation row never supplies an unstated registration
start/end. The current live regulator rows cannot establish any status at
`2026-08-31` either, because their list date is unavailable and their source
observation occurs after that date.

The existing 711 official NSE taxonomy records retain exact four-tier codes
and were first observed on 2026-08-27, so they are PIT-eligible at
2026-08-31. They remain descriptive taxonomy evidence only. The current
stored financial macro-sector code is `IN05`; an approved exact code map is
still required to distinguish a supported non-financial entity from banks,
NBFCs, insurers, brokers, exchanges, asset managers, holding/investment
companies, and other intermediaries. Therefore no rule such as
`taxonomy != Financial Services -> NON_FINANCIAL` exists.

Candidate taxonomy-map readiness is limited to this stable-code boundary:

| Stable code family | Candidate research handling | Status |
| --- | --- | --- |
| `IN05` financial macro sector | Requires an approved exact subcategory map; cannot itself select any supported company type. | `PROPOSED / NOT_APPROVED / NOT_ACTIVE` |
| Every other macro/sector/industry/basic-industry code | Requires an approved positive code-to-`NON_FINANCIAL` map and regulator-conflict rule. | `PROPOSED / NOT_APPROVED / NOT_ACTIVE` |

No display-name heuristic or inferred taxonomy map is introduced here.

## Production evidence receipt — 2026-09-05

The first immutable application inserted four source artifacts and 183 entity
rows. An immediate in-memory exact replay inserted zero new artifacts and zero
new rows (121/26/28/8 rows were reported `ALREADY_PRESENT` respectively).

| Evidence family | Rows | Exact active-issuer links | Unresolved regulator rows |
| --- | ---: | ---: | ---: |
| RBI scheduled commercial bank | 121 | 0 | 121 |
| RBI registered NBFC | 0 | 0 | 0 |
| RBI registered ARC | 0 | 0 | 0 |
| RBI cancelled NBFC / ARC | 0 | 0 | 0 |
| IRDAI Life insurer | 26 | 0 | 26 |
| IRDAI General insurer | 28 | 0 | 28 |
| IRDAI Health insurer | 8 | 0 | 8 |
| **Total regulator entity evidence** | **183** | **0** | **183** |

There are 20 exact-text-only legal-name correspondences with historic issuer
evidence, including `ICICI Bank Limited`; all remain unresolved and do not
alter the table above. No regulator-versus-taxonomy company-type conflict is
claimed because there is no approved taxonomy code map or exact regulator
issuer link to compare.

### 2026-08-31 readiness

| Measure | Count / status |
| --- | --- |
| Active exact issuer observations | 335 |
| Distinct active CINs | 332 |
| Exact RBI bank issuer links | 0 |
| Exact RBI NBFC issuer links | 0 |
| Exact IRDAI Life / General / Health links | 0 / 0 / 0 |
| Existing NSE taxonomy rows PIT-eligible | 711 |
| Taxonomy rows with an exact active-issuer observation | 201 rows / 202 observations |
| Unsupported financial taxonomy cases | `NOT_EVALUATED` — exact code map is unapproved |
| Conflicts | 0 proven; no precedence or heuristic was applied |
| Active issuer observations with no exact regulator company-type evidence | 335 |

### 2024-02-05 readiness

At `2024-02-05T23:59:59Z`, active issuer bridges, PIT-valid regulator evidence,
and PIT-valid taxonomy evidence are all **0**. The current evidence has not
been used backwards.

### Five-target evidence readiness

| Symbol | Active exact CIN / ISIN bridge | Exact RBI / IRDAI link | Exact PIT taxonomy evidence | Readiness only |
| --- | --- | --- | --- | --- |
| APARINDS | Present | None | Present | Future branch unavailable pending approved taxonomy map. |
| DEEPINDS | Present | None | Absent | `ISSUER_LINKAGE_UNRESOLVED` / taxonomy unavailable. |
| GENUSPOWER | Present | None | Absent | `ISSUER_LINKAGE_UNRESOLVED` / taxonomy unavailable. |
| GLAND | Present | None | Present | Future branch unavailable pending approved taxonomy map. |
| ICICIBANK | Present: `L65190GJ1994PLC021012` / `INE090A01021` | None; RBI legal-name row has no CIN | Present | `POTENTIAL_EXACT_NAME_CORRESPONDENCE` only; no bank classification. |

## Explicit unresolved blocker and next boundary

`COMPANY_TYPE_EVIDENCE_COVERAGE = INSUFFICIENT`.

The concrete blocker is the absence of an approved exact regulator-identifier
bridge for the 183 stored RBI/IRDAI rows, combined with inaccessible official
RBI NBFC/ARC row documents and the absence of an approved exact NSE taxonomy
code map. These prevent a positive, PIT-safe issuer company-type conclusion.

`PIT_COMPANY_TYPE_CLASSIFICATION_ACTIVATION_V1` is therefore not authorized by
this evidence slice. No Compounder backtest or product activation follows from
this document.
