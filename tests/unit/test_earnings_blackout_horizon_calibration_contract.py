"""Static proofs for the non-active earnings-event horizon calibration contract."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest

from app.fundamentals.diagnostic_comparability import canonical_json, content_fingerprint


ROOT = Path(__file__).resolve().parents[2]
ARTIFACT = ROOT / "docs/architecture/EARNINGS_BLACKOUT_HORIZON_CALIBRATION_CONTRACT_V1.json"
PROPOSAL_FP = "sha256:36c80f2ea561a4411b252e6b4749f9c73275d6e434b257e89bdeb24d83de0e21"
APPROVAL_FP = "sha256:0d2bd690a9b5cec347437163cbc7ad88cadec940b0546549ce40361b833414d0"
BOUNDARIES = {
    "V1_ACTIVE": True, "GATE_POLICY_V2_ACTIVE": False, "SIX_GATES_EXACTLY_SIX": True,
    "NO_UNVERIFIED_CALENDAR_CLEARANCE": True, "NO_RETROACTIVE_BLACKOUT": True,
    "NO_FUTURE_LEAKAGE": True, "NO_HORIZON_GUESS": True,
    "PILOT_SIMPLICITY_RULE": "ACTIVE", "AI_DECISION_AUTHORITY": False,
    "EARNINGS_DIRECTION_PREDICTION": False, "LIVE_ORDERS": False,
}
TOP_KEYS = set("""
schema_version contract_id contract_version baseline_commit authority status scope
runtime_implementation_authorized runtime_registration_created numeric_horizon_selected
proposal_reference research_basis calibration_layers calibration_modes event_contract
decision_snapshot realized_outcome reaction_session_policy session_distance risk_metrics
liquidity_and_slippage opportunity_cost heterogeneity known_late_and_lifecycle
sample_sufficiency benchmark_and_counterfactual anti_overfit future_experiment_contract
outcome_ledger_reuse data_readiness source_gaps boundaries next_continuation
next_continuation_started fingerprint_scheme contract_fingerprint
""".split())


def _unique(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError(f"DUPLICATE_JSON_KEY:{key}")
        value[key] = item
    return value


def _read():
    return json.loads(ARTIFACT.read_text(encoding="utf-8"), object_pairs_hook=_unique)


def _unsigned(value):
    return {key: item for key, item in value.items() if key != "contract_fingerprint"}


def _validate(value):
    """Test-only contract verifier. A rehash cannot legitimize weakened policy."""
    assert set(value) == TOP_KEYS
    assert value["contract_fingerprint"] == content_fingerprint(_unsigned(value))
    assert value["schema_version"] == "earnings-blackout-horizon-calibration-contract/v1"
    assert value["contract_id"] == "earnings-blackout-horizon-calibration-contract"
    assert value["contract_version"] == "v1"
    assert value["baseline_commit"] == "a42860e42074e5e93da982487bac4ed23707baf2"
    assert value["authority"] == {
        "basis": "USER_DELEGATED_BOUNDED_CALIBRATION_CONTRACT_REVIEW",
        "directive_id": "fd0a19ea-b8c5-48ac-be1d-228d4e47a854",
        "reviewer": "Codex calibration-contract architect", "human_signature_claimed": False,
    }
    assert value["status"] == "CALIBRATION_CONTRACT_READY_DATA_PARTIAL"
    assert value["scope"] == "NON_ACTIVE_MEASUREMENT_AND_EXPERIMENT_DESIGN_ONLY"
    assert value["runtime_implementation_authorized"] is value["runtime_registration_created"] is False
    assert value["numeric_horizon_selected"] is False
    assert value["proposal_reference"] == {
        "policy_id": "execution-gate-policy-v2-proposed", "policy_version": "v2-proposal.2",
        "proposal_fingerprint": PROPOSAL_FP,
        "approval_id": "earnings-blackout-policy-v2-governance-approval/v1",
        "approval_fingerprint": APPROVAL_FP,
        "approval_status": "GOVERNANCE_APPROVED_WITH_ACTIVATION_BLOCKERS",
    }
    assert [(row["id"], row["url"] if "url" in row else row["path"]) for row in value["research_basis"]] == [
        ("PATELL_WOLFSON_1984", "https://doi.org/10.1016/0304-405X(84)90024-2"),
        ("NBER_W31360", "https://www.nber.org/papers/w31360"),
        ("NSE_COMPLIANCE_CALENDAR", "https://www.nseindia.com/static/companies-listing/compliance-information-compliance-calendar-main-board"),
        ("HSI_HORIZON_RESEARCH_V1", "docs/architecture/EARNINGS_BLACKOUT_HORIZON_POLICY_RESEARCH_V1.md"),
    ]
    non_horizon_labels = {"UNIVERSAL_BLACKOUT_HORIZON", "UNIVERSAL_HORIZON", "NUMERIC_V2_HORIZON", "EVENT_RISK_HORIZON"}
    assert all(any(label in row["does_not_support"] for label in non_horizon_labels) for row in value["research_basis"])
    assert [(row["id"], row["requires_hsi_setup"]) for row in value["calibration_layers"]] == [
        ("MARKET_EVENT_RISK_CALIBRATION", False), ("HSI_ACTION_IMPACT_CALIBRATION", True),
    ]
    assert [row["id"] for row in value["calibration_modes"]] == [
        "STRICT_HISTORICAL_PIT_CALIBRATION", "PROSPECTIVE_SHADOW_CALIBRATION", "CURRENT_DESCRIPTIVE_RESEARCH",
    ]
    strict, prospective, descriptive = value["calibration_modes"]
    assert strict["later_schedule_backfill_allowed"] is False
    assert prospective["execution_influence"] is False
    assert descriptive["promotion_eligible"] == "NEVER_BY_ITSELF"
    _event_and_snapshot(value)
    _outcomes_and_metrics(value)
    _experiments_and_readiness(value)
    assert value["boundaries"] == BOUNDARIES
    assert value["next_continuation"] == "EARNINGS_BLACKOUT_PROSPECTIVE_SCHEDULE_RECEIPT_READINESS_V1"
    assert value["next_continuation_started"] is False
    assert value["fingerprint_scheme"] == "sha256:utf8:canonical-json-v1:exclude-contract_fingerprint"


def _event_and_snapshot(value):
    event = value["event_contract"]
    assert event["candidate_name"] == "EarningsEventCalibrationObservation"
    assert event["persistence"] == "NOT_IMPLEMENTED_NO_NEW_STORE_AUTHORIZED"
    assert event["cross_exchange_rule"] == "ONE_RECONCILED_LOGICAL_EVENT_WITH_NSE_AND_BSE_LINEAGES_RETAINED_UNDER_IT"
    assert event["duplicate_event_rule"] == "REJECT_OR_RECONCILE_NEVER_COUNT_TWICE"
    for name in (
        "canonical_instrument_id", "reconciled_schedule_event_id", "schedule_evidence_ids",
        "schedule_policy_id", "schedule_policy_version", "schedule_policy_fingerprint",
        "scheduled_event_date", "schedule_known_at", "hsi_first_observed_receipt_id",
        "hsi_first_observed_at", "revision_reschedule_lineage_ids", "actual_result_filing_id",
        "actual_result_publication_at", "actual_result_known_at", "event_type", "statement_scope",
        "calibration_mode",
    ):
        assert name in event["immutable_identity_fields"]
    assert len(event["immutable_identity_fields"]) == len(set(event["immutable_identity_fields"]))
    assert len(event["required_fingerprints"]) == len(set(event["required_fingerprints"]))
    snapshot = value["decision_snapshot"]
    assert snapshot["future_amendment_can_modify_snapshot"] is False
    assert snapshot["no_hindsight_entry"] is True
    assert snapshot["entry_layer_requirement"] == "ACTION_IMPACT_REQUIRES_GENUINE_FRESH_ENTRY_STATE_AND_EXACT_AS_OF_LINEAGE"
    for name in ("decision_as_of", "decision_session_id", "schedule_evidence_visible_at_decision",
                 "known_at_perspective", "registry_version", "strategy_version", "gate_policy_id",
                 "gate_policy_version", "gate_policy_fingerprint", "market_data_fingerprint",
                 "diagnostic_fingerprint", "setup_signal_state", "setup_signal_fingerprint"):
        assert name in snapshot["immutable_fields"]


def _outcomes_and_metrics(value):
    outcome = value["realized_outcome"]
    assert outcome["separate_from_decision_snapshot"] is True
    assert outcome["may_supply_decision_time_input"] is False
    assert outcome["date_only_actual_publication"] == "TEMPORAL_OUTCOME_INCOMPLETE"
    reaction = value["reaction_session_policy"]
    assert reaction == {
        "pre_open_exact_publication": "SAME_REGULAR_EXCHANGE_SESSION_ONLY_IF_OPEN_TIME_AND_SESSION_PROVEN",
        "during_regular_session_exact_publication": "INTRADAY_REACTION_ONLY_IF_CANONICAL_INTRADAY_ORDERING_EXISTS_OTHERWISE_TEMPORAL_OUTCOME_INCOMPLETE",
        "after_close_exact_publication": "NEXT_REGULAR_EXCHANGE_SESSION_ONLY_IF_SESSION_PROVEN",
        "date_only_publication": "TEMPORAL_OUTCOME_INCOMPLETE_NO_TIME_INVENTION",
        "non_standard_session": "REQUIRE_EXACT_SESSION_CLASS_AND_TRADABILITY_OR_TEMPORAL_OUTCOME_INCOMPLETE",
        "next_or_previous_session_fallback_allowed": False,
    }
    distance = value["session_distance"]
    assert distance["field"] == "TRADING_SESSIONS_TO_EVENT"
    assert distance["calendar_days_allowed"] is distance["candidate_grid_preselected"] is False
    assert distance["scheduled_date_non_session_or_unmappable"] == "TEMPORAL_OUTCOME_INCOMPLETE"
    metrics = {row["id"]: row for row in value["risk_metrics"]}
    assert tuple(metrics) == (
        "PREVIOUS_CLOSE_TO_REACTION_OPEN_GAP", "ABSOLUTE_OPENING_GAP", "SIGNED_OPENING_GAP",
        "ATR_NORMALIZED_OPENING_GAP", "REACTION_SESSION_RETURN", "ABSOLUTE_REACTION_SESSION_RETURN",
        "REALIZED_VOLATILITY", "MAXIMUM_ADVERSE_EXCURSION", "MAXIMUM_FAVOURABLE_EXCURSION",
        "POST_EVENT_DRAWDOWN", "POST_EVENT_VOLATILITY_NORMALIZATION",
    )
    assert metrics["ATR_NORMALIZED_OPENING_GAP"]["atr_calculation"] == "REUSE_EXISTING_CANONICAL_ATR_ONLY_NO_NEW_FORMULA"
    for name in ("REALIZED_VOLATILITY", "MAXIMUM_ADVERSE_EXCURSION", "MAXIMUM_FAVOURABLE_EXCURSION",
                 "POST_EVENT_DRAWDOWN", "POST_EVENT_VOLATILITY_NORMALIZATION"):
        assert metrics[name]["formula"] is None and metrics[name]["status_if_missing"] == "UNAVAILABLE"
    liquidity = value["liquidity_and_slippage"]
    assert liquidity["bid_ask_spread_invention_allowed"] is liquidity["unavailable_is_zero"] is False
    assert liquidity["measured_slippage"] == "REQUIRES_EXECUTION_OR_APPROVED_SHADOW_EXECUTION_MODEL"
    opportunity = value["opportunity_cost"]
    assert opportunity["layer"] == "HSI_ACTION_IMPACT_CALIBRATION_ONLY"
    assert opportunity["identical_strategy_logic_required"] is True
    assert opportunity["synthetic_entry_allowed"] is opportunity["unavailable_is_zero"] is False
    assert "stock went up" not in opportunity["false_veto_definition"].lower()


def _experiments_and_readiness(value):
    heterogeneity = value["heterogeneity"]
    assert heterogeneity["tiny_subgroups_allowed"] is heterogeneity["per_stock_horizon_optimization_allowed"] is False
    late = value["known_late_and_lifecycle"]
    assert late["historical_rule"] == "USE_ONLY_SCHEDULE_VERSION_VISIBLE_AT_EACH_DECISION"
    assert late["later_final_lifecycle_in_decision_snapshot"] is False
    sufficiency = value["sample_sufficiency"]
    assert sufficiency["states"] == ["SAMPLE_INSUFFICIENT", "RESEARCH_ONLY", "CALIBRATION_ELIGIBLE", "OOS_VALIDATED", "PROSPECTIVE_VALIDATED"]
    assert sufficiency["quantitative_promotion_thresholds"] == "UNSET_SEPARATE_GOVERNANCE_REQUIRED"
    assert sufficiency["tail_quantile_cutoff"] is None
    comparison = value["benchmark_and_counterfactual"]
    assert comparison["benchmarks"] == ["NIFTY_50", "NIFTY_500", "RELEVANT_SECTOR_INDEX_WHEN_CANONICAL"]
    assert comparison["reuse_new_benchmark_engine"] is comparison["highest_historical_return_selection_allowed"] is False
    anti = value["anti_overfit"]
    assert all(anti[name] is True for name in ("training_calibration_partition_required", "out_of_sample_partition_required", "walk_forward_or_temporal_holdout_required", "prospective_shadow_evidence_required"))
    assert anti["self_modifying_active_rule_allowed"] is anti["post_outcome_grid_construction_allowed"] is anti["new_calibration_database_authorized"] is False
    experiment = value["future_experiment_contract"]
    assert experiment["candidate_name"] == "EarningsBlackoutHorizonExperiment"
    assert experiment["persistence"] == "NOT_IMPLEMENTED" and experiment["automatic_activation"] is False
    assert experiment["selection_authority"] == "FUTURE_HUMAN_GOVERNANCE_ONLY"
    ledger = value["outcome_ledger_reuse"]
    assert ledger["new_database"] is ledger["integration_implemented"] is False
    assert ledger["action_layer"] == "REUSE_FORWARD_PAPER_AND_PAPER_OUTCOME_LINEAGE_WHEN_EXACT_VERSIONED_ENTRY_EXISTS"
    readiness = {row["input"]: row for row in value["data_readiness"]}
    assert set(readiness) == {
        "HISTORICAL_SCHEDULE_PIT", "PROSPECTIVE_SCHEDULE_RECEIPTS", "DAILY_BARS", "ATR_LINEAGE",
        "ACTUAL_FINANCIAL_RESULT_PUBLICATION", "OPENING_PRICES", "MARKET_BENCHMARK", "SECTOR_BENCHMARK",
        "MFE_MAE_CAPABLE_PRICE_PATH", "SLIPPAGE_EVIDENCE", "HSI_PRE_EVENT_SETUP_RECORDS",
    }
    assert readiness["HISTORICAL_SCHEDULE_PIT"]["state"] == "NOT_READY"
    assert readiness["PROSPECTIVE_SCHEDULE_RECEIPTS"]["state"] == "NOT_READY"
    assert readiness["DAILY_BARS"]["state"] == readiness["OPENING_PRICES"]["state"] == "READY"
    assert readiness["MARKET_BENCHMARK"]["state"] == "READY"
    assert readiness["SLIPPAGE_EVIDENCE"]["state"] == "NOT_READY"
    assert all(row["classification"].startswith(("MANDATORY", "OPTIONAL")) for row in readiness.values())
    gaps = value["source_gaps"]
    assert gaps["new_source_hunt_started"] is gaps["source_gap_is_zero"] is False


def test_contract_schema_and_all_safety_semantics_are_exact():
    _validate(_read())


def test_deterministic_replay_and_fingerprint_cover_each_top_level_field():
    value = _read()
    replay = json.loads(canonical_json(value), object_pairs_hook=_unique)
    _validate(replay)
    assert replay == value
    body = _unsigned(value)
    assert content_fingerprint(dict(reversed(list(body.items())))) == value["contract_fingerprint"]
    for key in body:
        altered = deepcopy(body)
        del altered[key]
        assert content_fingerprint(altered) != value["contract_fingerprint"]
    altered = deepcopy(body)
    altered["risk_metrics"].reverse()
    assert content_fingerprint(altered) != value["contract_fingerprint"]


@pytest.mark.parametrize(("path", "replacement"), [
    (("numeric_horizon_selected",), True),
    (("status",), "CALIBRATION_CONTRACT_READY_DATA_SUFFICIENT_FOR_SHADOW"),
    (("calibration_modes", 0, "later_schedule_backfill_allowed"), True),
    (("calibration_modes", 2, "promotion_eligible"), "HISTORICAL_ONLY"),
    (("decision_snapshot", "future_amendment_can_modify_snapshot"), True),
    (("decision_snapshot", "no_hindsight_entry"), False),
    (("realized_outcome", "may_supply_decision_time_input"), True),
    (("reaction_session_policy", "date_only_publication"), "NEXT_SESSION"),
    (("reaction_session_policy", "next_or_previous_session_fallback_allowed"), True),
    (("session_distance", "calendar_days_allowed"), True),
    (("session_distance", "candidate_grid_preselected"), True),
    (("liquidity_and_slippage", "bid_ask_spread_invention_allowed"), True),
    (("opportunity_cost", "synthetic_entry_allowed"), True),
    (("heterogeneity", "per_stock_horizon_optimization_allowed"), True),
    (("anti_overfit", "self_modifying_active_rule_allowed"), True),
    (("outcome_ledger_reuse", "new_database"), True),
    (("boundaries", "GATE_POLICY_V2_ACTIVE"), True),
    (("next_continuation_started",), True),
])
def test_rehashed_unsafe_change_is_rejected(path, replacement):
    value = deepcopy(_read())
    destination = value
    for item in path[:-1]:
        destination = destination[item]
    destination[path[-1]] = replacement
    value["contract_fingerprint"] = content_fingerprint(_unsigned(value))
    with pytest.raises(AssertionError):
        _validate(value)


def test_contract_reuses_existing_paths_and_is_not_imported_by_runtime():
    value = _read()
    for path in value["anti_overfit"]["experiment_reuse"]:
        assert (ROOT / path).is_file()
    for path in (
        "app/filings/earnings_schedule_known_at.py", "app/filings/earnings_schedule_identity.py",
        "app/filings/earnings_schedule_coverage.py", "app/filings/earnings_schedule_store.py",
        "app/market_data/current_prebreakout.py", "app/intelligence/market_technical_artifact.py",
        "app/paper/models.py", "app/forward_paper/models.py",
    ):
        assert (ROOT / path).is_file()
    for source in (ROOT / "app").rglob("*.py"):
        assert "EARNINGS_BLACKOUT_HORIZON_CALIBRATION_CONTRACT_V1" not in source.read_text(encoding="utf-8")


def test_duplicate_json_keys_and_unapproved_contract_surface_are_rejected():
    with pytest.raises(ValueError, match="DUPLICATE_JSON_KEY"):
        json.loads('{"status":"A","status":"ACTIVE"}', object_pairs_hook=_unique)
    value = _read()
    value["live_horizon"] = 5
    value["contract_fingerprint"] = content_fingerprint(_unsigned(value))
    with pytest.raises(AssertionError):
        _validate(value)
