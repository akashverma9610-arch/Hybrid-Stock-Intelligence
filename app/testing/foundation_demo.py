from datetime import UTC, datetime, timedelta

from app.config.freshness import FreshnessPolicyConfig
from app.domain.models import DataQuality, Instrument, MarketObservation, ObservationKind, Provenance
from app.services.foundation_service import FoundationService
from app.storage.sqlite_repository import SQLiteMarketDataRepository
from app.validation.freshness import FreshnessEngine
from app.validation.observation_validator import ObservationValidator


def main() -> None:
    evaluation_time = datetime(2026, 8, 21, 10, 0, tzinfo=UTC)
    policy = FreshnessPolicyConfig({ObservationKind.PRICE_BAR: timedelta(hours=24)}, timedelta(days=7))
    repository = SQLiteMarketDataRepository()
    service = FoundationService(repository, ObservationValidator(FreshnessEngine(policy)))
    observation = MarketObservation(
        id="mock-reliance-bar-001",
        instrument=Instrument("mock-reliance", "RELIANCE", "NSE", "INE002A01018"),
        kind=ObservationKind.PRICE_BAR,
        payload={"open": 1420.0, "high": 1442.0, "low": 1418.0, "close": 1437.0},
        provenance=Provenance(
            source="mock-fixture", source_identifier="fixture-001",
            market_timestamp=evaluation_time - timedelta(hours=1),
            retrieved_timestamp=evaluation_time - timedelta(minutes=59), data_quality=DataQuality.HIGH,
        ),
    )
    validation = service.ingest(observation, evaluated_timestamp=evaluation_time)
    snapshot = service.build_as_of_snapshot(as_of_timestamp=evaluation_time)
    print(f"validation={validation.status.value}")
    print(f"snapshot={snapshot.id} observations={len(snapshot.observations)}")
    repository.close()


if __name__ == "__main__":
    main()
