"""HTTP proof with real HSI services and isolated fixtures; no provider calls."""
import ast
from dataclasses import replace
from datetime import UTC, datetime, timedelta
import inspect
import json
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient
import pytest

from app.api.agent_main import create_app
from app.api.agent_query import StoredAgentDiagnostics, diagnostics_from_existing_state
from app.api import agent_query, agent_tools
from app.api.market_context_query import SnapshotBreadthQueryService, SnapshotMarketExtremesQueryService
from app.api.news_query import RepositoryNewsQueryService
from app.api.portfolio_query import SnapshotPortfolioQueryService
from app.api.schemas.agent_tools import ToolEnvelope
from app.data_sources.models import DataFamily, SourceRecordProvenance
from app.fundamentals.store import SQLiteFinancialFactStore
from app.intelligence.shared_brain_application import CoreUniverseInstrumentResolver, SharedBrainApplicationService, StoredSharedBrainEvidenceAssembler
from app.news.models import NewsArticleEvidence, NewsSourceQuality
from app.news.store import SQLiteNewsEvidenceStore
from app.universe_analysis.models import NseEquityInstrument
from app.universe_analysis.service import Canonical61DiagnosticRunner
from tests.fixtures.analytical_observations import bars
from tests.unit.test_canonical_61_runner_governance import _definition
from tests.unit.test_market_context_api import _breadth_record, _extremes
from tests.unit.test_portfolio_api import snapshot

T = datetime(2026, 9, 6, 12, tzinfo=UTC)
SECURITY = "NSE:INE372A01015"
PREFIX = "/hsi/v1"
KEY = "synthetic-agent-test-key-not-a-real-secret"
AUTH = {"Authorization": "Bearer " + KEY}
REQUEST = {"canonical_security_id": SECURITY, "as_of": T.isoformat(), "temporal_mode": "CURRENT_DESCRIPTIVE"}


@pytest.fixture(autouse=True)
def isolated_environment(monkeypatch):
    monkeypatch.setenv("HSI_AGENT_API_KEY", KEY)
    monkeypatch.delenv("DHAN_LIVE_MARKET_ENABLED", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("DATABASE_BACKEND", raising=False)


class Universe:
    def instruments_as_of(self, at):
        return (NseEquityInstrument(SECURITY, "APARINDS", SECURITY[4:], "Industrials", None,
            "ACTIVE", None, True, T - timedelta(days=10), "OFFICIAL_FIXTURE", "fixture:master"),)


class Governance:
    def get_canonical_diagnostic_strategy_definition(self, ref): return _definition()


class Observations:
    def __init__(self):
        self.values = (*bars(SECURITY, [10,11,12,13,14,15], volumes=[10,11,12,13,14,15]),
                       *bars("NIFTY_50", [100,101,102,103,104,105]))
    def observations_as_of(self, at): return self.values


def diagnostic_service(source=None, governance=None):
    return StoredAgentDiagnostics(universe=Universe(), governance=governance or Governance(),
        source_factory=lambda security, at: source or Observations())


def app_with_diagnostics(service=None):
    app = create_app()
    app.state.agent_diagnostic_service = service or diagnostic_service()
    return app


def test_startup_reuses_existing_api_and_separate_tool_openapi():
    from app.api.main import create_app as existing_app
    with TestClient(create_app()) as client:
        doc = client.get(PREFIX + "/openapi.json")
        assert client.get(PREFIX + "/docs").status_code == 200
        assert client.get("/health").status_code == 200
        assert client.get("/openapi.json").json()["paths"] == existing_app().openapi()["paths"]
    paths = doc.json()["paths"]
    assert set(paths) == {"/capabilities", "/diagnostics", "/stock-intelligence", "/market-context", "/news-catalysts", "/portfolio-state", "/market-scan"}
    assert doc.json()["servers"] == [{"url": PREFIX}]
    operations = [operation for path in paths.values() for operation in path.values()]
    assert {op["operationId"] for op in operations} == {
        "hsi_get_capabilities", "hsi_run_diagnostics", "hsi_get_stock_intelligence", "hsi_get_market_context", "hsi_get_news_catalysts", "hsi_get_portfolio_state", "hsi_scan_market"}
    assert all(op["security"] == [{"HSIAgentKey": []}] for op in operations)
    assert len(operations) == 7
    assert paths["/diagnostics"].keys() == {"post"}


@pytest.mark.parametrize("header", (None, "Bearer wrong", "Basic " + KEY, "Bearer", "Bearer " + KEY + " ", "Bearer wrong\tvalue"))
def test_missing_malformed_or_invalid_auth_fails(header):
    with TestClient(create_app()) as client:
        response = client.get(PREFIX + "/capabilities", headers={} if header is None else {"Authorization": header})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "HSI_AGENT_AUTH_FAILED"
    assert KEY not in response.text


def test_all_tool_routes_require_auth_before_backend_calls():
    with TestClient(app_with_diagnostics()) as client:
        for path in ("capabilities", "stock-intelligence", "market-context", "news-catalysts", "portfolio-state"):
            assert client.get(PREFIX + "/" + path).status_code == 401
        assert client.post(PREFIX + "/diagnostics", json=REQUEST).status_code == 401


def test_rotation_revocation_and_distinct_ingest_secret(monkeypatch, caplog):
    with TestClient(create_app()) as client:
        assert client.get(PREFIX + "/capabilities", headers=AUTH).status_code == 200
        monkeypatch.setenv("HSI_AGENT_API_KEY", "rotated-test-key")
        assert client.get(PREFIX + "/capabilities", headers=AUTH).status_code == 401
        assert client.get(PREFIX + "/capabilities", headers={"Authorization": "Bearer rotated-test-key"}).status_code == 200
        monkeypatch.delenv("HSI_AGENT_API_KEY")
        monkeypatch.setenv("HSI_EXTERNAL_INTELLIGENCE_INGEST_TOKEN", KEY)
        missing = client.get(PREFIX + "/capabilities", headers=AUTH)
        assert missing.status_code == 503 and missing.json()["error"]["code"] == "HSI_AGENT_AUTH_UNAVAILABLE"
    assert KEY not in caplog.text and "rotated-test-key" not in caplog.text


def test_duplicate_header_fails_closed():
    with TestClient(create_app()) as client:
        assert client.get(PREFIX + "/capabilities", headers=[("Authorization", AUTH["Authorization"]), ("Authorization", AUTH["Authorization"])]).status_code == 401


def test_manifest_has_truthful_tool_gaps_and_no_placeholder_scan():
    with TestClient(create_app()) as client:
        response = client.get(PREFIX + "/capabilities", headers=AUTH)
        entries = {v["tool_id"]: v for v in response.json()["data"]}
        assert entries["hsi_get_capabilities"]["readiness"] == "READY"
        assert entries["hsi_run_diagnostics"]["readiness"] != "READY"
        assert entries["hsi_scan_market"]["readiness"] == "PARTIAL"
        assert entries["hsi_scan_market"]["blockers"] == ["SHARED_SNAPSHOT_AND_NATIVE_SOURCE_COVERAGE_REQUIRED"]
        assert entries["hsi_scan_market"]["exposed"] is True
        assert entries["hsi_get_setup_inputs"]["readiness"] == "NOT_EXPOSED"
        assert all(v["read_only"] and v["authority"] == "RESEARCH_READ_ONLY" for v in entries.values())
        assert client.post(PREFIX + "/market-scan", headers=AUTH).status_code == 405
        assert response.headers["cache-control"] == "no-store"


def test_real_canonical_61_invoked_once_through_http_without_writes(monkeypatch):
    calls = []
    original = Canonical61DiagnosticRunner.run
    def counted(self, evidence, **kwargs):
        calls.append(evidence)
        return original(self, evidence, **kwargs)
    monkeypatch.setattr(Canonical61DiagnosticRunner, "run", counted)
    app = app_with_diagnostics()
    with TestClient(app) as client:
        import requests, sqlite3
        def forbidden(*args, **kwargs): pytest.fail("Forbidden effect")
        monkeypatch.setattr(requests.sessions.Session, "request", forbidden)
        monkeypatch.setattr(sqlite3, "connect", forbidden)
        response = client.post(PREFIX + "/diagnostics", json=REQUEST, headers=AUTH)
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["data"] is not None, payload
    assert len(calls) == 1
    assert [r["rule_id"] for r in payload["data"]["rules"]] == list(range(1, 62))
    assert any(r["result"] == "INSUFFICIENT_DATA" for r in payload["data"]["rules"])
    assert payload["data"]["evaluated_count"] + payload["data"]["missing_count"] == 61
    assert payload["data"]["strategy_fingerprint"] == _definition().semantic_fingerprint
    assert payload["data"]["strict_historical_pit"] == "NOT_READY"
    assert payload["execution_status"] == "NON_EXECUTABLE" and payload["actionability"] == "WATCH_ONLY"
    assert payload["data"]["input_fingerprint"] and payload["provenance"]


def test_diagnostics_serialization_and_timezone_determinism():
    with TestClient(app_with_diagnostics()) as client:
        one = client.post(PREFIX + "/diagnostics", json=REQUEST, headers=AUTH).json()
        two = client.post(PREFIX + "/diagnostics", json=REQUEST | {"as_of": "2026-09-06T17:30:00+05:30"}, headers=AUTH).json()
    assert one == two and one["data"] is not None


@pytest.mark.parametrize("body", (
    REQUEST | {"as_of": "2026-09-06T12:00:00"}, REQUEST | {"canonical_security_id": "APARINDS"},
    REQUEST | {"canonical_security_id": "NSE:INE372A01015\n"}, REQUEST | {"url": "https://arbitrary.test"},
    REQUEST | {"as_of": None}, REQUEST | {"strategy_version": "v2"}, REQUEST | {"evidence": {}},
))
def test_request_validation_is_strict_and_never_echoes_inputs(body):
    with TestClient(create_app()) as client:
        response = client.post(PREFIX + "/diagnostics", json=body, headers=AUTH)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_REQUEST"
    assert SECURITY not in response.text and "arbitrary.test" not in response.text


def test_strict_pit_and_unknown_security_do_not_invoke_runner(monkeypatch):
    def forbidden(*args, **kwargs): pytest.fail("runner should not execute")
    monkeypatch.setattr(Canonical61DiagnosticRunner, "run", forbidden)
    with TestClient(app_with_diagnostics()) as client:
        strict = client.post(PREFIX + "/diagnostics", json=REQUEST | {"temporal_mode": "STRICT_HISTORICAL_PIT"}, headers=AUTH).json()
        missing = client.post(PREFIX + "/diagnostics", json=REQUEST | {"canonical_security_id": "NSE:INE000A01001"}, headers=AUTH).json()
    assert strict["blockers"] == ["STRICT_HISTORICAL_PIT_NOT_READY"]
    assert missing["status"] == "BLOCKED" and missing["data"] is None


def test_missing_resources_and_future_governance_fail_closed():
    with pytest.raises(Exception): diagnostics_from_existing_state(SimpleNamespace())
    class Future:
        def get_canonical_diagnostic_strategy_definition(self, ref):
            return replace(_definition(), registered_at=T + timedelta(seconds=1))
    with TestClient(app_with_diagnostics(diagnostic_service(governance=Future()))) as client:
        response = client.post(PREFIX + "/diagnostics", json=REQUEST, headers=AUTH)
    assert response.json()["blockers"] == ["FUTURE_DIAGNOSTIC_GOVERNANCE"]


def test_default_diagnostics_route_uses_existing_resources_and_no_fake_universe():
    with TestClient(create_app()) as client:
        result = client.post(PREFIX + "/diagnostics", json=REQUEST, headers=AUTH).json()
    assert result["status"] == "BLOCKED" and result["data"] is None


def test_default_stored_composition_reaches_61_without_new_storage_or_persistence(monkeypatch):
    from app.universe_analysis.service import CoreUniverseAnalysisStore
    app = create_app()
    with TestClient(app) as client:
        core = app.state.core_api_snapshot_repository
        governance = app.state.decision_score_governance_repository
        CoreUniverseAnalysisStore(core).save_instrument(Universe().instruments_as_of(T)[0])
        governance.save_canonical_diagnostic_strategy_definition(_definition())
        # Native fixture admission occurs before the HTTP call. Observe SQL
        # thereafter: this default composition must issue reads only.
        sql = []
        connections = [governance._connection, core._connection]
        connections.extend(s._connection for s in app.state.market_wide_evidence_resources if hasattr(s, "_connection"))
        for connection in connections: connection.set_trace_callback(sql.append)
        response = client.post(PREFIX + "/diagnostics", json=REQUEST, headers=AUTH)
        for connection in connections: connection.set_trace_callback(None)
    data = response.json()["data"]
    assert data is not None, response.text
    assert len(data["rules"]) == 61
    assert data["missing_count"] > 0
    assert sql and all(s.lstrip().upper().startswith("SELECT") for s in sql), sql


def test_future_observation_is_excluded_by_existing_assembler():
    source = Observations()
    item = source.values[0]
    late = replace(item, id="future-observation", provenance=replace(item.provenance, retrieved_timestamp=T + timedelta(seconds=1)))
    source.values = (*source.values, late)
    with TestClient(app_with_diagnostics(diagnostic_service(source=source))) as client:
        response = client.post(PREFIX + "/diagnostics", json=REQUEST, headers=AUTH).json()
    assert response["data"] is not None
    assert "FUTURE_EVIDENCE_EXCLUDED" in response["warnings"]
    assert "future-observation" not in response["evidence_refs"]


def test_diagnostic_concurrency_has_no_unbounded_queue():
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event
    entered, release = Event(), Event()
    class Busy:
        def evaluate(self, body):
            entered.set()
            assert release.wait(5)
            return ToolEnvelope(status="BLOCKED", blockers=("FIXTURE_BLOCKED",))
    with TestClient(app_with_diagnostics(Busy())) as client, ThreadPoolExecutor(max_workers=1) as pool:
        first = pool.submit(client.post, PREFIX + "/diagnostics", json=REQUEST, headers=AUTH)
        try:
            assert entered.wait(5)
            second = client.post(PREFIX + "/diagnostics", json=REQUEST, headers=AUTH)
            assert second.json()["blockers"] == ["DIAGNOSTIC_TOOL_BUSY"]
        finally:
            release.set()
        assert first.result(timeout=5).status_code == 200


def test_missing_or_tampered_governance_never_reaches_rule_runner(monkeypatch):
    def forbidden(*args, **kwargs): pytest.fail("ungoverned runner")
    monkeypatch.setattr(Canonical61DiagnosticRunner, "run", forbidden)
    class Missing:
        def get_canonical_diagnostic_strategy_definition(self, ref): return None
    class Tampered:
        def get_canonical_diagnostic_strategy_definition(self, ref):
            definition = _definition()
            object.__setattr__(definition, "semantic_fingerprint", "sha256:" + "f" * 64)
            return definition
    for governance in (Missing(), Tampered()):
        with TestClient(app_with_diagnostics(diagnostic_service(governance=governance))) as client:
            response = client.post(PREFIX + "/diagnostics", json=REQUEST, headers=AUTH).json()
        assert response["status"] == "BLOCKED" and response["data"] is None


def test_stock_tool_calls_existing_shared_brain_with_explicit_cutoff():
    facts = SQLiteFinancialFactStore()
    service = SharedBrainApplicationService(resolver=CoreUniverseInstrumentResolver(Universe()),
        evidence_assembler=StoredSharedBrainEvidenceAssembler(facts), clock=lambda: pytest.fail("implicit clock"))
    with TestClient(create_app(shared_brain_application_service=service)) as client:
        response = client.get(PREFIX + "/stock-intelligence", params={"canonical_security_id": SECURITY, "as_of": T.isoformat()}, headers=AUTH)
    assert response.status_code == 200, response.text
    value = response.json()
    assert value["data"] is not None, value
    assert value["data"]["canonical_instrument_id"] == SECURITY
    assert value["status"] == "PARTIAL" and value["data"]["financial_semantics"] == []
    assert value["data"]["snapshot_fingerprint"] in value["provenance"]


def test_market_context_reuses_existing_views_and_leaves_missing_domains_visible():
    with TestClient(create_app(breadth_query_service=SnapshotBreadthQueryService(_breadth_record()),
                              market_extremes_query_service=SnapshotMarketExtremesQueryService(_extremes()))) as client:
        value = client.get(PREFIX + "/market-context", headers=AUTH).json()
    assert value["status"] == "PARTIAL"
    assert value["data"]["breadth"]["advances"] == 1
    assert value["data"]["extremes"]["market_state"] == "EUPHORIA"
    assert value["data"]["regime"] is None
    assert "REGIME_UNAVAILABLE" in value["blockers"]
    assert value["as_of"] is None  # mixed native timestamps, no invented common time


def test_portfolio_tool_reads_snapshot_without_actions_or_mutation():
    value = snapshot(marked=False)
    before = repr(value)
    with TestClient(create_app(portfolio_query_service=SnapshotPortfolioQueryService(value))) as client:
        response = client.get(PREFIX + "/portfolio-state", headers=AUTH).json()
    assert response["data"]["snapshot_id"] == value.snapshot_id
    assert response["data"]["holdings"][0]["quantity"] == "100"
    assert response["data"]["holdings"][0]["market_price"] is None
    assert response["status"] == "PARTIAL" and repr(value) == before
    assert not {"action", "trade_plan", "order", "sizing"} & response["data"].keys()


def test_news_tool_excludes_late_received_evidence_and_preserves_source_metadata():
    store = SQLiteNewsEvidenceStore()
    def article(id, received):
        return NewsArticleEvidence(id, "official-fixture", "Issuer", None, "https://example.test/disclosure",
            "Synthetic disclosure", "Synthetic source text", T, received, "en", "in", (SECURITY,), (), (),
            NewsSourceQuality.REPUTABLE_NEWS, SourceRecordProvenance(id, "official-fixture", "provider", T, received, received, None, None, DataFamily.NEWS_RESEARCH, "v1", "v1"))
    store.save(article("known", T)); store.save(article("future", T + timedelta(seconds=1)))
    with TestClient(create_app(news_query_service=RepositoryNewsQueryService(store))) as client:
        response = client.get(PREFIX + "/news-catalysts", headers=AUTH,
            params={"canonical_security_id": SECURITY, "as_of": T.isoformat()}).json()
        assert client.get(PREFIX + "/news-catalysts", headers=AUTH,
            params={"canonical_security_id": SECURITY, "as_of": T.isoformat(), "limit": 51}).status_code == 422
    assert response["evidence_refs"] == ["known"]
    assert response["status"] == "PARTIAL"
    assert response["data"]["items"][0]["source_quality"] == "REPUTABLE_NEWS"
    assert "NEWS_COVERAGE_NOT_PROVEN" in response["blockers"]


def test_provider_and_response_exceptions_do_not_expose_secrets_or_log_them(caplog):
    class Bad:
        def evaluate(self, body): raise ValueError("provider token=" + KEY)
    with TestClient(app_with_diagnostics(Bad()), raise_server_exceptions=False) as client:
        response = client.post(PREFIX + "/diagnostics", json=REQUEST, headers=AUTH)
    assert response.json()["status"] == "BLOCKED"
    assert KEY not in response.text and KEY not in caplog.text
    class Invalid:
        def evaluate(self, body): return {"status": KEY}
    with TestClient(app_with_diagnostics(Invalid()), raise_server_exceptions=False) as client:
        response = client.post(PREFIX + "/diagnostics", json=REQUEST, headers=AUTH)
    assert response.status_code == 500
    assert KEY not in response.text and KEY not in caplog.text


@pytest.mark.parametrize("path", ("orders", "broker", "admin", "sql", "files", "fetch", "portfolio/import", "api/v1/connections/upstox/credentials"))
def test_tool_prefix_never_routes_to_internal_or_execution_endpoints(path):
    with TestClient(create_app()) as client:
        assert client.post(PREFIX + "/" + path, headers=AUTH).status_code == 404


def test_static_reuse_boundary_no_new_engine_runtime_clock_or_persistence():
    tree = ast.parse(inspect.getsource(agent_query))
    attrs = {n.func.attr for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}
    assert {"assemble", "run", "authorize"} <= attrs
    assert not attrs & {"save", "save_snapshot", "commit", "execute", "now", "utcnow", "assess_prebreakout_setup", "evaluate_gates"}
    source = inspect.getsource(agent_tools) + inspect.getsource(agent_query)
    assert "app.broker" not in source and "app.orders" not in source
    assert "create_core_api_snapshot_repository" not in source
    assert "UnionRadarRuntimeBinding(" not in source and "CanonicalDiscoveryLead(" not in source
    with TestClient(create_app()) as client:
        document = client.get(PREFIX + "/openapi.json").text
    assert KEY not in document
