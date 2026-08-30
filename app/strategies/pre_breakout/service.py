"""Deterministic, point-in-time positional pre-breakout candidate discovery."""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP

from app.execution_simulation.service import ExecutionFeasibility, ExecutionFeasibilityStatus
from app.analysis.models import AnalysisStatus
from app.analysis.technical import TechnicalAnalysisEngine
from app.domain.models import AsOfSnapshot, StrategyVersionReference
from app.strategies.common.models import CandidateStatus, SetupQuality, StrategyCandidate, StrategyFamily


@dataclass(frozen=True, slots=True)
class PreBreakoutConfig:
    version: str = "pre-breakout-v1"
    benchmark: str = "NIFTY_500"
    mrs_lookbacks: tuple[int, ...] = (20, 60, 120)
    top_sector_count: int = 3
    bbw_percentile_max: Decimal = Decimal("10")
    bbw_history_sessions: int = 120
    atr_window: int = 5
    consolidation_volume_ratio_max: Decimal = Decimal("0.50")
    delivery_pct_min: Decimal = Decimal("60")
    high_distance_min_pct: Decimal = Decimal("3")
    high_distance_max_pct: Decimal = Decimal("6")
    rsi_min: Decimal = Decimal("55")
    rsi_max: Decimal = Decimal("65")
    minimum_reward_risk: Decimal = Decimal("3")
    delivery_required: bool = True
    breakout_confirmation_rule: str = "STRUCTURAL_RESISTANCE_ONLY"
    atr_contraction_rule: str = "MEAN_LAST_N_ATR_LT_MEAN_PRECEDING_N_ATR"

    def __post_init__(self) -> None:
        if self.top_sector_count < 1 or self.atr_window < 1:
            raise ValueError("Top-sector count and ATR window must be positive.")


@dataclass(frozen=True, slots=True)
class SectorRelativeStrength:
    sector: str
    as_of: datetime
    mrs_20: Decimal | None
    mrs_60: Decimal | None
    mrs_120: Decimal | None
    source_ids: tuple[str, ...]
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class SectorBreadth:
    sector: str
    as_of: datetime
    membership_snapshot_id: str
    above_50dma_pct: Decimal | None
    above_200dma_pct: Decimal | None
    constituent_count: int
    eligible_constituent_ids: tuple[str, ...]
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class SectorScan:
    scan_id: str
    config_version: str
    as_of: datetime
    benchmark: str
    selected_sectors: tuple[str, ...]
    relative_strength: tuple[SectorRelativeStrength, ...]
    breadth: tuple[SectorBreadth, ...]
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class PreBreakoutInput:
    candidate_id: str
    instrument_id: str
    sector: str
    scan_as_of: datetime
    universe_snapshot_id: str
    evidence_ids: tuple[str, ...]
    bbw_percentile: Decimal | None
    atr_recent: tuple[Decimal, ...]
    atr_prior: tuple[Decimal, ...]
    consolidation_volumes: tuple[Decimal, ...]
    volume_sma20: Decimal | None
    delivery_pct: Decimal | None
    price: Decimal | None
    high_52_week: Decimal | None
    rsi14: Decimal | None
    structural_resistance: Decimal | None
    structural_invalidation: Decimal | None
    realistic_target: Decimal | None
    sector_evidence_ids: tuple[str, ...] = ()
    execution_feasibility: ExecutionFeasibility | None = None


def mansfield_relative_strength(*, sector_prices: tuple[Decimal, ...], benchmark_prices: tuple[Decimal, ...], lookback: int) -> Decimal | None:
    """`100 * (relative[-1] / mean(relative[-L:]) - 1)`, with no future input."""
    if lookback < 1 or len(sector_prices) != len(benchmark_prices) or len(sector_prices) < lookback:
        return None
    if any(value <= 0 for value in (*sector_prices, *benchmark_prices)):
        return None
    line = tuple(sector / benchmark for sector, benchmark in zip(sector_prices, benchmark_prices, strict=True))
    mean = sum(line[-lookback:], Decimal("0")) / Decimal(lookback)
    return None if mean == 0 else Decimal("100") * (line[-1] / mean - Decimal("1"))


class PreBreakoutEngine:
    def __init__(self, technical: TechnicalAnalysisEngine | None = None) -> None:
        self._technical = technical or TechnicalAnalysisEngine()

    def sector_scan(self, *, scan_id: str, as_of: datetime, values: tuple[tuple[SectorRelativeStrength, SectorBreadth], ...], config: PreBreakoutConfig) -> SectorScan:
        ranked = sorted(values, key=lambda pair: _sector_sort_key(pair[0], pair[1]))
        selected = tuple(item[0].sector for item in ranked[:config.top_sector_count] if item[0].mrs_20 is not None)
        return SectorScan(scan_id, config.version, as_of, config.benchmark, selected, tuple(item[0] for item in ranked), tuple(item[1] for item in ranked), ())

    def evaluate(self, value: PreBreakoutInput, *, config: PreBreakoutConfig) -> StrategyCandidate:
        checks: list[tuple[str, bool | None]] = [
            ("BBW", None if value.bbw_percentile is None else value.bbw_percentile <= config.bbw_percentile_max),
            ("ATR_CONTRACTION", _atr_contracts(value.atr_recent, value.atr_prior, config.atr_window)),
            ("QUIET_CONSOLIDATION_VOLUME", _quiet_volume(value.consolidation_volumes, value.volume_sma20, config)),
            ("DELIVERY", None if value.delivery_pct is None else value.delivery_pct > config.delivery_pct_min),
            ("HIGH_PROXIMITY", _high_proximity(value.price, value.high_52_week, config)),
            ("RSI14", None if value.rsi14 is None else config.rsi_min <= value.rsi14 <= config.rsi_max),
        ]
        evaluated = tuple(name for name, state in checks if state is not None)
        passed = tuple(name for name, state in checks if state is True)
        quality = SetupQuality("setup-quality:" + value.candidate_id, StrategyFamily.PRE_BREAKOUT, config.version,
                               _quality(passed, evaluated), evaluated, passed, value.evidence_ids,
                               tuple(name + "_UNAVAILABLE" for name, state in checks if state is None))
        warnings = list(quality.warnings)
        if value.delivery_pct is None:
            warnings.append("DELIVERY_DATA_UNAVAILABLE")
        if any(state is False for _, state in checks):
            return _candidate(value, config, CandidateStatus.SETUP_REJECTED, quality, warnings + [name + "_FILTER_FAILED" for name, state in checks if state is False])
        if config.delivery_required and value.delivery_pct is None:
            return _candidate(value, config, CandidateStatus.PARTIAL, quality, warnings)
        if any(state is None for _, state in checks):
            return _candidate(value, config, CandidateStatus.PARTIAL, quality, warnings)
        rr = _reward_risk(value.structural_resistance, value.structural_invalidation, value.realistic_target)
        if rr is None:
            return _candidate(value, config, CandidateStatus.PARTIAL, quality, warnings + ["STRUCTURAL_TRIGGER_STOP_OR_TARGET_UNAVAILABLE"])
        if rr < config.minimum_reward_risk:
            return _candidate(value, config, CandidateStatus.SETUP_REJECTED, quality, warnings + ["REWARD_RISK_BELOW_MINIMUM"], rr)
        if value.execution_feasibility and value.execution_feasibility.status is ExecutionFeasibilityStatus.SETUP_VALID_EXECUTION_REJECTED:
            return _candidate(value, config, CandidateStatus.SETUP_VALID_EXECUTION_REJECTED, quality, warnings + list(value.execution_feasibility.warnings), rr)
        if value.execution_feasibility and value.execution_feasibility.status is ExecutionFeasibilityStatus.RESEARCH_REQUIRED:
            warnings.extend(value.execution_feasibility.warnings)
        return _candidate(value, config, CandidateStatus.CANDIDATE_GENERATED, quality, warnings, rr)

    def evaluate_with_canonical_bbw(self, value: PreBreakoutInput, *, snapshot: AsOfSnapshot,
                                    strategy_version: StrategyVersionReference, config: PreBreakoutConfig) -> StrategyCandidate:
        """Evaluate a setup after deriving BBW solely at the canonical TA boundary."""
        bbw = self._technical.bollinger_band_width_percentile(
            snapshot, instrument_id=value.instrument_id, strategy_version=strategy_version,
            evaluated_at=value.scan_as_of, history_sessions=config.bbw_history_sessions,
        )
        derived = replace(
            value,
            bbw_percentile=Decimal(str(bbw.value)) if bbw.status is AnalysisStatus.VALID and bbw.value is not None else None,
            evidence_ids=tuple(dict.fromkeys((*value.evidence_ids, bbw.id, *bbw.input_observation_ids))),
        )
        return self.evaluate(derived, config=config)


def _candidate(value: PreBreakoutInput, config: PreBreakoutConfig, status: CandidateStatus, quality: SetupQuality, warnings: list[str] | tuple[str, ...], rr: Decimal | None = None) -> StrategyCandidate:
    return StrategyCandidate(value.candidate_id, StrategyFamily.PRE_BREAKOUT, config.version, value.instrument_id, value.sector,
                             value.scan_as_of, value.universe_snapshot_id, status, quality, value.evidence_ids,
                             tuple(sorted(set(("PRICE_STRUCTURE", "TECHNICAL", "VOLUME", "DELIVERY", "SECTOR_RS_BREADTH")))), "2_TO_8_WEEKS",
                             value.structural_resistance, value.structural_invalidation, value.realistic_target, rr,
                             value.sector_evidence_ids, (), tuple(sorted(set(warnings))))


def _atr_contracts(recent: tuple[Decimal, ...], prior: tuple[Decimal, ...], window: int) -> bool | None:
    if len(recent) < window or len(prior) < window:
        return None
    return sum(recent[-window:], Decimal("0")) / window < sum(prior[-window:], Decimal("0")) / window


def _quiet_volume(volumes: tuple[Decimal, ...], sma20: Decimal | None, config: PreBreakoutConfig) -> bool | None:
    if not volumes or sma20 is None or sma20 <= 0:
        return None
    return all(volume < config.consolidation_volume_ratio_max * sma20 for volume in volumes)


def _high_proximity(price: Decimal | None, high: Decimal | None, config: PreBreakoutConfig) -> bool | None:
    if price is None or high is None or high <= 0:
        return None
    below = Decimal("100") * (high - price) / high
    return config.high_distance_min_pct <= below <= config.high_distance_max_pct


def _reward_risk(trigger: Decimal | None, stop: Decimal | None, target: Decimal | None) -> Decimal | None:
    if None in (trigger, stop, target) or trigger is None or stop is None or target is None or trigger <= stop or target <= trigger:
        return None
    return (target - trigger) / (trigger - stop)


def _quality(passed: tuple[str, ...], evaluated: tuple[str, ...]) -> Decimal:
    if not evaluated:
        return Decimal("0")
    return (Decimal("100") * Decimal(len(passed)) / Decimal(len(evaluated))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _sector_sort_key(rs: SectorRelativeStrength, breadth: SectorBreadth) -> tuple:
    # Lexicographic rank avoids undisclosed permanent weights.
    missing = Decimal("-999999")
    return (- (rs.mrs_20 if rs.mrs_20 is not None else missing), - (rs.mrs_60 if rs.mrs_60 is not None else missing),
            - (rs.mrs_120 if rs.mrs_120 is not None else missing), - (breadth.above_50dma_pct if breadth.above_50dma_pct is not None else missing),
            - (breadth.above_200dma_pct if breadth.above_200dma_pct is not None else missing), rs.sector)
