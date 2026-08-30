from datetime import datetime
from fastapi import APIRouter,Depends,Query,Request
from app.api.primary_market_query import UnavailablePrimaryMarketQueryService
from app.primary_market.models import PrimaryMarketIssueType
router=APIRouter(tags=["primary-market"])
def _service(request:Request):return request.app.state.primary_market_query_service
@router.get("/primary-market/issues")
def issues(start:datetime|None=Query(default=None,alias="from"),end:datetime|None=Query(default=None,alias="to"),sector:str|None=None,issue_type:PrimaryMarketIssueType|None=Query(default=None,alias="type"),limit:int=Query(default=50,ge=1,le=200),service=Depends(_service)):
 return {"items":[_issue(v) for v in service.issues(start=start,end=end,sector=sector,issue_type=issue_type,limit=limit)]}
@router.get("/primary-market/issues/{issue_id}")
def issue(issue_id:str,service=Depends(_service)):return _issue(service.issue(issue_id))
@router.get("/primary-market/summary")
def summary(as_of:datetime,days:int=Query(default=30,ge=1,le=365),service=Depends(_service)):
 v=service.summary(as_of=as_of,days=days);return {"issue_count":v.issue_count,"total_issue_size":str(v.total_issue_size),"total_fresh_issue":str(v.total_fresh_issue),"total_ofs":str(v.total_ofs),"subscription_coverage":v.subscription_coverage,"listing_coverage":v.listing_coverage,"median_listing_premium":str(v.median_listing_premium) if v.median_listing_premium is not None else None,"sector_counts":v.sector_counts,"warnings":v.warnings,"data_as_of":v.data_as_of}
def _issue(v):return {"issue_id":v.issue_id,"issuer_name":v.issuer_name,"instrument_id":v.instrument_id,"future_symbol":v.future_symbol,"exchange":v.exchange,"issue_type":v.issue_type.value,"sector":v.sector,"issue_open_date":v.issue_open_date,"issue_close_date":v.issue_close_date,"listing_date":v.listing_date,"issue_price":str(v.issue_price) if v.issue_price is not None else None,"total_issue_size":str(v.total_issue_size) if v.total_issue_size is not None else None,"fresh_issue_amount":str(v.fresh_issue_amount) if v.fresh_issue_amount is not None else None,"ofs_amount":str(v.ofs_amount) if v.ofs_amount is not None else None,"warnings":v.warnings}
