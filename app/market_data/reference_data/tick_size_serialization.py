"""Canonical, tamper-closed serialization for NSE tick-reference evidence."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Mapping

from app.market_data.models import Exchange

from .tick_size import (
    NseTickSizeObservation,
    NseTickSizeSegment,
    TickSizeAvailabilitySemantics,
    TickSizeSourceClass,
)


def nse_tick_size_observation_to_dict(value: NseTickSizeObservation) -> dict[str, object]:
    return {
        "record_id": value.record_id,
        "canonical_instrument_id": value.canonical_instrument_id,
        "exchange": value.exchange.value,
        "segment": value.segment.value,
        "isin": value.isin,
        "tick_size": str(value.tick_size),
        "source_class": value.source_class.value,
        "source_name": value.source_name,
        "source_artifact_fingerprint": value.source_artifact_fingerprint,
        "observed_at": value.observed_at.isoformat(),
        "effective_from": value.effective_from.isoformat() if value.effective_from else None,
        "effective_to": value.effective_to.isoformat() if value.effective_to else None,
        "availability_semantics": value.availability_semantics.value,
        "warnings": list(value.warnings),
        "evidence_fingerprint": value.evidence_fingerprint,
    }


def nse_tick_size_observation_from_dict(value: Mapping[str, object]) -> NseTickSizeObservation:
    try:
        tick_size = value["tick_size"]
        if isinstance(tick_size, float):
            raise TypeError("binary float is not canonical")
        result = NseTickSizeObservation(
            record_id=_text(value["record_id"]),
            canonical_instrument_id=_text(value["canonical_instrument_id"]),
            exchange=Exchange(_text(value["exchange"])),
            segment=NseTickSizeSegment(_text(value["segment"])),
            isin=_optional_text(value.get("isin")),
            tick_size=Decimal(_text(tick_size)),
            source_class=TickSizeSourceClass(_text(value["source_class"])),
            source_name=_text(value["source_name"]),
            source_artifact_fingerprint=_text(value["source_artifact_fingerprint"]),
            observed_at=datetime.fromisoformat(_text(value["observed_at"])),
            effective_from=_optional_datetime(value.get("effective_from")),
            effective_to=_optional_datetime(value.get("effective_to")),
            availability_semantics=TickSizeAvailabilitySemantics(_text(value["availability_semantics"])),
            warnings=_warnings(value["warnings"]),
            evidence_fingerprint=_text(value["evidence_fingerprint"]),
        )
    except ValueError as error:
        if str(error) == "NSE_TICK_EVIDENCE_FINGERPRINT_MISMATCH":
            raise
        raise ValueError("NSE_TICK_SERIALIZATION_INVALID") from error
    except (KeyError, TypeError, InvalidOperation) as error:
        raise ValueError("NSE_TICK_SERIALIZATION_INVALID") from error
    return result


def _text(value: object) -> str:
    if not isinstance(value, str):
        raise TypeError("string required")
    return value


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    return _text(value)


def _optional_datetime(value: object) -> datetime | None:
    if value is None:
        return None
    return datetime.fromisoformat(_text(value))


def _warnings(value: object) -> tuple[str, ...]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise TypeError("warnings list required")
    return tuple(value)
