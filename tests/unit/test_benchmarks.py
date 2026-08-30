from decimal import Decimal
from app.performance.benchmarks import BENCHMARKS,buy_hold,moving_average,momentum,randomized
def test_eight_registry_and_deterministic_benchmarks():
 assert len(BENCHMARKS)==8
 values=(Decimal("100"),Decimal("110"),Decimal("121"));assert buy_hold("nifty50_buy_hold",values).gross_return==Decimal(".21")
 assert moving_average(values,1).net_return is not None
 u={"A":values,"B":(Decimal("100"),Decimal("90"),Decimal("99"))};assert momentum(u,1,1).gross_return==Decimal(".1")
 assert randomized(u,7,5)==randomized(u,7,5) and randomized(u,8,5).run_results!=randomized(u,7,5).run_results
