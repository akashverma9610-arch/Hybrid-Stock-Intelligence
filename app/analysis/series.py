from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.analysis.models import AnalysisStatus
from app.domain.models import AsOfSnapshot, DataQuality, MarketObservation, ObservationKind


class AnalysisInputError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class PriceBarSeries:
    instrument_id: str
    bars: tuple[MarketObservation, ...]
    status: AnalysisStatus
    data_quality: DataQuality
    reason: str | None = None

    @property
    def observation_ids(self) -> tuple[str, ...]:
        return tuple(bar.id for bar in self.bars)


def price_bar_series(snapshot: AsOfSnapshot, instrument_id: str) -> PriceBarSeries:
    """Read only validated, chronological bars that were present in the supplied snapshot."""
    candidates = tuple(
        item for item in snapshot.observations
        if item.instrument.id == instrument_id and item.kind is ObservationKind.PRICE_BAR
    )
    if any(item.validation is None or not item.validation.eligible_for_analysis for item in candidates):
        return PriceBarSeries(instrument_id, (), AnalysisStatus.INVALID_DATA, DataQuality.UNKNOWN, "Snapshot contains ineligible observations.")
    if not candidates:
        return PriceBarSeries(instrument_id, (), AnalysisStatus.INSUFFICIENT_DATA, DataQuality.UNKNOWN, "No price bars are present in this snapshot.")
    ordered = tuple(sorted(candidates, key=lambda item: (item.provenance.market_timestamp, item.id)))
    for item in ordered:
        if not _valid_bar(item):
            return PriceBarSeries(instrument_id, (), AnalysisStatus.INVALID_DATA, DataQuality.UNKNOWN, f"Malformed price bar: {item.id}.")
        if item.provenance.market_timestamp > snapshot.as_of_timestamp or item.provenance.retrieved_timestamp > snapshot.as_of_timestamp:
            return PriceBarSeries(instrument_id, (), AnalysisStatus.INVALID_DATA, DataQuality.UNKNOWN, f"Look-ahead bar present: {item.id}.")
    return PriceBarSeries(instrument_id, ordered, AnalysisStatus.VALID, _lowest_quality(ordered))


def closes(series: PriceBarSeries) -> tuple[float, ...]:
    return tuple(float(item.payload["close"]) for item in series.bars)


def _valid_bar(item: MarketObservation) -> bool:
    return (
        isinstance(item.payload, dict)
        and all(key in item.payload and _is_number(item.payload[key]) for key in ("open", "high", "low", "close"))
    )


def _is_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _lowest_quality(bars: tuple[MarketObservation, ...]) -> DataQuality:
    values = {item.provenance.data_quality for item in bars}
    if DataQuality.LOW in values:
        return DataQuality.LOW
    if DataQuality.MEDIUM in values:
        return DataQuality.MEDIUM
    if DataQuality.HIGH in values:
        return DataQuality.HIGH
    return DataQuality.UNKNOWN
