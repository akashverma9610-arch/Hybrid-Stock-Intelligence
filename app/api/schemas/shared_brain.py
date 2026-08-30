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
