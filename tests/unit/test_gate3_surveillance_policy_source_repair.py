"""Governance audit proofs; no collector, source admission or live source parser.

The list fixture below is a conditional specification example only. It does not
establish completeness of a real HTTP response or confer production authority.
"""
from dataclasses import fields, replace
from datetime import timedelta
from decimal import Decimal
import csv
import gzip
import io
import json
from pathlib import Path
import subprocess

import pytest

from app.fundamentals.diagnostic_comparability import canonical_json, content_fingerprint
from app.gates.engine import (
    ActionContext, ExecutionEligibility, ExecutionGateEngine, GateOutcome,
    SurveillanceObservation,
)
from app.gates.source_readiness import GateSourceNotReady
from app.historical.nse_mii_security_master import extract_nse_mii_security_master
from tests.fixtures.gate_provenance import synthetic_evaluate
from tests.unit.test_gate_authority_closure import attack
from tests.unit.test_gate_source_authority import evaluate, producer
from tests.unit.test_nse_historical_mii_security_master import HEADERS, _response
from tests.unit.test_nse_session_identity import (
    D, _extraction, _lineage, activate_nse_mii_snapshot,
    NseSessionIdentityResolutionStatus, NseSessionPointIdentityStore,
    resolve_nse_session_identity, SQLiteCoreApiSnapshotRepository,
)
from tests.unit.test_six_gates_production_policy import CALENDAR, T, _input, _policy


RECEIPT_PATH = Path("docs/architecture/GATE3_SURVEILLANCE_POLICY_SOURCE_REPAIR_V1.json")
RECEIPT = json.loads(RECEIPT_PATH.read_text(encoding="utf-8"))
REQUIREMENTS = tuple(RECEIPT["conditional_fixture_contract"]["nonblocking_list_requirements"])


def _synthetic(inputs, context=ActionContext.FRESH_ENTRY):
    return synthetic_evaluate(
        ExecutionGateEngine(_policy().gate_config, CALENDAR),
        instrument_id="NSE:TEST", strategy_version="v1", registry_version="v1",
        scoring_configuration_version="v1", action_context=context,
        as_of_timestamp=T, evaluated_at=T, inputs=inputs,
    )


def _gate3(result):
    return next(x for x in result.decisions if x.gate_id == "GATE_3_SURVEILLANCE")


@pytest.mark.parametrize("field", ("asm_stage", "gsm_stage", "circuit_limit"))
def test_missing_frozen_component_prevents_synthetic_six_gate_liveness(field):
    result = _synthetic(_input(surveillance=replace(_input().surveillance, **{field: None})))
    assert _gate3(result).outcome is GateOutcome.INSUFFICIENT_DATA
    assert result.eligibility is ExecutionEligibility.INSUFFICIENT_DATA
    assert len(result.decisions) == 6
    assert all(x.outcome is GateOutcome.PASS for x in result.decisions if x.gate_id != "GATE_3_SURVEILLANCE")


def test_three_fields_can_pass_but_security_status_is_not_represented_or_verified():
    contract = _policy().surveillance_source
    assert contract.coverage == ("ASM", "GSM", "PRICE_BAND", "SECURITY_STATUS")
    assert not contract.absence_is_pass and contract.latest_eligible_completed_session_required
    assert {f.name for f in fields(SurveillanceObservation)} == {
        "id", "effective_at", "source", "authoritative", "asm_stage", "gsm_stage",
        "circuit_limit", "evidence_ids",
    }
    with pytest.raises(TypeError):
        replace(_input().surveillance, security_status=None)
    result = _synthetic(_input())
    assert len(result.decisions) == 6 and all(x.outcome is GateOutcome.PASS for x in result.decisions)
    assert result.eligibility is ExecutionEligibility.EXECUTABLE
    assert _gate3(result).confidence == 1.0  # Constant annotation, not measured source confidence.
    assert "NO_ACTION_OR_ORDER_CREATED" in result.warnings
    assert RECEIPT["frozen_runtime"]["synthetic_liveness_is_official_proof"] is False


@pytest.mark.parametrize("change", ({"asm_stage": 2}, {"gsm_stage": 1}, {"circuit_limit": Decimal(".05")}))
def test_exact_thresholds_block_without_adding_security_status_predicate(change):
    result = _synthetic(_input(surveillance=replace(_input().surveillance, **change)))
    assert _gate3(result).outcome is GateOutcome.FAIL
    assert _gate3(result).confidence is None
    assert result.eligibility is ExecutionEligibility.BLOCKED


def test_missing_fields_precede_asm_block_but_other_gate_fail_dominates_aggregate():
    inputs = _input(surveillance=replace(_input().surveillance, asm_stage=2, gsm_stage=None))
    assert _synthetic(inputs).eligibility is ExecutionEligibility.INSUFFICIENT_DATA
    failed = _synthetic(replace(inputs, trade_plan=replace(inputs.trade_plan, t1_reduction=Decimal(".4"))))
    assert _gate3(failed).outcome is GateOutcome.INSUFFICIENT_DATA
    assert failed.eligibility is ExecutionEligibility.BLOCKED


@pytest.mark.parametrize("context", tuple(ActionContext))
def test_gate3_has_no_action_context_exemption(context):
    assert _gate3(_synthetic(_input(surveillance=None), context)).outcome is GateOutcome.INSUFFICIENT_DATA


@pytest.mark.parametrize("observation", (
    None,
    replace(_input().surveillance, authoritative=False),
    replace(_input().surveillance, effective_at=T + timedelta(microseconds=1)),
    replace(_input().surveillance, effective_at=T - timedelta(days=8)),
))
def test_frozen_formula_missing_unverified_future_and_stale_are_not_clear(observation):
    engine = ExecutionGateEngine(_policy().gate_config, CALENDAR)
    # Direct private formula audit isolates its behavior from earlier source rejection.
    decision = engine._surveillance(T, _input(surveillance=observation), ())
    assert decision.outcome is GateOutcome.INSUFFICIENT_DATA


def test_four_session_age_is_inclusive_not_a_current_file_certificate():
    engine = ExecutionGateEngine(_policy().gate_config, CALENDAR)
    four, five = T - timedelta(days=7), T - timedelta(days=8)
    assert CALENDAR.sessions_between(four.date(), T.date()) == 4
    assert CALENDAR.sessions_between(five.date(), T.date()) == 5
    for effective, expected in ((four, GateOutcome.PASS), (five, GateOutcome.INSUFFICIENT_DATA)):
        decision = engine._surveillance(T, _input(surveillance=replace(_input().surveillance, effective_at=effective)), ())
        assert decision.outcome is expected


def test_real_source_authority_rejects_fabricated_clear_before_any_formula(monkeypatch):
    args, _, _ = attack("surveillance")
    monkeypatch.setattr(ExecutionGateEngine, "_surveillance", lambda *_: pytest.fail("unadmitted formula ran"))
    with pytest.raises(GateSourceNotReady, match="GATE_DOMAIN_AUTHORITY_UNAVAILABLE:surveillance"):
        evaluate(args, producer())


def _conditional_list_fixture(family, stage, proof):
    """Test-only truth table of hypothetical complete-source premises, not parsing."""
    if not proof["conflict_free"]:
        return "CONFLICTED"
    positive = stage is not None and stage >= (2 if family == "ASM" else 1)
    required = (RECEIPT["conditional_fixture_contract"]["positive_requirements"]
                if positive else REQUIREMENTS)
    if not all(proof[key] for key in required):
        return "UNKNOWN"
    return "BLOCKING_COMPONENT" if positive else "NON_BLOCKING_COMPONENT"


@pytest.mark.parametrize("family", ("ASM", "GSM"))
@pytest.mark.parametrize("missing", REQUIREMENTS)
def test_asm_gsm_absence_requires_every_complete_scope_pit_admission_premise(family, missing):
    proof = dict.fromkeys(REQUIREMENTS, True)
    assert _conditional_list_fixture(family, None, proof) == "NON_BLOCKING_COMPONENT"
    proof[missing] = False
    expected = "CONFLICTED" if missing == "conflict_free" else "UNKNOWN"
    assert _conditional_list_fixture(family, None, proof) == expected


@pytest.mark.parametrize("family,stage", (("ASM", 2), ("GSM", 1)))
def test_positive_component_does_not_need_negative_scope_completeness(family, stage):
    proof = dict.fromkeys(REQUIREMENTS, True)
    proof.update(complete_scope=False, full_file_or_all_pages=False)
    assert _conditional_list_fixture(family, stage, proof) == "BLOCKING_COMPONENT"
    proof["exact_security"] = False
    assert _conditional_list_fixture(family, stage, proof) == "UNKNOWN"


def test_stage_zero_shortlisting_is_not_absence_and_http_success_is_not_proof():
    proof = dict.fromkeys(REQUIREMENTS, True)
    shortlisted = {"indicator": 50, "asm_stage": 1, "gsm_stage": 0, "listed": True}
    assert _conditional_list_fixture("GSM", shortlisted["gsm_stage"], proof) == "NON_BLOCKING_COMPONENT"
    assert shortlisted["listed"] is True and shortlisted["indicator"] != shortlisted["gsm_stage"]
    proof = dict.fromkeys(REQUIREMENTS, False) | {"schema_valid": True, "http_200": True}
    assert _conditional_list_fixture("ASM", None, proof) != "NON_BLOCKING_COMPONENT"
    assert RECEIPT["conditional_fixture_contract"]["component_nonblocking_is_gate_pass"] is False


@pytest.mark.parametrize("status,eligible", (("2", "1"), ("3", "0"), ("6", "1"), ("99", "")))
def test_current_mii_parser_preserves_status_but_does_not_invent_gate_status_or_band(status, eligible):
    header = HEADERS.replace("Ignored", "PricRg,ElgbltyNrmlMkt")
    raw = f"100,EXACT,EQ,Exact Ltd,INE000A01001,{status},100,0,EQ,EQUITY,5,{eligible}\n"
    body = gzip.compress((header + raw).encode())
    row = extract_nse_mii_security_master(_response(body=body)).rows[0]
    assert row.normal_market_status_raw == status
    assert (row.symbol, row.isin, row.series, row.security_code) == ("EXACT", "INE000A01001", "EQ", "100")
    assert not {"circuit_limit", "price_band", "execution_eligible", "security_status", "normal_market_eligibility"} & {f.name for f in fields(row)}
    changed = gzip.compress((header + raw.replace(",EQUITY,5,", ",EQUITY,10,")).encode())
    other = extract_nse_mii_security_master(_response(body=changed)).rows[0]
    assert row.raw_row_fingerprint != other.raw_row_fingerprint  # Hash binds ignored data; does not recover it.
    assert row.historical_known_at is None


def test_price_export_schema_numeric_units_and_series_are_not_a_universal_pricrg_decoder():
    # Synthetic values in the inspected official schema; no live request in tests.
    rows = tuple(csv.DictReader(io.StringIO(
        "Symbol,Series,Security Name,Band,Remarks\nEXACT,EQ,Example,5,-\nEXACT,BE,Example,2,-\n"
    )))
    assert list(rows[0]) == RECEIPT["official_sources"][2]["columns"]
    assert Decimal(rows[0]["Band"]) / Decimal("100") == Decimal(".05")
    assert rows[0]["Symbol"] == rows[1]["Symbol"] and rows[0]["Series"] != rows[1]["Series"]
    assert RECEIPT["official_sources"][3]["universal_pricrg_percent_decoder_proven"] is False
    assert RECEIPT["conditional_fixture_contract"]["price_or_status_absent_is_nonblocking"] is False


def test_security_level_match_does_not_select_arbitrary_series_or_repair_conflict(tmp_path):
    repository = SQLiteCoreApiSnapshotRepository(tmp_path / "isolated_identity.sqlite")
    try:
        store = NseSessionPointIdentityStore(repository)
        _, activation = _lineage()
        extraction = _extraction(rows=(
            "100,EXACT,EQ,Exact Ltd,INE000A01001,2,100,0,EQ,EQUITY",
            "101,EXACT,BE,Exact Ltd,INE000A01001,3,100,0,EQ,EQUITY",
        ))
        activate_nse_mii_snapshot(store, activation=activation, snapshot=extraction.snapshot,
                                 rows=extraction.rows, calendar=CALENDAR)
        receipts = store.receipts()
        assert {x.series for x in receipts} == {"EQ", "BE"}
        forward = resolve_nse_session_identity(receipts, session_date=D, symbol="EXACT", isin="INE000A01001")
        reverse = resolve_nse_session_identity(tuple(reversed(receipts)), session_date=D, symbol="EXACT", isin="INE000A01001")
        assert forward == reverse
        assert forward.status is NseSessionIdentityResolutionStatus.EVIDENCE_CONFLICTED
        assert forward.receipt is None
    finally:
        repository.close()


def test_audit_receipt_reproduces_fingerprint_and_does_not_change_prior_measurements():
    payload = {k: v for k, v in RECEIPT.items() if k != "receipt_fingerprint"}
    assert RECEIPT["receipt_fingerprint"] == content_fingerprint(payload)
    assert canonical_json(RECEIPT) == canonical_json(json.loads(canonical_json(RECEIPT)))
    prior = json.loads(Path("docs/architecture/GATE3_SURVEILLANCE_SOURCE_READINESS_V1.json").read_text())
    assert RECEIPT["inherited_universe"]["source_receipt_fingerprint"] == prior["receipt_fingerprint"]
    measured = RECEIPT["inherited_universe"]
    assert measured["exact_local_isin_matches"] + measured["outside_local_scope"] == measured["unique_surveillance_isins"] == 314
    assert measured["resolved_target_series"] == 0 and measured["unresolved_target_series"] == 314
    assert RECEIPT["final_option"] == "D" and RECEIPT["final_decision"] == "GATE3_POLICY_REMAINS_UNRESOLVED"
    assert not RECEIPT["runtime_producer_active"] and not RECEIPT["production_observation_created"]
    assert all(x["pilot_admission"] == "NOT_READY" for x in RECEIPT["source_readiness"])


def test_repair_keeps_frozen_gate_runtime_and_previous_machine_receipt_unchanged():
    # The later bounded execution-master continuity repair is allowed to add
    # immutable capture admission to the upstream MII module.  It must not
    # alter the frozen Gate-3 evaluator, policy, identity resolver, or the
    # historical source-readiness receipt recorded by this repair.
    for path in (
        "app/gates/engine.py", "app/gates/production_policy.py", "app/gates/source_authority.py",
        "app/gates/version_compatibility.py", "app/gates/source_readiness.py",
        "app/historical/nse_session_identity.py",
        "docs/architecture/GATE3_SURVEILLANCE_SOURCE_READINESS_V1.json",
    ):
        expected = subprocess.check_output(["git", "show", RECEIPT["baseline_commit"] + ":" + path], text=True, encoding="utf-8")
        assert Path(path).read_text(encoding="utf-8") == expected
