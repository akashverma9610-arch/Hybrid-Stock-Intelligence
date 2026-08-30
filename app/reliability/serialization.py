"""Canonical fail-closed serialization of durable reliability decisions."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping

from app.data_sources.models import DataFamily
from app.reliability.models import (
    DataAvailability, ReliabilityDecision, ReliabilityStatus,
    StoredReliabilityDecision, reliability_decision_fingerprint,
)


class ReliabilityDecisionSerializationError(ValueError):
    pass


def reliability_decision_to(value: StoredReliabilityDecision) -> dict[str, object]:
    _require_durable(value)
    return {
        "decision_id": value.decision_id,
        "canonical_instrument_id": value.canonical_instrument_id,
        "evaluation_as_of": value.evaluation_as_of.isoformat(),
        "observed_at": value.observed_at.isoformat(),
        "available_at": value.available_at.isoformat(),
        "fingerprint": value.fingerprint,
        "decision": {
            "family": value.decision.family.value,
            "availability": {
                "family": value.decision.availability.family.value,
                "status": value.decision.availability.status.value,
                "source_id": value.decision.availability.source_id,
                "source_tier": value.decision.availability.source_tier,
                "observed_at": _timestamp(value.decision.availability.observed_at),
                "warnings": list(value.decision.availability.warnings),
            },
            "selected_source_id": value.decision.selected_source_id,
            "selected_tier": value.decision.selected_tier,
            "fallback_used": value.decision.fallback_used,
            "last_known_good_used": value.decision.last_known_good_used,
            "conflict_detected": value.decision.conflict_detected,
            "warnings": list(value.decision.warnings),
        },
    }


def reliability_decision_from(payload: Mapping[str, Any]) -> StoredReliabilityDecision:
    expected = {"decision_id", "canonical_instrument_id", "evaluation_as_of", "observed_at", "available_at", "fingerprint", "decision"}
    if not isinstance(payload, Mapping) or set(payload) != expected or not isinstance(payload["decision"], Mapping):
        raise ReliabilityDecisionSerializationError("RELIABILITY_DECISION_SERIALIZATION_INVALID")
    try:
        decision_payload = payload["decision"]
        availability_payload = decision_payload["availability"]
        if not isinstance(availability_payload, Mapping):
            raise TypeError("availability")
        availability = DataAvailability(
            DataFamily(availability_payload["family"]), ReliabilityStatus(availability_payload["status"]),
            _optional_string(availability_payload["source_id"]), _optional_int(availability_payload["source_tier"]),
            _parse_timestamp(availability_payload["observed_at"]), _string_tuple(availability_payload["warnings"]),
        )
        decision = ReliabilityDecision(
            DataFamily(decision_payload["family"]), availability,
            _optional_string(decision_payload["selected_source_id"]), _optional_int(decision_payload["selected_tier"]),
            _boolean(decision_payload["fallback_used"]), _boolean(decision_payload["last_known_good_used"]),
            _boolean(decision_payload["conflict_detected"]), _string_tuple(decision_payload["warnings"]),
        )
        observed_at, available_at, evaluation_as_of = (
            _required_timestamp(payload["observed_at"]), _required_timestamp(payload["available_at"]),
            _required_timestamp(payload["evaluation_as_of"]),
        )
        value = StoredReliabilityDecision(
            str(payload["decision_id"]), str(payload["canonical_instrument_id"]), decision,
            observed_at, available_at, str(payload["fingerprint"]), evaluation_as_of,
        )
    except (KeyError, TypeError, ValueError) as error:
        raise ReliabilityDecisionSerializationError("RELIABILITY_DECISION_SERIALIZATION_INVALID") from error
    if value.fingerprint != reliability_decision_fingerprint(value):
        raise ReliabilityDecisionSerializationError("RELIABILITY_DECISION_FINGERPRINT_MISMATCH")
    return value


def _require_durable(value: StoredReliabilityDecision) -> None:
    if not isinstance(value, StoredReliabilityDecision) or value.evaluation_as_of is None:
        raise ReliabilityDecisionSerializationError("RELIABILITY_DECISION_EVALUATION_AS_OF_REQUIRED")
    if value.fingerprint != reliability_decision_fingerprint(value):
        raise ReliabilityDecisionSerializationError("RELIABILITY_DECISION_FINGERPRINT_MISMATCH")


def _timestamp(value: datetime | None) -> str | None:
    if value is not None and (value.tzinfo is None or value.utcoffset() is None):
        raise ReliabilityDecisionSerializationError("RELIABILITY_DECISION_SERIALIZATION_INVALID")
    return None if value is None else value.isoformat()


def _parse_timestamp(value: object) -> datetime | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise TypeError("timestamp")
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("naive timestamp")
    return parsed


def _required_timestamp(value: object) -> datetime:
    parsed = _parse_timestamp(value)
    if parsed is None:
        raise ValueError("required timestamp")
    return parsed


def _optional_string(value: object) -> str | None:
    if value is not None and not isinstance(value, str):
        raise TypeError("string")
    return value


def _optional_int(value: object) -> int | None:
    if value is not None and (not isinstance(value, int) or isinstance(value, bool)):
        raise TypeError("int")
    return value


def _boolean(value: object) -> bool:
    if not isinstance(value, bool):
        raise TypeError("bool")
    return value


def _string_tuple(value: object) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise TypeError("string tuple")
    return tuple(value)
