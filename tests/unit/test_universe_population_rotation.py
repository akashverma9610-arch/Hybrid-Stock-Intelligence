from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from app.portfolio.models import (
    CashPosition, CashState, HoldingAnalytics, PortfolioDataStatus, PortfolioExposureSummary, PortfolioHolding,
    PortfolioRiskSummary, PortfolioSnapshot, PortfolioState,
)
from app.rotation.models import RotationConfig
from app.storage.sqlite_core_api_snapshot_repository import SQLiteCoreApiSnapshotRepository
from app.universe_analysis.importer import OfficialNseUniverseImporter
from app.universe_analysis.models import AnalyzedUniverseCandidate, NseEquityInstrument, UniverseAnalysisJob, UniverseAnalysisJobStatus
from app.universe_analysis.service import (
    CoreUniverseAnalysisStore, PortfolioUniverseRotationService, build_universe_snapshot,
)


T = datetime(2026, 8, 24, 10, tzinfo=UTC)


def test_official_csv_import_deduplicates_by_isin_and_excludes_unsupported_without_network(tmp_path) -> None:
    path = tmp_path / "official.csv"
    path.write_text("SYMBOL,ISIN,SECURITY_TYPE,LISTING_STATUS,TRADABLE,MAIN_BOARD,COMPANY_NAME\nOLD,INE000A,EQUITY,ACTIVE,true,true,Example Ltd\nNEW,INE000A,EQUITY,ACTIVE,true,true,Example Ltd Renamed\nETF,INE000B,ETF,ACTIVE,true,true,Fund\n", encoding="utf-8")
    store = CoreUniverseAnalysisStore(SQLiteCoreApiSnapshotRepository(tmp_path / "snapshots.sqlite"))
    report = OfficialNseUniverseImporter(store).import_csv(path, as_of=T, snapshot_id="nse-v1")
    assert report.accepted == 2 and report.duplicates == 1 and report.snapshot.excluded_count == 1
    values = store.instruments_as_of(T)
    assert len(values) == 2 and values[0].isin != values[1].isin
    assert report.snapshot.instrument_ids == ("NSE:INE000A",)


def _instrument(identifier: str) -> NseEquityInstrument:
    return NseEquityInstrument(identifier, identifier, None, "TECH", None, "ACTIVE", None, True, T, "OFFICIAL", security_type="EQUITY", main_board=True)


def _portfolio(*, cash_state: CashState = CashState.KNOWN) -> PortfolioSnapshot:
    analytics = HoldingAnalytics("HOLD", T, T, "score-h", Decimal("7.5"), "COMPLETE", .8, "gate-h", "EXECUTABLE", (), None, "VALID", "VALID", None, "INTACT", Decimal("90"), Decimal("120"), None, None, "TECH")
    holding = PortfolioHolding("h", "HOLD", Decimal("10"), Decimal("100"), Decimal("1000"), T, Decimal("0"), "TECH", None, None, True, Decimal("100"), "mark-h", Decimal("1000"), Decimal("0"), Decimal("0"), analytics, 1, 1, Decimal("30"))
    cash = CashPosition(
        None if cash_state is CashState.UNKNOWN else Decimal("100"), "INR", Decimal("0"), T, cash_state,
    )
    return PortfolioSnapshot("portfolio-v1", "portfolio", T, T, (holding,), cash, ("mark-h",), Decimal("1100"), Decimal("0"), Decimal("0"), Decimal("0"), PortfolioExposureSummary({"HOLD": Decimal(".9")}, Decimal(".1"), {"TECH": Decimal(".9")}, 1, Decimal(".9")), PortfolioRiskSummary(Decimal("30"), Decimal("1"), PortfolioDataStatus.COMPLETE, {"HOLD": Decimal("30")}), PortfolioState.FULLY_INVESTED, PortfolioDataStatus.COMPLETE, "weighted-average-v1", "strategy:v1")


def test_portfolio_universe_bridge_uses_existing_rotation_engine_and_excludes_self_candidates(tmp_path) -> None:
    store = CoreUniverseAnalysisStore(SQLiteCoreApiSnapshotRepository(tmp_path / "rotation.sqlite"))
    universe = build_universe_snapshot(snapshot_id="universe-v1", as_of=T, source="OFFICIAL", instruments=(_instrument("HOLD"), _instrument("CAND")))
    store.save_universe_snapshot(universe)
    job = UniverseAnalysisJob("job", 1, UniverseAnalysisJobStatus.COMPLETED, T, T, T, "NSE", T, T, 2, 10, 2, 2, 2, 0, 0, 0, (), "universe-v1")
    store.save_candidate(AnalyzedUniverseCandidate("self", "job", "universe-v1", "HOLD", "HOLD", "analysis-h", "score-h", Decimal("9.9"), .9, Decimal("3"), "EXECUTABLE", "TECH", None, "FRESH", "QUALIFIED", T, (), True, True, True, True, True, 1))
    store.save_candidate(AnalyzedUniverseCandidate("cand", "job", "universe-v1", "CAND", "CAND", "analysis-c", "score-c", Decimal("8.9"), .8, Decimal("2.4"), "EXECUTABLE", "HEALTH", None, "FRESH", "QUALIFIED", T, (), True, True, True, True, True, 1))
    config = RotationConfig("rotation-v1", Decimal(".8"), .7, Decimal("2"), True, True, False, "friction-v1", 1, 0)
    result = PortfolioUniverseRotationService(store=store, rotation_config=config).evaluate(portfolio=_portfolio(), universe=universe, job=job, evaluated_at=T)
    assert result.rotation_evaluation_id is not None and result.qualified_candidates == 1
    evaluation = store._repository.get_snapshot(f"universe-rotation:{result.rotation_evaluation_id}").payload
    assert evaluation.preferred_candidate_id == "CAND" and all(item.candidate.instrument_id != "HOLD" for item in evaluation.ranked_candidates)


def test_stale_holding_analysis_fails_closed_to_partial_rotation_snapshot(tmp_path) -> None:
    store = CoreUniverseAnalysisStore(SQLiteCoreApiSnapshotRepository(tmp_path / "stale.sqlite"))
    universe = build_universe_snapshot(snapshot_id="universe-v1", as_of=T, source="OFFICIAL", instruments=(_instrument("HOLD"),))
    job = UniverseAnalysisJob("job", 1, UniverseAnalysisJobStatus.COMPLETED, T, T, T, "NSE", T, T, 1, 10, 1, 1, 1, 0, 0, 0, (), "universe-v1")
    stale = _portfolio()
    from dataclasses import replace
    stale = replace(stale, holdings=(replace(stale.holdings[0], analytics=replace(stale.holdings[0].analytics, as_of_timestamp=T.replace(day=23))),))
    config = RotationConfig("rotation-v1", Decimal(".8"), .7, Decimal("2"), True, True, False, "friction-v1", 1, 0)
    result = PortfolioUniverseRotationService(store=store, rotation_config=config).evaluate(portfolio=stale, universe=universe, job=job, evaluated_at=T)
    assert result.rotation_evaluation_id is None and "STALE_OR_MISSING_HOLDING_ANALYSIS:HOLD" in result.warnings


def test_unknown_cash_does_not_short_circuit_governed_holding_candidate_comparison(tmp_path) -> None:
    store = CoreUniverseAnalysisStore(SQLiteCoreApiSnapshotRepository(tmp_path / "unknown-cash.sqlite"))
    universe = build_universe_snapshot(snapshot_id="universe-v1", as_of=T, source="OFFICIAL", instruments=(_instrument("HOLD"), _instrument("CAND")))
    store.save_universe_snapshot(universe)
    job = UniverseAnalysisJob("job", 1, UniverseAnalysisJobStatus.COMPLETED, T, T, T, "NSE", T, T, 2, 10, 2, 2, 2, 0, 0, 0, (), "universe-v1")
    store.save_candidate(AnalyzedUniverseCandidate("cand", "job", "universe-v1", "CAND", "CAND", "analysis-c", "score-c", Decimal("8.9"), .8, Decimal("2.4"), "EXECUTABLE", "HEALTH", None, "FRESH", "QUALIFIED", T, (), True, True, True, True, True, 1))
    config = RotationConfig("rotation-v1", Decimal(".8"), .7, Decimal("2"), True, True, False, "friction-v1", 1, 0)
    result = PortfolioUniverseRotationService(store=store, rotation_config=config).evaluate(
        portfolio=_portfolio(cash_state=CashState.UNKNOWN), universe=universe, job=job, evaluated_at=T,
    )
    evaluation = store._repository.get_snapshot(f"universe-rotation:{result.rotation_evaluation_id}").payload
    assert result.rotation_evaluation_id is not None and result.qualified_candidates == 1
    assert evaluation.context.cash_amount is None and evaluation.context.cash_state == "UNKNOWN"
    assert evaluation.decision.value == "COMPARISON_AVAILABLE_EXECUTION_BLOCKED"
    assert evaluation.comparisons[0].result.value == "ROTATE_CANDIDATE_PREFERRED"
