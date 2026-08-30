"""Stored-only materialization of the fully governed Pre-Breakout inputs."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum

from app.analysis.models import AnalysisStatus
from app.analysis.technical import TechnicalAnalysisEngine, _pivots
from app.analysis.series import price_bar_series
from app.domain.models import AsOfSnapshot, StrategyVersionReference, ValidationResult, ValidationStatus
from app.market_data.bridge import price_bar_observation
from app.market_data.models import Timeframe
from app.market_data.reference_data.resolver import (
    TickSizeReferenceResolver,
    TickSizeResolutionStatus,
    floor_to_tick_grid,
    validate_price_on_tick_grid,
)
from app.strategies.pre_breakout.governance import PreBreakoutPolicyGovernanceService
from app.strategies.pre_breakout.policy import (
    ConsolidationVolumeSemanticStatus,
    PreBreakoutPolicySelectionContext,
    PreBreakoutMultiStageEntrySuccessorDraft,
    PreBreakoutStructuralSuccessorDraft,
)


class PreBreakoutResolvedInputStatus(StrEnum):
    COMPLETE_RESOLVED_INPUTS = "COMPLETE_RESOLVED_INPUTS"
    PARTIAL_POLICY_BLOCKED = "PARTIAL_POLICY_BLOCKED"
    DATA_UNAVAILABLE = "DATA_UNAVAILABLE"
    GOVERNANCE_UNAVAILABLE = "GOVERNANCE_UNAVAILABLE"


@dataclass(frozen=True, slots=True)
class GovernedPreBreakoutResolvedInputs:
    instrument_id: str
    evaluation_as_of: datetime
    evaluation_session: datetime | None
    status: PreBreakoutResolvedInputStatus
    policy_id: str | None
    policy_version: str | None
    policy_fingerprint: str | None
    selection_id: str | None
    selection_fingerprint: str | None
    canonical_session_count: int
    latest_close: Decimal | None
    bbw_percentile: Decimal | None
    bbw_pass: bool | None
    current_atr14: Decimal | None
    previous_5_atr14: tuple[Decimal, ...]
    previous_5_atr14_mean: Decimal | None
    atr_contraction_pass: bool | None
    atr_observation_session: datetime | None
    rsi14: Decimal | None
    rsi_pass: bool | None
    official_delivery_pct: Decimal | None
    delivery_pass: bool | None
    high_252: Decimal | None
    high_252_session_count: int
    distance_below_high_pct: Decimal | None
    distance_from_high_pass: bool | None
    current_volume: int | None
    sma20_volume: Decimal | None
    volume_dry_up_status: str
    prior_20_volumes: tuple[int, ...]
    prior_20_volume_mean: Decimal | None
    volume_threshold_ratio: Decimal | None
    volume_threshold_value: Decimal | None
    volume_operator: str | None
    volume_dry_up_pass: bool | None
    volume_evaluation_session: datetime | None
    unresolved_fields: tuple[str, ...]
    blockers: tuple[str, ...]


class PreBreakoutStructuralStatus(StrEnum):
    STRUCTURAL_READY = "STRUCTURAL_READY"
    STRUCTURAL_ENTRY_READY = "STRUCTURAL_ENTRY_READY"
    POLICY_SEMANTICS_UNAVAILABLE = "POLICY_SEMANTICS_UNAVAILABLE"
    DATA_UNAVAILABLE = "DATA_UNAVAILABLE"
    NO_VALID_BASE_WINDOW = "NO_VALID_BASE_WINDOW"
    BASE_STRUCTURE_BROKEN = "BASE_STRUCTURE_BROKEN"
    TICK_SIZE_UNAVAILABLE = "TICK_SIZE_UNAVAILABLE"
    REFERENCE_DATA_CONFLICT = "REFERENCE_DATA_CONFLICT"
    TICK_GRID_ALIGNMENT_ERROR = "TICK_GRID_ALIGNMENT_ERROR"
    INVALID_TARGET_GEOMETRY = "INVALID_TARGET_GEOMETRY"
    POLICY_GEOMETRY_CONFLICT = "POLICY_GEOMETRY_CONFLICT"
    INVALID_PRE_BREAKOUT_ENTRY_GEOMETRY = "INVALID_PRE_BREAKOUT_ENTRY_GEOMETRY"
    NO_VALID_PRE_BREAKOUT_ENTRY_PRICE = "NO_VALID_PRE_BREAKOUT_ENTRY_PRICE"
    PRE_BREAKOUT_ENTRY_NOT_AVAILABLE = "PRE_BREAKOUT_ENTRY_NOT_AVAILABLE"
    ENTRY_RR_FAIL = "ENTRY_RR_FAIL"


@dataclass(frozen=True, slots=True)
class GovernedPreBreakoutPivot:
    bar_id: str
    session: datetime
    price: Decimal
    confirmation_session: datetime


@dataclass(frozen=True, slots=True)
class GovernedPreBreakoutBaseWindow:
    start: datetime
    end: datetime
    duration: int
    pivot_highs: tuple[GovernedPreBreakoutPivot, ...]
    pivot_lows: tuple[GovernedPreBreakoutPivot, ...]
    base_top: Decimal
    base_top_source_pivot_session: datetime


@dataclass(frozen=True, slots=True)
class GovernedPreBreakoutStructuralResult:
    instrument_id: str
    evaluation_as_of: datetime
    evaluation_session: datetime | None
    status: PreBreakoutStructuralStatus
    policy_id: str | None
    policy_version: str | None
    policy_fingerprint: str | None
    selection_id: str | None
    selection_fingerprint: str | None
    canonical_session_count: int
    valid_window_count: int
    selected_base: GovernedPreBreakoutBaseWindow | None
    resistance: Decimal | None
    trigger: Decimal | None
    support_pivot: GovernedPreBreakoutPivot | None
    structural_support: Decimal | None
    support_breached: bool | None
    tick_resolution_status: str | None
    tick_size: Decimal | None
    tick_record_id: str | None
    support_grid_aligned: bool | None
    final_stop: Decimal | None
    target: Decimal | None
    target_grid_aligned: bool | None
    risk: Decimal | None
    reward: Decimal | None
    actual_rr: Decimal | None
    rr_pass: bool | None
    blockers: tuple[str, ...]
    breakout_confirmation_trigger: Decimal | None = None
    breakout_trigger_role: str | None = None
    entry_reference_price: Decimal | None = None
    entry_reference_session: datetime | None = None
    entry_reference_geometry_status: str | None = None
    maximum_acceptable_entry_price: Decimal | None = None
    maximum_executable_entry_price: Decimal | None = None
    entry_reference_risk: Decimal | None = None
    entry_reference_reward: Decimal | None = None
    entry_reference_rr: Decimal | None = None
    entry_reference_rr_pass: bool | None = None
    actual_execution_price: Decimal | None = None
    actual_execution_status: str | None = None
    entry_economics_status: str | None = None
    policy_semantic_conflict: bool | None = None


class GovernedPreBreakoutTechnicalMaterializer:
    """Read-only selected-policy input assembly; it cannot emit candidates or orders."""

    def __init__(self, *, governance: PreBreakoutPolicyGovernanceService, historical_store, delivery_store,
                 technical: TechnicalAnalysisEngine | None = None,
                 tick_resolver: TickSizeReferenceResolver | None = None) -> None:
        self._governance = governance
        self._historical = historical_store
        self._delivery = delivery_store
        self._technical = technical or TechnicalAnalysisEngine()
        self._tick_resolver = tick_resolver

    def materialize(self, *, instrument_id: str, as_of: datetime) -> GovernedPreBreakoutResolvedInputs:
        selected = self._governance.get_selected_prebreakout_policy(
            context=PreBreakoutPolicySelectionContext.CURRENT_STORED_SCAN,
            as_of=as_of,
        )
        if selected is None:
            return self._unavailable(instrument_id, as_of, "SELECTED_POLICY_UNAVAILABLE")
        if self._historical.has_conflict_artifact(instrument_id):
            # Do not turn unresolved same-provider OHLCV revisions into
            # technical evidence.  The durable artifact is the sole conflict
            # source; no bar is changed or reselected here.
            return self._result(selected, instrument_id, as_of, (), (), ("OHLCV_CONFLICTED",))
        bars = self._historical.range(
            instrument_id, Timeframe.DAILY, datetime.min.replace(tzinfo=UTC), as_of, as_of=as_of,
        )
        if not bars:
            return self._result(selected, instrument_id, as_of, (), (), ("NO_CANONICAL_HISTORICAL_BARS",))
        snapshot = _snapshot(instrument_id, as_of, bars)
        policy = selected.policy
        reference = StrategyVersionReference("prebreakout-governed-materialization", policy.version)
        bbw = self._technical.bollinger_band_width_percentile(snapshot, instrument_id=instrument_id, strategy_version=reference, evaluated_at=as_of, history_sessions=policy.bbw_history_sessions)
        rsi = self._technical.rsi(snapshot, instrument_id=instrument_id, strategy_version=reference, evaluated_at=as_of, period=policy.rsi_period)
        atr_values = self._atr_values(instrument_id, as_of, bars, reference, policy.atr_period)
        delivery = self._delivery.latest_official_delivery(instrument_id, as_of=as_of) if self._delivery is not None else None
        return self._result(selected, instrument_id, as_of, bars, atr_values, (), bbw=bbw, rsi=rsi, delivery=delivery)

    def materialize_structure(self, *, instrument_id: str, as_of: datetime) -> GovernedPreBreakoutStructuralResult:
        """Materialize selected structural facts only; never emit a candidate or order."""
        selected = self._governance.get_selected_prebreakout_policy(
            context=PreBreakoutPolicySelectionContext.CURRENT_STORED_SCAN, as_of=as_of,
        )
        if selected is None:
            return self._structural_empty(instrument_id, as_of, PreBreakoutStructuralStatus.POLICY_SEMANTICS_UNAVAILABLE,
                                          ("SELECTED_POLICY_UNAVAILABLE",))
        if self._historical.has_conflict_artifact(instrument_id):
            return self._structural_empty(
                instrument_id, as_of, PreBreakoutStructuralStatus.DATA_UNAVAILABLE,
                ("OHLCV_CONFLICTED",),
            )
        bars = self._historical.range(
            instrument_id, Timeframe.DAILY, datetime.min.replace(tzinfo=UTC), as_of, as_of=as_of,
        )
        policy = selected.policy
        lineage = dict(policy_id=policy.policy_id, policy_version=policy.version,
                       policy_fingerprint=selected.policy_fingerprint, selection_id=selected.selection.selection_id,
                       selection_fingerprint=selected.selection_fingerprint)
        if not isinstance(policy, PreBreakoutStructuralSuccessorDraft) or not policy.policy_fully_resolved:
            return self._structural_empty(instrument_id, as_of, PreBreakoutStructuralStatus.POLICY_SEMANTICS_UNAVAILABLE,
                                          ("POLICY_STRUCTURAL_SEMANTICS_UNAVAILABLE",), bars=bars, **lineage)
        if len(bars) < policy.base_duration_min_sessions:
            return self._structural_empty(instrument_id, as_of, PreBreakoutStructuralStatus.DATA_UNAVAILABLE,
                                          ("INSUFFICIENT_CANONICAL_SESSIONS",), bars=bars, **lineage)
        windows = self._valid_base_windows(instrument_id, as_of, bars, policy)
        if not windows:
            return self._structural_empty(instrument_id, as_of, PreBreakoutStructuralStatus.NO_VALID_BASE_WINDOW,
                                          ("NO_VALID_WINDOW",), bars=bars, valid_window_count=0, **lineage)
        maximum_top = max(value.base_top for value in windows)
        selected_base = min((value for value in windows if value.base_top == maximum_top), key=lambda value: value.duration)
        support = selected_base.pivot_lows[-1]
        close = bars[-1].close
        common = dict(bars=bars, valid_window_count=len(windows), selected_base=selected_base,
                      resistance=selected_base.base_top, trigger=selected_base.base_top,
                      support_pivot=support, structural_support=support.price)
        if close < support.price:
            return self._structural_empty(instrument_id, as_of, PreBreakoutStructuralStatus.BASE_STRUCTURE_BROKEN,
                                          ("BASE_STRUCTURE_BROKEN",), support_breached=True, **lineage, **common)
        if self._tick_resolver is None:
            return self._structural_empty(instrument_id, as_of, PreBreakoutStructuralStatus.TICK_SIZE_UNAVAILABLE,
                                          ("TICK_SIZE_UNAVAILABLE_FOR_AS_OF",), support_breached=False,
                                          tick_resolution_status=TickSizeResolutionStatus.TICK_SIZE_UNAVAILABLE_FOR_AS_OF.value,
                                          **lineage, **common)
        resolution = self._tick_resolver.resolve_tick_size(instrument_id, as_of=as_of)
        tick_common = dict(support_breached=False, tick_resolution_status=resolution.status.value,
                           tick_size=resolution.tick_size, tick_record_id=resolution.selected_record_id)
        if resolution.status is TickSizeResolutionStatus.TICK_SIZE_UNAVAILABLE_FOR_AS_OF:
            return self._structural_empty(instrument_id, as_of, PreBreakoutStructuralStatus.TICK_SIZE_UNAVAILABLE,
                                          (resolution.status.value,), **lineage, **common, **tick_common)
        if resolution.status is TickSizeResolutionStatus.REFERENCE_DATA_CONFLICT:
            return self._structural_empty(instrument_id, as_of, PreBreakoutStructuralStatus.REFERENCE_DATA_CONFLICT,
                                          (resolution.status.value,), **lineage, **common, **tick_common)
        if resolution.status is not TickSizeResolutionStatus.AVAILABLE or resolution.tick_size is None:
            return self._structural_empty(instrument_id, as_of, PreBreakoutStructuralStatus.DATA_UNAVAILABLE,
                                          (resolution.status.value,), **lineage, **common, **tick_common)
        try:
            validate_price_on_tick_grid(support.price, resolution.tick_size)
        except ValueError as error:
            return self._structural_empty(instrument_id, as_of, PreBreakoutStructuralStatus.TICK_GRID_ALIGNMENT_ERROR,
                                          (str(error),), support_grid_aligned=False, **lineage, **common, **tick_common)
        stop = support.price - resolution.tick_size
        if stop <= Decimal("0"):
            return self._structural_empty(instrument_id, as_of, PreBreakoutStructuralStatus.INVALID_TARGET_GEOMETRY,
                                          ("FINAL_STOP_NON_POSITIVE",), support_grid_aligned=True, **lineage, **common, **tick_common)
        try:
            validate_price_on_tick_grid(stop, resolution.tick_size)
        except ValueError as error:
            return self._structural_empty(instrument_id, as_of, PreBreakoutStructuralStatus.TICK_GRID_ALIGNMENT_ERROR,
                                          (str(error),), support_grid_aligned=True, final_stop=stop, **lineage, **common, **tick_common)
        if selected_base.base_top <= support.price:
            return self._structural_empty(instrument_id, as_of, PreBreakoutStructuralStatus.INVALID_TARGET_GEOMETRY,
                                          ("INVALID_TARGET_GEOMETRY",), support_grid_aligned=True, final_stop=stop,
                                          **lineage, **common, **tick_common)
        target = selected_base.base_top + (selected_base.base_top - support.price)
        try:
            validate_price_on_tick_grid(target, resolution.tick_size)
        except ValueError as error:
            return self._structural_empty(instrument_id, as_of, PreBreakoutStructuralStatus.TICK_GRID_ALIGNMENT_ERROR,
                                          (str(error),), support_grid_aligned=True, final_stop=stop, target=target,
                                          target_grid_aligned=False, **lineage, **common, **tick_common)
        if isinstance(policy, PreBreakoutMultiStageEntrySuccessorDraft):
            return self._materialize_v1_3_entry_economics(
                instrument_id=instrument_id,
                as_of=as_of,
                policy=policy,
                bars=bars,
                final_stop=stop,
                target=target,
                trigger=selected_base.base_top,
                tick_size=resolution.tick_size,
                lineage=lineage,
                common=common,
                tick_common=tick_common,
            )
        risk = selected_base.base_top - stop
        reward = target - selected_base.base_top
        if risk <= Decimal("0") or reward <= Decimal("0"):
            return self._structural_empty(instrument_id, as_of, PreBreakoutStructuralStatus.INVALID_TARGET_GEOMETRY,
                                          ("INVALID_TARGET_GEOMETRY",), support_grid_aligned=True, final_stop=stop,
                                          target=target, target_grid_aligned=True, risk=risk, reward=reward,
                                          **lineage, **common, **tick_common)
        actual_rr = reward / risk
        rr_pass = actual_rr >= policy.minimum_rr
        status = PreBreakoutStructuralStatus.STRUCTURAL_READY if rr_pass else PreBreakoutStructuralStatus.POLICY_GEOMETRY_CONFLICT
        blockers = () if rr_pass else ("RR_FAIL", "POLICY_GEOMETRY_CONFLICT")
        return self._structural_empty(
            instrument_id, as_of, status, blockers, support_grid_aligned=True, final_stop=stop, target=target,
            target_grid_aligned=True, risk=risk, reward=reward, actual_rr=actual_rr, rr_pass=rr_pass,
            policy_semantic_conflict=status is PreBreakoutStructuralStatus.POLICY_GEOMETRY_CONFLICT,
            **lineage, **common, **tick_common,
        )

    def _materialize_v1_3_entry_economics(
        self, *, instrument_id: str, as_of: datetime, policy: PreBreakoutMultiStageEntrySuccessorDraft,
        bars, final_stop: Decimal, target: Decimal, trigger: Decimal, tick_size: Decimal,
        lineage: dict, common: dict, tick_common: dict,
    ) -> GovernedPreBreakoutStructuralResult:
        """Materialize V1.3 setup economics only; no order or fill is inferred."""
        rule = policy.multi_stage_entry
        entry_reference = bars[-1].close
        common_entry = dict(
            support_grid_aligned=True,
            final_stop=final_stop,
            target=target,
            target_grid_aligned=True,
            breakout_confirmation_trigger=trigger,
            breakout_trigger_role=rule.breakout_trigger_role.value,
            entry_reference_price=entry_reference,
            entry_reference_session=bars[-1].end_time,
            actual_execution_price=None,
            actual_execution_status="NOT_EVALUATED_AT_SCAN",
            policy_semantic_conflict=False,
        )
        try:
            maximum_acceptable = rule.maximum_acceptable_entry_price(
                trigger=trigger, support=final_stop + tick_size, tick_size=tick_size,
            )
            independently_derived = (
                target + policy.minimum_rr * final_stop
            ) / (policy.minimum_rr + Decimal("1"))
            if maximum_acceptable != independently_derived:
                raise ValueError("ENTRY_CEILING_FORMULA_MISMATCH")
            maximum_executable = floor_to_tick_grid(maximum_acceptable, tick_size)
            validate_price_on_tick_grid(maximum_executable, tick_size)
        except ValueError as error:
            return self._structural_empty(
                instrument_id, as_of, PreBreakoutStructuralStatus.DATA_UNAVAILABLE, (str(error),),
                maximum_acceptable_entry_price=None, maximum_executable_entry_price=None,
                entry_economics_status="UNAVAILABLE", **lineage, **common, **tick_common, **common_entry,
            )
        ceiling_common = dict(
            maximum_acceptable_entry_price=maximum_acceptable,
            maximum_executable_entry_price=maximum_executable,
        )
        if maximum_executable <= final_stop:
            return self._structural_empty(
                instrument_id, as_of, PreBreakoutStructuralStatus.NO_VALID_PRE_BREAKOUT_ENTRY_PRICE,
                (rule.no_valid_entry_status,), entry_reference_geometry_status=rule.no_valid_entry_status,
                entry_economics_status="NO_VALID_PRE_BREAKOUT_ENTRY_PRICE", **lineage, **common, **tick_common,
                **common_entry, **ceiling_common,
            )
        if maximum_executable >= trigger:
            return self._structural_empty(
                instrument_id, as_of, PreBreakoutStructuralStatus.PRE_BREAKOUT_ENTRY_NOT_AVAILABLE,
                (rule.trigger_entry_unavailable_status,), entry_reference_geometry_status=rule.trigger_entry_unavailable_status,
                entry_economics_status="PRE_BREAKOUT_ENTRY_NOT_AVAILABLE", **lineage, **common, **tick_common,
                **common_entry, **ceiling_common,
            )
        if entry_reference <= final_stop:
            return self._structural_empty(
                instrument_id, as_of, PreBreakoutStructuralStatus.INVALID_PRE_BREAKOUT_ENTRY_GEOMETRY,
                (rule.invalid_geometry_status,), entry_reference_geometry_status=rule.invalid_geometry_status,
                entry_economics_status="INVALID_PRE_BREAKOUT_ENTRY_GEOMETRY", **lineage, **common, **tick_common,
                **common_entry, **ceiling_common,
            )
        if entry_reference >= trigger:
            return self._structural_empty(
                instrument_id, as_of, PreBreakoutStructuralStatus.PRE_BREAKOUT_ENTRY_NOT_AVAILABLE,
                (rule.trigger_entry_unavailable_status,), entry_reference_geometry_status=rule.trigger_entry_unavailable_status,
                entry_economics_status="PRE_BREAKOUT_ENTRY_NOT_AVAILABLE", **lineage, **common, **tick_common,
                **common_entry, **ceiling_common,
            )
        reference_risk = entry_reference - final_stop
        reference_reward = target - entry_reference
        if reference_risk <= Decimal("0") or reference_reward <= Decimal("0"):
            return self._structural_empty(
                instrument_id, as_of, PreBreakoutStructuralStatus.INVALID_PRE_BREAKOUT_ENTRY_GEOMETRY,
                (rule.invalid_geometry_status,), entry_reference_geometry_status=rule.invalid_geometry_status,
                entry_economics_status="INVALID_PRE_BREAKOUT_ENTRY_GEOMETRY", **lineage, **common, **tick_common,
                **common_entry, **ceiling_common,
            )
        reference_rr = reference_reward / reference_risk
        economics = dict(
            entry_reference_geometry_status="PASS",
            entry_reference_risk=reference_risk,
            entry_reference_reward=reference_reward,
            entry_reference_rr=reference_rr,
            entry_reference_rr_pass=reference_rr >= policy.minimum_rr,
        )
        if entry_reference > maximum_executable:
            return self._structural_empty(
                instrument_id, as_of, PreBreakoutStructuralStatus.ENTRY_RR_FAIL,
                ("REFERENCE_ENTRY_TOO_HIGH", "ENTRY_RR_FAIL"), entry_economics_status="REFERENCE_ENTRY_TOO_HIGH",
                **lineage, **common, **tick_common, **common_entry, **ceiling_common, **economics,
            )
        if reference_rr < policy.minimum_rr:
            return self._structural_empty(
                instrument_id, as_of, PreBreakoutStructuralStatus.ENTRY_RR_FAIL,
                ("ENTRY_RR_FAIL",), entry_economics_status="REFERENCE_RR_FAIL",
                **lineage, **common, **tick_common, **common_entry, **ceiling_common, **economics,
            )
        return self._structural_empty(
            instrument_id, as_of, PreBreakoutStructuralStatus.STRUCTURAL_ENTRY_READY, (),
            entry_economics_status="PASS", **lineage, **common, **tick_common, **common_entry,
            **ceiling_common, **economics,
        )

    def _valid_base_windows(self, instrument_id, as_of, bars, policy) -> tuple[GovernedPreBreakoutBaseWindow, ...]:
        values: list[GovernedPreBreakoutBaseWindow] = []
        maximum = min(policy.base_duration_max_sessions, len(bars))
        # Every candidate window ends at the same latest canonical bar.  The
        # strict pivot predicate is local to a bar and its left/right window,
        # so calculate that immutable catalog once, then retain only pivots
        # whose full predicate and confirmation remain inside each candidate
        # window.  This is exactly the prior per-window result without
        # rebuilding an identical snapshot for every allowed duration.
        pivot_highs, pivot_lows = _confirmed_pivot_catalog(
            instrument_id,
            as_of,
            bars,
            policy.pivot_left_sessions,
            policy.pivot_right_sessions,
        )
        for duration in range(policy.base_duration_min_sessions, maximum + 1):
            candidate = bars[-duration:]
            if any(item.end_time > as_of or item.provenance.received_at > as_of for item in candidate):
                continue
            start = len(bars) - duration
            end = len(bars)
            # `_pivots` requires its symmetric left window to be present;
            # confirmation uses the governed right window.  These are the
            # same candidate-local boundary conditions formerly enforced by
            # `_confirmed_pivots(candidate, ...)`.
            def within_candidate(index: int) -> bool:
                return (
                    index - policy.pivot_left_sessions >= start
                    and index + policy.pivot_left_sessions < end
                    and index + policy.pivot_right_sessions < end
                )

            highs = tuple(value for index, value in pivot_highs if within_candidate(index))
            lows = tuple(value for index, value in pivot_lows if within_candidate(index))
            if len(highs) < 2 or len(lows) < 2 or lows[-1].price < lows[-2].price:
                continue
            top = max(highs, key=lambda item: (item.price, item.session))
            if candidate[-1].close > top.price:
                continue
            values.append(GovernedPreBreakoutBaseWindow(candidate[0].end_time, candidate[-1].end_time, duration, highs, lows, top.price, top.session))
        return tuple(values)

    @staticmethod
    def _structural_empty(instrument_id, as_of, status, blockers, *, bars=(), valid_window_count=0, selected_base=None,
                          resistance=None, trigger=None, support_pivot=None, structural_support=None, support_breached=None,
                          tick_resolution_status=None, tick_size=None, tick_record_id=None, support_grid_aligned=None,
                          final_stop=None, target=None, target_grid_aligned=None, risk=None, reward=None, actual_rr=None,
                          rr_pass=None, policy_id=None, policy_version=None, policy_fingerprint=None, selection_id=None,
                          selection_fingerprint=None, breakout_confirmation_trigger=None, breakout_trigger_role=None,
                          entry_reference_price=None, entry_reference_session=None, entry_reference_geometry_status=None,
                          maximum_acceptable_entry_price=None, maximum_executable_entry_price=None,
                          entry_reference_risk=None, entry_reference_reward=None, entry_reference_rr=None,
                          entry_reference_rr_pass=None, actual_execution_price=None, actual_execution_status=None,
                          entry_economics_status=None, policy_semantic_conflict=None):
        return GovernedPreBreakoutStructuralResult(
            instrument_id, as_of, bars[-1].end_time if bars else None, status, policy_id, policy_version,
            policy_fingerprint, selection_id, selection_fingerprint, len(bars), valid_window_count, selected_base,
            resistance, trigger, support_pivot, structural_support, support_breached, tick_resolution_status, tick_size,
            tick_record_id, support_grid_aligned, final_stop, target, target_grid_aligned, risk, reward, actual_rr,
            rr_pass, tuple(sorted(set(blockers))), breakout_confirmation_trigger, breakout_trigger_role,
            entry_reference_price, entry_reference_session, entry_reference_geometry_status,
            maximum_acceptable_entry_price, maximum_executable_entry_price, entry_reference_risk,
            entry_reference_reward, entry_reference_rr, entry_reference_rr_pass, actual_execution_price,
            actual_execution_status, entry_economics_status, policy_semantic_conflict,
        )

    def _atr_values(self, instrument_id, as_of, bars, reference, period) -> tuple[tuple[datetime, Decimal], ...]:
        # The governed contraction rule consumes exactly the latest ATR and
        # five immediately preceding values.  Evaluating older prefixes cannot
        # affect that result, so avoid reconstructing them during a bounded
        # current scan while preserving the same six canonical ATR outputs.
        values: list[tuple[datetime, Decimal]] = []
        for end in range(max(period + 1, len(bars) - 5), len(bars) + 1):
            subset = bars[:end]
            result = self._technical.atr(_snapshot(instrument_id, as_of, subset), instrument_id=instrument_id, strategy_version=reference, evaluated_at=as_of, period=period)
            if result.status is AnalysisStatus.VALID and result.value is not None:
                values.append((subset[-1].end_time, Decimal(str(result.value))))
        return tuple(values)

    def _unavailable(self, instrument_id, as_of, blocker):
        return GovernedPreBreakoutResolvedInputs(
            instrument_id=instrument_id,
            evaluation_as_of=as_of,
            evaluation_session=None,
            status=PreBreakoutResolvedInputStatus.GOVERNANCE_UNAVAILABLE,
            policy_id=None,
            policy_version=None,
            policy_fingerprint=None,
            selection_id=None,
            selection_fingerprint=None,
            canonical_session_count=0,
            latest_close=None,
            bbw_percentile=None,
            bbw_pass=None,
            current_atr14=None,
            previous_5_atr14=(),
            previous_5_atr14_mean=None,
            atr_contraction_pass=None,
            atr_observation_session=None,
            rsi14=None,
            rsi_pass=None,
            official_delivery_pct=None,
            delivery_pass=None,
            high_252=None,
            high_252_session_count=0,
            distance_below_high_pct=None,
            distance_from_high_pass=None,
            current_volume=None,
            sma20_volume=None,
            volume_dry_up_status="UNRESOLVED_POLICY_SEMANTICS",
            prior_20_volumes=(),
            prior_20_volume_mean=None,
            volume_threshold_ratio=None,
            volume_threshold_value=None,
            volume_operator=None,
            volume_dry_up_pass=None,
            volume_evaluation_session=None,
            unresolved_fields=(),
            blockers=(blocker,),
        )

    def _result(self, selected, instrument_id, as_of, bars, atr_values, extra_blockers, *, bbw=None, rsi=None, delivery=None):
        policy = selected.policy; blockers = list(extra_blockers); latest = bars[-1] if bars else None
        if len(atr_values) < 6: current_atr = previous = mean = atr_pass = atr_session = None; blockers.append("ATR_CONTRACTION_UNAVAILABLE")
        else:
            current_atr = atr_values[-1][1]; previous = tuple(value for _, value in atr_values[-6:-1]); mean = sum(previous, Decimal("0")) / Decimal(5); atr_pass = current_atr < mean; atr_session = atr_values[-1][0]
        if len(bars) < policy.high_lookback_sessions:
            high = distance = high_pass = None; high_count = len(bars); blockers.append("HIGH_252_UNAVAILABLE")
        else:
            window = bars[-policy.high_lookback_sessions:]; high = max(item.high for item in window); high_count = len(window); distance = (high - latest.close) / high * Decimal("100") if high > 0 else None; high_pass = None if distance is None else policy.min_distance_below_high_pct <= distance <= policy.max_distance_below_high_pct
        bbw_value = _value(bbw); rsi_value = _value(rsi); delivery_value = delivery.delivery_percentage if delivery is not None else None
        if bbw_value is None: blockers.append("BBW_PERCENTILE_UNAVAILABLE")
        if rsi_value is None: blockers.append("RSI14_UNAVAILABLE")
        if delivery_value is None: blockers.append("OFFICIAL_DELIVERY_UNAVAILABLE")
        volume = _volume_evidence(policy, bars)
        if volume.status == "UNAVAILABLE":
            blockers.append("VOLUME_DRY_UP_UNAVAILABLE")
        status = PreBreakoutResolvedInputStatus.DATA_UNAVAILABLE if blockers else PreBreakoutResolvedInputStatus.PARTIAL_POLICY_BLOCKED
        return GovernedPreBreakoutResolvedInputs(
            instrument_id, as_of, latest.end_time if latest else None, status,
            policy.policy_id, policy.version, selected.policy_fingerprint,
            selected.selection.selection_id, selected.selection_fingerprint,
            len(bars), latest.close if latest else None, bbw_value,
            None if bbw_value is None else bbw_value <= policy.bbw_percentile_threshold,
            current_atr, previous or (), mean, atr_pass, atr_session, rsi_value,
            None if rsi_value is None else policy.rsi_min <= rsi_value <= policy.rsi_max,
            delivery_value,
            None if delivery_value is None else delivery_value > policy.delivery_threshold_exclusive,
            high, high_count, distance, high_pass, latest.volume if latest else None,
            volume.sma20_volume, volume.status, volume.prior_volumes, volume.prior_mean,
            volume.threshold_ratio, volume.threshold_value, volume.operator,
            volume.passed, latest.end_time if latest else None, selected.unresolved_fields,
            tuple(sorted(set((*blockers, *selected.unresolved_fields)))),
        )


def _snapshot(instrument_id: str, as_of: datetime, bars) -> AsOfSnapshot:
    observations = tuple(
        price_bar_observation(bar).with_validation(ValidationResult(ValidationStatus.VALID, as_of))
        for bar in bars
    )
    return AsOfSnapshot(f"prebreakout-governed:{instrument_id}:{as_of.isoformat()}:{len(bars)}", as_of, as_of, "CURRENT_STORED_ONLY", observations)


def _confirmed_pivots(
    instrument_id: str,
    as_of: datetime,
    bars,
    left_sessions: int,
    right_sessions: int,
) -> tuple[tuple[GovernedPreBreakoutPivot, ...], tuple[GovernedPreBreakoutPivot, ...]]:
    """Reuse the existing strict left/right pivot helper and retain Decimal lineage."""
    highs, lows = _confirmed_pivot_catalog(instrument_id, as_of, bars, left_sessions, right_sessions)
    return tuple(value for _, value in highs), tuple(value for _, value in lows)


def _confirmed_pivot_catalog(
    instrument_id: str,
    as_of: datetime,
    bars,
    left_sessions: int,
    right_sessions: int,
) -> tuple[tuple[tuple[int, GovernedPreBreakoutPivot], ...], tuple[tuple[int, GovernedPreBreakoutPivot], ...]]:
    """Return confirmed pivots with their input-bar index for safe window filtering."""
    series = price_bar_series(_snapshot(instrument_id, as_of, bars), instrument_id)
    if series.status is not AnalysisStatus.VALID:
        return (), ()
    high_values, low_values = _pivots(series, left_sessions)
    by_id = {item.bar_id: (index, item) for index, item in enumerate(bars)}

    def lineage(values, field: str) -> tuple[tuple[int, GovernedPreBreakoutPivot], ...]:
        result: list[tuple[int, GovernedPreBreakoutPivot]] = []
        for observation, _ in values:
            index, source = by_id[observation.id]
            confirmation_index = index + right_sessions
            if confirmation_index >= len(bars):
                continue
            confirmation = bars[confirmation_index]
            if confirmation.end_time > as_of or confirmation.provenance.received_at > as_of:
                continue
            result.append((index, GovernedPreBreakoutPivot(
                source.bar_id, source.end_time, getattr(source, field), confirmation.end_time,
            )))
        return tuple(result)

    return lineage(high_values, "high"), lineage(low_values, "low")


def _value(result) -> Decimal | None:
    return Decimal(str(result.value)) if result is not None and result.status is AnalysisStatus.VALID and result.value is not None else None


@dataclass(frozen=True, slots=True)
class _VolumeEvidence:
    status: str
    prior_volumes: tuple[int, ...]
    sma20_volume: Decimal | None
    prior_mean: Decimal | None
    threshold_ratio: Decimal | None
    threshold_value: Decimal | None
    operator: str | None
    passed: bool | None


def _volume_evidence(policy, bars) -> _VolumeEvidence:
    """Apply only an already-selected volume semantic to canonical resolved bars."""
    rule = getattr(policy, "consolidation_volume_statistic", None)
    if rule is None:
        factual_volumes = tuple(bar.volume for bar in bars[-policy.volume_sma_period:] if bar.volume is not None)
        factual_mean = (
            sum((Decimal(value) for value in factual_volumes), Decimal("0")) / Decimal(policy.volume_sma_period)
            if len(factual_volumes) == policy.volume_sma_period else None
        )
        return _VolumeEvidence("UNRESOLVED_POLICY_SEMANTICS", (), factual_mean, None, None, None, None, None)
    current = bars[-1].volume if bars else None
    valid_prior = tuple(bar.volume for bar in bars[:-1] if bar.volume is not None)
    prior = valid_prior[-rule.minimum_prior_valid_observations:]
    evaluation = rule.evaluate(current_volume=current, prior_valid_volumes=prior)
    if evaluation.status is ConsolidationVolumeSemanticStatus.UNAVAILABLE:
        return _VolumeEvidence("UNAVAILABLE", prior, None, None, rule.threshold_ratio, None, rule.operator.value, None)
    return _VolumeEvidence(
        evaluation.status.value,
        prior,
        evaluation.prior_valid_session_sma,
        evaluation.prior_valid_session_sma,
        rule.threshold_ratio,
        evaluation.threshold_volume,
        rule.operator.value,
        evaluation.status is ConsolidationVolumeSemanticStatus.PASS,
    )
