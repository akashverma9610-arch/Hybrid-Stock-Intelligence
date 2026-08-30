from datetime import datetime
from decimal import Decimal
from app.portfolio.serialization import dumps
from .models import PaperTrade
def trade_from(v):
 v=dict(v)
 for k in ("created_at","as_of_timestamp"):v[k]=datetime.fromisoformat(v[k])
 for k in ("planned_entry","entry_zone_low","entry_zone_high","structural_stop","target_1","target_2","extended_target","initial_risk_reward","decision_score"):v[k]=Decimal(v[k]) if v[k] is not None else None
 v["warnings"]=tuple(v["warnings"]);return PaperTrade(**v)
