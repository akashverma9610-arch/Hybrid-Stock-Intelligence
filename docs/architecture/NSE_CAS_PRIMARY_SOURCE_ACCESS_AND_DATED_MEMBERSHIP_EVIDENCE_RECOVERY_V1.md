# NSE CAS Primary Source Access and Dated Membership Evidence Recovery V1

Status: `EVIDENCE_DOSSIER / EXTERNAL_INPUT_REQUIRED / NOT_ACTIVE`

Slice: `NSE_CAS_PRIMARY_SOURCE_ACCESS_AND_DATED_MEMBERSHIP_EVIDENCE_RECOVERY_V1`

**Decision C - `EXTERNAL_PRIMARY_SOURCE_INPUT_REQUIRED`. Slice status: `BLOCKED`.**

The bounded access investigation is complete; the evidence-dependent objective is not. Commit this truthful dossier after conformance validation, without treating document completion as source recovery or authority activation. Stop further network escalation. No CAS ingestion or runtime implementation is authorized here.

## Baseline, artifact and preservation

- Authoritative repository `D:\nse-stock-manager`, branch `main`; clean starting commit `cb3d57894f6e67ac7873afc7ea037da1d39b5707`.
- Dossier `nse-cas-primary-source-access-and-dated-membership-evidence-recovery / v1`.
- [Machine-readable dossier](NSE_CAS_PRIMARY_SOURCE_ACCESS_AND_DATED_MEMBERSHIP_EVIDENCE_RECOVERY_V1.json), fingerprint `sha256:be5c917b1bd03ae629713121349ff909dcaff93dd6addf8f2a3abd3a2b462c06`.
- [Predecessor CAS recovery](NSE_CAS_SECURITY_MEMBERSHIP_AND_CLOSE_SOURCE_RECOVERY_V1.md), fingerprint `sha256:b2fd0ba83dda8898065a43181837c675b2f46c6b27e3eb7404b68efa472b5d26`, remains unchanged.
- [Discovery-to-Brain handoff](CANONICAL_DISCOVERY_UNION_TO_BRAIN_HANDOFF_CONTRACT_V1.md), fingerprint `sha256:731399dfbca758763dda0ad9ee1350aa50cd433ab183bb62fc710e4b5826b1e8`, remains unchanged.
- Thirteen native predecessor fingerprints are retained. The accepted 204-file source-pin map is referenced, not duplicated; three predecessor-file pins bring this validation scope to 207. No historical artifact is edited.
- V1 six-gate policy stays **ACTIVE**; Execution Gate V2 stays **NOT_ACTIVE**. Research bootstrap stays **UNAPPROVED / NOT_REGISTERED / NOT_ACTIVE**, seed **UNSET**, all effective parameters null.

## 1. Exact primary-body recovery state

| Source | Reference provenance | Body/access state | Still unanswered |
| --- | --- | --- | --- |
| [CMTR73845](https://nsearchives.nseindia.com/content/circulars/CMTR73845.pdf) | Official CAS-page security-master modification title; 2026-04-22. Exact title is in JSON P01. | `OFFICIAL_REFERENCE_ONLY` / `ACCESS_REQUIRES_EXTERNAL_INPUT` | Actual universe, dictionary/codes, identity/series keys, publication/revisions and effective applicability |
| [CMTR74466](https://nsearchives.nseindia.com/content/circulars/CMTR74466.pdf) | Official CAS-page trading-modalities title; 2026-05-29. Exact title is in JSON P02. | `OFFICIAL_REFERENCE_ONLY` / `ACCESS_REQUIRES_EXTERNAL_INPUT` | Changes, annexures, phases, effective dates, membership impact and supersession |
| [CMTR67774 section 3.4](https://nsearchives.nseindia.com/content/circulars/CMTR67774.pdf) | Accepted SOP cross-reference dated 2025-04-30; exact target title remains unavailable. | `OFFICIAL_REFERENCE_ONLY` / `ACCESS_REQUIRES_EXTERNAL_INPUT` | Correct cash-market close calculation, no-trade branches and effective scope |

No target body, annexure inventory, precise publication timestamp or raw-file hash was recovered. The reference date is not a body-verified effective date. No third-party summary, derivative settlement rule, index formula or broker convention substitutes for the missing cash-market clause.

## 2. Bounded official access ledger

Audit date: 2026-09-15, not historical known-at.

For each target, the current `nsearchives.nseindia.com`, archive `archives.nseindia.com`, and `www.nseindia.com` circular paths were checked. Web retrieval returned safe-open/internal errors, not exchange HTTP status. Exact-ID official searches, the [circular archive](https://www.nseindia.com/resources/exchange-communication-circulars), [CAS product page](https://www.nseindia.com/static/products-services/closing-auction-session) and [FAQ listing](https://www.nseindia.com/static/trade/continuous-markets-FAQs) supplied references, not original target bodies. The FAQ attachment URL/body was not exposed. A SEBI search's unrelated 2008 numeric match was rejected.

One authorized host GET per target was then attempted for the three PDFs, the dated master candidate and the CAS market-data page: **five requests, five ReadTimeout results, zero HTTP responses, zero recovered bodies**. Configuration: 8-second connect / 12-second read timeout, 16 MiB maximum body and a 25-second checked streaming budget; no retries, redirects or concurrent downloads. TLS verification and proxy configuration were preserved; implicit netrc authentication was suppressed. No credentials, broker API or security workaround was used.

The failures do not prove 403/404, deletion, permanent unavailability, licensing requirements or denial of entitlement. The exact tested routes/results are in JSON `access_attempts`. No further speculative endpoint construction, repeated retries or access escalation is authorized by this checkpoint.

## 3. Project-retained originals and limits

Only the D: project was searched; no old OneDrive repository or unrelated personal directory was accessed.

- Filename enumeration included ignored PDFs, CSV/XLS/XLSX, ZIP and GZ paths: 7,571 paths observed, largely test artifacts. It was not complete: two old pytest cache directories returned access-denied errors, recorded in JSON. No ACL was changed.
- Exact target-ID and dated-master filename searches found no matching originals in the accessible scope. A bounded text reference scan covered `data/official_sources`, `data/incoming`, `data/archive` and `reports/research`, with a 2 MB per-file limit.
- Synthetic pytest masters, sample files, index/sector constituents and unrelated financial/company evidence were not admitted as CAS evidence. A project data-bot ZIP was inspected by directory listing only: 63 entries, no target-named member, no extraction.
- One retained NSE quote HTML shell matched the CAS search. Its unchanged bytes match the existing receipt: SHA-256 `c1587f291187f64f8df944c732ee9a59840ae00788fddab6f97b21618e28700d`, 146,357 bytes. Receipt metadata and the separate interpretation hash are recorded in JSON L01.

L01 contains a CAS navigation link, not membership data. Its receipt time `2026-09-07T17:15:23.109423+00:00` is an HTML observation, **not** CAS known-at. Matching a saved receipt hash establishes byte consistency, not independent proof of issuer authenticity, completeness or historical applicability. No original or receipt was modified. The bounded search does not assert that originals cannot exist in inaccessible caches or elsewhere.

## 4. New display evidence, not a source feed

The retained link led to the official [CAS market-data display](https://www.nseindia.com/market-data/closing-auction-session). It shows reference/final price, final volume, indicative equilibrium and imbalance labels plus a CSV-download control. The retrieved table says **No Records**.

This is `PRIMARY_SOURCE_PARTIAL`: display labels were recovered, but no dated CSV, rows, API contract, exact machine headers, ISIN/series/segment keys, publication time, finality code or no-match encoding was recovered. Empty display output does not prove an empty complete universe. A final-volume label or zero value cannot by itself prove no-match. Indicative information is not an executed trade.

This narrows **terminal-price source discovery only**. It does not replace the predecessor's missing machine-field proof, select an economic price convention or authorize a provider change.

## 5. Membership, completeness and revision evidence

| Requirement | Current result |
| --- | --- |
| Official file | `NSE_CM_security_31072026.csv.gz` remains a referenced candidate at the existing HSI public URL convention; body and member/public equivalence unverified |
| Actual membership rows | None recovered or created |
| Completeness | `UNDETERMINED_NO_PAYLOAD`; no complete universe or verified empty snapshot |
| Dictionary/inclusion/exclusion | Unknown; no CAS column/code invented |
| Revision chain | No initial payload, additions/removals, replacement rule or dated continuity chain recovered |
| Identity join | **IDENTITY_SOURCE_BLOCKED**; existing exact HSI identity primitives remain generically derivable |
| Series/segment key | Unverified; no ambiguous symbol-only join, ISIN-only series collapse, ETF/SME/other-segment expansion |
| Prospective capture | **SOURCE_BLOCKED**, not merely an implementation gap |
| Historical reconstruction | **HISTORICAL_MEMBERSHIP_UNRECOVERABLE** within available inputs; start/end bounds both null, not a claim of permanent loss |

A complete snapshot, static initial list, additions-only file, removals-only file, delta, sample and eligibility rule are distinct evidence kinds. A delta requires its verified base and explicit revision semantics; it cannot masquerade as a complete snapshot. A rule description or current display is not dated membership. Absence from a partial source does not prove non-CAS.

The applicability evidence checklist requires exact identity, official membership artifact/completeness, native effective interval, known-at provenance, D-visible revision chain and original/interpretation fingerprints. No runtime `CAS_applicable` function or schema is implemented. Unknown interval boundaries remain unknown, not perpetual validity. Suspension, identity change or relisting cannot be interpreted as a CAS revision without primary evidence.

## 6. Chronology, close semantics and fact-specific transport

Publication date/time, actual availability/observation, effectivity, original decision D and revision time remain separate. Filename date and filesystem modification time establish neither publication nor known-at. Later capture/publication does not authorize an earlier D; no correction policy is invented. The accepted August 3 live start and August 1 mock distinction remains intact, without implying per-security membership.

The predecessor's SOP finding remains: a published calculated/reference close can exist without a new matched trade. No newly recovered current field identifies that branch. Missing feed data cannot establish no-trade/no-match, and published close does not automatically become a research fill. The non-CAS §3.4 algorithm remains unavailable.

| Fact | Source role | Remaining boundary |
| --- | --- | --- |
| Membership and revisions | Exact official NSE dated master/list/dictionary | Originals missing |
| Exchange close formation | Effective NSE/SEBI primary rule text | Requested body gaps; no research-price authority |
| Actual final close/match kind | Current official output dictionary and original dated payload | Display labels only, no transport verification |
| Daily/intraday observations | Existing provider/source-specific HSI contracts | No homogeneous close, auction-finality or CAS bar assumption |
| Canonical stored evidence | Existing immutable HSI lineage | Not independent exchange-rule authority |

No universal source authority, averaging, carry-forward or nearest-bar fallback is selected. Conflicting official records must retain both originals and exact chronology; only explicit applicable supersession may resolve them, otherwise `SOURCE_CONFLICT`. No material primary conflict was established by this slice. Missing bodies and different field concepts are not manufactured contradictions.

## 7. One external-input requirement set

State: **EXTERNAL_PRIMARY_SOURCE_INPUT_REQUIRED**. Supply unchanged originals, not copied summaries or re-saved tables:

| ID | Required original | Acceptable form |
| --- | --- | --- |
| E01 | CMTR73845 and all referenced annexures/schema attachments | Original PDF and issued attachments |
| E02 | CMTR74466 and its changes/annexures | Original PDF and attachments |
| E03 | CMTR67774, including section 3.4 and relevant annexures | Complete original PDF |
| E04 | Complete dated CAS-bearing master/list and its exact versioned dictionary; July 31 filename is a candidate, not a promised CAS schema | Issued CSV/XLS/XLSX or untouched GZ/ZIP |
| E05 | Dated revisions/removals and notices linking the base through a stated bounded end date, or documented complete-replacement mechanism | Original notices and issued data files |
| E06 | Current CAS close/dissemination dictionary and original dated output, identifying final/reference/match distinctions where published | Original specification and exchange output; no invented flag required |

Minimum metadata: official issuer and original public URL/member-channel reference; original filename; document/schema identity; publication/availability evidence with real precision; effective dates and supersession; complete/delta scope and series/segment; actual receipt/download time or explicit unknown; authority to share the originals. **Do not send credentials, cookies or tokens.** No paid-access purchase or account setup is presumed.

Admission must hash unchanged raw bytes and preserve size/type/source first. Archive and extracted-member hashes remain distinct. A separately fingerprinted interpretation must bind those hashes and exact sections/columns. Verify provenance, completeness, native effectivity, D-visible revisions and identity before any recovered classification. A hash alone proves none of those semantics. Later originals must not backdate known-at. No placeholder or synthetic source file is created here.

## 8. Impact, validation and frozen continuation

No predecessor source blocker was closed. Official display labels narrow terminal-price transport discovery; **duration unit, session counting, start-price source, terminal boundary, prospective calendar and instrument eligibility are UNCHANGED**. Every parameter remains unapproved. Bootstrap remains blocked even before its separate parameter package, independent rationale, human approval, genuine decision origin and selected-parcel prerequisites.

[Conformance tests](../../tests/unit/test_nse_cas_primary_source_access_and_dated_membership_evidence_recovery.py) cover the requested preservation, provenance, completeness, chronology, scope, fingerprint, external-input and no-side-effect invariants. Relevant existing regressions exercise native identity/calendar and predecessor rejection behavior. Full backend is required only if shared/runtime behavior changes; this dossier/test-only slice changes none. Executed validation counts belong in the final checkpoint, not an advance success claim.

Exactly one next frozen continuation:

`NSE_CAS_USER_SUPPLIED_PRIMARY_EVIDENCE_ADMISSION_V1`

Precondition: the user supplies the original official bundle with provenance or identifies an explicitly authorized available primary-source access path. Then perform bounded evidence admission only. **Not started.** No automatic new recovery loop, ingestion, cohort, calibration, Brain binding, source registration or bootstrap activation.
