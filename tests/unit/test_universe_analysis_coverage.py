from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.crowd.models import CrowdCategory, CrowdObservation, NewsEvent
from app.domain.models import (
    DataQuality, EvidenceType, Instrument, MarketObservation, ObservationKind,
    Provenance, ValidationResult, ValidationStatus,
)
from app.gates.engine import ExecutionGateConfig, GateInput, PortfolioExposure, SurveillanceObservation, TradeManagementPlan
from app.research.models import (
    Catalyst, CatalystClock, GuidanceItem, ResearchClaim, ResearchDocument, ResearchSourceType, SourceTier,
)
from app.storage.sqlite_core_api_snapshot_repository import SQLiteCoreApiSnapshotRepository
from app.storage.core_api_snapshot_repository import CoreApiSnapshotFamily
from app.universe_analysis.models import (
    CoverageDomain, CoverageDomainStatus, DiagnosticCompleteness, NseEquityInstrument, UniverseAnalysisStage,
)
from app.universe_analysis.service import (
    Canonical61DiagnosticRunner, CoreUniverseAnalysisStore, PortfolioUniverseRotationService,
    StockDiagnosticInputAssembler, UniverseAnalysisService, build_universe_snapshot,
)
from app.rotation.models import RotationConfig
from app.portfolio.models import (
    CashPosition, HoldingAnalytics, PortfolioDataStatus, PortfolioExposureSummary, PortfolioHolding,
    PortfolioRiskSummary, PortfolioSnapshot, PortfolioState,
)


T = datetime(2026, 8, 24, 12, tzinfo=UTC)


class StoredFacts:
    def __init__(self, values): self.values = tuple(values)
    def observations_as_of(self, at): return self.values


class StoredUniverse:
    def __init__(self, values): self.values = tuple(values)
    def instruments_as_of(self, at): return self.values


def _observation(identifier, instrument, kind, payload, at, *, source="stored-fixture"):
    return MarketObservation(identifier, Instrument(instrument, instrument, "NSE"), kind, payload,
                             Provenance(source, identifier, at, at, DataQuality.HIGH),
                             ValidationResult(ValidationStatus.VALID, T))


def _bars(instrument: str, closes: tuple[float, ...], *, start: datetime | None = None):
    start = start or T - timedelta(days=len(closes))
    return tuple(_observation(f"{instrument}-bar-{index}", instrument, ObservationKind.PRICE_BAR,
                              {"open": close - .2, "high": close + 1, "low": close - 1, "close": close, "volume": 100 + index * 5},
                              start + timedelta(days=index)) for index, close in enumerate(closes))


def _fundamentals(instrument: str):
    values = []
    for number in range(6):
        period_end = T - timedelta(days=365 * (6 - number))
        values.append(_observation(f"{instrument}-annual-{number}", instrument, ObservationKind.FUNDAMENTAL, {
            "period_type": "annual", "period_end": period_end, "publication_timestamp": period_end + timedelta(days=30),
            "revenue": 1000 + number * 100, "ebitda": 200 + number * 25, "pat": 120 + number * 15, "eps": 12 + number,
            "ebit": 180 + number * 20, "total_equity": 700 + number * 40, "total_debt": 120, "cash": 80,
            "interest_expense": 10, "operating_cash_flow": 160 + number * 15, "capex": 40, "receivables": 110,
            "cogs": 650, "inventory": 130, "payables": 95, "promoter_holding": 52 + number * .1,
            "promoter_pledge": 0, "fii_holding": 12 + number * .1, "dii_holding": 10 + number * .1,
            "mutual_fund_holding": 8 + number * .1, "order_book": 500 + number * 30, "order_inflow": 350,
            "shares_outstanding": 100, "forward_eps": 20, "configured_growth_rate": .12,
            "valuation_comparison_universe": "NSE", "total_assets": 1200, "current_liabilities": 300,
        }, period_end + timedelta(days=30)))
    for number in range(5):
        period_end = T - timedelta(days=90 * (5 - number))
        values.append(_observation(f"{instrument}-quarter-{number}", instrument, ObservationKind.FUNDAMENTAL, {
            "period_type": "quarterly", "period_end": period_end, "publication_timestamp": period_end + timedelta(days=20),
            "revenue": 300 + number * 20, "ebitda": 65 + number * 5, "pat": 35 + number * 3, "eps": 3 + number * .2,
            "promoter_holding": 52 + number * .1, "promoter_pledge": 0, "fii_holding": 12 + number * .1,
            "dii_holding": 10 + number * .1, "mutual_fund_holding": 8 + number * .1,
            "order_book": 500 + number * 30, "order_inflow": 350,
        }, period_end + timedelta(days=20)))
    return tuple(values)


def _research(instrument: str):
    published = T - timedelta(days=3)
    document = ResearchDocument(f"{instrument}-filing", instrument, ResearchSourceType.EXCHANGE_FILING, "NSE", "fixture", published, published,
                                "Stored filing", "fixture://filing", SourceTier.TIER_1_PRIMARY)
    claims = (
        ResearchClaim(f"{instrument}-moat-a", document.research_item_id, instrument, "switching_cost", "fixture://claim/a", EvidenceType.DATA, SourceTier.TIER_1_PRIMARY, .9, published, published),
        ResearchClaim(f"{instrument}-moat-b", document.research_item_id, instrument, "brand", "fixture://claim/b", EvidenceType.DATA, SourceTier.TIER_1_PRIMARY, .9, published, published),
    )
    guidance = GuidanceItem(f"{instrument}-guidance", document.research_item_id, "revenue", 100, "FY27", published, "reported guidance", .8, 110, "actual")
    catalyst = Catalyst(f"{instrument}-catalyst", document.research_item_id, "order_win", "reported order", published, CatalystClock.NEAR_TERM, .8, "high", "growth", "positive")
    crowd = (
        CrowdObservation(f"{instrument}-crowd-a", instrument, CrowdCategory.SOCIAL, "source-a", "tier_5", -.3, published, published, "stored", .8, 200),
        CrowdObservation(f"{instrument}-crowd-b", instrument, CrowdCategory.POSITIONING, "source-b", "tier_4", -.2, published, published, "stored", .8, 200),
        CrowdObservation(f"{instrument}-crowd-c", instrument, CrowdCategory.NEWS, "source-c", "tier_4", -.1, published, published, "stored", .8, 200),
    )
    event = NewsEvent(f"{instrument}-news", instrument, T - timedelta(days=8), "stored announcement", "positive", "fixture://news")
    return _observation(f"{instrument}-research", instrument, ObservationKind.RESEARCH, {
        "research_document": document, "research_claims": claims, "guidance": (guidance,), "catalysts": (catalyst,),
        "crowd_observations": crowd, "news_events": (event,),
    }, published)


def rich_observations(instrument: str = "CAND", *, include_context: bool = True):
    # A gentle advance with two pullbacks supplies the current configured
    # technical, volume and trade-structure evaluators without a second engine.
    stock = _bars(instrument, (100, 103, 101, 105, 104, 108, 107, 111, 110, 114, 116, 112))
    benchmark = _bars("NIFTY_50", (1000, 1005, 1010, 1018, 1020, 1028, 1035, 1040, 1048, 1055, 1060, 1068))
    sector = _bars("TECH", (500, 506, 515, 523, 530, 538, 548, 555, 564, 573, 584, 595))
    vix = _bars("INDIA_VIX", (15, 14.9, 14.8, 14.7, 14.6, 14.5, 14.4, 14.3, 14.2, 14.1, 14, 13.9))
    context = benchmark + sector + vix if include_context else ()
    return stock + context + _fundamentals(instrument) + (_research(instrument),)


def _instrument(identifier="CAND"):
    return NseEquityInstrument(identifier, identifier, "INEFIXTURE", "TECH", "Software", "ACTIVE", None, True, T, "OFFICIAL", main_board=True)


def _gate_config():
    return ExecutionGateConfig("fixture-gates-v1", Decimal("0"), "fixture-friction", None, False, 10, Decimal(".1"), Decimal(".1"), 2,
                               True, Decimal(".01"), 30, Decimal(".5"), Decimal(".5"), True, Decimal(".10"), Decimal(".30"), Decimal(".50"), 5, "fixture-heat-v1")


def _gate_input(instrument, evidence, score):
    return GateInput(score.id, score.final_score, evidence.snapshot.id, evidence.as_of,
                     surveillance=SurveillanceObservation(f"surveillance:{instrument.instrument_id}", T, "official", True, 0, 0, Decimal(".1")),
                     trade_plan=TradeManagementPlan(f"plan:{instrument.instrument_id}", Decimal(".5"), Decimal(".5"), True, True, "after T1", "structural", "fixture", "fixture-gates-v1"),
                     exposure=PortfolioExposure(Decimal("1000"), Decimal("10"), Decimal("10"), Decimal(".10"), Decimal(".20")),
                     earnings_scheduled_at=T + timedelta(days=14), earnings_schedule_verified_at=T)


def test_rich_stored_fixture_reaches_all_61_without_private_api_exposure() -> None:
    evidence = StockDiagnosticInputAssembler(StoredFacts(rich_observations())).assemble(_instrument(), T)
    result = Canonical61DiagnosticRunner().run(evidence)
    assert len(result.evaluations) == 61
    assert result.evaluated == 61, [(item.canonical_rule_id, item.record.result) for item in result.evaluations if item.eligibility.value != "eligible"]
    assert result.missing == 0 and result.completeness is DiagnosticCompleteness.COMPLETE


def test_coverage_preflight_is_persisted_and_missing_required_history_is_not_neutral(tmp_path) -> None:
    repository = SQLiteCoreApiSnapshotRepository(tmp_path / "coverage.sqlite")
    store = CoreUniverseAnalysisStore(repository)
    candidate = _instrument()
    universe = build_universe_snapshot(snapshot_id="universe-rich", as_of=T, source="OFFICIAL", instruments=(candidate,))
    store.save_universe_snapshot(universe)
    service = UniverseAnalysisService(universe=StoredUniverse((candidate,)), assembler=StockDiagnosticInputAssembler(StoredFacts(rich_observations())),
                                      runner=Canonical61DiagnosticRunner(), store=store, gate_config=_gate_config(), gate_input_factory=_gate_input, clock=lambda: T)
    requested = service.request(universe_id="NSE", universe_as_of=T, as_of=T, universe_snapshot_id=universe.snapshot_id)
    result = service.run_next_batch()
    assert result is not None and result.stage is UniverseAnalysisStage.CANDIDATES_MATERIALIZED
    coverage = store.coverage(requested.job_id)
    assert len(coverage) == 1 and coverage[0].complete
    assert {item.domain for item in coverage[0].domains} == set(CoverageDomain)
    assert all(item.status is CoverageDomainStatus.READY for item in coverage[0].domains)
    assert store.candidates(requested.job_id)[0].analysis_snapshot_id.startswith("universe-stock:")
    sparse_service = UniverseAnalysisService(universe=StoredUniverse((candidate,)), assembler=StockDiagnosticInputAssembler(StoredFacts(_bars("CAND", (1, 2, 3)))),
                                             runner=Canonical61DiagnosticRunner(), store=CoreUniverseAnalysisStore(SQLiteCoreApiSnapshotRepository(tmp_path / "sparse.sqlite")), clock=lambda: T)
    sparse_service.request(universe_id="NSE", universe_as_of=T, as_of=T)
    sparse = sparse_service.run_next_batch()
    assert sparse is not None and sparse.coverage_ready_count == 0 and sparse.coverage_partial_count == 1


def _portfolio() -> PortfolioSnapshot:
    holdings = tuple(
        PortfolioHolding(
            f"holding:{symbol}", symbol, Decimal("10"), Decimal("100"), Decimal("1000"), T, Decimal("0"), "TECH", None,
            None, True, Decimal("100"), f"mark:{symbol}", Decimal("1000"), Decimal("0"), Decimal("0"),
            HoldingAnalytics(symbol, T, T, f"score:{symbol}", Decimal("4.0"), "COMPLETE", .8, f"gate:{symbol}", "EXECUTABLE", (),
                             None, "VALID", "VALID", None, "INTACT", Decimal("90"), Decimal("120"), None, None, "TECH"),
            1, 1, Decimal("30"),
        )
        for symbol in ("HOLD_A", "HOLD_B")
    )
    return PortfolioSnapshot(
        "portfolio-rich", "portfolio", T, T, holdings, CashPosition(Decimal("100"), "INR", Decimal("0"), T),
        tuple(item.price_observation_id for item in holdings), Decimal("2100"), Decimal("0"), Decimal("0"), Decimal("0"),
        PortfolioExposureSummary({item.instrument_id: Decimal(".45") for item in holdings}, Decimal(".1"), {"TECH": Decimal(".9")}, 2, Decimal(".9")),
        PortfolioRiskSummary(Decimal("60"), Decimal("1"), PortfolioDataStatus.COMPLETE, {item.instrument_id: Decimal("30") for item in holdings}),
        PortfolioState.FULLY_INVESTED, PortfolioDataStatus.COMPLETE, "weighted-average-v1", "strategy:v1",
    )


def test_e2e_candidates_are_materialized_only_from_job_outputs_and_reused_by_rotation(tmp_path) -> None:
    repository = SQLiteCoreApiSnapshotRepository(tmp_path / "e2e.sqlite")
    store = CoreUniverseAnalysisStore(repository)
    instruments = tuple(_instrument(value) for value in ("HOLD_A", "HOLD_B", "C", "D", "E"))
    universe = build_universe_snapshot(snapshot_id="universe-e2e", as_of=T, source="OFFICIAL", instruments=instruments)
    store.save_universe_snapshot(universe)
    incomplete_e = tuple(item for item in rich_observations("E", include_context=False) if item.kind is not ObservationKind.RESEARCH)
    observations = rich_observations("HOLD_A") + tuple(
        item for symbol in ("HOLD_B", "C", "D") for item in rich_observations(symbol, include_context=False)
    ) + incomplete_e

    def gate_input(instrument, evidence, score):
        value = _gate_input(instrument, evidence, score)
        if instrument.instrument_id == "D":
            return replace(value, surveillance=replace(value.surveillance, circuit_limit=Decimal(".01")))
        return value

    service = UniverseAnalysisService(universe=StoredUniverse(instruments), assembler=StockDiagnosticInputAssembler(StoredFacts(observations)),
                                      runner=Canonical61DiagnosticRunner(), store=store, gate_config=_gate_config(), gate_input_factory=gate_input, clock=lambda: T)
    requested = service.request(universe_id="NSE", universe_as_of=T, as_of=T, batch_size=2, universe_snapshot_id=universe.snapshot_id)
    while service.run_next_batch() is not None:
        pass
    job = service.get_job(requested.job_id)
    candidates = store.candidates(job.job_id)
    assert job.stage is UniverseAnalysisStage.CANDIDATES_MATERIALIZED
    assert {item.instrument_id for item in candidates} == {item.instrument_id for item in instruments}
    qualified = tuple(item for item in candidates if item.qualification_status == "QUALIFIED")
    assert {item.instrument_id for item in qualified} >= {"C", "HOLD_A", "HOLD_B"}
    assert next(item for item in candidates if item.instrument_id == "D").qualification_status == "PARTIAL"
    incomplete = next(item for item in candidates if item.instrument_id == "E")
    assert incomplete.decision_score is not None and incomplete.qualification_status == "PARTIAL"
    assert all(item.analysis_snapshot_id.startswith("universe-stock:") and item.scorecard_id and item.confidence is not None for item in candidates)
    rotation = PortfolioUniverseRotationService(
        store=store,
        rotation_config=RotationConfig("rotation-rich", Decimal(".1"), .7, Decimal("2"), True, True, False, "friction-v1", 0, 0),
    ).evaluate(portfolio=_portfolio(), universe=universe, job=job, evaluated_at=T)
    evaluation = store._repository.get_snapshot(f"universe-rotation:{rotation.rotation_evaluation_id}").payload
    assert rotation.rotation_evaluation_id is not None
    assert evaluation.preferred_candidate_id == "C"
    assert all(item.candidate.instrument_id not in {"HOLD_A", "HOLD_B"} for item in evaluation.ranked_candidates)
    assert evaluation.context.candidates[0].decision_scorecard_id == next(item for item in qualified if item.instrument_id == "C").scorecard_id
    assert service.get_job(job.job_id).stage is UniverseAnalysisStage.COMPLETED
    assert PortfolioUniverseRotationService(store=store, rotation_config=RotationConfig("rotation-rich", Decimal(".1"), .7, Decimal("2"), True, True, False, "friction-v1", 0, 0)).evaluate(
        portfolio=_portfolio(), universe=universe, job=job, evaluated_at=T
    ) == rotation


def test_removing_a_required_domain_keeps_all_61_output_partial_not_neutral() -> None:
    observations = tuple(item for item in rich_observations() if item.kind is not ObservationKind.FUNDAMENTAL)
    result = Canonical61DiagnosticRunner().run(StockDiagnosticInputAssembler(StoredFacts(observations)).assemble(_instrument(), T))
    assert result.completeness is DiagnosticCompleteness.PARTIAL and result.missing > 0
    assert any(item.canonical_rule_id == 16 and item.record.result == "INSUFFICIENT_DATA" for item in result.evaluations)


def test_ownership_coverage_is_explicitly_missing_when_shareholding_fields_are_absent(tmp_path) -> None:
    observations = tuple(
        replace(item, payload={key: value for key, value in item.payload.items() if key not in {"promoter_holding", "promoter_pledge", "fii_holding", "dii_holding", "mutual_fund_holding"}})
        if item.kind is ObservationKind.FUNDAMENTAL else item
        for item in rich_observations()
    )
    candidate = _instrument()
    repository = SQLiteCoreApiSnapshotRepository(tmp_path / "ownership.sqlite")
    store = CoreUniverseAnalysisStore(repository)
    universe = build_universe_snapshot(snapshot_id="universe-ownership", as_of=T, source="OFFICIAL", instruments=(candidate,))
    store.save_universe_snapshot(universe)
    service = UniverseAnalysisService(universe=StoredUniverse((candidate,)), assembler=StockDiagnosticInputAssembler(StoredFacts(observations)),
                                      runner=Canonical61DiagnosticRunner(), store=store, clock=lambda: T)
    request = service.request(universe_id="NSE", universe_as_of=T, as_of=T, universe_snapshot_id=universe.snapshot_id)
    service.run_next_batch()
    coverage = store.coverage(request.job_id)[0]
    ownership = next(value for value in coverage.domains if value.domain is CoverageDomain.OWNERSHIP)
    assert ownership.status is CoverageDomainStatus.MISSING and ownership.warning


def test_job_stages_are_immutable_and_resume_does_not_repeat_coverage_or_candidates(tmp_path) -> None:
    candidate = _instrument()
    repository = SQLiteCoreApiSnapshotRepository(tmp_path / "resume.sqlite")
    store = CoreUniverseAnalysisStore(repository)
    universe = build_universe_snapshot(snapshot_id="universe-resume", as_of=T, source="OFFICIAL", instruments=(candidate,))
    store.save_universe_snapshot(universe)
    service = UniverseAnalysisService(universe=StoredUniverse((candidate,)), assembler=StockDiagnosticInputAssembler(StoredFacts(rich_observations())),
                                      runner=Canonical61DiagnosticRunner(), store=store, gate_config=_gate_config(), gate_input_factory=_gate_input, clock=lambda: T)
    request = service.request(universe_id="NSE", universe_as_of=T, as_of=T, batch_size=1, universe_snapshot_id=universe.snapshot_id)
    completed = service.run_next_batch()
    assert completed is not None and completed.stage is UniverseAnalysisStage.CANDIDATES_MATERIALIZED
    assert service.run_next_batch() is None
    stages = tuple(item.payload.stage for item in repository.list_snapshots(CoreApiSnapshotFamily.UNIVERSE_ANALYSIS_JOB, limit=100))
    assert stages == (UniverseAnalysisStage.UNIVERSE_READY, UniverseAnalysisStage.COVERAGE_PREFLIGHT,
                      UniverseAnalysisStage.ELIGIBILITY_COMPLETE, UniverseAnalysisStage.ANALYZING,
                      UniverseAnalysisStage.CANDIDATES_MATERIALIZED)
    assert len(store.coverage(request.job_id)) == 1 and len(store.candidates(request.job_id)) == 1
