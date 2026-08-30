"""Minimal typed settings for the HTTP application."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Mapping

from app.storage.database import DatabaseSettings


@dataclass(frozen=True, slots=True)
class APISettings:
    environment: str = "development"
    application_name: str = "NSE Stock Manager"
    api_version: str = "v1"
    application_version: str = "0.1.0"
    cors_origins: tuple[str, ...] = ("http://localhost:3000", "http://127.0.0.1:3000")
    database: DatabaseSettings = DatabaseSettings()
    local_connection_management_enabled: bool | None = None

    @property
    def connection_management_available(self) -> bool:
        if self.local_connection_management_enabled is not None:
            return self.local_connection_management_enabled
        return self.environment.lower() in {"development", "local", "test"}

    @classmethod
    def from_environment(cls, environ: Mapping[str, str] | None = None) -> "APISettings":
        source = os.environ if environ is None else environ
        environment = source.get("APP_ENV", "development")
        raw_origins = source.get("CORS_ORIGINS")
        if raw_origins is None:
            origins = ("http://localhost:3000", "http://127.0.0.1:3000") if environment.lower() == "development" else ()
        else:
            origins = tuple(origin.strip() for origin in raw_origins.split(",") if origin.strip())
        if "*" in origins:
            raise ValueError("CORS_ORIGINS must list explicit origins; wildcard origins are not supported.")
        raw_connection_management = source.get("LOCAL_CONNECTION_MANAGEMENT_ENABLED")
        enabled = None if raw_connection_management is None else raw_connection_management.strip().lower() in {"1", "true", "yes"}
        return cls(
            environment=environment,
            application_name=source.get("APP_NAME", "NSE Stock Manager"),
            api_version=source.get("API_VERSION", "v1"),
            cors_origins=origins,
            database=DatabaseSettings.from_environment(source),
            local_connection_management_enabled=enabled,
        )
