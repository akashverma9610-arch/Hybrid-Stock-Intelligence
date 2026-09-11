"""Read-only retained-source and current financial-depth audit; no acquisition.

Produces one explicit-cutoff receipt, reusing canonical period corrections and
comparability. This script neither evaluates diagnostics nor persists them.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime
from hashlib import sha256
import json
from pathlib import Path
import re
import sqlite3
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.data_operations.financial_period_identity_repair import FinancialPeriodIdentityProjection, RECORD_TYPE
from app.filings.store import _filing
from app.fundamentals.bse_annual_history import select_missing_annual_history
from app.fundamentals.diagnostic_comparability import assemble_financial_comparability, canonical_json
from app.fundamentals.diagnostic_input import CanonicalFinancialDiagnosticInput, APPROVED_FINANCIAL_RULE_IDS
from app.fundamentals.models import FinancialMetric as M, FinancialPeriodType as P, FinancialValueBasis as B
from app.fundamentals.store import _fact
from app.storage.core_api_snapshot_repository import snapshot_json_from
from scripts.audit_financial_diagnostic_comparability import _market


class _Corrections:
    def __init__(self, connection):
        self.values = tuple(snapshot_json_from(row[0]).payload for row in connection.execute(
            "SELECT payload_json FROM core_api_snapshots WHERE record_type=? ORDER BY snapshot_id", (RECORD_TYPE,)))

    def corrections(self):
        return self.values


def corpus_audit(root, allowed_isins):
    documents, concepts = [], defaultdict(list)
    for path in sorted(root.rglob("*.xml")):
        raw = path.read_bytes()
        tree = ET.fromstring(raw)
        fields = {n.tag.split("}")[-1]: (n.text or "").strip() for n in tree.iter()}
        if fields.get("ISIN") not in allowed_isins:
            continue
        contexts = {}
        for node in tree.iter():
            if node.tag.split("}")[-1] == "context":
                contexts[node.get("id")] = {n.tag.split("}")[-1]: (n.text or "").strip()
                    for n in node.iter() if n.tag.split("}")[-1] in {"startDate", "endDate", "instant"}}
        schemas = tuple(n.get("{http://www.w3.org/1999/xlink}href") for n in tree.iter()
                        if n.tag.split("}")[-1] == "schemaRef")
        document = {"path": path.relative_to(ROOT).as_posix(), "sha256": sha256(raw).hexdigest(),
            "isin": fields["ISIN"], "code": fields.get("ScripCode"), "schemas": schemas,
            "period": fields.get("DateOfEndOfReportingPeriod"),
            "scope": fields.get("NatureOfReportStandaloneConsolidated"), "bytes": len(raw)}
        documents.append(document)
        for node in tree.iter():
            name = node.tag.split("}")[-1]
            if not re.search(r"^(EBIT|EarningsBefore)|OperatingProfit|Profit.*Finance|Depreciation|FinanceCost|Exceptional|OtherIncome|OperatingIncome", name, re.I):
                continue
            category = ("OPERATING_PROFIT_BUT_NOT_PROVEN_EBITDA" if name == "OperatingProfitBeforeProvisionAndContingencies"
                else "UNSUPPORTED" if name.startswith("Segment")
                else "COMPONENT_ONLY" if re.search(r"Depreciation|FinanceCost|Exceptional|OtherIncome|OperatingIncome", name)
                else "AMBIGUOUS")
            # A tag spelling alone never grants an exact direct mapping.
            concepts[(node.tag, category)].append({**document, "context_id": node.get("contextRef"),
                "context": contexts.get(node.get("contextRef")), "unit_ref": node.get("unitRef")})
    return {"documents": documents, "concepts": [
        {"qualified_name": name, "classification": category,
         "document_count": len({v["sha256"] for v in values}),
         "company_count": len({v["isin"] for v in values}),
         "periods": sorted({v["period"] for v in values if v["period"]}),
         "scopes": sorted({v["scope"] for v in values if v["scope"]}),
         "occurrence_count": len(values), "examples": values[:3]}
        for (name, category), values in sorted(concepts.items())]}


def audit(connection, *, as_of, historical_as_of, source_root):
    connection.execute("PRAGMA query_only=ON")
    connection.execute("BEGIN")
    facts = tuple(_fact(json.loads(r[0])) for r in connection.execute("SELECT payload_json FROM financial_facts ORDER BY fact_id"))
    filings = tuple(_filing(json.loads(r[0])) for r in connection.execute("SELECT payload_json FROM corporate_filings ORDER BY filing_id"))
    projection = FinancialPeriodIdentityProjection(_Corrections(connection))
    mappings = {}
    for row in connection.execute("SELECT payload_json FROM core_api_snapshots WHERE family='PROVIDER_INSTRUMENT_MAPPING' ORDER BY created_at,snapshot_id"):
        value = snapshot_json_from(row[0]).payload
        if value.provider == "BSE_OFFICIAL" and value.effective_as_of <= as_of:
            mappings[value.canonical_instrument_id] = value
    grouped = defaultdict(list)
    for value in facts:
        grouped[value.instrument.instrument_id].append(value)
    rows = []
    for identifier, own in sorted(grouped.items()):
        own_filings = tuple(f for f in filings if f.instrument.instrument_id == identifier)
        current = assemble_financial_comparability(projection.project(tuple(own), as_of=as_of), own_filings,
            canonical_instrument_id=identifier, as_of=as_of)
        historical = assemble_financial_comparability(projection.project(tuple(own), as_of=historical_as_of), own_filings,
            canonical_instrument_id=identifier, as_of=historical_as_of)
        market, price_reason = _market(connection, identifier, as_of)
        adapter = CanonicalFinancialDiagnosticInput(current)
        rules = {}
        for rule in APPROVED_FINANCIAL_RULE_IDS:
            value = adapter.rule_input(rule, market=market if rule == 29 else None)
            rules[str(rule)] = {"state": value.state.value, "reasons": value.reasons,
                               "metric_states": value.metric_states}
        mapping = mappings.get(identifier)
        selection = select_missing_annual_history(current, mapping, ()) if mapping else None
        annual_metrics = {}
        for metric in (M.REVENUE, M.EBITDA, M.EBIT, M.PAT, M.EPS_BASIC):
            series = current.series(metric, P.ANNUAL, B.FULL_YEAR)
            annual_metrics[metric.value] = {"count": len(series.observations), "state": series.state.value,
                "reasons": series.reasons, "ends": [o.period_identity.period_end for o in series.observations]}
        rows.append({"instrument_id": identifier, "symbol": own[0].instrument.symbol, "isin": own[0].instrument.isin,
            "bse_code": mapping.provider_instrument_reference if mapping else None,
            "facts": len(own), "filings": len(own_filings), "scope": current.scope.value,
            "annual_endpoints": tuple(sorted({k[3] for k in current.anchors(P.ANNUAL)})),
            "quarter_endpoints": tuple(sorted({k[3] for k in current.anchors(P.QUARTERLY)})),
            "annual_metrics": annual_metrics, "selection": selection, "rules": rules,
            "historical_observations": len(historical.observations), "price_reason": price_reason,
            "current_rejected": current.rejected})
    protected = {}
    for table in ("financial_facts", "corporate_filings", "portfolio_snapshots", "portfolio_transactions",
                  "paper_trades", "trade_plans", "strategy_versions", "diagnostic_results",
                  "canonical_diagnostic_strategy_definitions", "canonical_diagnostic_results"):
        columns = connection.execute("PRAGMA table_info(" + table + ")").fetchall()
        if columns:
            values = connection.execute("SELECT * FROM " + table + " ORDER BY 1").fetchall()
            protected[table] = {"count": len(values), "sha256": sha256(canonical_json(tuple(map(tuple, values))).encode()).hexdigest()}
    for kind in ("BseNifty500Mapping", "BseNifty500MappingInventory", "BseFinancialAcquisitionPlan"):
        values = tuple(connection.execute("SELECT snapshot_id,fingerprint FROM core_api_snapshots WHERE record_type=? ORDER BY snapshot_id", (kind,)))
        protected[kind] = {"count": len(values), "sha256": sha256(canonical_json(values).encode()).hexdigest()}
    return {"as_of": as_of, "historical_as_of": historical_as_of, "rows": rows, "protected": protected,
        "metrics": dict(Counter(f.metric.value for f in facts)),
        "periods": dict(Counter(f.period_type.value + "/" + f.value_basis.value for f in facts)),
        "corpus": corpus_audit(source_root, {f.instrument.isin for f in facts})}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--as-of", type=datetime.fromisoformat, required=True)
    parser.add_argument("--historical-as-of", type=datetime.fromisoformat, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or args.as_of.tzinfo is None or args.historical_as_of.tzinfo is None:
        parser.error("New output and explicit timezone-aware cutoffs required")
    with sqlite3.connect(args.database.resolve().as_uri() + "?mode=ro", uri=True) as connection:
        value = audit(connection, as_of=args.as_of, historical_as_of=args.historical_as_of, source_root=args.source_root.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as handle:
        handle.write(canonical_json(value) + "\n")
    print(json.dumps({"companies": len(value["rows"]), "facts": sum(r["facts"] for r in value["rows"]),
                      "corpus_documents": len(value["corpus"]["documents"]), "output": str(args.output)}))


if __name__ == "__main__":
    main()
