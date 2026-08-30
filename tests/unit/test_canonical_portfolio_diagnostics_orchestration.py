from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
import json
from pathlib import Path
import re
from types import SimpleNamespace

import pytest

from app.diagnostics.models import EvaluationEligibility
from app.data_operations.models import EvidenceDataFamily, EvidenceRefreshMode, EvidenceRefreshOutcome, EvidenceRefreshRequest, EvidenceRefreshStatus
from app.domain.canonical_diagnostic_strategy import (
    CanonicalDiagnosticDefinitionStatus, CanonicalDiagnosticGovernanceLimitation,
    CanonicalDiagnosticStrategyDefinition, governance_limitations_fingerprint,
    semantic_fingerprint_for_payload,
)
from app.domain.models import DiagnosticResult, canonical_diagnostic_result
from app.intelligence.research_diagnostic_evidence import (
    ExactAsOfStrategyGovernanceDiagnosticResultSource,
    ResearchDiagnosticEvidenceStoredSource,
)
from app.intelligence.shared_brain_application import StoredSharedBrainEvidenceAssembler
from app.fundamentals.store import SQLiteFinancialFactStore
from app.portfolio.canonical_diagnostics_orchestration import (
    PORTFOLIO_FIVE_CANONICAL_INSTRUMENT_IDS,
    CanonicalPortfolioDiagnosticsOrchestrator,
    refresh_targeted_holding_ohlcv,
    rehydrate_persisted_canonical_diagnostics,
)
from app.portfolio.models import (
    CashPosition, CashState, PortfolioDataStatus, PortfolioExposureSummary, PortfolioHolding,
    PortfolioRiskSummary, PortfolioSnapshot, PortfolioState,
)
from app.storage.sqlite_core_api_snapshot_repository import SQLiteCoreApiSnapshotRepository
from app.storage.sqlite_governance_repository import SQLiteStrategyGovernanceRepository
from app.universe_analysis.models import NseEquityInstrument
from app.universe_analysis.service import (
    Canonical61DiagnosticRunner, CoreUniverseAnalysisStore, StockDiagnosticInputAssembler,
)
from tests.fixtures.analytical_observations import ANALYSIS_TIME, bars


class StoredFacts:
    def __init__(self, values): self.values = tuple(values)
    def observations_as_of(self, at): return tuple(item for item in self.values if item.provenance.retrieved_timestamp <= at)


class CompleteBrain:
    def analyze_stock(self, identifier, *, context, as_of=None):
        return SimpleNamespace(
            canonical_instrument_id=identifier, as_of=as_of, evidence_status="COMPLETE",
            evidence_domains=(("REFERENCE_DATA", "AVAILABLE"),), snapshot_fingerprint=f"brain:{identifier}:{as_of.isoformat()}",
            context_projection_fingerprint="context", unified_state_fingerprint="unified",
            brain_research_state_v2_fingerprint="research", financial_semantic_section_fingerprint="financial",
        )


class TargetedRefreshJob:
    def __init__(self): self.targets = None
    def refresh_selected(self, request, *, canonical_instrument_ids):
        self.targets = canonical_instrument_ids
        return EvidenceRefreshOutcome(EvidenceRefreshStatus.NO_CHANGE, "existing-provider")


def _canonical_definition() -> CanonicalDiagnosticStrategyDefinition:
    root = Path(__file__).parents[2]
    parse = lambda path: json.loads(re.search(r"```json\r?\n(\{.*?\})\r?\n```", path.read_text(encoding="utf-8"), re.S).group(1))
    payload = parse(root / "docs" / "architecture" / "CANONICAL_UNIVERSE_ANALYSIS_V1_DEFINITION_PROPOSAL.md")
    approval = parse(root / "docs" / "architecture" / "CANONICAL_UNIVERSE_ANALYSIS_V1_APPROVAL.md")
    limitations = tuple(CanonicalDiagnosticGovernanceLimitation(**item) for item in approval["governance_limitations"])
    return CanonicalDiagnosticStrategyDefinition(
        strategy_id=payload["strategy"]["id"], strategy_version=payload["strategy"]["version"],
        canonical_payload=payload, semantic_fingerprint=semantic_fingerprint_for_payload(payload),
        governance_limitations=limitations, definition_status=CanonicalDiagnosticDefinitionStatus.APPROVED,
        reviewer_id=approval["reviewer"],
        definition_proposal_artifact="docs/architecture/CANONICAL_UNIVERSE_ANALYSIS_V1_DEFINITION_PROPOSAL.md",
        human_approval_artifact="docs/architecture/CANONICAL_UNIVERSE_ANALYSIS_V1_APPROVAL.md",
        created_at=ANALYSIS_TIME, registered_at=ANALYSIS_TIME,
    )


def _holding(identifier: str) -> PortfolioHolding:
    return PortfolioHolding(identifier, identifier, Decimal("1"), Decimal("100"), Decimal("100"), ANALYSIS_TIME,
                            Decimal("0"), "Industrials", None, None, True, Decimal("100"), "mark", Decimal("100"),
                            Decimal("0"), Decimal("0"), None, 1, 1, None)


def _snapshot() -> PortfolioSnapshot:
    holdings = tuple(_holding(identifier) for identifier in PORTFOLIO_FIVE_CANONICAL_INSTRUMENT_IDS)
    return PortfolioSnapshot("portfolio-five", "portfolio-five", ANALYSIS_TIME, ANALYSIS_TIME, holdings,
        CashPosition(None, "INR", Decimal("0"), ANALYSIS_TIME, cash_state=CashState.UNKNOWN), (), Decimal("500"), Decimal("0"),
        Decimal("0"), Decimal("0"), PortfolioExposureSummary({}, None, {}, 5, None),
        PortfolioRiskSummary(None, Decimal("0"), PortfolioDataStatus.PARTIAL, {}), PortfolioState.FULLY_INVESTED,
        PortfolioDataStatus.PARTIAL, "v1", None)


def _instrument(identifier: str) -> NseEquityInstrument:
    return NseEquityInstrument(identifier, identifier.rsplit(":", 1)[-1], None, "Industrials", None, "ACTIVE", None,
                                True, ANALYSIS_TIME, "official", f"fixture:{identifier}")


def _service(tmp_path, *, registered: bool):
    governance = SQLiteStrategyGovernanceRepository(tmp_path / "governance.db")
    definition = _canonical_definition()
    if registered:
        governance.save_canonical_diagnostic_strategy_definition(definition)
    core = SQLiteCoreApiSnapshotRepository(tmp_path / "core.db")
    universe = CoreUniverseAnalysisStore(core)
    for identifier in PORTFOLIO_FIVE_CANONICAL_INSTRUMENT_IDS:
        universe.save_instrument(_instrument(identifier))
    evidence = tuple(
        item for identifier in PORTFOLIO_FIVE_CANONICAL_INSTRUMENT_IDS
        for item in bars(identifier, [10, 11, 12, 13, 14, 15], volumes=[10, 11, 12, 13, 14, 15])
    ) + bars("NIFTY_50", [100, 101, 102, 103, 104, 105])
    service = CanonicalPortfolioDiagnosticsOrchestrator(
        universe=universe, assembler=StockDiagnosticInputAssembler(StoredFacts(evidence)),
        runner=Canonical61DiagnosticRunner(strategy=definition.reference), governance=governance,
        shared_brain=CompleteBrain(),
    )
    return service, governance, definition


def test_exact_five_holding_orchestration_reuses_runner_persists_and_is_idempotent(tmp_path):
    service, governance, definition = _service(tmp_path, registered=True)
    first = service.run(portfolio_snapshot=_snapshot(), canonical_instrument_ids=PORTFOLIO_FIVE_CANONICAL_INSTRUMENT_IDS,
                        strategy_version=definition.reference)
    second = service.run(portfolio_snapshot=_snapshot(), canonical_instrument_ids=PORTFOLIO_FIVE_CANONICAL_INSTRUMENT_IDS,
                         strategy_version=definition.reference)
    assert first.canonical_instrument_ids == PORTFOLIO_FIVE_CANONICAL_INSTRUMENT_IDS
    assert len(first.holdings) == 5 and all(len(item.persisted_diagnostic_ids) == 61 for item in first.holdings)
    assert all(item.shared_brain_status == "COMPLETE" for item in first.holdings)
    assert all(item.composition is not None and item.sell_side_decision is not None for item in first.holdings)
    assert all(item.sell_side_decision.action.value == "REVIEW_REQUIRED" for item in first.holdings)
    stored = governance.list_diagnostic_results(definition.reference, ANALYSIS_TIME)
    assert len(stored) == 5 * 61
    assert all(item.strategy_lineage_type.value == "CANONICAL_DIAGNOSTIC_STRATEGY" for item in stored)
    assert governance.get_strategy_definition(definition.reference) is None
    assert tuple(item.persisted_diagnostic_ids for item in first.holdings) == tuple(item.persisted_diagnostic_ids for item in second.holdings)


def test_unregistered_strategy_is_a_policy_blocker_without_diagnostic_write(tmp_path):
    service, governance, definition = _service(tmp_path, registered=False)
    result = service.run(portfolio_snapshot=_snapshot(), canonical_instrument_ids=PORTFOLIO_FIVE_CANONICAL_INSTRUMENT_IDS,
                         strategy_version=definition.reference)
    assert result.blockers == ("CANONICAL_DIAGNOSTIC_RUNNER_UNAUTHORIZED",)
    assert all(not item.persisted_diagnostic_ids for item in result.holdings)


def test_target_must_be_an_explicit_unique_portfolio_instrument(tmp_path):
    service, _, definition = _service(tmp_path, registered=True)
    with pytest.raises(ValueError, match="TARGETS_INVALID"):
        service.run(portfolio_snapshot=_snapshot(), canonical_instrument_ids=(PORTFOLIO_FIVE_CANONICAL_INSTRUMENT_IDS[0],) * 2,
                    strategy_version=definition.reference)
    with pytest.raises(ValueError, match="TARGET_NOT_IN_PORTFOLIO"):
        service.run(portfolio_snapshot=_snapshot(), canonical_instrument_ids=("NSE:NOT_A_HOLDING",), strategy_version=definition.reference)


def test_targeted_ohlcv_adapter_delegates_only_exact_portfolio_ids(tmp_path):
    job = TargetedRefreshJob()
    request = EvidenceRefreshRequest("run", EvidenceDataFamily.OHLCV, EvidenceRefreshMode.INCREMENTAL, ANALYSIS_TIME, ANALYSIS_TIME, None, 0)
    result = refresh_targeted_holding_ohlcv(
        job=job, request=request, portfolio_snapshot=_snapshot(),
        canonical_instrument_ids=PORTFOLIO_FIVE_CANONICAL_INSTRUMENT_IDS,
    )
    assert result.status is EvidenceRefreshStatus.NO_CHANGE
    assert job.targets == frozenset(PORTFOLIO_FIVE_CANONICAL_INSTRUMENT_IDS)


def test_persisted_diagnostic_source_is_exact_asof_and_future_records_do_not_rehydrate(tmp_path):
    _, governance, definition = _service(tmp_path, registered=True)
    future = DiagnosticResult("future", PORTFOLIO_FIVE_CANONICAL_INSTRUMENT_IDS[0], "46", definition.reference,
                              "TRIGGERED", None, None, (), (), ANALYSIS_TIME + timedelta(days=1), ANALYSIS_TIME + timedelta(days=1))
    assert rehydrate_persisted_canonical_diagnostics((future,), instrument_id=future.instrument_id, as_of=ANALYSIS_TIME) == ()
    current = canonical_diagnostic_result(
        id="current", instrument_id=future.instrument_id, rule_id="46", strategy_version=definition.reference,
        canonical_strategy_fingerprint=definition.semantic_fingerprint,
        canonical_limitations_fingerprint=governance_limitations_fingerprint(definition.governance_limitations),
        result="INSUFFICIENT_DATA", score=None, confidence=None, evidence_ids=(), input_observation_ids=(),
        evaluated_at=ANALYSIS_TIME, as_of_timestamp=ANALYSIS_TIME,
    )
    governance.save_diagnostic_result(current)
    source = ResearchDiagnosticEvidenceStoredSource(ExactAsOfStrategyGovernanceDiagnosticResultSource(
        governance, strategy_version=definition.reference,
    ))
    artifacts = source.list_stored_intelligence_artifacts(current.instrument_id, as_of=ANALYSIS_TIME)
    assert artifacts[0].availability.value == "PARTIAL"
    assembled = StoredSharedBrainEvidenceAssembler(SQLiteFinancialFactStore(tmp_path / "facts.db"), diagnostics=source).assemble(
        _instrument(current.instrument_id), as_of=ANALYSIS_TIME,
    )
    diagnostic_reference = next(item for item in assembled.unified_state.evidence_references if item.domain.value == "RESEARCH_DIAGNOSTICS")
    assert diagnostic_reference.availability.value == "PARTIAL"
    rehydrated = rehydrate_persisted_canonical_diagnostics((current,), instrument_id=current.instrument_id, as_of=ANALYSIS_TIME)
    assert rehydrated[0].eligibility is EvaluationEligibility.INELIGIBLE_MISSING_DATA
