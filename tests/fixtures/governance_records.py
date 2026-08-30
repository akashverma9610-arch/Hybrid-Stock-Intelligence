from datetime import UTC, datetime

from app.domain.models import (
    ApprovalStatus, AuthorReviewerMetadata, ConfigurationValueStatus, DataQuality,
    Evidence, EvidenceType, GateDecision, GateOutcome, Provenance, Scorecard,
    ScorecardComponent, StrategyConfiguration, StrategyDefinition, StrategyStatus,
    StrategyValidationStatus, StrategyVersionReference,
)


GOVERNANCE_TIME = datetime(2026, 8, 21, 10, 0, tzinfo=UTC)


def strategy_definition(version: str = "0.1", parent: StrategyVersionReference | None = None) -> StrategyDefinition:
    return StrategyDefinition(
        strategy_id="nse-manager", version=version, name="Mock governance strategy",
        status=StrategyStatus.DRAFT, created_at=GOVERNANCE_TIME, effective_from=None, effective_to=None,
        description="Fixture only; it makes no market or trading claim.",
        configuration=StrategyConfiguration(
            scoring_weights={"earnings_acceleration": ConfigurationValueStatus.REQUIRES_APPROVAL},
            execution_gate_parameters={"pre_earnings_blackout": ConfigurationValueStatus.REQUIRES_APPROVAL},
            portfolio_heat_limits={"portfolio_heat": ConfigurationValueStatus.UNSPECIFIED},
            sector_exposure_limits={"sector_exposure": ConfigurationValueStatus.UNSPECIFIED},
            position_limits={"position_count": ConfigurationValueStatus.UNSPECIFIED},
            risk_parameters={"per_position_risk": ConfigurationValueStatus.REQUIRES_APPROVAL},
        ),
        rule_definition_version=ConfigurationValueStatus.REQUIRES_APPROVAL,
        scoring_configuration_version=ConfigurationValueStatus.REQUIRES_APPROVAL,
        execution_gate_configuration_version=ConfigurationValueStatus.REQUIRES_APPROVAL,
        risk_configuration_version=ConfigurationValueStatus.REQUIRES_APPROVAL,
        benchmark_configuration_version=ConfigurationValueStatus.REQUIRES_APPROVAL,
        author_reviewer=AuthorReviewerMetadata("author-1", "reviewer-1"),
        approval_status=ApprovalStatus.PENDING, validation_status=StrategyValidationStatus.NOT_STARTED,
        parent_strategy_version=parent,
    )


def evidence() -> Evidence:
    return Evidence(
        id="evidence-1", source="mock-fixture", source_identifier="source-record-1", timestamp=GOVERNANCE_TIME,
        observation_ids=("mock-reliance-0900",), evidence_type=EvidenceType.DATA,
        factual_content_reference="fixture://mock-reliance-0900", confidence=1.0,
        provenance=Provenance("mock-fixture", "source-record-1", GOVERNANCE_TIME, GOVERNANCE_TIME, DataQuality.HIGH),
    )


def scorecard(reference: StrategyVersionReference, as_of: datetime) -> Scorecard:
    return Scorecard(
        id="scorecard-1", instrument_id="mock-reliance", strategy_version=reference,
        evaluated_at=GOVERNANCE_TIME, as_of_timestamp=as_of,
        components=(ScorecardComponent(
            "earnings_acceleration", ConfigurationValueStatus.REQUIRES_APPROVAL, None, None,
            ("evidence-1",), ConfigurationValueStatus.REQUIRES_APPROVAL,
        ),),
        aggregate_score=None,
    )


def gate_decision(reference: StrategyVersionReference, as_of: datetime) -> GateDecision:
    return GateDecision(
        id="gate-1", gate_name="pre_earnings_blackout", strategy_version=reference,
        outcome=GateOutcome.INSUFFICIENT_DATA, rationale="Fixture contains no earnings-calendar input.",
        evidence_ids=("evidence-1",), parameters_used={"blackout_window": ConfigurationValueStatus.REQUIRES_APPROVAL},
        evaluated_at=GOVERNANCE_TIME, as_of_timestamp=as_of,
    )
