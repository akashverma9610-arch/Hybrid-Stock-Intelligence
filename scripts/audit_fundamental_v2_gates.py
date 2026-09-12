"""Read-only deterministic gate inventory/replay; no DB, provider or action call.

Prints JSON only. Fixtures are synthetic and use the existing approved policy.
No report file is written and no production gate evaluation is persisted.
"""
from dataclasses import asdict, fields, replace
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
import ast
import json
from pathlib import Path
import subprocess
import sys
from types import ModuleType

from app.fundamentals.diagnostic_comparability import content_fingerprint
from app.gates.engine import (ActionContext, ExchangeCalendar, ExecutionGateEngine, GateInput,
                             PortfolioExposure, SurveillanceObservation, TradeManagementPlan)
from app.gates.production_policy import approved_six_gates_production_policy
from app.gates.version_compatibility import GateVersionBlocked, VERSION, gate_input_fingerprint
from app.registry.canonical import DIAGNOSTIC_REGISTRY_VERSION
from app.registry.versioned import V2_VERSION

BASELINE = "c182b6421303f5f1cb8df3517be36872e72d5602"
ROOT = Path(__file__).resolve().parents[1]
GATE_FIELDS = (
    ("GATE_1_ROTATION", "_rotation", ("raw_decision_score", "comparison_score", "expected_incremental_return", "modeled_switching_friction")),
    ("GATE_2_VELOCITY", "_velocity", ("holding_entry_date", "atr_expansion")),
    ("GATE_3_SURVEILLANCE", "_surveillance", ("surveillance",)),
    ("GATE_4_TRADE_PLAN", "_plan", ("trade_plan",)),
    ("GATE_5_HEAT", "_heat", ("exposure",)),
    ("GATE_6_EARNINGS", "_blackout", ("earnings_scheduled_at", "earnings_schedule_verified_at")),
)
AT = datetime(2026, 8, 31, 18, tzinfo=UTC)
FAMILIES = (
    ("V1_DECISION_SCORE", "INCUMBENT_COMPARISON_SCORE", "APPROVED_FRICTION_INPUTS"),
    ("HOLDING_ENTRY_SESSION", "ATR_EXPANSION"), ("AUTHORITATIVE_SURVEILLANCE_CIRCUIT",),
    ("APPROVED_TRADE_MANAGEMENT_PLAN",), ("PORTFOLIO_RISK_AND_ALLOCATION",),
    ("VERIFIED_EARNINGS_SCHEDULE", "EXCHANGE_CALENDAR"),
)
MISSING = (
    "Rotation score or economic input absent -> INSUFFICIENT_DATA; non-rotation exemption unchanged",
    "Holding/ATR absent -> INSUFFICIENT_DATA; fresh-entry exemption unchanged",
    "Absent/non-authoritative/future/stale/incomplete -> INSUFFICIENT_DATA",
    "Absent/undefined stop or T1 -> FAIL; unresolved config -> INSUFFICIENT_DATA",
    "Missing equity/risk/allocation -> INSUFFICIENT_DATA",
    "Missing/future verification -> INSUFFICIENT_DATA; existing-position exemptions unchanged",
)


def _source(path):
    return subprocess.check_output(["git", "show", BASELINE+":"+path], cwd=ROOT, text=True, encoding="utf-8")


def _methods(source):
    tree = ast.parse(source)
    engine = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "ExecutionGateEngine")
    return {n.name: n for n in engine.body if isinstance(n, ast.FunctionDef)}


def inventory():
    source = (ROOT/"app/gates/engine.py").read_text(encoding="utf-8")
    methods = _methods(source)
    rows = []
    for index, (gate, method, names) in enumerate(GATE_FIELDS):
        node = methods[method]
        actual = {n.attr for n in ast.walk(node) if isinstance(n, ast.Attribute)
                  and isinstance(n.value, ast.Name) and n.value.id == "data"}
        assert actual == set(names), (gate, actual)
        rows.append(dict(gate_id=gate, entry="app.gates.engine.ExecutionGateEngine.evaluate",
            method=method, input_type="GateInput", input_fields=names, required_evidence_families=FAMILIES[index],
            input_field_types={f.name: str(f.type) for f in fields(GateInput) if f.name in names},
            nested_fields=(() if index not in (2, 3, 4) else tuple(f.name for f in fields(
                (SurveillanceObservation, TradeManagementPlan, PortfolioExposure)[index-2]))),
            calendar_dependency=index in (1, 2, 5),
            aggregate_score_effect="Separate velocity adjustment only" if index == 1 else "No new score calculation",
            upstream_sources=("app.universe_analysis.service._gates", "app.backtest.analytical.HistoricalAnalyticalReplayService._gates",
                "app.backtest.portfolio_gates.HistoricalPortfolioGateReplayService.evaluate_frozen",
                "app.portfolio.canonical_six_gates_activation.CanonicalPortfolioSixGatesActivator._materialize_one"),
            decision_score_dependency=index == 0, portfolio_dependency=index in (0, 1, 4),
            direct_diagnostic_dependency=False, diagnostic_lineage="Opaque diagnostic_ids; V1 source guard before extraction",
            missing_behavior=MISSING[index], policy_version_source="ExecutionGateConfig.version",
            strategy_version_source="evaluate.strategy_version; plan has its original strategy/configuration references",
            as_of="Exact input snapshot cutoff; existing per-gate PIT/freshness/calendar semantics preserved",
            prior_risk="Top-level V2 guard only; nested duck types and scalar extraction could lose registry provenance",
            current_guard="Nominal input/field validation plus explicit registry admission before all gate calculations",
            version_retention="Legacy scalar inputs have no native registry; optional GateEvidenceContext retains typed dependency lineage",
            fallback="No cross-registry selection; unknown explicit versions rejected; exact legacy label v1 retained",
            policy_ast_fingerprint=content_fingerprint(ast.dump(node))))
    return dict(inventory_version=VERSION, baseline_commit=BASELINE,
                gate_input_fields=tuple(f.name for f in fields(GateInput)), gates=rows,
                durable_lineage_limitation="No migration: legacy scalar-to-source linkage is not retroactively invented",
                required_incompatible_evidence="Whole evaluation raises controlled VERSION_BLOCKED; no gate result emitted",
                optional_incompatible_evidence="Conservatively rejected, not silently dropped")


def audit():
    name = "_hsi_frozen_gate_engine"
    old = ModuleType(name); sys.modules[name] = old
    source = _source("app/gates/engine.py")
    exec(compile(source, name, "exec"), old.__dict__)
    current = _methods((ROOT/"app/gates/engine.py").read_text(encoding="utf-8")); prior = _methods(source)
    for _, method, _ in GATE_FIELDS:
        assert ast.dump(current[method]) == ast.dump(prior[method])
    assert _source("app/gates/production_policy.py") == (ROOT/"app/gates/production_policy.py").read_text(encoding="utf-8")
    policy = approved_six_gates_production_policy(approved_at=AT)
    policy.verify_integrity()
    config = policy.gate_config; calendar = ExchangeCalendar("NSE:isolated-calendar")
    value = GateInput("isolated-score", Decimal("9"), "isolated-snapshot", AT, Decimal("7"),
        Decimal("2"), Decimal("1"), date(2026, 8, 3), Decimal("2"),
        SurveillanceObservation("isolated-surveillance", AT, "NSE:synthetic-fixture", True, 0, 0, Decimal(".10")),
        TradeManagementPlan("isolated-plan", config.initial_tranche, config.t1_reduction, True, True, "after T1", "existing conditions", "fixture/v1", config.version),
        PortfolioExposure(Decimal("100000"), Decimal("2000"), Decimal("1000"), Decimal(".10"), Decimal(".20")),
        AT+timedelta(days=20), AT, ("isolated-evidence",), ("isolated-diagnostic",))
    cases = [(context, value) for context in ActionContext]
    for _, _, names in GATE_FIELDS:
        for field in names:
            cases.append((ActionContext.ROTATE_IN, replace(value, **{field: None})))
    cases.extend(((ActionContext.HOLD_EXISTING, replace(value, atr_expansion=Decimal(".1"))),
                  (ActionContext.FRESH_ENTRY, replace(value, surveillance=replace(value.surveillance, asm_stage=2))),
                  (ActionContext.FRESH_ENTRY, replace(value, earnings_scheduled_at=AT+timedelta(days=1)))))
    pairs = []; engine = ExecutionGateEngine(config, calendar)
    for context, data in cases:
        args = dict(instrument_id="NSE:ISOLATED", strategy_version="fixture/v1", registry_version=DIAGNOSTIC_REGISTRY_VERSION,
                    scoring_configuration_version="decision-score-v1", as_of_timestamp=AT, evaluated_at=AT, inputs=data)
        before = old.ExecutionGateEngine(config, calendar).evaluate(**args, action_context=old.ActionContext(context.value))
        from tests.fixtures.gate_provenance import synthetic_evaluate
        after = synthetic_evaluate(engine, **args, action_context=context)
        assert content_fingerprint(before) == content_fingerprint(after)
        pairs.append((context.value, gate_input_fingerprint(data), before, after))
    rows = []
    for index, (gate, _, names) in enumerate(GATE_FIELDS):
        attempts = []
        for field in names:
            try:
                engine.evaluate(instrument_id="NSE:ISOLATED", strategy_version="fixture/v1", registry_version=DIAGNOSTIC_REGISTRY_VERSION,
                    scoring_configuration_version="v1", action_context=ActionContext.FRESH_ENTRY, as_of_timestamp=AT,
                    evaluated_at=AT, inputs=replace(value, **{field: {"registry_version": V2_VERSION, "core_state": "READY", "value": 10}}))
            except GateVersionBlocked as exc:
                attempts.append((field, str(exc), exc.compatibility_state))
            else:
                raise AssertionError("Shadow input was admitted")
        replay = tuple((ctx, fp, content_fingerprint(before.decisions[index]), content_fingerprint(after.decisions[index]))
                       for ctx, fp, before, after in pairs)
        rows.append(dict(gate_id=gate, gate_policy_version=config.version, gate_policy_fingerprint=policy.fingerprint,
            registry_version_accepted=DIAGNOSTIC_REGISTRY_VERSION, shadow_accepted=False,
            required_evidence_families=FAMILIES[index], compatibility_state="V1_ONLY_SHADOW_FORBIDDEN",
            cross_version_rejections=attempts, v1_replay_fingerprint=content_fingerprint(replay), v1_replay_equal=True,
            test_fingerprint=content_fingerprint((replay, attempts))))
    body = dict(receipt_version=VERSION, baseline_commit=BASELINE, as_of=AT.isoformat(), fixture_type="SYNTHETIC_ISOLATED_EXISTING_POLICY",
        replay_case_count=len(pairs), gates=rows, inventory_fingerprint=content_fingerprint(inventory()),
        production_evaluations=0, writes=0, provider_calls=0, orders=0, v1_active=True, v2_active=False,
        b08_status="CLOSED_FOR_SHADOW_COMPATIBILITY", b09_status="STILL_BLOCKING_ACTIVATION", b14_status="STILL_BLOCKING_ACTIVATION")
    return dict(body, fingerprint=content_fingerprint(body))


if __name__ == "__main__":
    print(json.dumps(dict(inventory=inventory(), receipt=audit()), sort_keys=True, indent=2))
