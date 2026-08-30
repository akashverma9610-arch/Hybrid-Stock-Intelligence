from app.storage.sqlite_governance_repository import SQLiteStrategyGovernanceRepository
from app.strategies.pre_breakout.policy import PreBreakoutPolicySelectionContext
from tests.unit.test_pre_breakout_policy_governance_domain import selection
import pytest
def test_selection_sqlite_insert_filter_reopen_tamper(tmp_path):
 path=str(tmp_path/'g.sqlite'); value=selection(warnings=('x',)); repo=SQLiteStrategyGovernanceRepository(path); repo.save_prebreakout_policy_selection(value); assert repo.get_prebreakout_policy_selection('s1')==value
 assert repo.list_prebreakout_policy_selections('p',PreBreakoutPolicySelectionContext.CURRENT_STORED_SCAN)==(value,)
 with pytest.raises(ValueError): repo.save_prebreakout_policy_selection(selection(policy_id='other'))
 repo.close(); repo=SQLiteStrategyGovernanceRepository(path); assert repo.get_prebreakout_policy_selection('s1')==value
 repo._connection.execute("UPDATE prebreakout_policy_selections SET payload_json=replace(payload_json,'\"policy_id\":\"p\"','\"policy_id\":\"bad\"')"); repo._connection.commit()
 with pytest.raises(ValueError): repo.list_prebreakout_policy_selections()
