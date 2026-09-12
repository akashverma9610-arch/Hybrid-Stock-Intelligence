"""Declarative proposal checks, not a second gate or a V2 runtime evaluator.

V1 source pins are deliberate approval guards: later changes require an explicit
governance review, not silently refreshing these accepted baseline fingerprints.
"""
from __future__ import annotations

import ast
from copy import deepcopy
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import re

import pytest

from app.fundamentals.diagnostic_comparability import canonical_json, content_fingerprint
from app.registry.canonical import EXECUTION_GATES, EXECUTION_GATE_REGISTRY_VERSION


ROOT = Path(__file__).resolve().parents[2]
ARTIFACT = ROOT / "docs/architecture/EARNINGS_BLACKOUT_POLICY_V2_PROPOSAL.json"
GATE_IDS = [
    "GATE_1_ROTATION", "GATE_2_VELOCITY", "GATE_3_SURVEILLANCE",
    "GATE_4_TRADE_PLAN", "GATE_5_HEAT", "GATE_6_EARNINGS",
]
METHODS = ["_rotation", "_velocity", "_surveillance", "_plan", "_heat", "_blackout"]
SOURCE_PATHS = [
    "app/gates/engine.py", "app/gates/production_policy.py", "app/registry/canonical.py",
    "app/gates/source_authority.py", "app/gates/version_compatibility.py",
]
GATE_DEFINITION_SHAPE = {
    "gate_id": int, "canonical_name": str, "purpose": str, "required_inputs": [str],
    "intended_policy": str, "parameters_status": str, "missing_data_behavior": str,
    "calculation_version": str,
}
# Test-only closed schema: no runtime model, registry, lookup, or new dependency.
SCHEMA = {
    **{key: str for key in (
        "schema_version", "policy_id", "policy_version_candidate", "parent_policy_version",
        "parent_version", "baseline_commit", "status", "activation_status",
        "gate_registry_version", "next_continuation", "proposal_fingerprint",
    )},
    "policy_lifecycle": [str], "gate_ids": [str],
    "source_fingerprints_lf": {path: str for path in SOURCE_PATHS},
    "unchanged_gates": [{
        "gate_id": str, "registry_id": int, "definition_reference": str, "method": str,
        "definition_fingerprint": str, "implementation_fingerprint": str,
    }],
    "gate6_v1": {
        "definition": GATE_DEFINITION_SHAPE, "definition_fingerprint": str,
        "implementation_fingerprint": str, "blackout_sessions": int,
        "absence_is_pass": bool, "outside_or_past_scalar_result": str, "mutated": bool,
    },
    "gate6_proposed": {
        "gate_id": str, "name": str, "purpose": str, "entry_contexts": [str],
        "management_exemptions": [str], "management_gate_outcome": str,
        "management_exemption_is_clearance": bool,
        "result_mapping": {"BLOCKED": str, "UNKNOWN": str}, "clear_support_state": str,
        "unknown_is_bad_stock": bool, "unknown_allows_entry_ready": bool,
    },
    "required_schedule_evidence": [str],
    "known_at_basis": {
        **{k: str for k in ("perspective", "contract", "state_required", "basis", "visibility", "lifecycle_selection")},
        **{k: bool for k in ("source_public_time_retained_separately", "caller_retrieved_at_sufficient", "date_only_to_datetime_invention", "retroactive_block")},
    },
    "unknown_reasons": [str],
    "hard_block_semantics": {
        **{k: bool for k in ("requires_all_schedule_evidence", "window_operational", "policy_and_source_effective_at_or_before_as_of", "cancelled_event_provides_positive_block", "superseded_event_provides_positive_block", "earlier_legitimate_entry_invalidated")},
        "causal_condition": str, "window_formula": type(None), "revisions_effect": str,
        "cancellation_effect": str,
    },
    "soft_context": {"name": str, "status": str, "channel": str, "source": str, "uses": [str], "forbidden": [str]},
    "horizon_policy": {
        "states": [str], "state": str, "value": type(None), "unit": type(None),
        "precision_and_boundaries": type(None), "calibration_required": bool,
        "inherits_v1_five": bool, "b14": str, "b09": str,
    },
    "decision_cases": [{"case": str, "state": str, "gate_outcome": str, "reason": str}],
    "replay": {k: bool for k in (
        "v1_records_immutable", "explicit_policy_id_version_fingerprint",
        "as_of_source_and_regulatory_versions_required", "local_observation_and_revision_lineage_required",
        "current_data_backfill", "implicit_latest_policy",
    )},
    "pilot": {k: bool for k in (
        "research_continues_when_unknown", "unknown_bypass_allowed", "horizon_unset_blocks_activation",
        "complete_historical_calendar_required_for_prospective_research", "entry_ready_usability_requires_policy_review",
    )},
    "downstream_impact": [{"consumer": str, "classification": str, "reference": str, "requirement": str}],
    "activation_blockers": [{"id": str, "area": str, "classification": str}],
    "calibration_requirements": [str],
    "reuse": {k: str for k in ("schedule_identity", "known_at", "coverage", "trading_calendar", "gate_result", "event_evidence")},
    "boundaries": {
        **{k: bool for k in (
            "v1_active", "gate_policy_v2_active", "v2_diagnostic_active", "v2_shadow_only",
            "registered", "runtime_wired", "new_gate_engine", "new_calendar", "new_diagnostic",
            "ai_decision_authority", "no_unverified_calendar_clearance", "no_retroactive_blackout",
            "no_ai_predicted_earnings_date",
        )},
        **{k: str for k in ("b08", "current_identity_contract", "prospective_first_observed_contract", "pilot_simplicity_rule")},
    },
    "next_continuation_started": bool,
}


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("DUPLICATE_PROPOSAL_KEY")
        result[key] = value
    return result


def _read():
    return json.loads(ARTIFACT.read_text(encoding="utf-8"), object_pairs_hook=_unique_object)


def _schema(value, shape):
    if isinstance(shape, dict):
        assert type(value) is dict and value.keys() == shape.keys()
        for key in shape:
            _schema(value[key], shape[key])
    elif isinstance(shape, list):
        assert type(value) is list and value
        assert len({canonical_json(item) for item in value}) == len(value)
        for item in value:
            _schema(item, shape[0])
    else:
        assert type(value) is shape
        if shape is str:
            assert value.strip() == value and value


def _method_fingerprint(name):
    source = (ROOT / SOURCE_PATHS[0]).read_text(encoding="utf-8")
    engine = next(n for n in ast.parse(source).body if isinstance(n, ast.ClassDef) and n.name == "ExecutionGateEngine")
    method = next(n for n in engine.body if isinstance(n, ast.FunctionDef) and n.name == name)
    return "sha256:" + hashlib.sha256(ast.get_source_segment(source, method).encode("utf-8")).hexdigest()


def test_closed_proposal_schema_and_nonactive_governance_identity():
    value = _read()
    _schema(value, SCHEMA)
    assert (value["schema_version"], value["policy_id"], value["policy_version_candidate"]) == (
        "earnings-blackout-policy-proposal/v1", "execution-gate-policy-v2-proposed", "v2-proposal.1",
    )
    assert (value["parent_policy_version"], value["parent_version"]) == ("six-gates-production-v1", "v1")
    assert value["baseline_commit"] == "faa4394b3f4b77a538133a5de4f75f7d135d9e1e"
    assert (value["status"], value["activation_status"]) == ("PROPOSED", "NOT_ACTIVE")
    assert value["policy_lifecycle"] == ["PROPOSED", "GOVERNANCE_APPROVED", "SHADOW", "ACTIVE", "RETIRED"]


@pytest.mark.parametrize("mutation", ["extra_key", "missing_key", "wrong_type", "numeric_horizon", "duplicate_gate"])
def test_schema_rejects_unapproved_or_malformed_surface(mutation):
    value = _read()
    if mutation == "extra_key": value["runtime_loader"] = "unapproved"
    elif mutation == "missing_key": del value["known_at_basis"]["visibility"]
    elif mutation == "wrong_type": value["gate6_v1"]["blackout_sessions"] = True
    elif mutation == "numeric_horizon": value["horizon_policy"]["value"] = 5
    else: value["gate_ids"].append(value["gate_ids"][0])
    with pytest.raises(AssertionError):
        _schema(value, SCHEMA)


def test_duplicate_json_keys_are_rejected_not_last_value_wins():
    with pytest.raises(ValueError, match="DUPLICATE_PROPOSAL_KEY"):
        json.loads('{"status":"PROPOSED","status":"ACTIVE"}', object_pairs_hook=_unique_object)


def test_exact_six_gates_and_gate_one_through_five_definition_and_method_pins():
    value = _read()
    assert value["gate_ids"] == GATE_IDS
    assert value["gate_registry_version"] == EXECUTION_GATE_REGISTRY_VERSION
    assert [gate.gate_id for gate in EXECUTION_GATES] == list(range(1, 7))
    assert len(value["unchanged_gates"]) == 5
    for index, item in enumerate(value["unchanged_gates"]):
        assert (item["gate_id"], item["registry_id"], item["method"]) == (GATE_IDS[index], index + 1, METHODS[index])
        assert item["definition_reference"] == "app/registry/canonical.py#EXECUTION_GATES"
        assert item["definition_fingerprint"] == content_fingerprint(EXECUTION_GATES[index])
        assert item["implementation_fingerprint"] == _method_fingerprint(METHODS[index])


@pytest.mark.parametrize("path", SOURCE_PATHS)
def test_v1_runtime_policy_authority_and_registry_source_remain_unchanged(path):
    normalized = (ROOT / path).read_bytes().replace(b"\r\n", b"\n")
    assert _read()["source_fingerprints_lf"][path] == "sha256:" + hashlib.sha256(normalized).hexdigest()


def test_v1_gate_six_exact_definition_and_five_session_rule_are_retained():
    old = _read()["gate6_v1"]
    assert canonical_json(old["definition"]) == canonical_json(asdict(EXECUTION_GATES[5]))
    assert old["definition_fingerprint"] == content_fingerprint(EXECUTION_GATES[5])
    assert old["implementation_fingerprint"] == _method_fingerprint("_blackout")
    assert old["blackout_sessions"] == 5
    assert old["outside_or_past_scalar_result"] == "PASS"
    assert old["absence_is_pass"] is old["mutated"] is False


def test_proposed_hard_block_requires_all_evidence_without_a_window_number():
    value = _read()
    assert value["required_schedule_evidence"] == [
        "EXACT_CANONICAL_INSTRUMENT", "QUALIFYING_OFFICIAL_FINANCIAL_RESULTS_PURPOSE",
        "TRUSTED_OFFICIAL_PAYLOAD_LINEAGE", "VERIFIED_HSI_FIRST_OBSERVED_RECEIPT",
        "VERSIONED_EVENT_AND_REVISION_LINEAGE", "CONFLICT_FREE_EFFECTIVE_LIFECYCLE",
        "VISIBLE_NON_CANCELLED_NON_SUPERSEDED_NON_COMPLETED_EVENT",
        "APPROVED_RELEVANT_COVERAGE_AND_FRESHNESS", "APPROVED_EFFECTIVE_HORIZON_AND_MEMBERSHIP",
    ]
    assert value["horizon_policy"] == {
        "states": ["APPROVED_VALUE", "POLICY_UNSET", "CALIBRATION_REQUIRED"], "state": "POLICY_UNSET",
        "value": None, "unit": None, "precision_and_boundaries": None,
        "calibration_required": True, "inherits_v1_five": False, "b14": "OPEN",
        "b09": "SEPARATE_RULE_HORIZON_POLICY",
    }
    assert value["hard_block_semantics"] == {
        "requires_all_schedule_evidence": True,
        "causal_condition": "known_at <= evaluation_as_of AND APPROVED_WINDOW_MEMBERSHIP",
        "window_formula": None, "window_operational": False,
        "policy_and_source_effective_at_or_before_as_of": True,
        "cancelled_event_provides_positive_block": False, "superseded_event_provides_positive_block": False,
        "revisions_effect": "OWN_KNOWN_AT_ONWARD_ONLY",
        "cancellation_effect": "REMOVE_LINKED_BLOCK_ONLY_NOT_GLOBAL_CLEARANCE",
        "earlier_legitimate_entry_invalidated": False,
    }


def test_declarative_unknown_blocked_table_never_claims_clear_or_evaluates_v2():
    value = _read()
    cases = value["decision_cases"]
    assert cases[0] == {
        "case": "ALL_PREDICATES_AND_APPROVED_WINDOW", "state": "BLOCKED",
        "gate_outcome": "FAIL", "reason": "VERIFIED_EVENT_IN_APPROVED_WINDOW",
    }
    expected = {
        "HORIZON_UNSET": "EVENT_RISK_HORIZON_POLICY_UNSET",
        "BEFORE_FIRST_OBSERVATION": "EVIDENCE_NOT_YET_KNOWN", "MISSING_SCHEDULE": "SCHEDULE_UNVERIFIED",
        "INCOMPLETE_COVERAGE": "SOURCE_COVERAGE_INCOMPLETE", "STALE_COVERAGE": "SOURCE_COVERAGE_STALE",
        "FAILED_SOURCE": "SOURCE_FAILED", "CONFLICTED_SCHEDULE": "SCHEDULE_CONFLICTED",
        "UNKNOWN_KNOWN_AT": "KNOWN_AT_UNAVAILABLE", "AMBIGUOUS_PURPOSE": "EVENT_PURPOSE_AMBIGUOUS",
        "UNSUPPORTED_PRECISION": "EVENT_PRECISION_UNSUPPORTED", "OUTSIDE_WINDOW": "CLEAR_UNSUPPORTED",
        "COMPLETED_OR_PAST_EVENT": "CLEAR_UNSUPPORTED", "LAST_POSITIVE_EVENT_CANCELLED_OR_SUPERSEDED": "CLEAR_UNSUPPORTED",
    }
    assert {row["case"]: row["reason"] for row in cases[1:]} == expected
    for row in cases[1:]:
        assert (row["state"], row["gate_outcome"]) == ("UNKNOWN", "INSUFFICIENT_DATA")
        assert row["reason"] in value["unknown_reasons"]
    proposed = value["gate6_proposed"]
    assert proposed["gate_id"] == GATE_IDS[-1]
    assert proposed["clear_support_state"] == "CLEAR_UNSUPPORTED"
    assert proposed["result_mapping"] == {"BLOCKED": "FAIL", "UNKNOWN": "INSUFFICIENT_DATA"}
    assert proposed["unknown_is_bad_stock"] is proposed["unknown_allows_entry_ready"] is False


def test_inclusive_known_at_revision_and_late_notice_requirements_are_explicit():
    value = _read()
    assert value["known_at_basis"] == {
        "perspective": "HSI_LOCAL", "contract": "app/filings/earnings_schedule_known_at.py",
        "state_required": "PROSPECTIVE_FIRST_OBSERVED_PIT", "basis": "VERIFIED_SYSTEM_FIRST_OBSERVED_RECEIPT",
        "source_public_time_retained_separately": True, "visibility": "known_at <= evaluation_as_of",
        "lifecycle_selection": "RESOLVE_LOCAL_VISIBILITY_PER_REVISION_BEFORE_EFFECTIVE_LIFECYCLE",
        "caller_retrieved_at_sufficient": False, "date_only_to_datetime_invention": False, "retroactive_block": False,
    }
    assert value["replay"] == {
        "v1_records_immutable": True, "explicit_policy_id_version_fingerprint": True,
        "as_of_source_and_regulatory_versions_required": True, "local_observation_and_revision_lineage_required": True,
        "current_data_backfill": False, "implicit_latest_policy": False,
    }


def test_management_scope_is_not_clearance_and_unknown_does_not_stop_research():
    value = _read()
    gate = value["gate6_proposed"]
    assert gate["entry_contexts"] == ["FRESH_ENTRY", "ADD_TO_POSITION", "ROTATE_IN"]
    assert gate["management_exemptions"] == ["HOLD_EXISTING", "REDUCE_EXISTING", "EXIT_EXISTING", "RISK_MANAGEMENT"]
    assert gate["management_gate_outcome"] == "PASS"
    assert gate["management_exemption_is_clearance"] is False
    assert value["pilot"] == {
        "research_continues_when_unknown": True, "unknown_bypass_allowed": False,
        "horizon_unset_blocks_activation": True, "complete_historical_calendar_required_for_prospective_research": False,
        "entry_ready_usability_requires_policy_review": True,
    }


def test_soft_context_is_optional_non_gate_and_non_numerical():
    assert _read()["soft_context"] == {
        "name": "RESULTS_SEASON_RISK_CONTEXT", "status": "NOT_ACTIVE",
        "channel": "EXISTING_SHARED_BRAIN_RESEARCH_EXPLANATION",
        "source": "EFFECTIVE_DATED_BROAD_REPORTING_WINDOWS_NOT_COMPANY_SCHEDULE",
        "uses": ["RESEARCH", "UI_EXPLANATION", "QUALITATIVE_CONFIDENCE_CONTEXT"],
        "forbidden": ["GATE_PASS", "GATE_FAIL", "SCORE_POINTS", "NUMERIC_CONFIDENCE_PENALTY", "POSITION_SIZE", "ENTRY_EXIT", "TARGET_STOP", "TRADE_INSTRUCTION", "PREDICTED_EARNINGS_DATE"],
    }


def test_exact_downstream_impact_inventory_and_activation_blockers():
    value = _read()
    assert [(row["consumer"], row["classification"]) for row in value["downstream_impact"]] == [
        ("Decision Score", "NO_CHANGE"), ("Brain", "ADAPTER_UPDATE_REQUIRED"),
        ("Portfolio", "POLICY_REVIEW_REQUIRED"), ("Signals", "ADAPTER_UPDATE_REQUIRED"),
        ("TradePlan", "NO_CHANGE"), ("Entry-ready lifecycle", "POLICY_REVIEW_REQUIRED"),
        ("Alerts", "POLICY_REVIEW_REQUIRED"), ("Outcome ledger", "CALIBRATION_REQUIRED"),
        ("Backtest", "ADAPTER_UPDATE_REQUIRED"), ("Six-Gates orchestration", "ADAPTER_UPDATE_REQUIRED"),
    ]
    for item in value["downstream_impact"]:
        assert (ROOT / item["reference"]).is_file()
    assert [item["id"] for item in value["activation_blockers"]] == [f"A{i}" for i in range(1, 12)]
    assert [item["classification"] for item in value["activation_blockers"]] == [
        "BLOCKING", "BLOCKING", "BLOCKING", "BLOCKING", "BLOCKING", "NON_BLOCKING",
        "BLOCKING", "BLOCKING", "DEFERRED_FOR_SHADOW", "DEFERRED_FOR_SHADOW", "NON_BLOCKING",
    ]
    assert value["calibration_requirements"] == [
        "KNOWN_AT_TO_EVENT_DISTANCE", "OVERNIGHT_OPEN_GAP", "ABSOLUTE_GAP", "ATR_NORMALIZED_GAP",
        "MFE", "MAE", "DRAWDOWN", "SLIPPAGE", "POST_EVENT_VOLATILITY", "MISSED_OPPORTUNITY_FROM_BLOCKING",
        "FALSE_BLOCK_RATE", "SCHEDULE_REVISION_RATE", "SCHEDULE_KNOWN_LATE_RATE",
    ]


def test_reuse_contract_has_no_duplicate_engine_or_registry_activation():
    value = _read()
    assert value["reuse"] == {
        "schedule_identity": "app/filings/earnings_schedule_identity.py",
        "known_at": "app/filings/earnings_schedule_known_at.py",
        "coverage": "app/filings/earnings_schedule_coverage.py",
        "trading_calendar": "app/gates/engine.py#ExchangeCalendar",
        "gate_result": "app/gates/engine.py#GateOutcome",
        "event_evidence": "app/gates/official_earnings_schedule_candidate.py",
    }
    for reference in value["reuse"].values():
        path, _, symbol = reference.partition("#")
        assert (ROOT / path).is_file()
        if symbol:
            assert f"class {symbol}" in (ROOT / path).read_text(encoding="utf-8")
    assert value["boundaries"] == {
        "v1_active": True, "gate_policy_v2_active": False, "v2_diagnostic_active": False,
        "v2_shadow_only": True, "b08": "CLOSED_FOR_ACTIVATION_COMPATIBILITY",
        "current_identity_contract": "READY", "prospective_first_observed_contract": "READY",
        "registered": False, "runtime_wired": False, "new_gate_engine": False, "new_calendar": False,
        "new_diagnostic": False, "ai_decision_authority": False, "no_unverified_calendar_clearance": True,
        "no_retroactive_blackout": True, "no_ai_predicted_earnings_date": True, "pilot_simplicity_rule": "ACTIVE",
    }
    # Runtime sources must not discover/import this documentation-only candidate.
    for source in (ROOT / "app").rglob("*.py"):
        text = source.read_text(encoding="utf-8")
        assert "execution-gate-policy-v2-proposed" not in text
        assert "EARNINGS_BLACKOUT_POLICY_V2_PROPOSAL" not in text
    assert value["next_continuation"] == "EARNINGS_BLACKOUT_POLICY_V2_GOVERNANCE_APPROVAL"
    assert value["next_continuation_started"] is False


def test_proposal_fingerprint_roundtrip_order_independence_and_tamper_detection():
    value = _read()
    supplied = value.pop("proposal_fingerprint")
    assert re.fullmatch(r"sha256:[0-9a-f]{64}", supplied)
    assert content_fingerprint(value) == supplied
    assert content_fingerprint(json.loads(canonical_json(value))) == supplied
    assert content_fingerprint(dict(reversed(list(value.items())))) == supplied
    # Every field, including safety/provenance/array order, remains in the digest.
    for key in value:
        changed = deepcopy(value)
        del changed[key]
        assert content_fingerprint(changed) != supplied
    changed = deepcopy(value)
    changed["gate_ids"].reverse()
    assert content_fingerprint(changed) != supplied
    changed = deepcopy(value)
    changed["gate6_proposed"]["result_mapping"]["UNKNOWN"] = "PASS"
    assert content_fingerprint(changed) != supplied
