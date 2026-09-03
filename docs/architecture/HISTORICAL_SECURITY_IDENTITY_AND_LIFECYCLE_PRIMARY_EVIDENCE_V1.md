# Historical Security Identity and Lifecycle Primary Evidence V1

**Status: `IMPLEMENTED_BOUNDED_INGESTION / PRIMARY_SOURCE_ONLY / NOT_ACTIVE / NON_EXECUTABLE`.**

## Purpose

This bounded foundation answers only a factual PIT question:

> At time T, what exact approved-source listed-security identity was known and
> effective, under what symbol and ISIN, and was it listed and active?

It does not create a historical universe, classify company type, construct a
Compounder panel, calculate returns, stitch securities, evaluate candidates,
or change a portfolio or execution boundary.

## Reused canonical identity levels

`HistoricalSecurityIdentity` remains the sole immutable listed-security
receipt. It preserves canonical instrument/security identity, exchange,
symbol, ISIN, series, listed/tradable intervals, effective symbol interval,
lifecycle status, primary source, source reference, observation/known time
(`as_of`), and version. It must not be read as a legal-company identity.

Company/legal entity, listed security, ISIN, exchange symbol, and exchange
listing therefore remain distinct. A successor, predecessor, merger,
amalgamation, ISIN change, or rename relationship is recorded only when an
approved primary source expressly supplies it; none is inferred by the new
selector.

## PIT selection rule

`resolve_historical_security_identity` is a pure read-only selector over
already immutable identity receipts. For a requested exact canonical
instrument and aware historical as-of it:

1. excludes receipts not known by the as-of (`identity.as_of > as_of`);
2. selects only symbol records whose effective interval contains the as-of;
3. rejects overlapping records with different semantic identity as
   `EVIDENCE_CONFLICTED`;
4. checks explicit listed and tradable intervals; and
5. requires explicit `ACTIVE` or `RELISTED` lifecycle status for an eligible listed result.

An announcement known before a later effective symbol change remains known but
does not replace the old symbol before its effective timestamp. A missing
identity, future-known identity, non-effective identity, interval exclusion,
or non-active status is explicit and cannot trigger current-symbol
substitution. Missing bars never imply delisting.

The result carries the selected identity's symbol, ISIN, source, source-known
time, effective interval, lifecycle status, and a deterministic fingerprint.
Unavailable/conflicted results carry no fabricated identity fields.

## Primary-source acquisition boundary

The repository already permits only append-only local-file identity ingestion
through `HistoricalSecurityMasterCsvImporter`. An acceptable source record
must at least provide `SYMBOL`, `EFFECTIVE_FROM`, `STATUS`, and `SOURCE`; the
recommended exact fields are canonical instrument ID, ISIN, exchange, series,
listed/tradable start and end, effective end, source version, and primary
source reference. Existing corporate-action ingestion remains separate.

`BSE_PRIMARY_SECURITY_LIFECYCLE_NOTICE_INGESTION_V1` provides a fixed,
allowlisted BSE acquisition boundary for individual `Notices & Circulars`
documents and the official compulsory-delisted-company document.  It accepts
only explicit event types: name/scrip-ID change, delisting/discontinuation,
merger/cessation, listing/relisting, suspension, and revocation of suspension.
It records source document identity, content fingerprint, BSE scrip code/ISIN
where supplied, the notice publication/known time, and the separately stated
effective time.  It has no crawler or generic URL input.

Every primary document is persisted as immutable lifecycle evidence even when
it cannot be linked.  An identity is created only after an exact BSE scrip-code
or ISIN link to one canonical security.  If both identifiers are supplied,
both must agree.  Company names are retained descriptively in the evidence but
are never linkage keys.  The current BSE master can provide an exact link only;
it can never establish historical listing or effective dates.

The compulsory-delisted PDF is acquired only from BSE's fixed official path.
It has a text-layer, seven-column table and is extracted with the existing
optional `pdfplumber` convention—never OCR.  Each retained row preserves page
and ordinal, exact company text, ISIN when structurally present, lot size,
face value, demat indicator, exact delisting date, document observation time,
and a raw-row fingerprint.  Rows with unstable boundaries, malformed ISINs,
or malformed dates are rejected rather than repaired.

A compiled PDF can establish an exact endpoint but not the historical date on
which an old row was known.  Its observation time is therefore deliberately
separate from `historical_known_at`, which remains unavailable.  An exact ISIN
association may be recorded as evidence linkage, but it cannot become a
PIT-eligible `HistoricalSecurityIdentity` receipt without an approved
historical known/publication time.  No listing start is inferred.

Potential evidence must be an approved primary NSE/BSE/exchange artifact:
security master, listing/delisting record, exchange circular, symbol/ISIN
change, or merger/amalgamation effective-date record. Yahoo, Screener,
Moneycontrol, Wikipedia, web summaries, fuzzy company-name matching, and a
current provider master are not canonical historical lifecycle evidence.

## Current coverage diagnostic

The bounded ingestion mechanism is implemented and validated against
actual-style BSE notice content.  Production coverage is measured only after a
document acquisition run; no current master snapshot is counted as historical
lifecycle evidence.

The bounded first pass acquired three fixed BSE notices (two delistings and
one revocation of suspension) plus the fixed compulsory-delisted PDF.  The
three notices each had an exact BSE scrip code and distinct known/effective
times, but none supplied an exact stored ISIN/canonical-security link; they
are retained as immutable unresolved evidence.  The PDF extractor found 1,337
complete rows (991 structurally valid ISINs), rejected 108 malformed-ISIN rows,
and rejected no date rows.  Its date range is 2016-08-17 through 2026-06-16.
No current canonical instrument had an exact ISIN match in this local store.

| Measure | Current count | Meaning |
| --- | ---: | --- |
| `HISTORICAL_SECURITY_LIFECYCLE_EVIDENCE` receipts | 1,340 | Three BSE notices plus 1,337 exact compiled-PDF endpoint rows. |
| `HISTORICAL_SECURITY_IDENTITY` receipts | 0 | No historical listed-security identity can be resolved until exact linked primary evidence is acquired. |
| Deterministically extracted compulsory-delisted rows | 1,337 | Endpoint evidence only; no historical known time is claimed. |
| Distinct covered securities / ISINs | 0 / 0 | No lifecycle population exists. |
| Symbol-change lineages | 0 | No continuity may be inferred. |
| Known listing starts / ends | 0 / 0 | Listing intervals are unavailable. |
| Delisted, inactive, merged, or ceased securities | 0 | Absence is not evidence that none existed. |
| Conflicts | 0 stored | No source was imported; this is not clearance. |
| Current membership observations | 762 active, all effective/known 2026-08-30 | Current-style snapshot only, not historical membership. |

Survivorship reconstruction status: `NOT_READY`.

## Explicit blockers and next dependency

The remaining primary-source gap is coverage, not ingestion logic: a bounded
set of exact BSE notices and delisted-list rows must be acquired, staged, and
linked through exact historical/current mapping evidence.  NSE dated security
master availability remains discovery-only; the repository has no proven
historical NSE snapshots and does not import them in this slice.

After usable identity/lifecycle evidence exists, the next separate governed dependency is
`PIT_COMPANY_TYPE_CLASSIFICATION_RESEARCH_AND_CONTRACT_V1`; it must attach to
the stable canonical listed-security identity and must not be inferred from
sector/industry or names.
