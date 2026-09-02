"""V1F connector contract tests; all delivery stays isolated from a real Desk."""
from __future__ import annotations

import json
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.api.schemas.intelligence import ExternalIntelligenceEventRequest
from app.intelligence.external_intelligence_live_connector import (
    DeliveryStatus,
    ExternalIntelligenceLiveConnector,
    HSI_ORIGIN_ENVIRONMENT_KEY,
    INGEST_TOKEN_ENVIRONMENT_KEY,
    IntelligenceIngestHttpResponse,
    LiveConnectorConfigurationError,
)


T = datetime(2026, 9, 1, 12, tzinfo=UTC)
BASE_URL = "https://hsi.example.test"
SECRET = "test-only-external-intelligence-secret"


class _Transport:
    def __init__(self, *responses) -> None:
        self.responses = list(responses)
        self.calls: list[tuple[str, str, bytes]] = []

    def post_intelligence_event(self, *, endpoint: str, authorization: str, payload: bytes):
        self.calls.append((endpoint, authorization, payload))
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def _payload(**changes) -> dict:
    value = {
        "schema_version": "hsi-external-intelligence-event/v1",
        "producer_event_id": "desk-rbi-2026-09-01-001",
        "event_type": "MONETARY_POLICY",
        "title": "Live-like RBI policy event",
        "country": "IN",
        "domain": "MACRO",
        "materiality": "HIGH",
        "policy_stage": "STATEMENT",
        "published_at": "2026-09-01T09:00:00+00:00",
        "discovered_at": "2026-09-01T10:00:00+00:00",
        "effective_at": "2026-09-01T10:30:00+00:00",
        "summary": "A structured, live-like policy summary.",
        "what_changed": "The policy communication changed.",
        "primary_source": {
            "source_name": "RBI", "source_type": "OFFICIAL",
            "source_reference": "https://example.test/rbi", "source_confidence": 0.95,
        },
        "supporting_sources": [{
            "source_name": "PIB", "source_type": "OFFICIAL",
            "source_reference": "https://example.test/pib", "source_confidence": 0.85,
        }],
        "facts": [{"content": "A source-grounded fact.", "source_references": ["https://example.test/rbi"], "confidence": 0.95}],
        "data_points": [{"name": "policy_rate", "value": "6.25", "unit": "percent", "period": "2026-09", "source_references": ["https://example.test/rbi"]}],
        "interpretation": [{"content": "A bounded interpretation.", "confidence": 0.7}],
        "inferences": [{"conclusion": "An unverified inference.", "confidence": 0.4}],
        "affected_sectors": ["FINANCIALS"], "affected_industries": ["BANKS"],
        "possible_company_exposure": [{
            "canonical_instrument_id": "NSE:INE090A01021", "external_company_name": "ICICI Bank",
            "exposure_type": "DIRECT", "confidence": 0.8, "verification_status": "VERIFIED",
        }],
        "event_confidence": 0.9, "exposure_confidence": 0.8, "time_horizon": "MEDIUM_TERM",
        "risks": ["A known risk."], "counter_evidence": ["A known counter-evidence item."],
        "why_hsi_should_care": "Structured evidence only.", "requires_hsi_analysis": True,
    }
    value.update(changes)
    return value


def _receipt(disposition: str = "ACCEPTED_NEW") -> IntelligenceIngestHttpResponse:
    return IntelligenceIngestHttpResponse(201 if disposition != "ACCEPTED_EXISTING" else 200, {
        "disposition": disposition,
        "canonical_event_id": "external-event:abc",
        "evidence_version_id": "external-evidence:def",
        "received_at": T.isoformat(),
        "schema_version": "hsi-external-intelligence-event/v1",
        "event_fingerprint": "sha256:event",
        "evidence_fingerprint": "sha256:evidence",
        "reevaluation_requested": True,
        "reevaluation_request_id": "intelligence-reevaluation:ghi",
        "blocker": None,
    })


def test_connector_sends_exact_v1c_payload_with_bearer_auth_and_preserves_desk_identity() -> None:
    transport = _Transport(_receipt())
    connector = ExternalIntelligenceLiveConnector(backend_url=BASE_URL, ingest_token=SECRET, transport=transport)

    result = connector.ingest_intelligence_event(_payload())

    endpoint, authorization, body = transport.calls[0]
    mapped = json.loads(body)
    assert endpoint == BASE_URL + "/api/v1/intelligence/events"
    assert authorization == "Bearer " + SECRET
    assert result.delivery_status is DeliveryStatus.DELIVERED and result.hsi_disposition == "ACCEPTED_NEW"
    assert result.canonical_event_id == "external-event:abc" and result.reevaluation_request_id == "intelligence-reevaluation:ghi"
    assert mapped["producer_event_id"] == _payload()["producer_event_id"]
    expected = ExternalIntelligenceEventRequest.model_validate(_payload()).model_dump(mode="json")
    for key in ("facts", "data_points", "interpretation", "inferences", "supporting_sources", "possible_company_exposure", "risks", "counter_evidence", "effective_at"):
        assert mapped[key] == expected[key]
    assert not {"producer_id", "received_at", "canonical_event_id", "evidence_version_id", "reevaluation_request_id"} & set(mapped)


@pytest.mark.parametrize("disposition", ("ACCEPTED_NEW", "ACCEPTED_EXISTING", "ACCEPTED_NEW_EVIDENCE"))
def test_each_accepted_hsi_receipt_maps_to_delivered(disposition: str) -> None:
    connector = ExternalIntelligenceLiveConnector(backend_url=BASE_URL, ingest_token=SECRET, transport=_Transport(_receipt(disposition)))
    result = connector.ingest_intelligence_event(_payload())
    assert result.delivery_status is DeliveryStatus.DELIVERED and result.hsi_disposition == disposition
    assert result.evidence_version_id == "external-evidence:def" and result.received_at == T.isoformat()


def test_exact_retry_preserves_producer_event_id_and_never_creates_a_client_side_duplicate() -> None:
    transport = _Transport(_receipt("ACCEPTED_NEW"), _receipt("ACCEPTED_EXISTING"))
    connector = ExternalIntelligenceLiveConnector(backend_url=BASE_URL, ingest_token=SECRET, transport=transport)
    event = _payload()
    first, retry = connector.ingest_intelligence_event(event), connector.ingest_intelligence_event(event)
    sent_ids = [json.loads(call[2])["producer_event_id"] for call in transport.calls]
    assert (first.delivery_status, retry.delivery_status) == (DeliveryStatus.DELIVERED, DeliveryStatus.DELIVERED)
    assert (first.hsi_disposition, retry.hsi_disposition) == ("ACCEPTED_NEW", "ACCEPTED_EXISTING")
    assert sent_ids == [event["producer_event_id"], event["producer_event_id"]]


@pytest.mark.parametrize("response,expected", (
    (IntelligenceIngestHttpResponse(401, {"error": {"code": "INTELLIGENCE_AUTH_FAILED"}}), "INTELLIGENCE_AUTH_FAILED"),
    (IntelligenceIngestHttpResponse(422, {"error": {"code": "INVALID_REQUEST"}}), "INVALID_REQUEST"),
    (ConnectionError("offline"), "HSI_NETWORK_UNAVAILABLE"),
))
def test_auth_schema_and_network_failures_remain_pending(response, expected: str) -> None:
    connector = ExternalIntelligenceLiveConnector(backend_url=BASE_URL, ingest_token=SECRET, transport=_Transport(response))
    result = connector.ingest_intelligence_event(_payload())
    assert result.delivery_status is DeliveryStatus.PENDING_DELIVERY and result.failure_code == expected


def test_invalid_desk_schema_is_pending_without_any_network_attempt() -> None:
    transport = _Transport(_receipt())
    connector = ExternalIntelligenceLiveConnector(backend_url=BASE_URL, ingest_token=SECRET, transport=transport)
    result = connector.ingest_intelligence_event(_payload(producer_id="not-allowed", event_type="UNKNOWN"))
    assert result.delivery_status is DeliveryStatus.PENDING_DELIVERY and result.failure_code == "HSI_SCHEMA_REJECTED"
    assert not transport.calls


def test_public_origin_and_token_environment_configuration_fail_closed(monkeypatch) -> None:
    monkeypatch.delenv(INGEST_TOKEN_ENVIRONMENT_KEY, raising=False)
    monkeypatch.delenv(HSI_ORIGIN_ENVIRONMENT_KEY, raising=False)
    with pytest.raises(LiveConnectorConfigurationError, match="credential"):
        ExternalIntelligenceLiveConnector.from_environment(transport=_Transport(_receipt()))
    monkeypatch.setenv(INGEST_TOKEN_ENVIRONMENT_KEY, SECRET)
    with pytest.raises(LiveConnectorConfigurationError, match="HTTPS origin"):
        ExternalIntelligenceLiveConnector.from_environment(transport=_Transport(_receipt()))
    monkeypatch.setenv(HSI_ORIGIN_ENVIRONMENT_KEY, "http://127.0.0.1:8000")
    with pytest.raises(LiveConnectorConfigurationError, match="public HTTPS"):
        ExternalIntelligenceLiveConnector.from_environment(transport=_Transport(_receipt()))
    transport = _Transport(_receipt())
    monkeypatch.setenv(HSI_ORIGIN_ENVIRONMENT_KEY, BASE_URL)
    connector = ExternalIntelligenceLiveConnector.from_environment(transport=transport)
    assert connector.ingest_intelligence_event(_payload()).delivery_status is DeliveryStatus.DELIVERED
    assert transport.calls[0][0] == BASE_URL + "/api/v1/intelligence/events"


def test_valid_but_oversized_event_is_pending_without_network_attempt() -> None:
    transport = _Transport(_receipt())
    connector = ExternalIntelligenceLiveConnector(backend_url=BASE_URL, ingest_token=SECRET, transport=transport)
    result = connector.ingest_intelligence_event(_payload(facts=[{
        "content": "x" * 3_000, "source_references": (), "confidence": 0.8,
    }] * 100))
    assert result.delivery_status is DeliveryStatus.PENDING_DELIVERY and result.failure_code == "HSI_PAYLOAD_TOO_LARGE"
    assert not transport.calls


def test_connector_has_only_the_fixed_event_endpoint_and_never_serializes_secret() -> None:
    with pytest.raises(LiveConnectorConfigurationError):
        ExternalIntelligenceLiveConnector(backend_url=BASE_URL + "/anything", ingest_token=SECRET)
    with pytest.raises(LiveConnectorConfigurationError):
        ExternalIntelligenceLiveConnector(backend_url="http://hsi.example.test", ingest_token=SECRET)
    connector = ExternalIntelligenceLiveConnector(backend_url=BASE_URL, ingest_token=SECRET, transport=_Transport(_receipt()))
    result = connector.ingest_intelligence_event(_payload())
    assert SECRET not in repr(connector) and SECRET not in repr(result) and SECRET not in str(asdict(result))
    source = (Path(__file__).parents[2] / "app" / "intelligence" / "external_intelligence_live_connector.py").read_text(encoding="utf-8")
    assert "def ingest_intelligence_event" in source
    assert source.count("/api/v1/intelligence/events") == 1
    assert not any(item in source for item in ("/portfolio", "/broker", "/orders", "intelligence:admin", "intelligence:trade", "print(", "logging."))
