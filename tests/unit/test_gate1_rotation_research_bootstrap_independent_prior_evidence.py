"""Offline evidence-dossier conformance; no approving/collecting runtime.

Symbolic witnesses test necessary claim-level rejection rules only. They never
select a number, resolve a policy, query production data or generate a cohort.
"""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import subprocess
from urllib.parse import urlsplit

import pytest

from app.fundamentals.diagnostic_comparability import canonical_json, content_fingerprint
from tests.unit import test_gate1_rotation_research_bootstrap_parameter_policy_proposal as previous

ROOT = Path(__file__).resolve().parents[2]
BASELINE = "98698bf78e1582af08a99ea0a4c12ff622957ffe"
STEM = "GATE1_ROTATION_RESEARCH_BOOTSTRAP_INDEPENDENT_PRIOR_EVIDENCE_V1"
PATH = ROOT / "docs/architecture" / (STEM + ".json")
FP = "sha256:b2c7e7913384dce1b76691d89cb59a9b38737f9fb365eed3392a0f55292359f6"
NEXT = "GATE1_ROTATION_RESEARCH_SESSION_PRICE_SOURCE_APPLICABILITY_AUDIT_V1"
TAXONOMY = (
    "INTERNAL_CANONICAL_POLICY_PRIOR", "INTERNAL_DESIGN_PRIOR",
    "EXTERNAL_PRIMARY_EVIDENCE", "EXTERNAL_EMPIRICAL_RESEARCH",
    "EXPERT_GOVERNANCE_PRIOR", "DESCRIPTIVE_CONTEXT_ONLY", "EXPLORATORY_ONLY",
    "PIT_UNSAFE", "CIRCULAR", "UNVERIFIED", "INCOMPATIBLE",
)
STRENGTHS = (
    "INADMISSIBLE", "CONFLICTED", "ABSENT", "CONTEXT_ONLY",
    "STRONG_INDEPENDENT_SUPPORT", "MODERATE_INDEPENDENT_SUPPORT", "LIMITED_SUPPORT",
)
MATRIX = {
    "CATEGORY_SCOPE": "EVIDENCE_PARTIALLY_SUFFICIENT",
    "POSITIONAL_SEED": "EVIDENCE_INSUFFICIENT",
    "LONG_TERM_SEED": "EVIDENCE_INSUFFICIENT",
    "NARROWER_STRATEGY_SEED": "EVIDENCE_PARTIALLY_SUFFICIENT",
    "NUMERIC_DURATION": "EVIDENCE_INSUFFICIENT",
    "DURATION_UNIT": "POLICY_REQUIRED",
    "D_BINDING": "EVIDENCE_SUFFICIENT_FOR_PROPOSAL",
    "SESSION_COUNTING": "SOURCE_NOT_READY",
    "START_PRICE": "EVIDENCE_INSUFFICIENT",
    "TERMINAL_BOUNDARY": "POLICY_REQUIRED",
    "TERMINAL_PRICE": "EVIDENCE_INSUFFICIENT",
    "PROSPECTIVE_CALENDAR_SUPPORT": "SOURCE_NOT_READY",
    "INSTRUMENT_ELIGIBILITY": "EVIDENCE_PARTIALLY_SUFFICIENT",
    "EVIDENCE_PROVENANCE": "EVIDENCE_SUFFICIENT_FOR_PROPOSAL",
    "HUMAN_APPROVAL_READINESS": "EXPERT_REVIEW_REQUIRED",
}
REJECTED = (
    "MIDPOINT_OF_RANGE", "ROUND_NUMBER_CONVENIENCE", "WEAK_SOURCE_VOTE",
    "BEST_RETURN_WINDOW", "PARAMETER_CHERRY_PICK", "RAW_OHLCV_ALONE",
    "FUTURE_COHORT_LABELS", "AGE_ALONE", "DESCRIPTIVE_TO_AUTHORITY",
    "AI_RECOMMENDATION_ALONE", "BARE_HUMAN_PREFERENCE", "RA_TITLE_ALONE",
    "LOOKBACK_AS_HOLDING_PERIOD",
)
EXTERNAL_FIELDS = (
    "title", "authors", "institution", "publication_date", "url", "locator",
    "population", "methodology", "sample_period", "studied_horizons",
    "selection_status", "asset_market_compatibility", "strategy_compatibility",
    "limitations", "numeric_conclusion", "evidence_class", "independence_profile",
    "independence_result", "accessed_on", "raw_response_fingerprint", "retention",
    "source_bytes_retained", "supports_exact_hsi_seed", "production_authority",
)


def _read(path=PATH):
    return json.loads(path.read_text(encoding="utf-8"))


def _digest(a):
    return content_fingerprint({k: v for k, v in a.items() if k != "artifact_fingerprint"})


def _need(condition, code):
    if not condition:
        raise ValueError(code)


def _verify(a):
    parent = previous._read()
    _need((a["baseline_commit"], a["slice"], a["version"], a["dossier_id"]) == (
        BASELINE, STEM, "v1", "gate1-rotation-research-bootstrap-independent-prior-evidence"),
        "DOSSIER_IDENTITY")
    _need((a["decision"], a["semantic_decision"], a["slice_status"]) == (
        "B", "INDEPENDENT_PRIOR_EVIDENCE_PARTIALLY_SUFFICIENT", "ACCEPTED/CLOSED"),
        "DECISION_INVENTED")
    _need(a["status"] == "EVIDENCE_DOSSIER / NO_PARAMETER_APPROVAL / NOT_ACTIVE"
          and a["bootstrap_policy_status"] == parent["status"]
          and a["authority"] == parent["authority"], "AUTHORITY_CHANGED")
    _need(a["effective_parameters"] == parent["effective_parameters"]
          and all(v is None for v in a["effective_parameters"].values()),
          "PARAMETER_INVENTED")
    _need(a["preservation"] == parent["preservation"]
          and a["registration"] == parent["registration"], "PREDECESSOR_WEAKENED")
    _need(tuple(r["id"] for r in a["taxonomy"]) == TAXONOMY
          and all(not r["direct_parameter_authority"] and not r["production_authority"]
                  and r["independent_human_approval_required"]
                  and r["provenance_requirements"] and r["admissible_role"]
                  for r in a["taxonomy"])
          and all(not r["may_inform_research_seed"] for r in a["taxonomy"][5:]),
          "TAXONOMY_PROMOTION")
    _need(tuple(a["rejected_shortcuts"]) == REJECTED, "SHORTCUT_ALLOWED")
    _need(tuple(r["id"] for r in a["strength_rules"]) == STRENGTHS
          and a["strength_numeric_score"] is None, "PSEUDO_PRECISION")
    records = a["internal_evidence"] + a["external_evidence"]
    ids = [r["id"] for r in records]
    _need(len(ids) == len(set(ids)) == 21
          and all(not r["supports_exact_hsi_seed"] for r in records),
          "INVENTED_OR_DUPLICATE_PRIOR")
    for r in a["internal_evidence"]:
        _need(r["path"] in a["inspected_file_fingerprints_lf"]
              and r["fingerprint_lf"] == a["inspected_file_fingerprints_lf"][r["path"]]
              and all(r[k] for k in ("last_commit", "commit_date", "version",
                                    "original_purpose", "compatibility",
                                    "numeric_conclusion", "admissibility")),
              "INTERNAL_PROVENANCE")
    for r in a["external_evidence"]:
        _need(all(k in r for k in EXTERNAL_FIELDS), "EXTERNAL_PROVENANCE")
        _need(all(r[k] for k in ("title", "authors", "institution", "publication_date",
                                "url", "locator", "limitations", "selection_status",
                                "asset_market_compatibility", "strategy_compatibility",
                                "independence_result")), "EXTERNAL_PROVENANCE")
        url = urlsplit(r["url"])
        _need(url.scheme == "https" and not url.username and not url.password
              and url.hostname in {
                  "www.bauer.uh.edu", "www.iima.ac.in",
                  "shleifer.scholars.harvard.edu", "www.nseindia.com", "www.sebi.gov.in",
              } and r["raw_response_fingerprint"] is None
              and not r["source_bytes_retained"] and not r["production_authority"],
              "EXTERNAL_PROVENANCE")
        if r["id"] in ("E01", "E02"):
            _need(all(r[k] for k in ("population", "methodology", "sample_period",
                                    "studied_horizons"))
                  and r["evidence_class"] == "EXTERNAL_EMPIRICAL_RESEARCH",
                  "EMPIRICAL_METHOD_UNVERIFIED")
        if r["id"] == "E03":
            _need(r["evidence_class"] == "UNVERIFIED"
                  and r["independence_result"] == "NOT_ESTABLISHED"
                  and all(r[k] is None for k in (
                      "population", "methodology", "sample_period", "studied_horizons")),
                  "UNREAD_SOURCE_PROMOTED")
    rows = a["parameter_evidence_matrix"]
    _need(len(rows) == len(MATRIX)
          and {r["component"]: r["readiness"] for r in rows} == MATRIX,
          "READINESS_INVENTED")
    for r in rows:
        _need(r["evidence_class"] in TAXONOMY and r["strength"] in STRENGTHS
              and r["independence_result"] and r["transferability"] and r["finding"]
              and all(i in ids for i in r["supporting_evidence_ids"] + r["contradicting_evidence_ids"])
              and "E03" not in r["supporting_evidence_ids"]
              and "E05" not in r["supporting_evidence_ids"]
              and len(r["supporting_evidence_ids"]) == len(set(r["supporting_evidence_ids"]))
              and len(r["contradicting_evidence_ids"]) == len(set(r["contradicting_evidence_ids"])),
              "MATRIX_SUPPORT_INVALID")
    _need(a["scope_options"]["selected_scope"] is None
          and not a["scope_options"]["stronger_numeric_support"]
          and not a["scope_options"]["same_seed_for_categories"]
          and a["scope_options"]["canonical_categories"] == ["POSITIONAL", "LONG_TERM"],
          "SCOPE_VALUE_INVENTED")
    _need(a["units"]["selected"] is None
          and not a["units"]["convert_studied_months_to_sessions"]
          and all(a["counting"][k] is None for k in (
              "chosen_rule", "first_counted_session", "D_index", "partial_weight", "special_weight")),
          "COUNT_DEFAULT")
    prices = a["price_boundaries"]
    _need(prices["start"] == "D" and all(prices[k] is None for k in (
        "start_price_rule", "terminal_boundary_rule", "terminal_price_rule"))
        and all(prices[k] is False for k in (
            "D_redefined", "start_price_is_fill", "start_at_after_D_allowed",
            "start_known_after_D_allowed", "later_same_day_close_at_intraday_D_allowed",
            "nearest_or_carry_forward_allowed", "label_or_fill_created"))
        and all(prices[k] is True for k in (
            "terminal_requires_exact_frozen_end", "terminal_requires_completed_and_known_by_R",
            "same_pair_basis_required")), "PRICE_DEFAULT")
    c = a["calendar"]
    _need(c["predecessor_probe_snapshot"] == parent["calendar"]["calendar_probes"]
          and c["native_visibility"] == parent["calendar"]["native_visibility"]
          and c["current_assessment"] ==
          "SOURCE_NOT_READY_FOR_UNIVERSAL_PROSPECTIVE_PRICE_CONVENTIONS"
          and all(not c[k] for k in (
              "official_effective_activation_date_verified", "original_circular_bytes_retained",
              "new_horizon_admission_certified", "amend_frozen_predecessor")),
          "CALENDAR_OVERCLAIM")
    _need([c["id"] for c in a["conflicts"]] == ["C01", "C02"]
          and all(not c["numeric_average_allowed"] for c in a["conflicts"])
          and a["conflicts"][0]["status"] == "UNRESOLVED_FOR_RESEARCH_CONVENTIONS",
          "CONFLICT_HIDDEN")
    e = a["expert"]
    _need(e["actual_prior"] is e["actual_approval"] is None and e["state"] == "ABSENT"
          and len(e["required"]) == 6
          and all(not e[k] for k in (
              "RA_mandatory", "RA_title_grants_authority",
              "opinion_creates_calibration", "backdating_allowed")), "EXPERT_AUTHORITY_INVENTED")
    _need(not a["bias"]["raw_paths_collection_authorized"]
          and a["bias"]["one_horizon_per_original_pair"]
          and a["bias"]["risks"] == parent["bias"]["risks"], "BIAS_ERASED")
    _need(all(v is False for v in a["runtime"].values()), "RUNTIME_SCOPE")
    _need(a["next_continuations"] == [NEXT] and not a["next_continuation_started"],
          "NEXT_SCOPE")
    _need(a["artifact_fingerprint"] == _digest(a) == FP, "DOSSIER_TAMPERED")


def _strength(w):
    """Test-only symbolic implementation of dossier precedence, NOT approval."""
    if (w["shortcut"] is not None or not all(w[k] for k in (
            "pit", "independent_generation", "independent_selection",
            "provenance", "method", "reproducible_to_claim", "limitations"))
            or w["class"] in ("PIT_UNSAFE", "CIRCULAR", "UNVERIFIED", "INCOMPATIBLE")
            or (w["numeric_claim"] and not w["numeric_supported"])):
        return "INADMISSIBLE"
    if w["same_claim_conflict"]:
        return "CONFLICTED"
    if not w["has_evidence"]:
        return "ABSENT"
    if not w["direct_scope"] or w["class"] in ("DESCRIPTIVE_CONTEXT_ONLY", "EXPLORATORY_ONLY"):
        return "CONTEXT_ONLY"
    if w["exact_compatible_constraint"] or w["fully_reproduced_same_purpose"]:
        return "STRONG_INDEPENDENT_SUPPORT"
    if w["bounded_limits"]:
        return "MODERATE_INDEPENDENT_SUPPORT"
    return "LIMITED_SUPPORT"


def _witness(**updates):
    # No numeric parameter/outcome. This is a logical conformance witness.
    value = dict(shortcut=None, pit=True, independent_generation=True,
                 independent_selection=True, provenance=True, method=True,
                 reproducible_to_claim=True, limitations=True,
                 numeric_claim=False, numeric_supported=False,
                 same_claim_conflict=False, has_evidence=True, direct_scope=False,
                 exact_compatible_constraint=False, fully_reproduced_same_purpose=False,
                 bounded_limits=False)
    value["class"] = "EXTERNAL_EMPIRICAL_RESEARCH"
    return value | updates


def test_dossier_and_eight_predecessors_are_immutable():
    a = _read(); _verify(a)
    assert len(a["predecessors"]) + 1 == 8
    for r in [a["parent"], *a["predecessors"]]:
        artifact = _read(ROOT / r["path"])
        assert artifact[r["field"]] == r["fingerprint"] == content_fingerprint(
            {k: v for k, v in artifact.items() if k != r["field"]})
        old = subprocess.check_output(["git", "show", BASELINE + ":" + r["path"]])
        assert old.replace(b"\r\n", b"\n") == (ROOT / r["path"]).read_bytes().replace(b"\r\n", b"\n")
    previous.test_artifact_and_all_seven_predecessors_unchanged()


@pytest.mark.parametrize("path,pin", _read()["inspected_file_fingerprints_lf"].items())
def test_baseline_pins_including_gates_and_original_source_versions(path, pin):
    # Historical pin: later legitimate changes need not invalidate audit history.
    raw = subprocess.check_output(["git", "show", BASELINE + ":" + path])
    assert "sha256:" + sha256(raw.replace(b"\r\n", b"\n")).hexdigest() == pin


@pytest.mark.parametrize("field", _read()["effective_parameters"])
def test_no_numeric_seed_range_or_other_effective_parameter_may_be_added(field):
    a = _read(); a["effective_parameters"][field] = "UNAUTHORIZED"
    a["artifact_fingerprint"] = _digest(a)
    with pytest.raises(ValueError, match="PARAMETER_INVENTED"):
        _verify(a)


@pytest.mark.parametrize("shortcut", REJECTED)
def test_midpoint_best_return_ohlcv_AI_human_title_and_circular_shortcuts_rejected(shortcut):
    assert _strength(_witness(shortcut=shortcut)) == "INADMISSIBLE"
    a = _read(); a["rejected_shortcuts"].remove(shortcut); a["artifact_fingerprint"] = _digest(a)
    with pytest.raises(ValueError, match="SHORTCUT_ALLOWED"):
        _verify(a)


@pytest.mark.parametrize("field", [
    "pit", "independent_generation", "independent_selection",
    "provenance", "method", "reproducible_to_claim", "limitations",
])
def test_every_independence_requirement_is_necessary_not_age_alone(field):
    assert _strength(_witness(**{field: False})) == "INADMISSIBLE"


@pytest.mark.parametrize("evidence_class", ["PIT_UNSAFE", "CIRCULAR", "UNVERIFIED", "INCOMPATIBLE"])
def test_rejected_classes_cannot_be_supported_by_appearance_or_timestamp(evidence_class):
    assert _strength(_witness(**{"class": evidence_class})) == "INADMISSIBLE"


@pytest.mark.parametrize("updates,expected", [
    ({}, "CONTEXT_ONLY"),
    ({"numeric_claim": True}, "INADMISSIBLE"),
    ({"has_evidence": False}, "ABSENT"),
    ({"direct_scope": True}, "LIMITED_SUPPORT"),
    ({"direct_scope": True, "bounded_limits": True}, "MODERATE_INDEPENDENT_SUPPORT"),
    ({"direct_scope": True, "exact_compatible_constraint": True}, "STRONG_INDEPENDENT_SUPPORT"),
    ({"direct_scope": True, "fully_reproduced_same_purpose": True}, "STRONG_INDEPENDENT_SUPPORT"),
    ({"direct_scope": True, "fully_reproduced_same_purpose": True, "same_claim_conflict": True}, "CONFLICTED"),
    ({"same_claim_conflict": True, "independent_selection": False}, "INADMISSIBLE"),
    ({"class": "DESCRIPTIVE_CONTEXT_ONLY", "direct_scope": True}, "CONTEXT_ONLY"),
    ({"class": "EXPLORATORY_ONLY", "direct_scope": True}, "CONTEXT_ONLY"),
])
def test_claim_level_strength_has_exact_rejection_first_precedence(updates, expected):
    w = _witness(**updates)
    assert _strength(w) == _strength(dict(reversed(list(w.items())))) == expected
    assert "AUTHORITY" not in expected


@pytest.mark.parametrize("evidence_class", TAXONOMY)
def test_all_classes_require_later_human_approval_and_never_grant_authority(evidence_class):
    a = _read()
    r = next(r for r in a["taxonomy"] if r["id"] == evidence_class)
    assert r["independent_human_approval_required"]
    r["direct_parameter_authority"] = True; a["artifact_fingerprint"] = _digest(a)
    with pytest.raises(ValueError, match="TAXONOMY_PROMOTION"):
        _verify(a)


@pytest.mark.parametrize("field", ["authors", "publication_date", "url", "methodology", "sample_period"])
def test_empirical_source_requires_original_provenance_and_method(field):
    a = _read(); a["external_evidence"][0][field] = None; a["artifact_fingerprint"] = _digest(a)
    with pytest.raises(ValueError, match="EXTERNAL_PROVENANCE|EMPIRICAL_METHOD_UNVERIFIED"):
        _verify(a)


def test_no_unread_source_or_retrospective_dataset_is_promoted():
    a = _read()
    assert a["evidence_scope"]["empirical_methods_reviewed"] == ["E01", "E02"]
    assert a["evidence_scope"]["screened_not_method_verified"] == ["E03"]
    assert a["external_evidence"][2]["methodology"] is None
    assert "Retrospective" in a["external_evidence"][1]["limitations"]
    assert all(not r["supports_exact_hsi_seed"] for r in a["external_evidence"])
    a["external_evidence"][2]["evidence_class"] = "EXTERNAL_EMPIRICAL_RESEARCH"
    a["artifact_fingerprint"] = _digest(a)
    with pytest.raises(ValueError, match="UNREAD_SOURCE_PROMOTED"):
        _verify(a)


def test_scope_transferability_and_lookback_holding_separation_are_explicit():
    a = _read()
    assert "20–60" in a["internal_evidence"][2]["observed_values_not_seed"]
    assert "backward" in a["internal_evidence"][2]["observed_values_not_seed"]
    assert "Formation is not holding" in a["external_evidence"][1]["studied_horizons"]
    assert all(r["asset_market_compatibility"] and r["strategy_compatibility"]
               and r["sample_period"] and r["limitations"] for r in a["external_evidence"][:2])
    assert not a["scope_options"]["stronger_numeric_support"]
    assert a["scope_options"]["selected_scope"] is None
    assert a["conflicts"][1]["status"] == "SCOPE_DIFFERENCE_NOT_EMPIRICAL_REFUTATION"


@pytest.mark.parametrize("component", MATRIX)
def test_complete_matrix_cannot_promote_any_unavailable_component(component):
    a = _read(); r = next(r for r in a["parameter_evidence_matrix"] if r["component"] == component)
    r["readiness"] = "READY"; a["artifact_fingerprint"] = _digest(a)
    with pytest.raises(ValueError, match="READINESS_INVENTED"):
        _verify(a)


def test_market_regime_gap_does_not_rewrite_predecessor_calendar_or_choose_close():
    a = _read()
    assert a["calendar"]["predecessor_probe_snapshot"] == previous._read()["calendar"]["calendar_probes"]
    assert a["calendar"]["current_assessment"].startswith("SOURCE_NOT_READY")
    assert a["conflicts"][0]["sources"] == ["I10", "E04"]
    assert not a["calendar"]["official_effective_activation_date_verified"]
    assert a["price_boundaries"]["terminal_price_rule"] is None
    previous.test_calendar_is_reused_not_backcast_or_economic_counter()


def test_original_D_chronology_price_vs_fill_and_gross_boundaries_retained():
    previous.test_approval_reuses_exact_predecessor_chronology_and_no_human_AI_bypass()
    previous.test_distinct_earlier_reference_not_D_replacement_and_no_label_output()
    previous.test_native_gross_maturity_and_funding_requirements_not_net_authority()
    assert previous._necessary_price_boundary(previous._price_witness(
        start_at="2026-01-05T11:00:00+00:00")) == "DECISION_PIT_VIOLATION"
    assert previous._necessary_price_boundary(previous._price_witness(
        perfect_fill=True)) == "EXECUTION_INFERENCE_FORBIDDEN"
    assert previous._necessary_price_boundary(previous._price_witness(
        terminal_present=False)) == "TERMINAL_OBSERVATION_MISSING"


@pytest.mark.parametrize("section,field,value,code", [
    ("authority", "usable", True, "AUTHORITY_CHANGED"),
    ("authority", "approval_ref", "fake", "AUTHORITY_CHANGED"),
    ("units", "selected", "TRADING_SESSIONS", "COUNT_DEFAULT"),
    ("units", "convert_studied_months_to_sessions", True, "COUNT_DEFAULT"),
    ("counting", "D_index", "invented", "COUNT_DEFAULT"),
    ("counting", "partial_weight", "invented", "COUNT_DEFAULT"),
    ("price_boundaries", "terminal_price_rule", "CLOSE", "PRICE_DEFAULT"),
    ("price_boundaries", "start_price_is_fill", True, "PRICE_DEFAULT"),
    ("price_boundaries", "D_redefined", True, "PRICE_DEFAULT"),
    ("price_boundaries", "nearest_or_carry_forward_allowed", True, "PRICE_DEFAULT"),
    ("calendar", "new_horizon_admission_certified", True, "CALENDAR_OVERCLAIM"),
    ("calendar", "amend_frozen_predecessor", True, "CALENDAR_OVERCLAIM"),
    ("expert", "actual_approval", "title-only", "EXPERT_AUTHORITY_INVENTED"),
    ("expert", "RA_title_grants_authority", True, "EXPERT_AUTHORITY_INVENTED"),
    ("bias", "raw_paths_collection_authorized", True, "BIAS_ERASED"),
    ("bias", "one_horizon_per_original_pair", False, "BIAS_ERASED"),
])
def test_resealed_default_or_authority_or_historical_mutation_rejected(section, field, value, code):
    a = _read(); a[section][field] = value; a["artifact_fingerprint"] = _digest(a)
    with pytest.raises(ValueError, match=code):
        _verify(a)


@pytest.mark.parametrize("field", _read()["runtime"])
def test_no_backfill_cohort_labels_calibration_scenario_registry_or_runtime_effect(field):
    a = _read(); a["runtime"][field] = True; a["artifact_fingerprint"] = _digest(a)
    with pytest.raises(ValueError, match="RUNTIME_SCOPE"):
        _verify(a)


def test_preserve_conflicts_no_averaging_no_false_consensus():
    a = _read(); a["conflicts"][0]["numeric_average_allowed"] = True
    a["artifact_fingerprint"] = _digest(a)
    with pytest.raises(ValueError, match="CONFLICT_HIDDEN"):
        _verify(a)
    a = _read(); a["parameter_evidence_matrix"][0]["supporting_evidence_ids"].append("E03")
    a["artifact_fingerprint"] = _digest(a)
    with pytest.raises(ValueError, match="MATRIX_SUPPORT_INVALID"):
        _verify(a)


def test_V1_ACTIVE_V2_NOT_ACTIVE_and_no_runtime_consumer():
    previous.test_active_V1_inactive_V2_and_no_runtime_consumer()
    a = _read()
    assert a["authority"]["v1"]["status"] == "ACTIVE"
    assert a["authority"]["v2"]["status"] == "NOT_ACTIVE"
    for path in (ROOT / "app").rglob("*.py"):
        assert STEM not in path.read_text(encoding="utf-8")


def test_explicit_stable_serialization_fingerprint_and_one_unstarted_next():
    a = _read(); _verify(json.loads(canonical_json(a)))
    assert _digest(dict(reversed(list(a.items())))) == FP
    md = PATH.with_suffix(".md").read_text(encoding="utf-8")
    assert a["status"] in md and a["semantic_decision"] in md and md.count(NEXT) == 1
    assert all(r["component"] in md and r["readiness"] in md for r in a["parameter_evidence_matrix"])
    assert all(r["path"] in md for r in a["internal_evidence"])
    a["next_continuations"].append("FORBIDDEN"); a["artifact_fingerprint"] = _digest(a)
    with pytest.raises(ValueError, match="NEXT_SCOPE"):
        _verify(a)
    a = _read(); a["rationale"] += " tampered"; a["artifact_fingerprint"] = _digest(a)
    with pytest.raises(ValueError, match="DOSSIER_TAMPERED"):
        _verify(a)
