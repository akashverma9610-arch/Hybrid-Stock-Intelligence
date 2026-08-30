"""Canonical, fail-closed serialization for immutable governed setup evidence."""
from __future__ import annotations

from dataclasses import fields, is_dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any, Mapping

from app.strategies.pre_breakout.materialization import (
    GovernedPreBreakoutBaseWindow, GovernedPreBreakoutPivot,
    GovernedPreBreakoutResolvedInputs, GovernedPreBreakoutStructuralResult,
    PreBreakoutResolvedInputStatus, PreBreakoutStructuralStatus,
)
from app.strategies.pre_breakout.setup_assessment import (
    GovernedPreBreakoutSetupAssessment, PreBreakoutSetupAssessmentStatus,
    PreBreakoutSetupBlocker, PreBreakoutSetupBlockerCategory,
)


class PreBreakoutSetupAssessmentSerializationError(ValueError):
    pass


_TYPES = {
    value.__name__: value for value in (
        GovernedPreBreakoutSetupAssessment, PreBreakoutSetupBlocker,
        GovernedPreBreakoutResolvedInputs, GovernedPreBreakoutStructuralResult,
        GovernedPreBreakoutPivot, GovernedPreBreakoutBaseWindow,
    )
}
_ENUMS = {
    value.__name__: value for value in (
        PreBreakoutSetupAssessmentStatus, PreBreakoutSetupBlockerCategory,
        PreBreakoutResolvedInputStatus, PreBreakoutStructuralStatus,
    )
}


def assessment_to(value: GovernedPreBreakoutSetupAssessment) -> dict[str, object]:
    if not isinstance(value, GovernedPreBreakoutSetupAssessment):
        raise PreBreakoutSetupAssessmentSerializationError("PRE_BREAKOUT_SETUP_ASSESSMENT_SERIALIZATION_INVALID")
    return {"assessment_id": value.assessment_id, "fingerprint": value.fingerprint, "assessment": _encode(value)}


def assessment_from(payload: Mapping[str, Any]) -> GovernedPreBreakoutSetupAssessment:
    if not isinstance(payload, Mapping) or set(payload) != {"assessment_id", "fingerprint", "assessment"}:
        raise PreBreakoutSetupAssessmentSerializationError("PRE_BREAKOUT_SETUP_ASSESSMENT_SERIALIZATION_INVALID")
    try:
        value = _decode(payload["assessment"])
    except (TypeError, ValueError, KeyError) as error:
        if isinstance(error, PreBreakoutSetupAssessmentSerializationError):
            raise
        raise PreBreakoutSetupAssessmentSerializationError("PRE_BREAKOUT_SETUP_ASSESSMENT_SERIALIZATION_INVALID") from error
    if not isinstance(value, GovernedPreBreakoutSetupAssessment):
        raise PreBreakoutSetupAssessmentSerializationError("PRE_BREAKOUT_SETUP_ASSESSMENT_SERIALIZATION_INVALID")
    if payload["assessment_id"] != value.assessment_id or payload["fingerprint"] != value.fingerprint:
        raise PreBreakoutSetupAssessmentSerializationError("PRE_BREAKOUT_SETUP_ASSESSMENT_FINGERPRINT_MISMATCH")
    return value


def _encode(value: Any) -> Any:
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            raise PreBreakoutSetupAssessmentSerializationError("PRE_BREAKOUT_SETUP_ASSESSMENT_SERIALIZATION_INVALID")
        return {"__datetime__": value.isoformat()}
    if isinstance(value, Decimal):
        return {"__decimal__": str(value)}
    if isinstance(value, StrEnum):
        return {"__enum__": type(value).__name__, "value": value.value}
    if is_dataclass(value):
        return {"__type__": type(value).__name__, "fields": {field.name: _encode(getattr(value, field.name)) for field in fields(value)}}
    if isinstance(value, tuple):
        return {"__tuple__": [_encode(item) for item in value]}
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise PreBreakoutSetupAssessmentSerializationError("PRE_BREAKOUT_SETUP_ASSESSMENT_SERIALIZATION_INVALID")


def _decode(value: Any) -> Any:
    if not isinstance(value, Mapping):
        return value
    if set(value) == {"__datetime__"}:
        parsed = datetime.fromisoformat(str(value["__datetime__"]))
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise PreBreakoutSetupAssessmentSerializationError("PRE_BREAKOUT_SETUP_ASSESSMENT_SERIALIZATION_INVALID")
        return parsed
    if set(value) == {"__decimal__"}:
        return Decimal(str(value["__decimal__"]))
    if set(value) == {"__tuple__"} and isinstance(value["__tuple__"], list):
        return tuple(_decode(item) for item in value["__tuple__"])
    if set(value) == {"__enum__", "value"}:
        enum = _ENUMS.get(str(value["__enum__"]))
        if enum is None:
            raise PreBreakoutSetupAssessmentSerializationError("PRE_BREAKOUT_SETUP_ASSESSMENT_SERIALIZATION_INVALID")
        return enum(value["value"])
    if set(value) == {"__type__", "fields"} and isinstance(value["fields"], Mapping):
        kind = _TYPES.get(str(value["__type__"]))
        if kind is None:
            raise PreBreakoutSetupAssessmentSerializationError("PRE_BREAKOUT_SETUP_ASSESSMENT_SERIALIZATION_INVALID")
        values = {name: _decode(item) for name, item in value["fields"].items()}
        expected = {field.name for field in fields(kind)}
        if set(values) != expected:
            raise PreBreakoutSetupAssessmentSerializationError("PRE_BREAKOUT_SETUP_ASSESSMENT_SERIALIZATION_INVALID")
        return kind(**values)
    raise PreBreakoutSetupAssessmentSerializationError("PRE_BREAKOUT_SETUP_ASSESSMENT_SERIALIZATION_INVALID")
