from __future__ import annotations

from datetime import datetime

from app.config.freshness import FreshnessPolicyConfig
from app.domain.models import Freshness, FreshnessStatus, ObservationKind


class FreshnessEngine:
    def __init__(self, policy: FreshnessPolicyConfig) -> None:
        self._policy = policy

    def evaluate(
        self,
        *,
        kind: ObservationKind,
        observed_timestamp: datetime | object,
        evaluated_timestamp: datetime,
    ) -> Freshness:
        maximum_age = self._policy.maximum_age_for(kind)
        if not _is_aware_datetime(observed_timestamp):
            return Freshness(FreshnessStatus.UNKNOWN, None, evaluated_timestamp, None, maximum_age.total_seconds())

        age_seconds = (evaluated_timestamp - observed_timestamp).total_seconds()
        if age_seconds < 0:
            status = FreshnessStatus.FUTURE
        elif age_seconds > maximum_age.total_seconds():
            status = FreshnessStatus.STALE
        else:
            status = FreshnessStatus.FRESH
        return Freshness(status, observed_timestamp, evaluated_timestamp, age_seconds, maximum_age.total_seconds())


def _is_aware_datetime(value: object) -> bool:
    return isinstance(value, datetime) and value.tzinfo is not None and value.utcoffset() is not None
