from dataclasses import replace
from datetime import timedelta

import pytest

from app.analysis.models import MarketRegimeRules, RelativeStrengthRules, TrendRules
from app.config.freshness import FreshnessPolicyConfig
from app.diagnostics.evaluators import DeterministicDiagnosticEvaluators, WeinsteinRules
from app.domain.models import AsOfSnapshot, ObservationKind
from app.services.foundation_service import FoundationService
from app.storage.sqlite_governance_repository import SQLiteStrategyGovernanceRepository
from app.validation.freshness import FreshnessEngine
from app.validation.observation_validator import ObservationValidator
from tests.fixtures.analytical_observations import ANALYSIS_TIME, STRATEGY_REFERENCE, bars, downtrend_bars, snapshot, uptrend_bars

REGIME = MarketRegimeRules(2, 3, 2, 3, .2, .1, .02, -.02, -.1, -.4, .3)
RS = RelativeStrengthRules(3, .1, .03, -.03)


def _as_of_pair(tmp_path, name, historical, future):
    repository = SQLiteStrategyGovernanceRepository(tmp_path / f"{name}.db")
    service = FoundationService(repository, ObservationValidator(FreshnessEngine(FreshnessPolicyConfig({ObservationKind.PRICE_BAR: timedelta(days=90)}, timedelta(days=90)))))
    evaluation = ANALYSIS_TIME + timedelta(days=10)
    for item in historical:
        service.ingest(item, evaluated_timestamp=evaluation)
    before = service.build_as_of_snapshot(as_of_timestamp=ANALYSIS_TIME)
    for item in future:
        service.ingest(item, evaluated_timestamp=evaluation)
    after = service.build_as_of_snapshot(as_of_timestamp=ANALYSIS_TIME)
    return repository, before, after


def _future(instrument, close, suffix):
    return replace(bars(instrument, [close], start=ANALYSIS_TIME + timedelta(days=1))[0], id=f"{instrument}-future-{suffix}")


def _assert_unchanged(first, second, future_ids):
    assert first == second
    assert first.record.input_observation_ids == second.record.input_observation_ids
    assert first.record.evidence_ids == second.record.evidence_ids
    assert first.record.confidence == second.record.confidence
    serialized = repr(first)
    assert all(identifier not in serialized for identifier in future_ids)


def test_rule_1_market_regime_excludes_future_bars(tmp_path):
    repo, before, after = _as_of_pair(tmp_path, "r1", uptrend_bars("benchmark"), (_future("benchmark", 1, "crash"),))
    engine = DeterministicDiagnosticEvaluators()
    first = engine.market_regime(before, "benchmark", STRATEGY_REFERENCE, REGIME, ANALYSIS_TIME)
    second = engine.market_regime(after, "benchmark", STRATEGY_REFERENCE, REGIME, ANALYSIS_TIME)
    _assert_unchanged(first, second, ("benchmark-future-crash",)); repo.close()


def test_rule_4_primary_trend_excludes_future_bars(tmp_path):
    rw, weekly_before, weekly_after = _as_of_pair(tmp_path, "r4w", uptrend_bars("stock"), (_future("stock", 1, "weekly"),))
    rd, daily_before, daily_after = _as_of_pair(tmp_path, "r4d", uptrend_bars("stock"), (_future("stock", 1, "daily"),))
    engine = DeterministicDiagnosticEvaluators(); rules = TrendRules(3, 5, True, 1)
    first = engine.primary_trend(weekly_before, daily_before, "stock", STRATEGY_REFERENCE, rules, ANALYSIS_TIME)
    second = engine.primary_trend(weekly_after, daily_after, "stock", STRATEGY_REFERENCE, rules, ANALYSIS_TIME)
    _assert_unchanged(first, second, ("stock-future-weekly", "stock-future-daily")); rw.close(); rd.close()


def test_rules_5_10_and_39_exclude_future_bars(tmp_path):
    history = uptrend_bars("stock")
    repo, before, after = _as_of_pair(tmp_path, "technical", history, (_future("stock", 1, "collapse"),))
    engine = DeterministicDiagnosticEvaluators()
    cases = (
        (engine.weinstein, ("stock", STRATEGY_REFERENCE, WeinsteinRules(3, 2), ANALYSIS_TIME)),
        (engine.market_structure, ("stock", STRATEGY_REFERENCE, 1, ANALYSIS_TIME)),
        (engine.indicator_layer, ("stock", STRATEGY_REFERENCE, 3, 70, 30, 20, 2, ANALYSIS_TIME)),
    )
    for method, args in cases:
        first, second = method(before, *args), method(after, *args)
        _assert_unchanged(first, second, ("stock-future-collapse",))
    repo.close()


def test_rule_6_relative_strength_excludes_future_stock_benchmark_and_sector_bars(tmp_path):
    repo, before, after = _as_of_pair(tmp_path, "r6-stock", uptrend_bars("stock"), (_future("stock", 1, "stock"),))
    rb, bench_before, bench_after = _as_of_pair(tmp_path, "r6-benchmark", uptrend_bars("benchmark"), (_future("benchmark", 100, "benchmark"),))
    rs, sector_before, sector_after = _as_of_pair(tmp_path, "r6-sector", uptrend_bars("sector"), (_future("sector", 1, "sector"),))
    before_all = AsOfSnapshot("r6-before", ANALYSIS_TIME, ANALYSIS_TIME, "fixture", before.observations + bench_before.observations + sector_before.observations)
    after_all = AsOfSnapshot("r6-after", ANALYSIS_TIME, ANALYSIS_TIME, "fixture", after.observations + bench_after.observations + sector_after.observations)
    engine = DeterministicDiagnosticEvaluators()
    first = engine.relative_strength(before_all, "stock", "benchmark", "sector", (), STRATEGY_REFERENCE, RS, ANALYSIS_TIME)
    second = engine.relative_strength(after_all, "stock", "benchmark", "sector", (), STRATEGY_REFERENCE, RS, ANALYSIS_TIME)
    _assert_unchanged(first, second, ("stock-future-stock", "benchmark-future-benchmark", "sector-future-sector")); repo.close(); rb.close(); rs.close()


def test_raw_future_observation_inside_snapshot_is_rejected_not_consumed():
    future = _future("benchmark", 1, "bypass")
    contaminated = AsOfSnapshot("contaminated", ANALYSIS_TIME, ANALYSIS_TIME, "manual", uptrend_bars("benchmark") + (future,))
    result = DeterministicDiagnosticEvaluators().market_regime(contaminated, "benchmark", STRATEGY_REFERENCE, REGIME, ANALYSIS_TIME)
    assert result.eligibility.value == "ineligible_invalid_data"
    assert "benchmark-future-bypass" not in result.record.input_observation_ids
