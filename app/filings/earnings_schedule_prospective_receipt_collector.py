"""Prospective-only official earnings-schedule source receipts.

This is a bounded ingestion boundary, not an earnings-risk evaluator.  It
captures what HSI actually observed from the existing official adapters,
retains raw bytes immutably in the established snapshot store, and emits only
partial/failed coverage evidence.  It never reconstructs historical PIT,
selects a blackout horizon, or calls Gate 6.
"""
from __future__ import annotations

from base64 import b64decode, b64encode
from dataclasses import dataclass, fields
from datetime import UTC, date, datetime
from enum import StrEnum
from hashlib import sha256
import re
from typing import Protocol

from app.filings.earnings_schedule_coverage import (
    CoverageLineageReference,
    CoverageQueryFilterSemantics,
    CoverageQueryStatus,
    EarningsScheduleCoverageReceipt,
    EarningsScheduleSourceFamily,
    make_earnings_schedule_coverage_receipt,
    make_system_coverage_first_observed_receipt,
)
from app.filings.earnings_schedule_discovery import discover_bse
from app.filings.earnings_schedule_identity import (
    EarningsScheduleCanonicalIdentityBridge,
    IdentityState,
)
from app.filings.earnings_schedule_known_at import (
    SourceTimestampSemanticAuthority,
    SystemFirstObservedReceipt,
    make_system_first_observed_receipt,
)
from app.filings.earnings_schedule_source import (
    BSEOfficialEarningsScheduleSource,
    Fetch,
    NSEOfficialEarningsScheduleSource,
    RawSchedule,
    SourceBatch,
    SourceState,
    Transport,
    classify,
    parse_meeting_date,
    public_url,
)
from app.fundamentals.diagnostic_comparability import content_fingerprint
from app.gates.official_earnings_schedule_candidate import (
    PurposeClassification,
    ScheduleLifecycleState,
    SchedulePrecision,
)
from app.storage.core_api_snapshot_repository import (
    CoreApiSnapshot,
    CoreApiSnapshotFamily,
    CoreApiSnapshotRepository,
)


CONTRACT_ID = "earnings-schedule-prospective-receipt-collector"
CONTRACT_VERSION = "v1"
COLLECTOR_VERSION = "prospective-earnings-schedule-receipt-collector/v1"
_ID = re.compile(r"[A-Za-z0-9._:-]+\Z")
_FP = re.compile(r"sha256:[0-9a-f]{64}\Z")
_INSTRUMENT = re.compile(r"NSE:IN[A-Z0-9]{9}[0-9]\Z")
_VERSION = re.compile(r"[A-Za-z0-9._:/-]+\Z")


class ProspectiveReceiptCollectorError(ValueError):
    """Stable fail-closed collector boundary error."""


class ProspectiveReceiptWriteOutcome(StrEnum):
    INSERTED = "INSERTED"
    ALREADY_PRESENT = "ALREADY_PRESENT"


class ProspectiveObservationState(StrEnum):
    OBSERVED = "OBSERVED"
    OUTSIDE_TARGET_COHORT = "OUTSIDE_TARGET_COHORT"
    IDENTITY_UNRESOLVED = "IDENTITY_UNRESOLVED"
    PURPOSE_AMBIGUOUS = "PURPOSE_AMBIGUOUS"
    NON_QUALIFYING = "NON_QUALIFYING"
    DATE_UNAVAILABLE = "DATE_UNAVAILABLE"
    EVIDENCE_CONFLICTED = "EVIDENCE_CONFLICTED"
    REVISION_LINEAGE_UNRESOLVED = "REVISION_LINEAGE_UNRESOLVED"


class ProspectivePollState(StrEnum):
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"


class CollectorClock(Protocol):
    def now(self) -> datetime: ...


class SystemUtcClock:
    """The sole production-time source; tests inject a deterministic clock."""

    def now(self) -> datetime:
        return datetime.now(UTC)


def _aware(value: object) -> bool:
    return type(value) is datetime and value.tzinfo is not None and value.utcoffset() is not None


def _utc(value: datetime) -> datetime:
    if not _aware(value):
        raise ProspectiveReceiptCollectorError("EARNINGS_PROSPECTIVE_AWARE_UTC_REQUIRED")
    return value.astimezone(UTC)


def _id(value: object) -> bool:
    return type(value) is str and _ID.fullmatch(value) is not None


def _fp(value: object) -> bool:
    return type(value) is str and _FP.fullmatch(value) is not None


def _version(value: object) -> bool:
    return type(value) is str and _VERSION.fullmatch(value) is not None


def _payload(value: object, *, skip: frozenset[str] = frozenset()) -> dict[str, object]:
    body: dict[str, object] = {}
    for item in fields(value):
        if item.name in skip:
            continue
        entry = getattr(value, item.name)
        body[item.name] = entry.isoformat() if type(entry) is date else entry
    return body


def _family(exchange) -> EarningsScheduleSourceFamily:
    if exchange.value == "NSE":
        return EarningsScheduleSourceFamily.NSE_BOARD_MEETINGS
    if exchange.value == "BSE":
        return EarningsScheduleSourceFamily.BSE_ANNOUNCEMENTS
    raise ProspectiveReceiptCollectorError("EARNINGS_PROSPECTIVE_SOURCE_FAMILY_UNSUPPORTED")


def _source_record_identity(row: RawSchedule) -> str:
    explicit = row.field("filing_identity")
    if explicit is not None:
        return explicit
    # Public URLs are retained on ``RawSchedule`` as raw provenance, but the
    # established known-at receipt accepts canonical opaque identifiers only.
    # This deterministic source-record token never replaces the URL evidence.
    return "source-record:" + content_fingerprint({"reference": row.field("link") or row.reference})[7:]


def _raw_artifact_endpoint(row: RawSchedule) -> str:
    """A BSE list row points *to* a detail URL but came from the list page."""
    return row.field("inventory_reference") if row.parser_version == "bse-public-corporates/v1" else row.reference


def _sorted_unique(values: tuple[str, ...]) -> bool:
    return bool(values) and values == tuple(sorted(set(values))) and all(_id(item) for item in values)


def _sorted_unique_or_empty(values: tuple[str, ...]) -> bool:
    return values == tuple(sorted(set(values))) and all(_id(item) for item in values)


def _snapshot_id(prefix: str, body: object) -> str:
    return prefix + ":" + content_fingerprint(body)[7:]


def _explicit_lifecycle(row: RawSchedule) -> ScheduleLifecycleState | None:
    """Return only an exact source-declared lifecycle, never a text inference.

    The existing source normalizer deliberately refuses a revised source row
    without an exact parent. This prospective collector can link one only when
    it already holds an immutable observation with the exact same source filing
    identity. Unknown labels stay unresolved rather than being normalized into
    a lifecycle state.
    """
    value = row.field("intimation_type")
    states = {
        "New": ScheduleLifecycleState.ANNOUNCED,
        "Original": ScheduleLifecycleState.ANNOUNCED,
        "Revised": ScheduleLifecycleState.REVISED,
        "Revision": ScheduleLifecycleState.REVISED,
        "Rescheduled": ScheduleLifecycleState.RESCHEDULED,
        "Cancelled": ScheduleLifecycleState.CANCELLED,
        "Canceled": ScheduleLifecycleState.CANCELLED,
    }
    return states.get(value) if value is not None else ScheduleLifecycleState.ANNOUNCED


@dataclass(frozen=True, slots=True)
class ProspectiveRawArtifactReceipt:
    """Lossless bytes captured before parser admission or normalization."""

    artifact_id: str
    source_family: EarningsScheduleSourceFamily
    source_endpoint: str
    payload_fingerprint: str
    raw_payload_base64: str
    first_observed_at: datetime
    request_identity: str
    adapter_version: str
    collector_version: str
    http_status: int
    bytes_received: int
    fingerprint: str
    contract_id: str = CONTRACT_ID
    contract_version: str = CONTRACT_VERSION
    actionability: str = "WATCH_ONLY"
    execution_status: str = "NON_EXECUTABLE"

    def __post_init__(self) -> None:
        object.__setattr__(self, "first_observed_at", _utc(self.first_observed_at))
        try:
            raw = b64decode(self.raw_payload_base64.encode("ascii"), validate=True)
        except (ValueError, UnicodeEncodeError):
            raw = b""
        expected_id = _snapshot_id("prospective-earnings-artifact", {
            "source_family": self.source_family,
            "source_endpoint": self.source_endpoint,
            "payload_fingerprint": self.payload_fingerprint,
        })
        if (
            self.artifact_id != expected_id
            or not isinstance(self.source_family, EarningsScheduleSourceFamily)
            or public_url(self.source_endpoint) != self.source_endpoint
            or not _fp(self.payload_fingerprint)
            or "sha256:" + sha256(raw).hexdigest() != self.payload_fingerprint
            or not _id(self.request_identity)
            or not _version(self.adapter_version)
            or self.collector_version != COLLECTOR_VERSION
            or type(self.http_status) is not int or not 100 <= self.http_status <= 599
            or type(self.bytes_received) is not int or self.bytes_received != len(raw)
            or self.contract_id != CONTRACT_ID or self.contract_version != CONTRACT_VERSION
            or self.actionability != "WATCH_ONLY" or self.execution_status != "NON_EXECUTABLE"
            or self.fingerprint != content_fingerprint(_payload(self, skip=frozenset({"fingerprint"})))
        ):
            raise ProspectiveReceiptCollectorError("EARNINGS_PROSPECTIVE_RAW_ARTIFACT_INVALID")

    @property
    def raw_payload(self) -> bytes:
        self.__post_init__()
        return b64decode(self.raw_payload_base64.encode("ascii"), validate=True)


def make_raw_artifact_receipt(*, source_family: EarningsScheduleSourceFamily, source_endpoint: str,
                              raw_payload: bytes, observed_at: datetime, request_identity: str,
                              adapter_version: str, http_status: int) -> ProspectiveRawArtifactReceipt:
    if type(raw_payload) is not bytes:
        raise ProspectiveReceiptCollectorError("EARNINGS_PROSPECTIVE_RAW_BYTES_REQUIRED")
    payload_fp = "sha256:" + sha256(raw_payload).hexdigest()
    endpoint = public_url(source_endpoint)
    artifact_id = _snapshot_id("prospective-earnings-artifact", {
        "source_family": source_family, "source_endpoint": endpoint, "payload_fingerprint": payload_fp,
    })
    body: dict[str, object] = {
        "artifact_id": artifact_id, "source_family": source_family, "source_endpoint": endpoint,
        "payload_fingerprint": payload_fp,
        "raw_payload_base64": b64encode(raw_payload).decode("ascii"),
        "first_observed_at": _utc(observed_at), "request_identity": request_identity,
        "adapter_version": adapter_version, "collector_version": COLLECTOR_VERSION,
        "http_status": http_status, "bytes_received": len(raw_payload),
        "contract_id": CONTRACT_ID, "contract_version": CONTRACT_VERSION,
        "actionability": "WATCH_ONLY", "execution_status": "NON_EXECUTABLE",
    }
    return ProspectiveRawArtifactReceipt(**(body | {"fingerprint": content_fingerprint(body)}))


@dataclass(frozen=True, slots=True)
class ProspectiveSourceObservation:
    """One parsed source row bound to its immutable raw response artifact."""

    observation_id: str
    raw_artifact_id: str
    source_family: EarningsScheduleSourceFamily
    source_record_identity: str
    source_record_fingerprint: str
    source: RawSchedule
    discovery_observation_id: str | None
    first_observed_at: datetime
    source_public_time_raw: str | None
    source_received_time_raw: str | None
    source_timestamp_authority: SourceTimestampSemanticAuthority
    fingerprint: str
    contract_id: str = CONTRACT_ID
    contract_version: str = CONTRACT_VERSION
    actionability: str = "WATCH_ONLY"
    execution_status: str = "NON_EXECUTABLE"

    def __post_init__(self) -> None:
        object.__setattr__(self, "first_observed_at", _utc(self.first_observed_at))
        self.source.__post_init__()
        expected_id = _snapshot_id("prospective-earnings-observation", {
            "source_family": self.source_family, "source_record_identity": self.source_record_identity,
            "source_record_fingerprint": self.source_record_fingerprint,
            "discovery_observation_id": self.discovery_observation_id,
        })
        if (
            self.observation_id != expected_id or not _id(self.raw_artifact_id)
            or not isinstance(self.source_family, EarningsScheduleSourceFamily)
            or not _id(self.source_record_identity) or not _fp(self.source_record_fingerprint)
            or self.source_record_fingerprint != self.source.fingerprint
            or _family(self.source.exchange) is not self.source_family
            or _source_record_identity(self.source) != self.source_record_identity
            or (self.discovery_observation_id is not None and not _id(self.discovery_observation_id))
            or not isinstance(self.source_timestamp_authority, SourceTimestampSemanticAuthority)
            or self.source_timestamp_authority is not SourceTimestampSemanticAuthority.UNPROVEN
            or any(item is not None and (type(item) is not str or not item.strip()) for item in (
                self.source_public_time_raw, self.source_received_time_raw,
            ))
            or self.contract_id != CONTRACT_ID or self.contract_version != CONTRACT_VERSION
            or self.actionability != "WATCH_ONLY" or self.execution_status != "NON_EXECUTABLE"
            or self.fingerprint != content_fingerprint(_payload(self, skip=frozenset({"fingerprint"})))
        ):
            raise ProspectiveReceiptCollectorError("EARNINGS_PROSPECTIVE_SOURCE_OBSERVATION_INVALID")


def make_source_observation(*, artifact: ProspectiveRawArtifactReceipt, source: RawSchedule,
                            observed_at: datetime,
                            discovery_observation_id: str | None = None) -> ProspectiveSourceObservation:
    artifact.__post_init__()
    source.__post_init__()
    family, record = _family(source.exchange), _source_record_identity(source)
    body: dict[str, object] = {
        "raw_artifact_id": artifact.artifact_id, "source_family": family,
        "source_record_identity": record, "source_record_fingerprint": source.fingerprint,
        "source": source, "discovery_observation_id": discovery_observation_id,
        "first_observed_at": _utc(observed_at),
        "source_public_time_raw": source.field("disseminated"),
        "source_received_time_raw": source.field("received"),
        "source_timestamp_authority": SourceTimestampSemanticAuthority.UNPROVEN,
        "contract_id": CONTRACT_ID, "contract_version": CONTRACT_VERSION,
        "actionability": "WATCH_ONLY", "execution_status": "NON_EXECUTABLE",
    }
    body["observation_id"] = _snapshot_id("prospective-earnings-observation", {
        "source_family": family, "source_record_identity": record,
        "source_record_fingerprint": source.fingerprint, "discovery_observation_id": discovery_observation_id,
    })
    return ProspectiveSourceObservation(**(body | {"fingerprint": content_fingerprint(body)}))


@dataclass(frozen=True, slots=True)
class ProspectiveQualifiedScheduleReceipt:
    """Positive, source-observed schedule evidence with no public-time claim."""

    receipt_id: str
    source_observation_id: str
    canonical_instrument_id: str
    source_family: EarningsScheduleSourceFamily
    source_filing_identity: str
    source_payload_fingerprint: str
    purpose_classification: PurposeClassification
    purpose_rule: str
    event_date: date
    event_precision: SchedulePrecision
    source_public_time_raw: str | None
    source_received_time_raw: str | None
    source_timestamp_authority: SourceTimestampSemanticAuthority
    system_first_observed: SystemFirstObservedReceipt
    processed_at: datetime
    lifecycle_state: ScheduleLifecycleState
    revision_of_receipt_id: str | None
    identity_fingerprint: str
    candidate_policy_version: str
    fingerprint: str
    contract_id: str = CONTRACT_ID
    contract_version: str = CONTRACT_VERSION
    source_authority_state: str = "UNVERIFIED_SOURCE_AUTHORITY"
    actionability: str = "WATCH_ONLY"
    execution_status: str = "NON_EXECUTABLE"
    gate6_clearance: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "processed_at", _utc(self.processed_at))
        self.system_first_observed.__post_init__()
        expected_id = _snapshot_id("prospective-earnings-schedule", {
            "source_family": self.source_family, "source_filing_identity": self.source_filing_identity,
            "source_payload_fingerprint": self.source_payload_fingerprint,
        })
        requires_parent = {
            ScheduleLifecycleState.REVISED, ScheduleLifecycleState.RESCHEDULED,
            ScheduleLifecycleState.CANCELLED, ScheduleLifecycleState.SUPERSEDED,
        }
        if (
            self.receipt_id != expected_id or not _id(self.source_observation_id)
            or _INSTRUMENT.fullmatch(self.canonical_instrument_id) is None
            or not isinstance(self.source_family, EarningsScheduleSourceFamily)
            or not _id(self.source_filing_identity) or not _fp(self.source_payload_fingerprint)
            or self.purpose_classification in {PurposeClassification.AMBIGUOUS, PurposeClassification.NON_QUALIFYING}
            or not _id(self.purpose_rule) or type(self.event_date) is not date
            or self.event_precision is not SchedulePrecision.DATE_ONLY
            or self.source_timestamp_authority is not SourceTimestampSemanticAuthority.UNPROVEN
            or any(item is not None and (type(item) is not str or not item.strip()) for item in (
                self.source_public_time_raw, self.source_received_time_raw,
            ))
            or self.system_first_observed.canonical_instrument_id != self.canonical_instrument_id
            or self.system_first_observed.source_filing_identity != self.source_filing_identity
            or self.system_first_observed.source_payload_fingerprint != self.source_payload_fingerprint
            or self.system_first_observed.observed_at > self.processed_at
            or not isinstance(self.lifecycle_state, ScheduleLifecycleState)
            or ((self.lifecycle_state in requires_parent) != (self.revision_of_receipt_id is not None))
            or (self.revision_of_receipt_id is not None and (
                not _id(self.revision_of_receipt_id) or self.revision_of_receipt_id == self.receipt_id
            ))
            or not _fp(self.identity_fingerprint) or not _version(self.candidate_policy_version)
            or self.source_authority_state != "UNVERIFIED_SOURCE_AUTHORITY"
            or self.contract_id != CONTRACT_ID or self.contract_version != CONTRACT_VERSION
            or self.actionability != "WATCH_ONLY" or self.execution_status != "NON_EXECUTABLE"
            or self.gate6_clearance is not False
            or self.fingerprint != content_fingerprint(_payload(self, skip=frozenset({"fingerprint"})))
        ):
            raise ProspectiveReceiptCollectorError("EARNINGS_PROSPECTIVE_QUALIFIED_RECEIPT_INVALID")


def make_qualified_schedule_receipt(*, observation: ProspectiveSourceObservation,
                                    canonical_instrument_id: str, identity_fingerprint: str,
                                    purpose_classification: PurposeClassification, purpose_rule: str,
                                    event_date: date, first_observed: SystemFirstObservedReceipt,
                                    processed_at: datetime, lifecycle_state: ScheduleLifecycleState,
                                    revision_of_receipt_id: str | None) -> ProspectiveQualifiedScheduleReceipt:
    observation.__post_init__()
    filing_id, payload_fp = observation.source_record_identity, observation.source_record_fingerprint
    body: dict[str, object] = {
        "source_observation_id": observation.observation_id, "canonical_instrument_id": canonical_instrument_id,
        "source_family": observation.source_family, "source_filing_identity": filing_id,
        "source_payload_fingerprint": payload_fp, "purpose_classification": purpose_classification,
        "purpose_rule": purpose_rule, "event_date": event_date,
        "event_precision": SchedulePrecision.DATE_ONLY,
        "source_public_time_raw": observation.source_public_time_raw,
        "source_received_time_raw": observation.source_received_time_raw,
        "source_timestamp_authority": SourceTimestampSemanticAuthority.UNPROVEN,
        "system_first_observed": first_observed, "processed_at": _utc(processed_at),
        "lifecycle_state": lifecycle_state, "revision_of_receipt_id": revision_of_receipt_id,
        "identity_fingerprint": identity_fingerprint,
        "candidate_policy_version": "official-results-purpose/v1",
        "contract_id": CONTRACT_ID, "contract_version": CONTRACT_VERSION,
        "source_authority_state": "UNVERIFIED_SOURCE_AUTHORITY",
        "actionability": "WATCH_ONLY", "execution_status": "NON_EXECUTABLE", "gate6_clearance": False,
    }
    body["receipt_id"] = _snapshot_id("prospective-earnings-schedule", {
        "source_family": observation.source_family, "source_filing_identity": filing_id,
        "source_payload_fingerprint": payload_fp,
    })
    fingerprint_body = body | {"event_date": event_date.isoformat()}
    return ProspectiveQualifiedScheduleReceipt(**(body | {"fingerprint": content_fingerprint(fingerprint_body)}))


@dataclass(frozen=True, slots=True)
class ProspectiveScheduleAssessmentReceipt:
    """One deterministic admission outcome for an immutable source row.

    This records insufficient or conflicted source evidence explicitly.  It is
    not a candidate selector, a risk classification, or a negative calendar
    conclusion.
    """

    assessment_id: str
    source_observation_id: str
    state: ProspectiveObservationState
    reason_codes: tuple[str, ...]
    purpose_classification: PurposeClassification
    identity_fingerprint: str | None
    qualified_receipt_id: str | None
    first_observed_at: datetime
    processed_at: datetime
    fingerprint: str
    contract_id: str = CONTRACT_ID
    contract_version: str = CONTRACT_VERSION
    actionability: str = "WATCH_ONLY"
    execution_status: str = "NON_EXECUTABLE"
    gate6_clearance: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "first_observed_at", _utc(self.first_observed_at))
        object.__setattr__(self, "processed_at", _utc(self.processed_at))
        expected_id = _snapshot_id("prospective-earnings-assessment", {
            "source_observation_id": self.source_observation_id, "state": self.state,
            "reason_codes": self.reason_codes, "purpose_classification": self.purpose_classification,
            "identity_fingerprint": self.identity_fingerprint,
            "qualified_receipt_id": self.qualified_receipt_id,
        })
        positive = self.state is ProspectiveObservationState.OBSERVED
        if (
            self.assessment_id != expected_id or not _id(self.source_observation_id)
            or not isinstance(self.state, ProspectiveObservationState)
            or self.reason_codes != tuple(sorted(set(self.reason_codes)))
            or any(not _id(item) for item in self.reason_codes)
            or not isinstance(self.purpose_classification, PurposeClassification)
            or (self.identity_fingerprint is not None and not _fp(self.identity_fingerprint))
            or (self.qualified_receipt_id is not None and not _id(self.qualified_receipt_id))
            or positive != (self.qualified_receipt_id is not None and not self.reason_codes)
            or (not positive and (self.qualified_receipt_id is not None or not self.reason_codes))
            or self.processed_at < self.first_observed_at
            or self.contract_id != CONTRACT_ID or self.contract_version != CONTRACT_VERSION
            or self.actionability != "WATCH_ONLY" or self.execution_status != "NON_EXECUTABLE"
            or self.gate6_clearance is not False
            or self.fingerprint != content_fingerprint(_payload(self, skip=frozenset({"fingerprint"})))
        ):
            raise ProspectiveReceiptCollectorError("EARNINGS_PROSPECTIVE_ASSESSMENT_RECEIPT_INVALID")


def make_schedule_assessment_receipt(*, observation: ProspectiveSourceObservation,
                                     state: ProspectiveObservationState, reason_codes: tuple[str, ...],
                                     purpose_classification: PurposeClassification,
                                     identity_fingerprint: str | None,
                                     qualified_receipt_id: str | None, processed_at: datetime) -> ProspectiveScheduleAssessmentReceipt:
    observation.__post_init__()
    body: dict[str, object] = {
        "source_observation_id": observation.observation_id, "state": state,
        "reason_codes": tuple(sorted(set(reason_codes))), "purpose_classification": purpose_classification,
        "identity_fingerprint": identity_fingerprint, "qualified_receipt_id": qualified_receipt_id,
        "first_observed_at": observation.first_observed_at, "processed_at": _utc(processed_at),
        "contract_id": CONTRACT_ID, "contract_version": CONTRACT_VERSION,
        "actionability": "WATCH_ONLY", "execution_status": "NON_EXECUTABLE", "gate6_clearance": False,
    }
    body["assessment_id"] = _snapshot_id("prospective-earnings-assessment", {
        "source_observation_id": observation.observation_id, "state": state,
        "reason_codes": body["reason_codes"], "purpose_classification": purpose_classification,
        "identity_fingerprint": identity_fingerprint, "qualified_receipt_id": qualified_receipt_id,
    })
    return ProspectiveScheduleAssessmentReceipt(**(body | {"fingerprint": content_fingerprint(body)}))


@dataclass(frozen=True, slots=True)
class ProspectiveSourcePollReceipt:
    """An auditable bounded source query, including empty and failed results."""

    poll_id: str
    run_id: str
    source_family: EarningsScheduleSourceFamily
    source_endpoint: str
    observed_at: datetime
    processed_at: datetime
    state: ProspectivePollState
    source_state: SourceState
    reason: str
    raw_artifact_id: str | None
    source_fingerprint: str | None
    http_status: int | None
    discovered_rows: int
    fingerprint: str
    contract_id: str = CONTRACT_ID
    contract_version: str = CONTRACT_VERSION
    actionability: str = "WATCH_ONLY"
    execution_status: str = "NON_EXECUTABLE"
    gate6_clearance: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "observed_at", _utc(self.observed_at))
        object.__setattr__(self, "processed_at", _utc(self.processed_at))
        expected_id = _snapshot_id("prospective-earnings-poll", {
            "run_id": self.run_id, "source_family": self.source_family,
            "source_endpoint": self.source_endpoint, "observed_at": self.observed_at,
        })
        failed = self.state is ProspectivePollState.FAILED
        if (
            self.poll_id != expected_id or not _id(self.run_id)
            or not isinstance(self.source_family, EarningsScheduleSourceFamily)
            or public_url(self.source_endpoint) != self.source_endpoint
            or self.processed_at < self.observed_at or not isinstance(self.state, ProspectivePollState)
            or not isinstance(self.source_state, SourceState) or not _id(self.reason)
            or (self.raw_artifact_id is not None and not _id(self.raw_artifact_id))
            or (self.source_fingerprint is not None and not _fp(self.source_fingerprint))
            or (self.http_status is not None and (type(self.http_status) is not int or not 100 <= self.http_status <= 599))
            or type(self.discovered_rows) is not int or self.discovered_rows < 0
            or failed != (self.source_state not in {SourceState.SOURCE_PARTIAL, SourceState.SUCCESS_WITH_ROWS, SourceState.SUCCESS_NO_QUALIFYING_ROWS})
            or self.contract_id != CONTRACT_ID or self.contract_version != CONTRACT_VERSION
            or self.actionability != "WATCH_ONLY" or self.execution_status != "NON_EXECUTABLE"
            or self.gate6_clearance is not False
            or self.fingerprint != content_fingerprint(_payload(self, skip=frozenset({"fingerprint"})))
        ):
            raise ProspectiveReceiptCollectorError("EARNINGS_PROSPECTIVE_POLL_RECEIPT_INVALID")


def make_source_poll_receipt(*, run_id: str, batch: SourceBatch, observed_at: datetime,
                             processed_at: datetime, raw_artifact_id: str | None) -> ProspectiveSourcePollReceipt:
    batch.__post_init__()
    family = _family(batch.exchange)
    state = (ProspectivePollState.PARTIAL if batch.state in {
        SourceState.SOURCE_PARTIAL, SourceState.SUCCESS_WITH_ROWS, SourceState.SUCCESS_NO_QUALIFYING_ROWS,
    } else ProspectivePollState.FAILED)
    body: dict[str, object] = {
        "run_id": run_id, "source_family": family, "source_endpoint": batch.url,
        "observed_at": _utc(observed_at), "processed_at": _utc(processed_at), "state": state,
        "source_state": batch.state, "reason": batch.reason, "raw_artifact_id": raw_artifact_id,
        "source_fingerprint": batch.source_fingerprint, "http_status": batch.http_status,
        "discovered_rows": len(batch.rows), "contract_id": CONTRACT_ID, "contract_version": CONTRACT_VERSION,
        "actionability": "WATCH_ONLY", "execution_status": "NON_EXECUTABLE", "gate6_clearance": False,
    }
    body["poll_id"] = _snapshot_id("prospective-earnings-poll", {
        "run_id": run_id, "source_family": family, "source_endpoint": batch.url,
        "observed_at": body["observed_at"],
    })
    return ProspectiveSourcePollReceipt(**(body | {"fingerprint": content_fingerprint(body)}))


@dataclass(frozen=True, slots=True)
class ProspectiveCollectionRunReceipt:
    """One one-shot bounded run; it cannot schedule itself or authorize action."""

    run_id: str
    started_at: datetime
    completed_at: datetime
    target_instrument_ids: tuple[str, ...]
    poll_ids: tuple[str, ...]
    source_observation_ids: tuple[str, ...]
    qualified_receipt_ids: tuple[str, ...]
    coverage_receipt_ids: tuple[str, ...]
    inserted: int
    already_present: int
    failed_polls: int
    fingerprint: str
    contract_id: str = CONTRACT_ID
    contract_version: str = CONTRACT_VERSION
    actionability: str = "WATCH_ONLY"
    execution_status: str = "NON_EXECUTABLE"
    gate6_clearance: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "started_at", _utc(self.started_at))
        object.__setattr__(self, "completed_at", _utc(self.completed_at))
        expected_id = _snapshot_id("prospective-earnings-run", {
            "started_at": self.started_at, "target_instrument_ids": self.target_instrument_ids,
        })
        if (
            self.run_id != expected_id or self.completed_at < self.started_at
            or not _sorted_unique(self.target_instrument_ids)
            or any(_INSTRUMENT.fullmatch(item) is None for item in self.target_instrument_ids)
            or any(not _sorted_unique_or_empty(item) for item in (
                self.poll_ids, self.source_observation_ids, self.coverage_receipt_ids,
            ))
            or self.qualified_receipt_ids != tuple(sorted(set(self.qualified_receipt_ids)))
            or any(not _id(item) for item in self.qualified_receipt_ids)
            or min(self.inserted, self.already_present, self.failed_polls) < 0
            or self.contract_id != CONTRACT_ID or self.contract_version != CONTRACT_VERSION
            or self.actionability != "WATCH_ONLY" or self.execution_status != "NON_EXECUTABLE"
            or self.gate6_clearance is not False
            or self.fingerprint != content_fingerprint(_payload(self, skip=frozenset({"fingerprint"})))
        ):
            raise ProspectiveReceiptCollectorError("EARNINGS_PROSPECTIVE_RUN_RECEIPT_INVALID")


class ProspectiveEarningsScheduleReceiptStore:
    """Insert-only typed records in the existing immutable snapshot family."""

    family = CoreApiSnapshotFamily.EARNINGS_SCHEDULE_PROSPECTIVE_RECEIPT

    def __init__(self, repository: CoreApiSnapshotRepository) -> None:
        self._repository = repository

    def save(self, value: object, *, snapshot_id: str, created_at: datetime) -> ProspectiveReceiptWriteOutcome:
        fingerprint = getattr(value, "fingerprint", None)
        if not _id(snapshot_id) or not _fp(fingerprint):
            raise ProspectiveReceiptCollectorError("EARNINGS_PROSPECTIVE_STORE_VALUE_INVALID")
        existing = self._repository.get_snapshot(snapshot_id)
        if existing is not None:
            if existing.family is self.family and existing.payload == value:
                return ProspectiveReceiptWriteOutcome.ALREADY_PRESENT
            raise ProspectiveReceiptCollectorError("EARNINGS_PROSPECTIVE_IMMUTABILITY_CONFLICT")
        self._repository.save_snapshot(CoreApiSnapshot(
            snapshot_id, self.family, "v1", type(value).__name__, fingerprint, _utc(created_at), value,
        ))
        return ProspectiveReceiptWriteOutcome.INSERTED

    def retain_artifact(self, value: ProspectiveRawArtifactReceipt) -> tuple[ProspectiveRawArtifactReceipt, ProspectiveReceiptWriteOutcome]:
        """Return the original observation for unchanged raw source bytes."""
        existing = self._repository.get_snapshot(value.artifact_id)
        if existing is not None:
            if existing.family is self.family and isinstance(existing.payload, ProspectiveRawArtifactReceipt):
                existing.payload.__post_init__()
                return existing.payload, ProspectiveReceiptWriteOutcome.ALREADY_PRESENT
            raise ProspectiveReceiptCollectorError("EARNINGS_PROSPECTIVE_IMMUTABILITY_CONFLICT")
        return value, self.save(value, snapshot_id=value.artifact_id, created_at=value.first_observed_at)

    def retain_observation(self, value: ProspectiveSourceObservation) -> tuple[ProspectiveSourceObservation, ProspectiveReceiptWriteOutcome]:
        """Keep a source row's original prospective first-observed timestamp."""
        artifact = self._repository.get_snapshot(value.raw_artifact_id)
        if (
            artifact is None or artifact.family is not self.family
            or not isinstance(artifact.payload, ProspectiveRawArtifactReceipt)
            or artifact.payload.source_family is not value.source_family
            or artifact.payload.source_endpoint != _raw_artifact_endpoint(value.source)
        ):
            raise ProspectiveReceiptCollectorError("EARNINGS_PROSPECTIVE_RAW_LINEAGE_UNVERIFIED")
        if value.discovery_observation_id is not None:
            parent = self._repository.get_snapshot(value.discovery_observation_id)
            if (
                parent is None or parent.family is not self.family
                or not isinstance(parent.payload, ProspectiveSourceObservation)
                or parent.payload.source_family is not value.source_family
                or parent.payload.source_record_identity != value.source_record_identity
            ):
                raise ProspectiveReceiptCollectorError("EARNINGS_PROSPECTIVE_DISCOVERY_LINEAGE_UNVERIFIED")
        existing = self._repository.get_snapshot(value.observation_id)
        if existing is not None:
            if existing.family is self.family and isinstance(existing.payload, ProspectiveSourceObservation):
                existing.payload.__post_init__()
                return existing.payload, ProspectiveReceiptWriteOutcome.ALREADY_PRESENT
            raise ProspectiveReceiptCollectorError("EARNINGS_PROSPECTIVE_IMMUTABILITY_CONFLICT")
        return value, self.save(value, snapshot_id=value.observation_id, created_at=value.first_observed_at)

    def retain_assessment(self, value: ProspectiveScheduleAssessmentReceipt) -> tuple[ProspectiveScheduleAssessmentReceipt, ProspectiveReceiptWriteOutcome]:
        observation = self._repository.get_snapshot(value.source_observation_id)
        if observation is None or observation.family is not self.family or not isinstance(observation.payload, ProspectiveSourceObservation):
            raise ProspectiveReceiptCollectorError("EARNINGS_PROSPECTIVE_OBSERVATION_LINEAGE_UNVERIFIED")
        existing = self._repository.get_snapshot(value.assessment_id)
        if existing is not None:
            if existing.family is self.family and isinstance(existing.payload, ProspectiveScheduleAssessmentReceipt):
                existing.payload.__post_init__()
                return existing.payload, ProspectiveReceiptWriteOutcome.ALREADY_PRESENT
            raise ProspectiveReceiptCollectorError("EARNINGS_PROSPECTIVE_IMMUTABILITY_CONFLICT")
        return value, self.save(value, snapshot_id=value.assessment_id, created_at=value.processed_at)

    def retain_event(self, value: ProspectiveQualifiedScheduleReceipt) -> tuple[ProspectiveQualifiedScheduleReceipt, ProspectiveReceiptWriteOutcome]:
        observation = self._repository.get_snapshot(value.source_observation_id)
        if (
            observation is None or observation.family is not self.family
            or not isinstance(observation.payload, ProspectiveSourceObservation)
            or observation.payload.source_family is not value.source_family
            or observation.payload.source_record_identity != value.source_filing_identity
            or observation.payload.source_record_fingerprint != value.source_payload_fingerprint
            or observation.payload.first_observed_at != value.system_first_observed.observed_at
        ):
            raise ProspectiveReceiptCollectorError("EARNINGS_PROSPECTIVE_EVENT_LINEAGE_UNVERIFIED")
        if value.revision_of_receipt_id is not None:
            parent = self._repository.get_snapshot(value.revision_of_receipt_id)
            if (
                parent is None or parent.family is not self.family
                or not isinstance(parent.payload, ProspectiveQualifiedScheduleReceipt)
                or parent.payload.source_family is not value.source_family
                or parent.payload.source_filing_identity != value.source_filing_identity
                or parent.payload.canonical_instrument_id != value.canonical_instrument_id
                or parent.payload.system_first_observed.observed_at >= value.system_first_observed.observed_at
                or parent.payload.lifecycle_state in {
                    ScheduleLifecycleState.CANCELLED, ScheduleLifecycleState.SUPERSEDED,
                }
            ):
                raise ProspectiveReceiptCollectorError("EARNINGS_PROSPECTIVE_REVISION_PARENT_UNVERIFIED")
        existing = self._repository.get_snapshot(value.receipt_id)
        if existing is not None:
            if existing.family is self.family and isinstance(existing.payload, ProspectiveQualifiedScheduleReceipt):
                existing.payload.__post_init__()
                return existing.payload, ProspectiveReceiptWriteOutcome.ALREADY_PRESENT
            raise ProspectiveReceiptCollectorError("EARNINGS_PROSPECTIVE_IMMUTABILITY_CONFLICT")
        return value, self.save(value, snapshot_id=value.receipt_id, created_at=value.processed_at)

    def values(self) -> tuple[object, ...]:
        result: list[object] = []
        offset = 0
        while True:
            page = self._repository.list_snapshots(self.family, limit=100, offset=offset)
            result.extend(item.payload for item in page)
            if len(page) < 100:
                return tuple(result)
            offset += len(page)

    def save_run(self, value: ProspectiveCollectionRunReceipt) -> ProspectiveReceiptWriteOutcome:
        """Keep the first immutable run receipt if a deterministic test replays it.

        Per-invocation inserted/already-present counters are operational facts,
        not grounds to overwrite the prior receipt bearing the same run ID.
        """
        existing = self._repository.get_snapshot(value.run_id)
        if existing is not None:
            if existing.family is self.family and isinstance(existing.payload, ProspectiveCollectionRunReceipt):
                return ProspectiveReceiptWriteOutcome.ALREADY_PRESENT
            raise ProspectiveReceiptCollectorError("EARNINGS_PROSPECTIVE_IMMUTABILITY_CONFLICT")
        return self.save(value, snapshot_id=value.run_id, created_at=value.completed_at)

    def event_receipts(self, *, source_family: EarningsScheduleSourceFamily,
                       source_filing_identity: str) -> tuple[ProspectiveQualifiedScheduleReceipt, ...]:
        values = tuple(item for item in self.values() if isinstance(item, ProspectiveQualifiedScheduleReceipt)
                       and item.source_family is source_family and item.source_filing_identity == source_filing_identity)
        return tuple(sorted(values, key=lambda item: (item.system_first_observed.observed_at, item.receipt_id)))


class _RecordingTransport:
    """Captures the one exact response passed to existing adapter code."""

    def __init__(self, delegate: Transport) -> None:
        self._delegate = delegate
        self.response: Fetch | None = None

    def get(self, url: str) -> Fetch:
        response = self._delegate.get(url)
        self.response = response
        return response


@dataclass(frozen=True, slots=True)
class ProspectiveCollectionResult:
    run_receipt: ProspectiveCollectionRunReceipt
    positive_receipts: tuple[ProspectiveQualifiedScheduleReceipt, ...]
    live_positive_event_proof: str

    def __post_init__(self) -> None:
        self.run_receipt.__post_init__()
        if self.live_positive_event_proof not in {"PROVEN", "PENDING_EVENT", "FAILED"}:
            raise ProspectiveReceiptCollectorError("EARNINGS_PROSPECTIVE_LIVE_PROOF_INVALID")
        if (self.live_positive_event_proof == "PROVEN") != bool(self.positive_receipts):
            raise ProspectiveReceiptCollectorError("EARNINGS_PROSPECTIVE_LIVE_PROOF_CONTRADICTION")


class ProspectiveEarningsScheduleReceiptCollector:
    """Bounded NSE RSS + BSE recent-list/detail collection, one invocation only."""

    def __init__(self, *, store: ProspectiveEarningsScheduleReceiptStore,
                 identity_bridge: EarningsScheduleCanonicalIdentityBridge, transport: Transport,
                 clock: CollectorClock | None = None) -> None:
        self._store = store
        self._identity_bridge = identity_bridge
        self._transport = transport
        self._clock = clock or SystemUtcClock()
        if not isinstance(identity_bridge, EarningsScheduleCanonicalIdentityBridge):
            raise ProspectiveReceiptCollectorError("EARNINGS_PROSPECTIVE_IDENTITY_BRIDGE_REQUIRED")

    def _now(self) -> datetime:
        return _utc(self._clock.now())

    def collect_once(self, *, target_instrument_ids: tuple[str, ...]) -> ProspectiveCollectionResult:
        targets = tuple(sorted(target_instrument_ids))
        if targets != tuple(sorted(set(targets))) or not _sorted_unique(targets) or any(_INSTRUMENT.fullmatch(item) is None for item in targets):
            raise ProspectiveReceiptCollectorError("EARNINGS_PROSPECTIVE_EXACT_TARGETS_REQUIRED")
        started = self._now()
        run_id = _snapshot_id("prospective-earnings-run", {
            "started_at": started, "target_instrument_ids": targets,
        })
        inserted = already = failed = 0
        poll_ids: list[str] = []
        observations: list[ProspectiveSourceObservation] = []
        positives: list[ProspectiveQualifiedScheduleReceipt] = []
        coverage_ids: list[str] = []
        sequence = 0

        def save(value: object, snapshot_id: str, created_at: datetime) -> None:
            nonlocal inserted, already
            outcome = self._store.save(value, snapshot_id=snapshot_id, created_at=created_at)
            if outcome is ProspectiveReceiptWriteOutcome.INSERTED:
                inserted += 1
            else:
                already += 1

        def capture_batch(batch: SourceBatch, recorder: _RecordingTransport, observed_at: datetime) -> tuple[ProspectiveRawArtifactReceipt | None, ProspectiveSourcePollReceipt]:
            nonlocal inserted, already, failed
            artifact = None
            if recorder.response is not None:
                response = recorder.response
                artifact = make_raw_artifact_receipt(
                    source_family=_family(batch.exchange), source_endpoint=response.url,
                    raw_payload=response.body, observed_at=observed_at,
                    request_identity="OFFICIAL_SOURCE_GET", adapter_version="official-earnings-schedule-source/v1",
                    http_status=response.status,
                )
                artifact, outcome = self._store.retain_artifact(artifact)
                if outcome is ProspectiveReceiptWriteOutcome.INSERTED:
                    inserted += 1
                else:
                    already += 1
            poll = make_source_poll_receipt(
                run_id=run_id, batch=batch, observed_at=observed_at, processed_at=self._now(),
                raw_artifact_id=artifact.artifact_id if artifact else None,
            )
            save(poll, poll.poll_id, poll.processed_at)
            poll_ids.append(poll.poll_id)
            if poll.state is ProspectivePollState.FAILED:
                failed += 1
            return artifact, poll

        def retain_rows(batch: SourceBatch, artifact: ProspectiveRawArtifactReceipt | None, observed_at: datetime,
                        discovery_observation_id: str | None = None) -> tuple[ProspectiveSourceObservation, ...]:
            nonlocal inserted, already
            if artifact is None:
                return ()
            local: list[ProspectiveSourceObservation] = []
            seen: set[tuple[str, str]] = set()
            for row in batch.rows:
                key = (_source_record_identity(row), row.fingerprint)
                if key in seen:
                    continue
                seen.add(key)
                value = make_source_observation(
                    artifact=artifact, source=row, observed_at=observed_at,
                    discovery_observation_id=discovery_observation_id,
                )
                value, outcome = self._store.retain_observation(value)
                if outcome is ProspectiveReceiptWriteOutcome.INSERTED:
                    inserted += 1
                else:
                    already += 1
                local.append(value)
                observations.append(value)
            return tuple(local)

        # Existing bounded NSE RSS adapter; no source timestamp is promoted to
        # public-time authority.  RSS rows without exact security evidence are
        # intentionally retained but not guessed into qualifying candidates.
        nse_recorder = _RecordingTransport(self._transport)
        nse_observed = self._now()
        nse_batch = NSEOfficialEarningsScheduleSource(nse_recorder).fetch(retrieved_at=nse_observed)
        nse_artifact, nse_poll = capture_batch(nse_batch, nse_recorder, nse_observed)
        nse_discovery = retain_rows(nse_batch, nse_artifact, nse_observed)

        details: list[ProspectiveSourceObservation] = []
        # An RSS row is discovery only.  Each exact linked primary-intimation
        # document is bounded by the feed's item limit and retains a parent
        # discovery observation; no title/company-name inference is used.
        for discovery in nse_discovery:
            detail_recorder = _RecordingTransport(self._transport)
            detail_observed = self._now()
            detail_batch = NSEOfficialEarningsScheduleSource(detail_recorder).fetch_linked_prior_intimation(
                discovery.source, retrieved_at=detail_observed,
            )
            detail_artifact, _ = capture_batch(detail_batch, detail_recorder, detail_observed)
            details.extend(retain_rows(
                detail_batch, detail_artifact, detail_observed,
                discovery_observation_id=discovery.observation_id,
            ))

        # BSE discovery records are preserved first.  Each currently rendered,
        # exact detail link is then fetched through the already-supported
        # detail adapter; list evidence alone never admits purpose.
        bse_recorder = _RecordingTransport(self._transport)
        bse_observed = self._now()
        bse_batch = discover_bse(bse_recorder, retrieved_at=bse_observed)
        bse_artifact, bse_poll = capture_batch(bse_batch, bse_recorder, bse_observed)
        bse_discovery = retain_rows(bse_batch, bse_artifact, bse_observed)
        for discovery in bse_discovery:
            detail_recorder = _RecordingTransport(self._transport)
            detail_observed = self._now()
            detail_batch = BSEOfficialEarningsScheduleSource(detail_recorder).fetch(
                retrieved_at=detail_observed, url=discovery.source.reference,
            )
            detail_artifact, _ = capture_batch(detail_batch, detail_recorder, detail_observed)
            details.extend(retain_rows(
                detail_batch, detail_artifact, detail_observed,
                discovery_observation_id=discovery.observation_id,
            ))

        for observation in details:
            receipt, outcomes = self._qualify(
                observation, target_instrument_ids=targets, run_id=run_id, run_sequence=sequence,
            )
            sequence += 1
            for outcome in outcomes:
                if outcome is ProspectiveReceiptWriteOutcome.INSERTED:
                    inserted += 1
                else:
                    already += 1
            if receipt is not None:
                positives.append(receipt)

        # Reuse the existing V1 coverage receipt strictly as partial evidence.
        # A bounded discovery/list route never has complete source scope, so
        # even zero qualifying rows cannot become negative clearance.
        source_pairs = ((nse_batch, nse_poll), (bse_batch, bse_poll))
        for batch, poll in source_pairs:
            family = _family(batch.exchange)
            matching = tuple(sorted(
                (item for item in positives if item.source_family is family), key=lambda item: item.receipt_id,
            ))
            for target in targets:
                qualifying = tuple(CoverageLineageReference(item.receipt_id, item.fingerprint)
                                   for item in matching if item.canonical_instrument_id == target)
                status = CoverageQueryStatus.FAILED if poll.state is ProspectivePollState.FAILED else CoverageQueryStatus.PARTIAL
                response = (batch.source_fingerprint,) if batch.source_fingerprint else ()
                now = self._now()
                provisional = make_earnings_schedule_coverage_receipt(
                    canonical_instrument_id=target, source_family=family,
                    window_start=now.date(), window_end=now.date(),
                    filter_semantics=CoverageQueryFilterSemantics.SOURCE_SCOPE_UNPROVEN,
                    query_status=status, query_completed_at=now, response_fingerprints=response,
                    qualifying_rows=qualifying, source_error_code=batch.reason if status is CoverageQueryStatus.FAILED else None,
                )
                sequence += 1
                first = None if not response else make_system_coverage_first_observed_receipt(
                    canonical_instrument_id=target, source_family=family, query_identity=provisional.receipt_id,
                    response_fingerprints=response, observed_at=now, ingestion_run_id=run_id, run_sequence=sequence,
                )
                coverage = make_earnings_schedule_coverage_receipt(
                    canonical_instrument_id=target, source_family=family,
                    window_start=now.date(), window_end=now.date(),
                    filter_semantics=CoverageQueryFilterSemantics.SOURCE_SCOPE_UNPROVEN,
                    query_status=status, query_completed_at=now, response_fingerprints=response,
                    qualifying_rows=qualifying, source_error_code=batch.reason if status is CoverageQueryStatus.FAILED else None,
                    system_first_observed=first,
                )
                save(coverage, "prospective-earnings-coverage:" + coverage.receipt_id, coverage.query_completed_at)
                coverage_ids.append(coverage.receipt_id)

        completed = self._now()
        run_body: dict[str, object] = {
            "started_at": started, "completed_at": completed, "target_instrument_ids": targets,
            "poll_ids": tuple(sorted(set(poll_ids))),
            "source_observation_ids": tuple(sorted({item.observation_id for item in observations})),
            "qualified_receipt_ids": tuple(sorted({item.receipt_id for item in positives})),
            "coverage_receipt_ids": tuple(sorted(set(coverage_ids))), "inserted": inserted,
            "already_present": already, "failed_polls": failed,
            "contract_id": CONTRACT_ID, "contract_version": CONTRACT_VERSION,
            "actionability": "WATCH_ONLY", "execution_status": "NON_EXECUTABLE", "gate6_clearance": False,
        }
        run_body["run_id"] = run_id
        run = ProspectiveCollectionRunReceipt(**(run_body | {"fingerprint": content_fingerprint(run_body)}))
        outcome = self._store.save_run(run)
        if outcome is ProspectiveReceiptWriteOutcome.INSERTED:
            inserted += 1
        else:
            already += 1
        ordered = tuple(sorted({item.receipt_id: item for item in positives}.values(), key=lambda item: item.receipt_id))
        return ProspectiveCollectionResult(run, ordered, "PROVEN" if ordered else "PENDING_EVENT")

    def _qualify(self, observation: ProspectiveSourceObservation, *, target_instrument_ids: tuple[str, ...], run_id: str,
                 run_sequence: int) -> tuple[ProspectiveQualifiedScheduleReceipt | None, tuple[ProspectiveReceiptWriteOutcome, ...]]:
        row = observation.source
        source_key = "symbol" if row.exchange.value == "NSE" else "security_code"
        resolver = self._identity_bridge.resolve_nse if row.exchange.value == "NSE" else self._identity_bridge.resolve_bse
        identity = resolver(row.field(source_key), row.field("isin"), observation.first_observed_at)
        purpose = classify(row)
        def unavailable(state: ProspectiveObservationState, reasons: tuple[str, ...]):
            assessment = make_schedule_assessment_receipt(
                observation=observation, state=state, reason_codes=reasons,
                purpose_classification=purpose.classification, identity_fingerprint=(
                    identity.fingerprint if identity.resolution_state is IdentityState.RESOLVED else None
                ), qualified_receipt_id=None, processed_at=self._now(),
            )
            assessment, outcome = self._store.retain_assessment(assessment)
            return None, (outcome,)

        if identity.resolution_state is not IdentityState.RESOLVED or identity.canonical_instrument_id is None:
            extras = (() if purpose.classification not in {PurposeClassification.AMBIGUOUS, PurposeClassification.NON_QUALIFYING}
                      else (("EXPLICIT_RESULTS_PURPOSE_REQUIRED",) if purpose.classification is PurposeClassification.AMBIGUOUS
                            else ("NON_QUALIFYING_RESULTS_PURPOSE",)))
            return unavailable(ProspectiveObservationState.IDENTITY_UNRESOLVED, ("EXACT_CANONICAL_IDENTITY_REQUIRED",) + extras)
        if identity.canonical_instrument_id not in target_instrument_ids:
            # Discovery is intentionally global and source-complete scope is
            # unproven. Retain its raw lineage, but do not turn an exact
            # unrelated issuer into a receipt for this bounded 31-company
            # collection cohort.
            return unavailable(
                ProspectiveObservationState.OUTSIDE_TARGET_COHORT,
                ("OUTSIDE_EXACT_TARGET_COHORT",),
            )
        explicit_lifecycle = _explicit_lifecycle(row)
        prior = self._store.event_receipts(
            source_family=observation.source_family, source_filing_identity=observation.source_record_identity,
        )
        if explicit_lifecycle is None:
            return unavailable(
                ProspectiveObservationState.REVISION_LINEAGE_UNRESOLVED,
                ("SOURCE_LIFECYCLE_UNSUPPORTED",),
            )
        if explicit_lifecycle is not ScheduleLifecycleState.ANNOUNCED and not prior:
            # A source-declared revision/reschedule/cancellation has no
            # deterministic parent merely because it was observed first. Its
            # raw observation remains immutable; qualification stays closed.
            return unavailable(
                ProspectiveObservationState.REVISION_LINEAGE_UNRESOLVED,
                ("EXACT_PARENT_RECEIPT_REQUIRED",),
            )
        if purpose.classification in {PurposeClassification.AMBIGUOUS, PurposeClassification.NON_QUALIFYING}:
            state = (ProspectiveObservationState.PURPOSE_AMBIGUOUS if purpose.classification is PurposeClassification.AMBIGUOUS
                     else ProspectiveObservationState.NON_QUALIFYING)
            return unavailable(state, (purpose.rule,))
        try:
            scheduled = parse_meeting_date(row.field("meeting_date_iso") or row.field("meeting_date") or "")
        except ValueError:
            return unavailable(ProspectiveObservationState.DATE_UNAVAILABLE, ("SCHEDULE_DATE_UNAVAILABLE",))
        same = _snapshot_id("prospective-earnings-schedule", {
            "source_family": observation.source_family,
            "source_filing_identity": observation.source_record_identity,
            "source_payload_fingerprint": observation.source_record_fingerprint,
        })
        for item in prior:
            if item.receipt_id == same:
                assessment = make_schedule_assessment_receipt(
                    observation=observation, state=ProspectiveObservationState.OBSERVED, reason_codes=(),
                    purpose_classification=purpose.classification, identity_fingerprint=identity.fingerprint,
                    qualified_receipt_id=item.receipt_id, processed_at=self._now(),
                )
                _, outcome = self._store.retain_assessment(assessment)
                return item, (ProspectiveReceiptWriteOutcome.ALREADY_PRESENT, outcome)
        if prior and any(item.canonical_instrument_id != identity.canonical_instrument_id for item in prior):
            return unavailable(ProspectiveObservationState.EVIDENCE_CONFLICTED, ("SOURCE_RECORD_IDENTITY_CONFLICT",))
        if prior and prior[-1].lifecycle_state in {
            ScheduleLifecycleState.CANCELLED, ScheduleLifecycleState.SUPERSEDED,
        }:
            return unavailable(
                ProspectiveObservationState.REVISION_LINEAGE_UNRESOLVED,
                ("REVISION_PARENT_TERMINAL",),
            )
        lifecycle, parent = ScheduleLifecycleState.ANNOUNCED, None
        if prior:
            lifecycle = (
                explicit_lifecycle
                if explicit_lifecycle is not ScheduleLifecycleState.ANNOUNCED
                else ScheduleLifecycleState.REVISED
            )
            parent = prior[-1].receipt_id
        first = make_system_first_observed_receipt(
            canonical_instrument_id=identity.canonical_instrument_id,
            source_filing_identity=observation.source_record_identity,
            source_payload_fingerprint=observation.source_record_fingerprint,
            observed_at=observation.first_observed_at, ingestion_run_id=run_id, run_sequence=run_sequence,
        )
        receipt = make_qualified_schedule_receipt(
            observation=observation, canonical_instrument_id=identity.canonical_instrument_id,
            identity_fingerprint=identity.fingerprint, purpose_classification=purpose.classification,
            purpose_rule=purpose.rule, event_date=scheduled, first_observed=first,
            processed_at=self._now(), lifecycle_state=lifecycle, revision_of_receipt_id=parent,
        )
        receipt, event_outcome = self._store.retain_event(receipt)
        assessment = make_schedule_assessment_receipt(
            observation=observation, state=ProspectiveObservationState.OBSERVED, reason_codes=(),
            purpose_classification=purpose.classification, identity_fingerprint=identity.fingerprint,
            qualified_receipt_id=receipt.receipt_id, processed_at=self._now(),
        )
        _, assessment_outcome = self._store.retain_assessment(assessment)
        return receipt, (event_outcome, assessment_outcome)


__all__ = (
    "COLLECTOR_VERSION", "CONTRACT_ID", "CONTRACT_VERSION", "CollectorClock",
    "ProspectiveCollectionResult", "ProspectiveCollectionRunReceipt",
    "ProspectiveEarningsScheduleReceiptCollector", "ProspectiveEarningsScheduleReceiptStore",
    "ProspectiveObservationState", "ProspectivePollState", "ProspectiveQualifiedScheduleReceipt",
    "ProspectiveRawArtifactReceipt", "ProspectiveReceiptCollectorError", "ProspectiveReceiptWriteOutcome",
    "ProspectiveSourceObservation", "ProspectiveSourcePollReceipt", "SystemUtcClock",
    "make_qualified_schedule_receipt", "make_raw_artifact_receipt", "make_source_observation",
)
