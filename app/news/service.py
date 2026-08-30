"""Ingestion, cautious deterministic entity attachment and existing-research adapters."""
from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha256

from app.data_sources.models import DataFamily, SourceRecordProvenance
from app.filings.store import CorporateFilingsStore
from app.news.models import (NewsArticleEvidence, NewsEntity, NewsEventCategory, NewsEvidenceIngestionReport, NewsIngestionStatus, NewsSearchRequest, NewsSourceQuality, ProviderNewsArticle)
from app.news.providers import NewsResearchProvider
from app.news.store import NewsEvidenceStore
from app.research.models import Catalyst, CatalystClock, ResearchDocument, ResearchSnapshot, ResearchSourceType, SourceTier


class NewsEntityMatcher:
    def __init__(self, entities: tuple[NewsEntity, ...]) -> None: self._entities = entities
    def match(self, article: ProviderNewsArticle) -> tuple[tuple[NewsEntity, ...], tuple[str, ...]]:
        text = (article.title + " " + (article.description or "")).casefold()
        matches=[]
        for entity in self._entities:
            terms=(entity.canonical_name,*entity.aliases,entity.ticker or "",entity.isin or "")
            if any(term and len(term) >= 3 and term.casefold() in text for term in terms): matches.append(entity)
        if len(matches) > 1: return (), ("AMBIGUOUS_ENTITY_MATCH",)
        return tuple(matches), () if matches else ("UNMATCHED_ENTITY",)


class NewsEvidenceIngestionService:
    def __init__(self, provider: NewsResearchProvider, store: NewsEvidenceStore, matcher: NewsEntityMatcher, *, filings: CorporateFilingsStore | None = None, clock=lambda: datetime.now(UTC)) -> None:
        self._provider,self._store,self._matcher,self._filings,self._clock=provider,store,matcher,filings,clock
    def ingest(self, request: NewsSearchRequest) -> NewsEvidenceIngestionReport:
        started=self._clock(); articles=self._provider.search_news(request);accepted=duplicates=ambiguous=rejected=0;published=[];warnings=[];provenance=[]
        for article in articles:
            try:
                evidence=self._normalize(article,request)
                if evidence.match_warnings: ambiguous+=1
                if self._store.save(evidence): accepted+=1; published.append(evidence.published_at); provenance.append(evidence.provenance)
                else: duplicates+=1
            except (TypeError,ValueError): rejected+=1;warnings.append("NEWS_EVIDENCE_REJECTED")
        status=NewsIngestionStatus.FAILED if articles and rejected==len(articles) else NewsIngestionStatus.PARTIAL if rejected else NewsIngestionStatus.COMPLETED
        return NewsEvidenceIngestionReport(self._provider.provider_id,request,len(articles),accepted,duplicates,ambiguous,rejected,min(published) if published else None,max(published) if published else None,tuple(sorted(set(warnings))),tuple(provenance),started,self._clock(),status)
    def _normalize(self, article: ProviderNewsArticle, request: NewsSearchRequest) -> NewsArticleEvidence:
        entities,match_warnings=self._matcher.match(article);received=self._clock();category=_category(article.title,article.description); instruments=tuple(entity.instrument_id for entity in entities);sectors=tuple(entity.sector for entity in entities if entity.sector)
        provider_reference=article.provider_article_id or article.url;article_id="news:"+sha256(f"{self._provider.provider_id}:{provider_reference}".encode()).hexdigest()[:24]
        filing_id=self._filing_link(instruments,article) if instruments and self._filings else None
        prov=SourceRecordProvenance(article_id,self._provider.provider_id,article.provider_article_id,article.published_at,article.published_at,received,None,None,DataFamily.NEWS_RESEARCH,"news-evidence-v1","gnews-v1")
        return NewsArticleEvidence(article_id,self._provider.provider_id,article.publisher,article.publisher_url,article.url,article.title,article.description,article.published_at,received,article.language or request.language,article.country or request.country,instruments,sectors,(request.sector,) if request.sector else (),NewsSourceQuality.REPUTABLE_NEWS,prov,category,filing_id,match_warnings,("SECONDARY_EVIDENCE_ONLY",))
    def _filing_link(self, instruments: tuple[str,...], article: ProviderNewsArticle) -> str|None:
        # Link only when a same-instrument primary filing has matching factual category/date; never assert identity.
        for instrument in instruments:
            for filing in self._filings.list(instrument_id=instrument,start=article.published_at.replace(hour=0,minute=0,second=0,microsecond=0),end=article.published_at):
                if _category(filing.subject,None) is _category(article.title,article.description): return filing.filing_id
        return None


class NewsResearchInputBuilder:
    """Projects stored factual metadata into the existing research/catalyst contracts only."""
    def __init__(self, store: NewsEvidenceStore) -> None: self._store=store
    def build(self, instrument_id: str, *, as_of: datetime) -> ResearchSnapshot:
        values=self._store.list(instrument_id=instrument_id,as_of=as_of,limit=100)
        docs=[]; catalysts=[]
        for value in values:
            doc=ResearchDocument(value.article_id,instrument_id,ResearchSourceType.FINANCIAL_NEWS,value.publisher or value.source_provider,value.article_id,value.published_at,value.received_at,value.title,value.url,SourceTier.TIER_3_HIGH_QUALITY_SECONDARY,False)
            docs.append(doc)
            if value.event_category is not NewsEventCategory.UNCLASSIFIED:
                catalysts.append(Catalyst("news-catalyst:"+value.article_id,value.article_id,value.event_category.value,value.title,value.published_at,_clock(value.published_at,as_of),None,"unassessed","unassessed","unassessed",("SECONDARY_CONTEXT_ONLY",)))
        return ResearchSnapshot(as_of,tuple(docs),(),(),tuple(catalysts))


def _clock(published: datetime, as_of: datetime) -> CatalystClock:
    days=(as_of-published).days
    return CatalystClock.IMMEDIATE if days<=30 else CatalystClock.NEAR_TERM if days<=90 else CatalystClock.MEDIUM_TERM
def _category(title: str, description: str|None) -> NewsEventCategory:
    text=(title+" "+(description or "")).casefold()
    for words,category in ((('result','earnings'),NewsEventCategory.EARNINGS_RESULTS),(('order','contract'),NewsEventCategory.ORDER_CONTRACT),(('acquisition','merger','divest'),NewsEventCategory.ACQUISITION_DIVESTMENT),(('fund raise','fundraise','rights issue'),NewsEventCategory.FUNDRAISE),(('regulatory','sebi','legal'),NewsEventCategory.REGULATORY_LEGAL),(('management','ceo','director'),NewsEventCategory.MANAGEMENT_CHANGE),(('capacity','plant'),NewsEventCategory.CAPACITY_EXPANSION),(('rbi','policy','tax','commodity'),NewsEventCategory.MACRO)):
        if any(word in text for word in words): return category
    return NewsEventCategory.UNCLASSIFIED
