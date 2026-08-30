from decimal import Decimal
from .models import BenchmarkComparison
def compare(benchmark_id,benchmark_version,metrics,benchmark_return,benchmark_costs=Decimal("0"),fairness=()):
 strategy=metrics.get("capital_efficiency");excess=strategy-benchmark_return if strategy is not None and benchmark_return is not None else None
 classification="INCONCLUSIVE" if excess is None or fairness else "OUTPERFORMED_IN_SAMPLE" if excess>0 else "UNDERPERFORMED_IN_SAMPLE"
 return BenchmarkComparison(benchmark_id,benchmark_version,strategy,benchmark_return,excess,None,None,metrics.get("max_drawdown"),None,metrics.get("sharpe"),None,metrics.get("sortino"),None,metrics.get("volatility"),None,metrics.get("costs"),benchmark_costs,metrics.get("capital_efficiency"),benchmark_return,tuple(fairness),tuple(("SMALL_SAMPLE",) if metrics.get("sample_status") in {"VERY_LOW_SAMPLE","LOW_SAMPLE"} else ()),classification)
