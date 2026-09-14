"""Static .4 proposal and synthetic contract witnesses; no V2 runtime/model."""
from copy import deepcopy
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from hashlib import sha256
import json
from pathlib import Path
import subprocess

import pytest

from app.fundamentals.diagnostic_comparability import canonical_json, content_fingerprint
from app.gates.engine import ExecutionGateEngine
from app.gates.source_readiness import GateSourceNotReady
from app.gates.version_compatibility import domain_lineage, gate_evidence_context
from app.registry.canonical import EXECUTION_GATES, EXECUTION_GATE_REGISTRY_VERSION
from tests.unit import test_earnings_blackout_policy_v2_proposal as legacy
from tests.unit import test_execution_gate_policy_v2_composite_governance_approval as composite
from tests.unit import test_gate1_rotation_source_readiness as v1
from tests.unit.test_gate_authority_closure import attack
from tests.unit.test_gate_source_authority import evaluate, producer


ROOT = Path(__file__).resolve().parents[2]
PATH = ROOT / "docs/architecture/GATE1_ROTATION_POLICY_V2_PROPOSAL.json"
EXPECTED_FINGERPRINT = "sha256:0be5819937f85910700b672c7238d6cc01efa4777d8dac3518606837e2454769"
G3_POINTERS = ["/gate3_proposed", "/source_authority", "/security_status_guard", "/identity",
               "/component_source_contracts", "/effective_state_selector", "/known_at",
               "/result_contract", "/activation_blockers"]


def _read(path=PATH):
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=legacy._unique_object)


def _digest(value):
    return content_fingerprint({k: v for k, v in value.items() if k != "proposal_fingerprint"})


def _bundle(value, pointers):
    return {pointer[1:]: value[pointer[1:]] for pointer in pointers}


def _verify(value):
    """Test-only semantic review; no callable runtime admission policy added."""
    assert value.keys() == _read().keys()
    assert value["proposal_fingerprint"] == _digest(value)
    assert (value["proposal_id"], value["proposal_version"], value["status"], value["activation_status"]) == (
        "execution-gate-policy-v2-proposed", "v2-proposal.4", "PROPOSED", "NOT_ACTIVE")
    assert value["gate_ids"] == legacy.GATE_IDS
    assert value["parent_policy"]["policy_id"] == "six-gates-production-v1"
    assert value["parent_policy"]["version"] == "v1"
    assert value["composite_approval"] == {
        "required": True, "approval_reference": None, "effective_at": None,
        "prior_composite_approval_transfers": False,
        "prior_governed_candidate_remains_historical_unchanged": True}
    assert all(flag is False for flag in value["runtime"].values())
    assert value["versioning_model"] == "SINGLE_COMPOSITE_SUCCESSOR_BY_PINNED_REFERENCE"
    assert not any(value["replay"].values())
    g = value["gate1_proposed"]
    assert g["action_scope"]["economic_context"] == "ROTATE_IN"
    assert g["action_scope"]["not_applicable_contexts"] == [
        "FRESH_ENTRY", "ADD_TO_POSITION", "HOLD_EXISTING", "REDUCE_EXISTING", "EXIT_EXISTING", "RISK_MANAGEMENT"]
    assert not g["action_scope"]["new_scope"] and not g["action_scope"]["cash_comparator"]
    assert g["score_hurdle"]["formula"] == "raw_decision_score - comparison_score >= 1.00"
    assert g["score_hurdle"]["minimum"] == "1.00" and not g["score_hurdle"]["economic_conversion"]
    e = g["economics"]
    assert e["unit"] == "INR" and e["quantity"] == "GROSS_ROTATION_SCENARIO_ADVANTAGE_INR"
    assert e["comparator"] == "CANDIDATE_ROTATION_MINUS_INCUMBENT_NO_ROTATION_CONTINUATION"
    assert e["gross_formula"] == "candidate_scenario_terminal_value_inr - incumbent_continuation_terminal_value_inr"
    assert e["net_formula"] == "gross_rotation_scenario_advantage_inr - modeled_switching_friction_inr"
    assert (e["operator"], e["strict_hurdle"]) == (">", "0.00")
    assert e["terminal_values_nonnegative_finite"] and e["gross_advantage_may_be_negative"]
    assert not e["float_coercion_allowed"]
    assert e["scenario_model"] == "POLICY_UNSET" and e["scenario_model_reference"] is None
    assert not any(e[k] for k in ("probability_required", "expected_value_forecast", "realized_outcome",
                                  "target_is_scenario_authority", "score_is_return", "current_positive_source_ready"))
    c, h = g["capital"], g["horizon"]
    assert c["currency"] == "INR" and c["required_positive"] and c["same_C_both_scenarios"]
    assert c["binding"] == "C = selected_incumbent_quantity * incumbent_reference_price_inr"
    assert c["candidate_deployment_binding"] == "candidate_purchase_turnover_inr + candidate_residual_capital_inr = C"
    assert c["funding_and_residual_policy"] == "POLICY_UNSET" and c["candidate_residual_return_default"] is None
    assert not any(c[k] for k in ("portfolio_NAV_denominator", "entire_holding_default",
                                  "quantity_or_allocation_chosen_by_gate", "fees_deducted_from_deployment_then_subtracted_again"))
    assert h["required"] and h["same_reference_version_fingerprint_and_endpoint"]
    assert h["state"] == "HORIZON_BINDING_REQUIRED"
    assert h["value"] is h["unit"] is h["definition_reference"] is None
    assert not h["tradeplan_label_is_binding"] and not h["gate6_window_is_rotation_horizon"]
    assert g["scenario_contract"]["same_capital_cutoff_horizon_market_state_and_valuation_basis"]
    assert g["scenario_contract"]["gross_cost_reconciliation_and_funding_proof_required"]
    assert not g["scenario_contract"]["incumbent_zero_default"]
    assert not g["scenario_contract"]["gate4_pass_dependency"]
    f = g["friction"]
    assert f["unit"] == "INR" and f["formula"] == "execution_switching_cost_inr + tax_realization_impact_inr"
    assert [r["id"] for r in f["components"]] == ["purchase_statutory_costs", "sale_statutory_costs",
        "nse_member_transaction_charge", "brokerage", "gst", "slippage", "capital_gains_tax"]
    assert [r["classification"] for r in f["components"]] == ["RETAIN"] * 5 + ["SEPARATE_POLICY_REQUIRED"] * 2
    assert all(r["mandatory"] for r in f["components"][-2:])
    assert f["new_rate_values"] == {} and not f["missing_component_is_zero"]
    assert f["all_included_amounts_nonnegative"] and f["explicit_zero_requires_admitted_proof"]
    assert not f["separate_spread_impact_liquidity_terms"]
    assert (g["tax"]["chosen_option"], g["tax"]["mandatory"], g["tax"]["policy_state"]) == ("T1", True, "POLICY_UNSET")
    assert not g["tax"]["negative_credit_netting_or_future_tax_benefit_allowed"]
    assert g["slippage"]["mandatory"] and g["slippage"]["producer_state"] == "NOT_READY"
    assert not g["slippage"]["OHLC_proxy_allowed"]
    assert g["authority"]["proposed_class"] == "DETERMINISTIC_HSI_DERIVED_SCENARIO"
    for key in ("registered", "caller_self_hash_is_authority", "user_preference_is_hard_fact",
                "AI_populates_economics_or_gate", "user_entered_return_or_friction_allowed"):
        assert g["authority"][key] is False
    assert g["pit"]["known_at_boundary"] == g["pit"]["observation_as_of_boundary"] == "<= decision_as_of"
    assert g["pit"]["future_filtered_before_selection"]
    assert not any(g["pit"][k] for k in ("future_outcome_data_allowed", "later_portfolio_state_allowed",
                                        "publication_date_is_local_known_at", "processing_time_changes_identity"))
    assert g["result"]["outcomes"] == ["PASS", "FAIL", "INSUFFICIENT_DATA"]
    assert not g["result"]["result_is_order_authority"]
    assert value["calibration"]["decision"] == "BEFORE_ACTIVATION"
    assert not value["calibration"]["semantic_contract_requires_empirical_calibration_before_implementation"]
    assert value["calibration"]["scenario_shadow_validation_required"]
    assert value["final_policy_decision"] == "DETERMINISTIC_INR_ROTATION_ADVANTAGE_RECOMMENDED"
    assert value["final_result"] == "GATE1_V2_PROPOSAL_COHERENT_COMPOSITE_V2_4_REQUIRED"
    assert value["next_continuation"] == "EXECUTION_GATE_POLICY_V2_COMPOSITE_GOVERNANCE_APPROVAL_2"
    assert not value["next_continuation_started"]
    _verify_carry(value)
    _verify_blockers(value)


def test_exact_six_gate_identity_and_proposal_replay_is_not_approval():
    value = _read()
    _verify(value)
    assert value["proposal_fingerprint"] == EXPECTED_FINGERPRINT
    assert value["gate_registry_version"] == EXECUTION_GATE_REGISTRY_VERSION
    assert [r.gate_id for r in EXECUTION_GATES] == list(range(1, 7))
    assert _digest(dict(reversed(tuple(value.items())))) == EXPECTED_FINGERPRINT
    assert _digest(json.loads(canonical_json(value))) == EXPECTED_FINGERPRINT
    for key in value.keys() - {"proposal_fingerprint"}:
        altered = deepcopy(value)
        del altered[key]
        assert _digest(altered) != EXPECTED_FINGERPRINT
    with pytest.raises(ValueError, match="DUPLICATE_PROPOSAL_KEY"):
        json.loads('{"unit":"INR","unit":"PERCENT"}', object_pairs_hook=legacy._unique_object)


def _verify_carry(value):
    assert value["prior_composite"]["proposal_reference"] == "docs/architecture/GATE3_SURVEILLANCE_POLICY_V2_PROPOSAL.json"
    assert value["prior_composite"]["approval_reference"] == "docs/architecture/EXECUTION_GATE_POLICY_V2_COMPOSITE_GOVERNANCE_APPROVAL.json"
    prior = _read(ROOT / value["prior_composite"]["proposal_reference"])
    approval = _read(ROOT / value["prior_composite"]["approval_reference"])
    composite._verify(approval)
    assert prior["proposal_id"] == value["proposal_id"] and prior["proposal_version"] == "v2-proposal.3"
    assert value["prior_composite"]["proposal_fingerprint"] == _digest(prior)
    assert value["prior_composite"]["approval_fingerprint"] == approval["approval_fingerprint"]
    g3, g6 = value["gate3_carry_forward"], value["gate6_carry_forward"]
    assert g3["definition_pointers"] == G3_POINTERS
    assert g3["definition_bundle_fingerprint"] == content_fingerprint(_bundle(prior, G3_POINTERS))
    assert g3["approval_bundle_fingerprint"] == content_fingerprint(_bundle(approval, ["/gate3_approval", "/gate3_temporal_approval"]))
    assert g6["definition_fingerprint"] == content_fingerprint(prior["gate6_carry_forward"])
    assert g6["approval_definition_fingerprint"] == content_fingerprint(approval["gate6_carry_forward"])
    assert g3["semantic_override_fields"] == g6["semantic_override_fields"] == []
    assert g6["transitive_component_fingerprint"] == prior["gate6_carry_forward"]["proposal_fingerprint"]
    assert approval["gate6_carry_forward"]["no_veto_metadata"]["confidence"] is None
    assert approval["gate6_carry_forward"]["horizon"]["value"] is None
    inherited = value["inherited_constraints"]
    assert inherited["blocker_fingerprint"] == content_fingerprint(approval["blocker_register"])
    assert inherited["cross_gate_fingerprint"] == content_fingerprint(approval["cross_gate_and_liveness"])
    assert not inherited["operational_closure_reaudited"]


def test_full_prior_composite_and_gate3_gate6_bundles_carry_forward_without_overrides():
    _verify_carry(_read())


@pytest.mark.parametrize("path,pin", _read()["frozen_source_fingerprints_lf"].items())
def test_runtime_and_previous_governance_files_match_baseline_git_and_worktree(path, pin):
    baseline = subprocess.check_output(["git", "show", _read()["baseline_commit"] + ":" + path])
    for content in (baseline, (ROOT / path).read_bytes()):
        assert "sha256:" + sha256(content.replace(b"\r\n", b"\n")).hexdigest() == pin


def test_gate1_history_and_gate2_4_5_definition_and_method_pins_unchanged():
    value = _read()
    prior = _read(ROOT / value["prior_composite"]["proposal_reference"])
    assert value["unchanged_gates"] == [r for r in prior["unchanged_gates"] if r["registry_id"] in (2, 4, 5)]
    for row in value["unchanged_gates"] + [value["gate1_v1"]]:
        definition = next(g for g in EXECUTION_GATES if g.gate_id == row["registry_id"])
        assert content_fingerprint(asdict(definition)) == row["definition_fingerprint"]
        assert legacy._method_fingerprint(row["method"]) == row["implementation_fingerprint"]
    before = v1._rotation(v1._input())
    _verify(value)
    assert v1._rotation(v1._input()) == before
    assert not value["gate1_v1"]["old_scalars_reinterpreted"]


def test_b09_namespaced_dependency_is_applicability_not_a_numeric_holding_period():
    horizon = _read()["gate1_proposed"]["horizon"]
    ref = horizon["fundamental_B09_reference"]
    document = _read(ROOT / ref["path"])
    rows = document[ref["collection_pointer"][1:]]
    selected = [r for r in rows if r["blocker_id"] == ref["blocker_id"]]
    assert len(selected) == 1 and selected[0]["topic"] == "Versioned horizon-policy reference"
    assert "V2-compatible horizon/applicability" in selected[0]["required_proof"]
    assert horizon["value"] is None
    assert not horizon["gate6_window_is_rotation_horizon"]


def _pair():
    """Synthetic dimensional witness only; values never go to an HSI producer."""
    at = datetime(2026, 9, 1, tzinfo=timezone.utc)
    return dict(candidate="TEST:CANDIDATE", incumbent="TEST:INCUMBENT", capital=Decimal("1000"),
        incumbent_capital=Decimal("1000"), selected_quantity=Decimal("10"), held_quantity=Decimal("20"),
        incumbent_price=Decimal("100"), purchase=Decimal("1000"), residual=Decimal("0"),
        currency="INR", cost_currency="INR", unit="INR", as_of=at, incumbent_as_of=at,
        known_at=at, observation_as_of=at, horizon="SYNTHETIC_HORIZON_NOT_POLICY", incumbent_horizon="SYNTHETIC_HORIZON_NOT_POLICY",
        endpoint=at+timedelta(days=30), incumbent_endpoint=at+timedelta(days=30),
        model="SYNTHETIC_PAIRED_MODEL_NOT_APPROVAL", incumbent_model="SYNTHETIC_PAIRED_MODEL_NOT_APPROVAL",
        candidate_terminal=Decimal("1100"), incumbent_terminal=Decimal("1080"),
        execution_cost=Decimal("8"), tax=Decimal("2"), slippage=Decimal("1"),
        costs_excluded_from_gross=True, funding_reconciled=True)


def _check_pair(w):
    """Test-only invariants, not a scenario producer, public adapter or gate."""
    assert w["candidate"] != w["incumbent"]
    assert w["currency"] == w["cost_currency"] == w["unit"] == "INR"
    assert w["capital"] == w["incumbent_capital"] > 0
    assert 0 < w["selected_quantity"] <= w["held_quantity"] and w["incumbent_price"] > 0
    assert w["selected_quantity"] * w["incumbent_price"] == w["capital"]
    assert w["purchase"] >= 0 and w["residual"] >= 0
    assert w["purchase"] + w["residual"] == w["capital"]
    assert w["as_of"] == w["incumbent_as_of"]
    assert w["known_at"] <= w["as_of"] and w["observation_as_of"] <= w["as_of"]
    assert w["horizon"] == w["incumbent_horizon"] and w["model"] == w["incumbent_model"]
    assert w["endpoint"] == w["incumbent_endpoint"] > w["as_of"]
    assert w["costs_excluded_from_gross"] and w["funding_reconciled"]
    assert all(type(w[k]) is Decimal and w[k].is_finite() and w[k] >= 0 for k in (
        "execution_cost", "tax", "slippage", "candidate_terminal", "incumbent_terminal"))


@pytest.mark.parametrize("candidate_value,net_sign", (("1089", -1), ("1090", 0), ("1091", 1)))
def test_same_basis_synthetic_algebra_keeps_strict_zero_and_separate_score(candidate_value, net_sign):
    w = _pair() | {"candidate_terminal": Decimal(candidate_value)}
    _check_pair(w)
    # Slippage is already inside execution_cost, not added a second time.
    gross = w["candidate_terminal"] - w["incumbent_terminal"]
    net = gross - (w["execution_cost"] + w["tax"])
    assert (net > 0) - (net < 0) == net_sign
    assert ((gross / w["capital"]) - ((w["execution_cost"] + w["tax"]) / w["capital"]) > 0) == (net > 0)
    assert _read()["gate1_proposed"]["score_hurdle"]["unit"] == "SCORE_POINT"


@pytest.mark.parametrize("field,value", (
    ("incumbent", "TEST:CANDIDATE"), ("unit", "PERCENT"), ("cost_currency", "USD"),
    ("incumbent_capital", Decimal("2000")), ("capital", Decimal("0")),
    ("selected_quantity", Decimal("20")), ("held_quantity", Decimal("5")),
    ("purchase", Decimal("990")), ("residual", Decimal("10")),
    ("incumbent_horizon", "ANOTHER_HORIZON"), ("incumbent_model", "ANOTHER_MODEL"),
    ("tax", None), ("tax", Decimal("-1")), ("slippage", None),
    ("candidate_terminal", Decimal("NaN")), ("candidate_terminal", 1100.0),
    ("costs_excluded_from_gross", False), ("funding_reconciled", False),
))
def test_mismatched_missing_partial_or_double_counted_scenario_is_not_valid(field, value):
    with pytest.raises(AssertionError):
        _check_pair(_pair() | {field: value})


@pytest.mark.parametrize("field", ("incumbent_as_of", "known_at", "observation_as_of", "incumbent_endpoint"))
def test_pit_and_common_horizon_boundaries_do_not_confuse_modeled_endpoint_with_observation(field):
    w = _pair()
    _check_pair(w)  # Endpoint may be future; observation/known-at may not.
    with pytest.raises(AssertionError):
        _check_pair(w | {field: w[field] + timedelta(microseconds=1)})
    shifted = deepcopy(w)
    for name in ("as_of", "incumbent_as_of", "known_at", "observation_as_of", "endpoint", "incumbent_endpoint"):
        shifted[name] = shifted[name].astimezone(timezone(timedelta(hours=5, minutes=30)))
    _check_pair(shifted)
    assert canonical_json(w) == canonical_json(shifted)


@pytest.mark.parametrize("field", ("expected_incremental_return", "modeled_switching_friction"))
@pytest.mark.parametrize("label", ("USER_TYPED_20_PERCENT", "AI_FORECAST", "DETERMINISTIC_HSI_DERIVED_SCENARIO"))
def test_new_name_self_hash_or_user_ai_claim_never_grants_current_runtime_authority(field, label, monkeypatch):
    args, ref, value = attack(field)
    ref = domain_lineage(field, value, source_id=label, source_version=ref.source_version,
        policy_version=ref.policy_version, as_of=ref.as_of, known_at=ref.known_at,
        source_fingerprints=(_read()["proposal_fingerprint"],))
    args["evidence_context"] = gate_evidence_context(args["inputs"], as_of=ref.as_of,
        gate_policy_version=ref.policy_version, dependencies=(ref,))
    for name in legacy.METHODS:
        monkeypatch.setattr(ExecutionGateEngine, name, lambda *args: pytest.fail("unverified gate formula"))
    with pytest.raises(GateSourceNotReady):
        evaluate(args, producer())


def _verify_blockers(value):
    entries = value["activation_blockers"]
    assert [r["id"] for r in entries] == [f"G1B{i:02}" for i in range(1, 19)]
    assert [r["classification"] for r in entries] == ["BLOCKING"] * 15 + [
        "DEFERRED_FOR_REPLAY", "DEFERRED_FOR_SHADOW", "NON_BLOCKING"]
    assert all(r["state"] == "OPEN" and r["closure"] for r in entries)
    assert len({r["area"] for r in entries}) == 18
    assert {r["consumer"] for r in value["downstream_impact"]} == {
        "Six-Gates orchestration", "Portfolio Rotation Challenger", "Brain", "Signals", "Portfolio",
        "Entry-ready lifecycle", "Backtest/replay", "Outcome ledger", "TradePlan", "Decision Score", "Alerts"}
    for row in value["downstream_impact"]:
        assert (ROOT / row["reference"]).is_file()
    assert value["inherited_constraints"]["inherit_all_gate3_gate6_risk_and_activation_constraints"]


def test_blockers_scope_and_no_competing_runtime_policy():
    _verify_blockers(_read())
    for path in (ROOT / "app").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert "v2-proposal.4" not in text and "GATE1_ROTATION_POLICY_V2_PROPOSAL" not in text


@pytest.mark.parametrize("mutation", ("activate", "scope", "extra_gate", "score", "zero", "unit",
    "cash_comparator", "capital", "horizon", "probability", "tax", "slippage", "double_count",
    "ai", "approval_transfer", "gate3_override", "gate6_override", "missing_blocker",
    "defer_tax", "future", "history_alias", "unknown_key"))
def test_rehashed_unsafe_proposal_does_not_pass_semantic_review(mutation):
    value = _read()
    g = value["gate1_proposed"]
    if mutation == "activate": value["activation_status"] = "ACTIVE"
    elif mutation == "scope": g["action_scope"]["new_scope"] = True
    elif mutation == "extra_gate": value["gate_ids"].append("GATE_7_ECONOMICS")
    elif mutation == "score": g["score_hurdle"]["minimum"] = "0.70"
    elif mutation == "zero": g["economics"]["operator"] = ">="
    elif mutation == "unit": g["economics"]["unit"] = "PERCENT"
    elif mutation == "cash_comparator": g["economics"]["comparator"] = "CASH"
    elif mutation == "capital": g["capital"]["same_C_both_scenarios"] = False
    elif mutation == "horizon": g["horizon"]["value"] = 30
    elif mutation == "probability": g["economics"]["probability_required"] = True
    elif mutation == "tax": g["tax"]["mandatory"] = False
    elif mutation == "slippage": g["slippage"]["OHLC_proxy_allowed"] = True
    elif mutation == "double_count": g["capital"]["fees_deducted_from_deployment_then_subtracted_again"] = True
    elif mutation == "ai": g["authority"]["AI_populates_economics_or_gate"] = True
    elif mutation == "approval_transfer": value["composite_approval"]["prior_composite_approval_transfers"] = True
    elif mutation == "gate3_override": value["gate3_carry_forward"]["semantic_override_fields"] = ["asm_threshold"]
    elif mutation == "gate6_override": value["gate6_carry_forward"]["semantic_override_fields"] = ["confidence"]
    elif mutation == "missing_blocker": value["activation_blockers"].pop()
    elif mutation == "defer_tax": value["activation_blockers"][7]["classification"] = "NON_BLOCKING"
    elif mutation == "future": g["pit"]["future_outcome_data_allowed"] = True
    elif mutation == "history_alias": value["replay"]["old_field_alias_allowed"] = True
    else: value["runtime_hook"] = "unapproved"
    value["proposal_fingerprint"] = _digest(value)
    with pytest.raises(AssertionError):
        _verify(value)
