"""Static governance proofs; no V2 schedule evaluator or runtime registration."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

from app.fundamentals.diagnostic_comparability import canonical_json, content_fingerprint
from app.gates.engine import ExecutionEligibility, ExecutionGateEngine, GateOutcome
from tests.unit.test_earnings_blackout_policy_v2_proposal import (
    GATE_IDS, _compose_declared_outcome, _read as read_proposal, _unique_object,
    v1_fixture,
)


ROOT = Path(__file__).resolve().parents[2]
ARTIFACT = ROOT / "docs/architecture/EARNINGS_BLACKOUT_POLICY_V2_GOVERNANCE_APPROVAL.json"
BASELINE = "3b6194cadf9ff1e300f7272b8991d7b4e1525d78"
PROPOSAL_FP = "sha256:36c80f2ea561a4411b252e6b4749f9c73275d6e434b257e89bdeb24d83de0e21"
BOUNDARIES = {
    "V1_ACTIVE": True, "GATE_POLICY_V2_ACTIVE": False, "SIX_GATES_EXACTLY_SIX": True,
    "NO_UNVERIFIED_CALENDAR_CLEARANCE": True, "NO_RETROACTIVE_BLACKOUT": True,
    "NO_AI_PREDICTED_EARNINGS_DATE": True, "PILOT_SIMPLICITY_RULE": "ACTIVE",
    "AI_DECISION_AUTHORITY": False,
}
BLOCKER_AREAS = (
    "EVENT_RISK_HORIZON_CALIBRATION", "TRUSTED_SCHEDULE_PRODUCER",
    "SOURCE_STATE_INTERPRETATION", "RUNTIME_V2_GATE6_ADAPTER",
    "PASS_CONFIDENCE_SEMANTIC_GUARD", "EXECUTION_METADATA_PROPAGATION",
    "SIGNAL_ENTRY_READY_COMPATIBILITY", "OPTIONAL_ALERT_COMPATIBILITY",
    "OUTCOME_CALIBRATION_COMPATIBILITY", "HISTORICAL_POLICY_VERSION_ISOLATION",
    "COMPLETE_HISTORICAL_ARCHIVE_OUTCOMES", "AUTHORITATIVE_NEGATIVE_CLEARANCE",
    "OPTIONAL_RESULTS_SEASON_CONTEXT",
)
TOP_KEYS = set("""
schema_version approval_id baseline_commit authority decision approval_status scope
runtime_effective_at runtime_implementation_authorized runtime_registration_created
proposal_reference proposal_files_lf gate_ids liveness no_false_clearance veto
undetermined source_gaps residual_risk horizon soft_context holdings_and_lifecycle
replay presentation pilot downstream_impact activation_blockers calibration_requirements
calibration_parameters_approved reuse boundaries next_continuation next_continuation_started
fingerprint_scheme approval_fingerprint
""".split())


def read_approval():
    return json.loads(ARTIFACT.read_text(encoding="utf-8"), object_pairs_hook=_unique_object)


def unsigned(value):
    return {key: item for key, item in value.items() if key != "approval_fingerprint"}


def validate_approval(value):
    """Test-only semantic validation; rehashing cannot approve altered safety values."""
    source = read_proposal()
    assert source["proposal_fingerprint"] == PROPOSAL_FP
    assert content_fingerprint({k: v for k, v in source.items() if k != "proposal_fingerprint"}) == PROPOSAL_FP
    assert set(value) == TOP_KEYS
    assert value["approval_fingerprint"] == content_fingerprint(unsigned(value))
    assert value["schema_version"] == "earnings-blackout-policy-governance-approval/v1"
    assert value["approval_id"] == "earnings-blackout-policy-v2-governance-approval/v1"
    assert value["baseline_commit"] == BASELINE
    assert value["authority"] == {
        "basis": "USER_DELEGATED_BOUNDED_GOVERNANCE_REVIEW",
        "directive_id": "f0107207-5d2f-4a01-8dd8-d82dbf07f4d9",
        "reviewer": "Codex governance reviewer", "human_signature_claimed": False,
    }
    assert value["decision"] == "A"
    assert value["approval_status"] == "GOVERNANCE_APPROVED_WITH_ACTIVATION_BLOCKERS"
    assert value["scope"] == "SEMANTICS_AND_EXPLICIT_RESIDUAL_RISK_ONLY"
    assert value["runtime_effective_at"] is None
    assert value["runtime_implementation_authorized"] is value["runtime_registration_created"] is False
    assert value["proposal_reference"] == {
        "policy_id": source["policy_id"], "policy_version": source["policy_version_candidate"],
        "proposal_fingerprint": PROPOSAL_FP, "parent_policy_id": source["parent_policy_version"],
        "parent_version": source["parent_version"], "source_status": "PROPOSED",
        "original_proposal_overwritten": False,
    }
    assert value["gate_ids"] == source["gate_ids"] == GATE_IDS
    live = value["liveness"]
    assert live == {
        "decision": "FUTURE_COMPOSITION_PATH_PROVEN",
        "mapping": source["gate6_proposed"]["result_mapping"],
        "witness_preconditions": ["APPROVED_EFFECTIVE_MODE_AND_HORIZON",
            "VALID_REQUEST_AND_TRUSTED_PRODUCER_OBSERVATION",
            "NO_PROVEN_VETO_OR_RETAINED_UNRESOLVED_EVENT", "GATES_1_TO_5_PASS"],
        "witness_eligibility": "EXECUTABLE", "complete_entry_ready_proven": False,
        "current_v2_entry_path_active": False, "generic_insufficient_data_bypass_allowed": False,
    }
    assert value["no_false_clearance"] == {
        "decision": "REQUIRED_VERSIONED_NON_CLEARANCE",
        "no_veto_not_equivalent_to": ["CLEAR", "SAFE", "NO_EARNINGS_SOON", "AUTHORITATIVE_NEGATIVE_EVIDENCE"],
        "earnings_clearance": "UNVERIFIED",
        "required_no_veto_metadata": ["evaluation_mode", "earnings_clearance", "confidence",
            "source_warnings", "coverage_limitations", "policy_id", "policy_version",
            "policy_fingerprint", "source_receipt_lineage", "evaluation_as_of"],
        "evaluation_mode": "VERIFIED_EVENT_VETO", "confidence": None,
        "required_warning": "EARNINGS_CLEARANCE_UNVERIFIED", "source_warnings_suppressible": False,
        "missing_metadata_behavior": "REJECT_COMPATIBILITY", "pass_means_source_completeness": False,
        "pass_means_calendar_confidence_one": False,
    }
    assert value["veto"] == {
        "decision": "APPROVED_CONJUNCTION_ONLY_NOT_OPERATIONAL",
        "all_required": source["required_schedule_evidence"],
        "visibility": "known_at <= evaluation_as_of", "global_policy_and_producer_admission_required": True,
        "query_failure_erases_independent_valid_veto": False, "conflicted_event_can_prove_own_veto": False,
    }
    assert value["undetermined"] == {
        "required_cases": ["PRODUCER_RECEIPT_MISSING", "INVALID_PROVENANCE", "RETAINED_EVENT_UNRESOLVED",
            "SOURCE_STATE_CONFLICT", "MALFORMED_EVIDENCE", "VERSION_MISMATCH"],
        "global_invalid_admission": "REJECT_EVALUATION_OR_UNDETERMINED_NEVER_ELIGIBLE",
        "local_unresolved_without_independent_veto": "UNDETERMINED",
        "conflict_can_be_treated_as_source_gap": False, "existing_proposal_admission_reasons_preserved": True,
        "precedence": source["state_machine"]["precedence"],
    }
    assert value["source_gaps"] == {
        "trusted_observation_required": True,
        "no_veto_without_retained_event_may_include": ["PARTIAL", "UNPROVEN", "STALE", "OBSERVED_QUERY_FAILURE"],
        "missing_receipt_is_observed_failure": False, "unresolved_retained_event_allows_no_veto": False,
        "future_identity_in_historical_warning_allowed": False, "canonical_source_states_preserved": True,
    }
    assert value["residual_risk"] == {
        "id": "VERIFIED_EVENT_VETO_RESIDUAL_SOURCE_RISK", "version": "v1",
        "decision": "ACCEPTED_FOR_CONDITIONAL_SEMANTICS_NOT_RUNTIME_ACTIVATION",
        "description": "An official earnings event may exist but remain unobserved or unverified until later; no-veto composition accepts this exposure without negative clearance.",
        "must_be_visible_and_versioned": True, "confidence_one_or_safety_claim_allowed": False,
    }
    assert value["horizon"] == {
        "state": "POLICY_UNSET", "value": None, "unit": None, "precision_and_boundaries": None,
        "calibration_status": "CALIBRATION_REQUIRED", "inherits_v1_five": False,
        "regulatory_notice_is_risk_window": False, "b14": "OPEN", "b09": "SEPARATE_RULE_HORIZON_POLICY",
    }
    assert value["soft_context"] == {
        "id": "RESULTS_SEASON_RISK_CONTEXT", "activation": "NOT_ACTIVE",
        "boundaries": ["NON_GATE", "NON_SCORING", "NON_EXECUTABLE", "NON_SIZING", "NON_ACTIONABLE"],
        "future_uses": ["RESEARCH_EXPLANATION", "UI_CONTEXT", "QUALITATIVE_CONFIDENCE_DISCUSSION"],
        "numerical_confidence_adjustment_allowed": False, "new_brain_or_diagnostic_allowed": False,
    }
    holdings = value["holdings_and_lifecycle"]
    assert holdings == {
        "entry_scope": source["gate6_proposed"]["entry_contexts"],
        "management_exemptions": source["gate6_proposed"]["management_exemptions"],
        "input_contexts_not_action_outputs": True, "forced_sell_or_exit": False,
        "retroactive_violation": False, "new_add_authority_created": False,
        "revision_reschedule_cancellation_effect": "OWN_KNOWN_AT_ONWARD_ONLY",
        "cancellation": "REMOVE_LINKED_VETO_ONLY_NOT_GLOBAL_CLEARANCE",
        "lifecycle_selection": "LOCAL_VISIBILITY_PER_REVISION_BEFORE_EFFECTIVE_LIFECYCLE",
        "duplicate_headline_creates_event": False,
    }
    assert value["replay"] == source["replay"]
    assert value["presentation"] == {
        "event": ["VERIFIED", "NOT VERIFIED"], "clearance": "UNVERIFIED",
        "veto": ["ACTIVE", "NO VERIFIED VETO", "UNDETERMINED"],
        "verified_outside_window_event_remains_verified": True,
        "forbidden": ["Earnings Safe", "No Earnings Soon", "Calendar Clear"], "ui_implemented": False,
    }
    assert value["pilot"] == {
        "scope": "FUTURE_25_TO_30_USER_PILOT",
        "requires_governed_runtime_horizon_and_all_applicable_blockers_closed": True,
        "verified_veto_blocks_fresh_entry": True, "admitted_no_veto_can_continue_composition": True,
        "clearance_remains_unverified": True, "research_continues_regardless": True,
        "complete_historical_calendar_is_research_prerequisite": False,
        "commercial_readiness_claim": False, "started": False,
    }
    assert value["downstream_impact"] == {row["consumer"]: row["classification"] for row in source["downstream_impact"]}
    blockers = value["activation_blockers"]
    assert [row["id"] for row in blockers] == [f"B{i:02}" for i in range(1, 14)]
    assert tuple(row["area"] for row in blockers) == BLOCKER_AREAS
    origins = ("A1", "A2", "A3", "A4", "A5", "A5", "A5", "A6", "A7", "A8", "A9", "A10", "A11")
    for number, (row, origin) in enumerate(zip(blockers, origins), 1):
        assert set(row) == {"id", "area", "proposal_refs", "classification", "state", "closure"}
        expected = "NON_BLOCKING" if number in (8, 13) else "DEFERRED_FOR_SHADOW" if number in (11, 12) else "BLOCKING"
        assert row["classification"] == expected and row["state"] == "OPEN"
        assert row["proposal_refs"] == [origin]
        assert isinstance(row["closure"], str) and row["closure"].strip()
    assert value["calibration_requirements"] == source["calibration_requirements"] + [
        "RESCHEDULE_FREQUENCY", "UNOBSERVED_EVENT_MISS_RATE_WHERE_MEASURABLE",
    ]
    assert value["calibration_parameters_approved"] is False
    assert value["reuse"] == source["reuse"] | {
        "schedule_lifecycle": "app/filings/earnings_schedule_store.py",
        "canonical_reducer": "app/gates/engine.py#ExecutionGateEngine",
        "provenance_authority": "app/gates/source_authority.py", "policy_selection": "app/gates/production_policy.py",
    }
    assert value["boundaries"] == BOUNDARIES
    assert value["next_continuation"] == "EARNINGS_BLACKOUT_HORIZON_CALIBRATION_CONTRACT_V1"
    assert value["next_continuation_started"] is False
    assert value["fingerprint_scheme"] == "sha256:utf8:canonical-json-v1:exclude-approval_fingerprint"


def test_approval_semantics_blockers_risk_and_frozen_boundaries():
    validate_approval(read_approval())


def test_original_proposal_and_runtime_source_pins_are_unchanged():
    pins = read_approval()["proposal_files_lf"]
    assert set(pins) == {
        "docs/architecture/EARNINGS_BLACKOUT_POLICY_V2_PROPOSAL.json",
        "docs/architecture/EARNINGS_BLACKOUT_POLICY_V2_PROPOSAL.md",
        "tests/unit/test_earnings_blackout_policy_v2_proposal.py",
    }
    for path, expected in (pins | read_proposal()["source_fingerprints_lf"]).items():
        assert "sha256:" + hashlib.sha256((ROOT / path).read_bytes().replace(b"\r\n", b"\n")).hexdigest() == expected


@pytest.mark.parametrize(("state", "eligibility"), [
    ("NO_VETO_ESTABLISHED", "EXECUTABLE"), ("VETO", "BLOCKED"), ("UNDETERMINED", "INSUFFICIENT_DATA"),
])
def test_approved_mapping_uses_actual_reducer_not_a_second_evaluator(state, eligibility):
    result = _compose_declared_outcome(read_approval()["liveness"]["mapping"][state])
    assert [item.gate_id for item in result.decisions] == GATE_IDS
    assert all(item.outcome is GateOutcome.PASS for item in result.decisions[:5])
    assert result.eligibility is ExecutionEligibility(eligibility)
    assert result.decisions[-1].confidence is None
    assert result.decisions[-1].parameters["earnings_clearance"] == "UNVERIFIED"
    assert "NO_ACTION_OR_ORDER_CREATED" in result.warnings


def test_current_pass_confidence_hazard_is_unfixed_and_separately_blocking():
    assert ExecutionGateEngine(v1_fixture.CONFIG, v1_fixture.CALENDAR)._decision(
        GATE_IDS[-1], GateOutcome.PASS, "unchanged V1 helper",
    ).confidence == 1.0
    rows = read_approval()["activation_blockers"]
    assert rows[4]["area"] == "PASS_CONFIDENCE_SEMANTIC_GUARD"
    assert rows[5]["area"] == "EXECUTION_METADATA_PROPAGATION"
    assert all(row["classification"] == "BLOCKING" and row["state"] == "OPEN" for row in rows[4:7])


@pytest.mark.parametrize(("section", "field", "replacement"), [
    ("no_false_clearance", "confidence", 1.0),
    ("no_false_clearance", "earnings_clearance", "CLEAR"),
    ("no_false_clearance", "source_warnings_suppressible", True),
    ("no_false_clearance", "required_no_veto_metadata", []),
    ("no_false_clearance", "missing_metadata_behavior", "PASS"),
    ("undetermined", "required_cases", []),
    ("undetermined", "conflict_can_be_treated_as_source_gap", True),
    ("source_gaps", "missing_receipt_is_observed_failure", True),
    ("source_gaps", "unresolved_retained_event_allows_no_veto", True),
    ("veto", "query_failure_erases_independent_valid_veto", True),
    ("veto", "all_required", []),
    ("horizon", "value", 2),
    ("horizon", "inherits_v1_five", True),
    ("residual_risk", "must_be_visible_and_versioned", False),
    ("liveness", "mapping", {"VETO": "FAIL", "NO_VETO_ESTABLISHED": "INSUFFICIENT_DATA", "UNDETERMINED": "PASS"}),
    ("liveness", "complete_entry_ready_proven", True),
    ("boundaries", "GATE_POLICY_V2_ACTIVE", True),
    ("holdings_and_lifecycle", "retroactive_violation", True),
    ("pilot", "started", True),
    ("replay", "implicit_latest_policy", True),
])
def test_rehashed_unsafe_semantics_are_rejected(section, field, replacement):
    value = deepcopy(read_approval())
    value[section][field] = replacement
    value["approval_fingerprint"] = content_fingerprint(unsigned(value))
    with pytest.raises(AssertionError):
        validate_approval(value)


@pytest.mark.parametrize("mutation", ["missing", "duplicate", "closed", "nonblocking"])
def test_blocker_omission_duplicate_or_false_closure_is_rejected(mutation):
    value = read_approval()
    rows = value["activation_blockers"]
    if mutation == "missing":
        rows.pop(4)
    elif mutation == "duplicate":
        rows.append(deepcopy(rows[4]))
    elif mutation == "closed":
        rows[4]["state"] = "CLOSED"
    else:
        rows[4]["classification"] = "NON_BLOCKING"
    value["approval_fingerprint"] = content_fingerprint(unsigned(value))
    with pytest.raises(AssertionError):
        validate_approval(value)


def test_approval_roundtrip_and_fingerprint_cover_every_field():
    value = read_approval()
    replay = json.loads(canonical_json(value), object_pairs_hook=_unique_object)
    validate_approval(replay)
    assert replay == value
    body = unsigned(value)
    assert content_fingerprint(dict(reversed(list(body.items())))) == value["approval_fingerprint"]
    for key in body:
        changed = deepcopy(body)
        del changed[key]
        assert content_fingerprint(changed) != value["approval_fingerprint"]
    changed = deepcopy(body)
    changed["activation_blockers"].reverse()
    assert content_fingerprint(changed) != value["approval_fingerprint"]
    value["horizon"]["value"] = 5  # Integrity failure even without a rehash.
    with pytest.raises(AssertionError):
        validate_approval(value)


def test_duplicate_json_keys_and_unapproved_top_level_fields_are_rejected():
    with pytest.raises(ValueError):
        json.loads('{"approval_status":"A","approval_status":"ACTIVE"}', object_pairs_hook=_unique_object)
    value = read_approval()
    value["runtime_authority"] = "invented"
    value["approval_fingerprint"] = content_fingerprint(unsigned(value))
    with pytest.raises(AssertionError):
        validate_approval(value)


def test_reuse_paths_exist_and_no_application_imports_the_approval():
    for ref in read_approval()["reuse"].values():
        assert (ROOT / ref.split("#")[0]).is_file()
    for path in (ROOT / "app").rglob("*.py"):
        assert "EARNINGS_BLACKOUT_POLICY_V2_GOVERNANCE_APPROVAL" not in path.read_text(encoding="utf-8")
    receipt = ARTIFACT.with_suffix(".md").read_text(encoding="utf-8")
    for token in (PROPOSAL_FP, "GOVERNANCE_APPROVED_WITH_ACTIVATION_BLOCKERS",
                  "VERIFIED_EVENT_VETO_RESIDUAL_SOURCE_RISK", "EARNINGS_BLACKOUT_HORIZON_CALIBRATION_CONTRACT_V1"):
        assert token in receipt
