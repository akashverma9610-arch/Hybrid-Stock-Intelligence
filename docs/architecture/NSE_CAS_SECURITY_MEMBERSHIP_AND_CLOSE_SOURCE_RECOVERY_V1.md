# NSE CAS Security Membership and Close Source Recovery V1

Status: `SOURCE_RECOVERY_AUDIT / NO_PARAMETER_APPROVAL / NOT_ACTIVE`

Slice: `NSE_CAS_SECURITY_MEMBERSHIP_AND_CLOSE_SOURCE_RECOVERY_V1`

Audit closure: `ACCEPTED/CLOSED`. Source decision: **C - `CAS_MEMBERSHIP_SOURCE_STILL_BLOCKED`**.

This closes a bounded investigation, not membership recovery, a data feed or a research-price policy. No production database was read or changed. No runtime/provider code or source authority changed.

## Baseline and immutable lineage

- Repository: `D:\nse-stock-manager`; branch `main`; clean baseline `28fb8451208853c2705ca9b516f74e855441c581`.
- Artifact: `nse-cas-security-membership-and-close-source-recovery / v1` in the [machine-readable evidence matrix](NSE_CAS_SECURITY_MEMBERSHIP_AND_CLOSE_SOURCE_RECOVERY_V1.json).
- Artifact fingerprint: `sha256:b2fd0ba83dda8898065a43181837c675b2f46c6b27e3eb7404b68efa472b5d26`.
- [Session/price source predecessor](GATE1_ROTATION_RESEARCH_SESSION_PRICE_SOURCE_APPLICABILITY_AUDIT_V1.md): `sha256:e587cfb98e32610f6a0485c87d62a8546400ac19498c0aef18ad0b38b22e967c`.
- [Discovery-to-Brain handoff](CANONICAL_DISCOVERY_UNION_TO_BRAIN_HANDOFF_CONTRACT_V1.md): `canonical-discovery-union-to-brain-handoff / v1`, `sha256:731399dfbca758763dda0ad9ee1350aa50cd433ab183bb62fc710e4b5826b1e8`, remains `HANDOFF_CONTRACT_READY_WITH_CONSUMER_BINDING_BLOCKER`.
- Twelve native predecessor fingerprints and 204 LF-normalized file pins preserve the accepted chain, including the independent-prior dossier, bootstrap proposal and handoff source/tests/docs. Pins attest repository bytes, not inaccessible exchange documents.
- V1 `six-gates-production-v1 / v1` remains `ACTIVE`. Execution Gate V2 remains `NOT_ACTIVE`. Research bootstrap remains `UNAPPROVED / NOT_REGISTERED / NOT_ACTIVE`; seed `UNSET`; all effective parameters remain null.

## Recovery evidence and access limits

Research date: 2026-09-15. This date is **not** a reconstructed historical HSI observation timestamp. Evidence IDs below resolve to complete per-source chronology, findings and access details in JSON. A null publication time means unknown precision, not midnight; null supersession/effective end means not established, not perpetual validity.

| ID | Official source | Recovery | Result and limitation |
| --- | --- | --- | --- |
| S01 | [CMTR73845](https://nsearchives.nseindia.com/content/circulars/CMTR73845.pdf), referenced 2026-04-22 | BODY_UNAVAILABLE | Security-master reference only. No eligible list, CAS field/code, update mechanism or row identity inferred. |
| S02 | [CMTR74466](https://nsearchives.nseindia.com/content/circulars/CMTR74466.pdf), referenced 2026-05-29 | BODY_UNAVAILABLE | Modalities reference only; no amendment/effective-membership claim. |
| S03 | [CMTR67774 section 3.4](https://nsearchives.nseindia.com/content/circulars/CMTR67774.pdf), referenced 2025-04-30 | BODY_UNAVAILABLE | Non-CAS cash close algorithm, no-trade and fallback clauses remain unavailable. |
| S04 | [CMTR73362 SOP](https://nsearchives.nseindia.com/content/circulars/CMTR73362.pdf), 2026-03-18 | PRIMARY_TEXT_READ | CAS reference/equilibrium/no-match branches and non-CAS cross-reference reverified; not a dated membership payload. |
| S05 | [CMTR75479 live/mock notice](https://nsearchives.nseindia.com/content/circulars/CMTR75479.pdf), 2026-07-30 | PRIMARY_TEXT_READ | Live 2026-08-03 versus mock 2026-08-01; member-master location and filename reference recovered. |
| S06 | [NSE CAS page](https://www.nseindia.com/static/products-services/closing-auction-session), updated 2026-08-12 | PRIMARY_TEXT_READ | Current ordinary phase schedule, not historical per-security applicability. |
| S07 | [NSE FAQ catalogue](https://www.nseindia.com/static/trade/continuous-markets-FAQs), updated 2026-09-04 | LANDING_ONLY | CAS FAQ listed; attachment body not recovered. |
| S08 | [NSE reports catalogue](https://www.nseindia.com/all-reports) | PRIMARY_TEXT_READ | MII and final UDiFF products listed; no CAS completeness/schema/retention guarantee. |
| S09 | [Public MII candidate](https://nsearchives.nseindia.com/content/cm/NSE_CM_security_31072026.csv.gz) | BODY_UNAVAILABLE | URL follows existing HSI convention and S05 filename; public/extranet equivalence not verified. |
| S10 | [SEBI January introduction](https://www.sebi.gov.in/legal/circulars/jan-2026/introduction-of-closing-auction-session-cas-in-the-equity-cash-segment-and-certain-modifications-in-the-pre-open-auction-session_99122.html) | LANDING_ONLY | Final circular landing dated 2026-01-16; linked body unavailable. |
| S11 | [SEBI September consultation](https://www.sebi.gov.in/reports-and-statistics/reports/sep-2026/consultation-paper-on-review-of-certain-aspects-of-the-closing-auction-session-market-timings-and-settlement-methodologies-for-derivative-contracts-_104464.html) | LANDING_ONLY | 2026-09-12 public-comment notice is not an effective rule or supersession proof. |
| S12 | [NSE snapshot specification v1.21](https://nsearchives.nseindia.com/web/sites/default/files/inline-files/Snapshot_MDR_RT_CM_v1.21.pdf), 2024-08-28 | PRIMARY_TEXT_READ, relevant sections | Legacy close/LTP/indicative fields and generic security identity help separate concepts; not 2026 CAS compatibility. |

Each of S01-S03 was attempted through `nsearchives.nseindia.com`, `archives.nseindia.com`, and `www.nseindia.com` circular routes. The web reader returned safe-open/internal errors, not an exchange HTTP status. A bounded host GET failed with `ConnectionError` in the sandbox; one authorized network GET per circular then ended in `ReadTimeout` after 25 seconds. Connect/read bounds were 10/25 seconds with an approximately 12 MB response cap, TLS verification retained and no concurrent downloads or further retries. No response body/hash was recovered. S09 returned a web-tool internal error. SEBI linked bodies also failed safe-open retrieval.

These failures do **not** prove 403/404, document deletion or lack of entitlement. Searches for exact IDs, lists, flags, master extensions, revisions and FAQ attachments found references but no complete security-level payload. Derivative/index closing formulas were excluded as wrong-product substitutes for S03. No proxy/TLS/security bypass, credential use or broker API access occurred.

PDF text was inspected; attempted screenshot output contained only citation text, not visible page images. No visual-layout verification is claimed. Raw files were not retained. Each `evidence_fingerprint` seals the audit summary and provenance, **not raw source bytes**; all raw-response fingerprints and native historical HSI known-at values are null.

## Membership, chronology and identity

**Official membership source: `SOURCE_NOT_READY`. Recovered security rows: zero (audit scope only, not a production coverage count).** The broad phase-one derivative-eligible-stock description cannot establish a dated CAS list. Static, periodic, event-driven, rule-derived and snapshot update mechanisms remain unresolved. The master name `NSE_CM_security_31072026.csv.gz` is not a verified CAS schema or effective-date assertion.

S05 distinguishes the July 31 filename label, announced availability by August 1 at 06:00 IST, August 1 mock, and August 3 live start. An availability deadline does not prove an actual receipt or public-mirror publication. Publication date, exact publication timestamp, observation/known-at, effective interval, revision timestamp and supersession must remain separate.

The JSON `chronology.required_fields` is an **evidence checklist, not a new schema**: exact canonical identity; NSE security ID/token; ISIN; symbol/series/segment; official document, URL and schema version; raw fingerprint; source publication precision; observed/known-at; native effectivity and applicability interval; revision reference; completeness; original membership code and verified meaning; live/mock regime. Unknown ends cannot be interpreted as indefinite. Native interval inclusivity must be recovered, not invented here.

| Join | Generic HSI support | CAS conclusion |
| --- | --- | --- |
| ISIN + exact dated security identity | Existing MII and historical identity primitives | DERIVABLE after genuine membership rows and chronology exist |
| NSE ID/token + segment/series/lifecycle | Existing identity fields; conflicts fail closed | Requires source-specific versioned mapping; tokens are not globally eternal identities |
| Symbol | Supporting alias only | No ambiguous symbol-only match or present-symbol backcast |
| Whole CAS join | Reusable primitives, no CAS field interpretation | **IDENTITY_JOIN_SOURCE_GAP** |

Hashing an unrecognized raw MII column is not interpreting it. Missing rows in a partial list do not establish non-CAS; even a complete list needs approved complement semantics or explicit negative evidence. Entry, exit and category change require dated official change evidence. Suspension/delisting does not itself prove membership removal. Corporate actions, mergers/demergers and relisting need independent lifecycle/action lineage; no inferred continuity or price adjustment is introduced.

## Close formation, phases and machine fields

S04 sections 2 and 5 distinguish equilibrium close from reference-based close. No-match does not imply no regular trade. No-equilibrium/no-day-trade and corporate-action reference clauses must stay separate; use the actual official published record and its provenance, not a locally reconstructed fallback. An official value may exist without a new matched trade. It is not automatically executable or a research fill.

Non-CAS ordinary timing is known from S06, but its closing calculation remains **SOURCE_NOT_READY** because S03 section 3.4 was not recovered. No remembered half-hour formula or derivative settlement fallback is admitted. Source formation rules do not choose HSI start/terminal prices.

The exact ordinary IST phases are retained in JSON `phases.schedule`. Regular CAS trading ends at 15:15; entry has a random closing interval; matching follows entry closure. A nominal phase boundary is not a guaranteed final-close publication timestamp. No machine publication SLA was recovered.

| Required distinction | Exact recovered field / source | Readiness |
| --- | --- | --- |
| Exchange daily close versus last trade | HSI UDiFF `ClsPric` versus raw `LastPric`; previous `PrvsClsgPric` | Source lineage exists; CAS close-kind enrichment and research policy missing |
| Legacy official/indicative close | S12 `Closing Price` / `Previous Close Price`; MarketInfo separates `Close Price`, `Interval Close Price`, `Indicative Close Price` and LTP | LEGACY_SCHEMA_ONLY |
| Final auction price / matched quantity | SOP concepts, not a recovered current output dictionary | SOURCE_NOT_READY; indicative quantity is not final matched quantity |
| Match status / no-match / reference flag | No verified current transport fields | SOURCE_NOT_READY; missing feed is not a no-match flag |
| CAS membership flag/code | S01/S09 bodies absent | SOURCE_NOT_READY; no column name invented |

S12 describes a credential/agreement-based data product. Its generic security updates and pre-CAS auction files cannot be re-labelled CAS membership or output. No account/access configuration or download from that service was attempted. A future current schema may be public or agreement-controlled; no purchase requirement is presumed.

## Repository metadata reconciliation

All 16 exact inspected modules, versions/roles and file fingerprints are in JSON `internal_sources`. No adapter or service was invoked.

| Existing contract | Audit result | Boundary |
| --- | --- | --- |
| MII capture / session identity / identity selector | Reusable complete prospective capture, exact mapping and PIT primitives; historical receipt limitations retained | No new source of truth or CAS ingestion |
| Source-injected calendar / ordinary and special notices | Generic timing and bounded special-day evidence | Does not establish per-security CAS applicability |
| NSE UDiFF and legacy full bhavcopy | Different native close fields retained; logical daily interval is not publication time | **PRICE_SOURCE_POLICY_REQUIRED** |
| UDiFF `EXCHANGE_EOD_TRADE_PRICE` warning | Cannot certify a new executed trade for every source close | Warning/parser unchanged; no semantics silently promoted |
| Upstox daily candles | Provider close, UNKNOWN adjustment, interval-start/daily-end-unbound warning | No homogeneous official CAS close claim |
| Dhan REST/live | LTP, last-trade/receipt semantics, not verified final CAS match/reference fields | No live call or per-tick persistence |
| Dhan minute binder and 15m aggregator/reader | One regular-continuous phase, exact minute receipts, missing distinct from no-trade | **REGULAR_ONLY_NOT_CAS_VERIFIED** |
| Daily temporal and adjustment integrity | Native known-at/completion and action-specific lineage | No fabricated publication or generalized corporate-action adjustment |

A generic 15:15-15:30 aggregation would overlap CAS for a CAS security, not prove its last regular bar or official auction close. No exact final bar is selected, no no-match reference value is synthesized and no derivation is patched.

## Prospective, historical and exceptional coverage

| Domain | State | Missing evidence / rule |
| --- | --- | --- |
| Future prospective capture | **PROSPECTIVE_CAS_SOURCE_BLOCKED** | Current membership schema, complete payload, revisions/effectivity, close-kind transport and security/session binding |
| Since 2026-08-03 | **HISTORICAL_CAS_SOURCE_GAP** | Dated initial/revision files, retention evidence, publication/actual known-at and exact identity history |
| Muhurat / special live / truncated sessions | SOURCE_NOT_READY for CAS | Exact dated live notice plus CAS security applicability; no regular-time default |
| DR sessions | LIVE_VS_MOCK_MUST_BE_PROVEN | DR is not inherently mock; August 1 mock cannot mature research |
| Suspension / no orders / no regular trade / no match | SOURCE_NOT_READY for per-security observation | Preserve separate tradability, official close-kind and actual record; no invented price |
| Split/bonus / symbol change / merger/demerger / relisting | Exact lifecycle/action evidence required | Existing Historical Integrity primitives reused conceptually, not blanket adjustment or CAS membership proof |

Complete historical reconstruction is not a prerequisite for a separately approved future prospective start, but the present source/schema gaps still prevent readiness. A later download does not make a historical record known at D. Revisions visible later must not rewrite D. Unknown publication precision stays explicit; native date-only visibility guards are reused, not replaced.

## Fact authority and conflicts

Membership facts require verified dated NSE membership evidence. Effective NSE cash rules under the SEBI framework govern exchange close formation. A current output dictionary/payload must identify an official published close. Provider fields describe provider observations only; canonical HSI bars retain lineage rather than creating exchange-rule authority.

This is **SOURCE_PRECEDENCE_POLICY_REQUIRED**, not a selected price hierarchy. No source is preferred for a research fill, and values are not averaged, carried forward, aligned to a nearest bar or overwritten. Different close/LTP values may describe different facts rather than corrupt data. Conflicting membership versions remain fail-closed until exact scope, effective time and D-visible supersession are verified. No material primary-source contradiction was established by this audit; unread bodies and a later consultation are not themselves contradictions.

## Parameter impact and decision

| Parameter | Incremental source impact | Approval |
| --- | --- | --- |
| Duration unit | UNCHANGED | None |
| Session counting | UNCHANGED; global launch/mock fact reverified, security regime gap persists | None |
| Start price | UNCHANGED | None |
| Terminal boundary | UNCHANGED; schedule is not final-publication authority | None |
| Terminal price | BLOCKER_NARROWED; legacy distinct fields found, current CAS discriminator absent | None |
| Prospective calendar authority | UNCHANGED | None |
| Instrument eligibility | UNCHANGED; core membership still missing | None |

No predecessor blocker is fully closed. Close-field distinctions and a master-location reference narrow source questions, but three primary bodies, actual membership/revisions, current close-kind fields, special-session binding and historical known-at remain missing. Horizon, economic price, population and source-authority approvals remain separate. No cohorts, calibration or scenario bootstrap start.

Decision **C** is stronger than a generic partial-progress label: core security-level applicability is still unavailable. A future source recovery could enable bounded prospective policy work, but cannot alone activate it.

## Validation and one frozen continuation

[Conformance tests](../../tests/unit/test_nse_cas_security_membership_and_close_source_recovery.py) verify native fingerprints and all pinned files, exact recovery/readiness states, chronology/identity/close-kind safety, 28 scope requirements, authority invariants, tamper rejection and no runtime changes. Existing necessary-evidence witnesses and calendar/identity/bar regressions exercise the native rejection boundaries; they are not live membership proof. Full backend is required only if runtime/shared behavior changes; this documentation/test slice makes none. Final executed counts are reported in the commit checkpoint, not claimed in advance.

Exactly one next frozen continuation:

`NSE_CAS_PRIMARY_SOURCE_ACCESS_AND_DATED_MEMBERSHIP_EVIDENCE_RECOVERY_V1`

Recover the exact three official bodies/attachments, a complete dated master and documented revision sample via authorized official access or user-supplied original files. Check schema, scope, effective chronology, source bytes and observation provenance before proposing capture. Do not request credentials, repeat blind retries, register authority or change runtime. **Not started.**
