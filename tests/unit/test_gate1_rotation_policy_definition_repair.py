"""Governance proofs only: synthetic arithmetic is not economic source authority."""
import ast
from dataclasses import fields, replace
from datetime import timedelta
from decimal import Decimal
from hashlib import sha256
import json
from pathlib import Path
import subprocess

import pytest

from app.fundamentals.diagnostic_comparability import canonical_json, content_fingerprint
from app.gates.engine import ActionContext, ExecutionGateEngine, GateInput, GateOutcome
from app.gates.source_readiness import GateSourceNotReady, source_gap
from app.gates.version_compatibility import GateVersionBlocked, gate_evidence_context
from tests.unit.test_gate1_rotation_source_readiness import _input, _rotation
from tests.unit.test_gate_authority_closure import attack
from tests.unit.test_gate_provenance_repair import proven
from tests.unit.test_gate_source_authority import evaluate, producer
from tests.unit.test_six_gates_production_policy import _policy


RECEIPT = json.loads(Path(
    "docs/architecture/GATE1_ROTATION_POLICY_DEFINITION_REPAIR_V1.json"
).read_text(encoding="utf-8"))


def _git_text(revision, path):
    return subprocess.check_output(
        ["git", "show", f"{revision}:{path}"], encoding="utf-8"
    ).replace("\r\n", "\n")


def _lf_hash(text):
    return "sha256:" + sha256(text.replace("\r\n", "\n").encode("utf-8")).hexdigest()


def test_receipt_round_trip_tamper_detection_and_single_bounded_next_decision():
    body = {key: value for key, value in RECEIPT.items() if key != "receipt_fingerprint"}
    assert RECEIPT["receipt_fingerprint"] == content_fingerprint(body)
    assert canonical_json(RECEIPT) == canonical_json(json.loads(canonical_json(RECEIPT)))
    assert content_fingerprint(body | {"policy_change_authorized": True}) != RECEIPT["receipt_fingerprint"]
    assert RECEIPT["status"] == "GATE1_VERSIONED_ECONOMIC_POLICY_CHANGE_REQUIRED"
    assert RECEIPT["internal_conclusion"] == "V1_FORMULA_REQUIRES_VERSIONED_ECONOMIC_POLICY_CHANGE"
    assert RECEIPT["next_continuation"] == "GATE1_ROTATION_POLICY_V2_PROPOSAL"
    assert not RECEIPT["policy_change_authorized"] and not RECEIPT["runtime_producer_active"]
    assert RECEIPT["recommended_proposal_direction"] == "C"
    assert not RECEIPT["recommended_direction_is_approved_model"]
    assert set(RECEIPT["options"]) == set("ABCDE")


@pytest.mark.parametrize("evidence", RECEIPT["origin_evidence"], ids=lambda item: item["path"])
def test_historical_authority_pins_are_real_git_objects_not_reconstructed_claims(evidence):
    assert _lf_hash(_git_text(evidence["commit"], evidence["path"])) == evidence["lf_sha256"]
    assert RECEIPT["semantic_dimensions"]["economic_comparator"] == "UNKNOWN"
    assert RECEIPT["semantic_dimensions"]["fixed_friction_formula"] == "EXPLICITLY_APPROVED"


@pytest.mark.parametrize("path,expected", RECEIPT["frozen_lf_sha256"].items())
def test_runtime_previous_receipt_and_composite_sources_remain_frozen(path, expected):
    assert _lf_hash(Path(path).read_text(encoding="utf-8")) == expected
    assert _lf_hash(_git_text(RECEIPT["baseline_commit"], path)) == expected


def test_exact_rotation_formula_ast_unchanged_since_accepted_production_policy():
    def rotation_ast(text):
        tree = ast.parse(text)
        engine = next(node for node in tree.body if isinstance(node, ast.ClassDef)
                      and node.name == "ExecutionGateEngine")
        return ast.dump(next(node for node in engine.body if isinstance(node, ast.FunctionDef)
                             and node.name == "_rotation"), include_attributes=False)

    path = "app/gates/engine.py"
    assert rotation_ast(Path(path).read_text(encoding="utf-8")) == rotation_ast(
        _git_text(RECEIPT["frozen_scalar_behavior"]["strict_hurdle_since_commit"], path))
    earliest = _git_text("d64bb988ad253d04f970e7cea96f775e2e9dcbf6", path)
    assert "data.expected_incremental_return - data.modeled_switching_friction < self.config.net_economic_hurdle" in earliest
    assert "data.expected_incremental_return - data.modeled_switching_friction <= self.config.net_economic_hurdle" in Path(path).read_text()
    config = _policy().gate_config
    assert (config.min_score_advantage, config.net_economic_hurdle, config.require_economic_hurdle) == (
        Decimal("1.00"), Decimal("0.00"), True)


@pytest.mark.parametrize("raw,benefit,friction,outcome", (
    ("7.99", None, None, GateOutcome.FAIL),  # Known score failure precedes absent economics.
    ("8", None, "1", GateOutcome.INSUFFICIENT_DATA),
    ("8", "2", None, GateOutcome.INSUFFICIENT_DATA),
    ("8", "0.99", "1", GateOutcome.FAIL),
    ("8", "1", "1", GateOutcome.FAIL),
    ("8", "1.01", "1", GateOutcome.PASS),
))
def test_exact_score_equality_and_strict_economic_zero_boundary(raw, benefit, friction, outcome):
    result = _rotation(_input(raw_decision_score=Decimal(raw), comparison_score=Decimal("7"),
        expected_incremental_return=None if benefit is None else Decimal(benefit),
        modeled_switching_friction=None if friction is None else Decimal(friction)))
    assert result.outcome is outcome


@pytest.mark.parametrize("context", tuple(value for value in ActionContext if value is not ActionContext.ROTATE_IN))
def test_non_rotation_exemption_does_not_expand_economic_scope(context):
    result = _rotation(_input(expected_incremental_return=None, modeled_switching_friction=None), context)
    assert result.outcome is GateOutcome.PASS
    assert result.detail == "not applicable: no holding is being replaced"
    scope = RECEIPT["action_scope"]
    assert scope["cash_funded_FRESH_ENTRY"] == scope["add_tranche_ADD_TO_POSITION"] == "OUT_OF_SCOPE"
    assert scope["partial_rotation_capital_treatment"] == scope["full_rotation_capital_treatment"] == "UNDEFINED"


@pytest.mark.parametrize("benefit,cost,capital", (("100", "20", "1000"), ("20", "20", "100"), ("1", "20", "10")))
def test_same_positive_base_dimensional_algebra_is_not_a_return_model(benefit, cost, capital):
    e, f, c = map(Decimal, (benefit, cost, capital))
    assert c > 0
    assert (e - f > 0) == (e / c - f / c > 0)
    assert RECEIPT["dimensional_consistency"]["forbidden"] == "INR_MINUS_PERCENTAGE"
    assert not RECEIPT["dimensional_consistency"]["algebra_proves_semantic_compatibility"]
    assert not RECEIPT["dimensional_consistency"]["unit_adapter_created"]


def test_mixed_units_change_answer_and_are_not_misrepresented_as_runtime_unit_validation():
    # Illustrative 20% on 1000 INR is not the scalar 0.20 INR. No conversion policy is implemented.
    assert Decimal(".20") - Decimal("10") < 0
    assert Decimal(".20") * Decimal("1000") - Decimal("10") > 0
    for name in ("expected_incremental_return", "modeled_switching_friction"):
        assert GateInput.__annotations__[name] == "Decimal | None"
        assert source_gap(name).blocker == "GATE1_FRICTION_POLICY_AUTHORITY_NOT_READY"
    assert not RECEIPT["dimensional_consistency"]["current_operands_compatible"]


def test_comparator_horizon_capital_unresolved_without_erasing_existing_incumbent_identity():
    unresolved = RECEIPT["unresolved_economics"]
    assert all(unresolved[key] is None for key in (
        "comparator", "quantity", "unit", "horizon", "capital_base", "probability_model"))
    assert set(unresolved["blockers"]) == {
        "COMPARATOR_POLICY_MISSING", "RETURN_QUANTITY_POLICY_MISSING", "RETURN_UNIT_POLICY_MISSING",
        "HORIZON_POLICY_MISSING", "CAPITAL_BASE_POLICY_MISSING", "EXPECTED_VALUE_MODEL_POLICY_MISSING"}
    assert not unresolved["target_is_expectation"] and not unresolved["score_is_probability"]
    assert not unresolved["b09_supplies_gate1_horizon"]
    proof = proven()["incumbent_score_evidence"]
    assert proof.source.instrument_id == proof.comparison_result.instrument_id == "TEST:INCUMBENT"
    assert not {"economic_comparator", "capital_switched", "horizon_version"} & {f.name for f in fields(GateInput)}
    assert RECEIPT["reuse"]["incumbent_identity_already_in_score_provenance"]
    assert not RECEIPT["reuse"]["economic_pair_capital_horizon_binding_exists"]


def _costs():
    return dict(purchase_turnover=Decimal("100000"), sale_turnover=Decimal("100000"),
                brokerage=Decimal("10"), slippage=Decimal("10"),
                capital_gains_tax=Decimal("10"), gst_taxable_services=Decimal("10"))


def test_exact_current_friction_terms_units_and_tax_inclusion_not_tax_calculation():
    model = _policy().friction_model
    model.verify_integrity()
    expected = RECEIPT["friction"]
    for name, value in expected["fixed_parameters"].items():
        assert getattr(model, name) == Decimal(value)
    assert model.modeled_switching_friction(**_costs()) == Decimal("253.14")
    assert model.effective_at.isoformat() == expected["effective_at"]
    assert expected["tax_inclusion"] == "EXPLICIT_CURRENT_POLICY"
    assert expected["tax_calculation_policy"] == "UNKNOWN"
    assert expected["slippage_producer"] == "NOT_READY" and expected["slippage_required"]
    assert not expected["separate_spread_impact_liquidity_delay_components"]


@pytest.mark.parametrize("name,delta", (("brokerage", "1"), ("slippage", "1"),
                                      ("capital_gains_tax", "1"), ("gst_taxable_services", ".18")))
def test_cost_component_addition_and_none_never_implicitly_zero(name, delta):
    model = _policy().friction_model
    base = model.modeled_switching_friction(**_costs())
    assert model.modeled_switching_friction(**(_costs() | {name: Decimal("11")})) == base + Decimal(delta)
    assert model.modeled_switching_friction(**(_costs() | {name: None})) is None


@pytest.mark.parametrize("name", tuple(_costs()))
def test_negative_complete_cost_input_rejected_without_inventing_tax_credits(name):
    with pytest.raises(ValueError, match="NSE_CASH_DELIVERY_FRICTION_INPUT_INVALID"):
        _policy().friction_model.modeled_switching_friction(**(_costs() | {name: Decimal("-1")}))


@pytest.mark.parametrize("field", ("expected_incremental_return", "modeled_switching_friction"))
@pytest.mark.parametrize("claim,value", (("USER_TYPED_20_PERCENT", ".20"), ("AI_FORECAST", "500"), ("EXPLICIT_ZERO", "0")))
def test_user_ai_and_zero_claims_never_reach_any_gate_formula(field, claim, value, monkeypatch):
    args, ref, _ = attack(field)
    from app.gates.version_compatibility import domain_lineage
    claimed_value = Decimal(value)
    args["inputs"] = replace(args["inputs"], **{field: claimed_value})
    ref = domain_lineage(field, claimed_value, source_id=claim, source_version=ref.source_version,
        policy_version=ref.policy_version, as_of=ref.as_of, known_at=ref.known_at,
        source_fingerprints=ref.source_fingerprints)
    args["evidence_context"] = gate_evidence_context(args["inputs"], as_of=ref.as_of,
        gate_policy_version=ref.policy_version, dependencies=(ref,))
    for name in ("_rotation", "_velocity", "_surveillance", "_plan", "_heat", "_blackout"):
        monkeypatch.setattr(ExecutionGateEngine, name, lambda *a: pytest.fail("unverified formula executed"))
    with pytest.raises(GateSourceNotReady) as caught:
        evaluate(args, producer())
    assert caught.value.source_gap.blocker == "GATE1_FRICTION_POLICY_AUTHORITY_NOT_READY"


@pytest.mark.parametrize("time_field", ("as_of", "known_at"))
def test_future_scenario_lineage_excluded_and_equal_cutoff_still_not_authority(time_field):
    args, ref, _ = attack("expected_incremental_return")
    context = args["evidence_context"]
    assert context.as_of == ref.as_of == ref.known_at
    assert context.to_json() == gate_evidence_context(args["inputs"], as_of=context.as_of,
        gate_policy_version=context.gate_policy_version, dependencies=(ref,)).to_json()
    future = replace(ref, **{time_field: context.as_of + timedelta(microseconds=1)})
    with pytest.raises(GateVersionBlocked, match="FUTURE_EVIDENCE"):
        gate_evidence_context(args["inputs"], as_of=context.as_of,
            gate_policy_version=context.gate_policy_version, dependencies=(future,))
    with pytest.raises(GateSourceNotReady):
        evaluate(args, producer())


def test_duplicate_conflicting_and_tampered_lineage_is_rejected():
    args, ref, _ = attack("expected_incremental_return")
    context = args["evidence_context"]
    for duplicate in (ref, replace(ref, source_id="other-claimed-source")):
        with pytest.raises(GateVersionBlocked, match="DUPLICATE_OR_CONFLICTING"):
            gate_evidence_context(args["inputs"], as_of=context.as_of,
                gate_policy_version=context.gate_policy_version, dependencies=(ref, duplicate))
    with pytest.raises(GateVersionBlocked, match="FINGERPRINT_MISMATCH"):
        replace(context, fingerprint="sha256:" + "0" * 64)


def test_single_composite_successor_stays_inactive_with_frozen_gate1():
    proposal = json.loads(Path("docs/architecture/GATE3_SURVEILLANCE_POLICY_V2_PROPOSAL.json").read_text())
    approval = json.loads(Path("docs/architecture/EXECUTION_GATE_POLICY_V2_COMPOSITE_GOVERNANCE_APPROVAL.json").read_text())
    future = RECEIPT["single_future_policy"]
    assert future["proposal_fingerprint"] in canonical_json(proposal)
    assert future["approval_fingerprint"] in canonical_json(approval)
    assert future["policy_id"] in canonical_json(proposal) and future["version"] in canonical_json(proposal)
    assert not future["modified_or_activated_by_this_repair"]
    assert future["future_gate1_incorporation_requires_new_composite_governance"]
    assert RECEIPT["calibration_decision"] == "UNRESOLVED"
    assert RECEIPT["invariants"] == {
        "V1_ACTIVE": True, "GATE_POLICY_V2_ACTIVE": False, "SIX_GATES_EXACTLY_SIX": True,
        "NO_FABRICATED_ECONOMIC_RETURN": True, "NO_FABRICATED_SWITCHING_FRICTION": True,
        "NO_FUTURE_LEAKAGE": True, "NO_USER_ENTERED_GATE1_EXPECTED_RETURN_AUTHORITY": True,
        "PILOT_SIMPLICITY_RULE": "ACTIVE", "AI_DECISION_AUTHORITY": False}
