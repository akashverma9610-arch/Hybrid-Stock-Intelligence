from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.market_data.historical import BarWriteOutcome, SQLiteHistoricalBarStore
from app.market_data.models import (
    AdjustmentStatus,
    CanonicalOHLCVBar,
    Exchange,
    InstrumentIdentity,
    InstrumentType,
    MarketDataProvenance,
    Timeframe,
)
from app.storage.sqlite_governance_repository import SQLiteStrategyGovernanceRepository
from app.strategies.pre_breakout.governance import PreBreakoutPolicyGovernanceService
from app.strategies.pre_breakout.governance_commands import PreBreakoutPolicyGovernanceCommandService
from app.strategies.pre_breakout.materialization import GovernedPreBreakoutTechnicalMaterializer
from app.strategies.pre_breakout.policy import (
    PreBreakoutPolicyApprovalDecision,
    PreBreakoutPolicySelectionContext,
)


T = datetime(2026, 8, 28, 12, tzinfo=UTC)
LEGACY_FP = "5d54b7d3a3d8c85559caddfd2f11178330e42a5eb31f3dc2f9e3d4c39ecc4933"
SUCCESSOR_FP = "d61d2c51cf9af96fbee450d35b32354f688b89dc8bccba62592e761cdf39920d"
INSTRUMENT_ID = "NSE:VOLUME"


class _DeliveryStore:
    def latest_official_delivery(self, instrument_id: str, *, as_of: datetime):
        return SimpleNamespace(delivery_percentage=Decimal("61"))


def _identity() -> InstrumentIdentity:
    return InstrumentIdentity(INSTRUMENT_ID, Exchange.NSE, "VOLUME", "VOLUME", "INE000A01001", "EQ", InstrumentType.NSE_EQUITY, "Volume")


def _bar(number: int, volume: int | None, *, at: datetime | None = None, received_at: datetime | None = None) -> CanonicalOHLCVBar:
    timestamp = at or T - timedelta(days=20 - number)
    return CanonicalOHLCVBar(
        f"volume:{number}:{timestamp.isoformat()}", _identity(), Timeframe.DAILY,
        timestamp, timestamp, Decimal("100"), Decimal("105"), Decimal("95"), Decimal("100"),
        volume, None, None, AdjustmentStatus.UNKNOWN,
        MarketDataProvenance("fixture", INSTRUMENT_ID, timestamp, timestamp, received_at or timestamp, "fixture"),
    )


def _governance(tmp_path) -> PreBreakoutPolicyGovernanceService:
    repository = SQLiteStrategyGovernanceRepository(str(tmp_path / "governance.sqlite"))
    commands = PreBreakoutPolicyGovernanceCommandService(repository)
    commands.approve(
        approval_id="legacy-approval", policy_id="pre-breakout-policy-v1-draft", policy_version="v1-draft",
        decision=PreBreakoutPolicyApprovalDecision.APPROVE, reviewer_id="human:tester", reviewed_at=T - timedelta(days=2),
    )
    commands.select_for_current_stored_scan(
        selection_id="legacy-selection", approval_id="legacy-approval", selected_by="human:tester",
        selected_at=T - timedelta(days=2), effective_from=T - timedelta(days=2),
    )
    commands.approve(
        approval_id="successor-approval", policy_id="pre-breakout-policy-v1", policy_version="v1.1-draft",
        decision=PreBreakoutPolicyApprovalDecision.APPROVE, reviewer_id="human:tester", reviewed_at=T - timedelta(seconds=1),
    )
    commands.select_for_current_stored_scan(
        selection_id="successor-selection", approval_id="successor-approval", selected_by="human:tester",
        selected_at=T, effective_from=T,
    )
    return PreBreakoutPolicyGovernanceService(repository)


def _materializer(tmp_path, *, current_volume: int | None = 499_999, prior_count: int = 20, invalid_prior: bool = False):
    tmp_path.mkdir(parents=True, exist_ok=True)
    history = SQLiteHistoricalBarStore(tmp_path / "history.sqlite")
    for number in range(prior_count):
        assert history.upsert(_bar(number, 1_000_000)) is BarWriteOutcome.INSERTED
    if invalid_prior:
        assert history.upsert(_bar(prior_count, -1)) is BarWriteOutcome.INSERTED
        current_number = prior_count + 1
    else:
        current_number = prior_count
    assert history.upsert(_bar(current_number, current_volume)) is BarWriteOutcome.INSERTED
    return GovernedPreBreakoutTechnicalMaterializer(
        governance=_governance(tmp_path), historical_store=history, delivery_store=_DeliveryStore(),
    ), history


def test_selected_v11_enables_volume_but_legacy_as_of_remains_unresolved(tmp_path) -> None:
    materializer, _ = _materializer(tmp_path)
    legacy = materializer.materialize(instrument_id=INSTRUMENT_ID, as_of=T - timedelta(microseconds=1))
    successor = materializer.materialize(instrument_id=INSTRUMENT_ID, as_of=T)
    assert legacy.policy_fingerprint == LEGACY_FP and legacy.volume_dry_up_status == "UNRESOLVED_POLICY_SEMANTICS"
    assert successor.policy_fingerprint == SUCCESSOR_FP and successor.volume_dry_up_status == "PASS"
    assert successor.current_volume == 499_999 and successor.prior_20_volumes == (1_000_000,) * 20
    assert successor.prior_20_volume_mean == 1_000_000
    assert successor.volume_threshold_ratio == Decimal("0.50")
    assert successor.volume_threshold_value == 500_000
    assert successor.volume_operator == "STRICT_LESS_THAN" and successor.volume_dry_up_pass is True
    assert "CONSOLIDATION_VOLUME_STATISTIC" not in successor.blockers
    assert {"BASE_WINDOW_SELECTION_RULE", "SUPPORT_PIVOT_SELECTION_RULE", "NSE_TICK_SIZE_SOURCE"} <= set(successor.blockers)


@pytest.mark.parametrize(("current", "status", "passed"), ((499_999, "PASS", True), (500_000, "FAIL", False), (500_001, "FAIL", False)))
def test_volume_dry_up_strict_boundary_uses_selected_rule(tmp_path, current, status, passed) -> None:
    materializer, _ = _materializer(tmp_path, current_volume=current)
    value = materializer.materialize(instrument_id=INSTRUMENT_ID, as_of=T)
    assert value.volume_dry_up_status == status and value.volume_dry_up_pass is passed
    assert value.prior_20_volume_mean == 1_000_000 and value.volume_threshold_value == 500_000


def test_volume_unavailable_for_missing_current_or_fewer_than_twenty_valid_prior_observations(tmp_path) -> None:
    materializer, _ = _materializer(tmp_path, current_volume=None)
    missing_current = materializer.materialize(instrument_id=INSTRUMENT_ID, as_of=T)
    assert missing_current.volume_dry_up_status == "UNAVAILABLE" and missing_current.volume_dry_up_pass is None
    assert "VOLUME_DRY_UP_UNAVAILABLE" in missing_current.blockers
    materializer, _ = _materializer(tmp_path / "short", prior_count=19)
    short_history = materializer.materialize(instrument_id=INSTRUMENT_ID, as_of=T)
    assert short_history.volume_dry_up_status == "UNAVAILABLE" and len(short_history.prior_20_volumes) == 19


def test_invalid_canonical_volume_row_cannot_count_toward_prior_twenty(tmp_path) -> None:
    materializer, _ = _materializer(tmp_path, prior_count=19, invalid_prior=True)
    value = materializer.materialize(instrument_id=INSTRUMENT_ID, as_of=T)
    assert value.volume_dry_up_status == "UNAVAILABLE" and len(value.prior_20_volumes) == 19


def test_future_session_is_excluded_by_as_of_from_volume_evidence(tmp_path) -> None:
    materializer, history = _materializer(tmp_path)
    future_at = T + timedelta(days=1)
    assert history.upsert(_bar(99, 2_000_000, at=future_at, received_at=future_at)) is BarWriteOutcome.INSERTED
    before = materializer.materialize(instrument_id=INSTRUMENT_ID, as_of=T)
    after = materializer.materialize(instrument_id=INSTRUMENT_ID, as_of=future_at)
    assert before.current_volume == 499_999 and before.volume_dry_up_status == "PASS"
    assert after.current_volume == 2_000_000 and after.volume_dry_up_status == "FAIL"


def test_volume_materialization_stays_bounded_and_never_emits_structure_or_candidate(tmp_path) -> None:
    materializer, _ = _materializer(tmp_path)
    value = materializer.materialize(instrument_id=INSTRUMENT_ID, as_of=T)
    assert value.volume_evaluation_session == T
    assert not any(hasattr(value, name) for name in (
        "base", "support", "resistance", "trigger", "stop", "target", "reward_risk", "candidate", "signal", "paper_trade",
    ))
    assert value.policy_id == "pre-breakout-policy-v1" and value.policy_version == "v1.1-draft"
