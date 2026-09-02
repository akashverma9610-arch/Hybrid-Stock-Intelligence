"""Immutable P1A Watch-only HSISignal domain contract.

This module is intentionally a pure value contract.  It does not resolve a
strategy, project a Watch, read portfolio state, persist a record, or expose an
API.  Those boundaries require separately approved P1 slices.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum

from app.historical.guard import manifest_fingerprint
from app.intelligence.opportunity_archetypes import OpportunityArchetype


HSI_SIGNAL_CONTRACT = "hsi-signal/watch-only/v1"
_IDENTIFIER = re.compile(r"[A-Za-z0-9._:-]+")
_FINGERPRINT = re.compile(r"(?:sha256:)?[0-9a-f]{64}")


class HSISignalError(ValueError):
    """Raised when a Watch-only signal violates its immutable contract."""


class ValueAvailability(StrEnum):
    AVAILABLE = "AVAILABLE"
    UNAVAILABLE = "UNAVAILABLE"


class DetectionTimeStatus(StrEnum):
    AVAILABLE = "AVAILABLE"
    DETECTION_TIME_UNAVAILABLE = "DETECTION_TIME_UNAVAILABLE"


class LineageAvailability(StrEnum):
    PRESENT = "PRESENT"
    SOURCE_EMPTY = "SOURCE_EMPTY"


class StrategyResolutionStatus(StrEnum):
    RESOLVED = "RESOLVED"
    STRATEGY_UNAVAILABLE = "STRATEGY_UNAVAILABLE"


class HSISignalActionability(StrEnum):
    WATCH_ONLY = "WATCH_ONLY"


class HSISignalExecutionStatus(StrEnum):
    NON_EXECUTABLE = "NON_EXECUTABLE"


class PortfolioRelevance(StrEnum):
    NOT_EVALUATED = "NOT_EVALUATED"


class P1UnavailableReason(StrEnum):
    DETECTION_TIME_UNAVAILABLE = "DETECTION_TIME_UNAVAILABLE"
    HORIZON_UNAVAILABLE = "HORIZON_UNAVAILABLE"
    DIRECTION_UNAVAILABLE = "DIRECTION_UNAVAILABLE"
    STRENGTH_UNAVAILABLE = "STRENGTH_UNAVAILABLE"
    CONFIDENCE_UNAVAILABLE = "CONFIDENCE_UNAVAILABLE"
    MATERIALITY_UNAVAILABLE = "MATERIALITY_UNAVAILABLE"
    EXPIRY_POLICY_UNAVAILABLE = "EXPIRY_POLICY_UNAVAILABLE"


@dataclass(frozen=True, slots=True)
class StrategyResolutionReference:
    """Provenance-only result for a future read-only registry lookup."""

    status: StrategyResolutionStatus
    policy_id: str | None = None
    policy_version: str | None = None
    approval_id: str | None = None
    selection_id: str | None = None
    policy_fingerprint: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.status, StrategyResolutionStatus):
            raise HSISignalError("HSI_SIGNAL_STRATEGY_RESOLUTION_STATUS_INVALID")
        references = (
            self.policy_id, self.policy_version, self.approval_id,
            self.selection_id, self.policy_fingerprint,
        )
        if self.status is StrategyResolutionStatus.RESOLVED:
            if not all(references):
                raise HSISignalError("HSI_SIGNAL_STRATEGY_RESOLUTION_PROVENANCE_REQUIRED")
            for item in references[:-1]:
                _require_identifier(item, "HSI_SIGNAL_STRATEGY_RESOLUTION_PROVENANCE_INVALID")
            _require_fingerprint(self.policy_fingerprint, "HSI_SIGNAL_STRATEGY_RESOLUTION_FINGERPRINT_INVALID")
        elif any(references):
            raise HSISignalError("HSI_SIGNAL_STRATEGY_UNAVAILABLE_REFERENCE_FORBIDDEN")


@dataclass(frozen=True, slots=True)
class DiagnosticLineageReference:
    rule_id: str
    diagnostic_result_id: str
    artifact_id: str
    artifact_fingerprint: str

    def __post_init__(self) -> None:
        if not all((self.rule_id, self.diagnostic_result_id, self.artifact_id, self.artifact_fingerprint)):
            raise HSISignalError("HSI_SIGNAL_DIAGNOSTIC_LINEAGE_REQUIRED")
        for item in (self.rule_id, self.diagnostic_result_id, self.artifact_id):
            _require_identifier(item, "HSI_SIGNAL_DIAGNOSTIC_LINEAGE_IDENTITY_INVALID")
        _require_fingerprint(self.artifact_fingerprint, "HSI_SIGNAL_DIAGNOSTIC_LINEAGE_FINGERPRINT_INVALID")


@dataclass(frozen=True, slots=True)
class EvidenceLineageReference:
    canonical_event_id: str
    evidence_version_id: str
    evidence_fingerprint: str

    def __post_init__(self) -> None:
        if not all((self.canonical_event_id, self.evidence_version_id, self.evidence_fingerprint)):
            raise HSISignalError("HSI_SIGNAL_EVIDENCE_LINEAGE_REQUIRED")
        for item in (self.canonical_event_id, self.evidence_version_id):
            _require_identifier(item, "HSI_SIGNAL_EVIDENCE_LINEAGE_IDENTITY_INVALID")
        _require_fingerprint(self.evidence_fingerprint, "HSI_SIGNAL_EVIDENCE_LINEAGE_FINGERPRINT_INVALID")


@dataclass(frozen=True, slots=True)
class HSISignal:
    """Deterministic, immutable, non-executable P1 Watch projection contract."""

    canonical_instrument_id: str
    watch_id: str
    watch_fingerprint: str
    watch_as_of: datetime
    detected_at: datetime | None
    detection_time_status: DetectionTimeStatus
    archetype: OpportunityArchetype
    routing_policy_version: str
    horizon: str | None
    horizon_availability: ValueAvailability
    horizon_routing_evidence_ref: str | None
    direction: str | None
    direction_availability: ValueAvailability
    direction_routing_evidence_ref: str | None
    strategy_resolution: StrategyResolutionReference
    diagnostic_lineage: tuple[DiagnosticLineageReference, ...]
    diagnostic_lineage_availability: LineageAvailability
    evidence_lineage: tuple[EvidenceLineageReference, ...]
    evidence_lineage_availability: LineageAvailability
    source_watch_status: str
    source_lifecycle_flags: tuple[str, ...]
    blocker_codes: tuple[str, ...] = ()
    schema_version: str = HSI_SIGNAL_CONTRACT
    signal_id: str = field(init=False)
    actionability: HSISignalActionability = field(default=HSISignalActionability.WATCH_ONLY, init=False)
    execution_status: HSISignalExecutionStatus = field(default=HSISignalExecutionStatus.NON_EXECUTABLE, init=False)
    portfolio_relevance: PortfolioRelevance = field(default=PortfolioRelevance.NOT_EVALUATED, init=False)
    strength: None = field(default=None, init=False)
    strength_availability: ValueAvailability = field(default=ValueAvailability.UNAVAILABLE, init=False)
    confidence: None = field(default=None, init=False)
    confidence_availability: ValueAvailability = field(default=ValueAvailability.UNAVAILABLE, init=False)
    materiality: None = field(default=None, init=False)
    materiality_availability: ValueAvailability = field(default=ValueAvailability.UNAVAILABLE, init=False)
    expires_at: None = field(default=None, init=False)
    expiry_availability: ValueAvailability = field(default=ValueAvailability.UNAVAILABLE, init=False)
    unavailable_reasons: tuple[P1UnavailableReason, ...] = field(init=False)
    fingerprint: str = field(init=False)

    @classmethod
    def create(
        cls,
        *,
        canonical_instrument_id: str,
        watch_id: str,
        watch_fingerprint: str,
        watch_as_of: datetime,
        detected_at: datetime | None,
        detection_time_status: DetectionTimeStatus,
        archetype: OpportunityArchetype,
        routing_policy_version: str,
        horizon: str | None,
        horizon_availability: ValueAvailability,
        horizon_routing_evidence_ref: str | None,
        direction: str | None,
        direction_availability: ValueAvailability,
        direction_routing_evidence_ref: str | None,
        strategy_resolution: StrategyResolutionReference,
        diagnostic_lineage: tuple[DiagnosticLineageReference, ...],
        diagnostic_lineage_availability: LineageAvailability,
        evidence_lineage: tuple[EvidenceLineageReference, ...],
        evidence_lineage_availability: LineageAvailability,
        source_watch_status: str,
        source_lifecycle_flags: tuple[str, ...],
        blocker_codes: tuple[str, ...] = (),
    ) -> "HSISignal":
        return cls(
            canonical_instrument_id=canonical_instrument_id,
            watch_id=watch_id,
            watch_fingerprint=watch_fingerprint,
            watch_as_of=watch_as_of,
            detected_at=detected_at,
            detection_time_status=detection_time_status,
            archetype=archetype,
            routing_policy_version=routing_policy_version,
            horizon=horizon,
            horizon_availability=horizon_availability,
            horizon_routing_evidence_ref=horizon_routing_evidence_ref,
            direction=direction,
            direction_availability=direction_availability,
            direction_routing_evidence_ref=direction_routing_evidence_ref,
            strategy_resolution=strategy_resolution,
            diagnostic_lineage=_canonical_diagnostic_lineage(diagnostic_lineage, diagnostic_lineage_availability),
            diagnostic_lineage_availability=diagnostic_lineage_availability,
            evidence_lineage=_canonical_evidence_lineage(evidence_lineage, evidence_lineage_availability),
            evidence_lineage_availability=evidence_lineage_availability,
            source_watch_status=source_watch_status,
            source_lifecycle_flags=_unique_preserved(source_lifecycle_flags, "HSI_SIGNAL_SOURCE_LIFECYCLE_FLAGS_DUPLICATE"),
            blocker_codes=_canonical_strings(blocker_codes, "HSI_SIGNAL_BLOCKERS_DUPLICATE"),
        )

    def __post_init__(self) -> None:
        _validate_contract(self)
        unavailable_reasons = _unavailable_reasons(self)
        object.__setattr__(self, "unavailable_reasons", unavailable_reasons)
        signal_id = f"hsi-signal:{manifest_fingerprint(**_identity_values(self))[:32]}"
        object.__setattr__(self, "signal_id", signal_id)
        object.__setattr__(self, "fingerprint", manifest_fingerprint(**_fingerprint_values(self)))

    def verify(self) -> None:
        """Reject mutations rather than repairing immutable derived values."""
        _validate_contract(self)
        if self.unavailable_reasons != _unavailable_reasons(self):
            raise HSISignalError("HSI_SIGNAL_UNAVAILABLE_REASONS_MISMATCH")
        expected_signal_id = f"hsi-signal:{manifest_fingerprint(**_identity_values(self))[:32]}"
        if self.signal_id != expected_signal_id:
            raise HSISignalError("HSI_SIGNAL_IDENTITY_MISMATCH")
        if self.fingerprint != manifest_fingerprint(**_fingerprint_values(self)):
            raise HSISignalError("HSI_SIGNAL_FINGERPRINT_MISMATCH")


def _validate_contract(value: HSISignal) -> None:
    if value.schema_version != HSI_SIGNAL_CONTRACT:
        raise HSISignalError("HSI_SIGNAL_SCHEMA_VERSION_INVALID")
    if not all((
        isinstance(value.detection_time_status, DetectionTimeStatus),
        isinstance(value.horizon_availability, ValueAvailability),
        isinstance(value.direction_availability, ValueAvailability),
        isinstance(value.archetype, OpportunityArchetype),
        isinstance(value.strategy_resolution, StrategyResolutionReference),
        isinstance(value.diagnostic_lineage_availability, LineageAvailability),
        isinstance(value.evidence_lineage_availability, LineageAvailability),
    )):
        raise HSISignalError("HSI_SIGNAL_ENUM_OR_REFERENCE_INVALID")
    if not all((
        value.canonical_instrument_id, value.watch_id, value.watch_fingerprint,
        value.routing_policy_version, value.source_watch_status,
    )):
        raise HSISignalError("HSI_SIGNAL_IDENTITY_REQUIRED")
    for item in (value.canonical_instrument_id, value.watch_id, value.source_watch_status):
        _require_identifier(item, "HSI_SIGNAL_IDENTITY_INVALID")
    _require_text(value.routing_policy_version, "HSI_SIGNAL_ROUTING_POLICY_VERSION_INVALID")
    _require_fingerprint(value.watch_fingerprint, "HSI_SIGNAL_WATCH_FINGERPRINT_INVALID")
    _require_aware(value.watch_as_of, "HSI_SIGNAL_WATCH_AS_OF_REQUIRED")
    _validate_detection_time(value)
    _validate_supported_value(
        value.horizon, value.horizon_availability,
        value.horizon_routing_evidence_ref, "HORIZON",
    )
    _validate_supported_value(
        value.direction, value.direction_availability,
        value.direction_routing_evidence_ref, "DIRECTION",
    )
    _validate_lineage(
        value.diagnostic_lineage, value.diagnostic_lineage_availability,
        _diagnostic_lineage_key, "DIAGNOSTIC",
    )
    _validate_lineage(
        value.evidence_lineage, value.evidence_lineage_availability,
        _evidence_lineage_key, "EVIDENCE",
    )
    if not value.diagnostic_lineage and not value.evidence_lineage:
        raise HSISignalError("HSI_SIGNAL_LINEAGE_REQUIRED")
    if value.source_lifecycle_flags != tuple(dict.fromkeys(value.source_lifecycle_flags)):
        raise HSISignalError("HSI_SIGNAL_SOURCE_LIFECYCLE_FLAGS_NONCANONICAL")
    if any(not isinstance(item, str) or not _IDENTIFIER.fullmatch(item) for item in value.source_lifecycle_flags):
        raise HSISignalError("HSI_SIGNAL_SOURCE_LIFECYCLE_FLAGS_INVALID")
    if value.blocker_codes != tuple(sorted(set(value.blocker_codes))):
        raise HSISignalError("HSI_SIGNAL_BLOCKERS_NONCANONICAL")
    if any(not isinstance(item, str) or not _IDENTIFIER.fullmatch(item) for item in value.blocker_codes):
        raise HSISignalError("HSI_SIGNAL_BLOCKERS_INVALID")
    if (
        value.actionability is not HSISignalActionability.WATCH_ONLY
        or value.execution_status is not HSISignalExecutionStatus.NON_EXECUTABLE
        or value.portfolio_relevance is not PortfolioRelevance.NOT_EVALUATED
        or value.strength is not None or value.confidence is not None or value.materiality is not None
        or value.expires_at is not None
        or value.strength_availability is not ValueAvailability.UNAVAILABLE
        or value.confidence_availability is not ValueAvailability.UNAVAILABLE
        or value.materiality_availability is not ValueAvailability.UNAVAILABLE
        or value.expiry_availability is not ValueAvailability.UNAVAILABLE
    ):
        raise HSISignalError("HSI_SIGNAL_FIXED_P1_STATE_INVALID")


def hsi_signal_payload(value: HSISignal) -> dict[str, object]:
    """Return a deterministic, JSON-safe value payload without any runtime data."""
    if not isinstance(value, HSISignal):
        raise HSISignalError("HSI_SIGNAL_VALUE_REQUIRED")
    value.verify()
    return _fingerprint_values(value) | {"fingerprint": value.fingerprint}


def serialize_hsi_signal(value: HSISignal) -> str:
    """Stable serialization for domain tests and future read-only consumers."""
    return json.dumps(hsi_signal_payload(value), sort_keys=True, ensure_ascii=True, separators=(",", ":"))


def _require_aware(value: datetime, code: str) -> None:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise HSISignalError(code)


def _canonical_timestamp(value: datetime) -> str:
    _require_aware(value, "HSI_SIGNAL_TIMESTAMP_REQUIRED")
    return value.astimezone(UTC).isoformat()


def _require_identifier(value: str | None, code: str) -> None:
    if not isinstance(value, str) or not _IDENTIFIER.fullmatch(value):
        raise HSISignalError(code)


def _require_text(value: str | None, code: str) -> None:
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise HSISignalError(code)


def _require_fingerprint(value: str | None, code: str) -> None:
    if not isinstance(value, str) or not _FINGERPRINT.fullmatch(value):
        raise HSISignalError(code)


def _validate_detection_time(value: HSISignal) -> None:
    if value.detection_time_status is DetectionTimeStatus.AVAILABLE:
        if value.detected_at is None:
            raise HSISignalError("HSI_SIGNAL_DETECTION_TIME_REQUIRED")
        _require_aware(value.detected_at, "HSI_SIGNAL_DETECTION_TIME_REQUIRED")
        if value.detected_at > value.watch_as_of:
            raise HSISignalError("HSI_SIGNAL_DETECTION_TIME_AFTER_WATCH_AS_OF")
    elif value.detected_at is not None:
        raise HSISignalError("HSI_SIGNAL_DETECTION_TIME_UNAVAILABLE_REQUIRED")


def _validate_supported_value(value: str | None, availability: ValueAvailability,
                              evidence_reference: str | None, label: str) -> None:
    if availability is ValueAvailability.AVAILABLE:
        if not value or not evidence_reference:
            raise HSISignalError(f"HSI_SIGNAL_{label}_ROUTING_EVIDENCE_REQUIRED")
        _require_text(value, f"HSI_SIGNAL_{label}_VALUE_INVALID")
        _require_identifier(evidence_reference, f"HSI_SIGNAL_{label}_ROUTING_EVIDENCE_INVALID")
    elif value is not None or evidence_reference is not None:
        raise HSISignalError(f"HSI_SIGNAL_{label}_UNAVAILABLE_REQUIRED")


def _validate_lineage(values: tuple[object, ...], availability: LineageAvailability,
                      key, label: str, *, require_canonical_order: bool = True) -> None:
    expected_type = DiagnosticLineageReference if label == "DIAGNOSTIC" else EvidenceLineageReference
    if any(not isinstance(value, expected_type) for value in values):
        raise HSISignalError(f"HSI_SIGNAL_{label}_LINEAGE_REFERENCE_INVALID")
    if len(set(values)) != len(values):
        raise HSISignalError(f"HSI_SIGNAL_{label}_LINEAGE_DUPLICATE")
    identities = (
        tuple(value.rule_id for value in values)
        if label == "DIAGNOSTIC"
        else tuple((value.canonical_event_id, value.evidence_version_id) for value in values)
    )
    if len(set(identities)) != len(identities):
        raise HSISignalError(f"HSI_SIGNAL_{label}_LINEAGE_CONFLICT")
    if values:
        if availability is not LineageAvailability.PRESENT:
            raise HSISignalError(f"HSI_SIGNAL_{label}_LINEAGE_AVAILABILITY_INVALID")
        if require_canonical_order and values != tuple(sorted(values, key=key)):
            raise HSISignalError(f"HSI_SIGNAL_{label}_LINEAGE_NONCANONICAL")
    elif availability is not LineageAvailability.SOURCE_EMPTY:
        raise HSISignalError(f"HSI_SIGNAL_{label}_LINEAGE_EMPTY_UNEXPLAINED")


def _unavailable_reasons(value: HSISignal) -> tuple[P1UnavailableReason, ...]:
    reasons = {
        P1UnavailableReason.STRENGTH_UNAVAILABLE,
        P1UnavailableReason.CONFIDENCE_UNAVAILABLE,
        P1UnavailableReason.MATERIALITY_UNAVAILABLE,
        P1UnavailableReason.EXPIRY_POLICY_UNAVAILABLE,
    }
    if value.detection_time_status is DetectionTimeStatus.DETECTION_TIME_UNAVAILABLE:
        reasons.add(P1UnavailableReason.DETECTION_TIME_UNAVAILABLE)
    if value.horizon_availability is ValueAvailability.UNAVAILABLE:
        reasons.add(P1UnavailableReason.HORIZON_UNAVAILABLE)
    if value.direction_availability is ValueAvailability.UNAVAILABLE:
        reasons.add(P1UnavailableReason.DIRECTION_UNAVAILABLE)
    return tuple(sorted(reasons, key=lambda item: item.value))


def _diagnostic_lineage_key(value: DiagnosticLineageReference) -> tuple[str, str, str, str]:
    return value.rule_id, value.diagnostic_result_id, value.artifact_id, value.artifact_fingerprint


def _evidence_lineage_key(value: EvidenceLineageReference) -> tuple[str, str, str]:
    return value.canonical_event_id, value.evidence_version_id, value.evidence_fingerprint


def _identity_values(value: HSISignal) -> dict[str, object]:
    return {
        "canonical_instrument_id": value.canonical_instrument_id,
        "watch_id": value.watch_id,
        "watch_fingerprint": value.watch_fingerprint,
        "watch_as_of": _canonical_timestamp(value.watch_as_of),
        "detected_at": None if value.detected_at is None else _canonical_timestamp(value.detected_at),
        "detection_time_status": value.detection_time_status.value,
        "archetype": value.archetype.value,
        "routing_policy_version": value.routing_policy_version,
        "horizon": value.horizon,
        "horizon_availability": value.horizon_availability.value,
        "horizon_routing_evidence_ref": value.horizon_routing_evidence_ref,
        "direction": value.direction,
        "direction_availability": value.direction_availability.value,
        "direction_routing_evidence_ref": value.direction_routing_evidence_ref,
        "strategy_resolution": _strategy_resolution_payload(value.strategy_resolution),
        "diagnostic_lineage_availability": value.diagnostic_lineage_availability.value,
        "diagnostic_lineage": [_diagnostic_lineage_payload(item) for item in value.diagnostic_lineage],
        "evidence_lineage_availability": value.evidence_lineage_availability.value,
        "evidence_lineage": [_evidence_lineage_payload(item) for item in value.evidence_lineage],
        "projection_contract": value.schema_version,
    }


def _fingerprint_values(value: HSISignal) -> dict[str, object]:
    return {
        **_identity_values(value),
        "signal_id": value.signal_id,
        "source_watch_status": value.source_watch_status,
        "source_lifecycle_flags": list(value.source_lifecycle_flags),
        "blocker_codes": list(value.blocker_codes),
        "actionability": value.actionability.value,
        "execution_status": value.execution_status.value,
        "portfolio_relevance": value.portfolio_relevance.value,
        "strength": value.strength,
        "strength_availability": value.strength_availability.value,
        "confidence": value.confidence,
        "confidence_availability": value.confidence_availability.value,
        "materiality": value.materiality,
        "materiality_availability": value.materiality_availability.value,
        "expires_at": value.expires_at,
        "expiry_availability": value.expiry_availability.value,
        "unavailable_reasons": [item.value for item in value.unavailable_reasons],
        "schema_version": value.schema_version,
    }


def _canonical_diagnostic_lineage(
        values: tuple[DiagnosticLineageReference, ...], availability: LineageAvailability,
) -> tuple[DiagnosticLineageReference, ...]:
    ordered = tuple(values)
    _validate_lineage(
        ordered, availability, _diagnostic_lineage_key, "DIAGNOSTIC",
        require_canonical_order=False,
    )
    return tuple(sorted(ordered, key=_diagnostic_lineage_key))


def _canonical_evidence_lineage(
        values: tuple[EvidenceLineageReference, ...], availability: LineageAvailability,
) -> tuple[EvidenceLineageReference, ...]:
    ordered = tuple(values)
    _validate_lineage(
        ordered, availability, _evidence_lineage_key, "EVIDENCE",
        require_canonical_order=False,
    )
    return tuple(sorted(ordered, key=_evidence_lineage_key))


def _canonical_strings(values: tuple[str, ...], duplicate_code: str) -> tuple[str, ...]:
    ordered = tuple(values)
    if any(not isinstance(value, str) or not _IDENTIFIER.fullmatch(value) for value in ordered):
        raise HSISignalError(duplicate_code.removesuffix("_DUPLICATE") + "_INVALID")
    if len(set(ordered)) != len(ordered):
        raise HSISignalError(duplicate_code)
    return tuple(sorted(ordered))


def _unique_preserved(values: tuple[str, ...], duplicate_code: str) -> tuple[str, ...]:
    ordered = tuple(values)
    if any(not isinstance(value, str) or not _IDENTIFIER.fullmatch(value) for value in ordered):
        raise HSISignalError(duplicate_code.removesuffix("_DUPLICATE") + "_INVALID")
    if len(set(ordered)) != len(ordered):
        raise HSISignalError(duplicate_code)
    return ordered


def _strategy_resolution_payload(value: StrategyResolutionReference) -> dict[str, object]:
    return {
        "status": value.status.value,
        "policy_id": value.policy_id,
        "policy_version": value.policy_version,
        "approval_id": value.approval_id,
        "selection_id": value.selection_id,
        "policy_fingerprint": value.policy_fingerprint,
    }


def _diagnostic_lineage_payload(value: DiagnosticLineageReference) -> dict[str, str]:
    return {
        "rule_id": value.rule_id,
        "diagnostic_result_id": value.diagnostic_result_id,
        "artifact_id": value.artifact_id,
        "artifact_fingerprint": value.artifact_fingerprint,
    }


def _evidence_lineage_payload(value: EvidenceLineageReference) -> dict[str, str]:
    return {
        "canonical_event_id": value.canonical_event_id,
        "evidence_version_id": value.evidence_version_id,
        "evidence_fingerprint": value.evidence_fingerprint,
    }


__all__ = (
    "HSI_SIGNAL_CONTRACT", "DetectionTimeStatus", "DiagnosticLineageReference",
    "EvidenceLineageReference", "HSISignal", "HSISignalActionability",
    "HSISignalError", "HSISignalExecutionStatus", "LineageAvailability",
    "P1UnavailableReason", "PortfolioRelevance", "StrategyResolutionReference",
    "StrategyResolutionStatus", "ValueAvailability", "hsi_signal_payload",
    "serialize_hsi_signal",
)
