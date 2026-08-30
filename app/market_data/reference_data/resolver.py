"""Pure PIT resolution and exact tick-grid validation for stored evidence."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, ROUND_FLOOR
from enum import StrEnum

from .repository import TickSizeObservationRepository
from .tick_size import NseTickSizeObservation, TickSizeSourceClass


class TickSizeResolutionStatus(StrEnum):
    AVAILABLE = "AVAILABLE"
    TICK_SIZE_UNAVAILABLE_FOR_AS_OF = "TICK_SIZE_UNAVAILABLE_FOR_AS_OF"
    REFERENCE_DATA_CONFLICT = "REFERENCE_DATA_CONFLICT"
    INVALID_TICK_REFERENCE_DATA = "INVALID_TICK_REFERENCE_DATA"


@dataclass(frozen=True, slots=True)
class TickSizeResolution:
    status: TickSizeResolutionStatus
    canonical_instrument_id: str
    as_of: datetime
    tick_size: Decimal | None
    selected_source_class: TickSizeSourceClass | None
    selected_source_name: str | None
    selected_record_id: str | None
    eligible_official_record_ids: tuple[str, ...]
    eligible_licensed_record_ids: tuple[str, ...]
    corroborating_record_ids: tuple[str, ...]
    conflicting_record_ids: tuple[str, ...]
    warnings: tuple[str, ...] = ()


class TickSizeReferenceResolver:
    """Resolve immutable reference evidence; no source acquisition or inference."""

    def __init__(
        self,
        repository: TickSizeObservationRepository,
        *,
        approved_licensed_sources: frozenset[str] = frozenset(),
    ) -> None:
        self._repository = repository
        self._approved_licensed_sources = frozenset(approved_licensed_sources)

    def resolve_tick_size(
        self, canonical_instrument_id: str, *, as_of: datetime,
    ) -> TickSizeResolution:
        if not isinstance(canonical_instrument_id, str) or not canonical_instrument_id.strip():
            raise ValueError("TICK_REFERENCE_CANONICAL_INSTRUMENT_REQUIRED")
        _require_aware(as_of, "TICK_REFERENCE_AS_OF_NAIVE")
        observations = self._repository.list_tick_size_observations(
            canonical_instrument_id=canonical_instrument_id,
        )
        eligible = tuple(item for item in observations if item.is_eligible_as_of(as_of))
        official = tuple(
            item for item in eligible if item.source_class is TickSizeSourceClass.OFFICIAL_EXCHANGE
        )
        licensed_all = tuple(
            item for item in eligible if item.source_class is TickSizeSourceClass.LICENSED_REFERENCE_DATA
        )
        licensed = tuple(
            item for item in licensed_all if item.source_name in self._approved_licensed_sources
        )
        warnings = ("UNAPPROVED_LICENSED_SOURCE_IGNORED",) if len(licensed) != len(licensed_all) else ()
        official_ids = _record_ids(official)
        licensed_ids = _record_ids(licensed)

        if not official and not licensed:
            return TickSizeResolution(
                TickSizeResolutionStatus.TICK_SIZE_UNAVAILABLE_FOR_AS_OF,
                canonical_instrument_id, as_of, None, None, None, None,
                official_ids, licensed_ids, (), (), warnings,
            )

        authoritative = official if official else licensed
        if len({item.tick_size for item in authoritative}) != 1:
            return _conflict(canonical_instrument_id, as_of, official, licensed, warnings)
        if official and licensed and {item.tick_size for item in official} != {item.tick_size for item in licensed}:
            return _conflict(canonical_instrument_id, as_of, official, licensed, warnings)

        selected = _select_lineage(official if official else licensed)
        corroborating = tuple(
            record_id for record_id in _record_ids(official + licensed) if record_id != selected.record_id
        )
        return TickSizeResolution(
            TickSizeResolutionStatus.AVAILABLE,
            canonical_instrument_id,
            as_of,
            selected.tick_size,
            selected.source_class,
            selected.source_name,
            selected.record_id,
            official_ids,
            licensed_ids,
            corroborating,
            (),
            warnings,
        )


def validate_price_on_tick_grid(price: Decimal, tick_size: Decimal) -> None:
    """Raise a deterministic error unless exact Decimal grid alignment holds."""
    if not isinstance(price, Decimal) or not isinstance(tick_size, Decimal):
        raise ValueError("TICK_GRID_DECIMAL_REQUIRED")
    if not price.is_finite() or not tick_size.is_finite() or tick_size <= Decimal("0"):
        raise ValueError("INVALID_TICK_REFERENCE_DATA")
    if price % tick_size != Decimal("0"):
        raise ValueError("TICK_GRID_ALIGNMENT_ERROR")


def floor_to_tick_grid(price_ceiling: Decimal, tick_size: Decimal) -> Decimal:
    """Return the greatest exact Decimal grid price no greater than a ceiling.

    This is deliberately a ceiling-only operation: it never uses nearest or
    upward rounding and does not imply an executable order or fill.
    """
    if not isinstance(price_ceiling, Decimal) or not isinstance(tick_size, Decimal):
        raise ValueError("TICK_GRID_DECIMAL_REQUIRED")
    if not price_ceiling.is_finite() or not tick_size.is_finite() or tick_size <= Decimal("0"):
        raise ValueError("INVALID_TICK_REFERENCE_DATA")
    result = (price_ceiling / tick_size).to_integral_value(rounding=ROUND_FLOOR) * tick_size
    validate_price_on_tick_grid(result, tick_size)
    return result


def _conflict(
    canonical_instrument_id: str,
    as_of: datetime,
    official: tuple[NseTickSizeObservation, ...],
    licensed: tuple[NseTickSizeObservation, ...],
    warnings: tuple[str, ...],
) -> TickSizeResolution:
    return TickSizeResolution(
        TickSizeResolutionStatus.REFERENCE_DATA_CONFLICT,
        canonical_instrument_id,
        as_of,
        None,
        None,
        None,
        None,
        _record_ids(official),
        _record_ids(licensed),
        (),
        _record_ids(official + licensed),
        warnings,
    )


def _select_lineage(values: tuple[NseTickSizeObservation, ...]) -> NseTickSizeObservation:
    return max(values, key=lambda item: (item.eligible_from, item.observed_at, item.record_id))


def _record_ids(values: tuple[NseTickSizeObservation, ...]) -> tuple[str, ...]:
    return tuple(sorted(item.record_id for item in values))


def _require_aware(value: datetime, error: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(error)
