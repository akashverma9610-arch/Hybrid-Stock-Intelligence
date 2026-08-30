from datetime import UTC, datetime
from decimal import Decimal

import pytest

from app.market_data.nse_delivery import NseDeliveryReportImporter, NseDeliveryStore, _date_from_name
from app.storage.sqlite_core_api_snapshot_repository import SQLiteCoreApiSnapshotRepository


T=datetime(2026,8,28,18,tzinfo=UTC)

def _csv(value="61.25"):
    return "SYMBOL,SERIES,DATE1,TOTTRDQTY,DELIV_QTY,DELIV_PER,TOTTRDVAL,TOTALTRADES,VWAP\nALPHA,EQ,28-Aug-2026,100,61,"+value+",1000,10,10\nBETA,BE,28-Aug-2026,100,50,50,1000,10,10\n"

def test_official_delivery_import_retains_raw_artifact_and_exact_target_only(tmp_path):
    source=tmp_path/'sec_bhavdata_full_28082026.csv';source.write_text(_csv(),encoding='utf-8')
    store=NseDeliveryStore(SQLiteCoreApiSnapshotRepository(tmp_path/'core.sqlite'))
    result=NseDeliveryReportImporter(store).import_csv(source,source_url='https://www.nseindia.com/all-reports',source_page='https://www.nseindia.com/all-reports',fetched_at=T,targets={'ALPHA':('NSE:ALPHA','INE000A01001')})
    value=store.latest('NSE:ALPHA',as_of=T)
    assert result.accepted==1 and result.eq_rows_seen==1 and value is not None
    assert value.delivery_percentage==Decimal('61.25') and value.deliverable_quantity==61 and value.available_at==T
    assert result.artifact.authority=='NSE_OFFICIAL' and value.isin=='INE000A01001'

@pytest.mark.parametrize('delivery,quantity',[('101',61),('61.2',101),('-1',1)])
def test_delivery_range_and_quantity_are_fail_closed(tmp_path,delivery,quantity):
    source=tmp_path/'sec_bhavdata_full_28082026.csv';source.write_text(_csv(delivery).replace(',61,',f',{quantity},'),encoding='utf-8')
    store=NseDeliveryStore(SQLiteCoreApiSnapshotRepository(tmp_path/'core.sqlite'))
    result=NseDeliveryReportImporter(store).import_csv(source,source_url='https://www.nseindia.com/all-reports',source_page='https://www.nseindia.com/all-reports',fetched_at=T,targets={'ALPHA':('NSE:ALPHA','INE')})
    assert result.rejected==1 and store.latest('NSE:ALPHA',as_of=T) is None

def test_missing_delivery_does_not_become_a_prebreakout_pass():
    from app.strategies.pre_breakout.service import PreBreakoutConfig, PreBreakoutEngine
    from tests.unit.test_pre_breakout_inflection_strategies import _pre_input
    result=PreBreakoutEngine().evaluate(_pre_input(delivery_pct=None),config=PreBreakoutConfig())
    assert result.status.value=='PARTIAL' and 'DELIVERY_DATA_UNAVAILABLE' in result.warnings

def test_cli_import_is_local_file_only_and_never_constructs_a_network_fetcher(tmp_path):
    from app.runtime.cli import main
    source=tmp_path/'sec_bhavdata_full_28082026.csv';source.write_text(_csv(),encoding='utf-8')
    store=NseDeliveryStore(SQLiteCoreApiSnapshotRepository(tmp_path/'core.sqlite'))
    importer=NseDeliveryReportImporter(store); output=[]
    class Closed: 
        def close(self): pass
    assert main(['import-nse-delivery',str(source),'--source-url','https://www.nseindia.com/all-reports'],nse_delivery_import_factory=lambda:(importer,{'ALPHA':('NSE:ALPHA','INE')},Closed()),output=output.append)==0
    assert any('accepted=1' in line for line in output)

def test_official_filename_date_is_deterministic_and_timezone_aware():
    assert _date_from_name('sec_bhavdata_full_27082026.csv') == datetime(2026,8,27,tzinfo=UTC)
    assert _date_from_name('SEC_BHAVDATA_FULL_29022024.CSV') == datetime(2024,2,29,tzinfo=UTC)

@pytest.mark.parametrize('name,code', [('sec_bhavdata_full_31022026.csv','NSE_DELIVERY_FILENAME_DATE_INVALID'),('bhavcopy_27082026.csv','NSE_DELIVERY_FILENAME_UNSUPPORTED'),('arbitrary.csv','NSE_DELIVERY_FILENAME_UNSUPPORTED')])
def test_delivery_filename_rejects_non_official_or_impossible_dates(name,code):
    with pytest.raises(ValueError,match=code): _date_from_name(name)

def test_empty_valid_delivery_report_is_explicit_not_filename_error(tmp_path):
    source=tmp_path/'sec_bhavdata_full_27082026.csv';source.write_text('SYMBOL,SERIES,DATE1,TOTTRDQTY,DELIV_QTY,DELIV_PER\n',encoding='utf-8')
    store=NseDeliveryStore(SQLiteCoreApiSnapshotRepository(tmp_path/'core.sqlite'))
    with pytest.raises(ValueError,match='NSE_DELIVERY_REPORT_EMPTY'):
        NseDeliveryReportImporter(store).import_csv(source,source_url='https://www.nseindia.com/all-reports',source_page='https://www.nseindia.com/all-reports',fetched_at=T,targets={})

def test_live_nse_delivery_header_aliases_are_supported(tmp_path):
    source=tmp_path/'sec_bhavdata_full_27082026.csv'
    source.write_text('SYMBOL,SERIES,DATE1,TTL_TRD_QNTY,TURNOVER_LACS,NO_OF_TRADES,DELIV_QTY,DELIV_PER\nALPHA,EQ,27-Aug-2026,100,10.5,8,61,61\n',encoding='utf-8')
    store=NseDeliveryStore(SQLiteCoreApiSnapshotRepository(tmp_path/'core.sqlite'))
    result=NseDeliveryReportImporter(store).import_csv(source,source_url='https://www.nseindia.com/all-reports',source_page='https://www.nseindia.com/all-reports',fetched_at=T,targets={'ALPHA':('NSE:ALPHA','INE')})
    value=store.latest('NSE:ALPHA',as_of=T)
    assert result.accepted==1 and value is not None
    assert value.total_traded_quantity==100 and value.turnover==Decimal('10.5') and value.trade_count==8

def test_delivery_cli_returns_safe_delivery_error_not_generic_runtime_message(tmp_path):
    from app.runtime.cli import main
    source=tmp_path/'arbitrary.csv';source.write_text(_csv(),encoding='utf-8'); output=[]
    importer=NseDeliveryReportImporter(NseDeliveryStore(SQLiteCoreApiSnapshotRepository(tmp_path/'core.sqlite')))
    class Closed:
        def close(self): pass
    assert main(['import-nse-delivery',str(source),'--source-url','https://www.nseindia.com/all-reports'],nse_delivery_import_factory=lambda:(importer,{},Closed()),output=output.append)==1
    assert output == ['NSE_DELIVERY_FILENAME_UNSUPPORTED']

def test_latest_official_delivery_is_pit_safe_and_strictly_above_sixty(tmp_path):
    from app.market_data.nse_delivery import NseDeliveryObservation
    store=NseDeliveryStore(SQLiteCoreApiSnapshotRepository(tmp_path/'core.sqlite'))
    before=NseDeliveryObservation('old','report-old','NSE:ALPHA','ALPHA','INE',datetime(2026,8,27,tzinfo=UTC),100,60,Decimal('60'),None,None,None,T)
    future=NseDeliveryObservation('future','report-future','NSE:ALPHA','ALPHA','INE',datetime(2026,8,28,tzinfo=UTC),100,61,Decimal('61'),None,None,None,T.replace(day=29))
    store.save(before); store.save(future)
    assert store.latest_official_delivery('NSE:ALPHA',as_of=T) == before
    assert not (before.delivery_percentage > Decimal('60'))
