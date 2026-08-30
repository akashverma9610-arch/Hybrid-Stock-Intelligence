"""Optional documented GDFL GetHistory adapter; historical OHLCV only."""
from __future__ import annotations
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from hashlib import sha256
from typing import Callable, Mapping
from app.domain.models import DataQuality
from app.market_data.models import (AdjustmentStatus, CapabilityState, CanonicalOHLCVBar, ErrorCode, HistoricalBarsRequest, InstrumentIdentity, MarketDataError, MarketDataProvenance, ProviderCapabilities, ProviderInstrumentMapping, RetryDisposition, Timeframe)

GDFL_PROVIDER="global_datafeeds"
_TF={Timeframe.ONE_MINUTE:("MINUTE",1),Timeframe.FIVE_MINUTES:("MINUTE",5),Timeframe.FIFTEEN_MINUTES:("MINUTE",15),Timeframe.THIRTY_MINUTES:("MINUTE",30),Timeframe.SIXTY_MINUTES:("HOUR",1),Timeframe.DAILY:("DAY",1),Timeframe.WEEKLY:("WEEK",1)}
class GlobalDatafeedsHistoricalProvider:
 def __init__(self,access_key:str|None,*,transport:Callable[[Mapping[str,str]],object]|None=None,clock=lambda:datetime.now(UTC)):
  self._key,self._transport,self._clock=access_key,transport,clock
 def capabilities(self):return ProviderCapabilities(historical_candles=CapabilityState.SUPPORTED,supported_timeframes=frozenset(_TF),current_quotes=CapabilityState.UNSUPPORTED,batch_quotes=CapabilityState.UNSUPPORTED,index_data=CapabilityState.UNSUPPORTED)
 def request_parameters(self,request):
  if not self._key:raise MarketDataError(ErrorCode.AUTHENTICATION_REQUIRED,"Global Datafeeds historical access is not configured.")
  mapping=next((x for x in request.instrument.provider_mappings if x.provider==GDFL_PROVIDER),None)
  if not mapping:raise MarketDataError(ErrorCode.INSTRUMENT_NOT_FOUND,"Global Datafeeds instrument mapping is required.")
  periodicity,period=_TF.get(request.timeframe,(None,None))
  if not periodicity:raise MarketDataError(ErrorCode.UNSUPPORTED_TIMEFRAME,"Global Datafeeds timeframe is unsupported.")
  exchange=mapping.provider_exchange_segment or ("NSE_IDX" if request.instrument.exchange.value=="INDEX" else "NSE")
  return {"accessKey":self._key,"exchange":exchange,"instrumentIdentifier":mapping.provider_instrument_reference,"periodicity":periodicity,"period":str(period),"from":str(int(request.start.timestamp())),"to":str(int(request.end.timestamp())),"AdjustSplits":"false" if request.adjustment_preference is AdjustmentStatus.RAW else "true"}
 def get_historical_bars(self,request):
  if self._transport is None:raise MarketDataError(ErrorCode.PROVIDER_UNAVAILABLE,"Global Datafeeds transport is not configured.")
  try:payload=self._transport(self.request_parameters(request))
  except TimeoutError as e:raise MarketDataError(ErrorCode.PROVIDER_UNAVAILABLE,"Global Datafeeds request timed out.",RetryDisposition.RETRYABLE) from e
  except MarketDataError:raise
  except Exception as e:raise MarketDataError(ErrorCode.PROVIDER_UNAVAILABLE,"Global Datafeeds request failed.",RetryDisposition.RETRYABLE) from e
  if not isinstance(payload,dict):raise MarketDataError(ErrorCode.MALFORMED_RESPONSE,"Global Datafeeds response is malformed.")
  rows=payload.get("Result")
  if not isinstance(rows,list):raise MarketDataError(ErrorCode.MALFORMED_RESPONSE,"Global Datafeeds response has no Result array.")
  result=[];received=self._clock();adjustment=AdjustmentStatus.RAW if request.adjustment_preference is AdjustmentStatus.RAW else AdjustmentStatus.UNKNOWN
  for row in rows:
   try:
    stamp=datetime.fromtimestamp(int(row["LastTradeTime"]),UTC);o,h,l,c=(Decimal(str(row[x])) for x in ("Open","High","Low","Close"));volume=int(row.get("TradedQty",0))
    if min(o,h,l,c)<0 or h<max(o,l,c) or l>min(o,h,c) or volume<0:raise ValueError()
   except (KeyError,ValueError,TypeError):raise MarketDataError(ErrorCode.MALFORMED_RESPONSE,"Global Datafeeds OHLCV row is malformed.")
   duration={Timeframe.ONE_MINUTE:timedelta(minutes=1),Timeframe.FIVE_MINUTES:timedelta(minutes=5),Timeframe.FIFTEEN_MINUTES:timedelta(minutes=15),Timeframe.THIRTY_MINUTES:timedelta(minutes=30),Timeframe.SIXTY_MINUTES:timedelta(hours=1),Timeframe.DAILY:timedelta(days=1),Timeframe.WEEKLY:timedelta(days=7)}[request.timeframe];key=f"{request.instrument.instrument_id}:{request.timeframe.value}:{stamp.isoformat()}";mapping=next(x for x in request.instrument.provider_mappings if x.provider==GDFL_PROVIDER);p=MarketDataProvenance(GDFL_PROVIDER,mapping.provider_instrument_reference,stamp,stamp,received,"gdfl-history-v1","GetHistory")
   result.append(CanonicalOHLCVBar("gdfl:"+sha256(key.encode()).hexdigest()[:24],request.instrument,request.timeframe,stamp-duration,stamp,o,h,l,c,volume,None,None,adjustment,p,DataQuality.HIGH,("GDFL_SPLIT_ADJUSTMENT_ONLY",) if adjustment is AdjustmentStatus.UNKNOWN else ()))
  return tuple(sorted(result,key=lambda x:x.end_time))
