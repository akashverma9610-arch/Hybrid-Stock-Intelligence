"""Pure P1C projection from one immutable Market-Wide Watch to one HSISignal.

The source Watch remains the canonical discovery artifact.  This module only
copies its verified PIT-bound facts into the P1A value contract and combines
them with P1B's read-only strategy-policy provenance.
"""
from __future__ import annotations

from datetime import UTC, datetime

from app.intelligence.hsi_signal import (
    DetectionTimeStatus,
    DiagnosticLineageReference,
    EvidenceLineageReference,
    HSISignal,
    HSISignalError,
    LineageAvailability,
    ValueAvailability,
)
from app.intelligence.hsi_signal_strategy_registry import (
    HSISignalStrategyRegistry,
    HSISignalStrategyRegistryError,
    StrategyRegistryResolution,
    WatchStrategyRoutingContext,
)
from app.intelligence.market_wide_watch import MarketWideWatchRecord
from app.intelligence.opportunity_archetypes import OpportunityArchetype


class HSISignalProjectionError(ValueError):
    """Raised when an immutable Watch cannot safely be projected."""


def project_watch_to_hsi_signal(
    *,
    watch: MarketWideWatchRecord,
    archetype: OpportunityArchetype,
    registry: HSISignalStrategyRegistry,
) -> HSISignal:
    """Return one deterministic, non-executable signal for a routed Watch.

    This function has no repository, provider, portfolio, API, or persistence
    dependency.  P1B may read existing governance provenance through its
    injected reader, but neither this projector nor P1B writes anything.
    """
    _verify_watch_projection_input(watch, archetype, registry)
    watch_as_of = watch.watch_as_of.astimezone(UTC)
    context = WatchStrategyRoutingContext(
        canonical_instrument_id=watch.canonical_instrument_id,
        watch_id=watch.watch_id,
        watch_fingerprint=watch.fingerprint,
        watch_as_of=watch_as_of,
        archetype=archetype,
        watch_archetypes=watch.archetypes,
        setup_state=watch.setup_state,
        setup_policy_routes=watch.setup_policy_routes,
    )
    try:
        resolution = registry.resolve(context)
    except HSISignalStrategyRegistryError as error:
        raise HSISignalProjectionError("HSI_SIGNAL_PROJECTION_REGISTRY_RESOLUTION_INVALID") from error
    _verify_resolution_matches_watch(resolution, context)
    try:
        return HSISignal.create(
            canonical_instrument_id=watch.canonical_instrument_id,
            watch_id=watch.watch_id,
            watch_fingerprint=watch.fingerprint,
            watch_as_of=watch_as_of,
            detected_at=None,
            detection_time_status=DetectionTimeStatus.DETECTION_TIME_UNAVAILABLE,
            archetype=archetype,
            routing_policy_version=watch.policy_identity,
            horizon=None,
            horizon_availability=ValueAvailability.UNAVAILABLE,
            horizon_routing_evidence_ref=None,
            direction=None,
            direction_availability=ValueAvailability.UNAVAILABLE,
            direction_routing_evidence_ref=None,
            strategy_resolution=resolution.resolution,
            diagnostic_lineage=tuple(
                DiagnosticLineageReference(
                    rule_id=item.rule_id,
                    # The Watch retains the canonical diagnostic result token and
                    # artifact ID, not a second diagnostic-result object.  P1
                    # projects those exact retained values without a new lookup.
                    diagnostic_result_id=item.diagnostic_result,
                    artifact_id=item.artifact_id,
                    artifact_fingerprint=item.artifact_fingerprint,
                )
                for item in watch.evidence_references
            ),
            diagnostic_lineage_availability=(
                LineageAvailability.PRESENT
                if watch.evidence_references else LineageAvailability.SOURCE_EMPTY
            ),
            evidence_lineage=tuple(
                EvidenceLineageReference(
                    canonical_event_id=item.canonical_event_id,
                    evidence_version_id=item.evidence_version_id,
                    evidence_fingerprint=item.evidence_fingerprint,
                )
                for item in watch.external_evidence_references
            ),
            evidence_lineage_availability=(
                LineageAvailability.PRESENT
                if watch.external_evidence_references else LineageAvailability.SOURCE_EMPTY
            ),
            source_watch_status=watch.status.value,
            source_lifecycle_flags=watch.lifecycle_flags,
            blocker_codes=tuple(sorted({
                *watch.blocker_codes,
                *(() if resolution.reason_code is None else (resolution.reason_code.value,)),
            })),
        )
    except HSISignalError as error:
        raise HSISignalProjectionError("HSI_SIGNAL_PROJECTION_SOURCE_LINEAGE_INVALID") from error


def _verify_watch_projection_input(
    watch: MarketWideWatchRecord,
    archetype: OpportunityArchetype,
    registry: HSISignalStrategyRegistry,
) -> None:
    if not isinstance(watch, MarketWideWatchRecord):
        raise HSISignalProjectionError("HSI_SIGNAL_PROJECTION_WATCH_REQUIRED")
    if not isinstance(archetype, OpportunityArchetype):
        raise HSISignalProjectionError("HSI_SIGNAL_PROJECTION_ARCHETYPE_INVALID")
    if not isinstance(registry, HSISignalStrategyRegistry):
        raise HSISignalProjectionError("HSI_SIGNAL_PROJECTION_REGISTRY_REQUIRED")
    try:
        watch.verify()
    except (TypeError, ValueError) as error:
        raise HSISignalProjectionError("HSI_SIGNAL_PROJECTION_WATCH_INVALID") from error
    if archetype not in watch.archetypes:
        raise HSISignalProjectionError("HSI_SIGNAL_PROJECTION_ARCHETYPE_NOT_ROUTED")
    if watch.last_evidence_as_of is not None:
        if not _is_aware(watch.last_evidence_as_of):
            raise HSISignalProjectionError("HSI_SIGNAL_PROJECTION_LAST_EVIDENCE_AS_OF_INVALID")
        if watch.last_evidence_as_of.astimezone(UTC) > watch.watch_as_of.astimezone(UTC):
            raise HSISignalProjectionError("HSI_SIGNAL_PROJECTION_FUTURE_EVIDENCE_EXCLUDED")


def _verify_resolution_matches_watch(
    resolution: StrategyRegistryResolution,
    context: WatchStrategyRoutingContext,
) -> None:
    if not isinstance(resolution, StrategyRegistryResolution):
        raise HSISignalProjectionError("HSI_SIGNAL_PROJECTION_REGISTRY_RESOLUTION_INVALID")
    try:
        resolution.verify()
    except HSISignalStrategyRegistryError as error:
        raise HSISignalProjectionError("HSI_SIGNAL_PROJECTION_REGISTRY_RESOLUTION_INVALID") from error
    if (
        resolution.canonical_instrument_id != context.canonical_instrument_id
        or resolution.watch_id != context.watch_id
        or resolution.watch_fingerprint != context.watch_fingerprint
        or resolution.watch_as_of != context.watch_as_of
        or resolution.archetype != context.archetype.value
    ):
        raise HSISignalProjectionError("HSI_SIGNAL_PROJECTION_REGISTRY_RESOLUTION_MISMATCH")


def _is_aware(value: datetime) -> bool:
    return isinstance(value, datetime) and value.tzinfo is not None and value.utcoffset() is not None


__all__ = (
    "HSISignalProjectionError",
    "project_watch_to_hsi_signal",
)
