"""Static contract checks for the non-active horizon/timeframe policy candidate."""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path

from app.registry.canonical import DIAGNOSTIC_REGISTRY_VERSION, DIAGNOSTIC_RULES


_ROOT = Path(__file__).resolve().parents[2]
_POLICY_PATH = _ROOT / "docs" / "architecture" / "RULE_HORIZON_TIMEFRAME_APPLICABILITY_POLICY_V1_CANDIDATE.json"
_HORIZONS = ("SHORT_TERM", "POSITIONAL", "LONG_TERM")
_TIMEFRAMES = ("15m", "30m", "1H", "4H", "1D", "1W", "1M")
_APPLICABILITY = {"APPLICABLE", "CONTEXT", "NOT_APPLICABLE", "POLICY_UNSET"}
_ROLES = {"PRIMARY", "CONFIRMING", "CONTEXT", "EXECUTION", "NOT_USED", "POLICY_UNSET", "DATA_NOT_READY"}
_TECHNICAL_RULE_IDS = frozenset({
    *range(1, 15), 29, 31, 32, 34, *range(35, 47), *range(50, 62),
})


def _policy() -> dict[str, object]:
    return json.loads(_POLICY_PATH.read_text(encoding="utf-8"))


def _fingerprint(value: dict[str, object]) -> str:
    payload = dict(value)
    payload.pop("policy_fingerprint")
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return "sha256:" + sha256(encoded).hexdigest()


def test_candidate_is_complete_over_the_frozen_registry_and_three_horizons() -> None:
    policy = _policy()
    rows = policy["rule_horizon_rows"]

    assert policy["status"] == "CANDIDATE_NOT_ACTIVE"
    assert policy["canonical_registry_version"] == DIAGNOSTIC_REGISTRY_VERSION
    assert policy["canonical_horizons"] == list(_HORIZONS)
    assert policy["horizon_duration_boundaries"] == "UNSET"
    assert [row["rule_id"] for row in rows] == [rule.rule_id for rule in DIAGNOSTIC_RULES]
    assert len(rows) * len(_HORIZONS) == 183
    for row in rows:
        assert {row[horizon] for horizon in ("short_term", "positional", "long_term")} <= _APPLICABILITY


def test_candidate_technical_profiles_expand_without_fake_or_missing_timeframes() -> None:
    policy = _policy()
    rows = policy["rule_horizon_rows"]
    profiles = policy["technical_profiles"]
    profiled = {row["rule_id"] for row in rows if row["technical_profile"] is not None}

    assert tuple(policy["timeframes"]) == _TIMEFRAMES
    assert profiled == _TECHNICAL_RULE_IDS
    assert len(profiled) * len(_HORIZONS) * len(_TIMEFRAMES) == 882
    for row in rows:
        profile_id = row["technical_profile"]
        if profile_id is None:
            continue
        profile = profiles[profile_id]
        assert set(profile) == set(_HORIZONS)
        for horizon in _HORIZONS:
            assert set(profile[horizon]) == set(_TIMEFRAMES)
            assert set(profile[horizon].values()) <= _ROLES

    rule_14 = next(row for row in rows if row["rule_id"] == 14)
    profile_14 = profiles[rule_14["technical_profile"]]
    assert profile_14["POSITIONAL"]["1D"] == "POLICY_UNSET"
    assert profile_14["POSITIONAL"]["1W"] == "POLICY_UNSET"
    assert profile_14["POSITIONAL"]["4H"] == "DATA_NOT_READY"


def test_candidate_fingerprint_is_tamper_evident_and_rule_six_stays_partial() -> None:
    policy = _policy()
    rows = policy["rule_horizon_rows"]
    rule_6 = next(row for row in rows if row["rule_id"] == 6)

    assert policy["fingerprint_scheme"] == "sha256:utf8:canonical-json-v1"
    assert policy["policy_fingerprint"] == _fingerprint(policy)
    assert rule_6["short_term"] == "CONTEXT"
    assert rule_6["positional"] == "APPLICABLE"
    assert rule_6["long_term"] == "CONTEXT"
    assert policy["technical_profiles"][rule_6["technical_profile"]]["POSITIONAL"]["1D"] == "PRIMARY"
