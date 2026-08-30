from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from app.data_sources.models import FundamentalFactKind
from app.fundamentals.models import (
    FinancialFact, FinancialMetric, FinancialPeriodType, FinancialQualityFlag,
    FinancialValueBasis, NumericScale, StatementScope,
)
from app.market_data.models import Exchange, InstrumentIdentity, InstrumentType
from app.market_data.yahoo_enrichment import (
    YahooDatasetStatus, YahooSecondaryEnrichmentService, YahooSecondarySnapshotStore,
    _failure,
)
from app.storage.core_api_snapshot_repository import CoreApiSnapshotFamily
from app.storage.sqlite_core_api_snapshot_repository import SQLiteCoreApiSnapshotRepository
from app.universe_analysis.models import NseEquityInstrument


T = datetime(2026, 8, 27, 12, tzinfo=UTC)


class _Row:
    def __init__(self, values): self._values = values
    def to_dict(self): return dict(self._values)


class _Table:
    columns = ("2026-06-30", "2025-06-30")
    def __init__(self, rows=None): self._rows = rows or (("Total Revenue", {"2026-06-30": 100, "2025-06-30": 80}),)
    def iterrows(self):
        for label, values in self._rows: yield label, _Row(values)


class _Ticker:
    def __init__(self, symbol: str, *, failure: Exception | None = None): self.symbol, self.failure = symbol, failure
    def get_info(self):
        if self.failure: raise self.failure
        return {"symbol": self.symbol, "sector": "Healthcare", "industry": "Healthcare Facilities", "marketCap": 1000}
    def get_income_stmt(self, **_): return _Table()
    def get_balance_sheet(self, **_): return _Table((("Total Assets", {"2026-06-30": 120, "2025-06-30": 110}),))
    def get_cashflow(self, **_): return _Table((("Operating Cash Flow", {"2026-06-30": 30, "2025-06-30": 25}),))
    def get_actions(self, **_): return _Table((("2026-01-15", {"Dividends": 0, "Stock Splits": 2.0}),))
    def get_dividends(self, **_): return _Table()
    def get_splits(self, **_): return _Table()
    def __getattr__(self, name):
        if name.startswith("get_"):
            return lambda **_: []
        raise AttributeError(name)


def _cohort() -> tuple[NseEquityInstrument, ...]:
    symbols = ("APOLLOHOSP", "SAFARI", "ORIENTTECH", *(f"TEST{index:02d}" for index in range(37)))
    return tuple(NseEquityInstrument(
        f"NSE:INE{index:07d}", symbol, f"INE{index:07d}", None, None, "ACTIVE", None, True, T,
        "NSE_OFFICIAL_EXPORT", company_name=symbol,
    ) for index, symbol in enumerate(symbols, 1))


def _official_fact(instrument_id: str) -> FinancialFact:
    identity = InstrumentIdentity(instrument_id, Exchange.NSE, "APOLLOHOSP", "APOLLOHOSP", "INE0000001", "EQ", InstrumentType.NSE_EQUITY, "Apollo Hospitals")
    return FinancialFact(
        "bse:revenue", identity, FinancialMetric.REVENUE, Decimal("100"), "INR", "INR", NumericScale.CRORES,
        FinancialPeriodType.QUARTERLY, FinancialValueBasis.QUARTER_ONLY, None, datetime(2026, 6, 30, tzinfo=UTC),
        2027, 1, StatementScope.CONSOLIDATED, FundamentalFactKind.REPORTED, "BSE_OFFICIAL_XBRL", "bse-filing", "bse:xbrl",
        T, T, "bse-xbrl-v1", ("OFFICIAL",), (), None, (FinancialQualityFlag.COMPLETE,),
    )


def test_anchor_snapshots_are_append_only_secondary_research_with_raw_labels_and_pit(tmp_path):
    path = tmp_path / "snapshots.sqlite"; repository = SQLiteCoreApiSnapshotRepository(path)
    facts = {"NSE:INE0000001": (_official_fact("NSE:INE0000001"),)}
    delays: list[float] = []
    service = YahooSecondaryEnrichmentService(
        store=YahooSecondarySnapshotStore(repository), ticker_factory=lambda symbol: _Ticker(symbol),
        official_facts=lambda instrument_id: facts.get(instrument_id, ()), clock=lambda: T, sleeper=delays.append,
    )

    report = service.enrich(_cohort(), phase="anchors")
    assert report.requested == report.snapshots_saved == 3
    assert report.provider_requests == 87 and delays == [0.25] * (report.provider_requests - 1)
    first = YahooSecondarySnapshotStore(repository).latest("NSE:INE0000001")
    assert first is not None and first.provider == "YAHOO_FINANCE" and first.source_class == "SECONDARY_RESEARCH"
    assert first.pit_semantics == "OBSERVED_AT_FETCH_ONLY" and not first.canonical
    assert first.taxonomy_status == "SECONDARY_HINT" and first.sector_hint == "Healthcare"
    quarterly = next(item for item in first.datasets if item.dataset == "quarterly_income")
    assert quarterly.status is YahooDatasetStatus.READY
    assert quarterly.financial_rows[0].raw_label == "Total Revenue"
    assert quarterly.financial_rows[0].canonical_candidate == FinancialMetric.REVENUE.value
    assert report.reconciliation[0]["match_status"] == "UNAVAILABLE_UNIT_SCALE"
    assert not repository.list_snapshots(CoreApiSnapshotFamily.TAXONOMY_CLASSIFICATION, limit=1)
    assert not repository.list_snapshots(CoreApiSnapshotFamily.APPROVED_STRATEGY_VERSION, limit=1)

    before = repository.get_snapshot(first.snapshot_id)
    later = YahooSecondaryEnrichmentService(
        store=YahooSecondarySnapshotStore(repository), ticker_factory=lambda symbol: _Ticker(symbol),
        official_facts=lambda instrument_id: facts.get(instrument_id, ()), clock=lambda: datetime(2026, 8, 28, 12, tzinfo=UTC), sleeper=lambda _: None,
    ).enrich(_cohort(), phase="anchors")
    assert later.snapshots_saved == 3
    assert repository.get_snapshot(first.snapshot_id) == before
    reopened = SQLiteCoreApiSnapshotRepository(path)
    assert YahooSecondarySnapshotStore(reopened).latest("NSE:INE0000001") is not None
    assert repository.get_snapshot(first.snapshot_id).payload == before.payload


def test_yahoo_failure_taxonomy_is_explicit_and_safe():
    assert _failure(RuntimeError("429 too many requests"))[0] is YahooDatasetStatus.RATE_LIMITED
    assert _failure(TimeoutError("timeout"))[0] is YahooDatasetStatus.TRANSIENT_ERROR
    assert _failure(AttributeError("get_news unexpected keyword"))[0] is YahooDatasetStatus.UNSUPPORTED
    assert _failure(RuntimeError("provider rejected request"))[0] is YahooDatasetStatus.PROVIDER_ERROR


def test_yahoo_failures_and_empty_datasets_are_explicit_and_do_not_mutate_authoritative_families(tmp_path):
    repository = SQLiteCoreApiSnapshotRepository(tmp_path / "snapshots.sqlite")
    service = YahooSecondaryEnrichmentService(
        store=YahooSecondarySnapshotStore(repository), ticker_factory=lambda symbol: _Ticker(symbol, failure=RuntimeError("429 rate limit")),
        clock=lambda: T, sleeper=lambda _: None,
    )
    report = service.enrich(_cohort(), phase="anchors")
    snapshot = YahooSecondarySnapshotStore(repository).latest("NSE:INE0000001")
    assert snapshot is not None
    info = next(item for item in snapshot.datasets if item.dataset == "valuation_snapshot")
    assert info.status is YahooDatasetStatus.RATE_LIMITED and info.error_code == "RATE_LIMITED"
    assert any(item.status is YahooDatasetStatus.EMPTY for item in snapshot.datasets)
    assert report.failures and all("RATE_LIMITED" in item for item in report.failures)
    assert not repository.list_snapshots(CoreApiSnapshotFamily.HISTORICAL_CORPORATE_ACTION, limit=1)
    assert not repository.list_snapshots(CoreApiSnapshotFamily.APPROVED_STRATEGY_VERSION, limit=1)
