from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from app.execution_simulation.service import ExecutionFeasibility, ExecutionFeasibilityStatus
from app.intelligence.company_sensitivity.service import MacroEarningsTransmission
from app.intelligence.sector_economics.service import SensitivityDirection, SensitivityMagnitude
from app.storage.core_api_snapshot_repository import CoreApiSnapshotFamily
from app.storage.sqlite_core_api_snapshot_repository import SQLiteCoreApiSnapshotRepository
from app.strategies.common.models import CandidateStatus, StrategyFamily, StrategyOutcomeAttribution
from app.strategies.common.store import StrategySnapshotStore
from app.strategies.inflection.service import InflectionConfig, InflectionEngine, InflectionInput
from app.strategies.pre_breakout.service import (
    PreBreakoutConfig, PreBreakoutEngine, PreBreakoutInput, SectorBreadth,
    SectorRelativeStrength, mansfield_relative_strength,
)
from tests.fixtures.analytical_observations import STRATEGY_REFERENCE, bars, snapshot


UTC = timezone.utc
AS_OF = datetime(2026, 8, 20, tzinfo=UTC)


def _pre_input(**overrides) -> PreBreakoutInput:
    data = dict(
        candidate_id="pre-1", instrument_id="NSE:ABC", sector="Dynamic sector", scan_as_of=AS_OF,
        universe_snapshot_id="universe-as-of", evidence_ids=("bar-1", "delivery-1"), bbw_percentile=Decimal("9"),
        atr_recent=(Decimal("2"),) * 5, atr_prior=(Decimal("3"),) * 5,
        consolidation_volumes=(Decimal("40"), Decimal("45")), volume_sma20=Decimal("100"), delivery_pct=Decimal("61"),
        price=Decimal("95"), high_52_week=Decimal("100"), rsi14=Decimal("60"), structural_resistance=Decimal("100"),
        structural_invalidation=Decimal("93"), realistic_target=Decimal("122"), sector_evidence_ids=("sector-rs-1",),
    )
    data.update(overrides)
    return PreBreakoutInput(**data)


def _transmission(direction: SensitivityDirection = SensitivityDirection.POSITIVE) -> MacroEarningsTransmission:
    return MacroEarningsTransmission("transmission-1", "NSE:ABC", ("impact-1",), "profile-1", direction, direction,
                                     direction, direction, SensitivityMagnitude.MODERATE, "12M", 0.8, AS_OF, ("macro-1",))


def _inflection_input(**overrides) -> InflectionInput:
    data = dict(
        candidate_id="inflection-1", instrument_id="NSE:ABC", sector="Derived sector", scan_as_of=AS_OF,
        universe_snapshot_id="universe-as-of", evidence_ids=("fact-1", "ownership-1"), market_cap_crore=Decimal("5000"),
        roce_pct=Decimal("16"), debt_equity=Decimal("0.7"), gross_block_current=Decimal("116"), gross_block_prior_year=Decimal("100"),
        opm_current_pct=Decimal("12"), opm_prior_year_pct=Decimal("10"), fii_current_pct=Decimal("6"),
        fii_prior_two_quarters_pct=Decimal("5"), dii_current_pct=Decimal("4"), dii_prior_two_quarters_pct=Decimal("4"),
        promoter_pledge_current_pct=Decimal("0"), promoter_pledge_prior_pct=Decimal("0"), theme_evidence_ids=("sector-impact-1",),
        company_transmissions=(_transmission(),), catalyst_evidence_ids=("catalyst-1",),
    )
    data.update(overrides)
    return InflectionInput(**data)


def test_mansfield_formula_is_exact_and_future_bars_do_not_change_earlier_slice():
    sector = tuple(Decimal("100") + Decimal(index) for index in range(120))
    benchmark = tuple(Decimal("100") + Decimal(index) / Decimal("2") for index in range(120))
    value = mansfield_relative_strength(sector_prices=sector, benchmark_prices=benchmark, lookback=20)
    line = tuple(a / b for a, b in zip(sector, benchmark, strict=True))
    expected = Decimal("100") * (line[-1] / (sum(line[-20:], Decimal("0")) / Decimal("20")) - Decimal("1"))
    assert value == expected
    assert mansfield_relative_strength(sector_prices=sector + (Decimal("1000"),), benchmark_prices=benchmark + (Decimal("1"),), lookback=20) != value
    assert mansfield_relative_strength(sector_prices=sector, benchmark_prices=benchmark, lookback=20) == value
    assert mansfield_relative_strength(sector_prices=sector, benchmark_prices=benchmark, lookback=60) is not None
    assert mansfield_relative_strength(sector_prices=sector, benchmark_prices=benchmark, lookback=120) is not None


def test_sector_selection_is_configured_and_lexicographic_without_sector_names():
    engine = PreBreakoutEngine()
    a = SectorRelativeStrength("A", AS_OF, Decimal("1"), Decimal("2"), Decimal("3"), ("a",))
    b = SectorRelativeStrength("B", AS_OF, Decimal("2"), Decimal("1"), Decimal("1"), ("b",))
    breadth_a = SectorBreadth("A", AS_OF, "u", Decimal("60"), Decimal("55"), 2, ("x", "y"))
    breadth_b = SectorBreadth("B", AS_OF, "u", Decimal("50"), Decimal("50"), 2, ("z", "q"))
    scan = engine.sector_scan(scan_id="scan", as_of=AS_OF, values=((a, breadth_a), (b, breadth_b)), config=PreBreakoutConfig(top_sector_count=1))
    assert scan.selected_sectors == ("B",)
    assert scan.breadth[0].membership_snapshot_id == "u"


@pytest.mark.parametrize(("field", "value", "warning"), [
    ("bbw_percentile", Decimal("11"), "BBW_FILTER_FAILED"),
    ("atr_recent", (Decimal("4"),) * 5, "ATR_CONTRACTION_FILTER_FAILED"),
    ("consolidation_volumes", (Decimal("51"),), "QUIET_CONSOLIDATION_VOLUME_FILTER_FAILED"),
    ("delivery_pct", Decimal("60"), "DELIVERY_FILTER_FAILED"),
    ("price", Decimal("92"), "HIGH_PROXIMITY_FILTER_FAILED"),
    ("rsi14", Decimal("66"), "RSI14_FILTER_FAILED"),
])
def test_pre_breakout_each_default_filter_fails_explicitly(field, value, warning):
    result = PreBreakoutEngine().evaluate(_pre_input(**{field: value}), config=PreBreakoutConfig())
    assert result.status is CandidateStatus.SETUP_REJECTED
    assert warning in result.warnings


def test_pre_breakout_preserves_seven_percent_structural_stop_and_rejects_realistic_low_rr():
    structural = PreBreakoutEngine().evaluate(_pre_input(structural_resistance=Decimal("100"), structural_invalidation=Decimal("93"), realistic_target=Decimal("122")), config=PreBreakoutConfig())
    assert structural.status is CandidateStatus.CANDIDATE_GENERATED
    assert structural.structural_stop == Decimal("93")
    low_rr = PreBreakoutEngine().evaluate(_pre_input(structural_resistance=Decimal("100"), structural_invalidation=Decimal("95"), realistic_target=Decimal("112")), config=PreBreakoutConfig())
    assert low_rr.status is CandidateStatus.SETUP_REJECTED
    assert low_rr.realistic_target == Decimal("112")
    assert low_rr.reward_risk == Decimal("2.4")


def test_pre_breakout_delivery_missing_is_partial_and_execution_rejection_stays_separate():
    partial = PreBreakoutEngine().evaluate(_pre_input(delivery_pct=None), config=PreBreakoutConfig())
    assert partial.status is CandidateStatus.PARTIAL
    assert "DELIVERY_DATA_UNAVAILABLE" in partial.warnings
    feasibility = ExecutionFeasibility(ExecutionFeasibilityStatus.SETUP_VALID_EXECUTION_REJECTED, Decimal(".1"), Decimal(".1"), Decimal(".01"), False, Decimal("0"), ("EXECUTION_NOT_FEASIBLE",))
    result = PreBreakoutEngine().evaluate(_pre_input(execution_feasibility=feasibility), config=PreBreakoutConfig())
    assert result.status is CandidateStatus.SETUP_VALID_EXECUTION_REJECTED
    assert result.setup_quality.value == Decimal("100")


def test_pre_breakout_consumes_the_canonical_bbw_percentile_from_the_technical_engine():
    closes = [100 + ((index % 11) - 5) * (3 if index < 119 else 0.1) for index in range(139)]
    technical_snapshot = snapshot(bars("NSE:ABC", closes))
    value = PreBreakoutEngine().evaluate_with_canonical_bbw(
        _pre_input(bbw_percentile=None, scan_as_of=technical_snapshot.as_of_timestamp), snapshot=technical_snapshot,
        strategy_version=STRATEGY_REFERENCE, config=PreBreakoutConfig(),
    )
    assert "BBW_UNAVAILABLE" not in value.setup_quality.warnings
    assert "BOLLINGER_BAND_WIDTH_PERCENTILE" not in value.warnings
    assert any(item.startswith("analysis-") for item in value.evidence_ids)


def test_inflection_uses_percentage_points_and_dynamic_company_specific_context():
    result = InflectionEngine().evaluate(_inflection_input(), config=InflectionConfig())
    assert result.status is CandidateStatus.CANDIDATE_GENERATED
    low_pp = InflectionEngine().evaluate(_inflection_input(fii_current_pct=Decimal("5.05"), fii_prior_two_quarters_pct=Decimal("5"), dii_current_pct=Decimal("4"), dii_prior_two_quarters_pct=Decimal("4")), config=InflectionConfig())
    assert low_pp.status is CandidateStatus.INELIGIBLE
    assert "FII_DII_PP_FILTER_FAILED" in low_pp.warnings
    company_headwind = InflectionEngine().evaluate(_inflection_input(company_transmissions=(_transmission(SensitivityDirection.NEGATIVE),)), config=InflectionConfig())
    assert company_headwind.status is CandidateStatus.INELIGIBLE
    assert "COMPANY_SENSITIVITY_FILTER_FAILED" in company_headwind.warnings


def test_inflection_missing_pit_ownership_is_research_incomplete_not_assumed():
    result = InflectionEngine().evaluate(_inflection_input(fii_current_pct=None), config=InflectionConfig())
    assert result.status is CandidateStatus.RESEARCH_INCOMPLETE
    assert "FUNDAMENTAL_INFLECTION_PARTIAL" in result.warnings


def test_strategy_handoff_is_candidate_only_and_paper_attribution_is_family_separate(tmp_path: Path):
    candidate = PreBreakoutEngine().evaluate(_pre_input(), config=PreBreakoutConfig())
    assert candidate.status is CandidateStatus.CANDIDATE_GENERATED
    assert not hasattr(candidate, "decision_score")
    assert "BUY" not in {item.value for item in CandidateStatus}
    repository = SQLiteCoreApiSnapshotRepository(tmp_path / "strategy.sqlite")
    store = StrategySnapshotStore(repository)
    store.save(record_id=candidate.candidate_id, family=CoreApiSnapshotFamily.PRE_BREAKOUT_CANDIDATE, value=candidate, created_at=AS_OF)
    assert store.get(record_id=candidate.candidate_id, family=CoreApiSnapshotFamily.PRE_BREAKOUT_CANDIDATE) == candidate
    swing = StrategyOutcomeAttribution("swing", StrategyFamily.PRE_BREAKOUT, "v1", candidate.candidate_id, "paper-swing", "benchmark", ("MFE", "MAE", "R_MULTIPLE"), AS_OF)
    inflection = StrategyOutcomeAttribution("inflection", StrategyFamily.INFLECTION, "v1", "inflection-1", "paper-inflection", "benchmark", ("ALPHA_6M", "ALPHA_12M"), AS_OF)
    assert swing.strategy_family is not inflection.strategy_family
    store.save(record_id=swing.attribution_id, family=CoreApiSnapshotFamily.STRATEGY_OUTCOME_ATTRIBUTION, value=swing, created_at=AS_OF)
    assert store.get(record_id=swing.attribution_id, family=CoreApiSnapshotFamily.STRATEGY_OUTCOME_ATTRIBUTION) == swing


def test_strategy_config_scan_quality_and_candidates_round_trip_append_only(tmp_path: Path):
    repository = SQLiteCoreApiSnapshotRepository(tmp_path / "all-strategy-artifacts.sqlite")
    store = StrategySnapshotStore(repository)
    config = PreBreakoutConfig()
    rs = SectorRelativeStrength("Dynamic sector", AS_OF, Decimal("1"), Decimal("2"), Decimal("3"), ("rs-source",))
    breadth = SectorBreadth("Dynamic sector", AS_OF, "historical-membership", Decimal("60"), Decimal("55"), 2, ("NSE:ABC", "NSE:DEF"))
    scan = PreBreakoutEngine().sector_scan(scan_id="sector-scan", as_of=AS_OF, values=((rs, breadth),), config=config)
    candidate = PreBreakoutEngine().evaluate(_pre_input(), config=config)
    store.save(record_id="pre-config", family=CoreApiSnapshotFamily.PRE_BREAKOUT_CONFIG, value=config, created_at=AS_OF)
    store.save(record_id=scan.scan_id, family=CoreApiSnapshotFamily.PRE_BREAKOUT_SECTOR_SCAN, value=scan, created_at=AS_OF)
    store.save(record_id=candidate.setup_quality.quality_id, family=CoreApiSnapshotFamily.STRATEGY_SETUP_QUALITY, value=candidate.setup_quality, created_at=AS_OF)
    store.save(record_id=candidate.candidate_id, family=CoreApiSnapshotFamily.PRE_BREAKOUT_CANDIDATE, value=candidate, created_at=AS_OF)
    assert store.get(record_id="pre-config", family=CoreApiSnapshotFamily.PRE_BREAKOUT_CONFIG) == config
    assert store.get(record_id=scan.scan_id, family=CoreApiSnapshotFamily.PRE_BREAKOUT_SECTOR_SCAN) == scan
    assert store.get(record_id=candidate.setup_quality.quality_id, family=CoreApiSnapshotFamily.STRATEGY_SETUP_QUALITY) == candidate.setup_quality
    assert store.get(record_id=candidate.candidate_id, family=CoreApiSnapshotFamily.PRE_BREAKOUT_CANDIDATE) == candidate
    with pytest.raises(ValueError, match="immutable"):
        store.save(record_id=candidate.candidate_id, family=CoreApiSnapshotFamily.PRE_BREAKOUT_CANDIDATE, value=candidate, created_at=AS_OF)


def test_strategy_source_cannot_depend_on_scoring_gates_or_rotation():
    root = Path(__file__).resolve().parents[2] / "app" / "strategies"
    text = "\n".join(path.read_text(encoding="utf-8") for path in root.rglob("*.py"))
    for prohibited in ("decision_score", "SixHard", "CapitalRotationEngine", "BUY", "SELL", "ROTATE"):
        assert prohibited not in text
    # BBW strategy consumption delegates to the sole canonical technical
    # engine; there is no second Bollinger implementation in the strategy.
    pre_breakout = (root / "pre_breakout" / "service.py").read_text(encoding="utf-8")
    assert "TechnicalAnalysisEngine" in pre_breakout
    assert "sqrt(" not in pre_breakout and "standard_deviation" not in pre_breakout
