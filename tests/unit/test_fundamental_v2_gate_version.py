"""Isolated version admission and exact frozen V1 replay. No live actions."""
import ast
from dataclasses import FrozenInstanceError, asdict, fields, replace
from datetime import timedelta, timezone
from decimal import Decimal
from functools import lru_cache
import json
from pathlib import Path
import subprocess
import sys
from types import ModuleType, SimpleNamespace

import pytest

from app.gates.engine import ActionContext, ExecutionGateEngine, GateInput, GateOutcome
from app.gates.version_compatibility import (
    CROSS_REGISTRY, SHADOW_FORBIDDEN, VERSION, GateEvidenceContext, GateEvidenceLineage,
    GateVersionBlocked, gate_evidence_context, require_gate_source,
)
from app.fundamentals.diagnostic_comparability import content_fingerprint
from app.registry.canonical import DIAGNOSTIC_REGISTRY_VERSION as V1
from app.registry.versioned import RegistryMode, V2_VERSION, resolve_diagnostic_registry
from tests.unit import test_execution_gates as g
from tests.unit.test_fundamental_v2_brain_lineage import variants

BASELINE = "c182b6421303f5f1cb8df3517be36872e72d5602"
PERMITTED_APP = {
    "app/gates/version_compatibility.py", "app/gates/engine.py", "app/backtest/analytical.py",
    "app/backtest/portfolio_gates.py", "app/portfolio/canonical_six_gates.py",
    "app/portfolio/canonical_six_gates_activation.py", "app/intelligence/six_gates_evidence.py",
    "app/universe_analysis/service.py",
}


def evaluate(data=None, *, registry=V1, context=ActionContext.FRESH_ENTRY, lineage=None):
    return ExecutionGateEngine(g.CONFIG, g.CALENDAR).evaluate(
        instrument_id="isolated-gate-version", strategy_version="strategy/0.1", registry_version=registry,
        scoring_configuration_version="decision-score-v1", action_context=context, as_of_timestamp=g.ASOF,
        evaluated_at=g.ASOF, inputs=g.inputs() if data is None else data, evidence_context=lineage)


@lru_cache(maxsize=1)
def baseline():
    name = "_gate_version_baseline"
    module = ModuleType(name); sys.modules[name] = module
    source = subprocess.check_output(["git", "show", BASELINE+":app/gates/engine.py"], text=True, encoding="utf-8")
    exec(compile(source, name, "exec"), module.__dict__)
    return module


def v1_cases():
    return (
        (ActionContext.FRESH_ENTRY, g.inputs(), g.CONFIG),
        (ActionContext.ROTATE_IN, g.inputs(), g.CONFIG),
        (ActionContext.ROTATE_IN, g.inputs(comparison_score=Decimal("9.2")), g.CONFIG),
        (ActionContext.ROTATE_IN, g.inputs(comparison_score=None), g.CONFIG),
        (ActionContext.ROTATE_IN, g.inputs(), replace(g.CONFIG, require_economic_hurdle=True)),
        (ActionContext.HOLD_EXISTING, g.inputs(atr_expansion=Decimal("0.2")), g.CONFIG),
        (ActionContext.HOLD_EXISTING, g.inputs(holding_entry_date=None), g.CONFIG),
        (ActionContext.FRESH_ENTRY, g.inputs(surveillance=None), g.CONFIG),
        (ActionContext.FRESH_ENTRY, g.inputs(surveillance=g.surveillance(stage=2)), g.CONFIG),
        (ActionContext.FRESH_ENTRY, g.inputs(surveillance=g.surveillance(effective=g.ASOF-timedelta(days=3))), g.CONFIG),
        (ActionContext.FRESH_ENTRY, g.inputs(trade_plan=None), g.CONFIG),
        (ActionContext.FRESH_ENTRY, g.inputs(exposure=None), g.CONFIG),
        (ActionContext.FRESH_ENTRY, g.inputs(exposure=g.exposure(sector=Decimal(".50"))), g.CONFIG),
        (ActionContext.FRESH_ENTRY, g.inputs(earnings_scheduled_at=None), g.CONFIG),
        (ActionContext.FRESH_ENTRY, g.inputs(earnings_scheduled_at=g.ASOF+timedelta(days=2)), g.CONFIG),
        (ActionContext.RISK_MANAGEMENT, g.inputs(earnings_scheduled_at=g.ASOF+timedelta(days=2)), g.CONFIG),
        (ActionContext.FRESH_ENTRY, g.inputs(), replace(g.CONFIG, min_score_advantage=None)),
    )


def replay_pair(index):
    old = baseline(); context, inputs, config = v1_cases()[index]
    args = dict(instrument_id="isolated-gate-version", strategy_version="strategy/0.1", registry_version=V1,
                scoring_configuration_version="decision-score-v1", as_of_timestamp=g.ASOF, evaluated_at=g.ASOF)
    # Frozen gate methods compare their own enum identities. Inputs retain the
    # exact original field values, including None; no fixture value is repaired.
    before = old.ExecutionGateEngine(config, g.CALENDAR).evaluate(
        **args, action_context=old.ActionContext(context.value), inputs=inputs)
    after = ExecutionGateEngine(config, g.CALENDAR).evaluate(**args, action_context=context, inputs=inputs)
    return before, after


@pytest.mark.parametrize("index", range(17))
def test_all_six_v1_replay_identical(index):
    before, after = replay_pair(index)
    assert content_fingerprint(before) == content_fingerprint(after)
    assert len(after.decisions) == 6


def test_default_v1_only_and_exact_legacy_label_preserved():
    assert resolve_diagnostic_registry().registry_version == V1
    with pytest.raises(ValueError, match="NOT_ACTIVE"):
        resolve_diagnostic_registry(V2_VERSION)
    assert evaluate().registry_version == V1
    assert evaluate(registry="v1").registry_version == "v1"


@pytest.mark.parametrize("version", (V2_VERSION, "", None, "latest", "LATEST_AVAILABLE", "v2", "registry-v1"))
def test_no_unknown_or_latest_registry(version):
    with pytest.raises(GateVersionBlocked): evaluate(registry=version)


@pytest.mark.parametrize("field", ("raw_decision_score", "comparison_score", "atr_expansion", "holding_entry_date",
    "surveillance", "trade_plan", "exposure", "earnings_scheduled_at", "earnings_schedule_verified_at"))
@pytest.mark.parametrize("index", range(4))
def test_every_gate_rejects_raw_envelope_brain_and_portfolio_before_any_gate(field, index, monkeypatch):
    for method in ("_rotation", "_velocity", "_surveillance", "_plan", "_heat", "_blackout"):
        monkeypatch.setattr(ExecutionGateEngine, method, lambda *a, **kw: pytest.fail("gate ran before admission"))
    with pytest.raises(GateVersionBlocked, match="V2_SHADOW_GATE") as caught:
        evaluate(replace(g.inputs(), **{field: variants()[index]}))
    assert caught.value.compatibility_state == "VERSION_BLOCKED"


@pytest.mark.parametrize("field", ("portfolio_equity", "existing_risk_amount", "candidate_risk_amount", "candidate_allocation", "sector_allocation"))
def test_nested_heat_fields_cannot_receive_shadow(field):
    with pytest.raises(GateVersionBlocked, match="V2_SHADOW_GATE"):
        evaluate(g.inputs(exposure=replace(g.exposure(), **{field: variants()[3]})))


@pytest.mark.parametrize("field", ("initial_tranche", "t1_reduction", "stop_defined", "t1_defined", "breakeven_conditions"))
def test_nested_plan_fields_cannot_receive_shadow(field):
    with pytest.raises(GateVersionBlocked, match="V2_SHADOW_GATE"):
        evaluate(g.inputs(trade_plan=replace(g.plan(), **{field: variants()[2]})))


@pytest.mark.parametrize("value", ("READY", "UNKNOWN", "POLICY_BLOCKED", True, Decimal("NaN"), Decimal("Infinity"),
                                  {"registry_version": V2_VERSION, "value": 10}, SimpleNamespace(value=10)))
def test_unknown_numeric_and_ambiguous_unversioned_input_cannot_be_score(value):
    with pytest.raises(GateVersionBlocked): evaluate(g.inputs(raw_decision_score=value))


def dependency(field="raw_decision_score", **changes):
    args = dict(input_field=field, registry_version=V1, mode=RegistryMode.ACTIVE, strategy_version=None,
                policy_version="existing-source-v1", as_of=g.ASOF, source_fingerprints=(content_fingerprint("isolated-source"),),
                score_eligible=True, execution_eligible=True, portfolio_action_eligible=True)
    return GateEvidenceLineage(**(args | changes))


def binding(*items):
    return gate_evidence_context(g.inputs(), as_of=g.ASOF, gate_policy_version=g.CONFIG.version,
                                 dependencies=items or (dependency(),))


def test_typed_binding_is_observational_deterministic_utc_and_immutable():
    a = binding(dependency(), dependency("comparison_score"))
    b = binding(dependency("comparison_score"), dependency(as_of=g.ASOF.astimezone(timezone(timedelta(hours=5, minutes=30)))))
    assert a == b and a.to_json() == b.to_json() and a.contract_version == VERSION
    assert content_fingerprint(evaluate(lineage=a)) == content_fingerprint(evaluate())
    with pytest.raises(FrozenInstanceError): a.fingerprint = "changed"
    assert json.loads(a.to_json())["fingerprint"] == a.fingerprint


def test_mixed_lineage_never_drops_required_or_optional_incompatible_item():
    shadow = dependency("comparison_score", registry_version=V2_VERSION, mode=RegistryMode.SHADOW,
                        score_eligible=False, execution_eligible=False, portfolio_action_eligible=False)
    for bundle in ((shadow,), (dependency(), shadow), (shadow, dependency())):
        with pytest.raises(GateVersionBlocked, match="V2_SHADOW_GATE"):
            evaluate(lineage=binding(*bundle))


@pytest.mark.parametrize("changes", ({"fingerprint": "sha256:"+"0"*64}, {"gate_policy_version": "wrong"},
                                  {"as_of": g.ASOF+timedelta(seconds=1)}, {"input_fingerprint": "sha256:"+"0"*64}))
def test_binding_tamper_rejected(changes):
    with pytest.raises(GateVersionBlocked): replace(binding(), **changes)


def test_valid_rehashed_but_wrong_context_still_rejected():
    b = gate_evidence_context(g.inputs(comparison_score=Decimal("0")), as_of=g.ASOF,
                             gate_policy_version=g.CONFIG.version, dependencies=(dependency(),))
    with pytest.raises(GateVersionBlocked, match="BINDING_MISMATCH"): evaluate(lineage=b)


def test_duplicate_conflicting_future_lineage_rejected():
    for items in ((dependency(), dependency()), (dependency(), dependency(policy_version="conflict")),
                  (dependency(as_of=g.ASOF+timedelta(seconds=1)),)):
        with pytest.raises(GateVersionBlocked): binding(*items)
    with pytest.raises(GateVersionBlocked): dependency(source_fingerprints=("not-a-fingerprint",))
    with pytest.raises(GateVersionBlocked): dependency(mode=RegistryMode.SHADOW)
    with pytest.raises(GateVersionBlocked): dependency(as_of=g.ASOF.replace(tzinfo=None))


def test_missing_sources_remain_governed_insufficient_and_not_clearance():
    result = evaluate(g.inputs(surveillance=None, earnings_scheduled_at=None, earnings_schedule_verified_at=None))
    assert result.decisions[2].outcome is GateOutcome.INSUFFICIENT_DATA
    assert result.decisions[5].outcome is GateOutcome.INSUFFICIENT_DATA


def test_financial_dates_never_substitute_for_scheduled_earnings():
    from app.backtest.analytical import _earnings_schedule
    from app.domain.models import FinancialObservation, ObservationKind
    from tests.integration.test_historical_analytical_replay import metadata_observation
    for key in ("period_end", "filing_date", "publication_timestamp"):
        raw = metadata_observation("financial", "candidate", ObservationKind.FUNDAMENTAL, {key: g.ASOF}, g.ASOF)
        assert _earnings_schedule(SimpleNamespace(observations=(raw,)), "candidate") == (None, None)
        spoof = replace(raw, payload={key: g.ASOF, "earnings_scheduled_at": g.ASOF})
        with pytest.raises(ValueError, match="FINANCIAL_SOURCE_FORBIDDEN"):
            _earnings_schedule(SimpleNamespace(observations=(spoof,)), "candidate")
    raw = metadata_observation("event", "candidate", ObservationKind.CORPORATE_EVENT,
          {"earnings_scheduled_at": g.ASOF+timedelta(days=20), "earnings_schedule_verified_at": g.ASOF}, g.ASOF)
    assert _earnings_schedule(SimpleNamespace(observations=(raw,)), "candidate") == (g.ASOF+timedelta(days=20), g.ASOF)
    financial = FinancialObservation(**asdict(raw))
    # Retain typed instrument/provenance when constructing the typed filing.
    financial = replace(financial, instrument=raw.instrument, provenance=raw.provenance)
    with pytest.raises(ValueError, match="FINANCIAL_SOURCE_FORBIDDEN"):
        _earnings_schedule(SimpleNamespace(observations=(financial,)), "candidate")


def test_historical_extraction_rejects_shadow_and_truthy_surveillance():
    from app.backtest.analytical import _earnings_schedule, _surveillance
    from app.domain.models import ObservationKind
    from tests.integration.test_historical_analytical_replay import metadata_observation
    for fn, payload in ((_earnings_schedule, {"earnings_scheduled_at": g.ASOF}),
                        (_surveillance, {"asm_stage": 0})):
        raw = metadata_observation("bad", "candidate", ObservationKind.CORPORATE_EVENT,
                                   payload | {"registry_version": V2_VERSION}, g.ASOF)
        with pytest.raises(GateVersionBlocked): fn(SimpleNamespace(observations=(raw,)), "candidate")
    with pytest.raises(GateVersionBlocked): evaluate(g.inputs(surveillance=replace(g.surveillance(), authoritative="false")))


def test_score_guards_cannot_be_bypassed_through_gate_one():
    from tests.unit.test_decision_score import complete, score
    from app.scoring.engine import BASE_STATE_SCORES
    from app.diagnostics.downstream import classify_score_input
    for value in variants():
        card = score(complete()+(value,))
        assert card.final_score is None
        result = evaluate(g.inputs(raw_decision_score=card.final_score), context=ActionContext.ROTATE_IN)
        assert result.decisions[0].outcome is GateOutcome.INSUFFICIENT_DATA
    one = complete()[0]
    unknown = replace(one, record=replace(one.record, result="READY_FROM_UNKNOWN_POLICY"))
    assert classify_score_input(unknown, registry_version=V1, state_scores=BASE_STATE_SCORES).value is None


def test_current_scope_and_all_six_policy_asts_unchanged():
    changed = set(subprocess.check_output(["git", "diff", BASELINE, "--name-only", "--", "app"], text=True).splitlines())
    assert changed <= PERMITTED_APP
    old = ast.parse(subprocess.check_output(["git", "show", BASELINE+":app/gates/engine.py"], text=True, encoding="utf-8"))
    new = ast.parse(Path("app/gates/engine.py").read_text(encoding="utf-8"))
    def policies(tree):
        engine = next(x for x in tree.body if isinstance(x, ast.ClassDef) and x.name == "ExecutionGateEngine")
        return {x.name: ast.dump(x) for x in engine.body if isinstance(x, ast.FunctionDef) and x.name != "evaluate"}
    assert policies(old) == policies(new)
    for path in ("app/gates/production_policy.py", "app/scoring/engine.py", "app/diagnostics/downstream.py",
                 "app/rotation/engine.py", "app/portfolio/sell_side_policy.py", "app/portfolio/engine.py",
                 "app/diagnostics/brain_lineage.py", "app/registry/canonical.py", "app/registry/versioned.py"):
        assert Path(path).read_text(encoding="utf-8") == subprocess.check_output(["git", "show", BASELINE+":"+path], text=True, encoding="utf-8")
    tree = ast.parse(Path("app/gates/version_compatibility.py").read_text(encoding="utf-8"))
    imports = [node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)]
    assert not any(x.startswith(("app.portfolio", "app.storage", "app.api", "app.runtime", "app.providers", "app.rotation")) for x in imports)
    calls = {ast.unparse(node.func) for node in ast.walk(tree) if isinstance(node, ast.Call)}
    assert not calls & {"open", "datetime.now", "datetime.utcnow", "sqlite3.connect", "requests.get", "requests.post"}


def test_adapter_rejects_every_cross_registry_score_before_selection_or_write():
    from app.portfolio.canonical_six_gates_activation import CanonicalPortfolioSixGatesActivator
    from app.intelligence.six_gates_evidence import SixGatesEvidenceAdapter
    from app.universe_analysis.service import _gates
    class Repository:
        def list_canonical_decision_scorecards(self, *args): return variants()
        def __getattr__(self, name): pytest.fail("unexpected repository operation: "+name)
    activator = CanonicalPortfolioSixGatesActivator(governance=Repository(), engine=None)
    with pytest.raises(GateVersionBlocked): activator.materialize(execution_as_of=g.ASOF)
    for value in variants():
        source = SimpleNamespace(list_stored_six_gates_evaluations=lambda *a, **kw: (value,))
        with pytest.raises(GateVersionBlocked): SixGatesEvidenceAdapter(source).artifacts("NSE:ISOLATED", as_of=g.ASOF)
        with pytest.raises(GateVersionBlocked): _gates(None, value, (), None, g.ASOF, None)


def test_historical_candidate_incumbent_and_nested_score_cannot_be_unwrapped():
    from app.backtest.portfolio_gates import HistoricalPortfolioGateReplayService
    from app.backtest.analytical import HistoricalAnalyticalReplayService
    class NoUse:
        def __getattr__(self, name): pytest.fail("unexpected repository operation: "+name)
    service = HistoricalPortfolioGateReplayService(NoUse(), g.CALENDAR)
    for value in variants():
        for field in ("run", "candidate", "original", "state", "contexts"):
            args = dict(run=None, candidate=None, original=None, state=None, contexts=(),
                        evaluation_timestamp=g.ASOF, gate_config=g.CONFIG)
            args[field] = (value,) if field == "contexts" else value
            with pytest.raises(GateVersionBlocked): service.evaluate_frozen(**args)
        with pytest.raises(GateVersionBlocked):
            HistoricalAnalyticalReplayService._gates(None, None, None, "NSE:A", g.ASOF, value, (), None)
        with pytest.raises(GateVersionBlocked): require_gate_source(SimpleNamespace(components=(value,)))
    for value in (dict(core_state="READY", component_states=()), SimpleNamespace(core_state="READY")):
        with pytest.raises(GateVersionBlocked): require_gate_source(value)


def test_reference_cycle_rejected_and_tamper_never_repaired_to_eligible():
    value = SimpleNamespace(components=())
    value.components = (value,)
    with pytest.raises(GateVersionBlocked, match="CYCLE"): require_gate_source(value)
    b = binding()
    object.__setattr__(b, "fingerprint", "sha256:"+"f"*64)
    with pytest.raises(GateVersionBlocked, match="FINGERPRINT"): evaluate(lineage=b)


def test_audit_inventory_and_receipt_replay_exactly():
    from scripts.audit_fundamental_v2_gates import audit, inventory
    base = Path("docs/architecture")
    value = audit()
    assert value == audit()
    assert json.loads(json.dumps(inventory())) == json.loads((base/"FUNDAMENTAL_V2_SIX_GATES_VERSION_INVENTORY.json").read_text())
    assert json.loads(json.dumps(value)) == json.loads((base/"FUNDAMENTAL_V2_SIX_GATES_VERSION_RECEIPT.json").read_text())
    assert value["fingerprint"] == content_fingerprint({k: v for k, v in value.items() if k != "fingerprint"})
    assert value["replay_case_count"] == 21
    assert len(value["gates"]) == 6
    assert all(row["v1_replay_equal"] and not row["shadow_accepted"] for row in value["gates"])
