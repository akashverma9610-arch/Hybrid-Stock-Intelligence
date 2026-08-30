from __future__ import annotations

from copy import deepcopy

import pytest

from app.intelligence.intelligence_delta import IntelligenceDeltaError, compare_intelligence_states
from app.intelligence.intelligence_delta_serialization import (
    IntelligenceDeltaSerializationError, deserialize_intelligence_delta,
    reconstruct_intelligence_delta, serialize_intelligence_delta,
)
from app.intelligence.unified_state import IntelligenceEvidenceDomain
from tests.unit.test_intelligence_delta import T, _pair, _reference, _state


def _delta():
    previous, current = _pair(
        (_reference(IntelligenceEvidenceDomain.NEWS_CATALYSTS, fingerprint="news:old"),),
        (_reference(IntelligenceEvidenceDomain.NEWS_CATALYSTS, fingerprint="news:new"), _reference(IntelligenceEvidenceDomain.SECTOR)),
    )
    return previous, current, compare_intelligence_states(previous, current)


def test_exact_round_trip_for_multi_domain_delta_and_reconstruction():
    previous, current, value = _delta()
    payload = serialize_intelligence_delta(value)
    restored = deserialize_intelligence_delta(payload)
    assert restored == value
    assert reconstruct_intelligence_delta(previous, current, restored) == value


def test_no_change_round_trip_preserves_later_as_of_semantics():
    ref = _reference(IntelligenceEvidenceDomain.MARKET_DATA)
    previous, current = _pair((ref,), (ref,))
    value = compare_intelligence_states(previous, current)
    assert deserialize_intelligence_delta(serialize_intelligence_delta(value)) == value


@pytest.mark.parametrize("path,value", [
    (("canonical_instrument_id",), "NSE:OTHER"),
    (("previous_state_fingerprint",), "tampered"),
    (("current_state_fingerprint",), "tampered"),
    (("previous_as_of",), "2026-08-30T10:00:00+00:00"),
    (("changed_domains", 0), "MARKET_DATA"),
    (("domain_deltas", 0, "change_kinds", 0), "STATUS_CHANGED"),
    (("domain_deltas", 0, "current_reference", "artifact_fingerprints", 0), "tampered"),
    (("affected_output_contexts",), ["ENTRY_SETUP_REVIEW"]),
    (("impact_policy_fingerprint",), "tampered"),
    (("warnings",), ["TAMPERED"]),
])
def test_semantic_tampering_fails_closed(path, value):
    _, _, delta = _delta(); payload = deepcopy(serialize_intelligence_delta(delta))
    target = payload
    for key in path[:-1]: target = target[key]
    target[path[-1]] = value
    with pytest.raises((IntelligenceDeltaSerializationError, IntelligenceDeltaError)):
        deserialize_intelligence_delta(payload)


def test_unknown_enum_naive_timestamp_and_corrupt_nested_delta_fail_closed():
    _, _, delta = _delta()
    for mutate in (
        lambda payload: payload.__setitem__("status", "UNKNOWN"),
        lambda payload: payload.__setitem__("previous_as_of", "2026-08-28T10:00:00"),
        lambda payload: payload["domain_deltas"][0].__setitem__("domain", "UNKNOWN"),
    ):
        payload = deepcopy(serialize_intelligence_delta(delta)); mutate(payload)
        with pytest.raises((IntelligenceDeltaSerializationError, IntelligenceDeltaError)):
            deserialize_intelligence_delta(payload)


def test_reconstruction_rejects_wrong_state_pair_and_current_policy_is_not_reinterpreted():
    previous, current, delta = _delta()
    wrong = _state(at=T, references=())
    with pytest.raises(IntelligenceDeltaSerializationError, match="RECONSTRUCTION_MISMATCH"):
        reconstruct_intelligence_delta(wrong, current, delta)
