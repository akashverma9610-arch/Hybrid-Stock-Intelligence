# Exact Issuer-Identifier Primary Acquisition V1

**Status: `IMPLEMENTED_BOUNDED_ADAPTER / PRIMARY_SOURCE_ONLY / NOT_ACTIVE / NON_EXECUTABLE`.**

## Purpose

This slice supplies the existing session-scoped [`IssuerSecurityBridge`](ISSUER_LEGAL_ENTITY_SECURITY_IDENTITY_BRIDGE_PRIMARY_EVIDENCE_V1.md) only when an authoritative source directly states an exact ISIN and a stable issuer identifier. It persists source receipts and same-session bridges append-only in the existing `core_api_snapshots` repository families `HISTORICAL_ISSUER_IDENTIFIER_EVIDENCE` and `HISTORICAL_ISSUER_SECURITY_BRIDGE`. It does not create an issuer master, backfill historical identity, classify company type, or mutate financial, portfolio, strategy, broker, or execution state.

The separately bounded [BRSR primary backfill](BRSR_PRIMARY_ISSUER_IDENTIFIER_BACKFILL_V1.md) uses the immutable evidence family for an official BRSR row that directly states an exact NSE symbol and CIN but no ISIN. It is filing-level evidence only: it cannot create a session bridge or infer continuity.

## Exact admissible source shapes

| Source lineage | Required labelled structured fields | Identifier emitted | Date semantic | Rejected input |
| --- | --- | --- | --- | --- |
| NSE structured filing | `SYMBOL`, `ISIN`, `Corporate Identity Number (CIN) of the Listed Entity`, `Date of Submission` | `CIN` | `Date of Submission` must equal the bound NSE session date. | Filing prose, company-name-only data, absent/invalid CIN or ISIN. |
| NSE BRSR General archive | `APP_ID`, `TLA_SUBMITTED_DT`, `SYMB_SYMBOL`, `Corporate Identity Number (CIN) of the Listed Entity` | `CIN` filing evidence only | Exact exchange submission timestamp; no ISIN means no session bridge. | Name matching, current-symbol backfill, source-date substitution, or continuity inference. |
| BSE structured corporate-information row | `Scrip Code`, `ISIN`, `CIN`, `Publication Date` | `CIN` | `Publication Date` must equal the bound NSE session date. | Unlabelled block/prose, missing scrip code, CIN, ISIN, or date. |
| GLEIF/ANNA certified ISIN-to-LEI ZIP | One unambiguous CSV containing `ISIN`, `LEI` | `LEI` | Archive’s explicitly supplied file date must equal the bound NSE session date. | Current or later file used for an earlier session; malformed or multi-CSV archive. |

The NSE [QIP filing page](https://www.nseindia.com/companies-listing/corporate-filings-QIP) exposes the required company-detail fields, and NSE’s [XBRL filing information](https://www.nseindia.com/static/companies-listing/xbrl-information) documents the structured filing families. The GLEIF [ISIN-to-LEI relationship-file page](https://www.gleif.org/en/lei-data/lei-mapping/download-isin-to-lei-relationship-files) states that the daily mappings are an ANNA process certified by GLEIF, while also warning that coverage is limited to participating NNAs/newly issued ISINs and is intended to expand to legacy ISINs over time.

Source lineages are persisted independently. Multiple exact IDs for the same session security are retained and the bridge resolver returns `EVIDENCE_CONFLICTED`; no source precedence silently selects an issuer.

## Data and PIT invariants

- Binding uses an exact ISIN, never a company name, symbol similarity, parent/group relationship, or LLM output.
- A supplied NSE symbol is an additional exact consistency check: a mismatch rejects that candidate rather than falling back to ISIN-only linkage.
- The adapter creates only `EXACT_SESSION_DATE` bridges. It does not manufacture an effective interval or propagate a current mapping to another session.
- `historical_known_at`, if supplied, must be timezone-aware and no later than the source date. Its absence remains explicit—not an assertion that historical availability was verified.
- Source document bytes are fingerprinted; source-row identifiers/fingerprints, source reference/date/observation time, exact identifier, optional exact legal name, and GLEIF Level-1 registration-authority metadata are retained in immutable source evidence.
- GLEIF Level-1 `registrationAuthorityID` and `registrationAuthorityEntityID` are retained only as source metadata. An authority entity value is never promoted to `CIN` based on its shape.
- Replaying identical source evidence cannot create another evidence or bridge record. A distinct acquisition-operation receipt may record the deterministic `ALREADY_PRESENT` result without changing bridge evidence.

## Implementation boundary

`app.historical.issuer_identifier_acquisition` is a deterministic source-input/parser/store boundary. Network transfer, discovery pagination, credentials, and unlimited crawling are intentionally outside this module. The caller must provide one bounded raw source artifact, its official reference, explicit source date, and observation time. GLEIF input is capped at 64 MiB compressed / 256 MiB CSV-expanded, and can be given an exact allowed-ISIN set so a broad archive is scanned without persisting unrelated mappings. These are source-parser resource protections, not issuer or investment-policy thresholds.

No component imports company-type classification, a compounder/backtest, portfolio, broker, order, API, UI, or runtime modules. No output has a strategy, score, BUY/SELL/ROTATE instruction, sizing, price, or order field.

## Source and anchor audit

| Source contribution | Existing local primary artifacts with an exact issuer identifier | 2024-02-05 bridges | 2026-08-31 bridges | Result |
| --- | ---: | ---: | ---: | --- |
| NSE structured filings | 0 | 0 | 0 | Existing `CorporateFiling` rows retain no structured CIN/LEI field. |
| NSE BRSR FY23-24 General archive | 1,199 `CIN + symbol` filing receipts | 0 | 0 | Exact primary issuer evidence; source does not state ISIN, so session promotion remains blocked. |
| BSE primary filings / XBRL | 0 | 0 | 0 | Stored BSE records retain security/financial lineage but no structured CIN/LEI. |
| GLEIF/ANNA | 0 persisted | 0 | 0 | The dated 2026-08-31 archive is an eligible source shape, but no complete, verified exact artifact has yet been retained. |

All five named targets remain `ISSUER_EVIDENCE_UNAVAILABLE` under the existing
same-session bridge resolver at both anchors. Each now has a distinct exact
BRSR `CIN + symbol` source receipt, but that does not alter the resolver:

| Symbol | ISIN | Exact BRSR CIN | 2024-02-05 | 2026-08-31 |
| --- | --- | --- | --- | --- |
| `APARINDS` | `INE372A01015` | `L91110GJ1989PLC012802` | `ISSUER_EVIDENCE_UNAVAILABLE` | `ISSUER_EVIDENCE_UNAVAILABLE`; potential continuity only. |
| `GENUSPOWER` | `INE955D01029` | `L51909UP1992PLC051997` | `ISSUER_EVIDENCE_UNAVAILABLE` | `ISSUER_EVIDENCE_UNAVAILABLE`; potential continuity only. |
| `GLAND` | `INE068V01023` | `L24239TG1978PLC002276` | `ISSUER_EVIDENCE_UNAVAILABLE` | `ISSUER_EVIDENCE_UNAVAILABLE`; potential continuity only. |
| `DEEPINDS` | `INE0FHS01024` | `L14292GJ2006PLC049371` | `ISSUER_EVIDENCE_UNAVAILABLE` | `ISSUER_EVIDENCE_UNAVAILABLE`; potential continuity only. |
| `ICICIBANK` | `INE090A01021` | `L65190GJ1994PLC021012` | `ISSUER_EVIDENCE_UNAVAILABLE` | `ISSUER_EVIDENCE_UNAVAILABLE`; potential continuity only. |

## Remaining authoritative session-bridge gap

The remaining session-bridge blocker is not a name-matching problem. BRSR can establish dated exact `CIN + NSE symbol` filing evidence, but the FY23-24 General table does not pair that evidence with ISIN. The [ISIN ↔ Issuer Bridge Continuity Policy Proposal V1](ISIN_ISSUER_BRIDGE_CONTINUITY_POLICY_PROPOSAL_V1.md) records the separate, non-active anchor and forward-continuity question; no BRSR observation or later same-symbol session receipt is promoted before explicit approval and same-session MII proof. In particular, the GLEIF daily file must be acquired completely and validated as one ZIP before its filtered exact rows may be stored; a partial transfer is rejected. A 2026 file cannot be used for the 2024 anchor, and current exchange/company data cannot be retrofitted backward.

Until meaningful same-session bridge coverage exists, the next company-type ingestion/classification and Compounder backtest readiness stages remain out of scope.
