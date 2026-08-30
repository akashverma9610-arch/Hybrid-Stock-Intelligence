from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal
from random import Random
@dataclass(frozen=True,slots=True)
class BenchmarkDefinition:
 benchmark_id:str;version:str;methodology:str;required_data:tuple[str,...];capital_model:str;rebalance_frequency:str|None;cost_model:str;eligibility:str;limitations:tuple[str,...]
@dataclass(frozen=True,slots=True)
class BenchmarkRun:
 benchmark_id:str;version:str;start:Decimal;end:Decimal;gross_return:Decimal|None;net_return:Decimal|None;seed:int|None;run_results:tuple[Decimal,...];warnings:tuple[str,...]
BENCHMARKS=(
 BenchmarkDefinition("nifty50_buy_hold","v1","supplied index buy-and-hold","index series","FIXED_NOTIONAL",None,"explicit","as-of series",("PRICE_RETURN unless supplied total-return series",)),
 BenchmarkDefinition("nifty500_buy_hold","v1","supplied index buy-and-hold","index series","FIXED_NOTIONAL",None,"explicit","as-of series",("PRICE_RETURN unless supplied total-return series",)),
 BenchmarkDefinition("sector_index","v1","mapped relevant-sector index","sector map,index series","FIXED_NOTIONAL",None,"explicit","mapped sector",("UNKNOWN is retained",)),
 BenchmarkDefinition("simple_momentum","v1","fixed lookback/top-N/rebalance","universe prices","FIXED_NOTIONAL","configured","same cost model","as-of universe",("not optimized",)),
 BenchmarkDefinition("simple_moving_average","v1","price above fixed MA invested else cash","price series","FIXED_NOTIONAL","daily","same cost model","as-of series",("fixed period",)),
 BenchmarkDefinition("random_selection","v1","seeded equal-weight selections","as-of universe","FIXED_NOTIONAL","configured","same cost model","as-of universe",("distribution, not one lucky run",)),
 BenchmarkDefinition("previous_strategy_version","v1","frozen historical outcomes","prior report","compatible","same window","own frozen costs","compatible periods",("comparability warning if windows differ",)),
 BenchmarkDefinition("trader_like","v1","fixed trend/breakout/2R baseline","price,sector","FIXED_NOTIONAL","configured","same cost model","as-of universe",("not a human model",)),)
def buy_hold(identifier,values,cost=Decimal("0"),seed=None):
 if len(values)<2 or values[0]<=0:return BenchmarkRun(identifier,"v1",values[0] if values else Decimal("0"),values[-1] if values else Decimal("0"),None,None,seed,(),("INSUFFICIENT_DATA",))
 gross=values[-1]/values[0]-1;return BenchmarkRun(identifier,"v1",values[0],values[-1],gross,gross-cost,seed,(),())
def moving_average(values,period,cost=Decimal("0")):
 if len(values)<=period:return buy_hold("simple_moving_average",values,cost)
 ret=Decimal("0");on=False
 for i in range(period,len(values)):
  avg=sum(values[i-period:i],Decimal("0"))/period;now=values[i]>avg
  if on:ret+=values[i]/values[i-1]-1
  on=now
 return BenchmarkRun("simple_moving_average","v1",values[0],values[-1],ret,ret-cost,None,(),())
def momentum(universe,lookback,top_n,cost=Decimal("0")):
 scores=sorted(((series[-1]/series[-1-lookback]-1,name) for name,series in universe.items() if len(series)>lookback),reverse=True)[:top_n]
 vals=[x[0] for x in scores];r=sum(vals,Decimal("0"))/len(vals) if vals else None;return BenchmarkRun("simple_momentum","v1",Decimal("0"),Decimal("0"),r,r-cost if r is not None else None,None,tuple(vals),() if r is not None else ("INSUFFICIENT_DATA",))
def randomized(universe,seed,runs,cost=Decimal("0")):
 names=sorted(universe);rng=Random(seed);out=[]
 for _ in range(runs):
  name=rng.choice(names);series=universe[name];out.append(series[-1]/series[0]-1-cost)
 return BenchmarkRun("random_selection","v1",Decimal("0"),Decimal("0"),sum(out,Decimal("0"))/len(out),sum(out,Decimal("0"))/len(out),seed,tuple(out),("STATIC_UNIVERSE_SURVIVORSHIP_LIMITATION",))
