import inspect
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from fastapi.testclient import TestClient

from app.api.dependencies import get_benchmark_query_service, get_governance_query_service, get_performance_query_service
from app.api.main import create_app
from app.api.performance_governance_query import (
    BenchmarkQueryRecord, PerformanceQueryRecord, PromotionQueryRecord,
    SnapshotBenchmarkQueryService, SnapshotGovernanceQueryService, SnapshotPerformanceQueryService,
)
from app.api.routes import performance_governance as routes
from app.backtest.promotion import StrategyRollback
from app.historical.guard import manifest_fingerprint
from app.performance.models import BenchmarkComparison, PerformanceReport
from tests.unit.test_strategy_promotion_persistence import T, records


def _records():
    report = PerformanceReport(
        "report-api", "strategy/2.2", T, T + timedelta(days=10), "performance-v1", ("trade-1",), {
            "total_trades": 1, "closed_trades": 0, "win_rate": None, "expectancy": None,
            "average_r": None, "profit_factor": None, "total_return": Decimal("0"), "cagr": None,
            "max_drawdown": Decimal("0"), "volatility": None, "sharpe": None, "sortino": None,
            "turnover": Decimal("0"), "costs": Decimal("0"), "capital_efficiency": None,
            "sample_status": "VERY_LOW_SAMPLE",
        }, (), {}, ("ZERO_TRADE_SAMPLE",), T + timedelta(days=10), ("benchmark-run",), ("comparison-api",), (),
    )
    comparison = BenchmarkComparison(
        "nifty50_buy_hold", "v1", Decimal("0"), None, None, None, None, Decimal("0"), None,
        None, None, None, None, None, None, Decimal("0"), None, None, None,
        ("BENCHMARK_UNAVAILABLE",), ("SMALL_SAMPLE",), "INCONCLUSIVE",
    )
    policy, proposal, eligibility, review, version, activation = records()
    rollback = StrategyRollback("rollback", "prior", version.approved_id, review.review_id, activation.activation_id, T + timedelta(days=2), "return to approved version", manifest_fingerprint(x="rollback"))
    return (
        PerformanceQueryRecord(report, "backtest-test-run", "TEST"),
        BenchmarkQueryRecord("comparison-api", comparison, report.report_id, "TEST", report.start, report.end, "UNAVAILABLE", ("benchmark-input-1",)),
        version, activation, PromotionQueryRecord(proposal, eligibility, review, version, activation, rollback),
    )


def _app():
    performance, benchmark, version, activation, promotion = _records()
    return create_app(
        performance_query_service=SnapshotPerformanceQueryService((performance,)),
        benchmark_query_service=SnapshotBenchmarkQueryService((benchmark,)),
        governance_query_service=SnapshotGovernanceQueryService((version,), (promotion,), (activation, version)),
    ), performance, benchmark, version, activation, promotion


def test_performance_list_detail_metrics_zero_trade_and_filters_are_read_only():
    app, performance, *_ = _app()
    before = performance
    with TestClient(app) as client:
        listed = client.get("/api/v1/performance", params={"mode": "TEST", "limit": 1})
        detail = client.get("/api/v1/performance/report-api")
        empty = client.get("/api/v1/performance", params={"mode": "TRAIN"})
    assert listed.status_code == detail.status_code == 200 and empty.json()["items"] == []
    value = detail.json()
    assert value["mode"] == "TEST" and value["total_trades"] == 1 and value["win_rate"] is None
    assert value["total_return"] == "0" and value["costs"] == "0"
    assert "provenance_ids" not in value
    assert before == performance


def test_benchmarks_retain_unavailable_alignment_and_do_not_mislabel_test_as_train():
    app, _, benchmark, *_ = _app()
    with TestClient(app) as client:
        listed = client.get("/api/v1/benchmarks", params={"mode": "TEST"})
        detail = client.get("/api/v1/benchmarks/comparison-api")
        empty = client.get("/api/v1/benchmarks", params={"benchmark_id": "missing"})
    assert listed.status_code == detail.status_code == 200 and empty.json()["items"] == []
    value = detail.json()
    assert value["benchmark_id"] == "nifty50_buy_hold" and value["mode"] == "TEST"
    assert value["alignment_status"] == "UNAVAILABLE" and "BENCHMARK_UNAVAILABLE" in value["warnings"]
    assert value["strategy_return"] == "0" and benchmark.comparison == _records()[1].comparison
    assert "provenance_ids" not in value


def test_governance_distinguishes_proposed_human_approved_and_active_with_rollback():
    app, _, _, version, activation, promotion = _app()
    with TestClient(app) as client:
        versions = client.get("/api/v1/governance/strategy-versions")
        active = client.get("/api/v1/governance/active-strategy")
        promotions = client.get("/api/v1/governance/promotions")
        detail = client.get(f"/api/v1/governance/promotions/{promotion.proposal.proposal_id}")
    assert versions.status_code == active.status_code == promotions.status_code == detail.status_code == 200
    assert versions.json()["items"][0]["approved_id"] == version.approved_id
    assert active.json()["active"] and active.json()["activation_id"] == activation.activation_id
    value = detail.json()
    assert value["eligibility_status"] == "ELIGIBLE_FOR_REVIEW" and value["review_decision"] == "APPROVE"
    assert value["approved_version_id"] == version.approved_id and value["activation_id"] == activation.activation_id
    assert value["rollback_id"] == "rollback" and value["candidate_id"] == promotion.proposal.candidate_id


def test_inactive_empty_and_unavailable_governance_sources_fail_safely_without_latest_fallback():
    app = create_app(
        performance_query_service=SnapshotPerformanceQueryService(()),
        benchmark_query_service=SnapshotBenchmarkQueryService(()),
        governance_query_service=SnapshotGovernanceQueryService(),
    )
    with TestClient(app, raise_server_exceptions=False) as client:
        inactive = client.get("/api/v1/governance/active-strategy")
        versions = client.get("/api/v1/governance/strategy-versions")
        promotions = client.get("/api/v1/governance/promotions")
        missing = client.get("/api/v1/performance/missing")
    with TestClient(create_app(), raise_server_exceptions=False) as client:
        unavailable = client.get("/api/v1/benchmarks")
    assert inactive.status_code == 200 and inactive.json()["active"] is False and inactive.json()["active_version"] is None
    assert versions.json()["items"] == [] and promotions.json()["items"] == []
    assert missing.status_code == 404 and missing.json()["error"]["code"] == "PERFORMANCE_NOT_FOUND"
    assert unavailable.status_code == 503 and unavailable.json()["error"]["code"] == "BENCHMARKS_UNAVAILABLE"
    source = inspect.getsource(routes)
    assert not any(item in source for item in ("PerformanceEngine", "buy_hold", "StrategyPromotionService", "save_", "POST"))
