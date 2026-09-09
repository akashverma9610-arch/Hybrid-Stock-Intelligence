"""Static proof for the non-active canonical intraday derivation candidate."""

from __future__ import annotations

from datetime import UTC, date, datetime
from hashlib import sha256
import json
from pathlib import Path

from app.historical.canonical_market_session_event_time import SessionPhaseType
from app.historical.nse_capital_market_session_evidence_2022_2026 import nse_capital_market_calendar_2022_2026


_ROOT = Path(__file__).resolve().parents[2]
_POLICY_PATH = _ROOT / "docs" / "architecture" / "CANONICAL_INTRADAY_TIMEFRAME_DERIVATION_POLICY_V1_CANDIDATE.json"
_RULE_POLICY_PATH = _ROOT / "docs" / "architecture" / "RULE_HORIZON_TIMEFRAME_APPLICABILITY_POLICY_V1_CANDIDATE.json"
_TIMEFRAMES = ("15m", "30m", "1H", "4H")


def _policy() -> dict[str, object]:
    return json.loads(_POLICY_PATH.read_text(encoding="utf-8"))


def _fingerprint(value: dict[str, object]) -> str:
    payload = dict(value)
    payload.pop("policy_fingerprint")
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return "sha256:" + sha256(encoded).hexdigest()


def _timeframe(policy: dict[str, object], identifier: str) -> dict[str, object]:
    return next(value for value in policy["timeframes"] if value["id"] == identifier)  # type: ignore[index,return-value]


def test_candidate_is_tamper_evident_and_preserves_exact_intraday_taxonomy() -> None:
    policy = _policy()

    assert policy["policy_id"] == "canonical-intraday-timeframe-derivation-policy"
    assert policy["version"] == "v1-candidate"
    assert policy["status"] == "CANDIDATE_NOT_ACTIVE"
    assert policy["fingerprint_scheme"] == "sha256:utf8:canonical-json-v1"
    assert policy["policy_fingerprint"] == _fingerprint(policy)
    assert tuple(policy["canonical_timeframes"]) == _TIMEFRAMES
    assert [value["id"] for value in policy["timeframes"]] == list(_TIMEFRAMES)  # type: ignore[index]


def test_standard_375_minute_partition_has_no_hidden_remainder() -> None:
    partition = _policy()["standard_session"]["partition"]  # type: ignore[index]

    assert partition == {
        "15m": {"duration_minutes": 15, "full_intervals": 25, "remainder_minutes": 0},
        "30m": {"duration_minutes": 30, "full_intervals": 12, "remainder_minutes": 15},
        "1H": {"duration_minutes": 60, "full_intervals": 6, "remainder_minutes": 15},
        "4H": {"duration_minutes": 240, "full_intervals": 1, "remainder_minutes": 135},
    }
    assert _policy()["standard_session"]["minutes"] == 375  # type: ignore[index]


def test_session_anchor_is_canonical_phase_and_never_crosses_sessions() -> None:
    authority = _policy()["canonical_session_authority"]  # type: ignore[index]

    assert authority["calendar_contract"] == "canonical-market-session-calendar-and-event-time"
    assert authority["required_phase"] == "REGULAR_CONTINUOUS"
    assert authority["anchor"] == "EXACT_CANONICAL_PHASE_START"
    assert authority["ordinary_clock_assumption"] == "PROHIBITED"
    assert authority["session_crossing"] == "PROHIBITED"
    assert authority["calendar_or_phase_unavailable"] == "FAIL_CLOSED_NO_DERIVATION"


def test_calendar_proves_reference_and_special_session_phase_boundaries() -> None:
    calendar = nse_capital_market_calendar_2022_2026()
    ordinary = tuple(
        value for value in calendar.phases_for(date(2026, 9, 8), as_of=datetime(2026, 9, 8, 16, tzinfo=UTC))
        if value.phase_type is SessionPhaseType.REGULAR_CONTINUOUS
    )
    special = tuple(
        value for value in calendar.phases_for(date(2024, 11, 1), as_of=datetime(2024, 11, 1, 20, tzinfo=UTC))
        if value.phase_type is SessionPhaseType.REGULAR_CONTINUOUS
    )

    assert len(ordinary) == len(special) == 1
    assert (ordinary[0].ends_at - ordinary[0].starts_at).total_seconds() == 375 * 60
    assert (special[0].ends_at - special[0].starts_at).total_seconds() == 60 * 60
    assert ordinary[0].fingerprint != special[0].fingerprint


def test_15m_policy_is_exact_but_not_data_or_production_ready() -> None:
    value = _timeframe(_policy(), "15m")

    assert value["session_anchor"] == "EXACT_CANONICAL_PHASE_START"
    assert value["boundary_policy"] == "FULL_SESSION_OPEN_ANCHORED_FIXED_15_MINUTE_INTERVALS"
    assert value["tail_policy"] == "NOT_APPLICABLE_FOR_375_MINUTE_STANDARD_SESSION"
    assert value["base_evidence_requirement"] == "15_EXACT_ONE_MINUTE_COVERAGE_STATES__CLOSED_OR_EXPLICIT_NO_TRADE"
    assert value["current_policy_readiness"] == "POLICY_READY"
    assert value["current_data_readiness"] == "NOT_READY"
    assert value["live_proof_readiness"] == "NOT_READY"
    assert value["production_readiness"] == "NOT_READY"


def test_unresolved_remainder_timeframes_cannot_be_silently_activated() -> None:
    policy = _policy()
    thirty = _timeframe(policy, "30m")
    hour = _timeframe(policy, "1H")
    four_hour = _timeframe(policy, "4H")

    for value in (thirty, hour):
        assert value["session_anchor"] == "UNSET"
        assert value["boundary_policy"] == "UNSET"
        assert value["tail_policy"].startswith("UNSET__375_MINUTE_SESSION_HAS_15_MINUTE_REMAINDER")
        assert value["current_policy_readiness"] == "POLICY_UNSET"
        assert value["production_readiness"] == "NOT_READY"
    assert four_hour["session_anchor"] == "UNSET"
    assert four_hour["boundary_policy"] == "UNSET"
    assert four_hour["tail_policy"].startswith("UNSET__375_MINUTE_SESSION_HAS_135_MINUTE_REMAINDER")
    assert four_hour["current_policy_readiness"] == "NOT_READY"
    assert "CROSS_SESSION_PROHIBITION" in four_hour["unresolved_parameters"]


def test_special_session_gap_and_no_trade_states_remain_distinct() -> None:
    policy = _policy()
    common = policy["common_derivation_rules"]  # type: ignore[index]
    fifteen = _timeframe(policy, "15m")

    assert fifteen["special_session_policy"] == "ACTUAL_CANONICAL_PHASE_ONLY__FULL_15_MINUTE_PARTITIONS_ONLY__NO_PARTIAL_BAR"
    assert fifteen["halt_reopen_policy"] == "EXACT_CANONICAL_PHASE_EVIDENCE_REQUIRED__ANY_UNOBSERVED_REQUIRED_WINDOW_FAILS_CLOSED"
    assert common["gap_not_equal_no_trade"] is True
    assert common["provider_gap"] == "REQUIRED_WINDOW_FAILS_CLOSED__NO_COMPLETE_BAR"
    assert common["no_trade"] == "EXPLICIT_CONTINUOUS_OBSERVATION_REQUIRED__NO_FABRICATED_PRICE"
    assert common["entire_interval_no_trade"] == "NO_OHLCV_BAR_MATERIALIZED__DESCRIPTIVE_NO_TRADE_RECEIPT_ONLY"


def test_ohlc_volume_completeness_and_known_at_are_fail_closed() -> None:
    common = _policy()["common_derivation_rules"]  # type: ignore[index]

    assert common["ohlc"] == {
        "open": "FIRST_GENUINE_TRADE_PRICE",
        "high": "MAXIMUM_GENUINE_TRADE_PRICE",
        "low": "MINIMUM_GENUINE_TRADE_PRICE",
        "close": "LAST_GENUINE_TRADE_PRICE",
        "prohibited": ["DAILY_HIGH_LOW", "PROVIDER_DAY_HIGH_LOW", "FORWARD_FILL", "INTERPOLATION"],
    }
    assert common["volume"]["aggregation"] == "SUM_VALID_INCREMENTAL_BASE_VOLUME"  # type: ignore[index]
    assert common["volume"]["unresolved_baseline"] == "INCOMPLETE__VOLUME_NOT_COMPLETE"  # type: ignore[index]
    assert common["complete_bar"] == "REQUIRES_EVERY_REQUIRED_MINUTE_OBSERVED_OR_EXPLICIT_NO_TRADE__NO_GAP__NO_CONFLICT__VALID_VOLUME"
    assert common["known_at"] == "MAX_INTERVAL_END_AND_ALL_REQUIRED_EVIDENCE_KNOWN_AT__ACTUAL_FINALIZATION_TIME"
    assert common["late_repair"] == "LATER_KNOWN_AT__IMMUTABLE_REVISION_OR_CONFLICT__NO_RETROACTIVE_KNOWLEDGE"


def test_replay_conflict_storage_and_provider_neutrality_stay_immutable() -> None:
    policy = _policy()
    common = policy["common_derivation_rules"]  # type: ignore[index]
    storage = policy["storage_interaction"]  # type: ignore[index]

    assert common["replay"] == "IDENTICAL_EVIDENCE_IDEMPOTENT"
    assert common["conflict"] == "PRESERVE_PRIOR_EVIDENCE_AND_CONFLICT_LINEAGE__NO_SILENT_REWRITE"
    assert policy["base_evidence"]["canonicality"] == "PROVIDER_NEUTRAL_AFTER_NORMALIZATION"  # type: ignore[index]
    assert storage["retention_duration"] == "UNSET"
    assert storage["delete_data"] == "NOT_AUTHORIZED"
    assert policy["scope"]["live_capture_activation"] == "NOT_ACTIVE"  # type: ignore[index]


def test_rule_14_remains_genuine_mtf_only_without_changing_the_frozen_policy() -> None:
    policy = _policy()
    rule_policy = json.loads(_RULE_POLICY_PATH.read_text(encoding="utf-8"))
    rule_14 = next(value for value in rule_policy["rule_horizon_rows"] if value["rule_id"] == 14)
    profile = rule_policy["technical_profiles"][rule_14["technical_profile"]]

    assert policy["rule_horizon_compatibility"]["canonical_61_by_3_rows"] == "UNCHANGED"  # type: ignore[index]
    assert policy["rule_horizon_compatibility"]["prohibited_substitutions"] == [  # type: ignore[index]
        "1D_AS_4H", "15m_AS_30m", "15m_AS_1H", "1H_AS_4H",
    ]
    assert profile["SHORT_TERM"]["15m"] == "DATA_NOT_READY"
    assert profile["SHORT_TERM"]["30m"] == "DATA_NOT_READY"
    assert profile["SHORT_TERM"]["1H"] == "DATA_NOT_READY"
    assert profile["SHORT_TERM"]["4H"] == "DATA_NOT_READY"


def test_dhan_identity_blockers_and_next_slice_are_visible_without_repair() -> None:
    policy = _policy()
    coverage = policy["dhan_identity_coverage"]  # type: ignore[index]

    assert coverage == {
        "selected_universe": 2553,
        "exact_ready": 2287,
        "provider_identity_not_found": 5,
        "security_class_mismatch": 261,
        "ambiguous": 0,
        "symbol_conflict": 0,
        "repair_authorized": False,
    }
    assert policy["next_dominant_solvable_blocker"] == "CANONICAL_PROSPECTIVE_15M_BAR_DERIVATION_V1"
