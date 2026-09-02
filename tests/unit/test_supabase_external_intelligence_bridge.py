from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.main import create_app
from app.intelligence.external_intelligence_application import ExternalIntelligenceApplicationService
from app.intelligence.external_intelligence_live_connector import (
    DeliveryStatus, DeskDeliveryReceipt, ExternalIntelligenceLiveConnector,
    IntelligenceIngestHttpResponse,
)
from app.intelligence.external_intelligence_news_projection import ExternalIntelligenceNewsProjector
from app.intelligence.external_intelligence_reevaluation import (
    ExternalIntelligenceReevaluationConsumer, ExternalIntelligenceReevaluationDisposition,
)
from app.intelligence.macro_news_evidence import NewsCatalystEvidenceAdapter
from app.intelligence.supabase_inbox_bridge import (
    APPROVED_SUPABASE_ORIGIN, BridgeCycleReceipt, InboxDeliveryState, InboxRow,
    SupabaseBridgeConfigurationError, SupabaseBridgeNetworkError, SupabaseBridgeSettings,
    SupabaseExternalIntelligenceBridge, SupabaseInboxRestGateway, retry_delay,
)
from app.intelligence.unified_state import BrainOutputContext, IntelligenceEvidenceDomain
from app.news.store import SQLiteNewsEvidenceStore
from app.storage.sqlite_external_intelligence_repository import SQLiteExternalIntelligenceRepository
from app.universe_analysis.models import NseEquityInstrument


T = datetime(2026, 9, 1, 12, tzinfo=UTC)
ROW_ID = "b68fa5f9-5299-41d9-8a8e-6ca08b14d533"
TARGET = "NSE:INE090A01021"


def payload(**changes: object) -> dict[str, object]:
    value: dict[str, object] = {
        "schema_version": "hsi-external-intelligence-event/v1", "producer_event_id": "supabase-bridge-test-1",
        "event_type": "MONETARY_POLICY", "title": "TEST_SUPABASE_HSI_BRIDGE_CANARY", "country": "IN",
        "domain": "MACRO", "materiality": "HIGH", "policy_stage": "STATEMENT",
        "published_at": "2026-09-01T09:00:00+00:00", "discovered_at": "2026-09-01T10:00:00+00:00",
        "summary": "Synthetic Supabase bridge transport test.", "what_changed": "Synthetic transport-only change.",
        "primary_source": {"source_name": "Synthetic RBI", "source_type": "TEST", "source_reference": "https://invalid.test/rbi", "source_confidence": 0.9},
        "supporting_sources": [], "facts": [{"content": "Synthetic fact", "source_references": ["https://invalid.test/rbi"], "confidence": 0.9}],
        "data_points": [], "interpretation": [], "inferences": [], "affected_sectors": ["FINANCIALS"], "affected_industries": ["BANKS"],
        "possible_company_exposure": [{"canonical_instrument_id": TARGET, "external_company_name": "ICICI Bank", "exposure_type": "DIRECT", "confidence": 0.8, "verification_status": "VERIFIED"}],
        "event_confidence": 0.8, "exposure_confidence": 0.8, "requires_hsi_analysis": True,
    }
    value.update(changes)
    return value


def row(*, attempts: int = 1, raw_payload: dict[str, object] | None = None) -> InboxRow:
    event = raw_payload or payload()
    return InboxRow(ROW_ID, str(event.get("producer_event_id", "")), "sha256:test", event, InboxDeliveryState.CLAIMED, attempts)


def delivered(event: dict[str, object], disposition: str = "ACCEPTED_NEW") -> DeskDeliveryReceipt:
    return DeskDeliveryReceipt(DeliveryStatus.DELIVERED, str(event["producer_event_id"]), disposition, "canonical-1", "evidence-1", "request-1", T.isoformat(), None)


class _Inbox:
    def __init__(self, rows: tuple[InboxRow, ...] = ()) -> None:
        self.rows = rows
        self.claims: list[tuple[int, int]] = []
        self.updates: list[tuple[str, dict[str, object]]] = []
        self.fail_update = False

    def claim_due(self, *, limit: int, claim_ttl_seconds: int) -> tuple[InboxRow, ...]:
        self.claims.append((limit, claim_ttl_seconds))
        return self.rows

    def update_row(self, row_id: str, values: dict[str, object]) -> None:
        if self.fail_update:
            raise SupabaseBridgeNetworkError("synthetic update failure")
        self.updates.append((row_id, dict(values)))


class _Connector:
    def __init__(self, *receipts: DeskDeliveryReceipt | Exception) -> None:
        self.receipts = list(receipts)
        self.events: list[dict[str, object]] = []

    def ingest_intelligence_event(self, event: dict[str, object]) -> DeskDeliveryReceipt:
        self.events.append(dict(event))
        result = self.receipts.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


@pytest.mark.parametrize("disposition,field", (("ACCEPTED_NEW", "accepted_new"), ("ACCEPTED_EXISTING", "accepted_existing"), ("ACCEPTED_NEW_EVIDENCE", "accepted_new_evidence")))
def test_valid_claim_is_delivered_for_all_accepted_hsi_dispositions(disposition: str, field: str) -> None:
    inbox = _Inbox((row(),)); connector = _Connector(delivered(payload(), disposition))
    receipt = SupabaseExternalIntelligenceBridge(inbox=inbox, connector=connector, clock=lambda: T).run_once()
    assert receipt.claimed == receipt.delivered == 1 and getattr(receipt, field) == 1
    assert inbox.claims == [(10, 600)] and inbox.updates[0][1]["delivery_status"] == "DELIVERED"
    assert inbox.updates[0][1]["hsi_disposition"] == disposition and connector.events[0]["producer_event_id"] == "supabase-bridge-test-1"


def test_malformed_and_identity_mismatch_payloads_are_dead_lettered_without_hsi_call() -> None:
    invalid = InboxRow(ROW_ID, "bad", "sha256:test", {"producer_event_id": "bad"}, InboxDeliveryState.CLAIMED, 1)
    mismatch = InboxRow(ROW_ID, "supabase-bridge-test-1", "sha256:test", payload(producer_event_id="different"), InboxDeliveryState.CLAIMED, 1)
    for claimed_row in (invalid, mismatch):
        inbox = _Inbox((claimed_row,)); connector = _Connector()
        receipt = SupabaseExternalIntelligenceBridge(inbox=inbox, connector=connector, clock=lambda: T).run_once()
        assert receipt.dead_letter == receipt.malformed == 1 and not connector.events
        assert inbox.updates[0][1]["delivery_status"] == "DEAD_LETTER"


def test_transient_failure_retries_with_bounded_exponential_backoff_and_max_attempts_dead_letters() -> None:
    unavailable = DeskDeliveryReceipt(DeliveryStatus.PENDING_DELIVERY, "supabase-bridge-test-1", None, None, None, None, None, "HSI_HTTP_503")
    inbox = _Inbox((row(attempts=3),)); connector = _Connector(unavailable)
    receipt = SupabaseExternalIntelligenceBridge(inbox=inbox, connector=connector, clock=lambda: T).run_once()
    assert receipt.retry == receipt.hsi_unavailable == 1
    assert inbox.updates[0][1]["next_attempt_at"] == (T + timedelta(minutes=4)).isoformat()
    assert [retry_delay(item).total_seconds() for item in (1, 2, 3, 4, 5, 6, 7, 20)] == [60, 120, 240, 480, 900, 1800, 3600, 3600]
    maxed = _Inbox((row(attempts=10),)); result = SupabaseExternalIntelligenceBridge(inbox=maxed, connector=_Connector(unavailable), clock=lambda: T).run_once()
    assert result.dead_letter == 1 and maxed.updates[0][1]["last_error"] == "MAX_ATTEMPTS_EXCEEDED"


def test_hsi_409_is_permanent_dead_letter_and_network_exception_retries() -> None:
    conflict = DeskDeliveryReceipt(DeliveryStatus.PENDING_DELIVERY, "supabase-bridge-test-1", None, None, None, None, None, "HSI_HTTP_409")
    inbox = _Inbox((row(),)); receipt = SupabaseExternalIntelligenceBridge(inbox=inbox, connector=_Connector(conflict), clock=lambda: T).run_once()
    assert receipt.dead_letter == 1 and inbox.updates[0][1]["last_error"] == "HSI_HTTP_409"
    retry_inbox = _Inbox((row(),)); retry = SupabaseExternalIntelligenceBridge(inbox=retry_inbox, connector=_Connector(ConnectionError("synthetic")), clock=lambda: T).run_once()
    assert retry.retry == retry.hsi_unavailable == 1


def test_post_hsi_update_failure_is_reclaimed_and_exactly_retried_without_new_producer_id() -> None:
    inbox = _Inbox((row(),)); inbox.fail_update = True
    connector = _Connector(delivered(payload(), "ACCEPTED_NEW"), delivered(payload(), "ACCEPTED_EXISTING"))
    bridge = SupabaseExternalIntelligenceBridge(inbox=inbox, connector=connector, clock=lambda: T)
    assert bridge.run_once().supabase_failure == 1
    inbox.fail_update = False
    result = bridge.run_once()
    assert result.delivered == result.accepted_existing == 1
    assert [event["producer_event_id"] for event in connector.events] == ["supabase-bridge-test-1", "supabase-bridge-test-1"]
    assert inbox.updates[0][1]["delivery_status"] == "DELIVERED"


def test_settings_are_bounded_disabled_by_default_and_environment_configuration_fails_closed() -> None:
    assert not SupabaseBridgeSettings.from_environment({}).enabled
    with pytest.raises(SupabaseBridgeConfigurationError): SupabaseBridgeSettings(batch_size=11)
    with pytest.raises(SupabaseBridgeConfigurationError): SupabaseBridgeSettings(claim_ttl_seconds=59)
    with pytest.raises(SupabaseBridgeConfigurationError): SupabaseInboxRestGateway(origin="https://other.supabase.co", secret_key="sb_secret_test")
    with pytest.raises(SupabaseBridgeConfigurationError): SupabaseInboxRestGateway.from_environment({"HSI_EXTERNAL_INTELLIGENCE_SUPABASE_URL": APPROVED_SUPABASE_ORIGIN})


def test_rest_gateway_is_hard_bounded_to_project_rpc_table_and_apikey_header(monkeypatch) -> None:
    calls: list[object] = []
    class _Response:
        def __init__(self, data: bytes) -> None: self.data = data
        def read(self) -> bytes: return self.data
        def __enter__(self): return self
        def __exit__(self, *args): return False
    def fake_urlopen(request, timeout):
        calls.append(request)
        return _Response(json.dumps([{
            "id": ROW_ID, "producer_event_id": "supabase-bridge-test-1", "payload_fingerprint": "sha256:test", "raw_payload": payload(), "delivery_status": "CLAIMED", "attempt_count": 1,
        }]).encode())
    monkeypatch.setattr("app.intelligence.supabase_inbox_bridge.urlopen", fake_urlopen)
    gateway = SupabaseInboxRestGateway(origin=APPROVED_SUPABASE_ORIGIN, secret_key="sb_secret_not_logged")
    assert gateway.claim_due(limit=10, claim_ttl_seconds=600)[0].id == ROW_ID
    with pytest.raises(SupabaseBridgeConfigurationError): gateway.update_row(ROW_ID, {"raw_payload": {}})
    request = calls[0]
    assert request.full_url == APPROVED_SUPABASE_ORIGIN + "/rest/v1/rpc/claim_external_intelligence_inbox"
    assert request.get_header("Apikey") == "sb_secret_not_logged" and request.get_header("Authorization") is None


def test_stale_claim_is_only_consumed_from_atomic_claim_rpc_and_bridge_has_no_broader_authority() -> None:
    source = Path("app/intelligence/supabase_inbox_bridge.py").read_text(encoding="utf-8")
    assert "claim_external_intelligence_inbox" in source and "FOR UPDATE" not in source
    assert "portfolio" not in source.lower() and "broker" not in source.lower() and "orders" not in source.lower()
    assert "/api/v1/intelligence/events" not in source  # the fixed path remains encapsulated by the existing connector
    assert "raw_payload" not in "".join(BridgeCycleReceipt().__repr__())


def test_runtime_cli_exposes_explicit_one_shot_bridge_command(monkeypatch) -> None:
    from app.runtime.cli import main
    class _Bridge:
        def run_once(self): return BridgeCycleReceipt(claimed=1, delivered=1, accepted_new=1)
        def run_forever(self): return 1
    monkeypatch.setattr("app.intelligence.supabase_inbox_bridge.build_supabase_external_intelligence_bridge", lambda: _Bridge())
    output: list[str] = []
    assert main(["bridge-external-intelligence-inbox", "--once"], output=output.append) == 0
    assert "claimed=1" in output[0] and "accepted_new=1" in output[0]


@dataclass(frozen=True, slots=True)
class _View:
    evidence_domains: tuple[tuple[str, str], ...]
    evidence_status: str
    blockers: tuple[str, ...]


class _BrainSpy:
    def __init__(self, news: SQLiteNewsEvidenceStore) -> None:
        self._adapter = NewsCatalystEvidenceAdapter(news=news)
    def analyze_stock(self, identifier: str, *, context: BrainOutputContext, as_of: datetime) -> _View:
        artifacts = self._adapter.artifacts(identifier, as_of=as_of)
        news = next(item for item in artifacts if item.domain is IntelligenceEvidenceDomain.NEWS_CATALYSTS)
        return _View((("NEWS_CATALYSTS", news.availability.value),), "PARTIAL", ("OTHER_DOMAINS_MISSING",))


class _TestClientTransport:
    def __init__(self, client: TestClient) -> None: self.client = client
    def post_intelligence_event(self, *, endpoint: str, authorization: str, payload: bytes) -> IntelligenceIngestHttpResponse:
        assert endpoint == "http://127.0.0.1:8000/api/v1/intelligence/events"
        response = self.client.post("/api/v1/intelligence/events", content=payload, headers={"Authorization": authorization, "Content-Type": "application/json"})
        return IntelligenceIngestHttpResponse(response.status_code, response.json())


def test_isolated_synthetic_e2e_bridge_to_authenticated_hsi_canonical_news_and_shared_brain(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("HSI_EXTERNAL_INTELLIGENCE_INGEST_TOKEN", "test-local-token")
    path = tmp_path / "isolated.sqlite"; repository = SQLiteExternalIntelligenceRepository(path)
    app = create_app(external_intelligence_application_service=ExternalIntelligenceApplicationService(repository, clock=lambda: T))
    api = TestClient(app, raise_server_exceptions=False)
    connector = ExternalIntelligenceLiveConnector(backend_url="http://127.0.0.1:8000", ingest_token="test-local-token", transport=_TestClientTransport(api))
    inbox = _Inbox((row(),)); receipt = SupabaseExternalIntelligenceBridge(inbox=inbox, connector=connector, clock=lambda: T).run_once()
    assert receipt.delivered == receipt.accepted_new == 1 and repository.external_intelligence_row_counts() == {"events": 1, "evidence_versions": 1, "reevaluation_requests": 1}
    canonical = repository._connection.execute("SELECT canonical_event_id FROM external_intelligence_events").fetchone()[0]
    event = repository.get_event(canonical); evidence = repository.get_evidence_version(repository._connection.execute("SELECT evidence_version_id FROM external_intelligence_evidence_versions").fetchone()[0])
    news = SQLiteNewsEvidenceStore(path); ExternalIntelligenceNewsProjector(news).project_and_save(event, evidence)
    request_id = repository._connection.execute("SELECT request_id FROM external_intelligence_reevaluation_requests").fetchone()[0]
    result = ExternalIntelligenceReevaluationConsumer(repository, news, _BrainSpy(news)).consume(
        request_id, intelligence_as_of=evidence.received_at + timedelta(seconds=1),
    )
    assert result.disposition is ExternalIntelligenceReevaluationDisposition.COMPLETED_READ_ONLY and result.targets[0].news_state_after == "PARTIAL"
    api.close(); repository.close(); news._connection.close()
