"""Frozen-policy origin and identity audit; no runtime adapter or source fetch.

The joins below are synthetic governance examples, not an admitted producer.
"""
import ast
from dataclasses import fields, replace
from datetime import timedelta
from decimal import Decimal
from hashlib import sha256
import json
from pathlib import Path
import subprocess

import pytest

from app.domain.models import Instrument
from app.fundamentals.diagnostic_comparability import canonical_json, content_fingerprint
from app.gates.engine import ActionContext, ExecutionEligibility, ExecutionGateEngine, GateInput, GateOutcome, SurveillanceObservation
from app.gates.production_policy import (
    approved_six_gates_production_policy, selected_production_gate_engine,
    six_gates_production_policy_fingerprint,
)
from app.gates.source_readiness import GateSourceNotReady
from app.gates.version_compatibility import (
    DOMAIN_FIELDS, GateEvidenceContext, GateVersionBlocked, domain_lineage,
    gate_evidence_context,
)
from app.market_data.models import Exchange, InstrumentIdentity, InstrumentType, ProviderInstrumentMapping
from app.storage.sqlite_governance_repository import SQLiteStrategyGovernanceRepository
from tests.fixtures.gate_provenance import synthetic_evaluate
from tests.unit.test_gate_authority_closure import attack
from tests.unit.test_gate_source_authority import evaluate, producer
from tests.unit.test_nse_session_identity import D, _extraction
from tests.unit.test_six_gates_production_policy import CALENDAR, T, _input


RECEIPT = json.loads(Path("docs/architecture/GATE3_SURVEILLANCE_POLICY_SOURCE_REPAIR_2.json").read_text())
AT = T - timedelta(hours=1)  # 14:30 IST, explicitly inside the synthetic session.
CURRENT_EFFECTIVE = AT - timedelta(hours=5, minutes=15)


def _policy():
    return approved_six_gates_production_policy(approved_at=AT - timedelta(days=10))


def _run(observation):
    inputs = replace(_input(), surveillance=observation, snapshot_as_of_timestamp=AT,
                     earnings_schedule_verified_at=AT)
    return synthetic_evaluate(
        ExecutionGateEngine(_policy().gate_config, CALENDAR), instrument_id="NSE:TEST",
        strategy_version="v1", registry_version="v1", scoring_configuration_version="v1",
        action_context=ActionContext.FRESH_ENTRY, as_of_timestamp=AT, evaluated_at=AT,
        inputs=inputs,
    )


def _blob(revision, path):
    return subprocess.check_output(["git", "show", revision + ":" + path])


def _method(tree, name):
    return next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == name)


def test_original_approved_source_descriptor_is_unchanged_not_a_new_status_rule():
    path = "app/gates/production_policy.py"
    original = _blob(RECEIPT["policy_origin_commit"], path)
    assert original == _blob(RECEIPT["baseline_commit"], path)
    assert Path(path).read_text() == original.decode().replace("\r\n", "\n")
    contract = _policy().surveillance_source
    assert contract.coverage == ("ASM", "GSM", "PRICE_BAND", "SECURITY_STATUS")
    assert contract.latest_eligible_completed_session_required is True
    assert contract.absence_is_pass is False
    assert RECEIPT["security_status"]["decision"] == "S1"
    assert RECEIPT["security_status"]["origin_role"] == "DESCRIPTIVE_SOURCE_FAMILY"


def test_formula_ast_and_exact_substantive_fields_match_original_release():
    original = ast.parse(_blob(RECEIPT["policy_origin_commit"], "app/gates/engine.py"))
    current = ast.parse(Path("app/gates/engine.py").read_text())
    method = _method(current, "_surveillance")
    assert ast.dump(_method(original, "_surveillance")) == ast.dump(method)
    accesses = {n.attr for n in ast.walk(method) if isinstance(n, ast.Attribute)
                and isinstance(n.value, ast.Name) and n.value.id == "item"}
    assert accesses == {"effective_at", "authoritative", "asm_stage", "gsm_stage", "circuit_limit", "evidence_ids"}
    assert RECEIPT["v1_contract"]["required_formula_values"] == ["asm_stage", "gsm_stage", "circuit_limit"]
    assert "security_status" not in {f.name for f in fields(SurveillanceObservation)}
    assert "security_status" not in {f.name for f in fields(GateInput)}
    assert "security_status" not in {f.name for f in fields(GateEvidenceContext)}
    assert "security_status" not in DOMAIN_FIELDS


def test_completed_session_flag_is_not_read_by_formula_or_existing_authority():
    # Generic dataclass serialization includes the flag; this audit checks decision use.
    for path in Path("app/gates").glob("*.py"):
        tree = ast.parse(path.read_text())
        attrs = {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
        assert not attrs & {"latest_eligible_completed_session_required", "security_status"}
    assert RECEIPT["human_approval_provenance"]["timing_clause_verbatim"] == (
        "The observation must correspond to the latest eligible official NSE surveillance state "
        "for the relevant completed trading session."
    )
    assert RECEIPT["timing"]["approved_scope"] == "GATE3_SOURCE_EVIDENCE"
    assert RECEIPT["timing"]["decision"] == "T3"


def test_selected_engine_receives_configuration_not_an_implemented_session_selector():
    class Reader:
        def selected_six_gates_production_policy(self, *, as_of):
            assert as_of == AT
            return _policy()

    engine = selected_production_gate_engine(repository=Reader(), calendar=CALENDAR, as_of=AT)
    assert engine.config == _policy().gate_config
    assert not hasattr(engine, "surveillance_source")
    assert engine.source_authority is None


def test_completed_session_rewording_cannot_repair_an_existing_approval_hash(tmp_path):
    policy = _policy()
    changed = replace(policy, surveillance_source=replace(
        policy.surveillance_source, latest_eligible_completed_session_required=False))
    with pytest.raises(ValueError, match="FINGERPRINT_MISMATCH"):
        changed.verify_integrity()
    rehashed = replace(changed, fingerprint=six_gates_production_policy_fingerprint(changed))
    assert rehashed.fingerprint != policy.fingerprint
    repo = SQLiteStrategyGovernanceRepository(tmp_path / "synthetic_policy.sqlite")
    try:
        repo.save_six_gates_production_policy(policy)
        with pytest.raises(ValueError, match="immutable"):
            repo.save_six_gates_production_policy(rehashed)
        assert repo.selected_six_gates_production_policy(as_of=AT) == policy
    finally:
        repo.close()


@pytest.mark.parametrize("changed", ({"asm_stage": 2}, {"gsm_stage": 1}, {"circuit_limit": Decimal(".05")}))
def test_prior_completed_state_can_miss_a_current_effective_restriction(changed):
    prior = _input().surveillance
    current = replace(prior, effective_at=CURRENT_EFFECTIVE, **changed)
    assert CALENDAR.sessions_between(prior.effective_at.date(), AT.date()) == 1
    assert CURRENT_EFFECTIVE < AT and CURRENT_EFFECTIVE.date() == AT.date()
    old, new = _run(prior), _run(current)
    assert old.decisions[2].outcome is GateOutcome.PASS
    assert old.eligibility is ExecutionEligibility.EXECUTABLE
    assert new.decisions[2].outcome is GateOutcome.FAIL
    assert new.eligibility is ExecutionEligibility.BLOCKED
    assert len(new.decisions) == 6
    assert all(x.outcome is GateOutcome.PASS for i, x in enumerate(new.decisions) if i != 2)
    assert "NO_ACTION_OR_ORDER_CREATED" in old.warnings


def test_current_removal_demonstrates_selection_change_in_both_directions():
    old = replace(_input().surveillance, asm_stage=2)
    new = replace(old, effective_at=CURRENT_EFFECTIVE, asm_stage=0)
    assert _run(old).eligibility is ExecutionEligibility.BLOCKED
    assert _run(new).eligibility is ExecutionEligibility.EXECUTABLE


def test_pit_first_observation_excludes_future_knowledge_independently_of_effectiveness():
    observation = replace(_input().surveillance, effective_at=CURRENT_EFFECTIVE)
    inputs = replace(_input(), surveillance=observation, snapshot_as_of_timestamp=AT,
                     earnings_schedule_verified_at=AT)
    ref = domain_lineage("surveillance", observation, source_id=observation.id,
        source_version="synthetic-source-v1", policy_version=_policy().gate_config.version,
        as_of=AT, known_at=AT + timedelta(microseconds=1),
        source_fingerprints=(content_fingerprint("synthetic-surveillance"),))
    with pytest.raises(GateVersionBlocked, match="FUTURE_EVIDENCE"):
        gate_evidence_context(inputs, as_of=AT, gate_policy_version=_policy().gate_config.version,
                              dependencies=(ref,))
    observation = replace(observation, effective_at=AT + timedelta(microseconds=1))
    assert _run(observation).decisions[2].outcome is GateOutcome.INSUFFICIENT_DATA


def test_status_role_resolution_does_not_bypass_whole_source_authority(monkeypatch):
    args, _, _ = attack("surveillance")
    monkeypatch.setattr(ExecutionGateEngine, "_surveillance", lambda *_: pytest.fail("unadmitted formula ran"))
    with pytest.raises(GateSourceNotReady, match="GATE_DOMAIN_AUTHORITY_UNAVAILABLE:surveillance"):
        evaluate(args, producer())


def _target(series="EQ"):
    return InstrumentIdentity("NSE:INE000A01001", Exchange.NSE, "EXACT", None,
        "INE000A01001", series, InstrumentType.NSE_EQUITY, "Example",
        provider_mappings=(ProviderInstrumentMapping("SYNTHETIC_PROVIDER", "provider-only-reference"),))


def _master():
    return _extraction(rows=(
        "100,EXACT,EQ,Example,INE000A01001,2,100,0,EQ,EQUITY",
        "101,EXACT,BE,Example,INE000A01001,3,100,0,EQ,EQUITY",
    )).rows


def _identity_example(target, rows):
    """Test-only exact-key illustration over existing contracts, not an adapter."""
    if target.exchange is not Exchange.NSE or not target.isin or not target.series:
        return None
    matches = tuple(row for row in rows if row.report_date == D and
                    (row.symbol, row.isin, row.series) == (target.symbol, target.isin, target.series))
    return matches[0] if len(matches) == 1 else None


@pytest.mark.parametrize("family", ("ASM", "GSM"))
@pytest.mark.parametrize("series", ("EQ", "BE"))
def test_security_scope_needs_execution_security_membership_not_a_list_series(family, series):
    target = _target(series)
    master = _identity_example(target, _master())
    # Fixture declares source applicability; this is not a blanket all-series policy.
    source = {"family": family, "exchange": "NSE", "symbol": "EXACT", "isin": "INE000A01001",
              "framework_applicable": True}
    assert "series" not in source
    assert master is not None and master.isin == source["isin"] and master.symbol == source["symbol"]
    assert _identity_example(replace(target, isin="INE000A01002"), _master()) is None
    assert _identity_example(replace(target, exchange=Exchange.BSE), _master()) is None
    assert _identity_example(replace(target, symbol="Same Company Name"), _master()) is None


@pytest.mark.parametrize("series,band,token", (("EQ", "10", "100"), ("BE", "2", "101")))
def test_price_band_uses_the_target_series_not_surveillance_list_rows(series, band, token):
    target = _target(series); row = _identity_example(target, _master())
    prices = (("EXACT", "EQ", "10"), ("EXACT", "BE", "2"))
    matched = tuple(value for symbol, source_series, value in prices
                    if (symbol, source_series) == (row.symbol, row.series))
    assert matched == (band,) and row.security_code == token
    assert target.provider_mappings[0].provider_instrument_reference != row.security_code
    assert _identity_example(target, tuple(reversed(_master()))) == row
    assert _identity_example(target, (*_master(), row)) is None


def test_missing_target_series_is_local_unknown_not_a_fabricated_eq_or_global_identity_failure():
    assert _identity_example(_target(None), _master()) is None
    assert _identity_example(_target("ZZ"), _master()) is None
    assert not {"series", "token"} & {f.name for f in fields(Instrument)}
    assert {"isin", "series", "exchange", "symbol", "provider_mappings"} <= {f.name for f in fields(InstrumentIdentity)}
    assert RECEIPT["inherited_impact"]["actual_target_price_join_count"] is None


@pytest.mark.parametrize("family", ("ASM", "GSM"))
def test_complete_product_is_not_an_admitted_export_or_policy_change(family):
    item = next(x for x in RECEIPT["identity_and_product_matrix"] if x["family"] == family)
    assert item["product_complete"] is True
    assert item["adapter_completeness"] == "UNPROVEN"
    assert item["source_row_series_required"] is False
    assert item["pilot_producer"] == "NOT_READY"
    assert _policy().surveillance_source.absence_is_pass is False


def test_three_inputs_and_constant_annotation_not_empirical_completeness_or_status_pass():
    result = _run(replace(_input().surveillance, effective_at=CURRENT_EFFECTIVE))
    assert result.eligibility is ExecutionEligibility.EXECUTABLE
    assert result.decisions[2].confidence == 1.0
    for field in ("asm_stage", "gsm_stage", "circuit_limit"):
        incomplete = _run(replace(_input().surveillance, **{field: None}))
        assert incomplete.eligibility is ExecutionEligibility.INSUFFICIENT_DATA
    assert RECEIPT["security_status"]["non_formula_status_guard"] is False


@pytest.mark.parametrize("path,digest", tuple(RECEIPT["code_fingerprints"]["paths"].items()))
def test_frozen_code_fingerprints_and_working_tree_match_audited_baseline(path, digest):
    blob = _blob(RECEIPT["baseline_commit"], path)
    assert sha256(blob).hexdigest() == digest
    assert Path(path).read_text(encoding="utf-8") == blob.decode().replace("\r\n", "\n")


def test_receipt_integrity_and_exact_single_successor_without_activation():
    assert RECEIPT["receipt_fingerprint"] == content_fingerprint({k: v for k, v in RECEIPT.items() if k != "receipt_fingerprint"})
    assert canonical_json(RECEIPT) == canonical_json(json.loads(canonical_json(RECEIPT)))
    prior = json.loads(Path("docs/architecture/GATE3_SURVEILLANCE_POLICY_SOURCE_REPAIR_V1.json").read_text())
    assert RECEIPT["prior_receipt_fingerprint"] == prior["receipt_fingerprint"]
    assert RECEIPT["final_option"] == "C" and RECEIPT["versioned_policy_required"] is True
    assert RECEIPT["next_continuation"] == "GATE3_SURVEILLANCE_POLICY_V2_PROPOSAL"
    assert not RECEIPT["next_continuation_started"] and not RECEIPT["collector_implemented"]
    assert RECEIPT["protected_boundaries"] == prior["protected_boundaries"]
