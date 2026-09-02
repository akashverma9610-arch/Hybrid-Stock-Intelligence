from __future__ import annotations

import ast
from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime, timedelta, timezone
import inspect
from pathlib import Path

import pytest

import app.intelligence.market_extremes_assurance_projection as module
from app.crisis.models import (
    DistributionRisk,
    LeadershipQuality,
    MarketCycleStage,
    MarketExtremeLevel,
    PriceEarningsDivergence,
    UpsideExcessAssessment,
    UpsideExcessFactor,
    UpsideExcessState,
)
from app.intelligence.market_extremes_assurance_projection import (
    MARKET_EXTREMES_ASSURANCE_FINGERPRINT_SCHEME,
    MarketExtremesAssuranceCandidate,
    MarketExtremesAssuranceContext,
    MarketExtremesAssuranceError,
    MarketExtremesAssuranceReason,
    MarketExtremesAssuranceState,
    market_extremes_assurance_candidate,
    project_market_extremes_assurance,
    serialize_market_extremes_assurance,
)


T = datetime(2026, 9, 3, 10, 0, tzinfo=UTC)


def _assessment(
    *,
    assessment_id: str = "upside:one",
    state: UpsideExcessState = UpsideExcessState.EUPHORIA,
    data_as_of: datetime = T - timedelta(minutes=5),
    assessed_at: datetime = T - timedelta(minutes=2),
    policy_version: str = "upside-v1",
    entity_id: str = "NIFTY500",
    warning: str = "EUPHORIA_IS_NOT_TOP_CONFIRMATION",
) -> UpsideExcessAssessment:
    return UpsideExcessAssessment(
        assessment_id=assessment_id,
        policy_version=policy_version,
        level=MarketExtremeLevel.MARKET,
        entity_id=entity_id,
        excess_state=state,
        cycle_stage=MarketCycleStage.EUPHORIA if state is UpsideExcessState.EUPHORIA else MarketCycleStage.ACCELERATING,
        excess_score=None,
        confidence=0.8,
        top_confirmed=False,
        distribution_risk=DistributionRisk.NONE,
        leadership_quality=LeadershipQuality.HEALTHY,
        price_earnings_divergence=PriceEarningsDivergence.INSUFFICIENT_DATA,
        assessed_at=assessed_at,
        data_as_of=data_as_of,
        previous_state=None,
        transition_reason="MULTI_FACTOR_EXCESS_STATE",
        supporting_factors=(UpsideExcessFactor.PRICE_ACCELERATION,),
        contradicting_factors=(),
        unavailable_factors=(),
        warnings=(warning,),
        evidence_ids=("evidence:one",),
        provenance_ids=("provenance:one",),
    )


def _context(**overrides) -> MarketExtremesAssuranceContext:
    values = {
        "as_of": T,
        "freshness_floor": T - timedelta(hours=1),
        "expected_policy_version": "upside-v1",
        "expected_fingerprint_scheme": MARKET_EXTREMES_ASSURANCE_FINGERPRINT_SCHEME,
        "expected_entity_id": "NIFTY500",
    }
    values.update(overrides)
    return MarketExtremesAssuranceContext(**values)


def _candidate(*, snapshot_id: str = "snapshot:one", assessment: UpsideExcessAssessment | None = None):
    return market_extremes_assurance_candidate(
        snapshot_id=snapshot_id, assessment=assessment or _assessment(),
    )


def test_no_candidates_is_explicitly_unavailable():
    result = project_market_extremes_assurance(_context(), ())

    assert result.assurance_state is MarketExtremesAssuranceState.UNAVAILABLE
    assert result.selected_regime is None
    assert result.reason_codes == (MarketExtremesAssuranceReason.MARKET_EXTREMES_SNAPSHOT_UNAVAILABLE,)


def test_verified_euphoria_is_ready_without_profit_interpretation():
    result = project_market_extremes_assurance(_context(), (_candidate(),))

    assert result.assurance_state is MarketExtremesAssuranceState.READY
    assert result.selected_regime is UpsideExcessState.EUPHORIA
    assert result.selected_snapshot_id == "snapshot:one"
    assert result.reason_codes == ()
    assert result.verification_summary.pit_eligible_candidates == 1


def test_neutral_and_downside_regimes_remain_descriptive_core_states():
    normal = _candidate(assessment=_assessment(state=UpsideExcessState.NORMAL))
    breakdown = _candidate(snapshot_id="snapshot:breakdown", assessment=_assessment(assessment_id="upside:breakdown", state=UpsideExcessState.BREAKDOWN))

    normal_result = project_market_extremes_assurance(_context(), (normal,))
    breakdown_result = project_market_extremes_assurance(_context(), (breakdown,))

    assert normal_result.selected_regime is UpsideExcessState.NORMAL
    assert breakdown_result.selected_regime is UpsideExcessState.BREAKDOWN
    assert normal_result.assurance_state is breakdown_result.assurance_state is MarketExtremesAssuranceState.READY


def test_exact_duplicates_are_deduplicated_but_preserved_in_audit_lineage():
    candidate = _candidate()
    result = project_market_extremes_assurance(_context(), (candidate, candidate))

    assert result.assurance_state is MarketExtremesAssuranceState.READY
    assert result.verification_summary.unique_candidates == 1
    assert result.verification_summary.duplicate_candidates == 1
    assert any(MarketExtremesAssuranceReason.MARKET_EXTREMES_EXACT_DUPLICATE_CANDIDATE in item.reason_codes for item in result.rejected_candidate_references)


def test_fingerprint_mismatch_is_unverifiable_and_lineaged():
    bad = replace(_candidate(), stored_fingerprint="sha256:" + "0" * 64)
    result = project_market_extremes_assurance(_context(), (bad,))

    assert result.assurance_state is MarketExtremesAssuranceState.UNVERIFIABLE
    assert MarketExtremesAssuranceReason.MARKET_EXTREMES_FINGERPRINT_MISMATCH in result.reason_codes
    assert result.rejected_candidate_references[0].snapshot_id == "snapshot:one"


def test_tampered_identity_and_policy_version_fail_closed():
    bad_id = replace(_candidate(), snapshot_id="not a canonical id")
    bad_policy = _candidate(assessment=_assessment(policy_version="upside-v0"))

    identity = project_market_extremes_assurance(_context(), (bad_id,))
    policy = project_market_extremes_assurance(_context(), (bad_policy,))

    assert identity.assurance_state is MarketExtremesAssuranceState.UNVERIFIABLE
    assert MarketExtremesAssuranceReason.MARKET_EXTREMES_IDENTITY_INVALID in identity.reason_codes
    assert policy.assurance_state is MarketExtremesAssuranceState.UNVERIFIABLE
    assert MarketExtremesAssuranceReason.MARKET_EXTREMES_POLICY_VERSION_MISMATCH in policy.reason_codes


def test_future_only_and_mixed_future_candidates_are_pit_safe():
    future_assessment = _assessment(data_as_of=T + timedelta(minutes=1), assessed_at=T + timedelta(minutes=2))
    future = _candidate(snapshot_id="snapshot:future", assessment=future_assessment)
    eligible = _candidate()

    future_only = project_market_extremes_assurance(_context(), (future,))
    mixed = project_market_extremes_assurance(_context(), (future, eligible))

    assert future_only.assurance_state is MarketExtremesAssuranceState.TEMPORALLY_INVALID
    assert future_only.selected_regime is None
    assert future_only.reason_codes == (MarketExtremesAssuranceReason.MARKET_EXTREMES_AFTER_REQUESTED_AS_OF,)
    assert mixed.assurance_state is MarketExtremesAssuranceState.READY
    assert mixed.selected_snapshot_id == "snapshot:one"
    assert any(MarketExtremesAssuranceReason.MARKET_EXTREMES_AFTER_REQUESTED_AS_OF in item.reason_codes for item in mixed.rejected_candidate_references)


def test_stale_candidate_has_no_usable_regime_but_retains_selected_lineage():
    stale = _candidate(assessment=_assessment(data_as_of=T - timedelta(days=2), assessed_at=T - timedelta(days=2) + timedelta(minutes=1)))
    result = project_market_extremes_assurance(_context(), (stale,))

    assert result.assurance_state is MarketExtremesAssuranceState.STALE
    assert result.selected_regime is None
    assert result.selected_snapshot_id == "snapshot:one"
    assert result.reason_codes == (MarketExtremesAssuranceReason.MARKET_EXTREMES_STALE_AT_FRESHNESS_FLOOR,)


def test_freshness_floor_must_not_be_after_as_of():
    with pytest.raises(MarketExtremesAssuranceError, match="FRESHNESS_FLOOR_AFTER_AS_OF"):
        _context(freshness_floor=T + timedelta(seconds=1))


def test_same_timestamp_distinct_verified_content_is_conflicted():
    left = _candidate(snapshot_id="snapshot:left")
    right = _candidate(snapshot_id="snapshot:right", assessment=_assessment(assessment_id="upside:right", warning="OTHER_WARNING"))
    result = project_market_extremes_assurance(_context(), (left, right))

    assert result.assurance_state is MarketExtremesAssuranceState.CONFLICTED
    assert result.selected_regime is None
    assert result.reason_codes == (MarketExtremesAssuranceReason.MARKET_EXTREMES_SELECTED_TIMESTAMP_CONFLICT,)


def test_older_conflict_cannot_override_unique_newer_snapshot():
    old = T - timedelta(hours=2)
    left = _candidate(snapshot_id="snapshot:old-left", assessment=_assessment(assessment_id="upside:old-left", data_as_of=old, assessed_at=old + timedelta(minutes=1)))
    right = _candidate(snapshot_id="snapshot:old-right", assessment=_assessment(assessment_id="upside:old-right", data_as_of=old, assessed_at=old + timedelta(minutes=1), warning="OTHER"))
    newest = _candidate(snapshot_id="snapshot:new", assessment=_assessment(assessment_id="upside:new", data_as_of=T - timedelta(minutes=5), assessed_at=T - timedelta(minutes=2)))

    result = project_market_extremes_assurance(_context(), (left, right, newest))

    assert result.assurance_state is MarketExtremesAssuranceState.READY
    assert result.selected_snapshot_id == "snapshot:new"


def test_candidate_order_and_equivalent_timezones_are_deterministic():
    base = _candidate()
    india = timezone(timedelta(hours=5, minutes=30))
    timezone_equivalent = _candidate(
        assessment=replace(_assessment(), data_as_of=(T - timedelta(minutes=5)).astimezone(india), assessed_at=(T - timedelta(minutes=2)).astimezone(india)),
    )
    equivalent = _candidate(
        snapshot_id="snapshot:equivalent",
        assessment=replace(_assessment(assessment_id="upside:equivalent"), data_as_of=(T - timedelta(minutes=5)).astimezone(india), assessed_at=(T - timedelta(minutes=2)).astimezone(india)),
    )
    first = project_market_extremes_assurance(_context(), (base, equivalent))
    second = project_market_extremes_assurance(_context(), (equivalent, base))

    assert base.stored_fingerprint == timezone_equivalent.stored_fingerprint
    assert first.projection_id == second.projection_id
    assert serialize_market_extremes_assurance(first) == serialize_market_extremes_assurance(second)


def test_output_is_immutable_and_verify_detects_tampering():
    value = project_market_extremes_assurance(_context(), (_candidate(),))
    with pytest.raises(FrozenInstanceError):
        value.assurance_state = MarketExtremesAssuranceState.STALE

    object.__setattr__(value, "fingerprint", "sha256:" + "f" * 64)
    with pytest.raises(MarketExtremesAssuranceError, match="FINGERPRINT_MISMATCH"):
        value.verify()


def test_missing_provenance_is_unverifiable_and_never_silent():
    no_lineage = _candidate(assessment=replace(_assessment(), evidence_ids=(), provenance_ids=()))
    result = project_market_extremes_assurance(_context(), (no_lineage,))

    assert result.assurance_state is MarketExtremesAssuranceState.UNVERIFIABLE
    assert MarketExtremesAssuranceReason.MARKET_EXTREMES_PROVENANCE_UNVERIFIABLE in result.reason_codes


def test_projection_has_no_forbidden_dependencies_or_runtime_clock():
    source = Path(inspect.getfile(module)).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    } | {
        node.module or ""
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    }

    assert not any(name.startswith(prefix) for name in imports for prefix in (
        "app.storage", "app.api", "app.portfolio", "app.broker", "app.orders", "app.signals",
    ))
    assert "datetime.now" not in source and "datetime.utcnow" not in source
    assert all(term not in source.upper() for term in ("BUY", "SELL", "TRIM", "EXIT", "ROTATE"))


def test_candidate_type_is_immutable_and_public_contract_exposes_no_profit_fields():
    candidate = _candidate()
    with pytest.raises(FrozenInstanceError):
        candidate.snapshot_id = "changed"

    result = project_market_extremes_assurance(_context(), (candidate,))
    forbidden = {"profit", "order", "portfolio", "target", "quantity", "actionability"}
    assert not (forbidden & set(result.__dataclass_fields__))
    assert isinstance(candidate, MarketExtremesAssuranceCandidate)
