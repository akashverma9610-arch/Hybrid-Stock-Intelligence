from __future__ import annotations

import hashlib
from datetime import datetime

from app.analysis.evidence import analysis_evidence
from app.analysis.models import AnalysisStatus, TrendClassification, TrendResult, TrendRules
from app.analysis.series import AnalysisInputError, closes, price_bar_series
from app.analysis.technical import TECHNICAL_CALCULATION_VERSION, TechnicalAnalysisEngine
from app.domain.models import AsOfSnapshot, EvidenceType, StrategyVersionReference


class TrendEngine:
    def __init__(self, technical_engine: TechnicalAnalysisEngine | None = None) -> None:
        self._technical = technical_engine or TechnicalAnalysisEngine()

    def classify(self, snapshot: AsOfSnapshot, *, instrument_id: str, strategy_version: StrategyVersionReference | None,
                 rules: TrendRules, evaluated_at: datetime) -> TrendResult:
        if strategy_version is None:
            raise AnalysisInputError("Analysis requires a strategy version.")
        if rules.require_price_structure and (rules.pivot_window is None or rules.pivot_window < 1):
            raise AnalysisInputError("A positive configured pivot window is required when price structure is required.")
        series = price_bar_series(snapshot, instrument_id)
        if series.status is not AnalysisStatus.VALID:
            return _result(series, strategy_version, snapshot, evaluated_at, TrendClassification.INSUFFICIENT_DATA,
                           (series.reason or "No eligible price bars.",), AnalysisStatus.INVALID_DATA if series.status is AnalysisStatus.INVALID_DATA else AnalysisStatus.INSUFFICIENT_DATA)
        fast = self._technical.sma(snapshot, instrument_id=instrument_id, strategy_version=strategy_version,
                                   period=rules.fast_sma_period, evaluated_at=evaluated_at)
        slow = self._technical.sma(snapshot, instrument_id=instrument_id, strategy_version=strategy_version,
                                   period=rules.slow_sma_period, evaluated_at=evaluated_at)
        structure = (
            self._technical.price_structure(snapshot, instrument_id=instrument_id, strategy_version=strategy_version,
                                            pivot_window=rules.pivot_window, evaluated_at=evaluated_at)  # type: ignore[arg-type]
            if rules.require_price_structure else None
        )
        if fast.status is not AnalysisStatus.VALID or slow.status is not AnalysisStatus.VALID:
            return _result(series, strategy_version, snapshot, evaluated_at, TrendClassification.INSUFFICIENT_DATA,
                           ("Moving-average requirements are not met.",), AnalysisStatus.INSUFFICIENT_DATA)
        if rules.require_price_structure and (structure is None or structure.status is not AnalysisStatus.VALID):
            return _result(series, strategy_version, snapshot, evaluated_at, TrendClassification.INSUFFICIENT_DATA,
                           ("Confirmed pivot requirements are not met.",), AnalysisStatus.INSUFFICIENT_DATA)
        last_close = closes(series)[-1]
        ma_up = last_close > fast.value > slow.value
        ma_down = last_close < fast.value < slow.value
        structure_up = structure is not None and structure.higher_high is True and structure.higher_low is True
        structure_down = structure is not None and structure.lower_high is True and structure.lower_low is True
        if ma_up and (structure_up or not rules.require_price_structure):
            classification, conditions = TrendClassification.UPTREND, ("close > fast SMA > slow SMA", "higher high and higher low" if rules.require_price_structure else "price structure not required")
        elif ma_down and (structure_down or not rules.require_price_structure):
            classification, conditions = TrendClassification.DOWNTREND, ("close < fast SMA < slow SMA", "lower high and lower low" if rules.require_price_structure else "price structure not required")
        else:
            classification, conditions = TrendClassification.SIDEWAYS, ("Neither configured uptrend nor downtrend conditions are satisfied.",)
        return _result(series, strategy_version, snapshot, evaluated_at, classification, conditions, AnalysisStatus.VALID)


def _result(series, strategy, snapshot, evaluated_at, classification, conditions, status) -> TrendResult:
    payload = f"trend|{series.instrument_id}|{strategy.strategy_id}|{strategy.version}|{snapshot.as_of_timestamp.isoformat()}|{'|'.join(series.observation_ids)}|{classification.value}"
    result_id = f"analysis-{hashlib.sha256(payload.encode()).hexdigest()[:16]}"
    evidence = (
        analysis_evidence(analysis_id=result_id, evidence_type=EvidenceType.DATA, source="trend-engine", timestamp=evaluated_at,
                          observation_ids=series.observation_ids, content_reference="analysis://trend/inputs", confidence=1.0 if status is AnalysisStatus.VALID else None, data_quality=series.data_quality),
        analysis_evidence(analysis_id=result_id, evidence_type=EvidenceType.INTERPRETATION, source="trend-engine", timestamp=evaluated_at,
                          observation_ids=series.observation_ids, content_reference=f"analysis://trend/conditions/{'|'.join(conditions)}", confidence=1.0 if status is AnalysisStatus.VALID else None, data_quality=series.data_quality),
        analysis_evidence(analysis_id=result_id, evidence_type=EvidenceType.INFERENCE, source="trend-engine", timestamp=evaluated_at,
                          observation_ids=series.observation_ids, content_reference=f"analysis://trend/classification/{classification.value}", confidence=1.0 if status is AnalysisStatus.VALID else None, data_quality=series.data_quality),
    )
    return TrendResult(result_id, series.instrument_id, strategy, classification, conditions, series.observation_ids,
                       TECHNICAL_CALCULATION_VERSION, evaluated_at, snapshot.as_of_timestamp, series.data_quality,
                       1.0 if status is AnalysisStatus.VALID else None, status, evidence)
