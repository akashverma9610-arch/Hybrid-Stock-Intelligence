"""Isolated end-to-end execution-gate canary using the approved policies only.

The fixtures in this module are deliberately synthetic and are persisted only
to pytest's temporary SQLite database.  They never use a real NSE identity,
portfolio snapshot, surveillance source, earnings source, or order path.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
import json
from pathlib import Path
import re

import pytest
from tests.fixtures.gate_provenance import synthetic_evaluate
from app.gates.score_provenance import score_evidence

from app.domain.canonical_diagnostic_strategy import (
    CanonicalDiagnosticDefinitionStatus,
    CanonicalDiagnosticGovernanceLimitation,
    CanonicalDiagnosticStrategyDefinition,
    governance_limitations_fingerprint,
    semantic_fingerprint_for_payload,
)
from app.domain.models import canonical_diagnostic_result
from app.gates.engine import (
    ActionContext,
    ExchangeCalendar,
    ExecutionEligibility,
    GateInput,
    GateOutcome,
    PortfolioExposure,
    SurveillanceObservation,
    TradeManagementPlan,
)
from app.gates.production_policy import (
    approved_six_gates_production_policy,
    selected_production_gate_engine,
)
from app.historical.guard import manifest_fingerprint
from app.portfolio.canonical_decision_score import canonical_decision_scorecard_from
from app.portfolio.canonical_diagnostics_orchestration import (
    rehydrate_persisted_canonical_diagnostics,
)
from app.portfolio.canonical_six_gates import canonical_execution_gate_evaluation_from
from app.registry.canonical import DIAGNOSTIC_REGISTRY_VERSION, SCORING_POLICY
from app.scoring.engine import build_scorecard
from app.storage.sqlite_governance_repository import SQLiteStrategyGovernanceRepository


CANARY_INSTRUMENT_ID = "TEST:HSI_SIX_GATES_CANARY"
POLICY_APPROVED_AT = datetime(2026, 9, 1, 7, 26, 54, 636363, tzinfo=UTC)
EXECUTION_AS_OF = datetime(2026, 9, 1, 10, tzinfo=UTC)
SCORE_AS_OF = EXECUTION_AS_OF - timedelta(minutes=10)
SETUP_AS_OF = EXECUTION_AS_OF - timedelta(minutes=15)
EXPECTED_POLICY_FINGERPRINT = "a275a4dc33136009ba62abd77516abd8fcd87721df125fb7de25fb1c3e55c881"


@dataclass(frozen=True, slots=True)
class _SyntheticSetup:
    """Test-fixture authority for the Setup-to-gate contract only."""

    setup_id: str
    instrument_id: str
    setup_as_of: datetime
    entry: Decimal
    structural_stop: Decimal
    t1: Decimal
    t2: Decimal
    extended_target: Decimal
    risk_reward: Decimal
    setup_horizon: str
    initial_tranche: Decimal
    t1_reduction: Decimal
    breakeven_conditions: str
    evidence_ids: tuple[str, ...]
    policy_fingerprint: str
    fingerprint: str

    @classmethod
    def create(cls) -> "_SyntheticSetup":
        values = dict(
            setup_id="synthetic-setup:HSI_SIX_GATES_CANARY:v1",
            instrument_id=CANARY_INSTRUMENT_ID,
            setup_as_of=SETUP_AS_OF,
            entry=Decimal("100"), structural_stop=Decimal("95"), t1=Decimal("110"),
            t2=Decimal("115"), extended_target=Decimal("120"), risk_reward=Decimal("4.00"),
            setup_horizon="SYNTHETIC_TEST_ONLY", initial_tranche=Decimal("0.50"),
            t1_reduction=Decimal("0.50"), breakeven_conditions="Move stop to entry after T1",
            evidence_ids=("fixture-authority:setup", "fixture-authority:market-structure"),
            policy_fingerprint="synthetic-setup-contract-v1",
        )
        return cls(**values, fingerprint=manifest_fingerprint(**values))

    def verify_integrity(self) -> None:
        assert self.instrument_id == CANARY_INSTRUMENT_ID
        assert self.setup_as_of <= EXECUTION_AS_OF
        assert self.entry > self.structural_stop
        assert self.t1 > self.entry and self.t2 > self.t1 and self.extended_target > self.t2
        assert self.risk_reward > Decimal("0")
        assert self.initial_tranche == Decimal("0.50")
        assert self.t1_reduction == Decimal("0.50")
        assert self.breakeven_conditions
        assert self.fingerprint == manifest_fingerprint(**{
            key: getattr(self, key) for key in self.__dataclass_fields__ if key != "fingerprint"
        })

    def trade_plan(self) -> TradeManagementPlan:
        self.verify_integrity()
        return TradeManagementPlan(
            self.setup_id, self.initial_tranche, self.t1_reduction, True, True,
            self.breakeven_conditions, "synthetic structural stop", "decision-score-policy-v1",
            "six-gates-production-v1",
        )


@dataclass(slots=True)
class _CanaryContext:
    repository: SQLiteStrategyGovernanceRepository
    policy: object
    score: object
    setup: _SyntheticSetup
    modeled_friction: Decimal

    def base_input(self, **changes) -> GateInput:
        value = GateInput(
            scorecard_id=self.score.id,
            raw_decision_score=self.score.final_score,
            snapshot_id="synthetic-execution-snapshot:HSI_SIX_GATES_CANARY:v1",
            snapshot_as_of_timestamp=EXECUTION_AS_OF,
            comparison_score=self.score.final_score - Decimal("1.00"),
            expected_incremental_return=Decimal("500"),
            modeled_switching_friction=self.modeled_friction,
            holding_entry_date=date(2026, 8, 10),
            atr_expansion=Decimal("1.10"),
            surveillance=SurveillanceObservation(
                "fixture-authority:surveillance", EXECUTION_AS_OF - timedelta(minutes=5),
                "TEST_FIXTURE_AUTHORITY", True, 0, 0, Decimal("0.10"),
                ("fixture-authority:surveillance",),
            ),
            trade_plan=self.setup.trade_plan(),
            exposure=PortfolioExposure(
                Decimal("100000"), Decimal("4000"), Decimal("1000"), Decimal("0.20"),
                Decimal("0.30"), ("fixture-authority:portfolio",),
            ),
            earnings_scheduled_at=EXECUTION_AS_OF + timedelta(days=14),
            earnings_schedule_verified_at=EXECUTION_AS_OF - timedelta(minutes=2),
            evidence_ids=(
                *self.setup.evidence_ids, "fixture-authority:friction",
                "fixture-authority:earnings", "fixture-authority:portfolio",
            ),
            diagnostic_ids=tuple(item.record.id for item in self._diagnostics()),
        )
        return replace(value, **changes)

    def _diagnostics(self):
        return rehydrate_persisted_canonical_diagnostics(
            self.repository.list_diagnostic_results(self.score.strategy_version, SCORE_AS_OF),
            instrument_id=CANARY_INSTRUMENT_ID, as_of=SCORE_AS_OF,
        )

    def evaluate(self, *, action_context=ActionContext.ROTATE_IN, **changes):
        self.policy.pit_contract.validate(
            decision_score_as_of=self.score.as_of_timestamp,
            portfolio_snapshot_as_of=EXECUTION_AS_OF,
            setup_as_of=self.setup.setup_as_of,
            surveillance_as_of=(changes.get("surveillance") or self.base_input().surveillance).effective_at,
            earnings_verified_as_of=changes.get("earnings_schedule_verified_at", EXECUTION_AS_OF - timedelta(minutes=2)),
            friction_policy_effective_at=self.policy.friction_model.effective_at,
            execution_gate_as_of=EXECUTION_AS_OF,
        )
        engine = selected_production_gate_engine(
            repository=self.repository, calendar=ExchangeCalendar("NSE-synthetic-canary"),
            as_of=EXECUTION_AS_OF,
        )
        return synthetic_evaluate(engine,
            instrument_id=CANARY_INSTRUMENT_ID, strategy_version=self.score.strategy_version,
            registry_version=DIAGNOSTIC_REGISTRY_VERSION,
            scoring_configuration_version=self.score.configuration_version,
            action_context=action_context, as_of_timestamp=EXECUTION_AS_OF,
            evaluated_at=EXECUTION_AS_OF, inputs=self.base_input(**changes),
            candidate_score_evidence=score_evidence(self.score),
        )


def _definition() -> CanonicalDiagnosticStrategyDefinition:
    root = Path(__file__).parents[2]
    def parse(path: Path) -> dict:
        return json.loads(re.search(r"```json\r?\n(\{.*?\})\r?\n```", path.read_text(encoding="utf-8"), re.S).group(1))
    payload = parse(root / "docs" / "architecture" / "CANONICAL_UNIVERSE_ANALYSIS_V1_DEFINITION_PROPOSAL.md")
    approval = parse(root / "docs" / "architecture" / "CANONICAL_UNIVERSE_ANALYSIS_V1_APPROVAL.md")
    return CanonicalDiagnosticStrategyDefinition(
        strategy_id=payload["strategy"]["id"], strategy_version=payload["strategy"]["version"],
        canonical_payload=payload, semantic_fingerprint=semantic_fingerprint_for_payload(payload),
        governance_limitations=tuple(CanonicalDiagnosticGovernanceLimitation(**item) for item in approval["governance_limitations"]),
        definition_status=CanonicalDiagnosticDefinitionStatus.APPROVED, reviewer_id=approval["reviewer"],
        definition_proposal_artifact="docs/architecture/CANONICAL_UNIVERSE_ANALYSIS_V1_DEFINITION_PROPOSAL.md",
        human_approval_artifact="docs/architecture/CANONICAL_UNIVERSE_ANALYSIS_V1_APPROVAL.md",
        created_at=SCORE_AS_OF, registered_at=SCORE_AS_OF,
    )


@pytest.fixture
def canary(tmp_path) -> _CanaryContext:
    """Build the complete synthetic chain in a fresh SQLite file only."""
    repository = SQLiteStrategyGovernanceRepository(tmp_path / "six-gates-canary.db")
    definition = _definition()
    repository.save_canonical_diagnostic_strategy_definition(definition)
    limitations_fingerprint = governance_limitations_fingerprint(definition.governance_limitations)
    for rule_id in range(1, 62):
        repository.save_diagnostic_result(canonical_diagnostic_result(
            id=f"synthetic-diagnostic:{rule_id}", instrument_id=CANARY_INSTRUMENT_ID,
            rule_id=str(rule_id), strategy_version=definition.reference,
            canonical_strategy_fingerprint=definition.semantic_fingerprint,
            canonical_limitations_fingerprint=limitations_fingerprint, result="VALID", score=None,
            confidence=0.95, evidence_ids=(f"fixture-authority:diagnostic:{rule_id}",),
            input_observation_ids=(f"fixture-authority:input:{rule_id}",),
            evaluated_at=SCORE_AS_OF, as_of_timestamp=SCORE_AS_OF,
        ))
    score = build_scorecard(
        instrument_id=CANARY_INSTRUMENT_ID, strategy_version=definition.reference,
        registry_version=DIAGNOSTIC_REGISTRY_VERSION, as_of_timestamp=SCORE_AS_OF,
        evaluated_at=SCORE_AS_OF,
        diagnostics=rehydrate_persisted_canonical_diagnostics(
            repository.list_diagnostic_results(definition.reference, SCORE_AS_OF),
            instrument_id=CANARY_INSTRUMENT_ID, as_of=SCORE_AS_OF,
        ), configuration_version="decision-score-policy-v1",
    )
    canonical_score = canonical_decision_scorecard_from(
        score, definition=definition, scoring_policy=SCORING_POLICY,
        latest_completed_market_session=SCORE_AS_OF - timedelta(days=1),
    )
    repository.save_canonical_decision_scorecard(canonical_score)
    policy = approved_six_gates_production_policy(
        approved_at=POLICY_APPROVED_AT, effective_at=POLICY_APPROVED_AT,
    )
    assert policy.fingerprint == EXPECTED_POLICY_FINGERPRINT
    repository.save_six_gates_production_policy(policy)
    friction = policy.friction_model.modeled_switching_friction(
        purchase_turnover=Decimal("100000"), sale_turnover=Decimal("100000"),
        brokerage=Decimal("10"), slippage=Decimal("10"), capital_gains_tax=Decimal("10"),
        gst_taxable_services=Decimal("10"),
    )
    assert friction is not None and Decimal("500") - friction > Decimal("0")
    value = _CanaryContext(repository, policy, canonical_score, _SyntheticSetup.create(), friction)
    yield value
    repository.close()


def _gate(result, gate_id: str):
    return next(item for item in result.decisions if item.gate_id == gate_id)


def test_isolated_all_pass_chain_is_immutable_and_never_creates_an_order(canary, tmp_path) -> None:
    database_path = Path(canary.repository._connection.execute("PRAGMA database_list").fetchone()[2])
    assert database_path.resolve() == (tmp_path / "six-gates-canary.db").resolve()
    assert CANARY_INSTRUMENT_ID.startswith("TEST:")
    canary.setup.verify_integrity()
    assert canary.score.scoring_policy_version == "decision-score-policy-v1"
    assert canary.score.as_of_timestamp <= EXECUTION_AS_OF
    result = canary.evaluate()
    assert [item.outcome for item in result.decisions] == [GateOutcome.PASS] * 6
    assert result.eligibility is ExecutionEligibility.EXECUTABLE
    assert result.failed_gate_ids == () and result.insufficient_gate_ids == ()
    assert "NO_ACTION_OR_ORDER_CREATED" in result.warnings
    persisted = canonical_execution_gate_evaluation_from(result, score=canary.score)
    assert canary.repository.save_canonical_execution_gate_evaluation(persisted) == persisted
    assert canary.repository.save_canonical_execution_gate_evaluation(persisted) == persisted
    assert canary.repository._connection.execute("SELECT COUNT(*) FROM canonical_execution_gate_evaluations").fetchone()[0] == 1
    assert canary.repository._connection.execute("SELECT COUNT(*) FROM canonical_execution_gate_decisions").fetchone()[0] == 6
    assert canary.repository._connection.execute("SELECT COUNT(*) FROM strategy_versions").fetchone()[0] == 0
    assert canary.repository._connection.execute("SELECT COUNT(*) FROM execution_gate_evaluations").fetchone()[0] == 0


@pytest.mark.parametrize(("label", "action_context", "changes", "gate_id", "outcome"), [
    ("score advantage", ActionContext.ROTATE_IN, {"comparison_score": Decimal("6.01")}, "GATE_1_ROTATION", GateOutcome.FAIL),
    ("missing friction", ActionContext.ROTATE_IN, {"modeled_switching_friction": None}, "GATE_1_ROTATION", GateOutcome.INSUFFICIENT_DATA),
    ("velocity", ActionContext.HOLD_EXISTING, {"atr_expansion": Decimal("0.99")}, "GATE_2_VELOCITY", GateOutcome.FAIL),
    ("asm", ActionContext.ROTATE_IN, {"surveillance": SurveillanceObservation("fixture:asm", EXECUTION_AS_OF, "TEST_FIXTURE_AUTHORITY", True, 2, 0, Decimal("0.10"))}, "GATE_3_SURVEILLANCE", GateOutcome.FAIL),
    ("gsm", ActionContext.ROTATE_IN, {"surveillance": SurveillanceObservation("fixture:gsm", EXECUTION_AS_OF, "TEST_FIXTURE_AUTHORITY", True, 0, 1, Decimal("0.10"))}, "GATE_3_SURVEILLANCE", GateOutcome.FAIL),
    ("circuit", ActionContext.ROTATE_IN, {"surveillance": SurveillanceObservation("fixture:circuit", EXECUTION_AS_OF, "TEST_FIXTURE_AUTHORITY", True, 0, 0, Decimal("0.05"))}, "GATE_3_SURVEILLANCE", GateOutcome.FAIL),
    ("stale surveillance", ActionContext.ROTATE_IN, {"surveillance": SurveillanceObservation("fixture:stale", EXECUTION_AS_OF - timedelta(days=8), "TEST_FIXTURE_AUTHORITY", True, 0, 0, Decimal("0.10"))}, "GATE_3_SURVEILLANCE", GateOutcome.INSUFFICIENT_DATA),
    ("tranche", ActionContext.ROTATE_IN, {"trade_plan": TradeManagementPlan("fixture:bad-tranche", Decimal("0.51"), Decimal("0.50"), True, True, "Move stop to entry after T1", "synthetic", "decision-score-policy-v1", "six-gates-production-v1")}, "GATE_4_TRADE_PLAN", GateOutcome.FAIL),
    ("breakeven", ActionContext.ROTATE_IN, {"trade_plan": TradeManagementPlan("fixture:no-breakeven", Decimal("0.50"), Decimal("0.50"), True, True, None, "synthetic", "decision-score-policy-v1", "six-gates-production-v1")}, "GATE_4_TRADE_PLAN", GateOutcome.FAIL),
    ("heat", ActionContext.ROTATE_IN, {"exposure": PortfolioExposure(Decimal("100000"), Decimal("6000"), Decimal("1000"), Decimal("0.20"), Decimal("0.30"))}, "GATE_5_HEAT", GateOutcome.FAIL),
    ("stock allocation", ActionContext.ROTATE_IN, {"exposure": PortfolioExposure(Decimal("100000"), Decimal("4000"), Decimal("1000"), Decimal("0.26"), Decimal("0.30"))}, "GATE_5_HEAT", GateOutcome.FAIL),
    ("sector allocation", ActionContext.ROTATE_IN, {"exposure": PortfolioExposure(Decimal("100000"), Decimal("4000"), Decimal("1000"), Decimal("0.20"), Decimal("0.36"))}, "GATE_5_HEAT", GateOutcome.FAIL),
    ("unknown portfolio equity", ActionContext.ROTATE_IN, {"exposure": PortfolioExposure(None, Decimal("4000"), Decimal("1000"), Decimal("0.20"), Decimal("0.30"))}, "GATE_5_HEAT", GateOutcome.INSUFFICIENT_DATA),
    ("earnings blackout", ActionContext.FRESH_ENTRY, {"earnings_scheduled_at": EXECUTION_AS_OF + timedelta(days=4)}, "GATE_6_EARNINGS", GateOutcome.FAIL),
    ("unverified earnings", ActionContext.FRESH_ENTRY, {"earnings_schedule_verified_at": None}, "GATE_6_EARNINGS", GateOutcome.INSUFFICIENT_DATA),
])
def test_each_required_gate_independently_blocks_the_isolated_canary(
    canary, label, action_context, changes, gate_id, outcome,
) -> None:
    result = canary.evaluate(action_context=action_context, **changes)
    assert _gate(result, gate_id).outcome is outcome, label
    assert result.eligibility is not ExecutionEligibility.EXECUTABLE, label


@pytest.mark.parametrize("context", [
    ActionContext.HOLD_EXISTING, ActionContext.REDUCE_EXISTING,
    ActionContext.EXIT_EXISTING, ActionContext.RISK_MANAGEMENT,
])
def test_earnings_blackout_does_not_block_defensive_contexts(canary, context) -> None:
    result = canary.evaluate(
        action_context=context, earnings_scheduled_at=EXECUTION_AS_OF + timedelta(days=1),
        earnings_schedule_verified_at=None,
    )
    assert _gate(result, "GATE_6_EARNINGS").outcome is GateOutcome.PASS


def test_pit_contract_rejects_lookahead_and_all_gates_are_required(canary) -> None:
    with pytest.raises(ValueError, match="LOOKAHEAD"):
        canary.policy.pit_contract.validate(
            decision_score_as_of=canary.score.as_of_timestamp,
            portfolio_snapshot_as_of=EXECUTION_AS_OF,
            setup_as_of=EXECUTION_AS_OF + timedelta(seconds=1),
            surveillance_as_of=EXECUTION_AS_OF,
            earnings_verified_as_of=EXECUTION_AS_OF,
            friction_policy_effective_at=canary.policy.friction_model.effective_at,
            execution_gate_as_of=EXECUTION_AS_OF,
        )
    result = canary.evaluate(trade_plan=TradeManagementPlan(
        "fixture:missing-stop", Decimal("0.50"), Decimal("0.50"), False, True,
        "Move stop to entry after T1", "synthetic", "decision-score-policy-v1", "six-gates-production-v1",
    ))
    assert _gate(result, "GATE_4_TRADE_PLAN").outcome is GateOutcome.FAIL
    assert result.eligibility is ExecutionEligibility.BLOCKED
