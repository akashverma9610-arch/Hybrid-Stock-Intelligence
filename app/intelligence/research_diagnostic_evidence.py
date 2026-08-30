"""Stored-only 61-diagnostic lineage for UnifiedIntelligenceState.

The existing repository has durable individual ``DiagnosticResult`` records,
but no durable ``ResearchSnapshot`` read model.  This boundary therefore
projects only completed diagnostic bundles and explicitly leaves research
evidence unavailable.  It never runs an evaluator or research engine.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Protocol

from app.domain.models import DiagnosticResult, FreshnessStatus, StrategyVersionReference
from app.historical.guard import manifest_fingerprint
from app.intelligence.unified_state import (
    IntelligenceEvidenceAvailability,
    IntelligenceEvidenceDomain,
    IntelligenceInvalidationDomain,
)
from app.intelligence.unified_state_builder import StoredIntelligenceArtifact
from app.registry.canonical import DIAGNOSTIC_RULES
from app.storage.governance_repository import StrategyGovernanceRepository


class StoredDiagnosticResultSource(Protocol):
    """Read-only boundary for existing, durable diagnostic records."""

    def list_stored_diagnostic_results(
        self, canonical_instrument_id: str, *, as_of: datetime,
    ) -> tuple[DiagnosticResult, ...]: ...


class StrategyGovernanceDiagnosticResultSource:
    """Expose one already-known governance result bundle without broad querying.

    ``StrategyGovernanceRepository`` deliberately supports diagnostics by
    exact strategy/version and exact evaluation as-of.  This adapter retains
    that conservative contract; it does not add an ad-hoc query surface.
    """

    def __init__(
        self,
        repository: StrategyGovernanceRepository,
        *,
        strategy_version: StrategyVersionReference,
        evaluation_as_of: datetime,
    ) -> None:
        self._repository = repository
        self._strategy_version = strategy_version
        self._evaluation_as_of = evaluation_as_of

    def list_stored_diagnostic_results(
        self, canonical_instrument_id: str, *, as_of: datetime,
    ) -> tuple[DiagnosticResult, ...]:
        if self._evaluation_as_of > as_of:
            return ()
        return tuple(
            value
            for value in self._repository.list_diagnostic_results(
                self._strategy_version, self._evaluation_as_of,
            )
            if value.instrument_id == canonical_instrument_id
        )


class ResearchDiagnosticEvidenceAdapter:
    """Project immutable diagnostic metadata; research itself remains absent."""

    def __init__(self, diagnostics: StoredDiagnosticResultSource | None = None) -> None:
        self._diagnostics = diagnostics

    def artifacts(self, canonical_instrument_id: str, *, as_of: datetime) -> tuple[StoredIntelligenceArtifact, ...]:
        if self._diagnostics is None:
            return (_unavailable_artifact(
                canonical_instrument_id,
                IntelligenceEvidenceDomain.RESEARCH_DIAGNOSTICS,
                ("DIAGNOSTIC_DURABLE_READ_BOUNDARY_MISSING", "RESEARCH_DURABLE_READ_BOUNDARY_MISSING"),
                artifact_id="diagnostic-evidence:unavailable",
            ),)
        values = tuple(
            item
            for item in self._diagnostics.list_stored_diagnostic_results(canonical_instrument_id, as_of=as_of)
            if _eligible(item, canonical_instrument_id, as_of)
        )
        if not values:
            return (_unavailable_artifact(
                canonical_instrument_id,
                IntelligenceEvidenceDomain.RESEARCH_DIAGNOSTICS,
                ("DIAGNOSTIC_NOT_YET_COMPUTED", "RESEARCH_DURABLE_READ_BOUNDARY_MISSING"),
                artifact_id="diagnostic-evidence:unavailable",
            ),)
        grouped: dict[tuple[StrategyVersionReference, datetime], list[DiagnosticResult]] = defaultdict(list)
        for value in values:
            grouped[(value.strategy_version, value.as_of_timestamp)].append(value)
        selected_key = max(grouped, key=lambda item: (
            item[1], item[0].strategy_id, item[0].version,
            tuple(sorted(value.id for value in grouped[item])),
        ))
        return (_diagnostic_bundle_artifact(canonical_instrument_id, selected_key, tuple(grouped[selected_key])),)


class ResearchDiagnosticEvidenceStoredSource:
    """U14B-3E1 source for existing CompositeStoredIntelligenceSource wiring."""

    def __init__(self, diagnostics: StoredDiagnosticResultSource | None = None) -> None:
        self._adapter = ResearchDiagnosticEvidenceAdapter(diagnostics)

    def list_stored_intelligence_artifacts(
        self, canonical_instrument_id: str, *, as_of: datetime,
    ) -> tuple[StoredIntelligenceArtifact, ...]:
        return self._adapter.artifacts(canonical_instrument_id, as_of=as_of)


def _diagnostic_bundle_artifact(
    canonical_instrument_id: str,
    key: tuple[StrategyVersionReference, datetime],
    values: tuple[DiagnosticResult, ...],
) -> StoredIntelligenceArtifact:
    reference, evaluation_as_of = key
    ordered = tuple(sorted(values, key=lambda item: (item.rule_id, item.id)))
    rule_ids = tuple(item.rule_id for item in ordered)
    expected = {str(item.rule_id) for item in DIAGNOSTIC_RULES}
    duplicate_rules = len(set(rule_ids)) != len(rule_ids)
    complete = set(rule_ids) == expected and not duplicate_rules
    warnings = set()
    if not complete:
        warnings.add("DIAGNOSTIC_61_BUNDLE_PARTIAL")
    if duplicate_rules:
        warnings.add("DIAGNOSTIC_DUPLICATE_RULE_LINEAGE")
    # No dedicated research/diagnostic invalidation enum exists.  Preserve the
    # nearest current vocabulary rather than introducing an overlapping domain.
    warnings.add("DIAGNOSTIC_INVALIDATION_REFERENCE_DATA")
    warnings.add("RESEARCH_DURABLE_READ_BOUNDARY_MISSING")
    return StoredIntelligenceArtifact(
        canonical_instrument_id=canonical_instrument_id,
        domain=IntelligenceEvidenceDomain.RESEARCH_DIAGNOSTICS,
        artifact_id=(
            f"diagnostic-61:{reference.strategy_id}:{reference.version}:"
            f"{evaluation_as_of.isoformat()}:{canonical_instrument_id}"
        ),
        artifact_fingerprint=manifest_fingerprint(
            strategy_id=reference.strategy_id, strategy_version=reference.version,
            evaluation_as_of=evaluation_as_of,
            diagnostics=tuple(
                (item.id, item.rule_id, item.result, item.evaluated_at, item.as_of_timestamp,
                 item.evidence_ids, item.input_observation_ids)
                for item in ordered
            ),
        ),
        availability=(
            IntelligenceEvidenceAvailability.AVAILABLE
            if complete else IntelligenceEvidenceAvailability.PARTIAL
        ),
        evidence_as_of=evaluation_as_of,
        observed_at=max(item.evaluated_at for item in ordered),
        available_at=max(item.evaluated_at for item in ordered),
        freshness_status=FreshnessStatus.UNKNOWN,
        freshness_policy_reference=None,
        source_provenance_fingerprint=manifest_fingerprint(
            strategy_id=reference.strategy_id, strategy_version=reference.version,
            diagnostic_ids=tuple(item.id for item in ordered),
        ),
        historical_integrity_reference=None,
        invalidation_domain=IntelligenceInvalidationDomain.REFERENCE_DATA,
        warnings=tuple(sorted(warnings)),
    )


def _unavailable_artifact(
    canonical_instrument_id: str,
    domain: IntelligenceEvidenceDomain,
    warnings: tuple[str, ...],
    *,
    artifact_id: str,
) -> StoredIntelligenceArtifact:
    return StoredIntelligenceArtifact(
        canonical_instrument_id=canonical_instrument_id,
        domain=domain,
        artifact_id=artifact_id,
        artifact_fingerprint=manifest_fingerprint(domain=domain.value, artifact_id=artifact_id, warnings=warnings),
        availability=IntelligenceEvidenceAvailability.UNAVAILABLE,
        evidence_as_of=None,
        observed_at=None,
        available_at=None,
        freshness_status=FreshnessStatus.UNKNOWN,
        freshness_policy_reference=None,
        source_provenance_fingerprint=None,
        historical_integrity_reference=None,
        invalidation_domain=IntelligenceInvalidationDomain.REFERENCE_DATA,
        warnings=tuple(sorted(set(warnings))),
    )


def _eligible(value: DiagnosticResult, canonical_instrument_id: str, as_of: datetime) -> bool:
    return (
        value.instrument_id == canonical_instrument_id
        and _aware(value.as_of_timestamp)
        and _aware(value.evaluated_at)
        and value.as_of_timestamp <= as_of
        and value.evaluated_at <= as_of
    )


def _aware(value: datetime) -> bool:
    return value.tzinfo is not None and value.utcoffset() is not None


__all__ = (
    "ResearchDiagnosticEvidenceAdapter", "ResearchDiagnosticEvidenceStoredSource",
    "StoredDiagnosticResultSource", "StrategyGovernanceDiagnosticResultSource",
)
