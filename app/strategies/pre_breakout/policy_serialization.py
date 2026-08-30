from datetime import datetime
from decimal import Decimal
from dataclasses import fields, replace
from .policy import *
def _to(value): return {field.name:(item.value if isinstance(item,Enum) else item.isoformat() if isinstance(item,datetime) else list(item) if isinstance(item,tuple) else item) for field in fields(value) for item in (getattr(value,field.name),)}
def approval_to(value): return _to(value)
def selection_to(value): return _to(value)
def approval_from(value):
 try: data={**value,"decision":PreBreakoutPolicyApprovalDecision(value["decision"]),"reviewed_at":datetime.fromisoformat(value["reviewed_at"]),"created_at":datetime.fromisoformat(value["created_at"]),"warnings":tuple(value["warnings"])}
 except (KeyError,TypeError,ValueError) as error: raise ValueError("PREBREAKOUT_POLICY_APPROVAL_SERIALIZATION_INVALID") from error
 try: return PreBreakoutPolicyApproval(**data)
 except TypeError as error: raise ValueError("PREBREAKOUT_POLICY_APPROVAL_SERIALIZATION_INVALID") from error
def selection_from(value):
 try: data={**value,"selection_context":PreBreakoutPolicySelectionContext(value["selection_context"]),"selected_at":datetime.fromisoformat(value["selected_at"]),"effective_from":datetime.fromisoformat(value["effective_from"]),"warnings":tuple(value["warnings"])}
 except (KeyError,TypeError,ValueError) as error: raise ValueError("PREBREAKOUT_POLICY_SELECTION_SERIALIZATION_INVALID") from error
 try: return PreBreakoutPolicySelection(**data)
 except TypeError as error: raise ValueError("PREBREAKOUT_POLICY_SELECTION_SERIALIZATION_INVALID") from error


def successor_draft_to(value: PreBreakoutVolumeResolvedSuccessorDraft) -> dict[str, object]:
    """Pure canonical representation of the unselected V1.1 successor draft."""
    payload = _to(value)
    payload["consolidation_volume_statistic"] = {
        "statistic": value.consolidation_volume_statistic.statistic.value,
        "comparison_reference": value.consolidation_volume_statistic.comparison_reference.value,
        "reference_period": value.consolidation_volume_statistic.reference_period,
        "include_current_in_reference": value.consolidation_volume_statistic.include_current_in_reference,
        "threshold_ratio": str(value.consolidation_volume_statistic.threshold_ratio),
        "operator": value.consolidation_volume_statistic.operator.value,
        "minimum_prior_valid_observations": value.consolidation_volume_statistic.minimum_prior_valid_observations,
    }
    for name in (
        "bbw_percentile_threshold", "dry_up_ratio_threshold", "delivery_threshold_exclusive",
        "min_distance_below_high_pct", "max_distance_below_high_pct", "rsi_min", "rsi_max",
        "minimum_rr", "breakout_trigger_buffer",
    ):
        payload[name] = str(getattr(value, name))
    payload["fingerprint"] = value.fingerprint
    return payload


def successor_draft_from(value: dict[str, object]) -> PreBreakoutVolumeResolvedSuccessorDraft:
    try:
        rule_value = value["consolidation_volume_statistic"]
        if not isinstance(rule_value, dict):
            raise TypeError("volume rule must be an object")
        rule = ConsolidationVolumeStatisticRule(
            statistic=ConsolidationVolumeStatistic(str(rule_value["statistic"])),
            comparison_reference=ConsolidationVolumeComparisonReference(str(rule_value["comparison_reference"])),
            reference_period=int(rule_value["reference_period"]),
            include_current_in_reference=bool(rule_value["include_current_in_reference"]),
            threshold_ratio=Decimal(str(rule_value["threshold_ratio"])),
            operator=ConsolidationVolumeComparisonOperator(str(rule_value["operator"])),
            minimum_prior_valid_observations=int(rule_value["minimum_prior_valid_observations"]),
        )
        data = {**value, "consolidation_volume_statistic": rule, "unresolved_fields": tuple(value["unresolved_fields"])}
        for name in (
            "bbw_percentile_threshold", "dry_up_ratio_threshold", "delivery_threshold_exclusive",
            "min_distance_below_high_pct", "max_distance_below_high_pct", "rsi_min", "rsi_max",
            "minimum_rr", "breakout_trigger_buffer",
        ):
            data[name] = Decimal(str(value[name]))
        stored_fingerprint = str(data.pop("fingerprint"))
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError("PREBREAKOUT_SUCCESSOR_DRAFT_SERIALIZATION_INVALID") from error
    try:
        result = PreBreakoutVolumeResolvedSuccessorDraft(**data)
    except (TypeError, ValueError) as error:
        raise ValueError("PREBREAKOUT_SUCCESSOR_DRAFT_SERIALIZATION_INVALID") from error
    if result.fingerprint != stored_fingerprint:
        raise ValueError("PREBREAKOUT_SUCCESSOR_DRAFT_FINGERPRINT_MISMATCH")
    return result


_SUCCESSOR_DECIMAL_FIELDS = (
    "bbw_percentile_threshold", "dry_up_ratio_threshold", "delivery_threshold_exclusive",
    "min_distance_below_high_pct", "max_distance_below_high_pct", "rsi_min", "rsi_max",
    "minimum_rr", "breakout_trigger_buffer",
)


def _nested_to(value):
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, tuple):
        return [_nested_to(item) for item in value]
    if hasattr(value, "__dataclass_fields__"):
        return {field.name: _nested_to(getattr(value, field.name)) for field in fields(value)}
    return value


def _common_successor_payload(value: PreBreakoutStructuralSuccessorDraft) -> dict[str, object]:
    payload: dict[str, object] = {}
    for field in fields(PreBreakoutVolumeResolvedSuccessorDraft):
        item = getattr(value, field.name)
        payload[field.name] = _nested_to(item)
    return payload


def structural_successor_draft_to(value: PreBreakoutStructuralSuccessorDraft) -> dict[str, object]:
    """Pure canonical representation of the unselected V1.2 structural draft."""
    payload = _common_successor_payload(value)
    for name in (
        "base_window_validity", "base_top_definition", "base_window_selection",
        "support_pivot_selection", "support_breach", "tick_source", "tick_grid",
        "structural_stop", "resistance_trigger", "target_support_binding",
    ):
        payload[name] = _nested_to(getattr(value, name))
    payload["fingerprint"] = value.fingerprint
    return payload


def _object(value: object, field: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise TypeError(field + " must be an object")
    return value


def _boolean(value: object) -> bool:
    if type(value) is not bool:
        raise TypeError("boolean required")
    return value


def structural_successor_draft_from(value: dict[str, object]) -> PreBreakoutStructuralSuccessorDraft:
    """Rebuild a V1.2 draft and independently verify its stored fingerprint."""
    try:
        volume_value = _object(value["consolidation_volume_statistic"], "volume rule")
        volume = ConsolidationVolumeStatisticRule(
            statistic=ConsolidationVolumeStatistic(str(volume_value["statistic"])),
            comparison_reference=ConsolidationVolumeComparisonReference(str(volume_value["comparison_reference"])),
            reference_period=int(volume_value["reference_period"]),
            include_current_in_reference=_boolean(volume_value["include_current_in_reference"]),
            threshold_ratio=Decimal(str(volume_value["threshold_ratio"])),
            operator=ConsolidationVolumeComparisonOperator(str(volume_value["operator"])),
            minimum_prior_valid_observations=int(volume_value["minimum_prior_valid_observations"]),
        )
        validity_value = _object(value["base_window_validity"], "base validity")
        validity = BaseWindowValidityRule(
            candidate_kind=BaseWindowCandidateKind(str(validity_value["candidate_kind"])),
            minimum_canonical_sessions=int(validity_value["minimum_canonical_sessions"]),
            maximum_canonical_sessions=int(validity_value["maximum_canonical_sessions"]),
            require_consecutive_eligible_canonical_sessions=_boolean(validity_value["require_consecutive_eligible_canonical_sessions"]),
            require_evaluation_session_included=_boolean(validity_value["require_evaluation_session_included"]),
            require_window_end_at_evaluation=_boolean(validity_value["require_window_end_at_evaluation"]),
            minimum_confirmed_pivot_highs=int(validity_value["minimum_confirmed_pivot_highs"]),
            minimum_confirmed_pivot_lows=int(validity_value["minimum_confirmed_pivot_lows"]),
            require_latest_two_pivot_lows_non_decreasing=_boolean(validity_value["require_latest_two_pivot_lows_non_decreasing"]),
            require_evaluation_close_at_or_below_base_top=_boolean(validity_value["require_evaluation_close_at_or_below_base_top"]),
            no_valid_window_status=BaseWindowFailureStatus(str(validity_value["no_valid_window_status"])),
            maximum_range_pct=None if validity_value["maximum_range_pct"] is None else Decimal(str(validity_value["maximum_range_pct"])),
        )
        top_value = _object(value["base_top_definition"], "base top")
        top = BaseTopDefinitionRule(
            source=BaseTopSource(str(top_value["source"])),
            equal_maximum_lineage=EqualBaseTopLineage(str(top_value["equal_maximum_lineage"])),
            pivot_must_be_inside_candidate_window=_boolean(top_value["pivot_must_be_inside_candidate_window"]),
            raw_session_high_allowed=_boolean(top_value["raw_session_high_allowed"]),
        )
        selection_value = _object(value["base_window_selection"], "base selection")
        selection = BaseWindowSelectionRule(
            method=BaseWindowSelectionMethod(str(selection_value["method"])),
            construct_all_valid_suffix_windows=_boolean(selection_value["construct_all_valid_suffix_windows"]),
            retain_exact_maximum_base_top=_boolean(selection_value["retain_exact_maximum_base_top"]),
            select_shortest_retained_window=_boolean(selection_value["select_shortest_retained_window"]),
            allow_reward_risk_optimization=_boolean(selection_value["allow_reward_risk_optimization"]),
            allow_stop_optimization=_boolean(selection_value["allow_stop_optimization"]),
            allow_target_optimization=_boolean(selection_value["allow_target_optimization"]),
        )
        support_value = _object(value["support_pivot_selection"], "support selection")
        support = SupportPivotSelectionRule(
            method=SupportPivotMethod(str(support_value["method"])),
            support_price_field=str(support_value["support_price_field"]),
            pivot_must_be_inside_selected_base=_boolean(support_value["pivot_must_be_inside_selected_base"]),
            unconfirmed_pivot_allowed=_boolean(support_value["unconfirmed_pivot_allowed"]),
            raw_session_low_fallback_allowed=_boolean(support_value["raw_session_low_fallback_allowed"]),
            allow_stop_or_reward_risk_selection=_boolean(support_value["allow_stop_or_reward_risk_selection"]),
        )
        breach_value = _object(value["support_breach"], "support breach")
        breach = SupportBreachRule(
            comparison=SupportBreachComparison(str(breach_value["comparison"])),
            equality_is_breach=_boolean(breach_value["equality_is_breach"]),
            failure_status=str(breach_value["failure_status"]),
            applies_to_setup_eligibility_only=_boolean(breach_value["applies_to_setup_eligibility_only"]),
        )
        tick_value = _object(value["tick_source"], "tick source")
        tick = TickSourceRule(
            method=TickSourceMethod(str(tick_value["method"])), official_nse_first=_boolean(tick_value["official_nse_first"]),
            approved_licensed_exact_identity_nse_cash_fallback=_boolean(tick_value["approved_licensed_exact_identity_nse_cash_fallback"]),
            licensed_fallback_requires_explicit_approval=_boolean(tick_value["licensed_fallback_requires_explicit_approval"]),
            unavailable_status=str(tick_value["unavailable_status"]), conflict_status=str(tick_value["conflict_status"]),
            inferred_tick_fallback_allowed=_boolean(tick_value["inferred_tick_fallback_allowed"]), decimal_arithmetic_required=_boolean(tick_value["decimal_arithmetic_required"]),
        )
        grid_value = _object(value["tick_grid"], "tick grid")
        grid = TickGridRule(
            method=TickGridMethod(str(grid_value["method"])), required_remainder=Decimal(str(grid_value["required_remainder"])),
            epsilon_allowed=_boolean(grid_value["epsilon_allowed"]), rounding_repair_allowed=_boolean(grid_value["rounding_repair_allowed"]),
            nearest_grid_repair_allowed=_boolean(grid_value["nearest_grid_repair_allowed"]), floor_or_ceil_repair_allowed=_boolean(grid_value["floor_or_ceil_repair_allowed"]),
            misalignment_status=str(grid_value["misalignment_status"]),
        )
        stop_value = _object(value["structural_stop"], "structural stop")
        stop = StructuralStopRule(
            method=StructuralStopMethod(str(stop_value["method"])), structural_invalidation_source=str(stop_value["structural_invalidation_source"]),
            valid_tick_required=_boolean(stop_value["valid_tick_required"]), support_grid_aligned_required=_boolean(stop_value["support_grid_aligned_required"]),
            derived_stop_grid_aligned_required=_boolean(stop_value["derived_stop_grid_aligned_required"]), percent_or_atr_buffer_allowed=_boolean(stop_value["percent_or_atr_buffer_allowed"]),
            forced_percent_range_allowed=_boolean(stop_value["forced_percent_range_allowed"]),
        )
        trigger_value = _object(value["resistance_trigger"], "resistance trigger")
        trigger = ResistanceTriggerRule(
            resistance_source=str(trigger_value["resistance_source"]), trigger_source=str(trigger_value["trigger_source"]),
            trigger_buffer=Decimal(str(trigger_value["trigger_buffer"])),
        )
        target_value = _object(value["target_support_binding"], "target binding")
        target = TargetSupportBindingRule(
            status=TargetSupportBindingStatus(str(target_value["status"])), target_support_source=str(target_value["target_support_source"]),
            base_height_formula=str(target_value["base_height_formula"]), target_formula=str(target_value["target_formula"]),
            current_structural_support_is_bound=_boolean(target_value["current_structural_support_is_bound"]),
            target_only_support_definition_allowed=_boolean(target_value["target_only_support_definition_allowed"]),
            older_or_deeper_support_fallback_allowed=_boolean(target_value["older_or_deeper_support_fallback_allowed"]),
            selected_base_top_required=_boolean(target_value["selected_base_top_required"]),
            current_structural_support_required=_boolean(target_value["current_structural_support_required"]),
            selected_base_top_must_exceed_support=_boolean(target_value["selected_base_top_must_exceed_support"]),
            unavailable_geometry_status=str(target_value["unavailable_geometry_status"]),
            invalid_geometry_status=str(target_value["invalid_geometry_status"]),
            reward_formula=str(target_value["reward_formula"]), risk_formula=str(target_value["risk_formula"]),
            reward_risk_minimum=Decimal(str(target_value["reward_risk_minimum"])),
            reward_risk_requires_positive_risk_and_reward=_boolean(target_value["reward_risk_requires_positive_risk_and_reward"]),
            target_may_be_moved_to_manufacture_reward_risk=_boolean(target_value["target_may_be_moved_to_manufacture_reward_risk"]),
        )
        data = {**value, "consolidation_volume_statistic": volume, "base_window_validity": validity,
                "base_top_definition": top, "base_window_selection": selection, "support_pivot_selection": support,
                "support_breach": breach, "tick_source": tick, "tick_grid": grid, "structural_stop": stop,
                "resistance_trigger": trigger, "target_support_binding": target, "unresolved_fields": tuple(value["unresolved_fields"])}
        for name in _SUCCESSOR_DECIMAL_FIELDS:
            data[name] = Decimal(str(value[name]))
        stored_fingerprint = str(data.pop("fingerprint"))
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError("PREBREAKOUT_STRUCTURAL_SUCCESSOR_DRAFT_SERIALIZATION_INVALID") from error
    try:
        result = PreBreakoutStructuralSuccessorDraft(**data)
    except (TypeError, ValueError) as error:
        raise ValueError("PREBREAKOUT_STRUCTURAL_SUCCESSOR_DRAFT_SERIALIZATION_INVALID") from error
    if result.fingerprint != stored_fingerprint:
        raise ValueError("PREBREAKOUT_STRUCTURAL_SUCCESSOR_DRAFT_FINGERPRINT_MISMATCH")
    return result


def multi_stage_entry_successor_draft_to(value: PreBreakoutMultiStageEntrySuccessorDraft) -> dict[str, object]:
    """Pure canonical representation of the unselected V1.3 successor draft."""
    payload = structural_successor_draft_to(value)
    payload["multi_stage_entry"] = _nested_to(value.multi_stage_entry)
    payload["fingerprint"] = value.fingerprint
    return payload


def multi_stage_entry_successor_draft_from(value: dict[str, object]) -> PreBreakoutMultiStageEntrySuccessorDraft:
    """Rebuild V1.3 from its exact inherited V1.2 semantics and verify lineage."""
    try:
        if not isinstance(value, dict):
            raise TypeError("payload must be an object")
        expected = structural_successor_draft_to(prebreakout_policy_v1_2_structural_successor_draft())
        expected_keys = (set(expected) - {"fingerprint"}) | {"multi_stage_entry", "fingerprint"}
        if set(value) != expected_keys or value["version"] != "v1.3-draft":
            raise ValueError("unexpected successor payload")
        for name, expected_value in expected.items():
            if name not in {"version", "fingerprint"} and value[name] != expected_value:
                raise ValueError("inherited V1.2 semantics changed")
        entry_value = _object(value["multi_stage_entry"], "multi-stage entry")
        rule = MultiStageEntryRule(
            entry_reference_method=EntryReferenceMethod(str(entry_value["entry_reference_method"])),
            entry_reference_is_factual_not_fill=_boolean(entry_value["entry_reference_is_factual_not_fill"]),
            entry_reference_is_not_order_price=_boolean(entry_value["entry_reference_is_not_order_price"]),
            maximum_acceptable_entry_method=MaximumAcceptableEntryMethod(str(entry_value["maximum_acceptable_entry_method"])),
            maximum_acceptable_entry_formula=str(entry_value["maximum_acceptable_entry_formula"]),
            maximum_acceptable_entry_is_economic_ceiling_only=_boolean(entry_value["maximum_acceptable_entry_is_economic_ceiling_only"]),
            maximum_acceptable_entry_is_not_synthetic_entry=_boolean(entry_value["maximum_acceptable_entry_is_not_synthetic_entry"]),
            executable_entry_grid_method=ExecutableEntryGridMethod(str(entry_value["executable_entry_grid_method"])),
            exact_decimal_arithmetic_required=_boolean(entry_value["exact_decimal_arithmetic_required"]),
            upward_rounding_allowed=_boolean(entry_value["upward_rounding_allowed"]),
            nearest_tick_rounding_allowed=_boolean(entry_value["nearest_tick_rounding_allowed"]),
            preserve_aligned_ceiling_exactly=_boolean(entry_value["preserve_aligned_ceiling_exactly"]),
            maximum_executable_entry_is_not_order_price=_boolean(entry_value["maximum_executable_entry_is_not_order_price"]),
            maximum_executable_entry_is_not_assumed_fill=_boolean(entry_value["maximum_executable_entry_is_not_assumed_fill"]),
            require_executable_entry_above_final_stop=_boolean(entry_value["require_executable_entry_above_final_stop"]),
            require_executable_entry_below_trigger=_boolean(entry_value["require_executable_entry_below_trigger"]),
            entry_reference_must_not_exceed_executable_ceiling=_boolean(entry_value["entry_reference_must_not_exceed_executable_ceiling"]),
            entry_reference_must_be_above_final_stop=_boolean(entry_value["entry_reference_must_be_above_final_stop"]),
            entry_reference_must_be_below_trigger=_boolean(entry_value["entry_reference_must_be_below_trigger"]),
            reference_risk_formula=str(entry_value["reference_risk_formula"]),
            reference_reward_formula=str(entry_value["reference_reward_formula"]),
            reference_reward_risk_minimum=Decimal(str(entry_value["reference_reward_risk_minimum"])),
            reward_risk_basis=PreBreakoutRiskRewardBasis(str(entry_value["reward_risk_basis"])),
            transaction_friction_handling=str(entry_value["transaction_friction_handling"]),
            actual_execution_price_method=ActualExecutionPriceMethod(str(entry_value["actual_execution_price_method"])),
            actual_execution_price_is_later_factual_value=_boolean(entry_value["actual_execution_price_is_later_factual_value"]),
            actual_execution_revalidation_required=_boolean(entry_value["actual_execution_revalidation_required"]),
            actual_execution_must_not_exceed_executable_ceiling=_boolean(entry_value["actual_execution_must_not_exceed_executable_ceiling"]),
            actual_execution_must_be_above_final_stop=_boolean(entry_value["actual_execution_must_be_above_final_stop"]),
            actual_execution_must_be_below_trigger=_boolean(entry_value["actual_execution_must_be_below_trigger"]),
            actual_execution_must_satisfy_reference_minimum_rr=_boolean(entry_value["actual_execution_must_satisfy_reference_minimum_rr"]),
            breakout_trigger_role=BreakoutTriggerRole(str(entry_value["breakout_trigger_role"])),
            breakout_trigger_is_not_initial_entry=_boolean(entry_value["breakout_trigger_is_not_initial_entry"]),
            do_not_chase=_boolean(entry_value["do_not_chase"]),
            price_too_high_status=str(entry_value["price_too_high_status"]),
            no_valid_entry_status=str(entry_value["no_valid_entry_status"]),
            trigger_entry_unavailable_status=str(entry_value["trigger_entry_unavailable_status"]),
            invalid_geometry_status=str(entry_value["invalid_geometry_status"]),
        )
        stored_fingerprint = str(value["fingerprint"])
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError("PREBREAKOUT_MULTI_STAGE_ENTRY_SUCCESSOR_DRAFT_SERIALIZATION_INVALID") from error
    try:
        result = replace(prebreakout_policy_v1_3_multi_stage_entry_successor_draft(), multi_stage_entry=rule)
        result.assert_exact_v1_3_multi_stage_entry_semantics()
    except (TypeError, ValueError) as error:
        raise ValueError("PREBREAKOUT_MULTI_STAGE_ENTRY_SUCCESSOR_DRAFT_SERIALIZATION_INVALID") from error
    if result.fingerprint != stored_fingerprint:
        raise ValueError("PREBREAKOUT_MULTI_STAGE_ENTRY_SUCCESSOR_DRAFT_FINGERPRINT_MISMATCH")
    return result
