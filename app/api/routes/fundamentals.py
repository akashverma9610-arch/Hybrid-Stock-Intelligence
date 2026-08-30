from datetime import datetime
from fastapi import APIRouter, Depends, Query
from app.api.dependencies import get_fundamentals_query_service
from app.api.fundamentals_query import FundamentalsQueryService
from app.api.schemas.fundamentals import FinancialFactResponse, FinancialSeriesResponse, FundamentalSnapshotResponse
from app.fundamentals.models import FinancialFact, FinancialMetric, FinancialPeriodType, StatementScope

router=APIRouter(tags=["fundamentals"])
@router.get("/fundamentals/{symbol}",response_model=FundamentalSnapshotResponse)
def fundamentals(symbol:str,as_of:datetime=Query(...),scope:StatementScope=StatementScope.CONSOLIDATED,service:FundamentalsQueryService=Depends(get_fundamentals_query_service)):
    value=service.snapshot(symbol,as_of=as_of,scope=scope);return FundamentalSnapshotResponse(snapshot_id=value.snapshot_id,instrument_id=value.instrument.instrument_id,statement_scope=value.statement_scope.value,data_as_of=value.data_as_of,latest_quarter_end=value.latest_quarter_end,latest_annual_end=value.latest_annual_end,quality_flags=tuple(x.value for x in value.quality_flags),provenance=value.provenance,values=tuple(_fact(x) for x in value.values))
@router.get("/fundamentals/{symbol}/series",response_model=FinancialSeriesResponse)
def series(symbol:str,metric:FinancialMetric,period_type:FinancialPeriodType|None=None,scope:StatementScope|None=None,as_of:datetime|None=None,limit:int=Query(50,ge=1,le=100),service:FundamentalsQueryService=Depends(get_fundamentals_query_service)):
    return FinancialSeriesResponse(items=tuple(_fact(x) for x in service.series(symbol,metric,period_type=period_type,scope=scope,as_of=as_of,limit=limit)))
def _fact(v:FinancialFact)->FinancialFactResponse:return FinancialFactResponse(fact_id=v.fact_id,instrument_id=v.instrument.instrument_id,metric=v.metric.value,value=v.value,currency=v.currency,unit=v.unit,scale=v.scale.value,period_type=v.period_type.value,value_basis=v.value_basis.value,period_start=v.period_start,period_end=v.period_end,fiscal_year=v.fiscal_year,fiscal_quarter=v.fiscal_quarter,statement_scope=v.statement_scope.value,fact_kind=v.fact_kind.value,source=v.source,filing_id=v.filing_id,source_reference=v.source_reference,published_at=v.published_at,received_at=v.received_at,normalization_version=v.normalization_version,provenance=v.provenance,parent_fact_ids=v.parent_fact_ids,revision_of_fact_id=v.revision_of_fact_id,quality_flags=tuple(x.value for x in v.quality_flags))
