"""Immutable primary-regulator evidence for future company-type research.

This is deliberately an evidence and readiness boundary.  It preserves what
RBI, IRDAI and the already-canonical NSE Indices taxonomy state; it does not
classify an issuer, infer an entity relationship from a name, or activate a
company-type policy.
"""
from __future__ import annotations

from dataclasses import dataclass, fields
from datetime import UTC, date, datetime
from enum import StrEnum
from hashlib import sha256
from html.parser import HTMLParser
from io import BytesIO
import json
import re
from typing import Iterable, Mapping

from app.historical.isin_issuer_bridge_continuity import IsinIssuerForwardObservation
from app.storage.core_api_snapshot_repository import (
    CoreApiSnapshot, CoreApiSnapshotFamily, CoreApiSnapshotRepository,
)
from app.taxonomy.models import InstrumentTaxonomyClassification
from app.universe_analysis.models import NseEquityInstrument


CONTRACT_ID = "pit-regulator-company-type-evidence-ingestion"
CONTRACT_VERSION = "v1"
RBI_SCHEDULED_BANKS_URL = "https://www.rbi.org.in/Scripts/BS_viewcontent.aspx?Id=3657"
RBI_NBFC_LIST_URL = "https://www.rbi.org.in/Scripts/BS_NBFCList.aspx"
RBI_REGISTERED_NBFC_ARC_XLSX_URL = "https://rbidocs.rbi.org.in/rdocs/content/DOCs/List_of_NBFCs_and_ARCs_registered_with_the_RBI.XLSX"
RBI_CANCELLED_NBFC_ARC_XLSX_URL = "https://rbidocs.rbi.org.in/rdocs/content/DOCs/List_of_NBFCs_and_ARCs_whose_CoR_has_been_cancelled_by_the_RBI.XLSX"
IRDAI_LIFE_INSURERS_URL = "https://irdai.gov.in/list-of-life-insurers1"
IRDAI_GENERAL_INSURERS_URL = "https://irdai.gov.in/list-of-general-insurers"
IRDAI_HEALTH_INSURERS_URL = "https://irdai.gov.in/list-of-health-insurers"

_ID = re.compile(r"[A-Za-z0-9._:-]+\Z")
_FP = re.compile(r"sha256:[0-9a-f]{64}\Z")
_CIN = re.compile(r"[LU][0-9]{5}[A-Z]{2}[0-9]{4}[A-Z]{3}[0-9]{6}\Z")


class RegulatorCompanyTypeEvidenceError(ValueError):
    """Stable, fail-closed error for immutable regulator evidence."""


class RegulatorEvidenceSource(StrEnum):
    RBI_SCHEDULED_COMMERCIAL_BANKS = "RBI_SCHEDULED_COMMERCIAL_BANKS"
    RBI_REGISTERED_NBFC_ARC = "RBI_REGISTERED_NBFC_ARC"
    RBI_CANCELLED_NBFC_ARC = "RBI_CANCELLED_NBFC_ARC"
    IRDAI_LIFE_INSURERS = "IRDAI_LIFE_INSURERS"
    IRDAI_GENERAL_INSURERS = "IRDAI_GENERAL_INSURERS"
    IRDAI_HEALTH_INSURERS = "IRDAI_HEALTH_INSURERS"


class RegulatorEntityEvidenceKind(StrEnum):
    SCHEDULED_COMMERCIAL_BANK = "SCHEDULED_COMMERCIAL_BANK"
    RBI_REGISTERED_NBFC = "RBI_REGISTERED_NBFC"
    RBI_REGISTERED_ARC = "RBI_REGISTERED_ARC"
    RBI_CANCELLED_NBFC = "RBI_CANCELLED_NBFC"
    RBI_CANCELLED_ARC = "RBI_CANCELLED_ARC"
    IRDAI_LIFE_INSURER = "IRDAI_LIFE_INSURER"
    IRDAI_GENERAL_INSURER = "IRDAI_GENERAL_INSURER"
    IRDAI_HEALTH_INSURER = "IRDAI_HEALTH_INSURER"


class RegulatorEntityStatus(StrEnum):
    LISTED = "LISTED"
    CANCELLED = "CANCELLED"


class RegulatorTemporalStatus(StrEnum):
    SOURCE_DATE_PRESENT = "SOURCE_DATE_PRESENT"
    SOURCE_DATE_UNAVAILABLE = "SOURCE_DATE_UNAVAILABLE"
    CANCELLATION_DATE_PRESENT = "CANCELLATION_DATE_PRESENT"


class IssuerLinkageStatus(StrEnum):
    EXACT_CIN_LINKED = "EXACT_CIN_LINKED"
    ISSUER_LINKAGE_UNRESOLVED = "ISSUER_LINKAGE_UNRESOLVED"
    EVIDENCE_CONFLICTED = "EVIDENCE_CONFLICTED"


class RegulatorEvidenceWriteOutcome(StrEnum):
    INSERTED = "INSERTED"
    ALREADY_PRESENT = "ALREADY_PRESENT"


@dataclass(frozen=True, slots=True)
class RegulatorSourceArtifact:
    source_artifact_id: str
    source: RegulatorEvidenceSource
    source_reference: str
    source_fingerprint: str
    content_type: str
    content_length: int
    source_as_of_date: date | None
    observed_at: datetime
    temporal_status: RegulatorTemporalStatus
    schema: tuple[str, ...]
    fingerprint: str
    contract_id: str = CONTRACT_ID
    contract_version: str = CONTRACT_VERSION
    # A dated historical publication can be acquired later without changing
    # the date on which the regulator made it knowable.  This date-only field
    # deliberately does not manufacture a publication time of day.
    source_known_on: date | None = None

    def __post_init__(self) -> None:
        if not _artifact_valid(self) or self.fingerprint != _hash(_artifact_payload(self)):
            raise RegulatorCompanyTypeEvidenceError("REGULATOR_SOURCE_ARTIFACT_INVALID")


@dataclass(frozen=True, slots=True)
class RegulatorEntityEvidence:
    evidence_id: str
    source_artifact_id: str
    source_artifact_fingerprint: str
    source: RegulatorEvidenceSource
    source_record_id: str
    source_record_fingerprint: str
    entity_kind: RegulatorEntityEvidenceKind
    entity_status: RegulatorEntityStatus
    legal_name: str
    regulator_registration_id: str | None
    cin: str | None
    regulator_subtype: str | None
    address: str | None
    effective_on: date | None
    cancellation_on: date | None
    source_as_of_date: date | None
    observed_at: datetime
    temporal_status: RegulatorTemporalStatus
    fingerprint: str
    contract_id: str = CONTRACT_ID
    contract_version: str = CONTRACT_VERSION
    # These fields preserve an RBI cancellation/surrender event as stated by
    # the source.  A CoR issue date is not a derived registration interval.
    source_known_on: date | None = None
    cor_issued_on: date | None = None
    event_reason: str | None = None

    def __post_init__(self) -> None:
        if not _evidence_valid(self) or self.fingerprint != _hash(_evidence_payload(self)):
            raise RegulatorCompanyTypeEvidenceError("REGULATOR_ENTITY_EVIDENCE_INVALID")

    def verify(self) -> None:
        self.__post_init__()


@dataclass(frozen=True, slots=True)
class RegulatorEvidenceBatch:
    artifact: RegulatorSourceArtifact
    evidence: tuple[RegulatorEntityEvidence, ...]

    def __post_init__(self) -> None:
        if not self.evidence or any(item.source_artifact_id != self.artifact.source_artifact_id or item.source_artifact_fingerprint != self.artifact.fingerprint for item in self.evidence):
            raise RegulatorCompanyTypeEvidenceError("REGULATOR_EVIDENCE_BATCH_INVALID")


@dataclass(frozen=True, slots=True)
class RegulatorIssuerLinkAudit:
    evidence_id: str
    entity_kind: RegulatorEntityEvidenceKind
    cin: str | None
    pit_eligible: bool
    linkage_status: IssuerLinkageStatus
    issuer_bridge_ids: tuple[str, ...]
    reason: str


@dataclass(frozen=True, slots=True)
class TaxonomyIssuerEvidenceAudit:
    classification_id: str
    isin: str | None
    issuer_bridge_ids: tuple[str, ...]
    taxonomy_codes: tuple[str, ...]
    source_as_of: datetime
    pit_eligible: bool


class RegulatorCompanyTypeEvidenceStore:
    """Append-only use of the existing immutable snapshot repository."""

    def __init__(self, repository: CoreApiSnapshotRepository) -> None:
        self._repository = repository

    def save_artifact(self, value: RegulatorSourceArtifact) -> RegulatorEvidenceWriteOutcome:
        return self._save(value.source_artifact_id, value, value.observed_at)

    def save_evidence(self, value: RegulatorEntityEvidence) -> RegulatorEvidenceWriteOutcome:
        return self._save(value.evidence_id, value, value.observed_at)

    def artifacts(self) -> tuple[RegulatorSourceArtifact, ...]:
        return tuple(item for item in self._all() if isinstance(item, RegulatorSourceArtifact))

    def evidence(self) -> tuple[RegulatorEntityEvidence, ...]:
        return tuple(item for item in self._all() if isinstance(item, RegulatorEntityEvidence))

    def _save(self, snapshot_id: str, value: object, observed_at: datetime) -> RegulatorEvidenceWriteOutcome:
        existing = self._repository.get_snapshot(snapshot_id)
        if existing is not None:
            if existing.family is not CoreApiSnapshotFamily.HISTORICAL_REGULATOR_ENTITY_EVIDENCE or existing.payload != value:
                raise RegulatorCompanyTypeEvidenceError("REGULATOR_EVIDENCE_IMMUTABILITY_CONFLICT")
            return RegulatorEvidenceWriteOutcome.ALREADY_PRESENT
        fingerprint = getattr(value, "fingerprint", None)
        self._repository.save_snapshot(CoreApiSnapshot(
            snapshot_id, CoreApiSnapshotFamily.HISTORICAL_REGULATOR_ENTITY_EVIDENCE, "v1",
            type(value).__name__, fingerprint, observed_at, value,
        ))
        return RegulatorEvidenceWriteOutcome.INSERTED

    def _all(self) -> tuple[object, ...]:
        values: list[object] = []
        offset = 0
        while True:
            page = self._repository.list_snapshots(CoreApiSnapshotFamily.HISTORICAL_REGULATOR_ENTITY_EVIDENCE, limit=100, offset=offset)
            values.extend(item.payload for item in page)
            if len(page) < 100:
                break
            offset += len(page)
        return tuple(values)


def source_artifact_from_payload(*, source: RegulatorEvidenceSource, source_reference: str, payload: bytes,
                                 content_type: str, observed_at: datetime, source_as_of_date: date | None,
                                 schema: Iterable[str], temporal_status: RegulatorTemporalStatus | None = None,
                                 source_known_on: date | None = None) -> RegulatorSourceArtifact:
    """Create a source receipt.  Current observation never claims historic knowledge."""
    if not _aware(observed_at) or not _nonblank(source_reference) or not payload:
        raise RegulatorCompanyTypeEvidenceError("REGULATOR_SOURCE_METADATA_INVALID")
    source_fingerprint = _bytes_hash(payload)
    status = temporal_status or (RegulatorTemporalStatus.SOURCE_DATE_PRESENT if source_as_of_date else RegulatorTemporalStatus.SOURCE_DATE_UNAVAILABLE)
    identity = {
        "source": source.value, "source_reference": source_reference, "source_fingerprint": source_fingerprint,
        "source_as_of_date": _date_text(source_as_of_date), "temporal_status": status.value,
    }
    if source_known_on is not None:
        identity["source_known_on"] = _date_text(source_known_on)
    artifact_id = "regulator-source:" + _hash(identity)[7:39]
    values = dict(
        source_artifact_id=artifact_id, source=source, source_reference=source_reference,
        source_fingerprint=source_fingerprint, content_type=content_type, content_length=len(payload),
        source_as_of_date=source_as_of_date, observed_at=_utc(observed_at), temporal_status=status,
        schema=tuple(sorted({_clean_header(item) for item in schema if _nonblank(item)})),
        source_known_on=source_known_on,
    )
    return RegulatorSourceArtifact(**values, fingerprint=_hash(_artifact_payload_from_values(values)))


def rbi_scheduled_bank_batch(*, payload: bytes, observed_at: datetime, source_as_of_date: date | None = None,
                             source_reference: str = RBI_SCHEDULED_BANKS_URL,
                             source_known_on: date | None = None) -> RegulatorEvidenceBatch:
    rows = _html_rows(payload)
    artifact = source_artifact_from_payload(
        source=RegulatorEvidenceSource.RBI_SCHEDULED_COMMERCIAL_BANKS, source_reference=source_reference,
        payload=payload, content_type="text/html", observed_at=observed_at, source_as_of_date=source_as_of_date,
        schema=("category", "serial_number", "legal_name"), source_known_on=source_known_on,
    )
    category: str | None = None
    values: list[RegulatorEntityEvidence] = []
    for ordinal, row in enumerate(rows, start=1):
        if len(row) == 1 and row[0] and not _looks_serial(row[0]):
            category = row[0]
            continue
        if len(row) < 2 or not _looks_serial(row[0]) or not category:
            continue
        values.append(_entity(
            artifact=artifact, source_record_id=f"rbi-scheduled-bank-row:{ordinal}",
            entity_kind=RegulatorEntityEvidenceKind.SCHEDULED_COMMERCIAL_BANK,
            entity_status=RegulatorEntityStatus.LISTED, legal_name=row[1], regulator_subtype=category,
        ))
    return _batch(artifact, values)


def rbi_nbfc_arc_batch(*, payload: bytes, source: RegulatorEvidenceSource, observed_at: datetime,
                       source_as_of_date: date, source_reference: str,
                       source_known_on: date | None = None) -> RegulatorEvidenceBatch:
    """Parse an official RBI XLSX without manufacturing absent identifiers.

    The official list's headers vary by release.  Only explicit, recognized
    columns are consumed; a missing legal-name column fails closed.
    """
    if source not in {RegulatorEvidenceSource.RBI_REGISTERED_NBFC_ARC, RegulatorEvidenceSource.RBI_CANCELLED_NBFC_ARC}:
        raise RegulatorCompanyTypeEvidenceError("RBI_NBFC_SOURCE_INVALID")
    try:
        from openpyxl import load_workbook
        book = load_workbook(BytesIO(payload), read_only=True, data_only=True)
    except Exception as error:  # source response can be an access-denial HTML page.
        raise RegulatorCompanyTypeEvidenceError("RBI_NBFC_SOURCE_NOT_VALID_XLSX") from error
    sheet = book.active
    raw_rows = tuple(tuple(_cell(item) for item in row) for row in sheet.iter_rows(values_only=True))
    header_index, header = _find_header(raw_rows)
    name_column = _column(header, "NAME OF THE COMPANY", "COMPANY NAME", "NAME")
    if name_column is None:
        raise RegulatorCompanyTypeEvidenceError("RBI_NBFC_REQUIRED_NAME_COLUMN_UNAVAILABLE")
    artifact = source_artifact_from_payload(
        source=source, source_reference=source_reference, payload=payload,
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        observed_at=observed_at, source_as_of_date=source_as_of_date, schema=header,
        temporal_status=RegulatorTemporalStatus.SOURCE_DATE_PRESENT,
        source_known_on=source_known_on,
    )
    category_column = _column(header, "CATEGORY", "TYPE OF NBFC", "NBFC CATEGORY", "COMPANY CATEGORY")
    cor_column = _column(header, "COR NO", "COR NUMBER", "CERTIFICATE OF REGISTRATION NO", "REGISTRATION NO")
    cin_column = _column(header, "CIN")
    address_column = _column(header, "ADDRESS", "REGISTERED OFFICE ADDRESS")
    date_column = _column(header, "CANCELLATION DATE", "DATE OF CANCELLATION", "DATE OF REGISTRATION")
    values: list[RegulatorEntityEvidence] = []
    for ordinal, row in enumerate(raw_rows[header_index + 1:], start=header_index + 2):
        name = _at(row, name_column)
        if not name:
            continue
        category = _at(row, category_column)
        is_arc = "ARC" in (category or "").upper() or "ASSET RECONSTRUCTION" in (category or "").upper()
        cancelled = source is RegulatorEvidenceSource.RBI_CANCELLED_NBFC_ARC
        kind = (
            RegulatorEntityEvidenceKind.RBI_CANCELLED_ARC if cancelled and is_arc else
            RegulatorEntityEvidenceKind.RBI_CANCELLED_NBFC if cancelled else
            RegulatorEntityEvidenceKind.RBI_REGISTERED_ARC if is_arc else
            RegulatorEntityEvidenceKind.RBI_REGISTERED_NBFC
        )
        cancellation = _parse_optional_date(_at(row, date_column)) if cancelled else None
        values.append(_entity(
            artifact=artifact, source_record_id=f"rbi-nbfc-row:{ordinal}", entity_kind=kind,
            entity_status=RegulatorEntityStatus.CANCELLED if cancelled else RegulatorEntityStatus.LISTED,
            legal_name=name, regulator_registration_id=_at(row, cor_column), cin=_at(row, cin_column),
            regulator_subtype=category, address=_at(row, address_column), cancellation_on=cancellation,
            temporal_status=RegulatorTemporalStatus.CANCELLATION_DATE_PRESENT if cancellation else artifact.temporal_status,
        ))
    return _batch(artifact, values)


def irdai_insurer_batch(*, payload: bytes, source: RegulatorEvidenceSource, observed_at: datetime,
                        source_as_of_date: date | None = None, source_reference: str | None = None) -> RegulatorEvidenceBatch:
    kinds = {
        RegulatorEvidenceSource.IRDAI_LIFE_INSURERS: (RegulatorEntityEvidenceKind.IRDAI_LIFE_INSURER, IRDAI_LIFE_INSURERS_URL),
        RegulatorEvidenceSource.IRDAI_GENERAL_INSURERS: (RegulatorEntityEvidenceKind.IRDAI_GENERAL_INSURER, IRDAI_GENERAL_INSURERS_URL),
        RegulatorEvidenceSource.IRDAI_HEALTH_INSURERS: (RegulatorEntityEvidenceKind.IRDAI_HEALTH_INSURER, IRDAI_HEALTH_INSURERS_URL),
    }
    if source not in kinds:
        raise RegulatorCompanyTypeEvidenceError("IRDAI_INSURER_SOURCE_INVALID")
    kind, default_reference = kinds[source]
    tables = _html_rows(payload, keep_empty=True)
    artifact = source_artifact_from_payload(
        source=source, source_reference=source_reference or default_reference, payload=payload,
        content_type="text/html", observed_at=observed_at, source_as_of_date=source_as_of_date,
        schema=("serial_number", "legal_name", "registration_number", "address"),
    )
    values: list[RegulatorEntityEvidence] = []
    header_index, header = _find_irdai_header(tables)
    name_column = _column(header, "NAME", "INSURER")
    registration_column = _column(header, "REGN NO", "REGISTRATION NO")
    address_column = _column(header, "ADDRESS", "REGISTERED CORPORATE ADDRESS")
    assert name_column is not None  # established by _find_irdai_header.
    # Keep only the named insurer table.  A serial number from page navigation
    # or another regulator directory cannot enter this approved family.
    for ordinal, row in enumerate(tables[header_index + 1:], start=header_index + 2):
        name = _at(row, name_column)
        if not row or not _looks_serial(row[0]) or not name:
            continue
        registration = _at(row, registration_column)
        address = _at(row, address_column)
        values.append(_entity(
            artifact=artifact, source_record_id=f"irdai-insurer-row:{ordinal}", entity_kind=kind,
            entity_status=RegulatorEntityStatus.LISTED, legal_name=name,
            regulator_registration_id=registration, address=address,
            regulator_subtype=kind.value,
        ))
    return _batch(artifact, values)


def persist_regulator_evidence(*, store: RegulatorCompanyTypeEvidenceStore, batch: RegulatorEvidenceBatch) -> tuple[int, int, int, int]:
    """Persist an immutable source batch.  Exact replays have no new rows."""
    artifact_outcome = store.save_artifact(batch.artifact)
    inserted = present = 0
    for item in batch.evidence:
        outcome = store.save_evidence(item)
        inserted += outcome is RegulatorEvidenceWriteOutcome.INSERTED
        present += outcome is RegulatorEvidenceWriteOutcome.ALREADY_PRESENT
    return (int(artifact_outcome is RegulatorEvidenceWriteOutcome.INSERTED), int(artifact_outcome is RegulatorEvidenceWriteOutcome.ALREADY_PRESENT), inserted, present)


def audit_exact_regulator_issuer_links(*, evidence: Iterable[RegulatorEntityEvidence],
                                       active_bridges: Iterable[IsinIssuerForwardObservation], as_of: datetime) -> tuple[RegulatorIssuerLinkAudit, ...]:
    """Assess CIN-only compatibility; legal names are deliberately ignored."""
    if not _aware(as_of):
        raise RegulatorCompanyTypeEvidenceError("REGULATOR_AUDIT_AS_OF_INVALID")
    eligible = tuple(item for item in active_bridges if item.later_session_date <= _utc(as_of).date() and all(known <= _utc(as_of) for known in item.anchor_known_ats))
    by_cin: dict[str, list[IsinIssuerForwardObservation]] = {}
    for item in eligible:
        by_cin.setdefault(item.cin, []).append(item)
    supplied = _canonical_evidence(evidence)
    eligible_kinds_by_cin: dict[str, set[RegulatorEntityEvidenceKind]] = {}
    for item in supplied:
        if item.cin is not None and _evidence_pit_eligible(item, _utc(as_of)):
            eligible_kinds_by_cin.setdefault(item.cin, set()).add(item.entity_kind)
    values: list[RegulatorIssuerLinkAudit] = []
    for item in supplied:
        pit_eligible = _evidence_pit_eligible(item, _utc(as_of))
        matches = tuple(sorted({bridge.observation_id: bridge for bridge in by_cin.get(item.cin or "", ())}.values(), key=lambda value: value.observation_id)) if pit_eligible else ()
        conflicted = item.cin is not None and len(eligible_kinds_by_cin.get(item.cin, ())) > 1
        status = IssuerLinkageStatus.EVIDENCE_CONFLICTED if conflicted else (IssuerLinkageStatus.EXACT_CIN_LINKED if matches else IssuerLinkageStatus.ISSUER_LINKAGE_UNRESOLVED)
        values.append(RegulatorIssuerLinkAudit(
            evidence_id=item.evidence_id, entity_kind=item.entity_kind, cin=item.cin, pit_eligible=pit_eligible, linkage_status=status,
            issuer_bridge_ids=tuple(value.observation_id for value in matches),
            reason=(
                "INCOMPATIBLE_EXACT_REGULATOR_EVIDENCE" if conflicted else "EXACT_CIN_MATCH" if matches else
                "SOURCE_DATE_UNAVAILABLE" if item.source_as_of_date is None else
                "SOURCE_KNOWN_AFTER_AS_OF" if item.source_known_on is not None and item.source_known_on > _utc(as_of).date() else
                "SOURCE_OBSERVED_AFTER_AS_OF" if item.observed_at > _utc(as_of) else
                "REGULATOR_CIN_ABSENT" if item.cin is None else "NO_ACTIVE_EXACT_CIN_BRIDGE"
            ),
        ))
    return tuple(values)


def audit_nse_taxonomy_issuer_evidence(*, classifications: Iterable[InstrumentTaxonomyClassification],
                                       instruments: Iterable[NseEquityInstrument], active_bridges: Iterable[IsinIssuerForwardObservation],
                                       as_of: datetime) -> tuple[TaxonomyIssuerEvidenceAudit, ...]:
    """Expose exact ISIN-linked taxonomy lineage without a code-to-type map."""
    if not _aware(as_of):
        raise RegulatorCompanyTypeEvidenceError("TAXONOMY_AUDIT_AS_OF_INVALID")
    by_instrument: dict[str, set[str]] = {}
    for instrument in instruments:
        if instrument.isin:
            by_instrument.setdefault(instrument.instrument_id, set()).add(instrument.isin)
    bridge_by_isin: dict[str, set[str]] = {}
    for bridge in active_bridges:
        if bridge.later_session_date <= _utc(as_of).date() and all(known <= _utc(as_of) for known in bridge.anchor_known_ats):
            bridge_by_isin.setdefault(bridge.isin, set()).add(bridge.observation_id)
    values: list[TaxonomyIssuerEvidenceAudit] = []
    for item in sorted(classifications, key=lambda value: value.classification_id):
        pit_eligible = item.eligible_as_of(_utc(as_of))
        isins = by_instrument.get(item.instrument_id, set())
        isin = next(iter(isins)) if len(isins) == 1 else None
        codes = tuple(code for code in (item.macro_economic_sector_code, item.sector_code, item.industry_code, item.basic_industry_code) if code)
        values.append(TaxonomyIssuerEvidenceAudit(
            classification_id=item.classification_id, isin=isin,
            issuer_bridge_ids=tuple(sorted(bridge_by_isin.get(isin or "", ()))), taxonomy_codes=codes,
            source_as_of=item.as_of, pit_eligible=pit_eligible,
        ))
    return tuple(values)


def _entity(*, artifact: RegulatorSourceArtifact, source_record_id: str, entity_kind: RegulatorEntityEvidenceKind,
            entity_status: RegulatorEntityStatus, legal_name: str, regulator_registration_id: str | None = None,
            cin: str | None = None, regulator_subtype: str | None = None, address: str | None = None,
            effective_on: date | None = None, cancellation_on: date | None = None,
            temporal_status: RegulatorTemporalStatus | None = None, cor_issued_on: date | None = None,
            event_reason: str | None = None) -> RegulatorEntityEvidence:
    legal_name = _required(legal_name, "REGULATOR_ENTITY_LEGAL_NAME_INVALID")
    record_values = {
        "source_artifact": artifact.source_fingerprint, "record": source_record_id, "legal_name": legal_name,
        "registration": regulator_registration_id, "cin": cin, "subtype": regulator_subtype,
        "address": address, "effective": _date_text(effective_on), "cancelled": _date_text(cancellation_on),
    }
    if cor_issued_on is not None:
        record_values["cor_issued_on"] = _date_text(cor_issued_on)
    if event_reason is not None:
        record_values["event_reason"] = event_reason
    values = dict(
        source_artifact_id=artifact.source_artifact_id, source_artifact_fingerprint=artifact.fingerprint,
        source=artifact.source, source_record_id=_required(source_record_id, "REGULATOR_SOURCE_RECORD_ID_INVALID"),
        source_record_fingerprint=_hash(record_values),
        entity_kind=entity_kind, entity_status=entity_status, legal_name=legal_name,
        regulator_registration_id=_optional(regulator_registration_id), cin=_optional(cin), regulator_subtype=_optional(regulator_subtype),
        address=_optional(address), effective_on=effective_on, cancellation_on=cancellation_on,
        source_as_of_date=artifact.source_as_of_date, observed_at=artifact.observed_at,
        temporal_status=temporal_status or artifact.temporal_status,
        source_known_on=artifact.source_known_on, cor_issued_on=cor_issued_on, event_reason=_optional(event_reason),
    )
    if values["cin"] is not None and _CIN.fullmatch(values["cin"]) is None:
        raise RegulatorCompanyTypeEvidenceError("REGULATOR_ENTITY_CIN_INVALID")
    optional_new = {"source_known_on", "cor_issued_on", "event_reason"}
    identity = {
        key: _scalar(value) for key, value in values.items()
        if key not in {"observed_at", "source_record_fingerprint"} and (key not in optional_new or value is not None)
    }
    evidence_id = "regulator-entity:" + _hash(identity)[7:39]
    return RegulatorEntityEvidence(evidence_id=evidence_id, **values, fingerprint=_hash(_evidence_payload_from_values(values | {"evidence_id": evidence_id})))


def _batch(artifact: RegulatorSourceArtifact, evidence: Iterable[RegulatorEntityEvidence]) -> RegulatorEvidenceBatch:
    values = _canonical_evidence(evidence)
    if not values:
        raise RegulatorCompanyTypeEvidenceError("REGULATOR_SOURCE_NO_SUPPORTED_ENTITY_ROWS")
    return RegulatorEvidenceBatch(artifact, values)


class _TableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(); self.rows: list[tuple[str, ...]] = []; self._row: list[str] = []; self._cell: list[str] = []; self._in_cell = False
    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "tr": self._row = []
        elif tag in {"td", "th"}: self._in_cell = True; self._cell = []
    def handle_data(self, data: str) -> None:
        if self._in_cell: self._cell.append(data)
    def handle_endtag(self, tag: str) -> None:
        if tag in {"td", "th"}:
            self._row.append(" ".join("".join(self._cell).split())); self._in_cell = False
        elif tag == "tr" and self._row:
            self.rows.append(tuple(self._row))


def _html_rows(payload: bytes, *, keep_empty: bool = False) -> tuple[tuple[str, ...], ...]:
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError:
        text = payload.decode("utf-8", errors="replace")
    parser = _TableParser(); parser.feed(text); parser.close()
    return tuple(row for row in parser.rows if keep_empty or any(row))


def _find_header(rows: tuple[tuple[str, ...], ...]) -> tuple[int, tuple[str, ...]]:
    for index, row in enumerate(rows[:30]):
        header = tuple(_clean_header(value) for value in row)
        if any(value in {"NAME", "COMPANY NAME", "NAME OF THE COMPANY"} for value in header):
            return index, header
    raise RegulatorCompanyTypeEvidenceError("RBI_NBFC_HEADERS_UNAVAILABLE")


def _find_irdai_header(rows: tuple[tuple[str, ...], ...]) -> tuple[int, tuple[str, ...]]:
    for index, row in enumerate(rows[:60]):
        header = tuple(_clean_header(value) for value in row)
        if any(value in {"NAME", "INSURER"} for value in header) and any("NO" in value for value in header[:2]):
            return index, header
    raise RegulatorCompanyTypeEvidenceError("IRDAI_INSURER_HEADERS_UNAVAILABLE")


def _column(header: tuple[str, ...], *candidates: str) -> int | None:
    wanted = {_clean_header(value) for value in candidates}
    return next((index for index, value in enumerate(header) if value in wanted), None)


def _at(row: tuple[str, ...], index: int | None) -> str | None:
    return _optional(row[index]) if index is not None and index < len(row) else None


def _parse_optional_date(value: str | None) -> date | None:
    if value is None: return None
    for layout in ("%d-%m-%Y", "%d/%m/%Y", "%Y-%m-%d"):
        try: return datetime.strptime(value, layout).date()
        except ValueError: pass
    return None


def _canonical_evidence(values: Iterable[RegulatorEntityEvidence]) -> tuple[RegulatorEntityEvidence, ...]:
    unique: dict[str, RegulatorEntityEvidence] = {}
    for item in values:
        item.verify()
        existing = unique.get(item.evidence_id)
        if existing is not None and existing != item:
            raise RegulatorCompanyTypeEvidenceError("REGULATOR_EVIDENCE_DUPLICATE_CONFLICT")
        unique[item.evidence_id] = item
    return tuple(sorted(unique.values(), key=lambda item: item.evidence_id))


def _evidence_pit_eligible(value: RegulatorEntityEvidence, as_of: datetime) -> bool:
    """Use a regulator's supplied known date where one is preserved.

    Historical publication dates are deliberately date-granular.  The local
    receipt timestamp records acquisition, not the date the regulator made a
    historical document public.  Undated/current adapters retain the original
    stricter receipt-time rule.
    """
    if value.source_as_of_date is None or value.source_as_of_date > as_of.date():
        return False
    if value.source_known_on is not None:
        return value.source_known_on <= as_of.date()
    return value.observed_at <= as_of


def _artifact_valid(value: RegulatorSourceArtifact) -> bool:
    return all((
        _identifier(value.source_artifact_id), isinstance(value.source, RegulatorEvidenceSource), _nonblank(value.source_reference),
        _fingerprint(value.source_fingerprint), _nonblank(value.content_type), isinstance(value.content_length, int) and value.content_length > 0,
        value.source_as_of_date is None or _is_date(value.source_as_of_date), _aware(value.observed_at),
        value.source_known_on is None or _is_date(value.source_known_on),
        isinstance(value.temporal_status, RegulatorTemporalStatus), bool(value.schema), value.contract_id == CONTRACT_ID, value.contract_version == CONTRACT_VERSION,
    ))


def _evidence_valid(value: RegulatorEntityEvidence) -> bool:
    cancelled = value.entity_status is RegulatorEntityStatus.CANCELLED
    return all((
        _identifier(value.evidence_id), _identifier(value.source_artifact_id), _fingerprint(value.source_artifact_fingerprint),
        isinstance(value.source, RegulatorEvidenceSource), _identifier(value.source_record_id), _fingerprint(value.source_record_fingerprint),
        isinstance(value.entity_kind, RegulatorEntityEvidenceKind), isinstance(value.entity_status, RegulatorEntityStatus), _nonblank(value.legal_name),
        value.regulator_registration_id is None or _nonblank(value.regulator_registration_id), value.cin is None or _CIN.fullmatch(value.cin) is not None,
        value.regulator_subtype is None or _nonblank(value.regulator_subtype), value.address is None or _nonblank(value.address),
        value.effective_on is None or _is_date(value.effective_on), value.cancellation_on is None or _is_date(value.cancellation_on),
        value.source_as_of_date is None or _is_date(value.source_as_of_date), _aware(value.observed_at),
        value.source_known_on is None or _is_date(value.source_known_on), value.cor_issued_on is None or _is_date(value.cor_issued_on),
        value.event_reason is None or _nonblank(value.event_reason),
        isinstance(value.temporal_status, RegulatorTemporalStatus), (not cancelled) or value.entity_kind in {RegulatorEntityEvidenceKind.RBI_CANCELLED_NBFC, RegulatorEntityEvidenceKind.RBI_CANCELLED_ARC},
        value.contract_id == CONTRACT_ID, value.contract_version == CONTRACT_VERSION,
    ))


def _artifact_payload(value: RegulatorSourceArtifact) -> dict[str, object]: return _artifact_payload_from_values({field.name: getattr(value, field.name) for field in fields(value) if field.name not in {"fingerprint", "contract_id", "contract_version"}})
def _artifact_payload_from_values(value: Mapping[str, object]) -> dict[str, object]: return _payload_values(value)
def _evidence_payload(value: RegulatorEntityEvidence) -> dict[str, object]: return _evidence_payload_from_values({field.name: getattr(value, field.name) for field in fields(value) if field.name not in {"fingerprint", "contract_id", "contract_version"}})
def _evidence_payload_from_values(value: Mapping[str, object]) -> dict[str, object]: return _payload_values(value)
def _payload_values(value: Mapping[str, object]) -> dict[str, object]:
    # Preserve validation of existing v1 snapshots created before these
    # optional source-detail fields were added.  New non-null values are part
    # of immutable source/evidence fingerprints.
    optional_new = {"source_known_on", "cor_issued_on", "event_reason"}
    return {key: _scalar(item) for key, item in value.items() if key not in optional_new or item is not None}
def _hash(value: object) -> str: return "sha256:" + sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()).hexdigest()
def _bytes_hash(value: bytes) -> str: return "sha256:" + sha256(value).hexdigest()
def _scalar(value: object) -> object:
    if isinstance(value, StrEnum): return value.value
    if isinstance(value, datetime): return _utc(value).isoformat()
    if isinstance(value, date): return value.isoformat()
    if isinstance(value, tuple): return tuple(_scalar(item) for item in value)
    return value
def _clean_header(value: object) -> str: return " ".join(str(value or "").upper().replace(".", " ").split())
def _cell(value: object) -> str: return "" if value is None else str(value).strip()
def _optional(value: object) -> str | None: return value.strip() if isinstance(value, str) and value.strip() else None
def _required(value: object, error: str) -> str:
    result = _optional(value)
    if result is None: raise RegulatorCompanyTypeEvidenceError(error)
    return result
def _nonblank(value: object) -> bool: return _optional(value) is not None
def _identifier(value: object) -> bool: return isinstance(value, str) and _ID.fullmatch(value) is not None
def _fingerprint(value: object) -> bool: return isinstance(value, str) and _FP.fullmatch(value) is not None
def _aware(value: object) -> bool: return isinstance(value, datetime) and value.tzinfo is not None and value.utcoffset() is not None
def _utc(value: datetime) -> datetime:
    if not _aware(value): raise RegulatorCompanyTypeEvidenceError("REGULATOR_AWARE_TIMESTAMP_REQUIRED")
    return value.astimezone(UTC)
def _is_date(value: object) -> bool: return isinstance(value, date) and not isinstance(value, datetime)
def _date_text(value: date | None) -> str | None: return value.isoformat() if value else None
def _looks_serial(value: str) -> bool: return bool(re.fullmatch(r"\d+\.?", value.strip()))


__all__ = (
    "CONTRACT_ID", "CONTRACT_VERSION", "IRDAI_GENERAL_INSURERS_URL", "IRDAI_HEALTH_INSURERS_URL", "IRDAI_LIFE_INSURERS_URL",
    "RBI_CANCELLED_NBFC_ARC_XLSX_URL", "RBI_NBFC_LIST_URL", "RBI_REGISTERED_NBFC_ARC_XLSX_URL", "RBI_SCHEDULED_BANKS_URL",
    "IssuerLinkageStatus", "RegulatorCompanyTypeEvidenceError", "RegulatorCompanyTypeEvidenceStore", "RegulatorEntityEvidence",
    "RegulatorEntityEvidenceKind", "RegulatorEntityStatus", "RegulatorEvidenceBatch", "RegulatorEvidenceSource", "RegulatorEvidenceWriteOutcome",
    "RegulatorIssuerLinkAudit", "RegulatorSourceArtifact", "RegulatorTemporalStatus", "TaxonomyIssuerEvidenceAudit",
    "audit_exact_regulator_issuer_links", "audit_nse_taxonomy_issuer_evidence", "irdai_insurer_batch", "persist_regulator_evidence",
    "rbi_nbfc_arc_batch", "rbi_scheduled_bank_batch", "source_artifact_from_payload",
)
