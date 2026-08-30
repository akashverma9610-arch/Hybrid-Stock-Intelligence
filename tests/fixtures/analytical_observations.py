from datetime import UTC, datetime, timedelta

from app.domain.models import (
    AsOfSnapshot, DataQuality, Instrument, MarketObservation, ObservationKind,
    Provenance, StrategyVersionReference, ValidationResult, ValidationStatus,
)


ANALYSIS_TIME = datetime(2026, 8, 21, 12, 0, tzinfo=UTC)
STRATEGY_REFERENCE = StrategyVersionReference("nse-manager", "0.1")


def bars(instrument_id: str, closes: list[float], *, start: datetime | None = None,
         highs: list[float] | None = None, lows: list[float] | None = None,
         volumes: list[float] | None = None) -> tuple[MarketObservation, ...]:
    start = start or (ANALYSIS_TIME - timedelta(days=len(closes)))
    instrument = Instrument(instrument_id, instrument_id.upper(), "MOCK")
    result = []
    for index, close in enumerate(closes):
        timestamp = start + timedelta(days=index)
        result.append(MarketObservation(
            id=f"{instrument_id}-{index:02d}", instrument=instrument, kind=ObservationKind.PRICE_BAR,
            payload={"open": close, "high": highs[index] if highs else close + 1, "low": lows[index] if lows else close - 1, "close": close, **({"volume": volumes[index]} if volumes else {})},
            provenance=Provenance("mock-analysis", f"{instrument_id}-source-{index}", timestamp, timestamp, DataQuality.HIGH),
            validation=ValidationResult(ValidationStatus.VALID, ANALYSIS_TIME),
        ))
    return tuple(result)


def snapshot(*series: tuple[MarketObservation, ...], as_of: datetime = ANALYSIS_TIME) -> AsOfSnapshot:
    return AsOfSnapshot("analysis-snapshot", as_of, as_of, "fixture", tuple(item for group in series for item in group))


def uptrend_bars(instrument_id: str = "stock") -> tuple[MarketObservation, ...]:
    return bars(instrument_id, [10, 12, 11, 14, 13, 16, 15, 18])


def downtrend_bars(instrument_id: str = "stock") -> tuple[MarketObservation, ...]:
    return bars(instrument_id, [18, 16, 17, 14, 15, 12, 13, 10])


def sideways_bars(instrument_id: str = "stock") -> tuple[MarketObservation, ...]:
    return bars(instrument_id, [10, 10.2, 10.0, 10.2, 10.0, 10.1, 10.0, 10.1])


def invalid_bar_snapshot() -> AsOfSnapshot:
    item = bars("invalid", [10])[0]
    invalid = MarketObservation(item.id, item.instrument, item.kind, item.payload, item.provenance,
                                ValidationResult(ValidationStatus.INVALID, ANALYSIS_TIME))
    return snapshot((invalid,))


def stale_bar_snapshot() -> AsOfSnapshot:
    item = bars("stale", [10])[0]
    stale = MarketObservation(item.id, item.instrument, item.kind, item.payload, item.provenance,
                              ValidationResult(ValidationStatus.STALE, ANALYSIS_TIME))
    return snapshot((stale,))
