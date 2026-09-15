"""Offline source-audit conformance, not an applicability or price producer.

Synthetic witnesses exercise necessary rejection boundaries only. They cannot
fetch sources, register authority, admit a cohort, select prices or change gates.
"""
from datetime import UTC, datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path
import subprocess
from urllib.parse import urlsplit

import pytest

from app.fundamentals.diagnostic_comparability import canonical_json, content_fingerprint
from tests.unit import test_gate1_rotation_research_bootstrap_independent_prior_evidence as previous

ROOT = Path(__file__).resolve().parents[2]
BASELINE = "43da29f531990c47fa605c08c494e7b4adf7f182"
STEM = "GATE1_ROTATION_RESEARCH_SESSION_PRICE_SOURCE_APPLICABILITY_AUDIT_V1"
PATH = ROOT / "docs/architecture" / (STEM + ".json")
FP = "sha256:e587cfb98e32610f6a0485c87d62a8546400ac19498c0aef18ad0b38b22e967c"
NEXT = "NSE_CAS_SECURITY_MEMBERSHIP_AND_CLOSE_SOURCE_RECOVERY_V1"
MATRIX = {
    "REGULAR_NSE_SESSION_SOURCE": "DERIVABLE",
    "CAS_APPLICABILITY_SOURCE": "SOURCE_NOT_READY",
    "CAS_SECURITY_MEMBERSHIP": "SOURCE_NOT_READY",
    "CAS_EFFECTIVE_DATES": "SOURCE_EVIDENCE_SUFFICIENT",
    "SECURITY_IDENTITY_MAPPING": "DERIVABLE",
    "PROSPECTIVE_CALENDAR": "SOURCE_NOT_READY",
    "HISTORICAL_CALENDAR": "SOURCE_NOT_READY",
    "SPECIAL_SESSIONS": "SOURCE_NOT_READY",
    "DAILY_CLOSE_SEMANTICS": "POLICY_REQUIRED",
    "INTRADAY_COVERAGE": "SOURCE_NOT_READY",
    "START_D_OBSERVATION_COVERAGE": "POLICY_REQUIRED",
    "TERMINAL_OBSERVATION_COVERAGE": "POLICY_REQUIRED",
    "ADJUSTED_PRICE_INTEGRITY": "DERIVABLE",
    "SUSPENSION_NO_TRADE": "SOURCE_NOT_READY",
    "DELISTING": "BLOCKED",
    "CORPORATE_ACTION_TRANSITIONS": "POLICY_REQUIRED",
    "SOURCE_PRECEDENCE": "POLICY_REQUIRED",
    "CONFLICT_HANDLING": "CONFLICTED"
}
INTERNAL = tuple("I%02d" % i for i in range(1, 20))
OFFICIAL = tuple("O%02d" % i for i in range(1, 8))
CASES_D = ["BEFORE_OPEN","DURING_REGULAR","DURING_CAS_OR_CLOSING","AFTER_CLOSE","NON_TRADING_DAY","SPECIAL_SESSION"]
CASES_END = ["REGULAR_CLOSE","CAS_CLOSE","NON_CAS_CLOSE","SPECIAL_SESSION","SUSPENSION","MISSING_FEED_BAR","DELISTING","CORPORATE_ACTION"]
IMPACTS = {
    "DURATION_UNIT": "UNCHANGED",
    "COUNTING": "NARROWED",
    "START_PRICE": "NARROWED",
    "TERMINAL_BOUNDARY": "NARROWED",
    "TERMINAL_PRICE": "NEW",
    "CALENDAR_AUTHORITY": "NARROWED",
    "INSTRUMENT_ELIGIBILITY": "NARROWED"
}


def _read():
    return json.loads(PATH.read_text(encoding="utf-8"))


def _digest(a):
    return content_fingerprint({k: v for k, v in a.items() if k != "artifact_fingerprint"})


def _need(condition, code):
    if not condition:
        raise ValueError(code)


def _verify(a):
    p = previous._read()
    _need((a["baseline_commit"], a["slice"], a["version"], a["audit_id"]) == (
        BASELINE, STEM, "v1", "gate1-rotation-research-session-price-source-applicability-audit"
    ), "AUDIT_IDENTITY")
    _need((a["decision"], a["semantic_decision"], a["slice_status"]) == (
        "C", "SESSION_PRICE_SOURCE_APPLICABILITY_SOURCE_GAPS", "ACCEPTED/CLOSED"
    ), "READINESS_OVERCLAIM")
    _need(a["status"] == "SOURCE_APPLICABILITY_AUDIT / NO_PARAMETER_APPROVAL / NOT_ACTIVE"
          and a["authority"] == p["authority"]
          and a["bootstrap_policy_status"] == p["bootstrap_policy_status"], "AUTHORITY_CHANGED")
    for field in ("preservation", "registration", "effective_parameters"):
        _need(a[field] == p[field], "PREDECESSOR_CHANGED")
    _need(all(v is None for v in a["effective_parameters"].values()), "PARAMETER_INVENTED")
    _need(not any(a["runtime"].values()), "RUNTIME_SCOPE")
    scope = a["scope"]
    _need(scope["selected_research_population"] is None
          and not any(scope[k] for k in (
              "expanded", "eq_series_proves_ordinary_equity", "financial_or_other_company_type_inferred",
              "etf_sme_other_segments_auto_included", "index_price_is_security_price"
          )), "SEGMENT_EXPANSION")
    c = a["classifier"]
    _need(c["status"] == "NECESSARY_EVIDENCE_REQUIREMENTS_ONLY_NOT_IMPLEMENTED"
          and c["states"] == ["CAS_APPLICABLE", "NON_CAS", "UNKNOWN", "SOURCE_CONFLICT"]
          and not any(c[k] for k in (
              "absence_from_partial_list_is_non_cas", "current_membership_backcast",
              "runtime_now_used", "global_launch_implies_membership", "symbol_only_matching",
              "implementation_authorized"
          )) and c["default_for_unknown"] is None
          and len(c["mandatory_evidence"]) == 9, "APPLICABILITY_SHORTCUT")
    _need(not any(a["temporal"][k] for k in (
        "later_notice_authorizes_earlier_D", "correction_automatically_rewrites_history",
        "same_day_date_is_exact_publication"
    )) and a["temporal"]["terminal_future_regime_policy"] == "POLICY_REQUIRED", "PIT_REWRITE")
    identity = a["identity"]
    _need(identity["readiness"] == "DERIVABLE"
          and identity["cas_join_readiness"] == "SOURCE_NOT_READY"
          and not any(identity[k] for k in (
              "current_symbol_backcast", "session_point_is_listing_interval",
              "session_point_is_intraday_publication", "suspension_is_identity_deletion"
          )), "IDENTITY_OVERCLAIM")
    _need(a["prospective"]["status"] == "PROSPECTIVE_SOURCE_BLOCKED"
          and not a["prospective"]["ready_now"]
          and not a["prospective"]["complete_historical_reconstruction_required_for_new_D"]
          and {r["component"]: r["status"] for r in a["historical"]} == {
              "CAS_NON_CAS_APPLICABILITY": "ABSENT", "SESSION_CALENDAR": "BOUNDED",
              "PRICE_OBSERVATIONS": "INSUFFICIENT", "SECURITY_IDENTITY": "BOUNDED",
              "CORPORATE_ACTION_CONSISTENCY": "INSUFFICIENT"
          }, "COVERAGE_OVERCLAIM")
    _need(tuple(r["id"] for r in a["official_sources"]) == OFFICIAL, "OFFICIAL_INVENTORY")
    for r in a["official_sources"]:
        url = urlsplit(r["url"])
        _need(url.scheme == "https" and not url.username and not url.password
              and url.hostname in {"nsearchives.nseindia.com", "www.nseindia.com", "www.sebi.gov.in"}
              and r["native_HSI_known_at"] is None and r["raw_response_fingerprint"] is None
              and not r["raw_bytes_retained"] and not r["research_authority"]
              and not r["correction_chain_recovered"], "SOURCE_PROVENANCE")
        _need(r["access_status"] == {
            "O01": "PRIMARY_BODY_READ", "O02": "PRIMARY_BODY_READ",
            "O03": "PRIMARY_PAGE_READ", "O04": "BODY_UNAVAILABLE",
            "O05": "BODY_UNAVAILABLE", "O06": "BODY_UNAVAILABLE",
            "O07": "LANDING_ONLY_BODY_UNAVAILABLE"
        }[r["id"]], "UNREAD_SOURCE_PROMOTED")
    _need(a["official_sources"][0]["effective_date"] == "2026-08-03", "EFFECTIVE_DATE_CHANGED")
    _need(tuple(r["id"] for r in a["internal_sources"]) == INTERNAL, "INTERNAL_INVENTORY")
    for r in a["internal_sources"]:
        _need(r["fingerprint_lf"] == a["inspected_file_fingerprints_lf"][r["path"]]
              and all(r[k] for k in ("source_type", "purpose", "coverage", "effective", "known_at",
                                     "version", "security_segment", "historical", "prospective",
                                     "authority")), "INTERNAL_PROVENANCE")
    rows = a["source_applicability_matrix"]
    _need(len(rows) == len(MATRIX) and {r["component"]: r["readiness"] for r in rows} == MATRIX,
          "MATRIX_INCOMPLETE_OR_PROMOTED")
    for r in rows:
        _need(r["authority_status"] == "AUTHORITY_NOT_REGISTERED"
              and all(r[k] for k in ("provenance", "PIT_status", "historical_status",
                                    "prospective_status", "blocker_recommendation"))
              and all(x in INTERNAL + OFFICIAL for x in r["canonical_sources"]),
              "MATRIX_PROVENANCE")
    _need(len(a["price_candidates"]) == 10
          and len({r["id"] for r in a["price_candidates"]}) == 10
          and all(not r["selected"] and not r["executable_fill"] for r in a["price_candidates"]),
          "PRICE_AUTHORITY")
    _need([r["case"] for r in a["start_cases"]] == CASES_D
          and [r["case"] for r in a["terminal_cases"]] == CASES_END
          and all(r["selected_price"] is None and not r["fallback"]
                  for r in a["start_cases"] + a["terminal_cases"]), "PRICE_DEFAULT")
    _need(not any(a["close_semantics"][k] for k in (
        "homogeneous", "bar_close_is_verified_official_across_regimes",
        "auction_indicator_in_canonical_bar", "official_reference_is_hsi_fallback_permission",
        "synthetic_price_allowed"
    )) and a["close_semantics"]["official_reference_may_exist_without_new_trade"],
          "CLOSE_SEMANTICS_OVERCLAIM")
    r = a["reconciliation"]
    _need(r["state"] == "PRICE_SOURCE_PRECEDENCE_POLICY_REQUIRED"
          and r["selected_source"] is None and not any(r[k] for k in (
              "auto_average", "prefer_daily", "prefer_live", "prefer_cas"
          )), "PRICE_PRECEDENCE_INVENTED")
    _need(a["corporate_actions"]["raw_immutable"]
          and not a["corporate_actions"]["mixed_adjustment_allowed"]
          and not a["corporate_actions"]["price_move_infers_action"]
          and a["corporate_actions"]["return_method"] is None, "ADJUSTMENT_SHORTCUT")
    _need(not any(a["exceptional"][k] for k in (
        "synthetic_prices", "carry_forward", "nearest_bar", "automatic_deferral",
        "automatic_exclusion", "new_lifecycle_created"
    )), "EXCEPTIONAL_PRICE_INVENTED")
    _need(not any(a["special"][k] for k in (
        "mock_is_real", "mock_matures_horizon", "ordinary_count_by_default",
        "unannounced_closure_changes_frozen_end"
    )), "MOCK_OR_SPECIAL_PROMOTION")
    _need(len(a["conflicts"]) == 5 and all(not r["automatic_winner"] and r["required"]
                                         for r in a["conflicts"]), "CONFLICT_HIDDEN")
    _need({r["parameter"]: r["impact"] for r in a["parameter_impact"]} == IMPACTS
          and all(not r["parameter_approved"] for r in a["parameter_impact"]), "PARAMETER_APPROVED")
    _need(a["next_continuations"] == [NEXT] and not a["next_continuation_started"], "NEXT_SCOPE")
    _need(_digest(a) == a["artifact_fingerprint"] == FP, "AUDIT_TAMPERED")


def test_audit_is_consistent_and_stably_serialized():
    a = _read()
    _verify(a)
    _verify(json.loads(canonical_json(a)))
    assert _digest(dict(reversed(list(a.items())))) == FP


@pytest.mark.parametrize("ref", [_read()["parent"], *_read()["predecessors"]], ids=lambda r: r["path"])
def test_all_nine_predecessors_unchanged(ref):
    p = ROOT / ref["path"]
    old = json.loads(p.read_text(encoding="utf-8"))
    assert old[ref["field"]] == ref["fingerprint"]
    assert content_fingerprint({k: v for k, v in old.items() if k != ref["field"]}) == ref["fingerprint"]
    committed = subprocess.check_output(["git", "show", BASELINE + ":" + ref["path"]], cwd=ROOT)
    assert p.read_bytes().replace(b"\r\n", b"\n") == committed.replace(b"\r\n", b"\n")


@pytest.mark.parametrize("path,fp", _read()["inspected_file_fingerprints_lf"].items())
def test_frozen_baseline_source_pins(path, fp):
    raw = subprocess.check_output(["git", "show", BASELINE + ":" + path], cwd=ROOT)
    assert "sha256:" + sha256(raw.replace(b"\r\n", b"\n")).hexdigest() == fp


def test_V1_ACTIVE_V2_NOT_ACTIVE_no_runtime_consumer():
    previous.test_V1_ACTIVE_V2_NOT_ACTIVE_and_no_runtime_consumer()
    a = _read()
    assert a["authority"]["v1"]["status"] == "ACTIVE"
    assert a["authority"]["v2"]["status"] == "NOT_ACTIVE"
    for path in (ROOT / "app").rglob("*.py"):
        assert STEM not in path.read_text(encoding="utf-8")


def _witness(**changes):
    # Synthetic requirements witness, not live exchange membership or admitted price.
    D = datetime(2026, 9, 15, 8, tzinfo=UTC)
    w = dict(D=D, effective_from=D - timedelta(days=1), effective_to=D + timedelta(days=1),
             native_known_at=D, session_matches=True, official_body_verified=True,
             fingerprint_verified=True, exact_identity=True, scope_verified=True,
             membership=True, complete=False, complement_semantics=False,
             explicit_negative=False, current_backcast=False, conflict=False,
             live=True, future_correction=False)
    w.update(changes)
    return w


def _necessary_applicability(w):
    # Cannot establish availability: only tests the audit's necessary conditions.
    cutoff = w["D"]
    if w["conflict"]:
        return "SOURCE_CONFLICT"
    if any(v.tzinfo is None or v.utcoffset() is None for v in (
        cutoff, w["effective_from"], w["effective_to"], w["native_known_at"]
    )):
        return "UNKNOWN"
    if not (w["effective_from"] <= cutoff <= w["effective_to"]
            and w["native_known_at"] <= cutoff):
        return "UNKNOWN"
    if not all(w[k] for k in ("session_matches", "official_body_verified", "fingerprint_verified",
                              "exact_identity", "scope_verified", "live")):
        return "UNKNOWN"
    if w["current_backcast"] or w["future_correction"]:
        return "UNKNOWN"
    if w["membership"] is True and w["explicit_negative"]:
        return "SOURCE_CONFLICT"
    if w["membership"] is True:
        return "CAS_APPLICABLE"
    if w["explicit_negative"] or (
        w["membership"] is False and w["complete"] and w["complement_semantics"]
    ):
        return "NON_CAS"
    return "UNKNOWN"


@pytest.mark.parametrize("changes,expected", [
    ({}, "CAS_APPLICABLE"),
    ({"membership": False}, "UNKNOWN"),
    ({"membership": None}, "UNKNOWN"),
    ({"membership": False, "complete": True}, "UNKNOWN"),
    ({"membership": False, "complete": True, "complement_semantics": True}, "NON_CAS"),
    ({"membership": False, "explicit_negative": True}, "NON_CAS"),
    ({"explicit_negative": True}, "SOURCE_CONFLICT"),
    ({"conflict": True}, "SOURCE_CONFLICT"),
    ({"exact_identity": False}, "UNKNOWN"),
    ({"scope_verified": False}, "UNKNOWN"),
    ({"official_body_verified": False}, "UNKNOWN"),
    ({"fingerprint_verified": False}, "UNKNOWN"),
    ({"session_matches": False}, "UNKNOWN"),
    ({"current_backcast": True}, "UNKNOWN"),
    ({"live": False}, "UNKNOWN"),
    ({"future_correction": True}, "UNKNOWN"),
])
def test_source_identity_segment_completeness_and_mock_rejection(changes, expected):
    assert _necessary_applicability(_witness(**changes)) == expected


@pytest.mark.parametrize("field", ["native_known_at", "effective_from"])
def test_future_publication_or_effectivity_cannot_authorize_D(field):
    w = _witness()
    w[field] = w["D"] + timedelta(microseconds=1)
    assert _necessary_applicability(w) == "UNKNOWN"


def test_equal_cutoff_and_equivalent_timezone_and_expired_evidence():
    w = _witness()
    assert _necessary_applicability(w) == "CAS_APPLICABLE"
    w["D"] = w["D"].astimezone(timezone(timedelta(hours=5, minutes=30)))
    assert _necessary_applicability(w) == "CAS_APPLICABLE"
    w["effective_to"] = w["D"] - timedelta(microseconds=1)
    assert _necessary_applicability(w) == "UNKNOWN"


def test_terminal_future_evidence_never_rewrites_original_D():
    w = _witness()
    original_D = w["D"]
    R = original_D + timedelta(days=10)
    w.update(effective_from=original_D + timedelta(days=2),
             effective_to=R + timedelta(days=1), native_known_at=R)
    assert _necessary_applicability(w) == "UNKNOWN"
    later = {**w, "D": R}
    assert _necessary_applicability(later) == "CAS_APPLICABLE"
    assert w["D"] == original_D
    assert _read()["temporal"]["terminal_future_regime_policy"] == "POLICY_REQUIRED"


def test_date_only_publication_does_not_invent_intraday_knownness():
    from app.historical.canonical_market_session_event_time import make_first_party_session_source, _source_visible
    from datetime import date
    source = make_first_party_session_source(
        source_id="synthetic-official-date",
        source_reference="https://nsearchives.nseindia.com/content/circulars/synthetic-fixture.pdf",
        published_on=date(2026, 9, 15))
    assert not _source_visible(source, datetime(2026, 9, 15, 18, tzinfo=UTC), "Asia/Kolkata")
    assert _source_visible(source, datetime(2026, 9, 16, 18, tzinfo=UTC), "Asia/Kolkata")


@pytest.mark.parametrize("field", _read()["runtime"])
def test_no_runtime_registration_cohort_labels_calibration_model_gate_side_effect(field):
    a = _read()
    a["runtime"][field] = True
    a["artifact_fingerprint"] = _digest(a)
    with pytest.raises(ValueError, match="RUNTIME_SCOPE"):
        _verify(a)


@pytest.mark.parametrize("field", _read()["effective_parameters"])
def test_no_seed_unit_start_terminal_or_other_default(field):
    a = _read()
    a["effective_parameters"][field] = "FORBIDDEN_DEFAULT"
    a["artifact_fingerprint"] = _digest(a)
    with pytest.raises(ValueError, match="PREDECESSOR_CHANGED"):
        _verify(a)


@pytest.mark.parametrize("component", MATRIX)
def test_unavailable_matrix_rows_cannot_be_resealed_as_READY(component):
    a = _read()
    next(r for r in a["source_applicability_matrix"] if r["component"] == component)["readiness"] = "READY"
    a["artifact_fingerprint"] = _digest(a)
    with pytest.raises(ValueError, match="MATRIX_INCOMPLETE_OR_PROMOTED"):
        _verify(a)


@pytest.mark.parametrize("section,field,code", [
    ("classifier", "absence_from_partial_list_is_non_cas", "APPLICABILITY_SHORTCUT"),
    ("classifier", "current_membership_backcast", "APPLICABILITY_SHORTCUT"),
    ("classifier", "global_launch_implies_membership", "APPLICABILITY_SHORTCUT"),
    ("scope", "eq_series_proves_ordinary_equity", "SEGMENT_EXPANSION"),
    ("scope", "etf_sme_other_segments_auto_included", "SEGMENT_EXPANSION"),
    ("temporal", "later_notice_authorizes_earlier_D", "PIT_REWRITE"),
    ("temporal", "correction_automatically_rewrites_history", "PIT_REWRITE"),
    ("identity", "session_point_is_intraday_publication", "IDENTITY_OVERCLAIM"),
    ("close_semantics", "homogeneous", "CLOSE_SEMANTICS_OVERCLAIM"),
    ("close_semantics", "official_reference_is_hsi_fallback_permission", "CLOSE_SEMANTICS_OVERCLAIM"),
    ("reconciliation", "prefer_daily", "PRICE_PRECEDENCE_INVENTED"),
    ("reconciliation", "prefer_live", "PRICE_PRECEDENCE_INVENTED"),
    ("reconciliation", "prefer_cas", "PRICE_PRECEDENCE_INVENTED"),
    ("reconciliation", "auto_average", "PRICE_PRECEDENCE_INVENTED"),
    ("corporate_actions", "mixed_adjustment_allowed", "ADJUSTMENT_SHORTCUT"),
    ("exceptional", "nearest_bar", "EXCEPTIONAL_PRICE_INVENTED"),
    ("exceptional", "carry_forward", "EXCEPTIONAL_PRICE_INVENTED"),
    ("exceptional", "synthetic_prices", "EXCEPTIONAL_PRICE_INVENTED"),
    ("exceptional", "automatic_deferral", "EXCEPTIONAL_PRICE_INVENTED"),
    ("special", "mock_matures_horizon", "MOCK_OR_SPECIAL_PROMOTION"),
    ("special", "ordinary_count_by_default", "MOCK_OR_SPECIAL_PROMOTION"),
])
def test_resealed_shortcuts_rejected(section, field, code):
    a = _read()
    a[section][field] = True
    a["artifact_fingerprint"] = _digest(a)
    with pytest.raises(ValueError, match=code):
        _verify(a)


@pytest.mark.parametrize("section", ["start_cases", "terminal_cases"])
def test_no_prices_for_suspension_delisting_special_missing_or_D(section):
    for i in range(len(_read()[section])):
        a = _read()
        a[section][i]["selected_price"] = 0
        a["artifact_fingerprint"] = _digest(a)
        with pytest.raises(ValueError, match="PRICE_DEFAULT"):
            _verify(a)


def test_unread_source_conflict_and_authority_cannot_be_promoted():
    for idx in (3, 4, 5, 6):
        a = _read()
        a["official_sources"][idx]["access_status"] = "PRIMARY_BODY_READ"
        a["artifact_fingerprint"] = _digest(a)
        with pytest.raises(ValueError, match="UNREAD_SOURCE_PROMOTED"):
            _verify(a)
    for idx in range(5):
        a = _read()
        a["conflicts"][idx]["automatic_winner"] = True
        a["artifact_fingerprint"] = _digest(a)
        with pytest.raises(ValueError, match="CONFLICT_HIDDEN"):
            _verify(a)


def test_supported_actions_do_not_claim_complete_return_method():
    a = _read()
    assert {r["kind"]: r["state"] for r in a["corporate_actions"]["cases"]} == {
        "SPLIT": "DERIVABLE", "BONUS": "DERIVABLE", "DIVIDEND": "POLICY_REQUIRED",
        "RIGHTS": "SOURCE_NOT_READY", "MERGER_DEMERGER": "BLOCKED",
        "SYMBOL_SECURITY_RELISTING": "BLOCKED"
    }
    assert a["corporate_actions"]["return_method"] is None
    assert "PENDING_MATURITY" in a["exceptional"]["reuse"]
    assert "EXCLUDED" in a["exceptional"]["reuse"]


def test_document_matrix_one_next_and_tampering():
    a = _read()
    md = PATH.with_suffix(".md").read_text(encoding="utf-8")
    assert a["status"] in md and a["semantic_decision"] in md and md.count(NEXT) == 1
    assert all(r["component"] in md and r["readiness"] in md for r in a["source_applicability_matrix"])
    assert all(r["path"] in md for r in a["internal_sources"])
    assert STEM + ".md" in (ROOT / "README.md").read_text(encoding="utf-8")
    a["next_continuations"].append("FORBIDDEN")
    a["artifact_fingerprint"] = _digest(a)
    with pytest.raises(ValueError, match="NEXT_SCOPE"):
        _verify(a)
    a = _read()
    a["rationale"] += " tampered"
    a["artifact_fingerprint"] = _digest(a)
    with pytest.raises(ValueError, match="AUDIT_TAMPERED"):
        _verify(a)
