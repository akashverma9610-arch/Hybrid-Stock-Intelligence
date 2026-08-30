from datetime import UTC, datetime, timedelta

from app.domain.models import DataQuality, Instrument, MarketObservation, ObservationKind, Provenance


EVALUATION_TIME = datetime(2026, 8, 21, 10, 0, tzinfo=UTC)
INSTRUMENT = Instrument("mock-reliance", "RELIANCE", "NSE", "INE002A01018")


def valid_observation(observation_id: str = "mock-reliance-0900", age: timedelta = timedelta(hours=1)) -> MarketObservation:
    market_time = EVALUATION_TIME - age
    return MarketObservation(
        id=observation_id, instrument=INSTRUMENT, kind=ObservationKind.PRICE_BAR,
        payload={"open": 1420.0, "high": 1442.0, "low": 1418.0, "close": 1437.0, "volume": 1_200_000},
        provenance=Provenance("mock-fixture", "valid-001", market_time, market_time + timedelta(minutes=1), DataQuality.HIGH),
    )


def stale_observation() -> MarketObservation:
    return valid_observation("mock-reliance-stale", age=timedelta(days=2))


def incomplete_observation() -> MarketObservation:
    item = valid_observation("mock-reliance-incomplete")
    return MarketObservation(item.id, item.instrument, item.kind, {"open": 1420.0, "high": 1442.0, "low": 1418.0}, item.provenance)


def invalid_price_observation() -> MarketObservation:
    item = valid_observation("mock-reliance-negative-price")
    return MarketObservation(item.id, item.instrument, item.kind, {**item.payload, "close": -1.0}, item.provenance)


def future_timestamp_observation() -> MarketObservation:
    item = valid_observation("mock-reliance-future")
    future = EVALUATION_TIME + timedelta(minutes=1)
    return MarketObservation(item.id, item.instrument, item.kind, item.payload, Provenance("mock-fixture", "future-001", future, future, DataQuality.HIGH))


def duplicate_observation() -> MarketObservation:
    """Duplicate fixture: ingest after `valid_observation()` with the same ID."""
    return valid_observation()


def invalid_timestamp_observation() -> MarketObservation:
    item = valid_observation("mock-reliance-invalid-timestamp")
    return MarketObservation(item.id, item.instrument, item.kind, item.payload, Provenance("mock-fixture", "invalid-time-001", "not-a-timestamp", EVALUATION_TIME, DataQuality.HIGH))


def invalid_volume_observation() -> MarketObservation:
    item = valid_observation("mock-reliance-invalid-volume")
    return MarketObservation(item.id, item.instrument, item.kind, {**item.payload, "volume": -1}, item.provenance)


def multiple_timestamp_observations() -> tuple[MarketObservation, MarketObservation]:
    early = valid_observation("mock-reliance-0800", age=timedelta(hours=2))
    late = valid_observation("mock-reliance-0930", age=timedelta(minutes=30))
    return early, late
