import ast
import dataclasses
import hashlib
import inspect
import json
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import pytest

import app.intelligence.hsi_signal as hsi_signal_module
from app.intelligence.hsi_signal import (
    DetectionTimeStatus,
    DiagnosticLineageReference,
    EvidenceLineageReference,
    HSISignal,
    HSISignalActionability,
    HSISignalError,
    HSISignalExecutionStatus,
    LineageAvailability,
    P1UnavailableReason,
    PortfolioRelevance,
    StrategyResolutionReference,
    StrategyResolutionStatus,
    ValueAvailability,
    hsi_signal_payload,
    serialize_hsi_signal,
)
from app.intelligence.opportunity_archetypes import OpportunityArchetype


T = datetime(2026, 9, 2, 10, 30, tzinfo=UTC)


def _fingerprint(value: str) -> str:
    return f"sha256:{hashlib.sha256(value.encode()).hexdigest()}"


def _diagnostic(rule_id: str = "24") -> DiagnosticLineageReference:
    return DiagnosticLineageReference(rule_id, f"diagnostic:{rule_id}", f"artifact:{rule_id}", _fingerprint(f"artifact:{rule_id}"))


def _evidence(event_id: str = "event:1") -> EvidenceLineageReference:
    return EvidenceLineageReference(event_id, f"evidence:{event_id}", _fingerprint(event_id))


def _unavailable_strategy() -> StrategyResolutionReference:
    return StrategyResolutionReference(StrategyResolutionStatus.STRATEGY_UNAVAILABLE)


def _signal(**overrides) -> HSISignal:
    values = {
        "canonical_instrument_id": "NSE:INE000000001",
        "watch_id": "market-wide-watch:watch-1",
        "watch_fingerprint": _fingerprint("watch-1"),
        "watch_as_of": T,
        "detected_at": None,
        "detection_time_status": DetectionTimeStatus.DETECTION_TIME_UNAVAILABLE,
        "archetype": OpportunityArchetype.EARNINGS_INFLECTION,
        "routing_policy_version": "opportunity-archetype-routing-policy/v1",
        "horizon": None,
        "horizon_availability": ValueAvailability.UNAVAILABLE,
        "horizon_routing_evidence_ref": None,
        "direction": None,
        "direction_availability": ValueAvailability.UNAVAILABLE,
        "direction_routing_evidence_ref": None,
        "strategy_resolution": _unavailable_strategy(),
        "diagnostic_lineage": (_diagnostic(),),
        "diagnostic_lineage_availability": LineageAvailability.PRESENT,
        "evidence_lineage": (),
        "evidence_lineage_availability": LineageAvailability.SOURCE_EMPTY,
        "source_watch_status": "WATCH_ACTIVE",
        "source_lifecycle_flags": ("DISCOVERED", "WATCH"),
        "blocker_codes": ("STRATEGY_UNAVAILABLE",),
    }
    values.update(overrides)
    return HSISignal.create(**values)


def test_hsi_signal_is_immutable_and_valid_minimal_construction_is_watch_only():
    value = _signal()

    with pytest.raises(dataclasses.FrozenInstanceError):
        value.watch_id = "changed"

    assert value.signal_id.startswith("hsi-signal:")
    assert value.actionability is HSISignalActionability.WATCH_ONLY
    assert value.execution_status is HSISignalExecutionStatus.NON_EXECUTABLE
    assert value.portfolio_relevance is PortfolioRelevance.NOT_EVALUATED
    assert value.watch_as_of == T
    assert value.detected_at is None
    assert value.detection_time_status is DetectionTimeStatus.DETECTION_TIME_UNAVAILABLE


def test_hsi_signal_timestamp_availability_never_uses_runtime_time():
    unavailable = _signal()
    available = _signal(
        detected_at=T - timedelta(minutes=5),
        detection_time_status=DetectionTimeStatus.AVAILABLE,
    )

    assert P1UnavailableReason.DETECTION_TIME_UNAVAILABLE in unavailable.unavailable_reasons
    assert P1UnavailableReason.DETECTION_TIME_UNAVAILABLE not in available.unavailable_reasons
    assert available.detected_at == T - timedelta(minutes=5)

    with pytest.raises(HSISignalError, match="DETECTION_TIME_REQUIRED"):
        _signal(detection_time_status=DetectionTimeStatus.AVAILABLE)
    with pytest.raises(HSISignalError, match="DETECTION_TIME_AFTER_WATCH_AS_OF"):
        _signal(detected_at=T + timedelta(seconds=1), detection_time_status=DetectionTimeStatus.AVAILABLE)
    with pytest.raises(HSISignalError, match="DETECTION_TIME_UNAVAILABLE_REQUIRED"):
        _signal(detected_at=T, detection_time_status=DetectionTimeStatus.DETECTION_TIME_UNAVAILABLE)

    equivalent_timezone = timezone(timedelta(hours=5, minutes=30))
    utc_detected = _signal(detected_at=T - timedelta(minutes=5), detection_time_status=DetectionTimeStatus.AVAILABLE)
    equivalent_detected = _signal(
        detected_at=(T - timedelta(minutes=5)).astimezone(equivalent_timezone),
        detection_time_status=DetectionTimeStatus.AVAILABLE,
    )
    assert utc_detected.signal_id == equivalent_detected.signal_id
    assert serialize_hsi_signal(utc_detected) == serialize_hsi_signal(equivalent_detected)


def test_hsi_signal_rejects_fabricated_optional_intelligence_values():
    with pytest.raises(HSISignalError, match="HORIZON_UNAVAILABLE_REQUIRED"):
        _signal(horizon="TACTICAL")
    with pytest.raises(HSISignalError, match="DIRECTION_UNAVAILABLE_REQUIRED"):
        _signal(direction="LONG")
    with pytest.raises(HSISignalError, match="HORIZON_ROUTING_EVIDENCE_REQUIRED"):
        _signal(horizon_availability=ValueAvailability.AVAILABLE, horizon="TACTICAL")
    with pytest.raises(HSISignalError, match="DIRECTION_ROUTING_EVIDENCE_REQUIRED"):
        _signal(direction_availability=ValueAvailability.AVAILABLE, direction="LONG")

    supported = _signal(
        horizon="TACTICAL", horizon_availability=ValueAvailability.AVAILABLE,
        horizon_routing_evidence_ref="routing:horizon",
        direction="LONG", direction_availability=ValueAvailability.AVAILABLE,
        direction_routing_evidence_ref="routing:direction",
    )
    assert P1UnavailableReason.HORIZON_UNAVAILABLE not in supported.unavailable_reasons
    assert P1UnavailableReason.DIRECTION_UNAVAILABLE not in supported.unavailable_reasons

    value = _signal()
    assert value.strength is value.confidence is value.materiality is None
    assert value.strength_availability is ValueAvailability.UNAVAILABLE
    assert value.confidence_availability is ValueAvailability.UNAVAILABLE
    assert value.materiality_availability is ValueAvailability.UNAVAILABLE
    assert value.expires_at is None
    assert value.expiry_availability is ValueAvailability.UNAVAILABLE
    assert {
        P1UnavailableReason.STRENGTH_UNAVAILABLE,
        P1UnavailableReason.CONFIDENCE_UNAVAILABLE,
        P1UnavailableReason.MATERIALITY_UNAVAILABLE,
        P1UnavailableReason.EXPIRY_POLICY_UNAVAILABLE,
    }.issubset(value.unavailable_reasons)


def test_hsi_signal_fixed_p1_states_cannot_be_supplied_or_tampered_with():
    with pytest.raises(TypeError):
        HSISignal(actionability=HSISignalActionability.WATCH_ONLY)  # type: ignore[call-arg]

    value = _signal()
    object.__setattr__(value, "portfolio_relevance", None)
    with pytest.raises(HSISignalError, match="FIXED_P1_STATE_INVALID"):
        value.verify()


def test_hsi_signal_requires_explicit_nonempty_lineage_and_canonical_collections():
    with pytest.raises(HSISignalError, match="LINEAGE_REQUIRED"):
        _signal(
            diagnostic_lineage=(), diagnostic_lineage_availability=LineageAvailability.SOURCE_EMPTY,
        )
    with pytest.raises(HSISignalError, match="EVIDENCE_LINEAGE_EMPTY_UNEXPLAINED"):
        _signal(evidence_lineage_availability=LineageAvailability.PRESENT)

    first, second = _diagnostic("6"), _diagnostic("24")
    one, two = _evidence("event:2"), _evidence("event:1")
    value = _signal(
        diagnostic_lineage=(second, first),
        evidence_lineage=(one, two),
        evidence_lineage_availability=LineageAvailability.PRESENT,
        blocker_codes=("Z_BLOCKER", "A_BLOCKER"),
    )
    assert value.diagnostic_lineage == (second, first)
    assert value.evidence_lineage == (two, one)
    assert value.blocker_codes == ("A_BLOCKER", "Z_BLOCKER")
    assert value.source_lifecycle_flags == ("DISCOVERED", "WATCH")

    with pytest.raises(HSISignalError, match="BLOCKERS_DUPLICATE"):
        _signal(blocker_codes=("A_BLOCKER", "A_BLOCKER"))
    with pytest.raises(HSISignalError, match="DIAGNOSTIC_LINEAGE_DUPLICATE"):
        _signal(diagnostic_lineage=(_diagnostic(), _diagnostic()))
    with pytest.raises(HSISignalError, match="DIAGNOSTIC_LINEAGE_CONFLICT"):
        _signal(diagnostic_lineage=(_diagnostic("24"), DiagnosticLineageReference(
            "24", "diagnostic:other", "artifact:other", _fingerprint("artifact:other"),
        )))
    with pytest.raises(HSISignalError, match="EVIDENCE_LINEAGE_DUPLICATE"):
        _signal(
            evidence_lineage=(_evidence(), _evidence()),
            evidence_lineage_availability=LineageAvailability.PRESENT,
        )
    with pytest.raises(HSISignalError, match="EVIDENCE_LINEAGE_CONFLICT"):
        _signal(
            evidence_lineage=(_evidence("event:1"), EvidenceLineageReference(
                "event:1", "evidence:event:1", _fingerprint("conflicting-evidence"),
            )),
            evidence_lineage_availability=LineageAvailability.PRESENT,
        )


def test_hsi_signal_strategy_resolution_contract_fails_closed():
    assert _signal().strategy_resolution.status is StrategyResolutionStatus.STRATEGY_UNAVAILABLE

    with pytest.raises(HSISignalError, match="STRATEGY_UNAVAILABLE_REFERENCE_FORBIDDEN"):
        StrategyResolutionReference(StrategyResolutionStatus.STRATEGY_UNAVAILABLE, policy_id="policy")
    with pytest.raises(HSISignalError, match="STRATEGY_RESOLUTION_PROVENANCE_REQUIRED"):
        StrategyResolutionReference(StrategyResolutionStatus.RESOLVED, policy_id="policy")


def test_hsi_signal_serialization_is_stable_and_json_safe():
    value = _signal(
        diagnostic_lineage=(_diagnostic("24"), _diagnostic("6")),
        evidence_lineage=(_evidence("event:2"), _evidence("event:1")),
        evidence_lineage_availability=LineageAvailability.PRESENT,
    )
    reordered = _signal(
        diagnostic_lineage=(_diagnostic("6"), _diagnostic("24")),
        evidence_lineage=(_evidence("event:1"), _evidence("event:2")),
        evidence_lineage_availability=LineageAvailability.PRESENT,
    )

    serialized = serialize_hsi_signal(value)
    assert serialized == serialize_hsi_signal(value) == serialize_hsi_signal(reordered)
    assert value.signal_id == reordered.signal_id
    assert value.fingerprint == reordered.fingerprint
    payload = json.loads(serialized)
    assert payload == hsi_signal_payload(value)
    assert payload["watch_as_of"] == T.isoformat()


def test_hsi_signal_normalizes_equivalent_timezone_timestamps_and_separates_identity_from_content_fingerprint():
    equivalent_timezone = timezone(timedelta(hours=5, minutes=30))
    utc_value = _signal()
    equivalent_value = _signal(watch_as_of=T.astimezone(equivalent_timezone))
    changed_content = _signal(blocker_codes=("ADDITIONAL_SOURCE_BLOCKER", "STRATEGY_UNAVAILABLE"))

    assert utc_value.signal_id == equivalent_value.signal_id
    assert utc_value.fingerprint == equivalent_value.fingerprint
    assert serialize_hsi_signal(utc_value) == serialize_hsi_signal(equivalent_value)
    assert utc_value.signal_id == changed_content.signal_id
    assert utc_value.fingerprint != changed_content.fingerprint

    object.__setattr__(utc_value, "signal_id", "hsi-signal:tampered")
    with pytest.raises(HSISignalError, match="IDENTITY_MISMATCH"):
        utc_value.verify()
    object.__setattr__(equivalent_value, "fingerprint", "tampered")
    with pytest.raises(HSISignalError, match="FINGERPRINT_MISMATCH"):
        equivalent_value.verify()


def test_hsi_signal_rejects_malformed_canonical_identity_and_fingerprints():
    with pytest.raises(HSISignalError, match="IDENTITY_INVALID"):
        _signal(canonical_instrument_id="NSE: INE000000001")
    with pytest.raises(HSISignalError, match="WATCH_FINGERPRINT_INVALID"):
        _signal(watch_fingerprint="not-a-fingerprint")
    with pytest.raises(HSISignalError, match="DIAGNOSTIC_LINEAGE_FINGERPRINT_INVALID"):
        DiagnosticLineageReference("24", "diagnostic:24", "artifact:24", "malformed")


def test_hsi_signal_contract_has_no_trade_execution_or_portfolio_object_fields():
    field_names = {field.name for field in dataclasses.fields(HSISignal)}
    forbidden = {
        "entry_price", "stop_loss", "target_price", "market_price", "quantity",
        "sizing", "allocation", "instruction", "order", "broker", "portfolio",
    }
    assert not field_names.intersection(forbidden)
    assert "portfolio_relevance" in field_names


def test_hsi_signal_module_has_no_signal_broker_portfolio_or_persistence_dependency():
    tree = ast.parse(Path(inspect.getsourcefile(hsi_signal_module)).read_text(encoding="utf-8"))
    imports = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    forbidden_prefixes = ("app.signals", "app.broker", "app.portfolio", "app.storage", "app.api")
    assert not any(name.startswith(forbidden_prefixes) for name in imports)
