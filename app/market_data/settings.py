"""Typed provider selection only; real-provider credentials are never read here."""
from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import timedelta
from typing import Mapping


@dataclass(frozen=True, slots=True)
class MarketDataProviderSettings:
    provider: str = "mock"
    environment: str = "local"
    timeout: timedelta = timedelta(seconds=10)
    quote_freshness_seconds: int = 60
    intraday_bar_freshness_seconds: int = 300
    daily_bar_freshness_seconds: int = 86400
    credential_variable_name: str | None = None

    @classmethod
    def from_environment(cls, environ: Mapping[str, str] | None = None) -> "MarketDataProviderSettings":
        source = os.environ if environ is None else environ
        return cls(
            provider=source.get("MARKET_DATA_PROVIDER", "mock"),
            environment=source.get("MARKET_DATA_PROVIDER_ENV", "local"),
            timeout=timedelta(seconds=int(source.get("MARKET_DATA_TIMEOUT_SECONDS", "10"))),
            quote_freshness_seconds=int(source.get("MARKET_DATA_QUOTE_FRESHNESS_SECONDS", "60")),
            intraday_bar_freshness_seconds=int(source.get("MARKET_DATA_INTRADAY_BAR_FRESHNESS_SECONDS", "300")),
            daily_bar_freshness_seconds=int(source.get("MARKET_DATA_DAILY_BAR_FRESHNESS_SECONDS", "86400")),
            credential_variable_name=source.get("MARKET_DATA_CREDENTIAL_VARIABLE"),
        )
