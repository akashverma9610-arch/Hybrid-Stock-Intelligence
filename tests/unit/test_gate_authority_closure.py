"""Real fail-closed authority, not the synthetic arithmetic fixture authority."""
import ast
from dataclasses import FrozenInstanceError, fields, replace
from datetime import timedelta
from decimal import Decimal
import json
from pathlib import Path
import subprocess
from types import SimpleNamespace

import pytest

from app.fundamentals.diagnostic_comparability import canonical_json, content_fingerprint
from app.gates.engine import ActionContext, ExecutionEligibility, ExecutionGateEngine, GateOutcome
from app.gates.source_authority import RepositoryGateAuthority, UnavailableGateAuthority
from app.gates.source_readiness import GateSourceNotReady, SOURCE_GAPS, SourceReadiness, source_gap
from app.gates.version_compatibility import GateVersionBlocked, domain_lineage, gate_evidence_context
from tests.unit.test_gate_source_authority import (
    CONFIG, complete, evaluate, legacy_inputs, persisted, producer, run_args, score,
)


EXPECTED = ("expected_incremental_return", "modeled_switching_friction", "atr_expansion",
    "surveillance", "trade_plan", "exposure", "earnings_scheduled_at", "earnings_schedule_verified_at")


def attack(field):
    card = score(complete()); args = run_args(card)
    value = getattr(legacy_inputs(expected_incremental_return=Decimal("1"),
                                  modeled_switching_friction=Decimal(".1")), field)
    if field.startswith("earnings_"):
        value = card.as_of_timestamp + timedelta(days=10) if field == "earnings_scheduled_at" else card.as_of_timestamp
    args["inputs"] = replace(args["inputs"], **{field: value})
    ref = domain_lineage(field, value, source_id=getattr(value, "id", "claimed-canonical"),
        source_version="claimed-approved-v1", policy_version=CONFIG.version,
        as_of=card.as_of_timestamp, known_at=card.as_of_timestamp,
        source_fingerprints=(content_fingerprint("claimed-official-evidence"),))
    args["evidence_context"] = gate_evidence_context(args["inputs"], as_of=card.as_of_timestamp,
        gate_policy_version=CONFIG.version, dependencies=(ref,))
    return args, ref, value


def test_exact_eight_from_complete_committed_matrix_and_immutable_order():
    before = json.loads(Path("docs/architecture/FUNDAMENTAL_V2_GATE_SOURCE_AUTHORITY_MATRIX.json").read_text())
    assert tuple(before["neutral_fields_blocked_without_adapter"]) == EXPECTED
    assert tuple(x.input_field for x in SOURCE_GAPS) == EXPECTED
    assert len(before["fields"]) == 36
    for gap in SOURCE_GAPS:
        assert gap.gate_id and gap.blocker and gap.future_slice and gap.state in SourceReadiness
        assert not gap.state.value.startswith("READY")
        with pytest.raises(FrozenInstanceError): gap.state = SourceReadiness.READY_AFTER_NARROW_ADAPTER
    assert source_gap("unrecognized") is None
    with pytest.raises(ValueError, match="GAP_UNKNOWN"):
        GateSourceNotReady("no authority", input_field="unrecognized")


@pytest.mark.parametrize("field", EXPECTED)
def test_named_absence_classification_before_any_formula(field, monkeypatch):
    args, _, _ = attack(field)
    for name in ("_rotation", "_velocity", "_surveillance", "_plan", "_heat", "_blackout"):
        monkeypatch.setattr(ExecutionGateEngine, name, lambda *a: pytest.fail("formula executed"))
    with pytest.raises(GateSourceNotReady) as caught:
        evaluate(args, producer())
    error = caught.value
    assert isinstance(error, GateVersionBlocked)
    assert error.compatibility_state == "VERSION_BLOCKED"
    assert error.source_gap is source_gap(field)
    assert str(error) == ("EARNINGS_CALENDAR_AUTHORITY_NOT_READY" if field.startswith("earnings_")
                          else "GATE_DOMAIN_AUTHORITY_UNAVAILABLE:" + field)


@pytest.mark.parametrize("field", EXPECTED)
def test_reader_cannot_invent_missing_producer_or_make_writes(field, tmp_path):
    repo, card = persisted(tmp_path); repo.save_decision_scorecard(card)
    args, _, _ = attack(field)
    changes = repo._connection.total_changes
    with pytest.raises(GateSourceNotReady) as caught:
        evaluate(args, RepositoryGateAuthority(repo))
    assert caught.value.source_gap.input_field == field
    assert repo._connection.total_changes == changes
    assert repo._connection.execute("SELECT count(*) FROM trade_plans").fetchone()[0] == 0
    repo.close()


@pytest.mark.parametrize("context", tuple(ActionContext))
def test_absent_source_never_clears_all_gates_even_when_existing_exemptions_apply(context):
    args = run_args(score(complete())) | {"action_context": context}
    result = evaluate(args, producer())
    # Frozen Gate 4 explicitly FAILs an absent plan; it is not an insufficiency.
    # Preserve that stricter outcome and the original aggregate precedence.
    assert result.eligibility is ExecutionEligibility.BLOCKED
    assert all(result.decisions[i].outcome is GateOutcome.INSUFFICIENT_DATA for i in (2, 4))
    assert result.decisions[3].outcome is GateOutcome.FAIL
    if context in {ActionContext.FRESH_ENTRY, ActionContext.ADD_TO_POSITION, ActionContext.ROTATE_IN}:
        assert result.decisions[5].outcome is GateOutcome.INSUFFICIENT_DATA
    # Exemptions are existing context semantics, not producer readiness.


def test_ready_descriptor_and_claimed_source_never_grant_authority():
    args, ref, value = attack("surveillance")
    fake = replace(source_gap("surveillance"), state=SourceReadiness.READY_EXISTING_CANONICAL_PRODUCER)
    forged_ref = SimpleNamespace(**{f.name: getattr(ref, f.name) for f in fields(ref)}, readiness=fake)
    with pytest.raises(GateSourceNotReady): UnavailableGateAuthority().verify_domain(forged_ref, value)
    with pytest.raises(TypeError): evaluate(args | {"producer_readiness": fake}, producer())


def test_real_approved_fixed_policy_not_caller_scenario_approval(tmp_path):
    from app.gates.production_policy import approved_six_gates_production_policy, selected_production_gate_engine
    from tests.unit.test_six_gates_production_policy import T, CALENDAR
    repo, _ = persisted(tmp_path)
    policy = approved_six_gates_production_policy(approved_at=T)
    repo.save_six_gates_production_policy(policy)
    changes = repo._connection.total_changes
    selected = repo.selected_six_gates_production_policy(as_of=T)
    selected.verify_integrity()
    engine = selected_production_gate_engine(repository=repo, calendar=CALENDAR, as_of=T)
    assert engine.config == selected.gate_config  # All exact approved fixed assumptions, no market provenance required.
    assert engine.config.friction_model_version == selected.friction_model.model_id
    assert repo.selected_six_gates_production_policy(as_of=T-timedelta(microseconds=1)) is None
    with pytest.raises(ValueError, match="FINGERPRINT"):
        replace(selected, gate_config=replace(selected.gate_config, net_economic_hurdle=Decimal("-1"))).verify_integrity()
    assert selected.friction_model.modeled_switching_friction(purchase_turnover=Decimal("1"),
        sale_turnover=Decimal("1"), brokerage=None, slippage=None, capital_gains_tax=None, gst_taxable_services=None) is None
    # Even binding a number to the real approved POLICY hash cannot approve user scenario costs.
    _, ref, value = attack("modeled_switching_friction")
    ref = replace(ref, source_id=selected.approval_id, source_version=selected.version,
                  source_fingerprints=("sha256:"+selected.fingerprint,))
    with pytest.raises(GateSourceNotReady):
        RepositoryGateAuthority(repo).verify_domain(ref, value, instrument_id="stock", as_of=T, gate_policy_version=selected.policy_id)
    assert repo._connection.total_changes == changes
    repo.close()


def test_available_atr_and_plan_contracts_are_not_semantically_gate_producers():
    from app.analysis.models import IndicatorResult
    from app.signals.models import TradePlan
    from app.strategies.pre_breakout.setup_assessment import GovernedPreBreakoutSetupAssessment
    indicator_fields = {f.name for f in fields(IndicatorResult)}
    assert {"input_observation_ids", "calculation_version", "as_of_timestamp", "status"} <= indicator_fields
    assert "atr_expansion" not in indicator_fields
    plan_fields = {f.name for f in fields(TradePlan)}
    assert {"plan_id", "structural_stop", "target_1", "management_plan_reference"} <= plan_fields
    assert not {"initial_tranche", "t1_reduction", "as_of_timestamp", "instrument_id"} & plan_fields
    assert "candidate_formation_eligible" in {f.name for f in fields(GovernedPreBreakoutSetupAssessment)}
    assert not {"initial_tranche", "t1_reduction"} & {f.name for f in fields(GovernedPreBreakoutSetupAssessment)}
    # Contract discovery is intentionally not a positive admission test for absent producers.


def test_unknown_capital_is_not_repaired_by_risk_admission():
    args, ref, value = attack("exposure")
    unknown = replace(value, portfolio_equity=None, existing_risk_amount=None)
    before = content_fingerprint(unknown)
    with pytest.raises(GateSourceNotReady): UnavailableGateAuthority().verify_domain(ref, unknown)
    assert content_fingerprint(unknown) == before and unknown.portfolio_equity is None


@pytest.mark.parametrize("raw", (Decimal("100"), {"entry": "100", "stop": "90", "target": "120"},
                                {"stop_defined": True, "t1_defined": True}))
def test_raw_prices_or_plan_booleans_never_form_a_canonical_plan(raw):
    args = run_args(score(complete()))
    args["inputs"] = replace(args["inputs"], trade_plan=raw)
    with pytest.raises(GateVersionBlocked): evaluate(args, producer())


@pytest.mark.parametrize("label", ("period_end", "filing_date", "historical_results", "AI_prediction"))
def test_dates_and_forecasts_never_become_verified_calendar(label):
    _, ref, value = attack("earnings_scheduled_at")
    ref = replace(ref, source_id=label, source_fingerprints=(content_fingerprint(label),))
    with pytest.raises(GateSourceNotReady) as caught: UnavailableGateAuthority().verify_domain(ref, value)
    assert caught.value.source_gap.blocker == "EARNINGS_CALENDAR_AUTHORITY_NOT_READY"


def test_closure_receipts_replay_without_rewriting_previous_evidence():
    from scripts.audit_gate_authority_closure import matrices, receipt
    for label, actual in (("MATRICES", matrices()), ("RECEIPT", receipt())):
        expected = json.loads(Path("docs/architecture/FUNDAMENTAL_V2_GATE_AUTHORITY_CLOSURE_"+label+".json").read_text())
        assert json.loads(canonical_json(actual)) == expected
        assert actual["fingerprint"] == content_fingerprint({k:v for k,v in actual.items() if k != "fingerprint"})
    report = matrices(); proof = receipt()
    assert len(report["expanded_fields"]) == 36
    assert all(x["authority_readiness"] in SourceReadiness for x in report["expanded_fields"])
    assert proof["v1_replay_cases"] == 21 and proof["unsafe_ingress_accepted"] == 0
    assert proof["b08_after"] == "CLOSED_FOR_ACTIVATION_COMPATIBILITY"
    assert proof["gate_source_data_readiness"] == "NOT_READY" and proof["v2_active"] is False
    assert proof["next_continuation"] == "EARNINGS_CALENDAR_SOURCE_GOVERNANCE_V1"
    assert not proof["generic_repair_4"]


def test_no_new_calculation_or_io_and_all_frozen_formulas_preserved():
    for name in ("app/gates/engine.py", "app/gates/production_policy.py", "app/analysis/technical.py",
                 "app/registry/canonical.py", "app/gates/score_provenance.py", "app/gates/version_compatibility.py",
                 "app/portfolio/engine.py", "app/signals/models.py"):
        assert Path(name).read_text() == subprocess.check_output(["git", "show", "c76affb:"+name], text=True)
    tree = ast.parse(Path("app/gates/source_readiness.py").read_text())
    imports = [n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)]
    assert imports == ["dataclasses", "enum", "app.gates.version_compatibility"]
    calls = {getattr(n.func, "attr", getattr(n.func, "id", "")) for n in ast.walk(tree) if isinstance(n, ast.Call)}
    assert not calls & {"open", "connect", "execute", "now", "utcnow", "save", "request", "atr", "build_scorecard"}
