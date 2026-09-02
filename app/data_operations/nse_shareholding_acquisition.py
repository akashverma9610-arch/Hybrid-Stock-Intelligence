"""Bounded acquisition of the official NSE shareholding-pattern CSV export.

This is deliberately an acquisition and staging boundary only.  It never
interprets ownership percentages and it delegates every canonical write to the
existing ``NseReg31ShareholdingRefreshJob`` / official-file importer.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
import io
import json
from pathlib import Path
import re
from typing import Callable, Iterable
from urllib.parse import urlsplit
from xml.etree import ElementTree
from zoneinfo import ZoneInfo

import requests

from app.data_operations.nse_reg31_identity import NseReg31IdentityReconciliationStore


NSE_SHAREHOLDING_PAGE_URL = "https://www.nseindia.com/companies-listing/corporate-filings-shareholding-pattern"
NSE_SHAREHOLDING_EXPORT_URL = "https://www.nseindia.com/api/corporate-share-holdings-master"
NSE_SHAREHOLDING_PROVIDER = "NSE_OFFICIAL"
_MAXIMUM_BYTES = 5_000_000
_OFFICIAL_HOST = "www.nseindia.com"
_CSV_REQUIRED_HEADERS = frozenset({"COMPANY", "AS ON DATE", "ACTION", "BROADCAST DATE/TIME"})
_SAFE_FILENAME = re.compile(r"^CF-Shareholding-Pattern-equities-[A-Z0-9]+-\d{2}-[A-Za-z]{3}-\d{4}\.csv$")
_SAFE_XBRL_FILENAME = re.compile(r"^SHP-Reg31-equities-[A-Z0-9]+-\d{4}-\d{2}-\d{2}-[A-Za-z0-9_-]+\.xml$")


@dataclass(frozen=True, slots=True)
class NseReg31Target:
    symbol: str
    isin: str

    def __post_init__(self) -> None:
        if not re.fullmatch(r"[A-Z0-9]+", self.symbol):
            raise ValueError("NSE shareholding target symbol is invalid.")
        if not re.fullmatch(r"INE[A-Z0-9]{9,10}", self.isin):
            raise ValueError("NSE shareholding target ISIN is invalid.")


APPROVED_NSE_REG31_TARGETS = (
    NseReg31Target("APARINDS", "INE372A01015"),
    NseReg31Target("DEEPINDS", "INE0FHS01024"),
    NseReg31Target("GENUSPOWER", "INE955D01029"),
    NseReg31Target("GLAND", "INE068V01023"),
    NseReg31Target("ICICIBANK", "INE090A01021"),
)


class NseShareholdingAcquisitionError(RuntimeError):
    """Safe, non-secret acquisition failure."""


class NseShareholdingAcquisitionConflict(NseShareholdingAcquisitionError):
    """The official source changed at a deterministic staging path."""


@dataclass(frozen=True, slots=True)
class NseShareholdingStagedArtifact:
    target: NseReg31Target
    path: Path
    sha256: str
    retrieved_at: datetime
    source_url: str
    status: str


class NseOfficialShareholdingAcquirer:
    """Fetch exactly approved NSE shareholding artifacts and stage raw bytes."""

    def __init__(
        self,
        source_directory: Path,
        *,
        session: requests.Session | None = None,
        identity_reconciliation_store: NseReg31IdentityReconciliationStore | None = None,
        timeout_seconds: int = 20,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        if timeout_seconds < 1:
            raise ValueError("NSE shareholding timeout must be positive.")
        self._source_directory = source_directory
        self._session = session or requests.Session()
        self._identity_reconciliation_store = identity_reconciliation_store
        self._verified_latest: dict[str, dict[str, object]] = {}
        self._timeout_seconds = timeout_seconds
        self._clock = clock

    def acquire(self, targets: Iterable[NseReg31Target] = APPROVED_NSE_REG31_TARGETS) -> tuple[NseShareholdingStagedArtifact, ...]:
        values = tuple(targets)
        if not values:
            raise ValueError("At least one explicit NSE shareholding target is required.")
        approved = {(item.symbol, item.isin) for item in APPROVED_NSE_REG31_TARGETS}
        if any((item.symbol, item.isin) not in approved for item in values):
            raise ValueError("NSE shareholding acquisition target is not approved.")
        if len({item.symbol for item in values}) != len(values):
            raise ValueError("NSE shareholding acquisition targets must be unique.")
        self._prime_official_session()
        # Establish the complete exact-symbol/ISIN cohort before staging any
        # raw bytes.  A later target mismatch must not leave a partial batch.
        for item in values:
            self._verify_target_identity(item)
        return tuple(self._acquire_one(item) for item in values)

    def acquire_current_xbrl(self, targets: Iterable[NseReg31Target] = APPROVED_NSE_REG31_TARGETS) -> tuple[NseShareholdingStagedArtifact, ...]:
        """Stage only an independently current, official NSE Reg31 XBRL.

        This is intentionally separate from the legacy CSV endpoint: a current
        XBRL may be valid even when a page CSV names a historical or distinct
        security.  It never reclassifies or accepts that CSV.
        """
        values = self._approved_unique_targets(targets)
        self._prime_official_session()
        for item in values:
            self._verify_target_identity(item, require_current_xbrl=True)
        return tuple(self._acquire_current_xbrl_one(item) for item in values)

    def _approved_unique_targets(self, targets: Iterable[NseReg31Target]) -> tuple[NseReg31Target, ...]:
        values = tuple(targets)
        if not values:
            raise ValueError("At least one explicit NSE shareholding target is required.")
        approved = {(item.symbol, item.isin) for item in APPROVED_NSE_REG31_TARGETS}
        if any((item.symbol, item.isin) not in approved for item in values):
            raise ValueError("NSE shareholding acquisition target is not approved.")
        if len({item.symbol for item in values}) != len(values):
            raise ValueError("NSE shareholding acquisition targets must be unique.")
        return values

    def _prime_official_session(self) -> None:
        response = self._session.get(NSE_SHAREHOLDING_PAGE_URL, headers=_headers(), timeout=self._timeout_seconds)
        _require_official_response(response, expected_content_type="text/html")

    def _verify_target_identity(self, target: NseReg31Target, *, require_current_xbrl: bool = False) -> None:
        params = {"index": "equities", "symbol": target.symbol}
        identity = self._session.get(NSE_SHAREHOLDING_EXPORT_URL, params=params, headers=_headers("application/json"), timeout=self._timeout_seconds)
        _require_official_response(identity, expected_content_type="application/json")
        returned_isin, latest = _returned_identity(identity.content, target)
        # The XBRL path is a distinct evidence artifact.  Its direct current
        # identity gate is sufficient for this acquisition only; it never
        # converts an incompatible page-CSV identity into an accepted CSV.
        if require_current_xbrl:
            self._verify_current_attachment(target, latest, expected_issuer=str(latest.get("name") or ""))
            self._verified_latest[target.symbol] = latest
            return
        if returned_isin == target.isin:
            self._verified_latest[target.symbol] = latest
            return
        reconciliation = (
            self._identity_reconciliation_store.get(
                canonical_instrument_id="NSE:" + target.isin,
                returned_isin=returned_isin,
                as_of=self._clock().astimezone(UTC),
            )
            if self._identity_reconciliation_store is not None else None
        )
        if reconciliation is None or not reconciliation.acquisition_permitted:
            raise NseShareholdingAcquisitionError("NSE_SHAREHOLDING_EXACT_IDENTITY_MISMATCH")
        if reconciliation.current_identity.isin != target.isin or reconciliation.current_identity.symbol != target.symbol:
            raise NseShareholdingAcquisitionError("NSE_SHAREHOLDING_RECONCILIATION_CANONICAL_IDENTITY_INVALID")
        self._verify_current_attachment(target, latest, expected_issuer=reconciliation.current_identity.issuer_name)
        self._verified_latest[target.symbol] = latest

    def _verify_current_attachment(self, target: NseReg31Target, latest: dict[str, object], *, expected_issuer: str) -> None:
        reference = latest.get("xbrl")
        if not isinstance(reference, str) or not reference:
            raise NseShareholdingAcquisitionError("REG31_XBRL_OFFICIAL_SOURCE_REQUIRED")
        attachment = self._session.get(reference, headers=_headers("application/xml,text/xml,*/*"), timeout=self._timeout_seconds)
        _require_archive_response(attachment, expected_content_type="xml")
        _verify_current_xbrl_identity(attachment.content, target, expected_issuer)

    def _acquire_one(self, target: NseReg31Target) -> NseShareholdingStagedArtifact:
        params = {"index": "equities", "symbol": target.symbol}
        csv_response = self._session.get(
            NSE_SHAREHOLDING_EXPORT_URL,
            params={**params, "csv": "true"},
            headers=_headers("text/csv"), timeout=self._timeout_seconds,
        )
        _require_official_response(csv_response, expected_content_type="text/csv")
        content = bytes(csv_response.content)
        latest = self._verified_latest.get(target.symbol)
        company_name = latest.get("name") if latest is not None else None
        if not isinstance(company_name, str) or not company_name:
            raise NseShareholdingAcquisitionError("NSE_SHAREHOLDING_IDENTITY_RESPONSE_INVALID")
        _verify_csv(content, expected_company_name=company_name)
        name = _official_filename(csv_response.headers.get("Content-Disposition"), target, self._clock())
        return self._stage(target, name, content, csv_response.url)

    def _acquire_current_xbrl_one(self, target: NseReg31Target) -> NseShareholdingStagedArtifact:
        latest = self._verified_latest.get(target.symbol)
        if latest is None:
            raise NseShareholdingAcquisitionError("REG31_XBRL_OFFICIAL_SOURCE_REQUIRED")
        reference = latest.get("xbrl")
        if not isinstance(reference, str) or not reference:
            raise NseShareholdingAcquisitionError("REG31_XBRL_OFFICIAL_SOURCE_REQUIRED")
        response = self._session.get(reference, headers=_headers("application/xml,text/xml,*/*"), timeout=self._timeout_seconds)
        _require_archive_response(response, expected_content_type="xml")
        content = bytes(response.content)
        issuer = latest.get("name")
        if not isinstance(issuer, str) or not issuer:
            raise NseShareholdingAcquisitionError("REG31_XBRL_ISSUER_MISMATCH")
        _verify_current_xbrl_identity(content, target, issuer)
        reporting_period = latest.get("date")
        publication = latest.get("broadcastDate")
        document_id = latest.get("recordId")
        if not all(isinstance(value, str) and value for value in (reporting_period, publication, document_id)):
            raise NseShareholdingAcquisitionError("REG31_XBRL_UNSUPPORTED_STRUCTURE")
        period_end = _nse_date_to_iso(reporting_period)
        publication_at = _nse_timestamp_to_iso(publication)
        name = f"SHP-Reg31-equities-{target.symbol}-{period_end}-{document_id}.xml"
        return self._stage(
            target, name, content, response.url,
            file_format="XBRL/XML", issuer=issuer, reporting_period_end=period_end,
            official_publication_timestamp=publication_at, official_document_id=document_id,
        )

    def _stage(self, target: NseReg31Target, name: str, content: bytes, source_url: str, *, file_format: str = "CSV", issuer: str | None = None, reporting_period_end: str | None = None, official_publication_timestamp: str | None = None, official_document_id: str | None = None) -> NseShareholdingStagedArtifact:
        retrieved_at = self._clock().astimezone(UTC)
        digest = sha256(content).hexdigest()
        self._source_directory.mkdir(parents=True, exist_ok=True)
        destination = self._source_directory / name
        if destination.exists():
            existing = sha256(destination.read_bytes()).hexdigest()
            if existing == digest:
                try:
                    self._write_manifest(target, destination, digest, retrieved_at, source_url, file_format=file_format, issuer=issuer, reporting_period_end=reporting_period_end, official_publication_timestamp=official_publication_timestamp, official_document_id=official_document_id)
                except NseShareholdingAcquisitionConflict:
                    if file_format != "XBRL/XML" or not _has_pit_corrected_manifest(destination, digest, source_url):
                        raise
                return NseShareholdingStagedArtifact(target, destination, digest, retrieved_at, source_url, "IDENTICAL")
            # Preserve the conflicting raw source as a distinct artifact.  The
            # existing importer then detects the immutable same-period conflict
            # rather than allowing a silent overwrite.
            destination = destination.with_name(destination.stem + f"-sha256-{digest[:12]}" + destination.suffix)
            if destination.exists() and sha256(destination.read_bytes()).hexdigest() == digest:
                return NseShareholdingStagedArtifact(target, destination, digest, retrieved_at, source_url, "CONFLICT_RETAINED")
            status = "CONFLICT_RETAINED"
        else:
            status = "STAGED"
        temporary = destination.with_suffix(destination.suffix + ".tmp")
        try:
            temporary.write_bytes(content)
            temporary.replace(destination)
            self._write_manifest(target, destination, digest, retrieved_at, source_url, file_format=file_format, issuer=issuer, reporting_period_end=reporting_period_end, official_publication_timestamp=official_publication_timestamp, official_document_id=official_document_id)
        finally:
            if temporary.exists():
                temporary.unlink()
        return NseShareholdingStagedArtifact(target, destination, digest, retrieved_at, source_url, status)

    def _write_manifest(self, target: NseReg31Target, artifact: Path, digest: str, retrieved_at: datetime, source_url: str, *, file_format: str, issuer: str | None, reporting_period_end: str | None, official_publication_timestamp: str | None, official_document_id: str | None) -> None:
        manifest = artifact.with_suffix(artifact.suffix + ".provenance.json")
        payload = {
            "provider": NSE_SHAREHOLDING_PROVIDER,
            "source_url": source_url,
            "symbol": target.symbol,
            "isin": target.isin,
            "retrieved_at": retrieved_at.isoformat(),
            "filename": artifact.name,
            "sha256": digest,
        }
        if file_format == "XBRL/XML":
            if not all((issuer, reporting_period_end, official_publication_timestamp, official_document_id)):
                raise NseShareholdingAcquisitionError("REG31_XBRL_UNSUPPORTED_STRUCTURE")
            payload.update({
                "file_format": file_format,
                "canonical_instrument_id": "NSE:" + target.isin,
                "issuer": issuer,
                "reporting_period_end": reporting_period_end,
                "official_publication_timestamp": official_publication_timestamp,
                "official_document_id": official_document_id,
                "filing_type": "REGULATION_31_SHAREHOLDING_PATTERN",
            })
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8") + b"\n"
        if manifest.exists():
            if manifest.read_bytes() != encoded:
                raise NseShareholdingAcquisitionConflict("NSE_SHAREHOLDING_PROVENANCE_CONFLICT")
            return
        temporary = manifest.with_suffix(manifest.suffix + ".tmp")
        try:
            temporary.write_bytes(encoded)
            temporary.replace(manifest)
        finally:
            if temporary.exists():
                temporary.unlink()


def _headers(accept: str = "text/html,application/xhtml+xml") -> dict[str, str]:
    return {
        "Accept": accept,
        "Referer": NSE_SHAREHOLDING_PAGE_URL,
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/136.0 Safari/537.36",
    }


def _require_official_response(response: requests.Response, *, expected_content_type: str) -> None:
    url = response.url
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.hostname != _OFFICIAL_HOST:
        raise NseShareholdingAcquisitionError("NSE_SHAREHOLDING_NON_OFFICIAL_RESPONSE")
    if response.status_code != 200:
        raise NseShareholdingAcquisitionError(f"NSE_SHAREHOLDING_HTTP_{response.status_code}")
    if expected_content_type not in response.headers.get("Content-Type", "").lower():
        raise NseShareholdingAcquisitionError("NSE_SHAREHOLDING_UNEXPECTED_CONTENT_TYPE")
    if len(response.content) == 0 or len(response.content) > _MAXIMUM_BYTES:
        raise NseShareholdingAcquisitionError("NSE_SHAREHOLDING_INVALID_PAYLOAD_SIZE")


def _require_archive_response(response: requests.Response, *, expected_content_type: str) -> None:
    parsed = urlsplit(response.url)
    if parsed.scheme != "https" or parsed.hostname != "nsearchives.nseindia.com":
        raise NseShareholdingAcquisitionError("NSE_SHAREHOLDING_NON_OFFICIAL_RESPONSE")
    if response.status_code != 200:
        raise NseShareholdingAcquisitionError(f"NSE_SHAREHOLDING_HTTP_{response.status_code}")
    if expected_content_type not in response.headers.get("Content-Type", "").lower():
        raise NseShareholdingAcquisitionError("NSE_SHAREHOLDING_UNEXPECTED_CONTENT_TYPE")
    if len(response.content) == 0 or len(response.content) > _MAXIMUM_BYTES:
        raise NseShareholdingAcquisitionError("NSE_SHAREHOLDING_INVALID_PAYLOAD_SIZE")


def _returned_identity(payload: bytes, target: NseReg31Target) -> tuple[str, dict[str, object]]:
    try:
        records = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise NseShareholdingAcquisitionError("NSE_SHAREHOLDING_IDENTITY_RESPONSE_INVALID") from error
    if not isinstance(records, list) or not records:
        raise NseShareholdingAcquisitionError("NSE_SHAREHOLDING_NO_RECORDS")
    if not all(isinstance(record, dict) and record.get("symbol") == target.symbol for record in records):
        raise NseShareholdingAcquisitionError("NSE_SHAREHOLDING_EXACT_IDENTITY_MISMATCH")
    isins = {record.get("isin") for record in records}
    if len(isins) != 1 or not isinstance(next(iter(isins)), str):
        raise NseShareholdingAcquisitionError("NSE_SHAREHOLDING_EXACT_IDENTITY_MISMATCH")
    latest = records[0]
    return next(iter(isins)), latest


def _verify_current_xbrl_identity(content: bytes, target: NseReg31Target, expected_issuer: str) -> None:
    try:
        root = ElementTree.fromstring(content)
    except ElementTree.ParseError as error:
        raise NseShareholdingAcquisitionError("NSE_SHAREHOLDING_CURRENT_ATTACHMENT_INVALID") from error
    if root.tag.rsplit("}", 1)[-1].split(":")[-1].casefold() != "xbrl":
        raise NseShareholdingAcquisitionError("REG31_XBRL_UNSUPPORTED_STRUCTURE")
    schema_refs = [value for element in root.iter() if element.tag.rsplit("}", 1)[-1].split(":")[-1] == "schemaRef" for value in element.attrib.values()]
    if not any("shp" in value.casefold() for value in schema_refs):
        raise NseShareholdingAcquisitionError("REG31_XBRL_FILING_TYPE_MISMATCH")
    values = {
        element.tag.rsplit("}", 1)[-1].casefold(): (element.text or "").strip()
        for element in root.iter() if element.text and element.text.strip()
    }
    isin, symbol, issuer = values.get("isin"), values.get("symbol"), values.get("nameofthecompany")
    if isin != target.isin:
        raise NseShareholdingAcquisitionError("REG31_XBRL_IDENTITY_MISMATCH")
    if symbol != target.symbol:
        raise NseShareholdingAcquisitionError("REG31_XBRL_SYMBOL_MISMATCH")
    if issuer is None or issuer.casefold() != expected_issuer.casefold():
        raise NseShareholdingAcquisitionError("REG31_XBRL_ISSUER_MISMATCH")


def _verify_csv(content: bytes, *, expected_company_name: str) -> None:
    try:
        reader = csv.DictReader(io.StringIO(content.decode("utf-8-sig")))
        headers = set(reader.fieldnames or ())
        first = next(reader, None)
    except (UnicodeDecodeError, csv.Error) as error:
        raise NseShareholdingAcquisitionError("NSE_SHAREHOLDING_CSV_INVALID") from error
    if not _CSV_REQUIRED_HEADERS.issubset(headers) or first is None:
        raise NseShareholdingAcquisitionError("NSE_SHAREHOLDING_CSV_SCHEMA_INVALID")
    if any((row.get("COMPANY") or "").casefold() != expected_company_name.casefold() for row in (first, *reader)):
        raise NseShareholdingAcquisitionError("NSE_SHAREHOLDING_CSV_IDENTITY_MISMATCH")


def _official_filename(disposition: str | None, target: NseReg31Target, retrieved_at: datetime) -> str:
    match = re.search(r"filename=([^;]+)", disposition or "", re.IGNORECASE)
    candidate = match.group(1).strip().strip('"') if match else ""
    if not _SAFE_FILENAME.fullmatch(candidate) or f"-{target.symbol}-" not in candidate:
        candidate = f"CF-Shareholding-Pattern-equities-{target.symbol}-{retrieved_at:%d-%b-%Y}.csv"
    return candidate


def _nse_date_to_iso(value: str) -> str:
    for pattern in ("%d-%b-%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, pattern).date().isoformat()
        except ValueError:
            continue
    raise NseShareholdingAcquisitionError("REG31_XBRL_PERIOD_MISMATCH")


def _nse_timestamp_to_iso(value: str) -> str:
    for pattern in ("%d-%b-%Y %H:%M:%S", "%Y-%m-%dT%H:%M:%S%z"):
        try:
            parsed = datetime.strptime(value, pattern)
            return parsed.replace(tzinfo=ZoneInfo("Asia/Kolkata")).astimezone(UTC).isoformat() if parsed.tzinfo is None else parsed.astimezone(UTC).isoformat()
        except ValueError:
            continue
    raise NseShareholdingAcquisitionError("REG31_XBRL_UNSUPPORTED_STRUCTURE")


def _has_pit_corrected_manifest(artifact: Path, digest: str, source_url: str) -> bool:
    path = artifact.with_name(artifact.name + ".metadata-correction-v1.json")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return False
    return (
        isinstance(payload, dict)
        and payload.get("raw_sha256") == digest
        and payload.get("source_url") == source_url
        and payload.get("policy") == "nse-reg31-pit-timestamp-correction / v1"
        and isinstance(payload.get("corrected_published_at"), str)
    )


__all__ = (
    "APPROVED_NSE_REG31_TARGETS", "NSE_SHAREHOLDING_EXPORT_URL", "NSE_SHAREHOLDING_PAGE_URL",
    "NseOfficialShareholdingAcquirer", "NseReg31Target", "NseShareholdingAcquisitionConflict",
    "NseShareholdingAcquisitionError", "NseShareholdingStagedArtifact",
)
