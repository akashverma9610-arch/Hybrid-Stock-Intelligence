from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace

from app.production_v1.sector_universe_coverage import (
    CURRENT_SECTOR_UNIVERSE_COVERAGE_POLICY,
    SectorUniverseCoverageState,
    assess_sector_universe_coverage,
    create_frozen_sector_universe_coverage_policy,
)


T = datetime(2026, 8, 30, tzinfo=UTC)


def _report(*, ready: tuple[str, ...] = ("Chemicals", "Healthcare", "Realty"),
            unavailable: tuple[str, ...] = ("Construction",)):
    values = []
    breadth = []
    for sector in (*ready, *unavailable):
        values.append(SimpleNamespace(
            sector=sector, official_index=f"Nifty {sector}",
            rs20=Decimal("1") if sector in ready else None,
            rs60=Decimal("1") if sector in ready else None,
            rs120=Decimal("1") if sector in ready else None,
            exclusion_reason=None if sector in ready else "INSUFFICIENT_ALIGNED_120_SESSION_HISTORY",
        ))
        breadth.append(SimpleNamespace(sector=sector, status="READY"))
    return SimpleNamespace(
        generated_at=T, relative_strength=tuple(values), breadth=tuple(breadth),
        ranked_sectors=tuple(ready), top3=tuple(ready[:3]),
    )


def test_selected_policy_is_immutable_and_has_no_synthetic_or_fuzzy_fallback() -> None:
    policy = CURRENT_SECTOR_UNIVERSE_COVERAGE_POLICY
    assert policy.approved_by == "human:Akash-Verma" and policy.selected_for_production_v1 and policy.active
    assert policy.required_top_sector_count == 3
    assert not policy.zero_score_fallback_permitted
    assert not policy.fuzzy_substitution_permitted
    assert not policy.synthetic_index_permitted
    assert policy.fingerprint == create_frozen_sector_universe_coverage_policy(
        policy_id=policy.policy_id, version=policy.version,
        proposal_policy_id=policy.proposal_policy_id, proposal_version=policy.proposal_version,
        approved_by=policy.approved_by, provenance=policy.provenance,
    ).fingerprint


def test_exact_canonical_sector_rows_are_evidence_eligible_or_explicitly_excluded() -> None:
    assessment = assess_sector_universe_coverage(_report())
    assert assessment.canonical_sector_count == 4
    assert assessment.eligible_sectors == ("Chemicals", "Healthcare", "Realty")
    assert assessment.excluded_sectors[0].sector == "Construction"
    assert assessment.excluded_sectors[0].official_index == "Nifty Construction"
    assert assessment.excluded_sectors[0].reason == "INSUFFICIENT_ALIGNED_120_SESSION_HISTORY"
    assert assessment.state is SectorUniverseCoverageState.READY_WITH_LIMITATION


def test_fewer_than_three_evidence_eligible_sectors_fails_closed_without_a_rank_fallback() -> None:
    assessment = assess_sector_universe_coverage(_report(ready=("Chemicals", "Healthcare")))
    assert assessment.state is SectorUniverseCoverageState.BLOCKED
    assert assessment.reason == "SECTOR_UNIVERSE_TOP3_EVIDENCE_INSUFFICIENT"
    assert assessment.top_sectors == ("Chemicals", "Healthcare")


def test_recovery_and_degradation_are_dynamic_not_a_hard_coded_sector_list() -> None:
    degraded = assess_sector_universe_coverage(_report(ready=("Chemicals", "Healthcare")))
    recovered = assess_sector_universe_coverage(_report(ready=("Chemicals", "Healthcare", "Construction"), unavailable=()))
    assert degraded.state is SectorUniverseCoverageState.BLOCKED
    assert recovered.state is SectorUniverseCoverageState.READY_WITH_LIMITATION
    assert recovered.eligible_sectors == ("Chemicals", "Construction", "Healthcare")


def test_as_of_is_preserved_by_the_coverage_assessment() -> None:
    report = _report()
    report.generated_at = T  # SimpleNamespace makes the explicit input boundary visible.
    assert assess_sector_universe_coverage(report).as_of == T
