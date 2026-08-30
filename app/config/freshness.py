from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Mapping

from app.domain.models import ObservationKind


@dataclass(frozen=True, slots=True)
class FreshnessPolicyConfig:
    """Configurable thresholds, not assertions about real provider SLAs."""

    maximum_age_by_kind: Mapping[ObservationKind, timedelta]
    default_maximum_age: timedelta

    def maximum_age_for(self, kind: ObservationKind) -> timedelta:
        return self.maximum_age_by_kind.get(kind, self.default_maximum_age)
