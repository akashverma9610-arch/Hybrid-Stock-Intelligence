from __future__ import annotations
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from hashlib import sha256
from app.market_data.aggregation import BreadthAggregator, IndexObservationService, MarketUniverse
from app.market_data.models import MarketDataProvenance
from app.market_data.store import MarketDataStore
from app.storage.core_api_snapshot_repository import CoreApiSnapshot, CoreApiSnapshotFamily, CoreApiSnapshotRepository

class RuntimeMode(StrEnum): STORED_DATA="STORED_DATA"; MOCK="MOCK"
class RuntimeCycleStatus(StrEnum): SUCCESS="SUCCESS"; PARTIAL="PARTIAL"; FAILED="FAILED"; SKIPPED="SKIPPED"
class RuntimeStage(StrEnum): DATA_READ="DATA_READ"; QUALITY="QUALITY"; AGGREGATION="AGGREGATION"; REGIME="REGIME"; EXTREMES="EXTREMES"; SECTOR="SECTOR"; STOCK="STOCK"; PUBLICATION="PUBLICATION"
@dataclass(frozen=True,slots=True)
class RuntimeStageResult: stage:RuntimeStage;status:RuntimeCycleStatus;started_at:datetime;completed_at:datetime;warnings:tuple[str,...]=();error_code:str|None=None;record_count:int=0
@dataclass(frozen=True,slots=True)
class DataConfidenceSummary: quote_coverage:float;index_available:bool;vix_available:bool;breadth_coverage:str|None;warnings:tuple[str,...]
@dataclass(frozen=True,slots=True)
class RuntimeCycleResult: cycle_id:str;started_at:datetime;completed_at:datetime;mode:RuntimeMode;universe_id:str;data_as_of:datetime;overall_status:RuntimeCycleStatus;stage_results:tuple[RuntimeStageResult,...];warnings:tuple[str,...];snapshots_written:tuple[str,...];provenance:MarketDataProvenance;data_confidence:DataConfidenceSummary

class RuntimeCycleCoordinator:
 def __init__(self,store:MarketDataStore,universe:MarketUniverse,snapshots:CoreApiSnapshotRepository,*,bars=None,fundamentals_adapter=None,stock_analysis_builder=None,news_research_builder=None,stock_input_enricher=None,primary_market_extremes_builder=None,market_extremes_input_consumer=None,clock=lambda:datetime.now(UTC)):
  self.store,self.universe,self.snapshots,self.bars,self.fundamentals_adapter,self.stock_analysis_builder,self.news_research_builder,self.stock_input_enricher,self.primary_market_extremes_builder,self.market_extremes_input_consumer,self.clock=store,universe,snapshots,bars,fundamentals_adapter,stock_analysis_builder,news_research_builder,stock_input_enricher,primary_market_extremes_builder,market_extremes_input_consumer,clock
 def run_cycle(self,*,mode:RuntimeMode=RuntimeMode.STORED_DATA,publish:bool=True,cycle_id:str|None=None)->RuntimeCycleResult:
  started=self.clock(); members=self.universe.constituents_as_of(started)
  if not members: raise ValueError("Runtime cycle requires an explicit non-empty universe.")
  quotes={i:self.store.latest_quote(i) for i in members}; quotes={i:q for i,q in quotes.items() if q is not None}
  prov=MarketDataProvenance("RUNTIME",None,started,started,started,"runtime-v1",cycle_id or "cycle","stored-data")
  stages=[RuntimeStageResult(RuntimeStage.DATA_READ,RuntimeCycleStatus.SUCCESS,started,started,record_count=len(quotes))]
  breadth,participation=BreadthAggregator().aggregate(self.universe,quotes,data_as_of=started,provenance=prov,bars=self.bars)
  partial=participation.coverage.value!="COMPLETE"
  overall=RuntimeCycleStatus.PARTIAL if partial else RuntimeCycleStatus.SUCCESS
  stages += [RuntimeStageResult(RuntimeStage.QUALITY,RuntimeCycleStatus.PARTIAL if partial else RuntimeCycleStatus.SUCCESS,started,started,participation.warnings),RuntimeStageResult(RuntimeStage.AGGREGATION,RuntimeCycleStatus.SUCCESS,started,started,record_count=1)]
  cid=cycle_id or sha256(f"{mode.value}:{self.universe.universe_id}:{started.isoformat()}".encode()).hexdigest()[:16]; written=()
  stages.append(RuntimeStageResult(RuntimeStage.REGIME,RuntimeCycleStatus.SKIPPED,started,started,("CANONICAL_RUNTIME_ADAPTER_DEFERRED",)))
  if self.primary_market_extremes_builder is not None and self.market_extremes_input_consumer is not None:
   ipo=self.primary_market_extremes_builder.build(level=__import__("app.crisis.models",fromlist=["MarketExtremeLevel"]).MarketExtremeLevel.MARKET,entity_id=self.universe.universe_id,as_of=started);self.market_extremes_input_consumer(ipo);stages.append(RuntimeStageResult(RuntimeStage.EXTREMES,RuntimeCycleStatus.PARTIAL if ipo.rolling_ipo_count==0 else RuntimeCycleStatus.SUCCESS,started,started,("PRIMARY_MARKET_EVIDENCE_UNAVAILABLE",) if ipo.rolling_ipo_count==0 else (),record_count=ipo.rolling_ipo_count))
  else:stages.append(RuntimeStageResult(RuntimeStage.EXTREMES,RuntimeCycleStatus.SKIPPED,started,started,("CANONICAL_RUNTIME_ADAPTER_DEFERRED",)))
  stages.append(RuntimeStageResult(RuntimeStage.SECTOR,RuntimeCycleStatus.SKIPPED,started,started,("CANONICAL_RUNTIME_ADAPTER_DEFERRED",)))
  if self.fundamentals_adapter is not None and self.stock_analysis_builder is not None:
   produced=[]; stock_warnings=[]
   for instrument_id in members:
    fundamental_input=self.fundamentals_adapter.build(instrument_id,as_of=started)
    # Stored optional evidence is supplied only through an explicit existing-input adapter.
    # The coordinator never fetches news and does not alter diagnostics or score semantics.
    research_input=self.news_research_builder.build(instrument_id,as_of=started) if self.news_research_builder is not None else None
    analysis_input=self.stock_input_enricher(fundamental_input,research_input) if research_input is not None and self.stock_input_enricher is not None else fundamental_input
    result=self.stock_analysis_builder(analysis_input)
    if result is None: stock_warnings.append("STOCK_ANALYSIS_NOT_PRODUCED:"+instrument_id);continue
    produced.append(result)
    if publish:
     identifier=f"runtime:{cid}:stock:{result.symbol}"; record=CoreApiSnapshot(identifier,CoreApiSnapshotFamily.STOCK_ANALYSIS,"v1","stock-analysis-v1",sha256(f"{cid}:{result.symbol}:{'|'.join(fundamental_input.fact_ids)}".encode()).hexdigest(),started,result)
     try:self.snapshots.save_snapshot(record)
     except ValueError:pass
     written=(*written,identifier)
   stock_status=RuntimeCycleStatus.SUCCESS if produced and not stock_warnings else RuntimeCycleStatus.PARTIAL if produced or stock_warnings else RuntimeCycleStatus.SKIPPED
   stages.append(RuntimeStageResult(RuntimeStage.STOCK,stock_status,started,started,tuple(stock_warnings),record_count=len(produced)))
   if stock_status is RuntimeCycleStatus.PARTIAL: overall=RuntimeCycleStatus.PARTIAL
  else: stages.append(RuntimeStageResult(RuntimeStage.STOCK,RuntimeCycleStatus.SKIPPED,started,started,("CANONICAL_RUNTIME_ADAPTER_DEFERRED",)))
  if publish:
   snap=CoreApiSnapshot(f"runtime:{cid}",CoreApiSnapshotFamily.MARKET_REGIME,"v1","runtime-market-state-v1",sha256(f"{cid}:{breadth.observation_id}".encode()).hexdigest(),started,{"cycle_id":cid,"data_as_of":started,"overall_status":overall.value,"warnings":participation.warnings,"breadth":breadth,"participation":participation})
   try:self.snapshots.save_snapshot(snap)
   except ValueError: pass
   written=(*written,snap.snapshot_id)
   stages.append(RuntimeStageResult(RuntimeStage.PUBLICATION,RuntimeCycleStatus.SUCCESS,started,started,record_count=1))
  else: stages.append(RuntimeStageResult(RuntimeStage.PUBLICATION,RuntimeCycleStatus.SKIPPED,started,started,("DRY_RUN",)))
  confidence=DataConfidenceSummary(len(quotes)/len(members),False,False,participation.coverage.value,participation.warnings)
  return RuntimeCycleResult(cid,started,self.clock(),mode,self.universe.universe_id,started,overall,tuple(stages),participation.warnings,written,prov,confidence)
