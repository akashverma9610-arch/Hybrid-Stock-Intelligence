"""Stored canonical setup and composed Agent workflow; isolated fixtures only."""
import ast
from dataclasses import replace
from datetime import timedelta
from decimal import Decimal
import inspect
import json
from types import SimpleNamespace

from fastapi.testclient import TestClient
import pytest

from app.api import agent_setup
from app.api.agent_main import create_app
from app.api.agent_query import StoredAgentDiagnostics
from app.api.market_context_query import SnapshotBreadthQueryService, SnapshotMarketExtremesQueryService
from app.api.portfolio_query import SnapshotPortfolioQueryService
from app.fundamentals.store import SQLiteFinancialFactStore
from app.intelligence.shared_brain_application import CoreUniverseInstrumentResolver, SharedBrainApplicationService, StoredSharedBrainEvidenceAssembler
from app.strategies.pre_breakout.setup_assessment import GovernedPreBreakoutSetupAssessmentService
from app.universe_analysis.service import Canonical61DiagnosticRunner
from tests.fixtures.analytical_observations import bars
from tests.unit.pre_breakout_setup_fixture import assessment
from tests.unit.test_agent_tool_facade import AUTH, KEY, PREFIX, SECURITY, T, Governance
from tests.unit.test_hsi_signal_strategy_registry import _approved_selected
from tests.unit.test_market_context_api import _breadth_record, _extremes
from tests.unit.test_portfolio_api import snapshot as portfolio_snapshot
from tests.unit.test_shared_market_scan import service as scan_service, instrument

URL = PREFIX + "/setup"
PARAMS = {"canonical_security_id": SECURITY, "as_of": T.isoformat()}


@pytest.fixture(autouse=True)
def isolated_env(monkeypatch):
    monkeypatch.setenv("HSI_AGENT_API_KEY", KEY)
    for key in ("DHAN_LIVE_MARKET_ENABLED", "DATABASE_URL", "DATABASE_BACKEND"):
        monkeypatch.delenv(key, raising=False)


def stored(tmp_path, *, security=SECURITY, at=T, eligible=True, structural=None, technical=None):
    repo, approval, selection = _approved_selected(tmp_path)
    selection = repo.get_prebreakout_policy_selection(selection.selection_id)
    source = assessment(at=at, eligible=eligible)
    lineage = dict(instrument_id=security, policy_id=selection.policy_id, policy_version=selection.policy_version,
        policy_fingerprint=selection.policy_fingerprint, selection_id=selection.selection_id,
        selection_fingerprint=selection.fingerprint)
    value = replace(source, **lineage,
        technical_inputs=replace(source.technical_inputs, **lineage, **(technical or {})),
        structural=replace(source.structural, **lineage, **(structural or {})))
    repo.save_prebreakout_setup_assessment(value)
    return repo, value


def read(repo, **params):
    return agent_setup.setup_response(repo, params.get("security", SECURITY), as_of=params.get("at", T))


def test_native_stored_values_and_nullable_gaps(tmp_path):
    repo, source = stored(tmp_path)
    result = read(repo)
    assert result.status == "PARTIAL", result
    data = result.data
    assert data.assessment_id == source.assessment_id and data.assessment_fingerprint == source.fingerprint
    assert data.entry_reference_price == Decimal("470")
    assert data.breakout_confirmation_trigger == Decimal("500")
    assert data.breakout_trigger_role == "CONFIRMATION_NOT_INITIAL_ENTRY"
    assert data.structural_stop == source.structural.final_stop
    assert data.target_1 == source.structural.target and data.entry_rr == source.structural.entry_reference_rr
    assert data.target_2 is data.extended_target is data.horizon is data.exact_invalidation is None
    assert data.freshness == "UNKNOWN" and data.source_as_of == source.evaluation_as_of
    assert data.decision_score.status == data.six_gates.status == "BLOCKED"
    assert data.execution_gate_v2 == "NOT_ACTIVE"
    assert result.actionability == "WATCH_ONLY" and result.execution_status == "NON_EXECUTABLE"
    assert {source.assessment_id, source.selection_id, "h", "l", "tick-id"} <= set(result.evidence_refs)
    assert read(repo).model_dump_json() == result.model_dump_json()
    assert type(data).model_validate_json(data.model_dump_json()) == data
    repo.close()


@pytest.mark.parametrize("field,output", (
    ("entry_reference_price", "entry_reference_price"), ("final_stop", "structural_stop"),
    ("target", "target_1"), ("entry_reference_rr", "entry_rr"),
    ("breakout_confirmation_trigger", "breakout_confirmation_trigger"),
))
def test_missing_fields_are_never_synthesized(tmp_path, field, output):
    repo, _ = stored(tmp_path, eligible=False, structural={field: None})
    result = read(repo)
    assert result.status == "BLOCKED" and getattr(result.data, output) is None
    assert any(c.status == "BLOCKED" for c in result.data.components)
    repo.close()


def test_empty_future_and_other_security_fail_closed(tmp_path):
    repo, _ = stored(tmp_path, at=T + timedelta(seconds=1))
    assert read(repo).blockers == ("SETUP_ASSESSMENT_NOT_AVAILABLE_AT_CUTOFF",)
    assert read(repo, security="NSE:INE000A01001").data is None
    assert read(None).blockers == ("SETUP_READ_REPOSITORY_UNAVAILABLE",)
    repo.close()


def test_latest_conflicting_assessments_do_not_depend_on_sort_order(tmp_path):
    repo, value = stored(tmp_path)
    repo.save_prebreakout_setup_assessment(replace(value, warnings=("OTHER_ASSESSMENT",)))
    assert read(repo).blockers == ("SETUP_ASSESSMENT_AMBIGUOUS",)
    repo.close()


@pytest.mark.parametrize("kind", ("nested_time", "nested_identity", "policy", "future_governance", "missing_selection"))
def test_unverifiable_lineage_or_pit_blocks_prices(tmp_path, kind):
    changes = {"entry_reference_session": T + timedelta(seconds=1)} if kind == "nested_time" else {}
    repo, value = stored(tmp_path, structural=changes)
    if kind in {"nested_identity", "policy"}:
        part = replace(value.structural, **({"instrument_id": "NSE:INE000A01001"} if kind == "nested_identity" else {"policy_fingerprint": "wrong"}))
        replacement = replace(value, structural=part)
        repo.list_prebreakout_setup_assessments = lambda **_: (replacement,)
    elif kind == "missing_selection":
        repo.get_prebreakout_policy_selection = lambda _: None
    elif kind == "future_governance":
        # Valid native governance whose effective selection lies after the setup.
        from app.strategies.pre_breakout.governance_commands import PreBreakoutPolicyGovernanceCommandService
        selection = PreBreakoutPolicyGovernanceCommandService(repo).select_for_current_stored_scan(
            selection_id="future", approval_id="approval:one", selected_by="human:owner",
            selected_at=T + timedelta(seconds=1), effective_from=T + timedelta(seconds=1))
        selection = repo.get_prebreakout_policy_selection(selection.selection_id)
        repo.get_prebreakout_policy_selection = lambda _: selection
    result = read(repo)
    assert result.status == "BLOCKED" and result.data is None
    repo.close()


def test_native_decoder_rejects_tampered_stored_fingerprint_without_repair(tmp_path):
    repo, value = stored(tmp_path)
    original = repo._connection.execute("SELECT payload_json FROM prebreakout_setup_assessments WHERE id=?", (value.assessment_id,)).fetchone()[0]
    payload = json.loads(original)
    payload["fingerprint"] = "tampered-secret-provider-text"
    repo._connection.execute("UPDATE prebreakout_setup_assessments SET payload_json=? WHERE id=?", (json.dumps(payload), value.assessment_id))
    result = read(repo)
    assert result.status == "BLOCKED" and result.data is None
    assert "tampered-secret" not in result.model_dump_json()
    repo.close()


def test_stored_score_and_gate_lineage_are_reused_without_evaluation(tmp_path, monkeypatch):
    from tests.unit.test_canonical_decision_score_activation import _repository, _activate
    from tests.unit.test_canonical_six_gates import _evaluation, canonical_execution_gate_evaluation_from
    from app.gates.engine import ExecutionGateEngine
    from app.intelligence.decision_score_evidence import decision_scorecard_artifact_fingerprint
    from app.intelligence.six_gates_evidence import six_gates_evaluation_artifact_fingerprint
    repo = _repository(tmp_path)
    score = repo.get_canonical_decision_scorecard(_activate(repo).outcomes[0].score_id)
    gates = canonical_execution_gate_evaluation_from(_evaluation(score), score=score)
    repo.save_canonical_execution_gate_evaluation(gates)
    setup_repo, _ = stored(tmp_path / "setup")
    # Borrow native readers over isolated, already-computed canonical records.
    setup_repo.list_canonical_decision_scorecards = repo.list_canonical_decision_scorecards
    setup_repo.list_canonical_execution_gate_evaluations = repo.list_canonical_execution_gate_evaluations
    monkeypatch.setattr(ExecutionGateEngine, "evaluate", lambda *a, **k: pytest.fail("gate recomputation"))
    result = read(setup_repo)
    assert result.data.decision_score.artifact_id == score.id
    assert result.data.decision_score.fingerprint == decision_scorecard_artifact_fingerprint(score)
    assert result.data.six_gates.artifact_id == gates.evaluation.id
    assert result.data.six_gates.fingerprint == six_gates_evaluation_artifact_fingerprint(gates)
    assert result.data.decision_score.status == result.data.six_gates.status == "PARTIAL"
    assert result.data.six_gates.blockers == ("SIX_GATES_NOT_BOUND_TO_SETUP_CONTEXT",)
    # Readers exclude future stored evaluation timestamps before projection.
    assert agent_setup._context(repo, SECURITY, score.as_of_timestamp - timedelta(seconds=1), gates=False).status == "BLOCKED"
    assert agent_setup._context(repo, SECURITY, score.as_of_timestamp - timedelta(seconds=1), gates=True).status == "BLOCKED"
    setup_repo.close()
    repo.close()


@pytest.mark.parametrize("auth,status", (({}, 401), ({"Authorization": "Bearer invalid"}, 401), (AUTH, 200)))
def test_setup_route_security(tmp_path, auth, status):
    repo, _ = stored(tmp_path)
    app = create_app()
    app.state.decision_score_governance_repository = repo
    with TestClient(app) as client:
        response = client.get(URL, params=PARAMS, headers=auth)
    assert response.status_code == status
    assert KEY not in response.text
    repo.close()


@pytest.mark.parametrize("params", ({}, PARAMS | {"canonical_security_id": "APARINDS"}, PARAMS | {"as_of": "2026-09-06T12:00:00"}))
def test_setup_requires_exact_identity_and_aware_cutoff(params):
    with TestClient(create_app()) as client:
        assert client.get(URL, params=params, headers=AUTH).status_code == 422


def test_composed_scan_diagnostics_brain_market_setup_portfolio_workflow(tmp_path, monkeypatch):
    scan, refresh_calls = scan_service()
    frozen = scan.refresh(as_of=T)
    security = frozen.batch.candidate_union.candidates[0].canonical_instrument_id
    repo, source = stored(tmp_path, security=security)
    universe = SimpleNamespace(instruments_as_of=lambda at: (instrument(),))
    observations = SimpleNamespace(observations_as_of=lambda at: (*bars(security, [10, 11, 12, 13, 14, 15]), *bars("NIFTY_50", [100, 101, 102, 103, 104, 105])))
    facts = SQLiteFinancialFactStore()
    brain = SharedBrainApplicationService(resolver=CoreUniverseInstrumentResolver(universe),
        evidence_assembler=StoredSharedBrainEvidenceAssembler(facts), clock=lambda: pytest.fail("implicit clock"))
    portfolio = portfolio_snapshot(marked=False)
    before = repr(portfolio)
    app = create_app(shared_brain_application_service=brain,
        breadth_query_service=SnapshotBreadthQueryService(_breadth_record()),
        market_extremes_query_service=SnapshotMarketExtremesQueryService(_extremes()),
        portfolio_query_service=SnapshotPortfolioQueryService(portfolio))
    app.state.decision_score_governance_repository = repo
    app.state.agent_market_scan_service = scan
    app.state.agent_diagnostic_service = StoredAgentDiagnostics(universe=universe, governance=Governance(), source_factory=lambda *args: observations)
    calls, sql = [], []
    original = Canonical61DiagnosticRunner.run
    def counted(self, *args, **kwargs):
        calls.append(1)
        return original(self, *args, **kwargs)
    monkeypatch.setattr(Canonical61DiagnosticRunner, "run", counted)
    def forbidden(*args, **kwargs): pytest.fail("forbidden effect")
    monkeypatch.setattr(GovernedPreBreakoutSetupAssessmentService, "assess_prebreakout_setup", forbidden)
    import requests
    monkeypatch.setattr(requests.sessions.Session, "request", forbidden)
    with TestClient(app) as client:
        repo._connection.set_trace_callback(sql.append)
        monkeypatch.setattr(scan, "refresh", forbidden)
        scan_result = client.get(PREFIX + "/market-scan", params={"as_of": T.isoformat()}, headers=AUTH).json()
        selected = scan_result["data"]["candidate_union"]["candidates"][0]["canonical_instrument_id"]
        assert selected == security
        params = {"canonical_security_id": selected, "as_of": T.isoformat()}
        diagnostics = client.post(PREFIX + "/diagnostics", json=params | {"temporal_mode": "CURRENT_DESCRIPTIVE"}, headers=AUTH).json()
        stock = client.get(PREFIX + "/stock-intelligence", params=params, headers=AUTH).json()
        market = client.get(PREFIX + "/market-context", headers=AUTH).json()
        setup = client.get(URL, params=params, headers=AUTH).json()
        holdings = client.get(PREFIX + "/portfolio-state", headers=AUTH).json()
        second = client.get(PREFIX + "/market-scan", params={"as_of": T.isoformat()}, headers=AUTH).json()
    assert scan_result == second and refresh_calls == [T]
    assert calls == [1], diagnostics
    assert [r["rule_id"] for r in diagnostics["data"]["rules"]] == list(range(1, 62))
    assert diagnostics["data"]["canonical_security_id"] == stock["data"]["canonical_instrument_id"] == setup["data"]["canonical_security_id"] == security
    assert diagnostics["as_of"] == stock["as_of"] == setup["as_of"]
    assert setup["data"]["assessment_fingerprint"] == source.fingerprint
    assert market["data"]["breadth"] is not None and market["as_of"] is None
    assert holdings["data"] is not None and repr(portfolio) == before
    for response in (diagnostics, stock, market, setup, holdings):
        assert response["execution_status"] == "NON_EXECUTABLE" and response["actionability"] == "WATCH_ONLY"
    assert sql and all(s.lstrip().upper().startswith("SELECT") for s in sql), sql
    facts._connection.close()
    repo.close()


def test_http_timezone_replay_and_persisted_reopen(tmp_path):
    from app.storage.sqlite_governance_repository import SQLiteStrategyGovernanceRepository
    repo, source = stored(tmp_path)
    repo.close()
    reopened = SQLiteStrategyGovernanceRepository(tmp_path / "governance.sqlite")
    app = create_app()
    app.state.decision_score_governance_repository = reopened
    with TestClient(app) as client:
        one = client.get(URL, params=PARAMS, headers=AUTH)
        two = client.get(URL, params=PARAMS | {"as_of": "2026-09-06T17:30:00+05:30"}, headers=AUTH)
    assert one.status_code == two.status_code == 200
    assert one.json() == two.json()
    assert one.json()["data"]["assessment_fingerprint"] == source.fingerprint


def test_repository_failure_is_redacted_and_never_replaced_by_prices(caplog):
    def fail(**kwargs): raise ValueError(KEY + " SQL provider-secret")
    app = create_app()
    with TestClient(app) as client:
        owned = app.state.decision_score_governance_repository
        app.state.decision_score_governance_repository = SimpleNamespace(list_prebreakout_setup_assessments=fail)
        response = client.get(URL, params=PARAMS, headers=AUTH)
        # Restore the API-owned repository for its normal shutdown lifecycle.
        app.state.decision_score_governance_repository = owned
    assert response.status_code == 200 and response.json()["data"] is None
    assert KEY not in response.text + caplog.text
    assert "provider-secret" not in response.text + caplog.text


def test_projection_has_only_read_calls_and_no_engine_provider_or_clock_dependency():
    tree = ast.parse(inspect.getsource(agent_setup))
    imports = {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
    assert imports == {"dataclasses", "datetime", "decimal", "typing", "pydantic", "app.api.schemas.agent_tools",
        "app.intelligence.decision_score_evidence", "app.intelligence.six_gates_evidence", "app.strategies.pre_breakout.governance"}
    calls = {n.func.attr for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}
    assert not calls & {"now", "utcnow", "save", "execute", "connect", "refresh", "evaluate", "materialize", "run", "assess_prebreakout_setup"}
    assert not any(n.startswith(("save_", "delete_", "update_")) for n in calls)
    assert not {"quantity", "allocation", "order", "action", "trade_plan"} & agent_setup.SetupResponse.model_fields.keys()
