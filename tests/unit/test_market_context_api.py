from datetime import UTC, datetime, timedelta
from decimal import Decimal
import inspect

from fastapi.testclient import TestClient

from app.api.main import create_app
from app.api.market_context_query import (
    BreadthQueryRecord, SnapshotBreadthQueryService, SnapshotCrisisQueryService,
    SnapshotMarketExtremesQueryService,
)
from app.api.routes import market as market_routes
from app.crisis.engine import CrisisMarketDislocationEngine
from app.crisis.extremes import MarketExtremesEngine
from app.crisis.models import (
    CrisisAssessmentInput, CrisisFactor, CrisisFactorSignal, CrisisPolicySettings,
    MarketExtremeLevel, MarketStatus, UpsideExcessAssessmentInput,
    UpsideExcessFactor, UpsideExcessFactorSignal, UpsideExcessPolicySettings,
)
from app.domain.models import DataQuality
from app.historical.models import InstrumentLifecycle, UniverseMembership
from app.market_data.aggregation import BreadthAggregator, MarketUniverse
from app.market_data.models import (
    CanonicalQuote, Exchange, FreshnessAssessment, FreshnessState,
    InstrumentIdentity, InstrumentType, MarketDataProvenance, MarketSessionState,
)
from app.storage.core_api_snapshot_repository import CoreApiSnapshot, CoreApiSnapshotFamily
from app.storage.sqlite_core_api_snapshot_repository import SQLiteCoreApiSnapshotRepository

T = datetime(2026, 8, 25, 10, tzinfo=UTC)
PROVENANCE = MarketDataProvenance("FIXTURE", None, T, T, T, "v1")


def _quote(symbol: str, price: str, previous: str) -> CanonicalQuote:
    identity = InstrumentIdentity(symbol, Exchange.NSE, symbol, None, None, None, InstrumentType.NSE_EQUITY, symbol)
    return CanonicalQuote(
        f"quote-{symbol}", identity, Decimal(price), Decimal(previous), None, None, None, 100,
        None, None, None, None, None, None, None, PROVENANCE,
        FreshnessAssessment(FreshnessState.FRESH, T, T, timedelta(), timedelta(minutes=1), MarketSessionState.OPEN), DataQuality.HIGH,
    )


def _breadth_record() -> BreadthQueryRecord:
    universe = MarketUniverse("NIFTY_TEST", "v1", tuple(
        UniverseMembership(f"member-{symbol}", symbol, "NIFTY_TEST", T - timedelta(days=1), None, T - timedelta(days=1), "fixture", "fixture", InstrumentLifecycle.ACTIVE)
        for symbol in ("A", "B", "C")
    ))
    breadth, participation = BreadthAggregator().aggregate(
        universe, {"A": _quote("A", "101", "100"), "B": _quote("B", "99", "100"), "C": _quote("C", "100", "100")}, data_as_of=T, provenance=PROVENANCE,
    )
    return BreadthQueryRecord(breadth, participation, T, "cycle-safe")


def _extremes():
    policy = UpsideExcessPolicySettings("up-v1", 2, Decimal(".2"), Decimal(".4"), Decimal(".6"), Decimal(".8"), 2, 3, 2, .49)
    signal = lambda factor: UpsideExcessFactorSignal(factor, True, True, Decimal(".9"), .9, T, T)
    return MarketExtremesEngine(policy).assess_upside(UpsideExcessAssessmentInput(
        "extremes-1", MarketExtremeLevel.MARKET, "NIFTY_TEST", None, T, T,
        (signal(UpsideExcessFactor.PRICE_ACCELERATION), signal(UpsideExcessFactor.VALUATION_EXPANSION), signal(UpsideExcessFactor.RETAIL_PARTICIPATION_PROXY)), (),
    ))


def _crisis():
    policy = CrisisPolicySettings("crisis-v1", 2, Decimal(".25"), Decimal(".5"), Decimal(".8"), Decimal(".95"), 2, 2, .49)
    signals = (
        CrisisFactorSignal(CrisisFactor.MARKET_BREADTH, True, True, Decimal(".6"), .9, T, T),
        CrisisFactorSignal(CrisisFactor.ATR_EXPANSION, True, True, Decimal(".6"), .9, T, T),
    )
    return CrisisMarketDislocationEngine(policy).assess(CrisisAssessmentInput("crisis-1", "NIFTY_TEST", None, T, T, MarketStatus.TRADING_NORMAL, signals, ()))


def _app():
    return create_app(
        breadth_query_service=SnapshotBreadthQueryService(_breadth_record()),
        market_extremes_query_service=SnapshotMarketExtremesQueryService(_extremes()),
        crisis_query_service=SnapshotCrisisQueryService(_crisis()),
    )


def test_market_context_public_models_are_distilled_read_only_and_have_no_private_fields():
    with TestClient(_app()) as client:
        breadth = client.get("/api/v1/market/breadth")
        extremes = client.get("/api/v1/market/extremes")
        crisis = client.get("/api/v1/market/crisis")
    assert breadth.status_code == extremes.status_code == crisis.status_code == 200
    assert breadth.json()["advances"] == 1 and breadth.json()["declines"] == 1
    assert breadth.json()["participation_state"] == "COMPLETE" and breadth.json()["cycle_reference"] == "cycle-safe"
    assert extremes.json()["market_state"] == "EUPHORIA" and extremes.json()["top_confirmed"] is False
    assert crisis.json()["state"] == "STRESS"
    forbidden = {"evidence_ids", "provenance_ids", "diagnostic_ids", "factor_weights", "thresholds", "gate_ids", "supporting_factors"}
    assert not forbidden.intersection(breadth.json())
    assert not forbidden.intersection(extremes.json())
    assert not forbidden.intersection(crisis.json())
    source = inspect.getsource(market_routes).lower()
    assert "@market_router.post" not in source and "@market_router.put" not in source and "@market_router.delete" not in source


def test_market_context_no_stored_data_is_unavailable_not_normal():
    with TestClient(create_app(), raise_server_exceptions=False) as client:
        for path, code in (("/api/v1/market/breadth", "MARKET_BREADTH_UNAVAILABLE"), ("/api/v1/market/extremes", "MARKET_EXTREMES_UNAVAILABLE"), ("/api/v1/market/crisis", "MARKET_CRISIS_UNAVAILABLE")):
            result = client.get(path)
            assert result.status_code == 503 and result.json()["error"]["code"] == code


def test_market_context_repository_reads_frozen_snapshots_without_recomputation(tmp_path):
    repository = SQLiteCoreApiSnapshotRepository(tmp_path / "market-context.sqlite")
    record = _breadth_record()
    repository.save_snapshot(CoreApiSnapshot("runtime-breadth", CoreApiSnapshotFamily.MARKET_REGIME, "v1", "runtime-market-state-v1", "fp-breadth", T, {"cycle_id": "cycle-frozen", "data_as_of": T, "breadth": record.breadth, "participation": record.participation}))
    repository.save_snapshot(CoreApiSnapshot("frozen-extremes", CoreApiSnapshotFamily.UPSIDE_EXCESS_ASSESSMENT, "v1", "upside-v1", "fp-extremes", T, _extremes()))
    repository.save_snapshot(CoreApiSnapshot("frozen-crisis", CoreApiSnapshotFamily.CRISIS_ASSESSMENT, "v1", "crisis-v1", "fp-crisis", T, _crisis()))
    with TestClient(create_app(core_api_snapshot_repository=repository)) as client:
        breadth, extremes, crisis = (client.get(path) for path in ("/api/v1/market/breadth", "/api/v1/market/extremes", "/api/v1/market/crisis"))
    assert breadth.json()["cycle_reference"] == "cycle-frozen"
    assert extremes.json()["market_state"] == "EUPHORIA" and crisis.json()["state"] == "STRESS"
