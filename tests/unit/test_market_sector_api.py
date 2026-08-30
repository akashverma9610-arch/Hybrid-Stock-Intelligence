import inspect
from datetime import UTC, datetime
from decimal import Decimal

from fastapi.testclient import TestClient

from app.analysis.models import AnalysisStatus, MarketRegime, MarketRegimeResult
from app.api.dependencies import get_market_regime_query_service, get_sector_query_service
from app.api.main import create_app
from app.api.market_query import (
    SectorAnalysisQueryRecord,
    SnapshotMarketRegimeQueryService,
    SnapshotSectorQueryService,
)
from app.api.routes import market as market_routes
from app.api.schemas.market import MarketRegimeResponse, SectorListResponse, SectorResponse
from app.diagnostics.models import EvaluatedDiagnostic, EvaluationEligibility
from app.domain.models import DataQuality, DiagnosticResult, StrategyVersionReference


CALCULATED_AT = datetime(2026, 9, 1, 15, 30, tzinfo=UTC)
DATA_AS_OF = datetime(2026, 9, 1, 15, 15, tzinfo=UTC)
STRATEGY = StrategyVersionReference("market-api", "1")


def regime(*, status: AnalysisStatus = AnalysisStatus.VALID) -> MarketRegimeResult:
    classification = MarketRegime.BULL if status is AnalysisStatus.VALID else MarketRegime.INSUFFICIENT_DATA
    return MarketRegimeResult(
        "market-regime-api", "NIFTY50", STRATEGY, classification,
        ("benchmark_return=0.040000", "trend=uptrend"), ("nifty-bar-1", "nifty-bar-2"),
        "market-regime-v1", CALCULATED_AT, DATA_AS_OF, DataQuality.HIGH,
        .87 if status is AnalysisStatus.VALID else None, status, (),
    )


def sector(*, sector_id: str = "energy", phase: str = "ROTATING_IN", rank: int = 2,
           eligibility: EvaluationEligibility = EvaluationEligibility.ELIGIBLE) -> SectorAnalysisQueryRecord:
    diagnostic = DiagnosticResult(
        f"sector-{sector_id}", sector_id, "3", STRATEGY, phase, 3.5, .82,
        (f"evidence-{sector_id}",), (f"bar-{sector_id}",), CALCULATED_AT, DATA_AS_OF,
    )
    rotation = EvaluatedDiagnostic(
        diagnostic, 3, "sector-rotation-v1", eligibility, (),
        (("excess", "0.125"), ("classification", "observable price/RS proxy; inference only, not fund flow")),
    )
    return SectorAnalysisQueryRecord(
        sector_id, sector_id.title(), rotation, rank=rank, warnings=("PROXY_INFERENCE_ONLY",),
    )


def test_market_regime_maps_existing_enum_timestamps_confidence_and_provenance():
    value = regime()
    application = create_app(market_regime_query_service=SnapshotMarketRegimeQueryService(value))
    with TestClient(application) as client:
        response = client.get("/api/v1/market/regime")

    result = MarketRegimeResponse.model_validate(response.json())
    assert response.status_code == 200
    assert result.regime == MarketRegime.BULL.value
    assert result.calculated_at == CALCULATED_AT and result.data_as_of == DATA_AS_OF
    assert result.confidence == .87 and result.input_observation_ids == value.input_observation_ids
    assert response.json()["calculated_at"].endswith(("Z", "+00:00"))


def test_market_regime_unavailable_and_partial_status_are_safe_and_explicit():
    with TestClient(create_app(), raise_server_exceptions=False) as client:
        unavailable = client.get("/api/v1/market/regime")
    application = create_app(market_regime_query_service=SnapshotMarketRegimeQueryService(regime(status=AnalysisStatus.INSUFFICIENT_DATA)))
    with TestClient(application) as client:
        partial = client.get("/api/v1/market/regime")

    assert unavailable.status_code == 503
    assert unavailable.json()["error"]["code"] == "MARKET_REGIME_UNAVAILABLE"
    assert partial.status_code == 200
    assert "ANALYSIS_STATUS:insufficient_data" in partial.json()["warnings"]


def test_sector_list_detail_ordering_phase_and_numeric_fields_preserve_existing_records():
    first, second = sector(sector_id="energy", rank=2), sector(sector_id="banks", phase="ACCUMULATING", rank=1)
    application = create_app(sector_query_service=SnapshotSectorQueryService((first, second)))
    with TestClient(application) as client:
        listing = client.get("/api/v1/sectors")
        detail = client.get("/api/v1/sectors/energy")

    items = SectorListResponse.model_validate(listing.json()).sectors
    item = SectorResponse.model_validate(detail.json())
    assert listing.status_code == detail.status_code == 200
    assert tuple(value.sector_id for value in items) == ("energy", "banks")
    assert (item.phase, item.rank, item.relative_strength, item.score, item.confidence) == (
        "ROTATING_IN", 2, Decimal("0.125"), 3.5, .82,
    )
    assert detail.json()["relative_strength"] == "0.125"
    assert item.evidence_ids == ("evidence-energy",)


def test_empty_unknown_unavailable_and_stale_sector_paths_are_honest():
    with TestClient(create_app(sector_query_service=SnapshotSectorQueryService(())), raise_server_exceptions=False) as client:
        empty = client.get("/api/v1/sectors")
        unknown = client.get("/api/v1/sectors/unknown")
    with TestClient(create_app(), raise_server_exceptions=False) as client:
        unavailable = client.get("/api/v1/sectors")
    stale = sector(eligibility=EvaluationEligibility.INELIGIBLE_STALE_DATA)
    with TestClient(create_app(sector_query_service=SnapshotSectorQueryService((stale,)))) as client:
        stale_response = client.get("/api/v1/sectors/energy")

    assert empty.status_code == 200 and empty.json() == {"sectors": []}
    assert unknown.status_code == 404 and unknown.json()["error"]["code"] == "SECTOR_NOT_FOUND"
    assert unavailable.status_code == 503 and unavailable.json()["error"]["code"] == "SECTOR_ANALYSIS_UNAVAILABLE"
    assert "PROXY_INFERENCE_ONLY" in stale_response.json()["warnings"]
    assert "ANALYSIS_STATUS:ineligible_stale_data" in stale_response.json()["warnings"]


def test_query_dependencies_are_overridable_and_routes_are_read_only():
    regime_value, sector_value = regime(), sector()
    application = create_app()
    application.dependency_overrides[get_market_regime_query_service] = lambda: SnapshotMarketRegimeQueryService(regime_value)
    application.dependency_overrides[get_sector_query_service] = lambda: SnapshotSectorQueryService((sector_value,))
    before = regime_value, sector_value
    with TestClient(application) as client:
        assert client.get("/api/v1/market/regime").status_code == 200
        assert client.get("/api/v1/sectors").status_code == 200
        assert client.get("/api/v1/sectors/energy").status_code == 200
    assert (regime_value, sector_value) == before
    source = inspect.getsource(market_routes)
    assert "MarketRegimeEngine" not in source and "sector_rotation(" not in source
