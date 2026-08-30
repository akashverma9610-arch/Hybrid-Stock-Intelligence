from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Collection

from app.domain.models import (
    DataQuality,
    MarketObservation,
    ObservationKind,
    ValidationIssue,
    ValidationResult,
    ValidationStatus,
)
from app.validation.freshness import FreshnessEngine


class ObservationValidator:
    """Deterministic validation. It records problems; it never repairs input."""

    def __init__(self, freshness_engine: FreshnessEngine) -> None:
        self._freshness_engine = freshness_engine

    def validate(
        self,
        observation: MarketObservation,
        *,
        evaluated_timestamp: datetime,
        existing_observation_ids: Collection[str] = (),
    ) -> ValidationResult:
        issues: list[ValidationIssue] = []
        self._validate_required_fields(observation, issues)
        self._validate_timestamps(observation, evaluated_timestamp, issues)
        self._validate_payload(observation, issues)

        freshness = None
        if isinstance(observation.kind, ObservationKind):
            freshness = self._freshness_engine.evaluate(
                kind=observation.kind,
                observed_timestamp=observation.provenance.market_timestamp,
                evaluated_timestamp=evaluated_timestamp,
            )

        status = self._select_status(observation, issues, freshness, existing_observation_ids)
        return ValidationResult(status, evaluated_timestamp, tuple(issues), freshness)

    @staticmethod
    def _validate_required_fields(observation: MarketObservation, issues: list[ValidationIssue]) -> None:
        if not _non_empty(observation.id):
            issues.append(ValidationIssue("id", "A non-empty observation ID is required."))
        if not _non_empty(observation.instrument.id):
            issues.append(ValidationIssue("instrument.id", "An instrument ID is required."))
        if not _non_empty(observation.instrument.symbol):
            issues.append(ValidationIssue("instrument.symbol", "A symbol is required."))
        if not _non_empty(observation.instrument.exchange):
            issues.append(ValidationIssue("instrument.exchange", "An exchange is required."))
        if not isinstance(observation.kind, ObservationKind):
            issues.append(ValidationIssue("kind", "Observation kind is malformed."))
        if not isinstance(observation.payload, dict):
            issues.append(ValidationIssue("payload", "Payload must be a mapping."))
        if not _non_empty(observation.provenance.source):
            issues.append(ValidationIssue("provenance.source", "A source is required."))
        if not isinstance(observation.provenance.data_quality, DataQuality):
            issues.append(ValidationIssue("provenance.data_quality", "Data quality is malformed."))

    @staticmethod
    def _validate_timestamps(
        observation: MarketObservation, evaluated_timestamp: datetime, issues: list[ValidationIssue]
    ) -> None:
        market_timestamp = observation.provenance.market_timestamp
        retrieved_timestamp = observation.provenance.retrieved_timestamp
        if not _is_aware_datetime(market_timestamp):
            issues.append(ValidationIssue("provenance.market_timestamp", "Market timestamp must be timezone-aware."))
        if not _is_aware_datetime(retrieved_timestamp):
            issues.append(ValidationIssue("provenance.retrieved_timestamp", "Retrieval timestamp must be timezone-aware."))
        if _is_aware_datetime(market_timestamp) and _is_aware_datetime(retrieved_timestamp):
            if retrieved_timestamp < market_timestamp:
                issues.append(ValidationIssue("provenance.retrieved_timestamp", "Retrieval cannot precede market time."))
            if market_timestamp > evaluated_timestamp or retrieved_timestamp > evaluated_timestamp:
                issues.append(ValidationIssue("provenance", "Observation contains a future timestamp."))

    @staticmethod
    def _validate_payload(observation: MarketObservation, issues: list[ValidationIssue]) -> None:
        if not isinstance(observation.payload, dict) or not isinstance(observation.kind, ObservationKind):
            return
        required_fields = {
            ObservationKind.PRICE_BAR: ("open", "high", "low", "close"),
            ObservationKind.VOLUME: ("volume",),
        }.get(observation.kind, ())
        for field in required_fields:
            if field not in observation.payload or observation.payload[field] is None:
                issues.append(ValidationIssue(f"payload.{field}", "Required value is missing."))

        for field in ("open", "high", "low", "close"):
            if field in observation.payload and observation.payload[field] is not None:
                value = observation.payload[field]
                if not _is_number(value):
                    issues.append(ValidationIssue(f"payload.{field}", "Price must be numeric."))
                elif value < 0:
                    issues.append(ValidationIssue(f"payload.{field}", "Negative prices are invalid."))
        if "volume" in observation.payload and observation.payload["volume"] is not None:
            volume = observation.payload["volume"]
            if not _is_number(volume) or volume < 0:
                issues.append(ValidationIssue("payload.volume", "Volume must be a non-negative number."))

    @staticmethod
    def _select_status(
        observation: MarketObservation,
        issues: list[ValidationIssue],
        freshness: object,
        existing_observation_ids: Collection[str],
    ) -> ValidationStatus:
        invalid_fields = {issue.field for issue in issues}
        if any(
            field in invalid_fields
            for field in {"id", "instrument.id", "instrument.symbol", "instrument.exchange", "payload", "kind", "provenance.source", "provenance.data_quality"}
        ):
            return ValidationStatus.INVALID
        if any("Negative prices" in issue.message or "must be numeric" in issue.message or "Volume must" in issue.message for issue in issues):
            return ValidationStatus.INVALID
        if any("timezone-aware" in issue.message or "Retrieval cannot" in issue.message for issue in issues):
            return ValidationStatus.INVALID
        if any("future timestamp" in issue.message for issue in issues):
            return ValidationStatus.FUTURE_TIMESTAMP
        if observation.id in existing_observation_ids:
            return ValidationStatus.DUPLICATE
        if any("Required value is missing" in issue.message for issue in issues):
            return ValidationStatus.INCOMPLETE
        if getattr(freshness, "status", None).value == "stale":
            return ValidationStatus.STALE
        if observation.provenance.data_quality in {DataQuality.LOW, DataQuality.UNKNOWN}:
            return ValidationStatus.QUALITY_WARNING
        return ValidationStatus.VALID


def _is_aware_datetime(value: object) -> bool:
    return isinstance(value, datetime) and value.tzinfo is not None and value.utcoffset() is not None


def _non_empty(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _is_number(value: object) -> bool:
    return isinstance(value, (int, float, Decimal)) and not isinstance(value, bool)
