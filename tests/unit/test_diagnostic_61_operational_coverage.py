"""Coverage metadata is not a second registry, rule engine or authority."""
from copy import deepcopy
from datetime import UTC, datetime, timedelta, timezone
import inspect
import json

import pytest

from app.registry.canonical import DIAGNOSTIC_RULES
from app.universe_analysis.technical_diagnostic_input import technical_diagnostic_rule_requirements
from scripts import audit_diagnostic_61_operational_coverage as audit
from tests.unit.test_radar_diagnostic_orchestration import _accepted

AT = datetime(2026,9,10,tzinfo=UTC)


def fixture():
    # Synthetic counts prove the projection, not production coverage.
    measured = {"sector":{"aligned_rule_2_3_inputs":2,"technical_denominator":10},
                "universe_denominator":12,"benchmark_input_ready":True}
    technical = {"securities_with_certified_daily_and_weekly_input":10,
        "rules":{str(r.rule_id):{"states":{"READY":10},"minimum_daily_observations":r.minimum_daily_observations,
            "minimum_weekly_observations":r.minimum_weekly_observations} for r in technical_diagnostic_rule_requirements()}}
    return measured, technical


def artifact():
    m,t=fixture()
    return audit.build_artifact(measured=m,technical=t,as_of=AT)


def test_exact_canonical_61_names_purpose_and_axes_are_not_an_independent_registry():
    value=artifact()
    assert len(value["records"])==61
    for row, definition in zip(value["records"],DIAGNOSTIC_RULES,strict=True):
        assert row["rule_id"]==definition.rule_id
        assert row["rule_name"]==definition.canonical_name
        assert row["purpose"]==definition.purpose
        assert row["category"]==definition.category
        assert len(row["axes"])==16
        assert row["axes"]["EVALUATOR_READY"]=="READY"
    assert 62 not in {r["rule_id"] for r in value["records"]}
    assert all(sum(counts.values())==61 for counts in value["summary"].values())


def test_fingerprint_is_deterministic_order_independent_and_serialization_complete():
    first=artifact()
    m,t=fixture()
    second=audit.build_artifact(measured=dict(reversed(list(m.items()))),technical=t,
        as_of=AT.astimezone(timezone(timedelta(hours=5,minutes=30))))
    assert first==second
    audit.validate_artifact(json.loads(audit.encoded(first)))
    altered=deepcopy(first);altered["records"][58]["limitations"]="silently repaired"
    with pytest.raises(ValueError,match="FINGERPRINT_MISMATCH"): audit.validate_artifact(altered)
    altered=deepcopy(first);altered["records"].pop()
    altered["fingerprint"]=audit.fingerprint({k:v for k,v in altered.items() if k!="fingerprint"})
    with pytest.raises(ValueError,match="REGISTRY_MISMATCH"): audit.validate_artifact(altered)


def test_missing_counts_are_null_not_zero_and_missing_is_not_inapplicable():
    rows={r["rule_id"]:r for r in artifact()["records"]}
    assert rows[16]["coverage"]["certified_input_ready_count"] is None
    assert rows[21]["operational_state"]=="NOT_READY"
    assert rows[21]["operational_state"]!="NOT_APPLICABLE"
    m,t=fixture();t["rules"]["10"]["states"]={"NOT_READY":10}
    value=audit.build_artifact(measured=m,technical=t,as_of=AT)
    assert value["records"][9]["coverage"]["certified_input_ready_count"]==0


def test_ready_price_component_never_becomes_full_valuation_or_hybrid_coverage():
    rows={r["rule_id"]:r for r in artifact()["records"]}
    for number in (29,31,32,34,35,55,56,57,59,60,61):
        assert rows[number]["coverage"]["certified_input_ready_count"] is None
        component=rows[number]["timeframe_policy"]["daily_weekly_component_audit_excludes_benchmark_sector_join"]
        assert component["states"]["READY"]==10  # synthetic component only
    assert rows[29]["axes"]["CURRENT_DESCRIPTIVE_READY"]=="PARTIAL"


def test_horizon_definition_is_frozen_183_and_runtime_nonactivation_is_separate():
    value=artifact();policy=audit.canonical_policy()
    assert value["horizon_rows"]==183 and value["policy_content_fingerprint"]==audit.POLICY_FP
    assert [r["horizon_policy"]["source_cells_unchanged"] for r in value["records"]]==policy["rule_horizon_rows"]
    assert all(r["horizon_policy"]["definition"]=="READY" for r in value["records"])
    assert all(r["horizon_policy"]["runtime_consumption"]=="PARTIAL" for r in value["records"])
    assert value["records"][13]["horizon_policy"]["source_cells_unchanged"]["positional"]=="POLICY_UNSET"


def test_rule_6_14_35_57_limitations_survive_abundant_daily_data():
    rows={r["rule_id"]:r for r in artifact()["records"]}
    for n,reason in ((6,"PEER_COHORT_NOT_READY"),(14,"TIMEFRAME_DATA_NOT_READY"),
                     (35,"NAMED_VWAP_SEMANTICS_UNAVAILABLE"),(57,"EVENT_EVIDENCE_NOT_READY")):
        assert reason in rows[n]["blockers"]
        assert rows[n]["operational_state"]!="OPERATIONAL_CURRENT_DESCRIPTIVE"
    assert rows[14]["timeframe_policy"]["other_timeframes"].startswith("NOT_READY")


def test_financial_ownership_and_per_dependency_temporal_boundaries_remain_distinct():
    rows={r["rule_id"]:r for r in artifact()["records"]}
    assert "6 annual" in rows[16]["input_dependencies"]
    assert "5 quarter-only" in rows[25]["input_dependencies"]
    assert "Quarterly holdings != daily flows != block/bulk transactions" in rows[22]["limitations"]
    assert rows[16]["axes"]["STRICT_HISTORICAL_PIT_READY"]=="PARTIAL"
    assert rows[10]["axes"]["STRICT_HISTORICAL_PIT_READY"]=="NOT_READY"
    assert rows[16]["axes"]["INPUT_CONTRACT_READY"]=="PARTIAL"
    assert "SOURCE_CONTRACT_INCOMPLETE" in rows[29]["blockers"]


def test_radar_lead_joins_all_61_readiness_rows_without_execution_or_horizon_rewrite():
    receipt=_accepted(); rows={r["rule_id"]:r for r in artifact()["records"]}
    assert {r.rule_id for r in receipt.rule_references}==set(rows)
    assert len(receipt.rule_references)==61
    assert receipt.evaluated_rule_count==sum(r.readiness.value=="EVALUATED" for r in receipt.rule_references)
    assert receipt.actionability.value=="WATCH_ONLY"
    assert receipt.execution_status.value=="NON_EXECUTABLE"
    by_rule={r.rule_id:r for r in receipt.rule_references}
    assert by_rule[59].diagnostic_result=="INSUFFICIENT_DATA"
    for n in (35,57): assert by_rule[n].diagnostic_result=="INSUFFICIENT_DATA"
    assert all("NOT_INVOKED_IN_THIS_SLICE" in r["downstream"]["status"] for r in rows.values())


def test_audit_has_no_database_or_trading_write_path_or_current_time():
    source=inspect.getsource(audit)
    for forbidden in (".save(","INSERT INTO","UPDATE ","DELETE FROM",".now(",".utcnow(","place_order(","build_scorecard(","ExecutionGateEngine("):
        assert forbidden not in source
    assert "?mode=ro" in source and "PRAGMA query_only=ON" in source
    with pytest.raises(ValueError,match="TIMEZONE_REQUIRED"):
        m,t=fixture();audit.build_artifact(measured=m,technical=t,as_of=AT.replace(tzinfo=None))


def test_latest_effective_audit_inputs_do_not_arbitrarily_resolve_ties():
    with pytest.raises(ValueError,match="AMBIGUOUS_LATEST"):
        audit._latest((("x",AT,1),("x",AT,2)),lambda v:v[0],lambda v:v[1],AT)
    assert audit._latest((("x",AT+timedelta(seconds=1),1),),lambda v:v[0],lambda v:v[1],AT)=={}
