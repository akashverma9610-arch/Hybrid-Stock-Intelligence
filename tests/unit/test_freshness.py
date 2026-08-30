from datetime import UTC, datetime, timedelta

from app.config.freshness import FreshnessPolicyConfig
from app.domain.models import FreshnessStatus, ObservationKind
from app.validation.freshness import FreshnessEngine


def test_freshness_uses_configured_threshold_and_reports_age() -> None:
    evaluated = datetime(2026, 8, 21, 10, 0, tzinfo=UTC)
    engine = FreshnessEngine(FreshnessPolicyConfig({ObservationKind.PRICE_BAR: timedelta(minutes=30)}, timedelta(days=1)))
    result = engine.evaluate(kind=ObservationKind.PRICE_BAR, observed_timestamp=evaluated - timedelta(minutes=31), evaluated_timestamp=evaluated)

    assert result.status is FreshnessStatus.STALE
    assert result.age_seconds == 1860.0
    assert result.maximum_age_seconds == 1800.0
