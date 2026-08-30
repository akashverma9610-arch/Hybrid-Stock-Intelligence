from app.storage.sqlite_governance_repository import SQLiteStrategyGovernanceRepository
from tests.unit.test_pre_breakout_policy_governance_domain import approval
import pytest
def test_approval_sqlite_insert_get_reopen_and_tamper(tmp_path):
 path=str(tmp_path/'g.sqlite'); value=approval(warnings=('x',)); repo=SQLiteStrategyGovernanceRepository(path); repo.save_prebreakout_policy_approval(value); assert repo.get_prebreakout_policy_approval('a1')==value
 with pytest.raises(ValueError): repo.save_prebreakout_policy_approval(approval(policy_id='other'))
 repo.close(); repo=SQLiteStrategyGovernanceRepository(path); assert repo.list_prebreakout_policy_approvals('p')==(value,)
 repo._connection.execute("UPDATE prebreakout_policy_approvals SET payload_json=replace(payload_json,'\"policy_id\":\"p\"','\"policy_id\":\"bad\"')"); repo._connection.commit()
 with pytest.raises(ValueError): repo.get_prebreakout_policy_approval('a1')
