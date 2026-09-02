from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.domain.models import FreshnessStatus
from app.intelligence.company_evidence import CompositeStoredIntelligenceSource
from app.intelligence.non_company_evidence import NonCompanyEvidenceStoredSource
from app.intelligence.unified_state import (
    IntelligenceEvidenceAvailability,
    IntelligenceEvidenceDomain,
    IntelligenceEvidenceReference,
    IntelligenceInvalidationDomain,
    IntelligenceStateCompleteness,
    create_unified_intelligence_state,
)
from app.intelligence.unified_state_builder import StoredIntelligenceArtifact, UnifiedIntelligenceStateBuilder
from app.reliability.integrity import (
    RELIABILITY_INTEGRITY_DOMAINS,
    ReliabilityFallbackState,
    ReliabilityIntegrityEvidenceSource,
    ReliabilityIntegrityObservationStore,
    ReliabilityProvenanceState,
    build_reliability_integrity_observation,
)
from app.storage.sqlite_core_api_snapshot_repository import SQLiteCoreApiSnapshotRepository


T = datetime(2026, 9, 1, 12, tzinfo=UTC)
INSTRUMENT = "NSE:INE372A01015"


def _reference(
    domain: IntelligenceEvidenceDomain,
    *,
    availability: IntelligenceEvidenceAvailability = IntelligenceEvidenceAvailability.AVAILABLE,
    freshness: FreshnessStatus = FreshnessStatus.FRESH,
    provenance: str | None = "official-provenance",
    warnings: tuple[str, ...] = (),
    at: datetime = T,
) -> IntelligenceEvidenceReference:
    has_evidence = availability is not IntelligenceEvidenceAvailability.UNAVAILABLE
    return IntelligenceEvidenceReference(
        domain=domain,
        availability=availability,
        artifact_ids=(f"{domain.value.lower()}-artifact",) if has_evidence else (),
        artifact_fingerprints=(f"{domain.value.lower()}-fingerprint",) if has_evidence else (),
        evidence_as_of=at if has_evidence else None,
        observed_at=at if has_evidence else None,
        freshness_status=freshness,
        freshness_policy_reference="existing-domain-policy" if has_evidence else None,
        source_provenance_fingerprint=provenance if has_evidence else None,
        historical_integrity_reference="integrity-lineage" if has_evidence else None,
        warnings=tuple(sorted(warnings)),
    )


def _state(overrides: dict[IntelligenceEvidenceDomain, dict] | None = None):
    overrides = overrides or {}
    references = []
    for domain in IntelligenceEvidenceDomain:
        values = overrides.get(domain, {})
        references.append(_reference(domain, **values))
    return create_unified_intelligence_state(
        canonical_instrument_id=INSTRUMENT,
        as_of=T,
        evaluation_session=T,
        state_schema_version="unified-intelligence-state-v1",
        intelligence_contract_version="shared-brain-v1",
        evidence_references=tuple(references),
        completeness=IntelligenceStateCompleteness.COMPLETE,
    )


def test_official_provenance_and_corrected_reg31_pit_lineage_are_retained() -> None:
    observation = build_reliability_integrity_observation(_state({
        IntelligenceEvidenceDomain.FUNDAMENTALS: {"provenance": "bse-official-xbrl-fingerprint"},
        IntelligenceEvidenceDomain.OWNERSHIP: {
            "provenance": "nse-reg31-corrected-xbrl-fingerprint",
            "warnings": ("NSE_REG31_PIT_CORRECTION_APPLIED",),
        },
    }))
    fundamentals = next(item for item in observation.dimensions if item.domain is IntelligenceEvidenceDomain.FUNDAMENTALS)
    ownership = next(item for item in observation.dimensions if item.domain is IntelligenceEvidenceDomain.OWNERSHIP)
    assert fundamentals.provenance_state is ReliabilityProvenanceState.RETAINED
    assert fundamentals.source_provenance_fingerprint == "bse-official-xbrl-fingerprint"
    assert ownership.pit_valid and "NSE_REG31_PIT_CORRECTION_APPLIED" in ownership.blockers


def test_fallback_fresh_stale_unavailable_and_conflict_remain_categorical() -> None:
    observation = build_reliability_integrity_observation(_state({
        IntelligenceEvidenceDomain.MARKET_DATA: {"warnings": ("RELIABILITY_STATUS_FALLBACK_USED",)},
        IntelligenceEvidenceDomain.TECHNICAL: {"availability": IntelligenceEvidenceAvailability.STALE, "freshness": FreshnessStatus.STALE},
        IntelligenceEvidenceDomain.SECTOR: {"availability": IntelligenceEvidenceAvailability.UNAVAILABLE},
        IntelligenceEvidenceDomain.HISTORICAL_INTEGRITY: {"availability": IntelligenceEvidenceAvailability.CONFLICTED},
    }))
    by_domain = {item.domain: item for item in observation.dimensions}
    assert by_domain[IntelligenceEvidenceDomain.MARKET_DATA].fallback_state is ReliabilityFallbackState.FALLBACK_USED
    assert by_domain[IntelligenceEvidenceDomain.TECHNICAL].freshness_state is FreshnessStatus.STALE
    assert by_domain[IntelligenceEvidenceDomain.SECTOR].evidence_state is IntelligenceEvidenceAvailability.UNAVAILABLE
    assert by_domain[IntelligenceEvidenceDomain.HISTORICAL_INTEGRITY].conflict_detected
    assert observation.conflict_detected
    assert observation.evidence_state is IntelligenceEvidenceAvailability.CONFLICTED


def test_observation_is_deterministic_and_contains_no_numeric_score_or_ordering() -> None:
    first = build_reliability_integrity_observation(_state())
    second = build_reliability_integrity_observation(_state())
    assert first == second
    assert len(first.dimensions) == len(RELIABILITY_INTEGRITY_DOMAINS)
    assert not hasattr(first, "score")
    assert {item.value for item in ReliabilityFallbackState} == {
        "NOT_REPORTED", "FALLBACK_USED", "LAST_KNOWN_GOOD", "DEGRADED",
    }


def test_store_is_pit_safe_idempotent_and_reopen_durable(tmp_path) -> None:
    path = tmp_path / "reliability.sqlite"
    repository = SQLiteCoreApiSnapshotRepository(path)
    store = ReliabilityIntegrityObservationStore(repository)
    value = build_reliability_integrity_observation(_state())
    assert store.save(value) == value
    assert store.save(value) == value
    assert store.list(canonical_instrument_id=INSTRUMENT, as_of=T - timedelta(seconds=1)) == ()
    assert store.list(canonical_instrument_id=INSTRUMENT, as_of=T) == (value,)
    repository.close()
    reopened = SQLiteCoreApiSnapshotRepository(path)
    assert ReliabilityIntegrityObservationStore(reopened).list(canonical_instrument_id=INSTRUMENT, as_of=T) == (value,)
    reopened.close()


def test_shared_brain_reliability_composition_does_not_upgrade_other_domains(tmp_path) -> None:
    repository = SQLiteCoreApiSnapshotRepository(tmp_path / "composition.sqlite")
    store = ReliabilityIntegrityObservationStore(repository)
    observation = build_reliability_integrity_observation(_state({
        IntelligenceEvidenceDomain.SECTOR: {"availability": IntelligenceEvidenceAvailability.UNAVAILABLE},
    }))
    store.save(observation)

    class _Core:
        def list_stored_intelligence_artifacts(self, canonical_instrument_id, *, as_of):
            return (StoredIntelligenceArtifact(
                canonical_instrument_id, IntelligenceEvidenceDomain.REFERENCE_DATA,
                "canonical-identity", "identity-fingerprint", IntelligenceEvidenceAvailability.AVAILABLE,
                as_of, as_of, as_of, FreshnessStatus.UNKNOWN, None, "identity-provenance", None,
                IntelligenceInvalidationDomain.REFERENCE_DATA,
            ),)

    state = UnifiedIntelligenceStateBuilder(CompositeStoredIntelligenceSource(
        _Core(),
        NonCompanyEvidenceStoredSource(
            reliability_integrity_source=ReliabilityIntegrityEvidenceSource(store),
        ),
    )).build(INSTRUMENT, as_of=T)
    reliability = next(item for item in state.evidence_references if item.domain is IntelligenceEvidenceDomain.RELIABILITY)
    sector = next(item for item in state.evidence_references if item.domain is IntelligenceEvidenceDomain.SECTOR)
    assert reliability.availability is IntelligenceEvidenceAvailability.PARTIAL
    assert sector.availability is IntelligenceEvidenceAvailability.UNAVAILABLE
    repository.close()
