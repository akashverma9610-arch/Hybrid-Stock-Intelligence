# BRSR Primary Issuer-Identifier Backfill V1

**Status: `IMPLEMENTED_BOUNDED_ACQUISITION / PRIMARY_EXCHANGE_ONLY / NOT_ACTIVE / NON_EXECUTABLE`.**

## Purpose and boundary

This source-specific adapter extracts a filing-level relationship only when one
official NSE BRSR General-table row directly labels the NSE application ID,
submission timestamp, NSE symbol, CIN, and (when supplied) listed-entity name.
It appends that source receipt to the immutable
`HISTORICAL_ISSUER_IDENTIFIER_EVIDENCE` boundary.

The BRSR General table used here does **not** state ISIN. It therefore proves
exact `CIN + NSE symbol` filing evidence, not an `ISIN + CIN` bridge and not a
timeless issuer master. It creates no `IssuerSecurityBridge`, security
interval, historical bridge, or company type. A later same-symbol session may
be reported only as `POTENTIAL_PIT_BRIDGE_CONTINUITY`; promotion needs a
separately approved continuity policy.

```text
official NSE BRSR General row
  → exact application ID + symbol + CIN + submission timestamp
  → immutable filing-level issuer evidence
  → potential continuity audit only

not: company name → CIN
not: BRSR symbol → later-session ISIN bridge
not: CIN → company type
```

The module has no company-type, Compounder/backtest, discovery, portfolio,
API, UI, runtime, broker, order, score, or strategy dependency. It neither
parses free-form prose nor uses OCR.

## Official archive discovery

The [NSE Compliance Information archive](https://www.nseindia.com/regulations/listing-compliance)
lists BRSR bulk files for FY21-22, FY22-23, FY23-24, and FY24-25. It is not a
complete issuer registry: BRSR was mandatory for the top 1,000 listed entities
from FY22-23, while earlier coverage may be voluntary. Missing BRSR evidence
does not prove that an issuer does not exist or cannot be identified elsewhere.

This bounded slice uses the official FY23-24 archive
[`BRSR_Data_Dump.zip`](https://nsearchives.nseindia.com/web/sites/default/files/inline-files/BRSR_Data_Dump.zip)
and the explicitly selected member
`BRSR_Data_Dump/BRSR_General/brsr_general 1.xlsx`. Its `Export Worksheet`
directly labels `APP_ID`, `TLA_SUBMITTED_DT`, `SYMB_SYMBOL`, `Corporate
Identity Number (CIN) of the Listed Entity`, and `Name of the Listed Entity`.
The source document fingerprint is the selected workbook member; provenance
also retains the official ZIP URL and exact member path.

FY21-22 was inspected as an official workbook and contains separate submission
and general-disclosure tables, so its normalized-table join is not part of this
direct-row adapter. FY22-23 is a 160 MiB official workbook and was not
downloaded under the bounded-input limit. FY24-25 returned an official-host
availability failure during discovery and was not retried. None changes the
FY23-24 artifact's provenance or semantics.

## Exact extraction rules

| Field | Accepted labelled field | Treatment |
| --- | --- | --- |
| Filing identity | `APP_ID`, `APPLICATION_NUMBER`, or `BRSR_SUBMISSION_DTLS_ID` | Required; an XLSX integer is retained as its exact decimal application ID. |
| NSE security locator | `SYMB_SYMBOL`, `NSE Symbol`, or `Symbol` | Required exact source field; no name-derived fallback. |
| CIN | `Corporate Identity Number (CIN) of the Listed Entity`, `CIN`, or `COMPANY_CIN` | Required; only existing structural CIN validation is applied. |
| Filing-known time | `TLA_SUBMITTED_DT`, `Date of Submission`, or `PDF_SUBMISSION_DT` | Required; exchange-displayed Indian time becomes UTC `historical_known_at`, retaining its Indian calendar date as `source_as_of_date`. |
| Legal display metadata | `Name of the Listed Entity` (preferred), otherwise `COMPANY_NAME` or `Name of the Company` | Optional source display metadata only; never a matching key. |

One unambiguous General sheet must contain the required labelled fields. A
duplicate application ID with different content, ambiguous header, malformed
CIN, missing exact symbol, unsafe ZIP member path, oversize input, or invalid
filing timestamp fails closed. Replay cannot add another evidence row.

The parser has a 64 MiB ZIP bound and a 16 MiB selected-workbook bound. These
are parser safety controls, not coverage or investment thresholds. It loads
only the caller-specified workbook member and never pattern-selects a member.

## PIT and bridge boundary

`historical_known_at` is the official submission timestamp, never download or
parser runtime. Source observation time is provenance only. BRSR evidence is
available no earlier than its submission time.

| Evidence available | Permitted result | Prohibited result |
| --- | --- | --- |
| BRSR row with exact CIN and exact NSE symbol | Immutable filing-level `CIN + symbol` evidence. | ISIN/session bridge, continuity, or company type. |
| Exact source date plus independently retained exact session identity and ISIN in the same source context | Existing bridge rules may be evaluated independently. | Source-date substitution or inferred continuity. |
| Earlier BRSR symbol+CIN and later same-symbol session receipt | Read-only potential-continuity audit. | Historical bridge promotion. |
| Different CIN for exact same-symbol filing evidence | Retain evidence and report conflict. | Latest-row or source-priority resolution. |

The existing [`Issuer / Legal-Entity ↔ Listed-Security Identity Bridge`](ISSUER_LEGAL_ENTITY_SECURITY_IDENTITY_BRIDGE_PRIMARY_EVIDENCE_V1.md)
remains the only session-bridge contract.

## Bounded coverage result

The FY23-24 General workbook contains 1,204 inspected rows. Five rows have a
non-company placeholder rather than a structurally valid CIN and are rejected.
The remaining 1,199 filing-level evidence rows cover 1,174 distinct NSE symbols
and 1,171 distinct CINs. This is meaningful issuer **evidence** coverage, not
historical-session bridge coverage.

| Symbol | Exact CIN | NSE BRSR submission timestamp | Application ID | Result |
| --- | --- | --- | ---: | --- |
| `DEEPINDS` | `L14292GJ2006PLC049371` | `2024-06-20T10:38:09+00:00` | `45705` | Exact BRSR evidence retained. |
| `APARINDS` | `L91110GJ1989PLC012802` | `2024-07-31T11:41:17+00:00` | `52562` | Exact BRSR evidence retained. |
| `ICICIBANK` | `L65190GJ1994PLC021012` | `2024-08-05T17:45:27+00:00` | `53232` | Exact BRSR evidence retained. |
| `GLAND` | `L24239TG1978PLC002276` | `2024-08-07T13:57:13+00:00` | `53580` | Exact BRSR evidence retained. |
| `GENUSPOWER` | `L51909UP1992PLC051997` | `2024-09-06T05:41:15+00:00` | `57912` | Exact BRSR evidence retained. |

No BSE evidence is fabricated: the retained BSE filing corpus has no labelled
CIN field, and this adapter cannot transform financial/XBRL identity text into
issuer evidence.

## Verification and non-goals

Focused tests prove labelled CIN and symbol extraction, exact numeric
application IDs, source-member provenance, malformed-CIN rejection, ambiguous
row/header rejection, preserved filing timestamp, deterministic identity,
immutable replay, exact-symbol target audit, conflict retention, and absence
of company-type, Compounder/backtest, portfolio, discovery, and execution
dependencies.

No BRSR evidence alone enables company type, financial comparability,
Compounder qualification, ranking, BUY/SELL/ROTATE action, portfolio mutation,
or broker/order action.
