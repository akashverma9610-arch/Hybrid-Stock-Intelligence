import inspect
from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal

from fastapi.testclient import TestClient

from app.analysis.models import AnalysisStatus, MarketRegime, MarketRegimeResult
from app.api.dependencies import get_stock_analysis_query_service
from app.api.main import create_app
from app.api.routes import stocks as stock_routes
from app.api.schemas.stocks import StockAnalysisResponse
from app.api.stock_query import (
    AnalysisSectionQueryRecord,
    DiagnosticCoverageQueryRecord,
    SnapshotStockAnalysisQueryService,
    StockAnalysisQueryResult,
)
from app.diagnostics.models import EvaluatedDiagnostic, EvaluationEligibility
from app.domain.models import DataQuality, DiagnosticResult, StrategyVersionReference
from app.gates.engine import (
    ActionContext,
    ExecutionEligibility,
    ExecutionGateEvaluation,
    GateDecisionRecord,
    GateOutcome,
)
from app.scoring.engine import DecisionScorecard, ScoredComponent


ANALYZED_AT = datetime(2026, 10, 1, 15, 30, tzinfo=UTC)
DATA_AS_OF = datetime(2026, 10, 1, 15, 15, tzinfo=UTC)
STRATEGY = StrategyVersionReference("stock-api", "1")


def diagnostic(rule: int, result: str, *, score: float | None = None) -> EvaluatedDiagnostic:
    record = DiagnosticResult(
        f"diagnostic-{rule}", "COFORGE", str(rule), STRATEGY, result, score, .81,
        (f"evidence-{rule}",), (f"observation-{rule}",), ANALYZED_AT, DATA_AS_OF,
    )
    return EvaluatedDiagnostic(
        record, rule, "diagnostic-v1", EvaluationEligibility.ELIGIBLE, (),
        (("source_type", "INTERPRETATION"),),
    )


def market_regime() -> MarketRegimeResult:
    return MarketRegimeResult(
        "regime-1", "NIFTY50", STRATEGY, MarketRegime.SELECTIVE_BULL,
        ("trend=uptrend",), ("nifty-1",), "market-regime-v1", ANALYZED_AT,
        DATA_AS_OF, DataQuality.HIGH, .92, AnalysisStatus.VALID, (),
    )


def scorecard() -> DecisionScorecard:
    component = ScoredComponent(
        "market_regime", "COMPLETE", Decimal("8"), Decimal("0.10"), Decimal("0.80"),
        (1,), (), ("diagnostic-1",), ("evidence-1",), .81, (),
    )
    return DecisionScorecard(
        "scorecard-1", "COFORGE", STRATEGY, "registry-v1", "score-v1", DATA_AS_OF,
        ANALYZED_AT, (component,), Decimal("8.20"), "COMPLETE", .74, ("SCORECARD_AUDITABLE",),
    )


def gates() -> ExecutionGateEvaluation:
    decisions = tuple(
        GateDecisionRecord(f"gate-{index}", GateOutcome.PASS, f"canonical gate {index} passed", .8, (f"gate-evidence-{index}",), {"version": "v1"})
        for index in range(1, 7)
    )
    return ExecutionGateEvaluation(
        "gate-evaluation-1", "COFORGE", STRATEGY, "registry-v1", "score-v1", "gates-v1",
        "scorecard-1", "snapshot-1", ActionContext.FRESH_ENTRY, DATA_AS_OF, ANALYZED_AT,
        Decimal("8.20"), Decimal("0"), Decimal("8.20"), decisions, ExecutionEligibility.EXECUTABLE,
        (), (), ("GATES_AUDITABLE",), tuple(item for decision in decisions for item in decision.evidence_ids),
        ("diagnostic-1",), {"configuration": "gates-v1"},
    )


def stock_result(*, partial: bool = False) -> StockAnalysisQueryResult:
    items = (diagnostic(1, "SELECTIVE_BULL"), diagnostic(10, "HH_HL_BULLISH"), diagnostic(24, "ACCELERATING"))
    section = lambda item: AnalysisSectionQueryRecord("PARTIAL" if partial else "COMPLETE", (item,), ("SECTION_PARTIAL",) if partial else ())
    return StockAnalysisQueryResult(
        "COFORGE", "NSE", "Coforge Limited", "TECHNOLOGY", "IT Services", ANALYZED_AT, DATA_AS_OF,
        "PARTIAL" if partial else "COMPLETE", market_regime(), "ROTATING_IN", 3,
        DiagnosticCoverageQueryRecord(61, 45, 4, 8, 4, items), None if partial else scorecard(), None if partial else gates(),
        section(items[1]), section(items[2]), section(diagnostic(30, "CATALYST_PRESENT")),
        section(diagnostic(29, "REASONABLE")), section(diagnostic(45, "ACCEPTABLE")), section(diagnostic(7, "PROXY_BULLISH")),
        ("STALE_PRICE_DATA",) if partial else ("PROXY_NOT_DIRECT_INSTITUTIONAL_KNOWLEDGE",),
        ("snapshot-1", "scorecard-1", "gate-evaluation-1"),
    )


def test_stock_analysis_maps_existing_analysis_sections_without_recalculation():
    value = stock_result()
    with TestClient(create_app(stock_analysis_query_service=SnapshotStockAnalysisQueryService((value,)))) as client:
        response = client.get("/api/v1/stocks/coforge/analysis")

    result = StockAnalysisResponse.model_validate(response.json())
    assert response.status_code == 200
    assert result.identity.symbol == "COFORGE" and result.identity.exchange == "NSE"
    assert result.market_context.market_regime == MarketRegime.SELECTIVE_BULL.value
    assert (result.market_context.sector_phase, result.market_context.sector_rank) == ("ROTATING_IN", 3)
    assert result.analysis_coverage.status == "PARTIAL"
    assert result.decision.final_score == Decimal("8.20") and result.decision.confidence == .74
    assert result.execution_gates.overall_status == "EXECUTABLE"
    assert result.technical.status == "COMPLETE"
    assert result.fundamentals.status == "COMPLETE"
    assert result.research.status == "COMPLETE"
    assert result.valuation.status == "COMPLETE"
    assert result.trade_structure.status == "COMPLETE"
    assert result.liquidity.status == "COMPLETE"
    assert response.json()["decision"]["final_score"] == "8.20"
    assert response.json()["data"]["analysis_timestamp"].endswith(("Z", "+00:00"))


def test_stock_analysis_public_contract_hides_proprietary_diagnostic_inventory():
    value = stock_result()
    with TestClient(create_app(stock_analysis_query_service=SnapshotStockAnalysisQueryService((value,)))) as client:
        payload = client.get("/api/v1/stocks/COFORGE/analysis").json()

    serialized = str(payload)
    forbidden = (
        "diagnostic_id", "diagnostic_ids", "rule_id", "components", "weight",
        "weighted_contribution", "gate_id", "failed_gate_ids", "items",
        "HH_HL_BULLISH", "ACCELERATING", "61",
    )
    assert not any(value in serialized for value in forbidden)
    assert payload["decision"]["final_score"] == "8.20"
    assert payload["decision"]["confidence"] == .74
    assert payload["execution_gates"]["overall_status"] == "EXECUTABLE"


def test_partial_analysis_stale_warning_remains_visible_without_audit_provenance():
    value = stock_result(partial=True)
    with TestClient(create_app(stock_analysis_query_service=SnapshotStockAnalysisQueryService((value,)))) as client:
        response = client.get("/api/v1/stocks/COFORGE/analysis")

    assert response.status_code == 200
    assert response.json()["data"]["status"] == "PARTIAL"
    assert response.json()["decision"] is None and response.json()["execution_gates"] is None
    assert "STALE_PRICE_DATA" in response.json()["data"]["warnings"]
    assert "provenance_ids" not in response.json()["data"]


def test_stock_list_reads_existing_public_snapshots_only_and_keeps_empty_semantics():
    first = stock_result()
    second = replace(stock_result(), symbol="ALPHA", name="Alpha Limited", decision_scorecard=None)
    with TestClient(create_app(stock_analysis_query_service=SnapshotStockAnalysisQueryService((first, second)))) as client:
        response = client.get("/api/v1/stocks")
    assert response.status_code == 200
    assert [item["symbol"] for item in response.json()["items"]] == ["ALPHA", "COFORGE"]
    assert response.json()["items"][0]["latest_score"] is None
    assert {"diagnostics", "provenance_ids", "components", "gate_ids"}.isdisjoint(response.json()["items"][1])

    with TestClient(create_app(stock_analysis_query_service=SnapshotStockAnalysisQueryService(()))) as client:
        empty = client.get("/api/v1/stocks")
    assert empty.status_code == 200 and empty.json() == {"items": [], "total": 0}


def test_unknown_unavailable_and_invalid_stock_requests_fail_safely():
    value = stock_result()
    with TestClient(create_app(stock_analysis_query_service=SnapshotStockAnalysisQueryService((value,))), raise_server_exceptions=False) as client:
        unknown = client.get("/api/v1/stocks/UNKNOWN/analysis")
        invalid = client.get("/api/v1/stocks/COFORGE.NS/analysis")
    with TestClient(create_app(), raise_server_exceptions=False) as client:
        unavailable = client.get("/api/v1/stocks/COFORGE/analysis")

    assert unknown.status_code == 404 and unknown.json()["error"]["code"] == "STOCK_NOT_FOUND"
    assert invalid.status_code == 422 and invalid.json()["error"]["code"] == "INVALID_SYMBOL"
    assert unavailable.status_code == 503 and unavailable.json()["error"]["code"] == "STOCK_ANALYSIS_UNAVAILABLE"
    assert "Traceback" not in unavailable.text


def test_stock_analysis_dependency_override_and_reads_do_not_mutate_analysis():
    value = stock_result()
    application = create_app()
    application.dependency_overrides[get_stock_analysis_query_service] = lambda: SnapshotStockAnalysisQueryService((value,))
    before = value
    with TestClient(application) as client:
        assert client.get("/api/v1/stocks/coforge/analysis").status_code == 200
    assert value == before
    source = inspect.getsource(stock_routes)
    assert "build_scorecard" not in source and "ExecutionGateEngine" not in source
    assert "MarketRegimeEngine" not in source and ".calculate(" not in source
    assert "save_" not in source and "requests" not in source
