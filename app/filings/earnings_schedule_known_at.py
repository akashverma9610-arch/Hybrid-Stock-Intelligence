"""Pure, fail-closed known-at semantics for official earnings schedules.

This module is intentionally *not* connected to schedule normalization, the
candidate store, Gate 6, or any runtime.  It represents two different facts:
when an exchange made an exact source record public, and when HSI first
observed that record.  A caller must supply the immutable source provenance;
this module never consults a clock, a transport, a repository, or a provider.
"""
from __future__ import annotations

from dataclasses import dataclass, fields
from datetime import UTC, datetime
from enum import StrEnum
import re

from app.fundamentals.diagnostic_comparability import canonical_json, content_fingerprint
from app.historical.filing_timestamp_timezone_provenance import (
    FilingTimestampProvenanceReceipt,
    TimestampResolutionState,
)


CONTRACT_ID = "official-earnings-schedule-known-at-semantics"
CONTRACT_VERSION = "v1"
_IDENTIFIER = re.compile(r"[A-Za-z0-9._:-]+\Z")
_FINGERPRINT = re.compile(r"sha256:[0-9a-f]{64}\Z")


class EarningsScheduleKnownAtError(ValueError):
    """Stable fail-closed error for malformed schedule temporal evidence."""


class TimestampFieldSemantic(StrEnum):
    PUBLIC_DISSEMINATION_TIME = "PUBLIC_DISSEMINATION_TIME"
    EXCHANGE_RECEIPT_TIME = "EXCHANGE_RECEIPT_TIME"
    ISSUER_DOCUMENT_TIME = "ISSUER_DOCUMENT_TIME"
    EVENT_SCHEDULE_TIME = "EVENT_SCHEDULE_TIME"
    SYSTEM_FIRST_OBSERVED_TIME = "SYSTEM_FIRST_OBSERVED_TIME"
    UNKNOWN_SEMANTIC = "UNKNOWN_SEMANTIC"


class SourceTimestampSemanticAuthority(StrEnum):
    PROVEN = "PROVEN"
    UNPROVEN = "UNPROVEN"


class SystemFirstObservedOrigin(StrEnum):
    AUTOMATIC_INGESTION_BOUNDARY = "AUTOMATIC_INGESTION_BOUNDARY"


class KnownAtPerspective(StrEnum):
    PUBLIC_MARKET = "PUBLIC_MARKET"
    HSI_LOCAL = "HSI_LOCAL"


class KnownAtState(StrEnum):
    STRICT_SOURCE_PIT = "STRICT_SOURCE_PIT"
    PROSPECTIVE_FIRST_OBSERVED_PIT = "PROSPECTIVE_FIRST_OBSERVED_PIT"
    CURRENT_DESCRIPTIVE_ONLY = "CURRENT_DESCRIPTIVE_ONLY"
    TEMPORAL_AUTHORITY_UNAVAILABLE = "TEMPORAL_AUTHORITY_UNAVAILABLE"


class KnownAtReason(StrEnum):
    PUBLIC_SOURCE_PIT_VERIFIED = "PUBLIC_SOURCE_PIT_VERIFIED"
    SYSTEM_FIRST_OBSERVED_VERIFIED = "SYSTEM_FIRST_OBSERVED_VERIFIED"
    SOURCE_PUBLIC_TIMESTAMP_UNPROVEN = "SOURCE_PUBLIC_TIMESTAMP_UNPROVEN"
    SOURCE_TIMESTAMP_NOT_PUBLIC_DISSEMINATION = "SOURCE_TIMESTAMP_NOT_PUBLIC_DISSEMINATION"
    SOURCE_TIMESTAMP_TIMEZONE_UNPROVEN = "SOURCE_TIMESTAMP_TIMEZONE_UNPROVEN"
    SOURCE_SEMANTIC_EVIDENCE_AFTER_PUBLIC_TIME = "SOURCE_SEMANTIC_EVIDENCE_AFTER_PUBLIC_TIME"
    SOURCE_PUBLIC_TIME_AFTER_AS_OF = "SOURCE_PUBLIC_TIME_AFTER_AS_OF"
    SYSTEM_FIRST_OBSERVED_UNAVAILABLE = "SYSTEM_FIRST_OBSERVED_UNAVAILABLE"
    SYSTEM_FIRST_OBSERVED_AFTER_AS_OF = "SYSTEM_FIRST_OBSERVED_AFTER_AS_OF"
    SYSTEM_OBSERVATION_PRECEDES_SOURCE_PUBLIC_TIME = "SYSTEM_OBSERVATION_PRECEDES_SOURCE_PUBLIC_TIME"
    TEMPORAL_EVIDENCE_ABSENT = "TEMPORAL_EVIDENCE_ABSENT"


def _aware(value: object) -> bool:
    return type(value) is datetime and value.tzinfo is not None and value.utcoffset() is not None


def _utc(value: datetime) -> datetime:
    if not _aware(value):
        raise EarningsScheduleKnownAtError("EARNINGS_SCHEDULE_KNOWN_AT_TIMESTAMP_AWARE_REQUIRED")
    return value.astimezone(UTC)


def _identifier(value: object) -> bool:
    return type(value) is str and _IDENTIFIER.fullmatch(value) is not None


def _fingerprint(value: object) -> bool:
    return type(value) is str and _FINGERPRINT.fullmatch(value) is not None


def _ordered_pairs(ids: tuple[str, ...], fingerprints: tuple[str, ...]) -> bool:
    pairs = tuple(zip(ids, fingerprints, strict=True))
    return (
        bool(pairs)
        and len(pairs) == len(set(pairs))
        and len(ids) == len(set(ids))
        and len(fingerprints) == len(set(fingerprints))
        and pairs == tuple(sorted(pairs))
        and all(_identifier(identity) and _fingerprint(fingerprint) for identity, fingerprint in pairs)
    )


def _payload(value: object, *, skip: frozenset[str] = frozenset()) -> dict[str, object]:
    return {field.name: getattr(value, field.name) for field in fields(value) if field.name not in skip}


@dataclass(frozen=True, slots=True)
class SourceTimestampEvidence:
    """A source timestamp plus separately proven field-role semantics.

    The existing timestamp receipt owns lossless raw retention and timezone
    provenance.  This wrapper supplies no timezone rule; it only records
    whether first-party evidence has proven that the field is public
    dissemination rather than exchange receipt or an issuer/event date.
    """

    semantic: TimestampFieldSemantic
    semantic_authority: SourceTimestampSemanticAuthority
    semantic_evidence_ids: tuple[str, ...]
    semantic_evidence_fingerprints: tuple[str, ...]
    semantic_evidence_known_at: datetime | None
    timestamp_receipt: FilingTimestampProvenanceReceipt

    def __post_init__(self) -> None:
        if self.semantic_evidence_known_at is not None:
            object.__setattr__(self, "semantic_evidence_known_at", _utc(self.semantic_evidence_known_at))
        self.timestamp_receipt.__post_init__()
        public_proven = (
            self.semantic is TimestampFieldSemantic.PUBLIC_DISSEMINATION_TIME
            and self.semantic_authority is SourceTimestampSemanticAuthority.PROVEN
        )
        if (
            not isinstance(self.semantic, TimestampFieldSemantic)
            or self.semantic is TimestampFieldSemantic.SYSTEM_FIRST_OBSERVED_TIME
            or not isinstance(self.semantic_authority, SourceTimestampSemanticAuthority)
            or len(self.semantic_evidence_ids) != len(self.semantic_evidence_fingerprints)
            or (public_proven and not _ordered_pairs(self.semantic_evidence_ids, self.semantic_evidence_fingerprints))
            or (public_proven and not _aware(self.semantic_evidence_known_at))
            or (not public_proven and (self.semantic_evidence_ids or self.semantic_evidence_fingerprints or self.semantic_evidence_known_at is not None))
        ):
            raise EarningsScheduleKnownAtError("EARNINGS_SCHEDULE_SOURCE_TIMESTAMP_SEMANTICS_INVALID")

    @property
    def strict_public_at(self) -> datetime | None:
        self.__post_init__()
        if (
            self.semantic is TimestampFieldSemantic.PUBLIC_DISSEMINATION_TIME
            and self.semantic_authority is SourceTimestampSemanticAuthority.PROVEN
            and self.timestamp_receipt.resolution_state is TimestampResolutionState.EXACT_FILING_TIMESTAMP_KNOWN
            and self.semantic_evidence_known_at is not None
            and self.semantic_evidence_known_at <= self.timestamp_receipt.normalized_utc_timestamp
        ):
            return _utc(self.timestamp_receipt.normalized_utc_timestamp)  # type: ignore[arg-type]
        return None


@dataclass(frozen=True, slots=True)
class SystemFirstObservedReceipt:
    """A prospective-only receipt created at an automatic ingestion boundary.

    The origin is intentionally fixed.  This pure contract cannot turn an
    arbitrary caller timestamp into a trusted receipt; production admission
    remains deferred until a boundary records these values automatically.
    """

    receipt_id: str
    canonical_instrument_id: str
    source_filing_identity: str
    source_payload_fingerprint: str
    observed_at: datetime
    ingestion_run_id: str
    run_sequence: int
    origin: SystemFirstObservedOrigin
    fingerprint: str
    contract_id: str = CONTRACT_ID
    contract_version: str = CONTRACT_VERSION
    actionability: str = "WATCH_ONLY"
    execution_status: str = "NON_EXECUTABLE"

    def __post_init__(self) -> None:
        object.__setattr__(self, "observed_at", _utc(self.observed_at))
        expected_id = "earnings-schedule-first-observed:" + content_fingerprint({
            "contract_id": self.contract_id,
            "contract_version": self.contract_version,
            "canonical_instrument_id": self.canonical_instrument_id,
            "source_filing_identity": self.source_filing_identity,
            "source_payload_fingerprint": self.source_payload_fingerprint,
            "observed_at": self.observed_at,
            "ingestion_run_id": self.ingestion_run_id,
            "run_sequence": self.run_sequence,
            "origin": self.origin,
        })[7:]
        if (
            self.receipt_id != expected_id
            or not _identifier(self.canonical_instrument_id)
            or not _identifier(self.source_filing_identity)
            or not _fingerprint(self.source_payload_fingerprint)
            or not _identifier(self.ingestion_run_id)
            or not isinstance(self.run_sequence, int)
            or self.run_sequence < 0
            or self.origin is not SystemFirstObservedOrigin.AUTOMATIC_INGESTION_BOUNDARY
            or self.contract_id != CONTRACT_ID
            or self.contract_version != CONTRACT_VERSION
            or self.actionability != "WATCH_ONLY"
            or self.execution_status != "NON_EXECUTABLE"
            or self.fingerprint != content_fingerprint(_payload(self, skip=frozenset({"fingerprint"})))
        ):
            raise EarningsScheduleKnownAtError("EARNINGS_SCHEDULE_FIRST_OBSERVED_RECEIPT_INVALID")

    def to_json(self) -> str:
        self.__post_init__()
        return canonical_json(_payload(self))


def make_system_first_observed_receipt(*, canonical_instrument_id: str, source_filing_identity: str,
                                       source_payload_fingerprint: str, observed_at: datetime,
                                       ingestion_run_id: str, run_sequence: int) -> SystemFirstObservedReceipt:
    """Build a deterministic receipt for a future trusted ingestion boundary."""
    body: dict[str, object] = {
        "canonical_instrument_id": canonical_instrument_id,
        "source_filing_identity": source_filing_identity,
        "source_payload_fingerprint": source_payload_fingerprint,
        "observed_at": _utc(observed_at),
        "ingestion_run_id": ingestion_run_id,
        "run_sequence": run_sequence,
        "origin": SystemFirstObservedOrigin.AUTOMATIC_INGESTION_BOUNDARY,
        "contract_id": CONTRACT_ID,
        "contract_version": CONTRACT_VERSION,
        "actionability": "WATCH_ONLY",
        "execution_status": "NON_EXECUTABLE",
    }
    receipt_id = "earnings-schedule-first-observed:" + content_fingerprint({
        key: body[key] for key in ("contract_id", "contract_version", "canonical_instrument_id",
                                    "source_filing_identity", "source_payload_fingerprint", "observed_at",
                                    "ingestion_run_id", "run_sequence", "origin")
    })[7:]
    values = body | {"receipt_id": receipt_id}
    return SystemFirstObservedReceipt(**(values | {"fingerprint": content_fingerprint(values)}))


@dataclass(frozen=True, slots=True)
class EarningsScheduleKnownAtEvidence:
    """Exact source identity with optional public-time and HSI-observation facts."""

    canonical_instrument_id: str
    source_filing_identity: str
    source_payload_fingerprint: str
    source_timestamp: SourceTimestampEvidence | None
    system_first_observed: SystemFirstObservedReceipt | None

    def __post_init__(self) -> None:
        if self.source_timestamp is not None:
            self.source_timestamp.__post_init__()
            receipt = self.source_timestamp.timestamp_receipt
            source_matches = (
                receipt.canonical_instrument_id == self.canonical_instrument_id
                and receipt.filing_id == self.source_filing_identity
                and receipt.source_payload_fingerprint == self.source_payload_fingerprint
            )
        else:
            source_matches = True
        if self.system_first_observed is not None:
            self.system_first_observed.__post_init__()
            observed_matches = (
                self.system_first_observed.canonical_instrument_id == self.canonical_instrument_id
                and self.system_first_observed.source_filing_identity == self.source_filing_identity
                and self.system_first_observed.source_payload_fingerprint == self.source_payload_fingerprint
            )
        else:
            observed_matches = True
        if (
            not _identifier(self.canonical_instrument_id)
            or not _identifier(self.source_filing_identity)
            or not _fingerprint(self.source_payload_fingerprint)
            or not source_matches
            or not observed_matches
        ):
            raise EarningsScheduleKnownAtError("EARNINGS_SCHEDULE_KNOWN_AT_EVIDENCE_INVALID")


@dataclass(frozen=True, slots=True)
class EarningsScheduleKnownAtResolution:
    """A reproducible answer for one perspective at one supplied PIT cutoff."""

    resolution_id: str
    canonical_instrument_id: str
    source_filing_identity: str
    source_payload_fingerprint: str
    perspective: KnownAtPerspective
    as_of: datetime
    state: KnownAtState
    known_at: datetime | None
    source_public_at: datetime | None
    hsi_available_at: datetime | None
    source_timestamp_semantic: TimestampFieldSemantic | None
    source_timestamp_receipt_fingerprint: str | None
    semantic_evidence_ids: tuple[str, ...]
    semantic_evidence_fingerprints: tuple[str, ...]
    semantic_evidence_known_at: datetime | None
    system_first_observed_receipt_id: str | None
    system_first_observed_receipt_fingerprint: str | None
    reason_codes: tuple[KnownAtReason, ...]
    fingerprint: str
    contract_id: str = CONTRACT_ID
    contract_version: str = CONTRACT_VERSION
    actionability: str = "WATCH_ONLY"
    execution_status: str = "NON_EXECUTABLE"

    def __post_init__(self) -> None:
        object.__setattr__(self, "as_of", _utc(self.as_of))
        for name in ("known_at", "source_public_at", "hsi_available_at"):
            value = getattr(self, name)
            if value is not None:
                object.__setattr__(self, name, _utc(value))
        if self.semantic_evidence_known_at is not None:
            object.__setattr__(self, "semantic_evidence_known_at", _utc(self.semantic_evidence_known_at))
        reasons = tuple(sorted(set(self.reason_codes), key=lambda value: value.value))
        identity_body = {
            "contract_id": self.contract_id,
            "contract_version": self.contract_version,
            "canonical_instrument_id": self.canonical_instrument_id,
            "source_filing_identity": self.source_filing_identity,
            "source_payload_fingerprint": self.source_payload_fingerprint,
            "perspective": self.perspective,
            "as_of": self.as_of,
        }
        expected_id = "earnings-schedule-known-at:" + content_fingerprint(identity_body)[7:]
        resolved = self.state in {KnownAtState.STRICT_SOURCE_PIT, KnownAtState.PROSPECTIVE_FIRST_OBSERVED_PIT}
        valid_shape = (
            (self.state is KnownAtState.STRICT_SOURCE_PIT
             and self.perspective is KnownAtPerspective.PUBLIC_MARKET
             and self.known_at == self.source_public_at and self.known_at is not None)
            or (self.state is KnownAtState.PROSPECTIVE_FIRST_OBSERVED_PIT
                and self.perspective is KnownAtPerspective.HSI_LOCAL
                and self.known_at == self.hsi_available_at and self.known_at is not None)
            or (self.state in {KnownAtState.CURRENT_DESCRIPTIVE_ONLY, KnownAtState.TEMPORAL_AUTHORITY_UNAVAILABLE}
                and self.known_at is None)
        )
        if (
            self.resolution_id != expected_id
            or not _identifier(self.canonical_instrument_id)
            or not _identifier(self.source_filing_identity)
            or not _fingerprint(self.source_payload_fingerprint)
            or not isinstance(self.perspective, KnownAtPerspective)
            or not isinstance(self.state, KnownAtState)
            or (self.source_timestamp_semantic is not None and not isinstance(self.source_timestamp_semantic, TimestampFieldSemantic))
            or (self.source_timestamp_semantic is None and (
                self.source_timestamp_receipt_fingerprint is not None
                or self.semantic_evidence_ids or self.semantic_evidence_fingerprints
                or self.semantic_evidence_known_at is not None
            ))
            or (self.source_timestamp_semantic is not None and (
                not _fingerprint(self.source_timestamp_receipt_fingerprint)
                or len(self.semantic_evidence_ids) != len(self.semantic_evidence_fingerprints)
                or tuple(zip(self.semantic_evidence_ids, self.semantic_evidence_fingerprints, strict=True)) != tuple(sorted(zip(self.semantic_evidence_ids, self.semantic_evidence_fingerprints, strict=True)))
                or len(self.semantic_evidence_ids) != len(set(self.semantic_evidence_ids))
                or len(self.semantic_evidence_fingerprints) != len(set(self.semantic_evidence_fingerprints))
                or any(not _identifier(item) for item in self.semantic_evidence_ids)
                or any(not _fingerprint(item) for item in self.semantic_evidence_fingerprints)
                or (bool(self.semantic_evidence_ids) != (self.semantic_evidence_known_at is not None))
            ))
            or ((self.system_first_observed_receipt_id is None) != (self.system_first_observed_receipt_fingerprint is None))
            or (self.system_first_observed_receipt_id is not None and (
                not _identifier(self.system_first_observed_receipt_id)
                or not _fingerprint(self.system_first_observed_receipt_fingerprint)
            ))
            or self.reason_codes != reasons
            or not self.reason_codes
            or not valid_shape
            or (resolved and self.known_at is not None and self.known_at > self.as_of)
            or (self.source_public_at is not None and self.source_public_at > self.as_of)
            or (self.hsi_available_at is not None and self.hsi_available_at > self.as_of)
            or self.contract_id != CONTRACT_ID
            or self.contract_version != CONTRACT_VERSION
            or self.actionability != "WATCH_ONLY"
            or self.execution_status != "NON_EXECUTABLE"
            or self.fingerprint != content_fingerprint(_payload(self, skip=frozenset({"fingerprint"})))
        ):
            raise EarningsScheduleKnownAtError("EARNINGS_SCHEDULE_KNOWN_AT_RESOLUTION_INVALID")

    def to_json(self) -> str:
        self.__post_init__()
        return canonical_json(_payload(self))


def resolve_earnings_schedule_known_at(*, evidence: EarningsScheduleKnownAtEvidence,
                                       perspective: KnownAtPerspective, as_of: datetime) -> EarningsScheduleKnownAtResolution:
    """Resolve source-public and HSI-local availability without conflating them.

    ``PUBLIC_MARKET`` never substitutes HSI observation for exchange public
    dissemination.  ``HSI_LOCAL`` never backdates an observation to a source
    timestamp.  The caller chooses the perspective explicitly; this contract
    deliberately does not introduce an implicit ``max(public, observed)`` rule.
    """
    evidence.__post_init__()
    point = _utc(as_of)
    if not isinstance(perspective, KnownAtPerspective):
        raise EarningsScheduleKnownAtError("EARNINGS_SCHEDULE_KNOWN_AT_PERSPECTIVE_INVALID")
    source = evidence.source_timestamp
    semantic = None if source is None else source.semantic
    source_receipt_fingerprint = None if source is None else source.timestamp_receipt.fingerprint
    semantic_ids = () if source is None else source.semantic_evidence_ids
    semantic_fingerprints = () if source is None else source.semantic_evidence_fingerprints
    semantic_known_at = None if source is None else source.semantic_evidence_known_at
    public_at = None if source is None else source.strict_public_at
    observed_at = None if evidence.system_first_observed is None else evidence.system_first_observed.observed_at
    observed_receipt_id = None if evidence.system_first_observed is None else evidence.system_first_observed.receipt_id
    observed_receipt_fingerprint = None if evidence.system_first_observed is None else evidence.system_first_observed.fingerprint
    visible_public = public_at if public_at is not None and public_at <= point else None
    visible_observed = observed_at if observed_at is not None and observed_at <= point else None
    source_reasons: list[KnownAtReason] = []
    observation_reasons: list[KnownAtReason] = []
    if source is None:
        source_reasons.append(KnownAtReason.TEMPORAL_EVIDENCE_ABSENT)
    if source is not None and source.semantic is not TimestampFieldSemantic.PUBLIC_DISSEMINATION_TIME:
        source_reasons.append(KnownAtReason.SOURCE_TIMESTAMP_NOT_PUBLIC_DISSEMINATION)
    if source is not None and source.semantic is TimestampFieldSemantic.PUBLIC_DISSEMINATION_TIME:
        if source.semantic_authority is not SourceTimestampSemanticAuthority.PROVEN:
            source_reasons.append(KnownAtReason.SOURCE_PUBLIC_TIMESTAMP_UNPROVEN)
        if source.timestamp_receipt.resolution_state is not TimestampResolutionState.EXACT_FILING_TIMESTAMP_KNOWN:
            source_reasons.append(KnownAtReason.SOURCE_TIMESTAMP_TIMEZONE_UNPROVEN)
        if (
            source.semantic_authority is SourceTimestampSemanticAuthority.PROVEN
            and source.timestamp_receipt.normalized_utc_timestamp is not None
            and source.semantic_evidence_known_at is not None
            and source.semantic_evidence_known_at > source.timestamp_receipt.normalized_utc_timestamp
        ):
            source_reasons.append(KnownAtReason.SOURCE_SEMANTIC_EVIDENCE_AFTER_PUBLIC_TIME)
    if public_at is not None and public_at > point:
        source_reasons.append(KnownAtReason.SOURCE_PUBLIC_TIME_AFTER_AS_OF)
    if observed_at is None:
        observation_reasons.append(KnownAtReason.SYSTEM_FIRST_OBSERVED_UNAVAILABLE)
    elif observed_at > point:
        observation_reasons.append(KnownAtReason.SYSTEM_FIRST_OBSERVED_AFTER_AS_OF)
    if public_at is not None and observed_at is not None and observed_at < public_at:
        observation_reasons.append(KnownAtReason.SYSTEM_OBSERVATION_PRECEDES_SOURCE_PUBLIC_TIME)
        visible_observed = None

    state: KnownAtState
    known_at: datetime | None
    if perspective is KnownAtPerspective.PUBLIC_MARKET and visible_public is not None:
        state, known_at = KnownAtState.STRICT_SOURCE_PIT, visible_public
    elif perspective is KnownAtPerspective.HSI_LOCAL and visible_observed is not None:
        state, known_at = KnownAtState.PROSPECTIVE_FIRST_OBSERVED_PIT, visible_observed
    elif source is not None:
        state, known_at = KnownAtState.CURRENT_DESCRIPTIVE_ONLY, None
    else:
        state, known_at = KnownAtState.TEMPORAL_AUTHORITY_UNAVAILABLE, None
    if state is KnownAtState.STRICT_SOURCE_PIT:
        actual_reasons = (KnownAtReason.PUBLIC_SOURCE_PIT_VERIFIED,)
    elif state is KnownAtState.PROSPECTIVE_FIRST_OBSERVED_PIT:
        actual_reasons = (KnownAtReason.SYSTEM_FIRST_OBSERVED_VERIFIED,)
    elif perspective is KnownAtPerspective.PUBLIC_MARKET:
        actual_reasons = tuple(sorted(set(source_reasons), key=lambda value: value.value))
    else:
        actual_reasons = tuple(sorted(set(observation_reasons), key=lambda value: value.value))
    if not actual_reasons:
        actual_reasons = (KnownAtReason.TEMPORAL_EVIDENCE_ABSENT,)
    identity_body = {
        "contract_id": CONTRACT_ID,
        "contract_version": CONTRACT_VERSION,
        "canonical_instrument_id": evidence.canonical_instrument_id,
        "source_filing_identity": evidence.source_filing_identity,
        "source_payload_fingerprint": evidence.source_payload_fingerprint,
        "perspective": perspective,
        "as_of": point,
    }
    body: dict[str, object] = {
        "resolution_id": "earnings-schedule-known-at:" + content_fingerprint(identity_body)[7:],
        "canonical_instrument_id": evidence.canonical_instrument_id,
        "source_filing_identity": evidence.source_filing_identity,
        "source_payload_fingerprint": evidence.source_payload_fingerprint,
        "perspective": perspective,
        "as_of": point,
        "state": state,
        "known_at": known_at,
        "source_public_at": visible_public,
        "hsi_available_at": visible_observed,
        "source_timestamp_semantic": semantic,
        "source_timestamp_receipt_fingerprint": source_receipt_fingerprint,
        "semantic_evidence_ids": semantic_ids,
        "semantic_evidence_fingerprints": semantic_fingerprints,
        "semantic_evidence_known_at": semantic_known_at,
        "system_first_observed_receipt_id": observed_receipt_id,
        "system_first_observed_receipt_fingerprint": observed_receipt_fingerprint,
        "reason_codes": actual_reasons,
        "contract_id": CONTRACT_ID,
        "contract_version": CONTRACT_VERSION,
        "actionability": "WATCH_ONLY",
        "execution_status": "NON_EXECUTABLE",
    }
    return EarningsScheduleKnownAtResolution(**(body | {"fingerprint": content_fingerprint(body)}))


__all__ = (
    "CONTRACT_ID", "CONTRACT_VERSION", "EarningsScheduleKnownAtError", "EarningsScheduleKnownAtEvidence",
    "EarningsScheduleKnownAtResolution", "KnownAtPerspective", "KnownAtReason", "KnownAtState",
    "SourceTimestampEvidence", "SourceTimestampSemanticAuthority", "SystemFirstObservedOrigin",
    "SystemFirstObservedReceipt", "TimestampFieldSemantic", "make_system_first_observed_receipt",
    "resolve_earnings_schedule_known_at",
)
