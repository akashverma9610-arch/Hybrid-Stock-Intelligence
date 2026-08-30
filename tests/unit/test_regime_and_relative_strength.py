from app.analysis.market_regime import MarketRegimeEngine
from app.analysis.models import MarketRegime, MarketRegimeRules, RelativeStrengthClassification, RelativeStrengthRules
from app.analysis.relative_strength import RelativeStrengthEngine
from tests.fixtures.analytical_observations import ANALYSIS_TIME, STRATEGY_REFERENCE, bars, downtrend_bars, snapshot, uptrend_bars


REGIME_RULES = MarketRegimeRules(
    fast_sma_period=2, slow_sma_period=3, atr_period=2, return_lookback=3,
    strong_bull_minimum_return=0.20, bull_minimum_return=0.10, selective_bull_minimum_return=0.02,
    selective_bear_maximum_return=-0.02, bear_maximum_return=-0.10, panic_maximum_return=-0.40,
    panic_atr_percent=0.30,
)
RS_RULES = RelativeStrengthRules(lookback=3, leader_minimum_excess_return=0.10,
                                 emerging_leader_minimum_excess_return=0.03, laggard_maximum_excess_return=-0.03)


def test_market_regime_is_transparent_and_returns_insufficient_for_missing_benchmark() -> None:
    engine = MarketRegimeEngine()
    bull = engine.classify(snapshot(uptrend_bars("benchmark")), benchmark_instrument_id="benchmark", strategy_version=STRATEGY_REFERENCE, rules=REGIME_RULES, evaluated_at=ANALYSIS_TIME)
    bear = engine.classify(snapshot(downtrend_bars("benchmark")), benchmark_instrument_id="benchmark", strategy_version=STRATEGY_REFERENCE, rules=REGIME_RULES, evaluated_at=ANALYSIS_TIME)
    missing = engine.classify(snapshot(), benchmark_instrument_id="benchmark", strategy_version=STRATEGY_REFERENCE, rules=REGIME_RULES, evaluated_at=ANALYSIS_TIME)

    assert bull.classification is MarketRegime.STRONG_BULL
    assert bear.classification is MarketRegime.BEAR
    assert missing.classification is MarketRegime.INSUFFICIENT_DATA
    assert any("benchmark_return" in condition for condition in bull.conditions)


def test_relative_strength_measures_stock_benchmark_and_sector_returns() -> None:
    engine = RelativeStrengthEngine()
    leader = engine.calculate(
        snapshot(bars("stock", [10, 11, 12, 13, 15, 16]), bars("benchmark", [10, 10.2, 10.5, 10.8, 11, 11.2]), bars("sector", [10, 10.5, 10.8, 11, 11.2, 11.4])),
        instrument_id="stock", benchmark_instrument_id="benchmark", sector_instrument_id="sector",
        strategy_version=STRATEGY_REFERENCE, rules=RS_RULES, evaluated_at=ANALYSIS_TIME,
    )
    laggard = engine.calculate(
        snapshot(bars("stock", [10, 9.8, 9.5, 9.3, 9.1, 9]), bars("benchmark", [10, 10.2, 10.5, 10.8, 11, 11.2])),
        instrument_id="stock", benchmark_instrument_id="benchmark", sector_instrument_id=None,
        strategy_version=STRATEGY_REFERENCE, rules=RS_RULES, evaluated_at=ANALYSIS_TIME,
    )

    assert leader.classification is RelativeStrengthClassification.LEADER
    assert leader.sector_excess_return is not None
    assert laggard.classification is RelativeStrengthClassification.LAGGARD


def test_relative_strength_requires_valid_stock_and_benchmark_bars() -> None:
    result = RelativeStrengthEngine().calculate(snapshot(bars("stock", [10, 11, 12])), instrument_id="stock",
                                                benchmark_instrument_id="missing", sector_instrument_id=None,
                                                strategy_version=STRATEGY_REFERENCE, rules=RS_RULES, evaluated_at=ANALYSIS_TIME)
    assert result.classification is RelativeStrengthClassification.INSUFFICIENT_DATA
