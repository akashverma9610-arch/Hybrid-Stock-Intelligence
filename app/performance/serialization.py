from datetime import datetime
from decimal import Decimal
from .models import BenchmarkComparison,EquityPoint,PerformanceEvaluationDataset,PerformanceReport
from .benchmarks import BenchmarkRun
from dataclasses import is_dataclass
def pack(x):
 if isinstance(x,Decimal):return {"$decimal":str(x)}
 if isinstance(x,datetime):return {"$datetime":x.isoformat()}
 if isinstance(x,tuple):return {"$tuple":[pack(v) for v in x]}
 if isinstance(x,dict):return {k:pack(v) for k,v in x.items()}
 if is_dataclass(x):return {k:pack(getattr(x,k)) for k in x.__dataclass_fields__}
 return x
def unpack(x):
 if isinstance(x,dict):
  if "$decimal" in x:return Decimal(x["$decimal"])
  if "$datetime" in x:return datetime.fromisoformat(x["$datetime"])
  if "$tuple" in x:return tuple(unpack(v) for v in x["$tuple"])
  return {k:unpack(v) for k,v in x.items()}
 return x
def dump(obj):return pack({k:getattr(obj,k) for k in obj.__dataclass_fields__})
def dataset_from(x):return PerformanceEvaluationDataset(**unpack(x))
def report_from(x):
 x=unpack(x);x["equity_curve"]=tuple(EquityPoint(**v) for v in x["equity_curve"]);return PerformanceReport(**x)
def run_from(x):return BenchmarkRun(**unpack(x))
def comparison_from(x):return BenchmarkComparison(**unpack(x))
