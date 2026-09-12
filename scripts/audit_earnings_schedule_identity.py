"""Read-only, reproducible identity audit of the financial-fact target population.

Explicit cutoffs only. Prints a receipt; does not write artifacts or databases.
Query keys are the stored canonical identity inventory, not newly found events.
"""
from __future__ import annotations

import argparse
from collections import Counter
from contextlib import closing
from datetime import datetime
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.filings.earnings_schedule_identity import EarningsScheduleCanonicalIdentityBridge as Bridge, VERSION
from app.fundamentals.diagnostic_comparability import content_fingerprint
from app.historical.security_identity_selector import resolve_historical_security_identity
from app.historical.security_master import HistoricalSecurityIdentity
from app.storage.core_api_snapshot_repository import snapshot_json_from
from app.universe_analysis.models import NseEquityInstrument, ProviderInstrumentMappingRecord

PROTECTED = ('financial_facts','corporate_filings','core_api_snapshots','portfolio_snapshots','portfolios',
    'portfolio_transactions','canonical_diagnostic_strategy_definitions','canonical_diagnostic_results',
    'strategy_versions','diagnostic_results','paper_trades','trade_plans','execution_gate_evaluations',
    'canonical_execution_gate_evaluations','six_gates_production_policy_approvals')


def protected_state(c):
    result = {}
    for table in PROTECTED:
        columns = [r[1] for r in c.execute('PRAGMA table_info("'+table+'")')]
        order = ','.join('"'+name.replace('"','""')+'"' for name in columns)
        h, n = sha256(), 0
        for row in c.execute('SELECT * FROM "'+table+'" ORDER BY '+order):
            h.update(json.dumps(tuple(row),separators=(',',':'),ensure_ascii=True).encode())
            h.update(b'\n'); n += 1
        result[table] = {'rows':n,'sha256':h.hexdigest()}
    schema = list(c.execute('SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name'))
    result['schema'] = {'sha256':sha256(json.dumps(schema,separators=(',',':')).encode()).hexdigest()}
    return result


class _ReadOnlySnapshots:
    """Audit adapter to the existing snapshot-reader protocol, SELECT only."""
    def __init__(self, connection):
        self.connection, self.cache = connection, {}

    def list_snapshots(self, family, *, limit, offset):
        if family not in self.cache:
            rows = self.connection.execute('SELECT payload_json FROM core_api_snapshots WHERE family=? ORDER BY snapshot_id', (family.value,))
            self.cache[family] = tuple(snapshot_json_from(raw) for (raw,) in rows)
        return self.cache[family][offset:offset+limit]


def identity_matrix(bridge, targets, *, as_of, historical_as_of):
    rows = []
    for instrument in sorted(targets):
        isin = instrument.removeprefix('NSE:')
        masters = [s.payload for s in bridge.snapshots if isinstance(s.payload,NseEquityInstrument)
                   and s.payload.instrument_id==instrument and s.payload.data_as_of<=as_of]
        masters.sort(key=lambda p:(p.data_as_of,p.symbol))
        symbol = masters[-1].symbol if masters else None
        mappings = [s.payload for s in bridge.snapshots if isinstance(s.payload,ProviderInstrumentMappingRecord)
                    and s.payload.canonical_instrument_id==instrument and s.payload.effective_as_of<=as_of]
        bse = sorted((p for p in mappings if p.provider=='BSE_OFFICIAL'),key=lambda p:(p.effective_as_of,p.mapping_id))
        code = bse[-1].provider_instrument_reference if bse else None
        historical = tuple(s.payload for s in bridge.snapshots if isinstance(s.payload,HistoricalSecurityIdentity)
                           and s.payload.canonical_instrument_id==instrument and s.payload.exchange=='NSE')
        before=resolve_historical_security_identity(historical,canonical_instrument_id=instrument,as_of=as_of)
        current_nse=bridge.resolve_nse(symbol,isin,as_of)
        current_bse=bridge.resolve_bse(code,isin,as_of)
        old_nse=bridge.resolve_nse(symbol,isin,historical_as_of)
        old_bse=bridge.resolve_bse(code,isin,historical_as_of)
        rows.append(dict(canonical_instrument_id=instrument,isin=isin,nse_symbol=symbol,bse_code=code,
            before_adapter_state=before.status.value,before_adapter_fingerprint=before.fingerprint,
            current_nse=json.loads(current_nse.to_json()),current_bse=json.loads(current_bse.to_json()),
            historical_nse=json.loads(old_nse.to_json()),historical_bse=json.loads(old_bse.to_json()),
            current_future_identity_ready=current_nse.resolution_state.value=='RESOLVED' and current_bse.resolution_state.value=='RESOLVED',
            strict_historical_identity_ready=old_nse.resolution_state.value=='RESOLVED' and old_bse.resolution_state.value=='RESOLVED',
            broker_mapping_providers=sorted({p.provider for p in mappings if p.provider in {'UPSTOX','DHAN'}}),
            old_historical_intervals=[dict(identity_id=p.identity_id,symbol=p.symbol,
                known_at=p.as_of.isoformat(),effective_from=p.symbol_effective_from.isoformat(),
                effective_to=p.symbol_effective_to.isoformat() if p.symbol_effective_to else None,
                source_fingerprint=p.source_fingerprint) for p in sorted(historical,key=lambda p:p.identity_id)],
            window_coverage='WINDOW_COVERAGE_UNPROVEN',known_at='PUBLIC_KNOWN_AT_SEMANTICS_UNRESOLVED',
            gate6_clearance=False))
    return rows


def audit(c, *, as_of, historical_as_of):
    targets = tuple(r[0] for r in c.execute('SELECT DISTINCT instrument_id FROM financial_facts ORDER BY instrument_id'))
    bridge = Bridge.from_reader(_ReadOnlySnapshots(c))
    rows = identity_matrix(bridge,targets,as_of=as_of,historical_as_of=historical_as_of)
    counts = {field:dict(sorted(Counter(r[field]['resolution_state'] for r in rows).items()))
              for field in ('current_nse','current_bse','historical_nse','historical_bse')}
    inventory = dict(c.execute('SELECT family,COUNT(*) FROM core_api_snapshots GROUP BY family ORDER BY family'))
    body = dict(version=VERSION,audit_as_of=as_of.isoformat(),historical_as_of=historical_as_of.isoformat(),
        target_population='DISTINCT financial_facts.instrument_id; query keys from retained identity inventory, not live schedule coverage',
        target_count=len(rows),counts=counts,companies=rows,snapshot_family_counts=inventory,
        authority_hierarchy=['historical-security-pit-selector existing inclusive intervals and observation boundary',
            'NSE_UNIVERSE latest data_as_of <= as_of; exact NSE_OFFICIAL_EXPORT; identity only',
            'BSE_OFFICIAL bse-xbrl-v1 exact ISIN/code immutable mapping effective_as_of <= as_of',
            'UDIFF/MII source-session evidence is not a strict public-known-at interval',
            'DHAN/UPSTOX transport metadata never identity admission'],
        protected=protected_state(c),no_identity_writes=True,no_provider_calls=True,
        no_gate6_activation=True,no_source_discovery=True)
    return body | {'fingerprint':content_fingerprint(body)}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database',type=Path,required=True)
    parser.add_argument('--as-of',type=datetime.fromisoformat,required=True)
    parser.add_argument('--historical-as-of',type=datetime.fromisoformat,required=True)
    args=parser.parse_args()
    with closing(sqlite3.connect(args.database.resolve().as_uri()+'?mode=ro',uri=True)) as c:
        c.execute('PRAGMA query_only=ON')
        c.execute('BEGIN')
        print(json.dumps(audit(c,as_of=args.as_of,historical_as_of=args.historical_as_of),sort_keys=True,indent=2))
