from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

from app.production_v1.canonical_setup_activation import CanonicalSetupOpportunityStore
from app.production_v1.top3_opportunity_finder import (
    Top3OpportunityFinderRunStore,
    Top3OpportunityFinderService,
)
from app.storage.sqlite_core_api_snapshot_repository import SQLiteCoreApiSnapshotRepository
from app.storage.sqlite_governance_repository import SQLiteStrategyGovernanceRepository
from app.strategies.pre_breakout.setup_assessment import (
    PreBreakoutSetupAssessmentStatus,
    PreBreakoutSetupBlocker,
    PreBreakoutSetupBlockerCategory,
)
from tests.unit.pre_breakout_setup_fixture import T, assessment


class _Rankings:
    def __init__(self, ranking) -> None:
        self.ranking = ranking
        self.calls = 0

    def latest(self, *, as_of):
        assert as_of == T
        self.calls += 1
        return self.ranking


class _Assessments:
    def __init__(self, values) -> None:
        self.values = values
        self.calls: list[tuple[str, object]] = []

    def assess_prebreakout_setup(self, instrument_id, *, as_of, sector_rotation):
        assert as_of == T
        self.calls.append((instrument_id, sector_rotation))
        return self.values[instrument_id]


def _value(instrument_id: str, *, status: PreBreakoutSetupAssessmentStatus):
    base = assessment()
    value = replace(
        base,
        instrument_id=instrument_id,
        technical_inputs=replace(base.technical_inputs, instrument_id=instrument_id),
        structural=replace(base.structural, instrument_id=instrument_id),
    )
    if status is PreBreakoutSetupAssessmentStatus.ELIGIBLE_TO_FORM_CANDIDATE:
        return value
    category = (
        PreBreakoutSetupBlockerCategory.DATA_BLOCKER
        if status is PreBreakoutSetupAssessmentStatus.BLOCKED_DATA
        else PreBreakoutSetupBlockerCategory.TECHNICAL_SETUP_FAIL
    )
    return replace(
        value,
        status=status,
        candidate_formation_eligible=False,
        blockers=(PreBreakoutSetupBlocker(category, f"{instrument_id}-BLOCKER"),),
    )


def _service(tmp_path, values, constituents):
    path = tmp_path / "top3.sqlite"
    core = SQLiteCoreApiSnapshotRepository(path)
    governance = SQLiteStrategyGovernanceRepository(str(path))
    report = SimpleNamespace(
        top3=("Metals", "Healthcare", "Media"),
        constituents=constituents,
    )
    ranking = SimpleNamespace(
        ranking_id="current-sector-ranking:fixture",
        latest_completed_session=T,
        report=report,
    )
    rankings = _Rankings(ranking)
    assessments = _Assessments(values)
    return (
        Top3OpportunityFinderService(
            rankings=rankings,
            assessments=assessments,
            assessment_repository=governance,
            opportunities=CanonicalSetupOpportunityStore(core),
            runs=Top3OpportunityFinderRunStore(core),
        ),
        rankings,
        assessments,
        core,
        governance,
        report,
    )


def test_uses_only_stored_top3_constituents_and_is_idempotent(tmp_path) -> None:
    values = {
        "NSE:A": _value("NSE:A", status=PreBreakoutSetupAssessmentStatus.BLOCKED_DATA),
        "NSE:B": _value("NSE:B", status=PreBreakoutSetupAssessmentStatus.BLOCKED_TECHNICAL_SETUP),
        "NSE:C": _value("NSE:C", status=PreBreakoutSetupAssessmentStatus.BLOCKED_TECHNICAL_SETUP),
    }
    rows = (
        SimpleNamespace(symbol="A", sector="Metals", instrument_id="NSE:A", resolution_status="RESOLVED"),
        SimpleNamespace(symbol="A", sector="Metals", instrument_id="NSE:A", resolution_status="RESOLVED"),
        SimpleNamespace(symbol="B", sector="Healthcare", instrument_id="NSE:B", resolution_status="RESOLVED"),
        SimpleNamespace(symbol="C", sector="Media", instrument_id="NSE:C", resolution_status="RESOLVED"),
        SimpleNamespace(symbol="OUT", sector="Banks", instrument_id="NSE:OUT", resolution_status="RESOLVED"),
        SimpleNamespace(symbol="UNKNOWN", sector="Metals", instrument_id=None, resolution_status="UNRESOLVED"),
        SimpleNamespace(symbol="CONFLICT", sector="Metals", instrument_id="NSE:X", resolution_status="RESOLVED"),
        SimpleNamespace(symbol="CONFLICT", sector="Healthcare", instrument_id="NSE:X", resolution_status="RESOLVED"),
    )
    service, rankings, assessments, core, governance, report = _service(tmp_path, values, rows)
    first = service.run(as_of=T)
    second = service.run(as_of=T)

    assert first == second
    assert first.candidate_ids == ("NSE:A", "NSE:B", "NSE:C")
    assert first.excluded == (("NSE:X", "SECTOR_MEMBERSHIP_CONFLICT"), ("UNKNOWN", "UNRESOLVED"))
    assert first.data_blocked_count == 1
    assert first.condition_not_met_count == 2
    assert first.valid_count == 0 and first.opportunity_ids == ()
    assert len(first.near_misses) == 3
    assert {identifier for identifier, reused_report in assessments.calls} == {"NSE:A", "NSE:B", "NSE:C"}
    assert all(reused_report is report for _, reused_report in assessments.calls)
    assert len(governance.list_prebreakout_setup_assessments()) == 3
    assert Top3OpportunityFinderRunStore(core).list() == (first,)
    assert CanonicalSetupOpportunityStore(core).list(as_of=T) == ()
    assert rankings.calls == 2
    core.close(); governance.close()


def test_forms_only_a_canonical_opportunity_for_an_eligible_assessment(tmp_path) -> None:
    values = {"NSE:READY": _value("NSE:READY", status=PreBreakoutSetupAssessmentStatus.ELIGIBLE_TO_FORM_CANDIDATE)}
    rows = (SimpleNamespace(symbol="READY", sector="Metals", instrument_id="NSE:READY", resolution_status="RESOLVED"),)
    service, _, _, core, governance, _ = _service(tmp_path, values, rows)

    result = service.run(as_of=T)

    opportunities = CanonicalSetupOpportunityStore(core).list(as_of=T)
    assert result.valid_count == 1
    assert result.data_blocked_count == result.condition_not_met_count == 0
    assert result.opportunity_ids == (opportunities[0].opportunity_id,)
    assert opportunities[0].candidate.actual_execution_price is None
    assert opportunities[0].time_horizon_status == "NOT_GOVERNED_FOR_SETUP_OPPORTUNITY"
    core.close(); governance.close()
