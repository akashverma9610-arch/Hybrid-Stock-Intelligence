"""Offline bootstrap governance conformance; no approved policy or collector.

Symbolic witnesses check necessary rejection boundaries only. They contain no
duration/price/parcel value, never issue authority, and never open production
SQLite or generate research observations. Native calendar queries are pure.
"""
from copy import deepcopy
from datetime import UTC, date, datetime
from hashlib import sha256
import json
from pathlib import Path
import subprocess

import pytest

from app.fundamentals.diagnostic_comparability import canonical_json, content_fingerprint
from app.historical.nse_capital_market_session_evidence_2022_2026 import (
    nse_capital_market_calendar_2022_2026,
)
from tests.unit import test_gate1_rotation_research_horizon_mapping_evidence_feasibility as previous

ROOT = Path(__file__).resolve().parents[2]
BASELINE = "77582813c30d4a662d8c2a8db63e64f424ba7885"
STEM = "GATE1_ROTATION_RESEARCH_HORIZON_BOOTSTRAP_GOVERNANCE_V1"
PATH = ROOT / "docs/architecture" / (STEM + ".json")
FP = "sha256:79c9626950d25266bca4dfa56ca59922bbd558681fa9daa634025f88648627c8"
NEXT = "GATE1_ROTATION_RESEARCH_BOOTSTRAP_PARAMETER_POLICY_PROPOSAL_V1"
MATRIX = {
    "BOOTSTRAP_NECESSITY": "READY", "INDEPENDENT_PRIOR_AVAILABILITY": "SOURCE_NOT_READY",
    "EXISTING_STRATEGY_DURATION": "SOURCE_NOT_READY", "EXTERNAL_POLICY_EVIDENCE": "SOURCE_NOT_READY",
    "HUMAN_RA_APPROVAL_OPTION": "DERIVABLE", "PROSPECTIVE_REGISTRATION": "DERIVABLE",
    "RESEARCH_ONLY_AUTHORITY_BOUNDARY": "READY", "NUMERIC_SEED": "PARAMETER_REQUIRED",
    "DURATION_UNIT": "POLICY_REQUIRED", "COUNTING_CONVENTION": "POLICY_REQUIRED",
    "TERMINAL_CONVENTION": "POLICY_REQUIRED", "PROSPECTIVE_CALENDAR": "DERIVABLE",
    "HISTORICAL_CALENDAR": "SOURCE_NOT_READY", "PROSPECTIVE_DECISION_ORIGIN": "SOURCE_NOT_READY",
    "SELECTED_PARCEL": "SOURCE_NOT_READY", "RAW_FUTURE_PATH_RETENTION": "POLICY_REQUIRED",
    "GOVERNED_OUTCOME_MATURITY": "DERIVABLE", "TRANSITION_TO_CALIBRATION": "READY",
    "OOS_WALK_FORWARD": "SOURCE_NOT_READY", "PRODUCTION_COMPATIBILITY": "BLOCKED",
}
NULL_PARAMETERS = (
    "seed_value", "seed_range", "duration_unit", "D_alignment_rule", "counting_rule",
    "terminal_rule", "terminal_price_rule", "precision_rule", "calendar_binding",
    "effective_start", "selected_approver", "sample_minimum", "calibration_acceptance_threshold",
    "review_cadence",
)
FALSE_SELECTION = (
    "historical_forward_return_best_window_search", "retrospective_optimization",
    "particular_observation_outcome_influences_seed", "early_underperformance_changes_seed",
    "future_calibration_dataset_justifies_own_seed", "AI_selects_authoritative_seed",
    "negative_outcomes_may_be_discarded",
)
FORBIDDEN_AUTHORITY = {
    "LIVE_ROTATE_IN", "PORTFOLIO_CAPITAL_MOVEMENT", "GATE1_V2_PASS",
    "PRODUCTION_SCENARIO_ENDPOINT", "BROKER_EXECUTION",
}


def _read():
    return previous.previous._read(PATH)


def _digest(a):
    return content_fingerprint({k: v for k, v in a.items() if k != "artifact_fingerprint"})


def _need(condition, code):
    if not condition:
        raise ValueError(code)


def _verify(a):
    _need((a["baseline_commit"], a["decision"], a["semantic_decision"]) == (
        BASELINE, "B", "RESEARCH_HORIZON_BOOTSTRAP_GOVERNANCE_READY_WITH_PARAMETER_BLOCKERS"),
        "DECISION_INVALID")
    p = a["parameters"]
    _need(all(p[k] is None for k in NULL_PARAMETERS)
          and p["seed_grid"] == [] and p["category_mapping"] == []
          and p["approved_numeric_evidence_refs"] == []
          and p["status"] == "BOOTSTRAP_PARAMETER_APPROVAL_REQUIRED", "PARAMETER_INVENTED")
    h = a["research_authority"]
    _need(h["design_label"] == "RESEARCH_BOOTSTRAP_ONLY"
          and h["current_policy_state"] == "PROPOSED"
          and h["approved"] is False and h["registered"] is False
          and h["self_hash_is_authority"] is False
          and all(h[k] is None for k in ("policy_instance", "approval_ref",
                                         "registration_ref", "selected_producer"))
          and set(h["forbidden_authorizations"]) == FORBIDDEN_AUTHORITY, "AUTHORITY_INVENTED")
    _need(h["v1"] == dict(policy_id="six-gates-production-v1", version="v1", status="ACTIVE")
          and h["v2"] == dict(policy_id="execution-gate-policy-v2-proposed",
                             version="v2-proposal.4", status="NOT_ACTIVE"), "ACTIVATION_CHANGED")
    _need(a["preservation"] == previous._read()["preservation"], "PREDECESSOR_WEAKENED")
    s = a["selection_independence"]
    _need(all(s[k] is False for k in FALSE_SELECTION)
          and all(s[k] is True for k in (
              "selected_before_measured_outcomes", "registration_strictly_before_D",
              "source_rationale_frozen_before_registration", "document_sources_and_prior_data_access",
              "underperformance_is_not_a_seed_change_reason")), "SELECTION_LEAKAGE")
    _need(a["registration"]["required_chronology"] == [
        "rationale_known_at <= approved_at",
        "approved_at <= registered_at", "registered_at <= effective_from",
        "registered_at < D", "effective_from <= D",
    ] and a["registration"]["no_backdating"] is True, "PREREGISTRATION_WEAKENED")
    _need(a["historical_application"]["preapproval_D_eligible"] is False
          and a["historical_application"]["grandfathering"] is False
          and a["historical_application"]["exploratory_run_authorized_here"] is False,
          "HISTORICAL_AUTHORITY_INVENTED")
    _need(len(a["mechanism_routes"]) == 5
          and {r["route"] for r in a["mechanism_routes"]} == set("ABCDE")
          and all(r["approved"] is False for r in a["mechanism_routes"])
          and next(r for r in a["mechanism_routes"] if r["route"] == "D")["assessment"]
          == "REJECTED_FROZEN_SEMANTICS"
          and a["activated_route"] is None, "ROUTE_AUTHORITY_INVENTED")
    _need(a["raw_paths"]["official_horizons_per_pair"] == 1
          and all(a["raw_paths"][k] is False for k in (
              "collection_authorized_here", "can_create_additional_official_labels",
              "can_change_official_maturity", "can_change_frozen_end")), "RAW_PATH_AUTHORITY_INVENTED")
    _need(a["cohort"]["current_admission"] is False and a["cohort"]["current_observations"] == []
          and a["cohort"]["current_labels"] == [] and a["cohort"]["no_synthetic_backfill"] is True
          and a["cohort"]["raw_origin_is_complete_observation"] is False, "COHORT_INVENTED")
    _need(a["transition_to_calibration"]["automatic_promotion"] is False
          and a["transition_to_calibration"]["historical_bindings_rewritten"] is False
          and a["lifecycle"]["no_in_place_numeric_edit"] is True, "HISTORICAL_REWRITE")
    _need(a["human_AI_RA"]["direct_user_value_self_authorizes"] is False
          and a["human_AI_RA"]["RA_signature_confers_calibration"] is False
          and a["human_AI_RA"]["approval_confers_live_authority"] is False
          and "POLICY_APPROVAL" in a["human_AI_RA"]["AI_forbidden"], "APPROVER_BYPASS")
    _need(len(a["readiness"]) == len(MATRIX)
          and {r["component"]: r["state"] for r in a["readiness"]} == MATRIX, "READINESS_UPGRADED")
    _need(all(v is False for v in a["runtime"].values()), "RUNTIME_SCOPE")
    _need(a["next_continuations"] == [NEXT] and a["next_continuation_started"] is False, "NEXT_SCOPE")
    _need(a["artifact_fingerprint"] == _digest(a) == FP, "ARTIFACT_TAMPERED")


def _time(value):
    result = datetime.fromisoformat(value)
    _need(result.tzinfo is not None and result.utcoffset() is not None, "NAIVE_TIME")
    return result.astimezone(UTC)


def _witness():
    # Synthetic chronology/attestation booleans, not a policy/approval/event.
    return dict(approved_at="2026-01-05T08:00:00+00:00",
                registered_at="2026-01-05T09:00:00+00:00",
                effective_from="2026-01-05T10:00:00+00:00",
                D="2026-01-05T10:00:00+00:00",
                rationale_known_at="2026-01-05T08:00:00+00:00",
                actor="HUMAN", delegated=True, native_provenance_verified=True,
                source_closure=True, genuine_origin=True, original_parcel=True,
                independent_of_outcomes=True, production_requested=False)


def _necessary_boundary(w):
    """Necessary conditions only; even the valid witness cannot confer authority."""
    if w["production_requested"]:
        return "RESEARCH_SCOPE_ONLY"
    if w["actor"] not in {"HUMAN", "RA"} or not w["delegated"]:
        return "APPROVER_AUTHORITY_UNVERIFIED"
    if not w["native_provenance_verified"]:
        return "SOURCE_TAMPERED"
    approval, registration, effective, D, rationale = (
        _time(w[k]) for k in ("approved_at", "registered_at", "effective_from", "D", "rationale_known_at")
    )
    if not (rationale <= approval <= registration <= effective <= D and registration < D):
        return "PROSPECTIVE_REGISTRATION_REQUIRED"
    if not w["independent_of_outcomes"]:
        return "FUTURE_LABEL_LEAKAGE"
    if not w["genuine_origin"]:
        return "ORIGIN_NOT_AUTHENTIC"
    if not w["original_parcel"]:
        return "PARCEL_MISSING"
    if not w["source_closure"]:
        return "SOURCE_CLOSURE_REQUIRED"
    return "NECESSARY_CONDITIONS_ONLY_NOT_AUTHORITY"


def test_artifact_and_six_predecessors_remain_exact():
    a = _read(); _verify(a)
    assert len(a["predecessors"]) + 1 == 6
    for ref in [a["parent"], *a["predecessors"]]:
        path = ROOT / ref["path"]
        old = previous.previous._read(path)
        assert old[ref["field"]] == content_fingerprint(
            {k: v for k, v in old.items() if k != ref["field"]}
        ) == ref["fingerprint"]
        raw = subprocess.check_output(["git", "show", BASELINE + ":" + ref["path"]])
        assert path.read_bytes().replace(b"\r\n", b"\n") == raw.replace(b"\r\n", b"\n")
    previous.test_frozen_artifact_and_complete_predecessor_chain()


@pytest.mark.parametrize("path,pin", _read()["inspected_file_fingerprints_lf"].items())
def test_historical_pinned_sources(path, pin):
    raw = subprocess.check_output(["git", "show", BASELINE + ":" + path])
    assert "sha256:" + sha256(raw.replace(b"\r\n", b"\n")).hexdigest() == pin


@pytest.mark.parametrize("field", NULL_PARAMETERS + ("seed_grid", "category_mapping", "approved_numeric_evidence_refs"))
def test_resealed_unsupported_value_unit_endpoint_or_calibration_rejected(field):
    a = _read(); a["parameters"][field] = "UNAPPROVED"; a["artifact_fingerprint"] = _digest(a)
    with pytest.raises(ValueError, match="PARAMETER_INVENTED"):
        _verify(a)


@pytest.mark.parametrize("field", FALSE_SELECTION)
def test_retrospective_optimization_future_outcomes_and_early_losses_cannot_choose_seed(field):
    a = _read(); a["selection_independence"][field] = True; a["artifact_fingerprint"] = _digest(a)
    with pytest.raises(ValueError, match="SELECTION_LEAKAGE"):
        _verify(a)


@pytest.mark.parametrize("field,value", [
    ("approved_at", "2026-01-05T11:00:00+00:00"),
    ("registered_at", "2026-01-05T10:00:00+00:00"),
    ("registered_at", "2026-01-05T11:00:00+00:00"),
    ("effective_from", "2026-01-05T08:30:00+00:00"),
    ("effective_from", "2026-01-05T11:00:00+00:00"),
    ("D", "2026-01-04T10:00:00+00:00"),
    ("rationale_known_at", "2026-01-05T11:00:00+00:00"),
    ("rationale_known_at", "2026-01-05T08:30:00+00:00"),
])
def test_approval_registration_future_effectivity_and_no_grandfathering(field, value):
    w = _witness(); w[field] = value
    assert _necessary_boundary(w) == "PROSPECTIVE_REGISTRATION_REQUIRED"


def test_boundary_utc_normalization_and_effective_start_equality_not_registration_equality():
    w = _witness()
    assert _necessary_boundary(w) == "NECESSARY_CONDITIONS_ONLY_NOT_AUTHORITY"
    w["D"] = "2026-01-05T15:30:00+05:30"
    assert _necessary_boundary(w) == "NECESSARY_CONDITIONS_ONLY_NOT_AUTHORITY"
    w["D"] = "2026-01-05T10:00:00"
    with pytest.raises(ValueError, match="NAIVE_TIME"):
        _necessary_boundary(w)
    a = _read()
    assert a["registration"]["native_effectivity_required"] is True
    assert a["registration"]["generic_effective_to_rule_invented"] is False


@pytest.mark.parametrize("actor,delegated", [
    ("AI", True), ("USER_VALUE", True), ("HUMAN", False), ("RA", False),
])
def test_AI_arbitrary_user_value_or_undelegated_RA_cannot_approve(actor, delegated):
    w = _witness(); w.update(actor=actor, delegated=delegated)
    assert _necessary_boundary(w) == "APPROVER_AUTHORITY_UNVERIFIED"


@pytest.mark.parametrize("actor", ["HUMAN", "RA"])
def test_scoped_approver_witness_is_never_production_authority(actor):
    w = _witness(); w["actor"] = actor
    assert _necessary_boundary(w) == "NECESSARY_CONDITIONS_ONLY_NOT_AUTHORITY"
    w["production_requested"] = True
    assert _necessary_boundary(w) == "RESEARCH_SCOPE_ONLY"
    a = _read()
    assert a["human_AI_RA"]["RA_mandatory_from_inspected_internal_governance"] is False
    assert "No blanket legal exemption" in a["human_AI_RA"]["legal_limit"]
    assert "not proof" in a["human_AI_RA"]["attestation"]


@pytest.mark.parametrize("field,reason", [
    ("native_provenance_verified", "SOURCE_TAMPERED"),
    ("independent_of_outcomes", "FUTURE_LABEL_LEAKAGE"),
    ("genuine_origin", "ORIGIN_NOT_AUTHENTIC"),
    ("original_parcel", "PARCEL_MISSING"),
    ("source_closure", "SOURCE_CLOSURE_REQUIRED"),
])
def test_missing_original_parcel_origin_or_source_never_admitted(field, reason):
    w = _witness(); w[field] = False
    assert _necessary_boundary(w) == reason


def test_frozen_circularity_not_relabelled_as_current_source_readiness():
    a = _read(); f = a["frozen_findings"]
    assert f["source_capture_as_of"] == previous._read()["data_audit"]["observed_at_utc"]
    assert f["recaptured_in_this_slice"] is False and f["paired_origins_found"] == f["paired_outcomes_found"] == 0
    assert not f["raw_bars_establish_horizon"] and not f["independent_numeric_authority_found"]
    assert a["definition"]["calibrated"] is a["definition"]["optimal"] is False
    assert a["prospective_first"]["assessment"] == "CONDITIONALLY_FEASIBLE_DESIGN_NOT_OPERATIONALLY_READY"


@pytest.mark.parametrize("field,value", [
    ("approved", True), ("registered", True), ("current_policy_state", "APPROVED_RESEARCH_ONLY"),
    ("approval_ref", "synthetic:human"), ("selected_producer", "synthetic:producer"),
    ("design_label", "PRODUCTION"), ("self_hash_is_authority", True),
])
def test_resealed_design_cannot_become_actual_approval_or_producer(field, value):
    a = _read(); a["research_authority"][field] = value; a["artifact_fingerprint"] = _digest(a)
    with pytest.raises(ValueError, match="AUTHORITY_INVENTED"):
        _verify(a)


def test_multiple_horizons_and_readiness_upgrade_do_not_bypass_frozen_policy():
    a = _read(); a["raw_paths"]["official_horizons_per_pair"] = 2
    a["artifact_fingerprint"] = _digest(a)
    with pytest.raises(ValueError, match="RAW_PATH_AUTHORITY_INVENTED"):
        _verify(a)
    a = _read()
    next(r for r in a["readiness"] if r["component"] == "NUMERIC_SEED")["state"] = "READY"
    a["artifact_fingerprint"] = _digest(a)
    with pytest.raises(ValueError, match="READINESS_UPGRADED"):
        _verify(a)


def test_all_routes_evidence_classes_and_future_registration_fields_explicit():
    a = _read()
    routes = {r["route"]: r for r in a["mechanism_routes"]}
    assert routes["A"]["assessment"] == "UNAVAILABLE"
    assert routes["B"]["assessment"] == "CONDITIONAL_SOURCE_NOT_READY"
    assert routes["C"]["assessment"] == "CONDITIONALLY_SUPPORTABLE_GOVERNANCE_PATH"
    assert routes["D"]["assessment"] == "REJECTED_FROZEN_SEMANTICS"
    assert routes["E"]["assessment"] == "CURRENT_OPERATIONAL_FALLBACK"
    assert len(a["evidence_classes"]) == 7
    assert all(r["alone_authorizes_seed"] is False and r["production_authority"] is False
               for r in a["evidence_classes"])
    fields = a["registration"]["fields"]
    assert len(fields) == len({(r["component"], r["field"]) for r in fields}) == 21
    assert all(r["required_for_issued_record"] and r["validation"] for r in fields)
    assert a["registration"]["shape_status"] == "DOCUMENT_REQUIREMENTS_NOT_IMPLEMENTED_SCHEMA"


def test_lifecycle_is_document_only_append_only_without_automatic_live_promotion():
    a = _read(); lifecycle = a["lifecycle"]
    states = {r["state"] for r in lifecycle["states"]}
    assert states == {"PROPOSED", "APPROVED_RESEARCH_ONLY", "ACCUMULATING_EVIDENCE",
                      "UNDER_CALIBRATION_REVIEW", "SUPERSEDED", "REJECTED"}
    assert all(r["production_authority"] is False for r in lifecycle["states"])
    assert lifecycle["transitions_are_append_only"] and not lifecycle["auto_transition"]
    assert all(r["from"] in states and r["to"] in states and r["condition"] for r in lifecycle["transitions"])
    assert a["transition_to_calibration"]["stages"] == [
        "RESEARCH_BOOTSTRAP", "EVIDENCE_ACCUMULATION", "CALIBRATION",
        "OOS_WALK_FORWARD_VALIDATION", "POLICY_PROPOSAL", "INDEPENDENT_APPROVAL",
        "SEPARATE_POSSIBLE_PRODUCTION_AUTHORITY",
    ]
    assert a["transition_to_calibration"]["calibration_policy"] is None


def test_all_inherited_exclusions_and_native_maturity_remain_exact():
    a = _read(); c = a["cohort"]
    p = previous.previous._read(ROOT / c["exclusions_source"])
    assert p["protocol_fingerprint"] == c["exclusions_fingerprint"]
    assert c["inherited_exclusion_codes"] == [r["code"] for r in p["exclusion_taxonomy"]]
    assert len(c["inherited_exclusion_codes"]) == 36
    assert c["maturity_states"] == p["maturity"]["states"]
    previous.test_original_D_and_pair_maturity_use_existing_rejection_witnesses()


@pytest.mark.parametrize("field", [
    "collection_authorized_here", "can_create_additional_official_labels",
    "can_change_official_maturity", "can_change_frozen_end",
])
def test_raw_paths_cannot_be_authoritative_horizons_or_rewrite_labels(field):
    a = _read(); a["raw_paths"][field] = True; a["artifact_fingerprint"] = _digest(a)
    with pytest.raises(ValueError, match="RAW_PATH_AUTHORITY_INVENTED"):
        _verify(a)


def test_retrospective_exploration_not_authoritative_and_seed_bias_explicit():
    a = _read()
    assert a["historical_application"]["distinct_dataset_labels"] == [
        "PROSPECTIVE_GOVERNED_COHORT", "RETROSPECTIVE_EXPLORATORY_NON_AUTHORITATIVE",
    ]
    assert a["historical_application"]["later_calibration_needs_new_prospective_validation"]
    assert {r["risk"] for r in a["bias_controls"]} == {
        "TRUNCATION", "DURATION_CONDITIONING", "CENSORING", "STRATEGY_MISMATCH",
        "REGIME_DEPENDENCE", "SURVIVOR_BIAS", "OUTSIDE_SEED_BLINDNESS", "ADAPTIVE_REVIEW",
    }
    assert all(r["later_calibration_must_report"] and r["numeric_acceptance_threshold"] is None
               for r in a["bias_controls"])
    a["transition_to_calibration"]["historical_bindings_rewritten"] = True
    a["artifact_fingerprint"] = _digest(a)
    with pytest.raises(ValueError, match="HISTORICAL_REWRITE"):
        _verify(a)


def test_actual_forward_calendar_is_bounded_not_historical_or_universal_readiness():
    a = _read(); calendar = nse_capital_market_calendar_2022_2026()
    assert calendar.calendar_id == a["calendar"]["calendar_id"]
    for r in a["calendar"]["calendar_probes"]:
        day, cutoff = date.fromisoformat(r["date"]), _time(r["as_of"])
        result = calendar.resolve_trading_day(day, as_of=cutoff)
        assert result.state.value == r["day_state"]
        assert [reason.value for reason in result.reasons] == r["reasons"]
        assert len(calendar.phases_for(day, as_of=cutoff)) == r["phase_count"]
    assert a["calendar"]["prospective_state"] == "DERIVABLE"
    assert a["calendar"]["historical_state"] == "SOURCE_NOT_READY"
    assert a["parameters"]["effective_start"] is None
    assert len(a["dependencies"]) == 9
    assert len({r["component"] for r in a["readiness"]}) == 20


@pytest.mark.parametrize("field", _read()["runtime"])
def test_resealed_registration_observations_model_and_runtime_side_effects_rejected(field):
    a = _read(); a["runtime"][field] = True; a["artifact_fingerprint"] = _digest(a)
    with pytest.raises(ValueError, match="RUNTIME_SCOPE"):
        _verify(a)


def test_V1_V2_and_unchanged_gates_no_runtime_consumer():
    previous.test_active_V1_inactive_V2_unchanged_and_no_application_consumer()
    pins = _read()["inspected_file_fingerprints_lf"]
    for path in ("app/gates/engine.py", "app/gates/production_policy.py",
                 "app/scoring/engine.py", "app/portfolio/models.py"):
        assert path in pins
    for path in (ROOT / "app").rglob("*.py"):
        assert STEM not in path.read_text(encoding="utf-8")


def test_canonical_serialization_exact_docs_and_one_next_frozen_continuation():
    a = _read(); _verify(json.loads(canonical_json(a)))
    assert _digest(dict(reversed(list(a.items())))) == FP
    md = PATH.with_suffix(".md").read_text(encoding="utf-8")
    assert a["status"] in md and a["semantic_decision"] in md and md.count(NEXT) == 1
    assert all(r["component"] in md and r["state"] in md for r in a["readiness"])
    assert all(r["url"] in md for r in a["external_sources"])
    corrupt = deepcopy(a); corrupt["rationale"] += " changed"; corrupt["artifact_fingerprint"] = _digest(corrupt)
    with pytest.raises(ValueError, match="ARTIFACT_TAMPERED"):
        _verify(corrupt)
    a["next_continuations"].append("FORBIDDEN_NEXT"); a["artifact_fingerprint"] = _digest(a)
    with pytest.raises(ValueError, match="NEXT_SCOPE"):
        _verify(a)
