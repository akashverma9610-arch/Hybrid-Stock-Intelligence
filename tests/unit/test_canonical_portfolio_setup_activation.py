from __future__ import annotations

from dataclasses import replace
from datetime import timedelta

from app.intelligence.governed_setup_evidence import CanonicalSetupOpportunityEvidenceSource
from app.intelligence.unified_state import IntelligenceEvidenceAvailability, IntelligenceEvidenceDomain
from app.production_v1.canonical_setup_activation import (
    CANONICAL_PORTFOLIO_SETUP_TARGETS,
    CanonicalPortfolioSetupMaterializationService,
    CanonicalPortfolioSetupRunStore,
    CanonicalSetupGateInputStatus,
    CanonicalSetupOpportunity,
    CanonicalSetupOpportunityStore,
)
from app.storage.core_api_snapshot_repository import CoreApiSnapshotFamily
from app.storage.sqlite_core_api_snapshot_repository import SQLiteCoreApiSnapshotRepository
from app.storage.sqlite_governance_repository import SQLiteStrategyGovernanceRepository
from app.strategies.pre_breakout.setup_assessment import (
    PreBreakoutSetupAssessmentStatus,
    PreBreakoutSetupBlocker,
    PreBreakoutSetupBlockerCategory,
)
from tests.unit.pre_breakout_setup_fixture import T, assessment


class _Rotation:
    def assess(self, *, as_of):
        assert as_of == T
        return object()


class _Assessments:
    def __init__(self, values):
        self.values = values
        self.calls: list[str] = []

    def assess_prebreakout_setup(self, instrument_id, *, as_of, sector_rotation):
        assert as_of == T and sector_rotation is not None
        self.calls.append(instrument_id)
        return self.values[instrument_id]


def _value(instrument_id: str, *, eligible: bool):
    base = assessment()
    value = replace(
        base,
        instrument_id=instrument_id,
        technical_inputs=replace(base.technical_inputs, instrument_id=instrument_id),
        structural=replace(base.structural, instrument_id=instrument_id),
    )
    if eligible:
        return value
    return replace(
        value,
        status=PreBreakoutSetupAssessmentStatus.BLOCKED_TECHNICAL_SETUP,
        candidate_formation_eligible=False,
        blockers=(PreBreakoutSetupBlocker(
            PreBreakoutSetupBlockerCategory.TECHNICAL_SETUP_FAIL, "VOLUME_NOT_DRY",
        ),),
    )


def _service(tmp_path, *, eligible_symbols=("APARINDS",)):
    path = tmp_path / "setup.sqlite"
    core = SQLiteCoreApiSnapshotRepository(path)
    governance = SQLiteStrategyGovernanceRepository(str(path))
    values = {
        instrument_id: _value(instrument_id, eligible=symbol in eligible_symbols)
        for symbol, instrument_id in CANONICAL_PORTFOLIO_SETUP_TARGETS
    }
    return (
        CanonicalPortfolioSetupMaterializationService(
            assessment_service=_Assessments(values), assessment_repository=governance,
            rotation_service=_Rotation(), opportunities=CanonicalSetupOpportunityStore(core),
            runs=CanonicalPortfolioSetupRunStore(core),
        ),
        core, governance,
    )


def test_exact_five_materialization_is_idempotent_and_never_creates_a_paper_setup(tmp_path) -> None:
    service, core, governance = _service(tmp_path)
    first = service.run(as_of=T)
    second = service.run(as_of=T)
    assert second == first
    assert tuple(item.symbol for item in first.outcomes) == tuple(item[0] for item in CANONICAL_PORTFOLIO_SETUP_TARGETS)
    assert first.current_setup_count == 1 and first.no_current_setup_count == 4
    ready = next(item for item in first.outcomes if item.symbol == "APARINDS")
    assert ready.gate_setup_input_status is CanonicalSetupGateInputStatus.READY
    assert ready.opportunity_id is not None
    assert all(item.gate_setup_input_status is CanonicalSetupGateInputStatus.NOT_READY for item in first.outcomes[1:])
    opportunities = CanonicalSetupOpportunityStore(core).list(as_of=T)
    assert len(opportunities) == 1
    assert opportunities[0].candidate.actual_execution_price is None
    assert opportunities[0].time_horizon_status == "NOT_GOVERNED_FOR_SETUP_OPPORTUNITY"
    assert core.list_snapshots(CoreApiSnapshotFamily.FORWARD_PAPER_EXECUTABLE_SETUP) == ()
    assert len(governance.list_prebreakout_setup_assessments()) == 5
    core.close(); governance.close()
    reopened = SQLiteCoreApiSnapshotRepository(tmp_path / "setup.sqlite")
    assert CanonicalPortfolioSetupRunStore(reopened).get(first.run_id) == first
    assert CanonicalSetupOpportunityStore(reopened).list(as_of=T) == opportunities
    reopened.close()


def test_technical_setup_can_materialize_without_any_decision_score_dependency(tmp_path) -> None:
    service, core, governance = _service(tmp_path, eligible_symbols=("GENUSPOWER",))
    result = service.run(as_of=T)
    ready = next(item for item in result.outcomes if item.symbol == "GENUSPOWER")
    assert ready.opportunity_id is not None
    assert CanonicalSetupOpportunityStore(core).list(as_of=T)[0].canonical_instrument_id == "NSE:INE955D01029"
    core.close(); governance.close()


def test_opportunity_evidence_is_available_only_for_a_durable_current_opportunity(tmp_path) -> None:
    service, core, governance = _service(tmp_path, eligible_symbols=("APARINDS",))
    service.run(as_of=T)
    source = CanonicalSetupOpportunityEvidenceSource(CanonicalSetupOpportunityStore(core))
    available = source.list_stored_intelligence_artifacts("NSE:INE372A01015", as_of=T)
    unavailable = source.list_stored_intelligence_artifacts("NSE:INE0FHS01024", as_of=T)
    assert len(available) == 1
    assert available[0].domain is IntelligenceEvidenceDomain.SETUP_OPPORTUNITY
    assert available[0].availability is IntelligenceEvidenceAvailability.AVAILABLE
    assert unavailable == ()
    assert source.list_stored_intelligence_artifacts("NSE:INE372A01015", as_of=T - timedelta(seconds=1)) == ()
    core.close(); governance.close()


def test_opportunity_rejects_tampered_candidate_lineage() -> None:
    value = _value("NSE:INE372A01015", eligible=True)
    original = CanonicalSetupOpportunity.from_assessment(value)
    try:
        CanonicalSetupOpportunity(
            **{**{field: getattr(original, field) for field in original.__dataclass_fields__ if field != "fingerprint"},
               "assessment_fingerprint": "tampered", "fingerprint": original.fingerprint}
        )
    except ValueError as error:
        assert "LINEAGE_MISMATCH" in str(error)
    else:
        raise AssertionError("tampered setup opportunity was accepted")
