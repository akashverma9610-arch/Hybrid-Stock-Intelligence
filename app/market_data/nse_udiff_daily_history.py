"""Immutable NSE UDiFF Final-Bhavcopy daily-history acquisition.

This module is an additive exchange-fact boundary.  It retains the exact ZIP
published by NSE and writes provider-versioned daily observations through the
existing historical-bar store.  It deliberately does *not* choose the source
for canonical technical reads, derive adjusted prices, infer historical
publication time, or make an indicator, setup, portfolio, or execution call.
"""
from __future__ import annotations

import base64
import csv
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from hashlib import sha256
from io import BytesIO, StringIO
from time import sleep
from typing import Callable, Iterable, Mapping, Protocol
from urllib.parse import urlsplit
import zipfile
from zoneinfo import ZoneInfo

import requests

from app.domain.models import DataQuality
from app.historical.guard import manifest_fingerprint
from app.market_data.historical import (
    BarWriteOutcome, HistoricalBarConflictArtifact, HistoricalBarStore,
)
from app.market_data.models import (
    AdjustmentStatus, CanonicalOHLCVBar, Exchange, InstrumentIdentity,
    InstrumentType, MarketDataProvenance, MarketDataQualityValidator, Timeframe,
)
from app.storage.core_api_snapshot_repository import (
    CoreApiSnapshot, CoreApiSnapshotFamily, CoreApiSnapshotRepository,
)
from app.universe_analysis.models import NseEquityInstrument, UniverseSnapshot
from app.universe_analysis.service import CoreUniverseAnalysisStore


NSE_UDIFF_SOURCE_FAMILY = "NSE_CM_UDIFF_FINAL_BHAVCOPY"
NSE_UDIFF_SOURCE_VERSION = "nse-udiff-final-bhavcopy-v1"
NSE_UDIFF_NORMALIZATION_VERSION = "nse-udiff-final-bhavcopy-v1"
# A distinct provider identity intentionally has no entry in the existing
# market-source tier map.  It preserves authoritative raw observations without
# silently changing Core V1 canonical-read selection.
NSE_UDIFF_BAR_PROVIDER = "NSE_UDIFF_OFFICIAL"
NSE_UDIFF_SOURCE_BASIS = "EXCHANGE_EOD_TRADE_PRICE"
NSE_UDIFF_START = date(2024, 7, 8)
NSE_UDIFF_END = date(2026, 8, 31)
NSE_UDIFF_SCHEMA_VERSION = "udiff-final-bhavcopy-34-fields-v1"
NSE_UDIFF_ARTIFACT_HOST = "nsearchives.nseindia.com"
NSE_UDIFF_URL_PREFIX = "https://nsearchives.nseindia.com/content/cm/"
_IST = ZoneInfo("Asia/Kolkata")

UDIFF_COLUMNS = (
    "TradDt", "BizDt", "Sgmt", "Src", "FinInstrmTp", "FinInstrmId", "ISIN",
    "TckrSymb", "SctySrs", "XpryDt", "FininstrmActlXpryDt", "StrkPric",
    "OptnTp", "FinInstrmNm", "OpnPric", "HghPric", "LwPric", "ClsPric",
    "LastPric", "PrvsClsgPric", "UndrlygPric", "SttlmPric", "OpnIntrst",
    "ChngInOpnIntrst", "TtlTradgVol", "TtlTrfVal", "TtlNbOfTxsExctd", "SsnId",
    "NewBrdLotQty", "Rmks", "Rsvd1", "Rsvd2", "Rsvd3", "Rsvd4",
)


class NseUdiffDailyStatus(StrEnum):
    ARTIFACT_VALID = "ARTIFACT_VALID"
    SOURCE_UNAVAILABLE = "SOURCE_UNAVAILABLE"
    SOURCE_BLOCKED = "SOURCE_BLOCKED"
    SOURCE_SCHEMA_DRIFT = "SOURCE_SCHEMA_DRIFT"
    SOURCE_ARCHIVE_INVALID = "SOURCE_ARCHIVE_INVALID"
    SOURCE_DATE_MISMATCH = "SOURCE_DATE_MISMATCH"
    SOURCE_TRANSPORT_FAILURE = "SOURCE_TRANSPORT_FAILURE"


class NseUdiffIdentityStatus(StrEnum):
    EXACT_IDENTITY_RESOLVED = "EXACT_IDENTITY_RESOLVED"
    HISTORICAL_IDENTITY_RESOLVED = "HISTORICAL_IDENTITY_RESOLVED"
    IDENTITY_DISCONTINUITY = "IDENTITY_DISCONTINUITY"
    IDENTITY_UNRESOLVED = "IDENTITY_UNRESOLVED"
    OUT_OF_ELIGIBLE_UNIVERSE = "OUT_OF_ELIGIBLE_UNIVERSE"


@dataclass(frozen=True, slots=True)
class NseUdiffDailySourceArtifact:
    """One exact downloaded ZIP; raw rows remain recoverable from this value."""

    artifact_id: str
    acquisition_id: str
    trade_date: date
    source_url: str
    filename: str | None
    content_sha256: str
    byte_size: int
    source_columns: tuple[str, ...]
    row_count: int
    schema_status: NseUdiffDailyStatus
    observed_at: datetime
    raw_zip_base64: str
    fingerprint: str

    def __post_init__(self) -> None:
        if (
            not self.artifact_id.startswith("nse-udiff-artifact:")
            or not self.acquisition_id.startswith("nse-udiff-acquisition:")
            or not _is_aware(self.observed_at)
            or self.byte_size < 1
            or self.row_count < 0
            or len(self.content_sha256) != 64
            or self.schema_status not in {
                NseUdiffDailyStatus.ARTIFACT_VALID,
                NseUdiffDailyStatus.SOURCE_SCHEMA_DRIFT,
                NseUdiffDailyStatus.SOURCE_ARCHIVE_INVALID,
                NseUdiffDailyStatus.SOURCE_DATE_MISMATCH,
            }
            or _sha256(_decode_zip(self.raw_zip_base64)) != self.content_sha256
            or self.fingerprint != _artifact_fingerprint(self)
        ):
            raise ValueError("NSE_UDIFF_SOURCE_ARTIFACT_INVALID")


@dataclass(frozen=True, slots=True)
class NseUdiffDailyAcquisitionReceipt:
    receipt_id: str
    acquisition_id: str
    trade_date: date
    status: NseUdiffDailyStatus
    observed_at: datetime
    artifact_id: str | None
    source_url: str
    rows_seen: int
    eligible_rows: int
    exact_identity_rows: int
    identity_discontinuities: int
    unresolved_identity_rows: int
    invalid_rows: int
    zero_volume_rows: int
    inserted: int
    duplicates: int
    conflicts: int
    error_code: str | None
    fingerprint: str

    def __post_init__(self) -> None:
        success = self.status is NseUdiffDailyStatus.ARTIFACT_VALID
        counts = (
            self.rows_seen, self.eligible_rows, self.exact_identity_rows,
            self.identity_discontinuities, self.unresolved_identity_rows,
            self.invalid_rows, self.zero_volume_rows, self.inserted,
            self.duplicates, self.conflicts,
        )
        if (
            not self.receipt_id.startswith("nse-udiff-receipt:")
            or not self.acquisition_id.startswith("nse-udiff-acquisition:")
            or not _is_aware(self.observed_at)
            or any(value < 0 for value in counts)
            or (success and (self.artifact_id is None or self.error_code is not None))
            or (not success and self.error_code is None)
            or (not success and self.inserted)
            or self.fingerprint != _receipt_fingerprint(self)
        ):
            raise ValueError("NSE_UDIFF_ACQUISITION_RECEIPT_INVALID")


@dataclass(frozen=True, slots=True)
class NseUdiffDailyManifestSession:
    trade_date: date
    receipt_id: str
    status: NseUdiffDailyStatus
    artifact_id: str | None


@dataclass(frozen=True, slots=True)
class NseUdiffDailyAcquisitionManifest:
    manifest_id: str
    acquisition_id: str
    universe_snapshot_id: str
    universe_snapshot_checksum: str
    requested_start: date
    requested_end: date
    requested_weekdays: tuple[date, ...]
    sessions: tuple[NseUdiffDailyManifestSession, ...]
    source_family: str
    source_version: str
    source_schema_version: str
    observed_at: datetime
    fingerprint: str

    def __post_init__(self) -> None:
        dates = tuple(item.trade_date for item in self.sessions)
        if (
            not self.manifest_id.startswith("nse-udiff-manifest:")
            or not self.acquisition_id.startswith("nse-udiff-acquisition:")
            or not self.universe_snapshot_id
            or not self.universe_snapshot_checksum
            or self.source_family != NSE_UDIFF_SOURCE_FAMILY
            or self.source_version != NSE_UDIFF_SOURCE_VERSION
            or self.source_schema_version != NSE_UDIFF_SCHEMA_VERSION
            or self.requested_start > self.requested_end
            or self.requested_weekdays != _weekdays(self.requested_start, self.requested_end)
            or dates != tuple(sorted(set(dates)))
            or any(item not in self.requested_weekdays for item in dates)
            or not _is_aware(self.observed_at)
            or self.fingerprint != _manifest_fingerprint(self)
        ):
            raise ValueError("NSE_UDIFF_ACQUISITION_MANIFEST_INVALID")


@dataclass(frozen=True, slots=True)
class NseUdiffDailyTarget:
    canonical_instrument_id: str
    isin: str
    current_symbol: str
    instrument: InstrumentIdentity

    @classmethod
    def from_instrument(cls, value: NseEquityInstrument) -> "NseUdiffDailyTarget":
        if (
            value.exchange.upper() != "NSE" or value.security_type.upper() != "EQUITY"
            or not value.instrument_id or not value.isin or not value.symbol
            or value.instrument_id != f"NSE:{value.isin.upper()}"
        ):
            raise ValueError("NSE_UDIFF_CURRENT_TARGET_EXACT_ISIN_REQUIRED")
        return cls(
            value.instrument_id, value.isin.upper(), value.symbol.upper(),
            InstrumentIdentity(
                value.instrument_id, Exchange.NSE, value.symbol.upper(), value.symbol.upper(),
                value.isin.upper(), None, InstrumentType.NSE_EQUITY, value.company_name,
            ),
        )


@dataclass(frozen=True, slots=True)
class NseUdiffDailyFetchResult:
    status: NseUdiffDailyStatus
    trade_date: date
    source_url: str
    observed_at: datetime
    raw_zip: bytes | None
    error_code: str | None = None

    def __post_init__(self) -> None:
        if not _is_aware(self.observed_at) or self.source_url != nse_udiff_daily_url(self.trade_date):
            raise ValueError("NSE_UDIFF_FETCH_RESULT_INVALID")
        success = self.status is NseUdiffDailyStatus.ARTIFACT_VALID
        if (success and (not self.raw_zip or self.error_code is not None)) or (not success and (self.raw_zip is not None or self.error_code is None)):
            raise ValueError("NSE_UDIFF_FETCH_RESULT_STATE_INVALID")


class NseUdiffDailySource(Protocol):
    def fetch(self, trade_date: date) -> NseUdiffDailyFetchResult: ...


class NseOfficialUdiffDailySource:
    """Bounded HTTPS reader for a single official date-labelled UDiFF ZIP."""

    def __init__(
        self, *, session_factory: Callable[[], requests.Session] = requests.Session,
        timeout_seconds: float = 30.0, observed_at: Callable[[], datetime] = lambda: datetime.now(UTC),
        delay_seconds: float = 0.2,
    ) -> None:
        if timeout_seconds <= 0 or delay_seconds < 0:
            raise ValueError("NSE_UDIFF_SOURCE_CONFIGURATION_INVALID")
        self._session_factory, self._timeout, self._observed_at, self._delay = session_factory, timeout_seconds, observed_at, delay_seconds

    def fetch(self, trade_date: date) -> NseUdiffDailyFetchResult:
        url = nse_udiff_daily_url(trade_date)
        session = self._session_factory()
        try:
            try:
                response = session.get(url, headers={"Accept": "application/zip", "User-Agent": "HSI-NSE-UDIFF-Acquisition/1.0"}, timeout=self._timeout)
            except requests.Timeout:
                return NseUdiffDailyFetchResult(NseUdiffDailyStatus.SOURCE_TRANSPORT_FAILURE, trade_date, url, _utc(self._observed_at()), None, "NSE_UDIFF_SOURCE_TIMEOUT")
            except requests.RequestException:
                return NseUdiffDailyFetchResult(NseUdiffDailyStatus.SOURCE_TRANSPORT_FAILURE, trade_date, url, _utc(self._observed_at()), None, "NSE_UDIFF_SOURCE_TRANSPORT_FAILURE")
            observed = _utc(self._observed_at())
            if response.status_code in {403, 429}:
                return NseUdiffDailyFetchResult(NseUdiffDailyStatus.SOURCE_BLOCKED, trade_date, url, observed, None, "NSE_UDIFF_SOURCE_BLOCKED")
            if response.status_code == 404:
                return NseUdiffDailyFetchResult(NseUdiffDailyStatus.SOURCE_UNAVAILABLE, trade_date, url, observed, None, "NSE_UDIFF_ARTIFACT_UNAVAILABLE")
            if response.status_code >= 400:
                return NseUdiffDailyFetchResult(NseUdiffDailyStatus.SOURCE_TRANSPORT_FAILURE, trade_date, url, observed, None, "NSE_UDIFF_SOURCE_HTTP_FAILURE")
            if not response.content:
                return NseUdiffDailyFetchResult(NseUdiffDailyStatus.SOURCE_TRANSPORT_FAILURE, trade_date, url, observed, None, "NSE_UDIFF_EMPTY_RESPONSE")
            return NseUdiffDailyFetchResult(NseUdiffDailyStatus.ARTIFACT_VALID, trade_date, url, observed, bytes(response.content), None)
        finally:
            close = getattr(session, "close", None)
            if callable(close):
                close()
            if self._delay:
                sleep(self._delay)


class NseUdiffDailyHistoryStore:
    """Typed immutable records held in the established core snapshot table."""

    def __init__(self, repository: CoreApiSnapshotRepository) -> None:
        self._repository = repository

    def artifact(self, acquisition_id: str, trade_date: date) -> NseUdiffDailySourceArtifact | None:
        value = self._repository.get_snapshot(_artifact_id(acquisition_id, trade_date))
        return value.payload if value is not None and isinstance(value.payload, NseUdiffDailySourceArtifact) else None

    def save_artifact(self, value: NseUdiffDailySourceArtifact) -> bool:
        existing = self.artifact(value.acquisition_id, value.trade_date)
        if existing is not None:
            if existing != value:
                raise ValueError("NSE_UDIFF_ARTIFACT_IMMUTABILITY_CONFLICT")
            return False
        self._save(CoreApiSnapshotFamily.NSE_UDIFF_DAILY_SOURCE_ARTIFACT, value.artifact_id, value, value.observed_at, value.fingerprint)
        return True

    def receipts(self, acquisition_id: str) -> tuple[NseUdiffDailyAcquisitionReceipt, ...]:
        values = (
            item.payload for item in self._all(CoreApiSnapshotFamily.NSE_UDIFF_DAILY_ACQUISITION_RECEIPT)
            if isinstance(item.payload, NseUdiffDailyAcquisitionReceipt) and item.payload.acquisition_id == acquisition_id
        )
        return tuple(sorted(values, key=lambda item: (item.trade_date, item.observed_at, item.receipt_id)))

    def latest_receipt(self, acquisition_id: str, trade_date: date) -> NseUdiffDailyAcquisitionReceipt | None:
        values = tuple(item for item in self.receipts(acquisition_id) if item.trade_date == trade_date)
        return max(values, key=lambda item: (item.observed_at, item.receipt_id)) if values else None

    def save_receipt(self, value: NseUdiffDailyAcquisitionReceipt) -> bool:
        existing = self._repository.get_snapshot(value.receipt_id)
        if existing is not None:
            if existing.payload != value:
                raise ValueError("NSE_UDIFF_RECEIPT_IMMUTABILITY_CONFLICT")
            return False
        self._save(CoreApiSnapshotFamily.NSE_UDIFF_DAILY_ACQUISITION_RECEIPT, value.receipt_id, value, value.observed_at, value.fingerprint)
        return True

    def manifests(self, acquisition_id: str) -> tuple[NseUdiffDailyAcquisitionManifest, ...]:
        values = (
            item.payload for item in self._all(CoreApiSnapshotFamily.NSE_UDIFF_DAILY_ACQUISITION_MANIFEST)
            if isinstance(item.payload, NseUdiffDailyAcquisitionManifest) and item.payload.acquisition_id == acquisition_id
        )
        return tuple(sorted(values, key=lambda item: (item.observed_at, item.manifest_id)))

    def save_manifest(self, value: NseUdiffDailyAcquisitionManifest) -> bool:
        existing = self._repository.get_snapshot(value.manifest_id)
        if existing is not None:
            if existing.payload != value:
                raise ValueError("NSE_UDIFF_MANIFEST_IMMUTABILITY_CONFLICT")
            return False
        self._save(CoreApiSnapshotFamily.NSE_UDIFF_DAILY_ACQUISITION_MANIFEST, value.manifest_id, value, value.observed_at, value.fingerprint)
        return True

    def _save(self, family: CoreApiSnapshotFamily, identifier: str, payload: object, created_at: datetime, fingerprint: str) -> None:
        self._repository.save_snapshot(CoreApiSnapshot(identifier, family, "v1", "nse-udiff-daily-history-v1", fingerprint, created_at, payload))

    def _all(self, family: CoreApiSnapshotFamily) -> tuple[CoreApiSnapshot, ...]:
        values: list[CoreApiSnapshot] = []
        offset = 0
        while True:
            page = self._repository.list_snapshots(family, limit=100, offset=offset)
            values.extend(page)
            if len(page) < 100:
                return tuple(values)
            offset += len(page)


@dataclass(frozen=True, slots=True)
class NseUdiffDailyBackfillReport:
    acquisition_id: str
    manifest: NseUdiffDailyAcquisitionManifest
    attempted_sessions: int
    replayed_sessions: int
    source_blocked: bool
    receipts: tuple[NseUdiffDailyAcquisitionReceipt, ...]

    @property
    def inserted(self) -> int: return sum(item.inserted for item in self.receipts)
    @property
    def duplicates(self) -> int: return sum(item.duplicates for item in self.receipts)
    @property
    def source_rows(self) -> int: return sum(item.rows_seen for item in self.receipts if item.status is NseUdiffDailyStatus.ARTIFACT_VALID)


class NseUdiffDailyHistoryBackfill:
    """Resume-safe bounded UDiFF archive acquisition and additive bar import."""

    def __init__(
        self, *, source: NseUdiffDailySource, evidence: NseUdiffDailyHistoryStore,
        bars: HistoricalBarStore, targets: Iterable[NseUdiffDailyTarget],
        acquisition_id: str, universe_snapshot: UniverseSnapshot,
        requested_start: date = NSE_UDIFF_START, requested_end: date = NSE_UDIFF_END,
        max_attempts_per_session: int = 2,
    ) -> None:
        if requested_start < NSE_UDIFF_START or requested_end > NSE_UDIFF_END or requested_end < requested_start:
            raise ValueError("NSE_UDIFF_SOURCE_ERA_BOUNDARY_VIOLATION")
        if max_attempts_per_session < 1:
            raise ValueError("NSE_UDIFF_RETRY_POLICY_INVALID")
        values = tuple(sorted(targets, key=lambda item: item.canonical_instrument_id))
        by_isin = {item.isin: item for item in values}
        if len(by_isin) != len(values):
            raise ValueError("NSE_UDIFF_TARGET_ISIN_AMBIGUOUS")
        if not acquisition_id.startswith("nse-udiff-acquisition:") or not universe_snapshot.snapshot_id:
            raise ValueError("NSE_UDIFF_ACQUISITION_ID_INVALID")
        self._source, self._evidence, self._bars, self._targets = source, evidence, bars, by_isin
        self._acquisition_id, self._universe, self._start, self._end = acquisition_id, universe_snapshot, requested_start, requested_end
        self._max_attempts_per_session = max_attempts_per_session

    def run(self, *, max_sessions: int | None = None) -> NseUdiffDailyBackfillReport:
        if max_sessions is not None and max_sessions < 1:
            raise ValueError("NSE_UDIFF_BATCH_LIMIT_INVALID")
        attempted = replayed = 0
        source_blocked = False
        receipts: list[NseUdiffDailyAcquisitionReceipt] = []
        for trade_date in _weekdays(self._start, self._end):
            previous = self._evidence.latest_receipt(self._acquisition_id, trade_date)
            artifact = self._evidence.artifact(self._acquisition_id, trade_date)
            if previous is not None and previous.status is NseUdiffDailyStatus.ARTIFACT_VALID:
                replayed += 1
                continue
            if artifact is not None and artifact.schema_status is not NseUdiffDailyStatus.ARTIFACT_VALID:
                # Retained invalid/drifted bytes are a terminal source fact for
                # this immutable acquisition identity, never a redownload cue.
                replayed += 1
                continue
            attempts = sum(item.trade_date == trade_date for item in self._evidence.receipts(self._acquisition_id))
            if attempts >= self._max_attempts_per_session:
                replayed += 1
                continue
            if max_sessions is not None and attempted >= max_sessions:
                break
            attempted += 1
            receipt = self._acquire_or_replay_one(trade_date)
            receipts.append(receipt)
            if receipt.status is NseUdiffDailyStatus.SOURCE_BLOCKED:
                source_blocked = True
                break
        latest = {item.trade_date: item for item in self._evidence.receipts(self._acquisition_id)}
        latest.update({item.trade_date: item for item in receipts})
        sessions = tuple(
            NseUdiffDailyManifestSession(day, latest[day].receipt_id, latest[day].status, latest[day].artifact_id)
            for day in _weekdays(self._start, self._end) if day in latest
        )
        # A partial manifest intentionally reports only observed request
        # results.  The full immutable manifest is emitted once every weekday
        # has a durable receipt; until then replay state remains explicit.
        manifest = _manifest(
            self._acquisition_id, self._universe, self._start, self._end,
            sessions, _latest_observed(latest.values()), requested_weekdays=_weekdays(self._start, self._end),
        )
        self._evidence.save_manifest(manifest)
        return NseUdiffDailyBackfillReport(self._acquisition_id, manifest, attempted, replayed, source_blocked, tuple(receipts))

    def _acquire_or_replay_one(self, trade_date: date) -> NseUdiffDailyAcquisitionReceipt:
        artifact = self._evidence.artifact(self._acquisition_id, trade_date)
        if artifact is None:
            fetched = self._source.fetch(trade_date)
            if fetched.status is not NseUdiffDailyStatus.ARTIFACT_VALID:
                receipt = _failed_receipt(self._acquisition_id, fetched)
                self._evidence.save_receipt(receipt)
                return receipt
            artifact = _artifact_from_bytes(self._acquisition_id, fetched)
            self._evidence.save_artifact(artifact)
        return self._import_artifact(artifact)

    def _import_artifact(self, artifact: NseUdiffDailySourceArtifact) -> NseUdiffDailyAcquisitionReceipt:
        if artifact.schema_status is not NseUdiffDailyStatus.ARTIFACT_VALID:
            receipt = _artifact_failure_receipt(artifact)
            self._evidence.save_receipt(receipt)
            return receipt
        parsed = _parse_valid_archive(artifact)
        bars: list[CanonicalOHLCVBar] = []
        exact = discontinuities = unresolved = invalid = zero_volume = eligible = 0
        seen: set[tuple[str, str, str]] = set()
        for index, row in enumerate(parsed.rows):
            status, target = _resolve_target(row, self._targets)
            if status is NseUdiffIdentityStatus.OUT_OF_ELIGIBLE_UNIVERSE:
                continue
            eligible += 1
            if status is NseUdiffIdentityStatus.IDENTITY_DISCONTINUITY:
                discontinuities += 1
                continue
            if status is not NseUdiffIdentityStatus.EXACT_IDENTITY_RESOLVED or target is None:
                unresolved += 1
                continue
            duplicate_key = (target.canonical_instrument_id, _field(row, "FinInstrmId"), _field(row, "SctySrs"))
            if duplicate_key in seen:
                discontinuities += 1
                continue
            seen.add(duplicate_key)
            try:
                bar, has_zero_volume = _bar_from_row(artifact, parsed, index, row, target)
                MarketDataQualityValidator.validate_bar(bar)
            except ValueError:
                invalid += 1
                continue
            exact += 1
            zero_volume += int(has_zero_volume)
            bars.append(bar)
        outcomes = _upsert_many(self._bars, bars)
        inserted = sum(item is BarWriteOutcome.INSERTED for item in outcomes)
        duplicates = sum(item is BarWriteOutcome.IDENTICAL for item in outcomes)
        conflicts = sum(item is BarWriteOutcome.CONFLICT for item in outcomes)
        for bar, outcome in zip(bars, outcomes, strict=True):
            if outcome is BarWriteOutcome.CONFLICT:
                stored = self._bars.same_provider_bar(bar)
                if stored is not None:
                    self._bars.save_conflict_artifact(HistoricalBarConflictArtifact.from_bars(stored, bar, detected_at=artifact.observed_at, ingestion_run_id=self._acquisition_id))
        values = dict(
            acquisition_id=self._acquisition_id, trade_date=artifact.trade_date,
            status=NseUdiffDailyStatus.ARTIFACT_VALID, observed_at=artifact.observed_at,
            artifact_id=artifact.artifact_id, source_url=artifact.source_url,
            rows_seen=artifact.row_count, eligible_rows=eligible, exact_identity_rows=exact,
            identity_discontinuities=discontinuities, unresolved_identity_rows=unresolved,
            invalid_rows=invalid, zero_volume_rows=zero_volume, inserted=inserted,
            duplicates=duplicates, conflicts=conflicts, error_code=None,
        )
        receipt = _receipt(**values)
        self._evidence.save_receipt(receipt)
        return receipt


def nse_udiff_daily_url(trade_date: date) -> str:
    if trade_date < NSE_UDIFF_START:
        raise ValueError("NSE_UDIFF_LEGACY_ERA_NOT_READY")
    return f"{NSE_UDIFF_URL_PREFIX}BhavCopy_NSE_CM_0_0_0_{trade_date:%Y%m%d}_F_0000.csv.zip"


def nse_udiff_acquisition_id(universe_snapshot: UniverseSnapshot, *, start: date = NSE_UDIFF_START, end: date = NSE_UDIFF_END) -> str:
    if start < NSE_UDIFF_START or end > NSE_UDIFF_END or end < start:
        raise ValueError("NSE_UDIFF_SOURCE_ERA_BOUNDARY_VIOLATION")
    fingerprint = manifest_fingerprint(
        source_family=NSE_UDIFF_SOURCE_FAMILY, source_version=NSE_UDIFF_SOURCE_VERSION,
        schema=NSE_UDIFF_SCHEMA_VERSION, universe_snapshot_id=universe_snapshot.snapshot_id,
        universe_snapshot_checksum=universe_snapshot.checksum, start=start.isoformat(), end=end.isoformat(),
    )
    return f"nse-udiff-acquisition:{fingerprint[:32]}"


def build_local_nse_udiff_daily_backfill(*, source: NseUdiffDailySource | None = None) -> tuple[NseUdiffDailyHistoryBackfill, tuple[object, ...]]:
    """Compose the explicit local operation; imports no API or UI wiring."""
    from app.market_data.historical import SQLiteHistoricalBarStore
    from app.storage.database import DatabaseBackend, DatabaseSettings
    from app.storage.repository_factory import create_core_api_snapshot_repository

    settings = DatabaseSettings.local_runtime()
    if settings.backend is not DatabaseBackend.SQLITE:
        raise ValueError("NSE_UDIFF_LOCAL_BACKFILL_SQLITE_REQUIRED")
    path = settings.url.removeprefix("sqlite:///")
    repository = create_core_api_snapshot_repository(settings)
    universe_store = CoreUniverseAnalysisStore(repository)
    snapshot = universe_store.latest_universe_snapshot()
    if snapshot is None:
        raise ValueError("NSE_UDIFF_CURRENT_UNIVERSE_SNAPSHOT_REQUIRED")
    instruments = {item.instrument_id: item for item in universe_store.instruments_as_of(snapshot.as_of)}
    targets = tuple(
        NseUdiffDailyTarget.from_instrument(instruments[item])
        for item in snapshot.instrument_ids if item in instruments
    )
    if not targets:
        raise ValueError("NSE_UDIFF_CURRENT_TARGETS_REQUIRED")
    historical = SQLiteHistoricalBarStore(path)
    backfill = NseUdiffDailyHistoryBackfill(
        source=source or NseOfficialUdiffDailySource(), evidence=NseUdiffDailyHistoryStore(repository),
        bars=historical, targets=targets,
        acquisition_id=nse_udiff_acquisition_id(snapshot), universe_snapshot=snapshot,
    )
    return backfill, (historical, repository)


@dataclass(frozen=True, slots=True)
class _ParsedArchive:
    filename: str | None
    columns: tuple[str, ...]
    rows: tuple[Mapping[str, str], ...]
    status: NseUdiffDailyStatus
    error_code: str | None


def _artifact_from_bytes(acquisition_id: str, fetched: NseUdiffDailyFetchResult) -> NseUdiffDailySourceArtifact:
    assert fetched.raw_zip is not None
    inspected = _inspect_archive(fetched.raw_zip, fetched.trade_date)
    values = dict(
        artifact_id=_artifact_id(acquisition_id, fetched.trade_date), acquisition_id=acquisition_id,
        trade_date=fetched.trade_date, source_url=fetched.source_url, filename=inspected.filename,
        content_sha256=_sha256(fetched.raw_zip), byte_size=len(fetched.raw_zip),
        source_columns=inspected.columns, row_count=len(inspected.rows), schema_status=inspected.status,
        observed_at=fetched.observed_at, raw_zip_base64=base64.b64encode(fetched.raw_zip).decode("ascii"),
    )
    return NseUdiffDailySourceArtifact(**values, fingerprint=_artifact_values_fingerprint(values))


def _parse_valid_archive(artifact: NseUdiffDailySourceArtifact) -> _ParsedArchive:
    parsed = _inspect_archive(_decode_zip(artifact.raw_zip_base64), artifact.trade_date)
    if parsed.status is not NseUdiffDailyStatus.ARTIFACT_VALID:
        raise ValueError("NSE_UDIFF_ARTIFACT_REVALIDATION_FAILED")
    if parsed.columns != artifact.source_columns or len(parsed.rows) != artifact.row_count:
        raise ValueError("NSE_UDIFF_ARTIFACT_TAMPERED")
    return parsed


def _inspect_archive(raw_zip: bytes, trade_date: date) -> _ParsedArchive:
    try:
        with zipfile.ZipFile(BytesIO(raw_zip)) as archive:
            names = tuple(item for item in archive.namelist() if not item.endswith("/"))
            if len(names) != 1 or not names[0].endswith(".csv"):
                return _ParsedArchive(None, (), (), NseUdiffDailyStatus.SOURCE_ARCHIVE_INVALID, "NSE_UDIFF_ARCHIVE_MEMBER_INVALID")
            filename = names[0].rsplit("/", 1)[-1]
            expected = f"BhavCopy_NSE_CM_0_0_0_{trade_date:%Y%m%d}_F_0000.csv"
            if filename != expected:
                return _ParsedArchive(filename, (), (), NseUdiffDailyStatus.SOURCE_DATE_MISMATCH, "NSE_UDIFF_FILENAME_DATE_MISMATCH")
            text = archive.read(names[0]).decode("utf-8-sig", errors="strict")
    except (zipfile.BadZipFile, KeyError, UnicodeDecodeError):
        return _ParsedArchive(None, (), (), NseUdiffDailyStatus.SOURCE_ARCHIVE_INVALID, "NSE_UDIFF_ARCHIVE_INVALID")
    reader = csv.DictReader(StringIO(text))
    columns = tuple(reader.fieldnames or ())
    rows = tuple({str(key): str(value or "") for key, value in row.items() if key is not None} for row in reader)
    if columns != UDIFF_COLUMNS:
        return _ParsedArchive(filename, columns, rows, NseUdiffDailyStatus.SOURCE_SCHEMA_DRIFT, "SOURCE_SCHEMA_DRIFT")
    return _ParsedArchive(filename, columns, rows, NseUdiffDailyStatus.ARTIFACT_VALID, None)


def _resolve_target(row: Mapping[str, str], targets: Mapping[str, NseUdiffDailyTarget]) -> tuple[NseUdiffIdentityStatus, NseUdiffDailyTarget | None]:
    isin = _field(row, "ISIN").upper()
    target = targets.get(isin)
    if target is None:
        return NseUdiffIdentityStatus.OUT_OF_ELIGIBLE_UNIVERSE, None
    if _field(row, "TckrSymb").upper() != target.current_symbol:
        return NseUdiffIdentityStatus.IDENTITY_DISCONTINUITY, None
    if not _field(row, "FinInstrmId") or not _field(row, "SctySrs"):
        return NseUdiffIdentityStatus.IDENTITY_UNRESOLVED, None
    return NseUdiffIdentityStatus.EXACT_IDENTITY_RESOLVED, target


def _bar_from_row(artifact: NseUdiffDailySourceArtifact, parsed: _ParsedArchive, index: int, row: Mapping[str, str], target: NseUdiffDailyTarget) -> tuple[CanonicalOHLCVBar, bool]:
    trade_date = _date_field(_field(row, "TradDt"))
    business_date = _date_field(_field(row, "BizDt"))
    if trade_date != artifact.trade_date or business_date != artifact.trade_date:
        raise ValueError("NSE_UDIFF_ROW_DATE_INVALID")
    if (_field(row, "Sgmt"), _field(row, "Src"), _field(row, "FinInstrmTp")) != ("CM", "NSE", "STK"):
        raise ValueError("NSE_UDIFF_ROW_MARKET_SCOPE_INVALID")
    open_, high, low, close = tuple(_positive_decimal(_field(row, name)) for name in ("OpnPric", "HghPric", "LwPric", "ClsPric"))
    if high < max(open_, low, close) or low > min(open_, high, close):
        raise ValueError("NSE_UDIFF_OHLC_INVALID")
    volume = _nonnegative_integer(_field(row, "TtlTradgVol"))
    turnover = _nonnegative_decimal(_field(row, "TtlTrfVal"))
    trades = _nonnegative_integer(_field(row, "TtlNbOfTxsExctd"))
    # A labelled trading-date boundary is used as the canonical daily interval;
    # it is not represented as an asserted NSE market-close timestamp.
    start = datetime.combine(trade_date, datetime.min.time(), tzinfo=_IST).astimezone(UTC)
    end = start + timedelta(days=1)
    row_fingerprint = _fingerprint({"artifact": artifact.content_sha256, "row_index": index, "row": tuple((name, _field(row, name)) for name in UDIFF_COLUMNS)})
    values = (
        artifact.content_sha256, target.canonical_instrument_id, trade_date.isoformat(),
        _field(row, "FinInstrmId"), _field(row, "SctySrs"), row_fingerprint,
    )
    bar = CanonicalOHLCVBar(
        "nse-udiff:" + _sha256("|".join(values))[:32], target.instrument, Timeframe.DAILY,
        start, end, open_, high, low, close, volume, turnover, trades, AdjustmentStatus.RAW,
        MarketDataProvenance(
            NSE_UDIFF_BAR_PROVIDER, f"NSE:CM:{_field(row, 'FinInstrmId')}", start,
            None, artifact.observed_at, NSE_UDIFF_NORMALIZATION_VERSION,
            f"{artifact.artifact_id}:row:{index}:{row_fingerprint}", artifact.source_url,
        ),
        DataQuality.HIGH,
        tuple(sorted((
            "DAILY_VWAP_FROM_UDIFF_NOT_APPLICABLE", "EXCHANGE_EOD_TRADE_PRICE",
            "HISTORICAL_SOURCE_PUBLICATION_TIME_UNKNOWN", "LOGICAL_NSE_TRADING_DAY_INTERVAL_NOT_MARKET_CLOSE",
            f"NSE_UDIFF_ARTIFACT:{artifact.artifact_id}", f"NSE_UDIFF_BIZ_DATE:{business_date.isoformat()}",
            f"NSE_UDIFF_SESSION:{_field(row, 'SsnId')}", f"NSE_UDIFF_SERIES:{_field(row, 'SctySrs')}",
        ))),
    )
    return bar, volume == 0


def _upsert_many(store: HistoricalBarStore, bars: list[CanonicalOHLCVBar]) -> tuple[BarWriteOutcome, ...]:
    method = getattr(store, "upsert_many", None)
    if callable(method):
        return tuple(method(bars))
    return tuple(store.upsert(bar) for bar in bars)


def _failed_receipt(acquisition_id: str, fetched: NseUdiffDailyFetchResult) -> NseUdiffDailyAcquisitionReceipt:
    return _receipt(
        acquisition_id=acquisition_id, trade_date=fetched.trade_date, status=fetched.status,
        observed_at=fetched.observed_at, artifact_id=None, source_url=fetched.source_url,
        rows_seen=0, eligible_rows=0, exact_identity_rows=0, identity_discontinuities=0,
        unresolved_identity_rows=0, invalid_rows=0, zero_volume_rows=0, inserted=0,
        duplicates=0, conflicts=0, error_code=fetched.error_code,
    )


def _artifact_failure_receipt(artifact: NseUdiffDailySourceArtifact) -> NseUdiffDailyAcquisitionReceipt:
    error = {
        NseUdiffDailyStatus.SOURCE_SCHEMA_DRIFT: "SOURCE_SCHEMA_DRIFT",
        NseUdiffDailyStatus.SOURCE_ARCHIVE_INVALID: "NSE_UDIFF_ARCHIVE_INVALID",
        NseUdiffDailyStatus.SOURCE_DATE_MISMATCH: "NSE_UDIFF_FILENAME_DATE_MISMATCH",
    }[artifact.schema_status]
    return _receipt(
        acquisition_id=artifact.acquisition_id, trade_date=artifact.trade_date, status=artifact.schema_status,
        observed_at=artifact.observed_at, artifact_id=artifact.artifact_id, source_url=artifact.source_url,
        rows_seen=artifact.row_count, eligible_rows=0, exact_identity_rows=0, identity_discontinuities=0,
        unresolved_identity_rows=0, invalid_rows=0, zero_volume_rows=0, inserted=0,
        duplicates=0, conflicts=0, error_code=error,
    )


def _receipt(**values: object) -> NseUdiffDailyAcquisitionReceipt:
    fingerprint = _fingerprint(values)
    values["receipt_id"] = f"nse-udiff-receipt:{str(values['acquisition_id']).split(':')[-1]}:{values['trade_date']}:{fingerprint[:20]}"
    values["fingerprint"] = _fingerprint({key: value for key, value in values.items() if key not in {"receipt_id", "fingerprint"}})
    # The published receipt fingerprint excludes its derived id, avoiding a
    # circular identity input while still authenticating every semantic field.
    return NseUdiffDailyAcquisitionReceipt(**values)  # type: ignore[arg-type]


def _manifest(acquisition_id: str, universe: UniverseSnapshot, start: date, end: date, sessions: tuple[NseUdiffDailyManifestSession, ...], observed_at: datetime, *, requested_weekdays: tuple[date, ...]) -> NseUdiffDailyAcquisitionManifest:
    values = dict(
        acquisition_id=acquisition_id, universe_snapshot_id=universe.snapshot_id,
        universe_snapshot_checksum=universe.checksum, requested_start=start, requested_end=end,
        requested_weekdays=requested_weekdays, sessions=sessions, source_family=NSE_UDIFF_SOURCE_FAMILY,
        source_version=NSE_UDIFF_SOURCE_VERSION, source_schema_version=NSE_UDIFF_SCHEMA_VERSION,
        observed_at=observed_at,
    )
    fingerprint = _fingerprint(values)
    values["manifest_id"] = f"nse-udiff-manifest:{acquisition_id.split(':')[-1]}:{fingerprint[:20]}"
    values["fingerprint"] = fingerprint
    # Partial execution manifests retain the observed weekday subset.  Their
    # constructor checks the subset deterministically rather than claiming a
    # complete historical exchange calendar.
    return _manifest_value(values)


def _manifest_value(values: dict[str, object]) -> NseUdiffDailyAcquisitionManifest:
    return NseUdiffDailyAcquisitionManifest(**values)  # type: ignore[arg-type]


def _latest_observed(values: Iterable[NseUdiffDailyAcquisitionReceipt]) -> datetime:
    items = tuple(values)
    return max((item.observed_at for item in items), default=datetime(1970, 1, 1, tzinfo=UTC))


def _artifact_id(acquisition_id: str, trade_date: date) -> str:
    return f"nse-udiff-artifact:{acquisition_id.split(':')[-1]}:{trade_date.isoformat()}"


def _artifact_fingerprint(value: NseUdiffDailySourceArtifact) -> str:
    return _fingerprint({key: getattr(value, key) for key in (
        "artifact_id", "acquisition_id", "trade_date", "source_url", "filename", "content_sha256",
        "byte_size", "source_columns", "row_count", "schema_status", "observed_at",
    )})


def _artifact_values_fingerprint(values: Mapping[str, object]) -> str:
    return _fingerprint({key: values[key] for key in (
        "artifact_id", "acquisition_id", "trade_date", "source_url", "filename", "content_sha256",
        "byte_size", "source_columns", "row_count", "schema_status", "observed_at",
    )})


def _receipt_fingerprint(value: NseUdiffDailyAcquisitionReceipt) -> str:
    return _fingerprint({key: getattr(value, key) for key in (
        "acquisition_id", "trade_date", "status", "observed_at", "artifact_id", "source_url",
        "rows_seen", "eligible_rows", "exact_identity_rows", "identity_discontinuities",
        "unresolved_identity_rows", "invalid_rows", "zero_volume_rows", "inserted", "duplicates",
        "conflicts", "error_code",
    )})


def _manifest_fingerprint(value: NseUdiffDailyAcquisitionManifest) -> str:
    return _fingerprint({key: getattr(value, key) for key in (
        "acquisition_id", "universe_snapshot_id", "universe_snapshot_checksum", "requested_start",
        "requested_end", "requested_weekdays", "sessions", "source_family", "source_version",
        "source_schema_version", "observed_at",
    )})


def _fingerprint(value: object) -> str:
    return "sha256:" + manifest_fingerprint(value=value)


def _sha256(value: bytes | str) -> str:
    return sha256(value if isinstance(value, bytes) else value.encode("utf-8")).hexdigest()


def _decode_zip(value: str) -> bytes:
    try:
        return base64.b64decode(value.encode("ascii"), validate=True)
    except (ValueError, UnicodeEncodeError) as error:
        raise ValueError("NSE_UDIFF_ARTIFACT_RAW_BYTES_INVALID") from error


def _field(row: Mapping[str, str], name: str) -> str:
    return str(row.get(name, "")).strip()


def _positive_decimal(value: str) -> Decimal:
    try:
        result = Decimal(value)
    except InvalidOperation as error:
        raise ValueError("NSE_UDIFF_DECIMAL_INVALID") from error
    if not result.is_finite() or result <= 0:
        raise ValueError("NSE_UDIFF_DECIMAL_INVALID")
    return result


def _nonnegative_decimal(value: str) -> Decimal:
    try:
        result = Decimal(value)
    except InvalidOperation as error:
        raise ValueError("NSE_UDIFF_DECIMAL_INVALID") from error
    if not result.is_finite() or result < 0:
        raise ValueError("NSE_UDIFF_DECIMAL_INVALID")
    return result


def _nonnegative_integer(value: str) -> int:
    try:
        result = int(value)
    except ValueError as error:
        raise ValueError("NSE_UDIFF_INTEGER_INVALID") from error
    if result < 0 or Decimal(value) != Decimal(result):
        raise ValueError("NSE_UDIFF_INTEGER_INVALID")
    return result


def _date_field(value: str) -> date:
    for pattern in ("%Y-%m-%d", "%d-%b-%Y", "%d-%b-%y"):
        try:
            return datetime.strptime(value, pattern).date()
        except ValueError:
            pass
    raise ValueError("NSE_UDIFF_DATE_INVALID")


def _weekdays(start: date, end: date) -> tuple[date, ...]:
    values: list[date] = []
    current = start
    while current <= end:
        if current.weekday() < 5:
            values.append(current)
        current += timedelta(days=1)
    return tuple(values)


def _is_aware(value: datetime) -> bool:
    return value.tzinfo is not None and value.utcoffset() is not None


def _utc(value: datetime) -> datetime:
    if not _is_aware(value):
        raise ValueError("NSE_UDIFF_OBSERVED_AT_NAIVE")
    return value.astimezone(UTC)
