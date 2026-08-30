import pytest
from app.news.store import PostgreSQLNewsEvidenceStore
from app.storage.database import DatabaseBackend, DatabaseConnectionFactory, DatabaseSettings

def test_news_postgresql_adapter_requires_explicit_postgres_backend():
    with pytest.raises(ValueError): PostgreSQLNewsEvidenceStore(DatabaseConnectionFactory(DatabaseSettings(DatabaseBackend.SQLITE,"sqlite:///:memory:")))
