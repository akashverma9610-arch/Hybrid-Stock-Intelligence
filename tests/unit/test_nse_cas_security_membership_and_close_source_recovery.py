"""Offline CAS source-recovery conformance, not a membership/price producer.

Reuse predecessor necessary-evidence witnesses without adding a classifier.
No network, provider, production database, portfolio or authority operations.
"""
from datetime import timedelta
from hashlib import sha256
import json
from pathlib import Path
import subprocess
from urllib.parse import urlsplit

import pytest

from app.fundamentals.diagnostic_comparability import canonical_json, content_fingerprint
from tests.unit import test_gate1_rotation_research_session_price_source_applicability_audit as previous

ROOT = Path(__file__).resolve().parents[2]
BASELINE = "28fb8451208853c2705ca9b516f74e855441c581"
STEM = "NSE_CAS_SECURITY_MEMBERSHIP_AND_CLOSE_SOURCE_RECOVERY_V1"
PATH = ROOT / "docs/architecture" / (STEM + ".json")
FP = "sha256:b2fd0ba83dda8898065a43181837c675b2f46c6b27e3eb7404b68efa472b5d26"
NEXT = "NSE_CAS_PRIMARY_SOURCE_ACCESS_AND_DATED_MEMBERSHIP_EVIDENCE_RECOVERY_V1"
RECOVERY = ["BODY_UNAVAILABLE"] * 3 + ["PRIMARY_TEXT_READ"] * 3 + [
    "LANDING_ONLY", "PRIMARY_TEXT_READ", "BODY_UNAVAILABLE", "LANDING_ONLY",
    "LANDING_ONLY", "PRIMARY_TEXT_READ",
]
MATRIX = {
    "CMTR73845": "SOURCE_NOT_READY", "CMTR74466": "SOURCE_NOT_READY",
    "CMTR67774_SECTION_3_4": "SOURCE_NOT_READY", "CAS_SECURITY_MEMBERSHIP": "SOURCE_NOT_READY",
    "GLOBAL_LIVE_CHRONOLOGY": "SOURCE_FACT_REVERIFIED", "MEMBERSHIP_REVISIONS": "SOURCE_NOT_READY",
    "IDENTITY_JOIN": "IDENTITY_JOIN_SOURCE_GAP", "CAS_CLOSE_RULE_TEXT": "SOURCE_FACT_REVERIFIED",
    "NON_CAS_CLOSE_RULE_TEXT": "SOURCE_NOT_READY", "CURRENT_CAS_PRICE_FIELDS": "SOURCE_NOT_READY",
    "LEGACY_CLOSE_FIELD_DICTIONARY": "LEGACY_SCHEMA_ONLY", "DAILY_CLOSE": "PRICE_SOURCE_POLICY_REQUIRED",
    "INTRADAY_CAS": "SOURCE_NOT_READY", "PROSPECTIVE": "PROSPECTIVE_CAS_SOURCE_BLOCKED",
    "HISTORICAL": "HISTORICAL_CAS_SOURCE_GAP", "SPECIAL_SESSION_CAS": "SOURCE_NOT_READY",
    "SOURCE_PRECEDENCE": "SOURCE_PRECEDENCE_POLICY_REQUIRED", "PIT": "HISTORICAL_KNOWN_AT_COVERAGE_UNPROVEN",
}


def _read():
    return json.loads(PATH.read_text(encoding="utf-8"))


def _digest(value, field="artifact_fingerprint"):
    return content_fingerprint({k: v for k, v in value.items() if k != field})


def _need(condition, code):
    if not condition:
        raise ValueError(code)


def _verify(a):
    p = previous._read()
    _need((a["baseline_commit"], a["slice"], a["audit_id"], a["version"]) == (
        BASELINE, STEM, "nse-cas-security-membership-and-close-source-recovery", "v1"
    ), "AUDIT_IDENTITY")
    _need((a["decision"], a["semantic_decision"], a["slice_status"]) == (
        "C", "CAS_MEMBERSHIP_SOURCE_STILL_BLOCKED", "ACCEPTED/CLOSED"
    ), "SOURCE_READINESS_OVERCLAIM")
    _need(a["status"] == "SOURCE_RECOVERY_AUDIT / NO_PARAMETER_APPROVAL / NOT_ACTIVE"
          and a["bootstrap_seed"] == "UNSET", "AUTHORITY_CHANGED")
    for field in ("authority", "bootstrap_policy_status", "preservation", "registration", "effective_parameters"):
        _need(a[field] == p[field], "AUTHORITY_CHANGED")
    _need(all(v is None for v in a["effective_parameters"].values()), "PARAMETER_INVENTED")
    _need(not any(a["runtime"].values()), "RUNTIME_SCOPE")
    _need(not any(a["safety"].values()), "SAFETY_BOUNDARY")
    _need(a["source_readiness"] == MATRIX, "READINESS_MATRIX")
    _need([r["requirement"] for r in a["scope_coverage"]] == [f"{n:02d}" for n in range(1, 29)]
          and all(r["state"] and r["location"] for r in a["scope_coverage"]), "SCOPE_INCOMPLETE")
    _need(a["membership_records"] == [] and a["membership"]["recovered_record_count"] == 0,
          "MEMBERSHIP_FABRICATED")
    m = a["membership"]
    _need(m["state"] == "SOURCE_NOT_READY" and all(m[k] is None for k in (
        "initial_universe", "source_field_name", "source_field_codes", "revision_mechanism", "unknown_default"
    )) and not any(m[k] for k in (
        "criterion_alone_proves_membership", "current_backcast", "partial_absence_means_non_cas",
        "complete_absence_without_complement_policy_means_non_cas", "symbol_only_join",
        "global_launch_implies_membership", "classifier_implemented"
    )), "MEMBERSHIP_SHORTCUT")
    c = a["chronology"]
    _need((c["global_live_date"], c["mock_date"], c["dated_master_label"],
           c["notice_master_availability_by"]) == (
        "2026-08-03", "2026-08-01", "2026-07-31", "2026-08-01T06:00:00+05:30"
    ) and len(c["required_fields"]) == 22 and not any(c[k] for k in (
        "master_availability_is_actual_capture", "master_label_is_effective_date",
        "effective_to_unknown_is_indefinite", "later_revision_rewrites_D", "current_page_backcast",
        "publication_equals_retrieval"
    )), "CHRONOLOGY_SHORTCUT")
    _need(a["identity"]["readiness"] == "IDENTITY_JOIN_SOURCE_GAP"
          and a["identity"]["generic_join"] == "IDENTITY_JOIN_DERIVABLE"
          and a["identity"]["fields_verified_for_CAS"] == [], "IDENTITY_OVERCLAIM")
    _need([s["id"] for s in a["sources"]] == [f"S{n:02d}" for n in range(1, 13)]
          and [s["recovery_state"] for s in a["sources"]] == RECOVERY, "UNREAD_BODY_PROMOTED")
    for s in a["sources"]:
        url = urlsplit(s["url"])
        _need(url.scheme == "https" and url.hostname in {
            "nsearchives.nseindia.com", "www.nseindia.com", "www.sebi.gov.in"
        } and not url.username and not url.password, "SOURCE_URL")
        _need(s["recovered"] == (s["recovery_state"] == "PRIMARY_TEXT_READ")
              and s["raw_response_fingerprint"] is None and s["native_HSI_known_at"] is None
              and not any(s[k] for k in ("raw_bytes_retained", "visual_verification", "research_authority"))
              and all(s[k] for k in ("document_id", "publication_basis", "source_type", "locator",
                                     "membership_semantics", "timing_semantics", "close_semantics",
                                     "known_at_capability", "historical_coverage", "prospective_availability",
                                     "HSI_join_readiness", "blocker")), "SOURCE_PROVENANCE")
        _need(s["published_at"] is None and s["effective_to"] is None and s["revised_at"] is None
              and s["superseded_by"] is None, "SOURCE_CHRONOLOGY_INVENTED")
        _need(_digest(s, "evidence_fingerprint") == s["evidence_fingerprint"], "EVIDENCE_TAMPERED")
    _need(a["sources"][10]["effective_rule"] is False
          and a["sources"][11]["blocker"] == "LEGACY_SCHEMA_NOT_CAS_COMPATIBILITY_PROOF", "LEGACY_OR_DRAFT_PROMOTED")
    close = a["close_semantics"]
    _need(close["research_price_selected"] is None and not close["executable_fill"]
          and close["cas"]["published_close_may_exist_without_new_trade"]
          and not any(close["cas"][k] for k in (
              "no_equilibrium_implies_no_trade_all_day", "no_match_is_executed_trade",
              "absence_of_feed_proves_no_match", "HSI_reference_carry_forward_allowed"
          )) and close["non_cas"]["calculation"] is None and close["non_cas"]["no_trade_rule"] is None
          and not close["non_cas"]["equity_derivative_or_index_formula_substituted"], "CLOSE_SEMANTICS")
    _need(len(a["price_fields"]) == 10 and not any(r["research_selected"] for r in a["price_fields"])
          and all(r["exact_field"] is None for r in a["price_fields"][4:]), "PRICE_FIELD_INVENTED")
    _need(a["daily_close_state"] == "PRICE_SOURCE_POLICY_REQUIRED"
          and len(a["provider_reconciliation"]) == 4
          and not any(r["CAS_discriminator"] for r in a["provider_reconciliation"]), "PROVIDER_OVERCLAIM")
    intra = a["intraday"]
    _need(intra["classification"] == "REGULAR_ONLY_NOT_CAS_VERIFIED"
          and intra["state"] == "SOURCE_NOT_READY" and intra["exact_last_bar_for_security"] is None
          and not any(intra[k] for k in ("membership_consulted", "auction_reference_synthesized",
                                        "final_bar_equals_auction_close", "missing_equals_no_trade")), "INTRADAY_OVERCLAIM")
    phases = a["phases"]
    _need(phases["final_publication_timestamp"] is None and not phases["random_close_is_fixed_end"]
          and not phases["mock_matures_research"] and not phases["DR_implies_mock"]
          and len(phases["session_cases"]) == 5, "SPECIAL_OR_MOCK_PROMOTED")
    _need(a["prospective"]["status"] == "PROSPECTIVE_CAS_SOURCE_BLOCKED"
          and not a["prospective"]["ready_now"] and not a["prospective"]["retrospective_history_required_for_new_D"]
          and a["historical"]["status"] == "HISTORICAL_CAS_SOURCE_GAP"
          and a["historical"]["recovered_membership_snapshots"] == 0
          and not a["historical"]["retention_verified"] and a["historical"]["actual_HSI_known_at"] is None,
          "COVERAGE_OVERCLAIM")
    pr = a["precedence"]
    _need(pr["state"] == "SOURCE_PRECEDENCE_POLICY_REQUIRED" and pr["selected_price_source"] is None
          and not any(pr[k] for k in ("automatic_preference", "automatic_average", "research_price_authority")),
          "PRICE_AUTHORITY")
    _need(len(a["conflicts"]) == 4 and all(not r["observed"] and r["response"] for r in a["conflicts"]),
          "CONFLICT_EVIDENCE_INVENTED")
    impacts = a["parameter_impact"]
    _need(len(impacts) == 7 and all(not r["approved"] for r in impacts)
          and {r["parameter"]: r["impact"] for r in impacts} == {
              "DURATION_UNIT": "UNCHANGED", "SESSION_COUNTING": "UNCHANGED", "START_PRICE": "UNCHANGED",
              "TERMINAL_BOUNDARY": "UNCHANGED", "TERMINAL_PRICE": "BLOCKER_NARROWED",
              "PROSPECTIVE_CALENDAR_AUTHORITY": "UNCHANGED", "INSTRUMENT_ELIGIBILITY": "UNCHANGED"
          } and a["blockers_closed"] == [], "PARAMETER_APPROVED")
    _need(a["next_continuations"] == [NEXT] and not a["next_continuation_started"], "NEXT_SCOPE")
    _need(_digest(a) == a["artifact_fingerprint"] == FP, "AUDIT_TAMPERED")


def test_artifact_and_serialization_are_exact_and_tamper_evident():
    a = _read()
    _verify(a)
    _verify(json.loads(canonical_json(a)))
    assert _digest(dict(reversed(list(a.items())))) == FP
    assert FP in (PATH.with_suffix(".md")).read_text(encoding="utf-8")


@pytest.mark.parametrize("ref", [_read()["parent"], *_read()["predecessors"]], ids=lambda r: r["path"])
def test_all_twelve_native_predecessors_unchanged(ref):
    path = ROOT / ref["path"]
    p = json.loads(path.read_text(encoding="utf-8"))
    assert _digest(p, ref["field"]) == p[ref["field"]] == ref["fingerprint"]
    original = subprocess.check_output(["git", "show", BASELINE + ":" + ref["path"]], cwd=ROOT)
    assert path.read_bytes().replace(b"\r\n", b"\n") == original.replace(b"\r\n", b"\n")


@pytest.mark.parametrize("path,fp", _read()["inspected_file_fingerprints_lf"].items())
def test_baseline_source_pins(path, fp):
    raw = subprocess.check_output(["git", "show", BASELINE + ":" + path], cwd=ROOT)
    assert "sha256:" + sha256(raw.replace(b"\r\n", b"\n")).hexdigest() == fp


def test_native_V1_ACTIVE_V2_NOT_ACTIVE_and_no_runtime_consumer():
    previous.test_V1_ACTIVE_V2_NOT_ACTIVE_no_runtime_consumer()
    a = _read()
    assert a["authority"]["v1"]["status"] == "ACTIVE"
    assert a["authority"]["v2"]["status"] == "NOT_ACTIVE"
    for path in (ROOT / "app").rglob("*.py"):
        assert STEM not in path.read_text(encoding="utf-8")


@pytest.mark.parametrize("field", _read()["safety"])
def test_no_backcast_ambiguous_join_price_fallback_or_side_effect(field):
    a = _read()
    a["safety"][field] = True
    a["artifact_fingerprint"] = _digest(a)
    with pytest.raises(ValueError, match="SAFETY_BOUNDARY"):
        _verify(a)


@pytest.mark.parametrize("field", _read()["runtime"])
def test_no_runtime_DB_provider_portfolio_order_or_registration(field):
    a = _read()
    a["runtime"][field] = True
    a["artifact_fingerprint"] = _digest(a)
    with pytest.raises(ValueError, match="RUNTIME_SCOPE"):
        _verify(a)


@pytest.mark.parametrize("field", _read()["effective_parameters"])
def test_no_seed_horizon_price_or_parameter_activation(field):
    a = _read()
    a["effective_parameters"][field] = "fabricated"
    a["artifact_fingerprint"] = _digest(a)
    with pytest.raises(ValueError, match="AUTHORITY_CHANGED"):
        _verify(a)


@pytest.mark.parametrize("component", MATRIX)
def test_missing_sources_cannot_be_resealed_as_ready(component):
    a = _read()
    a["source_readiness"][component] = "READY"
    a["artifact_fingerprint"] = _digest(a)
    with pytest.raises(ValueError, match="READINESS_MATRIX"):
        _verify(a)


@pytest.mark.parametrize("i", range(12))
def test_source_summary_tamper_is_rejected_before_outer_wrapper(i):
    a = _read()
    a["sources"][i]["findings"].append("unverified claim")
    a["artifact_fingerprint"] = _digest(a)
    with pytest.raises(ValueError, match="EVIDENCE_TAMPERED"):
        _verify(a)


@pytest.mark.parametrize("section,field,value,code", [
    (None, "membership_records", [{"symbol": "SYNTHETIC"}], "MEMBERSHIP_FABRICATED"),
    ("chronology", "mock_date", "2026-08-03", "CHRONOLOGY_SHORTCUT"),
    ("chronology", "master_availability_is_actual_capture", True, "CHRONOLOGY_SHORTCUT"),
    ("chronology", "effective_to_unknown_is_indefinite", True, "CHRONOLOGY_SHORTCUT"),
    ("membership", "source_field_name", "invented_flag", "MEMBERSHIP_SHORTCUT"),
    ("membership", "current_backcast", True, "MEMBERSHIP_SHORTCUT"),
    ("membership", "criterion_alone_proves_membership", True, "MEMBERSHIP_SHORTCUT"),
    ("membership", "partial_absence_means_non_cas", True, "MEMBERSHIP_SHORTCUT"),
    ("close_semantics", "research_price_selected", "official_close", "CLOSE_SEMANTICS"),
    ("intraday", "final_bar_equals_auction_close", True, "INTRADAY_OVERCLAIM"),
    ("phases", "mock_matures_research", True, "SPECIAL_OR_MOCK_PROMOTED"),
    ("prospective", "ready_now", True, "COVERAGE_OVERCLAIM"),
    ("historical", "retention_verified", True, "COVERAGE_OVERCLAIM"),
    ("precedence", "selected_price_source", "NSE", "PRICE_AUTHORITY"),
    (None, "next_continuations", [NEXT, "ANOTHER_SLICE"], "NEXT_SCOPE"),
])
def test_governance_shortcuts_fail_closed_even_if_resealed(section, field, value, code):
    a = _read()
    (a if section is None else a[section])[field] = value
    a["artifact_fingerprint"] = _digest(a)
    with pytest.raises(ValueError, match=code):
        _verify(a)


@pytest.mark.parametrize("changes,expected", [
    ({"official_body_verified": False}, "UNKNOWN"),
    ({"exact_identity": False}, "UNKNOWN"),
    ({"scope_verified": False}, "UNKNOWN"),
    ({"membership": False}, "UNKNOWN"),
    ({"membership": False, "complete": True}, "UNKNOWN"),
    ({"current_backcast": True}, "UNKNOWN"),
    ({"future_correction": True}, "UNKNOWN"),
    ({"live": False}, "UNKNOWN"),
    ({"conflict": True}, "SOURCE_CONFLICT"),
    ({"explicit_negative": True}, "SOURCE_CONFLICT"),
])
def test_preserved_necessary_evidence_witnesses_not_real_membership(changes, expected):
    assert previous._necessary_applicability(previous._witness(**changes)) == expected


@pytest.mark.parametrize("field", ["native_known_at", "effective_from"])
def test_future_evidence_excluded_from_original_D(field):
    w = previous._witness()
    w[field] = w["D"] + timedelta(microseconds=1)
    assert previous._necessary_applicability(w) == "UNKNOWN"


def test_native_date_only_and_later_revision_visibility_boundaries():
    previous.test_date_only_publication_does_not_invent_intraday_knownness()
    previous.test_terminal_future_evidence_never_rewrites_original_D()


def test_access_failure_is_not_an_exchange_HTTP_denial_or_missing_document():
    a = _read()
    assert len(a["access_audit"]) == 4
    for row in a["access_audit"][:3]:
        assert len(row["attempts"]) == 5
        assert row["attempts"][-1]["result"] == "ReadTimeout"
        assert row["retries_after_timeout"] == 0
        assert all(attempt["http_status"] is None for attempt in row["attempts"])
    assert a["access_limits"]["TLS_verification"]
    assert not a["access_limits"]["authenticated_sessions_used"]
    assert not a["audit_date_is_historical_known_at"]


def test_internal_source_roles_use_existing_pinned_contracts_only():
    a = _read()
    assert len(a["internal_sources"]) == 16
    for row in a["internal_sources"]:
        assert row["role"] == "METADATA_ONLY_READ_NOT_INVOCATION"
        assert row["fingerprint_lf"] == a["inspected_file_fingerprints_lf"][row["path"]]
        assert row["finding"] and row["version"]
