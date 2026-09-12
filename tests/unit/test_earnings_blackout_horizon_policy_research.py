"""Machine-contract checks for the non-active blackout-horizon research receipt."""
from __future__ import annotations

import json
from pathlib import Path

from app.fundamentals.diagnostic_comparability import content_fingerprint


RECEIPT = Path("docs/architecture/EARNINGS_BLACKOUT_HORIZON_POLICY_RESEARCH_V1_RECEIPT.json")


def _receipt() -> dict[str, object]:
    return json.loads(RECEIPT.read_text(encoding="utf-8"))


def test_primary_source_and_historical_rule_guard_are_explicit_and_non_retroactive():
    value = _receipt()
    current = value["current_regulation_29"]
    historical = value["historical_rule_guard"]
    assert current == {
        "minimum_notice": "AT_LEAST_TWO_WORKING_DAYS",
        "exclusions": ["INTIMATION_DATE", "MEETING_DATE"],
        "authoritative_notice_guarantees_t_minus_5": False,
        "source": "https://www.nseindia.com/static/companies-listing/compliance-information-compliance-calendar-main-board",
    }
    assert historical["required"] == "EFFECTIVE_DATED_REGULATION_VERSION_REQUIRED_FOR_REPLAY"
    assert historical["current_rule_retroactive"] is False
    assert historical["old_rule_current"] is False


def test_policy_option_matrix_is_complete_deterministic_and_recommends_only_the_documented_option():
    value = _receipt()
    options = value["policy_options"]
    assert [(item["id"], item["name"]) for item in options] == [
        ("A", "KEEP_FIXED_5_SESSION_HARD_GATE"),
        ("B", "VERIFIED_SCHEDULE_DYNAMIC_HARD_BLOCK"),
        ("C", "VERIFIED_HARD_BLOCK_PLUS_SOFT_RESULTS_SEASON_CONTEXT"),
        ("D", "UNKNOWN_SCHEDULE_ALWAYS_BLOCKS_ENTRY"),
        ("E", "EARLIER_AUTHORITATIVE_SOURCE_REQUIRED"),
    ]
    assert value["final_decision"] == "VERIFIED_HARD_BLOCK_PLUS_SOFT_RISK_CONTEXT_RECOMMENDED"
    assert value["next_continuation"] == "EARNINGS_BLACKOUT_POLICY_V2_PROPOSAL"
    assert value["next_continuation_started"] is False


def test_receipt_replay_is_fingerprinted_and_preserves_unknown_not_clear_and_nonactive_boundaries():
    value = _receipt()
    supplied = value.pop("fingerprint")
    assert supplied == content_fingerprint(value)
    assert value["three_state_clearance"] == {
        "states": ["BLOCKED", "CLEAR", "UNKNOWN"],
        "current_clear_supported": False,
        "unknown_is_clear": False,
        "known_positive_event_can_block_after_admission": True,
    }
    assert value["source_authority"] == {
        "earlier_authoritative_t_minus_5_source_proven": False,
        "complete_negative_absence_proof_proven": False,
        "analyst_broker_ai_estimate_allowed": False,
    }
    assert value["v1_active"] is True
    assert value["v2_active"] is False
    assert value["gate6_wired"] is False
