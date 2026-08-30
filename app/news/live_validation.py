"""Explicit, opt-in GNews smoke harness; normal tests never invoke it."""
from __future__ import annotations

import json
import os
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode
from urllib.request import urlopen

from app.news.models import NewsSearchRequest
from app.news.providers import GNewsResearchProvider


def live_gnews_provider_from_environment() -> GNewsResearchProvider:
    key=os.environ.get("GNEWS_API_KEY")
    if not key or os.environ.get("GNEWS_LIVE_VALIDATION", "").lower() not in {"1","true","yes"}:
        raise RuntimeError("GNews live validation is opt-in and requires GNEWS_API_KEY plus GNEWS_LIVE_VALIDATION=true.")
    query=os.environ.get("GNEWS_TEST_QUERY")
    if not query: raise RuntimeError("GNews live validation requires GNEWS_TEST_QUERY.")
    def transport(endpoint: str, parameters: dict[str,str]):
        # This is deliberately confined to the explicit smoke harness and bounded request.
        with urlopen(endpoint+"?"+urlencode(parameters),timeout=10) as response:
            return json.loads(response.read().decode("utf-8"))
    return GNewsResearchProvider(key,transport=transport)


def validate_live_gnews() -> int:
    provider=live_gnews_provider_from_environment(); query=os.environ["GNEWS_TEST_QUERY"]
    now=datetime.now(UTC)
    return len(provider.search_news(NewsSearchRequest(query,start=now-timedelta(days=1),end=now,maximum=1)))
