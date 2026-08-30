from datetime import timedelta

from app.config.freshness import FreshnessPolicyConfig
from app.domain.models import ObservationKind, ValidationStatus
from app.validation.freshness import FreshnessEngine
from app.validation.observation_validator import ObservationValidator
from tests.fixtures.mock_observations import (
    EVALUATION_TIME, duplicate_observation, future_timestamp_observation, incomplete_observation,
    invalid_price_observation, invalid_timestamp_observation, invalid_volume_observation, stale_observation,
    valid_observation,
)


def validator() -> ObservationValidator:
    policy = FreshnessPolicyConfig({ObservationKind.PRICE_BAR: timedelta(hours=24)}, timedelta(days=7))
    return ObservationValidator(FreshnessEngine(policy))


def test_valid_mock_observation_is_eligible() -> None:
    result = validator().validate(valid_observation(), evaluated_timestamp=EVALUATION_TIME)
    assert result.status is ValidationStatus.VALID
    assert result.eligible_for_analysis is True


def test_stale_observation_fails_closed() -> None:
    result = validator().validate(stale_observation(), evaluated_timestamp=EVALUATION_TIME)
    assert result.status is ValidationStatus.STALE
    assert result.eligible_for_analysis is False


def test_incomplete_observation_fails_closed() -> None:
    result = validator().validate(incomplete_observation(), evaluated_timestamp=EVALUATION_TIME)
    assert result.status is ValidationStatus.INCOMPLETE
    assert result.eligible_for_analysis is False


def test_negative_price_is_invalid() -> None:
    result = validator().validate(invalid_price_observation(), evaluated_timestamp=EVALUATION_TIME)
    assert result.status is ValidationStatus.INVALID


def test_future_timestamp_is_rejected() -> None:
    result = validator().validate(future_timestamp_observation(), evaluated_timestamp=EVALUATION_TIME)
    assert result.status is ValidationStatus.FUTURE_TIMESTAMP


def test_invalid_timestamp_is_rejected() -> None:
    result = validator().validate(invalid_timestamp_observation(), evaluated_timestamp=EVALUATION_TIME)
    assert result.status is ValidationStatus.INVALID


def test_invalid_volume_is_rejected() -> None:
    result = validator().validate(invalid_volume_observation(), evaluated_timestamp=EVALUATION_TIME)
    assert result.status is ValidationStatus.INVALID


def test_duplicate_observation_is_rejected() -> None:
    item = duplicate_observation()
    result = validator().validate(item, evaluated_timestamp=EVALUATION_TIME, existing_observation_ids={item.id})
    assert result.status is ValidationStatus.DUPLICATE
