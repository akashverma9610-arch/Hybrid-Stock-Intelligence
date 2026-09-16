"""Offline repository reconciliation witnesses; no production runtime integration.

These checks pin the accepted graph rather than instantiate stores, providers,
portfolio services, schedulers or downstream production materializers.
"""
import ast
from copy import deepcopy
from dataclasses import asdict
from hashlib import sha256
import json
from pathlib import Path
import re
import subprocess

import pytest

from app.fundamentals.diagnostic_comparability import canonical_json, content_fingerprint
from app.intelligence.multi_funnel_discovery import (
    DiscoveryFunnelId as F, multi_funnel_discovery_registry,
)
from tests.unit import test_multi_funnel_candidate_union as union_fixture
from tests.unit import test_multi_funnel_orchestration as orchestration_fixture

ROOT = Path(__file__).resolve().parents[2]
BASELINE = "f3dbb065017c1577d1dffdd0c1a3901b561f6ff9"
STEM = "HSI_BRAIN_FUNNEL_RUNTIME_RECONCILIATION_AUDIT_V1"
PATH = ROOT / "docs/architecture" / (STEM + ".json")
PARENT = ROOT / "docs/architecture/GATE1_ROTATION_RESEARCH_SESSION_PRICE_SOURCE_APPLICABILITY_AUDIT_V1.json"
FP = "sha256:224297fc6ce7bc1b7a5bf412446b69c3f71e85e9608f7906eb6fb58ea65a83ab"
NEXT = "CANONICAL_DISCOVERY_UNION_TO_BRAIN_HANDOFF_CONTRACT_V1"
CLASSES = {
    "ALREADY_IN_BRAIN_ADAPTER_REQUIRED", "RESEARCH_BUILT_PROMOTION_REQUIRED",
    "ACTUALLY_MISSING_INTELLIGENCE", "CONTEXTUAL_ONLY",
}
BINDINGS = {
    "PRE_BREAKOUT", "SECTOR_ROTATION", "FUNDAMENTAL_INFLECTION",
    "COMPOUNDER", "POLICY_TRANSMISSION",
}
STAGES = {
    "EVIDENCE_ASSEMBLY", "CANONICAL_61", "RESEARCH_COMPARABILITY", "DECISION_SCORE",
    "DECISION_TRUST_ENVELOPE", "SETUP_PREPARATION", "SIX_GATES", "PORTFOLIO_ROTATION",
    "WATCH_SIGNAL", "HSI_SIGNAL", "SELL_SIDE",
}
SCOPES = {
    "WHOLE_ELIGIBLE_NSE_UNIVERSE", "BOUNDED_MARKET_UNIVERSE", "PORTFOLIO_CONTEXT_ONLY",
    "WATCHLIST_CONTEXT_ONLY", "EVENT_CONTEXT_ONLY", "OTHER_GOVERNED_SCOPE",
}
EDGES = {"OPERATIONAL", "IMPLEMENTED_NOT_WIRED", "SHADOW", "MISSING", "NOT_APPLICABLE"}
TRANSITIONS = {
    "WIRED_AND_OPERATIONAL", "IMPLEMENTED_NOT_WIRED", "SHADOW_ONLY",
    "ADAPTER_MISSING", "NOT_IMPLEMENTED", "CONTEXT_SPECIFIC",
}


def _read():
    return json.loads(PATH.read_text(encoding="utf-8"))


def _need(value, reason):
    if not value:
        raise ValueError(reason)


def _verify(a):
    parent = json.loads(PARENT.read_text(encoding="utf-8"))
    _need((a["slice"], a["baseline_commit"], a["version"]) == (STEM, BASELINE, "v1"), "IDENTITY")
    _need((a["decision"], a["semantic_decision"], a["slice_status"]) == (
        "B", "BRAIN_CAPABILITIES_EXIST_RUNTIME_WIRING_INCOMPLETE", "ACCEPTED/CLOSED"
    ), "DECISION")
    _need(a["status"] == "REPOSITORY_RECONCILIATION_AUDIT / NO_RUNTIME_INTEGRATION / NOT_ACTIVE", "STATUS")
    for key in ("authority", "bootstrap_policy_status", "effective_parameters", "preservation", "registration"):
        _need(a[key] == parent[key], "PREDECESSOR")
    _need(a["parent"]["fingerprint"] == parent["artifact_fingerprint"], "PARENT")
    _need(a["predecessors"] == parent["predecessors"] + [parent["parent"]], "ANCESTRY")
    _need(not any(a["runtime"].values()) and not any(a["safety"][k] for k in (
        "second_brain_authorized", "duplicate_final_scoring_found", "discovery_is_final_authority",
        "discovery_can_bypass_61", "discovery_can_bypass_score", "discovery_can_bypass_setup",
        "discovery_can_bypass_six_gates", "automatic_trading",
    )), "AUTHORITY_BOUNDARY")
    registry = json.loads(json.dumps(asdict(multi_funnel_discovery_registry())))
    _need(a["canonical_registry"] == registry, "REGISTRY")
    rows = a["matrix"]
    _need([r["funnel_id"] for r in rows] == [e["funnel_id"] for e in registry["entries"]]
          and len(rows) == 14, "FUNNEL_COVERAGE")
    for row, entry in zip(rows, registry["entries"]):
        _need(row["registry_entry"] == entry and row["primary_classification"] in CLASSES, "CLASSIFICATION")
        _need(row["intended_universe"] in SCOPES and row["scope_basis"], "SCOPE")
        _need(row["adapter_exists"] == (row["funnel_id"] in BINDINGS), "ADAPTER")
        _need(not any(row[k] for k in (
            "runtime_scanner_exists", "brain_inspection_invoked", "diagnosis_61_invoked",
            "decision_score_invoked", "setup_invoked", "six_gates_invoked",
        )), "INVOCATION_OVERCLAIM")
        _need(row["frontend_projection"] == "NOT_WIRED"
              and row["portfolio_signal_output"] == "NOT_WIRED_FROM_DISCOVERY_UNION", "PROJECTION")
        _need(row["source_blockers"] and row["wiring_blockers"] and row["provider_dependencies"], "BLOCKERS")
        _need(row["provenance_fields"] and row["duplication_risk"] and row["exact_missing_edges"], "PROVENANCE")
    c = a["candidate_contract"]
    _need(c["actual_status"] == "CANDIDATE_FOR_SHARED_BRAIN_INSPECTION"
          and c["consumer_status"] == "NO_RUNTIME_CONSUMER" and not c["persisted"]
          and not c["ranking"] and c["all_origins_preserved"] and c["trigger_evidence_preserved"], "UNION")
    _need(not a["scope"]["all_14_unconditional_whole_nse"]
          and not a["scope"]["automatic_context_expansion"]
          and not a["scope"]["source_observation_count_is_universe_coverage"], "SCOPE")
    _need({r["stage"] for r in a["downstream"]} == STAGES
          and all(r["status"] in TRANSITIONS and not r["invoked_by_multi_funnel_runner"] for r in a["downstream"]), "DOWNSTREAM")
    _need(a["radar_reuse"]["dedup_key"] == "lead_id"
          and not a["radar_reuse"]["runtime_bound"] and not a["radar_reuse"]["full_brain_claim"], "RADAR")
    _need(not a["score"]["all61_equal_weight"] and not a["score"]["unavailable_is_zero"]
          and not a["score"]["funnel_identity_input"] and not a["score"]["multiple_hit_bonus"], "SCORE")
    _need(a["setup"]["T2"] is None and a["setup"]["extended_target"] is None
          and a["setup"]["time_horizon"] == "NOT_GOVERNED_FOR_SETUP_OPPORTUNITY", "SETUP")
    _need({r["status"] for r in a["frontend"]} == {
        "PARTIAL_PROJECTION", "CANONICAL_PROJECTION", "LEGACY_PROJECTION", "NOT_WIRED"
    } and all(r["lineage_status"] in {"PROVENANCE_MISSING", "NOT_WIRED"} for r in a["frontend"]), "FRONTEND")
    _need(len(a["scheduler"]) == 5 and a["scheduler"][0]["status"] == "NOT_IMPLEMENTED", "SCHEDULER")
    _need(set(a["frontend_field_coverage"]) == {
        "source_funnels", "candidate_union_provenance", "diagnosis_61", "decision_score",
        "setup", "six_gates", "state_reason", "freshness",
    } and a["frontend_field_coverage"]["diagnosis_61"].startswith("AVAILABILITY_SUMMARY_ONLY"), "FRONTEND_FIELDS")
    _need(all(r["state"] in EDGES for r in a["graph"]["actual_edges"])
          and not a["graph"]["duplicate_decision_system_found"], "GRAPH")
    _need(set(a["lists"]["missing_intelligence"]) == {"EMERGING_COMPOUNDER", "VALUATION_RECOVERY"}
          and set(a["lists"]["research_promotion"]) == {"COMPOUNDER", "FUNDAMENTAL_INFLECTION", "POLICY_TRANSMISSION"}
          and set(a["lists"]["contextual_only"]) == {"HOLDING_STATE_CHANGE", "WATCHLIST_STATE_CHANGE", "MARKET_DISLOCATION"}, "GAPS")
    _need(a["pending_gate1"]["continuation"] == parent["next_continuations"][0]
          and a["pending_gate1"]["predecessor_decision"] == parent["semantic_decision"]
          and not a["pending_gate1"]["closed"]
          and a["pending_gate1"]["state"] == "PENDING_NOT_STARTED", "CAS")
    _need(a["next_continuations"] == [NEXT] and not a["next_continuation_started"], "NEXT")
    _need(a["artifact_fingerprint"] == content_fingerprint({
        k: v for k, v in a.items() if k != "artifact_fingerprint"
    }), "CONTENT_TAMPERED")


def _source(path):
    return (ROOT / path).read_text(encoding="utf-8-sig")


def _node(path, name):
    tree = ast.parse(_source(path))
    return next(n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.ClassDef)) and n.name == name)


def _calls(node):
    return {n.func.id if isinstance(n.func, ast.Name) else n.func.attr
            for n in ast.walk(node) if isinstance(n, ast.Call) and isinstance(n.func, (ast.Name, ast.Attribute))}


def test_complete_artifact_and_stable_content_fingerprint():
    a = _read()
    _verify(a)
    assert a["artifact_fingerprint"] == FP
    b = json.loads(canonical_json(a))
    _verify(b)
    assert content_fingerprint(a) == content_fingerprint(dict(reversed(list(a.items()))))


@pytest.mark.parametrize("path,expected", sorted(_read()["inspected_file_fingerprints_lf"].items()))
def test_source_pin_matches_current_and_accepted_baseline(path, expected):
    current = (ROOT / path).read_bytes().replace(b"\r\n", b"\n")
    accepted = subprocess.run(
        ["git", "show", BASELINE + ":" + path], cwd=ROOT, check=True, capture_output=True
    ).stdout.replace(b"\r\n", b"\n")
    assert "sha256:" + sha256(accepted).hexdigest() == expected
    if path in {"app/api/main.py", "app/api/dependencies.py"}:
        from tests.unit.test_catalyst_event_operational_closure import expected_catalyst_binding_source
        accepted = expected_catalyst_binding_source(path, accepted)
    assert current == accepted


@pytest.mark.parametrize("p", [_read()["parent"]] + _read()["predecessors"])
def test_predecessor_native_fingerprint_and_full_payload_unchanged(p):
    value = json.loads((ROOT / p["path"]).read_text(encoding="utf-8"))
    assert value[p["field"]] == p["fingerprint"]
    assert p["fingerprint"] == content_fingerprint({k: v for k, v in value.items() if k != p["field"]})


@pytest.mark.parametrize("funnel", list(F))
def test_exact_per_funnel_scope_classification_and_boundaries(funnel):
    a = _read()
    _verify(a)
    row = next(r for r in a["matrix"] if r["funnel_id"] == funnel)
    assert row["registry_entry"] == json.loads(json.dumps(asdict(multi_funnel_discovery_registry().get(funnel))))
    assert row["primary_classification"] in CLASSES
    assert (ROOT / row["brain_module"]).is_file()
    assert (ROOT / row["documentation_source"]).is_file()
    if row["registry_entry"]["status"] == "PARTIAL":
        assert row["primary_classification"] != "ACTUALLY_MISSING_INTELLIGENCE"
    if row["registry_entry"]["status"] == "RESEARCH_SHADOW":
        assert row["primary_classification"] == "RESEARCH_BUILT_PROMOTION_REQUIRED"


MUTATIONS = [
    (("matrix", 0, "brain_inspection_invoked"), True),
    (("matrix", 0, "diagnosis_61_invoked"), True),
    (("matrix", 0, "decision_score_invoked"), True),
    (("matrix", 0, "setup_invoked"), True),
    (("matrix", 0, "six_gates_invoked"), True),
    (("matrix", 0, "runtime_scanner_exists"), True),
    (("matrix", 0, "primary_classification"), "UNCLASSIFIED"),
    (("matrix", 0, "source_blockers"), []),
    (("matrix", 0, "wiring_blockers"), []),
    (("matrix", 0, "frontend_projection"), "CANONICAL_PROJECTION"),
    (("candidate_contract", "consumer_status"), "OPERATIONAL"),
    (("candidate_contract", "persisted"), True),
    (("candidate_contract", "all_origins_preserved"), False),
    (("candidate_contract", "ranking"), True),
    (("scope", "all_14_unconditional_whole_nse"), True),
    (("scope", "automatic_context_expansion"), True),
    (("radar_reuse", "dedup_key"), "canonical_instrument_id"),
    (("score", "all61_equal_weight"), True),
    (("score", "unavailable_is_zero"), True),
    (("score", "multiple_hit_bonus"), True),
    (("setup", "T2"), "FABRICATED"),
    (("authority", "v1", "status"), "NOT_ACTIVE"),
    (("authority", "v2", "status"), "ACTIVE"),
    (("runtime", "production_db_read"), True),
    (("runtime", "portfolio_accessed"), True),
    (("runtime", "broker_order_access"), True),
    (("runtime", "funnel_promoted"), True),
    (("safety", "second_brain_authorized"), True),
    (("pending_gate1", "closed"), True),
    (("next_continuations",), [NEXT, "UNAUTHORIZED_NEXT"]),
    (("next_continuation_started",), True),
]


@pytest.mark.parametrize("path,value", MUTATIONS)
def test_resealed_overclaims_and_authority_mutations_rejected(path, value):
    a = deepcopy(_read())
    target = a
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    a["artifact_fingerprint"] = content_fingerprint({k: v for k, v in a.items() if k != "artifact_fingerprint"})
    with pytest.raises(ValueError):
        _verify(a)


def test_registry_omission_and_duplicate_rejected():
    for rows in (_read()["matrix"][:-1], _read()["matrix"] + [_read()["matrix"][0]]):
        a = _read()
        a["matrix"] = rows
        with pytest.raises(ValueError, match="FUNNEL_COVERAGE"):
            _verify(a)


def test_actual_runner_stops_at_batch_and_not_deep_computation():
    n = _node("app/intelligence/multi_funnel_orchestration.py", "orchestrate_whole_market_discovery")
    calls = _calls(n)
    assert {"read_sources", "WholeMarketDiscoveryBatch", "unavailable_adapter"} <= calls
    assert not calls & {
        "run", "run_next_batch", "assemble", "assemble_for_radar", "build_scorecard", "analyze_stock",
        "evaluate", "assess_prebreakout_setup", "project_watch_to_hsi_signal", "save", "commit",
    }
    assert isinstance(n.body[-1], ast.Return)
    assert isinstance(n.body[-1].value.func, ast.Name)
    assert n.body[-1].value.func.id == "WholeMarketDiscoveryBatch"
    batch = _node("app/intelligence/multi_funnel_orchestration.py", "WholeMarketDiscoveryBatch")
    assert "union_discovery_candidates" in _calls(batch)


def test_isolated_batch_reads_only_five_bindings_and_never_invokes_brain(monkeypatch):
    import app.universe_analysis.service as service
    from app.intelligence.shared_brain_application import SharedBrainApplicationService
    from app.gates.engine import ExecutionGateEngine
    from app.strategies.pre_breakout.setup_assessment import GovernedPreBreakoutSetupAssessmentService
    source = orchestration_fixture._sector_run()
    def forbidden(*args, **kwargs):
        pytest.fail("Discovery must not invoke a downstream computation")
    monkeypatch.setattr(service.Canonical61DiagnosticRunner, "run", forbidden)
    monkeypatch.setattr(service, "build_scorecard", forbidden)
    monkeypatch.setattr(SharedBrainApplicationService, "analyze_stock", forbidden)
    monkeypatch.setattr(ExecutionGateEngine, "evaluate", forbidden)
    monkeypatch.setattr(GovernedPreBreakoutSetupAssessmentService, "assess_prebreakout_setup", forbidden)
    reads = []
    def reader(funnel, cutoff):
        reads.append((funnel.value, cutoff))
        return (source,) if funnel is F.SECTOR_ROTATION else ()
    result = orchestration_fixture._run(reader=reader)
    assert len(result.executions) == 14 and {f for f, _ in reads} == BINDINGS
    assert len(result.candidate_union.candidates) == 1
    assert result.candidate_union.candidates[0].status.value == "CANDIDATE_FOR_SHARED_BRAIN_INSPECTION"


def test_same_security_multiple_funnels_preserves_all_origins_without_ranking():
    u = union_fixture
    one = u._lead()
    two = u._lead(funnel=F.SECTOR_ROTATION, source="receipt:two")
    result = u.union_discovery_candidates(
        as_of=u.AS_OF, adapter_results=(u._adapter(F.PRE_BREAKOUT, (one,)), u._adapter(F.SECTOR_ROTATION, (two,)))
    )
    assert len(result.candidates) == 1
    candidate = result.candidates[0]
    assert candidate.distinct_funnel_count == 2 and len(candidate.origins) == 2
    assert {o.lead.lead_id for o in candidate.origins} == {one.lead_id, two.lead_id}
    assert {ref.reference_id for o in candidate.origins for ref in o.lead.lineage} == {"receipt:one", "receipt:two"}
    assert not {"score", "rank", "action", "quantity"} & set(candidate.__dataclass_fields__)


def test_existing_radar_bridge_is_not_new_union_consumer():
    node = _node("app/intelligence/radar_diagnostic_orchestration.py", "evaluate_one_lead")
    assert {"assemble_for_radar", "run"} <= _calls(node)
    batch = ast.unparse(_node("app/intelligence/radar_diagnostic_orchestration.py", "evaluate_leads"))
    assert "lead.lead_id" in batch
    assert "union_discovery_candidates" not in batch
    text = _source("app/intelligence/radar_diagnostic_orchestration.py")
    assert "DiscoveryFunnelStatus.OPERATIONAL" in text
    assert "strict_historical_pit_state" in text


def test_no_runtime_or_frontend_integration_call_site():
    forbidden = {
        "orchestrate_whole_market_discovery", "RadarToHsiDiagnosticOrchestrator",
        "project_watch_to_hsi_signal",
    }
    for directory in ("app/api", "app/runtime", "scripts", "tools"):
        for path in (ROOT / directory).rglob("*.py"):
            assert not (_calls(ast.parse(path.read_text(encoding="utf-8-sig"))) & forbidden), str(path)
    implementations = []
    for path in (ROOT / "app").rglob("*.py"):
        if "def assemble_for_radar(" in path.read_text(encoding="utf-8-sig"):
            implementations.append(path.relative_to(ROOT).as_posix())
    # Additive runtime slice: preserve the old bridge and every external-call
    # prohibition while admitting only the explicitly bounded concrete port.
    assert sorted(implementations) == ["app/intelligence/discovery_union_radar_binding.py",
                                      "app/intelligence/radar_diagnostic_orchestration.py"]
    for path in (ROOT / "frontend/src").rglob("*"):
        if path.suffix in {".ts", ".tsx"}:
            assert "multi_funnel" not in path.read_text(encoding="utf-8-sig")


def test_existing_downstream_services_are_not_erased():
    assert {"run", "build_scorecard", "_gates"} <= _calls(
        _node("app/universe_analysis/service.py", "run_next_batch"))
    watch = _node("app/intelligence/market_wide_watch.py", "_record")
    assert "route" in _calls(watch)
    assert not {"run", "build_scorecard", "evaluate"} & _calls(watch)
    projection = _node("app/intelligence/hsi_signal_projection.py", "project_watch_to_hsi_signal")
    assert "create" in _calls(projection) and "resolve" in _calls(projection)
    score = _source("app/scoring/engine.py")
    assert "classify_score_input" in score and "funnel" not in score
    query = _source("app/api/routes/market_wide_watch.py")
    assert "service.latest()" in query and "503" in query
    assert "SignalQueryService" in _source("app/api/routes/signals.py")
    assert "proprietary diagnostic inventory stays private" in _source("app/api/schemas/stocks.py")


def test_stale_registry_metadata_and_current_adapter_both_retained():
    row = next(r for r in _read()["matrix"] if r["funnel_id"] == "SECTOR_ROTATION")
    assert row["adapter_exists"]
    assert "SECTOR_TO_STOCK_LEAD_ADAPTER_NOT_IMPLEMENTED" in row["source_blockers"]
    assert any(c["code"] == "STALE_SECTOR_ADAPTER_BLOCKER" for c in _read()["conflicts"])


def test_document_links_tables_and_index():
    md = ROOT / "docs/architecture" / (STEM + ".md")
    text = md.read_text(encoding="utf-8")
    assert STEM + ".md" in (ROOT / "README.md").read_text(encoding="utf-8")
    for label, target in re.findall(r"\[([^\]]+)\]\(([^)]+)\)", text):
        if "://" not in target and not target.startswith("#"):
            assert (md.parent / target.split("#")[0]).resolve().is_file(), (label, target)
    widths = []
    for line in text.splitlines() + [""]:
        assert line.rstrip() == line
        if line.startswith("|"):
            widths.append(line.count("|"))
        elif widths:
            assert len(set(widths)) == 1
            widths = []
    assert _read()["next_continuations"][0] in text
