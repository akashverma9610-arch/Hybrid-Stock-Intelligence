"""Bounded Yahoo Finance secondary-research enrichment for the frozen cohort.

The module intentionally stores raw, observed-at-fetch evidence only.  It is
not a financial-fact importer, does not change canonical taxonomy, and is not
consumed by the stored-data Brain input assembler.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime
from enum import StrEnum
from hashlib import sha256
from pathlib import Path
from time import sleep
from typing import Any, Callable, Iterable, Mapping, Sequence
from uuid import uuid4
import csv
import json
import math

from app.fundamentals.models import FinancialFact, FinancialMetric
from app.market_data.yfinance import yahoo_nse_mapping
from app.storage.core_api_snapshot_repository import CoreApiSnapshot, CoreApiSnapshotFamily, CoreApiSnapshotRepository
from app.universe_analysis.models import NseEquityInstrument


class YahooDatasetStatus(StrEnum):
    READY = "READY"
    EMPTY = "EMPTY"
    UNSUPPORTED = "UNSUPPORTED"
    RATE_LIMITED = "RATE_LIMITED"
    TRANSIENT_ERROR = "TRANSIENT_ERROR"
    PROVIDER_ERROR = "PROVIDER_ERROR"


@dataclass(frozen=True, slots=True)
class YahooFinancialRow:
    raw_label: str
    canonical_candidate: str | None
    raw_value: str | None
    report_period: str | None
    fetched_at: datetime
    confidence: str
    mapping_version: str = "yahoo-secondary-financial-alias-v1"


@dataclass(frozen=True, slots=True)
class YahooSecondaryDataset:
    dataset: str
    status: YahooDatasetStatus
    fetched_at: datetime
    provider: str
    source_class: str
    pit_semantics: str
    canonical: bool
    raw_payload: Mapping[str, Any]
    financial_rows: tuple[YahooFinancialRow, ...] = ()
    error_code: str | None = None


@dataclass(frozen=True, slots=True)
class YahooSecondarySnapshot:
    snapshot_id: str
    instrument_id: str
    symbol: str
    yahoo_symbol: str
    fetched_at: datetime
    provider: str
    source_class: str
    pit_semantics: str
    canonical: bool
    taxonomy_status: str
    sector_hint: str | None
    industry_hint: str | None
    datasets: tuple[YahooSecondaryDataset, ...]
    fingerprint: str
    warnings: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class YahooEnrichmentReport:
    run_id: str
    phase: str
    requested: int
    snapshots_saved: int
    availability: Mapping[str, int]
    median_quarterly_periods: int
    median_annual_periods: int
    per_symbol: tuple[Mapping[str, Any], ...]
    reconciliation: tuple[Mapping[str, Any], ...]
    action_reconciliation: tuple[Mapping[str, Any], ...]
    failures: tuple[str, ...]
    provider_requests: int
    report_json: str | None = None
    report_csv: str | None = None


_PROVENANCE = {
    "provider": "YAHOO_FINANCE",
    "source_class": "SECONDARY_RESEARCH",
    "pit_semantics": "OBSERVED_AT_FETCH_ONLY",
    "canonical": False,
}

# These aliases only nominate a possible canonical counterpart for comparison;
# no Yahoo row becomes a canonical FinancialFact.
_FINANCIAL_ALIASES = {
    "total revenue": FinancialMetric.REVENUE,
    "operating revenue": FinancialMetric.REVENUE,
    "other non operating income expenses": FinancialMetric.OTHER_INCOME,
    "other income expense": FinancialMetric.OTHER_INCOME,
    "ebitda": FinancialMetric.EBITDA,
    "operating income": FinancialMetric.OPERATING_PROFIT,
    "pretax income": FinancialMetric.PBT,
    "tax provision": FinancialMetric.TAX,
    "net income": FinancialMetric.PAT,
    "basic eps": FinancialMetric.EPS_BASIC,
    "diluted eps": FinancialMetric.EPS_DILUTED,
    "interest expense": FinancialMetric.FINANCE_COST,
    "reconciled depreciation": FinancialMetric.DEPRECIATION,
    "depreciation": FinancialMetric.DEPRECIATION,
    "total assets": FinancialMetric.TOTAL_ASSETS,
    "total liabilities net minority interest": FinancialMetric.TOTAL_LIABILITIES,
    "stockholders equity": FinancialMetric.TOTAL_EQUITY,
    "total debt": FinancialMetric.TOTAL_DEBT,
    "cash cash equivalents and short term investments": FinancialMetric.CASH_AND_EQUIVALENTS,
    "current assets": FinancialMetric.CURRENT_ASSETS,
    "current liabilities": FinancialMetric.CURRENT_LIABILITIES,
    "inventory": FinancialMetric.INVENTORY,
    "accounts receivable": FinancialMetric.RECEIVABLES,
    "accounts payable": FinancialMetric.PAYABLES,
    "operating cash flow": FinancialMetric.CFO,
    "investing cash flow": FinancialMetric.CFI,
    "financing cash flow": FinancialMetric.CFF,
    "capital expenditure": FinancialMetric.CAPEX,
}


class YahooSecondarySnapshotStore:
    """Append-only storage through the existing core snapshot repository."""

    def __init__(self, repository: CoreApiSnapshotRepository) -> None:
        self._repository = repository

    def save(self, snapshot: YahooSecondarySnapshot) -> None:
        self._repository.save_snapshot(CoreApiSnapshot(
            snapshot.snapshot_id, CoreApiSnapshotFamily.YAHOO_SECONDARY_ENRICHMENT,
            "v1", "yahoo-secondary-enrichment-v1", snapshot.fingerprint,
            snapshot.fetched_at, snapshot,
        ))

    def latest(self, instrument_id: str) -> YahooSecondarySnapshot | None:
        offset = 0
        values: list[YahooSecondarySnapshot] = []
        while True:
            page = self._repository.list_snapshots(CoreApiSnapshotFamily.YAHOO_SECONDARY_ENRICHMENT, limit=100, offset=offset)
            values.extend(item.payload for item in page if isinstance(item.payload, YahooSecondarySnapshot) and item.payload.instrument_id == instrument_id)
            if len(page) < 100:
                return max(values, key=lambda item: (item.fetched_at, item.snapshot_id)) if values else None
            offset += len(page)


class YahooSecondaryEnrichmentService:
    """Sequential, defensive extraction of raw yfinance research endpoints."""

    def __init__(
        self,
        *,
        store: YahooSecondarySnapshotStore,
        ticker_factory: Callable[[str], object] | None = None,
        official_facts: Callable[[str], Iterable[FinancialFact]] = lambda _: (),
        official_actions: Callable[[str, datetime], Iterable[object]] = lambda _identifier, _at: (),
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        sleeper: Callable[[float], None] = sleep,
        delay_seconds: float = 0.25,
    ) -> None:
        self._store, self._factory, self._facts, self._actions = store, ticker_factory, official_facts, official_actions
        self._clock, self._sleep, self._delay = clock, sleeper, delay_seconds
        self.provider_requests = 0
        self._made_provider_request = False

    def enrich(self, cohort: Sequence[NseEquityInstrument], *, phase: str) -> YahooEnrichmentReport:
        selected = _select(cohort, phase)
        run_id = "yahoo-secondary-run:" + uuid4().hex
        saved: list[YahooSecondarySnapshot] = []
        failures: list[str] = []
        for instrument in selected:
            snapshot = self._snapshot(instrument)
            self._store.save(snapshot); saved.append(snapshot)
            failures.extend(f"{instrument.symbol}:{item.dataset}:{item.error_code}" for item in snapshot.datasets if item.status not in {YahooDatasetStatus.READY, YahooDatasetStatus.EMPTY})
        report = _report(run_id, phase, saved, self._facts, self._actions, self.provider_requests, tuple(sorted(failures)))
        return report

    def write_reports(self, report: YahooEnrichmentReport, directory: str | Path = "reports") -> YahooEnrichmentReport:
        target = Path(directory); target.mkdir(parents=True, exist_ok=True)
        base = target / "yahoo_bse_reconciliation"
        json_path, csv_path = base.with_suffix(".json"), base.with_suffix(".csv")
        payload = {
            "run_id": report.run_id, "phase": report.phase, "requested": report.requested,
            "snapshots_saved": report.snapshots_saved, "availability": dict(report.availability),
            "median_quarterly_periods": report.median_quarterly_periods,
            "median_annual_periods": report.median_annual_periods,
            "per_symbol": list(report.per_symbol), "reconciliation": list(report.reconciliation),
            "action_reconciliation": list(report.action_reconciliation), "failures": list(report.failures),
            "provider_requests": report.provider_requests,
        }
        json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=_json), encoding="utf-8")
        columns = ("symbol", "report_period", "canonical_fact", "bse_value", "yahoo_value", "absolute_difference", "percentage_difference", "match_status", "yahoo_raw_label", "bse_source_id")
        with csv_path.open("w", encoding="utf-8", newline="") as output:
            writer = csv.DictWriter(output, fieldnames=columns); writer.writeheader(); writer.writerows(report.reconciliation)
        return replace(report, report_json=str(json_path), report_csv=str(csv_path))

    def _snapshot(self, instrument: NseEquityInstrument) -> YahooSecondarySnapshot:
        at = self._clock().astimezone(UTC)
        mapping = yahoo_nse_mapping(_identity(instrument))
        if mapping is None:
            return _unmapped_snapshot(instrument, at)
        ticker = self._ticker(mapping.provider_instrument_reference)
        info = self._call("valuation_snapshot", lambda: ticker.get_info())
        info_data = _selected_info(info.raw_payload) if info.status is YahooDatasetStatus.READY else {}
        datasets = [info]
        for name, operation in _operations(ticker):
            datasets.append(self._call(name, operation))
        datasets = [_financialize(item, at) if item.dataset.startswith(("quarterly_", "annual_", "trailing_")) else item for item in datasets]
        sector, industry = _string(info_data.get("sector")), _string(info_data.get("industry"))
        fingerprint = _fingerprint(instrument.instrument_id, mapping.provider_instrument_reference, at, datasets)
        return YahooSecondarySnapshot(
            "yahoo-secondary:" + uuid4().hex, instrument.instrument_id, instrument.symbol,
            mapping.provider_instrument_reference, at, **_PROVENANCE,
            taxonomy_status="SECONDARY_HINT", sector_hint=sector, industry_hint=industry,
            datasets=tuple(datasets), fingerprint=fingerprint,
            warnings=("YAHOO_SECONDARY_RESEARCH_NON_AUTHORITATIVE", "PIT_OBSERVED_AT_FETCH_ONLY", "CANONICAL_TAXONOMY_UNCHANGED"),
        )

    def _ticker(self, symbol: str):
        if self._factory is not None:
            return self._factory(symbol)
        import yfinance as yf
        return yf.Ticker(symbol)

    def _call(self, name: str, operation: Callable[[], object]) -> YahooSecondaryDataset:
        # Every yfinance operation is sequential and paced.  This deliberately
        # makes the 40-symbol pass slower than a bulk fetch rather than
        # disguising provider pressure behind parallelism.
        if self._made_provider_request:
            self._sleep(self._delay)
        self._made_provider_request = True
        at = self._clock().astimezone(UTC); self.provider_requests += 1
        try:
            value = operation(); raw = _portable(value)
            return YahooSecondaryDataset(name, YahooDatasetStatus.EMPTY if _empty(raw) else YahooDatasetStatus.READY, at, **_PROVENANCE, raw_payload=raw)
        except Exception as error:
            status, code = _failure(error)
            if status in {YahooDatasetStatus.RATE_LIMITED, YahooDatasetStatus.TRANSIENT_ERROR}:
                self._sleep(0.5)
            return YahooSecondaryDataset(name, status, at, **_PROVENANCE, raw_payload={}, error_code=code)


def _operations(ticker: object) -> tuple[tuple[str, Callable[[], object]], ...]:
    return (
        ("quarterly_income", lambda: ticker.get_income_stmt(freq="quarterly")),
        ("annual_income", lambda: ticker.get_income_stmt(freq="yearly")),
        ("trailing_income", lambda: ticker.get_income_stmt(freq="trailing")),
        ("quarterly_balance_sheet", lambda: ticker.get_balance_sheet(freq="quarterly")),
        ("annual_balance_sheet", lambda: ticker.get_balance_sheet(freq="yearly")),
        ("quarterly_cashflow", lambda: ticker.get_cashflow(freq="quarterly")),
        ("annual_cashflow", lambda: ticker.get_cashflow(freq="yearly")),
        ("trailing_cashflow", lambda: ticker.get_cashflow(freq="trailing")),
        ("earnings_dates", lambda: ticker.get_earnings_dates(limit=16)),
        ("earnings_history", lambda: ticker.get_earnings_history()),
        ("share_count_history", lambda: ticker.get_shares_full(start="2018-01-01")),
        ("major_holders", lambda: ticker.get_major_holders()),
        ("institutional_holders", lambda: ticker.get_institutional_holders()),
        ("mutualfund_holders", lambda: ticker.get_mutualfund_holders()),
        ("analyst_price_targets", lambda: ticker.get_analyst_price_targets()),
        ("earnings_estimate", lambda: ticker.get_earnings_estimate()),
        ("revenue_estimate", lambda: ticker.get_revenue_estimate()),
        ("eps_trend", lambda: ticker.get_eps_trend()),
        ("eps_revisions", lambda: ticker.get_eps_revisions()),
        ("growth_estimates", lambda: ticker.get_growth_estimates()),
        ("recommendations", lambda: ticker.get_recommendations()),
        ("recommendations_summary", lambda: ticker.get_recommendations_summary()),
        ("upgrades_downgrades", lambda: ticker.get_upgrades_downgrades()),
        ("news", lambda: ticker.get_news(count=20, tab="news")),
        ("press_releases", lambda: ticker.get_news(count=20, tab="press releases")),
        ("actions", lambda: ticker.get_actions(period="max")),
        ("dividends", lambda: ticker.get_dividends(period="max")),
        ("splits", lambda: ticker.get_splits(period="max")),
    )


def _financialize(dataset: YahooSecondaryDataset, fetched_at: datetime) -> YahooSecondaryDataset:
    rows: list[YahooFinancialRow] = []
    raw_rows = dataset.raw_payload.get("rows") if isinstance(dataset.raw_payload, Mapping) else None
    if isinstance(raw_rows, list):
        for row in raw_rows:
            if not isinstance(row, Mapping):
                continue
            label = _string(row.get("label"))
            candidate = _FINANCIAL_ALIASES.get(_normal(label)) if label else None
            for period, value in (row.get("values") or {}).items() if isinstance(row.get("values"), Mapping) else ():
                rows.append(YahooFinancialRow(label or "", candidate.value if candidate else None, _value(value), str(period), fetched_at, "EXACT_LABEL" if candidate else "UNMAPPED"))
    return YahooSecondaryDataset(dataset.dataset, dataset.status, dataset.fetched_at, dataset.provider, dataset.source_class, dataset.pit_semantics, dataset.canonical, dataset.raw_payload, tuple(rows), dataset.error_code)


def _report(run_id: str, phase: str, snapshots: Sequence[YahooSecondarySnapshot], facts: Callable[[str], Iterable[FinancialFact]], actions: Callable[[str, datetime], Iterable[object]], provider_requests: int, failures: tuple[str, ...]) -> YahooEnrichmentReport:
    availability: dict[str, int] = {}
    quarters: list[int] = []; annuals: list[int] = []; rows: list[Mapping[str, Any]] = []; reconciliation: list[Mapping[str, Any]] = []; action_rows: list[Mapping[str, Any]] = []
    for snapshot in snapshots:
        names = {item.dataset: item for item in snapshot.datasets}
        for name, item in names.items():
            if item.status is YahooDatasetStatus.READY:
                availability[name] = availability.get(name, 0) + 1
        quarter = _periods(names.get("quarterly_income")); annual = _periods(names.get("annual_income")); quarters.append(quarter); annuals.append(annual)
        rows.append({
            "symbol": snapshot.symbol,
            "datasets_ready": sum(item.status is YahooDatasetStatus.READY for item in snapshot.datasets),
            "quarterly_periods": quarter, "annual_periods": annual,
            "dataset_statuses": {name: item.status.value for name, item in sorted(names.items())},
            "missing_or_unavailable": tuple(sorted(name for name, item in names.items() if item.status is not YahooDatasetStatus.READY)),
            "sector_hint": snapshot.sector_hint, "industry_hint": snapshot.industry_hint,
            "taxonomy_status": snapshot.taxonomy_status,
        })
        official = tuple(facts(snapshot.instrument_id))
        reconciliation.extend(_reconcile_financials(snapshot, official))
        action_rows.extend(_reconcile_actions(snapshot, actions(snapshot.instrument_id, snapshot.fetched_at)))
    return YahooEnrichmentReport(run_id, phase, len(snapshots), len(snapshots), availability, _median(quarters), _median(annuals), tuple(rows), tuple(reconciliation), tuple(action_rows), failures, provider_requests)


def _reconcile_financials(snapshot: YahooSecondarySnapshot, official: Sequence[FinancialFact]) -> tuple[Mapping[str, Any], ...]:
    outputs: list[Mapping[str, Any]] = []
    yahoo_rows = [row for dataset in snapshot.datasets for row in dataset.financial_rows if row.canonical_candidate]
    for fact in official:
        candidates = [row for row in yahoo_rows if row.canonical_candidate == fact.metric.value and _period_matches(row.report_period, fact.period_end)]
        yahoo = candidates[0] if candidates else None
        # yfinance statements expose raw values without a declared numeric
        # scale.  That is insufficient for a factual comparison to an official
        # BSE fact, so retain an explicit unavailable result instead of scaling.
        outputs.append({"symbol": snapshot.symbol, "report_period": fact.period_end.date().isoformat(), "canonical_fact": fact.metric.value, "bse_value": str(fact.value), "yahoo_value": yahoo.raw_value if yahoo else None, "absolute_difference": None, "percentage_difference": None, "match_status": "UNAVAILABLE_UNIT_SCALE" if yahoo else "UNAVAILABLE", "yahoo_raw_label": yahoo.raw_label if yahoo else None, "bse_source_id": fact.fact_id})
    return tuple(outputs)


def _reconcile_actions(snapshot: YahooSecondarySnapshot, official: Sequence[object]) -> tuple[Mapping[str, Any], ...]:
    dataset = next((item for item in snapshot.datasets if item.dataset == "actions"), None)
    yahoo_rows = dataset.raw_payload.get("rows", []) if dataset and isinstance(dataset.raw_payload, Mapping) else []
    # Yahoo's action table is retained only as a secondary reconciliation aid.
    # Its ``Stock Splits`` value is a factor, not an exchange action type, so
    # it must never be promoted into the official corporate-action store.
    yahoo_events: list[dict[str, str | None]] = []
    for row in yahoo_rows if isinstance(yahoo_rows, list) else ():
        if not isinstance(row, Mapping):
            continue
        values = row.get("values")
        if not isinstance(values, Mapping):
            continue
        date = _date_key(row.get("label"))
        dividend, split = values.get("Dividends"), values.get("Stock Splits")
        if _nonzero(dividend):
            yahoo_events.append({"date": date, "kind": "DIVIDEND", "ratio": None})
        if _nonzero(split):
            yahoo_events.append({"date": date, "kind": "SPLIT_OR_BONUS", "ratio": _value(split)})
    official_events = tuple(official)
    output: list[Mapping[str, Any]] = []
    used: set[int] = set()
    for event in official_events:
        date = _date_key(getattr(event, "effective_date", None))
        kind = getattr(getattr(event, "kind", None), "value", None) or _value(getattr(event, "kind", None))
        ratio = _ratio(getattr(event, "ratio_numerator", None), getattr(event, "ratio_denominator", None))
        matched = next((index for index, item in enumerate(yahoo_events) if index not in used and item["date"] == date and _action_compatible(str(kind), item["kind"])), None)
        if matched is None:
            output.append({"symbol": snapshot.symbol, "date": date, "nse_kind": kind, "nse_ratio": ratio, "yahoo_kind": None, "yahoo_ratio": None, "status": "NSE_ONLY"})
            continue
        used.add(matched); yahoo = yahoo_events[matched]
        status = "MATCH" if ratio is None or yahoo["ratio"] is None or _same_ratio(ratio, yahoo["ratio"]) else "RATIO_MISMATCH"
        output.append({"symbol": snapshot.symbol, "date": date, "nse_kind": kind, "nse_ratio": ratio, "yahoo_kind": yahoo["kind"], "yahoo_ratio": yahoo["ratio"], "status": status})
    for index, yahoo in enumerate(yahoo_events):
        if index not in used:
            output.append({"symbol": snapshot.symbol, "date": yahoo["date"], "nse_kind": None, "nse_ratio": None, "yahoo_kind": yahoo["kind"], "yahoo_ratio": yahoo["ratio"], "status": "YAHOO_ONLY"})
    return tuple(output or ({"symbol": snapshot.symbol, "date": None, "nse_kind": None, "nse_ratio": None, "yahoo_kind": None, "yahoo_ratio": None, "status": "NO_ACTIONS"},))


def _portable(value: object) -> Mapping[str, Any]:
    """Bound tabular yfinance output without retaining pandas objects."""
    if value is None:
        return {}
    if hasattr(value, "iterrows") and hasattr(value, "columns"):
        rows = []
        for index, row in value.iterrows():
            values = {str(key): _scalar(item) for key, item in row.to_dict().items()}
            rows.append({"label": _scalar(index), "values": values})
        return {"kind": "table", "columns": tuple(str(item) for item in value.columns), "rows": rows[:250]}
    if hasattr(value, "items") and hasattr(value, "index") and not isinstance(value, Mapping):
        return {"kind": "series", "rows": [{"label": _scalar(index), "value": _scalar(item)} for index, item in value.items()][:250]}
    if isinstance(value, Mapping):
        return {str(key): _portable(item) if hasattr(item, "iterrows") else _scalar(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return {"kind": "list", "items": [_portable(item) if isinstance(item, Mapping) else _scalar(item) for item in value[:250]]}
    return {"value": _scalar(value)}


def _selected_info(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    allowed = {"symbol", "shortName", "longName", "exchange", "quoteType", "currency", "financialCurrency", "sector", "industry", "marketCap", "enterpriseValue", "sharesOutstanding", "floatShares", "impliedSharesOutstanding", "trailingPE", "forwardPE", "priceToBook", "enterpriseToRevenue", "enterpriseToEbitda", "trailingEps", "forwardEps", "bookValue", "beta", "dividendYield", "payoutRatio", "totalRevenue", "ebitda", "operatingCashflow", "freeCashflow", "totalCash", "totalDebt", "debtToEquity", "currentRatio", "quickRatio", "returnOnAssets", "returnOnEquity", "grossMargins", "operatingMargins", "profitMargins", "revenueGrowth", "earningsGrowth", "heldPercentInsiders", "heldPercentInstitutions"}
    return {key: payload[key] for key in allowed if key in payload and payload[key] is not None}


def _failure(error: Exception) -> tuple[YahooDatasetStatus, str]:
    text = str(error).lower(); name = type(error).__name__.upper()
    if any(item in text for item in ("429", "rate limit", "too many request")):
        return YahooDatasetStatus.RATE_LIMITED, "RATE_LIMITED"
    if isinstance(error, (TimeoutError, ConnectionError)) or any(item in text for item in ("timeout", "temporar", "connection reset")):
        return YahooDatasetStatus.TRANSIENT_ERROR, "TRANSIENT_ERROR"
    if isinstance(error, (AttributeError, TypeError)) and ("get_" in text or "unexpected keyword" in text):
        return YahooDatasetStatus.UNSUPPORTED, "UNSUPPORTED"
    return YahooDatasetStatus.PROVIDER_ERROR, name[:80]


def _identity(item: NseEquityInstrument):
    from app.market_data.models import Exchange, InstrumentIdentity, InstrumentType
    return InstrumentIdentity(item.instrument_id, Exchange.NSE, item.symbol, item.symbol, item.isin, None, InstrumentType.NSE_EQUITY, item.company_name)


def _unmapped_snapshot(instrument: NseEquityInstrument, at: datetime) -> YahooSecondarySnapshot:
    dataset = YahooSecondaryDataset("mapping", YahooDatasetStatus.PROVIDER_ERROR, at, **_PROVENANCE, raw_payload={}, error_code="YAHOO_NSE_MAPPING_UNAVAILABLE")
    return YahooSecondarySnapshot("yahoo-secondary:" + uuid4().hex, instrument.instrument_id, instrument.symbol, "", at, **_PROVENANCE, taxonomy_status="SECONDARY_HINT", sector_hint=None, industry_hint=None, datasets=(dataset,), fingerprint=_fingerprint(instrument.instrument_id, "", at, (dataset,)), warnings=("YAHOO_NSE_MAPPING_UNAVAILABLE",))


def _select(cohort: Sequence[NseEquityInstrument], phase: str) -> tuple[NseEquityInstrument, ...]:
    if len(cohort) != 40 or len({item.instrument_id for item in cohort}) != 40:
        raise ValueError("YAHOO_SECONDARY_ENRICHMENT_REQUIRES_FROZEN_40_COHORT")
    if phase == "anchors":
        expected = {"APOLLOHOSP", "SAFARI", "ORIENTTECH"}; values = tuple(item for item in cohort if item.symbol in expected)
        if {item.symbol for item in values} != expected:
            raise ValueError("YAHOO_SECONDARY_ANCHOR_COHORT_UNAVAILABLE")
        return tuple(sorted(values, key=lambda item: item.symbol))
    if phase == "frozen-40":
        return tuple(sorted(cohort, key=lambda item: item.symbol))
    raise ValueError("YAHOO_SECONDARY_PHASE_MUST_BE_ANCHORS_OR_FROZEN_40")


def _fingerprint(instrument_id: str, symbol: str, at: datetime, datasets: Sequence[YahooSecondaryDataset]) -> str:
    value = "|".join((instrument_id, symbol, at.isoformat(), *(f"{item.dataset}:{item.status.value}:{json.dumps(item.raw_payload, sort_keys=True, default=_json)}" for item in datasets)))
    return sha256(value.encode()).hexdigest()


def _periods(dataset: YahooSecondaryDataset | None) -> int:
    if dataset is None: return 0
    rows = dataset.raw_payload.get("rows") if isinstance(dataset.raw_payload, Mapping) else None
    if not isinstance(rows, list): return 0
    values = {str(period) for row in rows if isinstance(row, Mapping) and isinstance(row.get("values"), Mapping) for period in row["values"]}
    return len(values)


def _period_matches(value: str | None, at: datetime) -> bool:
    if not value: return False
    return at.date().isoformat() in value or at.strftime("%Y-%m-%d") in value


def _median(values: Sequence[int]) -> int:
    values = sorted(values); return values[len(values) // 2] if values else 0
def _normal(value: str | None) -> str: return " ".join((value or "").replace("_", " ").replace("-", " ").lower().split())
def _string(value: object) -> str | None: return value.strip() if isinstance(value, str) and value.strip() else None
def _value(value: object) -> str | None: return None if value is None else str(value)
def _empty(value: Mapping[str, Any]) -> bool:
    return not value or (
        value.get("kind") in {"table", "series", "list"}
        and not value.get("rows", value.get("items", ()))
    )
def _json(value: object): return value.isoformat() if isinstance(value, datetime) else str(value)


def _date_key(value: object) -> str | None:
    if isinstance(value, datetime): return value.date().isoformat()
    text = _value(value)
    return text[:10] if text and len(text) >= 10 else text


def _nonzero(value: object) -> bool:
    try: return float(str(value)) != 0.0
    except (TypeError, ValueError): return False


def _ratio(numerator: object, denominator: object) -> str | None:
    if numerator is None or denominator is None: return None
    try: return str(float(str(numerator)) / float(str(denominator)))
    except (TypeError, ValueError, ZeroDivisionError): return None


def _same_ratio(left: str, right: str | None) -> bool:
    try: return right is not None and abs(float(left) - float(right)) < 0.000001
    except ValueError: return False


def _action_compatible(official: str, yahoo: str | None) -> bool:
    return official == yahoo or (official in {"SPLIT", "BONUS"} and yahoo == "SPLIT_OR_BONUS")


def _scalar(value: object) -> Any:
    if value is None: return None
    if isinstance(value, datetime): return value.isoformat()
    if hasattr(value, "to_pydatetime"):
        return value.to_pydatetime().isoformat()
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)): return None
    if isinstance(value, (str, int, float, bool)): return value
    return str(value)


__all__ = ("YahooDatasetStatus", "YahooSecondaryDataset", "YahooSecondaryEnrichmentService", "YahooSecondarySnapshot", "YahooSecondarySnapshotStore", "YahooEnrichmentReport")
