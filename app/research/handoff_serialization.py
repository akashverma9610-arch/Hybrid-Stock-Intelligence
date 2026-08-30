"""Canonical, fail-closed serialization for immutable Brain research handoffs."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any

from app.research.handoff import (
    BrainResearchHandoff,
    BrainResearchHandoffError,
    BrainResearchHandoffStatus,
    BrainResearchOriginType,
    BrainResearchStage,
)


_FIELDS = frozenset(BrainResearchHandoff.__dataclass_fields__)


def handoff_to(value: BrainResearchHandoff) -> dict[str, object]:
    """Return the exact JSON-safe representation of one immutable handoff."""
    if not isinstance(value, BrainResearchHandoff):
        raise ValueError("BRAIN_RESEARCH_HANDOFF_SERIALIZATION_INVALID")
    return {name: _to_json(getattr(value, name)) for name in value.__dataclass_fields__}


def handoff_from(value: object) -> BrainResearchHandoff:
    """Rebuild an immutable handoff and independently verify its fingerprint."""
    try:
        if not isinstance(value, dict) or set(value) != _FIELDS:
            raise TypeError("unexpected handoff payload")
        stored_fingerprint = _required_string(value["fingerprint"])
        result = BrainResearchHandoff(
            handoff_id=_required_string(value["handoff_id"]),
            canonical_instrument_id=_required_string(value["canonical_instrument_id"]),
            origin_type=BrainResearchOriginType(_required_string(value["origin_type"])),
            origin_artifact_id=_required_string(value["origin_artifact_id"]),
            origin_artifact_fingerprint=_required_string(value["origin_artifact_fingerprint"]),
            evaluation_as_of=_timestamp(value["evaluation_as_of"]),
            evaluation_session=_optional_timestamp(value["evaluation_session"]),
            requested_brain_stage=BrainResearchStage(_required_string(value["requested_brain_stage"])),
            research_status=BrainResearchHandoffStatus(_required_string(value["research_status"])),
            created_from_governed_artifact=_boolean(value["created_from_governed_artifact"]),
            origin_lineage=_pairs(value["origin_lineage"]),
            sector=_optional_string(value["sector"]),
            setup_family=_optional_string(value["setup_family"]),
            horizon=_optional_string(value["horizon"]),
            reference_facts=_pairs(value["reference_facts"]),
            warnings=_strings(value["warnings"]),
            fingerprint=stored_fingerprint,
        )
    except BrainResearchHandoffError as error:
        if "FINGERPRINT_MISMATCH" in str(error):
            raise ValueError("BRAIN_RESEARCH_HANDOFF_FINGERPRINT_MISMATCH") from error
        raise ValueError("BRAIN_RESEARCH_HANDOFF_SERIALIZATION_INVALID") from error
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError("BRAIN_RESEARCH_HANDOFF_SERIALIZATION_INVALID") from error
    if result.fingerprint != stored_fingerprint:
        raise ValueError("BRAIN_RESEARCH_HANDOFF_FINGERPRINT_MISMATCH")
    return result


def _to_json(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, tuple):
        return [_to_json(item) for item in value]
    return value


def _required_string(value: object) -> str:
    if not isinstance(value, str) or not value:
        raise TypeError("non-empty string required")
    return value


def _optional_string(value: object) -> str | None:
    if value is None:
        return None
    return _required_string(value)


def _timestamp(value: object) -> datetime:
    if not isinstance(value, str):
        raise TypeError("timestamp string required")
    result = datetime.fromisoformat(value)
    if result.tzinfo is None or result.utcoffset() is None:
        raise ValueError("timezone-aware timestamp required")
    return result


def _optional_timestamp(value: object) -> datetime | None:
    return None if value is None else _timestamp(value)


def _boolean(value: object) -> bool:
    if type(value) is not bool:
        raise TypeError("boolean required")
    return value


def _strings(value: object) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise TypeError("string list required")
    return tuple(value)


def _pairs(value: object) -> tuple[tuple[str, str], ...]:
    if not isinstance(value, list):
        raise TypeError("pair list required")
    result: list[tuple[str, str]] = []
    for item in value:
        if not isinstance(item, list) or len(item) != 2 or not all(isinstance(part, str) for part in item):
            raise TypeError("string pair required")
        result.append((item[0], item[1]))
    return tuple(result)
