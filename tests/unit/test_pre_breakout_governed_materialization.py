from __future__ import annotations

import json
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
from app.strategies.pre_breakout.materialization import (
    GovernedPreBreakoutTechnicalMaterializer,
    PreBreakoutResolvedInputStatus,
)
from app.strategies.pre_breakout.policy import (
    PreBreakoutPolicyApprovalDecision,
    PreBreakoutPolicyDraft,
)


AS_OF = datetime(2026, 8, 28, 12, tzinfo=UTC)
INSTRUMENT_ID = "NSE:ALPHA"


class _DeliveryStore:
    def __init__(self, value: Decimal | None = Decimal("61")) -> None:
        self.value = value
        self.calls = 0

    def latest_official_delivery(self, instrument_id: str, *, as_of: datetime):
        self.calls += 1
        return None if self.value is None else SimpleNamespace(delivery_percentage=self.value)


def _identity() -> InstrumentIdentity:
    return InstrumentIdentity(INSTRUMENT_ID, Exchange.NSE, "ALPHA", "ALPHA", "INE000A01001", "EQ", InstrumentType.NSE_EQUITY, "Alpha")


def _bar(number: int, *, close: Decimal = Decimal("100"), high: Decimal | None = None,
         low: Decimal | None = None, received_at: datetime | None = None) -> CanonicalOHLCVBar:
    timestamp = AS_OF - timedelta(days=300 - number)
    high = high if high is not None else close + Decimal("5")
    low = low if low is not None else close - Decimal("5")
    return CanonicalOHLCVBar(
        f"alpha:{number}", _identity(), Timeframe.DAILY, timestamp, timestamp,
        close, high, low, close, 1_000 + number, None, None, AdjustmentStatus.UNKNOWN,
        MarketDataProvenance("fixture", INSTRUMENT_ID, timestamp, timestamp, received_at or timestamp, "fixture"),
    )


def _history(tmp_path, *, sessions: int = 260, final_close: Decimal = Decimal("190")) -> SQLiteHistoricalBarStore:
    tmp_path.mkdir(parents=True, exist_ok=True)
    store = SQLiteHistoricalBarStore(tmp_path / "history.sqlite")
    for number in range(sessions):
        close, high, low = Decimal("100"), Decimal("105"), Decimal("95")
        if number >= sessions - 6:
            close = final_close
            high = Decimal("200") if number < sessions - 1 else final_close + Decimal("1")
            low = final_close if number < sessions - 1 else final_close - Decimal("1")
        assert store.upsert(_bar(number, close=close, high=high, low=low)) is BarWriteOutcome.INSERTED
    return store


def _governance(tmp_path, *, effective_from: datetime = AS_OF - timedelta(days=1)) -> PreBreakoutPolicyGovernanceService:
    repository = SQLiteStrategyGovernanceRepository(str(tmp_path / "governance.sqlite"))
    draft = PreBreakoutPolicyDraft(policy_id="prebreakout-test", version="v1")
    commands = PreBreakoutPolicyGovernanceCommandService(repository, drafts=(draft,))
    approval_at = effective_from - timedelta(seconds=1)
    commands.approve(
        approval_id="approval", policy_id=draft.policy_id, policy_version=draft.version,
        decision=PreBreakoutPolicyApprovalDecision.APPROVE,
        reviewer_id="human:tester", reviewed_at=approval_at,
    )
    commands.select_for_current_stored_scan(
        selection_id="selection", approval_id="approval", selected_by="human:tester",
        selected_at=effective_from, effective_from=effective_from,
    )
    return PreBreakoutPolicyGovernanceService(repository, drafts=(draft,))


def _materializer(tmp_path, *, sessions: int = 260, final_close: Decimal = Decimal("190"),
                  delivery: Decimal | None = Decimal("61"), effective_from: datetime = AS_OF - timedelta(days=1)):
    history = _history(tmp_path, sessions=sessions, final_close=final_close)
    deliveries = _DeliveryStore(delivery)
    return GovernedPreBreakoutTechnicalMaterializer(
        governance=_governance(tmp_path, effective_from=effective_from), historical_store=history, delivery_store=deliveries,
    ), history, deliveries


def test_selected_policy_drives_stored_materialization_and_preserves_lineage(tmp_path) -> None:
    materializer, _, delivery = _materializer(tmp_path)
    value = materializer.materialize(instrument_id=INSTRUMENT_ID, as_of=AS_OF)
    assert value.status is PreBreakoutResolvedInputStatus.PARTIAL_POLICY_BLOCKED
    assert value.policy_id == "prebreakout-test" and value.policy_version == "v1"
    assert value.policy_fingerprint and value.selection_id == "selection" and value.selection_fingerprint
    assert value.atr_contraction_pass is True
    assert len(value.previous_5_atr14) == 5 and value.current_atr14 < value.previous_5_atr14_mean
    assert value.high_252 == Decimal("200") and value.high_252_session_count == 252
    assert value.latest_close == Decimal("190") and value.distance_below_high_pct == Decimal("5")
    assert value.distance_from_high_pass is True
    assert value.volume_dry_up_status == "UNRESOLVED_POLICY_SEMANTICS"
    assert {"CONSOLIDATION_VOLUME_STATISTIC", "BASE_WINDOW_SELECTION_RULE", "SUPPORT_PIVOT_SELECTION_RULE", "NSE_TICK_SIZE_SOURCE"} <= set(value.blockers)
    assert delivery.calls == 1
    assert not any(hasattr(value, name) for name in (
        "candidate", "trigger", "stop", "target", "reward_risk", "signal", "paper_trade",
    ))


@pytest.mark.parametrize(
    ("close", "expected"),
    ((Decimal("194"), True), (Decimal("188"), True), (Decimal("195"), False), (Decimal("187"), False)),
)
def test_exact_governed_three_to_six_percent_high_distance_boundaries(tmp_path, close, expected) -> None:
    materializer, _, _ = _materializer(tmp_path, final_close=close)
    value = materializer.materialize(instrument_id=INSTRUMENT_ID, as_of=AS_OF)
    assert value.distance_below_high_pct == (Decimal("200") - close) / Decimal("2")
    assert value.distance_from_high_pass is expected


def test_atr_and_high_require_exact_eligible_history_not_approximate_windows(tmp_path) -> None:
    materializer, _, _ = _materializer(tmp_path, sessions=251)
    value = materializer.materialize(instrument_id=INSTRUMENT_ID, as_of=AS_OF)
    assert value.high_252 is None and value.high_252_session_count == 251
    assert value.distance_from_high_pass is None and "HIGH_252_UNAVAILABLE" in value.blockers
    materializer, _, _ = _materializer(tmp_path / "small", sessions=19)
    small = materializer.materialize(instrument_id=INSTRUMENT_ID, as_of=AS_OF)
    assert small.current_atr14 is None and small.atr_contraction_pass is None
    assert "ATR_CONTRACTION_UNAVAILABLE" in small.blockers


def test_historical_as_of_excludes_newest_canonical_session_without_lookahead(tmp_path) -> None:
    materializer, history, _ = _materializer(tmp_path)
    future = _bar(301, close=Decimal("300"), high=Decimal("300"), low=Decimal("299"), received_at=AS_OF + timedelta(days=1))
    assert history.upsert(future) is BarWriteOutcome.INSERTED
    before = materializer.materialize(instrument_id=INSTRUMENT_ID, as_of=AS_OF)
    after = materializer.materialize(instrument_id=INSTRUMENT_ID, as_of=AS_OF + timedelta(days=2))
    assert before.evaluation_session < future.end_time and before.latest_close == Decimal("190")
    assert after.evaluation_session == future.end_time and after.latest_close == Decimal("300")


def test_selection_effective_boundary_and_no_selection_fail_closed(tmp_path) -> None:
    materializer, _, _ = _materializer(tmp_path, effective_from=AS_OF)
    unavailable = materializer.materialize(instrument_id=INSTRUMENT_ID, as_of=AS_OF - timedelta(microseconds=1))
    available = materializer.materialize(instrument_id=INSTRUMENT_ID, as_of=AS_OF)
    assert unavailable.status is PreBreakoutResolvedInputStatus.GOVERNANCE_UNAVAILABLE
    assert "SELECTED_POLICY_UNAVAILABLE" in unavailable.blockers
    assert available.policy_id == "prebreakout-test"


def test_materializer_never_falls_back_to_a_draft_without_a_selected_policy(tmp_path) -> None:
    draft = PreBreakoutPolicyDraft(policy_id="unselected", version="v1")
    repository = SQLiteStrategyGovernanceRepository(str(tmp_path / "unselected.sqlite"))
    materializer = GovernedPreBreakoutTechnicalMaterializer(
        governance=PreBreakoutPolicyGovernanceService(repository, drafts=(draft,)),
        historical_store=_history(tmp_path / "unselected-history"),
        delivery_store=_DeliveryStore(),
    )
    value = materializer.materialize(instrument_id=INSTRUMENT_ID, as_of=AS_OF)
    assert value.status is PreBreakoutResolvedInputStatus.GOVERNANCE_UNAVAILABLE
    assert value.policy_id is None and value.blockers == ("SELECTED_POLICY_UNAVAILABLE",)


def test_tampered_selected_policy_record_fails_closed_before_materialization(tmp_path) -> None:
    materializer, _, _ = _materializer(tmp_path)
    repository = materializer._governance._repository
    row = repository._connection.execute(
        "SELECT payload_json FROM prebreakout_policy_selections WHERE id='selection'"
    ).fetchone()
    payload = json.loads(row["payload_json"])
    payload["policy_fingerprint"] = "tampered"
    repository._connection.execute(
        "UPDATE prebreakout_policy_selections SET payload_json=? WHERE id='selection'",
        (json.dumps(payload, separators=(",", ":")),),
    )
    repository._connection.commit()
    with pytest.raises(ValueError, match="FINGERPRINT_MISMATCH"):
        materializer.materialize(instrument_id=INSTRUMENT_ID, as_of=AS_OF)


def test_missing_delivery_is_unavailable_not_an_implicit_pass(tmp_path) -> None:
    materializer, _, _ = _materializer(tmp_path, delivery=None)
    value = materializer.materialize(instrument_id=INSTRUMENT_ID, as_of=AS_OF)
    assert value.status is PreBreakoutResolvedInputStatus.DATA_UNAVAILABLE
    assert value.official_delivery_pct is None and value.delivery_pass is None
    assert "OFFICIAL_DELIVERY_UNAVAILABLE" in value.blockers
