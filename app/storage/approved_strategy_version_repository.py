"""Narrow shared contract for the first PostgreSQL migration family."""

from __future__ import annotations

from typing import Protocol

from app.backtest.promotion import ApprovedStrategyVersion


class ApprovedStrategyVersionRepository(Protocol):
    def save_approved_strategy_version(self, value: ApprovedStrategyVersion) -> None: ...
    def get_approved_strategy_version(self, approved_id: str) -> ApprovedStrategyVersion | None: ...
    def list_approved_strategy_versions(self) -> tuple[ApprovedStrategyVersion, ...]: ...
