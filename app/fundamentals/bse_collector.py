"""Bounded official-BSE financial evidence acquisition for the five live holdings.

This module is an acquisition and provenance boundary only.  It resolves an
exact ISIN from the official BSE master, stages an official XBRL immutably, and
delegates all financial interpretation and canonical writes to the existing
local BSE XBRL importer.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from enum import StrEnum
from hashlib import sha256
from html.parser import HTMLParser
from io import BytesIO, StringIO
import json
import os
from pathlib import Path
import re
import tempfile
from threading import Event, Thread
from typing import Callable, Protocol
from urllib.parse import parse_qs, urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener, urlopen
from zipfile import BadZipFile, ZipFile
import xml.etree.ElementTree as ET

from app.data_operations.models import (
    EvidenceRefreshFailureKind, EvidenceRefreshOutcome, EvidenceRefreshRequest,
    EvidenceRefreshStatus, ReconciliationStatus,
)
from app.filings.store import CorporateFilingsStore
from app.fundamentals.bse_official import (
    BSE_OFFICIAL_PROVIDER, BSEOfficialFinancialResultsArchiveProvider, BSEOfficialFinancialResultsProvider,
    BSEOfficialLocalXbrlIngestionService, BseOfficialError, BseResultMetadata,
    BseResultMetadataAliases,
    parse_bse_xbrl,
)
from app.fundamentals.models import FinancialPeriodType, FinancialValueBasis, StatementScope
from app.fundamentals.store import FinancialFactStore
from app.market_data.models import Exchange, InstrumentIdentity, InstrumentType
from app.universe_analysis.models import NseEquityInstrument
from app.universe_analysis.service import CoreUniverseAnalysisStore


REAL_PORTFOLIO_BSE_FINANCIAL_TARGETS = (
    "NSE:INE372A01015", "NSE:INE0FHS01024", "NSE:INE955D01029",
    "NSE:INE068V01023", "NSE:INE090A01021",
)
# This is an explicit approved non-financial acquisition scope, not a sector
# or business-model classification. Financial institutions remain outside the
# annual Compounder evidence path.
COMPOUNDER_NON_FINANCIAL_BSE_HISTORICAL_TARGETS = (
    "NSE:INE372A01015", "NSE:INE955D01029", "NSE:INE068V01023",
    "NSE:INE0FHS01024",
)
_HISTORICAL_ANNUAL_PERIODS_PER_SCOPE = 5
_ICICI_BOUNDED_XBRL_DOCUMENTS = frozenset({
    "https://www.bseindia.com/XBRLFILES/IFBankingUploadDocument/IFBanking_532174_1942025184029.xml",
    "https://www.bseindia.com/XBRLFILES/IFBankingUploadDocument/IFBanking_532174_1810202517245.xml",
    "https://www.bseindia.com/XBRLFILES/IFBankingUploadDocument/IFBanking_532174_28042026113249.xml",
})
BSE_OFFICIAL_SCRIP_MASTER_URL = "https://www.bseindia.com/downloads1/SCRIP.ZIP"
_BSE_HOST = "www.bseindia.com"
_BSE_API_HOST = "api.bseindia.com"
BSE_OFFICIAL_EXACT_ISIN_LOOKUP_URL = "https://api.bseindia.com/BseIndiaAPI/api/PeerSmartSearch/w?Type=SS&text={isin}"
BSE_OFFICIAL_RESULTS_ARCHIVE_URL = "https://api.bseindia.com/BseIndiaAPI/api/Result_Arch_Download/w?scrip_cd={security_code}"
BSE_OFFICIAL_NOTICE_URL = "https://www.bseindia.com/markets/MarketInfo/DispNewNoticesCirculars.aspx?page={notice_id}"
BSE_OFFICIAL_COMPULSORY_DELISTED_URL = "https://www.bseindia.com/downloads1/comp_delisted_cos_db.pdf"
_MAX_XBRL_BYTES = 5 * 1024 * 1024
_MAX_MASTER_BYTES = 20 * 1024 * 1024
_MAX_LOOKUP_BYTES = 256 * 1024
_MAX_RESULTS_ARCHIVE_BYTES = 2 * 1024 * 1024
_BSE_XBRL_STREAM_CHUNK_BYTES = 64 * 1024
# Audit streaming is deliberately separate from the production policy.  It is
# only used to measure a known BSE XBRL safely before selecting the final cap.
_BSE_XBRL_AUDIT_MAX_BYTES = 16 * 1024 * 1024
_BSE_XBRL_PRODUCTION_MAX_BYTES = 8 * 1024 * 1024


class BseCollectorError(ValueError):
    """Safe source, identity, or staging rejection."""


class BseMappingStatus(StrEnum):
    EXACT = "EXACT"
    NOT_FOUND = "NOT_FOUND"
    AMBIGUOUS = "AMBIGUOUS"
    CONFLICTED = "CONFLICTED"
    BLOCKED = "BLOCKED"


class BseStageDisposition(StrEnum):
    NEW = "NEW"
    EXISTING_UNCHANGED = "EXISTING_UNCHANGED"
    NEW_VERSION = "NEW_VERSION"
    CONFLICT = "CONFLICT"
    NOT_AVAILABLE = "NOT_AVAILABLE"
    BLOCKED = "BLOCKED"


class BseFilingDisposition(StrEnum):
    """One auditable outcome for one official BSE archive/XBRL entry."""

    IMPORTED = "IMPORTED"
    XBRL_PERIOD_METADATA_CONFLICT = "XBRL_PERIOD_METADATA_CONFLICT"
    XBRL_IDENTITY_MISMATCH = "XBRL_IDENTITY_MISMATCH"
    XBRL_SCOPE_METADATA_CONFLICT = "XBRL_SCOPE_METADATA_CONFLICT"
    XBRL_FETCH_FAILED = "XBRL_FETCH_FAILED"
    XBRL_DOCUMENT_TOO_LARGE = "XBRL_DOCUMENT_TOO_LARGE"
    OFFICIAL_RESPONSE_NOT_XBRL = "OFFICIAL_RESPONSE_NOT_XBRL"
    MALFORMED_XBRL = "MALFORMED_XBRL"
    SOURCE_METADATA_TIMESTAMP_UNSUPPORTED = "SOURCE_METADATA_TIMESTAMP_UNSUPPORTED"
    UNCLASSIFIED_REJECTION = "UNCLASSIFIED_REJECTION"


@dataclass(frozen=True, slots=True)
class BseOfficialHttpResponse:
    url: str
    content_type: str | None
    body: bytes
    received_at: datetime


@dataclass(frozen=True, slots=True)
class BseXbrlStreamingPolicy:
    """Finite, BSE-XBRL-only byte policy; it never changes generic fetches."""

    production_max_bytes: int = _BSE_XBRL_PRODUCTION_MAX_BYTES
    audit_max_bytes: int = _BSE_XBRL_AUDIT_MAX_BYTES
    chunk_size_bytes: int = _BSE_XBRL_STREAM_CHUNK_BYTES

    def __post_init__(self) -> None:
        if self.production_max_bytes < _MAX_XBRL_BYTES or self.audit_max_bytes < self.production_max_bytes:
            raise ValueError("BSE_XBRL_STREAMING_LIMIT_INVALID")
        if not 4 * 1024 <= self.chunk_size_bytes <= 1024 * 1024:
            raise ValueError("BSE_XBRL_STREAMING_CHUNK_INVALID")


@dataclass(frozen=True, slots=True)
class BseQuarantinedXbrl:
    """Validated, non-canonical bytes awaiting atomic hash-addressed promotion."""

    path: Path
    source_url: str
    content_type: str | None
    byte_length: int
    sha256: str
    received_at: datetime


@dataclass(frozen=True, slots=True)
class BseBoundedXbrlRecoveryReceipt:
    document_identifier: str
    byte_length: int
    sha256: str
    content_type: str | None
    final_url: str
    stage: BseStagedXbrl | None
    audit_only: bool


@dataclass(frozen=True, slots=True)
class BseArchiveSnapshot:
    snapshot_id: str
    canonical_instrument_id: str
    isin: str
    security_code: str
    endpoint: str
    retrieved_at: datetime
    content_type: str | None
    byte_length: int
    raw_sha256: str
    parsed_row_count: int
    parsed_rows_fingerprint: str
    path: Path
    sidecar_path: Path


@dataclass(frozen=True, slots=True)
class BseSecurityCandidate:
    isin: str
    security_code: str
    security_id: str | None
    security_name: str | None
    source_reference: str
    retrieved_at: datetime


@dataclass(frozen=True, slots=True)
class BseSecurityMapping:
    canonical_instrument_id: str
    isin: str
    status: BseMappingStatus
    security_code: str | None
    security_id: str | None
    security_name: str | None
    source_reference: str
    retrieved_at: datetime
    fingerprint: str
    reason: str | None = None
    source_type: str = "BSE_STANDARDIZED_SECURITY_MASTER"
    source_master_date: date | None = None


@dataclass(frozen=True, slots=True)
class BseStagedXbrl:
    path: Path
    sidecar_path: Path
    disposition: BseStageDisposition
    sha256: str
    byte_length: int
    source_reference: str
    published_at: datetime
    received_at: datetime


@dataclass(frozen=True, slots=True)
class BseFilingDispositionRecord:
    """Metadata-only audit record; it never retains raw document content."""

    metadata: BseResultMetadata
    disposition: BseFilingDisposition
    detail: str | None = None
    staged: BseStageDisposition | None = None


@dataclass(frozen=True, slots=True)
class BseFinancialCollectorTargetReceipt:
    canonical_instrument_id: str
    isin: str | None
    mapping: BseSecurityMapping
    filings_discovered: int
    new_filings: int
    unchanged_filings: int
    conflicting_filings: int
    xbrls_downloaded: int
    xbrls_already_present: int
    import_attempts: int
    canonical_facts_accepted: int
    canonical_facts_unchanged: int
    financial_conflicts: int
    latest_published_at: datetime | None
    latest_fiscal_period: datetime | None
    blockers: tuple[str, ...] = ()
    filing_dispositions: tuple[BseFilingDispositionRecord, ...] = ()


@dataclass(frozen=True, slots=True)
class BseFinancialCollectorRun:
    run_id: str
    requested_as_of: datetime
    receipts: tuple[BseFinancialCollectorTargetReceipt, ...]


@dataclass(frozen=True, slots=True)
class BseFinancialRefreshRequest:
    """Future external-event trigger: identity only, never a URL or facts."""

    canonical_instrument_id: str
    requested_at: datetime
    reason: str = "FINANCIAL_REFRESH_REQUIRED"

    def __post_init__(self) -> None:
        if self.canonical_instrument_id not in REAL_PORTFOLIO_BSE_FINANCIAL_TARGETS:
            raise ValueError("BSE_FINANCIAL_REFRESH_TARGET_NOT_APPROVED")
        if self.requested_at.tzinfo is None or self.requested_at.utcoffset() is None:
            raise ValueError("BSE_FINANCIAL_REFRESH_TIMESTAMP_REQUIRED")
        if self.reason != "FINANCIAL_REFRESH_REQUIRED":
            raise ValueError("BSE_FINANCIAL_REFRESH_REASON_INVALID")


class BseOfficialHttpTransport:
    """Small allowlisted BSE fetcher; it never follows trust outside BSE."""

    def __init__(self, *, fetch: Callable[[str, int], BseOfficialHttpResponse] | None = None,
                 clock: Callable[[], datetime] = lambda: datetime.now(UTC)) -> None:
        self._fetch = fetch or self._https_fetch
        self._clock = clock

    def fetch_master(self) -> BseOfficialHttpResponse:
        return self._request(BSE_OFFICIAL_SCRIP_MASTER_URL, _MAX_MASTER_BYTES, kind="master")

    def fetch_xbrl(self, url: str) -> BseOfficialHttpResponse:
        return self._request(url, _MAX_XBRL_BYTES, kind="xbrl")

    def fetch_isin_lookup(self, isin: str) -> BseOfficialHttpResponse:
        if not re.fullmatch(r"[A-Z0-9]{12}", isin.upper()):
            raise BseCollectorError("BSE_EXACT_ISIN_LOOKUP_INVALID")
        return self._request(BSE_OFFICIAL_EXACT_ISIN_LOOKUP_URL.format(isin=isin.upper()), _MAX_LOOKUP_BYTES, kind="isin-lookup")

    def fetch_results_archive(self, url: str) -> str:
        response = self.fetch_results_archive_response(url)
        try:
            return response.body.decode("utf-8-sig")
        except UnicodeDecodeError as error:
            raise BseCollectorError("BSE_OFFICIAL_RESPONSE_NOT_UTF8") from error

    def fetch_results_archive_response(self, url: str) -> BseOfficialHttpResponse:
        return self._request(url, _MAX_RESULTS_ARCHIVE_BYTES, kind="results-archive")

    def fetch_lifecycle_notice(self, notice_id: str) -> BseOfficialHttpResponse:
        if not re.fullmatch(r"\d{8}-\d{1,3}", notice_id):
            raise BseCollectorError("BSE_LIFECYCLE_NOTICE_IDENTIFIER_INVALID")
        return self._request(BSE_OFFICIAL_NOTICE_URL.format(notice_id=notice_id), _MAX_RESULTS_ARCHIVE_BYTES, kind="lifecycle-notice")

    def fetch_compulsory_delisted_list(self) -> BseOfficialHttpResponse:
        return self._request(BSE_OFFICIAL_COMPULSORY_DELISTED_URL, _MAX_RESULTS_ARCHIVE_BYTES, kind="compulsory-delisted-list")

    def fetch_text(self, url: str) -> str:
        response = self._request(url, _MAX_XBRL_BYTES, kind="result-or-xbrl")
        try:
            return response.body.decode("utf-8-sig")
        except UnicodeDecodeError as error:
            raise BseCollectorError("BSE_OFFICIAL_RESPONSE_NOT_UTF8") from error

    def _request(self, url: str, maximum: int, *, kind: str) -> BseOfficialHttpResponse:
        _validate_bse_url(url, kind=kind)
        response = self._fetch(url, maximum)
        _validate_bse_url(response.url, kind=kind)
        if len(response.body) > maximum:
            raise BseCollectorError("BSE_OFFICIAL_RESPONSE_TOO_LARGE")
        _validate_content_type(response.content_type, kind=kind)
        return response

    def _https_fetch(self, url: str, maximum: int) -> BseOfficialHttpResponse:
        try:
            request = Request(url, headers={
                "Accept": "application/json, text/plain, text/html, application/xml, application/zip, */*",
                "Accept-Language": "en-US,en;q=0.9",
                "Origin": "https://www.bseindia.com",
                "Referer": "https://www.bseindia.com/",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36",
            }, method="GET")
            with urlopen(request, timeout=20) as response:  # nosec B310 - validated BSE-only URL
                body = response.read(maximum + 1)
                return BseOfficialHttpResponse(
                    response.geturl(), response.headers.get_content_type(), body, self._clock(),
                )
        except OSError as error:
            raise BseCollectorError("BSE_OFFICIAL_SOURCE_UNAVAILABLE") from error


class _BseXbrlRedirectHandler(HTTPRedirectHandler):
    """Reject a redirect before urllib can send a follow-up outside BSE."""

    def redirect_request(self, request, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        _validate_bse_url(newurl, kind="xbrl")
        return super().redirect_request(request, fp, code, msg, headers, newurl)


class BseOfficialBoundedXbrlAcquirer:
    """Stream one pre-authorised official BSE XBRL into non-canonical quarantine.

    Callers must provide the collector's exact mapping and BSE archive metadata;
    this is intentionally not a generic URL downloader.
    """

    def __init__(
        self,
        *,
        quarantine_root: Path,
        policy: BseXbrlStreamingPolicy = BseXbrlStreamingPolicy(),
        open_stream: Callable[[str], object] | None = None,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._quarantine_root, self._policy = quarantine_root, policy
        self._open_stream, self._clock = open_stream or self._https_open_stream, clock

    def acquire(self, *, mapping: BseSecurityMapping, metadata: BseResultMetadata) -> BseQuarantinedXbrl:
        return self._stream(mapping=mapping, metadata=metadata, maximum=self._policy.production_max_bytes)

    def audit_acquire(self, *, mapping: BseSecurityMapping, metadata: BseResultMetadata) -> BseQuarantinedXbrl:
        """Bounded measurement only; callers must promote separately after review."""
        return self._stream(mapping=mapping, metadata=metadata, maximum=self._policy.audit_max_bytes)

    def discard(self, value: BseQuarantinedXbrl) -> None:
        try:
            value.path.unlink(missing_ok=True)
        except OSError as error:
            raise BseCollectorError("BSE_XBRL_QUARANTINE_CLEANUP_FAILED") from error

    def _stream(self, *, mapping: BseSecurityMapping, metadata: BseResultMetadata, maximum: int) -> BseQuarantinedXbrl:
        if mapping.status is not BseMappingStatus.EXACT or mapping.security_code != metadata.security_code:
            raise BseCollectorError("BSE_XBRL_STAGING_IDENTITY_NOT_EXACT")
        _validate_bse_url(metadata.xbrl_url, kind="xbrl")
        self._quarantine_root.mkdir(parents=True, exist_ok=True)
        handle, raw_path = tempfile.mkstemp(prefix="bse-xbrl-", suffix=".part", dir=self._quarantine_root)
        path = Path(raw_path)
        total, digest = 0, sha256()
        try:
            with os.fdopen(handle, "wb") as target:
                try:
                    with self._open_stream(metadata.xbrl_url) as response:  # type: ignore[union-attr]
                        status = getattr(response, "status", getattr(response, "code", None))
                        if status is None or not 200 <= int(status) < 300:
                            raise BseCollectorError("BSE_OFFICIAL_HTTP_STATUS_REJECTED")
                        final_url = response.geturl() if hasattr(response, "geturl") else getattr(response, "url", metadata.xbrl_url)
                        _validate_bse_url(final_url, kind="xbrl")
                        headers = getattr(response, "headers", None)
                        content_type = (
                            headers.get_content_type() if headers is not None and hasattr(headers, "get_content_type")
                            else headers.get("Content-Type") if headers is not None else None
                        )
                        _validate_content_type(content_type, kind="xbrl")
                        while True:
                            chunk = response.read(self._policy.chunk_size_bytes)
                            if not chunk:
                                break
                            if len(chunk) > self._policy.chunk_size_bytes:
                                raise BseCollectorError("BSE_XBRL_STREAM_CHUNK_BOUND_VIOLATION")
                            total += len(chunk)
                            if total > maximum:
                                raise BseCollectorError("BSE_OFFICIAL_RESPONSE_TOO_LARGE")
                            digest.update(chunk)
                            target.write(chunk)
                except OSError as error:
                    raise BseCollectorError("BSE_OFFICIAL_SOURCE_UNAVAILABLE") from error
            if total == 0:
                raise BseCollectorError("BSE_OFFICIAL_RESPONSE_EMPTY")
            self._validate_quarantined(path, mapping=mapping, metadata=metadata, source_url=final_url)
            return BseQuarantinedXbrl(path, final_url, content_type, total, digest.hexdigest(), self._clock())
        except Exception:
            path.unlink(missing_ok=True)
            raise

    def _https_open_stream(self, url: str):  # type: ignore[no-untyped-def]
        request = Request(url, headers={
            "Accept": "application/xml,text/xml,application/octet-stream;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Origin": "https://www.bseindia.com",
            "Referer": "https://www.bseindia.com/",
            "User-Agent": "nse-stock-manager/1.0",
        }, method="GET")
        try:
            return build_opener(_BseXbrlRedirectHandler()).open(request, timeout=30)
        except OSError as error:
            raise BseCollectorError("BSE_OFFICIAL_SOURCE_UNAVAILABLE") from error

    @staticmethod
    def _validate_quarantined(path: Path, *, mapping: BseSecurityMapping, metadata: BseResultMetadata, source_url: str) -> None:
        try:
            prefix = path.read_bytes()
        except OSError as error:
            raise BseCollectorError("BSE_XBRL_QUARANTINE_UNAVAILABLE") from error
        leading = prefix[:4096].lstrip().lower()
        if b"<html" in leading or b"<!doctype html" in leading or b"<!doctype" in leading:
            raise BseCollectorError("BSE_OFFICIAL_XBRL_SIGNATURE_INVALID")
        try:
            root = ET.fromstring(prefix)
        except (UnicodeDecodeError, ET.ParseError) as error:
            raise BseCollectorError("BSE_OFFICIAL_XBRL_SIGNATURE_INVALID") from error
        if root.tag.rsplit("}", 1)[-1].lower() != "xbrl":
            raise BseCollectorError("BSE_OFFICIAL_XBRL_ROOT_INVALID")
        try:
            document = parse_bse_xbrl(prefix.decode("utf-8-sig"), source_url, period_end=metadata.period_end)
        except UnicodeDecodeError as error:
            raise BseCollectorError("BSE_XBRL_NOT_UTF8") from error
        if document.security_code != metadata.security_code or document.isin != mapping.isin:
            raise BseCollectorError("BSE_XBRL_CANONICAL_IDENTITY_MISMATCH")
        if document.scope is not None and document.scope is not metadata.scope:
            raise BseCollectorError("BSE_XBRL_SCOPE_MISMATCH")


class BseOfficialSecurityMaster:
    """Exact ISIN lookup through BSE's public security-search interface only."""

    def __init__(self, transport: BseOfficialHttpTransport) -> None:
        self._transport = transport
    def begin_run(self) -> None:
        """Retain the collector's run boundary without persisting lookup state."""

    def resolve(self, *, canonical_instrument_id: str, isin: str) -> BseSecurityMapping:
        if not re.fullmatch(r"[A-Z0-9]{12}", isin.upper()):
            return _mapping(canonical_instrument_id, isin, BseMappingStatus.BLOCKED, (), "CANONICAL_ISIN_INVALID")
        response = self._transport.fetch_isin_lookup(isin)
        candidates = _parse_bse_isin_lookup(response.body, response.url, response.received_at, expected_isin=isin.upper())
        distinct = {item.security_code: item for item in candidates}
        if not distinct:
            return _mapping(canonical_instrument_id, isin, BseMappingStatus.NOT_FOUND, (), "BSE_ISIN_NOT_FOUND",
                            source=response.url, observed=response.received_at, source_type="BSE_EXACT_ISIN_LOOKUP")
        if len(distinct) != 1:
            return _mapping(canonical_instrument_id, isin, BseMappingStatus.AMBIGUOUS, tuple(distinct.values()), "BSE_ISIN_MULTIPLE_SECURITIES",
                            source_type="BSE_EXACT_ISIN_LOOKUP")
        return _mapping(canonical_instrument_id, isin, BseMappingStatus.EXACT, tuple(distinct.values()), None,
                        source_type="BSE_EXACT_ISIN_LOOKUP")


class BseOfficialArchiveSnapshotStore:
    """Append-only raw BSE archive evidence for a reproducible audit run."""

    def __init__(self, root: Path) -> None:
        self._root = root

    def capture(self, *, mapping: BseSecurityMapping, response: BseOfficialHttpResponse) -> BseArchiveSnapshot:
        if mapping.status is not BseMappingStatus.EXACT or mapping.security_code is None:
            raise BseCollectorError("BSE_ARCHIVE_SNAPSHOT_IDENTITY_NOT_EXACT")
        _validate_bse_url(response.url, kind="results-archive")
        _validate_content_type(response.content_type, kind="results-archive")
        digest = sha256(response.body).hexdigest()
        try:
            rows = tuple(csv.DictReader(StringIO(response.body.decode("utf-8-sig"))))
        except (UnicodeDecodeError, csv.Error) as error:
            raise BseCollectorError("BSE_ARCHIVE_SNAPSHOT_PARSE_INVALID") from error
        rows_fingerprint = "sha256:" + sha256(json.dumps(rows, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        snapshot_id = f"bse-archive-{mapping.security_code}-{digest[:20]}"
        self._root.mkdir(parents=True, exist_ok=True)
        path, sidecar = self._root / f"{snapshot_id}.csv", self._root / f"{snapshot_id}.json"
        if path.exists() and path.read_bytes() != response.body:
            raise BseCollectorError("BSE_ARCHIVE_SNAPSHOT_HASH_COLLISION")
        if not path.exists():
            path.write_bytes(response.body)
            sidecar.write_text(json.dumps({
                "schema_version": "bse-official-archive-snapshot-v1", "snapshot_id": snapshot_id,
                "canonical_instrument_id": mapping.canonical_instrument_id, "isin": mapping.isin,
                "security_code": mapping.security_code, "endpoint": response.url,
                "request_parameters": {"scrip_cd": mapping.security_code}, "retrieved_at": response.received_at.isoformat(),
                "http_status": 200, "content_type": response.content_type, "byte_length": len(response.body),
                "raw_sha256": "sha256:" + digest, "parsed_row_count": len(rows), "parsed_rows_fingerprint": rows_fingerprint,
            }, sort_keys=True, separators=(",", ":")), encoding="utf-8")
        return BseArchiveSnapshot(snapshot_id, mapping.canonical_instrument_id, mapping.isin, mapping.security_code,
                                  response.url, response.received_at, response.content_type, len(response.body),
                                  "sha256:" + digest, len(rows), rows_fingerprint, path, sidecar)


class BseOfficialXbrlStaging:
    """Hash-addressed, append-only staging in the existing financial source root."""

    def __init__(self, root: Path) -> None:
        self._root = root

    @property
    def quarantine_root(self) -> Path:
        return self._root / ".quarantine"

    def preserve_archive_aliases(
        self,
        *,
        staged: BseStagedXbrl,
        mapping: BseSecurityMapping,
        aliases: BseResultMetadataAliases,
    ) -> Path:
        """Append immutable archive-row lineage for one already-staged XBRL.

        The manifest is deliberately separate from the source-document sidecar:
        an archive display alias cannot change the document bytes, mapping, or
        canonical fact semantics.
        """
        if mapping.status is not BseMappingStatus.EXACT or not aliases.aliases:
            raise BseCollectorError("BSE_XBRL_ALIAS_LINEAGE_INVALID")
        if aliases.document_url != staged.source_reference or any(item.xbrl_url != aliases.document_url for item in aliases.aliases):
            raise BseCollectorError("BSE_XBRL_ALIAS_DOCUMENT_MISMATCH")
        manifest = staged.sidecar_path.with_name(staged.sidecar_path.stem + ".aliases.json")
        payload = {
            "schema_version": "bse-official-xbrl-alias-lineage-v1",
            "canonical_instrument_id": mapping.canonical_instrument_id,
            "isin": mapping.isin,
            "security_code": mapping.security_code,
            "document_identifier": aliases.document_url,
            "content_sha256": staged.sha256,
            "aliases": [
                {
                    "financial_year": item.financial_year,
                    "quarter_label": item.quarter_label,
                    "filing_type": item.filing_type,
                    "status": item.status,
                    "filing_at": item.filing_at.isoformat(),
                    "revised_at": item.revised_at.isoformat() if item.revised_at else None,
                    "revision_reason": item.revision_reason,
                    "statement_scope": item.scope.value,
                    "period_end": item.period_end.isoformat(),
                    "period_type": item.period_type.value,
                    "value_basis": item.value_basis.value,
                    "source_page": item.source_page,
                    "timestamp_status": item.timestamp_status.value,
                    "raw_filing_timestamp": item.raw_filing_timestamp,
                    "raw_filing_timestamp_field_path": item.raw_filing_timestamp_field_path,
                }
                for item in aliases.aliases
            ],
            "preferred_display_alias": aliases.preferred.period_type.value,
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        if manifest.exists():
            if manifest.read_text(encoding="utf-8") != encoded:
                raise BseCollectorError("BSE_XBRL_ALIAS_LINEAGE_COLLISION")
            return manifest
        manifest.write_text(encoded, encoding="utf-8")
        return manifest

    def stage(
        self,
        *,
        mapping: BseSecurityMapping,
        metadata: BseResultMetadata,
        response: BseOfficialHttpResponse,
    ) -> BseStagedXbrl:
        if mapping.status is not BseMappingStatus.EXACT or mapping.security_code != metadata.security_code:
            raise BseCollectorError("BSE_XBRL_STAGING_IDENTITY_NOT_EXACT")
        _validate_bse_url(response.url, kind="xbrl")
        try:
            document = parse_bse_xbrl(response.body.decode("utf-8-sig"), response.url, period_end=metadata.period_end)
        except UnicodeDecodeError as error:
            raise BseCollectorError("BSE_XBRL_NOT_UTF8") from error
        if document.security_code != metadata.security_code or document.isin != mapping.isin:
            raise BseCollectorError("BSE_XBRL_CANONICAL_IDENTITY_MISMATCH")
        if document.scope is not None and document.scope is not metadata.scope:
            raise BseCollectorError("BSE_XBRL_SCOPE_MISMATCH")
        digest = sha256(response.body).hexdigest()
        stem = "bse-{code}-{isin}-{period}-{scope}-{digest}".format(
            code=metadata.security_code, isin=mapping.isin, period=metadata.period_end.date().isoformat(),
            scope=metadata.scope.value.lower(), digest=digest[:20],
        )
        self._root.mkdir(parents=True, exist_ok=True)
        path, sidecar = self._root / f"{stem}.xml", self._root / f"{stem}.json"
        prior_hashes = _prior_hashes(self._root, metadata.xbrl_url)
        if path.exists():
            if path.read_bytes() != response.body:
                raise BseCollectorError("BSE_XBRL_STAGE_HASH_COLLISION")
            return BseStagedXbrl(path, sidecar, BseStageDisposition.EXISTING_UNCHANGED, digest, len(response.body), response.url, metadata.filing_at, response.received_at)
        path.write_bytes(response.body)
        payload = {
            "schema_version": "bse-official-xbrl-staging-v1", "canonical_instrument_id": mapping.canonical_instrument_id,
            "isin": mapping.isin, "security_code": metadata.security_code, "security_id": mapping.security_id,
            "source_reference": response.url, "document_identifier": metadata.xbrl_url,
            "filename": path.name, "content_type": response.content_type, "byte_length": len(response.body),
            "sha256": digest, "published_at": metadata.filing_at.isoformat(), "discovered_at": mapping.retrieved_at.isoformat(),
            "received_at": response.received_at.isoformat(), "period_end": metadata.period_end.isoformat(),
            "statement_scope": metadata.scope.value,
        }
        sidecar.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":")), encoding="utf-8")
        disposition = BseStageDisposition.NEW_VERSION if prior_hashes else BseStageDisposition.NEW
        return BseStagedXbrl(path, sidecar, disposition, digest, len(response.body), response.url, metadata.filing_at, response.received_at)

    def promote_quarantine(
        self,
        *,
        mapping: BseSecurityMapping,
        metadata: BseResultMetadata,
        value: BseQuarantinedXbrl,
    ) -> BseStagedXbrl:
        """Atomically promote previously validated quarantine bytes into staging."""
        if mapping.status is not BseMappingStatus.EXACT or mapping.security_code != metadata.security_code:
            raise BseCollectorError("BSE_XBRL_STAGING_IDENTITY_NOT_EXACT")
        _validate_bse_url(value.source_url, kind="xbrl")
        quarantine = self.quarantine_root.resolve()
        try:
            source = value.path.resolve(strict=True)
        except OSError as error:
            raise BseCollectorError("BSE_XBRL_QUARANTINE_UNAVAILABLE") from error
        if source.parent != quarantine or source.suffix != ".part" or not source.name.startswith("bse-xbrl-"):
            raise BseCollectorError("BSE_XBRL_QUARANTINE_PATH_REJECTED")
        try:
            raw = source.read_bytes()
        except OSError as error:
            raise BseCollectorError("BSE_XBRL_QUARANTINE_UNAVAILABLE") from error
        if len(raw) != value.byte_length or sha256(raw).hexdigest() != value.sha256:
            raise BseCollectorError("BSE_XBRL_QUARANTINE_INTEGRITY_MISMATCH")
        # Revalidate immediately before canonical promotion. Quarantine never
        # becomes evidence merely because it was fully downloaded once.
        BseOfficialBoundedXbrlAcquirer._validate_quarantined(
            source, mapping=mapping, metadata=metadata, source_url=value.source_url,
        )
        document = parse_bse_xbrl(raw.decode("utf-8-sig"), value.source_url, period_end=metadata.period_end)
        digest = value.sha256
        stem = "bse-{code}-{isin}-{period}-{scope}-{digest}".format(
            code=metadata.security_code, isin=mapping.isin, period=metadata.period_end.date().isoformat(),
            scope=metadata.scope.value.lower(), digest=digest[:20],
        )
        self._root.mkdir(parents=True, exist_ok=True)
        path, sidecar = self._root / f"{stem}.xml", self._root / f"{stem}.json"
        prior_hashes = _prior_hashes(self._root, metadata.xbrl_url)
        if path.exists():
            if sha256(path.read_bytes()).hexdigest() != digest:
                raise BseCollectorError("BSE_XBRL_STAGE_HASH_COLLISION")
            source.unlink(missing_ok=True)
            return BseStagedXbrl(path, sidecar, BseStageDisposition.EXISTING_UNCHANGED, digest, len(raw), value.source_url, metadata.filing_at, value.received_at)
        payload = {
            "schema_version": "bse-official-xbrl-staging-v1", "canonical_instrument_id": mapping.canonical_instrument_id,
            "isin": mapping.isin, "security_code": metadata.security_code, "security_id": mapping.security_id,
            "source_reference": value.source_url, "document_identifier": metadata.xbrl_url,
            "filename": path.name, "content_type": value.content_type, "byte_length": len(raw),
            "sha256": digest, "published_at": metadata.filing_at.isoformat(), "discovered_at": mapping.retrieved_at.isoformat(),
            "received_at": value.received_at.isoformat(), "period_end": metadata.period_end.isoformat(),
            "statement_scope": metadata.scope.value, "acquisition": "BSE_XBRL_BOUNDED_STREAMING_V1",
            "final_bse_host": urlparse(value.source_url).hostname,
        }
        temporary_sidecar = sidecar.with_suffix(".json.part")
        try:
            temporary_sidecar.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":")), encoding="utf-8")
            os.replace(temporary_sidecar, sidecar)
            os.replace(source, path)
        except OSError as error:
            temporary_sidecar.unlink(missing_ok=True)
            raise BseCollectorError("BSE_XBRL_STAGE_PROMOTION_FAILED") from error
        disposition = BseStageDisposition.NEW_VERSION if prior_hashes else BseStageDisposition.NEW
        return BseStagedXbrl(path, sidecar, disposition, digest, len(raw), value.source_url, metadata.filing_at, value.received_at)


class BseOfficialIciciBoundedXbrlRecovery:
    """Private, fixed-target recovery for the three approved ICICIBANK XBRLs.

    This has no API endpoint and does not invoke a filing/fact importer.
    """

    def __init__(self, acquirer: BseOfficialBoundedXbrlAcquirer, staging: BseOfficialXbrlStaging) -> None:
        self._acquirer, self._staging = acquirer, staging

    def audit(self, *, mapping: BseSecurityMapping, metadata: BseResultMetadata) -> BseBoundedXbrlRecoveryReceipt:
        self._validate_target(mapping, metadata)
        value = self._acquirer.audit_acquire(mapping=mapping, metadata=metadata)
        try:
            return BseBoundedXbrlRecoveryReceipt(
                metadata.xbrl_url, value.byte_length, value.sha256, value.content_type, value.source_url, None, True,
            )
        finally:
            self._acquirer.discard(value)

    def recover(self, *, mapping: BseSecurityMapping, metadata: BseResultMetadata) -> BseBoundedXbrlRecoveryReceipt:
        self._validate_target(mapping, metadata)
        value = self._acquirer.acquire(mapping=mapping, metadata=metadata)
        try:
            staged = self._staging.promote_quarantine(mapping=mapping, metadata=metadata, value=value)
            return BseBoundedXbrlRecoveryReceipt(
                metadata.xbrl_url, value.byte_length, value.sha256, value.content_type, value.source_url, staged, False,
            )
        except Exception:
            self._acquirer.discard(value)
            raise

    @staticmethod
    def _validate_target(mapping: BseSecurityMapping, metadata: BseResultMetadata) -> None:
        if (
            mapping.canonical_instrument_id != "NSE:INE090A01021"
            or mapping.isin != "INE090A01021"
            or mapping.security_code != "532174"
            or metadata.security_code != "532174"
            or metadata.xbrl_url not in _ICICI_BOUNDED_XBRL_DOCUMENTS
        ):
            raise BseCollectorError("BSE_XBRL_BOUNDED_RECOVERY_TARGET_REJECTED")


class BseOfficialFinancialCollector:
    """One narrow five-holding BSE collector; no arbitrary identity or URL input."""

    def __init__(
        self,
        *,
        universe: CoreUniverseAnalysisStore,
        filings: CorporateFilingsStore,
        facts: FinancialFactStore,
        security_master: BseOfficialSecurityMaster,
        provider: BSEOfficialFinancialResultsProvider | BSEOfficialFinancialResultsArchiveProvider,
        transport: BseOfficialHttpTransport,
        staging: BseOfficialXbrlStaging,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._universe, self._security_master = universe, security_master
        self._provider, self._transport, self._staging, self._clock = provider, transport, staging, clock
        self._importer = BSEOfficialLocalXbrlIngestionService(filings, facts, mapping_store=universe, clock=clock)

    def request_refresh(self, value: BseFinancialRefreshRequest) -> BseFinancialRefreshRequest:
        """Accept only a future-safe request; source rediscovery remains internal."""
        return value

    def run(self, *, requested_as_of: datetime | None = None, run_id: str = "real-portfolio-bse-financials") -> BseFinancialCollectorRun:
        cutoff = requested_as_of or self._clock()
        if cutoff.tzinfo is None or cutoff.utcoffset() is None:
            raise ValueError("BSE_FINANCIAL_COLLECTOR_AS_OF_TIMEZONE_REQUIRED")
        self._security_master.begin_run()
        instruments = {item.instrument_id: item for item in self._universe.instruments_as_of(cutoff)}
        receipts = tuple(self._collect(identifier, instruments.get(identifier), cutoff) for identifier in REAL_PORTFOLIO_BSE_FINANCIAL_TARGETS)
        return BseFinancialCollectorRun(run_id, cutoff, receipts)

    def run_historical_annual_backfill(
        self, *, requested_as_of: datetime | None = None,
        run_id: str = "real-portfolio-bse-historical-annuals",
    ) -> BseFinancialCollectorRun:
        """Acquire at most five exact annual periods per scope for four targets.

        This is a bounded primary-source replay of the normal collector. It
        does not infer target eligibility, merge reporting scopes, or change
        the existing XBRL staging/import path.
        """
        cutoff = requested_as_of or self._clock()
        if cutoff.tzinfo is None or cutoff.utcoffset() is None:
            raise ValueError("BSE_FINANCIAL_COLLECTOR_AS_OF_TIMEZONE_REQUIRED")
        self._security_master.begin_run()
        instruments = {item.instrument_id: item for item in self._universe.instruments_as_of(cutoff)}
        receipts = tuple(
            self._collect(identifier, instruments.get(identifier), cutoff, historical_annual=True)
            for identifier in COMPOUNDER_NON_FINANCIAL_BSE_HISTORICAL_TARGETS
        )
        return BseFinancialCollectorRun(run_id, cutoff, receipts)

    def refresh(self, request: EvidenceRefreshRequest) -> EvidenceRefreshOutcome:
        run = self.run(requested_as_of=request.requested_as_of, run_id=request.run_id)
        values = run.receipts
        accepted = sum(item.new_filings for item in values)
        duplicates = sum(item.unchanged_filings for item in values)
        conflicts = sum(item.financial_conflicts + item.conflicting_filings for item in values)
        gaps = sum(1 for item in values if item.blockers)
        status = (
            EvidenceRefreshStatus.PARTIAL if accepted and (gaps or conflicts)
            else EvidenceRefreshStatus.COMPLETE if accepted
            else EvidenceRefreshStatus.CONFLICT_FOUND if conflicts
            else EvidenceRefreshStatus.SOURCE_UNAVAILABLE if gaps == len(values)
            else EvidenceRefreshStatus.NO_CHANGE
        )
        references = tuple(sorted({item.mapping.source_reference for item in values if item.mapping.status is BseMappingStatus.EXACT}))
        findings = tuple(
            (ReconciliationStatus.GAP_FOUND, item.canonical_instrument_id, blocker)
            for item in values for blocker in item.blockers
        )
        return EvidenceRefreshOutcome(
            status, BSE_OFFICIAL_PROVIDER, discovered_count=sum(item.filings_discovered for item in values),
            accepted_count=accepted, duplicate_count=duplicates, conflict_count=conflicts, gap_count=gaps,
            accepted_through=max((item.latest_published_at for item in values if item.latest_published_at is not None), default=None),
            verified_from_store=bool(accepted or duplicates) and not conflicts,
            failure_kind=EvidenceRefreshFailureKind.SOURCE_UNAVAILABLE if status is EvidenceRefreshStatus.SOURCE_UNAVAILABLE else None,
            error_summary="BSE_OFFICIAL_TARGETS_UNAVAILABLE" if status is EvidenceRefreshStatus.SOURCE_UNAVAILABLE else None,
            warnings=tuple(sorted({blocker for item in values for blocker in item.blockers})), source_references=references,
            findings=findings,
        )

    def _collect(
        self, identifier: str, instrument: NseEquityInstrument | None,
        cutoff: datetime, *, historical_annual: bool = False,
    ) -> BseFinancialCollectorTargetReceipt:
        if instrument is None or not instrument.isin:
            mapping = _mapping(identifier, "", BseMappingStatus.BLOCKED, (), "CANONICAL_INSTRUMENT_OR_ISIN_UNAVAILABLE")
            return _receipt(identifier, None, mapping, blockers=(mapping.reason or "CANONICAL_IDENTITY_UNAVAILABLE",))
        try:
            mapping = self._security_master.resolve(canonical_instrument_id=instrument.instrument_id, isin=instrument.isin)
        except BseCollectorError:
            mapping = _mapping(
                instrument.instrument_id, instrument.isin, BseMappingStatus.BLOCKED, (),
                "BSE_OFFICIAL_SECURITY_MASTER_UNAVAILABLE",
            )
            return _receipt(instrument.instrument_id, instrument.isin, mapping, blockers=(mapping.reason,))
        if mapping.status is not BseMappingStatus.EXACT:
            return _receipt(instrument.instrument_id, instrument.isin, mapping, blockers=(mapping.reason or "BSE_MAPPING_UNAVAILABLE",))
        identity = _identity(instrument)
        try:
            alias_groups = (
                self._provider.result_metadata_aliases(mapping.security_code or "")
                if isinstance(self._provider, BSEOfficialFinancialResultsArchiveProvider)
                else ()
            )
            metadata = (
                tuple(item.preferred for item in alias_groups)
                if alias_groups else self._provider.result_metadata(mapping.security_code or "")
            )
        except (BseCollectorError, BseOfficialError):
            return _receipt(instrument.instrument_id, instrument.isin, mapping, blockers=("BSE_OFFICIAL_FILING_DISCOVERY_UNAVAILABLE",))
        receipts: list[tuple[BseResultMetadata, BseStagedXbrl | None, object | None, BseFilingDispositionRecord]] = []
        selected = _historical_annual_metadata(metadata, cutoff) if historical_annual else metadata[-12:]
        eligible = tuple(item for item in selected if item.filing_at <= cutoff)
        for item in eligible:
            try:
                staged = self._staging.stage(mapping=mapping, metadata=item, response=self._transport.fetch_xbrl(item.xbrl_url))
                aliases = next((group for group in alias_groups if group.document_url == item.xbrl_url), None)
                if aliases is not None:
                    self._staging.preserve_archive_aliases(staged=staged, mapping=mapping, aliases=aliases)
                imported = self._importer.ingest_official_staged(identity, mapping.security_code or "", staged.path, metadata=item)
                receipts.append((item, staged, imported, BseFilingDispositionRecord(item, BseFilingDisposition.IMPORTED, staged=staged.disposition)))
            except (BseCollectorError, BseOfficialError, ValueError) as error:
                receipts.append((item, None, None, BseFilingDispositionRecord(item, _filing_disposition(error), str(error))))
        imported = tuple(item for item in receipts if item[2] is not None)
        rejected = tuple(item[3] for item in receipts if item[3].disposition is not BseFilingDisposition.IMPORTED)
        blocked = tuple(sorted({item.disposition.value for item in rejected}))
        return BseFinancialCollectorTargetReceipt(
            instrument.instrument_id, instrument.isin, mapping, len(eligible),
            sum(1 for _, _, item, _ in imported if item.filing_outcome.value == "INSERTED"),
            sum(1 for _, _, item, _ in imported if item.filing_outcome.value == "IDENTICAL"),
            0, sum(1 for _, stage, _, _ in imported if stage.disposition in {BseStageDisposition.NEW, BseStageDisposition.NEW_VERSION}),
            sum(1 for _, stage, _, _ in imported if stage.disposition is BseStageDisposition.EXISTING_UNCHANGED),
            len(imported), sum(item.facts_inserted for _, _, item, _ in imported),
            sum(item.facts_duplicate for _, _, item, _ in imported), sum(item.facts_conflicted for _, _, item, _ in imported),
            max((item.filing_at for item in eligible), default=None), max((item.period_end for item in eligible), default=None),
            blocked + (("BSE_FILING_NOT_PIT_ELIGIBLE",) if len(eligible) != len(selected) else ()),
            tuple(item[3] for item in receipts),
        )


@dataclass(frozen=True, slots=True)
class BseOfficialFinancialCollectorSettings:
    enabled: bool = False
    interval: timedelta = timedelta(hours=1)

    def __post_init__(self) -> None:
        if self.interval <= timedelta():
            raise ValueError("BSE_FINANCIAL_COLLECTOR_INTERVAL_INVALID")

    @classmethod
    def from_environment(cls) -> "BseOfficialFinancialCollectorSettings":
        """Read the separate opt-in scheduling switch; default is always off."""
        enabled = os.getenv("BSE_OFFICIAL_FINANCIAL_COLLECTOR_ENABLED", "false").strip().lower() == "true"
        raw_interval = os.getenv("BSE_OFFICIAL_FINANCIAL_COLLECTOR_INTERVAL_SECONDS", "3600").strip()
        try:
            interval_seconds = int(raw_interval)
        except ValueError as error:
            raise ValueError("BSE_FINANCIAL_COLLECTOR_INTERVAL_INVALID") from error
        return cls(enabled=enabled, interval=timedelta(seconds=interval_seconds))


class BseOfficialFinancialCollectorWorker:
    """Optional local worker.  Hosts must opt in explicitly; FastAPI never starts it."""

    def __init__(self, collector: BseOfficialFinancialCollector, settings: BseOfficialFinancialCollectorSettings,
                 *, wait: Callable[[float], bool] | None = None) -> None:
        self._collector, self._settings, self._stop = collector, settings, Event()
        self._wait = wait or self._stop.wait
        self._thread: Thread | None = None

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> bool:
        if not self._settings.enabled or self.running:
            return False
        self._stop.clear()
        self._thread = Thread(target=self.run_forever, name="bse-financial-collector", daemon=True)
        self._thread.start()
        return True

    def stop(self, *, join_timeout: float = 2.0) -> bool:
        if not self.running:
            return False
        self._stop.set(); self._thread.join(join_timeout)
        return True

    def run_forever(self, *, max_ticks: int | None = None) -> bool:
        if not self._settings.enabled:
            return False
        ticks = 0
        while not self._stop.is_set():
            self._collector.run()
            ticks += 1
            if max_ticks is not None and ticks >= max_ticks:
                break
            if self._wait(self._settings.interval.total_seconds()):
                break
        return True


def _identity(value: NseEquityInstrument) -> InstrumentIdentity:
    return InstrumentIdentity(value.instrument_id, Exchange.NSE, value.symbol, value.symbol, value.isin, None,
                              InstrumentType.NSE_EQUITY, value.company_name)


def _historical_annual_metadata(
    values: tuple[BseResultMetadata, ...], cutoff: datetime,
) -> tuple[BseResultMetadata, ...]:
    """Select exact annual archive entries without mixing statement scopes.

    Five distinct annual period ends are selected independently for each exact
    scope. Every legitimate archive vintage for a selected period is retained,
    so a later restatement cannot erase an earlier filing.
    """
    annual = tuple(
        value for value in values
        if value.period_type is FinancialPeriodType.ANNUAL
        and value.value_basis is FinancialValueBasis.FULL_YEAR
        and value.filing_at <= cutoff
        and value.scope in {StatementScope.CONSOLIDATED, StatementScope.STANDALONE}
    )
    selected: list[BseResultMetadata] = []
    for scope in (StatementScope.CONSOLIDATED, StatementScope.STANDALONE):
        scoped = tuple(value for value in annual if value.scope is scope)
        ends = tuple(sorted({value.period_end for value in scoped}, reverse=True))[
            :_HISTORICAL_ANNUAL_PERIODS_PER_SCOPE
        ]
        selected.extend(value for value in scoped if value.period_end in ends)
    return tuple(sorted(selected, key=lambda value: (
        value.period_end, value.scope.value, value.filing_at, value.xbrl_url,
    )))


def _mapping(
    identifier: str, isin: str, status: BseMappingStatus, candidates: tuple[BseSecurityCandidate, ...], reason: str | None,
    *, source: str | None = None, observed: datetime | None = None, source_type: str = "BSE_STANDARDIZED_SECURITY_MASTER",
    source_master_date: date | None = None,
) -> BseSecurityMapping:
    item = candidates[0] if len(candidates) == 1 else None
    source = item.source_reference if item is not None else source or BSE_OFFICIAL_SCRIP_MASTER_URL
    observed = item.retrieved_at if item is not None else observed or datetime.now(UTC)
    fingerprint = "sha256:" + sha256(json.dumps((identifier, isin.upper(), status.value, None if item is None else item.security_code, source, reason), separators=(",", ":")).encode()).hexdigest()
    return BseSecurityMapping(identifier, isin.upper(), status, None if item is None else item.security_code,
                              None if item is None else item.security_id, None if item is None else item.security_name,
                              source, observed, fingerprint, reason, source_type, source_master_date)


def _filing_disposition(error: Exception) -> BseFilingDisposition:
    message = str(error)
    if "period conflicts with official metadata" in message:
        return BseFilingDisposition.XBRL_PERIOD_METADATA_CONFLICT
    if "IDENTITY_MISMATCH" in message or "identity mismatch" in message:
        return BseFilingDisposition.XBRL_IDENTITY_MISMATCH
    if "SCOPE_MISMATCH" in message or "statement scope conflicts" in message:
        return BseFilingDisposition.XBRL_SCOPE_METADATA_CONFLICT
    if (
        "CONTENT_TYPE_REJECTED" in message or "not UTF8" in message
        or "XBRL_SIGNATURE_INVALID" in message or "XBRL_ROOT_INVALID" in message
        or "RESPONSE_EMPTY" in message
    ):
        return BseFilingDisposition.OFFICIAL_RESPONSE_NOT_XBRL
    if "XBRL is malformed" in message:
        return BseFilingDisposition.MALFORMED_XBRL
    if "SOURCE_UNAVAILABLE" in message or "HTTP_STATUS_REJECTED" in message or "QUARANTINE_" in message:
        return BseFilingDisposition.XBRL_FETCH_FAILED
    if "RESPONSE_TOO_LARGE" in message:
        return BseFilingDisposition.XBRL_DOCUMENT_TOO_LARGE
    if "filing timestamp is malformed" in message:
        return BseFilingDisposition.SOURCE_METADATA_TIMESTAMP_UNSUPPORTED
    return BseFilingDisposition.UNCLASSIFIED_REJECTION


def _receipt(identifier: str, isin: str | None, mapping: BseSecurityMapping, *, blockers: tuple[str, ...]) -> BseFinancialCollectorTargetReceipt:
    return BseFinancialCollectorTargetReceipt(identifier, isin, mapping, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, None, None, blockers)


def _validate_bse_url(url: str, *, kind: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname not in {_BSE_HOST, _BSE_API_HOST} or parsed.username or parsed.password or parsed.port not in {None, 443}:
        raise BseCollectorError("BSE_OFFICIAL_HOST_REJECTED")
    if parsed.hostname == _BSE_API_HOST:
        query = parse_qs(parsed.query)
        allowed = (
            kind == "isin-lookup"
            and parsed.path == "/BseIndiaAPI/api/PeerSmartSearch/w"
            and query.get("Type") == ["SS"]
            and len(query.get("text", ())) == 1
            and bool(re.fullmatch(r"[A-Z0-9]{12}", query["text"][0]))
        ) or (
            kind == "results-archive"
            and parsed.path == "/BseIndiaAPI/api/Result_Arch_Download/w"
            and len(query.get("scrip_cd", ())) == 1
            and bool(re.fullmatch(r"\d{6}", query["scrip_cd"][0]))
        )
        if not allowed:
            raise BseCollectorError("BSE_OFFICIAL_URL_PATH_REJECTED")
        return
    if kind == "master":
        allowed = url == BSE_OFFICIAL_SCRIP_MASTER_URL
    elif kind == "lifecycle-notice":
        query = parse_qs(parsed.query)
        allowed = (parsed.path == "/markets/MarketInfo/DispNewNoticesCirculars.aspx"
                   and len(query.get("page", ())) == 1
                   and bool(re.fullmatch(r"\d{8}-\d{1,3}", query["page"][0])))
    elif kind == "compulsory-delisted-list":
        allowed = url == BSE_OFFICIAL_COMPULSORY_DELISTED_URL
    elif kind == "xbrl":
        allowed = parsed.path.startswith("/XBRLFILES/")
    else:
        query = parse_qs(parsed.query)
        allowed = parsed.path == "/corporates/Comp_Results.aspx" and len(query.get("Code", ())) == 1 and query["Code"][0].isdigit()
        allowed = allowed or parsed.path.startswith("/XBRLFILES/")
    if not allowed:
        raise BseCollectorError("BSE_OFFICIAL_URL_PATH_REJECTED")


def _validate_content_type(content_type: str | None, *, kind: str) -> None:
    """Reject a declared non-document type before it reaches a parser or disk."""
    if content_type is None:
        return
    value = content_type.lower().split(";", 1)[0].strip()
    allowed = {
        "master": {"application/zip", "application/octet-stream"},
        "xbrl": {"application/xml", "text/xml", "application/octet-stream"},
        "result-or-xbrl": {"text/html", "application/xhtml+xml", "application/xml", "text/xml", "application/octet-stream"},
        "isin-lookup": {"application/json"},
        "results-archive": {"text/csv", "application/csv", "application/octet-stream"},
        "lifecycle-notice": {"text/html", "application/xhtml+xml", "application/octet-stream"},
        "compulsory-delisted-list": {"application/pdf", "application/octet-stream"},
    }[kind]
    if value not in allowed:
        raise BseCollectorError("BSE_OFFICIAL_CONTENT_TYPE_REJECTED")


def _parse_bse_master(payload: bytes, source: str, observed: datetime) -> tuple[BseSecurityCandidate, ...]:
    try:
        with ZipFile(BytesIO(payload)) as archive:
            members = tuple(item for item in archive.infolist() if not item.is_dir())
            if len(members) != 1 or members[0].file_size > _MAX_MASTER_BYTES or members[0].filename.startswith(("/", "\\")) or ".." in Path(members[0].filename).parts:
                raise BseCollectorError("BSE_SCRIP_MASTER_ARCHIVE_INVALID")
            raw = archive.read(members[0])
    except (BadZipFile, OSError) as error:
        raise BseCollectorError("BSE_SCRIP_MASTER_ARCHIVE_INVALID") from error
    try:
        rows = csv.DictReader(StringIO(raw.decode("utf-8-sig")))
        values = []
        for row in rows:
            fields = {_header(key): (value or "").strip() for key, value in row.items() if key}
            isin, code = fields.get("isin_code") or fields.get("isin"), fields.get("scrip_code") or fields.get("security_code")
            if not isin or not code or not code.isdigit():
                continue
            values.append(BseSecurityCandidate(isin.upper(), code, fields.get("instrument_code") or fields.get("security_id"), fields.get("scrip_name") or fields.get("security_name"), source, observed))
        return tuple(values)
    except (UnicodeDecodeError, csv.Error) as error:
        raise BseCollectorError("BSE_SCRIP_MASTER_PARSE_INVALID") from error


class _BseExactIsinLookupParser(HTMLParser):
    """Parse only BSE's compact search result shape; never infer a name match."""

    def __init__(self, expected_isin: str, source: str, observed: datetime) -> None:
        super().__init__()
        self._expected_isin, self._source, self._observed = expected_isin, source, observed
        self._current: dict[str, object] | None = None
        self._in_span = self._in_strong = False
        self._values: list[BseSecurityCandidate] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "li":
            value = dict(attrs).get("ng-click") or ""
            match = re.fullmatch(r"\s*liclick\('(?P<code>\d{6})','(?P<name>[^']+)'\)\s*", value)
            self._current = {"code": match.group("code"), "name": match.group("name"), "span": [], "isin": None} if match else None
        elif self._current is not None and tag == "span":
            self._in_span = True
        elif self._current is not None and tag == "strong":
            self._in_strong = True

    def handle_data(self, data: str) -> None:
        if self._current is None:
            return
        if self._in_strong:
            self._current["isin"] = data.strip().upper()
        elif self._in_span:
            self._current["span"].append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "strong":
            self._in_strong = False
        elif tag == "span":
            self._in_span = False
        elif tag == "li" and self._current is not None:
            isin = self._current["isin"]
            symbols = re.findall(r"[A-Z][A-Z0-9-]*", " ".join(self._current["span"]))
            symbol = symbols[0] if symbols else None
            if isin == self._expected_isin and symbol is not None:
                self._values.append(BseSecurityCandidate(
                    isin, self._current["code"], symbol, self._current["name"], self._source, self._observed,
                ))
            self._current = None

    def values(self) -> tuple[BseSecurityCandidate, ...]:
        return tuple(self._values)


def _parse_bse_isin_lookup(payload: bytes, source: str, observed: datetime, *, expected_isin: str) -> tuple[BseSecurityCandidate, ...]:
    try:
        document = json.loads(payload.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise BseCollectorError("BSE_EXACT_ISIN_LOOKUP_RESPONSE_INVALID") from error
    if not isinstance(document, str):
        raise BseCollectorError("BSE_EXACT_ISIN_LOOKUP_RESPONSE_INVALID")
    parser = _BseExactIsinLookupParser(expected_isin, source, observed)
    parser.feed(document)
    return parser.values()


def _prior_hashes(root: Path, document_url: str) -> set[str]:
    values: set[str] = set()
    for path in root.glob("bse-*.json"):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            continue
        if payload.get("document_identifier") == document_url and isinstance(payload.get("sha256"), str):
            values.add(payload["sha256"])
    return values


def _header(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.strip().lower()).strip("_")


__all__ = (
    "BSE_OFFICIAL_COMPULSORY_DELISTED_URL", "BSE_OFFICIAL_EXACT_ISIN_LOOKUP_URL", "BSE_OFFICIAL_NOTICE_URL", "BSE_OFFICIAL_RESULTS_ARCHIVE_URL", "BSE_OFFICIAL_SCRIP_MASTER_URL", "BseArchiveSnapshot", "BseBoundedXbrlRecoveryReceipt", "BseCollectorError", "BseFinancialCollectorRun",
    "BseFinancialRefreshRequest", "BseFilingDisposition", "BseFilingDispositionRecord", "BseMappingStatus", "BseOfficialBoundedXbrlAcquirer", "BseOfficialFinancialCollector",
    "BseOfficialArchiveSnapshotStore", "BseOfficialFinancialCollectorSettings", "BseOfficialFinancialCollectorWorker", "BseOfficialIciciBoundedXbrlRecovery",
    "BseOfficialHttpResponse", "BseOfficialHttpTransport", "BseOfficialSecurityMaster",
    "BseOfficialXbrlStaging", "BseQuarantinedXbrl", "BseSecurityMapping", "BseXbrlStreamingPolicy", "COMPOUNDER_NON_FINANCIAL_BSE_HISTORICAL_TARGETS", "REAL_PORTFOLIO_BSE_FINANCIAL_TARGETS",
)
