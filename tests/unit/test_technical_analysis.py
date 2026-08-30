from datetime import timedelta
from math import sqrt

import pytest

from app.analysis.models import AnalysisStatus, TrendClassification, TrendRules
from app.analysis.technical import TechnicalAnalysisEngine
from app.analysis.trend import TrendEngine
from app.analysis.series import AnalysisInputError
from tests.fixtures.analytical_observations import (
    ANALYSIS_TIME, STRATEGY_REFERENCE, bars, downtrend_bars, invalid_bar_snapshot,
    sideways_bars, snapshot, stale_bar_snapshot, uptrend_bars,
)


def test_sma_and_ema_are_deterministic() -> None:
    engine = TechnicalAnalysisEngine()
    data = snapshot(bars("stock", [1, 2, 3, 4, 5]))

    sma = engine.sma(data, instrument_id="stock", strategy_version=STRATEGY_REFERENCE, period=3, evaluated_at=ANALYSIS_TIME)
    ema = engine.ema(data, instrument_id="stock", strategy_version=STRATEGY_REFERENCE, period=3, evaluated_at=ANALYSIS_TIME)

    assert sma.value == 4.0
    assert ema.value == 4.0
    assert sma == engine.sma(data, instrument_id="stock", strategy_version=STRATEGY_REFERENCE, period=3, evaluated_at=ANALYSIS_TIME)


def test_rsi_atr_and_adx_use_documented_wilder_calculations() -> None:
    engine = TechnicalAnalysisEngine()
    rsi = engine.rsi(snapshot(bars("rsi", [1, 2, 3, 4])), instrument_id="rsi", strategy_version=STRATEGY_REFERENCE, period=3, evaluated_at=ANALYSIS_TIME)
    atr_bars = bars("atr", [10, 12, 11, 13], highs=[11, 13, 12, 14], lows=[9, 11, 10, 12])
    atr = engine.atr(snapshot(atr_bars), instrument_id="atr", strategy_version=STRATEGY_REFERENCE, period=2, evaluated_at=ANALYSIS_TIME)
    adx_bars = bars("adx", [9, 10, 11, 12, 13, 14], highs=[10, 11, 12, 13, 14, 15], lows=[8, 9, 10, 11, 12, 13])
    adx = engine.adx(snapshot(adx_bars), instrument_id="adx", strategy_version=STRATEGY_REFERENCE, period=3, evaluated_at=ANALYSIS_TIME)

    assert rsi.value == 100.0
    assert atr.value == 2.75
    assert adx.value == 100.0


def test_canonical_bollinger_band_width_uses_close_population_standard_deviation() -> None:
    engine = TechnicalAnalysisEngine()
    values = list(range(1, 21))
    result = engine.bollinger_band_width(snapshot(bars("bbw", values)), instrument_id="bbw", strategy_version=STRATEGY_REFERENCE, evaluated_at=ANALYSIS_TIME)
    mean = sum(values) / len(values)
    expected = (4 * sqrt(sum((value - mean) ** 2 for value in values) / len(values)) / mean) * 100
    assert result.status is AnalysisStatus.VALID
    assert result.value == pytest.approx(expected)
    assert result.parameters["price_input"] == "close"
    assert result.parameters["standard_deviation"] == "population"


def test_bbw_percentile_is_pit_safe_and_requires_120_visible_widths() -> None:
    engine = TechnicalAnalysisEngine()
    closes = [100 + ((index % 11) - 5) * (3 if index < 119 else 0.1) for index in range(139)]
    current = snapshot(bars("bbw", closes))
    percentile = engine.bollinger_band_width_percentile(current, instrument_id="bbw", strategy_version=STRATEGY_REFERENCE, evaluated_at=ANALYSIS_TIME, history_sessions=120)
    assert percentile.status is AnalysisStatus.VALID and percentile.value is not None
    insufficient = engine.bollinger_band_width_percentile(snapshot(bars("short-bbw", closes[:-1])), instrument_id="short-bbw", strategy_version=STRATEGY_REFERENCE, evaluated_at=ANALYSIS_TIME, history_sessions=120)
    assert insufficient.status is AnalysisStatus.INSUFFICIENT_DATA
    # The earlier frozen snapshot is evaluated independently; later bars never
    # alter its result or are admitted to its input-observation IDs.
    future = snapshot(bars("bbw", closes + [250, 300], start=ANALYSIS_TIME - timedelta(days=len(closes))))
    assert engine.bollinger_band_width_percentile(current, instrument_id="bbw", strategy_version=STRATEGY_REFERENCE, evaluated_at=ANALYSIS_TIME, history_sessions=120) == percentile
    assert len(future.observations) > len(current.observations)


def test_price_structure_and_trend_classification() -> None:
    technical, trend = TechnicalAnalysisEngine(), TrendEngine()
    up = snapshot(uptrend_bars())
    down = snapshot(downtrend_bars())
    rules = TrendRules(3, 5, True, 1)

    structure = technical.price_structure(up, instrument_id="stock", strategy_version=STRATEGY_REFERENCE, pivot_window=1, evaluated_at=ANALYSIS_TIME)
    assert (structure.higher_high, structure.higher_low, structure.lower_high, structure.lower_low) == (True, True, False, False)
    down_structure = technical.price_structure(down, instrument_id="stock", strategy_version=STRATEGY_REFERENCE, pivot_window=1, evaluated_at=ANALYSIS_TIME)
    assert (down_structure.higher_high, down_structure.higher_low, down_structure.lower_high, down_structure.lower_low) == (False, False, True, True)
    assert trend.classify(up, instrument_id="stock", strategy_version=STRATEGY_REFERENCE, rules=rules, evaluated_at=ANALYSIS_TIME).classification is TrendClassification.UPTREND
    assert trend.classify(down, instrument_id="stock", strategy_version=STRATEGY_REFERENCE, rules=rules, evaluated_at=ANALYSIS_TIME).classification is TrendClassification.DOWNTREND
    sideways = trend.classify(snapshot(sideways_bars()), instrument_id="stock", strategy_version=STRATEGY_REFERENCE,
                              rules=TrendRules(2, 3, False), evaluated_at=ANALYSIS_TIME)
    assert sideways.classification is TrendClassification.SIDEWAYS


def test_missing_or_invalid_data_fails_closed_and_strategy_is_required() -> None:
    engine = TechnicalAnalysisEngine()
    insufficient = engine.sma(snapshot(bars("short", [1, 2])), instrument_id="short", strategy_version=STRATEGY_REFERENCE, period=3, evaluated_at=ANALYSIS_TIME)
    invalid = engine.sma(invalid_bar_snapshot(), instrument_id="invalid", strategy_version=STRATEGY_REFERENCE, period=1, evaluated_at=ANALYSIS_TIME)

    assert insufficient.status is AnalysisStatus.INSUFFICIENT_DATA
    assert invalid.status is AnalysisStatus.INVALID_DATA
    stale_result = engine.sma(stale_bar_snapshot(), instrument_id="stale", strategy_version=STRATEGY_REFERENCE, period=1, evaluated_at=ANALYSIS_TIME)
    assert stale_result.status is AnalysisStatus.INVALID_DATA
    with pytest.raises(AnalysisInputError, match="strategy version"):
        engine.sma(snapshot(bars("stock", [1, 2, 3])), instrument_id="stock", strategy_version=None, period=2, evaluated_at=ANALYSIS_TIME)
