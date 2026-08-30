"""Frozen, evidence-derived sector-universe coverage governance for Production-V1.

The policy is deliberately about consumer readiness only.  It neither changes
the factual health of the ``INDEX_BARS`` refresh family nor creates sector
prices, rankings, candidates, or provider requests.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from app.historical.guard import manifest_fingerprint


class SectorUniverseCoverageApprovalStatus(StrEnum):
    APPROVED = "APPROVED"


class SectorUniverseCoverageState(StrEnum):
    READY_WITH_LIMITATION = "READY_WITH_LIMITATION"
    BLOCKED = "BLOCKED"


class SectorUniverseUnavailableBehavior(StrEnum):
    EXCLUDE_FROM_RANKING_AND_CANDIDATES = "EXCLUDE_FROM_RANKING_AND_CANDIDATES"


@dataclass(frozen=True, slots=True)
class SectorUniverseCoveragePolicy:
    """Immutable selected policy; eligibility is derived from stored evidence."""

    policy_id: str
    version: str
    proposal_policy_id: str
    proposal_version: str
    approval_status: SectorUniverseCoverageApprovalStatus
    approved_by: str
    selected_for_production_v1: bool
    active: bool
    benchmark_universe: str
    canonical_sector_universe_source: str
    required_rs_lookbacks: tuple[int, ...]
    required_breadth_status: str
    required_top_sector_count: int
    partial_operation_permitted: bool
    missing_sectors_are_p0_when_minimum_met: bool
    unavailable_sector_behavior: SectorUniverseUnavailableBehavior
    explicit_exclusion_disclosure_required: bool
    zero_score_fallback_permitted: bool
    fuzzy_substitution_permitted: bool
    synthetic_index_permitted: bool
    provenance: tuple[tuple[str, str], ...]
    fingerprint: str

    def __post_init__(self) -> None:
        if not all((self.policy_id, self.version, self.proposal_policy_id, self.proposal_version, self.approved_by, self.benchmark_universe, self.canonical_sector_universe_source)):
            raise ValueError("SECTOR_UNIVERSE_COVERAGE_POLICY_REQUIRED_FIELD")
        if not self.approved_by.startswith("human:"):
            raise ValueError("SECTOR_UNIVERSE_COVERAGE_POLICY_HUMAN_APPROVAL_REQUIRED")
        if self.approval_status is not SectorUniverseCoverageApprovalStatus.APPROVED or not self.selected_for_production_v1 or not self.active:
            raise ValueError("SECTOR_UNIVERSE_COVERAGE_POLICY_SELECTION_REQUIRED")
        if self.required_rs_lookbacks != tuple(sorted(set(self.required_rs_lookbacks))) or not self.required_rs_lookbacks:
            raise ValueError("SECTOR_UNIVERSE_COVERAGE_POLICY_LOOKBACKS_INVALID")
        if self.required_top_sector_count < 1:
            raise ValueError("SECTOR_UNIVERSE_COVERAGE_POLICY_TOP_COUNT_INVALID")
        if not self.partial_operation_permitted or self.missing_sectors_are_p0_when_minimum_met:
            raise ValueError("SECTOR_UNIVERSE_COVERAGE_POLICY_PARTIAL_OPERATION_REQUIRED")
        if self.unavailable_sector_behavior is not SectorUniverseUnavailableBehavior.EXCLUDE_FROM_RANKING_AND_CANDIDATES:
            raise ValueError("SECTOR_UNIVERSE_COVERAGE_POLICY_EXCLUSION_REQUIRED")
        if not self.explicit_exclusion_disclosure_required or self.zero_score_fallback_permitted or self.fuzzy_substitution_permitted or self.synthetic_index_permitted:
            raise ValueError("SECTOR_UNIVERSE_COVERAGE_POLICY_SAFETY_REQUIRED")
        if self.provenance != tuple(sorted(set(self.provenance))):
            raise ValueError("SECTOR_UNIVERSE_COVERAGE_POLICY_PROVENANCE_NONCANONICAL")
        if self.fingerprint != sector_universe_coverage_policy_fingerprint(self):
            raise ValueError("SECTOR_UNIVERSE_COVERAGE_POLICY_FINGERPRINT_MISMATCH")


@dataclass(frozen=True, slots=True)
class SectorUniverseCoverageExclusion:
    sector: str
    official_index: str
    readiness: str
    reason: str


@dataclass(frozen=True, slots=True)
class SectorUniverseCoverageAssessment:
    """One factual coverage decision at an explicit stored-data boundary."""

    as_of: datetime
    policy_id: str
    policy_version: str
    policy_fingerprint: str
    canonical_sector_count: int
    eligible_sectors: tuple[str, ...]
    ranked_sectors: tuple[str, ...]
    top_sectors: tuple[str, ...]
    excluded_sectors: tuple[SectorUniverseCoverageExclusion, ...]
    state: SectorUniverseCoverageState
    reason: str | None

    def __post_init__(self) -> None:
        if self.as_of.tzinfo is None or self.as_of.utcoffset() is None:
            raise ValueError("SECTOR_UNIVERSE_COVERAGE_AS_OF_REQUIRED")
        if len(self.top_sectors) > len(self.ranked_sectors):
            raise ValueError("SECTOR_UNIVERSE_COVERAGE_TOP_SECTORS_INVALID")

    @property
    def production_safe(self) -> bool:
        return self.state is SectorUniverseCoverageState.READY_WITH_LIMITATION


def create_frozen_sector_universe_coverage_policy(*, policy_id: str, version: str,
                                                   proposal_policy_id: str, proposal_version: str,
                                                   approved_by: str,
                                                   provenance: tuple[tuple[str, str], ...]) -> SectorUniverseCoveragePolicy:
    values = dict(
        policy_id=policy_id,
        version=version,
        proposal_policy_id=proposal_policy_id,
        proposal_version=proposal_version,
        approval_status=SectorUniverseCoverageApprovalStatus.APPROVED,
        approved_by=approved_by,
        selected_for_production_v1=True,
        active=True,
        benchmark_universe="NIFTY_500",
        canonical_sector_universe_source="CURRENT_OFFICIAL_NSE_SECTOR_INDEX_MAPPINGS",
        required_rs_lookbacks=(20, 60, 120),
        required_breadth_status="READY",
        required_top_sector_count=3,
        partial_operation_permitted=True,
        missing_sectors_are_p0_when_minimum_met=False,
        unavailable_sector_behavior=SectorUniverseUnavailableBehavior.EXCLUDE_FROM_RANKING_AND_CANDIDATES,
        explicit_exclusion_disclosure_required=True,
        zero_score_fallback_permitted=False,
        fuzzy_substitution_permitted=False,
        synthetic_index_permitted=False,
        provenance=tuple(sorted(set(provenance))),
    )
    return SectorUniverseCoveragePolicy(
        **values, fingerprint=sector_universe_coverage_policy_fingerprint_values(values),
    )


def sector_universe_coverage_policy_fingerprint(value: SectorUniverseCoveragePolicy) -> str:
    return sector_universe_coverage_policy_fingerprint_values({
        field: getattr(value, field) for field in value.__dataclass_fields__ if field != "fingerprint"
    })


def sector_universe_coverage_policy_fingerprint_values(values: dict) -> str:
    return manifest_fingerprint(
        policy_id=values["policy_id"], version=values["version"],
        proposal_policy_id=values["proposal_policy_id"], proposal_version=values["proposal_version"],
        approval_status=values["approval_status"].value, approved_by=values["approved_by"],
        selected_for_production_v1=values["selected_for_production_v1"], active=values["active"],
        benchmark_universe=values["benchmark_universe"], canonical_sector_universe_source=values["canonical_sector_universe_source"],
        required_rs_lookbacks=values["required_rs_lookbacks"], required_breadth_status=values["required_breadth_status"],
        required_top_sector_count=values["required_top_sector_count"], partial_operation_permitted=values["partial_operation_permitted"],
        missing_sectors_are_p0_when_minimum_met=values["missing_sectors_are_p0_when_minimum_met"],
        unavailable_sector_behavior=values["unavailable_sector_behavior"].value,
        explicit_exclusion_disclosure_required=values["explicit_exclusion_disclosure_required"],
        zero_score_fallback_permitted=values["zero_score_fallback_permitted"],
        fuzzy_substitution_permitted=values["fuzzy_substitution_permitted"],
        synthetic_index_permitted=values["synthetic_index_permitted"], provenance=values["provenance"],
    )


def assess_sector_universe_coverage(report, *, policy: SectorUniverseCoveragePolicy = None) -> SectorUniverseCoverageAssessment:
    """Assess existing current-sector output without recalculating it.

    ``report`` is intentionally a materialized stored-only rotation report;
    this function has no repository, provider, clock, or ranking dependency.
    """
    policy = policy or CURRENT_SECTOR_UNIVERSE_COVERAGE_POLICY
    by_breadth = {item.sector: item for item in report.breadth}
    eligible: list[str] = []
    excluded: list[SectorUniverseCoverageExclusion] = []
    for item in sorted(report.relative_strength, key=lambda value: value.sector):
        breadth = by_breadth.get(item.sector)
        missing_rs = any(getattr(item, f"rs{lookback}") is None for lookback in policy.required_rs_lookbacks)
        reason = item.exclusion_reason
        if reason is None and missing_rs:
            reason = "SECTOR_RANKING_EVIDENCE_UNAVAILABLE"
        if reason is None and (breadth is None or breadth.status != policy.required_breadth_status):
            reason = "SECTOR_BREADTH_UNAVAILABLE" if breadth is None else f"SECTOR_BREADTH_{breadth.status}"
        if reason is None:
            eligible.append(item.sector)
        else:
            excluded.append(SectorUniverseCoverageExclusion(item.sector, item.official_index, "UNAVAILABLE", reason))
    enough = len(eligible) >= policy.required_top_sector_count and len(report.top3) >= policy.required_top_sector_count
    state = SectorUniverseCoverageState.READY_WITH_LIMITATION if enough else SectorUniverseCoverageState.BLOCKED
    reason = None if enough else "SECTOR_UNIVERSE_TOP3_EVIDENCE_INSUFFICIENT"
    return SectorUniverseCoverageAssessment(
        report.generated_at, policy.policy_id, policy.version, policy.fingerprint,
        len(report.relative_strength), tuple(eligible), tuple(report.ranked_sectors), tuple(report.top3),
        tuple(excluded), state, reason,
    )


CURRENT_SECTOR_UNIVERSE_COVERAGE_POLICY = create_frozen_sector_universe_coverage_policy(
    policy_id="sector-universe-coverage-policy",
    version="v1-approved",
    proposal_policy_id="sector-universe-coverage-policy",
    proposal_version="v1-proposed",
    approved_by="human:Akash-Verma",
    provenance=(
        ("governance_approval", "TARGETED_P0_PARTIAL_SECTOR_UNIVERSE"),
        ("proposal_policy", "sector-universe-coverage-policy/v1-proposed"),
        ("scope", "PRODUCTION_V1_READINESS_ONLY"),
    ),
)


__all__ = (
    "CURRENT_SECTOR_UNIVERSE_COVERAGE_POLICY",
    "SectorUniverseCoverageApprovalStatus",
    "SectorUniverseCoverageAssessment",
    "SectorUniverseCoverageExclusion",
    "SectorUniverseCoveragePolicy",
    "SectorUniverseCoverageState",
    "SectorUniverseUnavailableBehavior",
    "assess_sector_universe_coverage",
    "create_frozen_sector_universe_coverage_policy",
    "sector_universe_coverage_policy_fingerprint",
)
