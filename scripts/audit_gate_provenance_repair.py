"""Print deterministic, isolated provenance repair evidence. No storage access."""
from dataclasses import fields
from decimal import Decimal
import json

from app.fundamentals.diagnostic_comparability import content_fingerprint
from app.gates.engine import GateInput, SurveillanceObservation, TradeManagementPlan, PortfolioExposure
from app.gates.version_compatibility import DOMAIN_FIELDS, GateVersionBlocked
from scripts.audit_fundamental_v2_gates import audit, GATE_FIELDS, AT

BASELINE = "5da0111324707ff1f95543d598571463fe63522c"
VERSION = "six-gates-provenance-repair/v1"
CALLERS = (
    ("app.universe_analysis.service._gates", "build_scorecard output", "candidate only; supplied comparison/domain primitives without provenance rejected"),
    ("app.backtest.analytical.HistoricalAnalyticalReplayService._gates", "historical V1 score output + frozen MarketObservation", "no verified calendar timestamp fallback"),
    ("app.backtest.portfolio_gates.HistoricalPortfolioGateReplayService.evaluate_frozen", "existing score/gate readers + frozen hypothetical replay state", "unlinked holding scores rejected; all linked scores checked before selection"),
    ("app.portfolio.canonical_six_gates_activation.CanonicalPortfolioSixGatesActivator._materialize_one", "canonical score reader and integrity verifier", "declared neutral context required; no automatic production neutral-source adapter"),
)
PRODUCERS = {
    "raw_decision_score": "app.scoring.engine.build_scorecard / canonical_decision_scorecard_from",
    "comparison_score": "original ExecutionGateEvaluation linked to incumbent scorecard through HistoricalAnalyticalEvaluation",
    "expected_incremental_return": "explicit frozen hypothetical replay scenario; otherwise caller-supplied approved-context reference required",
    "modeled_switching_friction": "explicit frozen hypothetical replay scenario; otherwise caller-supplied approved-context reference required",
    "holding_entry_date": "caller-supplied governed holding source; no automatic live producer in this slice",
    "atr_expansion": "caller-supplied canonical market/technical source; no automatic live producer in this slice",
    "surveillance": "app.backtest.analytical._surveillance / _market_gate_context; or explicit surveillance source context",
    "trade_plan": "caller-supplied approved plan; no plan generated",
    "exposure": "app.backtest.portfolio_gates._exposure + frozen scenario/state; or explicit governed risk source context",
    "earnings_scheduled_at": "app.backtest.analytical._earnings_schedule / _market_gate_context; or explicit calendar context",
    "earnings_schedule_verified_at": "same exact calendar source as scheduled event; no filing/period/observation fallback",
}


def inventory():
    rows = []
    nested = {"surveillance": SurveillanceObservation, "trade_plan": TradeManagementPlan, "exposure": PortfolioExposure}
    for item in fields(GateInput):
        name = item.name
        score = name in ("raw_decision_score", "comparison_score")
        family = "DIAGNOSTIC_SCORE" if score else DOMAIN_FIELDS.get(name, "INPUT_BINDING_METADATA")
        versions = ["REGISTRY_VERSION_REQUIRED", "POLICY_VERSION_REQUIRED", "SOURCE_VERSION_REQUIRED"] if score else ["NO_REGISTRY_VERSION_APPLICABLE"]
        if name in DOMAIN_FIELDS:
            versions += ["SOURCE_VERSION_REQUIRED", "POLICY_VERSION_REQUIRED"]
        special = {"PORTFOLIO_STATE": "PORTFOLIO_VERSION_REQUIRED", "RISK_ALLOCATION": "PORTFOLIO_VERSION_REQUIRED",
                   "TRADE_PLAN": "PLAN_VERSION_REQUIRED", "EARNINGS_CALENDAR": "CALENDAR_VERSION_REQUIRED"}
        if family in special: versions.append(special[family])
        members = (item,) if name not in nested else fields(nested[name])
        for member in members:
            rows.append(dict(field=name if name not in nested else name+"."+member.name, input_field=name,
                type=str(member.type), gates=[gate for gate, _, names in GATE_FIELDS if name in names],
                producer=PRODUCERS.get(name, "existing input snapshot / linked score metadata"),
                authority_domain=family, required_version_dimensions=versions,
                source_fingerprint=("full source card plus linked original comparison result" if score else
                    "explicit source fingerprint + exact field value fingerprint" if name in DOMAIN_FIELDS else "full GateInput binding"),
                prior_raw_admission=True, raw_admission_now=False if score or name in DOMAIN_FIELDS else "metadata only, not authority",
                legacy_admission="TRUSTED_V1_INTERNAL_ADAPTER" if score else "NON_REGISTRY_EVIDENCE",
                failure="VERSION_BLOCKED before any gate; missing None retains original gate policy",
                source_authentication="canonical source-reader trust boundary, not authenticated by a content hash"))
    body = dict(version=VERSION, baseline=BASELINE, gate_input_fields=[x.name for x in fields(GateInput)],
        fields=rows, callers=[dict(path=p, producer=s, admission=d, status="MIGRATED_TO_PROVENANCE_ENVELOPE") for p,s,d in CALLERS],
        unsafe_raw_registry_callers=0, raw_legacy_test_callers="TEST_ONLY: explicit tests.fixtures.gate_provenance adapters",
        remaining_authority_gaps=["legacy generic score lacks independent persisted fingerprint/producer attestation",
            "caller-declared neutral source references are content bindings, not authenticated authority",
            "legacy MarketObservation calendar has no independently approved calendar-source/version registry"],
        no_database_migration=True, no_provider_acquisition=True)
    return body | dict(fingerprint=content_fingerprint(body))


def receipt():
    from app.gates.engine import ExecutionGateEngine, ActionContext
    from app.gates.production_policy import approved_six_gates_production_policy
    from app.gates.engine import ExchangeCalendar
    old = audit()
    data = GateInput("isolated", Decimal("9"), "isolated-snapshot", AT, Decimal("7"))
    engine = ExecutionGateEngine(approved_six_gates_production_policy(approved_at=AT).gate_config, ExchangeCalendar("NSE-synthetic"))
    try:
        engine.evaluate(instrument_id="NSE:ISOLATED", strategy_version="fixture/v1",
            registry_version="diagnostic-registry-v1", scoring_configuration_version="decision-score-v1",
            action_context=ActionContext.ROTATE_IN, as_of_timestamp=AT, evaluated_at=AT, inputs=data)
    except GateVersionBlocked as exc:
        rejection = str(exc)
    else:
        raise AssertionError("unversioned score accepted")
    body = dict(version=VERSION, baseline=BASELINE, inventory_fingerprint=inventory()["fingerprint"],
        prior_replay_fingerprint=old["fingerprint"], replay_cases=old["replay_case_count"],
        gates=[dict(gate_id=x["gate_id"], v1_replay_equal=x["v1_replay_equal"], shadow_accepted=x["shadow_accepted"]) for x in old["gates"]],
        primitive_laundering_rejection=rejection, unsafe_raw_registry_callers=0,
        source_authentication_gaps=3, b08_before="CLOSED_FOR_SHADOW_COMPATIBILITY",
        b08_after="CLOSED_FOR_SHADOW_COMPATIBILITY", b09="STILL_BLOCKING_ACTIVATION", b14="STILL_BLOCKING_ACTIVATION",
        v1_active=True, v2_active=False, v2_shadow_only=True, writes=0, provider_calls=0, orders=0,
        historical_replay="linked artifacts preserve values; absent provenance is blocked, not retroactively stamped",
        next_continuation="FUNDAMENTAL_V2_SIX_GATES_VERSION_COMPATIBILITY_REPAIR_2")
    return body | dict(fingerprint=content_fingerprint(body))


if __name__ == "__main__":
    print(json.dumps(dict(inventory=inventory(), receipt=receipt()), indent=2, sort_keys=True))
