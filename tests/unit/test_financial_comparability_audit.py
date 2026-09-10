"""Audit metadata/data accounting regression using an isolated in-memory DB."""
import json
import sqlite3

from app.fundamentals.store import _dump
from app.filings.store import _dump as filing_dump
from app.registry.canonical import DIAGNOSTIC_RULES
from app.fundamentals.diagnostic_comparability import content_fingerprint
from scripts.audit_financial_diagnostic_comparability import audit
from tests.unit.test_financial_diagnostic_comparability import T, fact, filing


def test_audit_exact_registry_names_denominators_and_no_mutation():
    connection = sqlite3.connect(":memory:")
    f = fact()
    connection.executescript("""
    CREATE TABLE financial_facts(fact_id TEXT,payload_json TEXT);
    CREATE TABLE corporate_filings(filing_id TEXT,payload_json TEXT);
    CREATE TABLE nse_udiff_weekly_technical_bars(canonical_instrument_id TEXT,week_start TEXT,weekly_bar_id TEXT,payload_json TEXT);
    CREATE TABLE core_api_snapshots(family TEXT,payload_json TEXT);
    """)
    for table in ("portfolio_snapshots", "paper_trades", "trade_plans", "strategy_versions", "diagnostic_results", "canonical_diagnostic_strategy_definitions", "canonical_diagnostic_results"):
        connection.execute('CREATE TABLE "' + table + '" (id TEXT)')
    connection.execute("INSERT INTO financial_facts VALUES(?,?)", (f.fact_id, _dump(f)))
    connection.execute("INSERT INTO corporate_filings VALUES(?,?)", (f.filing_id, filing_dump(filing(f))))
    before = connection.total_changes
    result = audit(connection, as_of=T, historical_as_of=T.replace(year=2025))
    assert connection.total_changes == before
    assert result["financial_facts"] == 1 and result["financial_source_companies"] == 1
    assert result["approved_rule_ids"] == (16, 17, 18, 19, 20, 24, 25, 26, 29)
    for row in result["rules"]:
        assert row["name"] == next(r.canonical_name for r in DIAGNOSTIC_RULES if r.rule_id == row["rule_id"])
        assert sum(row["states"].values()) == 1
        assert row["strict_historical_as_of_usable"] == 0
    assert result["fingerprint"] == content_fingerprint({k:v for k,v in result.items() if k != "fingerprint"})
    assert json.dumps(result, sort_keys=True) == json.dumps(audit(connection, as_of=T, historical_as_of=T.replace(year=2025)), sort_keys=True)
    connection.close()
