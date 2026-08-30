from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from types import MappingProxyType
from typing import Any, Mapping

from app.domain.models import DataQuality, Evidence, StrategyVersionReference


class AnalysisStatus(StrEnum):
    VALID = "valid"
    INSUFFICIENT_DATA = "insufficient_data"
    INVALID_DATA = "invalid_data"


class TrendClassification(StrEnum):
    UPTREND = "uptrend"
    DOWNTREND = "downtrend"
    SIDEWAYS = "sideways"
    INSUFFICIENT_DATA = "insufficient_data"


class MarketRegime(StrEnum):
    STRONG_BULL = "strong_bull"
    BULL = "bull"
    SELECTIVE_BULL = "selective_bull"
    NEUTRAL = "neutral"
    SELECTIVE_BEAR = "selective_bear"
    BEAR = "bear"
    PANIC = "panic"
    INSUFFICIENT_DATA = "insufficient_data"


class RelativeStrengthClassification(StrEnum):
    LEADER = "leader"
    EMERGING_LEADER = "emerging_leader"
    AVERAGE = "average"
    LAGGARD = "laggard"
    INSUFFICIENT_DATA = "insufficient_data"


@dataclass(frozen=True, slots=True)
class IndicatorResult:
    id: str
    instrument_id: str
    strategy_version: StrategyVersionReference
    value: float | None
    calculation_name: str
    parameters: Mapping[str, Any]
    input_observation_ids: tuple[str, ...]
    calculation_version: str
    evaluated_at: datetime
    as_of_timestamp: datetime
    data_quality: DataQuality
    confidence: float | None
    status: AnalysisStatus
    evidence: tuple[Evidence, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "parameters", MappingProxyType(dict(self.parameters)))

    @property
    def evidence_ids(self) -> tuple[str, ...]:
        return tuple(item.id for item in self.evidence)


@dataclass(frozen=True, slots=True)
class PriceStructureResult:
    id: str
    instrument_id: str
    strategy_version: StrategyVersionReference
    higher_high: bool | None
    higher_low: bool | None
    lower_high: bool | None
    lower_low: bool | None
    pivot_observation_ids: tuple[str, ...]
    parameters: Mapping[str, Any]
    calculation_version: str
    evaluated_at: datetime
    as_of_timestamp: datetime
    data_quality: DataQuality
    confidence: float | None
    status: AnalysisStatus
    evidence: tuple[Evidence, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "parameters", MappingProxyType(dict(self.parameters)))

    @property
    def evidence_ids(self) -> tuple[str, ...]:
        return tuple(item.id for item in self.evidence)


@dataclass(frozen=True, slots=True)
class TrendRules:
    fast_sma_period: int
    slow_sma_period: int
    require_price_structure: bool
    pivot_window: int | None = None


@dataclass(frozen=True, slots=True)
class TrendResult:
    id: str
    instrument_id: str
    strategy_version: StrategyVersionReference
    classification: TrendClassification
    conditions: tuple[str, ...]
    input_observation_ids: tuple[str, ...]
    calculation_version: str
    evaluated_at: datetime
    as_of_timestamp: datetime
    data_quality: DataQuality
    confidence: float | None
    status: AnalysisStatus
    evidence: tuple[Evidence, ...] = ()

    @property
    def evidence_ids(self) -> tuple[str, ...]:
        return tuple(item.id for item in self.evidence)


@dataclass(frozen=True, slots=True)
class MarketRegimeRules:
    fast_sma_period: int
    slow_sma_period: int
    atr_period: int
    return_lookback: int
    strong_bull_minimum_return: float
    bull_minimum_return: float
    selective_bull_minimum_return: float
    selective_bear_maximum_return: float
    bear_maximum_return: float
    panic_maximum_return: float
    panic_atr_percent: float


@dataclass(frozen=True, slots=True)
class MarketRegimeResult:
    id: str
    benchmark_instrument_id: str
    strategy_version: StrategyVersionReference
    classification: MarketRegime
    conditions: tuple[str, ...]
    input_observation_ids: tuple[str, ...]
    calculation_version: str
    evaluated_at: datetime
    as_of_timestamp: datetime
    data_quality: DataQuality
    confidence: float | None
    status: AnalysisStatus
    evidence: tuple[Evidence, ...] = ()

    @property
    def evidence_ids(self) -> tuple[str, ...]:
        return tuple(item.id for item in self.evidence)


@dataclass(frozen=True, slots=True)
class RelativeStrengthRules:
    lookback: int
    leader_minimum_excess_return: float
    emerging_leader_minimum_excess_return: float
    laggard_maximum_excess_return: float


@dataclass(frozen=True, slots=True)
class RelativeStrengthResult:
    id: str
    instrument_id: str
    benchmark_instrument_id: str
    sector_instrument_id: str | None
    strategy_version: StrategyVersionReference
    absolute_return: float | None
    benchmark_return: float | None
    excess_return: float | None
    sector_return: float | None
    sector_excess_return: float | None
    classification: RelativeStrengthClassification
    input_observation_ids: tuple[str, ...]
    calculation_version: str
    evaluated_at: datetime
    as_of_timestamp: datetime
    data_quality: DataQuality
    confidence: float | None
    status: AnalysisStatus
    evidence: tuple[Evidence, ...] = ()

    @property
    def evidence_ids(self) -> tuple[str, ...]:
        return tuple(item.id for item in self.evidence)
