from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from app.domain.models import FreshnessStatus
from app.intelligence.output_evaluation_context import create_brain_output_evaluation_context
from app.intelligence.output_projection import (
    BrainOutputProjectionError,
    BrainOutputProjectionSectionKind,
    BrainOutputProjectionStatus,
    CURRENT_BRAIN_OUTPUT_PROJECTION_POLICY,
    project_brain_output,
)
from app.intelligence.unified_state import (
    BrainOutputContext,
    IntelligenceEvidenceAvailability,
    IntelligenceEvidenceDomain,
    IntelligenceEvidenceReference,
    IntelligenceStateCompleteness,
    create_brain_output_request,
    create_unified_intelligence_state,
)
from tests.unit.test_brain_output_evaluation_context import _gate, _request, _score, _state


def _context(context: BrainOutputContext):
    if context in {BrainOutputContext.ENTRY_SETUP_REVIEW, BrainOutputContext.OPPORTUNITY_DISCOVERY}:
        score = _score(); gate = _gate(score=score, action="FRESH_ENTRY")
        state = _state(score=score, gate=gate)
        return state, create_brain_output_evaluation_context(
            state, _request(state, context), decision_scorecard=score, gate_evaluation=gate,
        )
    if context is BrainOutputContext.ROTATION_REVIEW:
        score = _score(); gate = _gate(score=score, action="ROTATE_IN")
        state = _state(score=score, gate=gate)
        return state, create_brain_output_evaluation_context(
            state, _request(state, context), decision_scorecard=score, gate_evaluation=gate,
        )
    state = _state()
    portfolio = "snapshot:1" if context in {
        BrainOutputContext.PORTFOLIO_REVIEW, BrainOutputContext.SELL_TRIM_REVIEW,
    } else None
    return state, create_brain_output_evaluation_context(state, _request(state, context, portfolio=portfolio))


def _kinds(value):
    return tuple(section.kind for section in value.sections)


def test_validated_entry_context_projects_deterministically_without_action_fields():
    state, context = _context(BrainOutputContext.ENTRY_SETUP_REVIEW)
    first = project_brain_output(context)
    repeated = project_brain_output(context)
    assert first == repeated
    # A coherent context may still surface truthfully partial stored evidence.
    assert first.status is BrainOutputProjectionStatus.PARTIAL
    assert first.unified_state_fingerprint == state.fingerprint
    assert first.evaluation_context_fingerprint == context.fingerprint
    assert first.requirement_policy_fingerprint == context.requirement_policy_fingerprint
    assert BrainOutputProjectionSectionKind.ENTRY_CONTEXT in _kinds(first)
    assert not any(hasattr(first, field) for field in (
        "recommendation", "action", "buy", "sell", "hold", "trim", "rotate", "signal", "order", "paper_trade",
    ))


def test_non_ready_context_is_rejected_with_preserved_blocker_codes():
    state = _state()
    blocked = create_brain_output_evaluation_context(
        state, _request(state, BrainOutputContext.ENTRY_SETUP_REVIEW, portfolio=None),
    )
    with pytest.raises(BrainOutputProjectionError, match="REQUIRED_GATE_MISSING"):
        project_brain_output(blocked)


@pytest.mark.parametrize("context", tuple(BrainOutputContext))
def test_all_contexts_have_exact_projection_policy_sections_and_reuse_state(context):
    state, evaluation = _context(context)
    projection = project_brain_output(evaluation)
    requirement = CURRENT_BRAIN_OUTPUT_PROJECTION_POLICY.requirement_for(context)
    assert _kinds(projection) == requirement.section_kinds
    assert projection.unified_state_id == state.state_id
    assert projection.unified_state_fingerprint == state.fingerprint
    assert projection.evaluation_context_id == evaluation.evaluation_context_id
    assert projection.output_context is context


def test_context_changes_view_composition_but_never_changes_shared_state():
    score = _score(); gate = _gate(score=score)
    state = _state(score=score, gate=gate)
    entry = create_brain_output_evaluation_context(
        state, _request(state, BrainOutputContext.ENTRY_SETUP_REVIEW), decision_scorecard=score, gate_evaluation=gate,
    )
    deep = create_brain_output_evaluation_context(state, _request(state, BrainOutputContext.DEEP_ANALYSIS, portfolio=None))
    entry_projection = project_brain_output(entry)
    deep_projection = project_brain_output(deep)
    assert entry_projection.fingerprint != deep_projection.fingerprint
    assert entry_projection.unified_state_fingerprint == deep_projection.unified_state_fingerprint == state.fingerprint
    assert _kinds(entry_projection) != _kinds(deep_projection)


def test_projection_is_frozen_and_policy_identity_is_retained():
    _, context = _context(BrainOutputContext.ROTATION_REVIEW)
    projection = project_brain_output(context)
    with pytest.raises(FrozenInstanceError):
        projection.status = BrainOutputProjectionStatus.PARTIAL
    assert projection.projection_policy_fingerprint == CURRENT_BRAIN_OUTPUT_PROJECTION_POLICY.fingerprint
    assert projection.requirement_policy_id == context.requirement_policy_id


@pytest.mark.parametrize("availability", (
    IntelligenceEvidenceAvailability.PARTIAL,
    IntelligenceEvidenceAvailability.STALE,
    IntelligenceEvidenceAvailability.CONFLICTED,
    IntelligenceEvidenceAvailability.UNAVAILABLE,
))
def test_selected_evidence_availability_remains_visible(availability):
    at = datetime(2026, 8, 29, 10, tzinfo=UTC)
    reference = IntelligenceEvidenceReference(
        domain=IntelligenceEvidenceDomain.TECHNICAL, availability=availability,
        artifact_ids=("technical:1",), artifact_fingerprints=("technical-fingerprint",),
        evidence_as_of=at, observed_at=at, freshness_status=FreshnessStatus.UNKNOWN,
        freshness_policy_reference=None, source_provenance_fingerprint=None,
        historical_integrity_reference=None, warnings=(f"EVIDENCE_{availability.value}",),
    )
    state = create_unified_intelligence_state(
        canonical_instrument_id="NSE:INE000A01001", as_of=at, evaluation_session=None,
        state_schema_version="v1", intelligence_contract_version="v1",
        evidence_references=(reference,), completeness=IntelligenceStateCompleteness.PARTIAL,
    )
    context = create_brain_output_evaluation_context(
        state, create_brain_output_request(state, output_context=BrainOutputContext.DEEP_ANALYSIS),
    )
    projection = project_brain_output(context)
    technical = next(value for value in projection.sections if value.kind is BrainOutputProjectionSectionKind.TECHNICAL_SETUP)
    assert technical.evidence_references == (reference,)
    assert projection.status is BrainOutputProjectionStatus.PARTIAL
    assert f"EVIDENCE_{availability.value}" in projection.warnings


def test_projection_identity_changes_when_context_state_identity_changes():
    first_state, first_context = _context(BrainOutputContext.DEEP_ANALYSIS)
    second_state = _state(as_of=first_state.as_of + timedelta(hours=1))
    second_context = create_brain_output_evaluation_context(
        second_state, _request(second_state, BrainOutputContext.DEEP_ANALYSIS, portfolio=None),
    )
    assert project_brain_output(first_context).fingerprint != project_brain_output(second_context).fingerprint


def test_contract_is_pure_and_has_no_engine_network_or_persistence_surface():
    source = (Path(__file__).parents[2] / "app" / "intelligence" / "output_projection.py").read_text(encoding="utf-8")
    assert not any(token in source for token in (
        "build_scorecard", "evaluate_six_gates", "Canonical61DiagnosticRunner", "requests.", "urlopen", "httpx",
        "CREATE TABLE", "INSERT INTO", "Signal", "PaperTrade", "order(", "recommend(", "execute(",
    ))
