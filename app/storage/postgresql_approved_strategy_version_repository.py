"""PostgreSQL adapter for immutable approved strategy-version storage only.

Promotion/review/activation families deliberately remain in SQLite until their
own migrations are designed. This adapter persists already-authorized frozen
versions; it does not replace governance-service validation.
"""

from __future__ import annotations

import json

from app.backtest.promotion import ApprovedStrategyVersion
from app.backtest.promotion_serialization import approved_from, dump as promotion_dump
from app.storage.database import DatabaseBackend, DatabaseConnectionFactory


class PostgreSQLApprovedStrategyVersionRepository:
    def __init__(self, connections: DatabaseConnectionFactory) -> None:
        if connections.settings.backend is not DatabaseBackend.POSTGRESQL:
            raise ValueError("PostgreSQL approved-version repository requires DATABASE_BACKEND=postgresql.")
        self._connections = connections

    def save_approved_strategy_version(self, value: ApprovedStrategyVersion) -> None:
        payload = json.dumps(promotion_dump(value), sort_keys=True, separators=(",", ":"))
        try:
            with self._connections.transaction() as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        """INSERT INTO approved_strategy_versions (
                            approved_id, strategy_id, version, parent_approved_id, proposal_id, review_id,
                            candidate_id, config_fingerprints, approved_at, effective_from, status,
                            methodology_notes, fingerprint, payload_json
                        ) VALUES (
                            %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s, %s::jsonb, %s, %s::jsonb
                        )""",
                        (
                            value.approved_id, value.strategy_id, value.version, value.parent_approved_id,
                            value.proposal_id, value.review_id, value.candidate_id,
                            json.dumps(value.config_fingerprints), value.approved_at, value.effective_from,
                            value.status.value, json.dumps(value.methodology_notes), value.fingerprint, payload,
                        ),
                    )
        except Exception as error:
            if getattr(error, "sqlstate", None) == "23505":
                raise ValueError("Approved strategy versions are immutable and cannot be overwritten.") from error
            raise

    def get_approved_strategy_version(self, approved_id: str) -> ApprovedStrategyVersion | None:
        with self._connections.transaction() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT payload_json FROM approved_strategy_versions WHERE approved_id=%s", (approved_id,))
                row = cursor.fetchone()
        if row is None:
            return None
        payload = row[0] if isinstance(row[0], dict) else json.loads(row[0])
        return approved_from(payload)

    def list_approved_strategy_versions(self) -> tuple[ApprovedStrategyVersion, ...]:
        with self._connections.transaction() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT payload_json FROM approved_strategy_versions ORDER BY effective_from, approved_id")
                rows = cursor.fetchall()
        return tuple(approved_from(row[0] if isinstance(row[0], dict) else json.loads(row[0])) for row in rows)
