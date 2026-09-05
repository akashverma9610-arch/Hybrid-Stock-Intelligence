"""Bounded first-party NSE corporate-action coverage acquisition.

This additive source boundary retains the official API response exactly as
received, maps only exact NSE identities, and records query success separately
from an empty response or a source failure.  It never infers an action from a
price move, never changes retained OHLCV, and never claims that present-day
source observation was historically available.
"""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from enum import StrEnum
from hashlib import sha256
import json
import re
from time import sleep
from typing import Protocol

import requests

from app.historical.security_master import CorporateActionKind, HistoricalCorporateAction, HistoricalSecurityMasterStore
from app.storage.core_api_snapshot_repository import CoreApiSnapshot, CoreApiSnapshotFamily, CoreApiSnapshotRepository
from app.universe_analysis.service import CoreUniverseAnalysisStore


NSE_CORPORATE_ACTIONS_ENDPOINT = "https://www.nseindia.com/api/corporates-corporateActions"
NSE_CORPORATE_ACTIONS_PAGE = "https://www.nseindia.com/companies-listing/corporate-filings-actions"
NSE_CORPORATE_ACTIONS_SOURCE = "NSE_OFFICIAL_CORPORATE_ACTION_API"
NSE_CORPORATE_ACTIONS_VERSION = "nse-corporate-action-coverage-v1"
NSE_CORPORATE_ACTIONS_POLICY = "nse-corporate-action-coverage"
NSE_CORPORATE_ACTIONS_ACQUISITION_MODE = "EXCHANGE_WIDE_DATE_RANGE"
# Canonical NSE symbols may legally contain ``&`` (for example ``M&M``), so
# the acquisition accepts that established identity character without
# introducing any name-based matching or normalization.
_IDENTIFIER = re.compile(r"[A-Za-z0-9._:&-]+\Z")
_RATIO = re.compile(r"\b(\d+(?:\.\d+)?)\s*:\s*(\d+(?:\.\d+)?)\b")
_SPLIT_FACE_VALUE = re.compile(
    r"\bFROM\s+RS\.?\s*(\d+(?:\.\d+)?)\s*/?-?\s*PER\s+SHARE\s+TO\s+RS\.?\s*(\d+(?:\.\d+)?)\s*/?-?\s*PER\s+SHARE\b",
    re.IGNORECASE,
)


class NseCorporateActionAcquisitionError(ValueError):
    """Stable fail-closed acquisition or input error."""


class NseCorporateActionQueryStatus(StrEnum):
    SUCCESS_WITH_ACTIONS = "SUCCESS_WITH_ACTIONS"
    SUCCESS_EMPTY = "SUCCESS_EMPTY"
    SOURCE_BLOCKED = "SOURCE_BLOCKED"
    SOURCE_FAILED = "SOURCE_FAILED"
    INVALID_RESPONSE = "INVALID_RESPONSE"


class NseCorporateActionIdentityStatus(StrEnum):
    EXACT_ISIN_AND_SYMBOL = "EXACT_ISIN_AND_SYMBOL"
    EXACT_SYMBOL_EQ = "EXACT_SYMBOL_EQ"
    IDENTITY_UNRESOLVED = "IDENTITY_UNRESOLVED"
    IDENTITY_CONFLICT = "IDENTITY_CONFLICT"


class NseCorporateActionFamily(StrEnum):
    SPLIT = "SPLIT"
    BONUS = "BONUS"
    RIGHTS = "RIGHTS"
    DIVIDEND = "DIVIDEND"
    SPECIAL_DIVIDEND = "SPECIAL_DIVIDEND"
    AGM_DIVIDEND_MIXED = "AGM_DIVIDEND_MIXED"
    BUYBACK = "BUYBACK"
    MERGER = "MERGER"
    DEMERGER = "DEMERGER"
    CAPITAL_REDUCTION = "CAPITAL_REDUCTION"
    FACE_VALUE_CHANGE = "FACE_VALUE_CHANGE"
    SYMBOL_CHANGE = "SYMBOL_CHANGE"
    RELISTING = "RELISTING"
    INTEREST_REDEMPTION = "INTEREST_REDEMPTION"
    OTHER = "OTHER"
    UNKNOWN = "UNKNOWN"


class NseCorporateActionSecurityCoverageStatus(StrEnum):
    QUERY_SUCCESS_WITH_ACTIONS = "QUERY_SUCCESS_WITH_ACTIONS"
    QUERY_SUCCESS_NO_ACTIONS = "QUERY_SUCCESS_NO_ACTIONS"
    PARTIAL_DATE_RANGE = "PARTIAL_DATE_RANGE"
    QUERY_FAILED = "QUERY_FAILED"
    SOURCE_BLOCKED = "SOURCE_BLOCKED"
    IDENTITY_UNRESOLVED = "IDENTITY_UNRESOLVED"
    NOT_QUERIED = "NOT_QUERIED"


class NseCorporateActionContinuityStatus(StrEnum):
    NOT_CERTIFIED = "NOT_CERTIFIED"
    LIFECYCLE_SOURCE_REQUIRED = "LIFECYCLE_SOURCE_REQUIRED"


@dataclass(frozen=True, slots=True)
class NseCorporateActionQueryWindow:
    start_date: date
    end_date: date

    def __post_init__(self) -> None:
        if self.end_date < self.start_date:
            raise NseCorporateActionAcquisitionError("NSE_CORPORATE_ACTION_QUERY_WINDOW_INVALID")

    @property
    def key(self) -> str:
        return f"{self.start_date.isoformat()}:{self.end_date.isoformat()}"


@dataclass(frozen=True, slots=True)
class NseCorporateActionSourceResult:
    status: NseCorporateActionQueryStatus
    window: NseCorporateActionQueryWindow
    observed_at: datetime
    raw_response: str | None
    records: tuple[Mapping[str, object], ...]
    error_code: str | None = None

    def __post_init__(self) -> None:
        _aware(self.observed_at, "observed_at")
        if self.status in {NseCorporateActionQueryStatus.SUCCESS_WITH_ACTIONS, NseCorporateActionQueryStatus.SUCCESS_EMPTY}:
            if self.raw_response is None or self.error_code is not None:
                raise NseCorporateActionAcquisitionError("NSE_CORPORATE_ACTION_SOURCE_RESULT_INVALID")
            if self.status is NseCorporateActionQueryStatus.SUCCESS_EMPTY and self.records:
                raise NseCorporateActionAcquisitionError("NSE_CORPORATE_ACTION_EMPTY_RESULT_INVALID")
            if self.status is NseCorporateActionQueryStatus.SUCCESS_WITH_ACTIONS and not self.records:
                raise NseCorporateActionAcquisitionError("NSE_CORPORATE_ACTION_ACTION_RESULT_INVALID")
        elif not self.error_code:
            raise NseCorporateActionAcquisitionError("NSE_CORPORATE_ACTION_SOURCE_FAILURE_CODE_REQUIRED")


@dataclass(frozen=True, slots=True)
class NseCorporateActionSourceArtifact:
    artifact_id: str
    acquisition_id: str
    window: NseCorporateActionQueryWindow
    observed_at: datetime
    content_sha256: str
    raw_response: str
    record_count: int
    fingerprint: str

    def __post_init__(self) -> None:
        if not _valid_id(self.artifact_id, self.acquisition_id) or not _digest(self.content_sha256) or self.record_count < 0:
            raise NseCorporateActionAcquisitionError("NSE_CORPORATE_ACTION_ARTIFACT_INVALID")
        _aware(self.observed_at, "observed_at")
        if self.fingerprint != _fingerprint(_artifact_payload(self)):
            raise NseCorporateActionAcquisitionError("NSE_CORPORATE_ACTION_ARTIFACT_FINGERPRINT_INVALID")


@dataclass(frozen=True, slots=True)
class NseCorporateActionQueryReceipt:
    receipt_id: str
    acquisition_id: str
    window: NseCorporateActionQueryWindow
    status: NseCorporateActionQueryStatus
    observed_at: datetime
    record_count: int
    artifact_id: str | None
    error_code: str | None
    fingerprint: str

    def __post_init__(self) -> None:
        if not _valid_id(self.receipt_id, self.acquisition_id) or self.record_count < 0:
            raise NseCorporateActionAcquisitionError("NSE_CORPORATE_ACTION_QUERY_RECEIPT_INVALID")
        _aware(self.observed_at, "observed_at")
        success = self.status in {NseCorporateActionQueryStatus.SUCCESS_WITH_ACTIONS, NseCorporateActionQueryStatus.SUCCESS_EMPTY}
        # A failed/invalid response may still have an immutable raw artifact
        # (for example malformed JSON).  Only a successful response requires
        # an artifact; a failure must retain its typed reason and may retain
        # the source bytes without becoming an empty success.
        if (success and self.artifact_id is None) or (success and self.error_code is not None) or (not success and self.error_code is None):
            raise NseCorporateActionAcquisitionError("NSE_CORPORATE_ACTION_QUERY_RECEIPT_STATE_INVALID")
        if self.status is NseCorporateActionQueryStatus.SUCCESS_EMPTY and self.record_count:
            raise NseCorporateActionAcquisitionError("NSE_CORPORATE_ACTION_EMPTY_RECEIPT_INVALID")
        if self.status is NseCorporateActionQueryStatus.SUCCESS_WITH_ACTIONS and not self.record_count:
            raise NseCorporateActionAcquisitionError("NSE_CORPORATE_ACTION_ACTION_RECEIPT_INVALID")
        if self.fingerprint != _fingerprint(_receipt_payload(self)):
            raise NseCorporateActionAcquisitionError("NSE_CORPORATE_ACTION_QUERY_RECEIPT_FINGERPRINT_INVALID")


@dataclass(frozen=True, slots=True)
class NseCorporateActionObservation:
    observation_id: str
    acquisition_id: str
    artifact_id: str
    record_index: int
    raw_record_fingerprint: str
    symbol: str
    isin: str | None
    series: str | None
    raw_purpose: str
    family: NseCorporateActionFamily
    ex_date: datetime | None
    record_date: datetime | None
    book_closure_start: datetime | None
    book_closure_end: datetime | None
    canonical_instrument_id: str | None
    identity_status: NseCorporateActionIdentityStatus
    canonical_action_id: str | None
    adjustment_input_complete: bool
    warnings: tuple[str, ...]
    observed_at: datetime
    fingerprint: str

    def __post_init__(self) -> None:
        if not _valid_id(self.observation_id, self.acquisition_id, self.artifact_id) or self.record_index < 0 or not _digest(self.raw_record_fingerprint):
            raise NseCorporateActionAcquisitionError("NSE_CORPORATE_ACTION_OBSERVATION_INVALID")
        if not self.symbol or not self.raw_purpose or tuple(sorted(set(self.warnings))) != self.warnings:
            raise NseCorporateActionAcquisitionError("NSE_CORPORATE_ACTION_OBSERVATION_FIELDS_INVALID")
        _aware(self.observed_at, "observed_at")
        for field in ("ex_date", "record_date", "book_closure_start", "book_closure_end"):
            value = getattr(self, field)
            if value is not None:
                _aware(value, field)
        mapped = self.identity_status in {NseCorporateActionIdentityStatus.EXACT_ISIN_AND_SYMBOL, NseCorporateActionIdentityStatus.EXACT_SYMBOL_EQ}
        if mapped != (self.canonical_instrument_id is not None) or (self.canonical_action_id is not None and not mapped):
            raise NseCorporateActionAcquisitionError("NSE_CORPORATE_ACTION_OBSERVATION_IDENTITY_INVALID")
        if self.fingerprint != _fingerprint(_observation_payload(self)):
            raise NseCorporateActionAcquisitionError("NSE_CORPORATE_ACTION_OBSERVATION_FINGERPRINT_INVALID")


@dataclass(frozen=True, slots=True)
class NseCorporateActionSecurityCoverage:
    canonical_instrument_id: str
    status: NseCorporateActionSecurityCoverageStatus
    observation_ids: tuple[str, ...]
    continuity_status: NseCorporateActionContinuityStatus
    reasons: tuple[str, ...]

    def __post_init__(self) -> None:
        if not _valid_id(self.canonical_instrument_id) or self.observation_ids != tuple(sorted(set(self.observation_ids))) or tuple(sorted(set(self.reasons))) != self.reasons:
            raise NseCorporateActionAcquisitionError("NSE_CORPORATE_ACTION_SECURITY_COVERAGE_INVALID")
        if self.continuity_status is not NseCorporateActionContinuityStatus.LIFECYCLE_SOURCE_REQUIRED:
            raise NseCorporateActionAcquisitionError("NSE_CORPORATE_ACTION_LIFECYCLE_STATE_INVALID")


@dataclass(frozen=True, slots=True)
class NseCorporateActionCoverageAssessment:
    assessment_id: str
    acquisition_id: str
    universe_snapshot_id: str
    requested_window: NseCorporateActionQueryWindow
    coverages: tuple[NseCorporateActionSecurityCoverage, ...]
    observed_at: datetime
    fingerprint: str

    def __post_init__(self) -> None:
        identifiers = tuple(item.canonical_instrument_id for item in self.coverages)
        if not _valid_id(self.assessment_id, self.acquisition_id, self.universe_snapshot_id) or identifiers != tuple(sorted(set(identifiers))):
            raise NseCorporateActionAcquisitionError("NSE_CORPORATE_ACTION_COVERAGE_ASSESSMENT_INVALID")
        _aware(self.observed_at, "observed_at")
        if self.fingerprint != _fingerprint(_assessment_payload(self)):
            raise NseCorporateActionAcquisitionError("NSE_CORPORATE_ACTION_COVERAGE_ASSESSMENT_FINGERPRINT_INVALID")


@dataclass(frozen=True, slots=True)
class NseCorporateActionCoverageManifest:
    manifest_id: str
    acquisition_id: str
    universe_snapshot_id: str
    requested_window: NseCorporateActionQueryWindow
    source_family: str
    source_version: str
    acquisition_mode: str
    requested_instrument_ids: tuple[str, ...]
    query_receipt_ids: tuple[str, ...]
    source_artifact_ids: tuple[str, ...]
    successful_query_count: int
    empty_successful_query_count: int
    failed_query_count: int
    blocked_query_count: int
    invalid_query_count: int
    observation_count: int
    new_canonical_action_count: int
    duplicate_canonical_action_count: int
    coverage_assessment_id: str
    observed_at: datetime
    fingerprint: str

    def __post_init__(self) -> None:
        if not _valid_id(
            self.manifest_id,
            self.acquisition_id,
            self.universe_snapshot_id,
            self.coverage_assessment_id,
            self.source_family,
            self.source_version,
            self.acquisition_mode,
            *self.requested_instrument_ids,
        ):
            raise NseCorporateActionAcquisitionError("NSE_CORPORATE_ACTION_MANIFEST_INVALID")
        if (
            self.source_family != NSE_CORPORATE_ACTIONS_SOURCE
            or self.source_version != NSE_CORPORATE_ACTIONS_VERSION
            or self.acquisition_mode != NSE_CORPORATE_ACTIONS_ACQUISITION_MODE
            or not self.requested_instrument_ids
            or self.requested_instrument_ids != tuple(sorted(set(self.requested_instrument_ids)))
            or self.query_receipt_ids != tuple(sorted(set(self.query_receipt_ids)))
            or self.source_artifact_ids != tuple(sorted(set(self.source_artifact_ids)))
        ):
            raise NseCorporateActionAcquisitionError("NSE_CORPORATE_ACTION_MANIFEST_ORDER_INVALID")
        if min(
            self.successful_query_count,
            self.empty_successful_query_count,
            self.failed_query_count,
            self.blocked_query_count,
            self.invalid_query_count,
            self.observation_count,
            self.new_canonical_action_count,
            self.duplicate_canonical_action_count,
        ) < 0 or self.successful_query_count + self.failed_query_count + self.blocked_query_count + self.invalid_query_count != len(self.query_receipt_ids):
            raise NseCorporateActionAcquisitionError("NSE_CORPORATE_ACTION_MANIFEST_COUNT_INVALID")
        _aware(self.observed_at, "observed_at")
        if self.fingerprint != _fingerprint(_manifest_payload(self)):
            raise NseCorporateActionAcquisitionError("NSE_CORPORATE_ACTION_MANIFEST_FINGERPRINT_INVALID")


@dataclass(frozen=True, slots=True)
class NseCorporateActionBackfillResult:
    manifest: NseCorporateActionCoverageManifest
    assessment: NseCorporateActionCoverageAssessment
    query_receipts: tuple[NseCorporateActionQueryReceipt, ...]
    replayed: bool


class NseCorporateActionSource(Protocol):
    def fetch(self, window: NseCorporateActionQueryWindow) -> NseCorporateActionSourceResult: ...


class NseOfficialCorporateActionsSource:
    """One bounded official NSE query per supplied date window."""

    def __init__(
        self,
        *,
        session_factory: Callable[[], requests.Session] = requests.Session,
        timeout_seconds: float = 20.0,
        observed_at: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("NSE_CORPORATE_ACTION_SOURCE_CONFIGURATION_INVALID")
        self._session_factory = session_factory
        self._timeout = timeout_seconds
        self._observed_at = observed_at

    def fetch(self, window: NseCorporateActionQueryWindow) -> NseCorporateActionSourceResult:
        session = self._session_factory()
        try:
            try:
                try:
                    session.get(NSE_CORPORATE_ACTIONS_PAGE, headers=_page_headers(), timeout=self._timeout)
                except requests.RequestException:
                    pass
                response = session.get(
                    NSE_CORPORATE_ACTIONS_ENDPOINT,
                    headers=_api_headers(),
                    params={"index": "equities", "from_date": _nse_date(window.start_date), "to_date": _nse_date(window.end_date)},
                    timeout=self._timeout,
                )
            except requests.Timeout:
                return _failed_source_result(window, self._observed_at(), NseCorporateActionQueryStatus.SOURCE_FAILED, "NSE_CORPORATE_ACTION_TIMEOUT")
            except requests.RequestException:
                return _failed_source_result(window, self._observed_at(), NseCorporateActionQueryStatus.SOURCE_FAILED, "NSE_CORPORATE_ACTION_TRANSPORT_FAILURE")
            observed = _aware(self._observed_at(), "observed_at")
            if response.status_code in {403, 429}:
                return _failed_source_result(window, observed, NseCorporateActionQueryStatus.SOURCE_BLOCKED, "NSE_CORPORATE_ACTION_SOURCE_BLOCKED")
            if response.status_code >= 400:
                return _failed_source_result(window, observed, NseCorporateActionQueryStatus.SOURCE_FAILED, "NSE_CORPORATE_ACTION_HTTP_FAILURE")
            try:
                raw = response.content.decode("utf-8", errors="strict")
            except UnicodeDecodeError:
                return NseCorporateActionSourceResult(NseCorporateActionQueryStatus.INVALID_RESPONSE, window, observed, None, (), "NSE_CORPORATE_ACTION_RESPONSE_ENCODING_INVALID")
            try:
                payload = json.loads(raw)
            except (UnicodeDecodeError, json.JSONDecodeError):
                return NseCorporateActionSourceResult(NseCorporateActionQueryStatus.INVALID_RESPONSE, window, observed, raw, (), "NSE_CORPORATE_ACTION_INVALID_JSON")
            if not isinstance(payload, list) or any(not isinstance(item, Mapping) for item in payload):
                return NseCorporateActionSourceResult(NseCorporateActionQueryStatus.INVALID_RESPONSE, window, observed, raw, (), "NSE_CORPORATE_ACTION_RESPONSE_SCHEMA_INVALID")
            records = tuple(payload)
            return NseCorporateActionSourceResult(
                NseCorporateActionQueryStatus.SUCCESS_WITH_ACTIONS if records else NseCorporateActionQueryStatus.SUCCESS_EMPTY,
                window,
                observed,
                raw,
                records,
            )
        finally:
            close = getattr(session, "close", None)
            if callable(close):
                close()


class NseCorporateActionCoverageStore:
    """Immutable records in the existing core snapshot store, not a new database."""

    def __init__(self, repository: CoreApiSnapshotRepository) -> None:
        self._repository = repository

    def manifest(self, acquisition_id: str) -> NseCorporateActionCoverageManifest | None:
        identifier = _manifest_id(acquisition_id)
        value = self._repository.get_snapshot(identifier)
        return value.payload if value is not None and isinstance(value.payload, NseCorporateActionCoverageManifest) else None

    def query_receipts(self, acquisition_id: str) -> tuple[NseCorporateActionQueryReceipt, ...]:
        return tuple(sorted(
            (item.payload for item in _all(self._repository, CoreApiSnapshotFamily.NSE_CORPORATE_ACTION_QUERY_RECEIPT)
             if isinstance(item.payload, NseCorporateActionQueryReceipt) and item.payload.acquisition_id == acquisition_id),
            key=lambda item: (item.window.start_date, item.window.end_date, item.observed_at, item.receipt_id),
        ))

    def observations(self, acquisition_id: str) -> tuple[NseCorporateActionObservation, ...]:
        return tuple(sorted(
            (item.payload for item in _all(self._repository, CoreApiSnapshotFamily.NSE_CORPORATE_ACTION_OBSERVATION)
             if isinstance(item.payload, NseCorporateActionObservation) and item.payload.acquisition_id == acquisition_id),
            key=lambda item: item.observation_id,
        ))

    def save_artifact(self, value: NseCorporateActionSourceArtifact) -> None:
        self._save(CoreApiSnapshotFamily.NSE_CORPORATE_ACTION_SOURCE_ARTIFACT, value.artifact_id, value, value.observed_at)

    def save_receipt(self, value: NseCorporateActionQueryReceipt) -> None:
        self._save(CoreApiSnapshotFamily.NSE_CORPORATE_ACTION_QUERY_RECEIPT, value.receipt_id, value, value.observed_at)

    def save_observation(self, value: NseCorporateActionObservation) -> None:
        self._save(CoreApiSnapshotFamily.NSE_CORPORATE_ACTION_OBSERVATION, value.observation_id, value, value.observed_at)

    def save_assessment(self, value: NseCorporateActionCoverageAssessment) -> None:
        self._save(CoreApiSnapshotFamily.NSE_CORPORATE_ACTION_COVERAGE_ASSESSMENT, value.assessment_id, value, value.observed_at)

    def save_manifest(self, value: NseCorporateActionCoverageManifest) -> None:
        self._save(CoreApiSnapshotFamily.NSE_CORPORATE_ACTION_ACQUISITION_MANIFEST, value.manifest_id, value, value.observed_at)

    def _save(self, family: CoreApiSnapshotFamily, identifier: str, value: object, created_at: datetime) -> None:
        existing = self._repository.get_snapshot(identifier)
        if existing is not None:
            if existing.family is family and existing.payload == value:
                return
            raise NseCorporateActionAcquisitionError("NSE_CORPORATE_ACTION_IMMUTABLE_CONFLICT")
        # Each immutable contract validates a fingerprint over its explicit,
        # versioned payload in __post_init__.  The generic snapshot must retain
        # that same content fingerprint; re-serializing the dataclass here
        # would both be redundant and make the storage wrapper part of the
        # canonicalization contract.
        fingerprint = getattr(value, "fingerprint", None)
        if not isinstance(fingerprint, str) or not _digest(fingerprint):
            raise NseCorporateActionAcquisitionError("NSE_CORPORATE_ACTION_SNAPSHOT_FINGERPRINT_INVALID")
        self._repository.save_snapshot(CoreApiSnapshot(identifier, family, "v1", type(value).__name__, fingerprint, created_at, value))


class NseCorporateActionCoverageBackfill:
    """Controlled monthly official-source backfill with immutable receipts."""

    def __init__(
        self,
        *,
        repository: CoreApiSnapshotRepository,
        universe: CoreUniverseAnalysisStore,
        source: NseCorporateActionSource,
        master: HistoricalSecurityMasterStore | None = None,
        minimum_interval_seconds: float = 0.25,
        sleeper: Callable[[float], None] = sleep,
    ) -> None:
        if minimum_interval_seconds < 0:
            raise ValueError("NSE_CORPORATE_ACTION_PACING_INVALID")
        self._repository = repository
        self._universe = universe
        self._source = source
        self._master = master or HistoricalSecurityMasterStore(repository)
        self._store = NseCorporateActionCoverageStore(repository)
        self._minimum_interval = minimum_interval_seconds
        self._sleeper = sleeper

    def run(self, *, acquisition_id: str, start_date: date, end_date: date, observed_at: datetime) -> NseCorporateActionBackfillResult:
        if not _valid_id(acquisition_id):
            raise NseCorporateActionAcquisitionError("NSE_CORPORATE_ACTION_ACQUISITION_ID_INVALID")
        observed = _aware(observed_at, "observed_at")
        requested = NseCorporateActionQueryWindow(start_date, end_date)
        snapshot = self._universe.latest_universe_snapshot()
        if snapshot is None:
            raise NseCorporateActionAcquisitionError("NSE_CORPORATE_ACTION_UNIVERSE_SNAPSHOT_REQUIRED")
        existing = self._store.manifest(acquisition_id)
        if existing is not None:
            if existing.universe_snapshot_id != snapshot.snapshot_id or existing.requested_window != requested:
                raise NseCorporateActionAcquisitionError("NSE_CORPORATE_ACTION_ACQUISITION_SCOPE_CONFLICT")
            assessment_snapshot = self._repository.get_snapshot(existing.coverage_assessment_id)
            if assessment_snapshot is None or not isinstance(assessment_snapshot.payload, NseCorporateActionCoverageAssessment):
                raise NseCorporateActionAcquisitionError("NSE_CORPORATE_ACTION_ACQUISITION_MANIFEST_CORRUPT")
            return NseCorporateActionBackfillResult(existing, assessment_snapshot.payload, self._store.query_receipts(acquisition_id), True)

        # A later universe import can coexist in the snapshot store.  The
        # manifest must instead bind exactly to the eligible population frozen
        # by this snapshot, not every identity that happens to be valid as of
        # its timestamp.
        known_instruments = {
            item.instrument_id: item
            for item in self._universe.instruments_as_of(snapshot.as_of)
        }
        missing_snapshot_identities = tuple(
            identifier for identifier in snapshot.instrument_ids
            if identifier not in known_instruments
        )
        if missing_snapshot_identities:
            raise NseCorporateActionAcquisitionError("NSE_CORPORATE_ACTION_UNIVERSE_SNAPSHOT_IDENTITY_MISSING")
        instruments = _unique_instruments(
            tuple(known_instruments[identifier] for identifier in snapshot.instrument_ids)
        )
        windows = monthly_windows(requested.start_date, requested.end_date)
        receipts: list[NseCorporateActionQueryReceipt] = []
        artifacts: list[NseCorporateActionSourceArtifact] = []
        observations: list[NseCorporateActionObservation] = []
        new_actions = duplicate_actions = 0
        existing_actions = _existing_actions(self._repository)
        existing_by_key = {_action_key(item): item for item in existing_actions}
        for index, window in enumerate(windows):
            result = self._source.fetch(window)
            artifact = _artifact(acquisition_id, result)
            if artifact is not None:
                self._store.save_artifact(artifact)
                artifacts.append(artifact)
            receipt = _receipt(acquisition_id, result, artifact)
            self._store.save_receipt(receipt)
            receipts.append(receipt)
            if artifact is not None and result.status is NseCorporateActionQueryStatus.SUCCESS_WITH_ACTIONS:
                for record_index, record in enumerate(result.records):
                    observation, action = _observation(
                        acquisition_id=acquisition_id,
                        artifact=artifact,
                        record_index=record_index,
                        record=record,
                        instruments=instruments,
                    )
                    if action is not None:
                        prior = existing_by_key.get(_action_key(action))
                        if prior is not None:
                            observation = _with_canonical_action(observation, prior.action_id)
                            duplicate_actions += 1
                        else:
                            existing = self._repository.get_snapshot("historical-action:" + action.action_id)
                            if existing is not None:
                                if not isinstance(existing.payload, HistoricalCorporateAction) or _action_key(existing.payload) != _action_key(action):
                                    raise NseCorporateActionAcquisitionError("NSE_CORPORATE_ACTION_IMMUTABLE_CONFLICT")
                                observation = _with_canonical_action(observation, action.action_id)
                                duplicate_actions += 1
                            else:
                                self._master.save_action(action)
                                existing_by_key[_action_key(action)] = action
                                observation = _with_canonical_action(observation, action.action_id)
                                new_actions += 1
                    self._store.save_observation(observation)
                    observations.append(observation)
            if index + 1 < len(windows) and self._minimum_interval:
                self._sleeper(self._minimum_interval)
        assessment = _assessment(
            acquisition_id=acquisition_id,
            universe_snapshot_id=snapshot.snapshot_id,
            requested=requested,
            instruments=instruments,
            receipts=tuple(receipts),
            observations=tuple(observations),
            observed_at=observed,
        )
        self._store.save_assessment(assessment)
        manifest = _manifest(
            acquisition_id=acquisition_id,
            universe_snapshot_id=snapshot.snapshot_id,
            requested=requested,
            requested_instrument_ids=tuple(str(getattr(item, "instrument_id")) for item in instruments),
            receipts=tuple(receipts),
            artifacts=tuple(artifacts),
            observations=tuple(observations),
            new_actions=new_actions,
            duplicate_actions=duplicate_actions,
            assessment=assessment,
            observed_at=observed,
        )
        self._store.save_manifest(manifest)
        return NseCorporateActionBackfillResult(manifest, assessment, tuple(receipts), False)


def monthly_windows(start_date: date, end_date: date) -> tuple[NseCorporateActionQueryWindow, ...]:
    """Deterministically partition a source range without overlapping days."""
    if end_date < start_date:
        raise NseCorporateActionAcquisitionError("NSE_CORPORATE_ACTION_QUERY_WINDOW_INVALID")
    values: list[NseCorporateActionQueryWindow] = []
    cursor = start_date
    while cursor <= end_date:
        next_month = date(cursor.year + (cursor.month == 12), 1 if cursor.month == 12 else cursor.month + 1, 1)
        values.append(NseCorporateActionQueryWindow(cursor, min(end_date, date.fromordinal(next_month.toordinal() - 1))))
        cursor = next_month
    return tuple(values)


def _failed_source_result(window: NseCorporateActionQueryWindow, observed_at: datetime, status: NseCorporateActionQueryStatus, code: str) -> NseCorporateActionSourceResult:
    return NseCorporateActionSourceResult(status, window, _aware(observed_at, "observed_at"), None, (), code)


def _artifact(acquisition_id: str, result: NseCorporateActionSourceResult) -> NseCorporateActionSourceArtifact | None:
    if result.raw_response is None:
        return None
    digest = sha256(result.raw_response.encode("utf-8")).hexdigest()
    values = dict(
        artifact_id=_id("nse-ca-artifact", acquisition_id, result.window.key, digest),
        acquisition_id=acquisition_id,
        window=result.window,
        observed_at=_aware(result.observed_at, "observed_at"),
        content_sha256=digest,
        raw_response=result.raw_response,
        record_count=len(result.records),
    )
    return NseCorporateActionSourceArtifact(**values, fingerprint=_fingerprint(_artifact_payload_values(values)))


def _receipt(acquisition_id: str, result: NseCorporateActionSourceResult, artifact: NseCorporateActionSourceArtifact | None) -> NseCorporateActionQueryReceipt:
    values = dict(
        receipt_id=_id("nse-ca-query", acquisition_id, result.window.key, result.status.value, artifact.content_sha256 if artifact else result.error_code or "failure"),
        acquisition_id=acquisition_id,
        window=result.window,
        status=result.status,
        observed_at=_aware(result.observed_at, "observed_at"),
        record_count=len(result.records),
        artifact_id=artifact.artifact_id if artifact else None,
        error_code=result.error_code,
    )
    return NseCorporateActionQueryReceipt(**values, fingerprint=_fingerprint(_receipt_payload_values(values)))


def _observation(*, acquisition_id: str, artifact: NseCorporateActionSourceArtifact, record_index: int, record: Mapping[str, object], instruments: tuple[object, ...]) -> tuple[NseCorporateActionObservation, HistoricalCorporateAction | None]:
    raw_record = _canonical(record)
    raw_fingerprint = sha256(raw_record.encode("utf-8")).hexdigest()
    symbol = _text(record.get("symbol")).upper()
    purpose = _text(record.get("subject"))
    if not symbol or not purpose:
        raise NseCorporateActionAcquisitionError("NSE_CORPORATE_ACTION_REQUIRED_FIELDS_MISSING")
    isin = _optional_text(record.get("isin"))
    series = _optional_text(record.get("series"))
    family = _family(purpose)
    identity_status, instrument = _resolve_identity(symbol, isin, series.upper() if series else None, instruments)
    ex_date = _date(record.get("exDate"))
    record_date = _date(record.get("recDate"))
    warnings = ["HISTORICAL_SOURCE_KNOWN_AT_UNAVAILABLE"]
    numerator, denominator = _ratio(purpose, family)
    adjustment_complete = family in {NseCorporateActionFamily.SPLIT, NseCorporateActionFamily.BONUS} and numerator is not None and denominator is not None
    if family in {NseCorporateActionFamily.SPLIT, NseCorporateActionFamily.BONUS} and not adjustment_complete:
        warnings.append("ADJUSTMENT_INPUT_INCOMPLETE")
    if ex_date is None:
        warnings.append("EX_DATE_UNAVAILABLE")
    if identity_status in {NseCorporateActionIdentityStatus.IDENTITY_UNRESOLVED, NseCorporateActionIdentityStatus.IDENTITY_CONFLICT}:
        warnings.append(identity_status.value)
    values = dict(
        # An official response can, exceptionally, repeat an identical row.
        # Preserve the raw-row position as separate immutable provenance while
        # reconciling its logical canonical action below by semantic action key.
        observation_id=_id("nse-ca-observation", acquisition_id, artifact.artifact_id, str(record_index), raw_fingerprint),
        acquisition_id=acquisition_id,
        artifact_id=artifact.artifact_id,
        record_index=record_index,
        raw_record_fingerprint=raw_fingerprint,
        symbol=symbol,
        isin=isin,
        series=series,
        raw_purpose=purpose,
        family=family,
        ex_date=ex_date,
        record_date=record_date,
        book_closure_start=_date(record.get("bcStartDate")),
        book_closure_end=_date(record.get("bcEndDate")),
        canonical_instrument_id=str(getattr(instrument, "instrument_id")) if instrument is not None else None,
        identity_status=identity_status,
        canonical_action_id=None,
        adjustment_input_complete=adjustment_complete,
        warnings=tuple(sorted(set(warnings))),
        observed_at=artifact.observed_at,
    )
    observation = NseCorporateActionObservation(**values, fingerprint=_fingerprint(_observation_payload_values(values)))
    action = _historical_action(observation, artifact, numerator, denominator, record)
    return observation, action


def _with_canonical_action(value: NseCorporateActionObservation, action_id: str) -> NseCorporateActionObservation:
    values = {name: getattr(value, name) for name in NseCorporateActionObservation.__dataclass_fields__ if name != "fingerprint"}
    values["canonical_action_id"] = action_id
    return NseCorporateActionObservation(**values, fingerprint=_fingerprint(_observation_payload_values(values)))


def _historical_action(value: NseCorporateActionObservation, artifact: NseCorporateActionSourceArtifact, numerator: Decimal | None, denominator: Decimal | None, record: Mapping[str, object]) -> HistoricalCorporateAction | None:
    kind = {
        NseCorporateActionFamily.SPLIT: CorporateActionKind.SPLIT,
        NseCorporateActionFamily.BONUS: CorporateActionKind.BONUS,
        NseCorporateActionFamily.RIGHTS: CorporateActionKind.RIGHTS,
        NseCorporateActionFamily.DIVIDEND: CorporateActionKind.DIVIDEND,
        NseCorporateActionFamily.SPECIAL_DIVIDEND: CorporateActionKind.DIVIDEND,
        NseCorporateActionFamily.MERGER: CorporateActionKind.MERGER,
        NseCorporateActionFamily.DEMERGER: CorporateActionKind.DEMERGER,
        NseCorporateActionFamily.SYMBOL_CHANGE: CorporateActionKind.SYMBOL_CHANGE,
    }.get(value.family)
    if kind is None or value.canonical_instrument_id is None or value.ex_date is None:
        return None
    details = _canonical({
        "original_purpose": value.raw_purpose,
        "original_company_name": _text(record.get("comp")),
        "series": value.series or "",
        "face_value": _text(record.get("faceVal")),
        "book_closure_start_date": _text(record.get("bcStartDate")),
        "book_closure_end_date": _text(record.get("bcEndDate")),
        "api_isin": value.isin or "",
        "normalization_policy": NSE_CORPORATE_ACTIONS_POLICY,
        "normalization_version": NSE_CORPORATE_ACTIONS_VERSION,
    })
    action_id = _id("nse-ca-action", value.canonical_instrument_id, kind.value, value.ex_date.isoformat(), value.raw_record_fingerprint)
    return HistoricalCorporateAction(
        action_id,
        value.canonical_instrument_id,
        kind,
        _date(record.get("caBroadcastDate")),
        value.record_date,
        value.ex_date,
        value.ex_date,
        numerator,
        denominator,
        details,
        NSE_CORPORATE_ACTIONS_SOURCE,
        "nse-corporate-action-v1",
        value.observed_at,
        f"artifact_id={artifact.artifact_id};record_index={value.record_index}",
        value.warnings,
    )


def _assessment(*, acquisition_id: str, universe_snapshot_id: str, requested: NseCorporateActionQueryWindow, instruments: tuple[object, ...], receipts: tuple[NseCorporateActionQueryReceipt, ...], observations: tuple[NseCorporateActionObservation, ...], observed_at: datetime) -> NseCorporateActionCoverageAssessment:
    by_instrument: dict[str, list[NseCorporateActionObservation]] = defaultdict(list)
    unresolved_symbols: set[str] = set()
    for item in observations:
        if item.canonical_instrument_id is None:
            unresolved_symbols.add(item.symbol)
        else:
            by_instrument[item.canonical_instrument_id].append(item)
    statuses = {item.status for item in receipts}
    all_success = statuses <= {NseCorporateActionQueryStatus.SUCCESS_WITH_ACTIONS, NseCorporateActionQueryStatus.SUCCESS_EMPTY} and len(receipts) == len(monthly_windows(requested.start_date, requested.end_date))
    coverages = []
    for instrument in instruments:
        identifier = str(getattr(instrument, "instrument_id"))
        symbol = str(getattr(instrument, "symbol", "")).upper()
        matches = tuple(sorted(by_instrument.get(identifier, ()), key=lambda item: item.observation_id))
        if not receipts:
            status, reasons = NseCorporateActionSecurityCoverageStatus.NOT_QUERIED, ("NSE_CORPORATE_ACTION_NOT_QUERIED",)
        elif NseCorporateActionQueryStatus.SOURCE_BLOCKED in statuses:
            status, reasons = NseCorporateActionSecurityCoverageStatus.SOURCE_BLOCKED, ("NSE_CORPORATE_ACTION_SOURCE_BLOCKED",)
        elif not all_success:
            status, reasons = NseCorporateActionSecurityCoverageStatus.QUERY_FAILED, ("NSE_CORPORATE_ACTION_QUERY_FAILURE",)
        elif symbol in unresolved_symbols:
            status, reasons = NseCorporateActionSecurityCoverageStatus.IDENTITY_UNRESOLVED, ("NSE_CORPORATE_ACTION_IDENTITY_UNRESOLVED",)
        elif matches:
            status, reasons = NseCorporateActionSecurityCoverageStatus.QUERY_SUCCESS_WITH_ACTIONS, ("NSE_CORPORATE_ACTION_LIFECYCLE_SOURCE_REQUIRED",)
        else:
            status, reasons = NseCorporateActionSecurityCoverageStatus.QUERY_SUCCESS_NO_ACTIONS, ("NSE_CORPORATE_ACTION_LIFECYCLE_SOURCE_REQUIRED",)
        coverages.append(NseCorporateActionSecurityCoverage(identifier, status, tuple(item.observation_id for item in matches), NseCorporateActionContinuityStatus.LIFECYCLE_SOURCE_REQUIRED, reasons))
    values = dict(
        assessment_id=_id("nse-ca-coverage", acquisition_id, universe_snapshot_id, requested.key),
        acquisition_id=acquisition_id,
        universe_snapshot_id=universe_snapshot_id,
        requested_window=requested,
        coverages=tuple(sorted(coverages, key=lambda item: item.canonical_instrument_id)),
        observed_at=observed_at,
    )
    return NseCorporateActionCoverageAssessment(**values, fingerprint=_fingerprint(_assessment_payload_values(values)))


def _manifest(*, acquisition_id: str, universe_snapshot_id: str, requested: NseCorporateActionQueryWindow, requested_instrument_ids: tuple[str, ...], receipts: tuple[NseCorporateActionQueryReceipt, ...], artifacts: tuple[NseCorporateActionSourceArtifact, ...], observations: tuple[NseCorporateActionObservation, ...], new_actions: int, duplicate_actions: int, assessment: NseCorporateActionCoverageAssessment, observed_at: datetime) -> NseCorporateActionCoverageManifest:
    statuses = tuple(item.status for item in receipts)
    values = dict(
        manifest_id=_manifest_id(acquisition_id),
        acquisition_id=acquisition_id,
        universe_snapshot_id=universe_snapshot_id,
        requested_window=requested,
        source_family=NSE_CORPORATE_ACTIONS_SOURCE,
        source_version=NSE_CORPORATE_ACTIONS_VERSION,
        acquisition_mode=NSE_CORPORATE_ACTIONS_ACQUISITION_MODE,
        requested_instrument_ids=tuple(sorted(set(requested_instrument_ids))),
        query_receipt_ids=tuple(sorted(item.receipt_id for item in receipts)),
        source_artifact_ids=tuple(sorted(item.artifact_id for item in artifacts)),
        successful_query_count=sum(item in {NseCorporateActionQueryStatus.SUCCESS_WITH_ACTIONS, NseCorporateActionQueryStatus.SUCCESS_EMPTY} for item in statuses),
        empty_successful_query_count=sum(item is NseCorporateActionQueryStatus.SUCCESS_EMPTY for item in statuses),
        failed_query_count=sum(item is NseCorporateActionQueryStatus.SOURCE_FAILED for item in statuses),
        blocked_query_count=sum(item is NseCorporateActionQueryStatus.SOURCE_BLOCKED for item in statuses),
        invalid_query_count=sum(item is NseCorporateActionQueryStatus.INVALID_RESPONSE for item in statuses),
        observation_count=len(observations),
        new_canonical_action_count=new_actions,
        duplicate_canonical_action_count=duplicate_actions,
        coverage_assessment_id=assessment.assessment_id,
        observed_at=observed_at,
    )
    return NseCorporateActionCoverageManifest(**values, fingerprint=_fingerprint(_manifest_payload_values(values)))


def _unique_instruments(values: tuple[object, ...]) -> tuple[object, ...]:
    by_id: dict[str, object] = {}
    for value in values:
        identifier = str(getattr(value, "instrument_id", ""))
        if not _valid_id(identifier):
            raise NseCorporateActionAcquisitionError("NSE_CORPORATE_ACTION_UNIVERSE_IDENTITY_INVALID")
        existing = by_id.get(identifier)
        if existing is not None and existing != value:
            raise NseCorporateActionAcquisitionError("NSE_CORPORATE_ACTION_UNIVERSE_IDENTITY_CONFLICT")
        by_id[identifier] = value
    return tuple(by_id[key] for key in sorted(by_id))


def _resolve_identity(symbol: str, isin: str | None, series: str | None, instruments: tuple[object, ...]) -> tuple[NseCorporateActionIdentityStatus, object | None]:
    # The frozen population is main-board equity.  An API record without its
    # exact EQ series is still retained, but cannot become a canonical equity
    # action through a symbol fallback (or an otherwise coincident ISIN).
    if series != "EQ":
        return NseCorporateActionIdentityStatus.IDENTITY_UNRESOLVED, None
    exact_symbol = tuple(item for item in instruments if str(getattr(item, "symbol", "")).upper() == symbol)
    if isin:
        exact_isin = tuple(item for item in instruments if str(getattr(item, "isin", "") or "").upper() == isin)
        if len(exact_isin) == 1 and str(getattr(exact_isin[0], "symbol", "")).upper() == symbol:
            return NseCorporateActionIdentityStatus.EXACT_ISIN_AND_SYMBOL, exact_isin[0]
        return (NseCorporateActionIdentityStatus.IDENTITY_CONFLICT if exact_isin or exact_symbol else NseCorporateActionIdentityStatus.IDENTITY_UNRESOLVED), None
    if len(exact_symbol) == 1:
        return NseCorporateActionIdentityStatus.EXACT_SYMBOL_EQ, exact_symbol[0]
    return (NseCorporateActionIdentityStatus.IDENTITY_CONFLICT if exact_symbol else NseCorporateActionIdentityStatus.IDENTITY_UNRESOLVED), None


def _family(purpose: str) -> NseCorporateActionFamily:
    value = purpose.upper()
    if not value.strip(): return NseCorporateActionFamily.UNKNOWN
    if "DEMERGER" in value: return NseCorporateActionFamily.DEMERGER
    if "MERGER" in value or "AMALGAMATION" in value: return NseCorporateActionFamily.MERGER
    if "SYMBOL CHANGE" in value or "CHANGE IN SYMBOL" in value: return NseCorporateActionFamily.SYMBOL_CHANGE
    if "SPLIT" in value or "SUB-DIVISION" in value: return NseCorporateActionFamily.SPLIT
    if "BONUS" in value: return NseCorporateActionFamily.BONUS
    if "RIGHTS" in value: return NseCorporateActionFamily.RIGHTS
    if "SPECIAL" in value and "DIVIDEND" in value: return NseCorporateActionFamily.SPECIAL_DIVIDEND
    if "AGM" in value and "DIVIDEND" in value: return NseCorporateActionFamily.AGM_DIVIDEND_MIXED
    if "DIVIDEND" in value: return NseCorporateActionFamily.DIVIDEND
    if "BUY BACK" in value or "BUYBACK" in value: return NseCorporateActionFamily.BUYBACK
    if "CAPITAL REDUCTION" in value or "REDUCTION OF CAPITAL" in value: return NseCorporateActionFamily.CAPITAL_REDUCTION
    if "FACE VALUE" in value: return NseCorporateActionFamily.FACE_VALUE_CHANGE
    if "RELIST" in value: return NseCorporateActionFamily.RELISTING
    if "INTEREST" in value or "REDEMPTION" in value: return NseCorporateActionFamily.INTEREST_REDEMPTION
    return NseCorporateActionFamily.OTHER


def _ratio(purpose: str, family: NseCorporateActionFamily) -> tuple[Decimal | None, Decimal | None]:
    match = _RATIO.search(purpose)
    if match is not None:
        return Decimal(match.group(1)), Decimal(match.group(2))
    if family is NseCorporateActionFamily.SPLIT:
        match = _SPLIT_FACE_VALUE.search(purpose)
        if match is not None:
            return Decimal(match.group(1)), Decimal(match.group(2))
    return None, None


def _action_key(value: HistoricalCorporateAction) -> tuple[object, ...]:
    purpose = _purpose_from_details(value.details)
    return (
        value.canonical_instrument_id, value.kind.value, value.effective_date.astimezone(UTC),
        value.record_date.astimezone(UTC) if value.record_date else None,
        value.ex_date.astimezone(UTC) if value.ex_date else None,
        value.ratio_numerator, value.ratio_denominator, purpose,
    )


def _purpose_from_details(details: str | None) -> str:
    if not details:
        return ""
    try:
        decoded = json.loads(details)
    except json.JSONDecodeError:
        return details.strip().upper()
    return _text(decoded.get("original_purpose")).upper() if isinstance(decoded, Mapping) else ""


def _existing_actions(repository: CoreApiSnapshotRepository) -> tuple[HistoricalCorporateAction, ...]:
    return tuple(
        item.payload for item in _all(repository, CoreApiSnapshotFamily.HISTORICAL_CORPORATE_ACTION)
        if isinstance(item.payload, HistoricalCorporateAction)
    )


def _all(repository: CoreApiSnapshotRepository, family: CoreApiSnapshotFamily) -> tuple[CoreApiSnapshot, ...]:
    values: list[CoreApiSnapshot] = []
    offset = 0
    while True:
        page = repository.list_snapshots(family, limit=100, offset=offset)
        values.extend(page)
        if len(page) < 100:
            return tuple(values)
        offset += len(page)


def _page_headers() -> dict[str, str]:
    return {"User-Agent": _user_agent(), "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"}


def _api_headers() -> dict[str, str]:
    return {"User-Agent": _user_agent(), "Accept": "application/json", "Referer": NSE_CORPORATE_ACTIONS_PAGE}


def _user_agent() -> str:
    return "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"


def _nse_date(value: date) -> str:
    return value.strftime("%d-%m-%Y")


def _date(value: object) -> datetime | None:
    text = _optional_text(value)
    if text is None or text == "-": return None
    for form in ("%d-%b-%Y %H:%M:%S", "%d-%b-%Y %H:%M", "%d-%b-%Y"):
        try: return datetime.strptime(text, form).replace(tzinfo=UTC)
        except ValueError: continue
    raise NseCorporateActionAcquisitionError("NSE_CORPORATE_ACTION_DATE_INVALID")


def _artifact_payload(value: NseCorporateActionSourceArtifact) -> dict[str, object]: return _artifact_payload_values({name: getattr(value, name) for name in NseCorporateActionSourceArtifact.__dataclass_fields__ if name != "fingerprint"})
def _artifact_payload_values(value: Mapping[str, object]) -> dict[str, object]: return {"policy": NSE_CORPORATE_ACTIONS_POLICY, "version": NSE_CORPORATE_ACTIONS_VERSION, "artifact_id": value["artifact_id"], "acquisition_id": value["acquisition_id"], "window": _window(value["window"]), "observed_at": _time(value["observed_at"]), "content_sha256": value["content_sha256"], "raw_response": value["raw_response"], "record_count": value["record_count"]}
def _receipt_payload(value: NseCorporateActionQueryReceipt) -> dict[str, object]: return _receipt_payload_values({name: getattr(value, name) for name in NseCorporateActionQueryReceipt.__dataclass_fields__ if name != "fingerprint"})
def _receipt_payload_values(value: Mapping[str, object]) -> dict[str, object]: return {"policy": NSE_CORPORATE_ACTIONS_POLICY, "version": NSE_CORPORATE_ACTIONS_VERSION, "receipt_id": value["receipt_id"], "acquisition_id": value["acquisition_id"], "window": _window(value["window"]), "status": _enum(value["status"]), "observed_at": _time(value["observed_at"]), "record_count": value["record_count"], "artifact_id": value["artifact_id"], "error_code": value["error_code"]}
def _observation_payload(value: NseCorporateActionObservation) -> dict[str, object]: return _observation_payload_values({name: getattr(value, name) for name in NseCorporateActionObservation.__dataclass_fields__ if name != "fingerprint"})
def _observation_payload_values(value: Mapping[str, object]) -> dict[str, object]: return {"policy": NSE_CORPORATE_ACTIONS_POLICY, "version": NSE_CORPORATE_ACTIONS_VERSION, "observation_id": value["observation_id"], "acquisition_id": value["acquisition_id"], "artifact_id": value["artifact_id"], "record_index": value["record_index"], "raw_record_fingerprint": value["raw_record_fingerprint"], "symbol": value["symbol"], "isin": value["isin"], "series": value["series"], "raw_purpose": value["raw_purpose"], "family": _enum(value["family"]), "ex_date": _optional_time(value["ex_date"]), "record_date": _optional_time(value["record_date"]), "book_closure_start": _optional_time(value["book_closure_start"]), "book_closure_end": _optional_time(value["book_closure_end"]), "instrument": value["canonical_instrument_id"], "identity_status": _enum(value["identity_status"]), "canonical_action_id": value["canonical_action_id"], "adjustment_input_complete": value["adjustment_input_complete"], "warnings": list(value["warnings"]), "observed_at": _time(value["observed_at"])}
def _assessment_payload(value: NseCorporateActionCoverageAssessment) -> dict[str, object]: return _assessment_payload_values({name: getattr(value, name) for name in NseCorporateActionCoverageAssessment.__dataclass_fields__ if name != "fingerprint"})
def _assessment_payload_values(value: Mapping[str, object]) -> dict[str, object]: return {"policy": NSE_CORPORATE_ACTIONS_POLICY, "version": NSE_CORPORATE_ACTIONS_VERSION, "assessment_id": value["assessment_id"], "acquisition_id": value["acquisition_id"], "universe_snapshot_id": value["universe_snapshot_id"], "requested_window": _window(value["requested_window"]), "coverages": [{"instrument": item.canonical_instrument_id, "status": item.status.value, "observations": list(item.observation_ids), "continuity": item.continuity_status.value, "reasons": list(item.reasons)} for item in value["coverages"]], "observed_at": _time(value["observed_at"])}
def _manifest_payload(value: NseCorporateActionCoverageManifest) -> dict[str, object]: return _manifest_payload_values({name: getattr(value, name) for name in NseCorporateActionCoverageManifest.__dataclass_fields__ if name != "fingerprint"})
def _manifest_payload_values(value: Mapping[str, object]) -> dict[str, object]: return {"policy": NSE_CORPORATE_ACTIONS_POLICY, "version": NSE_CORPORATE_ACTIONS_VERSION, "manifest_id": value["manifest_id"], "acquisition_id": value["acquisition_id"], "universe_snapshot_id": value["universe_snapshot_id"], "requested_window": _window(value["requested_window"]), "source_family": value["source_family"], "source_version": value["source_version"], "acquisition_mode": value["acquisition_mode"], "requested_instrument_ids": list(value["requested_instrument_ids"]), "query_receipt_ids": list(value["query_receipt_ids"]), "source_artifact_ids": list(value["source_artifact_ids"]), "successful_query_count": value["successful_query_count"], "empty_successful_query_count": value["empty_successful_query_count"], "failed_query_count": value["failed_query_count"], "blocked_query_count": value["blocked_query_count"], "invalid_query_count": value["invalid_query_count"], "observation_count": value["observation_count"], "new_canonical_action_count": value["new_canonical_action_count"], "duplicate_canonical_action_count": value["duplicate_canonical_action_count"], "coverage_assessment_id": value["coverage_assessment_id"], "observed_at": _time(value["observed_at"])}


def _window(value: object) -> dict[str, str]:
    if not isinstance(value, NseCorporateActionQueryWindow): raise TypeError("NSE_CORPORATE_ACTION_WINDOW_REQUIRED")
    return {"start_date": value.start_date.isoformat(), "end_date": value.end_date.isoformat()}
def _optional_time(value: object) -> str | None: return None if value is None else _time(value)
def _time(value: object) -> str: return _aware(value, "timestamp").isoformat()
def _aware(value: object, field: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None: raise NseCorporateActionAcquisitionError(f"NSE_CORPORATE_ACTION_{field.upper()}_AWARE_REQUIRED")
    return value.astimezone(UTC)
def _valid_id(*values: str) -> bool: return all(bool(_IDENTIFIER.fullmatch(value)) for value in values)
def _digest(value: str) -> bool: return bool(re.fullmatch(r"[0-9a-f]{64}", value))
def _id(prefix: str, *values: str) -> str: return prefix + ":" + sha256("|".join(values).encode("utf-8")).hexdigest()[:32]
def _manifest_id(acquisition_id: str) -> str: return "nse-ca-manifest:" + acquisition_id
def _fingerprint(value: object) -> str: return sha256(_canonical(value).encode("utf-8")).hexdigest()
def _canonical(value: object) -> str: return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, default=_json_default)
def _json_default(value: object) -> object:
    if isinstance(value, (datetime, date)): return value.isoformat()
    if isinstance(value, Decimal): return str(value)
    if isinstance(value, StrEnum): return value.value
    raise TypeError(f"Unsupported canonical value: {type(value).__name__}")
def _enum(value: object) -> str: return value.value if isinstance(value, StrEnum) else str(value)
def _text(value: object) -> str: return str(value or "").strip()
def _optional_text(value: object) -> str | None: return _text(value) or None


__all__ = (
    "NSE_CORPORATE_ACTIONS_ENDPOINT", "NSE_CORPORATE_ACTIONS_POLICY", "NSE_CORPORATE_ACTIONS_SOURCE", "NSE_CORPORATE_ACTIONS_VERSION",
    "NseCorporateActionAcquisitionError", "NseCorporateActionBackfillResult", "NseCorporateActionContinuityStatus",
    "NseCorporateActionCoverageAssessment", "NseCorporateActionCoverageBackfill", "NseCorporateActionCoverageManifest",
    "NseCorporateActionCoverageStore", "NseCorporateActionFamily", "NseCorporateActionIdentityStatus", "NseCorporateActionObservation",
    "NseCorporateActionQueryReceipt", "NseCorporateActionQueryStatus", "NseCorporateActionQueryWindow",
    "NseCorporateActionSecurityCoverage", "NseCorporateActionSecurityCoverageStatus", "NseCorporateActionSourceResult",
    "NseCorporateActionSourceArtifact", "NseOfficialCorporateActionsSource", "monthly_windows",
)
