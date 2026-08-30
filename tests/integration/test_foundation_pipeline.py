from datetime import timedelta

from app.config.freshness import FreshnessPolicyConfig
from app.domain.models import ObservationKind, ValidationStatus
from app.services.foundation_service import FoundationService
from app.storage.sqlite_repository import SQLiteMarketDataRepository
from app.validation.freshness import FreshnessEngine
from app.validation.observation_validator import ObservationValidator
from tests.fixtures.mock_observations import EVALUATION_TIME, multiple_timestamp_observations, valid_observation


def test_mock_input_validation_storage_snapshot_and_retrieval(tmp_path) -> None:
    repository = SQLiteMarketDataRepository(tmp_path / "integration.db")
    policy = FreshnessPolicyConfig({ObservationKind.PRICE_BAR: timedelta(days=1)}, timedelta(days=7))
    service = FoundationService(repository, ObservationValidator(FreshnessEngine(policy)))
    early, late = multiple_timestamp_observations()

    assert service.ingest(early, evaluated_timestamp=EVALUATION_TIME).status is ValidationStatus.VALID
    assert service.ingest(late, evaluated_timestamp=EVALUATION_TIME).status is ValidationStatus.VALID
    snapshot = service.build_as_of_snapshot(as_of_timestamp=EVALUATION_TIME - timedelta(hours=1))
    replayed_snapshot = service.build_as_of_snapshot(as_of_timestamp=EVALUATION_TIME - timedelta(hours=1))
    restored = repository.get_snapshot(snapshot.id)

    assert [item.id for item in snapshot.observations] == ["mock-reliance-0800"]
    assert replayed_snapshot.id == snapshot.id
    assert restored is not None
    assert [item.id for item in restored.observations] == ["mock-reliance-0800"]
    assert repository.audit_event_count() == 4
    repository.close()
