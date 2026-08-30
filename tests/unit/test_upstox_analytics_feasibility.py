from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import app.market_data.upstox_analytics as analytics_module
from app.market_data.upstox_analytics import (
    APOLLOHOSP_ISIN,
    FUNDAMENTALS_ENDPOINTS,
    UpstoxAnalyticsFeasibilityTester,
    write_fundamentals_anchor_report,
    write_fundamentals_probe_report,
)
from app.data_sources.models import FundamentalFactKind
from app.fundamentals.models import FinancialFact, FinancialMetric, FinancialPeriodType, FinancialValueBasis, NumericScale, StatementScope
from app.market_data.models import Exchange, InstrumentIdentity, InstrumentType


T = datetime(2026, 8, 25, tzinfo=UTC)


def _bse_fact(metric: FinancialMetric, value: str) -> FinancialFact:
    instrument = InstrumentIdentity("NSE:APOLLOHOSP", Exchange.NSE, "APOLLOHOSP", "APOLLOHOSP", "INE437A01024", None, InstrumentType.NSE_EQUITY, "APOLLOHOSP")
    return FinancialFact(f"bse:{metric.value}", instrument, metric, Decimal(value), "INR", "INR", NumericScale.MILLIONS, FinancialPeriodType.QUARTERLY, FinancialValueBasis.QUARTER_ONLY, None, datetime(2026, 6, 30, tzinfo=UTC), 2027, 1, StatementScope.CONSOLIDATED, FundamentalFactKind.REPORTED, "BSE_OFFICIAL", "bse:filing", "source", T, T, "bse-official-local-xbrl-v1")


def _payload_for(url: str):
    if "/profile" in url:
        return {"status": "success", "data": {"sector": "Healthcare", "industry": "Hospitals", "company_profile": "x"}}
    if "income-statement" in url:
        return {"status": "success", "data": {"type": "consolidated", "time_period": "quarterly" if "quarterly" in url else "yearly", "units_in": "crore", "income_statement": [{"category": "revenue", "history": [{"period": "Jun 2026", "value": 100}]}], "full_statement": [{"particular": "Profit After Tax", "history": [{"period": "Mar 2026", "value": 20}]}]}}
    if "share-holdings" in url:
        return {"status": "success", "data": {"share_holdings": [{"category": "promoters", "period": "Jun 2026"}, {"category": "fii", "period": "Mar 2026"}]}}
    if "key-ratios" in url:
        return {"status": "success", "data": {"key_ratios": [{"name": "ROCE", "company_value": 12, "sector_value": 10}]}}
    if "corporate-actions" in url:
        return {"status": "success", "data": {"corporate_actions": [{"type": "dividend", "announcement_date": "2026-08-01", "ex_date": "2026-08-10"}]}}
    if "competitors" in url:
        return {"status": "success", "data": {"competitors": [{"isin": "INE000A01001", "instrument_key": "NSE_EQ|INE000A01001", "sector": "Healthcare"}]}}
    return {"status": "success", "data": {"type": "consolidated", "units_in": "crore", "history": [{"period": "Mar 2026"}], "full_statement": [{"particular": "Cash and Cash Equivalents"}]}}


def test_u04_probe_uses_exactly_nine_documented_fundamentals_endpoints_and_no_writes(tmp_path: Path):
    calls: list[tuple[str, dict[str, str]]] = []

    def transport(url: str, headers: dict[str, str]):
        calls.append((url, dict(headers)))
        return 200, _payload_for(url)

    result = UpstoxAnalyticsFeasibilityTester("synthetic-secret", transport=transport, clock=lambda: datetime(2026, 8, 25, tzinfo=UTC)).run()

    assert result.isin == APOLLOHOSP_ISIN
    assert tuple(item.endpoint for item in result.endpoints) == tuple(item[0] for item in FUNDAMENTALS_ENDPOINTS)
    assert len(calls) == 9 and all("historical-candle" not in url for url, _ in calls)
    assert all(headers == {"Content-Type": "application/json", "Accept": "application/json", "Authorization": "Bearer synthetic-secret"} for _, headers in calls)
    quarterly = next(item for item in result.endpoints if item.endpoint == "income_statement_quarterly")
    yearly = next(item for item in result.endpoints if item.endpoint == "income_statement_yearly_full")
    assert quarterly.safe_query_params == {"type": "consolidated", "time_period": "quarterly", "fs": "false"}
    assert yearly.safe_query_params == {"type": "consolidated", "time_period": "yearly", "fs": "true"}
    assert quarterly.units == "crore" and quarterly.pit_quality == "OBSERVED_AT_FETCH_ONLY"
    assert next(item for item in result.endpoints if item.endpoint == "key_ratios").summary["classification"] == "CURRENT_SNAPSHOT_ONLY"
    assert next(item for item in result.endpoints if item.endpoint == "profile").summary["taxonomy_role"] == "SECONDARY_VENDOR_RECONCILIATION_ONLY"
    assert next(item for item in result.endpoints if item.endpoint == "corporate_actions").summary["authority_role"] == "SECONDARY_RECONCILIATION_ONLY"
    write_fundamentals_probe_report(result, tmp_path / "probe.json", tmp_path / "probe.md")
    assert "synthetic-secret" not in (tmp_path / "probe.json").read_text(encoding="utf-8")


def test_missing_token_never_attempts_provider_call():
    calls: list[str] = []
    result = UpstoxAnalyticsFeasibilityTester(None, transport=lambda url, _: calls.append(url)).run()
    assert calls == [] and result.credential_accepted is False
    assert result.endpoints[0].error_code == "MISSING_CONFIGURATION"


def test_cloudflare_1010_fails_closed_and_stops_further_calls():
    calls: list[str] = []

    def transport(url: str, _: dict[str, str]):
        calls.append(url)
        return 403, {"status": "error", "code": "CLOUDFLARE_1010", "message": "blocked"}

    result = UpstoxAnalyticsFeasibilityTester("synthetic-secret", transport=transport).run()
    assert len(calls) == 1 and result.stopped_early is True and result.stop_reason == "CLOUDFLARE_1010"
    assert result.endpoints[0].error_code == "CLOUDFLARE_1010"


def test_periods_are_not_promoted_to_publication_timestamps_and_units_stay_explicit():
    def transport(url: str, _: dict[str, str]):
        payload = _payload_for(url)
        if "income-statement" in url:
            payload["data"]["updated_at"] = "2026-08-25T10:00:00Z"
            payload["data"]["income_statement"][0]["history"][0]["period_end"] = "2026-06-30"
        return 200, payload

    result = UpstoxAnalyticsFeasibilityTester("synthetic-secret", transport=transport).run()
    quarterly = next(item for item in result.endpoints if item.endpoint == "income_statement_quarterly")
    assert quarterly.units == "crore"
    assert quarterly.pit_quality == "OBSERVED_AT_FETCH_ONLY"
    semantics = {item["semantic"] for item in quarterly.timestamp_fields_detected}
    assert "PERIOD_END" in semantics and "UPDATED_AT" in semantics and "PUBLICATION_OR_FILING" not in semantics


def test_ambiguous_label_and_unit_are_never_guessed_in_bse_reconciliation(tmp_path: Path):
    def transport(url: str, _: dict[str, str]):
        payload = _payload_for(url)
        if "income-statement" in url:
            payload["data"]["units_in"] = None
            payload["data"]["income_statement"] = [{"category": "mystery sales", "history": [{"period": "Jun 2026", "value": 100}]}]
        return 200, payload

    result = UpstoxAnalyticsFeasibilityTester("synthetic-secret", transport=transport).run()
    quarterly = next(item for item in result.endpoints if item.endpoint == "income_statement_quarterly")
    assert quarterly.summary["revenue_available"] is False
    write_fundamentals_anchor_report((result,), tmp_path / "anchors.json", tmp_path / "anchors.md")
    assert "synthetic-secret" not in (tmp_path / "anchors.json").read_text(encoding="utf-8")


def test_analytics_transport_uses_requests_and_preserves_structured_403_payload(monkeypatch):
    calls = []

    class Response:
        status_code = 403
        content = b'{"status":"error","code":"UDAPI403","message":"forbidden"}'
        headers = {"Content-Type": "application/json"}

    def get(url, *, headers, timeout):
        calls.append((url, dict(headers), timeout))
        return Response()

    monkeypatch.setattr(analytics_module.requests, "get", get)
    tester = UpstoxAnalyticsFeasibilityTester("synthetic-secret", timeout_seconds=13)
    status, payload = tester._https_transport("https://api.upstox.com/v2/fundamentals/INE437A01024/profile", {"Content-Type": "application/json", "Accept": "application/json", "Authorization": "Bearer synthetic-secret"})
    assert status == 403 and payload == {"status": "error", "code": "UDAPI403", "message": "forbidden"}
    assert calls[0][2] == 13 and "User-Agent" not in calls[0][1]


def test_list_shaped_share_holdings_key_ratios_and_corporate_actions_are_successful():
    def transport(url: str, _: dict[str, str]):
        if "share-holdings" in url:
            data = [{"category": "promoters", "history": [{"period": "Jun 2026", "value": 55}]}, {"category": "fii", "history": [{"period": "Mar 2026", "value": 15}]}]
        elif "key-ratios" in url:
            data = [{"name": "ROCE", "company_value": 12.5, "sector_value": 11.2}]
        elif "corporate-actions" in url:
            data = [{"name": "Dividend", "expiry_date": "2026-08-20", "amount": 10, "ratio": None, "announcement_date": "2026-08-01", "ex_date": "2026-08-12", "event_details": [{"name": "Record Date", "value": "2026-08-13"}]}]
        else:
            data = _payload_for(url)["data"]
        return 200, {"status": "success", "data": data}

    result = UpstoxAnalyticsFeasibilityTester("synthetic-secret", transport=transport).run()
    holdings = next(item for item in result.endpoints if item.endpoint == "share_holdings")
    ratios = next(item for item in result.endpoints if item.endpoint == "key_ratios")
    actions = next(item for item in result.endpoints if item.endpoint == "corporate_actions")
    assert holdings.status == ratios.status == actions.status == "SUCCESS"
    assert holdings.data_schema_summary["data_shape"] == "ARRAY"
    assert holdings.summary["categories"] == ("fii", "promoters") and holdings.summary["periods"] == ("Jun 2026", "Mar 2026")
    assert holdings.summary["history_depth"] == 2
    assert ratios.summary["classification"] == "CURRENT_SNAPSHOT_ONLY"
    assert ratios.summary["ratios"] == ({"name": "ROCE", "company_value": 12.5, "sector_value": 11.2},)
    event = actions.summary["events"][0]
    assert event["dates"] == {"announcement_date": "2026-08-01", "ex_date": "2026-08-12"}
    assert event["event_details"] == ({"name": "Record Date", "value": "2026-08-13"},)


def test_bse_raw_inr_values_reconcile_by_dimension_and_revenue_is_only_a_total_candidate():
    bse = (
        _bse_fact(FinancialMetric.REVENUE, "70435000000"), _bse_fact(FinancialMetric.OTHER_INCOME, "488000000"),
        _bse_fact(FinancialMetric.PAT, "6104000000"), _bse_fact(FinancialMetric.EPS_BASIC, "40.39"),
    )
    def transport(url: str, _: dict[str, str]):
        data = _payload_for(url)["data"]
        if "income-statement" in url:
            data = {"type": "consolidated", "time_period": "quarterly", "units_in": "crore", "income_statement": [
                {"category": "revenue", "history": [{"period": "Jun 2026", "value": "7092.3"}]},
                {"category": "profit after tax", "history": [{"period": "Jun 2026", "value": "610.4"}]},
                {"category": "eps basic", "history": [{"period": "Jun 2026", "value": "40.39"}]},
            ], "full_statement": []}
        return 200, {"status": "success", "data": data}
    result = UpstoxAnalyticsFeasibilityTester("synthetic-secret", transport=transport, bse_facts=bse).run()
    rows = {item["metric"]: item for item in result.reconciliation}
    assert rows["PAT"]["dimension"] == "MONETARY" and rows["PAT"]["bse_comparable_value"] == "610.4000000" and rows["PAT"]["status"] == "MATCH"
    assert rows["EPS_BASIC"]["dimension"] == "PER_SHARE" and rows["EPS_BASIC"]["bse_comparable_value"] == "40.39" and rows["EPS_BASIC"]["status"] == "MATCH"
    total = rows["TOTAL_REVENUE_CANDIDATE"]
    assert total["canonical_mapping"] == "NOT_PROMOTED" and total["bse_total_revenue_candidate_crore"] == "7092.3000000" and total["status"] == "TOTAL_REVENUE_CANDIDATE_MATCH"


def test_competitors_400_is_endpoint_discrepancy_without_identifier_mutation():
    calls = []
    def transport(url: str, _: dict[str, str]):
        calls.append(url)
        if "competitors" in url:
            return 400, {"status": "error", "message": "Invalid Instrument key"}
        return 200, _payload_for(url)
    result = UpstoxAnalyticsFeasibilityTester("synthetic-secret", transport=transport).run()
    competitors = result.endpoints[-1]
    assert competitors.endpoint == "competitors" and competitors.error_code == "PROVIDER_ENDPOINT_DISCREPANCY"
    assert calls[-1].endswith("/INE437A01024/competitors") and result.isin == APOLLOHOSP_ISIN
