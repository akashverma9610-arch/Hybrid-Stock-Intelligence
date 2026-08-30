from fastapi import APIRouter, Depends, Query

from app.api.dependencies import get_universe_opportunity_query_service
from app.api.schemas.opportunities import OpportunitySnapshotResponse, UniverseAnalysisJobResponse
from app.api.universe_opportunity_query import UniverseOpportunityQueryService


router = APIRouter(tags=["opportunities"])


@router.get("/opportunities", response_model=OpportunitySnapshotResponse)
def opportunities(limit: int | None = Query(default=None, ge=1, le=100), sector: str | None = Query(default=None, min_length=1),
                  service: UniverseOpportunityQueryService = Depends(get_universe_opportunity_query_service)) -> OpportunitySnapshotResponse:
    value = service.latest(limit=limit, sector=sector)
    return OpportunitySnapshotResponse(
        as_of=value.as_of, universe_count=value.universe_count, eligible_count=value.eligible_count,
        analyzed_count=value.analyzed_count, complete_count=value.complete_count, partial_count=value.partial_count,
        unavailable_count=value.unavailable_count, qualified_candidate_count=value.qualified_candidate_count,
        warnings=value.warnings, freshness=value.freshness,
        coverage_status=value.coverage_status.value,
        opportunities=tuple(item.__dict__ if hasattr(item, "__dict__") else {field: getattr(item, field) for field in item.__dataclass_fields__} for item in value.opportunities),
    )


@router.get("/universe-analysis/jobs/{job_id}", response_model=UniverseAnalysisJobResponse)
def universe_analysis_job(job_id: str, service: UniverseOpportunityQueryService = Depends(get_universe_opportunity_query_service)) -> UniverseAnalysisJobResponse:
    value = service.job(job_id)
    return UniverseAnalysisJobResponse(**{field: getattr(value, field) for field in UniverseAnalysisJobResponse.model_fields})
