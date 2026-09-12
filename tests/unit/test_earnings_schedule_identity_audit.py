"""Read-only audit replay and actual population receipt consistency."""
from datetime import datetime, UTC
import json
from pathlib import Path
import sqlite3

import pytest

from scripts.audit_earnings_schedule_identity import audit, protected_state, PROTECTED
from app.fundamentals.diagnostic_comparability import content_fingerprint
from app.filings.earnings_schedule_identity import EarningsScheduleCanonicalIdentityBridge as Bridge, IdentityState as S
from app.storage.core_api_snapshot_repository import snapshot_json
from test_earnings_schedule_identity import master, mapping, snap, T, ISIN, INSTRUMENT

RECEIPT=Path('docs/architecture/EARNINGS_CALENDAR_CANONICAL_IDENTITY_BRIDGE_V1_RECEIPT.json')


def test_committed_population_receipt_fingerprints_and_state_counts():
    r=json.loads(RECEIPT.read_text(encoding='utf-8'))
    assert r['fingerprint']==content_fingerprint({k:v for k,v in r.items() if k!='fingerprint'})
    rows=r['companies']
    assert len(rows)==31==len({x['canonical_instrument_id'] for x in rows})
    assert [x['canonical_instrument_id'] for x in rows]==sorted(x['canonical_instrument_id'] for x in rows)
    for row in rows:
        assert row['canonical_instrument_id']=='NSE:'+row['isin']
        for field in ('current_nse','current_bse','historical_nse','historical_bse'):
            s=row[field]
            assert s['fingerprint']==content_fingerprint({k:v for k,v in s.items() if k!='fingerprint'})
            assert s['resolution_state']==('RESOLVED' if field.startswith('current') else 'IDENTITY_NOT_EFFECTIVE')
        assert row['window_coverage']=='WINDOW_COVERAGE_UNPROVEN' and not row['gate6_clearance']
        assert row['current_future_identity_ready'] and not row['strict_historical_identity_ready']
    assert r['protected']['financial_facts']['rows']==6118
    assert r['protected']['corporate_filings']['rows']==455
    assert r['protected']['core_api_snapshots']['rows']==206749
    assert r['protected']['portfolio_snapshots']['rows']==1
    assert all(r['protected'][t]['rows']==0 for t in ('strategy_versions','diagnostic_results','paper_trades','trade_plans'))


@pytest.mark.parametrize('symbol', ['APARINDS','DEEPINDS','GENUSPOWER','GLAND','ICICIBANK','ACUTAAS'])
def test_six_required_targets_same_unexceptional_bridge(symbol):
    row=next(x for x in json.loads(RECEIPT.read_text(encoding='utf-8'))['companies'] if x['nse_symbol']==symbol)
    p=master(instrument_id=row['canonical_instrument_id'],isin=row['isin'],symbol=symbol)
    b=mapping(canonical_instrument_id=p.instrument_id,isin=p.isin,provider_instrument_reference=row['bse_code'])
    bridge=Bridge((snap(p),snap(b)))
    assert bridge.resolve_nse(symbol,p.isin,T).resolution_state==S.RESOLVED
    assert bridge.resolve_bse(row['bse_code'],p.isin,T).resolution_state==S.RESOLVED
    assert bridge.resolve_nse(symbol,p.isin,datetime(2025,7,16,tzinfo=UTC)).resolution_state==S.IDENTITY_NOT_EFFECTIVE


def test_isolated_sqlite_audit_is_replayable_and_read_only(tmp_path):
    path=tmp_path/'identity-audit.sqlite'
    with sqlite3.connect(path) as c:
        for table in PROTECTED:
            shape=('snapshot_id TEXT PRIMARY KEY, family TEXT, payload_json TEXT' if table=='core_api_snapshots'
                   else 'instrument_id TEXT' if table=='financial_facts' else 'record TEXT')
            c.execute(f'CREATE TABLE {table} ({shape})')
        c.execute('INSERT INTO financial_facts VALUES (?)',(INSTRUMENT,))
        for s in (snap(master()),snap(mapping())):
            c.execute('INSERT INTO core_api_snapshots VALUES (?,?,?)',(s.snapshot_id,s.family.value,snapshot_json(s)))
    with sqlite3.connect(path.as_uri()+'?mode=ro',uri=True) as c:
        c.execute('PRAGMA query_only=ON');c.execute('BEGIN')
        before=protected_state(c); changes=c.total_changes
        first=audit(c,as_of=T,historical_as_of=datetime(2025,7,16,tzinfo=UTC))
        second=audit(c,as_of=T,historical_as_of=datetime(2025,7,16,tzinfo=UTC))
        assert first==second and before==first['protected']==protected_state(c)
        assert c.total_changes==changes==0
        assert first['counts']['current_nse']=={'RESOLVED':1}
        assert first['counts']['current_bse']=={'RESOLVED':1}
        assert c.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
        assert c.execute('PRAGMA foreign_key_check').fetchall()==[]
