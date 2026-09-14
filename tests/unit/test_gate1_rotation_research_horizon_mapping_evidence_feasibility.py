"""Offline evidence-feasibility conformance, not a horizon resolver or study.

The SQLite findings are a dated, sanitized audit receipt. Tests never open a
production database or create decisions, outcomes, durations or authority.
Necessary PIT/binding rejection witnesses reuse the frozen predecessor tests.
"""
from copy import deepcopy
from datetime import UTC, date, datetime
from hashlib import sha256
import json
from pathlib import Path
import subprocess

import pytest

from app.fundamentals.diagnostic_comparability import canonical_json, content_fingerprint
from app.historical.canonical_market_session_event_time import TradingDayState
from app.historical.nse_capital_market_session_evidence_2022_2026 import (
    nse_capital_market_calendar_2022_2026,
)
from tests.unit import test_gate1_rotation_research_horizon_policy_proposal as previous

ROOT = Path(__file__).resolve().parents[2]
BASELINE = "e2b5336bc17788d859dec1f0d3202c2134bbd0c2"
STEM = "GATE1_ROTATION_RESEARCH_HORIZON_MAPPING_EVIDENCE_FEASIBILITY_V1"
PATH = ROOT / "docs/architecture" / (STEM + ".json")
FP = "sha256:7892a8afe5d503261567d68f3144ca7eb28934a2e8b6c93bd63ce9ffbd3c8dfc"
NEXT = "GATE1_ROTATION_RESEARCH_HORIZON_BOOTSTRAP_GOVERNANCE_V1"
MAPPING = {
    "POSITIONAL_EVIDENCE": "EVIDENCE_INSUFFICIENT",
    "LONG_TERM_EVIDENCE": "EVIDENCE_INSUFFICIENT",
    "STRATEGY_DURATION": "POLICY_REQUIRED",
    "PAIRED_HISTORICAL_OUTCOMES": "SOURCE_NOT_READY",
    "PAPER_TRADE_EVIDENCE": "EVIDENCE_INSUFFICIENT",
    "FORWARD_STUDY_EVIDENCE": "EVIDENCE_INSUFFICIENT",
    "OOS_EVIDENCE": "SOURCE_NOT_READY", "WALK_FORWARD_EVIDENCE": "SOURCE_NOT_READY",
    "CATEGORY_MAPPING_METHOD": "POLICY_REQUIRED",
    "NUMERIC_DURATION": "EVIDENCE_INSUFFICIENT", "DURATION_UNIT": "POLICY_REQUIRED",
    "BOOTSTRAP_FEASIBILITY": "BLOCKED", "CALIBRATION_THRESHOLDS": "POLICY_REQUIRED",
    "MAPPING_STABILITY": "CALIBRATION_REQUIRED", "PRODUCTION_COMPATIBILITY": "BLOCKED",
}
COUNTING = {
    "D_SESSION_ALIGNMENT": "DERIVABLE", "START_SESSION_TREATMENT": "POLICY_REQUIRED",
    "SESSION_COUNTING": "POLICY_REQUIRED", "HOLIDAY_HANDLING": "DERIVABLE",
    "SPECIAL_SESSIONS": "POLICY_REQUIRED", "SUSPENSION_HANDLING": "SOURCE_NOT_READY",
    "TERMINAL_SESSION_SELECTION": "POLICY_REQUIRED", "MISSING_BAR_BEHAVIOR": "READY",
    "DELISTING_BEHAVIOR": "SOURCE_NOT_READY", "CORPORATE_ACTION_TRANSITION": "SOURCE_NOT_READY",
    "CALENDAR_PROVENANCE": "DERIVABLE", "HISTORICAL_CALENDAR_COMPLETENESS": "SOURCE_NOT_READY",
    "NEXT_TRADABLE_SESSION": "DERIVABLE", "VENUE_ALIGNMENT": "POLICY_REQUIRED",
}
FALSE_BOUNDARIES = (
    "retroactive_approval", "future_outcomes_in_duration_selection", "nearest_bar_fallback",
    "date_roll_fallback", "current_time_interpretation", "current_membership_backfill",
    "modern_calendar_backcast", "multi_horizon_best_result_selection",
    "OOS_reused_for_selection", "per_observation_hindsight_selection",
    "historical_relabeling", "unexpected_closure_may_rewrite_frozen_endpoint",
)
TRUE_BOUNDARIES = (
    "research_only", "one_immutable_binding_for_both_legs", "one_horizon_per_pair",
    "exact_original_decision_required", "selection_uses_only_D_visible_evidence",
    "native_source_fingerprint_verified_before_wrapper",
    "policy_approval_selection_effective_at_D_required",
    "terminal_requires_R_at_or_after_end_and_completion_and_known_price",
    "late_admin_replay_metadata_not_evidence",
)


def _read():
    return previous._read(PATH)


def _digest(a):
    return content_fingerprint({k: v for k, v in a.items() if k != "artifact_fingerprint"})


def _need(ok, code):
    if not ok:
        raise ValueError(code)


def _verify(a):
    """Validate this frozen audit, not potential new mapping authority."""
    _need(a["baseline_commit"] == BASELINE and a["decision"] == "D"
          and a["semantic_decision"] == "HORIZON_MAPPING_BOOTSTRAP_BLOCKED", "DECISION_INVALID")
    _need(a["authority"]["v1"] == dict(policy_id="six-gates-production-v1", version="v1", status="ACTIVE")
          and a["authority"]["v2"] == dict(policy_id="execution-gate-policy-v2-proposed",
                                         version="v2-proposal.4", status="NOT_ACTIVE"), "ACTIVATION_CHANGED")
    h = a["authority"]["research_horizon"]
    _need(h["approved"] is False and h["registered"] is False and h["approval_ref"] is None
          and h["status"] == "NOT_ACTIVE" and a["authority"]["self_hash_confers_authority"] is False,
          "AUTHORITY_INVENTED")
    p = a["unresolved_parameters"]
    _need(all(p[k] is None for k in (
        "numeric_duration", "numeric_range", "effective_duration_unit", "counting_rule",
        "terminal_price_rule", "endpoint_rule", "minimum_sample_count", "stability_threshold",
        "independent_seed",
    )) and p["numeric_grid"] == [] and p["category_mapping"] == [], "PARAMETER_INVENTED")
    b = a["preservation"]
    _need(b["start"] == "D" and all(b[k] is True for k in TRUE_BOUNDARIES)
          and all(b[k] is False for k in FALSE_BOUNDARIES), "BOUNDARY_WEAKENED")
    for field, expected in (("mapping_readiness", MAPPING), ("counting_readiness", COUNTING)):
        _need(len(a[field]) == len(expected)
              and {r["component"]: r["state"] for r in a[field]} == expected, "READINESS_UPGRADED")
    _need(all(r["automatic_mapping_authority"] is False
              for r in a["evidence_classes"] + a["inventory"]), "EVIDENCE_PROMOTED")
    _need(all(r["threshold_value"] is None for r in a["statistical_requirements"])
          and all(r["selected"] is False for r in a["methods"]), "CALIBRATION_INVENTED")
    _need(a["decision_origins"]["eligible_canonical_pairs_observed"] == 0
          and a["decision_origins"]["raw_OHLCV_can_create_decisions"] is False
          and a["decision_origins"]["links_are_paired_outcomes"] is False, "ORIGINS_FABRICATED")
    _need(a["bootstrap"]["state"] == "BLOCKED"
          and a["bootstrap"]["classification"] == "NO_SAFE_INDEPENDENT_BOOTSTRAP_SOURCE"
          and a["bootstrap"]["current_option_selected"] is None, "BOOTSTRAP_BYPASSED")
    _need(all(v is False for v in a["runtime"].values()), "RUNTIME_SCOPE")
    _need(a["next_continuations"] == [NEXT] and a["next_continuation_started"] is False, "NEXT_SCOPE")
    _need(a["artifact_fingerprint"] == _digest(a) == FP, "AUDIT_TAMPERED")


def test_frozen_artifact_and_complete_predecessor_chain():
    a = _read()
    _verify(a)
    for ref in [a["parent"], *a["predecessors"]]:
        p = ROOT / ref["path"]
        old = previous._read(p)
        assert old[ref["field"]] == content_fingerprint(
            {k: v for k, v in old.items() if k != ref["field"]}
        ) == ref["fingerprint"]
        raw = subprocess.check_output(["git", "show", BASELINE + ":" + ref["path"]])
        assert p.read_bytes().replace(b"\r\n", b"\n") == raw.replace(b"\r\n", b"\n")
    previous.test_proposal_and_all_predecessors_preserved()


@pytest.mark.parametrize("path,pin", _read()["inspected_file_fingerprints_lf"].items())
def test_historical_source_pins_at_audited_baseline(path, pin):
    # Pin the inspected revision, not arbitrary future source updates.
    raw = subprocess.check_output(["git", "show", BASELINE + ":" + path])
    assert "sha256:" + sha256(raw.replace(b"\r\n", b"\n")).hexdigest() == pin


def test_inventory_is_complete_source_pinned_and_not_empirical_authority():
    a = _read()
    required = {
        "id", "source", "owner", "purpose", "numeric_duration", "evidence_class", "pit",
        "replay_and_sample_provenance", "calibration_validity", "category_compatibility",
        "suitability", "automatic_mapping_authority",
    }
    assert len(a["inventory"]) == len({r["id"] for r in a["inventory"]}) == 24
    classes = {r["classification"] for r in a["evidence_classes"]}
    assert classes == {
        "CANONICAL_POLICY_EVIDENCE", "EMPIRICAL_CALIBRATION_EVIDENCE", "BACKTEST_ONLY_EVIDENCE",
        "DESCRIPTIVE_ONLY", "INSUFFICIENT", "INCOMPATIBLE", "PIT_UNSAFE",
    }
    for r in a["inventory"]:
        assert set(r) == required and r["source"] in a["inspected_file_fingerprints_lf"]
        assert r["evidence_class"] in classes
        assert all(isinstance(r[k], str) and r[k] for k in required - {"automatic_mapping_authority"})
    assert all(r["evidence_class"] != "EMPIRICAL_CALIBRATION_EVIDENCE" for r in a["inventory"])


@pytest.mark.parametrize("id", ["PRICES", "ROTATION_HOLDING", "PAPER", "FORWARD_PAPER",
                               "BACKTEST", "WALK_FORWARD", "PERFORMANCE", "LIFECYCLE"])
def test_rehash_cannot_promote_descriptive_incompatible_or_pit_unsafe_evidence(id):
    a = _read()
    next(r for r in a["inventory"] if r["id"] == id)["automatic_mapping_authority"] = True
    a["artifact_fingerprint"] = _digest(a)
    with pytest.raises(ValueError, match="EVIDENCE_PROMOTED"):
        _verify(a)


@pytest.mark.parametrize("field", [
    "numeric_duration", "numeric_range", "effective_duration_unit", "counting_rule",
    "terminal_price_rule", "endpoint_rule", "minimum_sample_count", "stability_threshold",
    "independent_seed", "numeric_grid", "category_mapping",
])
def test_no_resealed_numeric_seed_sample_threshold_unit_or_mapping(field):
    a = _read()
    a["unresolved_parameters"][field] = "SYNTHETIC_UNAPPROVED_VALUE"
    a["artifact_fingerprint"] = _digest(a)
    with pytest.raises(ValueError, match="PARAMETER_INVENTED"):
        _verify(a)


@pytest.mark.parametrize("field", FALSE_BOUNDARIES + TRUE_BOUNDARIES)
def test_resealed_pit_start_symmetry_and_optimization_boundaries_cannot_weaken(field):
    a = _read()
    a["preservation"][field] = not a["preservation"][field]
    a["artifact_fingerprint"] = _digest(a)
    with pytest.raises(ValueError, match="BOUNDARY_WEAKENED"):
        _verify(a)


def test_original_D_and_pair_maturity_use_existing_rejection_witnesses():
    previous.test_start_pair_and_terminal_constraints_preserve_predecessor()
    previous.test_historical_versions_maturity_and_multi_horizon_remain_frozen()
    previous.test_cutoff_utc_equivalence_and_no_runtime_time()
    for field in ("known_at", "as_of"):
        previous.test_future_input_cannot_select_duration(field)
    a = _read()
    a["preservation"]["start"] = "NEXT_SESSION"
    a["artifact_fingerprint"] = _digest(a)
    with pytest.raises(ValueError, match="BOUNDARY_WEAKENED"):
        _verify(a)


@pytest.mark.parametrize("matrix", ["mapping_readiness", "counting_readiness"])
def test_unavailable_readiness_cannot_be_resealed_as_ready(matrix):
    a = _read()
    next(r for r in a[matrix] if r["state"] != "READY")["state"] = "READY"
    a["artifact_fingerprint"] = _digest(a)
    with pytest.raises(ValueError, match="READINESS_UPGRADED"):
        _verify(a)


def test_categories_are_separate_and_neither_has_a_mapping():
    a = _read()
    assert {r["category"] for r in a["categories"]} == {"POSITIONAL", "LONG_TERM"}
    for r in a["categories"]:
        assert r["result"] == "NO_MAPPING_YET"
        assert all(r[k] is False for k in ("single_numeric_supported", "range_supported", "mapping_rule_supported"))
        assert r["cross_strategy_conflict"]
    previous.test_missing_conflicting_multiple_routing_and_calendar_fail_closed()


def test_dated_readonly_capture_proves_no_canonical_origins_not_absence_of_all_human_decisions():
    a = _read()
    c = a["data_audit"]
    assert c["access"] == "SQLITE_URI_MODE_RO_QUERY_ONLY" and c["single_read_transaction"] is True
    assert c["observed_at_utc"] == "2026-09-14T17:32:36.916818+00:00"
    counts = c["table_counts"]
    assert counts["historical_bars"] == 2663799 and counts["historical_bar_conflicts"] == 795
    assert all(n == 0 for name, n in counts.items() if name not in {"historical_bars", "historical_bar_conflicts"})
    assert c["bounded_query_failures"] == []
    assert a["price_audit"]["decision_link_types"] == {"SELL_SIDE_DECISION_EVENT": 43}
    assert a["price_audit"]["decision_link_rows_inspected"] == c["snapshot_family_counts"]["DECISION_OUTCOME_LINK"]
    runs = a["metadata_audit"]["families"]["FORWARD_PAPER_RUN"]
    assert len(runs) == 3
    assert all(r["metadata"][k] == 0 for r in runs for k in ("admitted", "entries", "exits", "sessions_processed"))
    origins = a["decision_origins"]
    assert {r["component"] for r in origins["field_readiness"]} == {
        "ORIGINAL_DECISION_ID", "D_CUTOFF", "INCUMBENT", "CHALLENGER",
        "EXACT_PARCEL", "STRATEGY_CATEGORY", "ARCHIVED_EVIDENCE",
    }
    assert all(r["state"] == "SOURCE_NOT_READY" for r in origins["field_readiness"])
    assert a["price_audit"]["price_sample"]["rows"] == 1000
    assert "not statistical" in a["price_audit"]["price_sample"]["method"]


def test_bootstrap_is_explicit_not_arbitrary_seed_or_historical_relabeling():
    b = _read()["bootstrap"]
    assert len(b["dependency"]) == 3 and len(b["safe_options_not_approved"]) == 3
    assert b["raw_origin_can_precede_outcome"] is True
    assert b["cannot_use_later_policy_for_historical_D"] is True
    assert all(b[k] is False for k in (
        "independent_numeric_policy_found", "externally_governed_prior_found", "genuine_origins_sufficient",
    ))


def test_methods_and_statistical_thresholds_are_unselected_not_duration_search():
    a = _read()
    assert len(a["methods"]) == len({r["method"] for r in a["methods"]}) == 6
    for r in a["methods"]:
        assert all(r[k] for k in ("interpretability", "overfitting", "hindsight_leakage",
                                  "sample_dependence", "regime_sensitivity", "reproducibility",
                                  "protocol_compatibility"))
    assert all(r["threshold_governance"] == "CALIBRATION_POLICY_REQUIRED"
               and r["threshold_value"] is None for r in a["statistical_requirements"])
    assert len(a["statistical_requirements"]) == 12
    assert all(r["state"] == "POLICY_REQUIRED" for r in a["duration_units"])


def test_actual_calendar_forward_only_rule_and_unresolved_special_phase():
    a = _read()
    assert a["calendar"]["coverage_classification"] == "INSUFFICIENT"
    assert a["calendar"]["historical_ordinary_complete"] is False
    calendar = nse_capital_market_calendar_2022_2026()
    cutoff = datetime(2026, 9, 7, 12, tzinfo=UTC)
    for day in (date(2022, 6, 6), date(2023, 6, 5), date(2024, 6, 3),
                date(2025, 6, 2), date(2026, 9, 4)):
        assert calendar.resolve_trading_day(day, as_of=cutoff).state is TradingDayState.UNKNOWN
    assert calendar.resolve_trading_day(date(2026, 9, 7), as_of=cutoff).state is TradingDayState.REGULAR_TRADING_DAY
    assert calendar.resolve_trading_day(date(2026, 9, 14), as_of=cutoff).state is TradingDayState.HOLIDAY
    assert calendar.phases_for(date(2026, 11, 8), as_of=cutoff) == ()
    earlier = datetime(2026, 9, 5, 16, 46, tzinfo=UTC)
    assert calendar.resolve_trading_day(date(2026, 9, 7), as_of=earlier).state is TradingDayState.UNKNOWN


def test_lifecycle_price_and_session_identity_not_upgraded_to_pit_completeness():
    a = _read()
    cases = {r["component"]: r["state"] for r in a["instrument_cases"]}
    assert cases == {"ACTIVE": "DERIVABLE", "SUSPENDED": "SOURCE_NOT_READY",
                     "DELISTED": "PIT_NOT_READY", "RENAMED_REIDENTIFIED": "DERIVABLE",
                     "MERGER_DEMERGER": "SOURCE_NOT_READY", "SYMBOL_TRANSITION": "DERIVABLE",
                     "CORPORATE_ACTION": "SOURCE_NOT_READY"}
    assert a["calendar"]["session_identity_not_calendar"] is True
    assert a["price_alignment"]["state"] == "PIT_NOT_READY"
    samples = a["metadata_audit"]["families"]["HISTORICAL_SECURITY_LIFECYCLE_EVIDENCE"]
    assert len(samples) == 5 and all(r["metadata"]["historical_known_at"] is None for r in samples)
    assert a["price_alignment"]["numeric_prices_exported"] is False


@pytest.mark.parametrize("field", _read()["runtime"])
def test_no_registration_cohort_labels_model_or_gate_side_effect_declaration(field):
    a = _read()
    a["runtime"][field] = True
    a["artifact_fingerprint"] = _digest(a)
    with pytest.raises(ValueError, match="RUNTIME_SCOPE"):
        _verify(a)


def test_active_V1_inactive_V2_unchanged_and_no_application_consumer():
    previous.test_research_only_no_ai_user_broker_cohort_or_gate_authority()
    pins = _read()["inspected_file_fingerprints_lf"]
    for path in ("app/gates/engine.py", "app/gates/production_policy.py", "app/scoring/engine.py",
                 "app/rotation/engine.py", "app/portfolio/models.py"):
        assert path in pins
    for path in (ROOT / "app").rglob("*.py"):
        assert STEM not in path.read_text(encoding="utf-8")


def test_serialization_fingerprint_documents_and_exactly_one_next_scope():
    a = _read()
    _verify(json.loads(canonical_json(a)))
    assert _digest(dict(reversed(list(a.items())))) == FP
    corrupted = deepcopy(a)
    corrupted["audit_limits"].append("unapproved assertion")
    corrupted["artifact_fingerprint"] = _digest(corrupted)
    with pytest.raises(ValueError, match="AUDIT_TAMPERED"):
        _verify(corrupted)
    md = PATH.with_suffix(".md").read_text(encoding="utf-8")
    assert a["status"] in md and a["semantic_decision"] in md
    for key in ("mapping_readiness", "counting_readiness", "inventory"):
        assert all(r.get("component", r.get("id")) in md for r in a[key])
    assert md.count(NEXT) == 1
    a["next_continuations"].append("FORBIDDEN_NEXT")
    a["artifact_fingerprint"] = _digest(a)
    with pytest.raises(ValueError, match="NEXT_SCOPE"):
        _verify(a)
