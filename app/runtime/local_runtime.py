"""Explicit, fail-closed configuration for the Windows local operator runtime."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Mapping

from app.storage.database import DatabaseBackend, DatabaseSettings, DatabaseStorageMode


LOCAL_OPERATOR_RUNTIME_ENV = "HSI_LOCAL_OPERATOR_RUNTIME"
LOCAL_DATABASE_URL = "sqlite:///data/nse_stock_manager.db"
LOCAL_CORS_ORIGINS = ("http://localhost:3001", "http://127.0.0.1:3001")


def local_operator_runtime_enabled(environ: Mapping[str, str] | None = None) -> bool:
    source = os.environ if environ is None else environ
    return source.get(LOCAL_OPERATOR_RUNTIME_ENV, "").strip().lower() in {"1", "true", "yes"}


def validate_local_operator_runtime(
    database: DatabaseSettings,
    *,
    environ: Mapping[str, str] | None = None,
    repository_root: Path | None = None,
) -> Path:
    """Return the approved local database path or fail before serving requests.

    This is deliberately opt-in. Test factories remain free to use isolated
    in-memory SQLite databases unless an operator explicitly enables this mode.
    """
    if not local_operator_runtime_enabled(environ):
        return Path()
    if database.backend is not DatabaseBackend.SQLITE or database.storage_mode is not DatabaseStorageMode.PERSISTENT_SQLITE:
        raise ValueError("HSI_LOCAL_RUNTIME_REQUIRES_PERSISTENT_DATABASE")
    if database.url != LOCAL_DATABASE_URL:
        raise ValueError("HSI_LOCAL_RUNTIME_REQUIRES_PERSISTENT_DATABASE")
    root = (repository_root or Path.cwd()).resolve()
    path = (root / "data" / "nse_stock_manager.db").resolve()
    if not path.is_file():
        raise ValueError("HSI_LOCAL_RUNTIME_REQUIRES_PERSISTENT_DATABASE")
    return path
