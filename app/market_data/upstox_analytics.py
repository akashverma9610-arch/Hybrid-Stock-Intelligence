"""Bounded, read-only Upstox Analytics fundamentals feasibility probes.

The module is deliberately an evidence collector, not a fundamentals ingestion
adapter. It never writes canonical facts, taxonomy, filings, or Brain inputs.
Provider values are reduced to secret-safe structural evidence; API retrieval
time and financial period labels are never treated as publication timestamps.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Callable, Iterable, Mapping
from urllib.error import URLError
from urllib.parse import urlencode

import requests

from app.fundamentals.models import FinancialFact, FinancialMetric, FinancialValueDimension


UPSTOX_ANALYTICS_BASE_URL = "https://api.upstox.com/v2/fundamentals"
APOLLOHOSP_ISIN = "INE437A01024"
APOLLOHOSP_SYMBOL = "APOLLOHOSP"
# Retained only as a stable identity constant for prior callers; U04 does not
# request Historical V3 and does not call it.
APOLLOHOSP_INSTRUMENT_KEY = "NSE_EQ|INE437A01024"

# Exactly the nine documented Fundamentals endpoints authorised for U04.
FUNDAMENTALS_ENDPOINTS: tuple[tuple[str, str, Mapping[str, str]], ...] = (
    ("profile", "profile", {}),
    ("income_statement_quarterly", "income-statement", {"type": "consolidated", "time_period": "quarterly", "fs": "false"}),
    ("income_statement_yearly_full", "income-statement", {"type": "consolidated", "time_period": "yearly", "fs": "true"}),
    ("balance_sheet", "balance-sheet", {"type": "consolidated", "fs": "true"}),
    ("cash_flow", "cash-flow", {"type": "consolidated", "fs": "true"}),
    ("share_holdings", "share-holdings", {}),
    ("key_ratios", "key-ratios", {}),
    ("corporate_actions", "corporate-actions", {}),
    ("competitors", "competitors", {}),
)
_ARRAY_DATA_ENDPOINTS = frozenset({"share_holdings", "key_ratios", "corporate_actions"})


@dataclass(frozen=True, slots=True)
class UpstoxAnalyticsEndpointResult:
    endpoint: str
    http_status: int | None
    status: str
    summary: Mapping[str, object]
    method: str = "GET"
    safe_url: str = ""
    safe_query_params: Mapping[str, str] | None = None
    content_type: str | None = None
    upstox_status: str | None = None
    top_level_schema: tuple[str, ...] = ()
    data_schema_summary: Mapping[str, object] | None = None
    record_count: int = 0
    periods: tuple[str, ...] = ()
    units: str | None = None
    statement_type: str | None = None
    time_period: str | None = None
    full_statement_present: bool | None = None
    timestamp_fields_detected: tuple[Mapping[str, str], ...] = ()
    pit_quality: str = "OBSERVED_AT_FETCH_ONLY"
    error_code: str | None = None
    error_message: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "safe_query_params", dict(self.safe_query_params or {}))
        object.__setattr__(self, "data_schema_summary", dict(self.data_schema_summary or {}))


@dataclass(frozen=True, slots=True)
class UpstoxAnalyticsFeasibilityResult:
    isin: str
    symbol: str | None
    instrument_key: str | None
    credential_accepted: bool
    endpoints: tuple[UpstoxAnalyticsEndpointResult, ...]
    reconciliation: tuple[Mapping[str, object], ...]
    pit_timestamp_fields: tuple[str, ...]
    stopped_early: bool = False
    stop_reason: str | None = None


Transport = Callable[[str, Mapping[str, str]], tuple[int, object]]


class UpstoxAnalyticsFeasibilityTester:
    """Run the bounded, sequential Fundamentals probe using U03 transport."""

    def __init__(
        self,
        access_token: str | None,
        *,
        isin: str = APOLLOHOSP_ISIN,
        symbol: str | None = APOLLOHOSP_SYMBOL,
        transport: Transport | None = None,
        bse_facts: Iterable[FinancialFact] = (),
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        timeout_seconds: float = 20.0,
    ) -> None:
        self._token = _token(access_token)
        self._isin, self._symbol = isin, symbol
        self._transport = transport or self._https_transport
        self._bse_facts = tuple(bse_facts)
        self._clock, self._timeout = clock, timeout_seconds
        self._content_types: dict[str, str | None] = {}

    def run(self) -> UpstoxAnalyticsFeasibilityResult:
        if not self._token:
            result = UpstoxAnalyticsEndpointResult(
                "credentials", None, "FAILED", {}, error_code="MISSING_CONFIGURATION",
                error_message="Upstox Analytics Token is not configured.",
            )
            return UpstoxAnalyticsFeasibilityResult(self._isin, self._symbol, _instrument_key(self._isin), False, (result,), (), ())
        results: list[UpstoxAnalyticsEndpointResult] = []
        stopped = False
        for name, resource, query in FUNDAMENTALS_ENDPOINTS:
            result = self._fundamentals(name, resource, query)
            results.append(result)
            if result.error_code == "CLOUDFLARE_1010":
                stopped = True
                break
        by_endpoint = {item.endpoint: item for item in results}
        reconciliation = _reconcile(self._bse_facts, by_endpoint.get("income_statement_quarterly"))
        timestamps = tuple(sorted({
            item["field"] for result in results if result.status == "SUCCESS"
            for item in result.timestamp_fields_detected
        }))
        return UpstoxAnalyticsFeasibilityResult(
            self._isin, self._symbol, _instrument_key(self._isin), any(item.http_status == 200 for item in results),
            tuple(results), reconciliation, timestamps, stopped,
            "CLOUDFLARE_1010" if stopped else None,
        )

    def _fundamentals(self, name: str, resource: str, query: Mapping[str, str]) -> UpstoxAnalyticsEndpointResult:
        safe_url = f"{UPSTOX_ANALYTICS_BASE_URL}/{self._isin}/{resource}"
        url = safe_url + (("?" + urlencode(query)) if query else "")
        return self._request(name, safe_url, query, url)

    def _request(self, name: str, safe_url: str, query: Mapping[str, str], url: str) -> UpstoxAnalyticsEndpointResult:
        try:
            status, payload = self._transport(url, _headers(self._token))
        except (TimeoutError, URLError, OSError):
            return _failed(name, safe_url, query, None, "PROVIDER_UNAVAILABLE", "Upstox provider is unavailable.")
        except Exception:
            return _failed(name, safe_url, query, None, "PROVIDER_RESPONSE_INVALID", "Upstox provider response is invalid.")
        content_type = self._content_types.get(url)
        if status != 200:
            code, message = _provider_error(payload, status)
            if name == "competitors" and status == 400:
                code = "PROVIDER_ENDPOINT_DISCREPANCY"
            return _failed(name, safe_url, query, status, code, message, content_type=content_type)
        if not isinstance(payload, Mapping):
            return _failed(name, safe_url, query, status, "MALFORMED_RESPONSE", "Upstox response is malformed.", content_type=content_type)
        upstox_status = _text(payload.get("status"))
        if str(payload.get("status", "success")).lower() not in {"success", "ok"}:
            code, message = _provider_error(payload, status)
            return _failed(name, safe_url, query, status, code, message, content_type=content_type, upstox_status=upstox_status)
        data = payload.get("data")
        if not isinstance(data, Mapping) and not (name in _ARRAY_DATA_ENDPOINTS and isinstance(data, (list, tuple))):
            return _failed(name, safe_url, query, status, "MALFORMED_RESPONSE", "Upstox response has no data object.", content_type=content_type, upstox_status=upstox_status)
        timestamps = _timestamp_fields(data)
        return UpstoxAnalyticsEndpointResult(
            name, status, "SUCCESS", _summarize_fundamentals(name, data), safe_url=safe_url,
            safe_query_params=query, content_type=content_type, upstox_status=upstox_status,
            top_level_schema=tuple(sorted(str(key) for key in payload)), data_schema_summary=_schema_summary(data),
            record_count=_record_count(data), periods=_periods(data), units=_text(data.get("units_in")) if isinstance(data, Mapping) else None,
            statement_type=_text(data.get("type")) if isinstance(data, Mapping) else None, time_period=_text(data.get("time_period")) if isinstance(data, Mapping) else None,
            full_statement_present=bool(_rows(data.get("full_statement"))) if isinstance(data, Mapping) else False, timestamp_fields_detected=timestamps,
            pit_quality="PUBLICATION_TIMESTAMP_PRESENT" if any(item["semantic"] == "PUBLICATION_OR_FILING" for item in timestamps) else "OBSERVED_AT_FETCH_ONLY",
        )

    def _https_transport(self, url: str, headers: Mapping[str, str]) -> tuple[int, object]:
        try:
            response = requests.get(url, headers=dict(headers), timeout=self._timeout)
            self._content_types[url] = getattr(response, "headers", {}).get("Content-Type")
            text = response.content.decode("utf-8", errors="replace")
            try:
                body: object = json.loads(text)
            except json.JSONDecodeError:
                body = ({"status": "error", "code": "CLOUDFLARE_1010", "message": "Provider blocked this HTTP client signature."}
                        if response.status_code == 403 and ("1010" in text or "browser_signature_banned" in text.lower()) else {})
            return response.status_code, body
        except requests.RequestException as error:
            raise URLError("Upstox Analytics request failed.") from error


def _headers(token: str | None) -> Mapping[str, str]:
    return {"Content-Type": "application/json", "Accept": "application/json", "Authorization": f"Bearer {token}"}


def _instrument_key(isin: str) -> str | None:
    return APOLLOHOSP_INSTRUMENT_KEY if isin == APOLLOHOSP_ISIN else None


def _failed(name: str, safe_url: str, query: Mapping[str, str], status: int | None, code: str, message: str, *, content_type: str | None = None, upstox_status: str | None = None) -> UpstoxAnalyticsEndpointResult:
    return UpstoxAnalyticsEndpointResult(name, status, "FAILED", {}, safe_url=safe_url, safe_query_params=query, content_type=content_type, upstox_status=upstox_status, error_code=code, error_message=message)


def _token(value: str | None) -> str | None:
    token = value.strip() if isinstance(value, str) else ""
    while token.lower().startswith("bearer "):
        token = token[7:].strip()
    return token or None


def _provider_error(payload: object, status: int | None) -> tuple[str, str]:
    if isinstance(payload, Mapping):
        errors = payload.get("errors")
        first = errors[0] if isinstance(errors, list) and errors and isinstance(errors[0], Mapping) else {}
        raw_code = payload.get("code") or payload.get("error_code") or first.get("code")
        raw_message = payload.get("message") or payload.get("error") or first.get("message")
        if raw_code or raw_message:
            return str(raw_code).strip().upper() if raw_code else _status_code(status), str(raw_message).strip() if raw_message else "Upstox request failed."
    return _status_code(status), "Upstox request failed."


def _status_code(status: int | None) -> str:
    return {401: "ACCESS_TOKEN_REJECTED", 403: "PROVIDER_PERMISSION_DENIED", 404: "RESOURCE_UNAVAILABLE", 429: "RATE_LIMITED"}.get(status, "PROVIDER_REQUEST_FAILED")


def _summarize_fundamentals(name: str, data: Mapping[str, object] | tuple[object, ...] | list[object]) -> Mapping[str, object]:
    if name == "profile":
        return {"sector": _text(data.get("sector")), "industry": _text(data.get("industry")), "company_profile_available": bool(_text(data.get("company_profile"))), "taxonomy_role": "SECONDARY_VENDOR_RECONCILIATION_ONLY"}
    if name.startswith("income_statement"):
        statement, full = _rows(data.get("income_statement")), _rows(data.get("full_statement"))
        categories, raw = _labels(statement), _labels(full)
        periods = _periods(statement)
        return {"categories": categories, "raw_full_statement_labels": raw, "period_count": len(periods), "oldest_period": periods[0] if periods else None, "newest_period": periods[-1] if periods else None, "revenue_available": _has_label(categories + raw, "revenue"), "operating_profit_available": _has_label(categories + raw, "operating profit", "ebitda"), "net_profit_available": _has_label(categories + raw, "profit after tax", "net profit"), "direct_fields_available": _fields_available(categories + raw), "quarterly_entries": _quarterly_entries(statement)}
    if name == "balance_sheet": return _statement_summary(data, ("equity", "borrowings", "debt", "cash", "current assets", "current liabilities", "fixed assets", "capital employed"))
    if name == "cash_flow": return _statement_summary(data, ("operating", "investing", "financing", "capex", "capital expenditure", "purchase of fixed assets"))
    if name == "share_holdings":
        rows = _rows(data) if not isinstance(data, Mapping) else _first_rows(data, "share_holding", "share_holdings", "history")
        histories = tuple(entry for row in rows for entry in _rows(row.get("history")))
        periods = _periods(histories)
        text = " ".join(_normal(value) for value in _walk_text(rows)); depth = len(periods)
        return {"categories": tuple(sorted({_text(row.get("category")) for row in rows if _text(row.get("category"))})), "periods": periods, "period_count": depth, "history_depth": depth, "at_least_5_quarters": depth >= 5, "at_least_8_quarters": depth >= 8, "at_least_12_quarters": depth >= 12, "promoter_available": "promoter" in text, "fii_available": "fii" in text or "foreign" in text, "dii_or_mutual_fund_available": "dii" in text or "mutual" in text, "public_available": "public" in text or "retail" in text, "pledge_available": "pledge" in text}
    if name == "key_ratios":
        rows = _rows(data) if not isinstance(data, Mapping) else _first_rows(data, "key_ratios", "history")
        labels = _labels(rows) + tuple(_normal(value) for value in _walk_text(rows))
        historical = bool(_periods(rows))
        return {"ratios": tuple({"name": _text(row.get("name")), "company_value": row.get("company_value"), "sector_value": row.get("sector_value")} for row in rows), "raw_ratio_labels": tuple(sorted(set(labels))), "roce_available": _has_label(labels, "roce"), "roe_available": _has_label(labels, "roe"), "roa_available": _has_label(labels, "roa"), "pe_available": _has_label(labels, "p/e", "pe ratio"), "pb_available": _has_label(labels, "p/b", "pb ratio"), "ev_ebitda_available": _has_label(labels, "ev/ebitda", "ev ebitda"), "classification": "HISTORY_PRESENT" if historical else "CURRENT_SNAPSHOT_ONLY"}
    if name == "corporate_actions":
        rows = _rows(data) if not isinstance(data, Mapping) else _first_rows(data, "corporate_actions", "actions", "history")
        text = " ".join(_normal(value) for value in _walk_text(rows)); fields = set(_walk_keys(rows))
        return {"event_count": len(rows), "event_types": tuple(sorted({_text(row.get("name")) for row in rows if _text(row.get("name"))})), "events": tuple(_corporate_action_summary(row) for row in rows), "split_available": "split" in text, "bonus_available": "bonus" in text, "rights_available": "right" in text, "dividend_available": "dividend" in text, "announcement_date_available": any("announcement" in key for key in fields), "ex_date_available": any(key in {"ex_date", "exdate"} for key in fields), "record_date_available": any("record" in key for key in fields), "authority_role": "SECONDARY_RECONCILIATION_ONLY"}
    if name == "competitors":
        rows = _first_rows(data, "competitors", "peer_companies", "data")
        return {"competitor_count": len(rows), "record_fields": tuple(sorted(set(_walk_keys(rows)))), "authority_role": "DISCOVERY_ONLY"}
    return {}


def _statement_summary(data: Mapping[str, object], labels: tuple[str, ...]) -> Mapping[str, object]:
    raw = _labels(_rows(data.get("full_statement"))) + _labels(_rows(data.get("history")))
    return {"period_count": len(_periods(data)), "raw_full_statement_labels": tuple(sorted(set(raw))), "available_fields": tuple(label for label in labels if _has_label(raw, label))}


def _reconcile(bse_facts: Iterable[FinancialFact], quarterly: UpstoxAnalyticsEndpointResult | None) -> tuple[Mapping[str, object], ...]:
    targets = ((FinancialMetric.PBT, ("profit before tax", "pbt")), (FinancialMetric.PAT, ("profit after tax", "net profit", "pat")), (FinancialMetric.EPS_BASIC, ("eps basic", "eps - basic")), (FinancialMetric.FINANCE_COST, ("finance cost", "interest expense")), (FinancialMetric.DEPRECIATION, ("depreciation",)))
    entries = quarterly.summary.get("quarterly_entries", ()) if quarterly and quarterly.status == "SUCCESS" else ()
    unit = quarterly.units if quarterly else None; rows: list[Mapping[str, object]] = []
    for metric, labels in targets:
        bse = next((fact for fact in bse_facts if fact.metric is metric), None)
        dimension = bse.value_dimension if bse else FinancialValueDimension.MONETARY
        bse_value = _bse_comparable_value(bse) if bse else None
        value = _quarterly_value(entries, labels, bse.period_end if bse else None)
        upstox_value = _upstox_comparable_value(value, unit, dimension) if value is not None else None
        status = "RAW_MAPPING_UNRESOLVED" if bse is None else "UPSTOX_UNAVAILABLE" if value is None else "UNIT_UNAVAILABLE" if bse_value is None or upstox_value is None else "MATCH" if bse_value == upstox_value else "ROUNDING_DIFFERENCE" if abs(bse_value - upstox_value) <= Decimal("0.01") else "VALUE_MISMATCH"
        rows.append(_reconciliation_row(metric.value, bse, dimension, value, unit, _matching_label(entries, labels), bse_value, upstox_value, status))
    # Upstox's quarterly ``revenue`` is deliberately not mapped to BSE
    # RevenueFromOperations. The APOLLOHOSP evidence indicates a total-revenue
    # candidate, so expose the deterministic Revenue + OtherIncome relation.
    revenue = next((fact for fact in bse_facts if fact.metric is FinancialMetric.REVENUE), None)
    other_income = next((fact for fact in bse_facts if fact.metric is FinancialMetric.OTHER_INCOME), None)
    total = (_bse_comparable_value(revenue) if revenue else None)
    other = (_bse_comparable_value(other_income) if other_income else None)
    total = total + other if total is not None and other is not None else None
    candidate = _quarterly_value(entries, ("revenue",), revenue.period_end if revenue else None)
    candidate_crore = _upstox_comparable_value(candidate, unit, FinancialValueDimension.MONETARY) if candidate is not None else None
    status = "RAW_MAPPING_UNRESOLVED" if total is None else "UPSTOX_UNAVAILABLE" if candidate_crore is None else "TOTAL_REVENUE_CANDIDATE_MATCH" if total == candidate_crore else "TOTAL_REVENUE_CANDIDATE_ROUNDING_DIFFERENCE" if abs(total - candidate_crore) <= Decimal("0.01") else "TOTAL_REVENUE_CANDIDATE_VALUE_MISMATCH"
    rows.append({"metric": "TOTAL_REVENUE_CANDIDATE", "canonical_mapping": "NOT_PROMOTED", "relation": "BSE_REVENUE_FROM_OPERATIONS_PLUS_OTHER_INCOME", "bse_revenue_from_operations_crore": str(_bse_comparable_value(revenue)) if revenue else None, "bse_other_income_crore": str(other) if other is not None else None, "bse_total_revenue_candidate_crore": str(total) if total is not None else None, "upstox_raw_label": _matching_label(entries, ("revenue",)), "upstox_value": str(candidate) if candidate is not None else None, "upstox_unit": unit, "normalized_comparable_value_crore": str(candidate_crore) if candidate_crore is not None else None, "status": status})
    return tuple(rows)


def _reconciliation_row(metric: str, fact: FinancialFact | None, dimension: FinancialValueDimension, value: Decimal | None, unit: str | None, raw_label: str | None, bse_value: Decimal | None, upstox_value: Decimal | None, status: str) -> Mapping[str, object]:
    comparable_unit = "INR_CRORE" if dimension is FinancialValueDimension.MONETARY else "PER_SHARE" if dimension is FinancialValueDimension.PER_SHARE else dimension.value
    return {"metric": metric, "dimension": dimension.value, "period": fact.period_end.isoformat() if fact else None, "bse_value": str(fact.value) if fact else None, "bse_unit": f"{fact.unit}:{fact.scale.value}" if fact else None, "bse_scale_interpretation": "DISPLAY_ROUNDING_METADATA_RAW_UNIT_VALUE" if fact and fact.source == "BSE_OFFICIAL" else None, "upstox_raw_label": raw_label, "upstox_value": str(value) if value is not None else None, "upstox_unit": unit, "comparable_unit": comparable_unit, "bse_comparable_value": str(bse_value) if bse_value is not None else None, "upstox_comparable_value": str(upstox_value) if upstox_value is not None else None, "difference": str(upstox_value - bse_value) if bse_value is not None and upstox_value is not None else None, "status": status}


def _bse_comparable_value(fact: FinancialFact | None) -> Decimal | None:
    if fact is None:
        return None
    if fact.value_dimension is FinancialValueDimension.PER_SHARE:
        return fact.value
    if fact.value_dimension is not FinancialValueDimension.MONETARY:
        return None
    # BSE XBRL facts are persisted as their explicit raw INR unit values. Its
    # LevelOfRounding is source display metadata, not a multiplier for the raw
    # XBRL number, so use unit semantics rather than that display declaration.
    if fact.currency == "INR" and fact.unit == "INR":
        return _currency_units_to_crore(fact.value, fact.unit)
    return _to_crore(fact.value, fact.scale.value)


def _upstox_comparable_value(value: Decimal | None, unit: str | None, dimension: FinancialValueDimension) -> Decimal | None:
    return value if dimension is FinancialValueDimension.PER_SHARE else _to_crore(value, unit) if dimension is FinancialValueDimension.MONETARY else None


def _currency_units_to_crore(value: Decimal, unit: str) -> Decimal | None:
    factor = {"INR": Decimal("0.0000001"), "RUPEES": Decimal("0.0000001")}.get(unit.upper())
    return value * factor if factor is not None else None


def _to_crore(value: Decimal | None, unit: str | None) -> Decimal | None:
    scale = {"CRORES": Decimal("1"), "CRORE": Decimal("1"), "LAKHS": Decimal("0.01"), "LAKH": Decimal("0.01"), "MILLIONS": Decimal("0.1"), "MILLION": Decimal("0.1"), "THOUSANDS": Decimal("0.00001"), "THOUSAND": Decimal("0.00001"), "UNITS": Decimal("0.0000001"), "RUPEES": Decimal("0.0000001"), "INR CRORES": Decimal("1"), "INR CRORE": Decimal("1")}.get(_normal(unit).upper()) if unit else None
    return value * scale if value is not None and scale is not None else None


def _quarterly_value(entries: object, labels: tuple[str, ...], period_end: datetime | None) -> Decimal | None:
    target = period_end.strftime("%b %Y").lower() if period_end else None
    for entry in entries if isinstance(entries, tuple) else ():
        if not isinstance(entry, Mapping) or not _has_label((_normal(entry.get("category")),), *labels) or (target and _normal(entry.get("period")) != target): continue
        try: return Decimal(str(entry.get("value")))
        except (InvalidOperation, ValueError, TypeError): continue
    return None
def _matching_label(entries: object, labels: tuple[str, ...]) -> str | None:
    return next((_text(entry.get("category")) for entry in entries if isinstance(entry, Mapping) and _has_label((_normal(entry.get("category")),), *labels)), None) if isinstance(entries, tuple) else None
def _quarterly_entries(rows: Iterable[Mapping[str, object]]) -> tuple[Mapping[str, object], ...]: return tuple({"category": _normal(item.get("category") or item.get("particular") or item.get("name")), "period": _text(entry.get("period")), "value": entry.get("value")} for item in rows for entry in _rows(item.get("history")))
def _fields_available(values: tuple[str, ...]) -> tuple[str, ...]:
    expected = {"other income": "OTHER_INCOME", "profit before tax": "PBT", "profit after tax": "PAT", "eps basic": "EPS_BASIC", "finance cost": "FINANCE_COST", "depreciation": "DEPRECIATION"}
    return tuple(name for label, name in expected.items() if _has_label(values, label))


def _corporate_action_summary(row: Mapping[str, object]) -> Mapping[str, object]:
    event_details = _rows(row.get("event_details"))
    dates = {
        field: _text(row.get(field))
        for field in ("announcement_date", "ex_date", "record_date")
        if _text(row.get(field))
    }
    return {
        "name": _text(row.get("name")), "expiry_date": _text(row.get("expiry_date")),
        "amount": row.get("amount"), "ratio": row.get("ratio"), "dates": dates,
        "event_details": tuple({"name": _text(item.get("name")), "value": item.get("value")} for item in event_details),
    }


def _schema_summary(value: object) -> Mapping[str, object]:
    if isinstance(value, Mapping):
        lists = {str(key): {"record_count": len(rows), "record_fields": tuple(sorted(set(_walk_keys(rows))))} for key, raw in value.items() if (rows := _rows(raw))}
        return {"data_shape": "OBJECT", "data_keys": tuple(sorted(str(key) for key in value)), "list_fields": lists}
    rows = _rows(value)
    return {"data_shape": "ARRAY", "record_count": len(rows), "record_fields": tuple(sorted(set(_walk_keys(rows))))}


def _record_count(value: object) -> int:
    return sum(len(_rows(item)) for item in value.values()) if isinstance(value, Mapping) else len(_rows(value))
def _periods(value: object) -> tuple[str, ...]:
    found: set[str] = set()
    def visit(item: object) -> None:
        if isinstance(item, Mapping):
            for key, nested in item.items():
                if str(key).lower() in {"period", "period_end", "as_of_date", "date", "quarter"} and (text := _text(nested)): found.add(text)
                visit(nested)
        elif isinstance(item, (list, tuple)):
            for nested in item: visit(nested)
    visit(value); return tuple(sorted(found))
def _timestamp_fields(value: object) -> tuple[Mapping[str, str], ...]:
    result = []
    for field in sorted(set(_walk_keys(value))):
        if not any(token in field for token in ("published", "filing", "announcement", "broadcast", "submission", "as_of", "updated", "period_end", "record_date", "ex_date")): continue
        semantic = "PUBLICATION_OR_FILING" if any(token in field for token in ("published", "filing", "broadcast", "submission")) else "EVENT_ANNOUNCEMENT" if "announcement" in field else "AS_OF" if "as_of" in field else "PERIOD_END" if "period_end" in field else "UPDATED_AT" if "updated" in field else "EVENT_DATE"
        result.append({"field": field, "semantic": semantic})
    return tuple(result)
def _first_rows(data: Mapping[str, object], *keys: str) -> tuple[Mapping[str, object], ...]: return next((rows for key in keys if (rows := _rows(data.get(key)))), ())
def _labels(rows: Iterable[Mapping[str, object]]) -> tuple[str, ...]: return tuple(sorted({_normal(item.get(field)) for item in rows for field in ("category", "particular", "name", "label", "type") if _normal(item.get(field))}))
def _has_label(values: Iterable[str], *needles: str) -> bool: return any(needle in value for needle in needles for value in tuple(_normal(item) for item in values))
def _rows(value: object) -> tuple[Mapping[str, object], ...]: return tuple(item for item in value if isinstance(item, Mapping)) if isinstance(value, (list, tuple)) else ()
def _walk_keys(value: object) -> tuple[str, ...]: return tuple(str(key).lower() for key in value) + tuple(key for item in value.values() for key in _walk_keys(item)) if isinstance(value, Mapping) else tuple(key for item in value for key in _walk_keys(item)) if isinstance(value, (list, tuple)) else ()
def _walk_text(value: object) -> tuple[str, ...]: return tuple(str(key) for key in value) + tuple(text for item in value.values() for text in _walk_text(item)) if isinstance(value, Mapping) else tuple(text for item in value for text in _walk_text(item)) if isinstance(value, (list, tuple)) else (str(value),) if isinstance(value, str) else ()
def _period_count(rows: Iterable[Mapping[str, object]]) -> int: return len(_periods(tuple(rows)))
def _normal(value: object) -> str: return " ".join(str(value or "").replace("_", " ").replace("-", " ").lower().split())
def _text(value: object) -> str | None: return value.strip() if isinstance(value, str) and value.strip() else None


def write_fundamentals_probe_report(result: UpstoxAnalyticsFeasibilityResult, json_path: Path, markdown_path: Path) -> None:
    """Persist requested secret-safe structural evidence, never response bodies."""
    payload = asdict(result); text = json.dumps(payload, indent=2, sort_keys=True, default=str)
    if "bearer " in text.lower() or "access_token" in text.lower() or "authorization" in text.lower(): raise ValueError("Refusing to write credential-like content to probe evidence.")
    json_path.parent.mkdir(parents=True, exist_ok=True); json_path.write_text(text + "\n", encoding="utf-8")
    lines = [f"# Upstox Analytics Fundamentals Probe — {result.symbol or result.isin}", "", "Read-only feasibility evidence. No canonical facts, filings, taxonomy, or Brain inputs were written.", "", "| Endpoint | HTTP | Result | Records | Periods | PIT quality |", "| --- | ---: | --- | ---: | --- | --- |"]
    lines.extend(f"| {item.endpoint} | {item.http_status or 'N/A'} | {item.status} | {item.record_count} | {len(item.periods)} | {item.pit_quality} |" for item in result.endpoints)
    lines.extend(["", "## BSE reconciliation", "", "| Metric | Status |", "| --- | --- |"]); lines.extend(f"| {item['metric']} | {item['status']} |" for item in result.reconciliation)
    markdown = "\n".join(lines) + "\n"
    if "bearer " in markdown.lower() or "access_token" in markdown.lower() or "authorization" in markdown.lower(): raise ValueError("Refusing to write credential-like content to probe evidence.")
    markdown_path.write_text(markdown, encoding="utf-8")


def write_fundamentals_anchor_report(results: Iterable[UpstoxAnalyticsFeasibilityResult], json_path: Path, markdown_path: Path) -> None:
    """Write the U04 three-anchor evidence package without raw responses."""
    values = tuple(results)
    payload = {"probe": "UPSTOX_U04_THREE_ANCHORS", "results": [asdict(item) for item in values]}
    text = json.dumps(payload, indent=2, sort_keys=True, default=str)
    if "bearer " in text.lower() or "access_token" in text.lower() or "authorization" in text.lower():
        raise ValueError("Refusing to write credential-like content to probe evidence.")
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(text + "\n", encoding="utf-8")
    lines = ["# Upstox Analytics Fundamentals Probe — Three Anchors", "", "Read-only feasibility evidence. No canonical writes occurred.", "", "| Symbol | Endpoint | HTTP | Result |", "| --- | --- | ---: | --- |"]
    for result in values:
        lines.extend(f"| {result.symbol or result.isin} | {item.endpoint} | {item.http_status or 'N/A'} | {item.status} |" for item in result.endpoints)
    markdown_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


__all__ = ("APOLLOHOSP_INSTRUMENT_KEY", "APOLLOHOSP_ISIN", "APOLLOHOSP_SYMBOL", "FUNDAMENTALS_ENDPOINTS", "UpstoxAnalyticsEndpointResult", "UpstoxAnalyticsFeasibilityResult", "UpstoxAnalyticsFeasibilityTester", "write_fundamentals_probe_report", "write_fundamentals_anchor_report")
