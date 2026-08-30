from __future__ import annotations

import hashlib
from math import sqrt
from datetime import datetime
from typing import Callable

from app.analysis.evidence import analysis_evidence
from app.analysis.models import AnalysisStatus, IndicatorResult, PriceStructureResult
from app.analysis.series import AnalysisInputError, PriceBarSeries, closes, price_bar_series
from app.domain.models import AsOfSnapshot, EvidenceType, StrategyVersionReference


TECHNICAL_CALCULATION_VERSION = "technical-v1"
BOLLINGER_BAND_PERIOD = 20
BOLLINGER_STANDARD_DEVIATIONS = 2.0


class TechnicalAnalysisEngine:
    """Pure deterministic indicators; never creates or repairs missing bars."""

    def sma(self, snapshot: AsOfSnapshot, *, instrument_id: str, strategy_version: StrategyVersionReference | None,
            period: int, evaluated_at: datetime) -> IndicatorResult:
        return self._indicator(snapshot, instrument_id, strategy_version, evaluated_at, "SMA", {"period": period}, period,
                               lambda values, _: sum(values[-period:]) / period)

    def ema(self, snapshot: AsOfSnapshot, *, instrument_id: str, strategy_version: StrategyVersionReference | None,
            period: int, evaluated_at: datetime) -> IndicatorResult:
        def calculate(values: tuple[float, ...], _: PriceBarSeries) -> float:
            ema_value = sum(values[:period]) / period
            multiplier = 2 / (period + 1)
            for value in values[period:]:
                ema_value = (value - ema_value) * multiplier + ema_value
            return ema_value
        return self._indicator(snapshot, instrument_id, strategy_version, evaluated_at, "EMA", {"period": period}, period, calculate)

    def rsi(self, snapshot: AsOfSnapshot, *, instrument_id: str, strategy_version: StrategyVersionReference | None,
            period: int, evaluated_at: datetime) -> IndicatorResult:
        def calculate(values: tuple[float, ...], _: PriceBarSeries) -> float:
            changes = [values[index] - values[index - 1] for index in range(1, len(values))]
            average_gain = sum(max(change, 0) for change in changes[:period]) / period
            average_loss = sum(max(-change, 0) for change in changes[:period]) / period
            for change in changes[period:]:
                average_gain = ((average_gain * (period - 1)) + max(change, 0)) / period
                average_loss = ((average_loss * (period - 1)) + max(-change, 0)) / period
            if average_loss == 0 and average_gain == 0:
                return 50.0
            if average_loss == 0:
                return 100.0
            relative_strength = average_gain / average_loss
            return 100 - (100 / (1 + relative_strength))
        return self._indicator(snapshot, instrument_id, strategy_version, evaluated_at, "RSI", {"period": period, "smoothing": "Wilder"}, period + 1, calculate)

    def atr(self, snapshot: AsOfSnapshot, *, instrument_id: str, strategy_version: StrategyVersionReference | None,
            period: int, evaluated_at: datetime) -> IndicatorResult:
        def calculate(_: tuple[float, ...], series: PriceBarSeries) -> float:
            ranges = _true_ranges(series)
            atr_value = sum(ranges[:period]) / period
            for true_range in ranges[period:]:
                atr_value = ((atr_value * (period - 1)) + true_range) / period
            return atr_value
        return self._indicator(snapshot, instrument_id, strategy_version, evaluated_at, "ATR", {"period": period, "smoothing": "Wilder true range"}, period + 1, calculate)

    def adx(self, snapshot: AsOfSnapshot, *, instrument_id: str, strategy_version: StrategyVersionReference | None,
            period: int, evaluated_at: datetime) -> IndicatorResult:
        def calculate(_: tuple[float, ...], series: PriceBarSeries) -> float:
            bars = series.bars
            true_ranges = _true_ranges(series)
            plus_dm: list[float] = []
            minus_dm: list[float] = []
            for index in range(1, len(bars)):
                high_move = float(bars[index].payload["high"]) - float(bars[index - 1].payload["high"])
                low_move = float(bars[index - 1].payload["low"]) - float(bars[index].payload["low"])
                plus_dm.append(high_move if high_move > low_move and high_move > 0 else 0.0)
                minus_dm.append(low_move if low_move > high_move and low_move > 0 else 0.0)
            smoothed_tr = sum(true_ranges[:period])
            smoothed_plus = sum(plus_dm[:period])
            smoothed_minus = sum(minus_dm[:period])
            dx_values: list[float] = [_dx(smoothed_tr, smoothed_plus, smoothed_minus)]
            for index in range(period, len(true_ranges)):
                smoothed_tr = smoothed_tr - (smoothed_tr / period) + true_ranges[index]
                smoothed_plus = smoothed_plus - (smoothed_plus / period) + plus_dm[index]
                smoothed_minus = smoothed_minus - (smoothed_minus / period) + minus_dm[index]
                dx_values.append(_dx(smoothed_tr, smoothed_plus, smoothed_minus))
            adx_value = sum(dx_values[:period]) / period
            for dx in dx_values[period:]:
                adx_value = ((adx_value * (period - 1)) + dx) / period
            return adx_value
        return self._indicator(snapshot, instrument_id, strategy_version, evaluated_at, "ADX", {"period": period, "smoothing": "Wilder DMI"}, 2 * period, calculate)

    def bollinger_band_width(self, snapshot: AsOfSnapshot, *, instrument_id: str,
                             strategy_version: StrategyVersionReference | None,
                             evaluated_at: datetime, period: int = BOLLINGER_BAND_PERIOD,
                             standard_deviations: float = BOLLINGER_STANDARD_DEVIATIONS) -> IndicatorResult:
        """Canonical close-based Bollinger Band Width as a percentage.

        The existing technical boundary owns the formula: population standard
        deviation over the rolling close window, upper/lower bands at the
        configured standard-deviation multiplier, then ``(upper-lower)/SMA *
        100``.  It intentionally does not repair a zero/invalid middle band.
        """
        parameters = {"period": period, "standard_deviations": standard_deviations, "price_input": "close", "standard_deviation": "population", "unit": "percent"}
        series = price_bar_series(snapshot, instrument_id)
        if series.status is not AnalysisStatus.VALID or len(series.bars) < period:
            return _indicator_result(series, strategy_version, snapshot, evaluated_at, "BOLLINGER_BAND_WIDTH", parameters, None,
                                     AnalysisStatus.INSUFFICIENT_DATA if series.status is AnalysisStatus.VALID else series.status)
        width = _bollinger_band_widths(closes(series), period, standard_deviations)[-1]
        if width is None:
            return _indicator_result(series, strategy_version, snapshot, evaluated_at, "BOLLINGER_BAND_WIDTH", parameters, None, AnalysisStatus.INSUFFICIENT_DATA)
        return _indicator_result(series, strategy_version, snapshot, evaluated_at, "BOLLINGER_BAND_WIDTH", parameters, width, AnalysisStatus.VALID)

    def bollinger_band_width_percentile(self, snapshot: AsOfSnapshot, *, instrument_id: str,
                                        strategy_version: StrategyVersionReference | None,
                                        evaluated_at: datetime, history_sessions: int,
                                        period: int = BOLLINGER_BAND_PERIOD,
                                        standard_deviations: float = BOLLINGER_STANDARD_DEVIATIONS) -> IndicatorResult:
        """PIT-safe inclusive percentile rank of the latest canonical BBW.

        It needs ``period + history_sessions - 1`` visible closes to produce
        the requested count of rolling BBW observations.  The trailing window
        ends at the supplied snapshot; no later observation is read.
        """
        if history_sessions < 1:
            raise AnalysisInputError("BBW history_sessions must be positive.")
        parameters = {"band_period": period, "standard_deviations": standard_deviations, "history_sessions": history_sessions, "percentile_method": "inclusive_percent_rank", "price_input": "close"}
        series = price_bar_series(snapshot, instrument_id)
        required = period + history_sessions - 1
        if series.status is not AnalysisStatus.VALID or len(series.bars) < required:
            return _indicator_result(series, strategy_version, snapshot, evaluated_at, "BOLLINGER_BAND_WIDTH_PERCENTILE", parameters, None,
                                     AnalysisStatus.INSUFFICIENT_DATA if series.status is AnalysisStatus.VALID else series.status)
        widths = _bollinger_band_widths(closes(series), period, standard_deviations)
        if any(value is None for value in widths):
            return _indicator_result(series, strategy_version, snapshot, evaluated_at, "BOLLINGER_BAND_WIDTH_PERCENTILE", parameters, None, AnalysisStatus.INSUFFICIENT_DATA)
        trailing = tuple(value for value in widths[-history_sessions:] if value is not None)
        latest = trailing[-1]
        percentile = 100.0 * sum(value <= latest for value in trailing) / len(trailing)
        return _indicator_result(series, strategy_version, snapshot, evaluated_at, "BOLLINGER_BAND_WIDTH_PERCENTILE", parameters, percentile, AnalysisStatus.VALID)

    def price_structure(self, snapshot: AsOfSnapshot, *, instrument_id: str,
                        strategy_version: StrategyVersionReference | None, pivot_window: int,
                        evaluated_at: datetime) -> PriceStructureResult:
        _require_strategy(strategy_version)
        if pivot_window < 1:
            raise AnalysisInputError("Pivot window must be at least one bar.")
        series = price_bar_series(snapshot, instrument_id)
        parameters = {"pivot_window": pivot_window, "logic": "strict confirmed local extrema"}
        if series.status is not AnalysisStatus.VALID:
            return _structure_result(series, strategy_version, snapshot, evaluated_at, parameters)
        highs, lows = _pivots(series, pivot_window)
        if len(highs) < 2 or len(lows) < 2:
            return _structure_result(series, strategy_version, snapshot, evaluated_at, parameters, reason="At least two confirmed pivot highs and lows are required.")
        higher_high = highs[-1][1] > highs[-2][1]
        lower_high = highs[-1][1] < highs[-2][1]
        higher_low = lows[-1][1] > lows[-2][1]
        lower_low = lows[-1][1] < lows[-2][1]
        pivot_ids = tuple(item[0].id for item in (*highs[-2:], *lows[-2:]))
        result_id = _id("price_structure", instrument_id, strategy_version, snapshot.as_of_timestamp, pivot_ids, parameters)
        evidence = _evidence(result_id, "price_structure", evaluated_at, pivot_ids, series.data_quality,
                             f"HH={higher_high};HL={higher_low};LH={lower_high};LL={lower_low}")
        return PriceStructureResult(result_id, instrument_id, strategy_version, higher_high, higher_low, lower_high, lower_low,
                                    pivot_ids, parameters, TECHNICAL_CALCULATION_VERSION, evaluated_at,
                                    snapshot.as_of_timestamp, series.data_quality, 1.0, AnalysisStatus.VALID, evidence)

    def _indicator(self, snapshot: AsOfSnapshot, instrument_id: str, strategy_version: StrategyVersionReference | None,
                   evaluated_at: datetime, name: str, parameters: dict[str, object], minimum_bars: int,
                   calculate: Callable[[tuple[float, ...], PriceBarSeries], float]) -> IndicatorResult:
        _require_strategy(strategy_version)
        period = parameters.get("period")
        if not isinstance(period, int) or period <= 0:
            raise AnalysisInputError("Indicator period must be a positive integer.")
        series = price_bar_series(snapshot, instrument_id)
        if series.status is not AnalysisStatus.VALID or len(series.bars) < minimum_bars:
            return _indicator_result(series, strategy_version, snapshot, evaluated_at, name, parameters, None,
                                     AnalysisStatus.INSUFFICIENT_DATA if series.status is AnalysisStatus.VALID else series.status)
        value = calculate(closes(series), series)
        return _indicator_result(series, strategy_version, snapshot, evaluated_at, name, parameters, value, AnalysisStatus.VALID)


def _true_ranges(series: PriceBarSeries) -> list[float]:
    values: list[float] = []
    for index in range(1, len(series.bars)):
        current, previous = series.bars[index], series.bars[index - 1]
        high, low, previous_close = float(current.payload["high"]), float(current.payload["low"]), float(previous.payload["close"])
        values.append(max(high - low, abs(high - previous_close), abs(low - previous_close)))
    return values


def _bollinger_band_widths(values: tuple[float, ...], period: int, standard_deviations: float) -> tuple[float | None, ...]:
    if period <= 0 or standard_deviations <= 0:
        raise AnalysisInputError("Bollinger period and standard deviations must be positive.")
    widths: list[float | None] = []
    for end in range(period, len(values) + 1):
        window = values[end - period:end]
        middle = sum(window) / period
        if middle <= 0:
            widths.append(None)
            continue
        standard_deviation = sqrt(sum((value - middle) ** 2 for value in window) / period)
        widths.append((2 * standard_deviations * standard_deviation / middle) * 100)
    return tuple(widths)


def _dx(smoothed_tr: float, smoothed_plus: float, smoothed_minus: float) -> float:
    if smoothed_tr == 0:
        return 0.0
    plus_di, minus_di = 100 * smoothed_plus / smoothed_tr, 100 * smoothed_minus / smoothed_tr
    denominator = plus_di + minus_di
    return 0.0 if denominator == 0 else 100 * abs(plus_di - minus_di) / denominator


def _pivots(series: PriceBarSeries, window: int) -> tuple[list[tuple[object, float]], list[tuple[object, float]]]:
    highs: list[tuple[object, float]] = []
    lows: list[tuple[object, float]] = []
    for index in range(window, len(series.bars) - window):
        bar = series.bars[index]
        high, low = float(bar.payload["high"]), float(bar.payload["low"])
        surrounding = series.bars[index - window:index] + series.bars[index + 1:index + window + 1]
        if all(high > float(item.payload["high"]) for item in surrounding):
            highs.append((bar, high))
        if all(low < float(item.payload["low"]) for item in surrounding):
            lows.append((bar, low))
    return highs, lows


def _indicator_result(series: PriceBarSeries, strategy: StrategyVersionReference, snapshot: AsOfSnapshot, evaluated_at: datetime,
                      name: str, parameters: dict[str, object], value: float | None, status: AnalysisStatus) -> IndicatorResult:
    result_id = _id(name, series.instrument_id, strategy, snapshot.as_of_timestamp, series.observation_ids, parameters)
    evidence = _evidence(result_id, name, evaluated_at, series.observation_ids, series.data_quality,
                         f"value={value}" if status is AnalysisStatus.VALID else (series.reason or "Insufficient valid bars."))
    return IndicatorResult(result_id, series.instrument_id, strategy, value, name, parameters, series.observation_ids,
                           TECHNICAL_CALCULATION_VERSION, evaluated_at, snapshot.as_of_timestamp, series.data_quality,
                           1.0 if status is AnalysisStatus.VALID else None, status, evidence)


def _structure_result(series: PriceBarSeries, strategy: StrategyVersionReference, snapshot: AsOfSnapshot, evaluated_at: datetime,
                      parameters: dict[str, object], reason: str | None = None) -> PriceStructureResult:
    result_id = _id("price_structure", series.instrument_id, strategy, snapshot.as_of_timestamp, series.observation_ids, parameters)
    status = series.status if series.status is not AnalysisStatus.VALID else AnalysisStatus.INSUFFICIENT_DATA
    evidence = _evidence(result_id, "price_structure", evaluated_at, series.observation_ids, series.data_quality, reason or series.reason or "Insufficient valid bars.")
    return PriceStructureResult(result_id, series.instrument_id, strategy, None, None, None, None, (), parameters,
                                TECHNICAL_CALCULATION_VERSION, evaluated_at, snapshot.as_of_timestamp, series.data_quality,
                                None, status, evidence)


def _evidence(result_id: str, name: str, evaluated_at: datetime, observation_ids: tuple[str, ...], quality, content: str):
    return (
        analysis_evidence(analysis_id=result_id, evidence_type=EvidenceType.DATA, source="technical-analysis-engine",
                          timestamp=evaluated_at, observation_ids=observation_ids, content_reference=f"analysis://{name}/inputs", confidence=1.0, data_quality=quality),
        analysis_evidence(analysis_id=result_id, evidence_type=EvidenceType.INTERPRETATION, source="technical-analysis-engine",
                          timestamp=evaluated_at, observation_ids=observation_ids, content_reference=f"analysis://{name}/{content}", confidence=1.0, data_quality=quality),
    )


def _id(name: str, instrument_id: str, strategy: StrategyVersionReference, as_of: datetime, input_ids: tuple[str, ...], parameters: dict[str, object]) -> str:
    payload = f"{name}|{instrument_id}|{strategy.strategy_id}|{strategy.version}|{as_of.isoformat()}|{'|'.join(input_ids)}|{sorted(parameters.items())}"
    return f"analysis-{hashlib.sha256(payload.encode()).hexdigest()[:16]}"


def _require_strategy(strategy: StrategyVersionReference | None) -> None:
    if strategy is None:
        raise AnalysisInputError("Analysis requires a strategy version.")
