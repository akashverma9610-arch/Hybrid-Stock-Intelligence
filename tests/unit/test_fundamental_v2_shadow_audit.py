"""Read-only audit accounting, tested on an isolated in-memory database."""
import sqlite3

import pytest

from app.filings.store import _dump as filing_dump
from app.fundamentals.store import _dump
from scripts.audit_fundamental_v2_shadow import audit
from tests.unit.test_financial_diagnostic_comparability import fact, filing, T


def test_readonly_audit_accounts_for_unknown_entities_and_forbids_writes():
    c=sqlite3.connect(':memory:')
    c.executescript('''
        CREATE TABLE financial_facts(fact_id TEXT,payload_json TEXT);
        CREATE TABLE corporate_filings(filing_id TEXT,payload_json TEXT);
        CREATE TABLE core_api_snapshots(snapshot_id TEXT,family TEXT,record_type TEXT,created_at TEXT,payload_json TEXT);
        CREATE TABLE nse_udiff_weekly_technical_bars(canonical_instrument_id TEXT,week_start TEXT,weekly_bar_id TEXT,payload_json TEXT);
    ''')
    f=fact()
    c.execute('INSERT INTO financial_facts VALUES(?,?)',(f.fact_id,_dump(f)))
    c.execute('INSERT INTO corporate_filings VALUES(?,?)',(f.filing_id,filing_dump(filing(f))))
    c.commit()
    before=c.total_changes
    result=audit(c,as_of=T)
    assert result['companies']==1 and result['financial_facts']==1
    assert result['entity_counts']=={'UNKNOWN_NON_COMPARABLE':1}
    assert all(r['states']['POLICY_BLOCKED']==1 and sum(r['states'].values())==1 for r in result['rules'])
    assert result['writes']==0 and result['source_unchanged'] is True and result['replay']=='PASS'
    assert c.total_changes==before
    assert audit(c,as_of=T)['fingerprint']==result['fingerprint']
    with pytest.raises(sqlite3.OperationalError,match='readonly'):
        c.execute('DELETE FROM financial_facts')
    c.close()
