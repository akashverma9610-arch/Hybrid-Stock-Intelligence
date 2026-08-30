"""Provider-neutral, non-secret reliability records.

These records describe a routing decision only.  They neither fetch a provider
nor invent a value when every declared source is unavailable.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from app.data_sources.models import DataFamily, SourceReadinessStatus
from app.historical.guard import manifest_fingerprint


class ReliabilityStatus(StrEnum):
    READY = "READY"
    DEGRADED = "DEGRADED"
    STALE = "STALE"
    PRIMARY_UNAVAILABLE = "PRIMARY_UNAVAILABLE"
    FALLBACK_USED = "FALLBACK_USED"
    LAST_KNOWN_GOOD = "LAST_KNOWN_GOOD"
    UNAVAILABLE = "UNAVAILABLE"
    CONFLICTED = "CONFLICTED"


@dataclass(frozen=True, slots=True)
class SourceHealth:
    source_id: str
    family: DataFamily
    tier: int
    readiness: SourceReadinessStatus
    observed_at: datetime | None
    data_available: bool
    freshness: ReliabilityStatus = ReliabilityStatus.READY
    warnings: tuple[str, ...] = ()
    value_fingerprint: str | None = None


@dataclass(frozen=True, slots=True)
class DataAvailability:
    family: DataFamily
    status: ReliabilityStatus
    source_id: str | None
    source_tier: int | None
    observed_at: datetime | None
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ReliabilityDecision:
    family: DataFamily
    availability: DataAvailability
    selected_source_id: str | None
    selected_tier: int | None
    fallback_used: bool
    last_known_good_used: bool
    conflict_detected: bool
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class StoredReliabilityDecision:
    """A precomputed routing conclusion with durable, non-secret lineage only."""

    decision_id: str
    canonical_instrument_id: str
    decision: ReliabilityDecision
    observed_at: datetime
    available_at: datetime
    fingerprint: str
    evaluation_as_of: datetime | None = None

    def __post_init__(self) -> None:
        if not all((self.decision_id, self.canonical_instrument_id, self.fingerprint)):
            raise ValueError("STORED_RELIABILITY_DECISION_REQUIRED_FIELD")
        timestamps = (self.observed_at, self.available_at, self.evaluation_as_of)
        if any(value is not None and (value.tzinfo is None or value.utcoffset() is None) for value in timestamps):
            raise ValueError("STORED_RELIABILITY_DECISION_TIMEZONE_REQUIRED")


def reliability_decision_fingerprint(value: StoredReliabilityDecision) -> str:
    """Fingerprint every semantic routing conclusion without provider payloads."""
    decision, availability = value.decision, value.decision.availability
    return manifest_fingerprint(
        decision_id=value.decision_id,
        canonical_instrument_id=value.canonical_instrument_id,
        evaluation_as_of=None if value.evaluation_as_of is None else value.evaluation_as_of.isoformat(),
        observed_at=value.observed_at.isoformat(), available_at=value.available_at.isoformat(),
        family=decision.family.value,
        availability=(availability.family.value, availability.status.value, availability.source_id,
                      availability.source_tier, None if availability.observed_at is None else availability.observed_at.isoformat(),
                      availability.warnings),
        selected_source_id=decision.selected_source_id, selected_tier=decision.selected_tier,
        fallback_used=decision.fallback_used, last_known_good_used=decision.last_known_good_used,
        conflict_detected=decision.conflict_detected, warnings=decision.warnings,
    )
