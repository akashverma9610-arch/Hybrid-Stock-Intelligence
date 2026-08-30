"""Validated local staging for official file-based evidence sources.

External downloaders may place files in ``incoming``.  They are never trusted
canonical writers: this module delegates parsing to the established importer,
then archives accepted source files or quarantines malformed files.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import subprocess
from typing import Callable, Mapping, Protocol

from app.data_operations.models import (
    EvidenceRefreshOutcome,
    EvidenceRefreshRequest,
    EvidenceRefreshStatus,
    ReconciliationStatus,
)
from app.market_data.nse_delivery import NseDeliveryReportImporter


class DeliveryImporter(Protocol):
    def import_csv(self, path: Path, *, source_url: str, source_page: str, fetched_at: datetime, targets: Mapping[str, tuple[str, str | None]]): ...


@dataclass(frozen=True, slots=True)
class DeliveryAcquisitionManifest:
    """Safe, non-canonical result returned by the local Node acquirer."""

    requested_session: date
    source_filename: str
    source_url: str
    acquired_at: datetime
    byte_count: int
    sha256: str | None
    temporary_path: Path | None
    staged_path: Path | None
    status: str
    error_code: str | None = None

    def __post_init__(self) -> None:
        if self.status not in {"ACQUIRED", "ALREADY_ACQUIRED", "NOT_YET_AVAILABLE", "SOURCE_UNAVAILABLE", "INVALID_RESPONSE", "FAILED"}:
            raise ValueError("DELIVERY_ACQUISITION_STATUS_INVALID")
        if self.acquired_at.tzinfo is None or self.acquired_at.utcoffset() is None:
            raise ValueError("DELIVERY_ACQUISITION_TIMESTAMP_NAIVE")
        if self.byte_count < 0:
            raise ValueError("DELIVERY_ACQUISITION_BYTE_COUNT_INVALID")


class DeliveryAcquirer(Protocol):
    def acquire(self, requested_session: date) -> DeliveryAcquisitionManifest: ...


class NodeDeliveryAcquirer:
    """Invokes the acquisition-only Node CLI; it never receives canonical stores."""

    def __init__(self, root: Path, *, node_executable: str = "node", timeout_seconds: int = 20) -> None:
        self._root = root.resolve()
        self._node = node_executable
        self._timeout_seconds = timeout_seconds
        self._script = self._root / "automation" / "nse_data_bot" / "src" / "delivery_acquirer.ts"

    @classmethod
    def from_environment(cls, root: Path, environ: Mapping[str, str] | None = None) -> "NodeDeliveryAcquirer | None":
        values = os.environ if environ is None else environ
        raw_enabled = values.get("NSE_DELIVERY_ACQUISITION_ENABLED", "false").strip().lower()
        if raw_enabled not in {"true", "1", "yes", "on", "false", "0", "no", "off"}:
            raise ValueError("NSE_DELIVERY_ACQUISITION_ENABLED must be a boolean value.")
        if raw_enabled not in {"true", "1", "yes", "on"}:
            return None
        try:
            timeout = int(values.get("NSE_DELIVERY_ACQUISITION_TIMEOUT_SECONDS", "20"))
        except ValueError as error:
            raise ValueError("NSE_DELIVERY_ACQUISITION_TIMEOUT_SECONDS must be an integer.") from error
        if timeout < 1:
            raise ValueError("NSE_DELIVERY_ACQUISITION_TIMEOUT_SECONDS must be positive.")
        return cls(root, node_executable=values.get("NSE_DATA_BOT_NODE_EXECUTABLE", "node"), timeout_seconds=timeout)

    def acquire(self, requested_session: date) -> DeliveryAcquisitionManifest:
        now = datetime.now(UTC)
        filename = f"sec_bhavdata_full_{requested_session.strftime('%d%m%Y')}.csv"
        source_url = f"https://archives.nseindia.com/products/content/{filename}"
        if not self._script.is_file():
            return DeliveryAcquisitionManifest(requested_session, filename, source_url, now, 0, None, None, None, "FAILED", "DELIVERY_ACQUIRER_SCRIPT_MISSING")
        command = (
            self._node, "--experimental-strip-types", str(self._script), "acquire-delivery",
            "--date", requested_session.isoformat(), "--root", str(self._root),
            "--timeout-ms", str(self._timeout_seconds * 1000),
        )
        try:
            result = subprocess.run(command, cwd=self._root, capture_output=True, text=True, timeout=self._timeout_seconds + 5, check=False)
        except FileNotFoundError:
            return DeliveryAcquisitionManifest(requested_session, filename, source_url, now, 0, None, None, None, "FAILED", "NODE_EXECUTABLE_UNAVAILABLE")
        except subprocess.TimeoutExpired:
            return DeliveryAcquisitionManifest(requested_session, filename, source_url, now, 0, None, None, None, "SOURCE_UNAVAILABLE", "NSE_DELIVERY_ACQUISITION_TIMEOUT")
        try:
            payload = json.loads(result.stdout.strip())
            manifest = self._manifest_from_payload(payload, requested_session)
        except (TypeError, ValueError, json.JSONDecodeError):
            return DeliveryAcquisitionManifest(requested_session, filename, source_url, now, 0, None, None, None, "FAILED", "DELIVERY_ACQUIRER_PROTOCOL_INVALID")
        if result.returncode and manifest.status in {"ACQUIRED", "ALREADY_ACQUIRED"}:
            return DeliveryAcquisitionManifest(requested_session, filename, source_url, now, 0, None, None, None, "FAILED", "DELIVERY_ACQUIRER_EXIT_FAILED")
        return manifest

    def _manifest_from_payload(self, payload: object, requested_session: date) -> DeliveryAcquisitionManifest:
        if not isinstance(payload, dict) or payload.get("family") != "DELIVERY" or payload.get("source") != "NSE_OFFICIAL":
            raise ValueError("DELIVERY_ACQUIRER_PROTOCOL_INVALID")
        if payload.get("requestedSession") != requested_session.isoformat():
            raise ValueError("DELIVERY_ACQUIRER_SESSION_MISMATCH")
        source_filename = payload.get("sourceFilename")
        source_url = payload.get("sourceUrl")
        status = payload.get("status")
        acquired_at = _parse_acquired_at(payload.get("acquiredAt"))
        if not isinstance(source_filename, str) or not isinstance(source_url, str) or not source_url.startswith("https://archives.nseindia.com/") or not isinstance(status, str):
            raise ValueError("DELIVERY_ACQUIRER_PROTOCOL_INVALID")
        temporary = _contained_path(self._root, payload.get("temporaryPath"))
        staged = _contained_path(self._root, payload.get("stagedPath"))
        byte_count = payload.get("byteCount")
        digest = payload.get("sha256")
        if not isinstance(byte_count, int) or byte_count < 0 or digest is not None and (not isinstance(digest, str) or len(digest) != 64):
            raise ValueError("DELIVERY_ACQUIRER_PROTOCOL_INVALID")
        error_code = payload.get("errorCode")
        if error_code is not None and not isinstance(error_code, str):
            raise ValueError("DELIVERY_ACQUIRER_PROTOCOL_INVALID")
        return DeliveryAcquisitionManifest(requested_session, source_filename, source_url, acquired_at, byte_count, digest, temporary, staged, status, error_code)


@dataclass(frozen=True, slots=True)
class FileStagingLayout:
    root: Path

    def incoming(self, family: str) -> Path:
        return self.root / "incoming" / family

    def archive(self, family: str) -> Path:
        return self.root / "archive" / family

    def quarantine(self, family: str) -> Path:
        return self.root / "quarantine" / family

    def ensure(self, family: str) -> None:
        for directory in (self.incoming(family), self.archive(family), self.quarantine(family)):
            directory.mkdir(parents=True, exist_ok=True)


def _destination(directory: Path, source: Path) -> Path:
    digest = sha256(source.read_bytes()).hexdigest()[:12]
    return directory / f"{source.stem}-{digest}{source.suffix.lower()}"


def _move_once(source: Path, destination: Path) -> None:
    """Archive/quarantine a staged copy once without reprocessing its bytes."""
    if destination.exists():
        source.unlink()
        return
    shutil.move(str(source), str(destination))


class NseDeliveryStagingJob:
    """Runs the existing strict delivery importer for bounded staged files.

    There is deliberately no NSE HTTP downloader here.  Official acquisition
    remains an explicitly configured external source, while validation,
    provenance, idempotency, archive and quarantine are controlled locally.
    """

    def __init__(
        self,
        importer: NseDeliveryReportImporter | DeliveryImporter,
        targets: Mapping[str, tuple[str, str | None]],
        layout: FileStagingLayout,
        *,
        source_url: str = "https://www.nseindia.com/all-reports",
        source_page: str = "https://www.nseindia.com/all-reports",
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        acquirer: DeliveryAcquirer | None = None,
        session_selector: Callable[[EvidenceRefreshRequest], date] | None = None,
    ) -> None:
        self._importer = importer
        self._targets = dict(targets)
        self._layout = layout
        self._source_url = source_url
        self._source_page = source_page
        self._clock = clock
        self._acquirer = acquirer
        self._session_selector = session_selector or (lambda request: request.requested_as_of.date())

    def refresh(self, request: EvidenceRefreshRequest) -> EvidenceRefreshOutcome:
        family = "delivery"
        self._layout.ensure(family)
        acquired: DeliveryAcquisitionManifest | None = None
        if self._acquirer is not None:
            acquired = self._acquirer.acquire(self._session_selector(request))
        files = tuple(sorted(self._layout.incoming(family).glob("*.csv"), key=lambda item: item.name.lower()))
        if not files:
            return _empty_delivery_outcome(acquired)
        accepted = duplicates = rejected = unresolved = 0
        latest = None
        references: list[str] = []
        findings: list[tuple[ReconciliationStatus, str, str]] = []
        for path in files:
            manifest = acquired if acquired is not None and acquired.staged_path is not None and path.resolve() == acquired.staged_path.resolve() else None
            try:
                report = self._importer.import_csv(
                    path, source_url=self._source_url, source_page=self._source_page,
                    fetched_at=manifest.acquired_at if manifest is not None else self._clock(), targets=self._targets,
                )
            except (OSError, UnicodeError, ValueError) as error:
                destination = _destination(self._layout.quarantine(family), path)
                _move_once(path, destination)
                rejected += 1
                code = str(error) or "DELIVERY_FILE_INVALID"
                findings.append((ReconciliationStatus.INVALID_EVIDENCE, destination.name, code))
                continue
            destination = _destination(self._layout.archive(family), path)
            _move_once(path, destination)
            accepted += report.accepted
            duplicates += report.duplicates
            rejected += report.rejected
            unresolved += report.unresolved
            latest = report.artifact.trade_date if latest is None else max(latest, report.artifact.trade_date)
            references.append(report.artifact.report_id)
            if manifest is not None:
                references.append(manifest.source_url)
            if report.rejected:
                findings.append((ReconciliationStatus.INVALID_EVIDENCE, report.artifact.report_id, "DELIVERY_ROWS_REJECTED"))
            if report.unresolved:
                findings.append((ReconciliationStatus.GAP_FOUND, report.artifact.report_id, "DELIVERY_TARGETS_UNRESOLVED"))
        status = (
            EvidenceRefreshStatus.INVALID_EVIDENCE if rejected and not accepted and not duplicates
            else EvidenceRefreshStatus.PARTIAL if rejected or unresolved
            else EvidenceRefreshStatus.NO_CHANGE if not accepted and duplicates
            else EvidenceRefreshStatus.COMPLETE
        )
        warnings = tuple(sorted(set(
            (("DELIVERY_ROWS_REJECTED",) if rejected else ())
            + (("DELIVERY_TARGETS_UNRESOLVED",) if unresolved else ())
        )))
        return EvidenceRefreshOutcome(
            status, "NSE_OFFICIAL", discovered_count=len(files), accepted_count=accepted,
            duplicate_count=duplicates, rejected_count=rejected, gap_count=unresolved,
            accepted_through=latest, source_fingerprint=sha256("|".join(sorted(references)).encode()).hexdigest() if references else None,
            verified_from_store=latest is not None, error_summary="DELIVERY_FILE_INVALID" if status is EvidenceRefreshStatus.INVALID_EVIDENCE else None,
            warnings=warnings, source_references=tuple(sorted(set(references))), findings=tuple(findings),
        )


def _empty_delivery_outcome(acquired: DeliveryAcquisitionManifest | None) -> EvidenceRefreshOutcome:
    if acquired is None:
        return EvidenceRefreshOutcome(EvidenceRefreshStatus.NO_CHANGE, "NSE_OFFICIAL", warnings=("DELIVERY_STAGING_EMPTY",))
    if acquired.status == "NOT_YET_AVAILABLE":
        return EvidenceRefreshOutcome(EvidenceRefreshStatus.NO_CHANGE, "NSE_OFFICIAL", warnings=("DELIVERY_NOT_YET_AVAILABLE",), source_references=(acquired.source_url,))
    if acquired.status in {"SOURCE_UNAVAILABLE", "FAILED"}:
        return EvidenceRefreshOutcome(EvidenceRefreshStatus.SOURCE_UNAVAILABLE, "NSE_OFFICIAL", error_summary=acquired.error_code or "NSE_DELIVERY_SOURCE_UNAVAILABLE", warnings=(acquired.error_code or "NSE_DELIVERY_SOURCE_UNAVAILABLE",), source_references=(acquired.source_url,))
    if acquired.status == "INVALID_RESPONSE":
        return EvidenceRefreshOutcome(EvidenceRefreshStatus.INVALID_EVIDENCE, "NSE_OFFICIAL", failure_kind=None, error_summary=acquired.error_code or "NSE_DELIVERY_INVALID_RESPONSE", warnings=(acquired.error_code or "NSE_DELIVERY_INVALID_RESPONSE",), source_references=(acquired.source_url,))
    if acquired.status == "ALREADY_ACQUIRED":
        return EvidenceRefreshOutcome(EvidenceRefreshStatus.NO_CHANGE, "NSE_OFFICIAL", warnings=("DELIVERY_ALREADY_ACQUIRED",), source_references=(acquired.source_url,))
    return EvidenceRefreshOutcome(EvidenceRefreshStatus.FAILED, "NSE_OFFICIAL", error_summary="DELIVERY_ACQUISITION_PROTOCOL_INVALID", warnings=("DELIVERY_ACQUISITION_PROTOCOL_INVALID",), source_references=(acquired.source_url,))


def _parse_acquired_at(value: object) -> datetime:
    if not isinstance(value, str):
        raise ValueError("DELIVERY_ACQUIRER_PROTOCOL_INVALID")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("DELIVERY_ACQUIRER_PROTOCOL_INVALID")
    return parsed


def _contained_path(root: Path, value: object) -> Path | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("DELIVERY_ACQUIRER_PROTOCOL_INVALID")
    resolved = Path(value).resolve()
    try:
        resolved.relative_to(root)
    except ValueError as error:
        raise ValueError("DELIVERY_ACQUIRER_PATH_ESCAPE") from error
    return resolved
