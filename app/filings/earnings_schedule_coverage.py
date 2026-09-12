"""Pure, non-active coverage and absence semantics for earnings schedules.

An exchange response can contain a qualifying future-results notice without
proving that every notice in an instrument/date window was searched.  This
module records that distinction deterministically.  It is deliberately not a
collector, repository, source adapter, Gate 6 input, or freshness scheduler.
"""
from __future__ import annotations

from dataclasses import dataclass, fields
from datetime import UTC, date, datetime
from enum import StrEnum
import re

from app.fundamentals.diagnostic_comparability import canonical_json, content_fingerprint


CONTRACT_ID = "official-earnings-schedule-coverage-window-policy"
CONTRACT_VERSION = "v1"
_IDENTIFIER = re.compile(r"[A-Za-z0-9._:-]+\Z")
_FINGERPRINT = re.compile(r"sha256:[0-9a-f]{64}\Z")


class EarningsScheduleCoverageError(ValueError):
    """Stable fail-closed error for malformed coverage lineage."""


class EarningsScheduleSourceFamily(StrEnum):
    NSE_EVENT_CALENDAR = "NSE_EVENT_CALENDAR"
    NSE_BOARD_MEETINGS = "NSE_BOARD_MEETINGS"
    NSE_ANNOUNCEMENTS = "NSE_ANNOUNCEMENTS"
    NSE_PRIOR_INTIMATION_XBRL = "NSE_PRIOR_INTIMATION_XBRL"
    BSE_BOARD_MEETINGS = "BSE_BOARD_MEETINGS"
    BSE_ANNOUNCEMENTS = "BSE_ANNOUNCEMENTS"


class CoverageQueryStatus(StrEnum):
    SUCCEEDED = "SUCCEEDED"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"
    IDENTITY_UNRESOLVED = "IDENTITY_UNRESOLVED"
    UNPROVEN = "UNPROVEN"
    CONFLICTED = "CONFLICTED"


class CoverageState(StrEnum):
    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"
    UNPROVEN = "UNPROVEN"
    CONFLICTED = "CONFLICTED"


class EarningsScheduleAbsenceState(StrEnum):
    QUALIFYING_EVENT_FOUND = "QUALIFYING_EVENT_FOUND"
    NO_QUALIFYING_EVENT_FOUND_COMPLETE_WINDOW = "NO_QUALIFYING_EVENT_FOUND_COMPLETE_WINDOW"
    NO_QUALIFYING_EVENT_FOUND_INCOMPLETE_WINDOW = "NO_QUALIFYING_EVENT_FOUND_INCOMPLETE_WINDOW"
    SOURCE_QUERY_FAILED = "SOURCE_QUERY_FAILED"
    IDENTITY_UNRESOLVED = "IDENTITY_UNRESOLVED"
    WINDOW_UNPROVEN = "WINDOW_UNPROVEN"
    EVIDENCE_CONFLICTED = "EVIDENCE_CONFLICTED"


class EarningsScheduleFreshnessState(StrEnum):
    FRESH = "FRESH"
    STALE = "STALE"
    UNPROVEN = "UNPROVEN"
    SOURCE_FAILED = "SOURCE_FAILED"


class CoverageQueryFilterSemantics(StrEnum):
    EXACT_INSTRUMENT_AND_DATE_WINDOW = "EXACT_INSTRUMENT_AND_DATE_WINDOW"
    SOURCE_SCOPE_UNPROVEN = "SOURCE_SCOPE_UNPROVEN"


class SystemCoverageObservationOrigin(StrEnum):
    AUTOMATIC_INGESTION_BOUNDARY = "AUTOMATIC_INGESTION_BOUNDARY"


def _aware(value: object) -> bool:
    return type(value) is datetime and value.tzinfo is not None and value.utcoffset() is not None


def _utc(value: datetime) -> datetime:
    if not _aware(value):
        raise EarningsScheduleCoverageError("EARNINGS_SCHEDULE_COVERAGE_AWARE_TIMESTAMP_REQUIRED")
    return value.astimezone(UTC)


def _identifier(value: object) -> bool:
    return type(value) is str and _IDENTIFIER.fullmatch(value) is not None


def _fingerprint(value: object) -> bool:
    return type(value) is str and _FINGERPRINT.fullmatch(value) is not None


def _payload(value: object, *, skip: frozenset[str] = frozenset()) -> dict[str, object]:
    return {
        field.name: getattr(value, field.name).isoformat() if type(getattr(value, field.name)) is date
        else getattr(value, field.name)
        for field in fields(value)
        if field.name not in skip
    }


def _ordered_unique_pairs(values: tuple["CoverageLineageReference", ...]) -> bool:
    pairs = tuple((item.reference_id, item.fingerprint) for item in values)
    return pairs == tuple(sorted(pairs)) and len(pairs) == len(set(pairs))


@dataclass(frozen=True, slots=True)
class CoverageLineageReference:
    """An exact source row/reference; it carries no inferred schedule meaning."""

    reference_id: str
    fingerprint: str

    def __post_init__(self) -> None:
        if not _identifier(self.reference_id) or not _fingerprint(self.fingerprint):
            raise EarningsScheduleCoverageError("EARNINGS_SCHEDULE_COVERAGE_LINEAGE_INVALID")


@dataclass(frozen=True, slots=True)
class SystemCoverageFirstObservedReceipt:
    """Prospective-only automatic observation of one exact source-query result.

    The pure type accepts supplied values for deterministic tests, but an
    operational collector may admit it only when an automatic ingestion
    boundary captures the instant and run sequence.  It never claims when the
    public market first knew a schedule.
    """

    receipt_id: str
    canonical_instrument_id: str
    source_family: EarningsScheduleSourceFamily
    query_identity: str
    response_fingerprints: tuple[str, ...]
    observed_at: datetime
    ingestion_run_id: str
    run_sequence: int
    origin: SystemCoverageObservationOrigin
    fingerprint: str
    contract_id: str = CONTRACT_ID
    contract_version: str = CONTRACT_VERSION
    actionability: str = "WATCH_ONLY"
    execution_status: str = "NON_EXECUTABLE"

    def __post_init__(self) -> None:
        object.__setattr__(self, "observed_at", _utc(self.observed_at))
        identity = {
            "contract_id": self.contract_id,
            "contract_version": self.contract_version,
            "canonical_instrument_id": self.canonical_instrument_id,
            "source_family": self.source_family,
            "query_identity": self.query_identity,
            "response_fingerprints": self.response_fingerprints,
            "observed_at": self.observed_at,
            "ingestion_run_id": self.ingestion_run_id,
            "run_sequence": self.run_sequence,
            "origin": self.origin,
        }
        expected_id = "earnings-schedule-coverage-first-observed:" + content_fingerprint(identity)[7:]
        if (
            self.receipt_id != expected_id
            or not _identifier(self.canonical_instrument_id)
            or not isinstance(self.source_family, EarningsScheduleSourceFamily)
            or not _identifier(self.query_identity)
            or not self.response_fingerprints
            or self.response_fingerprints != tuple(sorted(set(self.response_fingerprints)))
            or any(not _fingerprint(item) for item in self.response_fingerprints)
            or not _identifier(self.ingestion_run_id)
            or type(self.run_sequence) is not int
            or self.run_sequence < 0
            or self.origin is not SystemCoverageObservationOrigin.AUTOMATIC_INGESTION_BOUNDARY
            or self.contract_id != CONTRACT_ID
            or self.contract_version != CONTRACT_VERSION
            or self.actionability != "WATCH_ONLY"
            or self.execution_status != "NON_EXECUTABLE"
            or self.fingerprint != content_fingerprint(_payload(self, skip=frozenset({"fingerprint"})))
        ):
            raise EarningsScheduleCoverageError("EARNINGS_SCHEDULE_COVERAGE_FIRST_OBSERVED_INVALID")

    def to_json(self) -> str:
        self.__post_init__()
        return canonical_json(_payload(self))


def make_system_coverage_first_observed_receipt(
    *, canonical_instrument_id: str, source_family: EarningsScheduleSourceFamily,
    query_identity: str, response_fingerprints: tuple[str, ...], observed_at: datetime,
    ingestion_run_id: str, run_sequence: int,
) -> SystemCoverageFirstObservedReceipt:
    """Build a deterministic receipt for a future trusted collector boundary."""
    body: dict[str, object] = {
        "canonical_instrument_id": canonical_instrument_id,
        "source_family": source_family,
        "query_identity": query_identity,
        "response_fingerprints": response_fingerprints,
        "observed_at": _utc(observed_at),
        "ingestion_run_id": ingestion_run_id,
        "run_sequence": run_sequence,
        "origin": SystemCoverageObservationOrigin.AUTOMATIC_INGESTION_BOUNDARY,
        "contract_id": CONTRACT_ID,
        "contract_version": CONTRACT_VERSION,
        "actionability": "WATCH_ONLY",
        "execution_status": "NON_EXECUTABLE",
    }
    receipt_identity = {
        key: body[key]
        for key in (
            "contract_id", "contract_version", "canonical_instrument_id", "source_family", "query_identity",
            "response_fingerprints", "observed_at", "ingestion_run_id", "run_sequence", "origin",
        )
    }
    receipt_id = "earnings-schedule-coverage-first-observed:" + content_fingerprint(receipt_identity)[7:]
    values = body | {"receipt_id": receipt_id}
    return SystemCoverageFirstObservedReceipt(**(values | {"fingerprint": content_fingerprint(values)}))


def _coverage_state(
    *, status: CoverageQueryStatus, exact_scope: bool, pagination_complete: bool,
    identity_scope_complete: bool, revision_scope_complete: bool, ambiguous: bool,
) -> CoverageState:
    if status is CoverageQueryStatus.FAILED:
        return CoverageState.FAILED
    if status is CoverageQueryStatus.CONFLICTED or ambiguous:
        return CoverageState.CONFLICTED
    if status in {CoverageQueryStatus.IDENTITY_UNRESOLVED, CoverageQueryStatus.UNPROVEN}:
        return CoverageState.UNPROVEN
    if (
        status is CoverageQueryStatus.SUCCEEDED
        and exact_scope
        and pagination_complete
        and identity_scope_complete
        and revision_scope_complete
    ):
        return CoverageState.COMPLETE
    return CoverageState.PARTIAL


def _absence_state(
    *, coverage_state: CoverageState, query_status: CoverageQueryStatus,
    qualifying: tuple[CoverageLineageReference, ...],
) -> EarningsScheduleAbsenceState:
    if qualifying:
        return EarningsScheduleAbsenceState.QUALIFYING_EVENT_FOUND
    if coverage_state is CoverageState.COMPLETE:
        return EarningsScheduleAbsenceState.NO_QUALIFYING_EVENT_FOUND_COMPLETE_WINDOW
    if coverage_state is CoverageState.FAILED:
        return EarningsScheduleAbsenceState.SOURCE_QUERY_FAILED
    if coverage_state is CoverageState.CONFLICTED:
        return EarningsScheduleAbsenceState.EVIDENCE_CONFLICTED
    if coverage_state is CoverageState.UNPROVEN:
        return (
            EarningsScheduleAbsenceState.IDENTITY_UNRESOLVED
            if query_status is CoverageQueryStatus.IDENTITY_UNRESOLVED
            else EarningsScheduleAbsenceState.WINDOW_UNPROVEN
        )
    return EarningsScheduleAbsenceState.NO_QUALIFYING_EVENT_FOUND_INCOMPLETE_WINDOW


@dataclass(frozen=True, slots=True)
class EarningsScheduleCoverageReceipt:
    """One deterministic, non-authorising source-window query result.

    ``NO_QUALIFYING_EVENT_FOUND_COMPLETE_WINDOW`` is only a future candidate
    negative-evidence state.  This V1 receipt hard-codes no clearance, Gate 6
    behaviour, or freshness duration.
    """

    receipt_id: str
    canonical_instrument_id: str
    source_family: EarningsScheduleSourceFamily
    window_start: date
    window_end: date
    filter_semantics: CoverageQueryFilterSemantics
    query_status: CoverageQueryStatus
    query_completed_at: datetime
    response_fingerprints: tuple[str, ...]
    qualifying_rows: tuple[CoverageLineageReference, ...]
    non_qualifying_rows: tuple[CoverageLineageReference, ...]
    ambiguous_rows: tuple[CoverageLineageReference, ...]
    pagination_complete: bool
    identity_scope_complete: bool
    revision_scope_complete: bool
    source_error_code: str | None
    system_first_observed: SystemCoverageFirstObservedReceipt | None
    coverage_state: CoverageState
    absence_state: EarningsScheduleAbsenceState
    freshness_state: EarningsScheduleFreshnessState
    fingerprint: str
    contract_id: str = CONTRACT_ID
    contract_version: str = CONTRACT_VERSION
    actionability: str = "WATCH_ONLY"
    execution_status: str = "NON_EXECUTABLE"
    gate6_clearance: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "query_completed_at", _utc(self.query_completed_at))
        if self.system_first_observed is not None:
            self.system_first_observed.__post_init__()
        identity = {
            "contract_id": self.contract_id,
            "contract_version": self.contract_version,
            "canonical_instrument_id": self.canonical_instrument_id,
            "source_family": self.source_family,
            "window_start": self.window_start.isoformat() if type(self.window_start) is date else self.window_start,
            "window_end": self.window_end.isoformat() if type(self.window_end) is date else self.window_end,
            "filter_semantics": self.filter_semantics,
            "query_completed_at": self.query_completed_at,
            "response_fingerprints": self.response_fingerprints,
        }
        expected_id = "earnings-schedule-coverage:" + content_fingerprint(identity)[7:]
        all_rows = self.qualifying_rows + self.non_qualifying_rows + self.ambiguous_rows
        row_pairs = tuple((item.reference_id, item.fingerprint) for item in all_rows)
        expected_coverage = _coverage_state(
            status=self.query_status,
            exact_scope=self.filter_semantics is CoverageQueryFilterSemantics.EXACT_INSTRUMENT_AND_DATE_WINDOW,
            pagination_complete=self.pagination_complete,
            identity_scope_complete=self.identity_scope_complete,
            revision_scope_complete=self.revision_scope_complete,
            ambiguous=bool(self.ambiguous_rows),
        )
        expected_absence = _absence_state(
            coverage_state=expected_coverage,
            query_status=self.query_status,
            qualifying=self.qualifying_rows,
        )
        expected_freshness = (
            EarningsScheduleFreshnessState.SOURCE_FAILED
            if expected_coverage is CoverageState.FAILED
            else EarningsScheduleFreshnessState.UNPROVEN
        )
        observed_matches = self.system_first_observed is None or (
            self.system_first_observed.canonical_instrument_id == self.canonical_instrument_id
            and self.system_first_observed.source_family is self.source_family
            and self.system_first_observed.query_identity == self.receipt_id
            and self.system_first_observed.response_fingerprints == self.response_fingerprints
            and self.system_first_observed.observed_at >= self.query_completed_at
        )
        if (
            self.receipt_id != expected_id
            or not _identifier(self.canonical_instrument_id)
            or not isinstance(self.source_family, EarningsScheduleSourceFamily)
            or type(self.window_start) is not date
            or type(self.window_end) is not date
            or self.window_end < self.window_start
            or not isinstance(self.filter_semantics, CoverageQueryFilterSemantics)
            or not isinstance(self.query_status, CoverageQueryStatus)
            or (not self.response_fingerprints and self.query_status is not CoverageQueryStatus.FAILED)
            or self.response_fingerprints != tuple(sorted(set(self.response_fingerprints)))
            or any(not _fingerprint(item) for item in self.response_fingerprints)
            or any(not _ordered_unique_pairs(values) for values in (
                self.qualifying_rows, self.non_qualifying_rows, self.ambiguous_rows,
            ))
            or len(row_pairs) != len(set(row_pairs))
            or len({item.reference_id for item in all_rows}) != len(all_rows)
            or len({item.fingerprint for item in all_rows}) != len(all_rows)
            or self.source_error_code is not None and not _identifier(self.source_error_code)
            or (self.query_status is CoverageQueryStatus.FAILED) != (self.source_error_code is not None)
            or (self.query_status is CoverageQueryStatus.FAILED and all_rows)
            or (not self.response_fingerprints and self.system_first_observed is not None)
            or (self.query_status is CoverageQueryStatus.CONFLICTED and not self.ambiguous_rows)
            or self.coverage_state is not expected_coverage
            or self.absence_state is not expected_absence
            or self.freshness_state is not expected_freshness
            or not observed_matches
            or self.contract_id != CONTRACT_ID
            or self.contract_version != CONTRACT_VERSION
            or self.actionability != "WATCH_ONLY"
            or self.execution_status != "NON_EXECUTABLE"
            or self.gate6_clearance is not False
            or self.fingerprint != content_fingerprint(_payload(self, skip=frozenset({"fingerprint"})))
        ):
            raise EarningsScheduleCoverageError("EARNINGS_SCHEDULE_COVERAGE_RECEIPT_INVALID")

    @property
    def negative_evidence_candidate(self) -> bool:
        """True only for complete coverage; never a clearance in this V1 contract."""
        self.__post_init__()
        return self.absence_state is EarningsScheduleAbsenceState.NO_QUALIFYING_EVENT_FOUND_COMPLETE_WINDOW

    def to_json(self) -> str:
        self.__post_init__()
        return canonical_json(_payload(self))


def make_earnings_schedule_coverage_receipt(
    *, canonical_instrument_id: str, source_family: EarningsScheduleSourceFamily,
    window_start: date, window_end: date, filter_semantics: CoverageQueryFilterSemantics,
    query_status: CoverageQueryStatus, query_completed_at: datetime,
    response_fingerprints: tuple[str, ...], qualifying_rows: tuple[CoverageLineageReference, ...] = (),
    non_qualifying_rows: tuple[CoverageLineageReference, ...] = (),
    ambiguous_rows: tuple[CoverageLineageReference, ...] = (), pagination_complete: bool = False,
    identity_scope_complete: bool = False, revision_scope_complete: bool = False,
    source_error_code: str | None = None,
    system_first_observed: SystemCoverageFirstObservedReceipt | None = None,
) -> EarningsScheduleCoverageReceipt:
    """Build a deterministic V1 receipt without choosing a freshness duration."""
    point = _utc(query_completed_at)
    identity = {
        "contract_id": CONTRACT_ID,
        "contract_version": CONTRACT_VERSION,
        "canonical_instrument_id": canonical_instrument_id,
        "source_family": source_family,
        "window_start": window_start.isoformat() if type(window_start) is date else window_start,
        "window_end": window_end.isoformat() if type(window_end) is date else window_end,
        "filter_semantics": filter_semantics,
        "query_completed_at": point,
        "response_fingerprints": response_fingerprints,
    }
    receipt_id = "earnings-schedule-coverage:" + content_fingerprint(identity)[7:]
    coverage = _coverage_state(
        status=query_status,
        exact_scope=filter_semantics is CoverageQueryFilterSemantics.EXACT_INSTRUMENT_AND_DATE_WINDOW,
        pagination_complete=pagination_complete,
        identity_scope_complete=identity_scope_complete,
        revision_scope_complete=revision_scope_complete,
        ambiguous=bool(ambiguous_rows),
    )
    absence = _absence_state(
        coverage_state=coverage,
        query_status=query_status,
        qualifying=qualifying_rows,
    )
    freshness = EarningsScheduleFreshnessState.SOURCE_FAILED if coverage is CoverageState.FAILED else EarningsScheduleFreshnessState.UNPROVEN
    body: dict[str, object] = {
        "receipt_id": receipt_id,
        "canonical_instrument_id": canonical_instrument_id,
        "source_family": source_family,
        "window_start": window_start,
        "window_end": window_end,
        "filter_semantics": filter_semantics,
        "query_status": query_status,
        "query_completed_at": point,
        "response_fingerprints": response_fingerprints,
        "qualifying_rows": qualifying_rows,
        "non_qualifying_rows": non_qualifying_rows,
        "ambiguous_rows": ambiguous_rows,
        "pagination_complete": pagination_complete,
        "identity_scope_complete": identity_scope_complete,
        "revision_scope_complete": revision_scope_complete,
        "source_error_code": source_error_code,
        "system_first_observed": system_first_observed,
        "coverage_state": coverage,
        "absence_state": absence,
        "freshness_state": freshness,
        "contract_id": CONTRACT_ID,
        "contract_version": CONTRACT_VERSION,
        "actionability": "WATCH_ONLY",
        "execution_status": "NON_EXECUTABLE",
        "gate6_clearance": False,
    }
    fingerprint_body = body | {
        "window_start": window_start.isoformat() if type(window_start) is date else window_start,
        "window_end": window_end.isoformat() if type(window_end) is date else window_end,
    }
    return EarningsScheduleCoverageReceipt(**(body | {"fingerprint": content_fingerprint(fingerprint_body)}))


__all__ = (
    "CONTRACT_ID", "CONTRACT_VERSION", "CoverageLineageReference", "CoverageQueryFilterSemantics",
    "CoverageQueryStatus", "CoverageState", "EarningsScheduleAbsenceState", "EarningsScheduleCoverageError",
    "EarningsScheduleCoverageReceipt", "EarningsScheduleFreshnessState", "EarningsScheduleSourceFamily",
    "SystemCoverageFirstObservedReceipt", "SystemCoverageObservationOrigin",
    "make_earnings_schedule_coverage_receipt", "make_system_coverage_first_observed_receipt",
)
