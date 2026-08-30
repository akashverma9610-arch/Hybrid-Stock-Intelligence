from dataclasses import dataclass
from decimal import Decimal
@dataclass(frozen=True,slots=True)
class UsableEfficiency:
 valid_data:int;eligible:int;generated:int;triggered:int;filled:int;outcomes:int;valid_to_signal:Decimal|None;signal_to_trigger:Decimal|None;trigger_to_fill:Decimal|None;unfilled_rate:Decimal|None;net_r_per_session:Decimal|None;cost_per_return:Decimal|None
def usable_efficiency(valid,eligible,generated,triggered,filled,outcomes,unfilled,net_r,sessions,costs,net_return):
 ratio=lambda a,b:Decimal(a)/b if b else None
 return UsableEfficiency(valid,eligible,generated,triggered,filled,outcomes,ratio(generated,valid),ratio(triggered,generated),ratio(filled,triggered),ratio(unfilled,generated),net_r/sessions if sessions else None,costs/net_return if net_return else None)
@dataclass(frozen=True,slots=True)
class RotationEfficiency:
 evaluated:int;approved:int;triggered:int;successful:int;failed:int;unnecessary_churn:int;incremental_return:Decimal|None;friction_adjusted_benefit:Decimal|None
def rotation_efficiency(evaluated,approved,triggered,results,holding_returns,frictions):
 if not results or len(results)!=len(holding_returns):return RotationEfficiency(evaluated,approved,triggered,0,0,0,None,None)
 inc=[a-b for a,b in zip(results,holding_returns)];return RotationEfficiency(evaluated,approved,triggered,sum(x>0 for x in inc),sum(x<=0 for x in inc),sum(x<=0 for x in inc),sum(inc,Decimal("0")),sum((x-f for x,f in zip(inc,frictions)),Decimal("0")))
