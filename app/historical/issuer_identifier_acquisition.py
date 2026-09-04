"""Exact primary-source issuer-identifier acquisition.

This adapter deliberately accepts only already-structured exchange records or
the GLEIF/ANNA certified ISIN-to-LEI relationship file.  It turns neither a
company name nor a ticker into legal-entity evidence.  Source records remain
immutable, date-scoped receipts; the caller supplies the source observation
time and this module never reads the runtime clock or a provider master.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import UTC, date, datetime
from enum import StrEnum
import hashlib
from io import BytesIO, StringIO
import json
import re
from typing import Iterable, Mapping
from zipfile import BadZipFile, ZipFile

from app.historical.issuer_security_identity import (
    IssuerIdentifierType,
    IssuerSecurityBridge,
    IssuerSecurityBridgeSourceType,
    IssuerSecurityBridgeTemporalSemantics,
    create_issuer_security_bridge,
    resolve_issuer_security_bridge,
)
from app.historical.nse_session_identity import NseSessionPointIdentity
from app.storage.core_api_snapshot_repository import (
    CoreApiSnapshot,
    CoreApiSnapshotFamily,
    CoreApiSnapshotRepository,
)


CONTRACT_ID = "exact-issuer-identifier-primary-acquisition"
CONTRACT_VERSION = "v1"
# Transport is intentionally outside this module, but one supplied archive
# still needs a hard parser bound.  These are resource controls, not policy
# parameters and are kept independent of issuer-resolution semantics.
MAX_GLEIF_ISIN_LEI_ARCHIVE_BYTES = 64 * 1024 * 1024
MAX_GLEIF_ISIN_LEI_CSV_BYTES = 256 * 1024 * 1024
_ID = re.compile(r"[A-Za-z0-9._:-]+\Z")
_ISIN = re.compile(r"[A-Z]{2}[A-Z0-9]{9}[0-9]\Z")
_CIN = re.compile(r"[LU][0-9]{5}[A-Z]{2}[0-9]{4}[A-Z]{3}[0-9]{6}\Z")
_LEI = re.compile(r"[A-Z0-9]{20}\Z")
_FP = re.compile(r"sha256:[0-9a-f]{64}\Z")


class IssuerIdentifierEvidenceSource(StrEnum):
    """Source lineages retained independently; no precedence is implied."""

    NSE_STRUCTURED_FILING = "NSE_STRUCTURED_FILING"
    # The official NSE BRSR bulk archive is a distinct filing lineage.  Its
    # general-disclosure table may prove a CIN plus an exact NSE symbol without
    # asserting an ISIN or a timeless security relationship.
    NSE_BRSR_ARCHIVE = "NSE_BRSR_ARCHIVE"
    BSE_STRUCTURED_FILING = "BSE_STRUCTURED_FILING"
    GLEIF_ANNA_ISIN_LEI = "GLEIF_ANNA_ISIN_LEI"


class IssuerIdentifierWriteOutcome(StrEnum):
    INSERTED = "INSERTED"
    ALREADY_PRESENT = "ALREADY_PRESENT"


class IssuerIdentifierAcquisitionError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class GleifLevel1Reference:
    """Exact Level-1 attributes for an already resolved LEI.

    Registration-authority values are retained only as source metadata.  A
    value is never recast as a CIN merely because it resembles one.
    """

    lei: str
    legal_name: str | None
    registration_authority_id: str | None
    registration_authority_entity_id: str | None
    source_reference: str
    source_as_of_date: date
    source_fingerprint: str

    def __post_init__(self) -> None:
        if not (
            _LEI.fullmatch(self.lei) and _nonblank(self.source_reference)
            and _date(self.source_as_of_date) and _fingerprint(self.source_fingerprint)
            and (self.legal_name is None or _nonblank(self.legal_name))
            and ((self.registration_authority_id is None) == (self.registration_authority_entity_id is None))
            and (self.registration_authority_id is None or _nonblank(self.registration_authority_id))
            and (self.registration_authority_entity_id is None or _nonblank(self.registration_authority_entity_id))
        ):
            raise IssuerIdentifierAcquisitionError("GLEIF_LEVEL1_REFERENCE_INVALID")


@dataclass(frozen=True, slots=True)
class ExactIssuerIdentifierEvidence:
    """One structured, immutable ISIN-to-stable-identifier source receipt."""

    evidence_id: str
    source: IssuerIdentifierEvidenceSource
    source_record_id: str
    source_document_fingerprint: str
    source_record_fingerprint: str
    source_reference: str
    source_as_of_date: date
    source_observed_at: datetime
    historical_known_at: datetime | None
    isin: str | None
    nse_symbol: str | None
    bse_scrip_code: str | None
    issuer_identifier_type: IssuerIdentifierType
    issuer_identifier_value: str
    issuer_legal_name: str | None
    registration_authority_id: str | None
    registration_authority_entity_id: str | None
    fingerprint: str
    contract_id: str = CONTRACT_ID
    contract_version: str = CONTRACT_VERSION

    def __post_init__(self) -> None:
        if not _evidence_valid(self) or self.fingerprint != _hash(_evidence_payload(self)):
            raise IssuerIdentifierAcquisitionError("EXACT_ISSUER_IDENTIFIER_EVIDENCE_INVALID")

    def verify(self) -> None:
        self.__post_init__()


@dataclass(frozen=True, slots=True)
class IssuerIdentifierAcquisitionReceipt:
    """Deterministic receipt for one bounded supplied evidence batch."""

    receipt_id: str
    source: IssuerIdentifierEvidenceSource
    source_document_fingerprint: str
    source_as_of_date: date
    session_date: date
    evidence_inserted: int
    evidence_already_present: int
    bridge_inserted: int
    bridge_already_present: int
    exact_isin_candidates: int
    symbol_conflicts: int
    fingerprint: str
    contract_id: str = CONTRACT_ID
    contract_version: str = CONTRACT_VERSION

    def __post_init__(self) -> None:
        values = (
            self.evidence_inserted, self.evidence_already_present, self.bridge_inserted,
            self.bridge_already_present, self.exact_isin_candidates, self.symbol_conflicts,
        )
        if not (
            _identifier(self.receipt_id) and isinstance(self.source, IssuerIdentifierEvidenceSource)
            and _fingerprint(self.source_document_fingerprint) and _date(self.source_as_of_date)
            and _date(self.session_date) and min(values) >= 0
            and self.contract_id == CONTRACT_ID and self.contract_version == CONTRACT_VERSION
            and self.fingerprint == _hash(_receipt_payload(self))
        ):
            raise IssuerIdentifierAcquisitionError("EXACT_ISSUER_IDENTIFIER_ACQUISITION_RECEIPT_INVALID")


@dataclass(frozen=True, slots=True)
class IssuerIdentifierTargetAudit:
    """Read-only exact-security audit; it never classifies a company."""

    symbol: str
    session_date: date
    session_security_receipt_id: str | None
    isin: str | None
    bridge_available: bool
    cin: str | None
    lei: str | None
    sources: tuple[IssuerIdentifierEvidenceSource, ...]
    source_dates: tuple[date, ...]
    unresolved_reason: str | None

    def __post_init__(self) -> None:
        if not (
            _nonblank(self.symbol) and _date(self.session_date)
            and ((self.session_security_receipt_id is None) == (self.isin is None))
            and self.sources == tuple(sorted(set(self.sources), key=lambda item: item.value))
            and self.source_dates == tuple(sorted(set(self.source_dates)))
            and all(isinstance(item, IssuerIdentifierEvidenceSource) for item in self.sources)
            and (self.cin is None or _CIN.fullmatch(self.cin) is not None)
            and (self.lei is None or _LEI.fullmatch(self.lei) is not None)
            and (self.bridge_available or (self.cin is None and self.lei is None and not self.sources and not self.source_dates))
            and ((self.unresolved_reason is None) is self.bridge_available)
        ):
            raise IssuerIdentifierAcquisitionError("ISSUER_IDENTIFIER_TARGET_AUDIT_INVALID")


class IssuerIdentifierEvidenceStore:
    """Append-only evidence and bridge receipts in the existing snapshot store."""

    def __init__(self, repository: CoreApiSnapshotRepository) -> None:
        self._repository = repository

    def save_evidence(self, value: ExactIssuerIdentifierEvidence) -> IssuerIdentifierWriteOutcome:
        return self._save(
            family=CoreApiSnapshotFamily.HISTORICAL_ISSUER_IDENTIFIER_EVIDENCE,
            snapshot_id=value.evidence_id, record_type="exact-issuer-identifier-evidence-v1",
            value=value, created_at=value.source_observed_at,
        )

    def save_bridge(self, value: IssuerSecurityBridge) -> IssuerIdentifierWriteOutcome:
        return self._save(
            family=CoreApiSnapshotFamily.HISTORICAL_ISSUER_SECURITY_BRIDGE,
            snapshot_id=value.bridge_id, record_type="issuer-security-bridge-v1",
            value=value, created_at=value.source_observed_at,
        )

    def save_receipt(self, value: IssuerIdentifierAcquisitionReceipt, *, observed_at: datetime) -> IssuerIdentifierWriteOutcome:
        if not _aware(observed_at):
            raise IssuerIdentifierAcquisitionError("ISSUER_IDENTIFIER_ACQUISITION_OBSERVATION_TIMESTAMP_REQUIRED")
        return self._save(
            family=CoreApiSnapshotFamily.HISTORICAL_ISSUER_IDENTIFIER_EVIDENCE,
            snapshot_id=value.receipt_id, record_type="exact-issuer-identifier-acquisition-receipt-v1",
            value=value, created_at=_utc(observed_at),
        )

    def evidence(self) -> tuple[ExactIssuerIdentifierEvidence, ...]:
        return tuple(sorted(
            (item.payload for item in self._all(CoreApiSnapshotFamily.HISTORICAL_ISSUER_IDENTIFIER_EVIDENCE)
             if isinstance(item.payload, ExactIssuerIdentifierEvidence)),
            key=lambda item: (item.source_as_of_date, item.source.value, item.evidence_id),
        ))

    def bridges(self) -> tuple[IssuerSecurityBridge, ...]:
        return tuple(sorted(
            (item.payload for item in self._all(CoreApiSnapshotFamily.HISTORICAL_ISSUER_SECURITY_BRIDGE)
             if isinstance(item.payload, IssuerSecurityBridge)),
            key=lambda item: (item.session_date, item.bridge_id),
        ))

    def _save(self, *, family: CoreApiSnapshotFamily, snapshot_id: str, record_type: str, value: object, created_at: datetime) -> IssuerIdentifierWriteOutcome:
        existing = self._repository.get_snapshot(snapshot_id)
        if existing is not None:
            if existing.family is family and existing.payload == value:
                return IssuerIdentifierWriteOutcome.ALREADY_PRESENT
            raise IssuerIdentifierAcquisitionError("ISSUER_IDENTIFIER_IMMUTABLE_COLLISION")
        self._repository.save_snapshot(CoreApiSnapshot(
            snapshot_id, family, "v1", record_type, getattr(value, "fingerprint"), created_at, value,
        ))
        return IssuerIdentifierWriteOutcome.INSERTED

    def _all(self, family: CoreApiSnapshotFamily) -> tuple[CoreApiSnapshot, ...]:
        values: list[CoreApiSnapshot] = []
        offset = 0
        while True:
            page = self._repository.list_snapshots(family, limit=100, offset=offset)
            values.extend(page)
            if len(page) < 100:
                return tuple(values)
            offset += len(page)


def evidence_from_structured_row(
    *, source: IssuerIdentifierEvidenceSource, source_document: bytes | None = None,
    source_document_fingerprint: str | None = None,
    source_reference: str, source_record_id: str, source_as_of_date: date,
    source_observed_at: datetime, isin: str | None, issuer_identifier_type: IssuerIdentifierType,
    issuer_identifier_value: str, nse_symbol: str | None = None,
    bse_scrip_code: str | None = None, issuer_legal_name: str | None = None,
    registration_authority_id: str | None = None,
    registration_authority_entity_id: str | None = None,
    historical_known_at: datetime | None = None,
) -> ExactIssuerIdentifierEvidence:
    """Create source evidence only from fields already labelled by its source."""
    if not isinstance(source, IssuerIdentifierEvidenceSource):
        raise IssuerIdentifierAcquisitionError("ISSUER_IDENTIFIER_EVIDENCE_SOURCE_INVALID")
    if not _identifier(source_record_id) or not _date(source_as_of_date) or not _aware(source_observed_at):
        raise IssuerIdentifierAcquisitionError("ISSUER_IDENTIFIER_SOURCE_METADATA_INVALID")
    if historical_known_at is not None and (not _aware(historical_known_at) or _utc(historical_known_at).date() > source_as_of_date):
        raise IssuerIdentifierAcquisitionError("ISSUER_IDENTIFIER_FUTURE_KNOWN_TIME")
    if (source_document is None) == (source_document_fingerprint is None):
        raise IssuerIdentifierAcquisitionError("ISSUER_IDENTIFIER_SOURCE_DOCUMENT_LINEAGE_REQUIRED")
    if source_document is not None and not source_document:
        raise IssuerIdentifierAcquisitionError("ISSUER_IDENTIFIER_SOURCE_DOCUMENT_REQUIRED")
    if source_document_fingerprint is not None and not _fingerprint(source_document_fingerprint):
        raise IssuerIdentifierAcquisitionError("ISSUER_IDENTIFIER_SOURCE_DOCUMENT_FINGERPRINT_INVALID")
    # NSE BRSR General evidence is intentionally a CIN+NSE-symbol filing
    # observation.  The source-specific parser never claims an ISIN, so a
    # caller cannot accidentally repurpose this lineage into a bridge.
    if source is IssuerIdentifierEvidenceSource.NSE_BRSR_ARCHIVE and (
        isin is not None or nse_symbol is None or bse_scrip_code is not None
    ):
        raise IssuerIdentifierAcquisitionError("BRSR_FILING_SECURITY_LOCATOR_INVALID")
    document_fingerprint = source_document_fingerprint or _bytes_hash(source_document or b"")
    values = dict(
        source=source, source_record_id=source_record_id,
        source_document_fingerprint=document_fingerprint,
        source_reference=source_reference, source_as_of_date=source_as_of_date,
        source_observed_at=_utc(source_observed_at),
        historical_known_at=_utc(historical_known_at) if historical_known_at is not None else None,
        isin=isin, nse_symbol=nse_symbol, bse_scrip_code=bse_scrip_code,
        issuer_identifier_type=issuer_identifier_type,
        issuer_identifier_value=issuer_identifier_value,
        issuer_legal_name=issuer_legal_name,
        registration_authority_id=registration_authority_id,
        registration_authority_entity_id=registration_authority_entity_id,
    )
    values["source_record_fingerprint"] = _hash(_source_record_payload(values))
    identity = _evidence_identity(values)
    evidence_id = "issuer-identifier-evidence:" + _hash(identity)[7:39]
    return ExactIssuerIdentifierEvidence(
        evidence_id=evidence_id, **values,
        fingerprint=_hash(_evidence_payload_from_values(values | {"evidence_id": evidence_id})),
    )


def extract_nse_structured_identity_csv(
    *, payload: bytes, source_reference: str, source_observed_at: datetime,
) -> tuple[ExactIssuerIdentifierEvidence, ...]:
    """Read NSE's labelled structured CSV fields, not filing prose or names."""
    rows = _csv_rows(payload)
    required = {"SYMBOL", "ISIN", "CORPORATE IDENTITY NUMBER (CIN) OF THE LISTED ENTITY", "DATE OF SUBMISSION"}
    if not rows or not required.issubset(rows[0]):
        raise IssuerIdentifierAcquisitionError("NSE_STRUCTURED_IDENTITY_REQUIRED_FIELDS_MISSING")
    values: list[ExactIssuerIdentifierEvidence] = []
    for index, row in enumerate(rows, start=2):
        cin = row["CORPORATE IDENTITY NUMBER (CIN) OF THE LISTED ENTITY"]
        isin = row["ISIN"]
        if not (_CIN.fullmatch(cin) and _ISIN.fullmatch(isin)):
            continue
        values.append(evidence_from_structured_row(
            source=IssuerIdentifierEvidenceSource.NSE_STRUCTURED_FILING, source_document=payload,
            source_reference=source_reference, source_record_id="nse-structured-row:" + str(index),
            source_as_of_date=_parse_source_date(row["DATE OF SUBMISSION"]), source_observed_at=source_observed_at,
            isin=isin, nse_symbol=_optional(row.get("SYMBOL")),
            issuer_identifier_type=IssuerIdentifierType.CIN, issuer_identifier_value=cin,
            issuer_legal_name=_optional(row.get("COMPANY NAME")),
        ))
    return _canonical_evidence(values)


def extract_bse_structured_identity_rows(
    *, rows: Iterable[Mapping[str, str]], source_document: bytes, source_reference: str,
    source_observed_at: datetime,
) -> tuple[ExactIssuerIdentifierEvidence, ...]:
    """Read only a pre-parsed BSE labelled corporate-information block.

    The caller supplies a deterministic table/block parser.  This function
    refuses unlabeled prose and uses no company-name or symbol reconciliation.
    """
    values: list[ExactIssuerIdentifierEvidence] = []
    for index, original in enumerate(rows, start=1):
        row = {_header(key): (value or "").strip() for key, value in original.items()}
        required = {"SCRIP CODE", "ISIN", "CIN", "PUBLICATION DATE"}
        if not required.issubset(row):
            raise IssuerIdentifierAcquisitionError("BSE_STRUCTURED_IDENTITY_REQUIRED_FIELDS_MISSING")
        if not (_ISIN.fullmatch(row["ISIN"]) and _CIN.fullmatch(row["CIN"])):
            continue
        values.append(evidence_from_structured_row(
            source=IssuerIdentifierEvidenceSource.BSE_STRUCTURED_FILING, source_document=source_document,
            source_reference=source_reference, source_record_id="bse-structured-row:" + str(index),
            source_as_of_date=_parse_source_date(row["PUBLICATION DATE"]), source_observed_at=source_observed_at,
            isin=row["ISIN"], nse_symbol=_optional(row.get("NSE SYMBOL")), bse_scrip_code=row["SCRIP CODE"],
            issuer_identifier_type=IssuerIdentifierType.CIN, issuer_identifier_value=row["CIN"],
            issuer_legal_name=_optional(row.get("COMPANY NAME")),
        ))
    return _canonical_evidence(values)


def extract_gleif_isin_lei_zip(
    *, payload: bytes, source_reference: str, source_as_of_date: date, source_observed_at: datetime,
    allowed_isins: Iterable[str] | None = None,
) -> tuple[ExactIssuerIdentifierEvidence, ...]:
    """Extract only exact `ISIN`/`LEI` rows from one GLEIF/ANNA archive."""
    if not _date(source_as_of_date) or not _aware(source_observed_at):
        raise IssuerIdentifierAcquisitionError("GLEIF_ISIN_LEI_SOURCE_METADATA_INVALID")
    if not payload or len(payload) > MAX_GLEIF_ISIN_LEI_ARCHIVE_BYTES:
        raise IssuerIdentifierAcquisitionError("GLEIF_ISIN_LEI_ARCHIVE_SIZE_INVALID")
    try:
        with ZipFile(BytesIO(payload)) as archive:
            names = tuple(sorted(name for name in archive.namelist() if name.lower().endswith(".csv") and not name.endswith("/")))
            if len(names) != 1:
                raise IssuerIdentifierAcquisitionError("GLEIF_ISIN_LEI_ARCHIVE_CSV_AMBIGUOUS")
            info = archive.getinfo(names[0])
            if info.file_size > MAX_GLEIF_ISIN_LEI_CSV_BYTES:
                raise IssuerIdentifierAcquisitionError("GLEIF_ISIN_LEI_CSV_SIZE_INVALID")
            raw = archive.read(info)
    except (BadZipFile, OSError) as error:
        raise IssuerIdentifierAcquisitionError("GLEIF_ISIN_LEI_ARCHIVE_INVALID") from error
    rows = _csv_rows(raw)
    if not rows or not {"ISIN", "LEI"}.issubset(rows[0]):
        raise IssuerIdentifierAcquisitionError("GLEIF_ISIN_LEI_REQUIRED_FIELDS_MISSING")
    allowed = None if allowed_isins is None else frozenset(allowed_isins)
    if allowed is not None and any(_ISIN.fullmatch(value) is None for value in allowed):
        raise IssuerIdentifierAcquisitionError("GLEIF_ISIN_LEI_ALLOWED_ISIN_INVALID")
    values: list[ExactIssuerIdentifierEvidence] = []
    for index, row in enumerate(rows, start=2):
        isin, lei = row["ISIN"], row["LEI"]
        if _ISIN.fullmatch(isin) and _LEI.fullmatch(lei) and (allowed is None or isin in allowed):
            values.append(evidence_from_structured_row(
                source=IssuerIdentifierEvidenceSource.GLEIF_ANNA_ISIN_LEI, source_document=payload,
                source_reference=source_reference, source_record_id="gleif-isin-lei-row:" + str(index),
                source_as_of_date=source_as_of_date, source_observed_at=source_observed_at,
                isin=isin, issuer_identifier_type=IssuerIdentifierType.LEI, issuer_identifier_value=lei,
            ))
    return _canonical_evidence(values)


def gleif_level1_reference_from_payload(
    *, lei: str, payload: Mapping[str, object], source_reference: str, source_as_of_date: date,
) -> GleifLevel1Reference:
    """Preserve the exact structured Level-1 registration-authority fields."""
    if not _LEI.fullmatch(lei):
        raise IssuerIdentifierAcquisitionError("GLEIF_LEVEL1_LEI_INVALID")
    try:
        data = payload["data"]
        attributes = data["attributes"]  # type: ignore[index]
        entity = attributes["entity"]  # type: ignore[index]
        legal_name = entity.get("legalName", {}).get("name")  # type: ignore[union-attr]
        authority = entity.get("registrationAuthority") or {}  # type: ignore[union-attr]
        authority_id = authority.get("registrationAuthorityID")
        authority_entity_id = authority.get("registrationAuthorityEntityID")
    except (KeyError, TypeError, AttributeError) as error:
        raise IssuerIdentifierAcquisitionError("GLEIF_LEVEL1_STRUCTURED_FIELDS_MISSING") from error
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    return GleifLevel1Reference(
        lei=lei, legal_name=_optional(legal_name), registration_authority_id=_optional(authority_id),
        registration_authority_entity_id=_optional(authority_entity_id), source_reference=source_reference,
        source_as_of_date=source_as_of_date, source_fingerprint=_bytes_hash(raw),
    )


def acquire_exact_issuer_bridges(
    *, store: IssuerIdentifierEvidenceStore, session_securities: Iterable[NseSessionPointIdentity],
    evidence: Iterable[ExactIssuerIdentifierEvidence], source: IssuerIdentifierEvidenceSource,
    source_document_fingerprint: str, source_as_of_date: date, source_observed_at: datetime,
) -> IssuerIdentifierAcquisitionReceipt:
    """Persist one source batch and bind only its exact same-date ISIN rows.

    No source ordering resolves issuer disagreement: all exact bridge evidence
    is retained for the existing fail-closed bridge resolver.
    """
    if not _fingerprint(source_document_fingerprint) or not _date(source_as_of_date) or not _aware(source_observed_at):
        raise IssuerIdentifierAcquisitionError("ISSUER_IDENTIFIER_ACQUISITION_SOURCE_METADATA_INVALID")
    supplied = _canonical_evidence(evidence)
    if any(item.source is not source or item.source_document_fingerprint != source_document_fingerprint or item.source_as_of_date != source_as_of_date for item in supplied):
        raise IssuerIdentifierAcquisitionError("ISSUER_IDENTIFIER_ACQUISITION_SOURCE_LINEAGE_MISMATCH")
    sessions = _canonical_sessions(session_securities)
    e_inserted = e_present = b_inserted = b_present = candidates = symbol_conflicts = 0
    for item in supplied:
        outcome = store.save_evidence(item)
        e_inserted += outcome is IssuerIdentifierWriteOutcome.INSERTED
        e_present += outcome is IssuerIdentifierWriteOutcome.ALREADY_PRESENT
    by_isin: dict[str, list[ExactIssuerIdentifierEvidence]] = {}
    for item in supplied:
        if item.isin is not None:
            by_isin.setdefault(item.isin, []).append(item)
    for session in sessions:
        if session.session_date != source_as_of_date:
            continue
        for item in by_isin.get(session.isin, ()):
            candidates += 1
            if item.nse_symbol is not None and item.nse_symbol != session.symbol:
                symbol_conflicts += 1
                continue
            bridge = create_issuer_security_bridge(
                session_security=session, issuer_identifier_type=item.issuer_identifier_type,
                issuer_identifier_value=item.issuer_identifier_value, issuer_legal_name=item.issuer_legal_name,
                source_evidence_id=item.evidence_id, source_evidence_fingerprint=item.fingerprint,
                source_type=_bridge_source_type(item.source), source_reference=item.source_reference,
                source_as_of_date=item.source_as_of_date, source_observed_at=item.source_observed_at,
                historical_known_at=item.historical_known_at,
                temporal_semantics=IssuerSecurityBridgeTemporalSemantics.EXACT_SESSION_DATE,
            )
            outcome = store.save_bridge(bridge)
            b_inserted += outcome is IssuerIdentifierWriteOutcome.INSERTED
            b_present += outcome is IssuerIdentifierWriteOutcome.ALREADY_PRESENT
    values = dict(
        source=source, source_document_fingerprint=source_document_fingerprint,
        source_as_of_date=source_as_of_date, session_date=source_as_of_date,
        evidence_inserted=e_inserted, evidence_already_present=e_present,
        bridge_inserted=b_inserted, bridge_already_present=b_present,
        exact_isin_candidates=candidates, symbol_conflicts=symbol_conflicts,
    )
    receipt_id = "issuer-identifier-acquisition:" + _hash(_receipt_identity(values))[7:39]
    receipt = IssuerIdentifierAcquisitionReceipt(
        receipt_id=receipt_id, **values,
        fingerprint=_hash(_receipt_payload_from_values(values | {"receipt_id": receipt_id})),
    )
    store.save_receipt(receipt, observed_at=source_observed_at)
    return receipt


def audit_target_issuer_coverage(
    *, session_securities: Iterable[NseSessionPointIdentity], bridges: Iterable[IssuerSecurityBridge],
    evidence: Iterable[ExactIssuerIdentifierEvidence],
    targets: Iterable[str], session_date: date,
) -> tuple[IssuerIdentifierTargetAudit, ...]:
    """Audit named targets through the bridge resolver without name matching."""
    if not _date(session_date):
        raise IssuerIdentifierAcquisitionError("ISSUER_IDENTIFIER_TARGET_AUDIT_SESSION_DATE_INVALID")
    sessions = _canonical_sessions(session_securities)
    all_bridges = tuple(bridges)
    by_evidence_id = {item.evidence_id: item for item in _canonical_evidence(evidence)}
    results: list[IssuerIdentifierTargetAudit] = []
    for symbol in tuple(sorted(set(targets))):
        if not _nonblank(symbol):
            raise IssuerIdentifierAcquisitionError("ISSUER_IDENTIFIER_TARGET_AUDIT_SYMBOL_INVALID")
        matches = tuple(item for item in sessions if item.session_date == session_date and item.symbol == symbol)
        if len(matches) != 1:
            results.append(IssuerIdentifierTargetAudit(
                symbol=symbol, session_date=session_date, session_security_receipt_id=None, isin=None,
                bridge_available=False, cin=None, lei=None, sources=(), source_dates=(),
                unresolved_reason="EXACT_SESSION_SECURITY_UNAVAILABLE_OR_AMBIGUOUS",
            ))
            continue
        resolution = resolve_issuer_security_bridge(matches[0], bridges=all_bridges)
        available = resolution.readiness.value == "EXACT_ISSUER_BRIDGE"
        exact = resolution.bridges if available else ()
        linked_evidence = tuple(by_evidence_id[item.source_evidence_id] for item in exact if item.source_evidence_id in by_evidence_id)
        # A bridge without its immutable source receipt is not auditable as an
        # acquisition result.  Do not claim target coverage from partial input.
        lineage_missing = available and len(linked_evidence) != len(exact)
        if lineage_missing:
            available = False
            exact = ()
            linked_evidence = ()
        cin = next((item.issuer_identifier_value for item in exact if item.issuer_identifier_type is IssuerIdentifierType.CIN), None)
        lei = next((item.issuer_identifier_value for item in exact if item.issuer_identifier_type is IssuerIdentifierType.LEI), None)
        source_values = tuple(sorted({item.source for item in linked_evidence}, key=lambda item: item.value))
        results.append(IssuerIdentifierTargetAudit(
            symbol=symbol, session_date=session_date, session_security_receipt_id=matches[0].receipt_id,
            isin=matches[0].isin, bridge_available=available, cin=cin, lei=lei,
            sources=source_values, source_dates=tuple(sorted({item.source_as_of_date for item in linked_evidence})),
            unresolved_reason=None if available else ("SOURCE_EVIDENCE_LINEAGE_UNAVAILABLE" if lineage_missing else resolution.reasons[0].value),
        ))
    return tuple(results)


def _bridge_source_type(source: IssuerIdentifierEvidenceSource) -> IssuerSecurityBridgeSourceType:
    return {
        IssuerIdentifierEvidenceSource.NSE_STRUCTURED_FILING: IssuerSecurityBridgeSourceType.OFFICIAL_CORPORATE_FILING_STRUCTURED_IDENTITY,
        IssuerIdentifierEvidenceSource.NSE_BRSR_ARCHIVE: IssuerSecurityBridgeSourceType.OFFICIAL_CORPORATE_FILING_STRUCTURED_IDENTITY,
        IssuerIdentifierEvidenceSource.BSE_STRUCTURED_FILING: IssuerSecurityBridgeSourceType.OFFICIAL_CORPORATE_FILING_STRUCTURED_IDENTITY,
        IssuerIdentifierEvidenceSource.GLEIF_ANNA_ISIN_LEI: IssuerSecurityBridgeSourceType.GLEIF_ANNA_CERTIFIED_ISIN_LEI_RELATIONSHIP,
    }[source]


def _csv_rows(payload: bytes) -> tuple[dict[str, str], ...]:
    try:
        text = payload.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise IssuerIdentifierAcquisitionError("STRUCTURED_IDENTITY_SOURCE_NOT_UTF8") from error
    reader = csv.DictReader(StringIO(text))
    if not reader.fieldnames:
        raise IssuerIdentifierAcquisitionError("STRUCTURED_IDENTITY_SOURCE_HEADERS_MISSING")
    return tuple({ _header(key): (value or "").strip() for key, value in row.items() } for row in reader)


def _header(value: object) -> str:
    return " ".join(str(value or "").strip().upper().split())


def _parse_source_date(value: str) -> date:
    for format_ in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(value.strip(), format_).date()
        except ValueError:
            pass
    raise IssuerIdentifierAcquisitionError("STRUCTURED_IDENTITY_SOURCE_DATE_INVALID")


def _canonical_evidence(values: Iterable[ExactIssuerIdentifierEvidence]) -> tuple[ExactIssuerIdentifierEvidence, ...]:
    supplied = tuple(values)
    if not all(isinstance(item, ExactIssuerIdentifierEvidence) for item in supplied):
        raise IssuerIdentifierAcquisitionError("ISSUER_IDENTIFIER_EVIDENCE_INPUT_INVALID")
    unique: dict[tuple[str, str], ExactIssuerIdentifierEvidence] = {}
    for item in supplied:
        item.verify()
        key = (item.evidence_id, item.fingerprint)
        if key in unique and unique[key] != item:
            raise IssuerIdentifierAcquisitionError("ISSUER_IDENTIFIER_EVIDENCE_DUPLICATE_CONFLICT")
        unique[key] = item
    return tuple(sorted(unique.values(), key=lambda item: (item.source_as_of_date, item.source.value, item.evidence_id)))


def _canonical_sessions(values: Iterable[NseSessionPointIdentity]) -> tuple[NseSessionPointIdentity, ...]:
    supplied = tuple(values)
    if not all(isinstance(item, NseSessionPointIdentity) for item in supplied):
        raise IssuerIdentifierAcquisitionError("ISSUER_IDENTIFIER_SESSION_INPUT_INVALID")
    unique: dict[tuple[str, str], NseSessionPointIdentity] = {}
    for item in supplied:
        key = (item.receipt_id, item.fingerprint)
        if key in unique and unique[key] != item:
            raise IssuerIdentifierAcquisitionError("ISSUER_IDENTIFIER_SESSION_DUPLICATE_CONFLICT")
        unique[key] = item
    return tuple(sorted(unique.values(), key=lambda item: (item.session_date, item.symbol, item.isin, item.receipt_id)))


def _evidence_valid(value: ExactIssuerIdentifierEvidence) -> bool:
    pair = (value.registration_authority_id, value.registration_authority_entity_id)
    identifier = value.issuer_identifier_value
    valid_identifier = (
        value.issuer_identifier_type is IssuerIdentifierType.CIN and _CIN.fullmatch(identifier) is not None
    ) or (
        value.issuer_identifier_type is IssuerIdentifierType.LEI and _LEI.fullmatch(identifier) is not None
    )
    return all((
        _identifier(value.evidence_id), isinstance(value.source, IssuerIdentifierEvidenceSource),
        _identifier(value.source_record_id), _fingerprint(value.source_document_fingerprint),
        _fingerprint(value.source_record_fingerprint), _nonblank(value.source_reference),
        _date(value.source_as_of_date), _aware(value.source_observed_at),
        value.isin is None or _ISIN.fullmatch(value.isin) is not None,
        value.nse_symbol is None or _nonblank(value.nse_symbol),
        value.bse_scrip_code is None or _nonblank(value.bse_scrip_code),
        value.isin is not None or value.nse_symbol is not None or value.bse_scrip_code is not None,
        isinstance(value.issuer_identifier_type, IssuerIdentifierType), valid_identifier,
        value.issuer_legal_name is None or _nonblank(value.issuer_legal_name),
        (pair[0] is None) == (pair[1] is None),
        pair[0] is None or (_nonblank(pair[0]) and _nonblank(pair[1])),
        value.historical_known_at is None or _aware(value.historical_known_at),
        value.historical_known_at is None or _utc(value.historical_known_at).date() <= value.source_as_of_date,
        value.contract_id == CONTRACT_ID, value.contract_version == CONTRACT_VERSION,
    ))


def _evidence_identity(value: Mapping[str, object]) -> dict[str, object]:
    return {
        "contract_id": CONTRACT_ID, "contract_version": CONTRACT_VERSION,
        "source": value["source"].value, "source_record_id": value["source_record_id"],
        "source_document_fingerprint": value["source_document_fingerprint"],
        "source_record_fingerprint": value["source_record_fingerprint"],
        "source_reference": value["source_reference"], "source_as_of_date": value["source_as_of_date"].isoformat(),
        "historical_known_at": _time(value["historical_known_at"]),
        "isin": value["isin"], "nse_symbol": value["nse_symbol"], "bse_scrip_code": value["bse_scrip_code"],
        "issuer_identifier_type": value["issuer_identifier_type"].value,
        "issuer_identifier_value": value["issuer_identifier_value"],
    }


def _source_record_payload(value: Mapping[str, object]) -> dict[str, object]:
    return {
        key: _scalar(value[key]) for key in (
            "source", "source_record_id", "source_document_fingerprint", "source_reference", "source_as_of_date",
            "isin", "nse_symbol", "bse_scrip_code", "issuer_identifier_type", "issuer_identifier_value",
            "issuer_legal_name", "registration_authority_id", "registration_authority_entity_id",
        )
    }


def _evidence_payload(value: ExactIssuerIdentifierEvidence) -> dict[str, object]:
    return _evidence_payload_from_values({name: getattr(value, name) for name in value.__dataclass_fields__ if name not in {"fingerprint", "contract_id", "contract_version"}})


def _evidence_payload_from_values(value: Mapping[str, object]) -> dict[str, object]:
    return _evidence_identity(value) | {
        "evidence_id": value["evidence_id"], "source_observed_at": _time(value["source_observed_at"]),
        "issuer_legal_name": value["issuer_legal_name"],
        "registration_authority_id": value["registration_authority_id"],
        "registration_authority_entity_id": value["registration_authority_entity_id"],
    }


def _receipt_identity(value: Mapping[str, object]) -> dict[str, object]:
    return {
        "contract_id": CONTRACT_ID, "contract_version": CONTRACT_VERSION,
        "source": value["source"].value, "source_document_fingerprint": value["source_document_fingerprint"],
        "source_as_of_date": value["source_as_of_date"].isoformat(), "session_date": value["session_date"].isoformat(),
        # These counters describe this exact idempotent application result.
        # They keep an initial write and its replay as distinct immutable
        # operational receipts without changing any evidence or bridge ID.
        "evidence_inserted": value["evidence_inserted"], "evidence_already_present": value["evidence_already_present"],
        "bridge_inserted": value["bridge_inserted"], "bridge_already_present": value["bridge_already_present"],
        "exact_isin_candidates": value["exact_isin_candidates"], "symbol_conflicts": value["symbol_conflicts"],
    }


def _receipt_payload(value: IssuerIdentifierAcquisitionReceipt) -> dict[str, object]:
    return _receipt_payload_from_values({name: getattr(value, name) for name in value.__dataclass_fields__ if name not in {"fingerprint", "contract_id", "contract_version"}})


def _receipt_payload_from_values(value: Mapping[str, object]) -> dict[str, object]:
    return _receipt_identity(value) | {
        "receipt_id": value["receipt_id"],
    }


def _hash(value: object) -> str:
    return "sha256:" + hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()).hexdigest()


def _bytes_hash(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _scalar(value: object) -> object:
    if isinstance(value, StrEnum): return value.value
    if isinstance(value, datetime): return _utc(value).isoformat()
    if isinstance(value, date): return value.isoformat()
    return value


def _identifier(value: object) -> bool:
    return isinstance(value, str) and _ID.fullmatch(value) is not None


def _fingerprint(value: object) -> bool:
    return isinstance(value, str) and _FP.fullmatch(value) is not None


def _nonblank(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _optional(value: object) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _date(value: object) -> bool:
    return isinstance(value, date) and not isinstance(value, datetime)


def _aware(value: object) -> bool:
    return isinstance(value, datetime) and value.tzinfo is not None and value.utcoffset() is not None


def _utc(value: datetime) -> datetime:
    if not _aware(value):
        raise IssuerIdentifierAcquisitionError("ISSUER_IDENTIFIER_AWARE_TIMESTAMP_REQUIRED")
    return value.astimezone(UTC)


def _time(value: object) -> str | None:
    return _utc(value).isoformat() if isinstance(value, datetime) else None


__all__ = (
    "CONTRACT_ID", "CONTRACT_VERSION", "MAX_GLEIF_ISIN_LEI_ARCHIVE_BYTES", "MAX_GLEIF_ISIN_LEI_CSV_BYTES", "ExactIssuerIdentifierEvidence", "GleifLevel1Reference",
    "IssuerIdentifierAcquisitionError", "IssuerIdentifierAcquisitionReceipt", "IssuerIdentifierEvidenceSource",
    "IssuerIdentifierEvidenceStore", "IssuerIdentifierWriteOutcome", "acquire_exact_issuer_bridges",
    "audit_target_issuer_coverage",
    "evidence_from_structured_row", "extract_bse_structured_identity_rows", "extract_gleif_isin_lei_zip",
    "extract_nse_structured_identity_csv", "gleif_level1_reference_from_payload",
)
