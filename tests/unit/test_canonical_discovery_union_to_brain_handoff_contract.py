"""Offline contract conformance; synthetic witnesses are NOT a consumer binding.

No request dispatch, deep diagnosis, source acquisition or persistence occurs.
Witnesses demonstrate necessary identity/PIT/rejection algebra, not sufficient
production source verification or a new application handoff implementation.
"""
import ast
from copy import deepcopy
from dataclasses import asdict, replace
from datetime import UTC, datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path
import re
import subprocess

import pytest

from app.fundamentals.diagnostic_comparability import canonical_json, content_fingerprint
from app.historical.guard import BacktestLookaheadGuard
from app.historical.models import InstrumentLifecycle, UniverseMembership
from app.historical.security_master import HistoricalSecurityIdentity, HistoricalSecurityStatus
from app.intelligence.multi_funnel_discovery import (
    DiscoveryFunnelId as F, discovery_lead_payload, multi_funnel_discovery_registry,
)
from tests.unit import test_hsi_brain_funnel_runtime_reconciliation_audit as previous
from tests.unit import test_multi_funnel_candidate_union as fixture

ROOT = Path(__file__).resolve().parents[2]
STEM = "CANONICAL_DISCOVERY_UNION_TO_BRAIN_HANDOFF_CONTRACT_V1"
BASELINE = "89660090782a30b0eec8cc72dbe6a912f2087d17"
PATH = ROOT / "docs/architecture" / (STEM + ".json")
FP = "sha256:731399dfbca758763dda0ad9ee1350aa50cd433ab183bb62fc710e4b5826b1e8"
CID = "canonical-discovery-union-to-brain-handoff"
NEXT = "NSE_CAS_SECURITY_MEMBERSHIP_AND_CLOSE_SOURCE_RECOVERY_V1"
CONTEXTUAL = {"HOLDING_STATE_CHANGE", "WATCHLIST_STATE_CHANGE", "MARKET_DISLOCATION"}
RESEARCH = {"COMPOUNDER", "FUNDAMENTAL_INFLECTION", "POLICY_TRANSMISSION"}
READY = {"PRE_BREAKOUT", "SECTOR_ROTATION"}
FIELDS = (
    "contract_id contract_version contract_fingerprint inspection_request_id handoff_fingerprint "
    "canonical_security_id isin exchange security_type segment symbol identity_reference lifecycle_state "
    "source_master source_union source_candidate universe_reference membership_references union_as_of "
    "union_formed_at inspection_as_of request_created_at inspection_context origins origins.discovery_as_of "
    "origins.trigger_identity origins.producer_reference origins.lineage origins.freshness "
    "origins.role_and_admission origins.strategy_archetype origins.materiality_confidence context_references "
    "admission_state_and_reasons consumer_binding_reference consumer_binding_state submission_state "
    "prior_request_reference authority_boundary"
).split()
T = fixture.AS_OF


def _read():
    return json.loads(PATH.read_text(encoding="utf-8"))


def _need(condition, reason):
    if not condition:
        raise ValueError(reason)


def _verify(a):
    p = previous._read()
    _need((a["slice"], a["baseline_commit"], a["contract_id"], a["version"]) == (STEM, BASELINE, CID, "v1"), "IDENTITY")
    _need((a["decision"], a["semantic_decision"], a["slice_status"]) == (
        "B", "HANDOFF_CONTRACT_READY_WITH_CONSUMER_BINDING_BLOCKER", "ACCEPTED/CLOSED"
    ), "READINESS")
    _need(a["status"] == "CONTRACT_DEFINED / CONSUMER_BINDING_NOT_READY / NOT_ACTIVE", "STATUS")
    _need(a["parent"]["fingerprint"] == p["artifact_fingerprint"]
          and a["predecessors"] == p["predecessors"] + [p["parent"]], "PREDECESSOR")
    for key in ("authority", "bootstrap_policy_status", "effective_parameters", "preservation", "registration"):
        _need(a[key] == p[key], "GATE1_AUTHORITY")
    _need(a["registry"] == json.loads(canonical_json(asdict(multi_funnel_discovery_registry()))), "REGISTRY")
    rows = a["funnel_compatibility"]
    _need([r["funnel_id"] for r in rows] == [e["funnel_id"] for e in a["registry"]["entries"]] and len(rows)==14, "FUNNELS")
    for r,e in zip(rows,a["registry"]["entries"]):
        expected = ("CONDITIONAL_SOURCE_PROOF_REQUIRED" if r["funnel_id"] in READY else
                    "NON_ADMITTING_RESEARCH" if r["funnel_id"] in RESEARCH else
                    "UNSUPPORTED_AS_MARKETWIDE_ORIGIN" if r["funnel_id"] in CONTEXTUAL else "NON_ADMITTING_UNAVAILABLE")
        _need(r["registry_status"] == e["status"] and r["current_admission"] == expected
              and r["same_contract"] and not r["promoted"] and not r["new_discovery_implemented"], "PROMOTION")
    _need([r["field"] for r in a["fields"]] == FIELDS, "FIELD_MATRIX")
    for r in a["fields"]:
        _need(set(r) == {"field","requirement","source","existing_availability","pit_requirement",
                        "freshness_requirement","identity_fingerprint_role","consumer_use","missing_dependency","readiness"}
              and all(r.values()), "FIELD_GAP")
    i = a["identity"]
    _need(i["key_fields"] == ["contract_id","contract_version","canonical_security_id","inspection_as_of","inspection_context"]
          and i["inspection_context_fields"] == ["purpose","temporal_requirement","canonical_horizon","horizon_authority_reference"]
          and i["separate_identity_content"] and i["horizon_default"] is None
          and i["horizon_authority_default"] is None, "KEY_OR_DEFAULT")
    _need(set(i["context_temporal_vocabulary"]) == {"STRICT_PIT","CURRENT_DESCRIPTIVE"}, "PIT")
    _need(a["replay"]["immutable_history"] and not a["replay"]["automatic_successor"]
          and not a["replay"]["diagnosis_per_origin"] and not a["replay"]["union_in_logical_key"]
          and not a["replay"]["later_evidence_retroactive"]
          and a["replay"]["later_origin"].startswith("NEXT_EXPLICIT_INSPECTION_CUTOFF_ONLY"), "REPLAY")
    _need(a["temporal"]["no_time_defaults"] and a["temporal"]["no_duration_or_window_selected"], "TIME")
    _need(a["freshness"]["shared_ttl"] is None and a["freshness"]["shared_threshold"] is None
          and not a["freshness"]["source_defined_is_fresh_proof"], "FRESHNESS")
    _need(set(a["context"]["forbidden_marketwide_origins"]) == CONTEXTUAL
          and a["context"]["all_origins_preserved"] and not a["context"]["auto_filter_invalid_origins"]
          and not a["context"]["context_only_may_admit"] and not a["context"]["portfolio_lookup"], "CONTEXT")
    _need(a["consumer"]["state"] == "CONSUMER_BINDING_NOT_READY"
          and a["consumer"]["binding_reference"] is None and not a["consumer"]["persistence_created"], "CONSUMER")
    _need(set(a["consumer"]["ready_does_not_imply"]) == {
        "DIAGNOSIS_SUCCESS","DECISION_SCORE_AVAILABLE","SETUP_EXISTS","GATE_PASS",
        "PORTFOLIO_AUTHORIZATION","EXECUTION_AUTHORIZATION"
    }, "DOWNSTREAM_AUTHORITY")
    _need(not a["radar"]["direct_reuse"] and a["radar"]["wrapper_required"] and not a["radar"]["modified"], "RADAR")
    b = a["authority_boundary"]
    _need(b["statements"] == ["DISCOVERY_AUTHORITY != BRAIN_DECISION_AUTHORITY",
                             "BRAIN_INSPECTION_REQUEST != EXECUTION_AUTHORIZATION"]
          and b["actionability"] == "WATCH_ONLY" and b["execution_status"] == "NON_EXECUTABLE"
          and not any(v for v in b.values() if isinstance(v,bool)), "AUTHORITY")
    _need(not any(a["runtime"].values()), "RUNTIME")
    _need(not a["correlation"]["private_rules_exposed"] and not a["correlation"]["result_storage_created"]
          and not a["api_ui"]["modified"] and not a["api_ui"]["full_private61_inventory"], "API")
    _need(a["scheduler"]["cadence"] is None and a["scheduler"]["retry_policy"] is None
          and not a["scheduler"]["queue_created"] and not a["scheduler"]["automatic_reinspection"], "SCHEDULER")
    _need(a["pending_gate1"]["continuation"] == NEXT and a["pending_gate1"]["state"] == "PENDING_NOT_STARTED"
          and not a["pending_gate1"]["closed"] and a["pending_gate1"]["disposition"] == "IMMEDIATELY_AFTER_THIS_CONTRACT"
          and a["pending_gate1"]["predecessor_decision"] == p["pending_gate1"]["predecessor_decision"], "CAS")
    _need(a["next_continuations"] == [NEXT] and not a["next_continuation_started"], "NEXT")
    _need(a["contract_fingerprint"] == content_fingerprint({k:v for k,v in a.items() if k!="contract_fingerprint"}), "TAMPERED")


def _context():
    return dict(purpose="MARKET_WIDE_DISCOVERY_REVIEW", temporal_requirement="STRICT_PIT",
                canonical_horizon=None, horizon_authority_reference=None)


def _key(security, cutoff, context):
    # Test vector for the documented K formula; deliberately no union/origins.
    if re.fullmatch(r"NSE:[A-Z]{2}[A-Z0-9]{9}[0-9]", security) is None:
        raise ValueError("IDENTITY_INVALID")
    if cutoff.tzinfo is None or cutoff.utcoffset() is None:
        raise ValueError("PIT_INVALID")
    if (context["canonical_horizon"] is None) != (context["horizon_authority_reference"] is None):
        raise ValueError("HORIZON_AUTHORITY_MISMATCH")
    value = dict(contract_id=CID,contract_version="v1",canonical_security_id=security,
                 inspection_as_of=cutoff,inspection_context=context)
    return "brain-inspection-request:" + content_fingerprint(value).removeprefix("sha256:")


def _candidate(*leads):
    by_funnel={}
    for lead in leads:
        by_funnel.setdefault(lead.funnel_id, []).append(lead)
    union=fixture.union_discovery_candidates(as_of=T, adapter_results=tuple(
        fixture._adapter(f,tuple(values)) for f,values in by_funnel.items()))
    return union,union.candidates[0]


def _snapshot_vector(union,candidate,cutoff=T,context=None):
    # Only a fingerprint test vector; lacks mandatory native proof enrichment
    # and is NOT a complete/dispatchable request instance.
    context=context or _context()
    return dict(inspection_request_id=_key(candidate.canonical_instrument_id,cutoff,context),
                source_union_id=union.batch_id,source_union_fingerprint=union.fingerprint,
                source_candidate_id=candidate.candidate_id,source_candidate_fingerprint=candidate.fingerprint,
                inspection_as_of=cutoff,inspection_context=context,
                origins=tuple(discovery_lead_payload(o.lead) for o in candidate.origins),
                consumer_binding_state="CONSUMER_BINDING_NOT_READY", submission_state="NOT_SUBMITTED")


def _temporal_witness(lead,cutoff,identity,membership):
    # Necessary native identity/membership conditions, NOT full admission.
    lead.verify()
    if identity.canonical_instrument_id != lead.canonical_instrument_id or identity.isin != lead.canonical_instrument_id[4:]:
        return "IDENTITY_UNRESOLVED"
    if membership.instrument_id != lead.canonical_instrument_id:
        return "IDENTITY_UNRESOLVED"
    if lead.discovery_as_of > cutoff or any(r.known_at > lead.discovery_as_of or r.known_at > cutoff for r in lead.lineage):
        return "PIT_INVALID"
    for t in (lead.discovery_as_of,cutoff):
        if not identity.eligible_as_of(t) or BacktestLookaheadGuard().membership(membership,t).value != "ELIGIBLE":
            return "PIT_INVALID"
    return "NECESSARY_NATIVE_PIT_CONDITIONS_MET_NOT_ADMISSION"


def _native_identity_membership():
    identity=HistoricalSecurityIdentity("identity:test","NSE:INE000A01001","INE000A01001","NSE","SYNTHETIC","EQ",
        T-timedelta(days=2),None,None,None,T-timedelta(days=1),None,HistoricalSecurityStatus.ACTIVE,
        "SYNTHETIC_OFFICIAL_FIXTURE",T-timedelta(days=1),"v1","source:test",source_fingerprint="sha256:"+"1"*64)
    member=UniverseMembership("member:test",identity.canonical_instrument_id,"universe:test",
        T-timedelta(days=1),None,T-timedelta(days=1),"SYNTHETIC_OFFICIAL_FIXTURE","source:test",InstrumentLifecycle.ACTIVE)
    return identity,member


def test_complete_contract_and_native_predecessor_preserved():
    _verify(_read())
    previous._verify(previous._read())
    assert _read()["contract_fingerprint"] == FP


@pytest.mark.parametrize("path,fp",sorted(_read()["inspected_file_fingerprints_lf"].items()))
def test_frozen_source_matches_baseline_and_worktree(path,fp):
    current=(ROOT/path).read_bytes().replace(b"\r\n",b"\n")
    accepted=subprocess.check_output(["git","show",BASELINE+":"+path],cwd=ROOT).replace(b"\r\n",b"\n")
    assert current==accepted
    assert "sha256:"+sha256(current).hexdigest()==fp


@pytest.mark.parametrize("ref",[_read()["parent"]]+_read()["predecessors"])
def test_native_ancestor_fingerprint(ref):
    a=json.loads((ROOT/ref["path"]).read_text(encoding="utf-8"))
    assert a[ref["field"]]==ref["fingerprint"]
    assert content_fingerprint({k:v for k,v in a.items() if k!=ref["field"]})==ref["fingerprint"]


@pytest.mark.parametrize("field",FIELDS)
def test_field_mapping_is_complete_and_no_unavailable_value_is_ready(field):
    row=next(r for r in _read()["fields"] if r["field"]==field)
    assert row["pit_requirement"] and row["consumer_use"] and row["missing_dependency"]
    if row["existing_availability"] in {"MISSING","REQUIRES_POLICY","REQUIRES_IMPLEMENTATION"}:
        assert row["readiness"]!="READY"


@pytest.mark.parametrize("funnel",list(F))
def test_exact_fourteen_family_compatibility_without_promotion(funnel):
    _verify(_read())
    row=next(r for r in _read()["funnel_compatibility"] if r["funnel_id"]==funnel.value)
    assert row["same_contract"] and not row["new_discovery_implemented"] and not row["promoted"]


def test_one_security_multiple_origins_one_key_with_lossless_provenance():
    one=fixture._lead()
    two=fixture._lead(funnel=F.SECTOR_ROTATION,source="receipt:two")
    u1,c1=_candidate(one)
    u2,c2=_candidate(two,one)
    before=canonical_json(asdict(c1))
    a,b=_snapshot_vector(u1,c1),_snapshot_vector(u2,c2)
    assert a["inspection_request_id"]==b["inspection_request_id"]
    assert len({a["inspection_request_id"],b["inspection_request_id"]})==1
    assert len(c2.origins)==2
    assert {r["lead_id"] for r in b["origins"]}=={one.lead_id,two.lead_id}
    assert content_fingerprint(a)!=content_fingerprint(b)
    assert canonical_json(asdict(c1))==before
    assert "DUPLICATE_REQUEST_AMBIGUOUS" in _read()["replay"]["same_key_different_fingerprint"]


def test_idempotent_replay_and_input_order_do_not_change_key_or_content():
    one,two=fixture._lead(),fixture._lead(funnel=F.SECTOR_ROTATION,source="receipt:two")
    a=_snapshot_vector(*_candidate(one,two))
    first=fixture._adapter(F.PRE_BREAKOUT,(one,))
    replay=fixture.union_discovery_candidates(as_of=T,adapter_results=(
        first,fixture._adapter(F.SECTOR_ROTATION,(two,)),first))
    b=_snapshot_vector(replay,replay.candidates[0])
    assert a["inspection_request_id"]==b["inspection_request_id"]
    # Raw replay changes union coverage/fingerprint, so is NOT identical content.
    assert content_fingerprint(a)!=content_fingerprint(b)
    c=_snapshot_vector(*_candidate(two,one))
    assert canonical_json(a)==canonical_json(c)
    assert "IDEMPOTENT_REPLAY" in _read()["replay"]["same_key_same_fingerprint"]


def test_equivalent_aware_times_and_stable_serialization():
    union,candidate=_candidate(fixture._lead())
    a=_snapshot_vector(union,candidate)
    b=_snapshot_vector(union,candidate,cutoff=T.astimezone(timezone(timedelta(hours=5,minutes=30))))
    assert canonical_json(a)==canonical_json(b)
    assert content_fingerprint(a)==content_fingerprint(json.loads(canonical_json(a)))
    assert content_fingerprint(a)==content_fingerprint(dict(reversed(list(a.items()))))


@pytest.mark.parametrize("identity",["", "APARINDS", "NSE:INVALID", "BSE:INE000A01001"])
def test_noncanonical_security_cannot_get_request_key(identity):
    with pytest.raises(ValueError,match="IDENTITY_INVALID"):
        _key(identity,T,_context())


def test_no_horizon_or_runtime_timestamp_defaults():
    with pytest.raises(ValueError,match="PIT_INVALID"):
        _key("NSE:INE000A01001",T.replace(tzinfo=None),_context())
    c=_context()
    c["canonical_horizon"]="POSITIONAL"
    with pytest.raises(ValueError,match="HORIZON_AUTHORITY_MISMATCH"):
        _key("NSE:INE000A01001",T,c)
    assert _read()["identity"]["horizon_default"] is None


def test_later_cutoff_not_new_hit_defines_new_request():
    union,candidate=_candidate(fixture._lead())
    a=_snapshot_vector(union,candidate)
    b=_snapshot_vector(union,candidate,cutoff=T+timedelta(seconds=1))
    assert a["inspection_request_id"]!=b["inspection_request_id"]
    assert not _read()["replay"]["automatic_successor"]
    assert _read()["replay"]["later_origin"].startswith("NEXT_EXPLICIT_INSPECTION_CUTOFF_ONLY")


def test_native_identity_and_membership_cutoffs_inclusive_and_not_current_backcast():
    identity,member=_native_identity_membership()
    lead=fixture._lead()
    assert _temporal_witness(lead,T,identity,member).startswith("NECESSARY_NATIVE")
    assert _temporal_witness(lead,T,identity,replace(member,effective_to=T)).startswith("NECESSARY_NATIVE")
    assert _temporal_witness(lead,T,replace(identity,symbol_effective_to=T),member).startswith("NECESSARY_NATIVE")
    for bad in (replace(member,known_at=T+timedelta(seconds=1)),
                replace(member,effective_from=T+timedelta(seconds=1)),
                replace(member,effective_to=T-timedelta(seconds=1))):
        assert _temporal_witness(lead,T,identity,bad)=="PIT_INVALID"
    assert _temporal_witness(lead,T,identity,replace(member,instrument_id="NSE:INE000A01002"))=="IDENTITY_UNRESOLVED"


def test_union_visible_membership_does_not_prove_earlier_origin_membership():
    identity,member=_native_identity_membership()
    earlier=fixture._lead(as_of=T-timedelta(hours=1))
    assert _temporal_witness(earlier,T,identity,replace(member,known_at=T))=="PIT_INVALID"


def test_future_origin_and_tampered_lineage_fail_closed():
    identity,member=_native_identity_membership()
    future=fixture._lead(as_of=T+timedelta(seconds=1))
    assert _temporal_witness(future,T,identity,member)=="PIT_INVALID"
    bad=fixture._lead()
    object.__setattr__(bad,"fingerprint","0"*64)
    with pytest.raises(ValueError):
        _temporal_witness(bad,T,identity,member)


@pytest.mark.parametrize("reason,state",[
    ("PROVENANCE_MISSING","INSUFFICIENT_PROVENANCE"),("PRODUCER_VERSION_MISSING","INSUFFICIENT_PROVENANCE"),
    ("FRESHNESS_UNAVAILABLE","INSUFFICIENT_PROVENANCE"),("NO_VALID_ORIGIN","INSUFFICIENT_PROVENANCE"),
    ("STALE_REQUIRED_TRIGGER","STALE_TRIGGER"),("FUTURE_EVIDENCE","PIT_INVALID"),
    ("HISTORICAL_PIT_NOT_PROVEN","PIT_INVALID"),("UNIVERSE_MEMBERSHIP_MISSING","IDENTITY_UNRESOLVED"),
    ("UNSUPPORTED_CONTEXTUAL_ORIGIN","UNSUPPORTED_SCOPE"),("SOURCE_FINGERPRINT_INVALID","BLOCKED"),
])
def test_explicit_failure_contract_without_invented_proof(reason,state):
    row=next(r for r in _read()["failures"] if r["reason_code"]==reason)
    assert row["state"]==state and row["condition"]


def test_no_current_descriptive_upgrade_and_no_consumer_registration():
    a=_read()
    assert a["consumer"]["binding_reference"] is None
    assert a["consumer"]["state"]=="CONSUMER_BINDING_NOT_READY"
    assert not a["radar"]["direct_reuse"] and a["radar"]["wrapper_required"]
    source=(ROOT/a["radar"]["module"]).read_text(encoding="utf-8")
    assert "StrictHistoricalPitTechnicalState.NOT_READY" in source
    assert "current = unique.get(lead.lead_id)" in source
    assert "self._runner.run(evidence)" in source
    assert not a["runtime"]["runner_invoked"]


def test_discovery_and_handoff_do_not_mutate_score_or_authorize_downstream():
    a=_read()
    assert a["authority_boundary"]["actionability"]=="WATCH_ONLY"
    assert a["authority_boundary"]["execution_status"]=="NON_EXECUTABLE"
    assert not any(v for v in a["authority_boundary"].values() if isinstance(v,bool))
    assert not any(a["runtime"].values())
    assert len(a["consumer"]["ready_does_not_imply"])==6
    for key in ("score_fields","hit_bonus","confidence_from_rank","trigger_count_weight","price_fields","position_size_fields"):
        assert a["authority_boundary"][key] is False


def _failure_state_vector(reason_codes):
    # Synthetic truth-table projection of the definition, NOT a source verifier.
    # An empty vector is not evidence that a real candidate satisfied admission.
    a=_read()
    by_reason={r["reason_code"]:r["state"] for r in a["failures"]}
    states={by_reason[reason] for reason in reason_codes}
    candidate=next((state for state in a["failure_order"] if state in states),"READY_FOR_BRAIN_INSPECTION")
    return candidate,tuple(sorted(set(reason_codes))),a["consumer"]["state"],"NOT_SUBMITTED"


@pytest.mark.parametrize("reasons,expected",[
    (("PROVENANCE_MISSING",),"INSUFFICIENT_PROVENANCE"),
    (("PRODUCER_VERSION_MISSING",),"INSUFFICIENT_PROVENANCE"),
    (("STALE_REQUIRED_TRIGGER",),"STALE_TRIGGER"),
    (("FRESHNESS_UNAVAILABLE","STALE_REQUIRED_TRIGGER"),"INSUFFICIENT_PROVENANCE"),
    (("FUTURE_EVIDENCE","PROVENANCE_MISSING"),"PIT_INVALID"),
    (("SOURCE_FINGERPRINT_INVALID","FUTURE_EVIDENCE"),"BLOCKED"),
    (("DUPLICATE_REQUEST_AMBIGUOUS",),"BLOCKED"),
    (("UNSUPPORTED_CONTEXTUAL_ORIGIN",),"UNSUPPORTED_SCOPE"),
    (("NO_VALID_ORIGIN","RESEARCH_NOT_PROMOTED"),"INSUFFICIENT_PROVENANCE"),
    (("UNIVERSE_MEMBERSHIP_MISSING",),"IDENTITY_UNRESOLVED"),
    (("HISTORICAL_PIT_NOT_PROVEN",),"PIT_INVALID"),
    ((),"READY_FOR_BRAIN_INSPECTION"),
])
def test_failure_precedence_preserves_all_reasons_and_never_submits(reasons,expected):
    value=_failure_state_vector(reasons)
    assert value==_failure_state_vector(tuple(reversed(reasons)))
    assert value==(expected,tuple(sorted(set(reasons))),"CONSUMER_BINDING_NOT_READY","NOT_SUBMITTED")


@pytest.mark.parametrize("contextual",sorted(CONTEXTUAL))
def test_valid_origin_cannot_hide_unsupported_contextual_origin(contextual):
    rows={r["funnel_id"]:r for r in _read()["funnel_compatibility"]}
    origins=(rows["PRE_BREAKOUT"],rows[contextual])
    assert any(r["current_admission"]=="CONDITIONAL_SOURCE_PROOF_REQUIRED" for r in origins)
    reasons=tuple("UNSUPPORTED_CONTEXTUAL_ORIGIN" for r in origins
                  if r["current_admission"]=="UNSUPPORTED_AS_MARKETWIDE_ORIGIN")
    assert _failure_state_vector(reasons)[0]=="UNSUPPORTED_SCOPE"
    assert len(origins)==2  # neither origin was silently pruned


MUTATIONS=[
    (("identity","key_fields"),["canonical_security_id","origin_count"]),
    (("identity","horizon_default"),"POSITIONAL"),
    (("context","context_only_may_admit"),True),
    (("context","auto_filter_invalid_origins"),True),
    (("context","all_origins_preserved"),False),
    (("funnel_compatibility",0,"promoted"),True),
    (("freshness","shared_ttl"),3600),
    (("freshness","source_defined_is_fresh_proof"),True),
    (("replay","immutable_history"),False),
    (("replay","diagnosis_per_origin"),True),
    (("replay","later_evidence_retroactive"),True),
    (("consumer","state"),"READY"),
    (("consumer","binding_reference"),"fake:consumer"),
    (("consumer","ready_does_not_imply"),[]),
    (("authority_boundary","hit_bonus"),True),
    (("authority_boundary","gate_bypass"),True),
    (("authority_boundary","second_brain"),True),
    (("authority","v1","status"),"NOT_ACTIVE"),
    (("authority","v2","status"),"ACTIVE"),
    (("runtime","application_files_changed"),True),
    (("runtime","production_db_read"),True),
    (("runtime","portfolio_accessed"),True),
    (("runtime","broker_order_call"),True),
    (("api_ui","full_private61_inventory"),True),
    (("scheduler","cadence"),"hourly"),
    (("pending_gate1","closed"),True),
    (("next_continuations",),[NEXT,"ANOTHER_SLICE"]),
    (("next_continuation_started",),True),
]


@pytest.mark.parametrize("path,value",MUTATIONS)
def test_resealed_semantic_or_authority_changes_rejected(path,value):
    a=deepcopy(_read())
    current=a
    for key in path[:-1]:
        current=current[key]
    current[path[-1]]=value
    a["contract_fingerprint"]=content_fingerprint({k:v for k,v in a.items() if k!="contract_fingerprint"})
    with pytest.raises(ValueError):
        _verify(a)


def test_no_production_caller_or_concrete_radar_port_added():
    for directory in ("app/api","app/runtime","scripts","tools"):
        for p in (ROOT/directory).rglob("*.py"):
            calls=previous._calls(ast.parse(p.read_text(encoding="utf-8-sig")))
            assert not calls & {"orchestrate_whole_market_discovery","RadarToHsiDiagnosticOrchestrator"}
    ports=[p.relative_to(ROOT).as_posix() for p in (ROOT/"app").rglob("*.py")
           if "def assemble_for_radar(" in p.read_text(encoding="utf-8-sig")]
    assert ports==["app/intelligence/radar_diagnostic_orchestration.py"]


def test_markdown_links_tables_and_readme():
    p=ROOT/"docs/architecture"/(STEM+".md")
    text=p.read_text(encoding="utf-8")
    for target in re.findall(r"\[[^\]]+\]\(([^)]+)\)",text):
        if "://" not in target and not target.startswith("#"):
            assert (p.parent/target.split("#")[0]).resolve().is_file(),target
    assert STEM+".md" in (ROOT/"README.md").read_text(encoding="utf-8")
    widths=[]
    for line in text.splitlines()+[""]:
        assert line.rstrip()==line
        if line.startswith("|"):
            widths.append(line.count("|"))
        elif widths:
            assert len(set(widths))==1
            widths=[]
