from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.connections.credentials import InMemoryCredentialStore
from app.domain.models import DataQuality
from app.data_operations.backend_local_upstox import (
    BackendLocalRealPortfolioOhlcvActivation, REAL_PORTFOLIO_OHLCV_TARGETS,
)
from app.data_operations.models import EvidenceRefreshOutcome, EvidenceRefreshStatus
from app.market_data.historical import SQLiteHistoricalBarStore
from app.market_data.models import (
    AdjustmentStatus, CanonicalOHLCVBar, Exchange, InstrumentIdentity,
    InstrumentType, MarketDataProvenance, Timeframe,
)


REQUESTED_AT = datetime(2026, 8, 31, 13, 52, 49, tzinfo=UTC)
VISIBLE_AT = REQUESTED_AT + timedelta(seconds=1)


class _Universe:
    def provider_mapping(self, **_kwargs):
        return object()


class _Job:
    def __init__(self, historical):
        self._historical = historical

    def refresh_selected(self, request, *, canonical_instrument_ids):
        identifier = next(iter(canonical_instrument_ids))
        existing = self._historical.range(
            identifier, Timeframe.DAILY, datetime.min.replace(tzinfo=UTC), datetime.max.replace(tzinfo=UTC),
        )
        if existing:
            return EvidenceRefreshOutcome(
                EvidenceRefreshStatus.NO_CHANGE, "upstox", duplicate_count=len(existing), accepted_through=existing[-1].end_time,
            )
        bars = tuple(_bar(identifier, number) for number in range(252))
        for bar in bars:
            self._historical.upsert(bar)
        return EvidenceRefreshOutcome(
            EvidenceRefreshStatus.COMPLETE, "upstox", accepted_count=len(bars), accepted_through=bars[-1].end_time,
        )


def _bar(identifier: str, number: int) -> CanonicalOHLCVBar:
    end = REQUESTED_AT - timedelta(days=252 - number)
    identity = InstrumentIdentity(
        identifier, Exchange.INDEX if identifier.startswith("NIFTY") else Exchange.NSE,
        identifier, identifier, None, None,
        InstrumentType.BROAD_INDEX if identifier.startswith("NIFTY") else InstrumentType.NSE_EQUITY,
        identifier,
    )
    return CanonicalOHLCVBar(
        f"upstox:{identifier}:{number}", identity, Timeframe.DAILY, end - timedelta(days=1), end,
        Decimal("100"), Decimal("101"), Decimal("99"), Decimal("100"), 1000, None, None,
        AdjustmentStatus.UNKNOWN,
        MarketDataProvenance("upstox", f"NSE_INDEX|{identifier}", None, None, VISIBLE_AT, "upstox-v3"),
        DataQuality.HIGH,
    )


def test_post_ingestion_readiness_uses_visibility_cutoff_without_weakening_historical_pit(tmp_path):
    historical = SQLiteHistoricalBarStore(tmp_path / "history.sqlite")
    job = _Job(historical)
    calls = iter((REQUESTED_AT, *([VISIBLE_AT] * 20)))
    service = BackendLocalRealPortfolioOhlcvActivation(
        credential_store=InMemoryCredentialStore(), universe=_Universe(), historical=historical,
        equity_job=job, index_job=job, clock=lambda: next(calls),
    )

    result = service.run_twice()
    nifty_first = next(item for item in result.first_run if item.canonical_instrument_id == "NIFTY_50")
    nifty_second = next(item for item in result.second_run if item.canonical_instrument_id == "NIFTY_50")

    assert historical.latest("NIFTY_50", Timeframe.DAILY, 252, as_of=REQUESTED_AT) == ()
    assert len(historical.latest("NIFTY_50", Timeframe.DAILY, 252, as_of=VISIBLE_AT)) == 252
    assert nifty_first.session_count_before == 0 and nifty_first.session_count_after == 252
    assert nifty_first.readiness == "OHLCV_READY" and nifty_first.latest_session is not None
    assert nifty_second.accepted_count == 0 and nifty_second.duplicate_count == 252
    assert all(item.readiness == "OHLCV_READY" for item in result.first_run)
    assert tuple(item.canonical_instrument_id for item in result.first_run) == REAL_PORTFOLIO_OHLCV_TARGETS
