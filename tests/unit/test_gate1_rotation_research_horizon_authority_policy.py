"""Offline horizon-authority audit/conformance witnesses, never a resolver.

The predecessor's synthetic test bindings illustrate necessary rejection rules.
No durations are selected, policies registered, observations generated or stored.
Canonical effectivity is a required independently verified input, not redefined
here; the future actual policy must supply its native validity verifier.
"""
from copy import deepcopy
from datetime import UTC, datetime
from hashlib import sha256
import json
from pathlib import Path
import re
import subprocess

import pytest

from app.fundamentals.diagnostic_comparability import canonical_json, content_fingerprint
from tests.unit import test_gate1_rotation_paired_scenario_research_protocol as previous

ROOT = Path(__file__).resolve().parents[2]
BASELINE = "c75dc4f2b7ab3182ca3ff3541b7a83fb6fce1123"
STEM = "GATE1_ROTATION_RESEARCH_HORIZON_AUTHORITY_POLICY_V1"
PATH = ROOT / "docs/architecture" / (STEM + ".json")
FP = "sha256:aa9d4b211a5a2aba762c0b31af99b2a87fe08e0963865344104e9b87c33b0bb1"
NEXT = "GATE1_ROTATION_RESEARCH_HORIZON_POLICY_PROPOSAL_V1"
D, E, R = previous.D, previous.E, previous.R
MATRIX = {
    "B09_AVAILABILITY": "POLICY_REQUIRED", "B09_AUTHORITY": "BLOCKED",
    "STRATEGY_ROUTING": "DERIVABLE", "CATEGORICAL_HORIZON": "DERIVABLE",
    "NUMERIC_HORIZON": "POLICY_UNSET", "CATEGORY_MAPPING": "POLICY_REQUIRED",
    "DECISION_CUTOFF_BINDING": "READY", "SESSION_CALENDAR": "DERIVABLE",
    "START_BOUNDARY": "READY", "END_BOUNDARY": "POLICY_REQUIRED",
    "MULTI_HORIZON": "POLICY_REQUIRED", "PAIR_SYMMETRY": "READY",
    "HISTORICAL_REPLAY": "SOURCE_NOT_READY", "OUTCOME_MATURITY": "DERIVABLE",
    "POLICY_VERSIONING": "DERIVABLE", "RESEARCH_AUTHORITY": "AUTHORITY_NOT_REGISTERED",
    "FUTURE_PRODUCTION_COMPATIBILITY": "BLOCKED",
    "INSTRUMENT_TERMINAL_COVERAGE": "SOURCE_NOT_READY",
}
FORBIDDEN_ALIASES = (
    "SIGNAL_EXPIRY", "TRADEPLAN", "TARGET_STOP", "PAPER_WINDOWS", "FORWARD_PAPER",
    "WALK_FORWARD", "CALIBRATION_WINDOW", "OOS_DIAGNOSTIC_WINDOW", "HOLDING_STATISTICS",
    "ROTATION_COOLDOWN", "COMPOUNDER_BUSINESS_WINDOW", "DISCOVERY_RECALL_WINDOW",
    "MARKET_EXTREMES_FORWARD", "GATE6_BLACKOUT",
)


def _read(path=PATH):
    return previous.previous.predecessor.proposal._read(path)


def _need(condition, code):
    if not condition:
        raise ValueError(code)


def _digest(value, field):
    return content_fingerprint({k: v for k, v in value.items() if k != field})


def _verify_audit(a):
    _need((a["decision"], a["semantic_decision"]) ==
          ("C", "NEW_HORIZON_AUTHORITY_POLICY_REQUIRED"), "AUTHORITY_NOT_ESTABLISHED")
    c = a["current_resolution"]
    _need(all(c[k] is None for k in (
        "selected_authority", "numeric_duration", "numeric_range", "unit",
        "category_mapping", "endpoint_rule", "precision", "calendar_instance",
        "resolved_horizon",
    )) and c["numeric_grid"] == [] and c["registered"] is False, "PARAMETER_INVENTION")
    _need(c["state"] == "HORIZON_MAPPING_POLICY_REQUIRED", "PARAMETER_INVENTION")
    _need({r["component"]: r["state"] for r in a["readiness"]} == MATRIX
          and len(a["readiness"]) == len(MATRIX), "READINESS_MISREPRESENTED")
    _need(all(value is False for value in a["runtime"].values()), "FORBIDDEN_AUTHORITY")
    _need(a["boundaries"]["start"] == "D"
          and a["boundaries"]["nearest_bar_fallback"] is False, "BOUNDARY_WEAKENED")
    _need(a["next_continuations"] == [NEXT]
          and a["next_continuation_started"] is False, "NEXT_SLICE_SCOPE")
    _need(a["audit_fingerprint"] == _digest(a, "audit_fingerprint") == FP, "AUDIT_TAMPERED")


def _time(value):
    _need(type(value) is str, "HORIZON_INPUT_INVALID")
    result = datetime.fromisoformat(value)
    _need(result.tzinfo is not None and result.utcoffset() is not None, "HORIZON_INPUT_INVALID")
    return result.astimezone(UTC)


def _binding_witness():
    """Use the already frozen synthetic protocol example, not a new observation."""
    o, _, _ = previous._witness()
    h = deepcopy(o["decision"]["horizon"])
    return h, (deepcopy(h["policy"]),), deepcopy(h)


def _require_binding(h, independently_verified_policies, original, *,
                     decision=D, native_effectivity_verified=True,
                     routing_visible=True, mapping_verified=True, calendar_visible=True):
    """Necessary conditions only; does not establish real policy/source authority."""
    _need(h is not None and independently_verified_policies, "HORIZON_AUTHORITY_MISSING")
    # Exact aliases counted once, incompatible eligible records fail regardless of order.
    unique = {canonical_json(p) for p in independently_verified_policies}
    _need(len(unique) == 1, "HORIZON_AUTHORITY_CONFLICTED")
    _need(canonical_json(h["policy"]) in unique, "HORIZON_POLICY_VERSION_INVALID")
    _need(native_effectivity_verified is True, "HORIZON_EFFECTIVITY_UNVERIFIABLE")
    _need(routing_visible is True, "HORIZON_ROUTING_UNAVAILABLE")
    _need(mapping_verified is True, "HORIZON_MAPPING_POLICY_REQUIRED")
    _need(calendar_visible is True, "HORIZON_CALENDAR_UNRESOLVED")
    at = _time(decision)
    p = h["policy"]
    _need(all(_time(p[k]) <= at for k in ("approved_at", "known_at", "effective_from")),
          "HORIZON_INPUT_AFTER_CUTOFF")
    _need(all(_time(ref[k]) <= at for ref in previous._refs(h)
              for k in ("event_at", "known_at")), "HORIZON_INPUT_AFTER_CUTOFF")
    _need(_time(h["start"]) == at, "HORIZON_START_MISMATCH")
    _need(_time(h["end"]) > at, "HORIZON_TERMINAL_UNAVAILABLE")
    normalized = previous._wire(h, "HorizonBinding")
    _need(h["fingerprint"] == _digest(normalized, "fingerprint"), "HORIZON_INPUT_TAMPERED")
    _need(canonical_json(normalized) == canonical_json(previous._wire(original, "HorizonBinding")),
          "HORIZON_INPUT_TAMPERED")
    return normalized


def test_artifact_and_predecessor_chain_remain_exact():
    a = _read()
    _verify_audit(a)
    assert a["baseline_commit"] == BASELINE
    for ref in a["predecessors"]:
        p = _read(ROOT / ref["path"])
        assert p[ref["field"]] == _digest(p, ref["field"]) == ref["fingerprint"]
    previous.test_protocol_and_all_predecessor_boundaries_unchanged()


@pytest.mark.parametrize("path,pin", _read()["inspected_file_fingerprints_lf"].items())
def test_all_frozen_sources_match_baseline(path, pin):
    # Permanent historical pin; current-worktree preservation is separately checked at closure.
    raw = subprocess.check_output(["git", "show", BASELINE + ":" + path])
    assert "sha256:" + sha256(raw.replace(b"\r\n", b"\n")).hexdigest() == pin


def test_b09_keyed_namespace_not_numeric_or_earnings_alias():
    a = _read()
    b = _read(ROOT / "docs/architecture/FUNDAMENTAL_DIAGNOSTIC_REGISTRY_V2_GOVERNANCE_APPROVAL.json")
    row, = [r for r in b["activation_blockers"] if r["blocker_id"] == "B09"]
    assert (row["topic"], row["resolution"], row["activation_scope"]) == (
        "Versioned horizon-policy reference", "OPEN", "ALL_V2_RUNTIME")
    assert a["b09"]["canonical_pointer"].endswith("#/activation_blockers/B09")
    c = _read(ROOT / a["b09"]["candidate"]["path"])
    assert c["horizon_duration_boundaries"] == "UNSET"
    assert c["status"] == "CANDIDATE_NOT_ACTIVE"
    assert c["strict_historical_pit"] == "NOT_READY"
    assert c["policy_fingerprint"] == a["b09"]["candidate"]["fingerprint"]
    assert a["b09"]["semantic_distortion_if_used_as_duration"] is True
    assert "separate identifiers" in a["b09"]["namespace_warning"]


def test_inventory_covers_native_capabilities_without_claiming_live_authority():
    rows = _read()["inventory"]
    assert len(rows) == len({r["id"] for r in rows}) == 28
    fields = {
        "id", "owner", "identifier_version", "semantic_purpose", "representation",
        "decision_time_available", "deterministic", "pit_safe", "replayable",
        "strategy_specific", "mutable_after_cutoff", "native_authority",
        "paired_research_compatibility", "future_live_gate1_compatibility", "reason",
    }
    assert set(FORBIDDEN_ALIASES) <= {r["id"] for r in rows}
    for r in rows:
        assert set(r) == fields and all(isinstance(v, str) and v for v in r.values())
        assert (ROOT / r["owner"]).is_file()
        assert r["owner"] in _read()["inspected_file_fingerprints_lf"]
        assert r["future_live_gate1_compatibility"].startswith("NOT_AUTHORIZED")


@pytest.mark.parametrize("concept", FORBIDDEN_ALIASES)
def test_unrelated_windows_never_supply_research_authority(concept):
    row, = [r for r in _read()["inventory"] if r["id"] == concept]
    assert row["paired_research_compatibility"] == "EXCLUDED_AS_AUTHORITY"
    assert _read()["current_resolution"]["selected_authority"] is None


@pytest.mark.parametrize("field,value", [
    ("numeric_duration", 5), ("numeric_range", [2, 8]), ("numeric_grid", [10, 20, 30]),
    ("unit", "TRADING_SESSIONS"), ("category_mapping", {"POSITIONAL": 20}),
    ("selected_authority", "SELF_HASH"), ("registered", True),
    ("endpoint_rule", "NEAREST_FUTURE_BAR"),
])
def test_resealed_artifact_cannot_invent_numeric_or_borrowed_authority(field, value):
    a = _read()
    a["current_resolution"][field] = value
    a["audit_fingerprint"] = _digest(a, "audit_fingerprint")
    with pytest.raises(ValueError, match="PARAMETER_INVENTION"):
        _verify_audit(a)


def test_start_is_exactly_decision_not_merely_greater_than_or_equal():
    economic = _read(ROOT / _read()["predecessors"][2]["path"])
    assert "start_at_decision" in economic["horizon"]["definition_required"]
    h, policies, original = _binding_witness()
    assert _require_binding(h, policies, original)["start"] == D
    h["start"] = E
    with pytest.raises(ValueError, match="HORIZON_START_MISMATCH"):
        _require_binding(h, policies, original)


@pytest.mark.parametrize("decision", [None, "", "2026-01-05T10:00:00"])
def test_cutoff_required_and_timezone_aware(decision):
    h, policies, original = _binding_witness()
    with pytest.raises(ValueError):
        _require_binding(h, policies, original, decision=decision)


def test_utc_equivalence_and_stable_predecessor_fingerprint():
    h, policies, original = _binding_witness()
    h["start"] = "2026-01-05T15:30:00+05:30"
    h["end"] = "2026-01-07T15:30:00+05:30"
    result = _require_binding(h, policies, original, decision=h["start"])
    assert result == original
    assert content_fingerprint(result) == content_fingerprint(json.loads(canonical_json(result)))


@pytest.mark.parametrize("field", ["approved_at", "known_at", "effective_from"])
def test_future_policy_cannot_be_backdated_with_past_selection(field):
    h, _, original = _binding_witness()
    h["policy"][field] = R
    with pytest.raises(ValueError, match="HORIZON_INPUT_AFTER_CUTOFF"):
        _require_binding(h, (h["policy"],), original)


@pytest.mark.parametrize("field", ["event_at", "known_at"])
def test_future_selection_cannot_use_past_approval(field):
    h, _, original = _binding_witness()
    h["policy"]["selection_ref"][field] = R
    with pytest.raises(ValueError, match="HORIZON_INPUT_AFTER_CUTOFF"):
        _require_binding(h, (h["policy"],), original)


@pytest.mark.parametrize("field,code", [
    ("native_effectivity_verified", "HORIZON_EFFECTIVITY_UNVERIFIABLE"),
    ("routing_visible", "HORIZON_ROUTING_UNAVAILABLE"),
    ("mapping_verified", "HORIZON_MAPPING_POLICY_REQUIRED"),
    ("calendar_visible", "HORIZON_CALENDAR_UNRESOLVED"),
])
def test_unverified_validity_routing_mapping_calendar_fails_closed(field, code):
    h, policies, original = _binding_witness()
    with pytest.raises(ValueError, match=code):
        _require_binding(h, policies, original, **{field: False})


def test_missing_conflicting_and_exact_duplicate_authorities():
    h, policies, original = _binding_witness()
    with pytest.raises(ValueError, match="HORIZON_AUTHORITY_MISSING"):
        _require_binding(h, (), original)
    with pytest.raises(ValueError, match="HORIZON_AUTHORITY_MISSING"):
        _require_binding(None, policies, original)
    assert _require_binding(h, policies * 2, original) == original
    other = deepcopy(policies[0])
    other["fingerprint"] = "sha256:" + "a" * 64
    for order in [(policies[0], other), (other, policies[0])]:
        with pytest.raises(ValueError, match="HORIZON_AUTHORITY_CONFLICTED"):
            _require_binding(h, order, original)


def test_later_version_cannot_replace_pinned_original_even_if_self_rehashed():
    h, policies, original = _binding_witness()
    newer = deepcopy(policies[0])
    newer["version"] = "v2"
    with pytest.raises(ValueError, match="HORIZON_POLICY_VERSION_INVALID"):
        _require_binding(h, (newer,), original)
    assert _require_binding(h, policies, original) == original
    h["end"] = R
    h["fingerprint"] = _digest(h, "fingerprint")
    with pytest.raises(ValueError, match="HORIZON_INPUT_TAMPERED"):
        _require_binding(h, policies, original)


def test_pair_symmetry_uses_entire_binding_not_category_or_elapsed_holding():
    o, trusted, policies = previous._witness()
    o["outcome"]["challenger"]["horizon_fingerprint"] = "sha256:" + "a" * 64
    with pytest.raises(ValueError, match="PAIR_MISMATCH"):
        previous._check(previous._seal(o), trusted, policies)
    assert _read()["symmetry"]["one_binding"] is True
    assert _read()["symmetry"]["different_incumbent_holding_horizon"] is False


def test_future_outcomes_and_completion_cannot_select_horizon_or_early_label():
    previous.test_terminal_label_cannot_be_used_as_decision_feature()
    previous.test_early_maturity_and_missing_completion_proof_fail_closed()
    previous.test_pending_record_cannot_retain_future_completion_evidence()
    previous.test_endpoint_equality_needs_completion_and_outcome_receipts()
    a = _read()
    assert a["selection"]["future_outcome_input"] is False
    assert a["maturity"]["zero_return_default"] is False


def test_missing_terminal_no_nearest_bar_and_explicit_calendar_exceptions():
    previous.test_missing_terminal_and_partial_leg_cannot_be_admitted(
        "terminal_price_ref", None, "GROSS_LABEL_INCOMPLETE")
    a = _read()
    assert a["boundaries"]["unit"].startswith("POLICY_UNSET")
    assert a["boundaries"]["nearest_bar_fallback"] is False
    assert {r["case"] for r in a["boundaries"]["cases"]} == {
        "NORMAL_SESSION", "WEEKEND_OR_HOLIDAY", "SPECIAL_OR_HALF_SESSION",
        "SUSPENDED_OR_NON_TRADING_INSTRUMENT", "MISSING_TERMINAL_BAR",
        "DELISTING", "CORPORATE_ACTION", "EXCHANGE_CLOSURE_OR_OUTAGE",
    }


def test_multihorizon_immutability_no_ai_user_or_research_to_production_promotion():
    a = _read()
    assert a["multi_horizon"]["fanout_authorized"] is False
    assert a["multi_horizon"]["numeric_grid"] == []
    assert a["multi_horizon"]["best_realized_choice"] is False
    assert a["multi_horizon"]["current_admitted_pair"] == "ONE_CANONICAL_BOUND_RESULT"
    assert all(a["selection"][k] is False for k in (
        "hindsight_change", "latest_now_lookup", "runtime_clock", "ambiguous_order_resolution"))
    assert a["selection"]["original_version_pinned"] is True
    assert all(a["provenance"][k] is False for k in (
        "historical_rewrite", "source_repair", "self_hash_authority", "circular_identity_fingerprint"))
    assert a["frozen_boundaries"]["v1"] == "six-gates-production-v1/v1 ACTIVE"
    assert a["frozen_boundaries"]["v2"] == "NOT_ACTIVE"
    assert all(v is False for k, v in a["frozen_boundaries"].items() if k not in {"v1", "v2"})
    assert all(v is False for v in a["runtime"].values())
    for source in (ROOT / "app").rglob("*.py"):
        assert STEM not in source.read_text(encoding="utf-8")


def test_failure_taxonomy_is_deterministic_complete_and_never_a_label():
    rows = _read()["failures"]
    assert len(rows) == len({r["code"] for r in rows}) == 16
    assert all(re.fullmatch("HORIZON_[A-Z_]+", r["code"]) for r in rows)
    assert all(r["admission"] == "NOT_ADMITTED_AS_COMPLETE" and r["label"] is None for r in rows)
    assert {r["code"] for r in rows} >= {
        "HORIZON_AUTHORITY_MISSING", "HORIZON_AUTHORITY_CONFLICTED",
        "HORIZON_MAPPING_POLICY_REQUIRED", "HORIZON_STRATEGY_UNSUPPORTED",
        "HORIZON_ROUTING_UNAVAILABLE", "HORIZON_POLICY_STALE",
        "HORIZON_POLICY_VERSION_INVALID", "HORIZON_CALENDAR_UNRESOLVED",
        "HORIZON_INPUT_AFTER_CUTOFF",
    }
    assert json.loads(canonical_json(rows)) == rows


def test_machine_and_human_scope_and_exactly_one_frozen_next():
    a = _read()
    md = PATH.with_suffix(".md").read_text(encoding="utf-8")
    assert a["status"] in md and a["semantic_decision"] in md
    assert all(row["id"] in md for row in a["inventory"])
    assert all(row["code"] in md for row in a["failures"])
    assert all(row["component"] in md and row["state"] in md for row in a["readiness"])
    assert a["next_continuations"] == [NEXT]
    assert a["next_continuation_started"] is False
    assert md.count(NEXT) == 1
    assert "No full backend suite is required unless runtime/shared behavior changes" in md
