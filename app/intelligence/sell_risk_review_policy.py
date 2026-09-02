"""Pure, read-only Sell/Risk evidence-review policy.

``SELL_RISK_REVIEW_POLICY / v1-research-shadow`` is intentionally narrower
than a sell-side evaluator.  It evaluates only already-classified canonical
facts supplied by an upstream boundary; it never reads a repository, parses
narrative text, derives adverse polarity, or produces an investment action.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime
from enum import StrEnum
import hashlib
import json

from app.domain.models import FreshnessStatus
from app.intelligence.external_intelligence import EventType, Materiality
from app.intelligence.unified_state import IntelligenceEvidenceAvailability
from app.reliability.models import ReliabilityStatus


SELL_RISK_REVIEW_POLICY_ID = "SELL_RISK_REVIEW_POLICY"
SELL_RISK_REVIEW_POLICY_VERSION = "v1-research-shadow"
SELL_RISK_REVIEW_SCHEMA_VERSION = "sell-risk-review/v1"
_PRIMARY_SOURCE_TYPES = frozenset({"OFFICIAL", "OFFICIAL_PRIMARY", "GOVERNMENT", "REGULATOR", "EXCHANGE"})


class SellRiskReviewPolicyError(ValueError):
    """Raised when a purported canonical policy input is malformed or tampered."""


class SellRiskReviewStatus(StrEnum):
    NO_QUALIFYING_RISK_EVIDENCE = "NO_QUALIFYING_RISK_EVIDENCE"
    PRIORITY_EVIDENCE_REVIEW = "PRIORITY_EVIDENCE_REVIEW"
    URGENT_EVIDENCE_REVIEW = "URGENT_EVIDENCE_REVIEW"
    CONFLICTED_EVIDENCE_REVIEW = "CONFLICTED_EVIDENCE_REVIEW"
    TECHNICAL_STRUCTURE_REVIEW = "TECHNICAL_STRUCTURE_REVIEW"
    MULTI_DOMAIN_EVIDENCE_REVIEW = "MULTI_DOMAIN_EVIDENCE_REVIEW"
    EVIDENCE_UNAVAILABLE = "EVIDENCE_UNAVAILABLE"


class SellRiskReviewActionability(StrEnum):
    WATCH_ONLY = "WATCH_ONLY"


class SellRiskReviewExecutionStatus(StrEnum):
    NON_EXECUTABLE = "NON_EXECUTABLE"


class AdverseEventClassification(StrEnum):
    """An upstream classification; this policy does not calculate it."""

    ADVERSE = "ADVERSE"


class CanonicalMappingStatus(StrEnum):
    VERIFIED_EXACT = "VERIFIED_EXACT"
    UNVERIFIED = "UNVERIFIED"
    FUZZY = "FUZZY"


class ResolutionAvailability(StrEnum):
    AVAILABLE = "AVAILABLE"
    RESOLUTION_UNAVAILABLE = "RESOLUTION_UNAVAILABLE"


@dataclass(frozen=True, slots=True)
class CanonicalAdverseEventEvidence:
    """Verified upstream event facts, without narrative interpretation.

    The class is a typed input boundary, not an external-intelligence adapter.
    ``adverse_classification`` and ``event_type`` must have been supplied by a
    separately approved canonical upstream contract.  Absent classifications
    deliberately make an event unusable rather than inviting an inference.
    """

    canonical_event_id: str
    evidence_version_id: str
    evidence_fingerprint: str
    canonical_instrument_id: str
    event_type: EventType | None
    adverse_classification: AdverseEventClassification | None
    materiality: Materiality | None
    primary_source_type: str | None
    mapping_status: CanonicalMappingStatus
    evidence_availability: IntelligenceEvidenceAvailability
    freshness_status: FreshnessStatus | None
    reliability_status: ReliabilityStatus | None
    conflict_detected: bool
    received_at: datetime | None
    available_at: datetime | None
    resolution_status: str | None = None
    resolution_lineage_id: str | None = None

    def __post_init__(self) -> None:
        _require_text(self.canonical_event_id, "SELL_RISK_EVENT_ID_REQUIRED")
        _require_text(self.evidence_version_id, "SELL_RISK_EVIDENCE_ID_REQUIRED")
        _require_fingerprint(self.evidence_fingerprint, "SELL_RISK_EVIDENCE_FINGERPRINT_REQUIRED")
        _require_text(self.canonical_instrument_id, "SELL_RISK_EVENT_INSTRUMENT_REQUIRED")
        _aware_or_none(self.received_at, "SELL_RISK_EVENT_RECEIVED_AT_INVALID")
        _aware_or_none(self.available_at, "SELL_RISK_EVENT_AVAILABLE_AT_INVALID")
        if self.available_at is not None and self.received_at is not None and self.available_at < self.received_at:
            raise SellRiskReviewPolicyError("SELL_RISK_EVENT_AVAILABLE_BEFORE_RECEIVED")
        if self.resolution_status is not None:
            _require_text(self.resolution_status, "SELL_RISK_EVENT_RESOLUTION_STATUS_INVALID")
            _require_text(self.resolution_lineage_id or "", "SELL_RISK_EVENT_RESOLUTION_LINEAGE_REQUIRED")
        elif self.resolution_lineage_id is not None:
            raise SellRiskReviewPolicyError("SELL_RISK_EVENT_RESOLUTION_LINEAGE_CONTRADICTION")
        if self.primary_source_type is not None and (
            self.primary_source_type != self.primary_source_type.strip()
            or self.primary_source_type != self.primary_source_type.upper()
        ):
            raise SellRiskReviewPolicyError("SELL_RISK_EVENT_SOURCE_NONCANONICAL")

    @property
    def identity_key(self) -> tuple[str, str, str]:
        return self.canonical_event_id, self.evidence_version_id, self.evidence_fingerprint


@dataclass(frozen=True, slots=True)
class Rule46ReviewContext:
    """Existing Rule 46 output retained as context, never recalculated here."""

    canonical_instrument_id: str
    diagnostic_result_id: str
    artifact_id: str
    artifact_fingerprint: str
    source_state: str
    triggered: bool
    evidence_availability: IntelligenceEvidenceAvailability
    freshness_status: FreshnessStatus | None
    available_at: datetime | None

    def __post_init__(self) -> None:
        _require_text(self.canonical_instrument_id, "SELL_RISK_RULE46_INSTRUMENT_REQUIRED")
        _require_text(self.diagnostic_result_id, "SELL_RISK_RULE46_DIAGNOSTIC_REQUIRED")
        _require_text(self.artifact_id, "SELL_RISK_RULE46_ARTIFACT_REQUIRED")
        _require_fingerprint(self.artifact_fingerprint, "SELL_RISK_RULE46_FINGERPRINT_REQUIRED")
        _require_text(self.source_state, "SELL_RISK_RULE46_STATE_REQUIRED")
        _aware_or_none(self.available_at, "SELL_RISK_RULE46_AVAILABLE_AT_INVALID")

    @property
    def identity_key(self) -> tuple[str, str, str, str]:
        return self.diagnostic_result_id, self.artifact_id, self.artifact_fingerprint, self.source_state


@dataclass(frozen=True, slots=True)
class SellRiskReviewInput:
    """PIT-bound, read-only inputs for one instrument and one evaluation time."""

    canonical_instrument_id: str
    evaluation_as_of: datetime
    external_evidence_availability: IntelligenceEvidenceAvailability
    events: tuple[CanonicalAdverseEventEvidence, ...]
    rule46_context: Rule46ReviewContext | None

    def __post_init__(self) -> None:
        _require_text(self.canonical_instrument_id, "SELL_RISK_INPUT_INSTRUMENT_REQUIRED")
        _aware(self.evaluation_as_of, "SELL_RISK_INPUT_AS_OF_REQUIRED")
        if self.events != _canonical_events(self.events):
            raise SellRiskReviewPolicyError("SELL_RISK_INPUT_EVENTS_NONCANONICAL")
        if self.rule46_context is not None and self.rule46_context.canonical_instrument_id != self.canonical_instrument_id:
            raise SellRiskReviewPolicyError("SELL_RISK_RULE46_INSTRUMENT_MISMATCH")

    @classmethod
    def create(
        cls,
        *,
        canonical_instrument_id: str,
        evaluation_as_of: datetime,
        external_evidence_availability: IntelligenceEvidenceAvailability,
        events: tuple[CanonicalAdverseEventEvidence, ...] = (),
        rule46_context: Rule46ReviewContext | None = None,
    ) -> "SellRiskReviewInput":
        return cls(
            canonical_instrument_id=canonical_instrument_id,
            evaluation_as_of=_utc(evaluation_as_of),
            external_evidence_availability=external_evidence_availability,
            events=_canonical_events(events),
            rule46_context=rule46_context,
        )


@dataclass(frozen=True, slots=True)
class SellRiskEventLineage:
    canonical_event_id: str
    evidence_version_id: str
    evidence_fingerprint: str
    event_type: str | None
    materiality: str | None
    conflict_detected: bool
    resolution_availability: ResolutionAvailability
    resolution_status: str | None
    resolution_lineage_id: str | None

    def __post_init__(self) -> None:
        _require_text(self.canonical_event_id, "SELL_RISK_LINEAGE_EVENT_REQUIRED")
        _require_text(self.evidence_version_id, "SELL_RISK_LINEAGE_EVIDENCE_REQUIRED")
        _require_fingerprint(self.evidence_fingerprint, "SELL_RISK_LINEAGE_FINGERPRINT_REQUIRED")
        if self.resolution_availability is ResolutionAvailability.AVAILABLE and (self.resolution_status is None or self.resolution_lineage_id is None):
            raise SellRiskReviewPolicyError("SELL_RISK_LINEAGE_RESOLUTION_REQUIRED")
        if self.resolution_availability is ResolutionAvailability.RESOLUTION_UNAVAILABLE and (self.resolution_status is not None or self.resolution_lineage_id is not None):
            raise SellRiskReviewPolicyError("SELL_RISK_LINEAGE_RESOLUTION_CONTRADICTION")


@dataclass(frozen=True, slots=True)
class SellRiskRule46Lineage:
    diagnostic_result_id: str
    artifact_id: str
    artifact_fingerprint: str
    source_state: str
    triggered: bool

    def __post_init__(self) -> None:
        _require_text(self.diagnostic_result_id, "SELL_RISK_RULE46_LINEAGE_DIAGNOSTIC_REQUIRED")
        _require_text(self.artifact_id, "SELL_RISK_RULE46_LINEAGE_ARTIFACT_REQUIRED")
        _require_fingerprint(self.artifact_fingerprint, "SELL_RISK_RULE46_LINEAGE_FINGERPRINT_REQUIRED")
        _require_text(self.source_state, "SELL_RISK_RULE46_LINEAGE_STATE_REQUIRED")


@dataclass(frozen=True, slots=True)
class SellRiskReview:
    """Immutable review result; it deliberately contains no action authority."""

    review_id: str
    canonical_instrument_id: str
    evaluation_as_of: datetime
    policy_id: str
    policy_version: str
    status: SellRiskReviewStatus
    external_evidence_availability: IntelligenceEvidenceAvailability
    actionability: SellRiskReviewActionability
    execution_status: SellRiskReviewExecutionStatus
    event_lineage: tuple[SellRiskEventLineage, ...]
    rule46_lineage: SellRiskRule46Lineage | None
    blocker_codes: tuple[str, ...]
    fingerprint: str

    def verify(self) -> None:
        _require_text(self.review_id, "SELL_RISK_REVIEW_ID_REQUIRED")
        _require_text(self.canonical_instrument_id, "SELL_RISK_REVIEW_INSTRUMENT_REQUIRED")
        _aware(self.evaluation_as_of, "SELL_RISK_REVIEW_AS_OF_REQUIRED")
        if self.policy_id != SELL_RISK_REVIEW_POLICY_ID or self.policy_version != SELL_RISK_REVIEW_POLICY_VERSION:
            raise SellRiskReviewPolicyError("SELL_RISK_REVIEW_POLICY_IDENTITY_INVALID")
        if self.actionability is not SellRiskReviewActionability.WATCH_ONLY:
            raise SellRiskReviewPolicyError("SELL_RISK_REVIEW_ACTIONABILITY_INVALID")
        if self.execution_status is not SellRiskReviewExecutionStatus.NON_EXECUTABLE:
            raise SellRiskReviewPolicyError("SELL_RISK_REVIEW_EXECUTION_STATUS_INVALID")
        if self.event_lineage != tuple(sorted(set(self.event_lineage), key=_lineage_key)):
            raise SellRiskReviewPolicyError("SELL_RISK_REVIEW_EVENT_LINEAGE_NONCANONICAL")
        if self.blocker_codes != tuple(sorted(set(self.blocker_codes))):
            raise SellRiskReviewPolicyError("SELL_RISK_REVIEW_BLOCKERS_NONCANONICAL")
        if self.status is SellRiskReviewStatus.EVIDENCE_UNAVAILABLE and not self.blocker_codes:
            raise SellRiskReviewPolicyError("SELL_RISK_REVIEW_UNAVAILABLE_BLOCKER_REQUIRED")
        if self.status is SellRiskReviewStatus.NO_QUALIFYING_RISK_EVIDENCE and self.blocker_codes:
            raise SellRiskReviewPolicyError("SELL_RISK_REVIEW_NO_EVIDENCE_BLOCKER_CONTRADICTION")
        conflict_present = (
            self.external_evidence_availability is IntelligenceEvidenceAvailability.CONFLICTED
            or any(item.conflict_detected for item in self.event_lineage)
        )
        if self.status is SellRiskReviewStatus.CONFLICTED_EVIDENCE_REVIEW and not conflict_present:
            raise SellRiskReviewPolicyError("SELL_RISK_REVIEW_CONFLICT_LINEAGE_REQUIRED")
        if self.status in {
            SellRiskReviewStatus.PRIORITY_EVIDENCE_REVIEW,
            SellRiskReviewStatus.URGENT_EVIDENCE_REVIEW,
            SellRiskReviewStatus.TECHNICAL_STRUCTURE_REVIEW,
            SellRiskReviewStatus.MULTI_DOMAIN_EVIDENCE_REVIEW,
            SellRiskReviewStatus.NO_QUALIFYING_RISK_EVIDENCE,
        } and conflict_present:
            raise SellRiskReviewPolicyError("SELL_RISK_REVIEW_CONFLICT_STATUS_CONTRADICTION")
        if self.status is SellRiskReviewStatus.TECHNICAL_STRUCTURE_REVIEW:
            if self.rule46_lineage is None or not self.rule46_lineage.triggered or self.event_lineage:
                raise SellRiskReviewPolicyError("SELL_RISK_REVIEW_TECHNICAL_CONTEXT_INVALID")
        if self.status is SellRiskReviewStatus.MULTI_DOMAIN_EVIDENCE_REVIEW:
            if self.rule46_lineage is None or not self.rule46_lineage.triggered or not self.event_lineage:
                raise SellRiskReviewPolicyError("SELL_RISK_REVIEW_MULTI_DOMAIN_CONTEXT_INVALID")
        if self.status in {SellRiskReviewStatus.PRIORITY_EVIDENCE_REVIEW, SellRiskReviewStatus.URGENT_EVIDENCE_REVIEW, SellRiskReviewStatus.CONFLICTED_EVIDENCE_REVIEW} and not self.event_lineage:
            raise SellRiskReviewPolicyError("SELL_RISK_REVIEW_EVENT_LINEAGE_REQUIRED")
        expected_id = _review_id(self)
        if self.review_id != expected_id:
            raise SellRiskReviewPolicyError("SELL_RISK_REVIEW_ID_MISMATCH")
        if self.fingerprint != _fingerprint(self):
            raise SellRiskReviewPolicyError("SELL_RISK_REVIEW_FINGERPRINT_MISMATCH")

    def serialize(self) -> str:
        """Stable, versioned, locale-independent serialization."""
        self.verify()
        return json.dumps(_full_payload(self), sort_keys=True, separators=(",", ":"))


def evaluate_sell_risk_review(value: SellRiskReviewInput) -> SellRiskReview:
    """Evaluate the approved V1 review boundary without side effects."""
    if not isinstance(value, SellRiskReviewInput):
        raise SellRiskReviewPolicyError("SELL_RISK_INPUT_REQUIRED")
    evaluation_as_of = _utc(value.evaluation_as_of)
    qualifying = tuple(item for item in value.events if _is_qualifying_event(item, evaluation_as_of))
    blockers = _input_blockers(value, evaluation_as_of, qualifying)
    event_lineage = _event_lineage(qualifying)
    rule46 = value.rule46_context
    technical_triggered = _rule46_triggered(rule46, value.canonical_instrument_id, evaluation_as_of)
    rule46_lineage = _rule46_lineage(rule46) if (
        rule46 is not None and _rule46_context_eligible(rule46, value.canonical_instrument_id, evaluation_as_of)
    ) else None

    if blockers:
        status = SellRiskReviewStatus.EVIDENCE_UNAVAILABLE
    elif (
        value.external_evidence_availability is IntelligenceEvidenceAvailability.CONFLICTED
        or any(
            item.conflict_detected
            or item.evidence_availability is IntelligenceEvidenceAvailability.CONFLICTED
            or item.reliability_status is ReliabilityStatus.CONFLICTED
            for item in qualifying
        )
    ):
        status = SellRiskReviewStatus.CONFLICTED_EVIDENCE_REVIEW
    elif qualifying and technical_triggered:
        status = SellRiskReviewStatus.MULTI_DOMAIN_EVIDENCE_REVIEW
    elif qualifying:
        status = _event_status(qualifying)
    elif technical_triggered:
        status = SellRiskReviewStatus.TECHNICAL_STRUCTURE_REVIEW
    else:
        status = SellRiskReviewStatus.NO_QUALIFYING_RISK_EVIDENCE

    provisional = SellRiskReview(
        review_id="", canonical_instrument_id=value.canonical_instrument_id,
        evaluation_as_of=evaluation_as_of, policy_id=SELL_RISK_REVIEW_POLICY_ID,
        policy_version=SELL_RISK_REVIEW_POLICY_VERSION, status=status,
        external_evidence_availability=value.external_evidence_availability,
        actionability=SellRiskReviewActionability.WATCH_ONLY,
        execution_status=SellRiskReviewExecutionStatus.NON_EXECUTABLE,
        event_lineage=event_lineage, rule46_lineage=rule46_lineage,
        blocker_codes=tuple(sorted(set(blockers))), fingerprint="",
    )
    review_id = _review_id(provisional)
    result = replace(provisional, review_id=review_id)
    result = replace(result, fingerprint=_fingerprint(result))
    result.verify()
    return result


def _input_blockers(
    value: SellRiskReviewInput,
    as_of: datetime,
    qualifying: tuple[CanonicalAdverseEventEvidence, ...],
) -> tuple[str, ...]:
    blockers: set[str] = set()
    if value.external_evidence_availability not in {
        IntelligenceEvidenceAvailability.AVAILABLE,
        IntelligenceEvidenceAvailability.CONFLICTED,
    }:
        blockers.add(f"EXTERNAL_EVIDENCE_{value.external_evidence_availability.value}")
    if value.rule46_context is None:
        blockers.add("RULE46_CONTEXT_MISSING")
    elif not _rule46_context_eligible(value.rule46_context, value.canonical_instrument_id, as_of):
        blockers.add("RULE46_CONTEXT_UNAVAILABLE")
    # Contextual secondary or irrelevant events must not suppress an otherwise
    # valid primary review.  They cannot create one themselves.  If no event
    # qualifies, malformed purported risk evidence fails closed instead.
    if qualifying or not value.events:
        return tuple(sorted(blockers))
    for event in value.events:
        if event.canonical_instrument_id != value.canonical_instrument_id:
            blockers.add("EVENT_INSTRUMENT_MISMATCH")
        if not _event_pit_eligible(event, as_of):
            blockers.add("EVENT_PIT_INELIGIBLE")
        if event.evidence_availability is not IntelligenceEvidenceAvailability.AVAILABLE and event.evidence_availability is not IntelligenceEvidenceAvailability.CONFLICTED:
            blockers.add(f"EVENT_AVAILABILITY_{event.evidence_availability.value}")
        if event.freshness_status is not FreshnessStatus.FRESH:
            blockers.add("EVENT_FRESHNESS_UNAVAILABLE")
        if event.reliability_status is not ReliabilityStatus.READY:
            blockers.add("EVENT_RELIABILITY_UNAVAILABLE")
        if event.mapping_status is not CanonicalMappingStatus.VERIFIED_EXACT:
            blockers.add("EVENT_MAPPING_UNVERIFIED")
        if event.primary_source_type is None or event.primary_source_type not in _PRIMARY_SOURCE_TYPES:
            blockers.add("EVENT_PRIMARY_SOURCE_UNVERIFIED")
        if event.adverse_classification is not AdverseEventClassification.ADVERSE:
            blockers.add("EVENT_ADVERSE_CLASSIFICATION_UNAVAILABLE")
        if event.event_type is None:
            blockers.add("EVENT_FAMILY_UNAVAILABLE")
        if event.materiality is None:
            blockers.add("EVENT_MATERIALITY_UNAVAILABLE")
    return tuple(sorted(blockers))


def _event_pit_eligible(value: CanonicalAdverseEventEvidence, as_of: datetime) -> bool:
    return (
        value.received_at is not None and value.available_at is not None
        and _utc(value.received_at) <= as_of and _utc(value.available_at) <= as_of
    )


def _is_qualifying_event(value: CanonicalAdverseEventEvidence, as_of: datetime) -> bool:
    return (
        _event_pit_eligible(value, as_of)
        and value.adverse_classification is AdverseEventClassification.ADVERSE
        and value.event_type is not None
        and value.materiality in {Materiality.HIGH, Materiality.CRITICAL}
        and value.mapping_status is CanonicalMappingStatus.VERIFIED_EXACT
        and value.primary_source_type is not None
        and value.primary_source_type in _PRIMARY_SOURCE_TYPES
        and value.freshness_status is FreshnessStatus.FRESH
        and value.reliability_status in {ReliabilityStatus.READY, ReliabilityStatus.CONFLICTED}
        and value.evidence_availability in {IntelligenceEvidenceAvailability.AVAILABLE, IntelligenceEvidenceAvailability.CONFLICTED}
    )


def _event_status(values: tuple[CanonicalAdverseEventEvidence, ...]) -> SellRiskReviewStatus:
    return (
        SellRiskReviewStatus.URGENT_EVIDENCE_REVIEW
        if any(item.materiality is Materiality.CRITICAL for item in values)
        else SellRiskReviewStatus.PRIORITY_EVIDENCE_REVIEW
    )


def _rule46_context_eligible(value: Rule46ReviewContext, instrument_id: str, as_of: datetime) -> bool:
    return (
        value.canonical_instrument_id == instrument_id
        and value.available_at is not None and _utc(value.available_at) <= as_of
        and value.evidence_availability is IntelligenceEvidenceAvailability.AVAILABLE
        and value.freshness_status is FreshnessStatus.FRESH
    )


def _rule46_triggered(value: Rule46ReviewContext | None, instrument_id: str, as_of: datetime) -> bool:
    return value is not None and _rule46_context_eligible(value, instrument_id, as_of) and value.triggered


def _event_lineage(values: tuple[CanonicalAdverseEventEvidence, ...]) -> tuple[SellRiskEventLineage, ...]:
    return tuple(sorted({
        SellRiskEventLineage(
            canonical_event_id=item.canonical_event_id,
            evidence_version_id=item.evidence_version_id,
            evidence_fingerprint=item.evidence_fingerprint,
            event_type=None if item.event_type is None else item.event_type.value,
            materiality=None if item.materiality is None else item.materiality.value,
            conflict_detected=(
                item.conflict_detected
                or item.evidence_availability is IntelligenceEvidenceAvailability.CONFLICTED
                or item.reliability_status is ReliabilityStatus.CONFLICTED
            ),
            resolution_availability=(
                ResolutionAvailability.AVAILABLE
                if item.resolution_status is not None else ResolutionAvailability.RESOLUTION_UNAVAILABLE
            ),
            resolution_status=item.resolution_status,
            resolution_lineage_id=item.resolution_lineage_id,
        ) for item in values
    }, key=_lineage_key))


def _rule46_lineage(value: Rule46ReviewContext | None) -> SellRiskRule46Lineage | None:
    if value is None:
        return None
    return SellRiskRule46Lineage(
        diagnostic_result_id=value.diagnostic_result_id, artifact_id=value.artifact_id,
        artifact_fingerprint=value.artifact_fingerprint, source_state=value.source_state,
        triggered=value.triggered,
    )


def _canonical_events(values: tuple[CanonicalAdverseEventEvidence, ...]) -> tuple[CanonicalAdverseEventEvidence, ...]:
    if not all(isinstance(item, CanonicalAdverseEventEvidence) for item in values):
        raise SellRiskReviewPolicyError("SELL_RISK_EVENT_TYPE_INVALID")
    grouped: dict[tuple[str, str, str], CanonicalAdverseEventEvidence] = {}
    for item in values:
        existing = grouped.get(item.identity_key)
        if existing is not None and existing != item:
            raise SellRiskReviewPolicyError("SELL_RISK_EVENT_LINEAGE_CONFLICT")
        grouped[item.identity_key] = item
    return tuple(sorted(grouped.values(), key=lambda item: item.identity_key))


def _lineage_key(value: SellRiskEventLineage) -> tuple[str, str, str]:
    return value.canonical_event_id, value.evidence_version_id, value.evidence_fingerprint


def _review_id(value: SellRiskReview) -> str:
    return "sell-risk-review:" + _digest(_identity_payload(value))[:24]


def _fingerprint(value: SellRiskReview) -> str:
    return "sha256:" + _digest(_full_payload(value))


def _digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _identity_payload(value: SellRiskReview) -> dict[str, object]:
    return {
        "schema_version": SELL_RISK_REVIEW_SCHEMA_VERSION,
        "policy_id": value.policy_id,
        "policy_version": value.policy_version,
        "canonical_instrument_id": value.canonical_instrument_id,
        "evaluation_as_of": _timestamp(value.evaluation_as_of),
        "external_evidence_availability": value.external_evidence_availability.value,
        "event_identity": tuple((item.canonical_event_id, item.evidence_version_id, item.evidence_fingerprint) for item in value.event_lineage),
        "rule46_identity": None if value.rule46_lineage is None else (
            value.rule46_lineage.diagnostic_result_id, value.rule46_lineage.artifact_id,
            value.rule46_lineage.artifact_fingerprint, value.rule46_lineage.source_state,
        ),
    }


def _full_payload(value: SellRiskReview) -> dict[str, object]:
    return {
        "schema_version": SELL_RISK_REVIEW_SCHEMA_VERSION,
        "review_id": value.review_id,
        "canonical_instrument_id": value.canonical_instrument_id,
        "evaluation_as_of": _timestamp(value.evaluation_as_of),
        "policy_id": value.policy_id,
        "policy_version": value.policy_version,
        "status": value.status.value,
        "external_evidence_availability": value.external_evidence_availability.value,
        "actionability": value.actionability.value,
        "execution_status": value.execution_status.value,
        "event_lineage": tuple({
            "canonical_event_id": item.canonical_event_id,
            "evidence_version_id": item.evidence_version_id,
            "evidence_fingerprint": item.evidence_fingerprint,
            "event_type": item.event_type,
            "materiality": item.materiality,
            "conflict_detected": item.conflict_detected,
            "resolution_availability": item.resolution_availability.value,
            "resolution_status": item.resolution_status,
            "resolution_lineage_id": item.resolution_lineage_id,
        } for item in value.event_lineage),
        "rule46_lineage": None if value.rule46_lineage is None else {
            "diagnostic_result_id": value.rule46_lineage.diagnostic_result_id,
            "artifact_id": value.rule46_lineage.artifact_id,
            "artifact_fingerprint": value.rule46_lineage.artifact_fingerprint,
            "source_state": value.rule46_lineage.source_state,
            "triggered": value.rule46_lineage.triggered,
        },
        "blocker_codes": value.blocker_codes,
    }


def _require_text(value: str, error_code: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise SellRiskReviewPolicyError(error_code)


def _require_fingerprint(value: str, error_code: str) -> None:
    if not isinstance(value, str) or not value.startswith("sha256:") or len(value) <= len("sha256:"):
        raise SellRiskReviewPolicyError(error_code)


def _aware(value: datetime, error_code: str) -> None:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise SellRiskReviewPolicyError(error_code)


def _aware_or_none(value: datetime | None, error_code: str) -> None:
    if value is not None:
        _aware(value, error_code)


def _utc(value: datetime) -> datetime:
    _aware(value, "SELL_RISK_TIMESTAMP_INVALID")
    return value.astimezone(UTC)


def _timestamp(value: datetime) -> str:
    return _utc(value).isoformat()


__all__ = (
    "AdverseEventClassification", "CanonicalAdverseEventEvidence", "CanonicalMappingStatus",
    "ResolutionAvailability", "Rule46ReviewContext", "SELL_RISK_REVIEW_POLICY_ID",
    "SELL_RISK_REVIEW_POLICY_VERSION", "SellRiskEventLineage", "SellRiskReview",
    "SellRiskReviewActionability", "SellRiskReviewExecutionStatus", "SellRiskReviewInput",
    "SellRiskReviewPolicyError", "SellRiskReviewStatus", "evaluate_sell_risk_review",
)
