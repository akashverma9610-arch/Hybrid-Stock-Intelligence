from dataclasses import replace

from app.analysis.models import MarketRegimeRules, RelativeStrengthRules, TrendRules
from app.diagnostics.evaluators import ComponentEligibilityService, DeterministicDiagnosticEvaluators, WeinsteinRules
from app.diagnostics.models import ComponentEligibility, EvaluationEligibility
from tests.fixtures.analytical_observations import ANALYSIS_TIME, STRATEGY_REFERENCE, bars, downtrend_bars, snapshot, uptrend_bars

REGIME = MarketRegimeRules(2, 3, 2, 3, .2, .1, .02, -.02, -.1, -.4, .3)
RS = RelativeStrengthRules(3, .1, .03, -.03)


def test_six_canonical_diagnostics_reuse_analytical_engines() -> None:
    evaluator = DeterministicDiagnosticEvaluators()
    regime = evaluator.market_regime(snapshot(uptrend_bars("benchmark")), "benchmark", STRATEGY_REFERENCE, REGIME, ANALYSIS_TIME)
    weekly = replace(snapshot(tuple(replace(item, id=f"weekly-{item.id}") for item in uptrend_bars("stock"))), id="weekly-snapshot")
    daily = replace(snapshot(uptrend_bars("stock")), id="daily-snapshot")
    trend = evaluator.primary_trend(weekly, daily, "stock", STRATEGY_REFERENCE, TrendRules(3, 5, True, 1), ANALYSIS_TIME)
    stage = evaluator.weinstein(snapshot(bars("stock", [10, 10, 10, 11, 12, 13, 14, 15])), "stock", STRATEGY_REFERENCE, WeinsteinRules(3, 2), ANALYSIS_TIME)
    relative = evaluator.relative_strength(snapshot(uptrend_bars("stock"), uptrend_bars("benchmark")), "stock", "benchmark", None, (), STRATEGY_REFERENCE, RS, ANALYSIS_TIME)
    structure = evaluator.market_structure(snapshot(uptrend_bars("stock")), "stock", STRATEGY_REFERENCE, 1, ANALYSIS_TIME)
    layer = evaluator.indicator_layer(snapshot(bars("stock", [10,11,12,13,14,15,16,17])), "stock", STRATEGY_REFERENCE, 3, 70, 30, 20, 2, ANALYSIS_TIME)
    items = (regime, trend, stage, relative, structure, layer)
    assert [item.canonical_rule_id for item in items] == [1, 4, 5, 6, 10, 39]
    assert all(item.registry_version == "diagnostic-registry-v1" and item.record.strategy_version == STRATEGY_REFERENCE for item in items)
    assert trend.record.result == "BULLISH" and structure.record.result == "HH_HL_BULLISH" and len(layer.details) == 3


def test_mixed_missing_and_component_eligibility_remain_separate_from_score() -> None:
    evaluator = DeterministicDiagnosticEvaluators()
    weekly = replace(snapshot(tuple(replace(item, id=f"weekly-{item.id}") for item in uptrend_bars("stock"))), id="weekly-snapshot")
    daily = replace(snapshot(downtrend_bars("stock")), id="daily-snapshot")
    mixed = evaluator.primary_trend(weekly, daily, "stock", STRATEGY_REFERENCE, TrendRules(3, 5, True, 1), ANALYSIS_TIME)
    missing = evaluator.primary_trend(None, snapshot(uptrend_bars("stock")), "stock", STRATEGY_REFERENCE, TrendRules(3, 5, True, 1), ANALYSIS_TIME)
    contribution = ComponentEligibilityService().assess(missing)
    assert mixed.record.result == "MIXED"
    assert missing.record.result == "INSUFFICIENT_DATA" and missing.eligibility is EvaluationEligibility.INELIGIBLE_MISSING_DATA
    assert contribution.status is ComponentEligibility.INELIGIBLE and missing.record.score is None


def test_same_snapshot_cannot_be_presented_as_distinct_weekly_or_mtf_evidence() -> None:
    evaluator = DeterministicDiagnosticEvaluators()
    same = snapshot(uptrend_bars("stock"))
    trend = evaluator.primary_trend(same, same, "stock", STRATEGY_REFERENCE, TrendRules(3, 5, True, 1), ANALYSIS_TIME)
    mtf = evaluator.mtf({"daily": same, "weekly": same}, "stock", STRATEGY_REFERENCE, ANALYSIS_TIME)
    assert trend.record.result == mtf.record.result == "INSUFFICIENT_DATA"
    assert trend.eligibility is mtf.eligibility is EvaluationEligibility.INELIGIBLE_MISSING_DATA
