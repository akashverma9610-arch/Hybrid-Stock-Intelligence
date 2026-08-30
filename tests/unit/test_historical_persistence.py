from datetime import UTC,datetime
import pytest
from app.historical.models import *
from app.storage.sqlite_governance_repository import SQLiteStrategyGovernanceRepository
T=datetime(2026,1,1,tzinfo=UTC)
def manifest(i,v,fp):return HistoricalDatasetManifest(i,v,T,T,T,'nse','universe',{'market':['bar-1'],'research':['news-1']},{'source':'mock'},DatasetQuality.MODERATE_QUALITY,(GapType.MISSING_RESEARCH,),'raw-v1',SurvivorshipStatus.SURVIVORSHIP_LIMITED,'FULL',('STATIC_UNIVERSE',),fp)
def test_historical_models_roundtrip_immutable_and_versioned(tmp_path):
 r=SQLiteStrategyGovernanceRepository(tmp_path/'h.db');v1=manifest('dataset-v1','1','fp1');v2=manifest('dataset-v2','2','fp2');p=HistoricalPartition('train','dataset-v1',PartitionType.TRAIN,T,T,5,2,'frozen training window',T);m=UniverseMembership('member','stock','nifty',T,T,T,'mock','provenance',InstrumentLifecycle.DELISTED)
 r.save_historical_manifest(v1);r.save_historical_manifest(v2);r.save_historical_partition(p);r.save_universe_membership(m)
 assert r.get_historical_manifest('dataset-v1')==v1 and r.get_historical_manifest('dataset-v2')==v2 and r.get_historical_partition('train')==p and r.get_universe_membership('member')==m
 assert r.get_historical_manifest('dataset-v1').fingerprint!=r.get_historical_manifest('dataset-v2').fingerprint
 for fn,obj in ((r.save_historical_manifest,v1),(r.save_historical_partition,p),(r.save_universe_membership,m)):
  with pytest.raises(ValueError):fn(obj)
