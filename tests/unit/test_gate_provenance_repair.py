"""Source admission attacks and unchanged six-gate calculations, isolated only."""
import ast
from dataclasses import FrozenInstanceError, fields, replace
from datetime import timedelta, timezone
from decimal import Decimal
import json
from pathlib import Path
import subprocess

import pytest

from app.gates.engine import ExecutionGateEngine, GateInput
from app.gates.score_provenance import GateScoreEvidence, score_evidence
from app.gates.version_compatibility import (DOMAIN_FIELDS, GateVersionBlocked, domain_lineage,
    field_fingerprint, gate_evidence_context)
from app.fundamentals.diagnostic_comparability import content_fingerprint
from app.registry.versioned import V2_VERSION
from tests.fixtures.gate_provenance import synthetic_card, synthetic_comparison, synthetic_context, fixture_engine
from tests.unit import test_execution_gates as g
from tests.unit.test_fundamental_v2_brain_lineage import variants

BASELINE = "5da0111324707ff1f95543d598571463fe63522c"


def args(data=None):
    return dict(instrument_id="mock-stock", strategy_version="strategy/0.1",
        registry_version="diagnostic-registry-v1", scoring_configuration_version="decision-score-v1",
        action_context=g.ActionContext.ROTATE_IN, as_of_timestamp=g.ASOF, evaluated_at=g.ASOF,
        inputs=g.inputs() if data is None else data)


def proven(data=None):
    a = args(data)
    card = synthetic_card(a["inputs"], instrument=a["instrument_id"], strategy=a["strategy_version"],
                          scoring=a["scoring_configuration_version"], at=g.ASOF)
    other = synthetic_card(a["inputs"], instrument="TEST:INCUMBENT", strategy=a["strategy_version"],
                           scoring=a["scoring_configuration_version"], at=g.ASOF, incumbent=True)
    return a | dict(candidate_score_evidence=score_evidence(card),
        incumbent_score_evidence=score_evidence(other, comparison_result=synthetic_comparison(other, g.CONFIG.version)),
        evidence_context=synthetic_context(a["inputs"], g.CONFIG))


def evaluate(a):
    # Prior tests isolate content-binding/arithmetic, not new producer authority.
    return fixture_engine(ExecutionGateEngine(g.CONFIG, g.CALENDAR), a).evaluate(**a)


def test_complete_source_bound_v1_replay():
    before = g.evaluate(g.ActionContext.ROTATE_IN)
    after = evaluate(proven())
    assert content_fingerprint(before) == content_fingerprint(after)
    assert len(after.decisions) == 6


@pytest.mark.parametrize("field", ("candidate_score_evidence", "incumbent_score_evidence"))
def test_arbitrary_numbers_require_source_before_every_gate(field, monkeypatch):
    a = proven(); a[field] = None
    for name in ("_rotation", "_velocity", "_surveillance", "_plan", "_heat", "_blackout"):
        monkeypatch.setattr(ExecutionGateEngine, name, lambda *a: pytest.fail("calculation before admission"))
    with pytest.raises(GateVersionBlocked, match="PROVENANCE_REQUIRED"):
        evaluate(a)


@pytest.mark.parametrize("index", range(4))
def test_shadow_and_stripped_primitive_cannot_enter_adapter_or_gate(index):
    shadow = variants()[index]
    with pytest.raises(GateVersionBlocked): score_evidence(shadow)
    with pytest.raises(GateVersionBlocked): score_evidence(Decimal("8"))
    with pytest.raises(GateVersionBlocked): GateScoreEvidence(Decimal("8"), content_fingerprint(Decimal("8")))
    # Metadata stripping is not recoverable provenance, regardless of value.
    with pytest.raises(GateVersionBlocked, match="PROVENANCE_REQUIRED"):
        evaluate(args(g.inputs(raw_decision_score=Decimal("8"))))


@pytest.mark.parametrize("change", ({"final_score": Decimal("9")}, {"instrument_id": "other"},
    {"configuration_version": "other"}, {"registry_version": V2_VERSION},
    {"as_of_timestamp": g.ASOF+timedelta(seconds=1), "evaluated_at": g.ASOF+timedelta(seconds=1)}))
def test_content_tampering_and_rebinding_rejected(change):
    a = proven(); proof = a["candidate_score_evidence"]
    with pytest.raises(GateVersionBlocked):
        evaluate(a | {"candidate_score_evidence": replace(proof, source=replace(proof.source, **change))})
    # Rehashing doesn't repair the independently bound input/identity/PIT.
    with pytest.raises(GateVersionBlocked):
        evaluate(a | {"candidate_score_evidence": score_evidence(replace(proof.source, **change))})


def test_nested_mutation_detected_on_use():
    a = proven(); proof = a["candidate_score_evidence"]
    object.__setattr__(proof.source, "final_score", Decimal("0"))
    with pytest.raises(GateVersionBlocked, match="FINGERPRINT"): evaluate(a)


@pytest.mark.parametrize("field", tuple(DOMAIN_FIELDS))
def test_every_domain_requires_bound_reference_not_fake_registry(field):
    data = g.inputs(expected_incremental_return=Decimal("1"), modeled_switching_friction=Decimal(".1"))
    a = proven(data); binding = a["evidence_context"]
    refs = tuple(x for x in binding.dependencies if x.input_field != field)
    a["evidence_context"] = gate_evidence_context(data, as_of=g.ASOF,
        gate_policy_version=g.CONFIG.version, dependencies=refs)
    with pytest.raises(GateVersionBlocked, match="DOMAIN_PROVENANCE_REQUIRED:"+field): evaluate(a)
    ref = next(x for x in binding.dependencies if x.input_field == field)
    assert ref.registry_version is None and ref.mode is None and ref.strategy_version is None
    assert ref.score_eligible is False and ref.portfolio_action_eligible is False
    assert ref.evidence_family == DOMAIN_FIELDS[field]
    with pytest.raises(GateVersionBlocked, match="FALSE_PROVENANCE"):
        replace(ref, registry_version="diagnostic-registry-v1")


@pytest.mark.parametrize("field", ("surveillance", "trade_plan", "exposure", "atr_expansion"))
def test_shadow_domain_substitution_rejected(field):
    with pytest.raises(GateVersionBlocked): evaluate(proven() | {"inputs": g.inputs(**{field: variants()[3]})})


def test_plan_numeric_laundering_and_domain_value_change_rejected():
    a = proven()
    data = replace(a["inputs"], trade_plan=replace(a["inputs"].trade_plan, initial_tranche=Decimal(".1")))
    refs = a["evidence_context"].dependencies
    a["inputs"] = data
    a["evidence_context"] = gate_evidence_context(data, as_of=g.ASOF, gate_policy_version=g.CONFIG.version, dependencies=refs)
    with pytest.raises(GateVersionBlocked, match="DOMAIN_VALUE_MISMATCH"): evaluate(a)


def test_context_immutable_ordered_utc_and_duplicate_rejected():
    a = proven(); binding = a["evidence_context"]
    reverse = gate_evidence_context(a["inputs"], as_of=g.ASOF.astimezone(timezone(timedelta(hours=5, minutes=30))),
        gate_policy_version=g.CONFIG.version, dependencies=tuple(reversed(binding.dependencies)))
    assert binding.to_json() == reverse.to_json()
    with pytest.raises(FrozenInstanceError): binding.as_of = g.ASOF
    with pytest.raises(GateVersionBlocked, match="DUPLICATE"):
        gate_evidence_context(a["inputs"], as_of=g.ASOF, gate_policy_version=g.CONFIG.version,
            dependencies=binding.dependencies+(binding.dependencies[0],))
    assert json.loads(a["candidate_score_evidence"].to_json())["contract_version"] == "gate-score-provenance/v1"


def test_future_known_at_and_unverified_calendar_rejected():
    a = proven(); refs = a["evidence_context"].dependencies
    with pytest.raises(GateVersionBlocked, match="FUTURE"):
        gate_evidence_context(a["inputs"], as_of=g.ASOF, gate_policy_version=g.CONFIG.version,
            dependencies=tuple(replace(x, known_at=g.ASOF+timedelta(seconds=1)) for x in refs))
    from app.backtest.analytical import _earnings_schedule
    from tests.integration.test_historical_analytical_replay import metadata_observation
    from app.domain.models import ObservationKind
    from types import SimpleNamespace
    observation = metadata_observation("schedule", "candidate", ObservationKind.CORPORATE_EVENT,
        {"earnings_scheduled_at": g.ASOF+timedelta(days=2)}, g.ASOF)
    assert _earnings_schedule(SimpleNamespace(observations=(observation,)), "candidate") == (None, None)


def test_non_registry_domain_flags_cannot_grant_score_or_portfolio_authority():
    ref = proven()["evidence_context"].dependencies[0]
    for flags in ({"score_eligible": True}, {"portfolio_action_eligible": True}):
        with pytest.raises(GateVersionBlocked, match="AUTHORITY_CONTRADICTION"): replace(ref, **flags)


def test_comparison_requires_matching_original_gate_not_raw_score():
    a = proven(); proof = a["incumbent_score_evidence"]
    with pytest.raises(GateVersionBlocked): evaluate(a | {"incumbent_score_evidence": score_evidence(proof.source)})
    for change in ({"scorecard_id": "other"}, {"registry_version": V2_VERSION},
                   {"raw_decision_score": Decimal("0")}):
        with pytest.raises(GateVersionBlocked):
            score_evidence(proof.source, comparison_result=replace(proof.comparison_result, **change))


def test_app_has_no_fixture_bypass_and_gate_policies_are_unchanged():
    paths = ("app/gates/engine.py", "app/gates/version_compatibility.py", "app/gates/score_provenance.py")
    for path in paths:
        text = Path(path).read_text(encoding="utf-8")
        assert "tests.fixtures" not in text
        tree = ast.parse(text)
        calls = {ast.unparse(n.func) for n in ast.walk(tree) if isinstance(n, ast.Call)}
        assert not calls & {"datetime.now", "datetime.utcnow", "open", "sqlite3.connect", "requests.get"}
    for path in ("app/gates/production_policy.py", "app/scoring/engine.py", "app/registry/canonical.py",
                 "app/portfolio/engine.py", "app/rotation/engine.py"):
        assert Path(path).read_text(encoding="utf-8") == subprocess.check_output(
            ["git", "show", BASELINE+":"+path], text=True, encoding="utf-8")


def test_unlinked_historical_score_fails_before_writes(tmp_path):
    from tests.integration.test_historical_portfolio_gates import _fixture, _evaluate, GATE_CONFIG
    from app.backtest.models import HistoricalHoldingGateContext
    repo, run, candidate, original, _, state = _fixture(tmp_path)
    context = HistoricalHoldingGateContext("unlinked", "incumbent", None, "7", "7", .8, None, None, None)
    repo.save_historical_holding_gate_context(context)
    before = repo._connection.total_changes
    with pytest.raises(GateVersionBlocked, match="HOLDING_SOURCE_UNVERIFIED"):
        _evaluate(repo, run, candidate, original, state, GATE_CONFIG, (context,))
    assert repo._connection.total_changes == before
    repo.close()


def test_repair_audit_inventory_and_receipt_are_reproducible():
    from scripts.audit_gate_provenance_repair import inventory, receipt
    directory = Path("docs/architecture")
    for name, actual in (("INVENTORY", inventory()), ("RECEIPT", receipt())):
        stored = json.loads((directory / ("FUNDAMENTAL_V2_GATE_PROVENANCE_REPAIR_"+name+".json")).read_text())
        assert json.loads(json.dumps(actual)) == stored
        assert actual["fingerprint"] == content_fingerprint({k:v for k,v in actual.items() if k != "fingerprint"})
    assert len(inventory()["fields"]) == 36
    assert set(inventory()["gate_input_fields"]) == {x.name for x in fields(GateInput)}
    assert receipt()["b08_after"] == "CLOSED_FOR_SHADOW_COMPATIBILITY"
