"""Read-only local-runtime readiness summary for operators and the Dev Console."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

from app.runtime.local_runtime import LOCAL_DATABASE_URL
from app.storage.database import DatabaseBackend, DatabaseSettings


@dataclass(frozen=True, slots=True)
class LocalRuntimeReadiness:
    database_backend: str
    storage_mode: str
    database_path: str | None
    sqlite_integrity: str | None
    foreign_key_violations: int | None
    financial_facts: int | None
    corporate_filings: int | None
    portfolio_snapshots: int | None
    bse_receipts: int | None
    bse_plan_id: str | None
    bse_status: str
    market_wide_watch_status: str
    warnings: tuple[str, ...]


class LocalRuntimeReadinessService:
    """Open a short-lived SQLite read connection; never starts or resumes work."""

    def __init__(self, database: DatabaseSettings, *, market_wide_watch_service=None, repository=None) -> None:
        self._database = database
        self._watch = market_wide_watch_service
        self._repository = repository

    def status(self) -> LocalRuntimeReadiness:
        if self._database.backend is not DatabaseBackend.SQLITE or self._database.url.endswith(":memory:"):
            return LocalRuntimeReadiness(
                database_backend=self._database.backend.value,
                storage_mode=self._database.storage_mode.value,
                database_path=None,
                sqlite_integrity=None,
                foreign_key_violations=None,
                financial_facts=None,
                corporate_filings=None,
                portfolio_snapshots=None,
                bse_receipts=None,
                bse_plan_id=None,
                bse_status="NOT_CONFIGURED",
                market_wide_watch_status=self._watch_status(),
                warnings=("PERSISTENT_LOCAL_DATABASE_NOT_CONFIGURED",),
            )
        path = Path(self._database.url.removeprefix("sqlite:///"))
        if not path.is_file():
            return LocalRuntimeReadiness(
                database_backend=self._database.backend.value,
                storage_mode=self._database.storage_mode.value,
                database_path=str(path),
                sqlite_integrity=None,
                foreign_key_violations=None,
                financial_facts=None,
                corporate_filings=None,
                portfolio_snapshots=None,
                bse_receipts=None,
                bse_plan_id=None,
                bse_status="NOT_CONFIGURED",
                market_wide_watch_status=self._watch_status(),
                warnings=("LOCAL_DATABASE_MISSING",),
            )
        with sqlite3.connect(path) as connection:
            integrity = str(connection.execute("PRAGMA integrity_check").fetchone()[0])
            fk_violations = len(connection.execute("PRAGMA foreign_key_check").fetchall())
            tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
            def count(name: str) -> int | None:
                return int(connection.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0]) if name in tables else None
            bse_plan_id, bse_receipts, bse_status = self._bse_status()
            return LocalRuntimeReadiness(
                database_backend=self._database.backend.value,
                storage_mode=self._database.storage_mode.value,
                database_path=str(path),
                sqlite_integrity=integrity,
                foreign_key_violations=fk_violations,
                financial_facts=count("financial_facts"),
                corporate_filings=count("corporate_filings"),
                portfolio_snapshots=count("portfolio_snapshots"),
                bse_receipts=bse_receipts,
                bse_plan_id=bse_plan_id,
                bse_status=bse_status,
                market_wide_watch_status=self._watch_status(),
                warnings=(),
            )

    def _watch_status(self) -> str:
        if self._watch is None:
            return "NOT_CONFIGURED"
        return "AVAILABLE" if self._watch.latest() is not None else "UNAVAILABLE"

    def _bse_status(self) -> tuple[str | None, int | None, str]:
        if self._repository is None:
            return None, None, "NOT_CONFIGURED"
        # This imports only the immutable receipt reader. It performs no BSE
        # request, staging, acquisition, retry, or plan mutation.
        from app.fundamentals.bse_nifty500_acquisition import BseFinancialAcquisitionStore

        store = BseFinancialAcquisitionStore(self._repository)
        plan = store.latest_plan()
        if plan is None:
            return None, 0, "NO_PLAN"
        run_id = "bse-financial-run:" + plan.fingerprint[7:39]
        receipts = store.latest_receipts(run_id)
        halts = store.provider_halts(run_id)
        return plan.plan_id, len(receipts), "PROVIDER_HALTED" if halts else "RESUMABLE"
