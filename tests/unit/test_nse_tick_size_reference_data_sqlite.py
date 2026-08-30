from __future__ import annotations

import json
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.market_data.models import Exchange
from app.market_data.reference_data.repository import TickSizeObservationRepository
from app.market_data.reference_data.sqlite_repository import SQLiteTickSizeObservationRepository
from app.market_data.reference_data.tick_size import (
    NseTickSizeObservation,
    NseTickSizeSegment,
    TickSizeAvailabilitySemantics,
    TickSizeSourceClass,
)


T = datetime(2026, 8, 28, 16, tzinfo=timezone.utc)


def observation(
    record_id: str = "tick-1",
    *,
    instrument: str = "NSE:RELIANCE",
    source_class: TickSizeSourceClass = TickSizeSourceClass.OFFICIAL_EXCHANGE,
    observed_at: datetime = T,
    explicit: bool = False,
) -> NseTickSizeObservation:
    return NseTickSizeObservation(
        record_id=record_id,
        canonical_instrument_id=instrument,
        exchange=Exchange.NSE,
        segment=NseTickSizeSegment.NSE_CASH_EQUITY,
        isin="INE002A01018",
        tick_size=Decimal("0.05"),
        source_class=source_class,
        source_name="NSE/NDAL Masters Data CM" if source_class is TickSizeSourceClass.OFFICIAL_EXCHANGE else "Licensed data vendor",
        source_artifact_fingerprint=f"artifact-{record_id}",
        observed_at=observed_at,
        effective_from=observed_at if explicit else None,
        effective_to=observed_at + timedelta(days=1) if explicit else None,
        availability_semantics=(
            TickSizeAvailabilitySemantics.EXPLICIT_EFFECTIVE_PERIOD
            if explicit
            else TickSizeAvailabilitySemantics.FIRST_OBSERVED_ONLY
        ),
        warnings=("EOD_SNAPSHOT",),
    )


def test_repository_contract_is_narrow_and_insert_only() -> None:
    methods = set(TickSizeObservationRepository.__dict__)
    assert {"save_tick_size_observation", "get_tick_size_observation", "list_tick_size_observations"} <= methods
    assert not {"update_tick_size_observation", "delete_tick_size_observation", "get_tick_size_as_of"} & methods


def test_table_initializes_and_official_and_licensed_observations_save(tmp_path) -> None:
    repository = SQLiteTickSizeObservationRepository(tmp_path / "ticks.sqlite")
    official = observation("official")
    licensed = observation("licensed", source_class=TickSizeSourceClass.LICENSED_REFERENCE_DATA)
    repository.save_tick_size_observation(official)
    repository.save_tick_size_observation(licensed)
    assert repository.get_tick_size_observation("official") == official
    assert repository.get_tick_size_observation("licensed") == licensed
    assert repository._connection.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='nse_tick_size_observations'"
    ).fetchone() is not None


def test_absent_get_is_none_and_list_is_deterministic_with_exact_filters(tmp_path) -> None:
    repository = SQLiteTickSizeObservationRepository(tmp_path / "ticks.sqlite")
    later = observation("later", observed_at=T + timedelta(days=2))
    first = observation("first", observed_at=T)
    licensed = observation(
        "licensed", instrument="NSE:INFY", source_class=TickSizeSourceClass.LICENSED_REFERENCE_DATA
    )
    for value in (later, licensed, first):
        repository.save_tick_size_observation(value)
    assert repository.get_tick_size_observation("missing") is None
    assert tuple(value.record_id for value in repository.list_tick_size_observations()) == ("first", "licensed", "later")
    assert repository.list_tick_size_observations(canonical_instrument_id="NSE:RELIANCE") == (first, later)
    assert repository.list_tick_size_observations(source_class=TickSizeSourceClass.LICENSED_REFERENCE_DATA) == (licensed,)
    assert repository.list_tick_size_observations(
        canonical_instrument_id="NSE:INFY", source_class=TickSizeSourceClass.LICENSED_REFERENCE_DATA
    ) == (licensed,)


def test_reopen_preserves_exact_immutable_evidence(tmp_path) -> None:
    path = tmp_path / "ticks.sqlite"
    value = observation("durable", explicit=True)
    first = SQLiteTickSizeObservationRepository(path)
    first.save_tick_size_observation(value)
    first.close()
    reopened = SQLiteTickSizeObservationRepository(path)
    assert reopened.get_tick_size_observation(value.record_id) == value


@pytest.mark.parametrize(
    "changed",
    [
        lambda value: replace(value, tick_size=Decimal("0.10"), evidence_fingerprint=""),
        lambda value: replace(value, canonical_instrument_id="NSE:INFY", evidence_fingerprint=""),
        lambda value: replace(value, observed_at=T + timedelta(days=1), evidence_fingerprint=""),
        lambda value: replace(value, source_artifact_fingerprint="different", evidence_fingerprint=""),
    ],
)
def test_same_id_semantic_conflicts_fail_closed(tmp_path, changed) -> None:
    repository = SQLiteTickSizeObservationRepository(tmp_path / "ticks.sqlite")
    original = observation()
    repository.save_tick_size_observation(original)
    with pytest.raises(ValueError, match="immutable and cannot be overwritten"):
        repository.save_tick_size_observation(changed(original))
    assert repository.get_tick_size_observation(original.record_id) == original


def test_multiple_immutable_records_for_same_instrument_coexist(tmp_path) -> None:
    repository = SQLiteTickSizeObservationRepository(tmp_path / "ticks.sqlite")
    first = observation("first")
    second = observation("second", observed_at=T + timedelta(days=1), explicit=True)
    repository.save_tick_size_observation(first)
    repository.save_tick_size_observation(second)
    assert repository.list_tick_size_observations(canonical_instrument_id="NSE:RELIANCE") == (first, second)


@pytest.mark.parametrize("field, replacement", [
    ("tick_size", "0.10"),
    ("canonical_instrument_id", "NSE:INFY"),
    ("observed_at", "2026-08-29T16:00:00+00:00"),
])
def test_tampered_persisted_payload_fails_closed_for_get_and_list(tmp_path, field, replacement) -> None:
    repository = SQLiteTickSizeObservationRepository(tmp_path / "ticks.sqlite")
    value = observation()
    repository.save_tick_size_observation(value)
    payload = repository._connection.execute(
        "SELECT payload_json FROM nse_tick_size_observations WHERE id=?", (value.record_id,)
    ).fetchone()["payload_json"]
    tampered = json.loads(payload)
    tampered[field] = replacement
    repository._connection.execute(
        "UPDATE nse_tick_size_observations SET payload_json=? WHERE id=?",
        (json.dumps(tampered, sort_keys=True, separators=(",", ":")), value.record_id),
    )
    repository._connection.commit()
    with pytest.raises(ValueError, match="NSE_TICK_EVIDENCE_FINGERPRINT_MISMATCH"):
        repository.get_tick_size_observation(value.record_id)
    with pytest.raises(ValueError, match="NSE_TICK_EVIDENCE_FINGERPRINT_MISMATCH"):
        repository.list_tick_size_observations()


def test_persistence_is_decimal_and_provenance_exact(tmp_path) -> None:
    repository = SQLiteTickSizeObservationRepository(tmp_path / "ticks.sqlite")
    value = observation("exact", explicit=True)
    repository.save_tick_size_observation(value)
    recovered = repository.get_tick_size_observation("exact")
    assert recovered is not None
    assert recovered.tick_size == Decimal("0.05")
    assert recovered.observed_at == value.observed_at
    assert recovered.effective_from == value.effective_from
    assert recovered.effective_to == value.effective_to
    assert recovered.warnings == ("EOD_SNAPSHOT",)
    assert recovered.source_artifact_fingerprint == value.source_artifact_fingerprint
