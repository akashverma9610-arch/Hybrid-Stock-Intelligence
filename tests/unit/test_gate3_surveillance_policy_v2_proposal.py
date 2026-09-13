"""Documentation proposal proofs, not a runtime selector or another Gate engine."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from hashlib import sha256
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from app.fundamentals.diagnostic_comparability import canonical_json, content_fingerprint
from app.gates.engine import ExecutionEligibility, ExecutionGateEngine, GateDecisionRecord, GateOutcome
from app.registry.canonical import EXECUTION_GATES, EXECUTION_GATE_REGISTRY_VERSION
from tests.unit import test_earnings_blackout_policy_v2_proposal as previous
from tests.unit.test_gate3_surveillance_policy_source_repair_2 import _input, _policy, _run
from tests.unit import test_execution_gates as reducer_fixture


ROOT = Path(__file__).resolve().parents[2]
PATH = ROOT / "docs/architecture/GATE3_SURVEILLANCE_POLICY_V2_PROPOSAL.json"
AT = datetime(2026, 9, 1, 9, tzinfo=UTC)
DAY = AT.date()
FAMILIES = ("ASM", "GSM", "PRICE_BAND")


def _read():
    return json.loads(PATH.read_text(encoding="utf-8"), object_pairs_hook=previous._unique_object)


def _digest(value):
    return content_fingerprint({k: v for k, v in value.items() if k != "proposal_fingerprint"})


def _lf_digest(path):
    return "sha256:" + sha256((ROOT / path).read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def _verify(value):
    """Test-only semantic guard in addition to content-hash verification."""
    assert value.keys() == _read().keys()
    assert value["proposal_fingerprint"] == _digest(value)
    assert (value["proposal_id"], value["proposal_version"]) == (
        "execution-gate-policy-v2-proposed", "v2-proposal.3")
    assert value["gate_ids"] == previous.GATE_IDS
    assert value["status"] == "PROPOSED" and value["activation_status"] == "NOT_ACTIVE"
    assert value["composite_approval"] == {
        "required": True, "approval_reference": None, "effective_at": None,
        "prior_gate6_approval_transfers": False,
    }
    gate = value["gate3_proposed"]
    assert gate["formula_inputs"] == list(FAMILIES)
    assert gate["blocking_thresholds"] == {
        "asm_stage_gte": 2, "gsm_stage_gt": 0, "static_circuit_fraction_lte": "0.05"}
    assert gate["freshness"] == {"max_age": 4, "unit": "trading_sessions", "boundary_inclusive": True}
    assert gate["precedence"] == value["gate3_v1"]["precedence"]
    assert gate["independent_blocking_component_overrides_missing_other_component"] is False
    assert gate["gate6_independent_veto_logic_imported"] is False
    assert value["security_status_guard"] == {
        "SECURITY_STATUS_IS_NOT_GATE3_FORMULA_INPUT": True, "role": "DESCRIPTIVE_SOURCE_FAMILY",
        "mandatory_pass_field": False, "blocking_predicate": None,
        "future_use_requires_separate_governance": True,
    }
    selector = value["effective_state_selector"]
    assert selector["name"] == "LATEST_PIT_VISIBLE_EFFECTIVE_SURVEILLANCE_STATE"
    assert selector["order"].index("FILTER_LOCAL_KNOWN_AT") < selector["order"].index("RESOLVE_EXPLICIT_VISIBLE_SUPERSESSION")
    for key in ("date_to_intraday_timestamp", "missing_effective_to_means_forever",
                "input_order_or_largest_timestamp_wins", "unknown_current_record_allows_older_nonblocking_fallback"):
        assert selector[key] is False
    assert value["known_at"]["inclusive_boundary"] is True
    assert value["known_at"]["late_observation_changes_prior_decision"] is False
    assert value["known_at"]["request_start_is_payload_observation"] is False
    assert value["known_at"]["future_ids_in_historical_output"] is False
    assert value["replay_and_pilot"]["v1_history_immutable"] is True
    assert value["replay_and_pilot"]["implicit_latest_policy"] is False
    assert all(flag is False for flag in value["runtime"].values())
    assert value["boundaries"] == {
        "V1_ACTIVE": True, "GATE_POLICY_V2_ACTIVE": False, "SIX_GATES_EXACTLY_SIX": True,
        "NO_FABRICATED_SURVEILLANCE_CLEARANCE": True, "NO_UNVERIFIED_CALENDAR_CLEARANCE": True,
        "NO_FUTURE_LEAKAGE": True, "NO_RETROACTIVE_SURVEILLANCE_STATE": True,
        "PILOT_SIMPLICITY_RULE": "ACTIVE", "AI_DECISION_AUTHORITY": False,
    }


def test_identity_and_exact_six_gates_without_a_second_candidate_authority():
    value = _read()
    _verify(value)
    old = previous._read()
    assert value["proposal_id"] == old["policy_id"]
    assert value["supersedes_candidate_reference"]["version"] == old["policy_version_candidate"]
    assert value["parent_policy"]["policy_id"] == old["parent_policy_version"]
    assert value["parent_policy"]["version"] == old["parent_version"]
    assert value["gate_registry_version"] == EXECUTION_GATE_REGISTRY_VERSION
    assert [g.gate_id for g in EXECUTION_GATES] == list(range(1, 7))
    assert value["versioning_model"] == "SINGLE_COMPOSITE_SUCCESSOR_BY_PINNED_REFERENCE"
    assert value["next_continuation"] == "EXECUTION_GATE_POLICY_V2_COMPOSITE_GOVERNANCE_APPROVAL"
    assert not value["next_continuation_started"]
    for path in (ROOT / "app").rglob("*.py"):
        source = path.read_text(encoding="utf-8")
        assert value["proposal_id"] not in source
        assert "GATE3_SURVEILLANCE_POLICY_V2_PROPOSAL" not in source


def test_gates_1245_exact_definitions_methods_and_configuration_are_unchanged():
    value = _read()
    old = previous._read()
    expected = [x for x in old["unchanged_gates"] if x["registry_id"] != 3]
    assert value["unchanged_gates"] == expected
    for item in expected:
        assert item["definition_fingerprint"] == content_fingerprint(EXECUTION_GATES[item["registry_id"] - 1])
        assert item["implementation_fingerprint"] == previous._method_fingerprint(item["method"])
    assert value["parent_policy"]["definition_file_fingerprint_lf"] == _lf_digest("app/gates/production_policy.py")


@pytest.mark.parametrize("path", previous.SOURCE_PATHS)
def test_active_v1_source_policy_authority_and_reducer_unchanged(path):
    assert _read()["frozen_source_fingerprints_lf"][path] == _lf_digest(path)


def test_v1_gate3_definition_and_all_thresholds_and_precedence_are_pinned():
    value = _read()
    old = value["gate3_v1"]
    assert old["definition_fingerprint"] == content_fingerprint(EXECUTION_GATES[2])
    assert old["implementation_fingerprint"] == previous._method_fingerprint("_surveillance")
    for name in ("formula_inputs", "blocking_thresholds", "precedence", "freshness", "pass_confidence_annotation"):
        assert old[name] == value["gate3_proposed"][name]
    config = _policy().gate_config
    assert config.disallowed_asm_stage == old["blocking_thresholds"]["asm_stage_gte"]
    assert config.disallow_gsm and Decimal(old["blocking_thresholds"]["static_circuit_fraction_lte"]) == config.circuit_limit_threshold
    assert config.surveillance_max_age_days == 4 and config.surveillance_freshness_basis == "trading_sessions"
    assert _policy().surveillance_source.latest_eligible_completed_session_required
    assert _policy().surveillance_source.coverage == (*FAMILIES, "SECURITY_STATUS")


def test_gate6_entire_proposal_and_approval_carried_by_exact_references_not_reapproved():
    ref = _read()["gate6_carry_forward"]
    p = json.loads((ROOT / ref["proposal_reference"]).read_text())
    a = json.loads((ROOT / ref["approval_reference"]).read_text())
    assert ref["proposal_fingerprint"] == p["proposal_fingerprint"] == _digest(p)
    assert ref["approval_fingerprint"] == a["approval_fingerprint"] == content_fingerprint({k: v for k, v in a.items() if k != "approval_fingerprint"})
    assert ref["definition_fingerprint"] == content_fingerprint(p["gate6_proposed"])
    assert ref["proposal_file_fingerprint_lf"] == _lf_digest(ref["proposal_reference"])
    assert ref["approval_file_fingerprint_lf"] == _lf_digest(ref["approval_reference"])
    assert ref["definition_pointer"] == "/gate6_proposed"
    assert ref["approval_id"] == a["approval_id"]
    assert ref["incorporation"] == "ALL_GATE6_SEMANTICS_RISK_ACCEPTANCE_AND_APPROVAL_CONSTRAINTS_UNCHANGED"
    assert ref["semantic_override_fields"] == []
    assert not ref["prior_approval_is_composite_approval"]
    assert ref["horizon_state"] == a["horizon"]["state"] == "POLICY_UNSET"
    assert ref["horizon_value"] is ref["no_veto_confidence"] is None
    assert ref["no_veto_means_clearance"] is ref["horizon_inherits_v1_five"] is False
    assert p["gate6_proposed"]["result_mapping"] == a["liveness"]["mapping"]
    assert ref["activation_blockers_incorporated"] is True


@dataclass(frozen=True)
class _Witness:
    """Synthetic bounded temporal premise only; never passed as production evidence."""
    receipt: str
    known: datetime
    sessions: tuple[date, ...] | None
    value: int
    supersedes: tuple[str, ...] = ()
    admitted: bool = True
    instant_interval: tuple[datetime, datetime] | None = None


def _select_witness(rows, *, as_of=AT, session=DAY):
    """Test-only illustration of visibility/applicability/explicit replacement order.

    Premises represent already-verified source semantics, not a source parser,
    current-time lookup, real receipt verifier, freshness calculator or collector.
    """
    if session is None:
        return None
    visible = tuple(x for x in rows if x.known <= as_of)
    if any(not x.admitted or x.sessions is None for x in visible):
        return None
    identities = {}
    for row in visible:
        if row.receipt in identities and row != identities[row.receipt]:
            return None
        identities[row.receipt] = row
    effective = tuple(x for x in identities.values() if session in x.sessions and (
        x.instant_interval is None or x.instant_interval[0] <= as_of < x.instant_interval[1]))
    # Supersession premises apply only after BOTH temporal boundaries.
    removed = {parent for x in effective for parent in x.supersedes}
    leaves = tuple(x for x in effective if x.receipt not in removed)
    if len(leaves) != 1:
        return None
    return leaves[0]


def _witness_payload(row):
    # Explicit source-date serialization; no invented time for session dates.
    return {
        "receipt": row.receipt, "known": row.known.astimezone(UTC).isoformat(),
        "sessions": None if row.sessions is None else tuple(x.isoformat() for x in row.sessions),
        "value": row.value, "supersedes": row.supersedes, "admitted": row.admitted,
        "instant_interval": None if row.instant_interval is None else tuple(
            x.astimezone(UTC).isoformat() for x in row.instant_interval),
    }


def test_current_session_not_prior_completed_session_and_known_at_is_inclusive():
    old = _Witness("prior-session-only", AT - timedelta(days=1), (DAY - timedelta(days=1),), 0)
    new = _Witness("current-restriction", AT, (DAY,), 2)
    assert _select_witness((old, new)) == new
    assert _select_witness((old, new), as_of=AT - timedelta(microseconds=1)) is None
    assert _select_witness((old,)) is None  # No invented cross-session applicability.
    assert _read()["known_at"]["rule"] == "VERIFIED_HSI_FIRST_OBSERVED_AT_LE_EVALUATION_AS_OF"


def test_late_restriction_never_rewrites_the_earlier_view_or_its_fingerprint():
    earlier = _Witness("proven-current-before-revision", AT - timedelta(hours=1), (DAY,), 0)
    later = _Witness("late-known-restriction", AT + timedelta(minutes=1), (DAY,), 2, (earlier.receipt,))
    before = _select_witness((earlier,))
    assert _select_witness((later, earlier)) == before
    assert content_fingerprint(_witness_payload(_select_witness((later, earlier)))) == content_fingerprint(_witness_payload(before))
    assert later.receipt not in canonical_json(_witness_payload(before))
    assert _select_witness((earlier, later), as_of=later.known) == later


def test_visible_but_not_effective_revision_does_not_remove_current_proof():
    current = _Witness("today", AT - timedelta(hours=1), (DAY,), 0)
    future = _Witness("tomorrow", AT, (DAY + timedelta(days=1),), 2, (current.receipt,))
    assert _select_witness((future, current)) == current


def test_date_only_and_unknown_precision_do_not_invent_intraday_clock_or_forever():
    day = _Witness("one-proven-session", AT, (DAY,), 2)
    assert _select_witness((day,)) == day and day.instant_interval is None
    assert _select_witness((day,), session=DAY + timedelta(days=1)) is None
    assert _select_witness((replace(day, sessions=None),)) is None
    assert _select_witness((day,), session=None) is None
    assert _read()["effective_state_selector"]["closed_session_implies_next_session"] is False


def test_source_supported_instant_interval_start_inclusive_end_exclusive():
    item = _Witness("explicit-source-interval", AT, (DAY,), 2,
                    instant_interval=(AT, AT + timedelta(minutes=1)))
    assert _select_witness((item,)) == item
    assert _select_witness((item,), as_of=AT + timedelta(minutes=1)) is None


def test_date_precision_and_equivalent_utc_witness_serialization_are_stable():
    row = _Witness("date-precision", AT, (DAY,), 2)
    alternate = replace(row, known=datetime.fromisoformat("2026-09-01T14:30:00+05:30"))
    payload = _witness_payload(row)
    assert payload["sessions"] == ("2026-09-01",)
    assert payload["instant_interval"] is None
    assert canonical_json(payload) == canonical_json(_witness_payload(alternate))
    assert content_fingerprint(payload) == content_fingerprint(json.loads(canonical_json(payload)))


def test_timezone_equivalence_and_future_removal_are_causal():
    current = _Witness("restriction", AT - timedelta(hours=1), (DAY,), 2)
    removal = _Witness("removal", AT + timedelta(minutes=1), (DAY,), 0, (current.receipt,))
    alternate = datetime.fromisoformat("2026-09-01T14:30:00+05:30")
    assert _select_witness((current, removal), as_of=alternate) == current
    assert _select_witness((current, removal), as_of=removal.known) == removal


def test_duplicates_conflicts_and_order_never_create_arbitrary_availability():
    old = _Witness("one", AT - timedelta(minutes=1), (DAY,), 0)
    new = _Witness("two", AT, (DAY,), 2)
    assert _select_witness((old, old)) == old
    assert _select_witness((old, replace(old, value=2))) is None
    assert _select_witness((old, new)) is _select_witness((new, old)) is None
    linked = replace(new, supersedes=(old.receipt,))
    assert _select_witness((old, linked)) == _select_witness((linked, old)) == linked
    assert _select_witness((old, replace(linked, admitted=False))) is None


@pytest.mark.parametrize("field,value,expected", [
    ("asm_stage", 1, "PASS"), ("asm_stage", 2, "FAIL"),
    ("gsm_stage", 0, "PASS"), ("gsm_stage", 1, "FAIL"),
    ("circuit_limit", Decimal(".05"), "FAIL"),
    ("circuit_limit", Decimal(".0501"), "PASS"),
    ("asm_stage", None, "INSUFFICIENT_DATA"),
    ("gsm_stage", None, "INSUFFICIENT_DATA"),
    ("circuit_limit", None, "INSUFFICIENT_DATA"),
])
def test_selected_synthetic_values_use_unchanged_runtime_formula(field, value, expected):
    observation = replace(_input().surveillance, **{field: value})
    result = _run(observation)
    assert result.decisions[2].outcome.value == expected
    assert len(result.decisions) == 6 and "NO_ACTION_OR_ORDER_CREATED" in result.warnings


def test_blocking_plus_missing_remains_insufficient_not_imported_gate6_veto_order():
    observation = replace(_input().surveillance, asm_stage=2, gsm_stage=None)
    assert _run(observation).decisions[2].outcome is GateOutcome.INSUFFICIENT_DATA
    assert _read()["result_contract"]["mixed_blocking_and_missing"] == "INSUFFICIENT_DATA_PRESERVE_V1_COMPLETENESS_PRECEDENCE"


@pytest.mark.parametrize("effective_day,expected", [(25, "PASS"), (24, "INSUFFICIENT_DATA")])
def test_existing_four_session_freshness_boundary_is_not_relaxed(effective_day, expected):
    observation = replace(_input().surveillance, effective_at=datetime(2026, 8, effective_day, 10, tzinfo=UTC))
    assert _run(observation).decisions[2].outcome.value == expected


def test_unverified_source_cannot_create_pass_or_blocking_risk_conclusion():
    observation = replace(_input().surveillance, asm_stage=2, authoritative=False)
    assert _run(observation).decisions[2].outcome is GateOutcome.INSUFFICIENT_DATA


@pytest.mark.parametrize("g3,g6,expected", [
    ("PASS", "PASS", "EXECUTABLE"), ("FAIL", "PASS", "BLOCKED"),
    ("INSUFFICIENT_DATA", "PASS", "INSUFFICIENT_DATA"),
    ("PASS", "FAIL", "BLOCKED"), ("PASS", "INSUFFICIENT_DATA", "INSUFFICIENT_DATA"),
    ("INSUFFICIENT_DATA", "FAIL", "BLOCKED"),
])
def test_composite_declarations_use_actual_six_gate_reducer_not_new_authority(g3, g6, expected):
    d3 = GateDecisionRecord("GATE_3_SURVEILLANCE", GateOutcome(g3), "SYNTHETIC_PROPOSAL_ONLY",
                           1.0 if g3 == "PASS" else None, ("synthetic-surveillance",), {})
    d6 = GateDecisionRecord("GATE_6_EARNINGS", GateOutcome(g6), "SYNTHETIC_PROPOSAL_ONLY",
                           None, ("synthetic-earnings",), {"earnings_clearance": "UNVERIFIED"})
    with patch.object(ExecutionGateEngine, "_surveillance", return_value=d3), patch.object(ExecutionGateEngine, "_blackout", return_value=d6):
        result = reducer_fixture.evaluate()
    assert [x.gate_id for x in result.decisions] == previous.GATE_IDS
    assert result.eligibility == ExecutionEligibility(expected)
    assert result.decisions[5].confidence is None
    assert result.decisions[5].parameters["earnings_clearance"] == "UNVERIFIED"
    assert "NO_ACTION_OR_ORDER_CREATED" in result.warnings


def test_source_identity_completeness_and_unknown_contracts_are_distinct():
    value = _read()
    for family in ("ASM", "GSM"):
        assert value["identity"][family]["scope"] == "SECURITY_LEVEL_APPLIES_TO_EXECUTION_INSTRUMENT"
        assert value["identity"][family]["list_row_series_required"] is False
        assert value["identity"][family]["exact_membership_and_framework_applicability_required"] is True
        assert value["component_source_contracts"][family]["official_product_complete"] is True
        assert value["component_source_contracts"][family]["adapter_completeness"] == "UNPROVEN"
    band = value["component_source_contracts"]["PRICE_BAND"]
    assert band["unknown"] == ["ABSENT", "BLANK", "DYNAMIC", "UNSUPPORTED", "IDENTITY_MISMATCH", "SOURCE_AMBIGUITY"]
    assert band["absence_is_nonblocking"] is False
    assert value["identity"]["PRICE_BAND"]["grain"] == "EXACT_NSE_EXECUTION_SYMBOL_PLUS_SERIES"
    assert value["identity"]["PRICE_BAND"]["series_default"] is None
    assert value["source_authority"]["hard"] == "NSE_EXECUTION_VENUE_AUTHORITY"
    assert value["source_authority"]["bse"] == "CORROBORATIVE_ONLY"


def test_blockers_downstream_reuse_and_no_new_calibration_project():
    value = _read()
    blockers = value["activation_blockers"]
    assert [b["id"] for b in blockers] == [f"G3A{i:02d}" for i in range(1, 13)]
    assert [b["classification"] for b in blockers] == ["BLOCKING"] * 10 + ["DEFERRED_FOR_REPLAY", "NON_BLOCKING"]
    assert value["replay_and_pilot"]["historical_perfection_required_for_prospective_pilot"] is False
    assert value["gate3_proposed"]["new_threshold_calibration_required"] is False
    for row in value["downstream_impact"]:
        assert (ROOT / row["reference"]).is_file()
    for path in value["reuse"].values():
        assert (ROOT / path.split("#")[0]).is_file()
    assert {r["consumer"] for r in value["downstream_impact"]} >= {
        "Six-Gates orchestration", "Brain", "Signals", "Portfolio", "Entry-ready lifecycle",
        "Backtest/replay", "Outcome ledger", "Alerts",
    }


def test_deterministic_complete_proposal_serialization_and_all_field_tamper_detection():
    value = _read()
    _verify(value)
    assert _digest(json.loads(canonical_json(value))) == value["proposal_fingerprint"]
    assert _digest(dict(reversed(tuple(value.items())))) == value["proposal_fingerprint"]
    for key in value.keys() - {"proposal_fingerprint"}:
        changed = deepcopy(value)
        del changed[key]
        assert _digest(changed) != value["proposal_fingerprint"]
    with pytest.raises(ValueError, match="DUPLICATE_PROPOSAL_KEY"):
        json.loads('{"status":"PROPOSED","status":"ACTIVE"}', object_pairs_hook=previous._unique_object)


@pytest.mark.parametrize("mutation", ["threshold", "status_input", "active", "approval_transfer", "retroactive", "timestamp_wins", "missing_bypass", "extra_gate", "date_clock", "unknown_fallback"])
def test_rehashing_unsafe_semantics_does_not_satisfy_proposal_contract(mutation):
    value = _read()
    if mutation == "threshold": value["gate3_proposed"]["blocking_thresholds"]["asm_stage_gte"] = 3
    elif mutation == "status_input": value["gate3_proposed"]["formula_inputs"].append("SECURITY_STATUS")
    elif mutation == "active": value["activation_status"] = "ACTIVE"
    elif mutation == "approval_transfer": value["composite_approval"]["prior_gate6_approval_transfers"] = True
    elif mutation == "retroactive": value["known_at"]["late_observation_changes_prior_decision"] = True
    elif mutation == "timestamp_wins": value["effective_state_selector"]["input_order_or_largest_timestamp_wins"] = True
    elif mutation == "missing_bypass": value["gate3_proposed"]["independent_blocking_component_overrides_missing_other_component"] = True
    elif mutation == "extra_gate": value["gate_ids"].append("GATE_7_STATUS")
    elif mutation == "date_clock": value["effective_state_selector"]["date_to_intraday_timestamp"] = True
    else: value["effective_state_selector"]["unknown_current_record_allows_older_nonblocking_fallback"] = True
    value["proposal_fingerprint"] = _digest(value)
    with pytest.raises(AssertionError):
        _verify(value)
