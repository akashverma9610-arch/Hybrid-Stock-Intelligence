from app.analysis.sector_volume_ichimoku import ichimoku, vwap
from app.diagnostics.evaluators import ComponentEligibilityService, DeterministicDiagnosticEvaluators
from tests.fixtures.analytical_observations import ANALYSIS_TIME, STRATEGY_REFERENCE, bars, snapshot


def _market():
    return snapshot(
        bars("sector", [10, 11, 12, 13, 14, 15, 16, 17]),
        bars("benchmark", [10, 10.2, 10.4, 10.6, 10.8, 11, 11.2, 11.4]),
        bars("stock", [10, 11, 12, 11, 13, 14, 15, 16], volumes=[100, 100, 90, 110, 120, 130, 140, 400]),
    )


def test_all_eight_new_diagnostic_wrappers_are_deterministic_and_mapped():
    data = _market(); engine = DeterministicDiagnosticEvaluators()
    cases = (
        lambda: engine.sector_health(data, "sector", "benchmark", STRATEGY_REFERENCE, 3, .05, -.05, ANALYSIS_TIME),
        lambda: engine.sector_rotation(data, "sector", "benchmark", STRATEGY_REFERENCE, 3, .05, -.05, ANALYSIS_TIME),
        lambda: engine.volume(data, "stock", STRATEGY_REFERENCE, 3, 1.5, .7, ANALYSIS_TIME),
        lambda: engine.ichimoku(data, "stock", STRATEGY_REFERENCE, 2, 3, 4, 1, ANALYSIS_TIME),
        lambda: engine.chikou(data, "stock", STRATEGY_REFERENCE, 2, 3, 4, 1, ANALYSIS_TIME),
        lambda: engine.mtf({"daily": data, "weekly": data}, "stock", STRATEGY_REFERENCE, ANALYSIS_TIME),
        lambda: engine.vwap(data, "stock", STRATEGY_REFERENCE, ANALYSIS_TIME),
        lambda: engine.obv(data, "stock", STRATEGY_REFERENCE, 3, ANALYSIS_TIME),
    )
    component = ComponentEligibilityService()
    expected = {2: "sector_rotation", 3: "sector_rotation", 11: "volume_obv_vwap", 12: "ichimoku_mtf", 13: "ichimoku_mtf", 14: "ichimoku_mtf", 35: "volume_obv_vwap", 36: "volume_obv_vwap"}
    for evaluate in cases:
        result = evaluate()
        assert result == evaluate()
        assert result.eligibility.value == "eligible"
        assert result.record.score is None
        assert result.record.evidence_ids
        assert component.assess(result).component_id == expected[result.canonical_rule_id]


def test_chikou_uses_close_displaced_exactly_by_configured_period():
    data = snapshot(bars("stock", [10, 100, 90, 80, 70, 60, 50, 40]))
    # With displacement=3, the current close (40) must be compared with index -4 (70).
    result = ichimoku(data, "stock", 2, 3, 4, 3)
    assert dict(result.details)["chikou"] == "BEARISH_CONFIRMATION"


def test_chikou_displacement_is_configurable_not_a_fixed_previous_bar_check():
    data = snapshot(bars("stock", [10, 20, 30, 40, 50, 60]))
    # With displacement=2, the current close (60) is compared with index -3 (40).
    result = ichimoku(data, "stock", 2, 3, 4, 2)
    assert dict(result.details)["chikou"] == "BULLISH_CONFIRMATION"


def test_value_area_is_explicitly_unavailable_without_volume_at_price_data():
    result = vwap(snapshot(bars("stock", [10, 11, 12], volumes=[100, 200, 300])), "stock")
    details = dict(result.details)
    assert details["value_area"] == "UNAVAILABLE"
    assert not {"poc", "vah", "val"}.intersection(details)


def test_sector_and_volume_interpretations_are_proxy_safe():
    data = _market(); engine = DeterministicDiagnosticEvaluators()
    rotation = engine.sector_rotation(data, "sector", "benchmark", STRATEGY_REFERENCE, 3, .05, -.05, ANALYSIS_TIME)
    volume = engine.obv(data, "stock", STRATEGY_REFERENCE, 3, ANALYSIS_TIME)
    assert "not fund flow" in dict(rotation.details)["classification"]
    assert "not institutional accumulation" in dict(volume.details)["interpretation"]
