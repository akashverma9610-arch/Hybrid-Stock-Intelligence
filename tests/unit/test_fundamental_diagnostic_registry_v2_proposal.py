"""Static governance checks; this module implements no diagnostic evaluator."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict
from decimal import Decimal
from hashlib import sha256
import json
from pathlib import Path
import subprocess

import pytest

from app.registry.canonical import DIAGNOSTIC_REGISTRY_VERSION, DIAGNOSTIC_RULES
from app.scoring.engine import COMPONENTS


ROOT = Path(__file__).resolve().parents[2]
PATH = ROOT / "docs/architecture/FUNDAMENTAL_DIAGNOSTIC_REGISTRY_V2_PROPOSED.json"
CHANGED = (16, 17, 19, 25, 26, 29)
BASELINE = "f19f8072792d6cbf54310e359e4306153dc7a6a3"
ENTITIES = ("NON_FINANCIAL", "BANK", "NBFC", "INSURER", "UNKNOWN_NON_COMPARABLE")
STATES = {"READY", "PARTIAL", "INSUFFICIENT_DATA", "POLICY_BLOCKED", "NOT_APPLICABLE", "EVIDENCE_CONFLICTED"}
ROLES = {"MANDATORY_CORE", "OPTIONAL_COMPONENT", "BLOCKING_COMPONENT"}


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)


def fingerprint(value):
    return "sha256:" + sha256(canonical(value).encode("utf-8")).hexdigest()


def proposal():
    return json.loads(PATH.read_text(encoding="utf-8"))


def unsigned(value):
    return {key: item for key, item in value.items() if key != "proposal_fingerprint"}


def validate_proposal(value):
    """Audit the static artifact against frozen authority, never repair it."""
    assert value["status"] == "PROPOSED"
    assert value["activation_authorized"] is False
    assert value["runtime_wiring"] is False
    assert value["parent_commit"] == BASELINE
    assert value["parent_registry_version"] == DIAGNOSTIC_REGISTRY_VERSION == "diagnostic-registry-v1"
    assert value["registry_version_candidate"] == "diagnostic-registry-v2-proposed"
    assert value["proposal_fingerprint"] == fingerprint(unsigned(value))
    rows = value["rules"]
    assert [row["rule_id"] for row in rows] == list(range(1, 62))
    assert tuple(value["changed_rule_ids"]) == CHANGED
    assert value["unchanged_rule_count"] == 55
    assert value["parent_registry_semantic_fingerprint"] == fingerprint([asdict(rule) for rule in DIAGNOSTIC_RULES])
    for row, rule in zip(rows, DIAGNOSTIC_RULES, strict=True):
        assert row["parent_reference"] == f"diagnostic-registry-v1#{rule.rule_id}"
        assert row["parent_definition_fingerprint"] == fingerprint(asdict(rule))
        if rule.rule_id in CHANGED:
            assert row["change"] == "PROPOSED_SEMANTIC_DIFF"
            assert row["definition"]["rule_id"] == rule.rule_id
            assert row["v1_name"] == rule.canonical_name
            assert row["v1_purpose"] == rule.purpose
        else:
            assert row["change"] == "INHERIT_EXACT_PARENT"
            assert set(row) == {"rule_id", "parent_reference", "parent_definition_fingerprint", "change", "canonical_name"}
            assert row["canonical_name"] == rule.canonical_name


def definitions(value):
    return {row["rule_id"]: row["definition"] for row in value["rules"] if "definition" in row}


def test_exact_61_id_and_unchanged_55_parent_authority():
    validate_proposal(proposal())


@pytest.mark.parametrize("mutation", ["duplicate", "missing", "rule62", "unaffected", "v1_name", "activation", "fingerprint"])
def test_invalid_candidate_is_rejected_even_after_rehash_where_applicable(mutation):
    value = deepcopy(proposal())
    if mutation == "duplicate":
        value["rules"][-1] = deepcopy(value["rules"][-2])
    elif mutation == "missing":
        value["rules"].pop()
    elif mutation == "rule62":
        value["rules"][-1]["rule_id"] = 62
    elif mutation == "unaffected":
        value["rules"][0]["canonical_name"] = "Silently rewritten"
    elif mutation == "v1_name":
        value["rules"][15]["v1_name"] = "PBT is EBITDA"
    elif mutation == "activation":
        value["status"] = "ACTIVE"
    if mutation != "fingerprint":
        value["proposal_fingerprint"] = fingerprint(unsigned(value))
    else:
        value["rules"][15]["definition"]["purpose"] += " tampered"
    with pytest.raises(AssertionError):
        validate_proposal(value)


def test_frozen_source_git_bytes_and_semantics_remain_exact():
    for pin in proposal()["parent_source_pins"]:
        expected_blob = subprocess.check_output(
            ["git", "rev-parse", BASELINE + ":" + pin["path"]], cwd=ROOT, text=True,
        ).strip()
        actual_blob = subprocess.check_output(
            ["git", "hash-object", pin["path"]], cwd=ROOT, text=True,
        ).strip()
        assert expected_blob == actual_blob == pin["git_blob"]
    # Git blob bytes are canonical repository bytes; CRLF checkout policy is not a semantic difference.
    validate_proposal(proposal())


def test_six_rule_definition_schema_is_complete_and_all_policies_are_proposals():
    value = proposal()
    required = {"rule_id", "proposed_name", "v1_behavior", "purpose", "mandatory_change", "optional_change",
                "entity_change", "output_change", "reason", "sources", "risk", "components", "aggregation", "formula_note"}
    assert tuple(definitions(value)) == CHANGED
    source_ids = {source["source_id"] for source in value["sources"]}
    names = []
    for definition in definitions(value).values():
        assert required <= definition.keys() <= required | {"alternatives"}
        assert all(definition[key] for key in required)
        assert set(definition["sources"]) <= source_ids
        names.append(definition["proposed_name"])
        components = definition["components"]
        ids = [component["component_id"] for component in components]
        assert ids and len(ids) == len(set(ids))
        for component in components:
            assert component["role"] in ROLES
            assert component["role"] != "BLOCKING_COMPONENT"
            assert component["required_inputs"] and component["period_contract"]
            assert component["policy_availability"] in {"PROPOSED_ONLY", "POLICY_BLOCKED", "FUTURE_CONTRACT_REQUIRED"}
            if component["measurement_definition"] is None:
                assert component["policy_availability"] == "POLICY_BLOCKED"
    assert len(set(names)) == 6


def test_entity_matrix_is_exact_and_no_unknown_or_unapproved_branch_becomes_applicable():
    value = proposal()
    assert tuple(value["entity_classes"]) == ENTITIES
    matrix = value["entity_applicability"]
    assert tuple(row["rule_id"] for row in matrix) == CHANGED
    for row in matrix:
        assert set(row) == {"rule_id", *ENTITIES}
        assert row["NON_FINANCIAL"] == "STANDARD_BRANCH"
        assert all(row[entity] == "POLICY_BLOCKED" for entity in ENTITIES[1:])
        assert set(row.values()) - {row["rule_id"]} <= set(value["entity_cell_states"])
    assert value["entity_policy"]["name_heuristics_allowed"] is False
    assert value["entity_policy"]["absence_from_regulator_list_proves_nonfinancial"] is False
    assert value["entity_policy"]["classify_existing_unknowns"] is False


def test_component_contract_has_exact_states_roles_and_unavailable_confidence():
    contract = proposal()["component_contract"]
    assert tuple(contract["scope_rule_ids"]) == CHANGED
    assert tuple(proposal()["temporal_and_comparability_contract"]["scope_rule_ids"]) == CHANGED
    assert set(contract["states"]) == STATES
    assert set(contract["roles"]) == ROLES
    assert contract["implemented"] is False
    assert contract["confidence"]["default"] is None
    assert contract["confidence"]["synthetic_values_allowed"] is False
    assert {"evidence_ids", "evidence_fingerprints", "policy_version", "policy_fingerprint", "as_of", "reason_codes"} <= set(contract["fields"])
    assert contract["rule29_aliases"]["NOT_READY"] == ["INSUFFICIENT_DATA", "EVIDENCE_CONFLICTED"]
    assert contract["rule25_roles"]["CORE_REQUIRED"] == "MANDATORY_CORE"


@pytest.mark.parametrize("case", proposal()["component_contract"]["example_cases"], ids=lambda case: case["case_id"])
def test_readiness_examples_do_not_forgive_mandatory_inputs_or_grant_score_eligibility(case):
    # These are consistency assertions over proposal examples, not a production state resolver.
    assert set(case["mandatory"] + case["optional"]) <= STATES
    if case.get("aggregation") == "AT_LEAST_ONE_READY_APPLICABLE_COMPONENT":
        assert case["core_complete"] == ("READY" in case["optional"])
    else:
        assert case["mandatory"]
        assert case["core_complete"] == all(state == "READY" for state in case["mandatory"])
    assert case["semantic_scoring_eligible"] is False
    if case["case_id"] == "core_ready_optional_conflicted":
        assert case["retained_blockers"] == ["OPTIONAL_EVIDENCE_CONFLICTED"]
        assert case["full_component_coverage"] is False


def test_rule16_keeps_six_observations_and_five_intervals_for_each_core_cagr():
    definition = definitions(proposal())[16]
    core = [item for item in definition["components"] if item["role"] == "MANDATORY_CORE"]
    assert [item["component_id"] for item in core] == ["REVENUE_CAGR", "PAT_CAGR", "EPS_BASIC_CAGR"]
    assert all(item["minimum_observations"] == 6 and item["fiscal_intervals"] == 5 for item in core)
    assert all("(1/5)" in item["measurement_definition"] for item in core)
    assert all(item["role"] == "OPTIONAL_COMPONENT" for item in definition["components"] if "EBITDA" in item["component_id"])


def test_rule17_19_25_26_29_minimal_component_and_non_alias_boundaries():
    values = definitions(proposal())
    mandatory = lambda rule: [item["component_id"] for item in values[rule]["components"] if item["role"] == "MANDATORY_CORE"]
    assert mandatory(17) == ["ROE"]
    assert mandatory(19) == ["DEBT_EQUITY"]
    assert mandatory(25) == ["REVENUE_YOY_QOQ", "PAT_YOY_QOQ", "EPS_BASIC_YOY_QOQ"]
    assert mandatory(26) == ["NET_PROFIT_MARGIN"]
    assert mandatory(29) == []
    assert values[29]["aggregation"] == "AT_LEAST_ONE_READY_APPLICABLE_COMPONENT"
    assert {item["component_id"] for item in values[29]["components"]} == {"PE", "PB", "EV_EBITDA", "FORWARD_PE", "PEG"}
    margins = {item["component_id"]: item for item in values[26]["components"]}
    assert margins["NET_PROFIT_MARGIN"]["policy_availability"] == "PROPOSED_ONLY"
    assert margins["OPERATING_MARGIN"]["measurement_definition"] is None
    assert margins["GROSS_MARGIN"]["measurement_definition"] is None


def test_ratio_and_derived_metric_contracts_remain_non_active_and_distinct():
    value = proposal()
    assert value["reported_ratio"]["mandatory_core_eligible"] is False
    assert value["reported_ratio"]["dscr_is_interest_coverage"] is False
    assert value["derived_metric"]["formula"] is None
    assert value["derived_metric"]["reported_ebitda_alias"] is False
    assert value["derived_metric"]["reported_ebit_alias"] is False
    assert {"numerator_definition", "denominator_definition", "formula_fingerprint", "pit_visibility", "revision_lineage"} <= set(value["reported_ratio"]["required_fields"])


def test_proposal_replay_roundtrip_and_mapping_order_are_stable():
    first = proposal()
    second = json.loads(canonical(first))
    reverse_keys = dict(reversed(list(second.items())))
    assert canonical(first) == canonical(second) == canonical(reverse_keys)
    assert fingerprint(unsigned(first)) == fingerprint(unsigned(reverse_keys)) == first["proposal_fingerprint"]
    validate_proposal(second)


def test_downstream_inventory_paths_symbols_and_score_dependencies_match_repository():
    value = proposal()
    inventory = {row["consumer_id"]: row for row in value["downstream_impact"]}
    assert set(inventory) == {"financial_intake_and_evaluators", "canonical_execution_and_rehydration", "decision_score",
                             "higher_order_thesis", "shared_brain_portfolio", "six_gates", "long_term_shadows", "raw_evidence_stores"}
    allowed = {"NO_IMPACT", "SEMANTIC_REVIEW_REQUIRED", "IMPLEMENTATION_UPDATE_REQUIRED", "CALIBRATION_REQUIRED"}
    for row in inventory.values():
        assert set(row["classifications"]) <= allowed
        assert set(row["affected_rule_ids"]) <= set(CHANGED)
        sources = [(ROOT / path).read_text(encoding="utf-8") for path in row["paths"]]
        assert all(any(symbol in source for source in sources) for symbol in row["symbols"])
    score = {item.component_id: item for item in COMPONENTS}
    assert score["earnings_acceleration"].mandatory == (24,)
    assert set(CHANGED) & set(score["earnings_acceleration"].optional) == {16, 25, 26}
    assert score["valuation_risk_reward"].mandatory == (29, 45)
    assert score["earnings_acceleration"].weight == Decimal(".15")
    assert score["valuation_risk_reward"].weight == Decimal(".10")
    assert "CALIBRATION_REQUIRED" in inventory["six_gates"]["classifications"]


def test_horizon_policy_rows_and_fingerprint_remain_unchanged():
    impact = proposal()["horizon_impact"]
    horizon = json.loads((ROOT / impact["path"]).read_text(encoding="utf-8"))
    assert impact["source_status"] == horizon["status"] == "CANDIDATE_NOT_ACTIVE"
    assert impact["fingerprint"] == horizon["policy_fingerprint"]
    assert impact["rule_rows"] == [row for row in horizon["rule_horizon_rows"] if row["rule_id"] in CHANGED]
    assert impact["timeframes"] == horizon["timeframes"]
    assert impact["new_horizons"] == []
    assert impact["future_policy_version_required"] is True


def test_source_references_execution_binding_and_no_runtime_artifact_loading():
    value = proposal()
    for source in value["sources"]:
        if "path" in source:
            assert (ROOT / source["path"]).is_file()
        else:
            assert source["url"].startswith("https://")
    binding = value["execution_binding"]
    assert binding["required"] == ["registry_version", "strategy_version", "policy_version", "as_of"]
    assert binding["active_versions_per_execution"] == 1
    assert binding["implicit_current_registry"] is False
    assert binding["v2_strategy_binding"] == "NOT_CREATED"
    assert value["next_continuation"] == "FUNDAMENTAL_DIAGNOSTIC_REGISTRY_V2_GOVERNANCE_APPROVAL"
    assert value["data_build_vs_buy"]["acquisition_authorized"] is False
    for path in (ROOT / "app").rglob("*.py"):
        # The subsequent approved shadow slice may load the pinned artifact;
        # all existing active callers must still be free of V2 wiring.
        if path.relative_to(ROOT).as_posix() in {"app/registry/versioned.py", "app/fundamentals/diagnostic_v2_shadow.py"}:
            continue
        source = path.read_text(encoding="utf-8")
        assert PATH.name not in source
        assert "diagnostic-registry-v2-proposed" not in source
