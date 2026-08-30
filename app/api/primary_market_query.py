from app.api.errors import APIRequestError
from app.primary_market.service import PrimaryMarketAggregationService
class RepositoryPrimaryMarketQueryService:
 def __init__(self,store):self.store=store
 def issues(self,**kwargs):return self.store.list_issues(**kwargs)
 def issue(self,issue_id):
  value=self.store.get_issue(issue_id)
  if not value:raise APIRequestError(status_code=404,code="PRIMARY_MARKET_ISSUE_NOT_FOUND",message="Primary-market issue was not found.")
  return value
 def summary(self,*,as_of,days):return PrimaryMarketAggregationService(self.store).aggregate(end=as_of,days=days)
class UnavailablePrimaryMarketQueryService:
 def issues(self,**kwargs):raise APIRequestError(status_code=503,code="PRIMARY_MARKET_UNAVAILABLE",message="Primary-market evidence is unavailable.")
 def issue(self,*args):raise APIRequestError(status_code=503,code="PRIMARY_MARKET_UNAVAILABLE",message="Primary-market evidence is unavailable.")
 def summary(self,**kwargs):raise APIRequestError(status_code=503,code="PRIMARY_MARKET_UNAVAILABLE",message="Primary-market evidence is unavailable.")
