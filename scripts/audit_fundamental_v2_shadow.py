"""Bounded, read-only current-corpus shadow audit; explicit cutoff, no acquisition."""
from collections import Counter, defaultdict
from contextlib import closing
from datetime import datetime
import argparse
import json
from pathlib import Path
import sqlite3
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.data_operations.financial_period_identity_repair import FinancialPeriodIdentityCorrectionStore, FinancialPeriodIdentityProjection
from app.filings.store import _filing
from app.fundamentals.diagnostic_comparability import assemble_financial_comparability, content_fingerprint, canonical_json
from app.fundamentals.diagnostic_input import CanonicalFinancialDiagnosticInput
from app.fundamentals.diagnostic_v2_shadow import FundamentalDiagnosticV2ShadowEvaluator, ShadowEntity
from app.fundamentals.store import _fact
from app.historical.pit_company_type_classification_activation import (
    PitCompanyTypeClassificationActivation, classify_pit_company_types_from_repository,
)
from app.registry.versioned import V2_VERSION, V2_RULE_IDS
from app.storage.core_api_snapshot_repository import CoreApiSnapshotFamily, snapshot_json_from
from scripts.audit_financial_diagnostic_comparability import _market


class _ReadSnapshots:
    """Read only the existing snapshot family; intentionally no write methods."""
    def __init__(self, connection):
        self.connection = connection

    def list_snapshots(self, family, *, limit=100, offset=0):
        if not 0 < limit <= 100 or offset > 20000:
            raise ValueError("V2_SHADOW_AUDIT_SNAPSHOT_BOUND_EXCEEDED")
        return tuple(snapshot_json_from(row[0]) for row in self.connection.execute(
            "SELECT payload_json FROM core_api_snapshots WHERE family=? ORDER BY created_at,snapshot_id LIMIT ? OFFSET ?",
            (family.value, limit, offset)))


def _read(connection, table, id_column, cap):
    # Identifiers are fixed by the call sites, not external input.
    rows = connection.execute(f'SELECT payload_json FROM "{table}" ORDER BY "{id_column}" LIMIT ?', (cap+1,)).fetchall()
    if len(rows) > cap:
        raise ValueError("V2_SHADOW_AUDIT_CORPUS_BOUND_EXCEEDED")
    return tuple(row[0] for row in rows)


def audit(connection, *, as_of):
    if as_of.tzinfo is None or as_of.utcoffset() is None:
        raise ValueError("V2_SHADOW_AUDIT_EXPLICIT_ASOF_REQUIRED")
    connection.execute("PRAGMA query_only=ON")
    raw_facts = _read(connection, "financial_facts", "fact_id", 20000)
    raw_filings = _read(connection, "corporate_filings", "filing_id", 2000)
    raw_fingerprint = content_fingerprint((raw_facts, raw_filings))
    facts = tuple(_fact(json.loads(row)) for row in raw_facts)
    filings = tuple(_filing(json.loads(row)) for row in raw_filings)
    repository = _ReadSnapshots(connection)
    activation_rows = connection.execute("SELECT payload_json FROM core_api_snapshots WHERE family=? AND record_type=?",
        (CoreApiSnapshotFamily.PIT_COMPANY_TYPE_CLASSIFICATION.value, "PitCompanyTypeClassificationActivation")).fetchall()
    activations = tuple(snapshot_json_from(row[0]).payload for row in activation_rows)
    if len(activations) > 1 or any(not isinstance(a, PitCompanyTypeClassificationActivation) for a in activations):
        raise ValueError("V2_SHADOW_AUDIT_ENTITY_ACTIVATION_AMBIGUOUS")
    # Reuse the approved read-only canonical classifier at this explicit cutoff.
    # This is not heuristic/research classification and never persists receipts.
    report = classify_pit_company_types_from_repository(repository=repository, activation=activations[0], as_of=as_of) if activations else None
    company_types = {r.canonical_instrument_id: r for r in report.receipts} if report else {}
    projection = FinancialPeriodIdentityProjection(FinancialPeriodIdentityCorrectionStore(repository))
    companies = defaultdict(list)
    for fact in facts:
        companies[fact.instrument.instrument_id].append(fact)
    evaluator = FundamentalDiagnosticV2ShadowEvaluator()
    counts = {r: Counter() for r in V2_RULE_IDS}
    blockers = {r: Counter() for r in V2_RULE_IDS}
    rows = []
    for instrument_id, values in sorted(companies.items()):
        projected = projection.project(tuple(values), as_of=as_of)
        financial = CanonicalFinancialDiagnosticInput(assemble_financial_comparability(projected,
            tuple(f for f in filings if f.instrument.instrument_id == instrument_id),
            canonical_instrument_id=instrument_id, as_of=as_of), company_types.get(instrument_id))
        kind = financial.company_type.company_type if financial.company_type else None
        entity = ShadowEntity(kind.value) if kind else ShadowEntity.UNKNOWN_NON_COMPARABLE
        market, price_state = _market(connection, instrument_id, as_of)
        results = evaluator.evaluate(financial, registry_version=V2_VERSION, as_of=as_of, entity_type=entity, market=market)
        replay = evaluator.evaluate(financial, registry_version=V2_VERSION, as_of=as_of, entity_type=entity, market=market)
        if tuple(r.to_json() for r in results) != tuple(r.to_json() for r in replay):
            raise ValueError("V2_SHADOW_AUDIT_REPLAY_MISMATCH")
        rule_rows = []
        for result in results:
            state = "EVALUATED_CORE_READY" if result.core_state.value == "READY" else result.core_state.value
            counts[result.rule_id][state] += 1
            blockers[result.rule_id].update(result.blockers)
            rule_rows.append({"rule_id": result.rule_id, "core_state": state, "optional_coverage": result.optional_coverage,
                "blockers": result.blockers, "result_fingerprint": result.fingerprint,
                "components": [{"id": c.component_id, "state": c.state.value, "measurements": c.measurements, "reasons": c.reasons} for c in result.component_states]})
        rows.append({"canonical_instrument_id": instrument_id, "entity_type": entity.value,
            "entity_fingerprint": financial.company_type.fingerprint if financial.company_type else None,
            "input_fingerprint": financial.fingerprint, "price_state": price_state, "rules": rule_rows})
    if raw_fingerprint != content_fingerprint((_read(connection,"financial_facts","fact_id",20000), _read(connection,"corporate_filings","filing_id",2000))):
        raise ValueError("V2_SHADOW_AUDIT_SOURCE_CHANGED")
    payload = {"audit_version": "fundamental-v2-shadow-audit/v1", "as_of": as_of, "registry_version": V2_VERSION,
        "source_fingerprint": raw_fingerprint, "financial_facts": len(facts), "corporate_filings": len(filings),
        "companies": len(rows), "entity_counts": dict(sorted(Counter(r["entity_type"] for r in rows).items())),
        "classification_report_fingerprint": report.fingerprint if report else None,
        "rules": [{"rule_id": r, "states": {s: counts[r][s] for s in ("EVALUATED_CORE_READY","PARTIAL","INSUFFICIENT_DATA","POLICY_BLOCKED","EVIDENCE_CONFLICTED")},
                   "blockers": dict(sorted(blockers[r].items()))} for r in V2_RULE_IDS],
        "results": rows, "replay": "PASS", "source_unchanged": True, "writes": 0, "acquisition": False}
    return payload | {"fingerprint": content_fingerprint(payload)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--as-of", type=datetime.fromisoformat, required=True)
    args = parser.parse_args()
    with closing(sqlite3.connect(args.database.resolve().as_uri()+"?mode=ro",uri=True)) as connection:
        connection.execute("BEGIN")
        result = audit(connection, as_of=args.as_of)
    # Full deterministic audit is stdout only; no persistence subsystem.
    print(canonical_json(result))
