from __future__ import annotations

from dataclasses import replace
from datetime import timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.forward_paper.composition import (
    StoredExecutableSetupStore,
    compose_stored_executable_setup,
)
from app.production_v1.governed_setup_source import (
    GovernedExecutableSetupSourceRun,
    GovernedExecutableSetupSourceRunStore,
    GovernedExecutableSetupSourceService,
    GovernedExecutableSetupSourceState,
)
from app.production_v1.local import _governed_setup_source_readiness
from app.production_v1.models import ProductionReadinessState
from app.storage.sqlite_core_api_snapshot_repository import SQLiteCoreApiSnapshotRepository
from app.storage.sqlite_governance_repository import SQLiteStrategyGovernanceRepository
from app.strategies.pre_breakout.materialization import PreBreakoutStructuralStatus
from app.strategies.pre_breakout.setup_assessment import (
    PreBreakoutSetupAssessmentStatus,
    PreBreakoutSetupBlocker,
    PreBreakoutSetupBlockerCategory,
)
from tests.unit.pre_breakout_setup_fixture import INSTRUMENT_ID, T, assessment


class _Assessments:
    def __init__(self, value): self.value = value; self.calls = 0
    def assess_prebreakout_setup(self, instrument_id, *, as_of, sector_rotation=None):
        self.calls += 1
        assert instrument_id == INSTRUMENT_ID and as_of == T
        return self.value


class _Rotation:
    def assess(self, *, as_of):
        assert as_of == T
        return SimpleNamespace(
            top3=("Metals", "Healthcare", "Media"),
            constituents=(SimpleNamespace(instrument_id=INSTRUMENT_ID, sector="Metals"),),
            relative_strength=(
                SimpleNamespace(sector="Metals", exclusion_reason=None),
                SimpleNamespace(sector="Power", exclusion_reason="INSUFFICIENT_ALIGNED_120_SESSION_HISTORY"),
            ),
        )


def _blocked(value, category=PreBreakoutSetupBlockerCategory.TECHNICAL_SETUP_FAIL):
    status = {
        PreBreakoutSetupBlockerCategory.DATA_BLOCKER: PreBreakoutSetupAssessmentStatus.BLOCKED_DATA,
        PreBreakoutSetupBlockerCategory.SECTOR_BLOCKER: PreBreakoutSetupAssessmentStatus.BLOCKED_SECTOR,
        PreBreakoutSetupBlockerCategory.TECHNICAL_SETUP_FAIL: PreBreakoutSetupAssessmentStatus.BLOCKED_TECHNICAL_SETUP,
        PreBreakoutSetupBlockerCategory.ENTRY_ECONOMICS_FAIL: PreBreakoutSetupAssessmentStatus.BLOCKED_ENTRY_ECONOMICS,
    }[category]
    return replace(value, status=status, candidate_formation_eligible=False,
                   blockers=(PreBreakoutSetupBlocker(category, "BLOCKED"),))


def test_authoritative_governed_assessment_composes_deterministically() -> None:
    first = compose_stored_executable_setup(assessment(), time_stop_sessions=10)
    second = compose_stored_executable_setup(assessment(), time_stop_sessions=10)
    assert first == second
    assert first.setup_id.startswith("stored-executable:prebreakout-candidate-")
    assert first.source_candidate_fingerprint
    assert first.maximum_entry is None  # Current pre-breakout ceiling is not a breakout E_max.
    assert (first.trigger, first.structural_stop, first.target, first.time_stop_sessions) == (
        Decimal("500"), Decimal("449.95"), Decimal("550"), 10,
    )


@pytest.mark.parametrize("value", (
    _blocked(assessment()),
    _blocked(assessment(), PreBreakoutSetupBlockerCategory.DATA_BLOCKER),
    _blocked(assessment(), PreBreakoutSetupBlockerCategory.SECTOR_BLOCKER),
    replace(assessment(), top3_sector_membership=False),
    replace(assessment(), structural=replace(assessment().structural, breakout_confirmation_trigger=None)),
    replace(assessment(), structural=replace(assessment().structural, final_stop=None)),
    replace(assessment(), structural=replace(assessment().structural, target=None)),
    replace(assessment(), structural=replace(assessment().structural, entry_reference_rr_pass=False)),
    replace(assessment(), policy_fingerprint=None),
    replace(assessment(), technical_inputs=replace(assessment().technical_inputs, blockers=("OHLCV_CONFLICTED",))),
))
def test_partial_rejected_excluded_or_incomplete_assessment_cannot_compose(value) -> None:
    with pytest.raises(ValueError, match="GOVERNED_EXECUTABLE_SETUP"):
        compose_stored_executable_setup(value, time_stop_sessions=10)


def test_source_runner_persists_only_eligible_setup_and_is_idempotent_after_reopen(tmp_path) -> None:
    path = tmp_path / "source.sqlite"
    core = SQLiteCoreApiSnapshotRepository(path)
    governance = SQLiteStrategyGovernanceRepository(str(path))
    runner = GovernedExecutableSetupSourceService(
        assessment_service=_Assessments(assessment()), assessment_repository=governance,
        rotation_service=_Rotation(), setup_store=StoredExecutableSetupStore(core),
        run_store=GovernedExecutableSetupSourceRunStore(core), time_stop_sessions=10,
    )
    first = runner.run(as_of=T)
    second = runner.run(as_of=T)
    assert first == second
    assert first.state is GovernedExecutableSetupSourceState.READY_WITH_EXECUTABLE_SETUP
    assert first.persisted_count == 1 and first.duplicate_count == 0
    assert len(StoredExecutableSetupStore(core).list(as_of=T)) == 1
    core.close(); governance.close()
    reopened = SQLiteCoreApiSnapshotRepository(path)
    assert len(StoredExecutableSetupStore(reopened).list(as_of=T)) == 1
    run = GovernedExecutableSetupSourceRunStore(reopened).latest(as_of=T)
    assert run == first and run.executable_setup_fingerprints
    reopened.close()


def test_zero_current_candidate_is_ready_no_current_setup_and_never_creates_paper_artifacts(tmp_path) -> None:
    path = tmp_path / "zero.sqlite"
    core = SQLiteCoreApiSnapshotRepository(path)
    governance = SQLiteStrategyGovernanceRepository(str(path))
    blocked = _blocked(assessment())
    runner = GovernedExecutableSetupSourceService(
        assessment_service=_Assessments(blocked), assessment_repository=governance,
        rotation_service=_Rotation(), setup_store=StoredExecutableSetupStore(core),
        run_store=GovernedExecutableSetupSourceRunStore(core),
    )
    result = runner.run(as_of=T)
    assert result.state is GovernedExecutableSetupSourceState.READY_NO_CURRENT_SETUP
    assert result.reason == "NO_CURRENT_EXECUTABLE_SETUP"
    assert not StoredExecutableSetupStore(core).list(as_of=T)
    assert governance.get_prebreakout_setup_assessment(blocked.assessment_id) is not None
    core.close(); governance.close()


def test_eligible_setup_without_frozen_paper_time_stop_fails_closed(tmp_path) -> None:
    core = SQLiteCoreApiSnapshotRepository(tmp_path / "missing-time.sqlite")
    governance = SQLiteStrategyGovernanceRepository(str(tmp_path / "missing-time.sqlite"))
    result = GovernedExecutableSetupSourceService(
        assessment_service=_Assessments(assessment()), assessment_repository=governance,
        rotation_service=_Rotation(), setup_store=StoredExecutableSetupStore(core),
        run_store=GovernedExecutableSetupSourceRunStore(core),
    ).run(as_of=T)
    assert result.state is GovernedExecutableSetupSourceState.BLOCKED_COMPOSITION
    assert result.reason == "PAPER_TIME_STOP_SOURCE_UNCONFIGURED"
    assert not StoredExecutableSetupStore(core).list(as_of=T)
    core.close(); governance.close()


def test_future_assessment_is_not_visible_to_a_prior_pit_cutoff(tmp_path) -> None:
    path = tmp_path / "pit.sqlite"
    core = SQLiteCoreApiSnapshotRepository(path)
    governance = SQLiteStrategyGovernanceRepository(str(path))
    future = replace(assessment(), evaluation_as_of=T + timedelta(days=1), evaluation_session=T + timedelta(days=1))
    governance.save_prebreakout_setup_assessment(future)
    assert governance.list_prebreakout_setup_assessments(canonical_instrument_id=INSTRUMENT_ID) == (future,)
    assert StoredExecutableSetupStore(core).list(as_of=T) == ()
    core.close(); governance.close()


def test_source_runner_reuses_only_exact_cutoff_assessment_and_never_future_evidence(tmp_path) -> None:
    path = tmp_path / "reuse.sqlite"
    core = SQLiteCoreApiSnapshotRepository(path)
    governance = SQLiteStrategyGovernanceRepository(str(path))
    existing = assessment()
    governance.save_prebreakout_setup_assessment(existing)
    source = _Assessments(replace(existing, evaluation_as_of=T + timedelta(days=1), evaluation_session=T + timedelta(days=1)))
    runner = GovernedExecutableSetupSourceService(
        assessment_service=source, assessment_repository=governance, rotation_service=_Rotation(),
        setup_store=StoredExecutableSetupStore(core), run_store=GovernedExecutableSetupSourceRunStore(core), time_stop_sessions=10,
    )
    result = runner.run(as_of=T)
    assert source.calls == 0
    assert result.assessment_ids == (existing.assessment_id,)
    assert result.state is GovernedExecutableSetupSourceState.READY_WITH_EXECUTABLE_SETUP
    core.close(); governance.close()


def _receipt(*, state=GovernedExecutableSetupSourceState.READY_NO_CURRENT_SETUP):
    return GovernedExecutableSetupSourceRun.create(
        as_of=T, top3=("Metals",), excluded_sectors=("Power",),
        assessment_ids=("assessment:1",), assessment_fingerprints=("assessment-fp",),
        executable_setup_ids=(), executable_setup_fingerprints=(), eligible_count=0,
        partial_or_data_blocked_count=0, rejected_count=1, persisted_count=0,
        duplicate_count=0, state=state,
        reason="NO_CURRENT_EXECUTABLE_SETUP" if state is GovernedExecutableSetupSourceState.READY_NO_CURRENT_SETUP else "SOURCE_FAILURE",
    )


def test_production_readiness_treats_valid_empty_source_as_non_p0_degraded() -> None:
    assert _governed_setup_source_readiness(None) == (
        ProductionReadinessState.BLOCKED, "GOVERNED_SETUP_SOURCE_RUN_REQUIRED",
    )
    assert _governed_setup_source_readiness(_receipt()) == (
        ProductionReadinessState.DEGRADED, "READY_NO_CURRENT_SETUP",
    )
    assert _governed_setup_source_readiness(_receipt(state=GovernedExecutableSetupSourceState.BLOCKED_COMPOSITION)) == (
        ProductionReadinessState.BLOCKED, "SOURCE_FAILURE",
    )


def test_explicit_cli_reports_source_state_without_paper_execution() -> None:
    from app.runtime.cli import main

    receipt = _receipt()
    output: list[str] = []
    class _Source:
        def run(self, *, as_of):
            assert as_of == T
            return receipt
    assert main(
        ["run-governed-executable-setup-source", "--as-of", T.isoformat()],
        governed_executable_setup_source_factory=lambda **_: (_Source(), ()), output=output.append,
    ) == 0
    assert "state=READY_NO_CURRENT_SETUP" in output[0]
    assert "persisted=0" in output[0]
