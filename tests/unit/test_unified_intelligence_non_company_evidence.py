from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from app.data_sources.models import DataFamily
from app.domain.models import FreshnessStatus
from app.historical.security_master import HistoricalIntegrityStatus, HistoricalPriceIntegrity, HistoricalSecurityIdentity, HistoricalSecurityMasterStore, HistoricalSecurityStatus, PriceAdjustmentBasis
from app.intelligence.company_evidence import CompositeStoredIntelligenceSource
from app.intelligence.non_company_evidence import NonCompanyEvidenceStoredSource, ReliabilityEvidenceAdapter, StoredReliabilityDecision
from app.intelligence.unified_state import IntelligenceEvidenceAvailability, IntelligenceEvidenceDomain, IntelligenceInvalidationDomain, UnifiedIntelligenceStateError
from app.intelligence.unified_state_builder import StoredIntelligenceArtifact, UnifiedIntelligenceStateBuilder
from app.market_data.models import Exchange
from app.market_data.reference_data.resolver import TickSizeReferenceResolver
from app.market_data.reference_data.sqlite_repository import SQLiteTickSizeObservationRepository
from app.market_data.reference_data.tick_size import NseTickSizeObservation, NseTickSizeSegment, TickSizeAvailabilitySemantics, TickSizeSourceClass
from app.reliability.models import DataAvailability, ReliabilityDecision, ReliabilityStatus
from app.storage.sqlite_core_api_snapshot_repository import SQLiteCoreApiSnapshotRepository
from app.taxonomy.models import ClassificationSourceStatus, InstrumentTaxonomyClassification
from app.taxonomy.service import TaxonomySnapshotStore


T = datetime(2026, 8, 28, 12, tzinfo=UTC)
INSTRUMENT = "NSE:NONCOMPANY"


class _CoreSource:
    def list_stored_intelligence_artifacts(self, canonical_instrument_id: str, *, as_of: datetime):
        if canonical_instrument_id != INSTRUMENT:
            return ()
        return tuple(
            StoredIntelligenceArtifact(INSTRUMENT, domain, f"core:{domain.value}", f"core:{domain.value}:fp", IntelligenceEvidenceAvailability.AVAILABLE, T - timedelta(days=1), T - timedelta(days=1), T - timedelta(days=1), FreshnessStatus.FRESH, None, None, None, IntelligenceInvalidationDomain.PRICE if domain is IntelligenceEvidenceDomain.MARKET_DATA else IntelligenceInvalidationDomain.REFERENCE_DATA)
            for domain in (IntelligenceEvidenceDomain.REFERENCE_DATA, IntelligenceEvidenceDomain.MARKET_DATA)
        )


def _classification(*, at: datetime = T - timedelta(days=1)) -> InstrumentTaxonomyClassification:
    return InstrumentTaxonomyClassification("tax", INSTRUMENT, "Industry", "Sector", "Super", "NSE_OFFICIAL", ClassificationSourceStatus.OFFICIAL, at, None, at, 1.0, "v1", "nse:taxonomy")


def _tick(record_id: str, value: str = "0.05") -> NseTickSizeObservation:
    return NseTickSizeObservation(record_id, INSTRUMENT, Exchange.NSE, NseTickSizeSegment.NSE_CASH_EQUITY, "INE000A01001", Decimal(value), TickSizeSourceClass.OFFICIAL_EXCHANGE, "NSE", f"master:{record_id}", T - timedelta(days=1), T - timedelta(days=2), None, TickSizeAvailabilitySemantics.EXPLICIT_EFFECTIVE_PERIOD)


def _builder(tmp_path: Path, *, taxonomy_values=(), identities=(), integrities=(), ticks=(), reliability=()) -> UnifiedIntelligenceStateBuilder:
    repository = SQLiteCoreApiSnapshotRepository(tmp_path / "core.sqlite")
    taxonomy = TaxonomySnapshotStore(repository)
    historical = HistoricalSecurityMasterStore(repository)
    for value in taxonomy_values: taxonomy.save_classification(value)
    for value in identities: historical.save_identity(value)
    for value in integrities: historical.save_integrity(value)
    tick_repository = SQLiteTickSizeObservationRepository(tmp_path / "ticks.sqlite")
    for value in ticks: tick_repository.save_tick_size_observation(value)
    class _ReliabilitySource:
        def list_stored_reliability_decisions(self, canonical_instrument_id, *, as_of): return tuple(reliability)
    source = NonCompanyEvidenceStoredSource(taxonomy=taxonomy, historical_security_master=historical, tick_resolver=TickSizeReferenceResolver(tick_repository), reliability_source=_ReliabilitySource() if reliability else None)
    return UnifiedIntelligenceStateBuilder(CompositeStoredIntelligenceSource(_CoreSource(), source))


def _reference(state, domain): return next(item for item in state.evidence_references if item.domain is domain)


def test_taxonomy_is_a_pit_safe_sector_and_reference_lineage_not_sector_rotation(tmp_path: Path) -> None:
    state = _builder(tmp_path, taxonomy_values=(_classification(),)).build(INSTRUMENT, as_of=T)
    sector, reference = _reference(state, IntelligenceEvidenceDomain.SECTOR), _reference(state, IntelligenceEvidenceDomain.REFERENCE_DATA)
    assert sector.availability is IntelligenceEvidenceAvailability.AVAILABLE
    assert reference.availability is IntelligenceEvidenceAvailability.PARTIAL
    assert "SECTOR_ROTATION_DERIVED_READ_BOUNDARY_UNAVAILABLE" in sector.warnings
    assert sector.artifact_ids == ("taxonomy:tax",)
    assert "taxonomy:tax" in reference.artifact_ids


def test_future_taxonomy_and_historical_identity_are_excluded_from_earlier_state(tmp_path: Path) -> None:
    future = _classification(at=T + timedelta(days=1))
    identity = HistoricalSecurityIdentity("future-identity", INSTRUMENT, "INE000A01001", "NSE", "FUTURE", "EQ", None, None, None, None, T + timedelta(days=1), None, HistoricalSecurityStatus.ACTIVE, "NSE_OFFICIAL", T + timedelta(days=1), "v1")
    before = _builder(tmp_path, taxonomy_values=(future,), identities=(identity,)).build(INSTRUMENT, as_of=T)
    after = _builder(tmp_path / "after", taxonomy_values=(future,), identities=(identity,)).build(INSTRUMENT, as_of=T + timedelta(days=1))
    assert _reference(before, IntelligenceEvidenceDomain.SECTOR).availability is IntelligenceEvidenceAvailability.UNAVAILABLE
    assert "historical-security:future-identity" not in _reference(before, IntelligenceEvidenceDomain.REFERENCE_DATA).artifact_ids
    assert _reference(after, IntelligenceEvidenceDomain.SECTOR).availability is IntelligenceEvidenceAvailability.AVAILABLE


def test_tick_reference_is_bounded_and_absence_never_fabricates_a_tick(tmp_path: Path) -> None:
    available = _builder(tmp_path, taxonomy_values=(_classification(),), ticks=(_tick("tick"),)).build(INSTRUMENT, as_of=T)
    absent = _builder(tmp_path / "absent", taxonomy_values=(_classification(),)).build(INSTRUMENT, as_of=T)
    assert any(item.startswith("tick-resolution:tick") for item in _reference(available, IntelligenceEvidenceDomain.REFERENCE_DATA).artifact_ids)
    missing = _reference(absent, IntelligenceEvidenceDomain.REFERENCE_DATA)
    assert "tick-resolution:unavailable" in missing.artifact_ids
    assert "TICK_SIZE_UNAVAILABLE_FOR_AS_OF" in missing.warnings


def test_tick_conflict_propagates_fail_closed_without_arbitrary_selection(tmp_path: Path) -> None:
    builder = _builder(tmp_path, taxonomy_values=(_classification(),), ticks=(_tick("a", "0.05"), _tick("b", "0.10")))
    with pytest.raises(UnifiedIntelligenceStateError, match="CANONICAL_IDENTITY_CONFLICT"):
        builder.build(INSTRUMENT, as_of=T)


@pytest.mark.parametrize("status,expected", (
    (ReliabilityStatus.READY, IntelligenceEvidenceAvailability.AVAILABLE),
    (ReliabilityStatus.FALLBACK_USED, IntelligenceEvidenceAvailability.PARTIAL),
    (ReliabilityStatus.LAST_KNOWN_GOOD, IntelligenceEvidenceAvailability.PARTIAL),
    (ReliabilityStatus.UNAVAILABLE, IntelligenceEvidenceAvailability.UNAVAILABLE),
    (ReliabilityStatus.CONFLICTED, IntelligenceEvidenceAvailability.CONFLICTED),
))
def test_existing_reliability_states_are_preserved_without_any_new_score(status, expected) -> None:
    decision = ReliabilityDecision(DataFamily.HISTORICAL_OHLCV, DataAvailability(DataFamily.HISTORICAL_OHLCV, status, "source" if expected is not IntelligenceEvidenceAvailability.UNAVAILABLE else None, 1 if expected is not IntelligenceEvidenceAvailability.UNAVAILABLE else None, T, ()), "source", 1, status is ReliabilityStatus.FALLBACK_USED, status is ReliabilityStatus.LAST_KNOWN_GOOD, status is ReliabilityStatus.CONFLICTED)
    envelope = StoredReliabilityDecision("decision", INSTRUMENT, decision, T, T, "decision-fingerprint")
    artifact = ReliabilityEvidenceAdapter(type("Source", (), {"list_stored_reliability_decisions": lambda self, canonical_instrument_id, *, as_of: (envelope,)})()).artifacts(INSTRUMENT, as_of=T)[0]
    assert artifact.availability is expected
    assert f"RELIABILITY_STATUS_{status.value}" in artifact.warnings


def test_stored_integrity_is_referenced_and_future_integrity_is_excluded(tmp_path: Path) -> None:
    valid = HistoricalPriceIntegrity("valid", INSTRUMENT, T - timedelta(days=1), PriceAdjustmentBasis.RAW, HistoricalIntegrityStatus.PARTIAL, ("bar",), (), ("RAW_SERIES",))
    future = HistoricalPriceIntegrity("future", INSTRUMENT, T + timedelta(days=1), PriceAdjustmentBasis.RAW, HistoricalIntegrityStatus.INVALID, (), (), ("INVALID",))
    before = _builder(tmp_path, integrities=(valid, future)).build(INSTRUMENT, as_of=T)
    reference = _reference(before, IntelligenceEvidenceDomain.HISTORICAL_INTEGRITY)
    assert reference.availability is IntelligenceEvidenceAvailability.PARTIAL
    assert reference.artifact_ids == ("historical-integrity:valid",)


def test_non_company_artifact_order_reconstructs_deterministically_and_leaves_macro_news_technical_unavailable(tmp_path: Path) -> None:
    builder = _builder(tmp_path, taxonomy_values=(_classification(),), ticks=(_tick("tick"),))
    state = builder.build(INSTRUMENT, as_of=T)
    assert builder.reconstruct(INSTRUMENT, as_of=T, expected_state=state) == state
    assert all(_reference(state, domain).availability is IntelligenceEvidenceAvailability.UNAVAILABLE for domain in (IntelligenceEvidenceDomain.MACRO, IntelligenceEvidenceDomain.NEWS_CATALYSTS, IntelligenceEvidenceDomain.TECHNICAL))
    assert not any("candidate" in item.artifact_id for item in state.dependency_lineage)


def test_non_company_adapters_are_stored_only_and_do_not_embed_provider_or_action_execution() -> None:
    source = (Path(__file__).parents[2] / "app" / "intelligence" / "non_company_evidence.py").read_text(encoding="utf-8")
    assert not any(token in source for token in ("requests.", "urlopen", "httpx", "CREATE TABLE", "INSERT INTO", "PreBreakoutEngine", "DecisionScore", "SixGate", "Signal", "PaperTrade", "order("))
