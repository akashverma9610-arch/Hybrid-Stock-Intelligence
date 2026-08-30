"""Measurement-only calibration, redundancy, ablation and regime-validation utilities."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from math import sqrt


@dataclass(frozen=True, slots=True)
class OutcomeSample:
    score: Decimal
    r_multiple: Decimal | None
    win: bool | None
    mfe: Decimal | None
    mae: Decimal | None
    regime: str | None
    horizon: str | None


@dataclass(frozen=True, slots=True)
class CalibrationObservation:
    bucket: str
    sample_count: int
    win_probability: Decimal | None
    expectancy: Decimal | None
    median_r: Decimal | None
    failure_rate: Decimal | None
    regime: str | None
    horizon: str | None
    status: str


@dataclass(frozen=True, slots=True)
class RedundancyObservation:
    left_factor: str
    right_factor: str
    correlation: Decimal | None
    status: str
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class AblationObservation:
    factor: str
    full_metric: Decimal | None
    ablated_metric: Decimal | None
    delta: Decimal | None
    status: str


@dataclass(frozen=True, slots=True)
class RegimeValidationObservation:
    predicted_regime: str
    sample_count: int
    index_return: Decimal | None
    drawdown: Decimal | None
    volatility: Decimal | None
    status: str


class CalibrationService:
    _BUCKETS = ((Decimal("6"), Decimal("7"), "6-7"), (Decimal("7"), Decimal("8"), "7-8"), (Decimal("8"), Decimal("9"), "8-9"), (Decimal("9"), None, "9+"))
    def calibrate(self, samples: tuple[OutcomeSample, ...], *, regime: str | None = None, horizon: str | None = None) -> tuple[CalibrationObservation, ...]:
        selected = tuple(item for item in samples if (regime is None or item.regime == regime) and (horizon is None or item.horizon == horizon))
        result = []
        for low, high, name in self._BUCKETS:
            values = tuple(item for item in selected if item.score >= low and (high is None or item.score < high))
            r = sorted(item.r_multiple for item in values if item.r_multiple is not None)
            wins = tuple(item.win for item in values if item.win is not None)
            result.append(CalibrationObservation(name, len(values), _mean_bool(wins), _mean(tuple(item.r_multiple for item in values if item.r_multiple is not None)), r[len(r)//2] if r else None, Decimal("1") - _mean_bool(wins) if wins else None, regime, horizon, "INSUFFICIENT" if not values else "OBSERVED"))
        return tuple(result)

    @staticmethod
    def ablate(*, factor: str, full_metric: Decimal | None, ablated_metric: Decimal | None) -> AblationObservation:
        return AblationObservation(factor, full_metric, ablated_metric, full_metric - ablated_metric if full_metric is not None and ablated_metric is not None else None, "OBSERVED" if full_metric is not None and ablated_metric is not None else "INSUFFICIENT")


class DiagnosticRedundancyService:
    def correlate(self, *, left_factor: str, left: tuple[Decimal, ...], right_factor: str, right: tuple[Decimal, ...]) -> RedundancyObservation:
        if len(left) != len(right) or len(left) < 2:
            return RedundancyObservation(left_factor, right_factor, None, "INSUFFICIENT", ("PAIRWISE_SAMPLE_INSUFFICIENT",))
        x = [float(v) for v in left]; y = [float(v) for v in right]; mx = sum(x)/len(x); my = sum(y)/len(y)
        denominator = sqrt(sum((v-mx)**2 for v in x) * sum((v-my)**2 for v in y))
        if denominator == 0:
            return RedundancyObservation(left_factor, right_factor, None, "UNVERIFIABLE", ("ZERO_VARIANCE",))
        value = Decimal(str(sum((a-mx)*(b-my) for a,b in zip(x,y)) / denominator))
        return RedundancyObservation(left_factor, right_factor, value, "POSSIBLE_FACTOR_REDUNDANCY" if abs(value) >= Decimal("0.9") else "OBSERVED")


class RegimeValidationService:
    def validate(self, *, predicted_regime: str, outcomes: tuple[tuple[Decimal | None, Decimal | None, Decimal | None], ...]) -> RegimeValidationObservation:
        returns = tuple(item[0] for item in outcomes if item[0] is not None)
        drawdowns = tuple(item[1] for item in outcomes if item[1] is not None)
        volatility = tuple(item[2] for item in outcomes if item[2] is not None)
        return RegimeValidationObservation(predicted_regime, len(outcomes), _mean(returns), _mean(drawdowns), _mean(volatility), "OBSERVED" if outcomes else "INSUFFICIENT")


def _mean(values): return sum(values, Decimal("0")) / len(values) if values else None
def _mean_bool(values): return Decimal(sum(1 for value in values if value)) / Decimal(len(values)) if values else None
