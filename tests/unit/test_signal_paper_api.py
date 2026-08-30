import inspect
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from fastapi.testclient import TestClient

from app.api.dependencies import get_paper_trade_query_service, get_signal_query_service
from app.api.main import create_app
from app.api.routes import signals as signal_routes
from app.api.signal_paper_query import (
    PaperTradeQueryRecord,
    SignalQueryRecord,
    SnapshotPaperTradeQueryService,
    SnapshotSignalQueryService,
)
from app.gates.engine import ExchangeCalendar
from app.paper.engine import PaperTradingEngine
from app.paper.models import (
    CreationPolicy,
    FillMethod,
    GapPolicy,
    InvalidationPolicy,
    PaperBar,
    PaperTradingConfig,
    SameBarPolicy,
    SizingBasis,
)
from app.performance.models import PerformanceReport
from tests.unit.test_signal_lifecycle import ASOF, create, plan


CONFIG = PaperTradingConfig(
    "paper-api-v1", CreationPolicy.GENERATED, FillMethod.MARKETABLE_TRIGGER_FILL,
    SameBarPolicy.CONSERVATIVE_STOP_FIRST, GapPolicy.MARKET_OPEN, SizingBasis.UNIT_BASIS,
    Decimal("0"), Decimal("0"), "cost-api-v1", Decimal("0"), Decimal("0.5"), Decimal("0.5"),
    True, InvalidationPolicy.EXIT_ON_INVALIDATION, 3, 5, "daily",
)


def _records():
    signal, _ = create()
    engine = PaperTradingEngine(CONFIG, ExchangeCalendar("nse-api", frozenset()))
    trade = engine.create(signal, plan(), instrument_id="COFORGE", generated_at=ASOF)
    bars = (
        PaperBar("entry", ASOF, ASOF, Decimal("100"), Decimal("107"), Decimal("100"), Decimal("106"), "daily"),
        PaperBar("exit", ASOF + timedelta(days=1), ASOF + timedelta(days=1), Decimal("106"), Decimal("126"), Decimal("105"), Decimal("125"), "daily"),
        PaperBar("target", ASOF + timedelta(days=2), ASOF + timedelta(days=2), Decimal("125"), Decimal("136"), Decimal("120"), Decimal("135"), "daily"),
    )
    _, fills, outcome = engine.simulate(trade, bars, ASOF + timedelta(days=2))
    signal_record = SignalQueryRecord(signal, "NSE", plan(), Decimal("9.00"), "EXECUTABLE", ("GATES_AUDITABLE",), ("gate-evidence-1",))
    completed = PaperTradeQueryRecord(trade, "NSE", outcome, tuple(fills), ("paper-reference-1",))
    active = PaperTradeQueryRecord(
        trade.__class__(
            "paper-active", trade.source_signal_id, "INFY", trade.strategy_version, trade.registry_version,
            trade.scoring_configuration_version, trade.gate_configuration_version, trade.rotation_configuration_version,
            trade.signal_configuration_version, trade.paper_configuration_version, trade.portfolio_context_reference,
            trade.created_at, trade.as_of_timestamp, trade.entry_type, trade.planned_entry, trade.entry_zone_low,
            trade.entry_zone_high, trade.structural_stop, trade.target_1, trade.target_2, trade.extended_target,
            trade.initial_risk_reward, trade.decision_score, trade.data_confidence, trade.market_regime, trade.sector,
            trade.catalyst, trade.catalyst_clock, trade.trading_thesis_reference, trade.investment_thesis_reference,
            trade.invalidation_reference, trade.gate_status, trade.rotation_context, trade.warnings,
        ), "NSE", None, (), ("paper-reference-active",),
    )
    report = PerformanceReport(
        "performance-api-1", trade.strategy_version, ASOF, ASOF + timedelta(days=2), "performance-api-v1",
        (trade.paper_trade_id,), {
            "sample_status": "VERY_LOW_SAMPLE", "total_trades": 1, "closed_trades": 1, "open_trades": 0,
            "win_rate": Decimal("1"), "loss_rate": Decimal("0"), "expectancy": outcome.net_pnl,
            "average_r": outcome.r_multiple, "profit_factor": None, "max_drawdown": Decimal("0"),
            "sharpe": None, "sortino": None, "volatility": None, "costs": outcome.costs,
            "capital_efficiency": Decimal("0.02"),
        }, (), {}, ("SMALL_SAMPLE",), ASOF + timedelta(days=2), ("benchmark-run-1",), ("comparison-1",),
    )
    return signal_record, completed, active, report


def _client():
    signal, completed, active, report = _records()
    app = create_app(
        signal_query_service=SnapshotSignalQueryService((signal,)),
        paper_trade_query_service=SnapshotPaperTradeQueryService((completed, active), (report,)),
    )
    return app, signal, completed, active, report


def test_signal_list_detail_filters_pagination_and_decimal_mapping():
    app, signal, *_ = _client()
    with TestClient(app) as client:
        listed = client.get("/api/v1/signals", params={"symbol": "stock", "status": "WAITING_FOR_TRIGGER", "limit": 1})
        detail = client.get(f"/api/v1/signals/{signal.signal.signal_id}")
        empty = client.get("/api/v1/signals", params={"symbol": "MISSING"})

    assert listed.status_code == 200 and listed.json()["total"] == 1
    value = detail.json()
    assert detail.status_code == 200 and value["lifecycle_status"] == "WAITING_FOR_TRIGGER"
    assert value["decision_score"] == "9.00" and value["confidence"] == signal.signal.signal_confidence
    assert value["gate"]["eligibility"] == "EXECUTABLE" and value["trade_structure"]["planned_entry"] == "105"
    assert value["trade_structure"]["risk_reward_t1"] == "2" and value["generated_at"].endswith(("Z", "+00:00"))
    assert empty.json()["items"] == []
    assert not {"diagnostic_ids", "decision_scorecard_id", "evidence_ids", "rationale_references", "provenance_ids"}.intersection(value)
    assert not {"evaluation_id", "evidence_ids"}.intersection(value["gate"])


def test_paper_trade_list_detail_partial_outcome_and_stored_performance():
    app, _, completed, active, _ = _client()
    with TestClient(app) as client:
        listed = client.get("/api/v1/paper-trades", params={"status": "CLOSED_TARGET", "limit": 1})
        detail = client.get(f"/api/v1/paper-trades/{completed.trade.paper_trade_id}")
        partial = client.get(f"/api/v1/paper-trades/{active.trade.paper_trade_id}")
        performance = client.get("/api/v1/paper-trades/performance")

    assert listed.status_code == 200 and listed.json()["total"] == 1
    value = detail.json()
    assert value["lifecycle_status"] == "CLOSED_TARGET" and value["mfe"] is not None and value["mae"] is not None
    assert value["realized_r"] is not None and value["entry_price"] == "106" and value["exit_reason"] == "CLOSED_TARGET"
    assert partial.status_code == 200 and partial.json()["lifecycle_status"] == "CREATED"
    assert partial.json()["exit_price"] is None and partial.json()["realized_r"] is None
    assert performance.status_code == 200 and performance.json()["total_trades"] == 1
    assert performance.json()["average_r"] == value["realized_r"]
    assert not {"source_signal_id", "source_bar_ids", "provenance_ids"}.intersection(value)
    assert "provenance_ids" not in performance.json()


def test_signal_paper_not_found_unavailable_overrides_and_reads_do_not_mutate_records():
    app, signal, completed, active, report = _client()
    before = (signal, completed, active, report)
    with TestClient(app, raise_server_exceptions=False) as client:
        signal_missing = client.get("/api/v1/signals/missing")
        paper_missing = client.get("/api/v1/paper-trades/missing")
    unavailable = create_app()
    unavailable.dependency_overrides[get_signal_query_service] = lambda: SnapshotSignalQueryService(())
    unavailable.dependency_overrides[get_paper_trade_query_service] = lambda: SnapshotPaperTradeQueryService(())
    with TestClient(unavailable, raise_server_exceptions=False) as client:
        no_signals = client.get("/api/v1/signals")
        no_trades = client.get("/api/v1/paper-trades")
        no_performance = client.get("/api/v1/paper-trades/performance")

    assert signal_missing.status_code == 404 and signal_missing.json()["error"]["code"] == "SIGNAL_NOT_FOUND"
    assert paper_missing.status_code == 404 and paper_missing.json()["error"]["code"] == "PAPER_TRADE_NOT_FOUND"
    assert no_signals.status_code == 200 and no_signals.json()["items"] == []
    assert no_trades.status_code == 200 and no_trades.json()["items"] == []
    assert no_performance.status_code == 503 and no_performance.json()["error"]["code"] == "PERFORMANCE_UNAVAILABLE"
    assert before == (signal, completed, active, report)


def test_signal_paper_routes_are_read_only_adapters_without_execution_formulas():
    source = inspect.getsource(signal_routes)
    forbidden = ("SignalOrchestrator", "PaperTradingEngine", ".simulate(", "PerformanceEngine", "r_multiple", "net_pnl")
    assert not any(item in source for item in forbidden)
    assert "post" not in source.lower() and "/execute" not in source
