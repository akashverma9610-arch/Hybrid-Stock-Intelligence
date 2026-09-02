from __future__ import annotations

import json
import hashlib
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.api.main import create_app
from app.intelligence.external_intelligence_application import ExternalIntelligenceApplicationService
from app.storage.sqlite_external_intelligence_repository import SQLiteExternalIntelligenceRepository


T = datetime(2026, 9, 1, 12, tzinfo=UTC)
PATH = "/api/v1/intelligence/events"


def payload(**changes):
    value = {
        "schema_version": "hsi-external-intelligence-event/v1",
        "producer_event_id": "test-rbi-1",
        "event_type": "MONETARY_POLICY",
        "title": "TEST_RBI_POLICY_EVENT",
        "country": "IN",
        "domain": "MACRO",
        "materiality": "HIGH",
        "policy_stage": "STATEMENT",
        "published_at": "2026-09-01T09:00:00+00:00",
        "discovered_at": "2026-09-01T10:00:00+00:00",
        "effective_at": "2026-09-01T09:30:00+00:00",
        "summary": "Synthetic RBI policy event V1",
        "what_changed": "The synthetic policy rate changed.",
        "primary_source": {
            "source_name": "Synthetic RBI",
            "source_type": "TEST",
            "source_reference": "https://invalid.test/rbi",
            "source_confidence": 0.9,
        },
        "supporting_sources": [{
            "source_name": "Synthetic bulletin",
            "source_type": "TEST",
            "source_reference": "https://invalid.test/bulletin",
            "source_confidence": 0.8,
        }],
        "facts": [{"content": "Synthetic policy fact", "source_references": ["https://invalid.test/rbi"], "confidence": 0.9}],
        "data_points": [{"name": "repo_rate", "value": "6.25", "unit": "percent", "period": "2026-09", "source_references": ["https://invalid.test/rbi"]}],
        "interpretation": [{"content": "Synthetic interpretation", "confidence": 0.7}],
        "inferences": [{"conclusion": "Synthetic inference", "confidence": 0.4}],
        "affected_sectors": ["FINANCIALS"],
        "affected_industries": ["BANKS"],
        "possible_company_exposure": [{
            "canonical_instrument_id": "NSE:INE090A01021",
            "external_company_name": "ICICI Bank",
            "exposure_type": "DIRECT",
            "confidence": 0.8,
            "verification_status": "VERIFIED",
        }],
        "event_confidence": 0.85,
        "exposure_confidence": 0.7,
        "time_horizon": "MEDIUM_TERM",
        "risks": ["Synthetic risk"],
        "counter_evidence": ["Synthetic counter evidence"],
        "why_hsi_should_care": "Synthetic test only.",
        "requires_hsi_analysis": True,
    }
    value.update(changes)
    return value


def fortis_payload(**changes):
    """Exact semantic Fortis fixture; the original null is intentionally invalid."""
    value = {
        "schema_version": "hsi-external-intelligence-event/v1",
        "producer_event_id": "hsi-fortis-daiichi-forensic-audit-20260831",
        "event_type": "GOVERNANCE",
        "title": "Delhi High Court orders forensic audit into historical Fortis shareholding dissipation and change in control",
        "country": "India",
        "domain": "Corporate Governance / Legal Proceedings / Healthcare",
        "materiality": "HIGH",
        "published_at": "2026-09-01T00:37:00+05:30",
        "discovered_at": "2026-09-01T12:24:08+05:30",
        "effective_at": "2026-08-31T16:31:00+05:30",
        "summary": "Fortis Healthcare disclosed that the Delhi High Court has ordered appointment of a forensic auditor to examine the historical dissipation of shareholding by its erstwhile promoters, the subsequent change in control, and the roles of relevant stakeholders. Fortis stated that the order imposes no liability, penalty or fine on the company.",
        "what_changed": "STATUS_CHANGE: a forensic audit that had previously remained under judicial consideration has now been ordered by the Delhi High Court, creating a formal investigative process into historical ownership/control transactions.",
        "primary_source": {
            "source_name": "Fortis Healthcare Limited exchange disclosure to NSE and BSE",
            "source_type": "LISTED_COMPANY_EXCHANGE_DISCLOSURE",
            "source_reference": "FHL/SEC/2026-27; attachment FORTIS_01092026003656_Intimation.pdf; dated 2026-09-01",
            "source_confidence": 0.99,
        },
        "supporting_sources": [
            {
                "source_name": "Delhi High Court judgment mirror on Indian Kanoon",
                "source_type": "COURT_JUDGMENT_MIRROR",
                "source_reference": "https://indiankanoon.org/doc/110055624/",
                "source_confidence": 0.97,
            },
            {
                "source_name": "Reuters",
                "source_type": "NEWS_WIRE",
                "source_reference": "https://www.reuters.com/world/india/indian-court-directs-forensic-auditor-appointment-daiichi-fortis-case-ihh-says-2026-09-01/",
                "source_confidence": 0.95,
            },
        ],
        "facts": [
            {
                "content": "The Delhi High Court directed appointment of a forensic auditor to conduct a factual enquiry into the dissipation of the Singh Brothers' shareholding in Fortis Healthcare, the subsequent change in control, and the role of relevant stakeholders.",
                "source_references": [
                    "FHL/SEC/2026-27; FORTIS_01092026003656_Intimation.pdf",
                    "https://indiankanoon.org/doc/110055624/",
                ],
                "confidence": 0.99,
            },
            {
                "content": "Fortis Healthcare stated that the order imposed no liability, penalty or fine on the company and that Fortis was neither a party to the original dispute nor a judgment debtor in the execution proceedings.",
                "source_references": ["FHL/SEC/2026-27; FORTIS_01092026003656_Intimation.pdf"],
                "confidence": 0.99,
            },
        ],
        "data_points": [],
        "interpretation": [{
            "content": "The legal/governance overhang has moved from a contingent possibility of forensic review to a court-ordered investigative process, increasing the need to track subsequent findings and disclosures even though no current financial liability was imposed.",
            "confidence": 0.93,
        }],
        "inferences": [{
            "conclusion": "Future forensic findings could create additional governance, transaction-review, reputational or legal risk for Fortis or other stakeholders, but no such adverse finding is established at this stage.",
            "confidence": 0.65,
            "verification_status": "UNVERIFIED_INFERENCE",
        }],
        "affected_sectors": ["Healthcare"],
        "affected_industries": ["Hospitals and Healthcare Services"],
        "possible_company_exposure": [{
            "external_company_name": "Fortis Healthcare Limited",
            "exposure_type": "DIRECT",
            "confidence": 1.0,
            "verification_status": None,
        }],
        "event_confidence": 0.98,
        "exposure_confidence": 1.0,
        "time_horizon": "Immediate legal/governance monitoring; forensic audit process may extend over multiple months",
        "risks": [],
        "counter_evidence": [
            "The Delhi High Court order itself imposes no liability, penalty or fine on Fortis Healthcare.",
            "Fortis Healthcare is not a judgment debtor in the underlying execution proceedings.",
        ],
        "why_hsi_should_care": "This is a formal governance/legal status change for a listed healthcare company. HSI should track later forensic findings or court/company disclosures separately from the current no-liability position.",
        "requires_hsi_analysis": True,
    }
    value.update(changes)
    return value


def _payload_fingerprint(value: dict) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def client(tmp_path, monkeypatch, *, token: str | None = "test-secret", repository_type=SQLiteExternalIntelligenceRepository):
    if token is None:
        monkeypatch.delenv("HSI_EXTERNAL_INTELLIGENCE_INGEST_TOKEN", raising=False)
    else:
        monkeypatch.setenv("HSI_EXTERNAL_INTELLIGENCE_INGEST_TOKEN", token)
    tmp_path.mkdir(parents=True, exist_ok=True)
    repository = repository_type(tmp_path / "intelligence-api.sqlite")
    service = ExternalIntelligenceApplicationService(repository, clock=lambda: T)
    app = create_app(external_intelligence_application_service=service)
    return repository, TestClient(app, raise_server_exceptions=False)


def headers(token: str = "test-secret") -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_authenticated_synthetic_e2e_new_retry_new_evidence_and_conflict(tmp_path, monkeypatch) -> None:
    repository, api = client(tmp_path, monkeypatch)
    first = api.post(PATH, json=payload(), headers=headers())
    retry = api.post(PATH, json=payload(), headers=headers())
    second = api.post(PATH, json=payload(summary="Synthetic RBI policy event V2"), headers=headers())
    conflict = api.post(PATH, json=payload(country="US", summary="conflict"), headers=headers())
    assert first.status_code == 201 and first.json()["disposition"] == "ACCEPTED_NEW"
    assert retry.status_code == 200 and retry.json()["disposition"] == "ACCEPTED_EXISTING"
    assert second.status_code == 201 and second.json()["disposition"] == "ACCEPTED_NEW_EVIDENCE"
    assert conflict.status_code == 409 and conflict.json()["disposition"] == "REJECTED_CONFLICT"
    assert repository.external_intelligence_row_counts() == {"events": 1, "evidence_versions": 2, "reevaluation_requests": 2}
    assert datetime.fromisoformat(first.json()["received_at"].replace("Z", "+00:00")) == T
    assert "test-secret" not in first.text and "Authorization" not in first.text
    api.close(); repository.close()


def test_request_maps_all_structured_evidence_without_fetching_references(tmp_path, monkeypatch) -> None:
    repository, api = client(tmp_path, monkeypatch)
    response = api.post(PATH, json=payload(), headers=headers())
    assert response.status_code == 201
    evidence = repository.get_evidence_version(response.json()["evidence_version_id"])
    assert evidence is not None
    assert len(evidence.facts) == len(evidence.data_points) == len(evidence.interpretation) == len(evidence.inferences) == 1
    assert evidence.supporting_sources[0].source_reference == "https://invalid.test/bulletin"
    assert evidence.company_exposures[0].canonical_instrument_id == "NSE:INE090A01021"
    assert evidence.effective_at is not None and evidence.risks == ("Synthetic risk",)
    source = __import__("inspect").getsource(__import__("app.api.routes.intelligence", fromlist=["router"]))
    assert not any(value in source for value in ("import requests", "import httpx", "urlopen(", "urllib.", "socket."))
    api.close(); repository.close()


@pytest.mark.parametrize("authorization", (None, "Bearer wrong", "Basic test-secret"))
def test_auth_failures_write_nothing(tmp_path, monkeypatch, authorization) -> None:
    repository, api = client(tmp_path, monkeypatch)
    request_headers = {} if authorization is None else {"Authorization": authorization}
    response = api.post(PATH, json=payload(), headers=request_headers)
    assert response.status_code == 401 and repository.external_intelligence_row_counts() == {"events": 0, "evidence_versions": 0, "reevaluation_requests": 0}
    api.close(); repository.close()


def test_auth_unavailable_and_protected_fields_fail_without_writes(tmp_path, monkeypatch) -> None:
    repository, api = client(tmp_path, monkeypatch, token=None)
    unavailable = api.post(PATH, json=payload(), headers=headers("anything"))
    assert unavailable.status_code == 503
    api.close(); repository.close()

    repository, api = client(tmp_path / "protected", monkeypatch)
    protected = api.post(PATH, json=payload(received_at="2000-01-01T00:00:00+00:00", producer_id="attacker"), headers=headers())
    assert protected.status_code == 422 and repository.external_intelligence_row_counts() == {"events": 0, "evidence_versions": 0, "reevaluation_requests": 0}
    api.close(); repository.close()


@pytest.mark.parametrize("change", (
    {"event_type": "NOT_AN_EVENT"},
    {"event_confidence": 1.1},
    {"published_at": "2026-09-01T09:00:00"},
    {"primary_source": {"source_name": "", "source_type": "TEST", "source_confidence": 0.9}},
    {"possible_company_exposure": [{"external_company_name": "Unmapped", "exposure_type": "DIRECT", "confidence": 0.8, "verification_status": "VERIFIED"}]},
))
def test_invalid_payloads_fail_closed_before_persistence(tmp_path, monkeypatch, change) -> None:
    repository, api = client(tmp_path, monkeypatch)
    response = api.post(PATH, json=payload(**change), headers=headers())
    assert response.status_code == 422 and response.json()["error"]["code"] == "INVALID_REQUEST"
    assert repository.external_intelligence_row_counts() == {"events": 0, "evidence_versions": 0, "reevaluation_requests": 0}
    api.close(); repository.close()


def test_fortis_null_exposure_is_strictly_rejected_and_corrected_v1c_payload_is_accepted(tmp_path, monkeypatch) -> None:
    invalid = fortis_payload()
    with pytest.raises(ValidationError) as captured:
        from app.api.schemas.intelligence import ExternalIntelligenceEventRequest
        ExternalIntelligenceEventRequest.model_validate(invalid)
    error = captured.value.errors()[0]
    assert error["loc"] == ("possible_company_exposure", 0, "verification_status")
    assert error["type"] == "literal_error" and error["input"] is None

    corrected = fortis_payload(possible_company_exposure=[{
        "external_company_name": "Fortis Healthcare Limited",
        "exposure_type": "DIRECT",
        "confidence": 1.0,
        "verification_status": "UNVERIFIED_INFERENCE",
    }])
    assert corrected["producer_event_id"] == invalid["producer_event_id"]
    assert _payload_fingerprint(corrected) == _payload_fingerprint(corrected)
    assert _payload_fingerprint(corrected) != _payload_fingerprint(invalid)
    assert corrected["inferences"][0]["verification_status"] == "UNVERIFIED_INFERENCE"
    assert "Future forensic findings" not in " ".join(item["content"] for item in corrected["facts"])

    repository, api = client(tmp_path, monkeypatch)
    accepted = api.post(PATH, json=corrected, headers=headers())
    assert accepted.status_code == 201 and accepted.json()["disposition"] == "ACCEPTED_NEW"
    evidence = repository.get_evidence_version(accepted.json()["evidence_version_id"])
    assert evidence is not None
    assert evidence.company_exposures[0].canonical_instrument_id is None
    assert evidence.company_exposures[0].verification_status == "UNVERIFIED_INFERENCE"
    assert evidence.inferences[0].conclusion.startswith("Future forensic findings")
    assert repository.external_intelligence_row_counts() == {"events": 1, "evidence_versions": 1, "reevaluation_requests": 1}
    assert "paper_trades" not in {row[0] for row in repository._connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    api.close(); repository.close()


def test_declared_payload_bound_is_256_kib_and_writes_nothing(tmp_path, monkeypatch) -> None:
    repository, api = client(tmp_path, monkeypatch)
    body = json.dumps(payload(summary="x" * (256 * 1024)))
    response = api.post(PATH, content=body, headers={**headers(), "Content-Type": "application/json"})
    assert response.status_code == 413 and response.json()["error"]["code"] == "INTELLIGENCE_EVENT_TOO_LARGE"
    assert repository.external_intelligence_row_counts() == {"events": 0, "evidence_versions": 0, "reevaluation_requests": 0}
    api.close(); repository.close()


def test_application_persistence_failure_returns_no_accepted_receipt_and_rolls_back(tmp_path, monkeypatch) -> None:
    class FailingRequestRepository(SQLiteExternalIntelligenceRepository):
        def save_reevaluation_request(self, value):
            raise RuntimeError("synthetic persistence failure")

    repository, api = client(tmp_path, monkeypatch, repository_type=FailingRequestRepository)
    response = api.post(PATH, json=payload(), headers=headers())
    assert response.status_code == 500 and "ACCEPTED" not in response.text
    assert repository.external_intelligence_row_counts() == {"events": 0, "evidence_versions": 0, "reevaluation_requests": 0}
    api.close(); repository.close()


def test_openapi_receipt_schema_and_no_side_effect_tables(tmp_path, monkeypatch) -> None:
    repository, api = client(tmp_path, monkeypatch)
    document = api.get("/openapi.json").json()
    operation = document["paths"][PATH]["post"]
    assert operation["operationId"] == "ingest_external_intelligence_event"
    assert "ExternalIntelligenceReceiptResponse" in document["components"]["schemas"]
    before = {row[0] for row in repository._connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    assert api.post(PATH, json=payload(), headers=headers()).status_code == 201
    after = {row[0] for row in repository._connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    assert before == after and "news_evidence" not in after and "paper_trades" not in after
    assert repository.audit_event_count() == 0
    api.close(); repository.close()
