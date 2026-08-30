"""Read-only governed Pre-Breakout setup eligibility composition.

This is deliberately the boundary *before* candidate assembly.  It composes
the selected-policy materializer and the existing current sector-rotation
report without recalculating either source or inferring an execution/fill.
"""
from __future__ import annotations

from dataclasses import dataclass, fields, is_dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from app.historical.guard import manifest_fingerprint

from app.strategies.pre_breakout.materialization import (
    GovernedPreBreakoutResolvedInputs,
    GovernedPreBreakoutStructuralResult,
    PreBreakoutResolvedInputStatus,
    PreBreakoutStructuralStatus,
)


class PreBreakoutSetupBlockerCategory(StrEnum):
    GOVERNANCE_BLOCKER = "GOVERNANCE_BLOCKER"
    DATA_BLOCKER = "DATA_BLOCKER"
    SECTOR_BLOCKER = "SECTOR_BLOCKER"
    TECHNICAL_SETUP_FAIL = "TECHNICAL_SETUP_FAIL"
    STRUCTURAL_SETUP_FAIL = "STRUCTURAL_SETUP_FAIL"
    ENTRY_ECONOMICS_FAIL = "ENTRY_ECONOMICS_FAIL"


class PreBreakoutSetupAssessmentStatus(StrEnum):
    ELIGIBLE_TO_FORM_CANDIDATE = "ELIGIBLE_TO_FORM_CANDIDATE"
    BLOCKED_GOVERNANCE = "BLOCKED_GOVERNANCE"
    BLOCKED_DATA = "BLOCKED_DATA"
    BLOCKED_SECTOR = "BLOCKED_SECTOR"
    BLOCKED_TECHNICAL_SETUP = "BLOCKED_TECHNICAL_SETUP"
    BLOCKED_STRUCTURAL_SETUP = "BLOCKED_STRUCTURAL_SETUP"
    BLOCKED_ENTRY_ECONOMICS = "BLOCKED_ENTRY_ECONOMICS"


@dataclass(frozen=True, slots=True)
class PreBreakoutSetupBlocker:
    category: PreBreakoutSetupBlockerCategory
    code: str


@dataclass(frozen=True, slots=True)
class GovernedPreBreakoutSetupAssessment:
    """Immutable setup qualification only; never a candidate, signal, or order."""

    instrument_id: str
    evaluation_as_of: datetime
    evaluation_session: datetime | None
    status: PreBreakoutSetupAssessmentStatus
    candidate_formation_eligible: bool
    policy_id: str | None
    policy_version: str | None
    policy_fingerprint: str | None
    selection_id: str | None
    selection_fingerprint: str | None
    sector: str | None
    sector_rotation_status: str
    top3_sector_membership: bool | None
    sector_rotation_as_of: datetime | None
    sector_rotation_warnings: tuple[str, ...]
    technical_inputs: GovernedPreBreakoutResolvedInputs
    structural: GovernedPreBreakoutStructuralResult
    actual_execution_status: str | None
    blockers: tuple[PreBreakoutSetupBlocker, ...]
    warnings: tuple[str, ...]

    @property
    def fingerprint(self) -> str:
        """Deterministic identity of every persisted assessment-semantic field."""
        return prebreakout_setup_assessment_fingerprint(self)

    @property
    def assessment_id(self) -> str:
        """Stable immutable identifier derived from the canonical assessment."""
        return f"prebreakout-setup-assessment:{self.fingerprint[:32]}"


def prebreakout_setup_assessment_fingerprint(value: GovernedPreBreakoutSetupAssessment) -> str:
    """Fingerprint all semantic assessment fields without object-repr hashing."""
    if not isinstance(value, GovernedPreBreakoutSetupAssessment):
        raise ValueError("PRE_BREAKOUT_SETUP_ASSESSMENT_REQUIRED")
    return manifest_fingerprint(**{
        field.name: _semantic_assessment_value(getattr(value, field.name))
        for field in fields(value)
    })


def _semantic_assessment_value(value):
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, tuple):
        return tuple(_semantic_assessment_value(item) for item in value)
    if is_dataclass(value):
        return {
            field.name: _semantic_assessment_value(getattr(value, field.name))
            for field in fields(value)
        }
    return value


class GovernedPreBreakoutSetupAssessmentService:
    """Compose existing governed evidence into the pre-candidate boundary.

    Both collaborators are read-only.  The materializer resolves the selected
    policy at ``as_of``; the rotation service produces its existing stored-only
    Top-3 report at that same boundary.  This class intentionally contains no
    ranking, score, candidate, execution, or provider behavior.
    """

    def __init__(self, *, materializer, sector_rotation_service) -> None:
        self._materializer = materializer
        self._sector_rotation = sector_rotation_service

    def assess_prebreakout_setup(
        self, instrument_id: str, *, as_of: datetime, sector_rotation=None,
    ) -> GovernedPreBreakoutSetupAssessment:
        technical = self._materializer.materialize(instrument_id=instrument_id, as_of=as_of)
        structural = self._materializer.materialize_structure(instrument_id=instrument_id, as_of=as_of)
        blockers = _governance_blockers(technical, structural)

        # A missing or inconsistent selected-policy lineage is fail-closed and
        # does not need a sector report to explain why no setup can form.
        if blockers:
            return _assessment(
                technical, structural, status=_status(blockers), blockers=blockers,
            )

        # A bounded source scan computes one exact stored-only rotation report
        # at its decision cutoff.  Reusing that identical report for each
        # constituent avoids recomputing the same sector evidence hundreds of
        # times; callers without it retain the established materialization.
        rotation = sector_rotation if sector_rotation is not None else self._sector_rotation.assess(as_of=as_of)
        sector_rows = tuple(item for item in rotation.constituents if item.instrument_id == instrument_id)
        if not sector_rows:
            blockers.append(_block(PreBreakoutSetupBlockerCategory.DATA_BLOCKER, "SECTOR_ROTATION_UNAVAILABLE"))
            return _assessment(technical, structural, status=_status(blockers), blockers=blockers,
                               sector_rotation=rotation)
        sectors = tuple(sorted({item.sector for item in sector_rows}))
        if len(sectors) != 1:
            blockers.append(_block(PreBreakoutSetupBlockerCategory.DATA_BLOCKER, "SECTOR_MEMBERSHIP_CONFLICT"))
            return _assessment(technical, structural, status=_status(blockers), blockers=blockers,
                               sector_rotation=rotation, sector=sectors[0] if sectors else None)
        sector = sectors[0]
        unavailable = next((item for item in getattr(rotation, "relative_strength", ()) if item.sector == sector and item.exclusion_reason is not None), None)
        if unavailable is not None:
            # A stock in a sector without governed index evidence cannot move
            # through the top-down path via a stock-only fallback.
            blockers.append(_block(PreBreakoutSetupBlockerCategory.SECTOR_BLOCKER, "SECTOR_RANKING_UNAVAILABLE"))
            return _assessment(
                technical, structural, status=_status(blockers), blockers=blockers,
                sector_rotation=rotation, sector=sector,
                sector_rotation_status=f"SECTOR_RANKING_UNAVAILABLE:{unavailable.exclusion_reason}",
            )
        if sector not in rotation.top3:
            blockers.append(_block(PreBreakoutSetupBlockerCategory.SECTOR_BLOCKER, "NOT_IN_TOP3_SECTOR"))

        blockers.extend(_technical_blockers(technical))
        blockers.extend(_structural_blockers(structural))
        return _assessment(technical, structural, status=_status(blockers), blockers=blockers,
                           sector_rotation=rotation, sector=sector)


def _governance_blockers(
    technical: GovernedPreBreakoutResolvedInputs,
    structural: GovernedPreBreakoutStructuralResult,
) -> list[PreBreakoutSetupBlocker]:
    values: list[PreBreakoutSetupBlocker] = []
    if technical.status is PreBreakoutResolvedInputStatus.GOVERNANCE_UNAVAILABLE:
        values.append(_block(PreBreakoutSetupBlockerCategory.GOVERNANCE_BLOCKER, "SELECTED_POLICY_UNAVAILABLE"))
    if structural.status is PreBreakoutStructuralStatus.POLICY_SEMANTICS_UNAVAILABLE:
        values.append(_block(PreBreakoutSetupBlockerCategory.GOVERNANCE_BLOCKER, "POLICY_STRUCTURAL_SEMANTICS_UNAVAILABLE"))
    if technical.unresolved_fields:
        values.extend(
            _block(PreBreakoutSetupBlockerCategory.GOVERNANCE_BLOCKER, f"POLICY_UNRESOLVED:{field}")
            for field in technical.unresolved_fields
        )
    lineage = (
        technical.policy_id, technical.policy_version, technical.policy_fingerprint,
        technical.selection_id, technical.selection_fingerprint,
    )
    structural_lineage = (
        structural.policy_id, structural.policy_version, structural.policy_fingerprint,
        structural.selection_id, structural.selection_fingerprint,
    )
    if any(lineage) and any(structural_lineage) and lineage != structural_lineage:
        values.append(_block(PreBreakoutSetupBlockerCategory.GOVERNANCE_BLOCKER, "POLICY_SELECTION_LINEAGE_MISMATCH"))
    if structural.status is PreBreakoutStructuralStatus.POLICY_GEOMETRY_CONFLICT or structural.policy_semantic_conflict:
        values.append(_block(PreBreakoutSetupBlockerCategory.GOVERNANCE_BLOCKER, "POLICY_SEMANTIC_CONFLICT"))
    return values


def _technical_blockers(value: GovernedPreBreakoutResolvedInputs) -> list[PreBreakoutSetupBlocker]:
    values: list[PreBreakoutSetupBlocker] = []
    checks = (
        (value.bbw_pass, "BBW_PERCENTILE_UNAVAILABLE", "BBW_NOT_COMPRESSED"),
        (value.atr_contraction_pass, "ATR_CONTRACTION_UNAVAILABLE", "ATR_NOT_CONTRACTING"),
        (value.volume_dry_up_pass, "VOLUME_DRY_UP_UNAVAILABLE", "VOLUME_NOT_DRY"),
        (value.delivery_pass, "OFFICIAL_DELIVERY_UNAVAILABLE", "DELIVERY_NOT_ABOVE_THRESHOLD"),
        (value.distance_from_high_pass, "HIGH_252_UNAVAILABLE", "HIGH_DISTANCE_OUTSIDE_RANGE"),
        (value.rsi_pass, "RSI14_UNAVAILABLE", "RSI_OUTSIDE_RANGE"),
    )
    for passed, unavailable, failed in checks:
        if passed is None:
            values.append(_block(PreBreakoutSetupBlockerCategory.DATA_BLOCKER, unavailable))
        elif not passed:
            values.append(_block(PreBreakoutSetupBlockerCategory.TECHNICAL_SETUP_FAIL, failed))
    return values


def _structural_blockers(value: GovernedPreBreakoutStructuralResult) -> list[PreBreakoutSetupBlocker]:
    if value.status is PreBreakoutStructuralStatus.STRUCTURAL_ENTRY_READY:
        required = (
            value.selected_base, value.trigger, value.structural_support, value.final_stop,
            value.target, value.tick_size, value.entry_reference_price,
            value.maximum_acceptable_entry_price, value.maximum_executable_entry_price,
            value.entry_reference_risk, value.entry_reference_reward, value.entry_reference_rr,
        )
        if (
            all(item is not None for item in required)
            and value.support_breached is False
            and value.support_grid_aligned is True
            and value.target_grid_aligned is True
            and value.actual_execution_price is None
            and value.actual_execution_status == "NOT_EVALUATED_AT_SCAN"
            and value.entry_reference_price > value.final_stop
            and value.entry_reference_price < value.trigger
            and value.entry_reference_price <= value.maximum_executable_entry_price
            and value.entry_reference_risk > 0
            and value.entry_reference_reward > 0
            and value.entry_reference_rr_pass is True
        ):
            return []
        return [_block(PreBreakoutSetupBlockerCategory.DATA_BLOCKER, "ENTRY_ECONOMICS_UNAVAILABLE")]
    if value.status is PreBreakoutStructuralStatus.STRUCTURAL_READY:
        # V1.2 is retained exactly as it was evaluated.  It did not define the
        # V1.3 reference-entry boundary, so it cannot be silently promoted to
        # a current candidate-forming setup.
        return [_block(
            PreBreakoutSetupBlockerCategory.ENTRY_ECONOMICS_FAIL,
            "ENTRY_ECONOMICS_NOT_MATERIALIZED_FOR_POLICY_VERSION",
        )]
    if value.status in {
        PreBreakoutStructuralStatus.TICK_SIZE_UNAVAILABLE,
        PreBreakoutStructuralStatus.REFERENCE_DATA_CONFLICT,
        PreBreakoutStructuralStatus.DATA_UNAVAILABLE,
    }:
        return [_block(PreBreakoutSetupBlockerCategory.DATA_BLOCKER, code) for code in value.blockers]
    if value.status in {
        PreBreakoutStructuralStatus.INVALID_PRE_BREAKOUT_ENTRY_GEOMETRY,
        PreBreakoutStructuralStatus.NO_VALID_PRE_BREAKOUT_ENTRY_PRICE,
        PreBreakoutStructuralStatus.PRE_BREAKOUT_ENTRY_NOT_AVAILABLE,
        PreBreakoutStructuralStatus.ENTRY_RR_FAIL,
    }:
        return [_block(PreBreakoutSetupBlockerCategory.ENTRY_ECONOMICS_FAIL, code) for code in value.blockers]
    if value.status is PreBreakoutStructuralStatus.POLICY_GEOMETRY_CONFLICT:
        return []  # already represented precisely as a governance conflict.
    return [_block(PreBreakoutSetupBlockerCategory.STRUCTURAL_SETUP_FAIL, code) for code in value.blockers]


def _assessment(
    technical: GovernedPreBreakoutResolvedInputs,
    structural: GovernedPreBreakoutStructuralResult,
    *, status: PreBreakoutSetupAssessmentStatus,
    blockers: list[PreBreakoutSetupBlocker],
    sector_rotation=None,
    sector: str | None = None,
    sector_rotation_status: str | None = None,
) -> GovernedPreBreakoutSetupAssessment:
    ordered = tuple(sorted(set(blockers), key=lambda item: (item.category.value, item.code)))
    return GovernedPreBreakoutSetupAssessment(
        instrument_id=technical.instrument_id,
        evaluation_as_of=technical.evaluation_as_of,
        evaluation_session=technical.evaluation_session or structural.evaluation_session,
        status=status,
        candidate_formation_eligible=status is PreBreakoutSetupAssessmentStatus.ELIGIBLE_TO_FORM_CANDIDATE,
        policy_id=technical.policy_id,
        policy_version=technical.policy_version,
        policy_fingerprint=technical.policy_fingerprint,
        selection_id=technical.selection_id,
        selection_fingerprint=technical.selection_fingerprint,
        sector=sector,
        sector_rotation_status=sector_rotation_status or (
            "SECTOR_ROTATION_UNAVAILABLE" if sector_rotation is None or sector is None else
            "TOP3_ELIGIBLE" if sector in sector_rotation.top3 else "NOT_IN_TOP3_SECTOR"
        ),
        top3_sector_membership=(None if sector_rotation is None or sector is None else sector in sector_rotation.top3),
        sector_rotation_as_of=(None if sector_rotation is None else sector_rotation.generated_at),
        sector_rotation_warnings=(() if sector_rotation is None else tuple(sector_rotation.warnings)),
        technical_inputs=technical,
        structural=structural,
        actual_execution_status=structural.actual_execution_status,
        blockers=ordered,
        warnings=(),
    )


def _status(blockers: list[PreBreakoutSetupBlocker]) -> PreBreakoutSetupAssessmentStatus:
    if not blockers:
        return PreBreakoutSetupAssessmentStatus.ELIGIBLE_TO_FORM_CANDIDATE
    order = (
        (PreBreakoutSetupBlockerCategory.GOVERNANCE_BLOCKER, PreBreakoutSetupAssessmentStatus.BLOCKED_GOVERNANCE),
        (PreBreakoutSetupBlockerCategory.DATA_BLOCKER, PreBreakoutSetupAssessmentStatus.BLOCKED_DATA),
        (PreBreakoutSetupBlockerCategory.SECTOR_BLOCKER, PreBreakoutSetupAssessmentStatus.BLOCKED_SECTOR),
        (PreBreakoutSetupBlockerCategory.TECHNICAL_SETUP_FAIL, PreBreakoutSetupAssessmentStatus.BLOCKED_TECHNICAL_SETUP),
        (PreBreakoutSetupBlockerCategory.STRUCTURAL_SETUP_FAIL, PreBreakoutSetupAssessmentStatus.BLOCKED_STRUCTURAL_SETUP),
        (PreBreakoutSetupBlockerCategory.ENTRY_ECONOMICS_FAIL, PreBreakoutSetupAssessmentStatus.BLOCKED_ENTRY_ECONOMICS),
    )
    categories = {item.category for item in blockers}
    return next(status for category, status in order if category in categories)


def _block(category: PreBreakoutSetupBlockerCategory, code: str) -> PreBreakoutSetupBlocker:
    return PreBreakoutSetupBlocker(category, code)
