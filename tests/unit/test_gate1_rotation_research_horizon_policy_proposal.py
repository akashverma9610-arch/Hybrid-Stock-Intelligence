"""Offline proposal conformance; no resolver, observations or authority created.

Synthetic rejection witnesses exercise necessary proposal conditions only.
They never select a duration or register a mapping/producer. Source inspection
and historical Git reads preserve the unchanged canonical runtime contracts.
"""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import subprocess

import pytest

from app.fundamentals.diagnostic_comparability import canonical_json, content_fingerprint
from app.intelligence.multi_funnel_discovery import DiscoveryHorizon
from app.intelligence.radar_diagnostic_orchestration import CanonicalDiagnosticHorizon
from tests.unit import test_gate1_rotation_research_horizon_authority_policy as previous

ROOT = Path(__file__).resolve().parents[2]
BASELINE = "328458da03756099dcc9da0d1a5f25cfcd827d22"
STEM = "GATE1_ROTATION_RESEARCH_HORIZON_POLICY_PROPOSAL_V1"
PATH = ROOT / "docs/architecture" / (STEM + ".json")
FP = "sha256:090b3a017060f88c04e76dbd9bd69cd9f00fcbdadbea27faac23ca746b2b5864"
NEXT = "GATE1_ROTATION_RESEARCH_HORIZON_MAPPING_EVIDENCE_FEASIBILITY_V1"
D, E, R = previous.D, previous.E, previous.R
MATRIX = {
    "POLICY_IDENTITY": "READY", "SCOPE": "POLICY_PROPOSED",
    "ALLOWED_DECISION_INPUTS": "POLICY_PROPOSED", "ROUTING_SOURCE": "DERIVABLE",
    "CATEGORICAL_SOURCE": "DERIVABLE", "NUMERIC_DURATION": "POLICY_UNSET",
    "DURATION_UNIT": "POLICY_PROPOSED", "CATEGORY_MAPPING": "POLICY_REQUIRED",
    "DECISION_BINDING": "READY", "START_BOUNDARY": "READY",
    "END_BOUNDARY_CONVENTION": "POLICY_REQUIRED", "CALENDAR_AUTHORITY": "DERIVABLE",
    "PAIR_SYMMETRY": "READY", "MULTI_HORIZON": "POLICY_PROPOSED",
    "MATURITY_INTEGRATION": "DERIVABLE", "PIT_REPLAY": "SOURCE_NOT_READY",
    "CONFLICT_PRECEDENCE": "POLICY_PROPOSED", "PRODUCTION_COMPATIBILITY": "BLOCKED",
    "ACTIVATION_AUTHORITY": "AUTHORITY_NOT_REGISTERED", "CALENDAR_HISTORY": "SOURCE_NOT_READY",
}


def _read(path=PATH):
    return previous._read(path)


def _need(condition, code):
    if not condition:
        raise ValueError(code)


def _digest(value, field="policy_fingerprint"):
    return content_fingerprint({k: v for k, v in value.items() if k != field})


def _verify(a):
    _need((a["policy_id"], a["version"]) == (
        "gate1-rotation-research-horizon-policy", "v1-proposed"), "POLICY_IDENTITY_INVALID")
    _need((a["decision"], a["semantic_decision"]) == (
        "B", "RESEARCH_HORIZON_POLICY_PROPOSAL_READY_WITH_UNRESOLVED_PARAMETERS"), "READINESS_INVALID")
    _need(a["authority"]["activation_status"] == "NOT_ACTIVE"
          and a["authority"]["registered"] is False
          and all(a["authority"][k] is None for k in ("approval_ref", "approved_at", "effective_at")),
          "UNAPPROVED_AUTHORITY")
    n = a["numeric_problem"]
    _need(all(n[k] is None for k in ("numeric_duration", "numeric_range", "effective_unit"))
          and n["numeric_grid"] == [] and n["canonical_numeric_value_available"] is False,
          "NUMERIC_PARAMETER_INVENTED")
    _need(a["mapping"]["rows"] == [] and a["scope"]["approved_scope_rows"] == [],
          "UNAPPROVED_MAPPING")
    _need(a["routing_contract"]["allowed_intermediates"] == ["POSITIONAL", "LONG_TERM"]
          and not a["routing_contract"]["implicit_synonyms"], "CATEGORY_INVENTED")
    t = a["terminal_proposal"]
    _need(t["start"] == "D" and t["no_nearest_bar"] is True and t["no_date_roll_fallback"] is True,
          "BOUNDARY_WEAKENED")
    _need(all(t[k] is None for k in (
        "counting_rule_ref", "terminal_phase", "precision_ref", "partial_decision_session_count",
        "half_or_special_session_count", "endpoint_rule_ref", "end_value")), "END_POLICY_INVENTED")
    _need(a["binding"]["current_binding"] is None
          and a["binding"]["same_complete_binding_both_legs"] is True
          and a["binding"]["leg_specific_duration"] is False, "PAIR_ASYMMETRY")
    _need({x["component"]: x["state"] for x in a["readiness"]} == MATRIX
          and len(a["readiness"]) == len(MATRIX), "READINESS_INVALID")
    _need(all(v is False for v in a["runtime"].values()), "RUNTIME_SCOPE")
    _need(a["next_continuations"] == [NEXT] and a["next_continuation_started"] is False,
          "NEXT_SLICE_SCOPE")
    _need(a["policy_fingerprint"] == _digest(a) == FP, "PROPOSAL_TAMPERED")


def _context_reason(refs, *, decision=D, calendar_verified=True, strategy_category=None):
    """Necessary rejection witness; even unique context cannot authorize a horizon."""
    at = previous._time(decision)
    if not refs:
        return "ROUTING_SOURCE_MISSING"
    seen = {}
    reasons = set()
    categories = set()
    for ref in refs:
        key = ref["id"], ref["version"]
        if key in seen and seen[key] != ref:
            reasons.add("ROUTING_SOURCE_CONFLICT")
        seen[key] = ref
        if previous._time(ref["known_at"]) > at or previous._time(ref["as_of"]) > at:
            reasons.add("INPUT_AFTER_CUTOFF")
        if ref["category"] not in _read()["routing_contract"]["allowed_intermediates"]:
            reasons.add("CATEGORY_UNSUPPORTED")
        categories.add(ref["category"])
    if len(categories) != 1:
        reasons.add("CATEGORY_AMBIGUOUS")
    if strategy_category is not None and strategy_category not in categories:
        reasons.add("STRATEGY_CATEGORY_CONFLICT")
    if calendar_verified is not True:
        reasons.add("CALENDAR_UNRESOLVED")
    if reasons:
        return next(code for code in _read()["conflicts"]["reason_order"] if code in reasons)
    return "HORIZON_MAPPING_POLICY_REQUIRED"  # Empty table; never a resolved result.


def _ref():
    return dict(id="test:original-route", version="test-v1", category="POSITIONAL", known_at=D, as_of=D)


def test_proposal_and_all_predecessors_preserved():
    a = _read()
    _verify(a)
    assert a["baseline_commit"] == BASELINE
    for r in [a["parent"], *a["predecessors"]]:
        old = _read(ROOT / r["path"])
        assert old[r["field"]] == _digest(old, r["field"]) == r["fingerprint"]
    previous.test_artifact_and_predecessor_chain_remain_exact()


@pytest.mark.parametrize("path,pin", _read()["inspected_file_fingerprints_lf"].items())
def test_frozen_source_pins(path, pin):
    raw = subprocess.check_output(["git", "show", BASELINE + ":" + path])
    assert "sha256:" + sha256(raw.replace(b"\r\n", b"\n")).hexdigest() == pin


def test_existing_categories_not_tactical_synonyms_or_duration_authority():
    a = _read()
    assert set(a["routing_contract"]["allowed_intermediates"]) == {x.value for x in DiscoveryHorizon}
    assert CanonicalDiagnosticHorizon.SHORT_TERM.value == "SHORT_TERM"
    assert {x["category"] for x in a["categories"] if x["proposed_intermediate"]} == {"POSITIONAL", "LONG_TERM"}
    assert all(x["numeric_meaning"] is False and x["mapping_required"] is True for x in a["categories"])
    assert a["routing_contract"]["watch_archetype_to_category_fallback"] is False
    assert a["routing_contract"]["pre_breakout_implies_numeric_horizon"] is False
    assert a["routing_contract"]["unavailable_hsi_signal_horizon_repair"] is False
    previous.test_b09_keyed_namespace_not_numeric_or_earnings_alias()


@pytest.mark.parametrize("id", ["MARKET_REGIME", "SECTOR_CONTEXT", "CATALYST_EVENT", "PORTFOLIO_CONTEXT"])
def test_descriptive_context_cannot_drive_duration(id):
    r, = [x for x in _read()["input_admission"] if x["id"] == id]
    assert r["classification"].endswith("NOT_DURATION_DRIVER")


def test_input_matrix_complete_and_pinned():
    rows = _read()["input_admission"]
    assert len(rows) == len({x["id"] for x in rows}) == 12
    for x in rows:
        assert all(isinstance(v, str) and v for v in x.values())
        assert x["source"] in _read()["inspected_file_fingerprints_lf"]
    for key in ["latest_without_explicit_cutoff", "current_policy_identities_are_not_horizon_authority"]:
        assert _read()["routing_contract"][key] is (key != "latest_without_explicit_cutoff")
    previous.test_inventory_covers_native_capabilities_without_claiming_live_authority()


@pytest.mark.parametrize("concept", previous.FORBIDDEN_ALIASES)
def test_unrelated_periods_never_become_authority(concept):
    previous.test_unrelated_windows_never_supply_research_authority(concept)
    assert _read()["numeric_problem"]["unrelated_windows_borrowed"] is False


@pytest.mark.parametrize("field,value", [
    ("numeric_duration", 5), ("numeric_range", [2, 8]), ("numeric_grid", [10, 20, 30]),
    ("effective_unit", "TRADING_SESSIONS"), ("canonical_numeric_value_available", True),
])
def test_rehash_cannot_approve_unsupported_duration(field, value):
    a = _read(); a["numeric_problem"][field] = value; a["policy_fingerprint"] = _digest(a)
    with pytest.raises(ValueError, match="NUMERIC_PARAMETER_INVENTED"):
        _verify(a)


@pytest.mark.parametrize("field", ["approved_at", "effective_at", "approval_ref"])
def test_no_implicit_effectivity_or_registration(field):
    a = _read(); a["authority"][field] = D; a["policy_fingerprint"] = _digest(a)
    with pytest.raises(ValueError, match="UNAPPROVED_AUTHORITY"):
        _verify(a)


def test_mapping_shape_empty_closed_and_not_approved():
    a = _read(); m = a["mapping"]
    assert m["status"] == "EMPTY_UNAPPROVED_NOT_ACTIVE"
    assert m["schema_role"] == "DOCUMENT_ONLY_SHAPE_NOT_RUNTIME_MODEL"
    assert set(m["row_shape"]) == {
        "mapping_id", "mapping_version", "row_id", "category", "category_source_contract_ref",
        "supported_strategy_refs", "supported_archetypes", "supported_instrument_state_refs",
        "numeric_duration", "unit", "counting_rule_ref", "terminal_rule_ref", "precision_rule_ref",
        "justification_refs", "approval_ref", "selection_ref", "effective_version",
        "effectivity_verifier_ref", "activation_status", "supersedes_ref", "fingerprint",
    }
    a["mapping"]["rows"] = [{"category": "POSITIONAL", "numeric_duration": 20}]
    a["policy_fingerprint"] = _digest(a)
    with pytest.raises(ValueError, match="UNAPPROVED_MAPPING"):
        _verify(a)
    assert _context_reason([_ref()]) == "HORIZON_MAPPING_POLICY_REQUIRED"


@pytest.mark.parametrize("field", ["known_at", "as_of"])
def test_future_input_cannot_select_duration(field):
    r = _ref(); r[field] = R
    assert _context_reason([r]) == "INPUT_AFTER_CUTOFF"
    assert _read()["selection"]["forward_evidence"] is False


@pytest.mark.parametrize("category", ["TACTICAL", "SHORT_TERM", "PRE_BREAKOUT", "UNKNOWN", "20"])
def test_unknown_or_descriptive_category_fails_without_default(category):
    r = _ref(); r["category"] = category
    assert _context_reason([r]) == "CATEGORY_UNSUPPORTED"


def test_missing_conflicting_multiple_routing_and_calendar_fail_closed():
    r = _ref(); other = dict(r, id="test:second-route", category="LONG_TERM")
    assert _context_reason([]) == "ROUTING_SOURCE_MISSING"
    for refs in [(r, other), (other, r)]:
        assert _context_reason(refs) == "CATEGORY_AMBIGUOUS"
    conflict = dict(r, category="LONG_TERM")
    for refs in [(r, conflict), (conflict, r)]:
        assert _context_reason(refs) == "ROUTING_SOURCE_CONFLICT"
    assert _context_reason([r, deepcopy(r)]) == "HORIZON_MAPPING_POLICY_REQUIRED"
    assert _context_reason([r], strategy_category="LONG_TERM") == "STRATEGY_CATEGORY_CONFLICT"
    assert _context_reason([r], calendar_verified=False) == "CALENDAR_UNRESOLVED"
    future_conflict = dict(conflict, known_at=R)
    for refs in [(r, future_conflict), (future_conflict, r)]:
        assert _context_reason(refs) == "INPUT_AFTER_CUTOFF"


def test_cutoff_utc_equivalence_and_no_runtime_time():
    assert _context_reason([_ref()], decision="2026-01-05T15:30:00+05:30") == "HORIZON_MAPPING_POLICY_REQUIRED"
    assert _read()["selection"]["runtime_clock"] is False
    assert _read()["selection"]["look_up_latest_now"] is False
    for decision in (None, "", "2026-01-05T10:00:00"):
        with pytest.raises(ValueError):
            _context_reason([_ref()], decision=decision)


def test_start_pair_and_terminal_constraints_preserve_predecessor():
    previous.test_start_is_exactly_decision_not_merely_greater_than_or_equal()
    previous.test_pair_symmetry_uses_entire_binding_not_category_or_elapsed_holding()
    previous.test_missing_terminal_no_nearest_bar_and_explicit_calendar_exceptions()
    a = _read()
    assert a["terminal_proposal"]["start"] == "D"
    assert a["terminal_proposal"]["no_nearest_bar"] is True
    assert a["binding"]["same_complete_binding_both_legs"] is True
    assert len(a["terminal_proposal"]["cases"]) == 9
    assert {x["unit"] for x in a["duration_units"]} == {
        "TRADING_SESSIONS", "CALENDAR_DAYS", "ELAPSED_TIMESTAMP_DURATION"}
    assert all(x["effective"] is False for x in a["duration_units"])


@pytest.mark.parametrize("field,value", [("start", "NEXT_CLOSE"), ("no_nearest_bar", False)])
def test_resealed_start_or_terminal_fallback_is_rejected(field, value):
    a = _read(); a["terminal_proposal"][field] = value; a["policy_fingerprint"] = _digest(a)
    with pytest.raises(ValueError, match="BOUNDARY_WEAKENED"):
        _verify(a)


def test_no_new_partial_session_or_terminal_phase_default():
    a = _read(); a["terminal_proposal"]["partial_decision_session_count"] = True
    a["policy_fingerprint"] = _digest(a)
    with pytest.raises(ValueError, match="END_POLICY_INVENTED"):
        _verify(a)


def test_historical_versions_maturity_and_multi_horizon_remain_frozen():
    previous.test_later_version_cannot_replace_pinned_original_even_if_self_rehashed()
    previous.test_future_outcomes_and_completion_cannot_select_horizon_or_early_label()
    a = _read()
    assert a["selection"]["policy_version_pin"] is True
    assert a["selection"]["post_outcome_change"] is False
    assert a["historical_replay"]["later_policy_rewrite"] is False
    assert a["historical_replay"]["historical_backdating"] is False
    assert a["multi_horizon"]["proposal"] == "EXACTLY_ONE_CANONICAL_HORIZON_PER_PAIR"
    assert a["multi_horizon"]["numeric_grid"] == []
    assert a["multi_horizon"]["separate_observation_fanout"] is False
    assert a["multi_horizon"]["best_return_selection"] is False
    assert a["maturity"]["valid_horizon_before_end"] == "PENDING_MATURITY"
    assert a["maturity"]["outcome_can_select_duration"] is False


def test_research_only_no_ai_user_broker_cohort_or_gate_authority():
    a = _read()
    assert a["authority"]["scope"] == "RESEARCH_ONLY"
    assert a["authority"]["production_reuse"] == "SEPARATE_EXPLICIT_APPROVAL_REQUIRED"
    for key in ("ai_authority", "user_arbitrary_duration_authority", "proposal_hash_confers_authority", "owner_registration_created"):
        assert a["authority"][key] is False
    assert all(x is False for x in a["runtime"].values())
    assert a["frozen_boundaries"]["v1"] == "six-gates-production-v1/v1 ACTIVE"
    assert a["frozen_boundaries"]["v2"] == "NOT_ACTIVE"
    assert all(v is False for k, v in a["frozen_boundaries"].items() if k not in {"v1", "v2", "B09", "start"})
    for path in (ROOT / "app").rglob("*.py"):
        assert STEM not in path.read_text(encoding="utf-8")


def test_policy_serialization_reason_order_and_document_agree():
    a = _read(); _verify(json.loads(canonical_json(a)))
    assert _digest(a) == _digest(dict(reversed(list(a.items())))) == FP
    codes = a["conflicts"]["reason_order"]
    assert len(codes) == len(set(codes)) == 15
    assert a["conflicts"]["label_when_blocked"] is None
    assert a["conflicts"]["fallback"] is False
    md = PATH.with_suffix(".md").read_text(encoding="utf-8")
    assert a["status"] in md and a["semantic_decision"] in md
    for x in a["input_admission"]:
        assert x["id"] in md and x["classification"] in md
    for x in a["readiness"]:
        assert x["component"] in md and x["state"] in md
    assert all(code in md for code in codes)
    assert md.count(NEXT) == 1
    assert a["next_continuations"] == [NEXT] and a["next_continuation_started"] is False
