from datetime import UTC,datetime
from decimal import Decimal
from app.performance.benchmarks import randomized
from app.performance.comparability import cost_fairness
def test_random_distribution_consumes_seed_and_cost_warnings_are_explicit():
 u={str(i):(Decimal('100'),Decimal(str(101+i))) for i in range(6)};a=randomized(u,7,20,Decimal('.01'));b=randomized(u,7,20,Decimal('.01'));c=randomized(u,8,20,Decimal('.01'))
 assert a==b and a.run_results!=c.run_results and len(a.run_results)==20
 w=cost_fairness(Decimal('.2'),Decimal('.1'),Decimal('.2'),Decimal('.15'),'cost-v1','cost-v2',True);assert 'COST_MODELS_DIFFER' in w.warnings and 'TURNOVER_ASSUMPTIONS_DIFFER' in w.warnings
