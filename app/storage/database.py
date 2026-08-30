"""Lazy database configuration, connection, transaction, and readiness boundary.

No database connection is opened by importing this module or constructing a
factory. SQLite stays the safe local/test default; PostgreSQL is explicit.
"""

from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Iterator, Mapping


class DatabaseBackend(StrEnum):
    SQLITE = "sqlite"
    POSTGRESQL = "postgresql"


class DatabaseStorageMode(StrEnum):
    PERSISTENT_SQLITE = "PERSISTENT_SQLITE"
    IN_MEMORY_SQLITE = "IN_MEMORY_SQLITE"
    POSTGRESQL = "POSTGRESQL"


@dataclass(frozen=True, slots=True)
class DatabaseSettings:
    backend: DatabaseBackend = DatabaseBackend.SQLITE
    url: str = "sqlite:///:memory:"

    @classmethod
    def from_environment(cls, environ: Mapping[str, str] | None = None) -> "DatabaseSettings":
        source = os.environ if environ is None else environ
        try:
            backend = DatabaseBackend(source.get("DATABASE_BACKEND", DatabaseBackend.SQLITE.value).lower())
        except ValueError as error:
            raise ValueError("DATABASE_BACKEND must be sqlite or postgresql.") from error
        supplied_url = source.get("DATABASE_URL")
        if backend is DatabaseBackend.SQLITE:
            url = supplied_url or "sqlite:///:memory:"
            if not url.startswith("sqlite:///"):
                raise ValueError("SQLite DATABASE_URL must use sqlite:///.")
        else:
            if not supplied_url:
                raise ValueError("PostgreSQL DATABASE_URL is required when DATABASE_BACKEND=postgresql.")
            url = supplied_url
            if not (url.startswith("postgresql://") or url.startswith("postgres://")):
                raise ValueError("PostgreSQL DATABASE_URL must use postgresql:// or postgres://.")
        return cls(backend=backend, url=url)

    @classmethod
    def local_runtime(cls, environ: Mapping[str, str] | None = None) -> "DatabaseSettings":
        """Persistent default for explicit local runtime commands only.

        Unit/API construction keeps the in-memory default for test isolation;
        an operator explicitly invoking a data command must not accidentally
        import an official universe into a process-only database.
        """
        source = os.environ if environ is None else environ
        if source.get("DATABASE_URL") or source.get("DATABASE_BACKEND") == "postgresql":
            return cls.from_environment(source)
        return cls(DatabaseBackend.SQLITE, "sqlite:///data/nse_stock_manager.db")

    @property
    def storage_mode(self) -> DatabaseStorageMode:
        if self.backend is DatabaseBackend.POSTGRESQL:
            return DatabaseStorageMode.POSTGRESQL
        return DatabaseStorageMode.IN_MEMORY_SQLITE if self.url.endswith(":memory:") else DatabaseStorageMode.PERSISTENT_SQLITE


class DatabaseConnectionFactory:
    """Explicit connection/transaction factory; API routes never own commits."""

    def __init__(self, settings: DatabaseSettings) -> None:
        self.settings = settings

    def connect(self):
        if self.settings.backend is DatabaseBackend.SQLITE:
            connection = sqlite3.connect(_sqlite_path(self.settings.url))
            connection.row_factory = sqlite3.Row
            return connection
        try:
            import psycopg
        except ImportError as error:  # pragma: no cover - dependency-installed production path
            raise RuntimeError("PostgreSQL support requires the optional production database dependencies.") from error
        return psycopg.connect(self.settings.url)

    @contextmanager
    def transaction(self) -> Iterator[object]:
        connection = self.connect()
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()


@dataclass(frozen=True, slots=True)
class DatabaseReadiness:
    ready: bool
    backend: DatabaseBackend
    detail: str
    storage_mode: DatabaseStorageMode | None = None


class DatabaseReadinessProbe:
    """Explicit future readiness probe; liveness does not invoke it."""

    def __init__(self, connections: DatabaseConnectionFactory) -> None:
        self._connections = connections

    def check(self) -> DatabaseReadiness:
        try:
            connection = self._connections.connect()
            try:
                cursor = connection.cursor()
                cursor.execute("SELECT 1")
                cursor.fetchone()
            finally:
                connection.close()
        except Exception:
            return DatabaseReadiness(False, self._connections.settings.backend, "DATABASE_UNAVAILABLE", self._connections.settings.storage_mode)
        return DatabaseReadiness(True, self._connections.settings.backend, "DATABASE_READY", self._connections.settings.storage_mode)


def _sqlite_path(url: str) -> str:
    path = url.removeprefix("sqlite:///")
    if path == ":memory:":
        return path
    return str(Path(path))
