from app.domain.models import PriceBar, ValidationResult, ValidationStatus
from tests.fixtures.mock_observations import EVALUATION_TIME, valid_observation


def test_market_observation_carries_provenance_and_validation_status() -> None:
    observation = valid_observation()
    validated = observation.with_validation(ValidationResult(ValidationStatus.VALID, EVALUATION_TIME))

    assert validated.instrument.symbol == "RELIANCE"
    assert validated.provenance.source == "mock-fixture"
    assert validated.validation is not None
    assert validated.validation.eligible_for_analysis is True


def test_price_bar_is_a_typed_market_observation_model() -> None:
    observation = valid_observation()
    price_bar = PriceBar(**observation.__dict__) if hasattr(observation, "__dict__") else PriceBar(
        observation.id, observation.instrument, observation.kind, observation.payload, observation.provenance
    )
    assert price_bar.kind.value == "price_bar"
