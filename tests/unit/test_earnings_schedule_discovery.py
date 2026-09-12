"""Synthetic observed-shape fixtures; no assertion of live coverage/authority."""
from dataclasses import replace
from datetime import date, timedelta
from html import escape
import ast
import json
from pathlib import Path

import pytest

from app.filings.earnings_schedule_discovery import (
    BSE_CORPORATES, company_window_receipt, discover_bse, inspect_nse_join, parse_bse_discovery,
)
from app.filings.earnings_schedule_source import (
    Fetch, NSEOfficialEarningsScheduleSource, SourceState, classify,
    parse_bse_detail, parse_nse_prior_intimation, parse_nse_rss, public_url,
)
from app.gates.official_earnings_schedule_candidate import PurposeClassification as P
from test_earnings_schedule_adapters import (
    BSE_URL, Fake, INSTRUMENT, T, XML_URL, bse_html, identity, rss, xbrl,
)

WEB_URL = "https://nsearchives.nseindia.com/corporate/ixbrl/PRIOR_INTIMATION_75266_12012026173231_iXBRL_WEB.html"
DETAIL = "https://m.bseindia.com/MAnnDet.aspx?newsid=15bec8ef-4d88-44f6-bccc-4b0d111db3b3&flag=C&type=A&scrip_CD=532259"


def inventory(*, link=XML_URL, stamp="12-Sep-2026 10:00:00", **changes):
    row = parse_nse_rss(rss(stamp=stamp))[0]
    return replace(row, raw=tuple(sorted((dict(row.raw) | {"link": link} | changes).items())))


def web(**changes):
    fields = {"NSE Symbol*": "APARINDS", "ISIN*": "INE372A01015",
              "Name of the Company*": "Synthetic issuer", "Type of Meeting": "1) Board Meeting",
              "Type of Intimation*": "New", "Proposed Meeting Date": "2026-10-16",
              "Original Meeting Date": "2026-10-14",
              "Reason for Re-schedule (postpone or prepone) / Cancellation": "Synthetic reason",
              "Date of Report*": "2026-09-12", "Agenda*": "1) Financial results",
              "Whether results are audited or unaudited": "Unaudited",
              "Nature of report standalone or consolidated": "Standalone And Consolidated",
              "Period end Type": "Quarterly", "Period up to (Month)": "June",
              "Period up to (Year)": "2026", "Remarks (website dissemination)": "Synthetic"}
    fields.update(changes)
    return ("<html><h1>Prior Intimation</h1><table>" + "".join(
        f"<tr><td>{escape(k)}</td><td>{escape(v)}</td></tr>" for k, v in fields.items()) + "</table></html>").encode()


def inspect(inv=None, body=None, **kwargs):
    inv = inv or inventory()
    return inspect_nse_join(inv, Fetch(inv.field("link"), 200, body or xbrl()),
                            canonical_instrument_id=INSTRUMENT, identities=kwargs.pop("identities", (identity(),)),
                            observed_at=kwargs.pop("observed_at", T + timedelta(seconds=2)), **kwargs)


@pytest.mark.parametrize("url", [WEB_URL, BSE_CORPORATES, DETAIL,
    "https://www.nseindia.com/companies-listing/corporate-filings-board-meetings"])
def test_observed_public_routes_only(url):
    assert public_url(url) == url


@pytest.mark.parametrize("url", [WEB_URL.replace("PRIOR_INTIMATION", "INTEGRATED_FINANCIALS"),
    DETAIL + "&page=2", BSE_CORPORATES + "?symbol=APARINDS",
    "https://www.nseindia.com/api/corporate-board-meetings?csv=true"])
def test_no_guessed_csv_filter_or_later_financial_filing_route(url):
    with pytest.raises(ValueError):
        public_url(url)


def test_web_exact_fields_and_revision_intent_not_parent_link():
    inv = inventory(link=WEB_URL)
    body = web(**{"Type of Intimation*": "Re-schedule (postpone or prepone)"})
    row = parse_nse_prior_intimation(body, inv, document_url=WEB_URL)
    expected = {"symbol": "APARINDS", "isin": "INE372A01015", "meeting_date_iso": "2026-10-16",
                "original_meeting_date": "2026-10-14", "revision_reason": "Synthetic reason",
                "date_of_report": "2026-09-12", "audit_basis": "Unaudited",
                "statement_scope": "Standalone And Consolidated", "reporting_period_type": "Quarterly",
                "reporting_period_month": "June", "reporting_period_year": "2026", "remarks": "Synthetic"}
    assert all(row.field(k) == v for k, v in expected.items())
    assert row.field("inventory_fingerprint") == inv.fingerprint
    assert row.field("revision_of_schedule_id") is None
    result = inspect(inv, body)
    assert not result.current_descriptive_ready and "EXACT_PARENT_FILING_REQUIRED" in result.reasons


def test_xml_multiple_agendas_and_exact_optional_fields_retained():
    extra = b'<p:Agenda2>Financial results</p:Agenda2><p:DateOfReport>2026-09-12</p:DateOfReport><p:ReportingPeriodType>Quarterly</p:ReportingPeriodType>'
    row = parse_nse_prior_intimation(xbrl("Bonus")[:-7] + extra + b'</xbrl>', inventory())
    assert row.field("agenda_1") == "Bonus" and row.field("agenda_2") == "Financial results"
    assert row.field("date_of_report") == "2026-09-12"
    assert row.field("reporting_period_type") == "Quarterly"
    assert classify(row).classification == P.FINANCIAL_RESULTS_UNSPECIFIED


@pytest.mark.parametrize("body", [
    xbrl()[:-7] + b'<p:Agenda1>Bonus</p:Agenda1></xbrl>',
    xbrl()[:-7] + b'<p:Agenda3>Bonus</p:Agenda3></xbrl>',
    web().replace(b'</table>', b'<tr><td>ISIN*</td><td>INE002A01018</td></tr></table>'),
])
def test_duplicate_conflicting_or_gapped_structured_fields_rejected(body):
    inv = inventory(link=WEB_URL if body.startswith(b'<html>') else XML_URL)
    with pytest.raises(ValueError):
        parse_nse_prior_intimation(body, inv)


@pytest.mark.parametrize("agenda", ["Fund raising", "Other business", "Bonus", "Amalgamation"])
def test_structured_non_results_cannot_be_overridden_by_rss_or_remarks(agenda):
    inv = inventory(link=WEB_URL, purpose="Financial results", details="to consider financial results")
    body = web(**{"Agenda*": "1) " + agenda, "Remarks (website dissemination)": "to consider financial results"})
    result = inspect(inv, body)
    assert not result.current_descriptive_ready
    assert result.purpose in {P.NON_QUALIFYING, P.AMBIGUOUS}
    assert result.source.field("inventory_details") == "to consider financial results"


def test_current_descriptive_ready_but_report_date_and_first_observation_never_strict_pit():
    result = inspect(inventory(link=WEB_URL, disseminated=""), web())
    assert result.current_descriptive_ready and result.identity_state == "EXACT_IDENTITY_RESOLVED"
    assert result.known_at_state == "KNOWN_AT_NOT_STRICT_PIT" and not result.strict_pit_ready
    assert "known_at" not in dict(result.source.raw)
    assert result.to_json() == inspect(inventory(link=WEB_URL, disseminated=""), web()).to_json()


def test_timezone_proof_is_not_publication_authority_admission():
    result = inspect(inventory(stamp=T.isoformat()))
    assert result.current_descriptive_ready
    assert result.known_at_state == "TIMEZONE_RESOLVED_AUTHORITY_UNVERIFIED"
    assert not result.strict_pit_ready
    assert json.loads(result.to_json())["gate6_clearance"] is False


@pytest.mark.parametrize("field,wrong", [("NSESymbol", "RELIANCE"), ("ISIN", "INE002A01018")])
def test_symbol_isin_disagreement_is_conflicted(field, wrong):
    body = xbrl().replace((f'<p:{field}>' + ("APARINDS" if field == "NSESymbol" else "INE372A01015") + f'</p:{field}>').encode(),
                         f'<p:{field}>{wrong}</p:{field}>'.encode())
    result = inspect(body=body)
    assert result.identity_state == "IDENTITY_CONFLICTED" and not result.current_descriptive_ready


def test_name_only_and_future_identity_not_current_evidence():
    with pytest.raises(ValueError):
        inspect(body=xbrl().replace(b'<p:NSESymbol>APARINDS</p:NSESymbol>', b''))
    result = inspect(identities=(identity(as_of=T+timedelta(days=1)),))
    assert result.identity_state == "IDENTITY_UNRESOLVED" and not result.current_descriptive_ready


@pytest.mark.parametrize("link", [XML_URL.replace("123", "999"), "", "https://nsearchives.nseindia.com/corporate/xbrl/INTEGRATED_FINANCIALS_1.xml"])
def test_no_symbol_company_date_join_or_later_integrated_backdating(link):
    inv = inventory(link=link)
    with pytest.raises(ValueError):
        inspect_nse_join(inv, Fetch(XML_URL, 200, xbrl()), canonical_instrument_id=INSTRUMENT,
                         identities=(identity(),), observed_at=T)


def test_later_document_cannot_inherit_earlier_inventory_public_time():
    inv = inventory(stamp=T.isoformat())
    late_url = XML_URL.replace("20260912", "20261020")
    with pytest.raises(ValueError, match="JOIN_UNPROVEN"):
        parse_nse_prior_intimation(xbrl(), inv, document_url=late_url)


def listing(link=DETAIL):
    return f'<html><a href="{escape(link)}">Synthetic - Board Meeting Intimation for Financial Results</a></html>'.encode()


def test_bse_published_exact_link_variant_and_detail_reused():
    rows = parse_bse_discovery(listing())
    assert rows[0].reference == DETAIL and rows[0].field("security_code") == "532259"
    assert parse_bse_detail(bse_html(), DETAIL)[0].field("security_code") == "532259"
    transport = Fake(listing())
    batch = discover_bse(transport, retrieved_at=T)
    assert batch.state == SourceState.SOURCE_PARTIAL and transport.calls == [BSE_CORPORATES]


@pytest.mark.parametrize("body", [b'<html><app-root/></html>', b'<html>No announcements</html>'])
def test_bse_empty_or_shell_is_discovery_not_ready_not_no_event(body):
    batch = discover_bse(Fake(body), retrieved_at=T)
    assert batch.reason == "SOURCE_DISCOVERY_NOT_READY" and not batch.rows


def test_bse_failure_no_fallback_or_nse_dependency():
    transport = Fake(b'', status=503)
    batch = discover_bse(transport, retrieved_at=T)
    assert batch.state == SourceState.SOURCE_UNAVAILABLE and transport.calls == [BSE_CORPORATES]
    assert inspect().current_descriptive_ready


def test_company_window_receipt_partial_no_absence_and_order_stable():
    batch = NSEOfficialEarningsScheduleSource(Fake(rss())).fetch(retrieved_at=T)
    result = inspect(batch.rows[0])
    args = dict(instrument=INSTRUMENT, window_start=date(2026, 9, 1), window_end=date(2026, 10, 31), inspections=(result,))
    a = company_window_receipt(batch, **args)
    assert a == company_window_receipt(batch, **args)
    value = json.loads(a)
    assert value["query_state"] == "SOURCE_PARTIAL" and value["current_descriptive_ready"] == 1
    for field in ("response_complete", "pagination_complete", "complete_success", "individually_queried", "gate6_clearance"):
        assert value[field] is False
    assert value["freshness"] == "POLICY_BLOCKED"
    with pytest.raises(ValueError):
        company_window_receipt(batch, **(args | {"inspections": (result, result)}))


def test_company_window_empty_error_and_tampered_join_are_not_complete_queries():
    args = dict(instrument=INSTRUMENT, window_start=T.date(), window_end=T.date())
    for code, state in ((200, "WINDOW_COVERAGE_UNPROVEN"), (503, "SOURCE_FAILED")):
        batch = NSEOfficialEarningsScheduleSource(Fake(rss(copies=0), status=code)).fetch(retrieved_at=T)
        assert json.loads(company_window_receipt(batch, **args))["query_state"] == state
    batch = NSEOfficialEarningsScheduleSource(Fake(rss())).fetch(retrieved_at=T)
    other = inspect(inventory(purpose="other"))
    with pytest.raises(ValueError, match="JOIN_UNPROVEN"):
        company_window_receipt(batch, **args, inspections=(other,))


def test_window_count_does_not_promote_outside_window_or_invalid_inspection():
    batch = NSEOfficialEarningsScheduleSource(Fake(rss())).fetch(retrieved_at=T)
    result = inspect(batch.rows[0])
    value = json.loads(company_window_receipt(batch, instrument=INSTRUMENT, window_start=T.date(),
                                              window_end=T.date(), inspections=(result,)))
    assert value["current_descriptive_ready"] == 0
    with pytest.raises(ValueError):
        replace(result, identity_state="IDENTITY_CONFLICTED")
    with pytest.raises(ValueError):
        replace(result, known_at_state="STRICT_PIT_READY")


def test_discovery_boundary_no_activation_database_ai_or_runtime_clock():
    file = Path(__file__).parents[2] / 'app/filings/earnings_schedule_discovery.py'
    tree = ast.parse(file.read_text())
    imports = [n.module or '' for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)]
    assert not any(any(x in name for x in ('portfolio', 'broker', 'orders', 'storage', 'runtime', 'ai_', 'gates.engine')) for name in imports)
    calls = {n.func.attr for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}
    assert not calls & {'now', 'utcnow', 'connect', 'execute', 'save', 'commit'}
