"""Governance-only draft; production scanning must never consume this object."""
from __future__ import annotations
from dataclasses import dataclass, fields
from datetime import datetime
from decimal import Decimal
from enum import Enum
from app.historical.guard import manifest_fingerprint
from app.market_data.reference_data.resolver import floor_to_tick_grid

DRAFT_REQUIRES_HUMAN_APPROVAL = "DRAFT_REQUIRES_HUMAN_APPROVAL"
PREBREAKOUT_APPROVED_V1_UNRESOLVED_FIELDS = (
    "CONSOLIDATION_VOLUME_STATISTIC",
    "BASE_WINDOW_SELECTION_RULE",
    "SUPPORT_PIVOT_SELECTION_RULE",
    "NSE_TICK_SIZE_SOURCE",
)
PREBREAKOUT_APPROVED_V1_1_UNRESOLVED_FIELDS = (
    "BASE_WINDOW_SELECTION_RULE",
    "SUPPORT_PIVOT_SELECTION_RULE",
    "NSE_TICK_SIZE_SOURCE",
)
PREBREAKOUT_APPROVED_V1_2_UNRESOLVED_FIELDS: tuple[str, ...] = ()
class PreBreakoutPolicyApprovalDecision(str, Enum): APPROVE="APPROVE"; REJECT="REJECT"
class PreBreakoutPolicySelectionContext(str, Enum): CURRENT_STORED_SCAN="CURRENT_STORED_SCAN"


class ConsolidationVolumeStatistic(str, Enum):
    EVALUATION_SESSION_VOLUME = "EVALUATION_SESSION_VOLUME"
    BASE_WINDOW_AVERAGE_VOLUME = "BASE_WINDOW_AVERAGE_VOLUME"


class ConsolidationVolumeComparisonReference(str, Enum):
    PRIOR_VALID_SESSION_SMA = "PRIOR_VALID_SESSION_SMA"


class ConsolidationVolumeComparisonOperator(str, Enum):
    STRICT_LESS_THAN = "STRICT_LESS_THAN"
    LESS_THAN_OR_EQUAL = "LESS_THAN_OR_EQUAL"


class ConsolidationVolumeSemanticStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    UNAVAILABLE = "UNAVAILABLE"


class BaseWindowCandidateKind(str, Enum):
    SUFFIX_ENDING_AT_EVALUATION = "SUFFIX_ENDING_AT_EVALUATION"


class BaseWindowFailureStatus(str, Enum):
    NO_VALID_WINDOW = "NO_VALID_WINDOW"


class BaseTopSource(str, Enum):
    MAXIMUM_CONFIRMED_PIVOT_HIGH = "MAXIMUM_CONFIRMED_PIVOT_HIGH"


class EqualBaseTopLineage(str, Enum):
    MOST_RECENT_EQUAL_MAXIMUM_PIVOT = "MOST_RECENT_EQUAL_MAXIMUM_PIVOT"


class BaseWindowSelectionMethod(str, Enum):
    MAX_BASE_TOP_THEN_SHORTEST = "MAX_BASE_TOP_THEN_SHORTEST"


class SupportPivotMethod(str, Enum):
    MOST_RECENT_CONFIRMED_PIVOT_LOW_IN_SELECTED_BASE = "MOST_RECENT_CONFIRMED_PIVOT_LOW_IN_SELECTED_BASE"


class SupportBreachComparison(str, Enum):
    STRICT_CLOSE_LESS_THAN_SUPPORT = "STRICT_CLOSE_LESS_THAN_SUPPORT"


class TickSourceMethod(str, Enum):
    AUTHORITATIVE_REFERENCE_DATA_WITH_PIT_PRECEDENCE = "AUTHORITATIVE_REFERENCE_DATA_WITH_PIT_PRECEDENCE"


class TickGridMethod(str, Enum):
    EXACT_DECIMAL_MODULO = "EXACT_DECIMAL_MODULO"


class StructuralStopMethod(str, Enum):
    SUPPORT_MINUS_ONE_GOVERNED_TICK = "SUPPORT_MINUS_ONE_GOVERNED_TICK"


class TargetSupportBindingStatus(str, Enum):
    CURRENT_STRUCTURAL_SUPPORT = "CURRENT_STRUCTURAL_SUPPORT"


class EntryReferenceMethod(str, Enum):
    EVALUATION_SESSION_CANONICAL_CLOSE = "EVALUATION_SESSION_CANONICAL_CLOSE"


class MaximumAcceptableEntryMethod(str, Enum):
    MIN_RR_ANALYTIC_CEILING = "MIN_RR_ANALYTIC_CEILING"


class ExecutableEntryGridMethod(str, Enum):
    CONSERVATIVE_TICK_FLOOR = "CONSERVATIVE_TICK_FLOOR"


class ActualExecutionPriceMethod(str, Enum):
    LATER_OBSERVED_REVALIDATED_PRICE = "LATER_OBSERVED_REVALIDATED_PRICE"


class BreakoutTriggerRole(str, Enum):
    CONFIRMATION_NOT_INITIAL_ENTRY = "CONFIRMATION_NOT_INITIAL_ENTRY"


class PreBreakoutRiskRewardBasis(str, Enum):
    GROSS_STRUCTURAL_PRICE_RR = "GROSS_STRUCTURAL_PRICE_RR"

def _aware(value: datetime, code: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None: raise ValueError(code)
def _human(value: str, code: str) -> None:
    if not value.startswith("human:") or len(value) <= 6: raise ValueError(code)
def prebreakout_policy_approval_fingerprint(**value) -> str: return manifest_fingerprint(**value)
def prebreakout_policy_selection_fingerprint(**value) -> str: return manifest_fingerprint(**value)


@dataclass(frozen=True, slots=True)
class ConsolidationVolumeStatisticRule:
    """Typed successor-draft semantics only; this is not a scanner gate."""

    statistic: ConsolidationVolumeStatistic = ConsolidationVolumeStatistic.EVALUATION_SESSION_VOLUME
    comparison_reference: ConsolidationVolumeComparisonReference = ConsolidationVolumeComparisonReference.PRIOR_VALID_SESSION_SMA
    reference_period: int = 20
    include_current_in_reference: bool = False
    threshold_ratio: Decimal = Decimal("0.50")
    operator: ConsolidationVolumeComparisonOperator = ConsolidationVolumeComparisonOperator.STRICT_LESS_THAN
    minimum_prior_valid_observations: int = 20

    def __post_init__(self) -> None:
        if self.reference_period < 1 or self.minimum_prior_valid_observations < 1:
            raise ValueError("PREBREAKOUT_VOLUME_STATISTIC_PERIOD_INVALID")
        if self.threshold_ratio < Decimal("0"):
            raise ValueError("PREBREAKOUT_VOLUME_STATISTIC_RATIO_INVALID")

    @property
    def fingerprint(self) -> str:
        return manifest_fingerprint(
            statistic=self.statistic.value,
            comparison_reference=self.comparison_reference.value,
            reference_period=self.reference_period,
            include_current_in_reference=self.include_current_in_reference,
            threshold_ratio=self.threshold_ratio,
            operator=self.operator.value,
            minimum_prior_valid_observations=self.minimum_prior_valid_observations,
        )

    def evaluate(
        self,
        *,
        current_volume: int | None,
        prior_valid_volumes: tuple[int, ...],
    ) -> "ConsolidationVolumeSemanticEvaluation":
        """Evaluate only this proposed numeric definition, never a base or setup."""
        if (
            current_volume is None
            or current_volume < 0
            or len(prior_valid_volumes) != self.minimum_prior_valid_observations
            or any(value < 0 for value in prior_valid_volumes)
        ):
            return ConsolidationVolumeSemanticEvaluation(
                ConsolidationVolumeSemanticStatus.UNAVAILABLE, None, None,
            )
        mean = sum((Decimal(value) for value in prior_valid_volumes), Decimal("0")) / Decimal(self.reference_period)
        threshold = self.threshold_ratio * mean
        passed = (
            Decimal(current_volume) < threshold
            if self.operator is ConsolidationVolumeComparisonOperator.STRICT_LESS_THAN
            else Decimal(current_volume) <= threshold
        )
        return ConsolidationVolumeSemanticEvaluation(
            ConsolidationVolumeSemanticStatus.PASS if passed else ConsolidationVolumeSemanticStatus.FAIL,
            mean,
            threshold,
        )


@dataclass(frozen=True, slots=True)
class ConsolidationVolumeSemanticEvaluation:
    status: ConsolidationVolumeSemanticStatus
    prior_valid_session_sma: Decimal | None
    threshold_volume: Decimal | None


@dataclass(frozen=True, slots=True)
class BaseWindowValidityRule:
    """The approved structural eligibility boundary, independent of indicators."""

    candidate_kind: BaseWindowCandidateKind = BaseWindowCandidateKind.SUFFIX_ENDING_AT_EVALUATION
    minimum_canonical_sessions: int = 20
    maximum_canonical_sessions: int = 60
    require_consecutive_eligible_canonical_sessions: bool = True
    require_evaluation_session_included: bool = True
    require_window_end_at_evaluation: bool = True
    minimum_confirmed_pivot_highs: int = 2
    minimum_confirmed_pivot_lows: int = 2
    require_latest_two_pivot_lows_non_decreasing: bool = True
    require_evaluation_close_at_or_below_base_top: bool = True
    no_valid_window_status: BaseWindowFailureStatus = BaseWindowFailureStatus.NO_VALID_WINDOW
    maximum_range_pct: Decimal | None = None

    def __post_init__(self) -> None:
        if self.minimum_canonical_sessions < 1 or self.maximum_canonical_sessions < self.minimum_canonical_sessions:
            raise ValueError("PREBREAKOUT_BASE_WINDOW_DURATION_INVALID")
        if self.minimum_confirmed_pivot_highs < 1 or self.minimum_confirmed_pivot_lows < 1:
            raise ValueError("PREBREAKOUT_BASE_WINDOW_PIVOT_MINIMUM_INVALID")
        if self.maximum_range_pct is not None:
            raise ValueError("PREBREAKOUT_BASE_WINDOW_RANGE_CAP_UNAPPROVED")


@dataclass(frozen=True, slots=True)
class BaseTopDefinitionRule:
    source: BaseTopSource = BaseTopSource.MAXIMUM_CONFIRMED_PIVOT_HIGH
    equal_maximum_lineage: EqualBaseTopLineage = EqualBaseTopLineage.MOST_RECENT_EQUAL_MAXIMUM_PIVOT
    pivot_must_be_inside_candidate_window: bool = True
    raw_session_high_allowed: bool = False


@dataclass(frozen=True, slots=True)
class BaseWindowSelectionRule:
    method: BaseWindowSelectionMethod = BaseWindowSelectionMethod.MAX_BASE_TOP_THEN_SHORTEST
    construct_all_valid_suffix_windows: bool = True
    retain_exact_maximum_base_top: bool = True
    select_shortest_retained_window: bool = True
    allow_reward_risk_optimization: bool = False
    allow_stop_optimization: bool = False
    allow_target_optimization: bool = False


@dataclass(frozen=True, slots=True)
class SupportPivotSelectionRule:
    method: SupportPivotMethod = SupportPivotMethod.MOST_RECENT_CONFIRMED_PIVOT_LOW_IN_SELECTED_BASE
    support_price_field: str = "LOW"
    pivot_must_be_inside_selected_base: bool = True
    unconfirmed_pivot_allowed: bool = False
    raw_session_low_fallback_allowed: bool = False
    allow_stop_or_reward_risk_selection: bool = False


@dataclass(frozen=True, slots=True)
class SupportBreachRule:
    comparison: SupportBreachComparison = SupportBreachComparison.STRICT_CLOSE_LESS_THAN_SUPPORT
    equality_is_breach: bool = False
    failure_status: str = "BASE_STRUCTURE_BROKEN"
    applies_to_setup_eligibility_only: bool = True


@dataclass(frozen=True, slots=True)
class TickSourceRule:
    method: TickSourceMethod = TickSourceMethod.AUTHORITATIVE_REFERENCE_DATA_WITH_PIT_PRECEDENCE
    official_nse_first: bool = True
    approved_licensed_exact_identity_nse_cash_fallback: bool = True
    licensed_fallback_requires_explicit_approval: bool = True
    unavailable_status: str = "TICK_SIZE_UNAVAILABLE_FOR_AS_OF"
    conflict_status: str = "REFERENCE_DATA_CONFLICT"
    inferred_tick_fallback_allowed: bool = False
    decimal_arithmetic_required: bool = True


@dataclass(frozen=True, slots=True)
class TickGridRule:
    method: TickGridMethod = TickGridMethod.EXACT_DECIMAL_MODULO
    required_remainder: Decimal = Decimal("0")
    epsilon_allowed: bool = False
    rounding_repair_allowed: bool = False
    nearest_grid_repair_allowed: bool = False
    floor_or_ceil_repair_allowed: bool = False
    misalignment_status: str = "TICK_GRID_ALIGNMENT_ERROR"


@dataclass(frozen=True, slots=True)
class StructuralStopRule:
    method: StructuralStopMethod = StructuralStopMethod.SUPPORT_MINUS_ONE_GOVERNED_TICK
    structural_invalidation_source: str = "CURRENT_STRUCTURAL_SUPPORT"
    valid_tick_required: bool = True
    support_grid_aligned_required: bool = True
    derived_stop_grid_aligned_required: bool = True
    percent_or_atr_buffer_allowed: bool = False
    forced_percent_range_allowed: bool = False


@dataclass(frozen=True, slots=True)
class ResistanceTriggerRule:
    resistance_source: str = "SELECTED_GOVERNED_BASE_TOP"
    trigger_source: str = "RESISTANCE"
    trigger_buffer: Decimal = Decimal("0")


@dataclass(frozen=True, slots=True)
class TargetSupportBindingRule:
    """Approved measured-move target semantics; materialization remains future work."""

    status: TargetSupportBindingStatus = TargetSupportBindingStatus.CURRENT_STRUCTURAL_SUPPORT
    target_support_source: str = "CURRENT_STRUCTURAL_SUPPORT"
    base_height_formula: str = "SELECTED_BASE_TOP_MINUS_CURRENT_STRUCTURAL_SUPPORT"
    target_formula: str = "SELECTED_BASE_TOP_PLUS_(SELECTED_BASE_TOP_MINUS_CURRENT_STRUCTURAL_SUPPORT)"
    current_structural_support_is_bound: bool = True
    target_only_support_definition_allowed: bool = False
    older_or_deeper_support_fallback_allowed: bool = False
    selected_base_top_required: bool = True
    current_structural_support_required: bool = True
    selected_base_top_must_exceed_support: bool = True
    unavailable_geometry_status: str = "TARGET_GEOMETRY_UNAVAILABLE"
    invalid_geometry_status: str = "INVALID_TARGET_GEOMETRY"
    reward_formula: str = "TARGET_MINUS_TRIGGER"
    risk_formula: str = "TRIGGER_MINUS_FINAL_STOP"
    reward_risk_minimum: Decimal = Decimal("3")
    reward_risk_requires_positive_risk_and_reward: bool = True
    target_may_be_moved_to_manufacture_reward_risk: bool = False


@dataclass(frozen=True, slots=True)
class MultiStageEntryRule:
    """Approved V1.3 entry semantics; this remains policy data, not execution."""

    entry_reference_method: EntryReferenceMethod = EntryReferenceMethod.EVALUATION_SESSION_CANONICAL_CLOSE
    entry_reference_is_factual_not_fill: bool = True
    entry_reference_is_not_order_price: bool = True
    maximum_acceptable_entry_method: MaximumAcceptableEntryMethod = MaximumAcceptableEntryMethod.MIN_RR_ANALYTIC_CEILING
    maximum_acceptable_entry_formula: str = "(2*TRIGGER_PLUS_2*SUPPORT_MINUS_3*TICK)/4"
    maximum_acceptable_entry_is_economic_ceiling_only: bool = True
    maximum_acceptable_entry_is_not_synthetic_entry: bool = True
    executable_entry_grid_method: ExecutableEntryGridMethod = ExecutableEntryGridMethod.CONSERVATIVE_TICK_FLOOR
    exact_decimal_arithmetic_required: bool = True
    upward_rounding_allowed: bool = False
    nearest_tick_rounding_allowed: bool = False
    preserve_aligned_ceiling_exactly: bool = True
    maximum_executable_entry_is_not_order_price: bool = True
    maximum_executable_entry_is_not_assumed_fill: bool = True
    require_executable_entry_above_final_stop: bool = True
    require_executable_entry_below_trigger: bool = True
    entry_reference_must_not_exceed_executable_ceiling: bool = True
    entry_reference_must_be_above_final_stop: bool = True
    entry_reference_must_be_below_trigger: bool = True
    reference_risk_formula: str = "ENTRY_REFERENCE_PRICE_MINUS_FINAL_STOP"
    reference_reward_formula: str = "TARGET_MINUS_ENTRY_REFERENCE_PRICE"
    reference_reward_risk_minimum: Decimal = Decimal("3")
    reward_risk_basis: PreBreakoutRiskRewardBasis = PreBreakoutRiskRewardBasis.GROSS_STRUCTURAL_PRICE_RR
    transaction_friction_handling: str = "INDEPENDENT_MANDATORY_EXECUTION_GATE"
    actual_execution_price_method: ActualExecutionPriceMethod = ActualExecutionPriceMethod.LATER_OBSERVED_REVALIDATED_PRICE
    actual_execution_price_is_later_factual_value: bool = True
    actual_execution_revalidation_required: bool = True
    actual_execution_must_not_exceed_executable_ceiling: bool = True
    actual_execution_must_be_above_final_stop: bool = True
    actual_execution_must_be_below_trigger: bool = True
    actual_execution_must_satisfy_reference_minimum_rr: bool = True
    breakout_trigger_role: BreakoutTriggerRole = BreakoutTriggerRole.CONFIRMATION_NOT_INITIAL_ENTRY
    breakout_trigger_is_not_initial_entry: bool = True
    do_not_chase: bool = True
    price_too_high_status: str = "ENTRY_PRICE_TOO_HIGH"
    no_valid_entry_status: str = "NO_VALID_PRE_BREAKOUT_ENTRY_PRICE"
    trigger_entry_unavailable_status: str = "PRE_BREAKOUT_ENTRY_NOT_AVAILABLE"
    invalid_geometry_status: str = "INVALID_PRE_BREAKOUT_ENTRY_GEOMETRY"

    def maximum_acceptable_entry_price(
        self, *, trigger: Decimal, support: Decimal, tick_size: Decimal,
    ) -> Decimal:
        """Return the analytic ceiling only; it is never an implied fill."""
        _entry_decimal_inputs(trigger=trigger, support=support, tick_size=tick_size)
        return (Decimal("2") * trigger + Decimal("2") * support - Decimal("3") * tick_size) / Decimal("4")

    def maximum_executable_entry_price(
        self, *, trigger: Decimal, support: Decimal, tick_size: Decimal,
    ) -> Decimal:
        """Apply the approved exact Decimal floor without upward/nearest repair."""
        ceiling = self.maximum_acceptable_entry_price(
            trigger=trigger, support=support, tick_size=tick_size,
        )
        executable = self.conservative_tick_floor(ceiling=ceiling, tick_size=tick_size)
        final_stop = support - tick_size
        if executable <= final_stop:
            raise ValueError(self.no_valid_entry_status)
        if executable >= trigger:
            raise ValueError(self.trigger_entry_unavailable_status)
        return executable

    def conservative_tick_floor(self, *, ceiling: Decimal, tick_size: Decimal) -> Decimal:
        """Floor an economic ceiling to the greatest valid exact tick-grid price."""
        return floor_to_tick_grid(ceiling, tick_size)

    def reference_reward_risk(
        self, *, entry_reference_price: Decimal, trigger: Decimal, support: Decimal,
        tick_size: Decimal, target: Decimal,
    ) -> Decimal:
        """Validate factual setup economics without treating it as an execution."""
        final_stop = support - tick_size
        ceiling = self.maximum_executable_entry_price(
            trigger=trigger, support=support, tick_size=tick_size,
        )
        if not isinstance(entry_reference_price, Decimal) or not entry_reference_price.is_finite():
            raise ValueError(self.invalid_geometry_status)
        if entry_reference_price <= final_stop:
            raise ValueError(self.invalid_geometry_status)
        if entry_reference_price >= trigger:
            raise ValueError(self.trigger_entry_unavailable_status)
        if entry_reference_price > ceiling:
            raise ValueError(self.price_too_high_status)
        if not isinstance(target, Decimal) or not target.is_finite() or target <= entry_reference_price:
            raise ValueError(self.invalid_geometry_status)
        reward_risk = (target - entry_reference_price) / (entry_reference_price - final_stop)
        if reward_risk < self.reference_reward_risk_minimum:
            raise ValueError(self.no_valid_entry_status)
        return reward_risk

    def validate_actual_execution_price(
        self, *, actual_execution_price: Decimal, trigger: Decimal, support: Decimal,
        tick_size: Decimal, target: Decimal,
    ) -> Decimal:
        """Pure later-boundary validation; it neither creates nor assumes a fill."""
        return self.reference_reward_risk(
            entry_reference_price=actual_execution_price,
            trigger=trigger,
            support=support,
            tick_size=tick_size,
            target=target,
        )


def _entry_decimal_inputs(*, trigger: Decimal, support: Decimal, tick_size: Decimal) -> None:
    if not all(isinstance(value, Decimal) and value.is_finite() for value in (trigger, support, tick_size)):
        raise ValueError("PREBREAKOUT_ENTRY_DECIMAL_REQUIRED")
    if tick_size <= Decimal("0") or trigger <= support:
        raise ValueError("INVALID_PRE_BREAKOUT_ENTRY_GEOMETRY")
    if trigger % tick_size != Decimal("0") or support % tick_size != Decimal("0"):
        raise ValueError("TICK_GRID_ALIGNMENT_ERROR")

@dataclass(frozen=True, slots=True)
class PreBreakoutPolicyApproval:
    approval_id:str; policy_id:str; policy_version:str; draft_policy_fingerprint:str; approved_policy_fingerprint:str; approved_values_fingerprint:str; reviewer_id:str; reviewed_at:datetime; decision:PreBreakoutPolicyApprovalDecision; created_at:datetime; warnings:tuple[str,...]; fingerprint:str
    def __post_init__(self):
        if not all((self.approval_id,self.policy_id,self.policy_version,self.draft_policy_fingerprint,self.approved_policy_fingerprint,self.approved_values_fingerprint,self.fingerprint)): raise ValueError("PREBREAKOUT_POLICY_APPROVAL_REQUIRED_FIELD")
        _human(self.reviewer_id,"HUMAN_REVIEWER_REQUIRED"); _aware(self.reviewed_at,"PREBREAKOUT_POLICY_APPROVAL_REVIEWED_AT_NAIVE"); _aware(self.created_at,"PREBREAKOUT_POLICY_APPROVAL_CREATED_AT_NAIVE")
        if self.created_at < self.reviewed_at: raise ValueError("PREBREAKOUT_POLICY_APPROVAL_CHRONOLOGY_INVALID")
        expected=prebreakout_policy_approval_fingerprint(approval_id=self.approval_id,policy_id=self.policy_id,policy_version=self.policy_version,draft_policy_fingerprint=self.draft_policy_fingerprint,approved_policy_fingerprint=self.approved_policy_fingerprint,approved_values_fingerprint=self.approved_values_fingerprint,reviewer_id=self.reviewer_id,reviewed_at=self.reviewed_at.isoformat(),decision=self.decision.value,created_at=self.created_at.isoformat(),warnings=self.warnings)
        if self.fingerprint != expected: raise ValueError("PREBREAKOUT_POLICY_APPROVAL_FINGERPRINT_MISMATCH")

@dataclass(frozen=True, slots=True)
class PreBreakoutPolicySelection:
    selection_id:str; approval_id:str; policy_id:str; policy_version:str; policy_fingerprint:str; selection_context:PreBreakoutPolicySelectionContext; selected_by:str; selected_at:datetime; effective_from:datetime; warnings:tuple[str,...]; fingerprint:str
    def __post_init__(self):
        if not all((self.selection_id,self.approval_id,self.policy_id,self.policy_version,self.policy_fingerprint,self.fingerprint)): raise ValueError("PREBREAKOUT_POLICY_SELECTION_REQUIRED_FIELD")
        _human(self.selected_by,"HUMAN_REVIEWER_REQUIRED"); _aware(self.selected_at,"PREBREAKOUT_POLICY_SELECTION_SELECTED_AT_NAIVE"); _aware(self.effective_from,"PREBREAKOUT_POLICY_SELECTION_EFFECTIVE_AT_NAIVE")
        if self.effective_from < self.selected_at: raise ValueError("PREBREAKOUT_POLICY_SELECTION_CHRONOLOGY_INVALID")
        expected=prebreakout_policy_selection_fingerprint(selection_id=self.selection_id,approval_id=self.approval_id,policy_id=self.policy_id,policy_version=self.policy_version,policy_fingerprint=self.policy_fingerprint,selection_context=self.selection_context.value,selected_by=self.selected_by,selected_at=self.selected_at.isoformat(),effective_from=self.effective_from.isoformat(),warnings=self.warnings)
        if self.fingerprint != expected: raise ValueError("PREBREAKOUT_POLICY_SELECTION_FINGERPRINT_MISMATCH")

@dataclass(frozen=True, slots=True)
class PreBreakoutPolicyDraft:
    policy_id: str = "pre-breakout-policy-v1-draft"
    version: str = "v1-draft"
    status: str = DRAFT_REQUIRES_HUMAN_APPROVAL
    bbw_percentile_threshold: Decimal = Decimal("10")
    bbw_history_sessions: int = 120
    volume_sma_period: int = 20
    dry_up_ratio_threshold: Decimal = Decimal("0.50")
    delivery_threshold_exclusive: Decimal = Decimal("60")
    high_lookback_sessions: int = 252
    min_distance_below_high_pct: Decimal = Decimal("3")
    max_distance_below_high_pct: Decimal = Decimal("6")
    rsi_period: int = 14
    rsi_min: Decimal = Decimal("55")
    rsi_max: Decimal = Decimal("65")
    minimum_rr: Decimal = Decimal("3")
    undefined_fields: tuple[str, ...] = (
        "ATR_CONTRACTION_RULE", "ATR_COMPARISON_WINDOW", "CONSOLIDATION_VOLUME_WINDOW",
        "BASE_DURATION_AND_RANGE", "PIVOT_CONFIRMATION", "RESISTANCE_DEFINITION",
        "BREAKOUT_TRIGGER_BUFFER", "STRUCTURAL_STOP_BUFFER", "TARGET_METHOD",
    )

    def assert_not_active(self) -> None:
        if self.status != DRAFT_REQUIRES_HUMAN_APPROVAL:
            raise ValueError("PRE_BREAKOUT_POLICY_DRAFT_STATUS_INVALID")


def prebreakout_policy_draft_fingerprint(value: PreBreakoutPolicyDraft) -> str:
    """Fingerprint every immutable draft field; no mutable scan state is involved."""
    return manifest_fingerprint(**{
        field.name: getattr(value, field.name)
        for field in fields(value)
    })


@dataclass(frozen=True, slots=True)
class PreBreakoutApprovedPolicy:
    """Exact Policy V1 values reconstructed from a frozen draft and approval lineage.

    This is deliberately a governed read model, not an active strategy or scanner
    configuration.  The unresolved fields remain explicit instead of receiving
    implicit trading defaults.
    """

    policy_id: str
    version: str
    bbw_percentile_threshold: Decimal
    bbw_history_sessions: int
    volume_sma_period: int
    dry_up_ratio_threshold: Decimal
    delivery_threshold_exclusive: Decimal
    high_lookback_sessions: int
    min_distance_below_high_pct: Decimal
    max_distance_below_high_pct: Decimal
    rsi_period: int
    rsi_min: Decimal
    rsi_max: Decimal
    minimum_rr: Decimal
    atr_period: int = 14
    atr_contraction_rule: str = "CURRENT_ATR14_LT_MEAN_PREVIOUS_5_VALID_ATR14_OBSERVATIONS"
    base_duration_min_sessions: int = 20
    base_duration_max_sessions: int = 60
    pivot_left_sessions: int = 3
    pivot_right_sessions: int = 3
    resistance_rule: str = "HIGHEST_CONFIRMED_PIVOT_HIGH_OR_GOVERNED_BASE_TOP"
    breakout_trigger_rule: str = "RESISTANCE"
    breakout_trigger_buffer: Decimal = Decimal("0")
    stop_rule: str = "STRUCTURAL_INVALIDATION_ONLY"
    target_rule: str = "BASE_HEIGHT_MEASURED_MOVE"
    reward_risk_below_minimum_rejected: bool = True
    unresolved_fields: tuple[str, ...] = PREBREAKOUT_APPROVED_V1_UNRESOLVED_FIELDS

    @classmethod
    def from_draft(cls, value: PreBreakoutPolicyDraft | "PreBreakoutVolumeResolvedSuccessorDraft" | "PreBreakoutStructuralSuccessorDraft" | "PreBreakoutMultiStageEntrySuccessorDraft") -> "PreBreakoutApprovedPolicy":
        if isinstance(value, PreBreakoutMultiStageEntrySuccessorDraft):
            value.assert_not_active()
            value.assert_exact_v1_3_multi_stage_entry_semantics()
            return value
        if isinstance(value, PreBreakoutStructuralSuccessorDraft):
            value.assert_not_active()
            value.assert_exact_v1_2_structural_semantics()
            return value
        if isinstance(value, PreBreakoutVolumeResolvedSuccessorDraft):
            value.assert_not_active()
            value.assert_exact_v1_1_volume_semantic()
            return value
        value.assert_not_active()
        return cls(
            policy_id=value.policy_id,
            version=value.version,
            bbw_percentile_threshold=value.bbw_percentile_threshold,
            bbw_history_sessions=value.bbw_history_sessions,
            volume_sma_period=value.volume_sma_period,
            dry_up_ratio_threshold=value.dry_up_ratio_threshold,
            delivery_threshold_exclusive=value.delivery_threshold_exclusive,
            high_lookback_sessions=value.high_lookback_sessions,
            min_distance_below_high_pct=value.min_distance_below_high_pct,
            max_distance_below_high_pct=value.max_distance_below_high_pct,
            rsi_period=value.rsi_period,
            rsi_min=value.rsi_min,
            rsi_max=value.rsi_max,
            minimum_rr=value.minimum_rr,
        )

    @property
    def values_fingerprint(self) -> str:
        return manifest_fingerprint(**{
            field.name: getattr(self, field.name)
            for field in fields(self)
            if field.name not in {"policy_id", "version"}
        })

    @property
    def fingerprint(self) -> str:
        return manifest_fingerprint(
            policy_id=self.policy_id,
            version=self.version,
            approved_values_fingerprint=self.values_fingerprint,
        )


@dataclass(frozen=True, slots=True)
class PreBreakoutVolumeResolvedSuccessorDraft(PreBreakoutApprovedPolicy):
    """Immutable V1.1 successor draft resolving only the numeric volume statistic.

    It is intentionally a draft despite inheriting the already governed V1
    values.  It cannot affect a scan until a new human approval and selection
    independently validate its fingerprinted lineage.
    """

    status: str = DRAFT_REQUIRES_HUMAN_APPROVAL
    consolidation_volume_statistic: ConsolidationVolumeStatisticRule = ConsolidationVolumeStatisticRule()
    unresolved_fields: tuple[str, ...] = PREBREAKOUT_APPROVED_V1_1_UNRESOLVED_FIELDS

    def __post_init__(self) -> None:
        self.assert_not_active()

    def assert_exact_v1_1_volume_semantic(self) -> None:
        rule = self.consolidation_volume_statistic
        if (
            rule.statistic is not ConsolidationVolumeStatistic.EVALUATION_SESSION_VOLUME
            or rule.comparison_reference is not ConsolidationVolumeComparisonReference.PRIOR_VALID_SESSION_SMA
            or rule.reference_period != 20
            or rule.include_current_in_reference is not False
            or rule.threshold_ratio != Decimal("0.50")
            or rule.operator is not ConsolidationVolumeComparisonOperator.STRICT_LESS_THAN
            or rule.minimum_prior_valid_observations != 20
        ):
            raise ValueError("PREBREAKOUT_SUCCESSOR_VOLUME_SEMANTIC_INVALID")
        if self.unresolved_fields != PREBREAKOUT_APPROVED_V1_1_UNRESOLVED_FIELDS:
            raise ValueError("PREBREAKOUT_SUCCESSOR_UNRESOLVED_FIELDS_INVALID")

    def assert_not_active(self) -> None:
        if self.status != DRAFT_REQUIRES_HUMAN_APPROVAL:
            raise ValueError("PREBREAKOUT_POLICY_DRAFT_STATUS_INVALID")

    @classmethod
    def from_v1(cls, value: PreBreakoutPolicyDraft | None = None) -> "PreBreakoutVolumeResolvedSuccessorDraft":
        inherited = PreBreakoutApprovedPolicy.from_draft(value or PreBreakoutPolicyDraft())
        result = cls(
            policy_id="pre-breakout-policy-v1",
            version="v1.1-draft",
            bbw_percentile_threshold=inherited.bbw_percentile_threshold,
            bbw_history_sessions=inherited.bbw_history_sessions,
            volume_sma_period=inherited.volume_sma_period,
            dry_up_ratio_threshold=inherited.dry_up_ratio_threshold,
            delivery_threshold_exclusive=inherited.delivery_threshold_exclusive,
            high_lookback_sessions=inherited.high_lookback_sessions,
            min_distance_below_high_pct=inherited.min_distance_below_high_pct,
            max_distance_below_high_pct=inherited.max_distance_below_high_pct,
            rsi_period=inherited.rsi_period,
            rsi_min=inherited.rsi_min,
            rsi_max=inherited.rsi_max,
            minimum_rr=inherited.minimum_rr,
            atr_period=inherited.atr_period,
            atr_contraction_rule=inherited.atr_contraction_rule,
            base_duration_min_sessions=inherited.base_duration_min_sessions,
            base_duration_max_sessions=inherited.base_duration_max_sessions,
            pivot_left_sessions=inherited.pivot_left_sessions,
            pivot_right_sessions=inherited.pivot_right_sessions,
            resistance_rule=inherited.resistance_rule,
            breakout_trigger_rule=inherited.breakout_trigger_rule,
            breakout_trigger_buffer=inherited.breakout_trigger_buffer,
            stop_rule=inherited.stop_rule,
            target_rule=inherited.target_rule,
            reward_risk_below_minimum_rejected=inherited.reward_risk_below_minimum_rejected,
        )
        result.assert_exact_v1_1_volume_semantic()
        return result


def prebreakout_policy_v1_1_volume_successor_draft() -> PreBreakoutVolumeResolvedSuccessorDraft:
    return PreBreakoutVolumeResolvedSuccessorDraft.from_v1()


def _structural_semantic_value(value):
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, tuple):
        return tuple(_structural_semantic_value(item) for item in value)
    if hasattr(value, "__dataclass_fields__"):
        return {
            field.name: _structural_semantic_value(getattr(value, field.name))
            for field in fields(value)
        }
    return value


@dataclass(frozen=True, slots=True)
class PreBreakoutStructuralSuccessorDraft(PreBreakoutVolumeResolvedSuccessorDraft):
    """Unselected V1.2 draft carrying approved structural semantics only.

    The existing runtime does not yet materialize any of these rules.  In
    The target's base support is explicitly bound to the same current
    structural support rule; runtime materialization remains future work.
    """

    version: str
    base_window_validity: BaseWindowValidityRule = BaseWindowValidityRule()
    base_top_definition: BaseTopDefinitionRule = BaseTopDefinitionRule()
    base_window_selection: BaseWindowSelectionRule = BaseWindowSelectionRule()
    support_pivot_selection: SupportPivotSelectionRule = SupportPivotSelectionRule()
    support_breach: SupportBreachRule = SupportBreachRule()
    tick_source: TickSourceRule = TickSourceRule()
    tick_grid: TickGridRule = TickGridRule()
    structural_stop: StructuralStopRule = StructuralStopRule()
    resistance_trigger: ResistanceTriggerRule = ResistanceTriggerRule()
    target_support_binding: TargetSupportBindingRule = TargetSupportBindingRule()
    unresolved_fields: tuple[str, ...] = PREBREAKOUT_APPROVED_V1_2_UNRESOLVED_FIELDS

    def __post_init__(self) -> None:
        self.assert_not_active()

    @property
    def values_fingerprint(self) -> str:
        return manifest_fingerprint(**{
            field.name: _structural_semantic_value(getattr(self, field.name))
            for field in fields(self)
            if field.name not in {"policy_id", "version", "status"}
        })

    @property
    def policy_fully_resolved(self) -> bool:
        return self.unresolved_fields == ()

    def assert_exact_v1_2_structural_semantics(self) -> None:
        volume = self.consolidation_volume_statistic
        if (
            volume.statistic is not ConsolidationVolumeStatistic.EVALUATION_SESSION_VOLUME
            or volume.comparison_reference is not ConsolidationVolumeComparisonReference.PRIOR_VALID_SESSION_SMA
            or volume.reference_period != 20
            or volume.include_current_in_reference is not False
            or volume.threshold_ratio != Decimal("0.50")
            or volume.operator is not ConsolidationVolumeComparisonOperator.STRICT_LESS_THAN
            or volume.minimum_prior_valid_observations != 20
        ):
            raise ValueError("PREBREAKOUT_SUCCESSOR_VOLUME_SEMANTIC_INVALID")
        validity = self.base_window_validity
        if (
            validity.candidate_kind is not BaseWindowCandidateKind.SUFFIX_ENDING_AT_EVALUATION
            or validity.minimum_canonical_sessions != 20
            or validity.maximum_canonical_sessions != 60
            or not validity.require_consecutive_eligible_canonical_sessions
            or not validity.require_evaluation_session_included
            or not validity.require_window_end_at_evaluation
            or validity.minimum_confirmed_pivot_highs != 2
            or validity.minimum_confirmed_pivot_lows != 2
            or not validity.require_latest_two_pivot_lows_non_decreasing
            or not validity.require_evaluation_close_at_or_below_base_top
            or validity.no_valid_window_status is not BaseWindowFailureStatus.NO_VALID_WINDOW
            or validity.maximum_range_pct is not None
        ):
            raise ValueError("PREBREAKOUT_BASE_WINDOW_SEMANTIC_INVALID")
        if (
            self.base_top_definition.source is not BaseTopSource.MAXIMUM_CONFIRMED_PIVOT_HIGH
            or self.base_top_definition.equal_maximum_lineage is not EqualBaseTopLineage.MOST_RECENT_EQUAL_MAXIMUM_PIVOT
            or not self.base_top_definition.pivot_must_be_inside_candidate_window
            or self.base_top_definition.raw_session_high_allowed
        ):
            raise ValueError("PREBREAKOUT_BASE_TOP_SEMANTIC_INVALID")
        selection = self.base_window_selection
        if (
            selection.method is not BaseWindowSelectionMethod.MAX_BASE_TOP_THEN_SHORTEST
            or not selection.construct_all_valid_suffix_windows
            or not selection.retain_exact_maximum_base_top
            or not selection.select_shortest_retained_window
            or selection.allow_reward_risk_optimization
            or selection.allow_stop_optimization
            or selection.allow_target_optimization
        ):
            raise ValueError("PREBREAKOUT_BASE_SELECTION_SEMANTIC_INVALID")
        support = self.support_pivot_selection
        if (
            support.method is not SupportPivotMethod.MOST_RECENT_CONFIRMED_PIVOT_LOW_IN_SELECTED_BASE
            or support.support_price_field != "LOW"
            or not support.pivot_must_be_inside_selected_base
            or support.unconfirmed_pivot_allowed
            or support.raw_session_low_fallback_allowed
            or support.allow_stop_or_reward_risk_selection
        ):
            raise ValueError("PREBREAKOUT_SUPPORT_SEMANTIC_INVALID")
        breach = self.support_breach
        if (
            breach.comparison is not SupportBreachComparison.STRICT_CLOSE_LESS_THAN_SUPPORT
            or breach.equality_is_breach
            or breach.failure_status != "BASE_STRUCTURE_BROKEN"
            or not breach.applies_to_setup_eligibility_only
        ):
            raise ValueError("PREBREAKOUT_SUPPORT_BREACH_SEMANTIC_INVALID")
        tick = self.tick_source
        if (
            tick.method is not TickSourceMethod.AUTHORITATIVE_REFERENCE_DATA_WITH_PIT_PRECEDENCE
            or not tick.official_nse_first
            or not tick.approved_licensed_exact_identity_nse_cash_fallback
            or not tick.licensed_fallback_requires_explicit_approval
            or tick.unavailable_status != "TICK_SIZE_UNAVAILABLE_FOR_AS_OF"
            or tick.conflict_status != "REFERENCE_DATA_CONFLICT"
            or tick.inferred_tick_fallback_allowed
            or not tick.decimal_arithmetic_required
        ):
            raise ValueError("PREBREAKOUT_TICK_SOURCE_SEMANTIC_INVALID")
        grid = self.tick_grid
        if (
            grid.method is not TickGridMethod.EXACT_DECIMAL_MODULO
            or grid.required_remainder != Decimal("0")
            or grid.epsilon_allowed
            or grid.rounding_repair_allowed
            or grid.nearest_grid_repair_allowed
            or grid.floor_or_ceil_repair_allowed
            or grid.misalignment_status != "TICK_GRID_ALIGNMENT_ERROR"
        ):
            raise ValueError("PREBREAKOUT_TICK_GRID_SEMANTIC_INVALID")
        stop = self.structural_stop
        if (
            stop.method is not StructuralStopMethod.SUPPORT_MINUS_ONE_GOVERNED_TICK
            or stop.structural_invalidation_source != "CURRENT_STRUCTURAL_SUPPORT"
            or not stop.valid_tick_required
            or not stop.support_grid_aligned_required
            or not stop.derived_stop_grid_aligned_required
            or stop.percent_or_atr_buffer_allowed
            or stop.forced_percent_range_allowed
        ):
            raise ValueError("PREBREAKOUT_STOP_SEMANTIC_INVALID")
        trigger = self.resistance_trigger
        if (
            trigger.resistance_source != "SELECTED_GOVERNED_BASE_TOP"
            or trigger.trigger_source != "RESISTANCE"
            or trigger.trigger_buffer != Decimal("0")
        ):
            raise ValueError("PREBREAKOUT_TRIGGER_SEMANTIC_INVALID")
        target = self.target_support_binding
        if (
            target.status is not TargetSupportBindingStatus.CURRENT_STRUCTURAL_SUPPORT
            or target.target_support_source != "CURRENT_STRUCTURAL_SUPPORT"
            or target.base_height_formula != "SELECTED_BASE_TOP_MINUS_CURRENT_STRUCTURAL_SUPPORT"
            or target.target_formula != "SELECTED_BASE_TOP_PLUS_(SELECTED_BASE_TOP_MINUS_CURRENT_STRUCTURAL_SUPPORT)"
            or not target.current_structural_support_is_bound
            or target.target_only_support_definition_allowed
            or target.older_or_deeper_support_fallback_allowed
            or not target.selected_base_top_required
            or not target.current_structural_support_required
            or not target.selected_base_top_must_exceed_support
            or target.unavailable_geometry_status != "TARGET_GEOMETRY_UNAVAILABLE"
            or target.invalid_geometry_status != "INVALID_TARGET_GEOMETRY"
            or target.reward_formula != "TARGET_MINUS_TRIGGER"
            or target.risk_formula != "TRIGGER_MINUS_FINAL_STOP"
            or target.reward_risk_minimum != Decimal("3")
            or not target.reward_risk_requires_positive_risk_and_reward
            or target.target_may_be_moved_to_manufacture_reward_risk
            or self.unresolved_fields != PREBREAKOUT_APPROVED_V1_2_UNRESOLVED_FIELDS
        ):
            raise ValueError("PREBREAKOUT_TARGET_SUPPORT_BINDING_UNRESOLVED")

    @classmethod
    def from_v1_1(cls, value: PreBreakoutVolumeResolvedSuccessorDraft | None = None) -> "PreBreakoutStructuralSuccessorDraft":
        inherited = value or prebreakout_policy_v1_1_volume_successor_draft()
        inherited.assert_exact_v1_1_volume_semantic()
        result = cls(**{
            field.name: getattr(inherited, field.name)
            for field in fields(PreBreakoutVolumeResolvedSuccessorDraft)
            if field.name not in {"version", "unresolved_fields"}
        }, version="v1.2-draft")
        result.assert_exact_v1_2_structural_semantics()
        return result


def prebreakout_policy_v1_2_structural_successor_draft() -> PreBreakoutStructuralSuccessorDraft:
    return PreBreakoutStructuralSuccessorDraft.from_v1_1()


@dataclass(frozen=True, slots=True)
class PreBreakoutMultiStageEntrySuccessorDraft(PreBreakoutStructuralSuccessorDraft):
    """Unselected V1.3 successor that separates setup entry from confirmation.

    This model deliberately does not materialize a setup, order, fill, signal, or
    trade.  The later execution boundary owns observed execution prices.
    """

    version: str
    multi_stage_entry: MultiStageEntryRule = MultiStageEntryRule()
    unresolved_fields: tuple[str, ...] = PREBREAKOUT_APPROVED_V1_2_UNRESOLVED_FIELDS

    def __post_init__(self) -> None:
        self.assert_not_active()

    def assert_exact_v1_3_multi_stage_entry_semantics(self) -> None:
        self.assert_exact_v1_2_structural_semantics()
        rule = self.multi_stage_entry
        if (
            rule.entry_reference_method is not EntryReferenceMethod.EVALUATION_SESSION_CANONICAL_CLOSE
            or not rule.entry_reference_is_factual_not_fill
            or not rule.entry_reference_is_not_order_price
            or rule.maximum_acceptable_entry_method is not MaximumAcceptableEntryMethod.MIN_RR_ANALYTIC_CEILING
            or rule.maximum_acceptable_entry_formula != "(2*TRIGGER_PLUS_2*SUPPORT_MINUS_3*TICK)/4"
            or not rule.maximum_acceptable_entry_is_economic_ceiling_only
            or not rule.maximum_acceptable_entry_is_not_synthetic_entry
            or rule.executable_entry_grid_method is not ExecutableEntryGridMethod.CONSERVATIVE_TICK_FLOOR
            or not rule.exact_decimal_arithmetic_required
            or rule.upward_rounding_allowed
            or rule.nearest_tick_rounding_allowed
            or not rule.preserve_aligned_ceiling_exactly
            or not rule.maximum_executable_entry_is_not_order_price
            or not rule.maximum_executable_entry_is_not_assumed_fill
            or not rule.require_executable_entry_above_final_stop
            or not rule.require_executable_entry_below_trigger
            or not rule.entry_reference_must_not_exceed_executable_ceiling
            or not rule.entry_reference_must_be_above_final_stop
            or not rule.entry_reference_must_be_below_trigger
            or rule.reference_risk_formula != "ENTRY_REFERENCE_PRICE_MINUS_FINAL_STOP"
            or rule.reference_reward_formula != "TARGET_MINUS_ENTRY_REFERENCE_PRICE"
            or rule.reference_reward_risk_minimum != Decimal("3")
            or rule.reward_risk_basis is not PreBreakoutRiskRewardBasis.GROSS_STRUCTURAL_PRICE_RR
            or rule.transaction_friction_handling != "INDEPENDENT_MANDATORY_EXECUTION_GATE"
            or rule.actual_execution_price_method is not ActualExecutionPriceMethod.LATER_OBSERVED_REVALIDATED_PRICE
            or not rule.actual_execution_price_is_later_factual_value
            or not rule.actual_execution_revalidation_required
            or not rule.actual_execution_must_not_exceed_executable_ceiling
            or not rule.actual_execution_must_be_above_final_stop
            or not rule.actual_execution_must_be_below_trigger
            or not rule.actual_execution_must_satisfy_reference_minimum_rr
            or rule.breakout_trigger_role is not BreakoutTriggerRole.CONFIRMATION_NOT_INITIAL_ENTRY
            or not rule.breakout_trigger_is_not_initial_entry
            or not rule.do_not_chase
            or rule.price_too_high_status != "ENTRY_PRICE_TOO_HIGH"
            or rule.no_valid_entry_status != "NO_VALID_PRE_BREAKOUT_ENTRY_PRICE"
            or rule.trigger_entry_unavailable_status != "PRE_BREAKOUT_ENTRY_NOT_AVAILABLE"
            or rule.invalid_geometry_status != "INVALID_PRE_BREAKOUT_ENTRY_GEOMETRY"
            or self.unresolved_fields != ()
        ):
            raise ValueError("PREBREAKOUT_MULTISTAGE_ENTRY_SEMANTIC_INVALID")

    @property
    def policy_semantic_conflict(self) -> bool:
        """V1.3 avoids the historical trigger-as-entry geometry conflict."""
        return False

    @classmethod
    def from_v1_2(
        cls, value: PreBreakoutStructuralSuccessorDraft | None = None,
    ) -> "PreBreakoutMultiStageEntrySuccessorDraft":
        inherited = value or prebreakout_policy_v1_2_structural_successor_draft()
        inherited.assert_exact_v1_2_structural_semantics()
        result = cls(**{
            field.name: getattr(inherited, field.name)
            for field in fields(PreBreakoutStructuralSuccessorDraft)
            if field.name not in {"version", "unresolved_fields"}
        }, version="v1.3-draft", unresolved_fields=())
        result.assert_exact_v1_3_multi_stage_entry_semantics()
        return result


def prebreakout_policy_v1_3_multi_stage_entry_successor_draft() -> PreBreakoutMultiStageEntrySuccessorDraft:
    return PreBreakoutMultiStageEntrySuccessorDraft.from_v1_2()


def prebreakout_policy_governance_drafts() -> tuple[PreBreakoutPolicyDraft | PreBreakoutVolumeResolvedSuccessorDraft | PreBreakoutStructuralSuccessorDraft | PreBreakoutMultiStageEntrySuccessorDraft, ...]:
    """Immutable drafts only; selection still governs any runtime use."""
    return (
        PreBreakoutPolicyDraft(),
        prebreakout_policy_v1_1_volume_successor_draft(),
        prebreakout_policy_v1_2_structural_successor_draft(),
        prebreakout_policy_v1_3_multi_stage_entry_successor_draft(),
    )
