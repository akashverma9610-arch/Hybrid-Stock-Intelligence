from datetime import UTC,datetime,timedelta

import pytest

from app.backtest.walk_forward import StrategyCandidate,WalkForwardMode,WalkForwardPlan,WalkForwardWindowGenerator,assert_test_isolation
from app.historical.guard import manifest_fingerprint
from app.historical.models import PartitionType

T=datetime(2026,1,1,tzinfo=UTC)
def test_rolling_and_expanding_windows_are_deterministic_and_isolate_test_data():
 sessions=tuple(T+timedelta(days=index) for index in range(30))
 candidate=StrategyCandidate("baseline","v2.1","registry","score","gate","rotation","signal","paper","allocation","performance",manifest_fingerprint(candidate="baseline"))
 plan=WalkForwardPlan("wf","dataset","1","nse","wf-v1",WalkForwardMode.ROLLING,5,2,3,3,1,1,10,"nse",T,(),manifest_fingerprint(plan="wf"))
 windows=WalkForwardWindowGenerator().generate(plan=plan,sessions=sessions,candidate=candidate)
 assert windows and windows==WalkForwardWindowGenerator().generate(plan=plan,sessions=sessions,candidate=candidate)
 assert all(window.train.end<window.test.start for window in windows)
 with pytest.raises(ValueError,match="TEST/OOS"): assert_test_isolation(windows[0],windows[0].test.start,purpose=PartitionType.TRAIN)
 with pytest.raises(ValueError,match="Pre-TEST"): assert_test_isolation(windows[0],windows[0].train.end,purpose=PartitionType.TEST)
