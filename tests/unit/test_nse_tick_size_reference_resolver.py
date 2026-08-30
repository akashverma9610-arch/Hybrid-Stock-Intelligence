from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.market_data.models import Exchange
from app.market_data.reference_data.resolver import (
    TickSizeReferenceResolver,
    TickSizeResolutionStatus,
    validate_price_on_tick_grid,
)
from app.market_data.reference_data.tick_size import (
    NseTickSizeObservation,
    NseTickSizeSegment,
    TickSizeAvailabilitySemantics,
    TickSizeSourceClass,
)


T = datetime(2026, 8, 28, 10, tzinfo=UTC)


class MemoryRepository:
    def __init__(self, values: tuple[NseTickSizeObservation, ...] = ()) -> None:
        self.values = values

    def save_tick_size_observation(self, value: NseTickSizeObservation) -> None:
        self.values += (value,)

    def get_tick_size_observation(self, record_id: str) -> NseTickSizeObservation | None:
        return next((item for item in self.values if item.record_id == record_id), None)

    def list_tick_size_observations(self, canonical_instrument_id=None, source_class=None):
        return tuple(
            item for item in self.values
            if (canonical_instrument_id is None or item.canonical_instrument_id == canonical_instrument_id)
            and (source_class is None or item.source_class is source_class)
        )


def observation(
    record_id: str,
    *,
    tick: str = "0.05",
    instrument: str = "NSE:RELIANCE",
    source_class: TickSizeSourceClass = TickSizeSourceClass.OFFICIAL_EXCHANGE,
    source_name: str = "NSE/NDAL Masters Data CM",
    observed_at: datetime = T,
    effective: bool = False,
) -> NseTickSizeObservation:
    return NseTickSizeObservation(
        record_id=record_id,
        canonical_instrument_id=instrument,
        exchange=Exchange.NSE,
        segment=NseTickSizeSegment.NSE_CASH_EQUITY,
        isin="INE002A01018",
        tick_size=Decimal(tick),
        source_class=source_class,
        source_name=source_name,
        source_artifact_fingerprint=f"artifact-{record_id}",
        observed_at=observed_at,
        effective_from=observed_at if effective else None,
        effective_to=observed_at + timedelta(hours=2) if effective else None,
        availability_semantics=(
            TickSizeAvailabilitySemantics.EXPLICIT_EFFECTIVE_PERIOD
            if effective else TickSizeAvailabilitySemantics.FIRST_OBSERVED_ONLY
        ),
        warnings=(),
    )


def resolve(values=(), *, as_of=T, approved=frozenset()):
    return TickSizeReferenceResolver(MemoryRepository(tuple(values)), approved_licensed_sources=approved).resolve_tick_size(
        "NSE:RELIANCE", as_of=as_of,
    )


def test_no_observations_or_future_evidence_is_unavailable() -> None:
    assert resolve().status is TickSizeResolutionStatus.TICK_SIZE_UNAVAILABLE_FOR_AS_OF
    assert resolve((observation("future", observed_at=T + timedelta(seconds=1)),)).status is TickSizeResolutionStatus.TICK_SIZE_UNAVAILABLE_FOR_AS_OF


def test_first_observed_boundary_and_historical_as_of_are_exact() -> None:
    value = observation("official")
    assert resolve((value,), as_of=T - timedelta(microseconds=1)).status is TickSizeResolutionStatus.TICK_SIZE_UNAVAILABLE_FOR_AS_OF
    assert resolve((value,), as_of=T).status is TickSizeResolutionStatus.AVAILABLE
    later = observation("later", observed_at=T + timedelta(days=1))
    assert resolve((value, later), as_of=T).selected_record_id == "official"


def test_half_open_effective_interval_is_respected() -> None:
    value = observation("period", effective=True)
    assert resolve((value,), as_of=T + timedelta(hours=1, minutes=59, seconds=59)).status is TickSizeResolutionStatus.AVAILABLE
    assert resolve((value,), as_of=T + timedelta(hours=2)).status is TickSizeResolutionStatus.TICK_SIZE_UNAVAILABLE_FOR_AS_OF


def test_official_same_value_uses_deterministic_latest_lineage() -> None:
    older = observation("a", observed_at=T)
    later = observation("z", observed_at=T + timedelta(minutes=1))
    result = resolve((older, later), as_of=T + timedelta(minutes=1))
    assert result.status is TickSizeResolutionStatus.AVAILABLE
    assert result.tick_size == Decimal("0.05")
    assert result.selected_record_id == "z"
    assert result.corroborating_record_ids == ("a",)


def test_differing_official_evidence_fails_closed() -> None:
    result = resolve((observation("a"), observation("b", tick="0.10")))
    assert result.status is TickSizeResolutionStatus.REFERENCE_DATA_CONFLICT
    assert result.conflicting_record_ids == ("a", "b")
    assert result.tick_size is None


def test_approved_licensed_is_fallback_but_unapproved_is_ignored() -> None:
    licensed = observation(
        "licensed", source_class=TickSizeSourceClass.LICENSED_REFERENCE_DATA, source_name="Licensed Alpha"
    )
    unapproved = resolve((licensed,))
    assert unapproved.status is TickSizeResolutionStatus.TICK_SIZE_UNAVAILABLE_FOR_AS_OF
    assert unapproved.warnings == ("UNAPPROVED_LICENSED_SOURCE_IGNORED",)
    approved = resolve((licensed,), approved=frozenset({"Licensed Alpha"}))
    assert approved.status is TickSizeResolutionStatus.AVAILABLE
    assert approved.selected_source_class is TickSizeSourceClass.LICENSED_REFERENCE_DATA


def test_kotak_and_upstox_are_not_approved_by_default() -> None:
    values = (
        observation("kotak", source_class=TickSizeSourceClass.LICENSED_REFERENCE_DATA, source_name="Kotak Neo"),
        observation("upstox", source_class=TickSizeSourceClass.LICENSED_REFERENCE_DATA, source_name="Upstox"),
    )
    result = resolve(values)
    assert result.status is TickSizeResolutionStatus.TICK_SIZE_UNAVAILABLE_FOR_AS_OF
    assert result.eligible_licensed_record_ids == ()
    assert result.warnings == ("UNAPPROVED_LICENSED_SOURCE_IGNORED",)


def test_differing_approved_licensed_evidence_fails_closed() -> None:
    values = (
        observation("a", source_class=TickSizeSourceClass.LICENSED_REFERENCE_DATA, source_name="Licensed Alpha"),
        observation("b", tick="0.10", source_class=TickSizeSourceClass.LICENSED_REFERENCE_DATA, source_name="Licensed Alpha"),
    )
    assert resolve(values, approved=frozenset({"Licensed Alpha"})).status is TickSizeResolutionStatus.REFERENCE_DATA_CONFLICT


def test_official_and_licensed_same_value_uses_official_with_corroboration() -> None:
    official = observation("official")
    licensed = observation("licensed", source_class=TickSizeSourceClass.LICENSED_REFERENCE_DATA, source_name="Licensed Alpha")
    result = resolve((official, licensed), approved=frozenset({"Licensed Alpha"}))
    assert result.status is TickSizeResolutionStatus.AVAILABLE
    assert result.selected_record_id == "official"
    assert result.corroborating_record_ids == ("licensed",)


def test_official_and_licensed_different_values_conflict_without_silent_precedence() -> None:
    official = observation("official")
    licensed = observation("licensed", tick="0.10", source_class=TickSizeSourceClass.LICENSED_REFERENCE_DATA, source_name="Licensed Alpha")
    assert resolve((official, licensed), approved=frozenset({"Licensed Alpha"})).status is TickSizeResolutionStatus.REFERENCE_DATA_CONFLICT


def test_canonical_identity_isolation_and_as_of_must_be_aware() -> None:
    other = observation("other", instrument="NSE:INFY")
    assert resolve((other,)).status is TickSizeResolutionStatus.TICK_SIZE_UNAVAILABLE_FOR_AS_OF
    with pytest.raises(ValueError, match="TICK_REFERENCE_AS_OF_NAIVE"):
        resolve((observation("official"),), as_of=datetime(2026, 8, 28, 10))


@pytest.mark.parametrize("price,tick", [
    (Decimal("100.00"), Decimal("0.05")),
    (Decimal("100.05"), Decimal("0.05")),
    (Decimal("420.00"), Decimal("0.10")),
])
def test_exact_decimal_grid_accepts_aligned_prices(price, tick) -> None:
    assert validate_price_on_tick_grid(price, tick) is None


@pytest.mark.parametrize("price,tick", [
    (Decimal("100.03"), Decimal("0.05")),
    (Decimal("420.05"), Decimal("0.10")),
])
def test_exact_decimal_grid_rejects_misalignment_without_tolerance(price, tick) -> None:
    with pytest.raises(ValueError, match="TICK_GRID_ALIGNMENT_ERROR"):
        validate_price_on_tick_grid(price, tick)


@pytest.mark.parametrize("price,tick", [
    (Decimal("1"), Decimal("0")),
    (Decimal("1"), Decimal("-0.05")),
    (Decimal("NaN"), Decimal("0.05")),
    (Decimal("1"), Decimal("Infinity")),
])
def test_grid_rejects_invalid_reference_data(price, tick) -> None:
    with pytest.raises(ValueError, match="INVALID_TICK_REFERENCE_DATA"):
        validate_price_on_tick_grid(price, tick)


def test_grid_rejects_binary_float_without_coercion() -> None:
    with pytest.raises(ValueError, match="TICK_GRID_DECIMAL_REQUIRED"):
        validate_price_on_tick_grid(100.05, Decimal("0.05"))
