from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.dependencies import get_portfolio_analysis_job_service
from app.api.errors import APIRequestError
from app.api.schemas.portfolio_analysis import PortfolioAnalysisJobListResponse, PortfolioAnalysisJobRequest, PortfolioAnalysisJobResponse
from app.portfolio_analysis.service import PortfolioAnalysisError, PortfolioAnalysisJobService

router = APIRouter(prefix="/portfolio/analysis-jobs", tags=["portfolio"])

@router.post("", response_model=PortfolioAnalysisJobResponse)
def request_portfolio_analysis(payload: PortfolioAnalysisJobRequest, service: PortfolioAnalysisJobService = Depends(get_portfolio_analysis_job_service)) -> PortfolioAnalysisJobResponse:
    try: return _response(service.request(payload.portfolio_snapshot_id))
    except PortfolioAnalysisError as error: raise _error(error) from error

@router.get("/{job_id}", response_model=PortfolioAnalysisJobResponse)
def portfolio_analysis_job(job_id: str, service: PortfolioAnalysisJobService = Depends(get_portfolio_analysis_job_service)) -> PortfolioAnalysisJobResponse:
    try: return _response(service.get(job_id))
    except PortfolioAnalysisError as error: raise _error(error) from error

@router.get("", response_model=PortfolioAnalysisJobListResponse)
def portfolio_analysis_jobs(service: PortfolioAnalysisJobService = Depends(get_portfolio_analysis_job_service)) -> PortfolioAnalysisJobListResponse:
    values = tuple(_response(item) for item in service.list())
    return PortfolioAnalysisJobListResponse(items=values, total=len(values))

def _response(job) -> PortfolioAnalysisJobResponse:
    return PortfolioAnalysisJobResponse(job_id=job.job_id, portfolio_reference=job.portfolio_snapshot_id, status=job.status.value,
        requested_at=job.requested_at, started_at=job.started_at, completed_at=job.completed_at, data_as_of=job.data_as_of,
        holdings_total=job.holdings_total, holdings_completed=job.holdings_completed, analysis_completeness=job.analysis_completeness.value,
        progress=f"{job.holdings_completed}/{job.holdings_total}", warnings=job.warnings, result_availability=job.result_availability)

def _error(error: PortfolioAnalysisError) -> APIRequestError:
    status = {"PORTFOLIO_EMPTY": 422, "PORTFOLIO_SNAPSHOT_NOT_FOUND": 404, "ANALYSIS_JOB_NOT_FOUND": 404}.get(error.code, 503)
    return APIRequestError(status_code=status, code=error.code, message=error.message)
