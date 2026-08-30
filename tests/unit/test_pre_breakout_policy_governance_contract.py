import inspect
import pytest
from app.storage.governance_repository import StrategyGovernanceRepository
from app.storage.sqlite_governance_repository import SQLiteStrategyGovernanceRepository
from app.strategies.pre_breakout.policy import PreBreakoutPolicyApproval, PreBreakoutPolicySelection, PreBreakoutPolicySelectionContext

def test_prebreakout_policy_contract_is_typed_and_unimplemented_by_default():
    expected={
      'save_prebreakout_policy_approval':PreBreakoutPolicyApproval,'get_prebreakout_policy_approval':PreBreakoutPolicyApproval,
      'list_prebreakout_policy_approvals':PreBreakoutPolicyApproval,'save_prebreakout_policy_selection':PreBreakoutPolicySelection,
      'get_prebreakout_policy_selection':PreBreakoutPolicySelection,'list_prebreakout_policy_selections':PreBreakoutPolicySelection,
    }
    for name,typ in expected.items():
        method=getattr(StrategyGovernanceRepository,name); assert typ.__name__ in str(inspect.signature(method))
        with pytest.raises(NotImplementedError): method(object(), None)
    assert 'PreBreakoutPolicySelectionContext' in str(inspect.signature(StrategyGovernanceRepository.list_prebreakout_policy_selections))

def test_existing_sqlite_adapter_remains_constructible_without_policy_tables(tmp_path):
    repository=SQLiteStrategyGovernanceRepository(str(tmp_path/'governance.sqlite')); repository.close()
    names=set(dir(StrategyGovernanceRepository)); assert not any('prebreakout' in name and any(word in name for word in ('update','delete','activate','promote')) for name in names)
