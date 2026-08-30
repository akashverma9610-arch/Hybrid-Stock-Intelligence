from __future__ import annotations

from datetime import UTC, datetime, timedelta
from dataclasses import replace
from decimal import Decimal

from app.market_data.historical import BarWriteOutcome, SQLiteHistoricalBarStore
from app.market_data.models import (
    AdjustmentStatus, CanonicalOHLCVBar, Exchange, InstrumentIdentity, InstrumentType,
    MarketDataProvenance, Timeframe,
)
from app.market_data.reference_data.resolver import TickSizeReferenceResolver, floor_to_tick_grid
from app.market_data.reference_data.tick_size import (
    NseTickSizeObservation, NseTickSizeSegment, TickSizeAvailabilitySemantics, TickSizeSourceClass,
)
from app.storage.sqlite_governance_repository import SQLiteStrategyGovernanceRepository
from app.strategies.pre_breakout.governance import PreBreakoutPolicyGovernanceService
from app.strategies.pre_breakout.governance_commands import PreBreakoutPolicyGovernanceCommandService
from app.strategies.pre_breakout.materialization import (
    GovernedPreBreakoutTechnicalMaterializer, PreBreakoutStructuralStatus, _confirmed_pivots,
)
from app.strategies.pre_breakout.policy import (
    PreBreakoutPolicyApprovalDecision,
    PreBreakoutPolicySelectionContext,
)


T = datetime(2026, 8, 28, 10, tzinfo=UTC)
INSTRUMENT_ID = "NSE:STRUCTURE"
V11 = "d61d2c51cf9af96fbee450d35b32354f688b89dc8bccba62592e761cdf39920d"
V12 = "c297513b6edd2da8e85dc5ceebd31c882527b8165118e964531c93d6dfdb5aef"
V13 = "ec748a3d21c6d44b05006ceeaca78cb95b52823a212df5bf59c1c96116f730ba"


class _TickRepository:
    def __init__(self, values=()): self.values = tuple(values)
    def save_tick_size_observation(self, value): self.values += (value,)
    def get_tick_size_observation(self, record_id): return next((item for item in self.values if item.record_id == record_id), None)
    def list_tick_size_observations(self, canonical_instrument_id=None, source_class=None):
        return tuple(item for item in self.values if (canonical_instrument_id is None or item.canonical_instrument_id == canonical_instrument_id) and (source_class is None or item.source_class is source_class))


def _identity() -> InstrumentIdentity:
    return InstrumentIdentity(INSTRUMENT_ID, Exchange.NSE, "STRUCTURE", "STRUCTURE", "INE000A01001", "EQ", InstrumentType.NSE_EQUITY, "Structure")


def _bar(index: int, high: str, low: str, close: str, *, total: int = 20) -> CanonicalOHLCVBar:
    at = T - timedelta(days=total - index)
    return CanonicalOHLCVBar(
        f"structure:{index}", _identity(), Timeframe.DAILY, at, at, Decimal(low) + Decimal("1"), Decimal(high), Decimal(low), Decimal(close),
        1_000_000, None, None, AdjustmentStatus.UNKNOWN,
        MarketDataProvenance("fixture", INSTRUMENT_ID, at, at, at, "fixture"),
    )


def _bars(*, final_close: str = "100", final_low: str | None = None):
    highs = ("100", "101", "102", "110", "104", "103", "102", "103", "104", "110", "104", "103", "102", "104", "105", "110", "105", "104", "103", "104")
    lows = ("95", "96", "97", "98", "97", "96", "90", "96", "97", "98", "97", "96", "90", "96", "97", "98", "97", "96", "95", "96")
    return tuple(_bar(index, high, final_low if index == len(highs) - 1 and final_low is not None else low, final_close if index == len(highs) - 1 else "100") for index, (high, low) in enumerate(zip(highs, lows, strict=True)))


def _bars_500_450(*, final_close: str = "490"):
    highs = ("490", "491", "492", "500", "494", "493", "492", "493", "494", "500", "494", "493", "492", "494", "495", "500", "495", "494", "493", "494")
    lows = ("455", "456", "457", "458", "457", "456", "450", "456", "457", "458", "457", "456", "450", "456", "457", "458", "457", "456", "455", "456")
    return tuple(
        _bar(
            index,
            max(Decimal(high), Decimal(final_close)) if index == len(highs) - 1 else high,
            low,
            final_close if index == len(highs) - 1 else "490",
        )
        for index, (high, low) in enumerate(zip(highs, lows, strict=True))
    )


def _flat_bars():
    """Valid canonical bars with no strict three-left/right pivot structure."""
    return tuple(_bar(index, "100", "95", "99") for index in range(20))


def _bars_60():
    prefix = tuple(_bar(index, "480", "440", "470", total=60) for index in range(40))
    suffix = tuple(replace(value, bar_id=f"structure:base:{index}") for index, value in enumerate(_bars_500_450()))
    return prefix + suffix


def _replace_bar(bars, index: int, **changes):
    return tuple(replace(value, **changes) if position == index else value for position, value in enumerate(bars))


def _governance(tmp_path, *, v13_effective: datetime | None = None) -> PreBreakoutPolicyGovernanceService:
    repository = SQLiteStrategyGovernanceRepository(str(tmp_path / "governance.sqlite"))
    commands = PreBreakoutPolicyGovernanceCommandService(repository)
    commands.approve(approval_id="v11", policy_id="pre-breakout-policy-v1", policy_version="v1.1-draft", decision=PreBreakoutPolicyApprovalDecision.APPROVE, reviewer_id="human:tester", reviewed_at=T - timedelta(seconds=3))
    commands.select_for_current_stored_scan(selection_id="s11", approval_id="v11", selected_by="human:tester", selected_at=T - timedelta(seconds=2), effective_from=T - timedelta(seconds=2))
    commands.approve(approval_id="v12", policy_id="pre-breakout-policy-v1", policy_version="v1.2-draft", decision=PreBreakoutPolicyApprovalDecision.APPROVE, reviewer_id="human:tester", reviewed_at=T - timedelta(seconds=1))
    commands.select_for_current_stored_scan(selection_id="s12", approval_id="v12", selected_by="human:tester", selected_at=T, effective_from=T)
    if v13_effective is not None:
        commands.approve(approval_id="v13", policy_id="pre-breakout-policy-v1", policy_version="v1.3-draft", decision=PreBreakoutPolicyApprovalDecision.APPROVE, reviewer_id="human:tester", reviewed_at=v13_effective - timedelta(microseconds=1))
        commands.select_for_current_stored_scan(selection_id="s13", approval_id="v13", selected_by="human:tester", selected_at=v13_effective, effective_from=v13_effective)
    return PreBreakoutPolicyGovernanceService(repository)


def _tick() -> NseTickSizeObservation:
    return NseTickSizeObservation("tick", INSTRUMENT_ID, Exchange.NSE, NseTickSizeSegment.NSE_CASH_EQUITY, "INE000A01001", Decimal("0.05"), TickSizeSourceClass.OFFICIAL_EXCHANGE, "fixture-nse", "fixture-artifact", T - timedelta(days=30), None, None, TickSizeAvailabilitySemantics.FIRST_OBSERVED_ONLY)


def _materializer(tmp_path, *, resolver=None, bars=None, v13_effective: datetime | None = None):
    tmp_path.mkdir(parents=True, exist_ok=True)
    history = SQLiteHistoricalBarStore(tmp_path / "history.sqlite")
    for value in bars or _bars():
        assert history.upsert(value) is BarWriteOutcome.INSERTED
    return GovernedPreBreakoutTechnicalMaterializer(governance=_governance(tmp_path, v13_effective=v13_effective), historical_store=history, delivery_store=None, tick_resolver=resolver)


def test_v11_history_remains_structurally_unavailable_and_v12_uses_selected_lineage(tmp_path) -> None:
    materializer = _materializer(tmp_path)
    before = materializer.materialize_structure(instrument_id=INSTRUMENT_ID, as_of=T - timedelta(microseconds=1))
    at = materializer.materialize_structure(instrument_id=INSTRUMENT_ID, as_of=T)

    assert before.status is PreBreakoutStructuralStatus.POLICY_SEMANTICS_UNAVAILABLE
    assert before.policy_version == "v1.1-draft" and before.policy_fingerprint == V11
    assert at.policy_version == "v1.2-draft" and at.policy_fingerprint == V12
    assert at.status is PreBreakoutStructuralStatus.TICK_SIZE_UNAVAILABLE
    assert at.final_stop is at.target is at.actual_rr is None


def test_selected_v12_materializes_exact_base_support_tick_and_geometry_conflict(tmp_path) -> None:
    resolver = TickSizeReferenceResolver(_TickRepository((_tick(),)))
    result = _materializer(tmp_path, resolver=resolver, bars=_bars_500_450()).materialize_structure(instrument_id=INSTRUMENT_ID, as_of=T)

    assert result.valid_window_count == 1 and result.selected_base is not None
    assert result.selected_base.duration == 20 and result.selected_base.base_top == Decimal("500")
    assert result.selected_base.base_top_source_pivot_session == _bars_500_450()[15].end_time
    assert result.resistance == result.trigger == Decimal("500")
    assert result.structural_support == Decimal("450") and result.support_pivot is not None
    assert result.support_pivot.session == _bars_500_450()[12].end_time
    assert result.tick_size == Decimal("0.05") and result.support_grid_aligned is True
    assert result.final_stop == Decimal("449.95")
    assert result.target == Decimal("550") and result.target_grid_aligned is True
    assert result.reward == Decimal("50") and result.risk == Decimal("50.05")
    assert result.actual_rr == Decimal("50") / Decimal("50.05") and result.actual_rr < Decimal("1")
    assert result.rr_pass is False and result.status is PreBreakoutStructuralStatus.POLICY_GEOMETRY_CONFLICT
    assert {"RR_FAIL", "POLICY_GEOMETRY_CONFLICT"} <= set(result.blockers)


def test_exact_20_to_60_suffix_windows_and_conservative_shortest_selection(tmp_path) -> None:
    bars = _bars_60()
    resolver = TickSizeReferenceResolver(_TickRepository((_tick(),)))
    materializer = _materializer(tmp_path, resolver=resolver, bars=bars)
    selected = materializer._governance.get_selected_prebreakout_policy(  # type: ignore[attr-defined]
        context=PreBreakoutPolicySelectionContext.CURRENT_STORED_SCAN,
        as_of=T,
    )
    assert selected is not None
    windows = materializer._valid_base_windows(INSTRUMENT_ID, T, bars, selected.policy)  # type: ignore[attr-defined]
    result = materializer.materialize_structure(instrument_id=INSTRUMENT_ID, as_of=T)

    assert {20, 60} <= {window.duration for window in windows}
    assert result.selected_base is not None and result.selected_base.duration == 20
    assert result.selected_base.base_top == Decimal("500")


def test_minimum_session_and_pivot_requirements_fail_closed(tmp_path) -> None:
    too_short = _materializer(tmp_path / "short", bars=_bars()[:-1]).materialize_structure(instrument_id=INSTRUMENT_ID, as_of=T)
    no_highs = _materializer(
        tmp_path / "no-highs", bars=tuple(replace(value, high=Decimal("100")) for value in _bars())
    ).materialize_structure(instrument_id=INSTRUMENT_ID, as_of=T)
    no_lows = _materializer(
        tmp_path / "no-lows", bars=tuple(replace(value, low=Decimal("90")) for value in _bars())
    ).materialize_structure(instrument_id=INSTRUMENT_ID, as_of=T)

    assert too_short.status is PreBreakoutStructuralStatus.DATA_UNAVAILABLE
    assert no_highs.status is PreBreakoutStructuralStatus.NO_VALID_BASE_WINDOW
    assert no_lows.status is PreBreakoutStructuralStatus.NO_VALID_BASE_WINDOW


def test_last_confirmed_lows_must_be_non_decreasing_and_equal_or_higher_is_valid(tmp_path) -> None:
    decreasing = _materializer(tmp_path / "decreasing", bars=_replace_bar(_bars(), 12, low=Decimal("89"))).materialize_structure(instrument_id=INSTRUMENT_ID, as_of=T)
    equal = _materializer(tmp_path / "equal-lows", bars=_bars()).materialize_structure(instrument_id=INSTRUMENT_ID, as_of=T)
    higher = _materializer(
        tmp_path / "higher", bars=_replace_bar(_bars(), 12, low=Decimal("91"))
    ).materialize_structure(instrument_id=INSTRUMENT_ID, as_of=T)

    assert decreasing.status is PreBreakoutStructuralStatus.NO_VALID_BASE_WINDOW
    assert equal.status is PreBreakoutStructuralStatus.TICK_SIZE_UNAVAILABLE
    assert higher.status is PreBreakoutStructuralStatus.TICK_SIZE_UNAVAILABLE
    assert higher.structural_support == Decimal("91")


def test_future_confirmation_is_not_an_eligible_pivot() -> None:
    bars = _replace_bar(
        _bars(), 18,
        provenance=replace(_bars()[18].provenance, received_at=T + timedelta(microseconds=1)),
    )
    highs, _ = _confirmed_pivots(INSTRUMENT_ID, T, bars, 3, 3)

    # The canonical series rejects a future-received bar before any pivot can be
    # used, which is stricter than merely excluding the pending confirmation.
    assert highs == ()


def test_raw_close_above_base_top_and_future_bar_visibility_are_invalid(tmp_path) -> None:
    above_top = _materializer(
        tmp_path / "above-top", bars=_replace_bar(_bars(), 19, high=Decimal("112"), close=Decimal("111"))
    ).materialize_structure(instrument_id=INSTRUMENT_ID, as_of=T)
    future_received = _materializer(
        tmp_path / "future-received",
        bars=_replace_bar(_bars(), 19, provenance=replace(_bars()[19].provenance, received_at=T + timedelta(microseconds=1))),
    ).materialize_structure(instrument_id=INSTRUMENT_ID, as_of=T)

    assert above_top.status is PreBreakoutStructuralStatus.NO_VALID_BASE_WINDOW
    assert future_received.status is PreBreakoutStructuralStatus.DATA_UNAVAILABLE


def test_support_breach_is_strict_and_equal_close_is_not_a_breach(tmp_path) -> None:
    resolver = TickSizeReferenceResolver(_TickRepository((_tick(),)))
    equal = _materializer(tmp_path / "equal", resolver=resolver, bars=_bars(final_close="90", final_low="90")).materialize_structure(instrument_id=INSTRUMENT_ID, as_of=T)
    assert equal.support_breached is False
    broken = _materializer(tmp_path / "broken", resolver=resolver, bars=_bars(final_close="89", final_low="89")).materialize_structure(instrument_id=INSTRUMENT_ID, as_of=T)
    assert broken.status is PreBreakoutStructuralStatus.BASE_STRUCTURE_BROKEN and broken.support_breached is True


def test_reference_conflict_and_tick_grid_misalignment_fail_closed(tmp_path) -> None:
    conflict = TickSizeReferenceResolver(_TickRepository((_tick(), NseTickSizeObservation("tick-2", INSTRUMENT_ID, Exchange.NSE, NseTickSizeSegment.NSE_CASH_EQUITY, "INE000A01001", Decimal("0.10"), TickSizeSourceClass.OFFICIAL_EXCHANGE, "fixture-nse", "fixture-artifact-2", T - timedelta(days=29), None, None, TickSizeAvailabilitySemantics.FIRST_OBSERVED_ONLY))))
    value = _materializer(tmp_path, resolver=conflict).materialize_structure(instrument_id=INSTRUMENT_ID, as_of=T)
    assert value.status is PreBreakoutStructuralStatus.REFERENCE_DATA_CONFLICT and value.final_stop is None

    misaligned_tick = NseTickSizeObservation(
        "misaligned-tick", INSTRUMENT_ID, Exchange.NSE, NseTickSizeSegment.NSE_CASH_EQUITY,
        "INE000A01001", Decimal("0.07"), TickSizeSourceClass.OFFICIAL_EXCHANGE,
        "fixture-nse", "fixture-artifact", T - timedelta(days=30), None, None,
        TickSizeAvailabilitySemantics.FIRST_OBSERVED_ONLY,
    )
    misaligned = TickSizeReferenceResolver(_TickRepository((misaligned_tick,)))
    value = _materializer(tmp_path / "misaligned", resolver=misaligned).materialize_structure(instrument_id=INSTRUMENT_ID, as_of=T)
    assert value.status is PreBreakoutStructuralStatus.TICK_GRID_ALIGNMENT_ERROR
    assert value.support_grid_aligned is False and value.final_stop is None


def test_no_confirmed_pivot_base_fails_closed_without_invoking_tick_resolution(tmp_path) -> None:
    result = _materializer(tmp_path, bars=_flat_bars()).materialize_structure(instrument_id=INSTRUMENT_ID, as_of=T)

    assert result.status is PreBreakoutStructuralStatus.NO_VALID_BASE_WINDOW
    assert result.valid_window_count == 0 and result.selected_base is None
    assert result.tick_size is None and result.final_stop is None


def test_structural_result_has_no_candidate_signal_or_trade_output(tmp_path) -> None:
    value = _materializer(tmp_path).materialize_structure(instrument_id=INSTRUMENT_ID, as_of=T)
    assert not any(hasattr(value, field) for field in ("candidate", "signal", "paper_trade", "order", "portfolio_action"))


def test_selected_v13_uses_governed_entry_reference_and_preserves_v12_history(tmp_path) -> None:
    effective = T + timedelta(seconds=1)
    bars = _bars_500_450(final_close="470")
    materializer = _materializer(
        tmp_path, resolver=TickSizeReferenceResolver(_TickRepository((_tick(),))), bars=bars,
        v13_effective=effective,
    )

    historical = materializer.materialize_structure(instrument_id=INSTRUMENT_ID, as_of=effective - timedelta(microseconds=1))
    current = materializer.materialize_structure(instrument_id=INSTRUMENT_ID, as_of=effective)

    assert historical.policy_version == "v1.2-draft" and historical.policy_fingerprint == V12
    assert historical.status is PreBreakoutStructuralStatus.POLICY_GEOMETRY_CONFLICT
    assert current.policy_version == "v1.3-draft" and current.policy_fingerprint == V13
    assert current.status is PreBreakoutStructuralStatus.STRUCTURAL_ENTRY_READY
    assert current.resistance == current.trigger == current.breakout_confirmation_trigger == Decimal("500")
    assert current.breakout_trigger_role == "CONFIRMATION_NOT_INITIAL_ENTRY"
    assert current.entry_reference_price == Decimal("470")
    assert current.entry_reference_session == bars[-1].end_time
    assert current.maximum_acceptable_entry_price == Decimal("474.9625")
    assert current.maximum_executable_entry_price == Decimal("474.95")
    assert (current.target - current.maximum_acceptable_entry_price) / (
        current.maximum_acceptable_entry_price - current.final_stop
    ) == Decimal("3")
    assert current.entry_reference_risk == Decimal("20.05")
    assert current.entry_reference_reward == Decimal("80")
    assert current.entry_reference_rr == Decimal("80") / Decimal("20.05")
    assert current.entry_reference_rr_pass is True
    assert current.actual_execution_price is None and current.actual_execution_status == "NOT_EVALUATED_AT_SCAN"
    assert current.entry_economics_status == "PASS" and current.policy_semantic_conflict is False
    assert not any(hasattr(current, field) for field in ("candidate", "signal", "paper_trade", "order", "portfolio_action"))


def test_v13_reference_examples_reject_setup_economics_without_policy_conflict(tmp_path) -> None:
    effective = T + timedelta(seconds=1)
    resolver = TickSizeReferenceResolver(_TickRepository((_tick(),)))
    expected = (
        ("474.95", PreBreakoutStructuralStatus.STRUCTURAL_ENTRY_READY, "PASS", Decimal("3.002")),
        ("475", PreBreakoutStructuralStatus.ENTRY_RR_FAIL, "REFERENCE_ENTRY_TOO_HIGH", Decimal("75") / Decimal("25.05")),
        ("500", PreBreakoutStructuralStatus.PRE_BREAKOUT_ENTRY_NOT_AVAILABLE, "PRE_BREAKOUT_ENTRY_NOT_AVAILABLE", None),
    )
    for close, status, economics_status, expected_rr in expected:
        value = _materializer(
            tmp_path / close.replace(".", "_"), resolver=resolver, bars=_bars_500_450(final_close=close),
            v13_effective=effective,
        ).materialize_structure(instrument_id=INSTRUMENT_ID, as_of=effective)
        assert value.status is status
        assert value.entry_economics_status == economics_status
        assert value.policy_semantic_conflict is False
        if expected_rr is None:
            assert value.entry_reference_rr is None
        else:
            assert value.entry_reference_rr == expected_rr


def test_v13_tick_floor_is_exact_never_nearest_or_upward_and_is_grid_aligned() -> None:
    assert floor_to_tick_grid(Decimal("474.9625"), Decimal("0.05")) == Decimal("474.95")
    assert floor_to_tick_grid(Decimal("474.95"), Decimal("0.05")) == Decimal("474.95")
    assert floor_to_tick_grid(Decimal("474.99"), Decimal("0.05")) == Decimal("474.95")


def test_v13_tick_unavailable_and_reference_conflict_keep_entry_economics_unavailable(tmp_path) -> None:
    effective = T + timedelta(seconds=1)
    bars = _bars_500_450(final_close="470")
    unavailable = _materializer(tmp_path / "unavailable", bars=bars, v13_effective=effective).materialize_structure(
        instrument_id=INSTRUMENT_ID, as_of=effective,
    )
    conflict = _materializer(
        tmp_path / "conflict",
        resolver=TickSizeReferenceResolver(_TickRepository((_tick(), NseTickSizeObservation(
            "tick-2", INSTRUMENT_ID, Exchange.NSE, NseTickSizeSegment.NSE_CASH_EQUITY, "INE000A01001",
            Decimal("0.10"), TickSizeSourceClass.OFFICIAL_EXCHANGE, "fixture-nse", "fixture-artifact-2",
            T - timedelta(days=29), None, None, TickSizeAvailabilitySemantics.FIRST_OBSERVED_ONLY,
        )))),
        bars=bars, v13_effective=effective,
    ).materialize_structure(instrument_id=INSTRUMENT_ID, as_of=effective)

    assert unavailable.status is PreBreakoutStructuralStatus.TICK_SIZE_UNAVAILABLE
    assert conflict.status is PreBreakoutStructuralStatus.REFERENCE_DATA_CONFLICT
    assert unavailable.maximum_acceptable_entry_price is unavailable.maximum_executable_entry_price is None
    assert conflict.maximum_acceptable_entry_price is conflict.maximum_executable_entry_price is None
