"""Offline parameter-policy conformance, not an approving/collecting runtime.

Witnesses contain only symbolic provenance/chronology booleans, no seed,
price, parcel or label values. Passing necessary checks never grants authority.
"""
from copy import deepcopy
from datetime import UTC, datetime
from hashlib import sha256
import json
from pathlib import Path
import subprocess

import pytest

from app.fundamentals.diagnostic_comparability import canonical_json, content_fingerprint
from app.intelligence.multi_funnel_discovery import DiscoveryHorizon
from tests.unit import test_gate1_rotation_research_horizon_bootstrap_governance as previous

ROOT = Path(__file__).resolve().parents[2]
BASELINE = "1cfb08b009d26434f0950da3bf7384ac4b7f88d3"
STEM = "GATE1_ROTATION_RESEARCH_BOOTSTRAP_PARAMETER_POLICY_PROPOSAL_V1"
PATH = ROOT / "docs/architecture" / (STEM + ".json")
FP = "sha256:e751cc6d7f4585d58b081ed9be9d876d399166059cb6d4836f7ff062ce7d8eb3"
NEXT = "GATE1_ROTATION_RESEARCH_BOOTSTRAP_INDEPENDENT_PRIOR_EVIDENCE_V1"
COMPONENTS = ["STRATEGY_CATEGORY_SCOPE","NUMERIC_DURATION","DURATION_UNIT","DECISION_BINDING","SESSION_COUNTING","TERMINAL_BOUNDARY","START_PRICE","TERMINAL_PRICE","CALENDAR_AUTHORITY","INSTRUMENT_ELIGIBILITY","MISSING_CONFLICT_BEHAVIOR","EVIDENCE_RATIONALE","HUMAN_APPROVAL","REGISTRATION_CHRONOLOGY"]
MATRIX = {
    "POLICY_IDENTITY": "READY",
    "RESEARCH_ONLY_SCOPE": "READY",
    "CATEGORY_APPLICABILITY": "POLICY_REQUIRED",
    "SEED_DURATION": "PARAMETER_REQUIRED",
    "DURATION_UNIT": "POLICY_REQUIRED",
    "D_BINDING": "READY",
    "START_PRICE": "POLICY_REQUIRED",
    "SESSION_COUNTING": "POLICY_REQUIRED",
    "TERMINAL_BOUNDARY": "POLICY_REQUIRED",
    "TERMINAL_PRICE": "POLICY_REQUIRED",
    "GROSS_LABEL_FEASIBILITY": "DERIVABLE",
    "CALENDAR_AUTHORITY": "DERIVABLE",
    "INSTRUMENT_ELIGIBILITY": "POLICY_PROPOSED",
    "PARCEL_DEPENDENCY": "SOURCE_NOT_READY",
    "DECISION_ORIGIN_DEPENDENCY": "SOURCE_NOT_READY",
    "EVIDENCE_PACKAGE": "SOURCE_NOT_READY",
    "HUMAN_APPROVAL": "AUTHORITY_NOT_REGISTERED",
    "AI_BOUNDARY": "READY",
    "REGISTRATION_CHRONOLOGY": "READY",
    "PROSPECTIVE_ONLY": "PROSPECTIVE_ONLY",
    "RAW_PATH_RETENTION": "POLICY_REQUIRED",
    "BOOTSTRAP_BIAS_CONTROLS": "POLICY_PROPOSED",
    "VERSIONING": "READY",
    "RETIREMENT": "POLICY_PROPOSED",
    "CALIBRATION_TRANSITION": "POLICY_PROPOSED",
    "PRODUCTION_COMPATIBILITY": "BLOCKED"
}
COUNT_CASES = ["BEFORE_REGULAR_OPEN","DURING_REGULAR_SESSION","AT_OR_AFTER_REGULAR_CLOSE","WEEKEND","EXCHANGE_HOLIDAY","SPECIAL_SESSION","SHORTENED_SESSION","EXCHANGE_WIDE_CLOSURE","SECURITY_SUSPENSION","INSTRUMENT_NON_TRADING"]
TERMINAL_CASES = ["NORMAL_TERMINAL_SESSION","HOLIDAY_OR_WEEKEND","SUSPENSION","MISSING_BAR","DATA_OUTAGE","EXCHANGE_CLOSURE","DELISTING","MERGER_DEMERGER","SECURITY_IDENTITY_TRANSITION","CORPORATE_ACTION_BOUNDARY"]


def _read(path=PATH):
    return json.loads(path.read_text(encoding="utf-8"))


def _digest(a):
    return content_fingerprint({k: v for k, v in a.items() if k != "policy_fingerprint"})


def _need(condition, code):
    if not condition:
        raise ValueError(code)


def _verify(a):
    _need((a["policy_id"], a["version"], a["baseline_commit"]) == (
        "gate1-rotation-research-bootstrap-parameter-policy", "v1-proposed", BASELINE),
        "POLICY_IDENTITY_INVALID")
    _need((a["decision"], a["semantic_decision"]) == (
        "B", "BOOTSTRAP_PARAMETER_POLICY_STRUCTURE_READY_VALUE_BLOCKED"), "DECISION_INVALID")
    h = a["authority"]
    _need(a["status"] == "PROPOSED / UNAPPROVED / NOT_REGISTERED / NOT_ACTIVE"
          and h["scope"] == "RESEARCH_BOOTSTRAP_ONLY"
          and (h["approval_state"], h["registration_state"], h["activation_state"]) ==
          ("UNAPPROVED", "NOT_REGISTERED", "NOT_ACTIVE")
          and h["usable"] is False
          and all(h[k] is None for k in ("approval_ref", "registration_ref", "producer_ref")),
          "AUTHORITY_INVENTED")
    _need(h["v1"] == dict(policy_id="six-gates-production-v1", version="v1", status="ACTIVE")
          and h["v2"] == dict(policy_id="execution-gate-policy-v2-proposed",
                             version="v2-proposal.4", status="NOT_ACTIVE"), "ACTIVATION_CHANGED")
    _need(all(v is None for v in a["effective_parameters"].values())
          and a["numeric"]["grid"] == [] and a["numeric"]["evidence_refs"] == []
          and a["numeric"]["independent_value_found"] is False
          and a["units"]["effective"] is None, "PARAMETER_INVENTED")
    p = a["atomic_package"]
    _need([r["id"] for r in p["components"]] == COMPONENTS
          and all(r["required_for_complete_approval"] for r in p["components"])
          and p["all_components_required"] is True and p["complete"] is False
          and p["partial_approval_allowed"] is False
          and p["number_alone_is_authority"] is False, "ATOMIC_PACKAGE_WEAKENED")
    _need(a["preservation"] == previous._read()["preservation"], "PREDECESSOR_WEAKENED")
    _need(a["categories"]["canonical_values"] == ["POSITIONAL", "LONG_TERM"]
          and a["categories"]["approved_rows"] == []
          and all(a["categories"][k] is False for k in (
              "shared_seed_approved", "separate_seeds_approved", "narrow_strategy_seed_approved")),
          "CATEGORY_MAPPING_INVENTED")
    d = a["boundary"]
    _need(d["horizon_start"] == "D" and d["D_redefined"] is False
          and d["economic_start_observation_at"] is d["actual_end"] is None
          and d["price_time_is_D_by_default"] is False
          and d["future_start_exception_authorized"] is False
          and d["same_binding_both_legs"] is True, "D_BOUNDARY_CHANGED")
    p = a["prices"]
    _need(all(p[k] is None for k in (
        "selected_start_field", "selected_terminal_field", "alignment_policy", "staleness_default"))
        and p["perfect_fill_assumed"] is p["executable_price_claimed"] is False
        and all(p[k] is True for k in (
            "no_nearest_bar", "no_carry_forward", "no_zero_return",
            "no_favorable_extension", "no_adverse_shortening")), "PRICE_POLICY_INVENTED")
    _need(a["counting"]["D_index"] is a["counting"]["first_counted_session"] is
          a["counting"]["precision"] is None and not a["counting"]["algorithm_implemented"]
          and all(r["current_count"] is None for r in a["counting"]["cases"])
          and a["terminal"]["resolved_end"] is a["terminal"]["phase"] is None
          and all(r["resolved_policy"] is None for r in a["terminal"]["cases"])
          and not a["terminal"]["unexpected_closure_rewrites_end"]
          and not a["terminal"]["nearest_bar"], "COUNT_OR_END_INVENTED")
    g = a["gross_labels"]
    _need(g["current_ready"] is False and g["current_labels"] == []
          and g["net_advantage_inr"] is g["auxiliary_percentage"] is g["expected_return"] is None
          and g["net_production_authority"] is False
          and g["maturity_not_admission"] is True
          and g["partial_leg_is_calibration_sample"] is False, "GROSS_NET_CONFUSION")
    _need(a["approval"]["actual_receipt"] is None
          and a["approval"]["requires_all_atomic_components"] is True
          and a["approval"]["human_designation_required"] is True
          and all(a["approval"][k] is False for k in (
              "RA_mandatory", "RA_alone_is_authority", "RA_alone_is_calibration",
              "arbitrary_user_number_is_approval", "AI_may_approve", "AI_may_select_authoritative_seed")),
          "APPROVAL_BYPASS")
    _need(a["registration"]["required_chronology"] == previous._read()["registration"]["required_chronology"]
          and all(a["registration"][k] is None for k in (
              "actual_approved_at", "actual_registered_at", "actual_effective_from"))
          and all(a["registration"][k] is False for k in (
              "registration_equal_D_allowed", "backdating", "future_approval_authorizes_original_D")),
          "CHRONOLOGY_WEAKENED")
    _need(a["prospective"]["only"] and not a["prospective"]["historical_backfill"]
          and not a["prospective"]["Watch_or_scan_promotion"]
          and not a["prospective"]["exploration_authorized_here"], "BACKFILL_AUTHORIZED")
    _need(a["raw_paths"]["official_horizons_per_pair"] == 1
          and not a["raw_paths"]["may_create_extra_labels"]
          and not a["raw_paths"]["may_change_horizon"]
          and not a["raw_paths"]["collection_authorized"], "PATH_FANOUT")
    _need(a["versioning"]["immutable"] and not a["versioning"]["old_cohorts_rewritten"]
          and not a["versioning"]["mix_incompatible_versions"]
          and not a["retirement"]["early_underperformance_changes_seed"]
          and not a["retirement"]["prior_outcomes_deleted"]
          and not a["retirement"]["old_policy_reactivated"]
          and not a["retirement"]["new_lifecycle_states_added"], "HISTORICAL_REWRITE")
    _need(not a["transition"]["automatic"] and not a["transition"]["production_inheritance"],
          "PRODUCTION_PROMOTION")
    _need(len(a["readiness"]) == len(MATRIX)
          and {r["component"]: r["state"] for r in a["readiness"]} == MATRIX, "READINESS_INVENTED")
    _need(all(v is False for v in a["runtime"].values()), "RUNTIME_SCOPE")
    _need(a["next_continuations"] == [NEXT] and a["next_continuation_started"] is False,
          "NEXT_SCOPE")
    _need(a["policy_fingerprint"] == _digest(a) == FP, "ARTIFACT_TAMPERED")


def _necessary_package(verified, *, independently_approved=False, production=False):
    """No parameter values: completeness witness never issues a policy."""
    if production:
        return ("RESEARCH_SCOPE_ONLY",)
    missing = tuple("PACKAGE_COMPONENT_UNVERIFIED:" + k for k in COMPONENTS
                    if verified.get(k) is not True)
    if missing:
        return missing
    if not independently_approved:
        return ("COMPLETE_PACKAGE_APPROVAL_REQUIRED",)
    return ("NECESSARY_CONDITIONS_ONLY_NOT_AUTHORITY",)


def _time(value):
    at = datetime.fromisoformat(value)
    if at.tzinfo is None or at.utcoffset() is None:
        raise ValueError("NAIVE_TIME")
    return at.astimezone(UTC)


def _price_witness(**updates):
    # Chronology metadata only; no numeric price or horizon is selected.
    values = dict(D="2026-01-05T10:00:00+00:00", start_at="2026-01-05T09:00:00+00:00",
                  start_known="2026-01-05T09:30:00+00:00", end="2026-01-06T10:00:00+00:00",
                  R="2026-01-06T11:00:00+00:00", terminal_known="2026-01-06T10:30:00+00:00",
                  alignment_verified=True, native_verified=True, completed=True,
                  exact_terminal=True, terminal_present=True, perfect_fill=False)
    values.update(updates)
    return values


def _necessary_price_boundary(w):
    if not w["native_verified"]:
        return "SOURCE_TAMPERED"
    if w["perfect_fill"]:
        return "EXECUTION_INFERENCE_FORBIDDEN"
    D, start, known, end, R, terminal_known = (
        _time(w[k]) for k in ("D", "start_at", "start_known", "end", "R", "terminal_known")
    )
    if end <= D:
        return "HORIZON_AMBIGUOUS"
    if start > D or known > D:
        return "DECISION_PIT_VIOLATION"
    if not w["alignment_verified"]:
        return "START_PRICE_POLICY_REQUIRED"
    if R < end or not w["completed"]:
        return "PENDING_MATURITY"
    if not w["exact_terminal"] or not w["terminal_present"]:
        return "TERMINAL_OBSERVATION_MISSING"
    if terminal_known > R:
        return "OUTCOME_NOT_YET_KNOWN"
    return "NECESSARY_CONDITIONS_ONLY_NOT_LABEL"


def test_artifact_and_all_seven_predecessors_unchanged():
    a = _read(); _verify(a)
    assert len(a["predecessors"]) + 1 == 7
    for r in [a["parent"], *a["predecessors"]]:
        p = ROOT / r["path"]; old = _read(p)
        assert old[r["field"]] == r["fingerprint"] == content_fingerprint(
            {k: v for k, v in old.items() if k != r["field"]})
        raw = subprocess.check_output(["git", "show", BASELINE + ":" + r["path"]])
        assert raw.replace(b"\r\n", b"\n") == p.read_bytes().replace(b"\r\n", b"\n")
    previous.test_artifact_and_six_predecessors_remain_exact()


@pytest.mark.parametrize("path,pin", _read()["inspected_file_fingerprints_lf"].items())
def test_baseline_source_pins(path, pin):
    raw = subprocess.check_output(["git", "show", BASELINE + ":" + path])
    assert "sha256:" + sha256(raw.replace(b"\r\n", b"\n")).hexdigest() == pin


@pytest.mark.parametrize("component", COMPONENTS)
def test_every_atomic_component_required_even_with_claimed_independent_approval(component):
    witness = {k: True for k in COMPONENTS}; witness[component] = False
    assert _necessary_package(witness, independently_approved=True) == (
        "PACKAGE_COMPONENT_UNVERIFIED:" + component,)
    a = _read()
    next(r for r in a["atomic_package"]["components"] if r["id"] == component)["required_for_complete_approval"] = False
    a["policy_fingerprint"] = _digest(a)
    with pytest.raises(ValueError, match="ATOMIC_PACKAGE_WEAKENED"):
        _verify(a)


@pytest.mark.parametrize("field", _read()["effective_parameters"])
def test_no_unsupported_value_or_convention_can_be_resealed_into_proposal(field):
    a = _read(); a["effective_parameters"][field] = "UNAPPROVED"; a["policy_fingerprint"] = _digest(a)
    with pytest.raises(ValueError, match="PARAMETER_INVENTED"):
        _verify(a)


def test_apparent_completeness_or_number_only_never_grants_authority():
    w = {k: True for k in COMPONENTS}
    assert _necessary_package(w) == ("COMPLETE_PACKAGE_APPROVAL_REQUIRED",)
    assert _necessary_package(w, independently_approved=True) == ("NECESSARY_CONDITIONS_ONLY_NOT_AUTHORITY",)
    assert _necessary_package(w, independently_approved=True, production=True) == ("RESEARCH_SCOPE_ONLY",)
    assert len(_necessary_package({"NUMERIC_DURATION": True})) == len(COMPONENTS) - 1
    w["NUMERIC_DURATION"] = "truthy"
    assert _necessary_package(w) == ("PACKAGE_COMPONENT_UNVERIFIED:NUMERIC_DURATION",)


@pytest.mark.parametrize("field", ["approval_ref", "registration_ref", "producer_ref"])
def test_forged_receipt_or_producer_cannot_activate(field):
    a = _read(); a["authority"][field] = "synthetic:unissued"; a["policy_fingerprint"] = _digest(a)
    with pytest.raises(ValueError, match="AUTHORITY_INVENTED"):
        _verify(a)


def test_native_categories_and_units_not_policy_defaults():
    a = _read()
    assert [v.value for v in DiscoveryHorizon] == a["categories"]["canonical_values"]
    assert a["units"]["state"] == "POLICY_REQUIRED"
    assert a["units"]["inherited_conceptual_preference"] == "TRADING_SESSIONS"
    assert {r["unit"] for r in a["units"]["candidates"]} == {
        "TRADING_SESSIONS", "CALENDAR_DAYS", "ELAPSED_TIMESTAMP_DURATION"}
    assert not a["categories"]["approved_rows"]
    a["categories"]["canonical_values"].append("TACTICAL"); a["policy_fingerprint"] = _digest(a)
    with pytest.raises(ValueError, match="CATEGORY_MAPPING_INVENTED"):
        _verify(a)


@pytest.mark.parametrize("case", COUNT_CASES)
def test_counting_all_market_conditions_explicit_without_counts(case):
    rows = _read()["counting"]["cases"]
    r = next(v for v in rows if v["case_id"] == case)
    assert r["current_count"] is None and r["state"] == "POLICY_REQUIRED"
    assert r["factual_reuse"] and r["unresolved"]
    assert len(rows) == len({r["case_id"] for r in rows}) == len(COUNT_CASES)


@pytest.mark.parametrize("case", TERMINAL_CASES)
def test_terminal_exceptions_preserve_old_exclusions_without_new_valuation(case):
    a = _read(); rows = a["terminal"]["cases"]
    r = next(v for v in rows if v["case_id"] == case)
    assert r["resolved_policy"] is None and r["rule"]
    assert r["inherited_reason"] in a["gross_labels"]["exclusion_codes"]
    assert len(rows) == len({r["case_id"] for r in rows}) == len(TERMINAL_CASES)


@pytest.mark.parametrize("updates,reason", [
    ({"end": "2026-01-05T10:00:00+00:00"}, "HORIZON_AMBIGUOUS"),
    ({"start_at": "2026-01-05T11:00:00+00:00"}, "DECISION_PIT_VIOLATION"),
    ({"start_known": "2026-01-05T11:00:00+00:00"}, "DECISION_PIT_VIOLATION"),
    ({"alignment_verified": False}, "START_PRICE_POLICY_REQUIRED"),
    ({"native_verified": False}, "SOURCE_TAMPERED"),
    ({"perfect_fill": True}, "EXECUTION_INFERENCE_FORBIDDEN"),
    ({"R": "2026-01-06T09:00:00+00:00"}, "PENDING_MATURITY"),
    ({"completed": False}, "PENDING_MATURITY"),
    ({"exact_terminal": False}, "TERMINAL_OBSERVATION_MISSING"),
    ({"terminal_present": False}, "TERMINAL_OBSERVATION_MISSING"),
    ({"terminal_known": "2026-01-06T12:00:00+00:00"}, "OUTCOME_NOT_YET_KNOWN"),
])
def test_D_visible_start_maturity_and_exact_terminal_necessary_boundaries(updates, reason):
    assert _necessary_price_boundary(_price_witness(**updates)) == reason


def test_distinct_earlier_reference_not_D_replacement_and_no_label_output():
    w = _price_witness()
    assert w["start_at"] != w["D"]
    assert _necessary_price_boundary(w) == "NECESSARY_CONDITIONS_ONLY_NOT_LABEL"
    w["D"] = "2026-01-05T15:30:00+05:30"
    assert _necessary_price_boundary(w) == "NECESSARY_CONDITIONS_ONLY_NOT_LABEL"
    w["D"] = "2026-01-05T10:00:00"
    with pytest.raises(ValueError, match="NAIVE_TIME"):
        _necessary_price_boundary(w)
    a = _read(); a["boundary"]["horizon_start"] = "NEXT_OPEN"; a["policy_fingerprint"] = _digest(a)
    with pytest.raises(ValueError, match="D_BOUNDARY_CHANGED"):
        _verify(a)


def test_native_gross_maturity_and_funding_requirements_not_net_authority():
    a = _read(); g = a["gross_labels"]; p = _read(ROOT / g["source"])
    assert g["exclusion_codes"] == [r["code"] for r in p["exclusion_taxonomy"]]
    assert len(g["exclusion_codes"]) == 36 and g["maturity_states"] == p["maturity"]["states"]
    assert "funding_quantity_residual_policy" in g["required"]
    assert not g["partial_leg_is_calibration_sample"] and not g["current_ready"]
    assert g["net_advantage_inr"] is g["auxiliary_percentage"] is g["expected_return"] is None
    previous.test_all_inherited_exclusions_and_native_maturity_remain_exact()


def test_approval_reuses_exact_predecessor_chronology_and_no_human_AI_bypass():
    a = _read()
    assert a["registration"]["required_chronology"] == [
        "rationale_known_at <= approved_at", "approved_at <= registered_at",
        "registered_at <= effective_from", "registered_at < D", "effective_from <= D"]
    previous.test_boundary_utc_normalization_and_effective_start_equality_not_registration_equality()
    for field, value in [
        ("approved_at", "2026-01-05T11:00:00+00:00"),
        ("registered_at", "2026-01-05T10:00:00+00:00"),
        ("rationale_known_at", "2026-01-05T08:30:00+00:00"),
        ("effective_from", "2026-01-05T11:00:00+00:00"),
    ]:
        w = previous._witness(); w[field] = value
        assert previous._necessary_boundary(w) == "PROSPECTIVE_REGISTRATION_REQUIRED"
    for actor, delegated in [("AI", True), ("USER_VALUE", True), ("RA", False), ("HUMAN", False)]:
        w = previous._witness(); w.update(actor=actor, delegated=delegated)
        assert previous._necessary_boundary(w) == "APPROVER_AUTHORITY_UNVERIFIED"


def test_calendar_is_reused_not_backcast_or_economic_counter():
    a = _read()
    assert a["calendar"]["calendar_probes"] == previous._read()["calendar"]["calendar_probes"]
    assert a["calendar"]["historical_state"] == "SOURCE_NOT_READY"
    assert a["calendar"]["prospective_state"] == "DERIVABLE"
    assert not a["calendar"]["current_range_certified"] and a["calendar"]["current_effective_date"] is None
    previous.test_actual_forward_calendar_is_bounded_not_historical_or_universal_readiness()


def test_required_provenance_and_eligibility_do_not_erase_origin_parcel_blockers():
    a = _read()
    assert len(a["evidence_package"]["required_fields"]) == len(set(a["evidence_package"]["required_fields"])) == 12
    assert a["evidence_package"]["actual_entries"] == []
    assert a["eligibility"]["approved_scope"] == a["eligibility"]["actual_instruments"] == []
    assert a["dependencies"]["parcel"] == a["dependencies"]["origin"] == "SOURCE_NOT_READY"
    assert not a["dependencies"]["parameter_ready_is_generation_ready"]
    assert not a["dependencies"]["actual_capture_authorized"]


@pytest.mark.parametrize("section,field,code", [
    ("prices", "no_nearest_bar", "PRICE_POLICY_INVENTED"),
    ("prices", "perfect_fill_assumed", "PRICE_POLICY_INVENTED"),
    ("raw_paths", "may_create_extra_labels", "PATH_FANOUT"),
    ("raw_paths", "may_change_horizon", "PATH_FANOUT"),
    ("prospective", "historical_backfill", "BACKFILL_AUTHORIZED"),
    ("prospective", "Watch_or_scan_promotion", "BACKFILL_AUTHORIZED"),
    ("versioning", "old_cohorts_rewritten", "HISTORICAL_REWRITE"),
    ("versioning", "mix_incompatible_versions", "HISTORICAL_REWRITE"),
    ("retirement", "early_underperformance_changes_seed", "HISTORICAL_REWRITE"),
    ("retirement", "prior_outcomes_deleted", "HISTORICAL_REWRITE"),
    ("retirement", "new_lifecycle_states_added", "HISTORICAL_REWRITE"),
    ("approval", "arbitrary_user_number_is_approval", "APPROVAL_BYPASS"),
    ("approval", "AI_may_approve", "APPROVAL_BYPASS"),
    ("approval", "RA_alone_is_authority", "APPROVAL_BYPASS"),
    ("transition", "production_inheritance", "PRODUCTION_PROMOTION"),
    ("transition", "automatic", "PRODUCTION_PROMOTION"),
])
def test_resealed_permission_fallback_or_historical_rewrite_is_rejected(section, field, code):
    a = _read(); a[section][field] = not a[section][field]; a["policy_fingerprint"] = _digest(a)
    with pytest.raises(ValueError, match=code):
        _verify(a)


@pytest.mark.parametrize("field", _read()["runtime"])
def test_no_runtime_producer_scenario_database_or_execution_changes(field):
    a = _read(); a["runtime"][field] = True; a["policy_fingerprint"] = _digest(a)
    with pytest.raises(ValueError, match="RUNTIME_SCOPE"):
        _verify(a)


def test_bias_retirement_and_calibration_remain_document_only():
    a = _read()
    assert set(a["bias"]["risks"]) == {
        "TRUNCATION", "DURATION_CONDITIONING", "CENSORING", "REGIME_MISMATCH",
        "STRATEGY_MISMATCH", "SECTOR_CONCENTRATION", "INSTRUMENT_CONCENTRATION",
        "SURVIVORSHIP", "OUTSIDE_HORIZON_BLINDNESS"}
    assert a["retirement"]["quantitative_trigger"] is None
    assert not a["retirement"]["automatic_restart"]
    assert a["transition"]["stages"] == [
        "BOOTSTRAP_PARAMETER_APPROVAL", "PROSPECTIVE_GENUINE_OBSERVATIONS",
        "MATURE_PAIRED_GROSS_EVIDENCE", "COHORT_SUFFICIENCY_REVIEW", "CALIBRATION",
        "OOS_WALK_FORWARD", "SCENARIO_METHODOLOGY_PROPOSAL",
        "INDEPENDENT_GOVERNANCE_APPROVAL", "SEPARATE_POSSIBLE_PRODUCTION_INTEGRATION"]
    assert a["transition"]["sufficiency_policy"] is a["transition"]["calibration_policy"] is a["transition"]["OOS_policy"] is None


def test_canonical_fingerprint_serialization_docs_and_exactly_one_next():
    a = _read(); _verify(json.loads(canonical_json(a)))
    assert _digest(dict(reversed(list(a.items())))) == FP
    md = PATH.with_suffix(".md").read_text(encoding="utf-8")
    assert a["status"] in md and a["semantic_decision"] in md and md.count(NEXT) == 1
    assert all(r["component"] in md and r["state"] in md for r in a["readiness"])
    assert all(r["id"] in md for r in a["atomic_package"]["components"])
    assert all(r["path"] in md for r in a["source_audit"])
    corrupt = deepcopy(a); corrupt["rationale"] += " changed"; corrupt["policy_fingerprint"] = _digest(corrupt)
    with pytest.raises(ValueError, match="ARTIFACT_TAMPERED"):
        _verify(corrupt)
    a["next_continuations"].append("FORBIDDEN"); a["policy_fingerprint"] = _digest(a)
    with pytest.raises(ValueError, match="NEXT_SCOPE"):
        _verify(a)


def test_active_V1_inactive_V2_and_no_runtime_consumer():
    previous.test_V1_V2_and_unchanged_gates_no_runtime_consumer()
    for path in (ROOT / "app").rglob("*.py"):
        assert STEM not in path.read_text(encoding="utf-8")
