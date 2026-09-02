"""Read-only Shared Brain consumption of durable external-intelligence requests.

This deliberately sits after V1D's durable News projection.  It neither
creates the projection nor updates the immutable request; each invocation
returns a deterministic processing receipt for the supplied PIT cutoff.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Protocol

from app.intelligence.external_intelligence import EvidenceVersion, ExternalEvent
from app.intelligence.external_intelligence_news_projection import ExternalIntelligenceNewsProjector
from app.intelligence.shared_brain_application import SharedBrainAnalysisView
from app.intelligence.unified_state import BrainOutputContext, IntelligenceEvidenceDomain
from app.news.store import NewsEvidenceStore
from app.storage.sqlite_external_intelligence_repository import SQLiteExternalIntelligenceRepository


class ExternalIntelligenceReevaluationDisposition(StrEnum):
    """Outcome of one non-persistent attempt to consume a request."""

    COMPLETED_READ_ONLY = "COMPLETED_READ_ONLY"
    BLOCKED_REQUEST_NOT_FOUND = "BLOCKED_REQUEST_NOT_FOUND"
    BLOCKED_EVENT_NOT_FOUND = "BLOCKED_EVENT_NOT_FOUND"
    BLOCKED_EVIDENCE_NOT_FOUND = "BLOCKED_EVIDENCE_NOT_FOUND"
    BLOCKED_EVIDENCE_LINEAGE_INVALID = "BLOCKED_EVIDENCE_LINEAGE_INVALID"
    BLOCKED_EVIDENCE_NOT_VISIBLE_AS_OF = "BLOCKED_EVIDENCE_NOT_VISIBLE_AS_OF"
    BLOCKED_NEWS_PROJECTION_MISSING = "BLOCKED_NEWS_PROJECTION_MISSING"
    BLOCKED_NEWS_PROJECTION_INVALID = "BLOCKED_NEWS_PROJECTION_INVALID"
    BLOCKED_TARGET_INVALID = "BLOCKED_TARGET_INVALID"
    UNSUPPORTED_NO_VERIFIED_CANONICAL_TARGET = "UNSUPPORTED_NO_VERIFIED_CANONICAL_TARGET"
    BLOCKED_SHARED_BRAIN_UNAVAILABLE = "BLOCKED_SHARED_BRAIN_UNAVAILABLE"


class SharedBrainReader(Protocol):
    """The existing application service's bounded read operation."""

    def analyze_stock(
        self, identifier: str, *, context: BrainOutputContext, as_of: datetime,
    ) -> SharedBrainAnalysisView: ...


@dataclass(frozen=True, slots=True)
class SharedBrainReevaluationTarget:
    canonical_instrument_id: str
    news_state_before: str
    news_state_after: str
    overall_brain_state_before: str
    overall_brain_state_after: str
    blockers: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ExternalIntelligenceReevaluationReceipt:
    """A typed, audit-friendly result without request-state mutation."""

    request_id: str
    canonical_event_id: str | None
    evidence_version_id: str | None
    intelligence_as_of: datetime
    targeted_canonical_instruments: tuple[str, ...]
    targets: tuple[SharedBrainReevaluationTarget, ...]
    disposition: ExternalIntelligenceReevaluationDisposition
    blocker: str | None = None


class ExternalIntelligenceReevaluationConsumer:
    """Validate one durable request and read the existing Shared Brain safely.

    The News record must already be the exact V1D projection.  This makes the
    consumer a strictly read-only boundary: it cannot backdate or generate
    evidence, expand a company name, or transition the immutable request.
    """

    def __init__(
        self,
        repository: SQLiteExternalIntelligenceRepository,
        news_store: NewsEvidenceStore,
        shared_brain: SharedBrainReader,
    ) -> None:
        self._repository = repository
        self._news_store = news_store
        self._shared_brain = shared_brain
        self._projector = ExternalIntelligenceNewsProjector(news_store)

    def consume(
        self, request_id: str, *, intelligence_as_of: datetime,
    ) -> ExternalIntelligenceReevaluationReceipt:
        cutoff = _utc_timestamp(intelligence_as_of)
        request = self._repository.get_reevaluation_request(request_id)
        if request is None:
            return _blocked(
                request_id, cutoff,
                ExternalIntelligenceReevaluationDisposition.BLOCKED_REQUEST_NOT_FOUND,
                "The durable reevaluation request is not available.",
            )
        event = self._repository.get_event(request.canonical_event_id)
        if event is None:
            return _blocked(
                request_id, cutoff,
                ExternalIntelligenceReevaluationDisposition.BLOCKED_EVENT_NOT_FOUND,
                "The request's canonical event is not available.",
                event_id=request.canonical_event_id, evidence_id=request.evidence_version_id,
            )
        evidence = self._repository.get_evidence_version(request.evidence_version_id)
        if evidence is None:
            return _blocked(
                request_id, cutoff,
                ExternalIntelligenceReevaluationDisposition.BLOCKED_EVIDENCE_NOT_FOUND,
                "The request's evidence version is not available.",
                event_id=event.canonical_event_id, evidence_id=request.evidence_version_id,
            )
        if not _exact_lineage(event, evidence, request.canonical_event_id):
            return _blocked(
                request_id, cutoff,
                ExternalIntelligenceReevaluationDisposition.BLOCKED_EVIDENCE_LINEAGE_INVALID,
                "The request, event, and evidence lineage is inconsistent.",
                event_id=event.canonical_event_id, evidence_id=evidence.evidence_version_id,
            )
        if evidence.received_at > cutoff:
            return _blocked(
                request_id, cutoff,
                ExternalIntelligenceReevaluationDisposition.BLOCKED_EVIDENCE_NOT_VISIBLE_AS_OF,
                "The evidence was not yet known to HSI at this cutoff.",
                event_id=event.canonical_event_id, evidence_id=evidence.evidence_version_id,
            )

        try:
            expected_news = self._projector.project(event, evidence)
        except ValueError:
            return _blocked(
                request_id, cutoff,
                ExternalIntelligenceReevaluationDisposition.BLOCKED_NEWS_PROJECTION_INVALID,
                "The derived News projection cannot be validated from canonical evidence.",
                event_id=event.canonical_event_id, evidence_id=evidence.evidence_version_id,
            )
        stored_news = self._news_store.get(expected_news.article_id)
        if stored_news is None:
            return _blocked(
                request_id, cutoff,
                ExternalIntelligenceReevaluationDisposition.BLOCKED_NEWS_PROJECTION_MISSING,
                "The required derived News projection is not available.",
                event_id=event.canonical_event_id, evidence_id=evidence.evidence_version_id,
            )
        if stored_news != expected_news:
            return _blocked(
                request_id, cutoff,
                ExternalIntelligenceReevaluationDisposition.BLOCKED_NEWS_PROJECTION_INVALID,
                "The stored derived News projection does not match canonical evidence.",
                event_id=event.canonical_event_id, evidence_id=evidence.evidence_version_id,
            )

        verified_targets = _verified_targets(evidence)
        if not verified_targets:
            return _blocked(
                request_id, cutoff,
                ExternalIntelligenceReevaluationDisposition.UNSUPPORTED_NO_VERIFIED_CANONICAL_TARGET,
                "No verified canonical instrument target is available for a stock Shared Brain read.",
                event_id=event.canonical_event_id, evidence_id=evidence.evidence_version_id,
            )
        if request.affected_canonical_instruments != verified_targets:
            return _blocked(
                request_id, cutoff,
                ExternalIntelligenceReevaluationDisposition.BLOCKED_TARGET_INVALID,
                "The request target set does not exactly match verified canonical evidence.",
                event_id=event.canonical_event_id, evidence_id=evidence.evidence_version_id,
            )

        before_cutoff = evidence.received_at - timedelta(microseconds=1)
        results: list[SharedBrainReevaluationTarget] = []
        try:
            for target in verified_targets:
                before = self._shared_brain.analyze_stock(
                    target, context=BrainOutputContext.ALERT_REVIEW, as_of=before_cutoff,
                )
                after = self._shared_brain.analyze_stock(
                    target, context=BrainOutputContext.ALERT_REVIEW, as_of=cutoff,
                )
                results.append(SharedBrainReevaluationTarget(
                    canonical_instrument_id=target,
                    news_state_before=_news_state(before),
                    news_state_after=_news_state(after),
                    overall_brain_state_before=before.evidence_status,
                    overall_brain_state_after=after.evidence_status,
                    blockers=tuple(sorted(set((*before.blockers, *after.blockers)))),
                ))
        except (TypeError, ValueError):
            return _blocked(
                request_id, cutoff,
                ExternalIntelligenceReevaluationDisposition.BLOCKED_SHARED_BRAIN_UNAVAILABLE,
                "The existing Shared Brain cannot compose a governed view for this request.",
                event_id=event.canonical_event_id, evidence_id=evidence.evidence_version_id,
                targets=verified_targets,
            )
        return ExternalIntelligenceReevaluationReceipt(
            request_id, event.canonical_event_id, evidence.evidence_version_id, cutoff,
            verified_targets, tuple(results),
            ExternalIntelligenceReevaluationDisposition.COMPLETED_READ_ONLY,
        )


def _verified_targets(evidence: EvidenceVersion) -> tuple[str, ...]:
    return tuple(sorted({
        item.canonical_instrument_id
        for item in evidence.company_exposures
        if item.verification_status == "VERIFIED" and item.canonical_instrument_id is not None
    }))


def _exact_lineage(event: ExternalEvent, evidence: EvidenceVersion, event_id: str) -> bool:
    return (
        event.canonical_event_id == event_id
        and evidence.event.canonical_event_id == event_id
        and evidence.event == event
    )


def _news_state(view: SharedBrainAnalysisView) -> str:
    return dict(view.evidence_domains).get(IntelligenceEvidenceDomain.NEWS_CATALYSTS.value, "UNAVAILABLE")


def _blocked(
    request_id: str,
    cutoff: datetime,
    disposition: ExternalIntelligenceReevaluationDisposition,
    blocker: str,
    *,
    event_id: str | None = None,
    evidence_id: str | None = None,
    targets: tuple[str, ...] = (),
) -> ExternalIntelligenceReevaluationReceipt:
    return ExternalIntelligenceReevaluationReceipt(
        request_id, event_id, evidence_id, cutoff, targets, (), disposition, blocker,
    )


def _utc_timestamp(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("External-intelligence reevaluation cutoff must include a timezone.")
    return value.astimezone(UTC)


__all__ = (
    "ExternalIntelligenceReevaluationConsumer", "ExternalIntelligenceReevaluationDisposition",
    "ExternalIntelligenceReevaluationReceipt", "SharedBrainReevaluationTarget",
)
