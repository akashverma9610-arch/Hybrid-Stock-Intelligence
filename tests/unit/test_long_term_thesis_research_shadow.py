from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime, timedelta, timezone
import ast
import inspect
from pathlib import Path

import pytest

import app.intelligence.long_term_thesis_research_shadow as module
from app.intelligence.long_term_thesis_review import (
    DeepAnalysisDossierCandidate,
    DossierEvidenceState,
    FINGERPRINT_SCHEME as REVIEW_FINGERPRINT_SCHEME,
    LongTermThesisFamily,
    LongTermThesisReviewContext,
    ThesisLineageReference,
    deep_analysis_dossier_candidate,
    review_long_term_thesis,
)
from app.intelligence.long_term_thesis_research_shadow import *


T = datetime(2026, 9, 3, 10, tzinfo=UTC)
FP = "sha256:" + "a" * 64


def _reference(name: str, at: datetime = T - timedelta(minutes=2)) -> ThesisLineageReference:
    return ThesisLineageReference(name, FP, at)


def _review(family: LongTermThesisFamily = LongTermThesisFamily.QUALITY_FAIR_VALUE):
    candidate = deep_analysis_dossier_candidate(
        canonical_instrument_id="NSE:INE000000001",
        dossier_id="brain-output-projection:1",
        dossier_fingerprint=FP,
        source_policy_version="brain-output-v1",
        dossier_as_of=T - timedelta(minutes=3),
        available_at=T - timedelta(minutes=2),
        evidence_state=DossierEvidenceState.AVAILABLE,
        diagnostic_lineage=(_reference("diagnostic:1"),),
        evidence_lineage=(_reference("evidence:1"),),
    )
    return review_long_term_thesis(LongTermThesisReviewContext(T, "brain-output-v1", REVIEW_FINGERPRINT_SCHEME), family, candidate)


def _coverage(family: LongTermThesisFamily, **states: ResearchShadowCoverageState):
    return tuple(
        LongTermCoverageObservation(domain, states.get(domain.value, ResearchShadowCoverageState.AVAILABLE), f"coverage:{domain.value.lower()}", FP, T - timedelta(minutes=1))
        for domain in required_coverage_domains(family)
    )


@pytest.mark.parametrize("family", tuple(LongTermThesisFamily))
def test_complete_pit_valid_coverage_is_policy_unavailable_not_positive(family):
    value = review_long_term_research_shadow(_review(family), _coverage(family))
    assert value.state is LongTermResearchShadowState.POLICY_UNAVAILABLE
    assert value.blockers == (LongTermResearchShadowReason.FAMILY_POLICY_UNAVAILABLE,)
    assert value.actionability == "WATCH_ONLY" and value.execution_status == "NON_EXECUTABLE"


@pytest.mark.parametrize(("state", "result", "reason"), (
    (ResearchShadowCoverageState.UNAVAILABLE, LongTermResearchShadowState.DATA_INSUFFICIENT, LongTermResearchShadowReason.COVERAGE_UNAVAILABLE),
    (ResearchShadowCoverageState.STALE, LongTermResearchShadowState.DATA_INSUFFICIENT, LongTermResearchShadowReason.COVERAGE_STALE),
    (ResearchShadowCoverageState.NON_COMPARABLE, LongTermResearchShadowState.DATA_INSUFFICIENT, LongTermResearchShadowReason.COVERAGE_NON_COMPARABLE),
    (ResearchShadowCoverageState.CONFLICTED, LongTermResearchShadowState.CONFLICTED, LongTermResearchShadowReason.COVERAGE_CONFLICTED),
))
def test_explicit_coverage_states_fail_closed(state, result, reason):
    family = LongTermThesisFamily.QUALITY_FAIR_VALUE
    domain = required_coverage_domains(family)[0]
    value = review_long_term_research_shadow(_review(family), _coverage(family, **{domain.value: state}))
    assert value.state is result and value.blockers == (reason,)


def test_missing_future_duplicate_and_tampered_coverage_fail_closed():
    family = LongTermThesisFamily.QUALITY_FAIR_VALUE
    complete = _coverage(family)
    missing = review_long_term_research_shadow(_review(family), complete[1:])
    future = replace(complete[0], available_at=T + timedelta(seconds=1))
    late = review_long_term_research_shadow(_review(family), (future, *complete[1:]))
    assert missing.state is LongTermResearchShadowState.DATA_INSUFFICIENT
    assert missing.blockers == (LongTermResearchShadowReason.REQUIRED_COVERAGE_MISSING,)
    assert late.state is LongTermResearchShadowState.TEMPORALLY_INVALID
    with pytest.raises(LongTermResearchShadowError, match="DOMAIN_DUPLICATE"):
        review_long_term_research_shadow(_review(family), (complete[0], complete[0], *complete[1:]))
    unrelated = LongTermCoverageObservation(LongTermCoverageDomain.DILUTION, ResearchShadowCoverageState.AVAILABLE, "coverage:unrelated", FP, T)
    with pytest.raises(LongTermResearchShadowError, match="DOMAIN_UNSUPPORTED"):
        review_long_term_research_shadow(_review(family), (*complete, unrelated))


def test_source_review_tampering_and_nonvalid_source_fail_closed():
    review = _review()
    object.__setattr__(review, "fingerprint", "sha256:" + "b" * 64)
    value = review_long_term_research_shadow(review, _coverage(review.family))
    assert value.state is LongTermResearchShadowState.UNVERIFIABLE
    assert value.blockers == (LongTermResearchShadowReason.SOURCE_REVIEW_UNVERIFIABLE,)


def test_utc_ordering_identity_and_serialization_are_deterministic():
    family = LongTermThesisFamily.FUNDAMENTAL_COMPOUNDER
    india = timezone(timedelta(hours=5, minutes=30))
    values = _coverage(family)
    shifted = tuple(replace(item, available_at=item.available_at.astimezone(india)) for item in reversed(values))
    first = review_long_term_research_shadow(_review(family), values)
    second = review_long_term_research_shadow(_review(family), shifted)
    assert first.receipt_id == second.receipt_id
    assert serialize_research_shadow(first) == serialize_research_shadow(second)


def test_immutability_and_tamper_detection():
    value = review_long_term_research_shadow(_review(), _coverage(LongTermThesisFamily.QUALITY_FAIR_VALUE))
    with pytest.raises(FrozenInstanceError):
        value.state = LongTermResearchShadowState.DATA_INSUFFICIENT
    object.__setattr__(value, "fingerprint", FP)
    with pytest.raises(LongTermResearchShadowError, match="FINGERPRINT_MISMATCH"):
        value.verify()


def test_no_forbidden_dependencies_or_contract_fields():
    source = Path(inspect.getfile(module)).read_text()
    imports = {item.name for item in ast.walk(ast.parse(source)) if isinstance(item, ast.Import) for item in item.names} | {item.module or "" for item in ast.walk(ast.parse(source)) if isinstance(item, ast.ImportFrom)}
    assert not any(item.startswith(prefix) for item in imports for prefix in ("app.portfolio", "app.storage", "app.api", "app.broker", "app.orders", "app.signals"))
    assert "datetime.now" not in source and "time.time" not in source
    forbidden = {"price", "entry", "stop", "target", "quantity", "allocation", "portfolio", "order", "broker", "score", "strength", "confidence", "materiality", "expiry"}
    assert not (set(LongTermThesisResearchShadow.__dataclass_fields__) & forbidden)
