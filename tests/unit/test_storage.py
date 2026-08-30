from datetime import timedelta

from app.config.freshness import FreshnessPolicyConfig
from app.domain.models import ObservationKind
from app.services.foundation_service import FoundationService
from app.storage.sqlite_repository import SQLiteMarketDataRepository
from app.validation.freshness import FreshnessEngine
from app.validation.observation_validator import ObservationValidator
from tests.fixtures.mock_observations import EVALUATION_TIME, valid_observation


def test_sqlite_preserves_observation_and_provenance(tmp_path) -> None:
    repository = SQLiteMarketDataRepository(tmp_path / "foundation.db")
    service = FoundationService(repository, ObservationValidator(FreshnessEngine(FreshnessPolicyConfig({ObservationKind.PRICE_BAR: timedelta(days=1)}, timedelta(days=7)))))
    service.ingest(valid_observation(), evaluated_timestamp=EVALUATION_TIME)
    snapshot = service.build_as_of_snapshot(as_of_timestamp=EVALUATION_TIME)
    restored = repository.get_snapshot(snapshot.id)

    assert restored is not None
    assert restored.observations[0].provenance.source == "mock-fixture"
    assert restored.observations[0].provenance.source_identifier == "valid-001"
    assert restored.observations[0].payload["close"] == 1437.0
    repository.close()
