"""Deterministic validation for the bounded official-source research receipt."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RECEIPT = ROOT / "docs" / "architecture" / "EARNINGS_CALENDAR_ALTERNATIVE_OFFICIAL_SOURCE_RESEARCH_V1_RECEIPT.json"


def _receipt() -> dict[str, object]:
    return json.loads(RECEIPT.read_text(encoding="utf-8"))


def _fingerprint(value: dict[str, object]) -> str:
    body = dict(value)
    body.pop("receipt_fingerprint")
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return "sha256:" + hashlib.sha256(canonical.encode("ascii")).hexdigest()


def test_cross_store_identity_audit_is_complete_and_fail_closed():
    value = _receipt()
    audit = value["identity_audit"]
    rows = audit["rows"]
    assert audit["population_count"] == 31
    assert len(rows) == 31
    assert len({row[0] for row in rows}) == 31
    assert all(row[0].startswith("NSE:IN") for row in rows)
    assert all(row[2].isdigit() and len(row[2]) == 6 for row in rows)
    classes = [row[-1] for row in rows]
    assert classes.count("CANONICAL_IDENTITY_EXISTS_ADAPTER_READER_MISALIGNED") == 30
    assert classes.count("IDENTITY_EXISTS_BUT_NOT_EFFECTIVE_FOR_DATE") == 1
    assert audit["reader_blocker"] == "INTERNAL_IDENTITY_BRIDGE"
    assert audit["classification_counts"]["CANONICAL_IDENTITY_GENUINELY_MISSING"] == 0


def test_source_research_does_not_convert_a_surface_or_identity_into_clearance():
    value = _receipt()
    governance = value["governance"]
    probes = value["source_probes"]
    options = value["source_option_matrix"]
    target_probe = value["target_historical_probe"]
    boundary = value["time_and_join_boundary"]
    outcome = value["outcome"]
    assert governance["NO_UNVERIFIED_CALENDAR_CLEARANCE"] is True
    assert governance["NO_NAME_BASED_IDENTITY"] is True
    assert governance["NO_UNDOCUMENTED_PRIVATE_SOURCE"] is True
    assert all(probes[name]["source_state"] == "SOURCE_AVAILABLE" for name in (
        "nse_event_calendar", "nse_board_meetings", "nse_announcements", "nse_archive_ixbrl", "bse_public_alternative"))
    assert boundary["timezone_assumed"] is False
    assert boundary["known_at_authority"] == "UNPROVEN"
    assert boundary["target_current_event"] == "CURRENT_EVENT_UNKNOWN_BECAUSE_WINDOW_INCOMPLETE"
    assert boundary["complete_window"] == "UNPROVEN"
    assert set(options) == {
        "NSE_EVENT_CALENDAR", "NSE_BOARD_MEETINGS", "NSE_ANNOUNCEMENTS",
        "NSE_PRIOR_INTIMATION_XBRL", "BSE_BOARD_MEETINGS", "BSE_ANNOUNCEMENTS",
        "BSE_PRIOR_INTIMATION_STRUCTURED", "PRIMARY_ISSUER_WEBSITE_FALLBACK",
    }
    assert set(target_probe) == {"APARINDS", "DEEPINDS", "GENUSPOWER", "GLAND", "ICICIBANK"}
    assert all(probes[name]["target_symbol_http_200"] == ["APARINDS", "DEEPINDS", "GENUSPOWER", "GLAND", "ICICIBANK"]
               for name in ("nse_event_calendar", "nse_board_meetings", "nse_announcements"))
    assert outcome == {
        "classification": "B",
        "label": "SOURCE_AVAILABLE_IDENTITY_BRIDGE_BLOCKED",
        "dominant_blocker": "INTERNAL_IDENTITY_BRIDGE",
        "next_slice": "EARNINGS_CALENDAR_CANONICAL_IDENTITY_BRIDGE_V1",
        "next_slice_started": False,
        "gate6_ready": False,
    }


def test_receipt_fingerprint_replays_without_network_or_database_access():
    value = _receipt()
    assert value["receipt_fingerprint"] == _fingerprint(value)
