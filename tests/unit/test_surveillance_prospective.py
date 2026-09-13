"""Isolated synthetic source evidence, never a gate or live-source claim."""
import ast
from dataclasses import FrozenInstanceError, fields, replace
from datetime import UTC, date, datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError, URLError
import ssl
from email.message import Message

import pytest

from app.filings.earnings_schedule_identity import EarningsScheduleCanonicalIdentityBridge as Bridge
from app.fundamentals.diagnostic_comparability import canonical_json
from app.market_data import surveillance_prospective as capture
from app.market_data.surveillance_prospective import (
    CaptureState as C, SurveillanceFamily as F, SurveillanceFetch, SurveillanceEvidenceStore as Store,
    ProspectiveSurveillanceCollector as Collector, OfficialSurveillanceTransport, SurveillanceRawSnapshot,
)
from app.market_data.surveillance_observations import (
    SurveillanceCaptureCompletenessReceipt, SurveillanceEvidenceReceipt,
    certify_product_capture, official_product, parse_source, project_poll, summary,
)
from app.storage.core_api_snapshot_repository import CoreApiSnapshotFamily as SF, snapshot_json, snapshot_json_from
from app.storage.sqlite_core_api_snapshot_repository import SQLiteCoreApiSnapshotRepository as Repo
from app.historical.nse_mii_security_master import NseMiiSecurityMasterEvidenceStore, extract_nse_mii_security_master
from tests.unit.test_nse_historical_mii_security_master import _response, _csv
from tests.unit.test_earnings_schedule_identity import snap, master

T = datetime(2026, 9, 13, 10, tzinfo=UTC)
ISIN = "INE372A01015"
CSV = b'Symbol,Series,Security Name,Band,Remarks\nAPARINDS,EQ,Synthetic,5,-\n'


class Clock:
    def __init__(self, at=T): self.at = at
    def now(self):
        at = self.at
        self.at += timedelta(seconds=1)
        return at


def asm(**changes):
    return dict(symbol="APARINDS", isin=ISIN, series=None, asmSurvIndicator="Stage II",
        asmTime="11-Sep-2026", survCode="LTASM - II (14)") | changes


def gsm(**changes):
    return dict(symbol="APARINDS", isin=ISIN, gsmStage="0", gsmTime="11-Sep-2026 08:13:02",
        survCode="GSM - 0 (99)") | changes


def asm_bytes(*rows):
    return json.dumps(dict(longterm=dict(data=list(rows or (asm(),))), shortterm=dict(data=[]))).encode()


class Transport:
    def __init__(self, body=None): self.body, self.calls = body or {}, []
    def get(self, family):
        self.calls.append(family)
        value = self.body.get(family, {F.ASM: asm_bytes(), F.GSM: json.dumps([gsm()]).encode(), F.PRICE_BAND: CSV}[family])
        return value if isinstance(value, SurveillanceFetch) else SurveillanceFetch(family, 200, value, len(value), True)


def fixture(tmp_path, body=None):
    repo = Repo(tmp_path / 'isolated.sqlite')
    store = Store(repo)
    transport = Transport(body)
    polls = Collector(store, transport, clock=Clock()).collect_once()
    return repo, store, polls


def bridge(*items): return Bridge(tuple(items or (snap(master(data_as_of=T-timedelta(days=1))),)))


def mii(repo, *, series="EQ", isin=ISIN, status=""):
    extraction = extract_nse_mii_security_master(_response(body=_csv(
        f"100,APARINDS,{series},Synthetic,{isin},{status},100,0,EQ,EQUITY,")))
    NseMiiSecurityMasterEvidenceStore(repo).save(extraction)
    return repo.list_snapshots(SF.HISTORICAL_NSE_SECURITY_MASTER_SNAPSHOT)


def project(store, poll, *, b=None, masters=(), at=T+timedelta(hours=1)):
    return project_poll(store, poll.record_id, identity_bridge=b or bridge(), master_snapshots=masters, clock=Clock(at))


def test_one_shot_three_fixed_requests_and_snapshot_reopen_idempotency(tmp_path):
    repo, store, polls = fixture(tmp_path)
    original = [(p.raw.record_id, p.raw.first_observed_at) for p in polls]
    ids = [p.record_id for p in polls]
    repo.close()
    repo = Repo(tmp_path / 'isolated.sqlite'); store = Store(repo)
    for record_id, original_poll in zip(ids, polls): assert store.get(record_id) == original_poll
    t = Transport()
    repeated = Collector(store, t, clock=Clock(T+timedelta(days=1))).collect_once()
    assert t.calls == list(F)
    assert [(p.raw.record_id, p.raw.first_observed_at) for p in repeated] == original
    assert all(p.requested_at > old.completed_at for p, old in zip(repeated, polls))
    assert len(repo.list_snapshots(SF.NSE_SURVEILLANCE_PROSPECTIVE)) == 9
    repo.close()


@pytest.mark.parametrize('family', list(F))
def test_changed_payload_new_snapshot_old_immutable(tmp_path, family):
    repo, store, polls = fixture(tmp_path)
    old = next(p for p in polls if p.family == family).raw
    new = store.retain_raw(family, old.raw_payload()+b'\n', T+timedelta(days=1))
    assert new.record_id != old.record_id and store.get(old.record_id) == old
    with pytest.raises(FrozenInstanceError): old.first_observed_at = T
    with pytest.raises(ValueError): replace(old, payload_fingerprint='sha256:'+'0'*64)
    with pytest.raises(ValueError): store.retain_raw(family, old.raw_payload(), T-timedelta(days=1))
    repo.close()


@pytest.mark.parametrize('family,expected', [(F.ASM,C.UNPROVEN),(F.GSM,C.UNPROVEN),(F.PRICE_BAND,C.COMPLETE)])
def test_product_documentation_is_not_api_capture_proof(tmp_path, family, expected):
    repo, store, polls = fixture(tmp_path)
    receipt = project(store,next(p for p in polls if p.family == family),masters=mii(repo))
    assert receipt.capture_state == expected
    assert receipt.official_product_completeness == 'PRODUCT_DOCUMENTED_COMPLETE'
    assert receipt.effective_state == 'UNRESOLVED'
    assert receipt.effective_from is receipt.effective_to is receipt.source_publication is None
    assert receipt.execution_status == 'NON_EXECUTABLE'
    assert receipt.first_observed_at <= receipt.capture_known_at <= receipt.processed_at
    repo.close()


@pytest.mark.parametrize('label,stage', [('Stage I',1),('Stage II',2),('Stage III',3),('Stage IV',4)])
def test_asm_explicit_stage_and_security_scope_no_series(tmp_path,label,stage):
    repo,store,polls=fixture(tmp_path,{F.ASM:asm_bytes(asm(asmSurvIndicator=label,survCode=f'LTASM - {label[6:]} ({12+stage})'))})
    r=project(store,polls[0]); o=r.observations[0]
    assert o.row.stage==stage and o.mapping_state=='RESOLVED' and o.row.series is None
    assert not o.master_lineage and dict(o.row.raw_fields)['asmTime']=='11-Sep-2026'
    repo.close()


@pytest.mark.parametrize('label,stage', [('0',0),('I',1),('II',2),('III',3),('IV',4)])
def test_gsm_single_stage_zero_distinct_from_missing(tmp_path,label,stage):
    body=json.dumps([gsm(gsmStage=label,survCode=f'GSM - {label} ({99 if stage==0 else stage})')]).encode()
    repo,store,polls=fixture(tmp_path,{F.GSM:body}); r=project(store,polls[1])
    assert r.observations[0].row.stage==stage and r.capture_state==C.UNPROVEN
    repo.close()


@pytest.mark.parametrize('code', ['LXII','XXXVI','L','VI','65',''])
def test_gsm_composite_indicator_not_stage(tmp_path,code):
    repo,store,polls=fixture(tmp_path,{F.GSM:json.dumps([gsm(gsmStage=code,survCode='IBC - Receipt & GSM 0 (62)')]).encode()})
    row=project(store,polls[1]).observations[0].row
    assert row.stage is None and row.value_state=='UNSUPPORTED'
    repo.close()


@pytest.mark.parametrize('band,state,value', [('2','EXPLICIT','0.02'),('20','EXPLICIT','0.2'),('','UNKNOWN',None),
    ('Dynamic','UNSUPPORTED',None),('No Band','UNSUPPORTED',None),('0','UNSUPPORTED',None),('-5','UNSUPPORTED',None),('NaN','UNSUPPORTED',None)])
def test_price_band_only_explicit_source_numeric(tmp_path,band,state,value):
    repo,store,polls=fixture(tmp_path,{F.PRICE_BAND:CSV.replace(b',5,',f',{band},'.encode())})
    row=project(store,polls[2],masters=mii(repo)).observations[0].row
    assert row.value_state==state and (str(row.static_band.normalize()) if row.static_band else None)==value
    repo.close()


@pytest.mark.parametrize('series,isin,expected', [('EQ',ISIN,'RESOLVED'),('BE',ISIN,'UNRESOLVED'),('EQ','INE000A01001','CONFLICTED')])
def test_price_band_exact_symbol_series_isin_not_default(tmp_path,series,isin,expected):
    repo,store,polls=fixture(tmp_path)
    o=project(store,polls[2],masters=mii(repo,series=series,isin=isin)).observations[0]
    assert o.mapping_state==expected
    if expected=='RESOLVED':
        assert len(o.master_lineage)==2 and o.nse_security_token=='100'
        assert o.descriptive_status is None  # absent status cannot block evidence
        assert o.master_report_date=='2025-12-29'  # not relabelled current
    repo.close()


def test_no_master_no_series_clearance(tmp_path):
    repo,store,polls=fixture(tmp_path); o=project(store,polls[2]).observations[0]
    assert o.mapping_state=='UNRESOLVED' and not o.master_lineage
    repo.close()


@pytest.mark.parametrize('body,state', [(b'{',C.PARTIAL),(b'{"longterm":{"data":[]}}',C.PARTIAL),
    (b'{"longterm":{"data":[]},"shortterm":{"data":[]},"page":1}',C.PARTIAL),
    (b'{"longterm":{},"longterm":{}}',C.PARTIAL)])
def test_bad_partial_or_ambiguous_api_shape_never_absence(tmp_path,body,state):
    repo,store,polls=fixture(tmp_path,{F.ASM:body}); r=project(store,polls[0])
    assert r.capture_state==state and not r.previous_complete_receipts
    repo.close()


@pytest.mark.parametrize('kind', ['duplicate','conflict','identity_conflict','stage_conflict'])
def test_duplicate_conflict_no_voting_or_silent_dedup(tmp_path,kind):
    row=asm()
    if kind=='conflict': row=asm(asmSurvIndicator='Stage I',survCode='LTASM - I (13)')
    if kind=='identity_conflict': row=asm(isin='INE000A01001')
    if kind=='stage_conflict': row=asm(asmSurvIndicator='Stage I')
    repo,store,polls=fixture(tmp_path,{F.ASM:asm_bytes(asm(),row)})
    r=project(store,polls[0]); assert len(r.observations)==2
    assert r.capture_state==(C.PARTIAL if kind=='duplicate' else C.CONFLICTED)
    repo.close()


def test_empty_asm_snapshot_not_complete_absence_or_zero(tmp_path):
    empty=json.dumps(dict(longterm=dict(data=[]),shortterm=dict(data=[]))).encode()
    repo,store,polls=fixture(tmp_path,{F.ASM:empty,F.GSM:b'[]'})
    for p in polls[:2]:
        r=project(store,p); assert r.capture_state==C.UNPROVEN and not r.observations
    repo.close()


def test_complete_replacement_candidate_partial_does_not_remove(tmp_path):
    repo,store,polls=fixture(tmp_path); masters=mii(repo)
    old=project(store,polls[2],masters=masters)
    newer=Collector(store,Transport({F.PRICE_BAND:CSV.replace(b',5,',b',2,')}),clock=Clock(T+timedelta(days=1))).collect_once()[2]
    current=project(store,newer,masters=masters,at=T+timedelta(days=1,hours=1))
    assert current.previous_complete_receipts[0].evidence_id==old.record_id
    assert current.replacement_state=='COMPLETE_REPLACEMENT_CANDIDATE_EFFECTIVITY_UNRESOLVED'
    failed=SurveillanceFetch(F.PRICE_BAND,503,b'',None,False,'HTTP_REJECTED')
    bad=Collector(store,Transport({F.PRICE_BAND:failed}),clock=Clock(T+timedelta(days=2))).collect_once()[2]
    r=project(store,bad,masters=masters,at=T+timedelta(days=2,hours=1))
    assert r.capture_state==C.FAILED and not r.previous_complete_receipts
    assert store.get(old.record_id)==old and store.get(current.record_id)==current
    repo.close()


@pytest.mark.parametrize('complete,length', [(False,len(CSV)),(True,len(CSV)+1)])
def test_partial_transfer_cannot_certify_csv(tmp_path,complete,length):
    repo,store,polls=fixture(tmp_path,{F.PRICE_BAND:SurveillanceFetch(F.PRICE_BAND,200,CSV,length,complete)})
    assert project(store,polls[2]).capture_state==C.PARTIAL
    repo.close()


def test_pit_future_identity_not_in_receipt_and_replay_stable(tmp_path):
    repo,store,polls=fixture(tmp_path)
    current=snap(master(data_as_of=T-timedelta(days=1)))
    future=snap(master(data_as_of=T+timedelta(days=1)))
    a=project(store,polls[0],b=bridge(current))
    b=project(store,polls[0],b=bridge(future,current),at=T+timedelta(days=5))
    assert a==b and future.snapshot_id not in canonical_json(b)
    r=repo.get_snapshot(a.record_id)
    assert snapshot_json_from(snapshot_json(r))==r
    repo.close()
    repo=Repo(tmp_path/'isolated.sqlite')
    assert Store(repo).get(a.record_id)==a
    repo.close()


def test_tampered_identity_and_raw_parent_fail_closed(tmp_path):
    repo,store,polls=fixture(tmp_path)
    s=snap(master(data_as_of=T-timedelta(days=1)))
    r=project(store,polls[0],b=bridge(replace(s,fingerprint='0'*64)))
    assert r.capture_state==C.CONFLICTED
    repo._connection.execute('DELETE FROM core_api_snapshots WHERE snapshot_id=?',(polls[0].raw.record_id,));repo._connection.commit()
    with pytest.raises(ValueError,match='RAW_PARENT'): project(store,polls[0])
    repo.close()


@pytest.mark.parametrize('key', ['access_token','api_key','api_secret','authorization','cookie','password'])
def test_sensitive_payload_not_persisted_or_returned(tmp_path,key):
    secret='SYNTHETIC_SECRET_NEVER_SAVE'
    repo,store,polls=fixture(tmp_path,{F.ASM:json.dumps({key:secret}).encode()})
    assert polls[0].raw is None and polls[0].reason=='SENSITIVE_PAYLOAD_REJECTED'
    text=''.join(row[0] for row in repo._connection.execute('SELECT payload_json FROM core_api_snapshots'))
    assert secret not in text
    repo.close()


@pytest.mark.parametrize('error,reason', [(TimeoutError(),'TIMEOUT'),(ssl.SSLError(),'TLS_FAILED'),(URLError('private-proxy-secret'),'NETWORK_FAILED')])
def test_transport_safe_errors_no_secret_arguments(error,reason):
    with patch.object(capture,'build_opener') as opener:
        opener.return_value.open.side_effect=error
        value=OfficialSurveillanceTransport().get(F.ASM)
    assert value.reason==reason and not value.body and 'private' not in repr(value)


def test_fixed_routes_tls_no_redirects_no_gate_dependency():
    with pytest.raises(ValueError): capture.source_url('https://arbitrary.test')
    assert capture._NoRedirect().redirect_request(None,None,None,None,None,'http://bad') is None
    root=Path(__file__).resolve().parents[2]
    for name in ['surveillance_prospective.py','surveillance_observations.py']:
        tree=ast.parse((root/'app/market_data'/name).read_text())
        imports=[n.module for n in ast.walk(tree) if isinstance(n,ast.ImportFrom)]
        assert not any(m and m.startswith(('app.gates','app.portfolio','app.signals','app.broker','app.orders','app.api')) for m in imports)
        strings={n.value for n in ast.walk(tree) if isinstance(n,ast.Constant) and isinstance(n.value,str)}
        assert not {'PASS','FAIL','EXECUTABLE','ENTRY_READY'} & strings
        assert 'CERT_NONE' not in ast.unparse(tree)
    names={f.name for f in fields(SurveillanceEvidenceReceipt)}
    assert not {'gate_result','score','entry_price','quantity','order','portfolio'} & names


def test_aware_clock_and_descriptive_time_not_backdated(tmp_path):
    repo,store,polls=fixture(tmp_path)
    r=project(store,polls[0]); assert r.first_observed_at>T and r.source_publication is None
    same=polls[0].raw.first_observed_at.astimezone(timezone(timedelta(hours=5,minutes=30)))
    assert replace(polls[0].raw,first_observed_at=same)==polls[0].raw
    with pytest.raises(ValueError): replace(polls[0].raw,first_observed_at=T.replace(tzinfo=None))
    with pytest.raises(ValueError): replace(r,effective_from='2026-09-11')
    with pytest.raises(ValueError): replace(r,execution_status='EXECUTABLE')
    repo.close()


@pytest.mark.parametrize('status', [401,403,429,503])
def test_http_rejection_closes_response_without_retaining_error_body(status):
    class SensitiveBody:
        closed=False
        def close(self): self.closed=True
        def read(self,*args): raise AssertionError('error body must not be read')
    body=SensitiveBody()
    error=HTTPError(capture.source_url(F.ASM),status,'private response',{},body)
    with patch.object(capture,'build_opener') as opener:
        opener.return_value.open.side_effect=error
        r=OfficialSurveillanceTransport().get(F.ASM)
    assert body.closed and r.body==b'' and r.reason=='HTTP_REJECTED'
    assert 'private' not in repr(r)


@pytest.mark.parametrize('mode,reason', [('valid',None),('large','SIZE_BOUND'),('encoding','ENCODING_UNSUPPORTED'),
    ('length','LENGTH_MISMATCH'),('html','CONTENT_TYPE_UNSUPPORTED')])
def test_transport_eof_bounds_header_allowlist_and_cleanup(mode,reason):
    class Response:
        status=200
        def __init__(self):
            self.closed=False; self.count=0; self.headers=Message()
            self.headers['Content-Type']='text/html' if mode=='html' else 'text/csv'
            self.headers['Content-Length']=str(capture.MAX_BYTES+1 if mode=='large' else len(CSV)+int(mode=='length'))
            self.headers['Content-Encoding']='gzip' if mode=='encoding' else 'identity'
            self.headers['Set-Cookie']='synthetic-sensitive-cookie'
        def __enter__(self): return self
        def __exit__(self,*args): self.closed=True
        def read1(self,n):
            self.count+=1
            return CSV if self.count==1 else b''
    response=Response()
    with patch.object(capture,'build_opener') as opener:
        opener.return_value.open.return_value=response
        r=OfficialSurveillanceTransport().get(F.PRICE_BAND)
        request=opener.return_value.open.call_args.args[0]
        assert not {'Authorization','Cookie'} & dict(request.header_items()).keys()
        assert opener.return_value.open.call_args.kwargs['timeout']==15
    assert response.closed and r.reason==reason
    assert 'sensitive-cookie' not in repr(r)


def test_runner_network_free_replay_existing_store_only(tmp_path,monkeypatch,capsys):
    from scripts import collect_gate3_surveillance as runner
    repo,store,polls=fixture(tmp_path)
    repo.save_snapshot(snap(master(data_as_of=T-timedelta(days=1))))
    mii(repo);repo.close()
    monkeypatch.setattr(runner.sys,'argv',['collector','--database',str(tmp_path/'isolated.sqlite'),
        '--replay-poll',*(p.record_id for p in polls)])
    with patch.object(OfficialSurveillanceTransport,'get',side_effect=AssertionError('replay cannot fetch')):
        assert runner.main()==0
    data=json.loads(capsys.readouterr().out)
    assert data['network_requests']==0 and data['restart_first_observed_verified']
    assert data['receipt_reopen_verified'] and data['gate_policy_v2_active'] is False
    assert data['master_report_date']=='2025-12-29'
    assert data['readiness']=='GATE3_SOURCE_CAPTURE_COMPLETENESS_NOT_PROVABLE_FROM_CURRENT_OFFICIAL_PATH'
    assert [item['collector_capture_state'] for item in data['completeness_receipts']]==['UNPROVEN','UNPROVEN','COMPLETE']


def test_runner_falls_back_to_latest_complete_master_when_newer_capture_is_partial(tmp_path):
    from scripts import collect_gate3_surveillance as runner
    repo, store, _ = fixture(tmp_path)
    repo.save_snapshot(snap(master(data_as_of=T-timedelta(days=1))))
    mii(repo)
    incomplete = extract_nse_mii_security_master(_response(
        report_date=date(2026, 9, 12),
        body=_csv(
            f"101,APARINDS,EQ,Synthetic,{ISIN},6,100,0,EQ,EQUITY,",
            "102,EXTRA,EQ,Extra Ltd,INE000A01002,6,100,0,EQ,EQUITY,",
        ),
    ))
    NseMiiSecurityMasterEvidenceStore(repo).save_rows(incomplete, offset=0, limit=1)
    repo.close()
    _, masters, continuity = runner.read_identity_inputs(tmp_path / 'isolated.sqlite', T)
    assert masters[0].payload.report_date.isoformat() == '2025-12-29'
    assert continuity == 'PARTIAL_LATEST_MASTER_CAPTURE_INCOMPLETE'


@pytest.mark.parametrize('status', ['', 'ACTIVE', 'SUSPENDED'])
def test_descriptive_master_status_is_not_a_gate_predicate(tmp_path,status):
    repo,store,polls=fixture(tmp_path)
    r=project(store,polls[2],masters=mii(repo,status=status))
    o=r.observations[0]
    assert o.mapping_state=='RESOLVED' and o.row.static_band is not None
    assert o.descriptive_status==(status or None)
    assert r.capture_state==C.COMPLETE and r.execution_status=='NON_EXECUTABLE'
    assert r.effective_state=='UNRESOLVED'
    # Exact source/master lineage is future adapter input, never admission.
    assert o.identity.canonical_instrument_id=='NSE:'+ISIN
    assert o.identity.evidence and len(o.master_lineage)==2
    assert r.poll_fingerprint and r.raw_id and r.scope_fingerprint
    assert r.first_observed_at<=r.capture_known_at<=r.processed_at
    repo.close()


def test_runner_reopen_checks_cannot_be_disabled_by_python_optimization():
    from scripts import collect_gate3_surveillance as runner
    tree=ast.parse(Path(runner.__file__).read_text())
    assert not any(isinstance(n,ast.Assert) for n in ast.walk(tree))
    strings={n.value for n in ast.walk(tree) if isinstance(n,ast.Constant) and isinstance(n.value,str)}
    assert {'SURVEILLANCE_RECEIPT_REOPEN_MISMATCH','SURVEILLANCE_FIRST_OBSERVATION_REOPEN_MISMATCH'}<=strings


def test_official_product_identity_is_fixed_not_inferred_from_endpoint_or_rows():
    asm_product=official_product(F.ASM); gsm_product=official_product(F.GSM); band_product=official_product(F.PRICE_BAND)
    assert asm_product.capture_endpoint.endswith('/reportASM')
    assert gsm_product.capture_endpoint.endswith('/reportGSM')
    assert asm_product.api_to_documented_export_bound is gsm_product.api_to_documented_export_bound is False
    assert band_product.capture_endpoint.endswith('/sec_list.csv') and band_product.api_to_documented_export_bound is True
    assert asm_product.expected_sections==('longterm','shortterm')
    assert gsm_product.expected_sections==('reported_gsm_array',)


def test_completeness_receipt_separates_documented_product_capture_and_row_admissibility(tmp_path):
    repo,store,polls=fixture(tmp_path)
    masters=mii(repo,isin='INE000A01001')
    evidence=[project(store,p,masters=masters if p.family is F.PRICE_BAND else ()) for p in polls]
    receipts=[certify_product_capture(store,p.record_id,r.record_id,clock=Clock(T+timedelta(hours=2))) for p,r in zip(polls,evidence)]
    assert [r.collector_capture_state for r in receipts]==[C.UNPROVEN,C.UNPROVEN,C.COMPLETE]
    assert all(r.official_product_is_complete for r in receipts)
    assert 'API_TO_DOCUMENTED_COMPLETE_EXPORT_BINDING_UNPROVEN' in receipts[0].reason_codes
    assert 'STAGEWISE_COMPLETE_PRODUCT_COVERAGE_UNPROVEN' in receipts[1].reason_codes
    assert 'ROW_IDENTITY_CONFLICT_RETAINED' in receipts[2].reason_codes
    assert dict(receipts[2].row_admissibility_counts)['CONFLICTED']==1
    assert receipts[2].effective_state=='UNRESOLVED' and receipts[2].source_date_state=='SOURCE_DATE_UNRESOLVED'
    assert receipts[2].record_id.startswith('surveillance-completeness:')
    assert receipts[2].first_observed_at==polls[2].raw.first_observed_at
    repo.close()


@pytest.mark.parametrize('count', [1,3])
def test_asm_row_count_never_certifies_documented_complete_export(tmp_path,count):
    body=asm_bytes(*(asm(symbol=f'APAR{n}',isin=ISIN) for n in range(count)))
    repo,store,polls=fixture(tmp_path,{F.ASM:body})
    evidence=project(store,polls[0]); receipt=certify_product_capture(store,polls[0].record_id,evidence.record_id)
    assert receipt.rows_seen==count and receipt.collector_capture_state is C.UNPROVEN
    assert receipt.pagination_state=='API_PAGINATION_CONTRACT_UNPROVEN'
    repo.close()


def test_complete_price_file_isolated_from_unsupported_row_values_and_identity_conflict(tmp_path):
    body=b'Symbol,Series,Security Name,Band,Remarks\nAPARINDS,EQ,Synthetic,No Band,-\n'
    repo,store,polls=fixture(tmp_path,{F.PRICE_BAND:body})
    evidence=project(store,polls[2],masters=mii(repo,isin='INE000A01001'))
    receipt=certify_product_capture(store,polls[2].record_id,evidence.record_id)
    assert evidence.capture_state is C.CONFLICTED
    assert receipt.collector_capture_state is C.COMPLETE
    counts=dict(receipt.row_admissibility_counts)
    assert counts['CONFLICTED']==counts['UNSUPPORTED_VALUE']==1
    assert 'ROW_IDENTITY_CONFLICT_RETAINED' in receipt.reason_codes
    assert 'ROW_VALUE_UNSUPPORTED_RETAINED' in receipt.reason_codes
    repo.close()


def test_failed_poll_completeness_is_not_empty_or_clear(tmp_path):
    repo,store,polls=fixture(tmp_path,{F.GSM:SurveillanceFetch(F.GSM,503,b'',None,False,'HTTP_REJECTED')})
    evidence=project(store,polls[1]); receipt=certify_product_capture(store,polls[1].record_id,evidence.record_id)
    assert evidence.capture_state is C.FAILED and receipt.collector_capture_state is C.FAILED
    assert receipt.first_observed_at is None and receipt.rows_seen==0
    assert 'HTTP_REJECTED' in receipt.reason_codes
    repo.close()


def test_completeness_reopen_idempotency_and_no_gate_or_clearance_dependency(tmp_path):
    repo,store,polls=fixture(tmp_path); evidence=project(store,polls[2],masters=mii(repo))
    one=certify_product_capture(store,polls[2].record_id,evidence.record_id,clock=Clock(T+timedelta(hours=2)))
    two=certify_product_capture(store,polls[2].record_id,evidence.record_id,clock=Clock(T+timedelta(days=1)))
    assert one == two and one.fingerprint==two.fingerprint
    repo.close(); repo=Repo(tmp_path/'isolated.sqlite'); stored=Store(repo).get(one.record_id)
    assert stored==one and isinstance(stored,SurveillanceCaptureCompletenessReceipt)
    names={f.name for f in fields(SurveillanceCaptureCompletenessReceipt)}
    assert not {'gate_result','pass','clearance','score','order','portfolio','effective_at'}&names
    repo.close()
