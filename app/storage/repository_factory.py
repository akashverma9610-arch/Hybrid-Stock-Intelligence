"""Explicit backend selection; callers opt in and routes stay repository-agnostic."""
from app.storage.database import DatabaseBackend, DatabaseConnectionFactory, DatabaseSettings
from app.storage.postgresql_core_api_snapshot_repository import PostgreSQLCoreApiSnapshotRepository
from app.storage.sqlite_core_api_snapshot_repository import SQLiteCoreApiSnapshotRepository


def create_core_api_snapshot_repository(settings: DatabaseSettings):
    if settings.backend is DatabaseBackend.SQLITE:
        return SQLiteCoreApiSnapshotRepository(settings.url.removeprefix("sqlite:///"))
    return PostgreSQLCoreApiSnapshotRepository(DatabaseConnectionFactory(settings))
