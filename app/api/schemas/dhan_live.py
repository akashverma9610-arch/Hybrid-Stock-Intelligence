from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel


class DhanLiveHealthResponse(BaseModel):
    enabled: bool; state: str; health: str; requested_targets: int; subscribed_targets: int
    mapped_packets: int; rejected_packets: int; last_packet_at: datetime | None; token_state: str; reconnect_count: int


class DhanLiveQuoteResponse(BaseModel):
    canonical_instrument_id: str; ltp: Decimal; provider_trade_timestamp: datetime; received_at: datetime
    freshness: str; provider: str; provider_security_id: str


class DhanLiveTargetResponse(BaseModel):
    canonical_instrument_id: str; symbol: str; ltp: Decimal | None; freshness: str
    received_at: datetime | None; provider_trade_timestamp: datetime | None


class DhanLiveSetupMonitorResponse(BaseModel):
    canonical_instrument_id: str; symbol: str; entry: Decimal | None; stop: Decimal | None
    target: Decimal | None; maximum_entry: Decimal | None; state: str


class DhanLiveOverviewResponse(BaseModel):
    health: DhanLiveHealthResponse
    targets: tuple[DhanLiveTargetResponse, ...]
    setup_monitoring: tuple[DhanLiveSetupMonitorResponse, ...]
    setup_state: str


class DhanLivePortfolioValuationResponse(BaseModel):
    canonical_instrument_id: str; symbol: str; quantity: Decimal; average_price: Decimal
    ltp: Decimal | None; market_value: Decimal | None; unrealized_pnl: Decimal | None
    provider_timestamp: datetime | None; received_at: datetime | None; state: str; blocker: str | None


class DhanLivePortfolioResponse(BaseModel):
    health: DhanLiveHealthResponse
    holdings: tuple[DhanLivePortfolioValuationResponse, ...]


class DhanStockLiveMarketResponse(BaseModel):
    canonical_instrument_id: str
    health: DhanLiveHealthResponse
    quote: DhanLiveQuoteResponse | None
