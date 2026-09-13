"""Static composite approval and synthetic composition; no runtime activation."""
from __future__ import annotations

import ast
from contextlib import ExitStack
from copy import deepcopy
from dataclasses import replace
from datetime import timedelta
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from app.fundamentals.diagnostic_comparability import canonical_json, content_fingerprint
from app.gates.engine import ExecutionGateEngine, GateDecisionRecord, GateOutcome
from app.registry.canonical import EXECUTION_GATES
from tests.unit import test_gate3_surveillance_policy_v2_proposal as proposal_tests
from tests.unit import test_earnings_blackout_policy_v2_proposal as gate6_tests


ROOT = Path(__file__).resolve().parents[2]
ARTIFACT = ROOT / "docs/architecture/EXECUTION_GATE_POLICY_V2_COMPOSITE_GOVERNANCE_APPROVAL.json"
PROPOSAL_FP = "sha256:57bbd7af01fe14fa95ae419187302d5dcc353e3cbd98181e43b5f691cb97ab3d"
TOP_KEYS = set("""
schema_version approval_id baseline_commit authority decision approval_status scope
activation_status runtime_effective_at proposal_reference reviewed_files_lf single_successor
gate_ids unchanged_gate_proof gate3_approval gate3_temporal_approval gate6_carry_forward
cross_gate_and_liveness research_boundary historical_isolation pilot blocker_register
downstream_impact architecture boundaries runtime next_continuation next_continuation_started
fingerprint_scheme approval_fingerprint
""".split())
BOUNDARIES = {
    "V1_ACTIVE": True, "GATE_POLICY_V2_ACTIVE": False, "SIX_GATES_EXACTLY_SIX": True,
    "NO_FABRICATED_SURVEILLANCE_CLEARANCE": True, "NO_UNVERIFIED_CALENDAR_CLEARANCE": True,
    "NO_FUTURE_LEAKAGE": True, "NO_RETROACTIVE_SURVEILLANCE_STATE": True,
    "NO_RETROACTIVE_BLACKOUT": True, "NO_HORIZON_GUESS": True,
    "PILOT_SIMPLICITY_RULE": "ACTIVE", "AI_DECISION_AUTHORITY": False,
}
BLOCKER_MAP = (
    ("ASM_COMPLETE_EXPORT", ("g3:G3A01",)),
    ("GSM_COMPLETE_EXPORT", ("g3:G3A02",)),
    ("EXACT_EXECUTION_PRICE_BAND", ("g3:G3A03",)),
    ("TRUSTED_PROSPECTIVE_RECEIPTS_AND_SOURCE_ADMISSION", ("g3:G3A04", "g6:B02")),
    ("SURVEILLANCE_EFFECTIVE_SELECTION", ("g3:G3A05",)),
    ("SOURCE_CONFLICT_AND_LIFECYCLE_ADMISSION", ("g3:G3A06", "g6:B03")),
    ("SINGLE_ENGINE_COMPONENT_ADAPTERS", ("g3:G3A07", "g6:B04")),
    ("SURVEILLANCE_PROSPECTIVE_CANARY", ("g3:G3A09",)),
    ("EARNINGS_HORIZON_AND_CALIBRATION", ("g6:B01",)),
    ("GATE6_NO_VETO_CONFIDENCE_GUARD", ("g6:B05",)),
    ("LOSSLESS_EXECUTION_METADATA_PROPAGATION", ("g3:G3A08", "g6:B06")),
    ("SIGNAL_PORTFOLIO_ENTRY_READY_REVIEW", ("g3:G3A08", "g6:B07")),
    ("OUTCOME_AND_CALIBRATION_COMPATIBILITY", ("g6:B09",)),
    ("COMPOSITE_VERSION_SELECTION_AND_COMPATIBILITY", ("g3:G3A08", "g6:B04")),
    ("HISTORICAL_POLICY_VERSION_ISOLATION", ("g3:G3A10", "g6:B10")),
    ("COMPLETE_SURVEILLANCE_HISTORY", ("g3:G3A11",)),
    ("COMPLETE_EARNINGS_HISTORY_AND_OUTCOMES", ("g6:B11",)),
    ("AUTHORITATIVE_NEGATIVE_CALENDAR_CLEARANCE", ("g6:B12",)),
    ("OPTIONAL_ALERTS", ("g3:G3A12", "g6:B08")),
    ("OPTIONAL_RESULTS_SEASON_CONTEXT", ("g6:B13",)),
)


def _read(path=ARTIFACT):
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=gate6_tests._unique_object)


def _unsigned(value):
    return {key: item for key, item in value.items() if key != "approval_fingerprint"}


def _verify(value):
    """Test-only semantic approval guard: rehashing does not grant authority."""
    p = proposal_tests._read()
    assert value.keys() == TOP_KEYS
    assert content_fingerprint(_unsigned(value)) == value["approval_fingerprint"]
    assert value["proposal_reference"] == {
        "path": "docs/architecture/GATE3_SURVEILLANCE_POLICY_V2_PROPOSAL.json",
        "policy_id": p["proposal_id"], "policy_version": p["proposal_version"],
        "proposal_fingerprint": PROPOSAL_FP, "parent_policy_id": "six-gates-production-v1",
        "parent_version": "v1", "original_status": "PROPOSED", "original_artifact_overwritten": False,
    }
    assert p["proposal_fingerprint"] == proposal_tests._digest(p) == PROPOSAL_FP
    assert value["approval_id"] == "execution-gate-policy-v2-composite-governance-approval/v1"
    assert value["approval_status"] == "COMPOSITE_V2_GOVERNANCE_APPROVED_WITH_ACTIVATION_BLOCKERS"
    assert value["decision"] == "A" and value["activation_status"] == "NOT_ACTIVE"
    assert value["runtime_effective_at"] is None
    assert value["boundaries"] == BOUNDARIES
    assert all(x is False for x in value["runtime"].values())
    assert value["gate_ids"] == gate6_tests.GATE_IDS
    single = value["single_successor"]
    assert single["governed_future_candidate"] == "execution-gate-policy-v2-proposed/v2-proposal.3"
    assert single["existing_reducer_only"] is True
    for key in ("independent_gate3_policy_authority", "independent_gate6_policy_authority",
                "automatic_prior_approval_transfer", "runtime_policy_registered"):
        assert single[key] is False
    g3 = value["gate3_approval"]
    assert g3["semantic_delta"] == p["gate3_proposed"]["semantic_delta"] == "SOURCE_STATE_SELECTION_ONLY"
    assert g3["formula_inputs"] == ["ASM", "GSM", "PRICE_BAND"]
    assert g3["blocking_thresholds"] == p["gate3_v1"]["blocking_thresholds"]
    assert g3["freshness"] == p["gate3_v1"]["freshness"]
    assert g3["security_status"] == {
        "role": "DESCRIPTIVE_SOURCE_FAMILY", "formula_input": False,
        "mandatory_pass_field": False, "blocking_predicate": None,
    }
    assert g3["blocking_plus_other_missing"] == "INSUFFICIENT_DATA"
    assert g3["independent_component_veto_added"] is False
    assert g3["pass_confidence_annotation"] == "1.0"
    assert g3["confidence_is_source_completeness_probability"] is g3["numeric_calibration_required"] is False
    temporal = value["gate3_temporal_approval"]
    assert temporal["time_fields_separate"] == ["SOURCE_PUBLICATION", "HSI_FIRST_OBSERVED", "EFFECTIVE_FROM", "EFFECTIVE_TO", "EVALUATION_AS_OF"]
    for key in ("known_at_boundary_inclusive", "effective_applicability_required_independently",
                "execution_session_requires_pit_visible_canonical_calendar",
                "future_filtered_before_revision_or_conflict_selection", "supersession_requires_explicit_visible_official_relation"):
        assert temporal[key] is True
    for key in ("source_publication_or_file_date_backdating", "effective_date_is_local_knowledge",
                "request_start_is_completed_payload_observation", "date_only_invented_clock",
                "unknown_effective_to_is_forever", "unresolved_current_state_falls_back_to_old_clearance",
                "late_observation_rewrites_earlier_decision", "future_ids_in_historical_output",
                "new_surveillance_residual_gap_clearance_accepted"):
        assert temporal[key] is False
    g6 = value["gate6_carry_forward"]
    prior_approval = _read(ROOT / g6["approval_reference"])
    prior_proposal = _read(ROOT / g6["proposal_reference"])
    assert g6["proposal_fingerprint"] == prior_proposal["proposal_fingerprint"] == proposal_tests._digest(prior_proposal)
    assert g6["approval_fingerprint"] == prior_approval["approval_fingerprint"] == content_fingerprint(_unsigned(prior_approval))
    assert g6["semantic_override_fields"] == []
    assert g6["mode"] == "VERIFIED_EVENT_VETO"
    assert g6["mapping"] == prior_proposal["gate6_proposed"]["result_mapping"]
    assert g6["no_veto_not_equivalent_to"] == prior_approval["no_false_clearance"]["no_veto_not_equivalent_to"]
    assert g6["no_veto_metadata"] == {
        "evaluation_mode": "VERIFIED_EVENT_VETO", "earnings_clearance": "UNVERIFIED",
        "confidence": None, "required_warning": "EARNINGS_CLEARANCE_UNVERIFIED",
        "source_warnings_and_coverage_limits_preserved": True,
        "policy_version_fingerprint_as_of_and_receipt_lineage_required": True,
        "missing_metadata_behavior": "REJECT_COMPATIBILITY",
    }
    assert g6["horizon"] == {
        "state": "POLICY_UNSET", "value": None, "unit": None,
        "precision_and_boundaries": None, "calibration_required": True,
        "inherits_v1_five": False, "regulatory_notice_is_risk_window": False,
    }
    assert g6["retroactive_blackout"] is g6["forced_position_action"] is False
    assert value["cross_gate_and_liveness"]["reducer"] == p["result_contract"]["six_gate_precedence"]
    assert value["cross_gate_and_liveness"]["gate3_missing_can_be_erased_by_gate6_no_veto"] is False
    assert value["cross_gate_and_liveness"]["cross_gate_override_voting_or_confidence_averaging"] is False
    assert value["historical_isolation"]["implicit_latest_upgrade"] is False
    assert value["historical_isolation"]["late_state_relabels_earlier_decision"] is False
    assert value["pilot"]["governance_is_execution_readiness"] is False
    assert value["pilot"]["perfect_historical_archives_required_for_prospective_operation"] is False
    _verify_blockers(value, p, prior_approval)


def _verify_blockers(value, proposal, gate6):
    register = value["blocker_register"]
    assert register["operational_closures_asserted"] is False
    assert register["semantic_approval_satisfied_only"] is True
    rows = register["entries"]
    assert [row["id"] for row in rows] == [f"CV2B{i:02d}" for i in range(1, 21)]
    assert len({row["area"] for row in rows}) == len(rows)
    assert [(row["area"], tuple(row["origins"])) for row in rows] == list(BLOCKER_MAP)
    assert [row["classification"] for row in rows] == ["BLOCKING"] * 15 + [
        "DEFERRED_FOR_REPLAY", "DEFERRED_FOR_SHADOW", "DEFERRED_FOR_SHADOW", "NON_BLOCKING", "NON_BLOCKING"]
    for row in rows:
        assert row.keys() == {"id", "area", "origins", "classification", "state", "closure"}
        assert row["state"] == "OPEN" and row["closure"].strip()
        assert len(row["origins"]) == len(set(row["origins"]))
    expected = {"g3:" + x["id"] for x in proposal["activation_blockers"]} | {"g6:" + x["id"] for x in gate6["activation_blockers"]}
    assert {origin for row in rows for origin in row["origins"]} == expected


def test_approval_binds_exact_proposal_without_overwriting_or_activating():
    value = _read()
    _verify(value)
    assert value["baseline_commit"] == "5787f37a45b77ab8fc2ca0227d4c7056dd560bae"
    assert value["authority"] == {
        "basis": "USER_DELEGATED_BOUNDED_GOVERNANCE_REVIEW",
        "directive_id": "3e26e7db-91b3-423e-a597-17fa9ee56ea5",
        "reviewer": "Codex governance reviewer", "human_signature_claimed": False,
    }
    for path, fingerprint in value["reviewed_files_lf"].items():
        assert proposal_tests._lf_digest(path) == fingerprint
    assert proposal_tests._read()["composite_approval"]["approval_reference"] is None
    assert value["next_continuation"] == "GATE3_SURVEILLANCE_PROSPECTIVE_COLLECTOR_V1"
    assert value["next_continuation_started"] is False


@pytest.mark.parametrize("index,method", [(0, "_rotation"), (1, "_velocity"), (3, "_plan"), (4, "_heat")])
def test_independent_definition_method_and_config_proof_for_unchanged_gate(index, method):
    p = proposal_tests._read()
    refs = p["unchanged_gates"]
    ref = next(row for row in refs if row["registry_id"] == index + 1)
    assert ref["definition_fingerprint"] == content_fingerprint(EXECUTION_GATES[index])
    assert ref["implementation_fingerprint"] == gate6_tests._method_fingerprint(method)
    assert _read()["unchanged_gate_proof"]["definition_and_method_set_fingerprint"] == content_fingerprint(refs)
    assert proposal_tests._lf_digest("app/gates/production_policy.py") == p["parent_policy"]["definition_file_fingerprint_lf"]


@pytest.mark.parametrize("path", gate6_tests.SOURCE_PATHS)
def test_original_engine_registry_authority_and_version_guard_are_unchanged(path):
    assert proposal_tests._lf_digest(path) == proposal_tests._read()["frozen_source_fingerprints_lf"][path]


def test_single_successor_no_runtime_import_or_competing_gate_engine():
    p = proposal_tests._read()
    assert p["proposal_id"] == gate6_tests._read()["policy_id"]
    assert p["supersedes_candidate_reference"]["version"] == "v2-proposal.2"
    engine_defs = []
    for path in (ROOT / "app/gates").glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        engine_defs.extend((str(path), node.name) for node in ast.walk(tree)
                           if isinstance(node, ast.ClassDef) and node.name == "ExecutionGateEngine")
    assert len(engine_defs) == 1
    for path in (ROOT / "app").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert "execution-gate-policy-v2-proposed" not in text
        assert "EXECUTION_GATE_POLICY_V2_COMPOSITE_GOVERNANCE_APPROVAL" not in text


def _compose(outcomes):
    """Synthetic declared outcomes through the existing reducer, not gate policies."""
    with ExitStack() as stack:
        for i, (method, outcome) in enumerate(zip(gate6_tests.METHODS, outcomes, strict=True)):
            params = {"evaluation_mode": "VERIFIED_EVENT_VETO", "earnings_clearance": "UNVERIFIED"} if i == 5 else {}
            record = GateDecisionRecord(gate6_tests.GATE_IDS[i], GateOutcome(outcome),
                "SYNTHETIC_COMPOSITE_APPROVAL_ONLY", None if i == 5 or outcome != "PASS" else 1.0,
                (f"synthetic-gate-{i + 1}",), params)
            stack.enter_context(patch.object(ExecutionGateEngine, method, return_value=record))
        return gate6_tests.v1_fixture.evaluate()


@pytest.mark.parametrize("g3", ["PASS", "FAIL", "INSUFFICIENT_DATA"])
@pytest.mark.parametrize("g6", ["PASS", "FAIL", "INSUFFICIENT_DATA"])
def test_all_cross_gate_pairs_keep_independent_results_and_actual_reducer(g3, g6):
    outcomes = ["PASS", "PASS", g3, "PASS", "PASS", g6]
    result = _compose(outcomes)
    expected = "BLOCKED" if "FAIL" in outcomes else ("INSUFFICIENT_DATA" if "INSUFFICIENT_DATA" in outcomes else "EXECUTABLE")
    assert result.eligibility.value == expected
    assert [r.gate_id for r in result.decisions] == _read()["gate_ids"]
    assert [r.outcome.value for r in result.decisions] == outcomes
    assert result.decisions[5].confidence is None
    assert result.decisions[5].parameters["earnings_clearance"] == "UNVERIFIED"
    assert "NO_ACTION_OR_ORDER_CREATED" in result.warnings


@pytest.mark.parametrize("index", [0, 1, 3, 4])
@pytest.mark.parametrize("state", ["FAIL", "INSUFFICIENT_DATA"])
def test_other_gate_failure_or_insufficiency_cannot_be_erased_by_composite_pass(index, state):
    outcomes = ["PASS"] * 6
    outcomes[index] = state
    result = _compose(outcomes)
    assert result.eligibility.value == ("BLOCKED" if state == "FAIL" else "INSUFFICIENT_DATA")
    assert result.decisions[index].outcome.value == state


def test_current_effective_and_late_known_replay_do_not_retroactively_mutate():
    at, day = proposal_tests.AT, proposal_tests.DAY
    old = proposal_tests._Witness("old-current-proof", at - timedelta(hours=1), (day,), 0)
    late = proposal_tests._Witness("late-restriction", at + timedelta(minutes=1), (day,), 2, (old.receipt,))
    before = proposal_tests._witness_payload(proposal_tests._select_witness((old,)))
    historical = proposal_tests._witness_payload(proposal_tests._select_witness((old, late)))
    assert canonical_json(before) == canonical_json(historical)
    assert late.receipt not in canonical_json(historical)
    assert proposal_tests._select_witness((late, old), as_of=late.known) == late
    prior_date = replace(old, sessions=(day - timedelta(days=1),))
    assert proposal_tests._select_witness((prior_date, replace(late, known=at))) == replace(late, known=at)
    assert before["instant_interval"] is None and before["sessions"] == (day.isoformat(),)


def test_v1_history_and_policy_are_not_implicitly_upgraded_by_loading_approval():
    policy = proposal_tests._policy()
    prior = proposal_tests._run(proposal_tests._input().surveillance)
    _verify(_read())
    after = proposal_tests._run(proposal_tests._input().surveillance)
    assert prior == after
    assert prior.gate_configuration_version == policy.policy_id == "six-gates-production-v1"
    assert policy.surveillance_source.latest_eligible_completed_session_required
    assert policy.gate_config.blackout_sessions == 5
    with pytest.raises(ValueError):
        replace(policy, version="v2-proposal.3").verify_integrity()
    assert gate6_tests._method_fingerprint("_surveillance") == proposal_tests._read()["gate3_v1"]["implementation_fingerprint"]
    assert gate6_tests._method_fingerprint("_blackout") == gate6_tests._read()["gate6_v1"]["implementation_fingerprint"]


def test_earnings_no_retroactivity_and_structure_readiness_not_horizon_approval():
    value = _read()
    g6 = value["gate6_carry_forward"]
    old = gate6_tests._read()
    assert old["known_at_basis"]["retroactive_block"] is False
    assert old["hard_block_semantics"]["revisions_effect"] == "OWN_KNOWN_AT_ONWARD_ONLY"
    assert old["hard_block_semantics"]["earlier_legitimate_entry_invalidated"] is False
    assert g6["prospective_state"] == {
        "collector_structure": "READY", "calibration_shadow_structure": "READY",
        "live_positive_event_proof": "PENDING_EVENT", "live_outcome": "PENDING_EVENT",
        "live_event_required_for_this_semantic_approval": False, "live_remeasured_in_this_slice": False,
    }
    assert value["pilot"]["automatic_jobs_started"] is False
    assert value["research_boundary"] == {
        "execution_uncertainty_is_low_quality": False, "execution_uncertainty_is_bearish": False,
        "execution_uncertainty_changes_score": False, "independent_research_continues": True,
    }


def test_all_blockers_reconciled_once_with_explicit_multi_component_criteria():
    value = _read()
    gate6 = _read(ROOT / value["gate6_carry_forward"]["approval_reference"])
    _verify_blockers(value, proposal_tests._read(), gate6)
    entries = {row["id"]: row for row in value["blocker_register"]["entries"]}
    assert entries["CV2B04"]["origins"] == ["g3:G3A04", "g6:B02"]
    assert entries["CV2B07"]["origins"] == ["g3:G3A07", "g6:B04"]
    assert entries["CV2B15"]["origins"] == ["g3:G3A10", "g6:B10"]
    assert entries["CV2B19"]["origins"] == ["g3:G3A12", "g6:B08"]
    for row in value["downstream_impact"]:
        assert set(row["blockers"]) <= entries.keys()
        assert (ROOT / row["reference"]).is_file()
    impacts = {row["consumer"]: row["classifications"] for row in value["downstream_impact"]}
    assert impacts["Gate3 numeric thresholds"] == ["CALIBRATION_NOT_REQUIRED"]
    assert impacts["Gate6 earnings horizon"] == ["CALIBRATION_REQUIRED"]
    assert impacts["Outcome ledger"] == ["ADAPTER_UPDATE_REQUIRED", "CALIBRATION_REQUIRED"]
    assert impacts["Decision Score"] == impacts["TradePlan"] == ["NO_CHANGE"]


def test_approval_deterministic_replay_and_complete_fingerprint_coverage():
    value = _read()
    _verify(value)
    unsigned = _unsigned(value)
    digest = value["approval_fingerprint"]
    assert content_fingerprint(json.loads(canonical_json(unsigned))) == digest
    assert content_fingerprint(dict(reversed(tuple(unsigned.items())))) == digest
    for key in unsigned:
        changed = deepcopy(unsigned)
        del changed[key]
        assert content_fingerprint(changed) != digest
    with pytest.raises(ValueError, match="DUPLICATE_PROPOSAL_KEY"):
        json.loads('{"decision":"A","decision":"C"}', object_pairs_hook=gate6_tests._unique_object)


@pytest.mark.parametrize("mutation", ["activate", "threshold", "status_guard", "veto_first", "retroactive", "horizon", "confidence", "competing_authority", "extra_gate", "closed_blocker", "missing_origin", "duplicate_blocker", "defer_required_blocker", "unknown_key"])
def test_rehashed_unsafe_or_incomplete_approval_is_rejected(mutation):
    value = _read()
    if mutation == "activate": value["activation_status"] = "ACTIVE"
    elif mutation == "threshold": value["gate3_approval"]["blocking_thresholds"]["asm_stage_gte"] = 3
    elif mutation == "status_guard": value["gate3_approval"]["security_status"]["mandatory_pass_field"] = True
    elif mutation == "veto_first": value["gate3_approval"]["blocking_plus_other_missing"] = "FAIL"
    elif mutation == "retroactive": value["gate3_temporal_approval"]["late_observation_rewrites_earlier_decision"] = True
    elif mutation == "horizon": value["gate6_carry_forward"]["horizon"]["value"] = 5
    elif mutation == "confidence": value["gate6_carry_forward"]["no_veto_metadata"]["confidence"] = 1.0
    elif mutation == "competing_authority": value["single_successor"]["independent_gate3_policy_authority"] = True
    elif mutation == "extra_gate": value["gate_ids"].append("GATE_7_STATUS")
    elif mutation == "closed_blocker": value["blocker_register"]["entries"][0]["state"] = "CLOSED"
    elif mutation == "missing_origin": value["blocker_register"]["entries"][3]["origins"].remove("g6:B02")
    elif mutation == "duplicate_blocker": value["blocker_register"]["entries"].append(deepcopy(value["blocker_register"]["entries"][0]))
    elif mutation == "defer_required_blocker": value["blocker_register"]["entries"][14]["classification"] = "DEFERRED_FOR_REPLAY"
    else: value["runtime_activation_hook"] = "unapproved"
    value["approval_fingerprint"] = content_fingerprint(_unsigned(value))
    with pytest.raises(AssertionError):
        _verify(value)
