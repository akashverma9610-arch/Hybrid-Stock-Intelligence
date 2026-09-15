"""Offline external-input dossier checks, not CAS ingestion or admission runtime.

No private retained files are required by these portable conformance tests.
The audit records their byte verification; fixtures are necessary-condition
witnesses only and never become source observations or membership records.
"""
from datetime import timedelta
from hashlib import sha256
import json
from pathlib import Path
import subprocess
from urllib.parse import urlsplit

import pytest

from app.fundamentals.diagnostic_comparability import canonical_json, content_fingerprint
from tests.unit import test_nse_cas_security_membership_and_close_source_recovery as previous

ROOT = Path(__file__).resolve().parents[2]
STEM = "NSE_CAS_PRIMARY_SOURCE_ACCESS_AND_DATED_MEMBERSHIP_EVIDENCE_RECOVERY_V1"
BASELINE = "cb3d57894f6e67ac7873afc7ea037da1d39b5707"
PATH = ROOT / "docs/architecture" / (STEM + ".json")
FP = "sha256:be5c917b1bd03ae629713121349ff909dcaff93dd6addf8f2a3abd3a2b462c06"
NEXT = "NSE_CAS_USER_SUPPLIED_PRIMARY_EVIDENCE_ADMISSION_V1"


def _read():
    return json.loads(PATH.read_text(encoding="utf-8"))


def _digest(value, field="artifact_fingerprint"):
    return content_fingerprint({k: v for k, v in value.items() if k != field})


def _need(condition, code):
    if not condition:
        raise ValueError(code)


def _pins():
    return {**previous._read()["inspected_file_fingerprints_lf"], **_read()["additional_file_fingerprints_lf"]}


def _verify(a):
    p = previous._read()
    _need((a["slice"], a["baseline_commit"], a["dossier_id"], a["version"]) == (
        STEM, BASELINE, "nse-cas-primary-source-access-and-dated-membership-evidence-recovery", "v1"
    ), "DOSSIER_IDENTITY")
    _need((a["decision"], a["semantic_decision"], a["slice_status"], a["status"]) == (
        "C", "EXTERNAL_PRIMARY_SOURCE_INPUT_REQUIRED", "BLOCKED",
        "EVIDENCE_DOSSIER / EXTERNAL_INPUT_REQUIRED / NOT_ACTIVE"
    ), "RECOVERY_OVERCLAIM")
    for field in ("authority", "bootstrap_policy_status", "bootstrap_seed", "effective_parameters", "preservation", "registration"):
        _need(a[field] == p[field], "FROZEN_AUTHORITY")
    _need(a["bootstrap_seed"] == "UNSET" and all(v is None for v in a["effective_parameters"].values()), "PARAMETER_INVENTED")
    _need(not any(a["runtime"].values()), "RUNTIME_SCOPE")
    _need(a["source_pin_reference"]["artifact_fingerprint"] == p["artifact_fingerprint"]
          and a["source_pin_reference"]["count"] == 204
          and len(a["additional_file_fingerprints_lf"]) == 3, "SOURCE_PIN_REFERENCE")
    _need(a["recovery_state_vocabulary"] == ["RECOVERED", "PARTIALLY_RECOVERED", "OFFICIAL_REFERENCE_ONLY",
          "ACCESS_REQUIRES_EXTERNAL_INPUT", "UNAVAILABLE"], "RECOVERY_VOCABULARY")
    _need(a["evidence_state_vocabulary"] == ["PRIMARY_SOURCE_VERIFIED", "PRIMARY_SOURCE_PARTIAL", "REFERENCE_ONLY",
          "SOURCE_CONFLICT", "SOURCE_MISSING"], "CONFIDENCE_VOCABULARY")
    _need([r["document_id"] for r in a["primary_bodies"]] == ["CMTR73845", "CMTR74466", "CMTR67774"], "BODY_INVENTORY")
    for row in a["primary_bodies"]:
        _need(row["reference_state"] == "OFFICIAL_REFERENCE_ONLY"
              and row["access_state"] == "ACCESS_REQUIRES_EXTERNAL_INPUT" and row["evidence_state"] == "REFERENCE_ONLY"
              and not row["body_recovered"] and not row["body_content_inferred"]
              and not row["attachment_inventory_complete"] and row["document_attachment_references"] == [], "BODY_INFERRED")
        _need(all(row[k] is None for k in ("raw_fingerprint", "raw_bytes", "raw_mime_type", "native_HSI_known_at",
                    "published_at", "effective_from", "effective_to", "revised_at", "superseded_by")), "BODY_PROVENANCE_INVENTED")
        _need(_digest(row, "evidence_fingerprint") == row["evidence_fingerprint"], "BODY_SUMMARY_TAMPERED")
    _need(a["primary_bodies"][2]["exact_title"] is None, "UNREAD_TITLE_INVENTED")
    for row in a["primary_bodies"] + a["reference_sources"]:
        u = urlsplit(row.get("official_url", row.get("url")))
        _need(u.scheme == "https" and u.hostname in {"nsearchives.nseindia.com", "www.nseindia.com"}
              and not u.username and not u.password, "UNOFFICIAL_SOURCE")
    _need(len(a["access_attempts"]) == 15 and all(r["http_status"] is None
          and not r["body_recovered"] and r["raw_fingerprint"] is None for r in a["access_attempts"]), "ACCESS_EVIDENCE")
    host = [r for r in a["access_attempts"] if r["method"] == "AUTHORIZED_BOUNDED_HOST_GET"]
    _need(len(host) == 5 and len({r["url"] for r in host}) == 5 and all(r["result"] == "ReadTimeout" for r in host), "BOUNDED_ATTEMPTS")
    limits = a["access_limits"]
    _need(limits["retries"] == 0 and limits["TLS_verification"] and limits["implicit_netrc_auth_disabled"]
          and not any(limits[k] for k in ("credential_values_accessed", "proxy_settings_changed", "source_files_written",
                                         "HTTP_status_assumed", "redirects_followed")), "ACCESS_BOUNDARY")
    local = a["local_discovery"]
    _need(not local["enumeration_complete"] and len(local["inaccessible_paths"]) == 2
          and local["exact_target_filename_matches"] == 0 and local["user_supplied_required_originals_located"] == 0
          and not any(local[k] for k in ("personal_directories_searched", "old_OneDrive_repository_accessed",
                                         "raw_originals_modified")), "LOCAL_SCOPE_OVERCLAIM")
    _need(len(local["retained_originals"]) == 1, "LOCAL_ORIGINAL_INVENTORY")
    raw = local["retained_originals"][0]
    _need(raw["evidence_state"] == "REFERENCE_ONLY" and not raw["membership_admitted"]
          and not raw["modified"] and raw["CAS_known_at"] is None
          and raw["hash_matches_existing_receipt"] and not raw["receipt_authenticity_independently_verified"], "QUOTE_SHELL_PROMOTED")
    _need(raw["raw_fingerprint"] == "sha256:c1587f291187f64f8df944c732ee9a59840ae00788fddab6f97b21618e28700d"
          and raw["size_bytes"] == 146357
          and _digest(raw, "derivative_fingerprint") == raw["derivative_fingerprint"]
          and raw["raw_fingerprint"] != raw["derivative_fingerprint"], "RAW_DERIVED_FINGERPRINT")
    display = a["current_display"]
    _need(display["state"] == "PRIMARY_SOURCE_PARTIAL" and display["CSV_download_control_visible"]
          and display["records_recovered"] == 0 and display["raw_row_keys"] == []
          and display["exact_CSV_headers"] is None and display["exact_API_url"] is None
          and not any(display[k] for k in ("CSV_payload_recovered", "label_is_machine_schema", "ISIN_verified",
                    "series_verified", "segment_verified", "finality_encoding_verified", "no_match_encoding_verified")), "DISPLAY_OVERCLAIM")
    _need(a["recovered_membership_payloads"] == [] and a["recovered_revisions"] == [], "MEMBERSHIP_INVENTED")
    m = a["membership"]
    _need(m["state"] == "SOURCE_MISSING" and m["completeness"] == "UNDETERMINED_NO_PAYLOAD"
          and m["exact_identifiers"] == [] and not any(m[k] for k in (
              "candidate_body_recovered", "revision_chain_complete", "delta_is_complete", "rule_is_membership",
              "empty_display_is_complete_universe", "all_current_members_backcast", "partial_absence_is_non_cas"
          )) and all(m[k] is None for k in ("publication_date", "effective_from", "effective_to", "segment_verified",
                       "inclusion_codes", "exclusion_codes", "source_schema_version", "raw_fingerprint", "raw_size_bytes")), "MEMBERSHIP_SHORTCUT")
    _need(m["allowed_evidence_kinds"] == ["COMPLETE_SNAPSHOT", "STATIC_INITIAL_LIST", "ADDITIONS_ONLY", "REMOVALS_ONLY",
          "DELTA_REVISION", "ILLUSTRATIVE_SAMPLE", "ELIGIBILITY_RULE_ONLY"] and len(m["revision_contract"]) == 7, "REVISION_CONTRACT")
    c = a["chronology"]
    _need(not any(c[k] for k in ("published_at_equals_effective_from", "filename_date_establishes_known_at",
                    "filesystem_mtime_is_publication", "later_revision_authorizes_original_D", "later_capture_backfills_known_at",
                    "unknown_effective_end_is_perpetual", "launch_implies_security_membership"))
          and c["evidence_contract_status"] == "NECESSARY_REQUIREMENTS_ONLY_NOT_IMPLEMENTED"
          and c["original_D"] is None and c["earliest_reconstructable_date"] is None
          and c["latest_reconstructable_date"] is None and c["global_live_date"] == "2026-08-03"
          and c["mock_date"] == "2026-08-01", "PIT_SHORTCUT")
    identity = a["identity"]
    _need(identity["result"] == "IDENTITY_SOURCE_BLOCKED" and identity["generic_HSI_join"] == "IDENTITY_JOIN_DERIVABLE"
          and identity["source_CAS_key_basis"] is None and not any(identity[k] for k in (
              "symbol_only_ambiguous_join", "symbol_only_display_proves_membership", "ETF_SME_other_scope_expanded",
              "ISIN_only_ignores_series")), "IDENTITY_SCOPE")
    close = a["close_sources"]
    _need(not any(close[k] for k in ("no_match_is_trade", "published_close_is_research_fill", "missing_feed_is_no_match",
                     "universal_source_authority", "reference_field_equals_final_field", "final_volume_zero_proves_no_match"))
          and close["price_precedence_selected"] is None and close["non_CAS"]["algorithm"] is None, "PRICE_SHORTCUT")
    _need(a["prospective"]["state"] == "SOURCE_BLOCKED" and not a["prospective"]["usable"]
          and a["historical"]["state"] == "HISTORICAL_MEMBERSHIP_UNRECOVERABLE"
          and a["historical"]["scope"].startswith("Within this bounded audit")
          and a["historical"]["from_date"] is None and a["historical"]["to_date"] is None
          and a["historical"]["security_rows"] == 0 and not a["historical"]["coverage_claimed"], "COVERAGE_OVERCLAIM")
    f = a["fingerprinting"]
    _need(not any(f[k] for k in ("raw_hash_proves_issuer", "raw_hash_proves_completeness", "raw_hash_proves_known_at",
                                 "synthetic_source_content_created")), "HASH_AUTHORITY")
    conflict = a["conflicts"]
    _need(not conflict["observed_material_primary_conflict"] and conflict["records"] == []
          and not conflict["convenient_value_selected"] and "SOURCE_CONFLICT" in conflict["behavior"], "CONFLICT_SHORTCUT")
    _need(len(a["parameter_impact"]) == 7 and all(not r["approved"] for r in a["parameter_impact"])
          and all(r["impact"] == ("BLOCKER_NARROWED" if r["parameter"] == "TERMINAL_PRICE_SOURCE" else "UNCHANGED")
                  for r in a["parameter_impact"]) and not a["bootstrap"]["source_ready"]
          and not a["bootstrap"]["activated"] and a["blockers_closed"] == [], "PARAMETER_APPROVAL")
    ext = a["external_input"]
    _need(ext["state"] == "EXTERNAL_PRIMARY_SOURCE_INPUT_REQUIRED" and ext["required"]
          and not ext["send_secrets"] and not ext["placeholder_files_created"]
          and [r["id"] for r in ext["items"]] == [f"E{n:02d}" for n in range(1, 7)]
          and all(r["required_original"] and r["accepted_types"] and r["issuer"] and r["closes"] for r in ext["items"])
          and len(ext["minimum_metadata"]) == 8 and len(ext["admission_steps"]) == 7, "EXTERNAL_INPUT_CONTRACT")
    _need(a["source_recovery_stopped"] and a["next_continuations"] == [NEXT]
          and not a["next_continuation_started"] and a["next_precondition"], "NEXT_SCOPE")
    _need([r["requirement"] for r in a["scope_coverage"]] == [f"{n:02d}" for n in range(1, 29)], "SCOPE_INCOMPLETE")
    _need(_digest(a) == a["artifact_fingerprint"] == FP, "DOSSIER_TAMPERED")


def test_complete_dossier_stable_serialization_and_previous_contract():
    a = _read()
    _verify(a)
    _verify(json.loads(canonical_json(a)))
    assert _digest(dict(reversed(list(a.items())))) == FP
    assert FP in PATH.with_suffix(".md").read_text(encoding="utf-8")
    previous._verify(previous._read())


@pytest.mark.parametrize("ref", [_read()["parent"], *_read()["predecessors"]], ids=lambda r: r["path"])
def test_all_thirteen_native_predecessors_unchanged(ref):
    path = ROOT / ref["path"]
    p = json.loads(path.read_text(encoding="utf-8"))
    assert p[ref["field"]] == _digest(p, ref["field"]) == ref["fingerprint"]
    original = subprocess.check_output(["git", "show", BASELINE + ":" + ref["path"]], cwd=ROOT)
    assert path.read_bytes().replace(b"\r\n", b"\n") == original.replace(b"\r\n", b"\n")


@pytest.mark.parametrize("path,fp", _pins().items())
def test_inherited_and_additional_baseline_pins(path, fp):
    raw = subprocess.check_output(["git", "show", BASELINE + ":" + path], cwd=ROOT)
    assert "sha256:" + sha256(raw.replace(b"\r\n", b"\n")).hexdigest() == fp


def test_V1_active_V2_inactive_no_new_runtime_consumer():
    previous.test_native_V1_ACTIVE_V2_NOT_ACTIVE_and_no_runtime_consumer()
    for path in (ROOT / "app").rglob("*.py"):
        assert STEM not in path.read_text(encoding="utf-8")


@pytest.mark.parametrize("field", _read()["runtime"])
def test_no_provider_DB_portfolio_broker_cohort_calibration_or_activation(field):
    a = _read()
    a["runtime"][field] = True
    a["artifact_fingerprint"] = _digest(a)
    with pytest.raises(ValueError, match="RUNTIME_SCOPE"):
        _verify(a)


@pytest.mark.parametrize("field", _read()["effective_parameters"])
def test_no_seed_duration_or_price_parameter_approval(field):
    a = _read()
    a["effective_parameters"][field] = "invented"
    a["artifact_fingerprint"] = _digest(a)
    with pytest.raises(ValueError, match="FROZEN_AUTHORITY"):
        _verify(a)


@pytest.mark.parametrize("i", range(3))
@pytest.mark.parametrize("field,value,code", [
    ("body_recovered", True, "BODY_INFERRED"),
    ("access_state", "RECOVERED", "BODY_INFERRED"),
    ("body_content_inferred", True, "BODY_INFERRED"),
    ("raw_fingerprint", "sha256:" + "1" * 64, "BODY_PROVENANCE_INVENTED"),
    ("effective_from", "2026-08-03", "BODY_PROVENANCE_INVENTED"),
    ("section_provenance", "invented section text", "BODY_SUMMARY_TAMPERED"),
])
def test_reference_only_is_not_a_recovered_body(i, field, value, code):
    a = _read()
    a["primary_bodies"][i][field] = value
    a["artifact_fingerprint"] = _digest(a)
    with pytest.raises(ValueError, match=code):
        _verify(a)


@pytest.mark.parametrize("section,field,code", [
    ("membership", "delta_is_complete", "MEMBERSHIP_SHORTCUT"),
    ("membership", "rule_is_membership", "MEMBERSHIP_SHORTCUT"),
    ("membership", "all_current_members_backcast", "MEMBERSHIP_SHORTCUT"),
    ("membership", "empty_display_is_complete_universe", "MEMBERSHIP_SHORTCUT"),
    ("membership", "revision_chain_complete", "MEMBERSHIP_SHORTCUT"),
    ("chronology", "published_at_equals_effective_from", "PIT_SHORTCUT"),
    ("chronology", "filename_date_establishes_known_at", "PIT_SHORTCUT"),
    ("chronology", "later_revision_authorizes_original_D", "PIT_SHORTCUT"),
    ("chronology", "later_capture_backfills_known_at", "PIT_SHORTCUT"),
    ("identity", "symbol_only_ambiguous_join", "IDENTITY_SCOPE"),
    ("identity", "ETF_SME_other_scope_expanded", "IDENTITY_SCOPE"),
    ("identity", "ISIN_only_ignores_series", "IDENTITY_SCOPE"),
    ("current_display", "label_is_machine_schema", "DISPLAY_OVERCLAIM"),
    ("current_display", "no_match_encoding_verified", "DISPLAY_OVERCLAIM"),
    ("close_sources", "no_match_is_trade", "PRICE_SHORTCUT"),
    ("close_sources", "published_close_is_research_fill", "PRICE_SHORTCUT"),
    ("close_sources", "final_volume_zero_proves_no_match", "PRICE_SHORTCUT"),
    ("close_sources", "universal_source_authority", "PRICE_SHORTCUT"),
    ("fingerprinting", "raw_hash_proves_issuer", "HASH_AUTHORITY"),
    ("fingerprinting", "raw_hash_proves_completeness", "HASH_AUTHORITY"),
    ("fingerprinting", "raw_hash_proves_known_at", "HASH_AUTHORITY"),
    ("prospective", "usable", "COVERAGE_OVERCLAIM"),
    ("historical", "coverage_claimed", "COVERAGE_OVERCLAIM"),
    ("conflicts", "convenient_value_selected", "CONFLICT_SHORTCUT"),
    ("external_input", "send_secrets", "EXTERNAL_INPUT_CONTRACT"),
])
def test_unsafe_shortcuts_rejected_even_after_outer_reseal(section, field, code):
    a = _read()
    a[section][field] = True
    a["artifact_fingerprint"] = _digest(a)
    with pytest.raises(ValueError, match=code):
        _verify(a)


def test_exactly_one_next_continuation_requires_external_input_and_is_not_started():
    for field, value in (("next_continuations", [NEXT, "OTHER"]), ("next_continuation_started", True),
                         ("source_recovery_stopped", False)):
        a = _read()
        a[field] = value
        a["artifact_fingerprint"] = _digest(a)
        with pytest.raises(ValueError, match="NEXT_SCOPE"):
            _verify(a)


def test_raw_bytes_hash_differs_from_normalized_or_derived_interpretation():
    # Generic bytes only, not a fabricated exchange document or written fixture.
    raw = b"one\r\ntwo\r\n"
    original = "sha256:" + sha256(raw).hexdigest()
    normalized = "sha256:" + sha256(raw.replace(b"\r\n", b"\n")).hexdigest()
    derived = content_fingerprint({"raw_fingerprint": original, "scope": "generic test only"})
    assert len({original, normalized, derived}) == 3
    a = _read()
    a["local_discovery"]["retained_originals"][0]["derivative_fingerprint"] = original
    a["artifact_fingerprint"] = _digest(a)
    with pytest.raises(ValueError, match="RAW_DERIVED_FINGERPRINT"):
        _verify(a)


@pytest.mark.parametrize("changes,expected", [
    ({"membership": False, "complete": False}, "UNKNOWN"),
    ({"membership": False, "complete": True, "complement_semantics": False}, "UNKNOWN"),
    ({"current_backcast": True}, "UNKNOWN"),
    ({"official_body_verified": False}, "UNKNOWN"),
    ({"exact_identity": False}, "UNKNOWN"),
    ({"scope_verified": False}, "UNKNOWN"),
    ({"conflict": True}, "SOURCE_CONFLICT"),
    ({"live": False}, "UNKNOWN"),
])
def test_native_predecessor_necessary_evidence_not_a_new_classifier(changes, expected):
    fixture = previous.previous
    assert fixture._necessary_applicability(fixture._witness(**changes)) == expected


def test_native_known_at_and_effective_boundaries_remain_distinct():
    fixture = previous.previous
    for field in ("native_known_at", "effective_from"):
        witness = fixture._witness()
        witness[field] = witness["D"] + timedelta(microseconds=1)
        assert fixture._necessary_applicability(witness) == "UNKNOWN"
    fixture.test_date_only_publication_does_not_invent_intraday_knownness()
