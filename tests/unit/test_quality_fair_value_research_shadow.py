from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime, timedelta, timezone
import ast
import inspect
from pathlib import Path

import pytest

import app.intelligence.quality_fair_value_research_shadow as module
from app.intelligence.long_term_thesis_research_shadow import (
    LongTermCoverageObservation, ResearchShadowCoverageState, required_coverage_domains,
    review_long_term_research_shadow,
)
from app.intelligence.long_term_thesis_review import *
from app.intelligence.quality_fair_value_research_shadow import *

T = datetime(2026, 9, 3, 10, tzinfo=UTC)
FP = "sha256:" + "a" * 64


def _receipt(*, coverage_state=ResearchShadowCoverageState.AVAILABLE):
    ref = ThesisLineageReference("diagnostic:1", FP, T - timedelta(minutes=2))
    candidate = deep_analysis_dossier_candidate(canonical_instrument_id="NSE:INE000000001", dossier_id="brain-output:1", dossier_fingerprint=FP, source_policy_version="brain-output-v1", dossier_as_of=T - timedelta(minutes=3), available_at=T - timedelta(minutes=2), evidence_state=DossierEvidenceState.AVAILABLE, diagnostic_lineage=(ref,), evidence_lineage=(ThesisLineageReference("evidence:1", FP, T - timedelta(minutes=2)),))
    review = review_long_term_thesis(LongTermThesisReviewContext(T, "brain-output-v1", FINGERPRINT_SCHEME), LongTermThesisFamily.QUALITY_FAIR_VALUE, candidate)
    coverage = tuple(LongTermCoverageObservation(domain, coverage_state, "coverage:" + domain.value.lower(), FP, T - timedelta(minutes=1)) for domain in required_coverage_domains(review.family))
    return review_long_term_research_shadow(review, coverage)


def test_nonfinancial_receipt_remains_policy_parameter_unavailable():
    value = evaluate_quality_fair_value_research_shadow(_receipt(), QualityFairValueBusinessBranch.NON_FINANCIAL_CORPORATE)
    assert value.state is QualityFairValueState.POLICY_PARAMETER_UNAVAILABLE
    assert set(value.reasons) == {QualityFairValueReason.QUALITY_PARAMETER_UNAVAILABLE, QualityFairValueReason.VALUATION_COMPARABILITY_UNAVAILABLE, QualityFairValueReason.CASH_CONVERSION_POLICY_UNAVAILABLE, QualityFairValueReason.LIFECYCLE_CALIBRATION_UNAVAILABLE}
    assert value.actionability == "WATCH_ONLY" and value.execution_status == "NON_EXECUTABLE" and value.research_status == "RESEARCH_SHADOW_V1"


@pytest.mark.parametrize("branch", (QualityFairValueBusinessBranch.BANK, QualityFairValueBusinessBranch.NBFC, QualityFairValueBusinessBranch.INSURER, QualityFairValueBusinessBranch.UNKNOWN, QualityFairValueBusinessBranch.STRUCTURALLY_NON_COMPARABLE))
def test_nonindustrial_branches_are_not_applicable(branch):
    value = evaluate_quality_fair_value_research_shadow(_receipt(), branch)
    assert value.state is QualityFairValueState.NOT_APPLICABLE


@pytest.mark.parametrize(("coverage_state", "result"), ((ResearchShadowCoverageState.UNAVAILABLE, QualityFairValueState.DATA_INSUFFICIENT), (ResearchShadowCoverageState.STALE, QualityFairValueState.DATA_INSUFFICIENT), (ResearchShadowCoverageState.NON_COMPARABLE, QualityFairValueState.DATA_INSUFFICIENT), (ResearchShadowCoverageState.CONFLICTED, QualityFairValueState.EVIDENCE_CONFLICTED)))
def test_upstream_evidence_fails_closed(coverage_state, result):
    assert evaluate_quality_fair_value_research_shadow(_receipt(coverage_state=coverage_state), QualityFairValueBusinessBranch.NON_FINANCIAL_CORPORATE).state is result


def test_identity_utc_serialization_and_tampering_are_deterministic():
    first = evaluate_quality_fair_value_research_shadow(_receipt(), QualityFairValueBusinessBranch.NON_FINANCIAL_CORPORATE)
    second = evaluate_quality_fair_value_research_shadow(_receipt(), QualityFairValueBusinessBranch.NON_FINANCIAL_CORPORATE)
    assert first.result_id == second.result_id and serialize_quality_fair_value(first) == serialize_quality_fair_value(second)
    with pytest.raises(FrozenInstanceError): first.state = QualityFairValueState.SHADOW_CANDIDATE
    object.__setattr__(first, "fingerprint", FP)
    with pytest.raises(QualityFairValueResearchShadowError, match="FINGERPRINT_MISMATCH"): first.verify()


def test_v1_cannot_construct_positive_states_or_wrong_branch_state():
    source = _receipt()
    with pytest.raises(QualityFairValueResearchShadowError, match="POSITIVE_STATE_FORBIDDEN"):
        QualityFairValueResearchShadow(source, QualityFairValueBusinessBranch.NON_FINANCIAL_CORPORATE, QualityFairValueState.SHADOW_CANDIDATE, ())
    with pytest.raises(QualityFairValueResearchShadowError, match="BRANCH_STATE_CONTRADICTION"):
        QualityFairValueResearchShadow(source, QualityFairValueBusinessBranch.NON_FINANCIAL_CORPORATE, QualityFairValueState.NOT_APPLICABLE, ())


def test_no_forbidden_dependencies_or_fields():
    source = Path(inspect.getfile(module)).read_text()
    imports = {x.name for node in ast.walk(ast.parse(source)) if isinstance(node, ast.Import) for x in node.names} | {node.module or "" for node in ast.walk(ast.parse(source)) if isinstance(node, ast.ImportFrom)}
    assert not any(item.startswith(prefix) for item in imports for prefix in ("app.portfolio", "app.storage", "app.api", "app.broker", "app.orders", "app.signals"))
    assert "datetime.now" not in source and "time.time" not in source
    assert not (set(QualityFairValueResearchShadow.__dataclass_fields__) & {"price", "entry", "stop", "target", "quantity", "allocation", "portfolio", "order", "broker", "score", "forecast"})
