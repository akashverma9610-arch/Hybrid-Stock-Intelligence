from datetime import datetime
from fastapi import APIRouter, Depends, Query
from app.api.dependencies import get_news_query_service
from app.api.news_query import NewsQueryService
from app.api.schemas.news import NewsArticleListResponse, NewsArticleResponse
from app.news.models import NewsArticleEvidence

router=APIRouter(tags=["news"])
@router.get("/news",response_model=NewsArticleListResponse)
def news(symbol:str|None=None,sector:str|None=None,start:datetime|None=Query(default=None,alias="from"),end:datetime|None=Query(default=None,alias="to"),source:str|None=None,limit:int=Query(default=50,ge=1,le=100),service:NewsQueryService=Depends(get_news_query_service)):
 return NewsArticleListResponse(items=tuple(_item(value) for value in service.list_news(instrument_id=symbol,sector=sector,start=start,end=end,provider=source,limit=limit)))
@router.get("/news/{article_id}",response_model=NewsArticleResponse)
def article(article_id:str,service:NewsQueryService=Depends(get_news_query_service)): return _item(service.news(article_id))
def _item(value:NewsArticleEvidence)->NewsArticleResponse:
 return NewsArticleResponse(article_id=value.article_id,source_provider=value.source_provider,publisher=value.publisher,publisher_url=value.publisher_url,url=value.url,title=value.title,description=value.description,published_at=value.published_at,received_at=value.received_at,language=value.language,country=value.country,instrument_ids=value.instrument_ids,sectors=value.sectors,themes=value.themes,source_quality=value.source_quality.value,event_category=value.event_category.value,linked_filing_id=value.linked_filing_id,match_warnings=value.match_warnings,warnings=value.warnings,company_name=value.company_name)
