"""Static approval-artifact proofs only; no V2 evaluator, adapter or activation."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import subprocess

import pytest

from tests.unit.test_fundamental_diagnostic_registry_v2_proposal import (
    CHANGED, ROLES, STATES, canonical, definitions, fingerprint, proposal,
    validate_proposal,
)


ROOT = Path(__file__).resolve().parents[2]
PATH = ROOT / "docs/architecture/FUNDAMENTAL_DIAGNOSTIC_REGISTRY_V2_GOVERNANCE_APPROVAL.json"
RECEIPT = PATH.with_suffix(".md")
BASELINE = "60e8529249961d8eb8fa8a287fd81ea8c0f0bce6"
PROPOSAL_FINGERPRINT = "sha256:668005237acd727ead86b19fca11a0fe9a1f640291dbe647a02cab989774a261"
BLOCKERS = tuple(f"B{number:02}" for number in range(1, 16))
DEFERRED = {"B11": "BANK_BRANCH_ONLY", "B12": "NBFC_BRANCH_ONLY", "B13": "INSURER_BRANCH_ONLY"}
SCORE_STATES = STATES | {
    "READY_STANDARD_BRANCH", "READY_ENTITY_SPECIFIC_BRANCH", "CORE_READY_OPTIONAL_INCOMPLETE",
    "CORE_READY_OPTIONAL_CONFLICTED", "CORE_AND_OPTIONAL_COMPLETE", "NOT_READY", "UNAVAILABLE",
    "UNKNOWN_OR_UNRECOGNIZED",
}


def approval():
    return json.loads(PATH.read_text(encoding="utf-8"))


def unsigned(value):
    return {key: item for key, item in value.items() if key != "approval_fingerprint"}


def validate_approval(value):
    """Reject inconsistent/rehashed policy changes; never repair the artifact."""
    source = proposal()
    validate_proposal(source)
    assert source["proposal_fingerprint"] == PROPOSAL_FINGERPRINT
    assert value["approval_fingerprint"] == fingerprint(unsigned(value))
    assert value["schema_version"] == "hsi-diagnostic-registry-governance-approval/v1"
    assert value["approval_id"] == "fundamental-diagnostic-registry-v2-governance-approval/v1"
    assert value["baseline_commit"] == BASELINE
    reference = value["proposal_reference"]
    assert reference["proposal_fingerprint"] == PROPOSAL_FINGERPRINT
    assert reference["candidate"] == "diagnostic-registry-v2-proposed"
    assert reference["parent"] == "diagnostic-registry-v1"
    assert reference["source_status"] == "PROPOSED"
    assert reference["original_proposal_overwritten"] is False
    assert value["approval_state"] == "GOVERNANCE_APPROVED_WITH_ACTIVATION_BLOCKERS"
    assert value["decision_outcome"] == "B"
    assert value["active"] is value["v2_active"] is False
    assert value["v1_active"] is True
    assert value["runtime_effective_at"] is None
    assert value["runtime_registration_created"] is value["shadow_execution_started"] is False
    scope = value["approval_scope"]
    assert tuple(scope["rule_ids"]) == CHANGED
    assert scope["rule_count"] == 61 and scope["unchanged_rule_count"] == 55
    assert scope["parent_registry_semantic_fingerprint"] == source["parent_registry_semantic_fingerprint"]
    assert scope["semantic_definition_approval"] is True
    assert all(scope[key] is False for key in (
        "implementation_approval", "score_policy_approval", "entity_branch_activation",
        "evidence_contract_implementation",
    ))
    rows = value["rule_decisions"]
    assert tuple(row["rule_id"] for row in rows) == CHANGED
    source_ids = {row["source_id"] for row in value["source_basis"]}
    for row in rows:
        assert row["decision"] == "APPROVE"
        assert row["reason"] and row["conditions"] and row["not_approved"]
        assert set(row["source_basis"]) <= source_ids
        assert {"B01", "B02", "B03", "B04", "B10", "B14", "B15"} <= set(row["activation_blockers"])
        assert set(row["activation_blockers"]) <= set(BLOCKERS)
        assert row["approved_core"] == [
            item["component_id"] for item in definitions(source)[row["rule_id"]]["components"]
            if item["role"] == "MANDATORY_CORE"
        ]
    entity = value["entity_policy_decision"]
    assert entity["matrix"] == source["entity_applicability"]
    assert entity["unknown_behavior"] == "POLICY_BLOCKED"
    assert entity["unknown_default_nonfinancial"] is entity["name_heuristics_allowed"] is False
    contract = value["component_readiness_decision"]
    assert set(contract["component_states"]) == STATES
    assert set(contract["roles"]) == ROLES
    assert contract["canonical_results_per_rule"] == 1
    assert contract["new_scoring_engine"] is contract["weight_renormalization_allowed"] is False
    assert contract["confidence_default"] is None
    assert contract["confidence_separate_from_score"] is True
    for case in contract["rule19_examples"]:
        assert case["full_rule_ready"] is case["score_eligible"] is False
        assert case["economic_verdict"] is None
    safety = value["score_safety"]
    assert safety["UNKNOWN_V2_STATE_MUST_NEVER_DEFAULT_POSITIVE"] is True
    assert safety["NO_V2_RESULT_MAY_BECOME_SUPPORTIVE_BY_UNKNOWN_STATE_FALLTHROUGH"] is True
    assert safety["all_v2_states_require_explicit_mapping"] is True
    assert safety["unknown_contribution"] is None and safety["unknown_eligibility"] is False
    assert safety["unknown_state_policy"] == "FAIL_CLOSED_UNRECOGNIZED_V2_STATE"
    assert safety["required_missing_score_result"] == "SCORE_INCOMPLETE"
    assert safety["implementation_performed"] is False
    dispositions = safety["state_dispositions"]
    assert len(dispositions) == len(SCORE_STATES)
    assert {row["state"] for row in dispositions} == SCORE_STATES
    for row in dispositions:
        assert row["score_eligible"] is row["supportive"] is False
        assert row["contribution"] is None and row["reason"]
    blockers = value["activation_blockers"]
    assert tuple(row["blocker_id"] for row in blockers) == BLOCKERS
    for row in blockers:
        deferred = row["blocker_id"] in DEFERRED
        assert row["classification"] == ("DEFERRED_NOT_REQUIRED_FOR_SHADOW" if deferred else "BLOCKING")
        assert row["resolution"] == "OPEN"
        assert all(row[key] for key in ("topic", "activation_scope", "evidence", "required_proof", "shadow_requirement"))
        if deferred:
            assert row["activation_scope"] == DEFERRED[row["blocker_id"]]
    gate = value["activation_gate"]
    assert gate["active"] is gate["all_blockers_resolved"] is False
    assert gate["open_blocking_count"] == 12 and gate["open_scoped_deferred_count"] == 3
    assert gate["deferred_does_not_mean_resolved"] is True


def test_approval_replays_against_exact_proposal_and_unchanged_61_rule_authority():
    validate_approval(approval())


@pytest.mark.parametrize("rule_id", CHANGED)
def test_each_governance_decision_matches_the_immutable_source_definition(rule_id):
    value = approval()
    decision = next(row for row in value["rule_decisions"] if row["rule_id"] == rule_id)
    source = definitions(proposal())[rule_id]
    assert decision["decision"] == "APPROVE"
    assert source["proposed_name"] in RECEIPT.read_text(encoding="utf-8")
    assert all(condition in RECEIPT.read_text(encoding="utf-8") for condition in decision["conditions"])
    assert set(decision["source_basis"]) <= set(source["sources"])
    if rule_id == 16:
        core = [c for c in source["components"] if c["role"] == "MANDATORY_CORE"]
        assert all(c["minimum_observations"] == 6 and c["fiscal_intervals"] == 5 for c in core)
    if rule_id == 29:
        assert decision["approved_availability"] == source["aggregation"]


def test_rule26_net_profit_wording_cannot_approve_operating_gross_or_ebitda_aliases():
    value = approval()
    decision = next(row for row in value["rule_decisions"] if row["rule_id"] == 26)
    assert decision["approved_core"] == ["NET_PROFIT_MARGIN"]
    for other in ("OPERATING_MARGIN", "GROSS_MARGIN", "EBITDA_MARGIN"):
        assert f"NET_PROFIT_MARGIN as {other}" in decision["not_approved"]
    components = {c["component_id"]: c for c in definitions(proposal())[26]["components"]}
    assert components["NET_PROFIT_MARGIN"]["measurement_definition"].startswith("PAT / revenue;")
    assert "100 * (margin_q - margin_q_minus_4)" in components["NET_PROFIT_MARGIN"]["measurement_definition"]
    assert components["NET_PROFIT_MARGIN"]["minimum_observations"] == 5
    for key in ("OPERATING_MARGIN", "GROSS_MARGIN"):
        assert components[key]["measurement_definition"] is None
        assert components[key]["policy_availability"] == "POLICY_BLOCKED"


def test_rule19_core_is_not_full_readiness_health_or_synthetic_score():
    contract = approval()["component_readiness_decision"]
    assert contract["core_and_coverage_are_separate"] is True
    assert contract["optional_absence_invalidates_complete_core"] is False
    assert contract["blocked_or_conflicted_values_default_zero"] is False
    assert "not production observations" in contract["example_scope"]
    cases = {case["case_id"]: case for case in contract["rule19_examples"]}
    assert cases["de_only"]["core_complete"] is True
    assert cases["de_only"]["coverage_state"] == "CORE_READY_OPTIONAL_INCOMPLETE"
    assert cases["de_optional_conflict"]["coverage_state"] == "CORE_READY_OPTIONAL_CONFLICTED"
    assert cases["de_optional_conflict"]["retained_blockers"] == ["INTEREST_COVERAGE_EVIDENCE_CONFLICTED"]
    assert cases["de_missing_other_ready"]["core_complete"] is False
    assert cases["de_missing_other_ready"]["coverage_state"] == "PARTIAL"
    clarification = contract["approval_clarification"]
    assert clarification["economic_verdict_on_readiness"] is None
    assert clarification["partial_or_na_core_is_complete"] is False


def test_entity_policy_is_conservative_and_no_company_is_reclassified():
    entity = approval()["entity_policy_decision"]
    assert entity["decision"] == "APPROVE"
    assert entity["matrix"] == proposal()["entity_applicability"]
    assert entity["current_unknown_companies_reclassified"] == 0
    assert entity["conflicting_classification_behavior"] == "EVIDENCE_CONFLICTED"
    assert entity["deferred_financial_branches"] == ["BANK", "NBFC", "INSURER"]


@pytest.mark.parametrize("state", sorted(SCORE_STATES))
def test_every_readiness_alias_and_unknown_is_explicitly_non_scoring_non_supportive(state):
    row = next(row for row in approval()["score_safety"]["state_dispositions"] if row["state"] == state)
    assert row["contribution"] is None
    assert row["score_eligible"] is row["supportive"] is False
    assert row["reason"]


def test_legacy_score_default_remains_an_immutable_approval_time_blocker():
    value = approval()
    risk = value["score_safety"]["legacy_risk"]
    source = subprocess.check_output(['git','show',BASELINE+':'+risk['path']],cwd=ROOT,text=True)
    assert risk["expression"] in source and risk["fallback_value"] == "5"
    assert risk['expression'] not in (ROOT/risk['path']).read_text(encoding='utf-8')
    blockers = {row["blocker_id"]: row for row in value["activation_blockers"]}
    for key in ("B03", "B04"):
        assert blockers[key]["classification"] == "BLOCKING"
        assert blockers[key]["resolution"] == "OPEN"
    assert value["score_safety"]["implementation_performed"] is False


def test_all_fifteen_blockers_and_seven_downstream_consumers_are_explicit():
    value = approval()
    validate_approval(value)
    assert set(value["activation_blocker_vocabulary"]) == {
        "BLOCKING", "NON_BLOCKING", "DEFERRED_NOT_REQUIRED_FOR_SHADOW", "NOT_APPLICABLE",
    }
    rows = value["downstream_risks"]
    assert {row["consumer"] for row in rows} == {
        "higher_order_rules", "thesis_synthesis", "decision_score", "six_gates",
        "long_term_shadows", "portfolio_brain", "research_outputs",
    }
    for row in rows:
        assert row["no_supportive_fallthrough"] is True
        assert row["risk"] and set(row["blocker_ids"]) <= set(BLOCKERS)
        assert all((ROOT / path).is_file() for path in row["paths"])


@pytest.mark.parametrize("mutation", [
    "unhashed_tamper", "activation", "missing_rule", "positive_unknown", "supportive_conflict",
    "missing_state", "closed_score_blocker", "missing_blocker", "financial_default", "core_healthy",
])
def test_unsafe_approval_is_rejected_even_when_attacker_recomputes_content_hash(mutation):
    value = deepcopy(approval())
    if mutation == "unhashed_tamper":
        value["rule_decisions"][0]["reason"] += " tampered"
    elif mutation == "activation":
        value["active"] = True
    elif mutation == "missing_rule":
        value["rule_decisions"].pop()
    elif mutation == "positive_unknown":
        row = next(row for row in value["score_safety"]["state_dispositions"] if row["state"] == "UNKNOWN_OR_UNRECOGNIZED")
        row.update(score_eligible=True, contribution="5")
    elif mutation == "supportive_conflict":
        row = next(row for row in value["score_safety"]["state_dispositions"] if row["state"] == "EVIDENCE_CONFLICTED")
        row["supportive"] = True
    elif mutation == "missing_state":
        value["score_safety"]["state_dispositions"].pop()
    elif mutation == "closed_score_blocker":
        value["activation_blockers"][3]["classification"] = "NON_BLOCKING"
    elif mutation == "missing_blocker":
        value["activation_blockers"].pop()
    elif mutation == "financial_default":
        value["entity_policy_decision"]["matrix"][0]["BANK"] = "STANDARD_BRANCH"
    elif mutation == "core_healthy":
        value["component_readiness_decision"]["rule19_examples"][0]["economic_verdict"] = "HEALTHY"
    if mutation != "unhashed_tamper":
        value["approval_fingerprint"] = fingerprint(unsigned(value))
    with pytest.raises(AssertionError):
        validate_approval(value)


def test_approval_roundtrip_and_mapping_order_have_identical_identity():
    first = approval()
    replay = json.loads(canonical(first))
    reverse_keys = dict(reversed(list(replay.items())))
    assert canonical(first) == canonical(replay) == canonical(reverse_keys)
    assert fingerprint(unsigned(first)) == fingerprint(unsigned(reverse_keys)) == first["approval_fingerprint"]
    assert first["approval_fingerprint"] != first["proposal_reference"]["proposal_fingerprint"]
    assert first["fingerprint_scheme"] == "sha256:utf8:canonical-json-v1:exclude-approval_fingerprint"
    validate_approval(replay)


def test_original_proposal_and_active_v1_source_git_bytes_are_preserved():
    pins = approval()["source_preservation_pins"]
    assert len(pins) == 13 and len({pin["path"] for pin in pins}) == 13
    for pin in pins:
        expected = subprocess.check_output(["git", "rev-parse", BASELINE + ":" + pin["path"]], cwd=ROOT, text=True).strip()
        if pin["path"] in {"tests/unit/test_fundamental_diagnostic_registry_v2_proposal.py",
                           "app/scoring/engine.py", "app/diagnostics/synthesis.py"}:
            # Preserve the approval-time test blob in history. Its phase guard
            # now admits the authorized shadow/downstream safety slices only.
            assert expected == pin["git_blob"]
            continue
        actual = subprocess.check_output(["git", "hash-object", pin["path"]], cwd=ROOT, text=True).strip()
        assert expected == actual == pin["git_blob"]
    validate_proposal(proposal())


def test_version_rehydration_horizon_and_non_implemented_contracts_stay_frozen():
    value = approval()
    binding = value["version_rehydration"]
    assert binding["required"] == ["registry_version", "strategy_version", "policy_version", "as_of"]
    assert binding["explicit_fingerprints_required"] is True
    assert binding["v1_results_rehydrate_as"] == "diagnostic-registry-v1"
    assert binding["global_latest_fallback"] is binding["implicit_v2_replay"] is binding["v1_history_mutable"] is False
    horizon = value["horizon_policy"]
    original = json.loads((ROOT / horizon["path"]).read_text(encoding="utf-8"))
    assert horizon["fingerprint"] == original["policy_fingerprint"]
    assert horizon["status"] == original["status"] == "CANDIDATE_NOT_ACTIVE"
    assert horizon["semantics_changed"] is horizon["timeframes_changed"] is horizon["activation_authorized"] is False
    ratio = value["reported_ratio"]
    assert ratio["role"] == "FORMULA_MATCHED_CORROBORATION_ONLY"
    assert ratio["implemented"] is ratio["same_name_implies_equivalence"] is False
    assert ratio["mandatory_core_substitution"] is ratio["dscr_equals_interest_coverage"] is False
    derived = value["derived_operating_earnings"]
    assert derived["status"] == "PLACEHOLDER_ONLY" and derived["formula"] is None
    assert all(derived[key] is False for key in ("is_reported_fact", "is_ebit", "is_ebitda", "active_derived_metric"))


def test_authority_sources_frozen_flags_and_one_unstarted_continuation():
    value = approval()
    authority = value["review_authority"]
    assert authority["authority"] == "USER_DELEGATED_BOUNDED_GOVERNANCE_REVIEW"
    assert authority["policy_id"] == "fundamental-diagnostic-registry-v2-governance-review"
    assert authority["policy_version"] == "v1" and authority["human_signature_claimed"] is False
    original_sources = {row["source_id"]: row for row in proposal()["sources"]}
    for source in value["source_basis"]:
        assert {key: item for key, item in source.items() if key != "reuse"} == original_sources[source["source_id"]]
    assert value["preserved_invariants"] == {
        "ONE_CANONICAL_61_DIAGNOSTIC_REGISTRY": True, "SEPARATE_TECHNICAL_BRAIN": False,
        "V1_ACTIVE": True, "V2_ACTIVE": False, "NO_SILENT_REGISTRY_REWRITE": True,
        "NO_SYNTHETIC_REPORTED_FACTS": True, "UNKNOWN_V2_STATE_MUST_NEVER_DEFAULT_POSITIVE": True,
        "NO_V2_RESULT_MAY_BECOME_SUPPORTIVE_BY_UNKNOWN_STATE_FALLTHROUGH": True,
        "AI_DECISION_AUTHORITY": False, "HSI_DATA_BUILD_VS_BUY_PRINCIPLE_V1": "FROZEN",
        "DATA_BUILD_VS_BUY_AUDIT_V1": "MANDATORY_BEFORE_MATERIAL_FINANCIAL_ACQUISITION",
        "HSI_EFFICIENT_VALIDATION_EXECUTION_POLICY_V1": "ACTIVE",
    }
    assert value["next_continuation"] == "FUNDAMENTAL_DIAGNOSTIC_REGISTRY_V2_SHADOW_IMPLEMENTATION_V1"
    next_scope = value["scope_for_next_shadow"]
    assert next_scope["material_acquisition_required_to_start"] is False
    assert next_scope["next_slice_started"] is next_scope["positive_strategy_or_trading_authority"] is False
    for path in (ROOT / "app").rglob("*.py"):
        if path.relative_to(ROOT).as_posix() in {"app/registry/versioned.py", "app/fundamentals/diagnostic_v2_shadow.py"}:
            continue
        text = path.read_text(encoding="utf-8")
        assert PATH.name not in text and value["approval_id"] not in text
