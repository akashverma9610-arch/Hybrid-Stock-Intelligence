"""Small provider boundary for licensed/machine-readable news metadata only."""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Callable, Mapping, Protocol

from app.market_data.models import ErrorCode, MarketDataError, RetryDisposition
from app.news.models import NewsSearchRequest, ProviderNewsArticle

GNEWS_PROVIDER = "gnews"


class NewsResearchProvider(Protocol):
    provider_id: str
    def search_news(self, request: NewsSearchRequest) -> tuple[ProviderNewsArticle, ...]: ...


class GNewsResearchProvider:
    """GNews Search endpoint adapter. It only requests API JSON; it never scrapes URLs."""
    provider_id = GNEWS_PROVIDER
    endpoint = "https://gnews.io/api/v4/search"

    def __init__(self, api_key: str | None, *, transport: Callable[[str, Mapping[str, str]], object] | None = None) -> None:
        self._api_key, self._transport = api_key, transport

    def request_parameters(self, request: NewsSearchRequest) -> dict[str, str]:
        if not self._api_key:
            raise MarketDataError(ErrorCode.AUTHENTICATION_REQUIRED, "GNews API key is not configured.")
        values = {"q": request.query, "lang": request.language, "country": request.country, "max": str(request.maximum), "page": str(request.page), "sortby": request.sort_by, "apikey": self._api_key}
        if request.start: values["from"] = _iso(request.start)
        if request.end: values["to"] = _iso(request.end)
        return values

    def search_news(self, request: NewsSearchRequest) -> tuple[ProviderNewsArticle, ...]:
        if self._transport is None:
            raise MarketDataError(ErrorCode.PROVIDER_UNAVAILABLE, "GNews transport is not configured.")
        try:
            payload = self._transport(self.endpoint, self.request_parameters(request))
        except TimeoutError as error:
            raise MarketDataError(ErrorCode.PROVIDER_UNAVAILABLE, "GNews request timed out.", RetryDisposition.RETRYABLE) from error
        except MarketDataError:
            raise
        except Exception as error:
            raise MarketDataError(ErrorCode.PROVIDER_UNAVAILABLE, "GNews request failed.", RetryDisposition.RETRYABLE) from error
        if not isinstance(payload, dict):
            raise MarketDataError(ErrorCode.MALFORMED_RESPONSE, "GNews response is malformed.")
        if payload.get("errors"):
            raise _provider_error(payload)
        articles = payload.get("articles")
        if not isinstance(articles, list):
            raise MarketDataError(ErrorCode.MALFORMED_RESPONSE, "GNews response has no articles array.")
        try:
            return tuple(_article(item) for item in articles)
        except (KeyError, TypeError, ValueError) as error:
            raise MarketDataError(ErrorCode.MALFORMED_RESPONSE, "GNews article metadata is malformed.") from error


def _iso(value: datetime) -> str:
    return value.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _article(value: Mapping[str, object]) -> ProviderNewsArticle:
    source = value.get("source")
    if not isinstance(source, dict): source = {}
    published = datetime.fromisoformat(str(value["publishedAt"]).replace("Z", "+00:00"))
    if published.tzinfo is None: raise ValueError("naive GNews publication")
    url, title = str(value["url"]), str(value["title"])
    if not url.startswith(("http://", "https://")) or not title.strip(): raise ValueError("invalid GNews metadata")
    return ProviderNewsArticle(str(value.get("id")) if value.get("id") else None, url, title, str(value["description"]) if value.get("description") is not None else None, str(source["name"]) if source.get("name") else None, str(source["url"]) if source.get("url") else None, published, str(value["language"]) if value.get("language") else None, str(value["country"]) if value.get("country") else None)


def _provider_error(payload: Mapping[str, object]) -> MarketDataError:
    text = " ".join(str(value) for value in payload.get("errors", ())).lower()
    if "api key" in text or "unauthorized" in text or "authentication" in text:
        code = ErrorCode.AUTHENTICATION_REQUIRED
    elif "rate" in text or "limit" in text:
        code = ErrorCode.RATE_LIMITED
    elif "invalid" in text or "query" in text:
        code = ErrorCode.MALFORMED_RESPONSE
    else:
        code = ErrorCode.PROVIDER_UNAVAILABLE
    return MarketDataError(code, "GNews provider rejected the request.", RetryDisposition.RETRYABLE if code in {ErrorCode.RATE_LIMITED, ErrorCode.PROVIDER_UNAVAILABLE} else RetryDisposition.NON_RETRYABLE)
