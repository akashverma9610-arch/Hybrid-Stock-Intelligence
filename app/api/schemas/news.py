from datetime import datetime
from pydantic import BaseModel

class NewsArticleResponse(BaseModel):
    article_id:str; source_provider:str; publisher:str|None; publisher_url:str|None; url:str; title:str; description:str|None; published_at:datetime; received_at:datetime; language:str|None; country:str|None; instrument_ids:tuple[str,...]; sectors:tuple[str,...]; themes:tuple[str,...]; source_quality:str; event_category:str; linked_filing_id:str|None; match_warnings:tuple[str,...]; warnings:tuple[str,...]; company_name:str|None=None
class NewsArticleListResponse(BaseModel): items:tuple[NewsArticleResponse,...]
