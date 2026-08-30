"""Public mapper for the read-only Production-v1 Shared Brain view."""
from __future__ import annotations

from app.api.schemas.shared_brain import (
    EvidenceDomainResponse,
    FinancialSemanticResponse,
    ForwardPaperAggregateResponse,
    ForwardPaperIntelligenceResponse,
    SharedBrainAnalysisResponse,
)
from app.intelligence.shared_brain_application import SharedBrainAnalysisView


def shared_brain_analysis_response(value: SharedBrainAnalysisView) -> SharedBrainAnalysisResponse:
    return SharedBrainAnalysisResponse(
        canonical_instrument_id=value.canonical_instrument_id,
        symbol=value.symbol,
        name=value.name,
        exchange=value.exchange,
        as_of=value.as_of,
        requested_context=value.requested_context.value,
        evidence_status=value.evidence_status,
        evidence_domains=tuple(EvidenceDomainResponse(domain=domain, availability=availability) for domain, availability in value.evidence_domains),
        financial_semantics=tuple(FinancialSemanticResponse(**{
            field: getattr(item, field) for field in item.__dataclass_fields__
        }) for item in value.financial_semantics),
        blockers=value.blockers,
        warnings=value.warnings,
        snapshot_fingerprint=value.snapshot_fingerprint,
        unified_state_fingerprint=value.unified_state_fingerprint,
        brain_research_state_v2_fingerprint=value.brain_research_state_v2_fingerprint,
        context_projection_fingerprint=value.context_projection_fingerprint,
        financial_semantic_section_fingerprint=value.financial_semantic_section_fingerprint,
        materiality_policy_id=value.materiality_policy_id,
        materiality_policy_version=value.materiality_policy_version,
        materiality_policy_fingerprint=value.materiality_policy_fingerprint,
        materiality_calibration_status=value.materiality_calibration_status,
        forward_performance_intelligence=ForwardPaperIntelligenceResponse(
            instrument_history=ForwardPaperAggregateResponse(**{
                field: getattr(value.forward_performance_intelligence.instrument_history, field)
                for field in value.forward_performance_intelligence.instrument_history.__dataclass_fields__
            }),
            relevant_cohort_history=ForwardPaperAggregateResponse(**{
                field: getattr(value.forward_performance_intelligence.relevant_cohort_history, field)
                for field in value.forward_performance_intelligence.relevant_cohort_history.__dataclass_fields__
            }),
            warnings=value.forward_performance_intelligence.warnings,
        ),
    )
