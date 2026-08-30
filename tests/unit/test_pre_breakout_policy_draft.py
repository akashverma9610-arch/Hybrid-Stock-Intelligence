from decimal import Decimal
from dataclasses import FrozenInstanceError
import pytest
from app.strategies.pre_breakout.policy import DRAFT_REQUIRES_HUMAN_APPROVAL, PreBreakoutPolicyDraft
from app.strategies.pre_breakout.service import PreBreakoutConfig

def test_draft_is_immutable_and_retains_existing_engine_thresholds():
    draft=PreBreakoutPolicyDraft(); config=PreBreakoutConfig()
    assert draft.status == DRAFT_REQUIRES_HUMAN_APPROVAL
    assert draft.bbw_percentile_threshold == config.bbw_percentile_max
    assert draft.delivery_threshold_exclusive == config.delivery_pct_min
    assert draft.minimum_rr == config.minimum_reward_risk == Decimal('3')
    with pytest.raises(FrozenInstanceError): draft.status='ACTIVE'

def test_draft_names_undefined_rules_without_importing_generic_trade_defaults():
    draft=PreBreakoutPolicyDraft(); draft.assert_not_active()
    assert 'ATR_CONTRACTION_RULE' in draft.undefined_fields
    assert 'TARGET_METHOD' in draft.undefined_fields
