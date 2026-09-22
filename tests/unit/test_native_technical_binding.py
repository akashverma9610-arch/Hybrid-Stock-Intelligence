from dataclasses import replace
from datetime import timedelta, date
from types import SimpleNamespace
import ast
from pathlib import Path

import pytest

from app.data_operations.native_technical_binding import NativeDailyTechnicalBinding, NativeSourceBindingError
from app.storage.core_api_snapshot_repository import CoreApiSnapshotFamily as F
from app.market_data.nse_udiff_daily_technical_read import NseUdiffDailyTechnicalUseMode
from app.market_data.nse_udiff_daily_integrity import build_udiff_session_coverage_manifest
from app.market_data.nse_udiff_daily_history import NseUdiffDailyStatus, _receipt
from app.historical.nse_capital_market_session_evidence_2022_2026 import nse_capital_market_calendar_2022_2026
from tests.unit.test_nse_udiff_daily_technical_read import request
from tests.unit.test_nse_udiff_daily_technical_eligibility import AT, D1, D2, D3, bar, interval
from tests.unit.test_nse_udiff_effective_identity_coverage import success_receipt


class Store:
    def __init__(self, bars=None, missing=(), future=(), dates=(D1,D2,D3)):
        self.bars = tuple(bars if bars is not None else tuple(bar(d) for d in dates))
        manifest = build_udiff_session_coverage_manifest(acquisition_id='nse-udiff-acquisition:fixture',
            requested_dates=dates, receipts=tuple(_receipt(acquisition_id='nse-udiff-acquisition:fixture',trade_date=d,
            status=NseUdiffDailyStatus.ARTIFACT_VALID, observed_at=AT,artifact_id='nse-udiff-artifact:fixture',
            source_url='https://nsearchives.nseindia.com/content/cm/fixture.zip',rows_seen=1,eligible_rows=1,
            exact_identity_rows=1,identity_discontinuities=0,unresolved_identity_rows=0,invalid_rows=0,
            zero_volume_rows=0,inserted=1,duplicates=0,conflicts=0,error_code=None) for d in dates),
            artifact_session_ids={d:('F1',) for d in dates},calendar=nse_capital_market_calendar_2022_2026(),as_of=AT)
        self.values={F.NSE_UDIFF_DAILY_SESSION_COVERAGE_MANIFEST:(manifest,),
            F.NSE_UDIFF_EFFECTIVE_IDENTITY_INTERVAL:tuple(interval(bar(d)) for d in dates),
            F.NSE_CORPORATE_ACTION_QUERY_RECEIPT:(success_receipt(dates[0],dates[-1]),),F.HISTORICAL_CORPORATE_ACTION:()}
        for key in missing:self.values[key]=()
        self.future,self.calls=future,[]

    def list_snapshots(self,family,*,limit,offset):
        self.calls.append(family)
        at=AT+timedelta(days=1) if family in self.future else AT
        return tuple(SimpleNamespace(payload=v,created_at=at,family=family) for v in self.values[family][offset:offset+limit])

    def raw_range(self,*args,**kwargs):return self.bars
    def list_conflict_artifacts(self,**kwargs):return ()


def bind(store):return NativeDailyTechnicalBinding(repository=store,historical_store=store,as_of=AT)


def test_native_complete_window_reuses_certifier_and_projection_without_writes():
    s=Store();before=s.bars
    value=bind(s).read(request())
    assert value.certified_read.state.value=='READY'
    assert len(value.technical_input.daily_snapshot.observations)==3
    assert s.bars==before
    assert value.technical_input.strict_historical_pit_state.value=='NOT_READY'


def test_same_cutoff_caches_shared_records_and_repeated_result_is_stable():
    s=Store();b=bind(s);a=b.read(request());calls=len(s.calls)
    assert b.read(request())==a and len(s.calls)==calls


@pytest.mark.parametrize('missing',[F.NSE_UDIFF_EFFECTIVE_IDENTITY_INTERVAL,F.NSE_CORPORATE_ACTION_QUERY_RECEIPT])
def test_missing_native_dependencies_fail_closed(missing):
    result=bind(Store(missing=(missing,))).read(request())
    assert result.technical_input is None and result.certified_read.state.value=='NOT_READY'


def test_future_source_snapshot_does_not_supply_coverage():
    result=bind(Store(future=(F.NSE_CORPORATE_ACTION_QUERY_RECEIPT,))).read(request())
    assert result.technical_input is None


def test_no_other_provider_fallback_for_missing_middle_session():
    values=(bar(D1),bar(D2,provider='upstox'),bar(D3))
    result=bind(Store(bars=values)).read(request())
    assert result.technical_input is None
    assert 'MISSING_REQUIRED_SECURITY_SESSION' in result.certified_read.reasons


def test_cutoff_mismatch_rejected():
    with pytest.raises(NativeSourceBindingError,match='CUTOFF_MISMATCH'):
        bind(Store()).read(replace(request(),evaluation_as_of=AT+timedelta(seconds=1)))


def test_unknown_calendar_not_weekday_default():
    with pytest.raises(NativeSourceBindingError,match='EXPECTED_SESSION_UNRESOLVED'):
        bind(Store(missing=(F.NSE_UDIFF_DAILY_SESSION_COVERAGE_MANIFEST,))).read(request())


def test_strict_historical_pit_never_reads_current_descriptive_stores():
    s=Store();value=bind(s).read(request(mode=NseUdiffDailyTechnicalUseMode.STRICT_HISTORICAL_PIT_TECHNICAL))
    assert not s.calls and value.technical_input is None


def test_no_io_authority_or_clock_calls():
    p=Path(__file__).parents[2]/'app/data_operations/native_technical_binding.py'
    tree=ast.parse(p.read_text())
    calls={n.func.attr for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute)}
    assert not calls.intersection({'now','utcnow','save','save_snapshot','execute','commit','submit','post','get_token'})


def test_future_bar_receipt_excluded_even_if_injected_reader_ignores_cutoff():
    future=replace(bar(D2),provenance=replace(bar(D2).provenance,received_at=AT+timedelta(seconds=1)))
    result=bind(Store(bars=(bar(D1),future,bar(D3)))).read(request())
    assert result.technical_input is None
    assert 'MISSING_REQUIRED_SECURITY_SESSION' in result.certified_read.reasons


def test_input_order_does_not_select_a_different_bar_or_change_fingerprint():
    assert bind(Store(bars=(bar(D3),bar(D1),bar(D2)))).read(request())==bind(Store()).read(request())


def test_duplicate_native_bar_is_not_silently_discarded():
    result=bind(Store(bars=(bar(D1),bar(D2),bar(D2),bar(D3)))).read(request())
    assert result.technical_input is None
    assert 'AMBIGUOUS_SECURITY_SESSION' in result.certified_read.reasons


def test_tampered_native_identity_rejected_not_repaired():
    s=Store()
    object.__setattr__(s.values[F.NSE_UDIFF_EFFECTIVE_IDENTITY_INTERVAL][0],'fingerprint','sha256:'+'0'*64)
    with pytest.raises(ValueError):
        bind(s).read(request())


def test_aware_cutoff_required():
    with pytest.raises(NativeSourceBindingError,match='AWARE_CUTOFF_REQUIRED'):
        NativeDailyTechnicalBinding(repository=Store(),historical_store=Store(),as_of=AT.replace(tzinfo=None))


def test_bar_reader_receives_exact_cutoff_and_never_writes():
    s=Store();seen=[]
    def read(*args,**kwargs):
        seen.append((args,kwargs));return s.bars
    s.raw_range=read
    bind(s).read(request())
    assert len(seen)==1
    assert seen[0][1]=={'as_of':AT}
    assert seen[0][0][0]==request().canonical_instrument_id


def test_certified_source_does_not_satisfy_a_longer_indicator_window():
    from app.universe_analysis.technical_diagnostic_input import technical_diagnostic_readiness
    value=bind(Store()).read(request())
    readiness=technical_diagnostic_readiness(value.technical_input,10)
    assert 'DAILY_HISTORY_INSUFFICIENT' in {x.value for x in readiness.blockers}
    assert readiness.current_descriptive_operational.value!='READY'


def test_native_historical_requested_sessions_need_no_synthetic_weekend_rows():
    days=(date(2024,7,12),date(2024,7,15))
    s=Store(dates=days)
    req=replace(request(),start_session=days[0],end_session=days[-1])
    result=bind(s).read(req)
    assert result.certified_read.state.value=='READY'
    assert result.certified_read.certification.expected_sessions==days
