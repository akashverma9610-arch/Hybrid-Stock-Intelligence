"""Static .4 approval and synthetic algebra/reducer witnesses, never a producer."""
from copy import deepcopy
from datetime import timedelta, timezone
from decimal import Decimal
from hashlib import sha256
import json
from pathlib import Path
import subprocess

import pytest

from app.fundamentals.diagnostic_comparability import canonical_json, content_fingerprint
from tests.unit import test_gate1_rotation_policy_v2_proposal as proposal
from tests.unit import test_execution_gate_policy_v2_composite_governance_approval as previous


ROOT = Path(__file__).resolve().parents[2]
PATH = ROOT / "docs/architecture/EXECUTION_GATE_POLICY_V2_COMPOSITE_GOVERNANCE_APPROVAL_2.json"
BASELINE = "c3eb2caa15b7d3e2aecf74c41f8706e9d6c3a479"
APPROVAL_FP = "sha256:4e93795ab75b9eac7dc05aca853e63008252765ca21a5d30b5dc160c54334c9e"
TOP_KEYS = set("""schema_version approval_id baseline_commit authority decision approval_status
scope activation_status runtime_effective_at proposal_reference single_successor gate_ids
semantic_bindings unchanged_gate_proof gate1_approval gate3_decision gate6_decision liveness
calibration historical_isolation pilot blocker_register accepted_subproofs downstream_impact
architecture boundaries runtime reviewed_files_lf fingerprint_scheme next_continuation
next_continuation_started approval_fingerprint""".split())
ORIGIN_GROUPS = (
    ("composite3:CV2B01",), ("composite3:CV2B02",), ("composite3:CV2B03",),
    ("composite3:CV2B04", "gate1:G1B10"), ("composite3:CV2B05",),
    ("composite3:CV2B06",), ("composite3:CV2B07", "gate1:G1B11"),
    ("composite3:CV2B08",), ("composite3:CV2B09",), ("composite3:CV2B10",),
    ("composite3:CV2B11", "composite3:CV2B12", "gate1:G1B12"),
    ("composite3:CV2B13", "gate1:G1B15"), ("composite3:CV2B14", "gate1:G1B14"),
    ("composite3:CV2B15", "gate1:G1B13"), ("composite3:CV2B16",),
    ("composite3:CV2B17", "gate1:G1B17"), ("composite3:CV2B18",),
    ("composite3:CV2B19", "gate1:G1B18"), ("composite3:CV2B20",),
) + tuple((f"gate1:G1B{i:02}",) for i in range(1, 10)) + (("gate1:G1B16",),)
G1_FALSE = """portfolio_NAV_or_cash_or_benchmark_substitution partial_pro_rata_full_position_shortcut
costs_deducted_from_deployment_and_again_from_gross funding_assumed_available
gate6_horizon_is_rotation_horizon scenario_model_approved tax_netting_or_credit_default
tax_user_number_is_authority slippage_zero_OHLC_AI_or_manual_default
separate_spread_impact_liquidity_term probability_required score_money_probability_conversion
authority_registered self_hash_or_user_AI_economics_are_authority
future_realized_values_or_later_portfolio_state tradeplan_pass_prerequisite
tradeplan_target_is_terminal_value challenger_clearance_feedback""".split()
G1_TRUE = """non_rotation_scope_unchanged same_parcel_capital_cutoff_horizon_required
cost_exclusive_endpoints_and_disjoint_friction_required common_horizon_required
tax_mandatory tax_selected_lot_lineage_required slippage_mandatory
authority_role_conceptually_approved independent_reproduction_and_admission_required
future_filtered_before_conflict_or_revision no_execution_authority""".split()


def _read():
    return proposal._read(PATH)


def _digest(value):
    return content_fingerprint({k: v for k, v in value.items() if k != "approval_fingerprint"})


def _verify(value):
    """Test-only semantic guard. A recomputed hash alone cannot grant approval."""
    p, old = proposal._read(), previous._read()
    proposal._verify(p)  # Independently verifies .3/.2 full and component chains.
    assert value.keys() == TOP_KEYS
    assert value["approval_fingerprint"] == _digest(value)
    assert value["schema_version"] == "execution-gate-composite-governance-approval/v2"
    assert value["approval_id"] == "execution-gate-policy-v2-composite-governance-approval/2"
    assert value["baseline_commit"] == BASELINE
    assert value["decision"] == "A"
    assert value["approval_status"] == "COMPOSITE_V2_4_GOVERNANCE_APPROVED_WITH_ACTIVATION_BLOCKERS"
    assert value["scope"] == "SEMANTIC_GOVERNANCE_ONLY_NOT_MODEL_OR_RUNTIME_APPROVAL"
    assert value["activation_status"] == "NOT_ACTIVE" and value["runtime_effective_at"] is None
    assert value["authority"] == {
        "basis": "USER_DELEGATED_BOUNDED_GOVERNANCE_REVIEW",
        "directive_id": "1c637c0b-59a3-4fc5-920d-5de9df7867d9",
        "reviewer": "Codex governance reviewer", "human_signature_claimed": False,
    }
    assert value["proposal_reference"] == {
        "path": str(proposal.PATH.relative_to(ROOT)).replace("\\", "/"),
        "policy_id": p["proposal_id"], "policy_version": "v2-proposal.4",
        "proposal_fingerprint": proposal.EXPECTED_FINGERPRINT,
        "parent_policy_id": "six-gates-production-v1", "parent_version": "v1",
        "original_status": "PROPOSED", "original_artifact_overwritten": False,
    }
    assert value["single_successor"] == {
        "governed_future_candidate": "execution-gate-policy-v2-proposed/v2-proposal.4",
        "replaces_candidate_not_runtime": "execution-gate-policy-v2-proposed/v2-proposal.3",
        "prior_approvals_rewritten": False, "prior_versions": ["v2-proposal.2", "v2-proposal.3"],
        "prior_role": "HISTORICAL_AND_COMPONENT_GOVERNANCE_ONLY",
        "component_authorities_compete": False, "automatic_prior_approval_transfer": False,
        "runtime_policy_registered": False, "existing_reducer_only": True,
    }
    assert value["gate_ids"] == proposal.legacy.GATE_IDS
    assert value["boundaries"] == p["boundaries"]
    assert all(v is False for v in value["runtime"].values())
    assert value["semantic_bindings"] == {
        "gate1_pointer": "/gate1_proposed", "gate1_fingerprint": content_fingerprint(p["gate1_proposed"]),
        "gate1_override_fields": [], "gate3": p["gate3_carry_forward"],
        "gate6": p["gate6_carry_forward"], "prior_composite": p["prior_composite"],
        "all_inherited_risk_and_activation_constraints_retained": True,
    }
    assert value["unchanged_gate_proof"] == {
        "gates_2_4_5": p["unchanged_gates"], "gate1_v1": p["gate1_v1"],
        "active_configuration_and_authority_source_pins": p["frozen_source_fingerprints_lf"],
        "production_database_remeasured": False,
    }
    g, source = value["gate1_approval"], p["gate1_proposed"]
    assert all(g[k] is False for k in G1_FALSE)
    assert all(g[k] is True for k in G1_TRUE)
    expected = {
        "scope": "ROTATE_IN_ONLY", "score_hurdle": source["score_hurdle"]["formula"],
        "score_unit": "SCORE_POINT", "economics_unit": "INR",
        "gross_formula": source["economics"]["gross_formula"], "net_formula": source["economics"]["net_formula"],
        "economic_operator": ">", "economic_hurdle": "0.00",
        "comparator": "EXACT_INCUMBENT_NO_ROTATION_CONTINUATION",
        "quantity": "DETERMINISTIC_SCENARIO_ADVANTAGE_NOT_EXPECTED_VALUE",
        "capital_binding": source["capital"]["binding"],
        "candidate_deployment_binding": source["capital"]["candidate_deployment_binding"],
        "partial_rotation": "ACTUAL_SELECTED_PARCEL_FOR_BOTH_SCENARIOS_ALL_COSTS_AND_TAX_LOTS",
        "funding_residual_policy": "POLICY_UNSET", "numeric_horizon": None,
        "fundamental_B09": source["horizon"]["fundamental_B09_reference"],
        "B09_role": source["horizon"]["B09_role"], "scenario_model": "POLICY_UNSET",
        "friction_formula": source["friction"]["formula"],
        "execution_cost_formula": source["friction"]["execution_formula"],
        "component_manifest_pointer": "/gate1_proposed/friction", "rates_approved": {},
        "tax_choice": "T1", "tax_policy": "POLICY_UNSET", "slippage_producer": "NOT_READY",
        "slippage_method": "POLICY_UNSET", "authority_class": "DETERMINISTIC_HSI_DERIVED_SCENARIO",
        "pit_boundary": "KNOWN_AT_AND_OBSERVATION_AS_OF_LE_DECISION_AS_OF_UTC_INCLUSIVE",
        "identity_and_lineage_pointer": "/gate1_proposed/pit", "result_precedence": source["result"]["order"],
        "confidence_annotation": "1.0_NOT_PREDICTION_PROBABILITY",
    }
    assert g == expected | dict.fromkeys(G1_FALSE, False) | dict.fromkeys(G1_TRUE, True)
    assert value["gate3_decision"] == {
        "semantic_change": False, "mode": "CURRENT_EFFECTIVE_PIT_VISIBLE", "inputs": ["ASM", "GSM", "PRICE_BAND"],
        "thresholds": old["gate3_approval"]["blocking_thresholds"], "freshness": old["gate3_approval"]["freshness"],
        "security_status": "DESCRIPTIVE_ONLY", "blocking_plus_missing": "INSUFFICIENT_DATA",
        "independent_positive_veto": False,
    }
    assert value["gate6_decision"] == {
        "semantic_change": False, "mode": "VERIFIED_EVENT_VETO", "mapping": old["gate6_carry_forward"]["mapping"],
        "no_veto_metadata": old["gate6_carry_forward"]["no_veto_metadata"],
        "horizon": old["gate6_carry_forward"]["horizon"], "no_veto_is_clearance": False, "retroactive_blackout": False,
    }
    assert value["calibration"] == p["calibration"]
    assert value["liveness"] == {
        "scope": "SYNTHETIC_CONDITIONAL_ALGEBRA_AND_EXISTING_REDUCER_ONLY",
        "reducer": old["cross_gate_and_liveness"]["reducer"],
        "positive": ["SCORE_GE_1", "COST_EXCLUSIVE_ADVANTAGE_GT_COMPLETE_FRICTION",
                     "OTHER_FIVE_COMPOSITION_PASS", "EXECUTABLE"],
        "nonpositive": "GATE1_FAIL_THEN_BLOCKED",
        "missing_required_economics": "INSUFFICIENT_DATA_IF_NO_OTHER_FAIL_AND_SCORE_PASSES",
        "no_veto_confidence": None, "no_veto_clearance": "UNVERIFIED",
        "no_veto_warning": "EARNINGS_CLEARANCE_UNVERIFIED", "cross_gate_override": False,
        "production_readiness_proven": False, "order_or_capital_authority_created": False,
    }
    assert value["historical_isolation"] == old["historical_isolation"] | {
        "v1_gate1_scalars_never_aliased_to_v2": True, "composite3_is_historical_governance": True,
        "v2_4_only_after_explicit_future_activation": True, "explicit_v2_replay_with_exact_lineage_required": True,
    }
    assert value["pilot"] == {
        "research_and_comparison_continue": True, "governance_is_execution_readiness": False,
        "ROTATE_IN_economic_admission": "FAIL_CLOSED_UNTIL_ALL_REQUIRED_PROOFS",
        "fresh_entry_and_add_outside_economic_branch": True,
        "uncertainty_reduces_score_or_quality": False,
        "perfect_archives_required_before_prospective_pilot": False, "automatic_jobs_started": False,
    }
    assert value["architecture"] == {
        "reuse": ["CANONICAL_PORTFOLIO_SNAPSHOT", "ROTATION_CHALLENGER_UPSTREAM_CONTEXT",
                  "CANONICAL_MARKET_FACTS", "EXISTING_POLICY_VERSIONING", "GATE_EVIDENCE_ENVELOPE",
                  "EXISTING_SIX_GATE_REDUCER", "EXISTING_OUTCOME_INFRASTRUCTURE"],
        "second_rotation_engine": False, "second_portfolio_model": False, "AI_economic_engine": False,
        "parallel_reducer": False, "competing_whole_policy": False,
    }
    assert value["next_continuation"] == "GATE1_ROTATION_ECONOMIC_SCENARIO_CONTRACT_V1"
    assert value["next_continuation_started"] is False
    _verify_blockers(value, p, old)


def _verify_blockers(value, p, old):
    register = value["blocker_register"]
    assert register["all_origin_entries_once"] and register["merge_means_all_proofs_not_any_one"]
    assert register["semantic_approval_satisfied_only"]
    assert register["new_operational_closures_asserted"] is False
    assert register["selection_blocker_partial_satisfaction"] == "NEW_COMPOSITE_SEMANTIC_APPROVAL_ONLY_RUNTIME_SELECTION_STILL_OPEN"
    origins = {"composite3:" + r["id"]: r for r in old["blocker_register"]["entries"]}
    origins.update({"gate1:" + r["id"]: r for r in p["activation_blockers"]})
    rows = register["entries"]
    assert [r["id"] for r in rows] == [f"CV24B{i:02}" for i in range(1, 30)]
    assert [tuple(r["origins"]) for r in rows] == list(ORIGIN_GROUPS)
    assert len({r["area"] for r in rows}) == 29
    flat = [o for r in rows for o in r["origins"]]
    assert len(flat) == len(set(flat)) == len(origins) == 38
    assert set(flat) == origins.keys()
    for i, row in enumerate(rows):
        assert row["state"] == ("BLOCKED_PARKED" if i < 2 else "OPEN")
        assert row["all_required_proofs_mandatory"] is True
        assert {origins[o]["classification"] for o in row["origins"]} == {row["classification"]}
        assert row["required_proofs"] == [{"origin": o, "closure": origins[o]["closure"]} for o in row["origins"]]
    subproofs = value["accepted_subproofs"]
    assert [(r["id"], r["state"]) for r in subproofs] == [
        ("ASM_GSM_COMPLETENESS", "BLOCKED_PARKED"),
        ("EXECUTION_MASTER_CONTINUITY", "CLOSED_SOURCE_EVIDENCE_SUBPROOF_RETAINED"),
        ("PRICE_BAND_DIRECT_CAPTURE", "READY_CAPTURE_SUBPROOF_RETAINED"),
        ("EARNINGS_PROSPECTIVE_STRUCTURE", "READY_STRUCTURE_PENDING_EVENT_AND_OUTCOME"),
    ]
    for r in subproofs:
        assert r["remeasured"] is False and r["detail"].strip()
        assert r["reference"] in value["reviewed_files_lf"]
        assert set(r["affected_blockers"]) <= {x["id"] for x in rows}
    master = subproofs[1]
    doc = (ROOT / master["reference"]).read_text(encoding="utf-8")
    assert master["receipt_id"] == "nse-mii-current-master-capture:648df000bae29e6de5320495bf162549"
    assert master["receipt_fingerprint"] == "sha256:9327ec8f4ae07a470146c16a1938b3346e7ba3705aab256c90ae415b7bdb6e33"
    assert master["receipt_id"] in doc and master["receipt_fingerprint"] in doc
    assert "CURRENT_EXECUTION_MASTER_CONTINUITY_CLOSED" in doc


def test_exact_approval_and_transitive_proposals_replay_without_reapproval_or_activation():
    v = _read()
    _verify(v)
    assert v["approval_fingerprint"] == APPROVAL_FP
    assert _digest(json.loads(canonical_json(v))) == APPROVAL_FP
    assert _digest(dict(reversed(tuple(v.items())))) == APPROVAL_FP
    for key in v.keys() - {"approval_fingerprint"}:
        altered = deepcopy(v)
        del altered[key]
        assert _digest(altered) != APPROVAL_FP
    with pytest.raises(ValueError, match="DUPLICATE_PROPOSAL_KEY"):
        json.loads('{"decision":"A","decision":"C"}', object_pairs_hook=proposal.legacy._unique_object)


@pytest.mark.parametrize("path,pin", _read()["reviewed_files_lf"].items())
def test_baseline_worktree_source_and_governance_byte_pins(path, pin):
    baseline = subprocess.check_output(["git", "show", BASELINE + ":" + path])
    for raw in (baseline, (ROOT / path).read_bytes()):
        assert "sha256:" + sha256(raw.replace(b"\r\n", b"\n")).hexdigest() == pin


def test_independent_gate_definitions_methods_config_and_v1_result_remain_unchanged():
    proposal.test_gate1_history_and_gate2_4_5_definition_and_method_pins_unchanged()
    before = proposal.v1._rotation(proposal.v1._input())
    _verify(_read())
    assert proposal.v1._rotation(proposal.v1._input()) == before
    policy = previous.proposal_tests._policy()
    assert policy.gate_config.min_score_advantage == Decimal("1.00")
    assert policy.gate_config.net_economic_hurdle == Decimal("0.00")


@pytest.mark.parametrize("field", G1_FALSE + G1_TRUE)
def test_rehashed_approval_cannot_invert_any_gate1_boundary(field):
    v = _read()
    v["gate1_approval"][field] = not v["gate1_approval"][field]
    v["approval_fingerprint"] = _digest(v)
    with pytest.raises(AssertionError):
        _verify(v)


@pytest.mark.parametrize("path,replacement", [
    ("activation_status", "ACTIVE"), ("runtime_effective_at", "2026-09-01T00:00:00Z"),
    ("gate1_approval/economics_unit", "PERCENT"), ("gate1_approval/economic_operator", ">="),
    ("gate1_approval/economic_hurdle", "1.00"), ("gate1_approval/score_hurdle", ">= 0.70"),
    ("gate1_approval/comparator", "CASH"), ("gate1_approval/numeric_horizon", 30),
    ("gate1_approval/scenario_model", "APPROVED"), ("gate1_approval/tax_choice", "T2"),
    ("gate1_approval/rates_approved", {"tax": "0.10"}),
    ("gate1_approval/slippage_producer", "READY"), ("gate1_approval/funding_residual_policy", "ZERO_COST"),
    ("gate1_approval/pit_boundary", "PUBLICATION_DATE"),
    ("semantic_bindings/gate1_fingerprint", "sha256:" + "0" * 64),
    ("semantic_bindings/gate3/semantic_override_fields", ["ASM"]),
    ("gate6_decision/no_veto_metadata/confidence", "1.0"),
    ("gate6_decision/horizon/value", 5), ("gate3_decision/blocking_plus_missing", "FAIL"),
    ("single_successor/component_authorities_compete", True),
    ("historical_isolation/v1_gate1_scalars_never_aliased_to_v2", False),
    ("pilot/governance_is_execution_readiness", True),
    ("liveness/production_readiness_proven", True), ("next_continuation_started", True),
])
def test_rehashed_semantic_or_activation_drift_rejected(path, replacement):
    v = _read()
    target = v
    *parents, key = path.split("/")
    for name in parents:
        target = target[name]
    target[key] = replacement
    v["approval_fingerprint"] = _digest(v)
    with pytest.raises(AssertionError):
        _verify(v)


@pytest.mark.parametrize("mutation", ["drop", "duplicate", "waive", "close", "demote_tax", "reopen_master", "claim_event", "seventh_gate"])
def test_blocker_dedup_retains_all_proofs_and_accepted_subproofs(mutation):
    v = _read()
    rows = v["blocker_register"]["entries"]
    if mutation == "drop": rows[10]["required_proofs"].pop()
    elif mutation == "duplicate": rows.append(deepcopy(rows[0]))
    elif mutation == "waive": rows[10]["all_required_proofs_mandatory"] = False
    elif mutation == "close": rows[12]["state"] = "CLOSED"
    elif mutation == "demote_tax": rows[26]["classification"] = "NON_BLOCKING"
    elif mutation == "reopen_master": v["accepted_subproofs"][1]["state"] = "OPEN"
    elif mutation == "claim_event": v["accepted_subproofs"][3]["state"] = "LIVE_EVENT_PROVEN"
    else: v["gate_ids"].append("GATE_7_ECONOMICS")
    v["approval_fingerprint"] = _digest(v)
    with pytest.raises(AssertionError):
        _verify(v)


@pytest.mark.parametrize("terminal,state", [("1091", "PASS"), ("1090", "FAIL"), ("1089", "FAIL")])
def test_synthetic_inr_score_cost_once_and_existing_reducer_liveness(terminal, state):
    w = proposal._pair() | {"candidate_terminal": Decimal(terminal)}
    proposal._check_pair(w)
    gross = w["candidate_terminal"] - w["incumbent_terminal"]
    # execution_cost already includes slippage; tax is the only separate component here.
    net = gross - w["execution_cost"] - w["tax"]
    assert Decimal("81") - Decimal("80") >= Decimal("1.00")
    assert ("PASS" if net > 0 else "FAIL") == state
    result = previous._compose([state, "PASS", "PASS", "PASS", "PASS", "PASS"])
    assert result.eligibility.value == ("EXECUTABLE" if state == "PASS" else "BLOCKED")
    assert result.decisions[5].confidence is None
    assert result.decisions[5].parameters["earnings_clearance"] == "UNVERIFIED"
    assert "NO_ACTION_OR_ORDER_CREATED" in result.warnings


@pytest.mark.parametrize("missing", ["candidate_terminal", "incumbent_terminal", "execution_cost", "tax", "slippage"])
def test_missing_required_economics_not_zero_or_synthetic_pass(missing):
    with pytest.raises(AssertionError):
        proposal._check_pair(proposal._pair() | {missing: None})
    result = previous._compose(["INSUFFICIENT_DATA"] + ["PASS"] * 5)
    assert result.eligibility.value == "INSUFFICIENT_DATA"
    assert _read()["gate1_approval"]["result_precedence"].index("SCORE_ADVANTAGE_BELOW_1_FAIL") < _read()["gate1_approval"]["result_precedence"].index("MISSING_OR_INVALID_REQUIRED_SCENARIO_INSUFFICIENT")


@pytest.mark.parametrize("g1", ["PASS", "FAIL", "INSUFFICIENT_DATA"])
@pytest.mark.parametrize("g3", ["PASS", "FAIL", "INSUFFICIENT_DATA"])
@pytest.mark.parametrize("g6", ["PASS", "FAIL", "INSUFFICIENT_DATA"])
def test_all_27_composite_states_use_exact_existing_reducer(g1, g3, g6):
    outcomes = [g1, "PASS", g3, "PASS", "PASS", g6]
    result = previous._compose(outcomes)
    expected = "BLOCKED" if "FAIL" in outcomes else "INSUFFICIENT_DATA" if "INSUFFICIENT_DATA" in outcomes else "EXECUTABLE"
    assert result.eligibility.value == expected
    assert [r.outcome.value for r in result.decisions] == outcomes
    assert [r.gate_id for r in result.decisions] == _read()["gate_ids"]
    assert result.decisions[5].confidence is None


@pytest.mark.parametrize("field,bad", [
    ("unit", "PERCENT"), ("cost_currency", "USD"), ("incumbent_capital", Decimal("2000")),
    ("selected_quantity", Decimal("20")), ("held_quantity", Decimal("5")),
    ("residual", Decimal("1")), ("incumbent_horizon", "OTHER"), ("incumbent_model", "OTHER"),
    ("costs_excluded_from_gross", False), ("funding_reconciled", False),
])
def test_same_capital_actual_partial_horizon_and_cost_exclusion_are_mandatory(field, bad):
    with pytest.raises(AssertionError):
        proposal._check_pair(proposal._pair() | {field: bad})


@pytest.mark.parametrize("field", ["known_at", "observation_as_of", "incumbent_as_of", "incumbent_endpoint"])
def test_inclusive_pit_utc_and_future_filter_are_not_a_numeric_horizon_policy(field):
    w = proposal._pair()
    proposal._check_pair(w)
    shifted = deepcopy(w)
    for key in ("as_of", "incumbent_as_of", "known_at", "observation_as_of", "endpoint", "incumbent_endpoint"):
        shifted[key] = shifted[key].astimezone(timezone(timedelta(hours=5, minutes=30)))
    assert canonical_json(w) == canonical_json(shifted)
    with pytest.raises(AssertionError):
        proposal._check_pair(w | {field: w[field] + timedelta(microseconds=1)})


@pytest.mark.parametrize("field", ["expected_incremental_return", "modeled_switching_friction"])
@pytest.mark.parametrize("claim", ["USER_ENTERED", "AI_FORECAST", "DETERMINISTIC_HSI_DERIVED_SCENARIO"])
def test_approval_hash_does_not_register_economic_authority(field, claim, monkeypatch):
    _verify(_read())
    args, old, amount = proposal.attack(field)
    ref = proposal.domain_lineage(field, amount, source_id=claim, source_version=old.source_version,
        policy_version=old.policy_version, as_of=old.as_of, known_at=old.known_at,
        source_fingerprints=(_read()["approval_fingerprint"],))
    args["evidence_context"] = proposal.gate_evidence_context(args["inputs"], as_of=ref.as_of,
        gate_policy_version=ref.policy_version, dependencies=(ref,))
    for name in proposal.legacy.METHODS:
        monkeypatch.setattr(proposal.ExecutionGateEngine, name, lambda *a: pytest.fail("unverified formula"))
    with pytest.raises(proposal.GateSourceNotReady):
        proposal.evaluate(args, proposal.producer())


def test_downstream_keeps_all_inherited_impacts_and_no_competing_runtime_authority():
    v, p, old = _read(), proposal._read(), previous._read()
    rows = {r["consumer"]: r for r in v["downstream_impact"]}
    assert len(rows) == 13
    for origin in p["downstream_impact"] + old["downstream_impact"]:
        assert set(origin["classifications"]) <= set(rows[origin["consumer"]]["classifications"])
    for row in rows.values():
        assert (ROOT / row["reference"]).is_file()
        assert set(row["blockers"]) <= {r["id"] for r in v["blocker_register"]["entries"]}
    assert rows["Decision Score"]["classifications"] == rows["TradePlan"]["classifications"] == ["NO_CHANGE"]
    previous.test_single_successor_no_runtime_import_or_competing_gate_engine()
    for path in (ROOT / "app").rglob("*.py"):
        assert "v2-proposal.4" not in path.read_text(encoding="utf-8")
