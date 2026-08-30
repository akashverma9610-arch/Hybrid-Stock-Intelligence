"""Public, read-only Shared Brain application projection schemas."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class FinancialSemanticResponse(BaseModel):
    metric: str
    trajectory_basis: str
    previous_period_label: str | None
    current_period_label: str | None
    previous_value: Decimal | None
    current_value: Decimal | None
    absolute_delta: Decimal | None
    relative_delta: Decimal | None
    sign_transition: str | None
    factual_display_phrase: str | None
    directionality_orientation: str | None
    directionality_rationale_code: str | None
    materiality_governance_state: str
    trajectory_fingerprint: str
    directionality_fingerprint: str | None


class EvidenceDomainResponse(BaseModel):
    domain: str
    availability: str


class ForwardPaperAggregateResponse(BaseModel):
    evidence_sufficiency: str
    scope: str
    cohort_definition: tuple[str, ...]
    as_of: datetime
    aggregation_version: str
    sample_count: int
    completed_count: int
    eligible_realized_count: int
    open_count: int
    waiting_count: int
    ambiguous_count: int
    blocked_count: int
    expired_unfilled_count: int
    missed_do_not_chase_count: int
    win_rate: Decimal | None
    expectancy_r: Decimal | None
    median_r: Decimal | None
    average_r: Decimal | None
    average_gross_r: Decimal | None
    median_gross_r: Decimal | None
    profit_factor: Decimal | None
    median_mfe_r: Decimal | None
    median_mae_r: Decimal | None
    average_holding_sessions: Decimal | None
    target_hit_rate: Decimal | None
    stop_hit_rate: Decimal | None
    expired_unfilled_rate: Decimal | None
    missed_do_not_chase_rate: Decimal | None
    source_study_ids: tuple[str, ...]
    source_study_fingerprints: tuple[str, ...]
    policy_versions: tuple[str, ...]
    execution_model_versions: tuple[str, ...]
    direction_values: tuple[str, ...]
    fingerprint: str


class ForwardPaperIntelligenceResponse(BaseModel):
    instrument_history: ForwardPaperAggregateResponse
    relevant_cohort_history: ForwardPaperAggregateResponse
    warnings: tuple[str, ...]


class SharedBrainAnalysisResponse(BaseModel):
    canonical_instrument_id: str
    symbol: str
    name: str | None
    exchange: str
    as_of: datetime
    requested_context: str
    evidence_status: str
    evidence_domains: tuple[EvidenceDomainResponse, ...]
    financial_semantics: tuple[FinancialSemanticResponse, ...]
    blockers: tuple[str, ...]
    warnings: tuple[str, ...]
    snapshot_fingerprint: str
    unified_state_fingerprint: str
    brain_research_state_v2_fingerprint: str
    context_projection_fingerprint: str
    financial_semantic_section_fingerprint: str
    materiality_policy_id: str
    materiality_policy_version: str
    materiality_policy_fingerprint: str
    materiality_calibration_status: str
    forward_performance_intelligence: ForwardPaperIntelligenceResponse
