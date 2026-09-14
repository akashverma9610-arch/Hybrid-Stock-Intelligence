"""Offline governance conformance only; never opens production data or models returns."""
from copy import deepcopy
from decimal import Decimal
from hashlib import sha256
import json
from pathlib import Path
import re
import subprocess

import pytest

from app.calibration.service import CalibrationService, OutcomeSample
from app.fundamentals.diagnostic_comparability import canonical_json, content_fingerprint
from tests.unit import test_gate1_rotation_economic_scenario_contract as predecessor


ROOT = Path(__file__).resolve().parents[2]
PATH = ROOT / "docs/architecture/GATE1_ROTATION_SCENARIO_MODEL_SOURCE_FEASIBILITY_V1.json"
BASELINE = "979543d1627c1b4ce09bd3dcec82824487b6dc48"
FP = "sha256:ae287baed26f5d57248284c044d959ad37b505402261b45394a9a4a1f25c95e3"
NEXT = "GATE1_ROTATION_PAIRED_SCENARIO_RESEARCH_PROTOCOL_V1"
COMPONENTS = set("CONTRACT IDENTITY OHLCV ADJUSTMENT CORPORATE_ACTIONS LIFECYCLE UNIVERSE CALENDAR BENCHMARK SECTOR_INDEX VOLUME_ADV VOLATILITY INTRADAY INCUMBENT_STATE COST_BASIS SELECTED_PARCEL CANDIDATE_ID SCORE DIAGNOSTICS STRATEGY REGIME CATALYST RELATIVE_STRENGTH HORIZON INCUMBENT_ENDPOINT CHALLENGER_ENDPOINT MODEL SALE_FUNDING SUPPLEMENTAL_CASH QUANTITY RESIDUAL TRADEABILITY COST_RATES BROKERAGE TAX_LOTS TAX_POLICY BID_ASK SLIPPAGE FRICTION REPLAY AUTHORITY OUTCOMES REFERENCE_PRICES".split())
MANDATORY = COMPONENTS - set("OHLCV ADJUSTMENT CORPORATE_ACTIONS LIFECYCLE UNIVERSE BENCHMARK SECTOR_INDEX VOLUME_ADV VOLATILITY INTRADAY COST_BASIS DIAGNOSTICS STRATEGY REGIME CATALYST RELATIVE_STRENGTH SUPPLEMENTAL_CASH BID_ASK OUTCOMES".split())
STATES = set("READY DERIVABLE POLICY_UNSET SOURCE_NOT_READY CALIBRATION_REQUIRED HISTORICAL_COVERAGE_INSUFFICIENT AUTHORITY_NOT_REGISTERED BLOCKED".split())
METHODS = set("EMPIRICAL_FORWARD_RETURNS STRATEGY_CONDITIONED_OUTCOMES REGIME_CONDITIONED_RETURNS BENCHMARK_RELATIVE TARGET_STOP_PATHWAYS EXPECTED_R SCORE_TO_RETURN VOLATILITY_NORMALIZED COMPARABLE_SETUPS SCENARIO_TREE".split())
ROW_FIELDS = set("id component required canonical_source current_schema timestamp_semantics adjustment_semantics pit_safe historically_replayable deterministic calibrated authority_status readiness_state current_evidence blocking_reason proposed_prerequisite".split())


def _read():
    return predecessor.proposal._read(PATH)


def _digest(value):
    return content_fingerprint({k: v for k, v in value.items() if k != "artifact_fingerprint"})


def _verify(value):
    """Validate this exact audit's claims, not general runtime source admission."""
    assert value["baseline_commit"] == BASELINE
    assert value["artifact_fingerprint"] == _digest(value)
    assert value["predecessor"]["fingerprint"] == predecessor.FP
    assert value["decision"] == "C" and value["semantic_decision"] == "SCENARIO_MODEL_NOT_YET_FEASIBLE"
    assert value["status"] == "FEASIBILITY_AUDITED / GOVERNANCE_AND_TESTS_ONLY / NOT_ACTIVE"
    assert set(value["readiness_vocabulary"]) == STATES
    rows = value["readiness_matrix"]
    assert len(rows) == len(COMPONENTS) == len({r["id"] for r in rows})
    assert {r["id"] for r in rows} == COMPONENTS
    assert set(value["mandatory_component_ids"]) == MANDATORY
    assert len(value["mandatory_component_ids"]) == len(MANDATORY)
    assert {r["id"] for r in rows if r["required"]} == MANDATORY
    for row in rows:
        assert set(row) == ROW_FIELDS and type(row["required"]) is bool
        assert row["readiness_state"] in STATES
        assert row["pit_safe"] in {"YES", "NO", "CONDITIONAL"}
        assert row["historically_replayable"] in {"YES", "NO", "CONDITIONAL"}
        assert row["canonical_source"] in value["inspected_file_fingerprints_lf"]
        assert all(isinstance(v, str) and v.strip() for k, v in row.items() if k != "required")
        assert row["calibrated"] in {"NOT_APPLICABLE", "NOT_ESTABLISHED_FOR_GATE1"}
        if row["readiness_state"] == "READY":
            assert row["id"] == "CONTRACT" and row["blocking_reason"] == "NONE"
            assert row["authority_status"] == "ACCEPTED_CONTRACT_ONLY"
        else:
            assert row["blocking_reason"] != "NONE"
            assert row["authority_status"] in {"EXISTING_V1_ONLY", "EXISTING_INPUT_ONLY_NOT_GATE1_SCENARIO_AUTHORITY"}
    horizon = value["horizon"]
    assert horizon["classification"] == "POLICY_REQUIRED" and horizon["matrix_state"] == "POLICY_UNSET"
    assert horizon["numeric_horizon"] is None and horizon["same_horizon_required"] and horizon["same_cutoff_required"]
    assert horizon["relabel_allowed"] is False
    model = value["methodology"]
    assert model["selected_family"] is model["incumbent_result_inr"] is model["challenger_result_inr"] is None
    assert model["same_family_required"] and model["asymmetric_methodology_approved"] is False
    assert len(model["families"]) == len(METHODS) and {m["id"] for m in model["families"]} == METHODS
    for item in model["families"]:
        assert item["selected"] is item["calibrated"] is item["reproducible_now_as_gate1"] is False
        assert item["minimum_sample_size"] is None
        for k in ("required_inputs", "available_inputs", "pit_integrity", "calibration_requirement", "sample_size_status", "survivorship_risk", "corporate_action_risk", "regime_dependence", "strategy_dependence", "economic_unit", "symmetric_applicability"):
            assert item[k]
    assert value["ownership"]["registered_producers"] == []
    assert set(value["ownership"]["forbidden_owners"]) == {"AI", "USER", "ANALYST", "SELF_HASH", "SECOND_BRAIN", "DECISION_SCORE_REPLACEMENT"}
    s = value["frozen_semantics"]
    assert s["context"] == "ROTATE_IN" and s["unit"] == "INR"
    for key in ("same_selected_parcel", "partial_conservation", "cost_exclusive", "friction_once", "tax_mandatory", "slippage_mandatory", "independent_hurdles", "PIT_future_exclusion"):
        assert s[key] is True
    assert s["score_hurdle"] == predecessor._read()["scope"]["score_formula"]
    assert s["economic_hurdle"] == "net_advantage_inr > 0.00"
    for key in ("expected_return_default", "tax_rate_default", "slippage_default"):
        assert s[key] is None
    assert s["active_policy"] == "six-gates-production-v1/v1"
    assert s["v2_active"] is s["authority_from_hash"] is False
    assert all(v is False for v in value["runtime"].values())
    assert value["blocker_effect"]["closed_operational_blockers"] == []
    assert value["blocker_effect"]["inherited_contract_unchanged"] is True
    assert len(value["prerequisites"]) == 6 and all(p["status"] == "OPEN" for p in value["prerequisites"])
    assert value["next_continuations"] == [NEXT] and value["next_continuation_started"] is False
    assert value["data_audit_fingerprint"] == content_fingerprint(value["data_audit"])
    assert value["data_audit"]["access"] == "SQLITE_URI_MODE_RO_AND_QUERY_ONLY"


def _rehash(value):
    value["artifact_fingerprint"] = _digest(value)
    return value


def test_artifact_and_predecessor_fingerprints_preserve_exact_accepted_contract():
    value = _read()
    assert value["artifact_fingerprint"] == FP
    _verify(value)
    assert predecessor._digest(predecessor._read()) == predecessor.FP
    predecessor.test_contract_exact_parent_fingerprints_and_non_activation()


@pytest.mark.parametrize("path,pin", _read()["inspected_file_fingerprints_lf"].items())
def test_inspected_source_fingerprint_is_exact_at_audited_baseline(path, pin):
    # Pin this historical inspection, not every future change to non-frozen code.
    source = subprocess.check_output(["git", "show", BASELINE + ":" + path])
    assert "sha256:" + sha256(source.replace(b"\r\n", b"\n")).hexdigest() == pin


@pytest.mark.parametrize("component", sorted(COMPONENTS))
def test_every_required_and_candidate_component_is_explicit_and_cannot_be_removed(component):
    value = _read()
    value["readiness_matrix"] = [r for r in value["readiness_matrix"] if r["id"] != component]
    with pytest.raises(AssertionError):
        _verify(_rehash(value))


@pytest.mark.parametrize("component", sorted(COMPONENTS - {"CONTRACT"}))
def test_rehashing_does_not_promote_unready_sources_to_ready(component):
    value = _read()
    next(r for r in value["readiness_matrix"] if r["id"] == component)["readiness_state"] = "READY"
    with pytest.raises(AssertionError):
        _verify(_rehash(value))


@pytest.mark.parametrize("who", ["AI", "USER", "ANALYST", "SELF_HASH"])
def test_no_claimed_authority_can_register_itself_in_audit(who):
    value = _read(); value["ownership"]["registered_producers"] = [who]
    with pytest.raises(AssertionError):
        _verify(_rehash(value))


@pytest.mark.parametrize("key", ["expected_return_default", "tax_rate_default", "slippage_default"])
def test_no_zero_default_including_friction_or_tax(key):
    value = _read(); value["frozen_semantics"][key] = "0"
    with pytest.raises(AssertionError):
        _verify(_rehash(value))


@pytest.mark.parametrize("path,new", [
    (("horizon", "numeric_horizon"), 30), (("horizon", "same_horizon_required"), False),
    (("horizon", "same_cutoff_required"), False), (("horizon", "relabel_allowed"), True),
    (("methodology", "same_family_required"), False), (("methodology", "asymmetric_methodology_approved"), True),
    (("methodology", "incumbent_result_inr"), "0"), (("methodology", "challenger_result_inr"), "100"),
    (("frozen_semantics", "PIT_future_exclusion"), False), (("frozen_semantics", "unit"), "PERCENT"),
    (("frozen_semantics", "score_hurdle"), "net_advantage_inr > 1"),
    (("frozen_semantics", "economic_hurdle"), "net_advantage_inr >= 0.00"),
    (("frozen_semantics", "v2_active"), True), (("frozen_semantics", "friction_once"), False),
])
def test_frozen_horizon_pit_unit_hurdle_and_non_activation_semantics(path, new):
    value = _read(); value[path[0]][path[1]] = new
    with pytest.raises(AssertionError):
        _verify(_rehash(value))


@pytest.mark.parametrize("model_id", sorted(METHODS))
def test_model_family_review_is_complete_but_not_selected_or_calibrated(model_id):
    value = _read(); item = next(m for m in value["methodology"]["families"] if m["id"] == model_id)
    item["calibrated"] = True
    with pytest.raises(AssertionError):
        _verify(_rehash(value))


def test_population_and_legacy_storage_are_not_conflated_or_run_receipts_used_as_outcomes():
    audit = _read()["data_audit"]
    assert audit["table_counts"]["historical_memberships"] == 0
    assert audit["snapshot_family_counts"]["HISTORICAL_UNIVERSE_MEMBERSHIP"] == 762
    assert audit["snapshot_family_counts"]["FORWARD_PAPER_RUN"] == 3
    assert audit["snapshot_family_counts"]["FORWARD_PAPER_STUDY"] == audit["snapshot_family_counts"]["FORWARD_PAPER_EVENT"] == 0
    assert audit["table_counts"]["paper_outcomes"] == audit["table_counts"]["walk_forward_window_results"] == 0
    assert audit["portfolio_cash_state"] == "UNKNOWN"
    assert audit["bounded_bar_sample"]["count"] == 2000
    assert "NOT_REPRESENTATIVE" in audit["bounded_bar_sample"]["selection"]
    assert sum(x["count"] for x in audit["bounded_bar_sample"]["provider_timeframe_basis_counts"]) == 2000
    life = next(x for x in audit["source_witnesses"] if x["family"] == "HISTORICAL_SECURITY_LIFECYCLE_EVIDENCE")
    assert life["fields"]["historical_known_at"] is None
    link = next(x for x in audit["source_witnesses"] if x["family"] == "DECISION_OUTCOME_LINK")
    assert link["fields"]["outcome_type"] == "SELL_SIDE_DECISION_EVENT"


def test_measurement_observed_is_not_calibrated_expectation_and_missing_is_not_zero():
    samples = (OutcomeSample(Decimal("8"), None, None, None, None, None, None),)
    result = CalibrationService().calibrate(samples)
    bucket = next(r for r in result if r.bucket == "8-9")
    assert bucket.status == "OBSERVED" and bucket.sample_count == 1
    assert bucket.expectancy is bucket.win_probability is None
    assert not _read()["methodology"]["families"][0]["calibrated"]


def test_exactly_one_next_continuation_and_no_model_implementation():
    value = _read(); value["next_continuations"].append("SECOND_SLICE")
    with pytest.raises(AssertionError):
        _verify(_rehash(value))
    assert _read()["ownership"]["future_owner"].startswith("app/rotation")
    assert all(v is False for v in _read()["runtime"].values())
    for path in (ROOT / "app").rglob("*.py"):
        assert "GATE1_ROTATION_SCENARIO_MODEL_SOURCE_FEASIBILITY_V1" not in path.read_text(encoding="utf-8")


def test_stable_serialization_complete_content_and_duplicate_keys_rejected():
    value = _read()
    assert _digest(json.loads(canonical_json(value))) == FP
    assert _digest(dict(reversed(tuple(value.items())))) == FP
    with pytest.raises(ValueError, match="DUPLICATE_PROPOSAL_KEY"):
        json.loads('{"decision":"C","decision":"A"}', object_pairs_hook=predecessor.proposal.legacy._unique_object)
    changed = deepcopy(value); changed["data_audit"]["table_counts"]["paper_outcomes"] = 99
    with pytest.raises(AssertionError):
        _verify(_rehash(changed))
    assert all(re.fullmatch(r"sha256:[0-9a-f]{64}", p) for p in value["inspected_file_fingerprints_lf"].values())
    assert all(r["calibrated"] != "CALIBRATED" for r in value["readiness_matrix"])


def test_existing_v1_and_six_gate_boundaries_unchanged():
    predecessor.test_contract_loading_cannot_change_v1_any_gate_or_register_v2()
    for path, pin in predecessor._read()["frozen_files_lf"].items():
        predecessor.test_frozen_core_and_all_governance_files_unchanged(path, pin)
