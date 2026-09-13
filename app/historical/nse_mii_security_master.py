"""Bounded primary NSE CM-MII dated security-master acquisition.

The public MII file proves only that an exact security record appeared in the
exchange master labelled with a particular report date.  NSE documents that
members should load the daily file before trading, but the public artifact does
not supply a verifiable publication time.  This module therefore retains
date-level snapshot evidence and never promotes it to a PIT identity receipt.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import UTC, date, datetime
from enum import StrEnum
import gzip
from hashlib import sha256
from io import StringIO
import re
from typing import Iterable
from urllib.parse import urlsplit

import requests

from app.historical.guard import manifest_fingerprint
from app.storage.core_api_snapshot_repository import CoreApiSnapshot, CoreApiSnapshotFamily, CoreApiSnapshotRepository


CONTRACT_ID = "nse-historical-mii-security-master-snapshot-acquisition"
CONTRACT_VERSION = "v1"
# V1 date snapshots remain immutable historical evidence.  This additive
# version has a capture-specific identity so a later complete recovery of the
# same official file cannot overwrite, or silently turn, a previously retained
# partial V1 checkpoint into complete evidence.
PROSPECTIVE_CAPTURE_CONTRACT_VERSION = "v2-prospective-complete-capture"
NSE_MII_SECURITY_MASTER_BASE_URL = "https://nsearchives.nseindia.com/content/cm"
NSE_MII_SECURITY_MASTER_FILENAME = "NSE_CM_security_{date:%d%m%Y}.csv.gz"
NSE_MII_SECURITY_MASTER_SOURCE = "NSE_CM_MII_SECURITY_FILE"
_NSE_ARCHIVE_HOST = "nsearchives.nseindia.com"
_ISIN = re.compile(r"[A-Z]{2}[A-Z0-9]{9}[0-9]\Z")
_REQUIRED_COLUMNS = frozenset({
    "FinInstrmId", "TckrSymb", "SctySrs", "FinInstrmNm", "ISIN",
    "SctyStsNrmlMkt", "ListgDt", "RmvlDt", "FinInstrmTp", "SctyTp",
})


class NseMiiSecurityMasterError(ValueError):
    """A stable, non-secret failure at the strict public NSE boundary."""


class NseMiiAvailabilitySemantics(StrEnum):
    DOCUMENTED_PRE_TRADING_DATE_ONLY = "DOCUMENTED_PRE_TRADING_DATE_ONLY"


class NseMiiIngestionStatus(StrEnum):
    INSERTED = "INSERTED"
    ALREADY_PRESENT = "ALREADY_PRESENT"


class NseMiiCaptureCompleteness(StrEnum):
    COMPLETE = "COMPLETE"


@dataclass(frozen=True, slots=True)
class NseMiiSecurityMasterHttpResponse:
    """One successful fixed-path download; acquisition time is not PIT time."""

    requested_date: date
    source_reference: str
    content_type: str | None
    body: bytes
    document_observed_at: datetime
    declared_length: int | None = None
    transfer_complete: bool = True

    def __post_init__(self) -> None:
        if (
            not isinstance(self.requested_date, date)
            or not _is_expected_source(self.source_reference, self.requested_date)
            or not self.body
            or not _aware(self.document_observed_at)
            or (self.declared_length is not None and (not isinstance(self.declared_length, int) or self.declared_length < 0))
            or not isinstance(self.transfer_complete, bool)
            or not self.transfer_complete
            or (self.declared_length is not None and self.declared_length != len(self.body))
        ):
            raise NseMiiSecurityMasterError("NSE_HISTORICAL_MII_RESPONSE_INVALID")


class NseOfficialMiiSecurityMasterTransport:
    """One allowlisted official NSE archive request at a supplied date."""

    def __init__(self, *, session: requests.Session | None = None, timeout_seconds: int = 30) -> None:
        if timeout_seconds < 1 or timeout_seconds > 60:
            raise NseMiiSecurityMasterError("NSE_HISTORICAL_MII_TIMEOUT_INVALID")
        self._session = session or requests.Session()
        self._timeout_seconds = timeout_seconds

    def fetch(self, requested_date: date) -> NseMiiSecurityMasterHttpResponse:
        source_reference = nse_mii_security_master_url(requested_date)
        try:
            response = self._session.get(source_reference, headers={
                "Accept": "application/gzip,application/x-gzip,application/octet-stream,*/*",
                "Referer": "https://www.nseindia.com/all-reports",
                "User-Agent": "HSI-NSE-Stock-Manager/1.0 (official historical security master)",
            }, timeout=self._timeout_seconds)
        except requests.RequestException as error:
            raise NseMiiSecurityMasterError("NSE_HISTORICAL_MII_TRANSPORT_FAILED") from error
        if response.status_code == 404:
            raise NseMiiSecurityMasterError("NSE_HISTORICAL_MII_REPORT_UNAVAILABLE")
        if response.status_code != 200:
            raise NseMiiSecurityMasterError("NSE_HISTORICAL_MII_HTTP_FAILURE")
        return NseMiiSecurityMasterHttpResponse(
            requested_date=requested_date,
            source_reference=source_reference,
            content_type=response.headers.get("Content-Type"),
            body=response.content,
            document_observed_at=datetime.now(UTC),
            declared_length=_content_length(response.headers.get("Content-Length")),
            transfer_complete=True,
        )


@dataclass(frozen=True, slots=True)
class NseMiiSecurityMasterSnapshot:
    report_date: date
    source_reference: str
    expected_filename: str
    raw_file_fingerprint: str
    schema_fingerprint: str
    row_count: int
    rejected_rows: int
    document_observed_at: datetime
    availability_semantics: NseMiiAvailabilitySemantics = NseMiiAvailabilitySemantics.DOCUMENTED_PRE_TRADING_DATE_ONLY
    historical_known_at: None = None
    contract_id: str = CONTRACT_ID
    contract_version: str = CONTRACT_VERSION

    def __post_init__(self) -> None:
        if (
            not _is_expected_source(self.source_reference, self.report_date)
            or self.expected_filename != _filename(self.report_date)
            or not self.raw_file_fingerprint.startswith("sha256:")
            or not self.schema_fingerprint.startswith("sha256:")
            or self.row_count < 1
            or self.rejected_rows < 0
            or not _aware(self.document_observed_at)
            or self.availability_semantics is not NseMiiAvailabilitySemantics.DOCUMENTED_PRE_TRADING_DATE_ONLY
            or self.historical_known_at is not None
            or self.contract_id != CONTRACT_ID
            or self.contract_version not in {CONTRACT_VERSION, PROSPECTIVE_CAPTURE_CONTRACT_VERSION}
        ):
            raise NseMiiSecurityMasterError("NSE_HISTORICAL_MII_SNAPSHOT_INVALID")

    @property
    def snapshot_id(self) -> str:
        return "nse-mii-security-master:" + manifest_fingerprint(**_snapshot_identity(self))[:32]

    @property
    def fingerprint(self) -> str:
        return "sha256:" + manifest_fingerprint(**_snapshot_manifest(self))


@dataclass(frozen=True, slots=True)
class NseMiiSecurityMasterRow:
    snapshot_id: str
    report_date: date
    row_number: int
    symbol: str
    isin: str
    series: str | None
    security_code: str
    security_name: str
    normal_market_status_raw: str | None
    security_type_raw: str | None
    financial_instrument_type_raw: str | None
    listing_date_raw: str | None
    removal_date_raw: str | None
    raw_row_fingerprint: str
    document_observed_at: datetime
    historical_known_at: None = None
    contract_id: str = CONTRACT_ID
    contract_version: str = CONTRACT_VERSION

    def __post_init__(self) -> None:
        if (
            not self.snapshot_id.startswith("nse-mii-security-master:")
            or self.row_number < 2
            or not self.symbol
            or not _ISIN.fullmatch(self.isin)
            or not self.security_code
            or not self.security_name
            or not self.raw_row_fingerprint.startswith("sha256:")
            or not _aware(self.document_observed_at)
            or self.historical_known_at is not None
            or self.contract_id != CONTRACT_ID
            or self.contract_version not in {CONTRACT_VERSION, PROSPECTIVE_CAPTURE_CONTRACT_VERSION}
        ):
            raise NseMiiSecurityMasterError("NSE_HISTORICAL_MII_ROW_INVALID")

    @property
    def row_id(self) -> str:
        return "nse-mii-security-row:" + manifest_fingerprint(**_row_identity(self))[:32]

    @property
    def fingerprint(self) -> str:
        return "sha256:" + manifest_fingerprint(**_row_manifest(self))


@dataclass(frozen=True, slots=True)
class NseMiiSecurityMasterExtraction:
    snapshot: NseMiiSecurityMasterSnapshot
    rows: tuple[NseMiiSecurityMasterRow, ...]
    invalid_identity_rows: int
    fingerprint: str
    raw_captured_rows: int | None = None
    parsed_rows: int | None = None
    structural_rejected_rows: int | None = None
    bytes_received: int | None = None
    declared_length: int | None = None
    transfer_complete: bool | None = None

    def __post_init__(self) -> None:
        if (
            not self.rows
            or self.rows != tuple(sorted(self.rows, key=lambda value: value.row_number))
            or len({value.row_id for value in self.rows}) != len(self.rows)
            or self.invalid_identity_rows < 0
            or self.snapshot.row_count != len(self.rows)
            or self.snapshot.rejected_rows != self.invalid_identity_rows
            or self.fingerprint != "sha256:" + manifest_fingerprint(**_extraction_manifest(self))
        ):
            raise NseMiiSecurityMasterError("NSE_HISTORICAL_MII_EXTRACTION_INVALID")
        current = self.snapshot.contract_version == PROSPECTIVE_CAPTURE_CONTRACT_VERSION
        counters = (
            self.raw_captured_rows, self.parsed_rows, self.structural_rejected_rows,
            self.bytes_received, self.declared_length, self.transfer_complete,
        )
        if current and (
            not isinstance(self.raw_captured_rows, int) or self.raw_captured_rows < 1
            or self.parsed_rows != self.raw_captured_rows
            or self.structural_rejected_rows != 0
            or self.parsed_rows != len(self.rows) + self.invalid_identity_rows
            or not isinstance(self.bytes_received, int) or self.bytes_received < 1
            or (self.declared_length is not None and self.declared_length != self.bytes_received)
            or self.transfer_complete is not True
        ):
            raise NseMiiSecurityMasterError("NSE_HISTORICAL_MII_EXTRACTION_INVALID")
        if not current and any(value is not None for value in counters):
            raise NseMiiSecurityMasterError("NSE_HISTORICAL_MII_EXTRACTION_INVALID")


@dataclass(frozen=True, slots=True)
class NseMiiSecurityMasterIngestionReceipt:
    snapshot_id: str
    status: NseMiiIngestionStatus
    rows_inserted: int
    rows_already_present: int
    fingerprint: str

    def __post_init__(self) -> None:
        if (
            not self.snapshot_id.startswith("nse-mii-security-master:")
            or min(self.rows_inserted, self.rows_already_present) < 0
            or self.rows_inserted + self.rows_already_present < 1
            or self.fingerprint != "sha256:" + manifest_fingerprint(**_receipt_manifest(self))
        ):
            raise NseMiiSecurityMasterError("NSE_HISTORICAL_MII_RECEIPT_INVALID")


@dataclass(frozen=True, slots=True)
class NseMiiCurrentMasterCaptureReceipt:
    """Admission of one complete, current-capture MII file.

    The receipt is intentionally additive.  It binds a new prospective-capture
    snapshot to direct-file transfer and row coverage evidence; it never
    changes an earlier V1 partial checkpoint or creates a security identity.
    """

    snapshot_id: str
    snapshot_fingerprint: str
    report_date: date
    source_reference: str
    raw_file_fingerprint: str
    extraction_fingerprint: str
    source_declared_rows: None
    raw_captured_rows: int
    parsed_rows: int
    retained_rows: int
    canonical_eligible_rows: int
    structural_rejected_rows: int
    identity_ineligible_rows: int
    bytes_received: int
    declared_length: int | None
    transfer_complete: bool
    pagination_state: str
    first_observed_at: datetime
    completeness: NseMiiCaptureCompleteness
    contract_id: str = CONTRACT_ID
    contract_version: str = PROSPECTIVE_CAPTURE_CONTRACT_VERSION
    fingerprint: str = ""

    def __post_init__(self) -> None:
        if (
            not self.snapshot_id.startswith("nse-mii-security-master:")
            or not _fingerprint(self.snapshot_fingerprint)
            or not isinstance(self.report_date, date)
            or not _is_expected_source(self.source_reference, self.report_date)
            or not _fingerprint(self.raw_file_fingerprint)
            or not _fingerprint(self.extraction_fingerprint)
            or self.source_declared_rows is not None
            or min(self.raw_captured_rows, self.parsed_rows, self.retained_rows, self.canonical_eligible_rows,
                   self.structural_rejected_rows, self.identity_ineligible_rows, self.bytes_received) < 0
            or self.raw_captured_rows != self.parsed_rows
            or self.parsed_rows != self.canonical_eligible_rows + self.identity_ineligible_rows
            or self.retained_rows != self.canonical_eligible_rows
            or self.structural_rejected_rows != 0
            or self.bytes_received < 1
            or (self.declared_length is not None and self.declared_length != self.bytes_received)
            or not self.transfer_complete
            or self.pagination_state != "SINGLE_FILE_NO_PAGINATION"
            or not _aware(self.first_observed_at)
            or self.completeness is not NseMiiCaptureCompleteness.COMPLETE
            or self.contract_id != CONTRACT_ID
            or self.contract_version != PROSPECTIVE_CAPTURE_CONTRACT_VERSION
            or self.fingerprint != "sha256:" + manifest_fingerprint(**_current_capture_manifest(self))
        ):
            raise NseMiiSecurityMasterError("NSE_CURRENT_MASTER_CAPTURE_RECEIPT_INVALID")

    @property
    def receipt_id(self) -> str:
        return "nse-mii-current-master-capture:" + manifest_fingerprint(**_current_capture_identity(self))[:32]


class NseMiiSecurityMasterEvidenceStore:
    """Append-only date-level NSE security-master evidence; no identity promotion."""

    def __init__(self, repository: CoreApiSnapshotRepository) -> None:
        self._repository = repository

    def snapshot(self, snapshot_id: str) -> NseMiiSecurityMasterSnapshot | None:
        value = self._repository.get_snapshot(snapshot_id)
        return value.payload if value is not None and isinstance(value.payload, NseMiiSecurityMasterSnapshot) else None

    def row(self, row_id: str) -> NseMiiSecurityMasterRow | None:
        value = self._repository.get_snapshot(row_id)
        return value.payload if value is not None and isinstance(value.payload, NseMiiSecurityMasterRow) else None

    def current_capture_receipt(self, receipt_id: str) -> NseMiiCurrentMasterCaptureReceipt | None:
        value = self._repository.get_snapshot(receipt_id)
        return value.payload if value is not None and isinstance(value.payload, NseMiiCurrentMasterCaptureReceipt) else None

    def save(self, extraction: NseMiiSecurityMasterExtraction) -> NseMiiSecurityMasterIngestionReceipt:
        """Persist a complete extraction, resuming safely after an interruption."""
        return self.save_rows(extraction, offset=0, limit=len(extraction.rows))

    def save_rows(
        self, extraction: NseMiiSecurityMasterExtraction, *, offset: int, limit: int,
    ) -> NseMiiSecurityMasterIngestionReceipt:
        """Persist one deterministic row page while retaining the complete artifact.

        The public security file is large.  A bounded page makes each
        append-only checkpoint observable and lets an interrupted process
        resume without rewriting an artifact or creating a second snapshot.
        """
        if offset < 0 or limit < 1 or offset >= len(extraction.rows):
            raise NseMiiSecurityMasterError("NSE_HISTORICAL_MII_ROW_PAGE_INVALID")
        snapshot = extraction.snapshot
        existing_snapshot = self.snapshot(snapshot.snapshot_id)
        if existing_snapshot is not None and not _same_snapshot(existing_snapshot, snapshot):
            raise NseMiiSecurityMasterError("NSE_HISTORICAL_MII_SNAPSHOT_ID_COLLISION")
        if existing_snapshot is None:
            self._repository.save_snapshot(CoreApiSnapshot(
                snapshot.snapshot_id, CoreApiSnapshotFamily.HISTORICAL_NSE_SECURITY_MASTER_SNAPSHOT,
                "v1", _snapshot_record_type(snapshot), snapshot.fingerprint,
                snapshot.document_observed_at, snapshot,
            ))
        inserted = present = 0
        for row in extraction.rows[offset:offset + limit]:
            existing_row = self.row(row.row_id)
            if existing_row is None:
                self._repository.save_snapshot(CoreApiSnapshot(
                    row.row_id, CoreApiSnapshotFamily.HISTORICAL_NSE_SECURITY_MASTER_SNAPSHOT,
                    "v1", _row_record_type(row), row.fingerprint, row.document_observed_at, row,
                ))
                inserted += 1
            elif _same_row(existing_row, row):
                present += 1
            else:
                raise NseMiiSecurityMasterError("NSE_HISTORICAL_MII_ROW_ID_COLLISION")
        status = NseMiiIngestionStatus.INSERTED if inserted or existing_snapshot is None else NseMiiIngestionStatus.ALREADY_PRESENT
        return _receipt(snapshot.snapshot_id, status, inserted, present)

    def save_complete_current_capture(
        self, extraction: NseMiiSecurityMasterExtraction, *, page_size: int = 1000,
    ) -> NseMiiCurrentMasterCaptureReceipt:
        """Admit a complete V2 prospective capture after every row is durable.

        Pages are only bounded write checkpoints.  They cannot themselves
        produce a `COMPLETE` result: a receipt is written only after every
        deterministic row ID is present and matches the parsed source.
        """
        if (
            extraction.snapshot.contract_version != PROSPECTIVE_CAPTURE_CONTRACT_VERSION
            or page_size < 1
            or page_size > 5_000
        ):
            raise NseMiiSecurityMasterError("NSE_CURRENT_MASTER_CAPTURE_INPUT_INVALID")
        for offset in range(0, len(extraction.rows), page_size):
            self.save_rows(extraction, offset=offset, limit=min(page_size, len(extraction.rows) - offset))
        for row in extraction.rows:
            stored = self.row(row.row_id)
            if stored is None or not _same_row(stored, row):
                raise NseMiiSecurityMasterError("NSE_CURRENT_MASTER_CAPTURE_ROW_COVERAGE_INCOMPLETE")
        snapshot = self.snapshot(extraction.snapshot.snapshot_id)
        if snapshot is None or not _same_snapshot(snapshot, extraction.snapshot):
            raise NseMiiSecurityMasterError("NSE_CURRENT_MASTER_CAPTURE_SNAPSHOT_UNVERIFIED")
        receipt = _current_capture_receipt(extraction)
        existing = self.current_capture_receipt(receipt.receipt_id)
        if existing is not None:
            if existing != receipt:
                raise NseMiiSecurityMasterError("NSE_CURRENT_MASTER_CAPTURE_RECEIPT_COLLISION")
            return existing
        self._repository.save_snapshot(CoreApiSnapshot(
            receipt.receipt_id, CoreApiSnapshotFamily.HISTORICAL_NSE_SECURITY_MASTER_SNAPSHOT,
            "v1", "nse-mii-security-master-prospective-capture-receipt-v1",
            receipt.fingerprint, receipt.first_observed_at, receipt,
        ))
        return receipt

    def reopen_complete_current_capture(self, receipt_id: str) -> NseMiiCurrentMasterCaptureReceipt:
        """Validate durable admission without a network request or new clock read."""
        receipt = self.current_capture_receipt(receipt_id)
        if receipt is None:
            raise NseMiiSecurityMasterError("NSE_CURRENT_MASTER_CAPTURE_RECEIPT_REQUIRED")
        receipt.__post_init__()
        snapshot = self.snapshot(receipt.snapshot_id)
        if (
            snapshot is None
            or snapshot.contract_version != PROSPECTIVE_CAPTURE_CONTRACT_VERSION
            or snapshot.fingerprint != receipt.snapshot_fingerprint
            or snapshot.raw_file_fingerprint != receipt.raw_file_fingerprint
            or snapshot.report_date != receipt.report_date
            or snapshot.source_reference != receipt.source_reference
            or snapshot.document_observed_at != receipt.first_observed_at
            or snapshot.row_count != receipt.retained_rows
            or snapshot.rejected_rows != receipt.identity_ineligible_rows
        ):
            raise NseMiiSecurityMasterError("NSE_CURRENT_MASTER_CAPTURE_REOPEN_INVALID")
        return receipt


def nse_mii_security_master_url(report_date: date) -> str:
    if not isinstance(report_date, date):
        raise NseMiiSecurityMasterError("NSE_HISTORICAL_MII_REPORT_DATE_INVALID")
    return f"{NSE_MII_SECURITY_MASTER_BASE_URL}/{_filename(report_date)}"


def extract_nse_mii_security_master(
    response: NseMiiSecurityMasterHttpResponse, *, contract_version: str = CONTRACT_VERSION,
) -> NseMiiSecurityMasterExtraction:
    """Strictly parse one actual gzip/CSV NSE CM-MII artifact.

    The report date remains a date-only fact.  ``document_observed_at`` is
    persisted solely as local acquisition provenance and never as known time.
    """
    if contract_version not in {CONTRACT_VERSION, PROSPECTIVE_CAPTURE_CONTRACT_VERSION}:
        raise NseMiiSecurityMasterError("NSE_HISTORICAL_MII_CONTRACT_VERSION_INVALID")
    content_type = (response.content_type or "").split(";", 1)[0].strip().lower()
    if content_type and content_type not in {"application/gzip", "application/x-gzip", "application/octet-stream"}:
        raise NseMiiSecurityMasterError("NSE_HISTORICAL_MII_CONTENT_TYPE_INVALID")
    if response.body[:2] != b"\x1f\x8b":
        raise NseMiiSecurityMasterError("NSE_HISTORICAL_MII_GZIP_REQUIRED")
    try:
        text = gzip.decompress(response.body).decode("utf-8-sig")
    except (OSError, UnicodeDecodeError) as error:
        raise NseMiiSecurityMasterError("NSE_HISTORICAL_MII_GZIP_OR_TEXT_INVALID") from error
    reader = csv.DictReader(StringIO(text))
    header = tuple(reader.fieldnames or ())
    if not _REQUIRED_COLUMNS.issubset(set(header)):
        raise NseMiiSecurityMasterError("NSE_HISTORICAL_MII_REQUIRED_COLUMNS_MISSING")
    raw_file_fingerprint = "sha256:" + sha256(response.body).hexdigest()
    schema_fingerprint = "sha256:" + manifest_fingerprint(columns=header)
    provisional_snapshot = NseMiiSecurityMasterSnapshot(
        report_date=response.requested_date,
        source_reference=response.source_reference,
        expected_filename=_filename(response.requested_date),
        raw_file_fingerprint=raw_file_fingerprint,
        schema_fingerprint=schema_fingerprint,
        row_count=1,
        rejected_rows=0,
        document_observed_at=response.document_observed_at,
        contract_version=contract_version,
    )
    rows: list[NseMiiSecurityMasterRow] = []
    invalid_identity_rows = 0
    raw_captured_rows = 0
    for row_number, source_row in enumerate(reader, start=2):
        raw_captured_rows += 1
        row = {key: (value or "").strip() for key, value in source_row.items() if key is not None}
        parsed = _row_from_source(
            snapshot_id=provisional_snapshot.snapshot_id, report_date=response.requested_date,
            row_number=row_number, source_row=row, observed_at=response.document_observed_at,
            contract_version=contract_version,
        )
        if parsed is None:
            invalid_identity_rows += 1
        else:
            rows.append(parsed)
    if not rows:
        raise NseMiiSecurityMasterError("NSE_HISTORICAL_MII_NO_VALID_SECURITY_ROWS")
    snapshot = NseMiiSecurityMasterSnapshot(
        report_date=response.requested_date,
        source_reference=response.source_reference,
        expected_filename=_filename(response.requested_date),
        raw_file_fingerprint=raw_file_fingerprint,
        schema_fingerprint=schema_fingerprint,
        row_count=len(rows),
        rejected_rows=invalid_identity_rows,
        document_observed_at=response.document_observed_at,
        contract_version=contract_version,
    )
    # ``snapshot_id`` excludes counts, so the second validated artifact keeps
    # each row's deterministic identity and cannot introduce a circular hash.
    if snapshot.snapshot_id != provisional_snapshot.snapshot_id:
        raise AssertionError("NSE_HISTORICAL_MII_SNAPSHOT_IDENTITY_UNSTABLE")
    ordered = tuple(sorted(rows, key=lambda value: value.row_number))
    extraction = NseMiiSecurityMasterExtraction(
        snapshot=snapshot, rows=ordered, invalid_identity_rows=invalid_identity_rows,
        fingerprint="sha256:" + manifest_fingerprint(**_extraction_manifest_values(
            snapshot_id=snapshot.snapshot_id, row_ids=tuple(value.row_id for value in ordered),
            invalid_identity_rows=invalid_identity_rows, contract_version=contract_version,
            raw_captured_rows=raw_captured_rows, bytes_received=len(response.body),
            declared_length=response.declared_length, transfer_complete=response.transfer_complete,
        )),
        **({
            "raw_captured_rows": raw_captured_rows,
            "parsed_rows": raw_captured_rows,
            "structural_rejected_rows": 0,
            "bytes_received": len(response.body),
            "declared_length": response.declared_length,
            "transfer_complete": response.transfer_complete,
        } if contract_version == PROSPECTIVE_CAPTURE_CONTRACT_VERSION else {}),
    )
    return extraction


def rows_not_after_report_date(
    rows: Iterable[NseMiiSecurityMasterRow], *, as_of_date: date,
) -> tuple[NseMiiSecurityMasterRow, ...]:
    """A descriptive date boundary, never a substitute for known-at PIT."""
    if not isinstance(as_of_date, date):
        raise NseMiiSecurityMasterError("NSE_HISTORICAL_MII_AS_OF_DATE_INVALID")
    return tuple(sorted(
        (value for value in rows if value.report_date <= as_of_date),
        key=lambda value: (value.report_date, value.symbol, value.isin, value.row_id),
    ))


def same_isin_symbol_changes(rows: Iterable[NseMiiSecurityMasterRow]) -> tuple[tuple[str, tuple[str, ...]], ...]:
    """Report only exact observations; this function creates no continuity."""
    grouped: dict[str, set[str]] = {}
    for row in rows:
        grouped.setdefault(row.isin, set()).add(row.symbol)
    return tuple((isin, tuple(sorted(symbols))) for isin, symbols in sorted(grouped.items()) if len(symbols) > 1)


def exact_bse_delisted_isin_overlaps(
    rows: Iterable[NseMiiSecurityMasterRow], *, bse_delisted_isins: Iterable[str],
) -> tuple[str, ...]:
    """Identifier-only NSE/BSE cross-reference with no lifecycle inference."""
    bse = {value.strip().upper() for value in bse_delisted_isins if _ISIN.fullmatch(value.strip().upper())}
    return tuple(sorted({row.isin for row in rows if row.isin in bse}))


def _row_from_source(
    *, snapshot_id: str, report_date: date, row_number: int, source_row: dict[str, str], observed_at: datetime,
    contract_version: str,
) -> NseMiiSecurityMasterRow | None:
    symbol = source_row["TckrSymb"].upper()
    isin = source_row["ISIN"].upper()
    security_code = source_row["FinInstrmId"]
    security_name = source_row["FinInstrmNm"]
    if not symbol or not _ISIN.fullmatch(isin) or not security_code or not security_name:
        return None
    raw_row_fingerprint = "sha256:" + manifest_fingerprint(columns=tuple(sorted(source_row.items())))
    return NseMiiSecurityMasterRow(
        snapshot_id=snapshot_id, report_date=report_date, row_number=row_number,
        symbol=symbol, isin=isin, series=_none(source_row["SctySrs"]), security_code=security_code,
        security_name=security_name, normal_market_status_raw=_none(source_row["SctyStsNrmlMkt"]),
        security_type_raw=_none(source_row["SctyTp"]), financial_instrument_type_raw=_none(source_row["FinInstrmTp"]),
        listing_date_raw=_none(source_row["ListgDt"]), removal_date_raw=_none(source_row["RmvlDt"]),
        raw_row_fingerprint=raw_row_fingerprint, document_observed_at=observed_at,
        contract_version=contract_version,
    )


def _filename(report_date: date) -> str:
    return NSE_MII_SECURITY_MASTER_FILENAME.format(date=report_date)


def _is_expected_source(value: str, report_date: date) -> bool:
    parsed = urlsplit(value)
    return (
        parsed.scheme == "https" and parsed.hostname == _NSE_ARCHIVE_HOST and not parsed.query and not parsed.fragment
        and parsed.path == f"/content/cm/{_filename(report_date)}"
    )


def _snapshot_identity(value: NseMiiSecurityMasterSnapshot) -> dict[str, str]:
    values = {
        "report_date": value.report_date.isoformat(), "source_reference": value.source_reference,
        "raw_file_fingerprint": value.raw_file_fingerprint, "schema_fingerprint": value.schema_fingerprint,
        "contract_id": value.contract_id, "contract_version": value.contract_version,
    }
    if value.contract_version == PROSPECTIVE_CAPTURE_CONTRACT_VERSION:
        # A later recovery of identical bytes has a distinct immutable capture
        # identity and must not rewrite a prior partial checkpoint.
        values["first_observed_at"] = value.document_observed_at.astimezone(UTC).isoformat()
    return values


def _snapshot_manifest(value: NseMiiSecurityMasterSnapshot) -> dict[str, object]:
    return _snapshot_identity(value) | {
        "expected_filename": value.expected_filename, "row_count": value.row_count,
        "rejected_rows": value.rejected_rows, "document_observed_at": value.document_observed_at.isoformat(),
        "availability_semantics": value.availability_semantics.value, "historical_known_at": None,
    }


def _row_identity(value: NseMiiSecurityMasterRow) -> dict[str, object]:
    return {
        "snapshot_id": value.snapshot_id, "row_number": value.row_number, "report_date": value.report_date.isoformat(),
        "raw_row_fingerprint": value.raw_row_fingerprint, "contract_id": value.contract_id, "contract_version": value.contract_version,
    }


def _row_manifest(value: NseMiiSecurityMasterRow) -> dict[str, object]:
    return _row_identity(value) | {
        "symbol": value.symbol, "isin": value.isin, "series": value.series, "security_code": value.security_code,
        "security_name": value.security_name, "normal_market_status_raw": value.normal_market_status_raw,
        "security_type_raw": value.security_type_raw, "financial_instrument_type_raw": value.financial_instrument_type_raw,
        "listing_date_raw": value.listing_date_raw, "removal_date_raw": value.removal_date_raw,
        "document_observed_at": value.document_observed_at.isoformat(), "historical_known_at": None,
    }


def _extraction_manifest(value: NseMiiSecurityMasterExtraction) -> dict[str, object]:
    return _extraction_manifest_values(
        snapshot_id=value.snapshot.snapshot_id, row_ids=tuple(item.row_id for item in value.rows),
        invalid_identity_rows=value.invalid_identity_rows,
        contract_version=value.snapshot.contract_version,
        raw_captured_rows=value.raw_captured_rows,
        bytes_received=value.bytes_received,
        declared_length=value.declared_length,
        transfer_complete=value.transfer_complete,
    )


def _extraction_manifest_values(
    *, snapshot_id: str, row_ids: tuple[str, ...], invalid_identity_rows: int,
    contract_version: str, raw_captured_rows: int | None, bytes_received: int | None,
    declared_length: int | None, transfer_complete: bool | None,
) -> dict[str, object]:
    result: dict[str, object] = {
        "snapshot_id": snapshot_id, "row_ids": row_ids,
        "invalid_identity_rows": invalid_identity_rows,
    }
    if contract_version == PROSPECTIVE_CAPTURE_CONTRACT_VERSION:
        result.update(
            raw_captured_rows=raw_captured_rows, parsed_rows=raw_captured_rows,
            structural_rejected_rows=0, bytes_received=bytes_received,
            declared_length=declared_length, transfer_complete=transfer_complete,
        )
    return result


def _receipt(snapshot_id: str, status: NseMiiIngestionStatus, inserted: int, present: int) -> NseMiiSecurityMasterIngestionReceipt:
    fingerprint = "sha256:" + manifest_fingerprint(
        snapshot_id=snapshot_id, status=status.value, rows_inserted=inserted, rows_already_present=present,
    )
    return NseMiiSecurityMasterIngestionReceipt(snapshot_id, status, inserted, present, fingerprint)


def _receipt_manifest(value: NseMiiSecurityMasterIngestionReceipt) -> dict[str, object]:
    return {
        "snapshot_id": value.snapshot_id, "status": value.status.value,
        "rows_inserted": value.rows_inserted, "rows_already_present": value.rows_already_present,
    }


def _same_snapshot(left: NseMiiSecurityMasterSnapshot, right: NseMiiSecurityMasterSnapshot) -> bool:
    return _snapshot_identity(left) == _snapshot_identity(right) and (
        left.expected_filename, left.row_count, left.rejected_rows, left.availability_semantics,
    ) == (
        right.expected_filename, right.row_count, right.rejected_rows, right.availability_semantics,
    )


def _same_row(left: NseMiiSecurityMasterRow, right: NseMiiSecurityMasterRow) -> bool:
    return _row_identity(left) == _row_identity(right) and (
        left.symbol, left.isin, left.series, left.security_code, left.security_name,
        left.normal_market_status_raw, left.security_type_raw, left.financial_instrument_type_raw,
        left.listing_date_raw, left.removal_date_raw,
    ) == (
        right.symbol, right.isin, right.series, right.security_code, right.security_name,
        right.normal_market_status_raw, right.security_type_raw, right.financial_instrument_type_raw,
        right.listing_date_raw, right.removal_date_raw,
    )


def _none(value: str) -> str | None:
    return value or None


def _aware(value: datetime) -> bool:
    return value.tzinfo is not None and value.utcoffset() is not None


def _content_length(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError) as error:
        raise NseMiiSecurityMasterError("NSE_HISTORICAL_MII_CONTENT_LENGTH_INVALID") from error
    if parsed < 0:
        raise NseMiiSecurityMasterError("NSE_HISTORICAL_MII_CONTENT_LENGTH_INVALID")
    return parsed


def _fingerprint(value: str) -> bool:
    return bool(re.fullmatch(r"sha256:[0-9a-f]{64}", value))


def _snapshot_record_type(value: NseMiiSecurityMasterSnapshot) -> str:
    return (
        CONTRACT_ID if value.contract_version == CONTRACT_VERSION
        else "nse-mii-security-master-prospective-snapshot-v2"
    )


def _row_record_type(value: NseMiiSecurityMasterRow) -> str:
    return (
        "nse-mii-security-master-row-v1" if value.contract_version == CONTRACT_VERSION
        else "nse-mii-security-master-prospective-row-v2"
    )


def _current_capture_identity(value: NseMiiCurrentMasterCaptureReceipt) -> dict[str, object]:
    return {
        "snapshot_id": value.snapshot_id,
        "snapshot_fingerprint": value.snapshot_fingerprint,
        "raw_file_fingerprint": value.raw_file_fingerprint,
        "extraction_fingerprint": value.extraction_fingerprint,
        "report_date": value.report_date.isoformat(),
        "source_reference": value.source_reference,
        "first_observed_at": value.first_observed_at.astimezone(UTC).isoformat(),
        "contract_id": value.contract_id,
        "contract_version": value.contract_version,
    }


def _current_capture_manifest(value: NseMiiCurrentMasterCaptureReceipt) -> dict[str, object]:
    return _current_capture_identity(value) | {
        "source_declared_rows": None,
        "raw_captured_rows": value.raw_captured_rows,
        "parsed_rows": value.parsed_rows,
        "retained_rows": value.retained_rows,
        "canonical_eligible_rows": value.canonical_eligible_rows,
        "structural_rejected_rows": value.structural_rejected_rows,
        "identity_ineligible_rows": value.identity_ineligible_rows,
        "bytes_received": value.bytes_received,
        "declared_length": value.declared_length,
        "transfer_complete": value.transfer_complete,
        "pagination_state": value.pagination_state,
        "completeness": value.completeness.value,
    }


def _current_capture_manifest_values(value: dict[str, object]) -> dict[str, object]:
    return {
        "snapshot_id": value["snapshot_id"],
        "snapshot_fingerprint": value["snapshot_fingerprint"],
        "raw_file_fingerprint": value["raw_file_fingerprint"],
        "extraction_fingerprint": value["extraction_fingerprint"],
        "report_date": value["report_date"].isoformat(),
        "source_reference": value["source_reference"],
        "first_observed_at": value["first_observed_at"].astimezone(UTC).isoformat(),
        "contract_id": CONTRACT_ID,
        "contract_version": PROSPECTIVE_CAPTURE_CONTRACT_VERSION,
        "source_declared_rows": None,
        "raw_captured_rows": value["raw_captured_rows"],
        "parsed_rows": value["parsed_rows"],
        "retained_rows": value["retained_rows"],
        "canonical_eligible_rows": value["canonical_eligible_rows"],
        "structural_rejected_rows": value["structural_rejected_rows"],
        "identity_ineligible_rows": value["identity_ineligible_rows"],
        "bytes_received": value["bytes_received"],
        "declared_length": value["declared_length"],
        "transfer_complete": value["transfer_complete"],
        "pagination_state": value["pagination_state"],
        "completeness": value["completeness"].value,
    }


def _current_capture_receipt(value: NseMiiSecurityMasterExtraction) -> NseMiiCurrentMasterCaptureReceipt:
    snapshot = value.snapshot
    fields = dict(
        snapshot_id=snapshot.snapshot_id,
        snapshot_fingerprint=snapshot.fingerprint,
        report_date=snapshot.report_date,
        source_reference=snapshot.source_reference,
        raw_file_fingerprint=snapshot.raw_file_fingerprint,
        extraction_fingerprint=value.fingerprint,
        source_declared_rows=None,
        raw_captured_rows=value.raw_captured_rows,
        parsed_rows=value.parsed_rows,
        retained_rows=len(value.rows),
        canonical_eligible_rows=len(value.rows),
        structural_rejected_rows=value.structural_rejected_rows,
        identity_ineligible_rows=value.invalid_identity_rows,
        bytes_received=value.bytes_received,
        declared_length=value.declared_length,
        transfer_complete=value.transfer_complete,
        pagination_state="SINGLE_FILE_NO_PAGINATION",
        first_observed_at=snapshot.document_observed_at,
        completeness=NseMiiCaptureCompleteness.COMPLETE,
    )
    return NseMiiCurrentMasterCaptureReceipt(
        **fields, fingerprint="sha256:" + manifest_fingerprint(**_current_capture_manifest_values(fields)),
    )


__all__ = (
    "CONTRACT_ID", "CONTRACT_VERSION", "PROSPECTIVE_CAPTURE_CONTRACT_VERSION", "NseMiiAvailabilitySemantics",
    "NseMiiCaptureCompleteness", "NseMiiIngestionStatus",
    "NseMiiSecurityMasterError", "NseMiiSecurityMasterEvidenceStore", "NseMiiSecurityMasterExtraction",
    "NseMiiSecurityMasterHttpResponse", "NseMiiSecurityMasterIngestionReceipt", "NseMiiCurrentMasterCaptureReceipt", "NseMiiSecurityMasterRow",
    "NseMiiSecurityMasterSnapshot", "NseOfficialMiiSecurityMasterTransport", "exact_bse_delisted_isin_overlaps",
    "extract_nse_mii_security_master", "nse_mii_security_master_url", "rows_not_after_report_date",
    "same_isin_symbol_changes",
)
