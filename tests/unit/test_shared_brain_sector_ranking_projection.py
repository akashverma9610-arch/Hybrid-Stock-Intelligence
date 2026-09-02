from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from app.intelligence.company_evidence import CompositeStoredIntelligenceSource
from app.intelligence.non_company_evidence import NonCompanyEvidenceStoredSource
from app.intelligence.unified_state import IntelligenceEvidenceAvailability, IntelligenceEvidenceDomain
from app.intelligence.unified_state_builder import StoredIntelligenceArtifact, UnifiedIntelligenceStateBuilder
from app.domain.models import FreshnessStatus
from app.intelligence.unified_state import IntelligenceInvalidationDomain
from app.market_data.current_sector_rotation import (
    CurrentSectorBreadthResult, CurrentSectorRankingArtifact, CurrentSectorRankingStore,
    CurrentSectorRelativeStrength, CurrentSectorRotationReport, SectorBackfillPlan,
)
from app.storage.sqlite_core_api_snapshot_repository import SQLiteCoreApiSnapshotRepository
from app.taxonomy.models import ClassificationSourceStatus, InstrumentTaxonomyClassification
from app.taxonomy.service import TaxonomySnapshotStore


T = datetime(2026, 9, 1, 12, tzinfo=UTC)


class _IdentitySource:
    def list_stored_intelligence_artifacts(self, instrument_id: str, *, as_of: datetime):
        return (StoredIntelligenceArtifact(
            instrument_id, IntelligenceEvidenceDomain.REFERENCE_DATA, f"identity:{instrument_id}",
            "identity-fingerprint", IntelligenceEvidenceAvailability.AVAILABLE, T - timedelta(days=2),
            T - timedelta(days=2), T - timedelta(days=2), FreshnessStatus.UNKNOWN, None, None, None,
            IntelligenceInvalidationDomain.REFERENCE_DATA,
        ),)


def _report() -> CurrentSectorRotationReport:
    def rs(sector: str) -> CurrentSectorRelativeStrength:
        return CurrentSectorRelativeStrength(sector, f"Nifty {sector}", 248, 0, 248, Decimal("1"), Decimal("2"), Decimal("3"), Decimal("3"), None)
    def breadth(sector: str, status: str, count: int, coverage: str) -> CurrentSectorBreadthResult:
        ready = status == "READY"
        return CurrentSectorBreadthResult(sector, f"Nifty {sector}", count, count if ready else count - 1, 1, Decimal("1"), count if ready else count - 2, 1, Decimal("1"), Decimal(coverage), status, None if ready else "CURRENT_CONSTITUENT_HISTORY_INCOMPLETE")
    return CurrentSectorRotationReport(
        T, T - timedelta(hours=2), 248,
        (rs("Metals & Mining"), rs("Healthcare"), rs("Media, Entertainment & Publication"), rs("Realty"), rs("Consumer Durables"), rs("Financial Services"), rs("Capital Goods")),
        (), (), (
            breadth("Metals & Mining", "READY", 10, "100"), breadth("Healthcare", "READY", 10, "100"),
            breadth("Media, Entertainment & Publication", "READY", 10, "100"), breadth("Realty", "READY", 10, "100"),
            breadth("Consumer Durables", "READY", 10, "100"), breadth("Financial Services", "READY", 10, "100"),
            breadth("Capital Goods", "PARTIAL", 50, "96"),
        ),
        ("Metals & Mining", "Healthcare", "Media, Entertainment & Publication", "Realty", "Consumer Durables", "Financial Services"),
        ("Metals & Mining", "Healthcare", "Media, Entertainment & Publication"),
        SectorBackfillPlan(False, (), 0, 0, 0, 0, (), 0, ()), 0, 0, 0, (),
    )


def _classification(instrument_id: str, sector: str) -> InstrumentTaxonomyClassification:
    return InstrumentTaxonomyClassification(
        f"taxonomy:{instrument_id}", instrument_id, "Industry", sector, "Super", "NSE_OFFICIAL",
        ClassificationSourceStatus.OFFICIAL, T - timedelta(days=2), None, T - timedelta(days=2),
        1.0, "v1", "nse:taxonomy",
    )


def _state(repository, taxonomy, rankings, instrument_id: str, *, as_of: datetime):
    source = CompositeStoredIntelligenceSource(
        _IdentitySource(), NonCompanyEvidenceStoredSource(taxonomy=taxonomy, sector_rankings=rankings),
    )
    return UnifiedIntelligenceStateBuilder(source).build(instrument_id, as_of=as_of)


def _sector(state):
    return next(value for value in state.evidence_references if value.domain is IntelligenceEvidenceDomain.SECTOR)


def test_stored_ranking_projects_rank_and_top3_without_recalculation(tmp_path: Path) -> None:
    repository = SQLiteCoreApiSnapshotRepository(tmp_path / "core.sqlite")
    rankings = CurrentSectorRankingStore(repository); artifact = rankings.save(CurrentSectorRankingArtifact.create(_report()))
    assert rankings.save(artifact) == artifact
    taxonomy = TaxonomySnapshotStore(repository)
    for identifier, sector in (("NSE:GLAND", "Healthcare"), ("NSE:ICICI", "Financial Services"), ("NSE:APAR", "Capital Goods")):
        taxonomy.save_classification(_classification(identifier, sector))

    gland, icici, apar = (_sector(_state(repository, taxonomy, rankings, identifier, as_of=T)) for identifier in ("NSE:GLAND", "NSE:ICICI", "NSE:APAR"))
    assert gland.availability is IntelligenceEvidenceAvailability.AVAILABLE
    assert {"SECTOR_RANK:2", "SECTOR_TOP3"} <= set(gland.warnings)
    assert icici.availability is IntelligenceEvidenceAvailability.AVAILABLE
    assert {"SECTOR_RANK:6", "SECTOR_NOT_TOP3"} <= set(icici.warnings)
    assert apar.availability is IntelligenceEvidenceAvailability.PARTIAL
    assert {"SECTOR_RANKING_UNAVAILABLE", "SECTOR_BREADTH_PARTIAL", "SECTOR_BREADTH_COVERAGE_96"} <= set(apar.warnings)

    before = _sector(_state(repository, taxonomy, rankings, "NSE:GLAND", as_of=T - timedelta(seconds=1)))
    assert before.availability is IntelligenceEvidenceAvailability.PARTIAL
    assert "CURRENT_SECTOR_RANKING_NOT_MATERIALIZED" in before.warnings
    source = (Path(__file__).parents[2] / "app" / "intelligence" / "non_company_evidence.py").read_text(encoding="utf-8")
    assert "mansfield_relative_strength" not in source and "PreBreakoutEngine" not in source


def test_missing_taxonomy_does_not_infer_a_sector(tmp_path: Path) -> None:
    repository = SQLiteCoreApiSnapshotRepository(tmp_path / "core.sqlite")
    rankings = CurrentSectorRankingStore(repository); rankings.save(CurrentSectorRankingArtifact.create(_report()))
    state = _state(repository, TaxonomySnapshotStore(repository), rankings, "NSE:DEEP", as_of=T)
    assert _sector(state).availability is IntelligenceEvidenceAvailability.UNAVAILABLE
