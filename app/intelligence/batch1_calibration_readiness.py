"""Read-only, PIT-bound readiness facts for deferred Batch 1 calibration.

This is deliberately not an Event/Catalyst or Market-Red policy.  Callers pass
canonical retained evidence and completed-session coverage; the module writes
nothing, selects no parameter, and creates no signal.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from types import MappingProxyType
from typing import Mapping, Sequence

from app.intelligence.external_intelligence import EvidenceVersion, ExposureType, Materiality


class CalibrationReadinessState(StrEnum):
    READY_FOR_RESEARCH = "READY_FOR_RESEARCH"
    INSUFFICIENT_FOR_CALIBRATION = "INSUFFICIENT_FOR_CALIBRATION"
    UNAVAILABLE = "UNAVAILABLE"


class CalibrationInsufficiencyCode(StrEnum):
    NO_ELIGIBLE_PRIMARY_EVENT = "NO_ELIGIBLE_PRIMARY_EVENT"
    VERIFIED_EXPOSURE_MISSING = "VERIFIED_EXPOSURE_MISSING"
    EVENT_LIFECYCLE_UNTYPED = "EVENT_LIFECYCLE_UNTYPED"
    STOCK_BENCHMARK_ALIGNMENT_MISSING = "STOCK_BENCHMARK_ALIGNMENT_MISSING"
    FORWARD_COMPLETED_SESSIONS_MISSING = "FORWARD_COMPLETED_SESSIONS_MISSING"
    BENCHMARK_SESSIONS_MISSING = "BENCHMARK_SESSIONS_MISSING"
    HISTORICAL_BREADTH_MISSING = "HISTORICAL_BREADTH_MISSING"
    PIT_CONSTITUENT_HISTORY_MISSING = "PIT_CONSTITUENT_HISTORY_MISSING"
    HISTORICAL_SECTOR_RS_UNAVAILABLE = "HISTORICAL_SECTOR_RS_UNAVAILABLE"
    TRADED_VALUE_OR_VOLUME_HISTORY_MISSING = "TRADED_VALUE_OR_VOLUME_HISTORY_MISSING"
    OFFICIAL_DELIVERY_HISTORY_MISSING = "OFFICIAL_DELIVERY_HISTORY_MISSING"
    PERSISTENCE_WINDOW_UNOBSERVABLE = "PERSISTENCE_WINDOW_UNOBSERVABLE"


WINDOWS = (1, 2, 3, 5, 10)
ALLOWED_EXPOSURES = frozenset({ExposureType.DIRECT, ExposureType.SUPPLY_CHAIN})


def _aware(value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("CALIBRATION_TIMESTAMP_TIMEZONE_REQUIRED")


def _ordered_sessions(values: Sequence[datetime]) -> tuple[datetime, ...]:
    supplied = tuple(values)
    if len(supplied) != len(set(supplied)):
        raise ValueError("CALIBRATION_SESSION_DUPLICATE")
    result = tuple(sorted(supplied))
    for value in result:
        _aware(value)
    return result


@dataclass(frozen=True, slots=True)
class MarketCalibrationCoverage:
    """Already-derived retained coverage; no current membership fallback."""

    benchmark_sessions: Mapping[str, Sequence[datetime]]
    historical_breadth_sessions: Sequence[datetime]
    pit_constituent_history_available: bool
    aligned_stock_benchmark_observations: int
    historical_sector_rs_available: bool
    traded_value_or_volume_observations: int
    official_delivery_sessions: Sequence[datetime]

    def __post_init__(self) -> None:
        if self.aligned_stock_benchmark_observations < 0 or self.traded_value_or_volume_observations < 0:
            raise ValueError("CALIBRATION_COVERAGE_COUNT_INVALID")
        object.__setattr__(self, "benchmark_sessions", MappingProxyType({
            key: _ordered_sessions(value) for key, value in sorted(self.benchmark_sessions.items())
        }))
        object.__setattr__(self, "historical_breadth_sessions", _ordered_sessions(self.historical_breadth_sessions))
        object.__setattr__(self, "official_delivery_sessions", _ordered_sessions(self.official_delivery_sessions))


@dataclass(frozen=True, slots=True)
class EventCalibrationReadiness:
    total_events: int
    eligible_primary_events: int
    verified_company_exposures: int
    events_by_family: tuple[tuple[str, int], ...]
    events_by_materiality: tuple[tuple[str, int], ...]
    timestamp_coverage: tuple[tuple[str, int], ...]
    typed_lifecycle_events: int
    aligned_event_instruments: int
    forward_observable_by_window: tuple[tuple[int, int], ...]
    state: CalibrationReadinessState
    insufficiency_codes: tuple[CalibrationInsufficiencyCode, ...]


@dataclass(frozen=True, slots=True)
class MarketRedCalibrationReadiness:
    benchmark_session_coverage: tuple[tuple[str, int, datetime | None], ...]
    historical_breadth_sessions: int
    pit_constituent_history_available: bool
    aligned_stock_benchmark_observations: int
    historical_sector_rs_available: bool
    traded_value_or_volume_observations: int
    official_delivery_sessions: int
    persistence_observable_by_window: tuple[tuple[int, bool], ...]
    state: CalibrationReadinessState
    insufficiency_codes: tuple[CalibrationInsufficiencyCode, ...]


@dataclass(frozen=True, slots=True)
class Batch1CalibrationReadiness:
    event_catalyst: EventCalibrationReadiness
    market_red: MarketRedCalibrationReadiness


def assess_batch1_calibration_readiness(
    evidence_versions: Sequence[EvidenceVersion],
    market: MarketCalibrationCoverage,
    *,
    primary_source_types: frozenset[str],
    typed_lifecycle_event_ids: frozenset[str] = frozenset(),
    stock_completed_sessions: Mapping[str, Sequence[datetime]] | None = None,
) -> Batch1CalibrationReadiness:
    """Assess retained inputs at their own timestamps, without a runtime clock."""
    if not primary_source_types:
        raise ValueError("CALIBRATION_PRIMARY_SOURCE_TYPES_REQUIRED")
    normalized_stock = MappingProxyType({
        key: _ordered_sessions(value) for key, value in sorted((stock_completed_sessions or {}).items())
    })
    values = tuple(sorted(evidence_versions, key=lambda item: (item.received_at, item.evidence_version_id)))
    eligible = tuple(item for item in values if item.primary_source.source_type in primary_source_types)
    exposures = tuple(
        (item, exposure) for item in eligible for exposure in item.company_exposures
        if exposure.exposure_type in ALLOWED_EXPOSURES
        and exposure.verification_status == "VERIFIED" and exposure.canonical_instrument_id
    )
    forward = []
    for window in WINDOWS:
        count = sum(
            len(tuple(session for session in normalized_stock.get(str(exposure.canonical_instrument_id), ()) if session > item.received_at)) >= window
            and all(len(tuple(session for session in sessions if session > item.received_at)) >= window
                    for sessions in market.benchmark_sessions.values())
            for item, exposure in exposures
        )
        forward.append((window, count))
    event_codes: list[CalibrationInsufficiencyCode] = []
    if not eligible: event_codes.append(CalibrationInsufficiencyCode.NO_ELIGIBLE_PRIMARY_EVENT)
    if not exposures: event_codes.append(CalibrationInsufficiencyCode.VERIFIED_EXPOSURE_MISSING)
    if not typed_lifecycle_event_ids: event_codes.append(CalibrationInsufficiencyCode.EVENT_LIFECYCLE_UNTYPED)
    if not exposures or not normalized_stock: event_codes.append(CalibrationInsufficiencyCode.STOCK_BENCHMARK_ALIGNMENT_MISSING)
    if not any(count for _, count in forward): event_codes.append(CalibrationInsufficiencyCode.FORWARD_COMPLETED_SESSIONS_MISSING)
    event_state = CalibrationReadinessState.READY_FOR_RESEARCH if not event_codes else CalibrationReadinessState.INSUFFICIENT_FOR_CALIBRATION
    timestamp_coverage = tuple((field, sum(getattr(item, field) is not None for item in values)) for field in ("published_at", "discovered_at", "received_at", "effective_at"))
    event = EventCalibrationReadiness(
        len(values), len(eligible), len(exposures), tuple(sorted(Counter(item.event.event_type.value for item in values).items())),
        tuple(sorted(Counter(item.event.materiality.value for item in values).items())), timestamp_coverage,
        len(set(typed_lifecycle_event_ids) & {item.event.canonical_event_id for item in values}), len({str(value.canonical_instrument_id) for _, value in exposures}),
        tuple(forward), event_state, tuple(event_codes),
    )
    benchmark = tuple((key, len(sessions), sessions[-1] if sessions else None) for key, sessions in market.benchmark_sessions.items())
    market_codes: list[CalibrationInsufficiencyCode] = []
    if not market.benchmark_sessions or any(not sessions for sessions in market.benchmark_sessions.values()): market_codes.append(CalibrationInsufficiencyCode.BENCHMARK_SESSIONS_MISSING)
    if not market.historical_breadth_sessions: market_codes.append(CalibrationInsufficiencyCode.HISTORICAL_BREADTH_MISSING)
    if not market.pit_constituent_history_available: market_codes.append(CalibrationInsufficiencyCode.PIT_CONSTITUENT_HISTORY_MISSING)
    if not market.aligned_stock_benchmark_observations: market_codes.append(CalibrationInsufficiencyCode.STOCK_BENCHMARK_ALIGNMENT_MISSING)
    if not market.historical_sector_rs_available: market_codes.append(CalibrationInsufficiencyCode.HISTORICAL_SECTOR_RS_UNAVAILABLE)
    if not market.traded_value_or_volume_observations: market_codes.append(CalibrationInsufficiencyCode.TRADED_VALUE_OR_VOLUME_HISTORY_MISSING)
    if not market.official_delivery_sessions: market_codes.append(CalibrationInsufficiencyCode.OFFICIAL_DELIVERY_HISTORY_MISSING)
    persistence = tuple((window, all(len(sessions) >= window for sessions in market.benchmark_sessions.values()) and bool(market.historical_breadth_sessions)) for window in (2, 3))
    if not all(value for _, value in persistence): market_codes.append(CalibrationInsufficiencyCode.PERSISTENCE_WINDOW_UNOBSERVABLE)
    market_state = CalibrationReadinessState.READY_FOR_RESEARCH if not market_codes else CalibrationReadinessState.INSUFFICIENT_FOR_CALIBRATION
    return Batch1CalibrationReadiness(event, MarketRedCalibrationReadiness(benchmark, len(market.historical_breadth_sessions), market.pit_constituent_history_available, market.aligned_stock_benchmark_observations, market.historical_sector_rs_available, market.traded_value_or_volume_observations, len(market.official_delivery_sessions), persistence, market_state, tuple(market_codes)))


__all__ = ["Batch1CalibrationReadiness", "CalibrationInsufficiencyCode", "CalibrationReadinessState", "EventCalibrationReadiness", "MarketCalibrationCoverage", "MarketRedCalibrationReadiness", "WINDOWS", "assess_batch1_calibration_readiness"]
