from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.strategies.pre_breakout.materialization import (
    GovernedPreBreakoutResolvedInputs,
    GovernedPreBreakoutStructuralResult,
    PreBreakoutResolvedInputStatus,
    PreBreakoutStructuralStatus,
)
from app.strategies.pre_breakout.setup_assessment import (
    GovernedPreBreakoutSetupAssessmentService,
    PreBreakoutSetupAssessmentStatus,
    PreBreakoutSetupBlockerCategory,
)


T = datetime(2026, 8, 28, 12, tzinfo=UTC)
INSTRUMENT_ID = "NSE:SETUP"


def _technical(**changes) -> GovernedPreBreakoutResolvedInputs:
    value = GovernedPreBreakoutResolvedInputs(
        instrument_id=INSTRUMENT_ID, evaluation_as_of=T, evaluation_session=T,
        status=PreBreakoutResolvedInputStatus.PARTIAL_POLICY_BLOCKED,
        policy_id="pre-breakout-policy-v1", policy_version="v1.3-draft", policy_fingerprint="v13-policy",
        selection_id="selection-v13", selection_fingerprint="selection-v13-fingerprint",
        canonical_session_count=252, latest_close=Decimal("470"),
        bbw_percentile=Decimal("10"), bbw_pass=True,
        current_atr14=Decimal("1"), previous_5_atr14=(Decimal("2"),) * 5,
        previous_5_atr14_mean=Decimal("2"), atr_contraction_pass=True, atr_observation_session=T,
        rsi14=Decimal("60"), rsi_pass=True,
        official_delivery_pct=Decimal("61"), delivery_pass=True,
        high_252=Decimal("500"), high_252_session_count=252,
        distance_below_high_pct=Decimal("6"), distance_from_high_pass=True,
        current_volume=499_999, sma20_volume=Decimal("1000000"), volume_dry_up_status="PASS",
        prior_20_volumes=(1_000_000,) * 20, prior_20_volume_mean=Decimal("1000000"),
        volume_threshold_ratio=Decimal("0.50"), volume_threshold_value=Decimal("500000"),
        volume_operator="STRICT_LESS_THAN", volume_dry_up_pass=True, volume_evaluation_session=T,
        unresolved_fields=(), blockers=(),
    )
    return replace(value, **changes)


def _structural(**changes) -> GovernedPreBreakoutStructuralResult:
    value = GovernedPreBreakoutStructuralResult(
        instrument_id=INSTRUMENT_ID, evaluation_as_of=T, evaluation_session=T,
        status=PreBreakoutStructuralStatus.STRUCTURAL_ENTRY_READY,
        policy_id="pre-breakout-policy-v1", policy_version="v1.3-draft", policy_fingerprint="v13-policy",
        selection_id="selection-v13", selection_fingerprint="selection-v13-fingerprint",
        canonical_session_count=252, valid_window_count=1, selected_base=SimpleNamespace(base_top=Decimal("500")),
        resistance=Decimal("500"), trigger=Decimal("500"), support_pivot=SimpleNamespace(price=Decimal("450")),
        structural_support=Decimal("450"), support_breached=False, tick_resolution_status="AVAILABLE",
        tick_size=Decimal("0.05"), tick_record_id="tick-1", support_grid_aligned=True,
        final_stop=Decimal("449.95"), target=Decimal("550"), target_grid_aligned=True,
        risk=None, reward=None, actual_rr=None, rr_pass=None, blockers=(),
        breakout_confirmation_trigger=Decimal("500"), breakout_trigger_role="CONFIRMATION_NOT_INITIAL_ENTRY",
        entry_reference_price=Decimal("470"), entry_reference_session=T,
        entry_reference_geometry_status="PASS", maximum_acceptable_entry_price=Decimal("474.9625"),
        maximum_executable_entry_price=Decimal("474.95"), entry_reference_risk=Decimal("20.05"),
        entry_reference_reward=Decimal("80"), entry_reference_rr=Decimal("80") / Decimal("20.05"),
        entry_reference_rr_pass=True, actual_execution_price=None, actual_execution_status="NOT_EVALUATED_AT_SCAN",
        entry_economics_status="PASS", policy_semantic_conflict=False,
    )
    return replace(value, **changes)


class _Materializer:
    def __init__(self, technical=None, structural=None) -> None:
        self.technical = technical or _technical()
        self.structural = structural or _structural()
        self.calls: list[tuple[str, datetime]] = []

    def materialize(self, *, instrument_id: str, as_of: datetime):
        self.calls.append((instrument_id, as_of)); return self.technical

    def materialize_structure(self, *, instrument_id: str, as_of: datetime):
        self.calls.append((instrument_id, as_of)); return self.structural


class _Rotation:
    def __init__(self, *, sector="Metals", top3=("Metals",), membership=True, exclusion_reason=None) -> None:
        self.sector, self.top3, self.membership = sector, top3, membership
        self.exclusion_reason = exclusion_reason
        self.calls: list[datetime] = []

    def assess(self, *, as_of: datetime):
        self.calls.append(as_of)
        values = (SimpleNamespace(instrument_id=INSTRUMENT_ID, sector=self.sector),) if self.membership else ()
        relative_strength = () if self.exclusion_reason is None else (
            SimpleNamespace(sector=self.sector, exclusion_reason=self.exclusion_reason),
        )
        return SimpleNamespace(generated_at=as_of, constituents=values, top3=self.top3,
                               relative_strength=relative_strength, warnings=("STORED_ONLY",))


def _service(*, technical=None, structural=None, rotation=None):
    materializer = _Materializer(technical, structural)
    rotation = rotation or _Rotation()
    return GovernedPreBreakoutSetupAssessmentService(materializer=materializer, sector_rotation_service=rotation), materializer, rotation


def _codes(value):
    return {(item.category, item.code) for item in value.blockers}


def test_v13_all_governed_conditions_pass_at_explicit_as_of_without_candidate_or_execution() -> None:
    service, materializer, rotation = _service()
    result = service.assess_prebreakout_setup(INSTRUMENT_ID, as_of=T)
    assert result.status is PreBreakoutSetupAssessmentStatus.ELIGIBLE_TO_FORM_CANDIDATE
    assert result.candidate_formation_eligible and result.sector == "Metals"
    assert result.top3_sector_membership is True and result.sector_rotation_as_of == T
    assert result.actual_execution_status == "NOT_EVALUATED_AT_SCAN"
    assert materializer.calls == [(INSTRUMENT_ID, T), (INSTRUMENT_ID, T)] and rotation.calls == [T]
    assert not any(hasattr(result, name) for name in ("candidate", "ranking", "score", "signal", "order", "paper_trade", "six_gates"))


def test_explicit_as_of_is_required() -> None:
    service, _, _ = _service()
    with pytest.raises(TypeError):
        service.assess_prebreakout_setup(INSTRUMENT_ID)  # type: ignore[call-arg]


def test_selected_governance_is_required_and_prevents_sector_call() -> None:
    technical = _technical(status=PreBreakoutResolvedInputStatus.GOVERNANCE_UNAVAILABLE, policy_id=None, policy_version=None,
                           policy_fingerprint=None, selection_id=None, selection_fingerprint=None)
    structural = _structural(status=PreBreakoutStructuralStatus.POLICY_SEMANTICS_UNAVAILABLE, policy_id=None,
                             policy_version=None, policy_fingerprint=None, selection_id=None, selection_fingerprint=None)
    service, _, rotation = _service(technical=technical, structural=structural)
    result = service.assess_prebreakout_setup(INSTRUMENT_ID, as_of=T)
    assert result.status is PreBreakoutSetupAssessmentStatus.BLOCKED_GOVERNANCE
    assert (PreBreakoutSetupBlockerCategory.GOVERNANCE_BLOCKER, "SELECTED_POLICY_UNAVAILABLE") in _codes(result)
    assert rotation.calls == []


def test_historical_v12_policy_geometry_conflict_is_preserved_without_v13_reinterpretation() -> None:
    technical = _technical(policy_version="v1.2-draft", policy_fingerprint="v12-policy", selection_id="selection-v12",
                           selection_fingerprint="selection-v12-fingerprint")
    structural = _structural(
        status=PreBreakoutStructuralStatus.POLICY_GEOMETRY_CONFLICT, policy_version="v1.2-draft",
        policy_fingerprint="v12-policy", selection_id="selection-v12", selection_fingerprint="selection-v12-fingerprint",
        actual_execution_status=None, entry_reference_price=None, maximum_acceptable_entry_price=None,
        maximum_executable_entry_price=None, entry_reference_risk=None, entry_reference_reward=None,
        entry_reference_rr=None, entry_reference_rr_pass=None, policy_semantic_conflict=True,
        blockers=("RR_FAIL", "POLICY_GEOMETRY_CONFLICT"),
    )
    service, _, _ = _service(technical=technical, structural=structural)
    result = service.assess_prebreakout_setup(INSTRUMENT_ID, as_of=T - timedelta(days=1))
    assert result.policy_version == "v1.2-draft"
    assert result.status is PreBreakoutSetupAssessmentStatus.BLOCKED_GOVERNANCE
    assert (PreBreakoutSetupBlockerCategory.GOVERNANCE_BLOCKER, "POLICY_SEMANTIC_CONFLICT") in _codes(result)


def test_historical_v12_structural_ready_is_not_silently_promoted_to_v13_entry_eligibility() -> None:
    technical = _technical(policy_version="v1.2-draft", policy_fingerprint="v12-policy", selection_id="selection-v12",
                           selection_fingerprint="selection-v12-fingerprint")
    structural = _structural(
        status=PreBreakoutStructuralStatus.STRUCTURAL_READY, policy_version="v1.2-draft",
        policy_fingerprint="v12-policy", selection_id="selection-v12", selection_fingerprint="selection-v12-fingerprint",
        actual_execution_status=None, entry_reference_price=None, maximum_acceptable_entry_price=None,
        maximum_executable_entry_price=None, entry_reference_risk=None, entry_reference_reward=None,
        entry_reference_rr=None, entry_reference_rr_pass=None, policy_semantic_conflict=False,
    )
    service, _, _ = _service(technical=technical, structural=structural)
    result = service.assess_prebreakout_setup(INSTRUMENT_ID, as_of=T - timedelta(days=1))
    assert result.status is PreBreakoutSetupAssessmentStatus.BLOCKED_ENTRY_ECONOMICS
    assert (PreBreakoutSetupBlockerCategory.ENTRY_ECONOMICS_FAIL,
            "ENTRY_ECONOMICS_NOT_MATERIALIZED_FOR_POLICY_VERSION") in _codes(result)
    assert not any(item.code == "POLICY_SEMANTIC_CONFLICT" for item in result.blockers)


def test_top3_membership_passes_and_non_top3_is_clean_sector_rejection() -> None:
    service, _, _ = _service(rotation=_Rotation(top3=("Metals",)))
    passed = service.assess_prebreakout_setup(INSTRUMENT_ID, as_of=T)
    service, _, _ = _service(rotation=_Rotation(top3=("Realty",)))
    rejected = service.assess_prebreakout_setup(INSTRUMENT_ID, as_of=T)
    assert passed.top3_sector_membership is True and passed.candidate_formation_eligible
    assert rejected.status is PreBreakoutSetupAssessmentStatus.BLOCKED_SECTOR
    assert (PreBreakoutSetupBlockerCategory.SECTOR_BLOCKER, "NOT_IN_TOP3_SECTOR") in _codes(rejected)


def test_sector_unavailable_is_data_blocker_not_silent_sector_failure() -> None:
    service, _, _ = _service(rotation=_Rotation(membership=False))
    result = service.assess_prebreakout_setup(INSTRUMENT_ID, as_of=T)
    assert result.status is PreBreakoutSetupAssessmentStatus.BLOCKED_DATA
    assert result.sector_rotation_status == "SECTOR_ROTATION_UNAVAILABLE"
    assert (PreBreakoutSetupBlockerCategory.DATA_BLOCKER, "SECTOR_ROTATION_UNAVAILABLE") in _codes(result)


def test_excluded_sector_cannot_enter_top_down_prebreakout_candidate_path() -> None:
    service, _, _ = _service(rotation=_Rotation(sector="Construction", top3=("Construction",),
                                                  exclusion_reason="INSUFFICIENT_ALIGNED_120_SESSION_HISTORY"))
    result = service.assess_prebreakout_setup(INSTRUMENT_ID, as_of=T)
    assert result.status is PreBreakoutSetupAssessmentStatus.BLOCKED_SECTOR
    assert result.candidate_formation_eligible is False
    assert result.sector_rotation_status == "SECTOR_RANKING_UNAVAILABLE:INSUFFICIENT_ALIGNED_120_SESSION_HISTORY"
    assert (PreBreakoutSetupBlockerCategory.SECTOR_BLOCKER, "SECTOR_RANKING_UNAVAILABLE") in _codes(result)


@pytest.mark.parametrize(
    ("field", "code"),
    (
        ("bbw_pass", "BBW_NOT_COMPRESSED"),
        ("atr_contraction_pass", "ATR_NOT_CONTRACTING"),
        ("volume_dry_up_pass", "VOLUME_NOT_DRY"),
        ("delivery_pass", "DELIVERY_NOT_ABOVE_THRESHOLD"),
        ("distance_from_high_pass", "HIGH_DISTANCE_OUTSIDE_RANGE"),
        ("rsi_pass", "RSI_OUTSIDE_RANGE"),
    ),
)
def test_each_existing_technical_failure_remains_a_technical_setup_failure(field, code) -> None:
    service, _, _ = _service(technical=_technical(**{field: False}))
    result = service.assess_prebreakout_setup(INSTRUMENT_ID, as_of=T)
    assert result.status is PreBreakoutSetupAssessmentStatus.BLOCKED_TECHNICAL_SETUP
    assert (PreBreakoutSetupBlockerCategory.TECHNICAL_SETUP_FAIL, code) in _codes(result)
    assert not result.structural.policy_semantic_conflict


def test_missing_technical_evidence_is_data_not_technical_failure() -> None:
    service, _, _ = _service(technical=_technical(bbw_percentile=None, bbw_pass=None))
    result = service.assess_prebreakout_setup(INSTRUMENT_ID, as_of=T)
    assert result.status is PreBreakoutSetupAssessmentStatus.BLOCKED_DATA
    assert (PreBreakoutSetupBlockerCategory.DATA_BLOCKER, "BBW_PERCENTILE_UNAVAILABLE") in _codes(result)


@pytest.mark.parametrize(
    ("status", "blocker", "category"),
    (
        (PreBreakoutStructuralStatus.NO_VALID_BASE_WINDOW, "NO_VALID_WINDOW", PreBreakoutSetupBlockerCategory.STRUCTURAL_SETUP_FAIL),
        (PreBreakoutStructuralStatus.BASE_STRUCTURE_BROKEN, "BASE_STRUCTURE_BROKEN", PreBreakoutSetupBlockerCategory.STRUCTURAL_SETUP_FAIL),
        (PreBreakoutStructuralStatus.TICK_SIZE_UNAVAILABLE, "TICK_SIZE_UNAVAILABLE_FOR_AS_OF", PreBreakoutSetupBlockerCategory.DATA_BLOCKER),
        (PreBreakoutStructuralStatus.REFERENCE_DATA_CONFLICT, "REFERENCE_DATA_CONFLICT", PreBreakoutSetupBlockerCategory.DATA_BLOCKER),
        (PreBreakoutStructuralStatus.INVALID_PRE_BREAKOUT_ENTRY_GEOMETRY, "INVALID_PRE_BREAKOUT_ENTRY_GEOMETRY", PreBreakoutSetupBlockerCategory.ENTRY_ECONOMICS_FAIL),
        (PreBreakoutStructuralStatus.ENTRY_RR_FAIL, "ENTRY_RR_FAIL", PreBreakoutSetupBlockerCategory.ENTRY_ECONOMICS_FAIL),
    ),
)
def test_structural_tick_and_entry_blockers_keep_their_distinct_categories(status, blocker, category) -> None:
    service, _, _ = _service(structural=_structural(status=status, blockers=(blocker,), policy_semantic_conflict=False))
    result = service.assess_prebreakout_setup(INSTRUMENT_ID, as_of=T)
    assert (category, blocker) in _codes(result)
    expected = {
        PreBreakoutSetupBlockerCategory.DATA_BLOCKER: PreBreakoutSetupAssessmentStatus.BLOCKED_DATA,
        PreBreakoutSetupBlockerCategory.STRUCTURAL_SETUP_FAIL: PreBreakoutSetupAssessmentStatus.BLOCKED_STRUCTURAL_SETUP,
        PreBreakoutSetupBlockerCategory.ENTRY_ECONOMICS_FAIL: PreBreakoutSetupAssessmentStatus.BLOCKED_ENTRY_ECONOMICS,
    }[category]
    assert result.status is expected


def test_policy_selection_lineage_and_blocker_order_are_deterministic() -> None:
    technical = _technical(bbw_pass=False, rsi_pass=False)
    structural = _structural(status=PreBreakoutStructuralStatus.ENTRY_RR_FAIL, blockers=("ENTRY_RR_FAIL",))
    service, _, _ = _service(technical=technical, structural=structural, rotation=_Rotation(top3=("Realty",)))
    result = service.assess_prebreakout_setup(INSTRUMENT_ID, as_of=T)
    assert (result.policy_id, result.policy_version, result.policy_fingerprint, result.selection_id) == (
        "pre-breakout-policy-v1", "v1.3-draft", "v13-policy", "selection-v13",
    )
    assert result.blockers == tuple(sorted(result.blockers, key=lambda item: (item.category.value, item.code)))
    assert result.status is PreBreakoutSetupAssessmentStatus.BLOCKED_SECTOR
