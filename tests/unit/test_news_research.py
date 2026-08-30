from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.data_sources.models import DataFamily, SourceValidationState
from app.data_sources.service import DataSourceCompositionService, SourceCompositionSettings
from app.market_data.models import ErrorCode, MarketDataError
from app.news.models import NewsEntity, NewsSearchRequest
from app.news.providers import GNewsResearchProvider
from app.news.service import NewsEntityMatcher, NewsEvidenceIngestionService, NewsResearchInputBuilder
from app.news.store import SQLiteNewsEvidenceStore
from app.filings.models import CorporateFiling, FilingType, PrimarySourceQuality
from app.filings.store import SQLiteCorporateFilingsStore
from app.market_data.models import Exchange, InstrumentIdentity, InstrumentType, MarketDataProvenance

T = datetime(2026, 8, 23, 10, tzinfo=UTC)


def payload(*, url="https://example.test/article-1", title="Alpha Ltd wins a major order", published="2026-08-22T10:00:00Z"):
    return {"articles": [{"id": "provider-1", "url": url, "title": title, "description": "Alpha expands capacity", "publishedAt": published, "source": {"name": "Example Financial", "url": "https://example.test"}, "language": "en", "country": "in"}]}


def service(tmp_path, *, response=None):
    provider=GNewsResearchProvider("secret",transport=lambda endpoint,params: response or payload())
    store=SQLiteNewsEvidenceStore(tmp_path/"news.sqlite")
    matcher=NewsEntityMatcher((NewsEntity("NSE:ALPHA","Alpha Ltd",("Alpha",),"ALPHA",sector="Industrials"),NewsEntity("NSE:BETA","Beta Ltd",("Beta",),"BETA",sector="Financials")))
    return NewsEvidenceIngestionService(provider,store,matcher,clock=lambda:T),store,provider


def test_gnews_request_maps_documented_bounded_filters_and_never_scrapes():
    provider=GNewsResearchProvider("secret",transport=lambda *_:payload(published="2026-08-23T10:00:00Z"))
    parameters=provider.request_parameters(NewsSearchRequest("Alpha Ltd",aliases=("ALPHA",),start=T-timedelta(days=3),end=T,maximum=5))
    assert parameters == {"q":"Alpha Ltd","lang":"en","country":"in","max":"5","page":"1","sortby":"publishedAt","apikey":"secret","from":"2026-08-20T10:00:00Z","to":"2026-08-23T10:00:00Z"}
    source=__import__("inspect").getsource(GNewsResearchProvider).lower()
    assert "requests.get" not in source and "urlopen(" not in source


def test_news_ingestion_store_dedup_pit_and_research_catalyst_projection(tmp_path):
    ingestion,store,_=service(tmp_path)
    report=ingestion.ingest(NewsSearchRequest("Alpha Ltd",maximum=5))
    assert report.accepted_count == 1 and report.status.value == "COMPLETED"
    evidence=store.list(instrument_id="NSE:ALPHA")[0]
    assert evidence.publisher == "Example Financial" and evidence.source_quality.value == "REPUTABLE_NEWS"
    assert store.get(evidence.article_id) == evidence
    assert store.list(instrument_id="NSE:ALPHA",as_of=T-timedelta(days=2)) == ()
    assert ingestion.ingest(NewsSearchRequest("Alpha Ltd")).duplicate_count == 1
    snapshot=NewsResearchInputBuilder(store).build("NSE:ALPHA",as_of=T)
    assert snapshot.documents[0].research_item_id == evidence.article_id
    assert snapshot.catalysts[0].category == "ORDER_CONTRACT"
    assert "SECONDARY_CONTEXT_ONLY" in snapshot.catalysts[0].conditions


def test_ambiguous_match_is_retained_without_instrument_and_later_article_does_not_rewrite(tmp_path):
    response=payload(title="Alpha and Beta announce acquisition",url="https://example.test/ambiguous")
    ingestion,store,_=service(tmp_path,response=response)
    first=ingestion.ingest(NewsSearchRequest("market acquisition")); evidence=store.list()[0]
    assert first.ambiguous_or_unmatched_count == 1 and evidence.instrument_ids == () and "AMBIGUOUS_ENTITY_MATCH" in evidence.match_warnings
    second=ingestion.ingest(NewsSearchRequest("market acquisition"))
    assert second.duplicate_count == 1 and store.get(evidence.article_id) == evidence


@pytest.mark.parametrize("message,code",[("invalid api key",ErrorCode.AUTHENTICATION_REQUIRED),("rate limit reached",ErrorCode.RATE_LIMITED),("invalid query",ErrorCode.MALFORMED_RESPONSE)])
def test_gnews_error_mapping(message,code):
    provider=GNewsResearchProvider("secret",transport=lambda *_:{"errors":[message]})
    with pytest.raises(MarketDataError) as caught: provider.search_news(NewsSearchRequest("Alpha"))
    assert caught.value.code is code


def test_malformed_response_rejected_and_no_default_network(tmp_path):
    provider=GNewsResearchProvider("secret",transport=lambda *_:{"articles":[{"title":"missing"}]})
    with pytest.raises(MarketDataError) as caught: provider.search_news(NewsSearchRequest("Alpha"))
    assert caught.value.code is ErrorCode.MALFORMED_RESPONSE
    with pytest.raises(MarketDataError): GNewsResearchProvider("secret").search_news(NewsSearchRequest("Alpha"))


def test_news_readiness_is_optional_and_distinguishes_configuration_validation():
    settings=SourceCompositionSettings.from_environment({"DATA_SOURCE_NEWS_RESEARCH_PRIORITY":"gnews"})
    missing=DataSourceCompositionService.from_settings(settings,states={"gnews":SourceValidationState(False)}).readiness().primary(DataFamily.NEWS_RESEARCH)
    configured=DataSourceCompositionService.from_settings(settings,states={"gnews":SourceValidationState(True,False)}).readiness().primary(DataFamily.NEWS_RESEARCH)
    ready=DataSourceCompositionService.from_settings(settings,states={"gnews":SourceValidationState(True,True)}).readiness().primary(DataFamily.NEWS_RESEARCH)
    assert (missing.status.value,configured.status.value,ready.status.value)==("MISSING_CONFIGURATION","CONFIGURED_NOT_VALIDATED","READY")
    assert "DELAYED_SOURCE_PLAN_DEPENDENT" in ready.warnings


def test_news_provider_does_not_leak_into_canonical_technical_regime_or_crisis_engines():
    import inspect
    from app.analysis import market_regime, relative_strength, series, technical
    from app.crisis import engine, extremes
    source="\n".join(inspect.getsource(module) for module in (series,relative_strength,technical,market_regime,engine,extremes)).lower()
    assert "app.news" not in source and "gnews" not in source


def test_filing_link_retains_primary_precedence_without_collapsing_secondary_story(tmp_path):
    filings=SQLiteCorporateFilingsStore(tmp_path/"filings.sqlite")
    instrument=InstrumentIdentity("NSE:ALPHA",Exchange.NSE,"ALPHA",None,None,None,InstrumentType.NSE_EQUITY,"Alpha Ltd")
    provenance=MarketDataProvenance("nse",None,T,T,T,"v1","test")
    filings.save(CorporateFiling("filing-1",instrument,Exchange.NSE,"nse",PrimarySourceQuality.PRIMARY_EXCHANGE,FilingType.ORDER_CONTRACT,None,"Alpha wins an order",T-timedelta(hours=1),T-timedelta(hours=1),"ref",None,provenance))
    provider=GNewsResearchProvider("secret",transport=lambda *_:payload(published="2026-08-23T10:00:00Z"))
    store=SQLiteNewsEvidenceStore(tmp_path/"news.sqlite")
    ingestion=NewsEvidenceIngestionService(provider,store,NewsEntityMatcher((NewsEntity("NSE:ALPHA","Alpha Ltd",("Alpha",),"ALPHA"),)),filings=filings,clock=lambda:T)
    ingestion.ingest(NewsSearchRequest("Alpha")); evidence=store.list()[0]
    assert evidence.linked_filing_id == "filing-1" and evidence.source_quality.value == "REPUTABLE_NEWS"
