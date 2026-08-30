"""GET-only performance, benchmark, and governance routes."""
from typing import Annotated
from fastapi import APIRouter, Depends, Query
from app.api.dependencies import get_benchmark_query_service, get_governance_query_service, get_performance_query_service
from app.api.performance_governance_query import BenchmarkQueryService, GovernanceQueryService, PerformanceQueryService, active_strategy_response, benchmark_response, performance_response, promotion_response, strategy_version_response
from app.api.schemas.performance_governance import ActiveStrategyResponse, BenchmarkListResponse, BenchmarkResponse, PerformanceListResponse, PerformanceResponse, PromotionListResponse, PromotionSummaryResponse, StrategyVersionListResponse

router = APIRouter(tags=["performance", "benchmarks", "governance"])
_Limit = Annotated[int, Query(ge=1, le=100)]
_Offset = Annotated[int, Query(ge=0)]

@router.get("/performance", response_model=PerformanceListResponse)
def performance(strategy_version: str | None = None, source_run_id: str | None = None, mode: str | None = None, limit: _Limit = 50, offset: _Offset = 0, service: PerformanceQueryService = Depends(get_performance_query_service)):
    items = service.list_performance(strategy_version=strategy_version, source_run_id=source_run_id, mode=mode)
    return PerformanceListResponse(items=tuple(performance_response(x) for x in items[offset:offset+limit]), total=len(items), limit=limit, offset=offset)

@router.get("/performance/{report_id}", response_model=PerformanceResponse)
def performance_detail(report_id: str, service: PerformanceQueryService = Depends(get_performance_query_service)): return performance_response(service.get_performance(report_id))

@router.get("/benchmarks", response_model=BenchmarkListResponse)
def benchmarks(benchmark_id: str | None = None, report_id: str | None = None, mode: str | None = None, limit: _Limit = 50, offset: _Offset = 0, service: BenchmarkQueryService = Depends(get_benchmark_query_service)):
    items = service.list_benchmarks(benchmark_id=benchmark_id, report_id=report_id, mode=mode)
    return BenchmarkListResponse(items=tuple(benchmark_response(x) for x in items[offset:offset+limit]), total=len(items), limit=limit, offset=offset)

@router.get("/benchmarks/{benchmark_id}", response_model=BenchmarkResponse)
def benchmark_detail(benchmark_id: str, service: BenchmarkQueryService = Depends(get_benchmark_query_service)): return benchmark_response(service.get_benchmark(benchmark_id))

@router.get("/governance/strategy-versions", response_model=StrategyVersionListResponse)
def strategy_versions(limit: _Limit = 50, offset: _Offset = 0, service: GovernanceQueryService = Depends(get_governance_query_service)):
    items = service.list_strategy_versions()
    return StrategyVersionListResponse(items=tuple(strategy_version_response(x) for x in items[offset:offset+limit]), total=len(items), limit=limit, offset=offset)

@router.get("/governance/active-strategy", response_model=ActiveStrategyResponse)
def active_strategy(service: GovernanceQueryService = Depends(get_governance_query_service)): return active_strategy_response(service.get_active_strategy())

@router.get("/governance/promotions", response_model=PromotionListResponse)
def promotions(limit: _Limit = 50, offset: _Offset = 0, service: GovernanceQueryService = Depends(get_governance_query_service)):
    items = service.list_promotions()
    return PromotionListResponse(items=tuple(promotion_response(x) for x in items[offset:offset+limit]), total=len(items), limit=limit, offset=offset)

@router.get("/governance/promotions/{proposal_id}", response_model=PromotionSummaryResponse)
def promotion_detail(proposal_id: str, service: GovernanceQueryService = Depends(get_governance_query_service)): return promotion_response(service.get_promotion(proposal_id))
