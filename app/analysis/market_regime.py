from __future__ import annotations

import hashlib
from datetime import datetime

from app.analysis.evidence import analysis_evidence
from app.analysis.models import AnalysisStatus, MarketRegime, MarketRegimeResult, MarketRegimeRules, TrendRules
from app.analysis.series import AnalysisInputError, closes, price_bar_series
from app.analysis.technical import TECHNICAL_CALCULATION_VERSION, TechnicalAnalysisEngine
from app.analysis.trend import TrendEngine
from app.domain.models import AsOfSnapshot, EvidenceType, StrategyVersionReference


class MarketRegimeEngine:
    def __init__(self, technical_engine: TechnicalAnalysisEngine | None = None, trend_engine: TrendEngine | None = None) -> None:
        self._technical = technical_engine or TechnicalAnalysisEngine()
        self._trend = trend_engine or TrendEngine(self._technical)

    def classify(self, snapshot: AsOfSnapshot, *, benchmark_instrument_id: str,
                 strategy_version: StrategyVersionReference | None, rules: MarketRegimeRules,
                 evaluated_at: datetime) -> MarketRegimeResult:
        if strategy_version is None:
            raise AnalysisInputError("Analysis requires a strategy version.")
        series = price_bar_series(snapshot, benchmark_instrument_id)
        if series.status is not AnalysisStatus.VALID or len(series.bars) < rules.return_lookback + 1:
            return _result(series, strategy_version, snapshot, evaluated_at, MarketRegime.INSUFFICIENT_DATA,
                           (series.reason or "Return lookback requirement is not met."),
                           AnalysisStatus.INVALID_DATA if series.status is AnalysisStatus.INVALID_DATA else AnalysisStatus.INSUFFICIENT_DATA)
        trend = self._trend.classify(snapshot, instrument_id=benchmark_instrument_id, strategy_version=strategy_version,
                                     rules=TrendRules(rules.fast_sma_period, rules.slow_sma_period, False), evaluated_at=evaluated_at)
        atr = self._technical.atr(snapshot, instrument_id=benchmark_instrument_id, strategy_version=strategy_version,
                                  period=rules.atr_period, evaluated_at=evaluated_at)
        if trend.status is not AnalysisStatus.VALID or atr.status is not AnalysisStatus.VALID:
            return _result(series, strategy_version, snapshot, evaluated_at, MarketRegime.INSUFFICIENT_DATA,
                           ("Trend or ATR requirement is not met.",), AnalysisStatus.INSUFFICIENT_DATA)
        values = closes(series)
        period_return = (values[-1] / values[-1 - rules.return_lookback]) - 1
        atr_percent = atr.value / values[-1] if values[-1] else 0.0
        conditions = (f"benchmark_return={period_return:.6f}", f"atr_percent={atr_percent:.6f}", f"trend={trend.classification.value}")
        if period_return <= rules.panic_maximum_return and atr_percent >= rules.panic_atr_percent:
            regime = MarketRegime.PANIC
        elif period_return >= rules.strong_bull_minimum_return and trend.classification.value == "uptrend":
            regime = MarketRegime.STRONG_BULL
        elif period_return >= rules.bull_minimum_return and trend.classification.value == "uptrend":
            regime = MarketRegime.BULL
        elif period_return >= rules.selective_bull_minimum_return:
            regime = MarketRegime.SELECTIVE_BULL
        elif period_return <= rules.bear_maximum_return and trend.classification.value == "downtrend":
            regime = MarketRegime.BEAR
        elif period_return <= rules.selective_bear_maximum_return:
            regime = MarketRegime.SELECTIVE_BEAR
        else:
            regime = MarketRegime.NEUTRAL
        return _result(series, strategy_version, snapshot, evaluated_at, regime, conditions, AnalysisStatus.VALID)


def _result(series, strategy, snapshot, evaluated_at, classification, conditions, status) -> MarketRegimeResult:
    payload = f"regime|{series.instrument_id}|{strategy.strategy_id}|{strategy.version}|{snapshot.as_of_timestamp.isoformat()}|{'|'.join(series.observation_ids)}|{classification.value}"
    result_id = f"analysis-{hashlib.sha256(payload.encode()).hexdigest()[:16]}"
    confidence = 1.0 if status is AnalysisStatus.VALID else None
    evidence = (
        analysis_evidence(analysis_id=result_id, evidence_type=EvidenceType.DATA, source="market-regime-engine", timestamp=evaluated_at,
                          observation_ids=series.observation_ids, content_reference="analysis://market-regime/inputs", confidence=confidence, data_quality=series.data_quality),
        analysis_evidence(analysis_id=result_id, evidence_type=EvidenceType.INTERPRETATION, source="market-regime-engine", timestamp=evaluated_at,
                          observation_ids=series.observation_ids, content_reference=f"analysis://market-regime/conditions/{'|'.join(conditions)}", confidence=confidence, data_quality=series.data_quality),
        analysis_evidence(analysis_id=result_id, evidence_type=EvidenceType.INFERENCE, source="market-regime-engine", timestamp=evaluated_at,
                          observation_ids=series.observation_ids, content_reference=f"analysis://market-regime/classification/{classification.value}", confidence=confidence, data_quality=series.data_quality),
    )
    return MarketRegimeResult(result_id, series.instrument_id, strategy, classification, conditions, series.observation_ids,
                              TECHNICAL_CALCULATION_VERSION, evaluated_at, snapshot.as_of_timestamp, series.data_quality,
                              confidence, status, evidence)
