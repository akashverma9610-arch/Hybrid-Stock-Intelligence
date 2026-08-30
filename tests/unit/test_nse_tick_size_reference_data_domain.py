from dataclasses import replace
from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.market_data.models import Exchange
from app.market_data.reference_data.tick_size import (
    NseTickSizeObservation,
    NseTickSizeSegment,
    TickSizeAvailabilitySemantics,
    TickSizeSourceClass,
)
from app.market_data.reference_data.tick_size_serialization import (
    nse_tick_size_observation_from_dict,
    nse_tick_size_observation_to_dict,
)


OBSERVED = datetime(2026, 8, 28, 16, tzinfo=UTC)


def observation(**changes):
    value = dict(
        record_id="nse-tick-1",
        canonical_instrument_id="NSE:RELIANCE",
        exchange=Exchange.NSE,
        segment=NseTickSizeSegment.NSE_CASH_EQUITY,
        isin="INE002A01018",
        tick_size=Decimal("0.05"),
        source_class=TickSizeSourceClass.OFFICIAL_EXCHANGE,
        source_name="NSE/NDAL Masters Data CM",
        source_artifact_fingerprint="sha256:master",
        observed_at=OBSERVED,
        effective_from=None,
        effective_to=None,
        availability_semantics=TickSizeAvailabilitySemantics.FIRST_OBSERVED_ONLY,
        warnings=("EOD_SNAPSHOT",),
    )
    value.update(changes)
    return NseTickSizeObservation(**value)


def test_valid_official_and_licensed_observations_construct() -> None:
    official = observation()
    licensed = observation(
        record_id="licensed-1",
        source_class=TickSizeSourceClass.LICENSED_REFERENCE_DATA,
        source_name="Licensed reference provider",
        availability_semantics=TickSizeAvailabilitySemantics.EXPLICIT_EFFECTIVE_PERIOD,
        effective_from=OBSERVED - timedelta(hours=1),
        effective_to=OBSERVED + timedelta(days=1),
    )
    assert official.tick_size == Decimal("0.05")
    assert licensed.source_class is TickSizeSourceClass.LICENSED_REFERENCE_DATA


@pytest.mark.parametrize(
    ("changes", "code"),
    [
        ({"canonical_instrument_id": ""}, "NSE_TICK_CANONICAL_INSTRUMENT_REQUIRED"),
        ({"exchange": Exchange.BSE}, "NSE_TICK_EXCHANGE_INVALID"),
        ({"segment": "NSE_FO"}, "NSE_TICK_SEGMENT_INVALID"),
        ({"tick_size": Decimal("0")}, "NSE_TICK_VALUE_INVALID"),
        ({"tick_size": Decimal("-0.01")}, "NSE_TICK_VALUE_INVALID"),
        ({"tick_size": Decimal("NaN")}, "NSE_TICK_VALUE_INVALID"),
        ({"tick_size": 0.05}, "NSE_TICK_DECIMAL_REQUIRED"),
        ({"observed_at": datetime(2026, 8, 28, 16)}, "NSE_TICK_OBSERVED_AT_NAIVE"),
        ({"availability_semantics": TickSizeAvailabilitySemantics.EXPLICIT_EFFECTIVE_PERIOD}, "NSE_TICK_EXPLICIT_EFFECTIVE_FROM_REQUIRED"),
        ({"effective_from": OBSERVED, "effective_to": OBSERVED}, "NSE_TICK_FIRST_OBSERVED_EFFECTIVITY_FORBIDDEN"),
        ({"warnings": ["not immutable"]}, "NSE_TICK_WARNINGS_INVALID"),
    ],
)
def test_invalid_domain_values_fail_closed(changes, code) -> None:
    with pytest.raises(ValueError, match=code):
        observation(**changes)


def test_invalid_explicit_effective_interval_fails_closed() -> None:
    with pytest.raises(ValueError, match="NSE_TICK_EFFECTIVE_INTERVAL_INVALID"):
        observation(
            availability_semantics=TickSizeAvailabilitySemantics.EXPLICIT_EFFECTIVE_PERIOD,
            effective_from=OBSERVED,
            effective_to=OBSERVED - timedelta(seconds=1),
        )


def test_eligible_from_uses_maximum_and_interval_is_half_open() -> None:
    value = observation(
        availability_semantics=TickSizeAvailabilitySemantics.EXPLICIT_EFFECTIVE_PERIOD,
        effective_from=OBSERVED + timedelta(days=1),
        effective_to=OBSERVED + timedelta(days=2),
    )
    assert value.eligible_from == OBSERVED + timedelta(days=1)
    assert not value.is_eligible_as_of(OBSERVED)
    assert value.is_eligible_as_of(value.eligible_from)
    assert not value.is_eligible_as_of(OBSERVED + timedelta(days=2))


def test_first_observed_metadata_never_backdates() -> None:
    value = observation()
    assert value.eligible_from == OBSERVED
    assert not value.is_eligible_as_of(OBSERVED - timedelta(microseconds=1))
    assert value.is_eligible_as_of(OBSERVED)
    with pytest.raises(ValueError, match="NSE_TICK_AS_OF_NAIVE"):
        value.is_eligible_as_of(datetime(2026, 8, 28, 16))


def test_serialization_round_trip_preserves_exact_semantics() -> None:
    value = observation(observed_at=OBSERVED.astimezone(timezone(timedelta(hours=5, minutes=30))))
    restored = nse_tick_size_observation_from_dict(nse_tick_size_observation_to_dict(value))
    assert restored == value
    assert restored.tick_size == Decimal("0.05")
    assert restored.source_class is TickSizeSourceClass.OFFICIAL_EXCHANGE
    assert restored.warnings == ("EOD_SNAPSHOT",)
    assert restored.observed_at.tzinfo is not None


@pytest.mark.parametrize("field,value", [
    ("tick_size", "0.01"),
    ("canonical_instrument_id", "NSE:OTHER"),
    ("source_class", TickSizeSourceClass.LICENSED_REFERENCE_DATA.value),
    ("observed_at", (OBSERVED + timedelta(minutes=1)).isoformat()),
    ("effective_from", OBSERVED.isoformat()),
    ("source_artifact_fingerprint", "sha256:other"),
])
def test_semantic_payload_tampering_retaining_fingerprint_fails_closed(field, value) -> None:
    payload = nse_tick_size_observation_to_dict(observation())
    if field == "effective_from":
        payload["availability_semantics"] = TickSizeAvailabilitySemantics.EXPLICIT_EFFECTIVE_PERIOD.value
        payload["effective_to"] = (OBSERVED + timedelta(days=1)).isoformat()
    payload[field] = value
    with pytest.raises(ValueError, match="NSE_TICK_EVIDENCE_FINGERPRINT_MISMATCH"):
        nse_tick_size_observation_from_dict(payload)


def test_malformed_serialized_payload_fails_closed_without_repair() -> None:
    payload = nse_tick_size_observation_to_dict(observation())
    payload["tick_size"] = 0.05
    with pytest.raises(ValueError, match="NSE_TICK_SERIALIZATION_INVALID"):
        nse_tick_size_observation_from_dict(payload)


def test_semantic_changes_change_fingerprint() -> None:
    value = observation()
    assert replace(value, tick_size=Decimal("0.01"), evidence_fingerprint="").evidence_fingerprint != value.evidence_fingerprint
    assert replace(value, source_artifact_fingerprint="sha256:new", evidence_fingerprint="").evidence_fingerprint != value.evidence_fingerprint
