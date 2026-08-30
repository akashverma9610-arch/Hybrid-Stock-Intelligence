from __future__ import annotations

import hashlib
from datetime import datetime

from app.analysis.evidence import analysis_evidence
from app.analysis.models import AnalysisStatus, RelativeStrengthClassification, RelativeStrengthResult, RelativeStrengthRules
from app.analysis.series import AnalysisInputError, closes, price_bar_series
from app.domain.models import AsOfSnapshot, EvidenceType, StrategyVersionReference


class RelativeStrengthEngine:
    def calculate(self, snapshot: AsOfSnapshot, *, instrument_id: str, benchmark_instrument_id: str,
                  sector_instrument_id: str | None, strategy_version: StrategyVersionReference | None,
                  rules: RelativeStrengthRules, evaluated_at: datetime) -> RelativeStrengthResult:
        if strategy_version is None:
            raise AnalysisInputError("Analysis requires a strategy version.")
        stock, benchmark = price_bar_series(snapshot, instrument_id), price_bar_series(snapshot, benchmark_instrument_id)
        if (stock.status is not AnalysisStatus.VALID or benchmark.status is not AnalysisStatus.VALID
                or len(stock.bars) < rules.lookback + 1 or len(benchmark.bars) < rules.lookback + 1):
            input_ids = stock.observation_ids + benchmark.observation_ids
            return _result(stock, benchmark, None, strategy_version, snapshot, evaluated_at, rules,
                           None, None, None, None, None, RelativeStrengthClassification.INSUFFICIENT_DATA,
                           AnalysisStatus.INVALID_DATA if AnalysisStatus.INVALID_DATA in {stock.status, benchmark.status} else AnalysisStatus.INSUFFICIENT_DATA, input_ids)
        stock_return = _return(stock, rules.lookback)
        benchmark_return = _return(benchmark, rules.lookback)
        excess = stock_return - benchmark_return
        if excess >= rules.leader_minimum_excess_return:
            classification = RelativeStrengthClassification.LEADER
        elif excess >= rules.emerging_leader_minimum_excess_return:
            classification = RelativeStrengthClassification.EMERGING_LEADER
        elif excess <= rules.laggard_maximum_excess_return:
            classification = RelativeStrengthClassification.LAGGARD
        else:
            classification = RelativeStrengthClassification.AVERAGE

        sector, sector_return, sector_excess = None, None, None
        if sector_instrument_id:
            sector = price_bar_series(snapshot, sector_instrument_id)
            if sector.status is AnalysisStatus.VALID and len(sector.bars) >= rules.lookback + 1:
                sector_return = _return(sector, rules.lookback)
                sector_excess = stock_return - sector_return
        input_ids = stock.observation_ids + benchmark.observation_ids + (sector.observation_ids if sector else ())
        return _result(stock, benchmark, sector, strategy_version, snapshot, evaluated_at, rules, stock_return,
                       benchmark_return, excess, sector_return, sector_excess, classification, AnalysisStatus.VALID, input_ids)


def _return(series, lookback: int) -> float:
    values = closes(series)
    return (values[-1] / values[-1 - lookback]) - 1


def _result(stock, benchmark, sector, strategy, snapshot, evaluated_at, rules, stock_return, benchmark_return, excess,
            sector_return, sector_excess, classification, status, input_ids) -> RelativeStrengthResult:
    payload = f"relative-strength|{stock.instrument_id}|{benchmark.instrument_id}|{strategy.strategy_id}|{strategy.version}|{snapshot.as_of_timestamp.isoformat()}|{'|'.join(input_ids)}|{classification.value}|{rules.lookback}"
    result_id = f"analysis-{hashlib.sha256(payload.encode()).hexdigest()[:16]}"
    quality = _quality(stock.data_quality, benchmark.data_quality, sector.data_quality if sector else None)
    confidence = 1.0 if status is AnalysisStatus.VALID else None
    content = f"stock_return={stock_return};benchmark_return={benchmark_return};excess_return={excess};sector_excess_return={sector_excess}"
    evidence = (
        analysis_evidence(analysis_id=result_id, evidence_type=EvidenceType.DATA, source="relative-strength-engine", timestamp=evaluated_at,
                          observation_ids=input_ids, content_reference="analysis://relative-strength/inputs", confidence=confidence, data_quality=quality),
        analysis_evidence(analysis_id=result_id, evidence_type=EvidenceType.INTERPRETATION, source="relative-strength-engine", timestamp=evaluated_at,
                          observation_ids=input_ids, content_reference=f"analysis://relative-strength/returns/{content}", confidence=confidence, data_quality=quality),
        analysis_evidence(analysis_id=result_id, evidence_type=EvidenceType.INFERENCE, source="relative-strength-engine", timestamp=evaluated_at,
                          observation_ids=input_ids, content_reference=f"analysis://relative-strength/classification/{classification.value}", confidence=confidence, data_quality=quality),
    )
    return RelativeStrengthResult(result_id, stock.instrument_id, benchmark.instrument_id,
                                  sector.instrument_id if sector else None, strategy, stock_return, benchmark_return,
                                  excess, sector_return, sector_excess, classification, input_ids, "relative-strength-v1",
                                  evaluated_at, snapshot.as_of_timestamp, quality, confidence, status, evidence)


def _quality(*values):
    values = set(value for value in values if value is not None)
    if not values:
        from app.domain.models import DataQuality
        return DataQuality.UNKNOWN
    from app.domain.models import DataQuality
    if DataQuality.LOW in values:
        return DataQuality.LOW
    if DataQuality.MEDIUM in values:
        return DataQuality.MEDIUM
    if DataQuality.HIGH in values:
        return DataQuality.HIGH
    return DataQuality.UNKNOWN
