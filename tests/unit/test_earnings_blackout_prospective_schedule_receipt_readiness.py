"""Static proofs for the non-active prospective earnings receipt readiness audit."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest

from app.fundamentals.diagnostic_comparability import canonical_json, content_fingerprint


ROOT = Path(__file__).resolve().parents[2]
ARTIFACT = ROOT / "docs/architecture/EARNINGS_BLACKOUT_PROSPECTIVE_SCHEDULE_RECEIPT_READINESS_V1.json"

TOP_KEYS = set("""
schema_version audit_id audit_version baseline_commit authority status scope
runtime_collector_active gate_policy_v2_active numeric_horizon_selected source_probe
bounded_population source_families first_observed minimum_chain later_requirements reuse
persistence_decision idempotency dual_exchange failure_mapping readiness_matrix
prospective_start_criteria canary boundaries next_continuation next_continuation_started
fingerprint_scheme audit_fingerprint
""".split())


def _unique(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError(f"DUPLICATE_JSON_KEY:{key}")
        value[key] = item
    return value


def _read():
    return json.loads(ARTIFACT.read_text(encoding="utf-8"), object_pairs_hook=_unique)


def _unsigned(value):
    return {key: item for key, item in value.items() if key != "audit_fingerprint"}


def _validate(value):
    assert set(value) == TOP_KEYS
    assert value["audit_fingerprint"] == content_fingerprint(_unsigned(value))
    assert value["schema_version"] == "earnings-blackout-prospective-schedule-receipt-readiness/v1"
    assert value["audit_id"] == "earnings-blackout-prospective-schedule-receipt-readiness"
    assert value["audit_version"] == "v1"
    assert value["baseline_commit"] == "75f88ff0d260fa3fb8f7c38192f4b7fe06a9cbc6"
    assert value["status"] == "PROSPECTIVE_RECEIPT_PATH_PARTIAL_ONE_BOUNDED_REPAIR_REQUIRED"
    assert value["scope"] == "DOCUMENTATION_ONLY_READINESS_AUDIT"
    assert value["runtime_collector_active"] is False
    assert value["gate_policy_v2_active"] is False
    assert value["numeric_horizon_selected"] is False
    assert value["authority"] == {
        "basis": "USER_DELEGATED_BOUNDED_PROSPECTIVE_SOURCE_READINESS_AUDIT",
        "directive_id": "a0c1de10-1c3a-4eb3-9063-19338f3e0108",
        "human_signature_claimed": False,
    }
    _probe_and_population(value)
    _minimum_boundary(value)
    _readiness_and_safety(value)


def _probe_and_population(value):
    probe = value["source_probe"]
    assert probe["mode"] == "ONE_BOUNDED_READ_ONLY_REQUEST_PER_OFFICIAL_SOURCE_FAMILY"
    assert probe["persisted_as_first_observed"] is False
    assert probe["sandbox_transport"] == "NETWORK_OR_TLS_UNAVAILABLE"
    assert probe["no_notice_conclusion_allowed"] is False
    assert probe["no_event_conclusion_allowed"] is False
    assert probe["host_transport"] == [
        {"source_family": "NSE_BOARD_MEETINGS", "http_status": 200, "state": "SOURCE_PARTIAL", "reason": "ROLLING_FEED_NOT_COMPLETE", "rows": 0, "qualifying_rows": 0},
        {"source_family": "BSE_ANNOUNCEMENTS", "http_status": 200, "state": "SOURCE_PARTIAL", "reason": "RECENT_LIST_WINDOW_COVERAGE_UNPROVEN", "rows": 10, "qualifying_rows": 0},
    ]
    population = value["bounded_population"]
    assert population["canonical_companies"] == population["current_nse_identity_resolved"] == population["current_bse_identity_resolved"] == 31
    assert population["historical_identity_reconstruction_started"] is False
    assert population["universe_expansion_started"] is False
    assert [row["id"] for row in value["source_families"]] == ["NSE_BOARD_MEETINGS", "BSE_ANNOUNCEMENTS"]
    assert all(row["positive_discovery"] == "PARTIAL" for row in value["source_families"])
    assert all(row["negative_absence"] == "NOT_READY" for row in value["source_families"])


def _minimum_boundary(value):
    first = value["first_observed"]
    assert first["required_origin"] == "AUTOMATIC_INGESTION_BOUNDARY"
    assert first["existing_capture"] == "NOT_READY_CALLER_SUPPLIED_SOURCE_BATCH_RETRIEVED_AT"
    assert first["backdating_allowed"] is False
    assert first["source_public_time_substitution_allowed"] is False
    assert first["event_date_substitution_allowed"] is False
    assert first["restart_rule"] == "UNCHANGED_LOGICAL_RECEIPT_PRESERVES_ORIGINAL_FIRST_OBSERVED_AT"
    assert value["minimum_chain"] == [
        "ADMITTED_OFFICIAL_POSITIVE_DISCOVERY_PATH", "EXACT_CURRENT_CANONICAL_IDENTITY",
        "EXPLICIT_QUALIFYING_FINANCIAL_RESULTS_PURPOSE", "AUTOMATIC_AWARE_UTC_HSI_FIRST_OBSERVED_AT",
        "IMMUTABLE_SOURCE_ROW_AND_PAYLOAD_FINGERPRINT", "IDEMPOTENT_LOGICAL_RECEIPT_KEY",
        "REVISION_CONFLICT_SAFE_LINEAGE", "PARTIAL_OR_FAILED_COVERAGE_RECEIPT",
    ]
    persistence = value["persistence_decision"]
    assert persistence["state"] == "ONE_NEW_TYPED_FAMILY_IN_EXISTING_IMMUTABLE_SNAPSHOT_STORE_REQUIRED"
    assert persistence["new_sqlite_table"] is False
    assert persistence["parallel_calendar_database"] is False
    assert persistence["family"] == "EARNINGS_SCHEDULE_PROSPECTIVE_RECEIPT"
    assert persistence["coverage_model"] == "REUSE_EarningsScheduleCoverageReceipt_NO_DUPLICATE_COVERAGE_MODEL"
    idempotency = value["idempotency"]
    assert idempotency["logical_receipt_key"] == ["source_family", "source_filing_identity", "source_payload_fingerprint"]
    assert idempotency["unchanged_replay"] == "IDENTICAL_REPLAY_PRESERVE_ORIGINAL_FIRST_OBSERVED_AT"
    assert idempotency["deduplicate_distinct_revisions"] is False
    assert idempotency["overwrite_allowed"] is False
    dual = value["dual_exchange"]
    assert dual["independent_source_receipts"] is True
    assert dual["one_source_may_begin_positive_receipt"] is True
    assert dual["both_sources_required_before_recording"] is False
    assert dual["one_source_proves_other_absent"] is False


def _readiness_and_safety(value):
    states = {row["input"]: row["state"] for row in value["readiness_matrix"]}
    assert states["AUTOMATIC_FIRST_OBSERVED_CAPTURE"] == "NOT_READY"
    assert states["NEGATIVE_ABSENCE_PROOF"] == "NOT_READY"
    assert states["PRICE_OUTCOMES"] == "READY"
    assert states["LAYER_2_HSI_OPPORTUNITY_LINEAGE"] == "PARTIAL"
    assert states["SLIPPAGE"] == states["MFE_MAE"] == "OPTIONAL_ENRICHMENT"
    start = value["prospective_start_criteria"]
    assert start["currently_satisfied"] is False
    assert start["single_missing_boundary"] == "EARNINGS_BLACKOUT_PROSPECTIVE_RECEIPT_COLLECTOR_V1"
    assert value["next_continuation"] == "EARNINGS_BLACKOUT_PROSPECTIVE_RECEIPT_COLLECTOR_V1"
    assert value["next_continuation_started"] is False
    assert value["canary"]["status"] == "NOT_IMPLEMENTED"
    assert "GATE_6_CHANGE" in value["canary"]["forbidden"]
    assert "BROKER_ORDER" in value["canary"]["forbidden"]
    assert value["boundaries"] == {
        "V1_ACTIVE": True, "GATE_POLICY_V2_ACTIVE": False, "SIX_GATES_EXACTLY_SIX": True,
        "NO_UNVERIFIED_CALENDAR_CLEARANCE": True, "NO_RETROACTIVE_BLACKOUT": True,
        "NO_FUTURE_LEAKAGE": True, "NO_HORIZON_GUESS": True,
        "PROSPECTIVE_FIRST_OBSERVED_ONLY": True, "PILOT_SIMPLICITY_RULE": "ACTIVE",
        "AI_DECISION_AUTHORITY": False,
    }
    for path in value["reuse"].values():
        if path.startswith("app/"):
            assert (ROOT / path).is_file()


def test_readiness_contract_schema_and_boundaries_are_exact():
    _validate(_read())


def test_deterministic_replay_and_fingerprint_cover_all_top_level_fields():
    value = _read()
    replay = json.loads(canonical_json(value), object_pairs_hook=_unique)
    _validate(replay)
    assert replay == value
    body = _unsigned(value)
    assert content_fingerprint(dict(reversed(list(body.items())))) == value["audit_fingerprint"]
    for key in body:
        altered = deepcopy(body)
        del altered[key]
        assert content_fingerprint(altered) != value["audit_fingerprint"]


@pytest.mark.parametrize(("path", "replacement"), [
    (("runtime_collector_active",), True),
    (("gate_policy_v2_active",), True),
    (("numeric_horizon_selected",), True),
    (("source_probe", "no_notice_conclusion_allowed"), True),
    (("first_observed", "backdating_allowed"), True),
    (("persistence_decision", "new_sqlite_table"), True),
    (("idempotency", "overwrite_allowed"), True),
    (("dual_exchange", "one_source_proves_other_absent"), True),
    (("prospective_start_criteria", "currently_satisfied"), True),
    (("next_continuation_started",), True),
    (("boundaries", "NO_UNVERIFIED_CALENDAR_CLEARANCE"), False),
])
def test_rehashed_unsafe_change_is_rejected(path, replacement):
    value = deepcopy(_read())
    destination = value
    for item in path[:-1]:
        destination = destination[item]
    destination[path[-1]] = replacement
    value["audit_fingerprint"] = content_fingerprint(_unsigned(value))
    with pytest.raises(AssertionError):
        _validate(value)


def test_duplicate_json_keys_and_unapproved_surface_are_rejected():
    with pytest.raises(ValueError, match="DUPLICATE_JSON_KEY"):
        json.loads('{"status":"A","status":"ACTIVE"}', object_pairs_hook=_unique)
    value = _read()
    value["calendar_clearance"] = True
    value["audit_fingerprint"] = content_fingerprint(_unsigned(value))
    with pytest.raises(AssertionError):
        _validate(value)


def test_document_and_runtime_static_boundary_remain_non_active():
    document = ROOT / "docs/architecture/EARNINGS_BLACKOUT_PROSPECTIVE_SCHEDULE_RECEIPT_READINESS_V1.md"
    assert document.is_file()
    assert "EARNINGS_BLACKOUT_PROSPECTIVE_SCHEDULE_RECEIPT_READINESS_V1" in (ROOT / "README.md").read_text(encoding="utf-8")
    for source in (ROOT / "app").rglob("*.py"):
        assert "EARNINGS_BLACKOUT_PROSPECTIVE_SCHEDULE_RECEIPT_READINESS_V1" not in source.read_text(encoding="utf-8")
