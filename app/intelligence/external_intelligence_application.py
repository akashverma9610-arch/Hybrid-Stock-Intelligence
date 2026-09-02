"""PIT-safe application composition for immutable external intelligence."""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime
from enum import StrEnum
from typing import Callable

from app.intelligence.external_intelligence import (
    CompanyExposure,
    DataPoint,
    EvidenceVersion,
    ExternalEvent,
    Fact,
    IdentityDisposition,
    Inference,
    Interpretation,
    ReevaluationRequest,
    SourceEvidence,
    classify,
)
from app.storage.sqlite_external_intelligence_repository import SQLiteExternalIntelligenceRepository


class ExternalIntelligenceApplicationDisposition(StrEnum):
    ACCEPTED_NEW = "ACCEPTED_NEW"
    ACCEPTED_EXISTING = "ACCEPTED_EXISTING"
    ACCEPTED_NEW_EVIDENCE = "ACCEPTED_NEW_EVIDENCE"
    REJECTED_CONFLICT = "REJECTED_CONFLICT"


@dataclass(frozen=True, slots=True)
class ExternalIntelligenceRecordCommand:
    """Typed input without a producer-controlled HSI received timestamp.

    Canonical-instrument validation belongs to the future authenticated command
    mapper (V1C).  This service therefore accepts typed V1B1 exposures and
    only carries already-verified canonical IDs into a reevaluation request.
    """

    event: ExternalEvent
    published_at: datetime
    discovered_at: datetime
    summary: str
    what_changed: str
    primary_source: SourceEvidence
    facts: tuple[Fact, ...] = ()
    data_points: tuple[DataPoint, ...] = ()
    interpretation: tuple[Interpretation, ...] = ()
    inferences: tuple[Inference, ...] = ()
    company_exposures: tuple[CompanyExposure, ...] = ()
    supporting_sources: tuple[SourceEvidence, ...] = ()
    event_confidence: float | None = None
    exposure_confidence: float | None = None
    time_horizon: str | None = None
    risks: tuple[str, ...] = ()
    counter_evidence: tuple[str, ...] = ()
    why_hsi_should_care: str | None = None
    effective_at: datetime | None = None
    affected_sectors: tuple[str, ...] = ()
    affected_industries: tuple[str, ...] = ()
    requires_hsi_analysis: bool = False


@dataclass(frozen=True, slots=True)
class ExternalIntelligenceApplicationReceipt:
    disposition: ExternalIntelligenceApplicationDisposition
    canonical_event_id: str
    evidence_version_id: str | None
    reevaluation_requested: bool
    reevaluation_request_id: str | None
    received_at: datetime
    event_fingerprint: str
    evidence_fingerprint: str | None
    blocker: str | None = None


class ExternalIntelligenceApplicationService:
    """Coordinates immutable V1B1 contracts and V1B2 storage; no transport work."""

    def __init__(
        self, repository: SQLiteExternalIntelligenceRepository,
        *, clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._clock = clock or (lambda: datetime.now(UTC))

    def record_event(self, command: ExternalIntelligenceRecordCommand) -> ExternalIntelligenceApplicationReceipt:
        received_at = self._received_at()
        incoming_event = replace(command.event, first_received_at=received_at)
        existing_event = self._repository.get_event_by_producer_identity(
            incoming_event.producer_id, incoming_event.producer_event_id,
        )
        if existing_event is not None and existing_event.fingerprint != incoming_event.fingerprint:
            return ExternalIntelligenceApplicationReceipt(
                ExternalIntelligenceApplicationDisposition.REJECTED_CONFLICT,
                existing_event.canonical_event_id, None, False, None, received_at,
                incoming_event.fingerprint, None,
                "Producer event identity maps to an incompatible canonical event.",
            )

        event = existing_event or incoming_event
        candidate_evidence = self._evidence_from(command, event, received_at)
        existing_evidence = self._repository.get_evidence_version(candidate_evidence.evidence_version_id)
        identity = classify(
            existing_event,
            "" if existing_evidence is not None else candidate_evidence.fingerprint,
            incoming_event,
        )
        if identity is IdentityDisposition.CONFLICTING_EVENT_IDENTITY:
            return ExternalIntelligenceApplicationReceipt(
                ExternalIntelligenceApplicationDisposition.REJECTED_CONFLICT,
                event.canonical_event_id, None, False, None, received_at,
                incoming_event.fingerprint, None,
                "Producer event identity maps to an incompatible canonical event.",
            )

        evidence = existing_evidence or candidate_evidence
        request = self._request_from(command, event, evidence, received_at) if command.requires_hsi_analysis else None
        existing_request = self._repository.get_reevaluation_request(request.request_id) if request is not None else None

        with self._repository.transaction():
            if existing_event is None:
                event = self._repository.save_event(event)
            if existing_evidence is None:
                evidence = self._repository.save_evidence_version(evidence)
            if request is not None and existing_request is None:
                request = self._repository.save_reevaluation_request(request)
            elif existing_request is not None:
                request = existing_request

        disposition = (
            ExternalIntelligenceApplicationDisposition.ACCEPTED_NEW
            if existing_event is None else
            ExternalIntelligenceApplicationDisposition.ACCEPTED_EXISTING
            if existing_evidence is not None else
            ExternalIntelligenceApplicationDisposition.ACCEPTED_NEW_EVIDENCE
        )
        return ExternalIntelligenceApplicationReceipt(
            disposition, event.canonical_event_id, evidence.evidence_version_id,
            request is not None, request.request_id if request is not None else None,
            evidence.received_at, event.fingerprint, evidence.fingerprint,
        )

    def get_event(self, canonical_event_id: str) -> ExternalEvent | None:
        return self._repository.get_event(canonical_event_id)

    def get_event_by_producer_identity(self, producer_id: str, producer_event_id: str) -> ExternalEvent | None:
        return self._repository.get_event_by_producer_identity(producer_id, producer_event_id)

    def list_evidence_versions(self, canonical_event_id: str) -> tuple[EvidenceVersion, ...]:
        return self._repository.list_evidence_versions(canonical_event_id)

    def list_evidence_visible_as_of(
        self, canonical_event_id: str, intelligence_as_of: datetime,
    ) -> tuple[EvidenceVersion, ...]:
        as_of = _utc_timestamp(intelligence_as_of)
        return tuple(
            item for item in self._repository.list_evidence_versions(canonical_event_id)
            if item.received_at <= as_of
        )

    def latest_evidence_as_of(self, canonical_event_id: str, intelligence_as_of: datetime) -> EvidenceVersion | None:
        visible = self.list_evidence_visible_as_of(canonical_event_id, intelligence_as_of)
        return visible[-1] if visible else None

    def list_reevaluation_requests(
        self, *, canonical_event_id: str | None = None, evidence_version_id: str | None = None,
    ) -> tuple[ReevaluationRequest, ...]:
        return self._repository.list_reevaluation_requests(
            canonical_event_id=canonical_event_id, evidence_version_id=evidence_version_id,
        )

    def _received_at(self) -> datetime:
        return _utc_timestamp(self._clock())

    @staticmethod
    def _evidence_from(
        command: ExternalIntelligenceRecordCommand, event: ExternalEvent, received_at: datetime,
    ) -> EvidenceVersion:
        return EvidenceVersion(
            event, received_at, command.published_at, command.discovered_at,
            command.summary, command.what_changed, command.primary_source,
            command.facts, command.data_points, command.interpretation, command.inferences,
            command.supporting_sources, command.company_exposures, command.event_confidence,
            command.exposure_confidence, command.time_horizon, command.risks,
            command.counter_evidence, command.why_hsi_should_care, command.effective_at,
            command.affected_sectors, command.affected_industries,
        )

    @staticmethod
    def _request_from(
        command: ExternalIntelligenceRecordCommand, event: ExternalEvent, evidence: EvidenceVersion, requested_at: datetime,
    ) -> ReevaluationRequest:
        instruments = tuple(sorted({
            item.canonical_instrument_id
            for item in evidence.company_exposures
            if item.verification_status == "VERIFIED" and item.canonical_instrument_id is not None
        }))
        return ReevaluationRequest(
            event.canonical_event_id, evidence.evidence_version_id, event.materiality, requested_at,
            instruments, tuple(sorted(set(evidence.affected_sectors))), tuple(sorted(set(evidence.affected_industries))),
        )


def _utc_timestamp(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("External-intelligence application clock must return a timezone-aware timestamp.")
    return value.astimezone(UTC)
