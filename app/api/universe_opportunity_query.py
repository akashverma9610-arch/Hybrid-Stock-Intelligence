"""Read-only public projection for persisted universe opportunity snapshots."""
from __future__ import annotations

from typing import Protocol

from app.api.errors import APIRequestError
from app.universe_analysis.models import UniverseAnalysisJob, UniverseOpportunitySnapshot
from app.universe_analysis.service import CoreUniverseAnalysisStore


class UniverseOpportunityQueryService(Protocol):
    def latest(self, *, limit: int | None = None, sector: str | None = None) -> UniverseOpportunitySnapshot: ...
    def job(self, job_id: str) -> UniverseAnalysisJob: ...


class CoreSnapshotUniverseOpportunityQueryService:
    def __init__(self, store: CoreUniverseAnalysisStore) -> None: self._store = store

    def latest(self, *, limit: int | None = None, sector: str | None = None) -> UniverseOpportunitySnapshot:
        value = self._store.latest_opportunity()
        if value is None:
            raise APIRequestError(
                status_code=503,
                code="OPPORTUNITY_SET_UNAVAILABLE",
                message="No persisted universe opportunity snapshot is available.",
            )
        items = tuple(item for item in value.opportunities if sector is None or item.sector == sector)
        if limit is not None: items = items[:limit]
        from dataclasses import replace
        return replace(value, opportunities=items)

    def job(self, job_id: str) -> UniverseAnalysisJob:
        value = self._store.get_job(job_id)
        if value is None:
            raise APIRequestError(
                status_code=404,
                code="UNIVERSE_ANALYSIS_JOB_NOT_FOUND",
                message="Universe-analysis job was not found.",
            )
        return value


class UnavailableUniverseOpportunityQueryService:
    def latest(self, **kwargs):
        raise APIRequestError(503, "OPPORTUNITY_SET_UNAVAILABLE", "No persisted universe opportunity snapshot is available.")
    def job(self, job_id: str):
        raise APIRequestError(503, "OPPORTUNITY_SET_UNAVAILABLE", "Universe-analysis status is not available.")
