from datetime import UTC, datetime
from fastapi.testclient import TestClient

from app.api.main import create_app
from app.api.settings import APISettings
from app.connections.credentials import InMemoryCredentialStore
from app.connections.repository import SQLiteConnectionProfileRepository
from app.connections.service import ProviderConnectionService
from app.connections.models import AccessState, ConnectionStatus, ConnectionTestResult

T=datetime(2026,8,23,tzinfo=UTC)
def test_gnews_connection_api_redacts_secret_and_clears():
    store=InMemoryCredentialStore();service=ProviderConnectionService(SQLiteConnectionProfileRepository(),store,{},clock=lambda:T)
    client=TestClient(create_app(api_settings=APISettings(local_connection_management_enabled=True),connection_service=service))
    assert client.get("/api/v1/connections/gnews").status_code==200
    saved=client.put("/api/v1/connections/gnews",json={"api_key":"secret-news-key"})
    assert saved.status_code==200 and saved.json()["credential_fields_configured"]=={"api_key":True} and "secret-news-key" not in saved.text
    cleared=client.delete("/api/v1/connections/gnews/credentials")
    assert cleared.status_code==200 and cleared.json()["credential_fields_configured"]=={"api_key":False}

class SuccessfulGNewsTester:
    def test(self, profile, credentials): return ConnectionTestResult("gnews",profile.connection_id,ConnectionStatus.CONNECTED,AccessState.AVAILABLE,AccessState.NOT_TESTED,"PASS",T,canonical_normalization="PASS")
class FailedGNewsTester:
    def test(self, profile, credentials): return ConnectionTestResult("gnews",profile.connection_id,ConnectionStatus.DEGRADED,AccessState.UNAVAILABLE,AccessState.NOT_TESTED,"FAIL",T,error_code="RATE_LIMITED")
def test_gnews_connection_validation_transitions_without_network():
    store=InMemoryCredentialStore(); service=ProviderConnectionService(SQLiteConnectionProfileRepository(),store,{"gnews":SuccessfulGNewsTester()},clock=lambda:T)
    assert service.gnews_profile().status.value=="NOT_CONFIGURED"
    service.update_gnews({"api_key":"secret"}); assert service.gnews_profile().status.value=="CONFIGURED"
    assert service.test_gnews().status.value=="CONNECTED" and service.gnews_profile().last_success_at==T
    failed=ProviderConnectionService(SQLiteConnectionProfileRepository(),store,{"gnews":FailedGNewsTester()},clock=lambda:T)
    assert failed.test_gnews().status.value=="DEGRADED"
