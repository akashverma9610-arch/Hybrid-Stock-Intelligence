from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta

import pytest

from app.intelligence.external_intelligence import (
    CompanyExposure, EvidenceVersion, EventType, ExternalEvent, ExposureType,
    Materiality, PolicyStage, SourceEvidence,
)
from app.intelligence.long_term_policy_transmission_research_shadow import *
from app.intelligence.long_term_thesis_research_shadow import *
from app.intelligence.long_term_thesis_review import *


T = datetime(2026, 9, 3, 10, tzinfo=UTC)
FP = "sha256:" + "a" * 64
TARGET = "NSE:INE000000001"


def receipt(policy_evidence, state=ResearchShadowCoverageState.AVAILABLE):
    reference = ThesisLineageReference("diagnostic:1", FP, T - timedelta(minutes=3))
    candidate = deep_analysis_dossier_candidate(
        canonical_instrument_id=TARGET, dossier_id="brain-output:1", dossier_fingerprint=FP,
        source_policy_version="brain-output-v1", dossier_as_of=T - timedelta(minutes=4),
        available_at=T - timedelta(minutes=3), evidence_state=DossierEvidenceState.AVAILABLE,
        diagnostic_lineage=(reference,), evidence_lineage=(ThesisLineageReference("evidence:1", FP, T - timedelta(minutes=3)),),
    )
    review = review_long_term_thesis(
        LongTermThesisReviewContext(T, "brain-output-v1", FINGERPRINT_SCHEME),
        LongTermThesisFamily.POLICY_TRANSMISSION, candidate,
    )
    return review_long_term_research_shadow(review, tuple(
        LongTermCoverageObservation(
            domain, state,
            policy_evidence.evidence_version_id if domain is LongTermCoverageDomain.PRIMARY_POLICY_EVIDENCE else "coverage:" + domain.value.lower(),
            policy_evidence.fingerprint if domain is LongTermCoverageDomain.PRIMARY_POLICY_EVIDENCE else FP,
            T - timedelta(minutes=1),
        )
        for domain in required_coverage_domains(review.family)
    ))


def evidence(**changes):
    event = ExternalEvent(
        "HSI_EXTERNAL_INTELLIGENCE_DESK", "policy-1", EventType.GOVERNMENT_POLICY,
        "Synthetic notified policy", "IN", "MACRO", Materiality.HIGH,
        T - timedelta(days=2), PolicyStage.NOTIFIED,
    )
    values = dict(
        event=event, received_at=T - timedelta(minutes=2), published_at=T - timedelta(days=1),
        discovered_at=T - timedelta(hours=23), summary="Synthetic policy fact", what_changed="Synthetic notified change",
        primary_source=SourceEvidence("Ministry", "GOVERNMENT", "notice:1", 1.0),
        company_exposures=(CompanyExposure(TARGET, None, ExposureType.DIRECT, 1.0, "VERIFIED"),),
        effective_at=T - timedelta(hours=12), affected_sectors=("INDUSTRIALS",), affected_industries=("CAPITAL_GOODS",),
    )
    values.update(changes)
    return EvidenceVersion(**values)


def evaluate(source=ResearchShadowCoverageState.AVAILABLE, branch=PolicyTransmissionBusinessBranch.NON_FINANCIAL_CORPORATE, **changes):
    item = evidence(**changes)
    return evaluate_policy_transmission_research_shadow(receipt(item, source), item, branch)


def test_complete_primary_policy_and_exact_exposure_still_has_no_benefit_conclusion():
    value = evaluate()
    assert value.state is PolicyTransmissionState.POLICY_DEFINITION_MISSING
    assert value.actionability == "WATCH_ONLY" and value.execution_status == "NON_EXECUTABLE"
    assert PolicyTransmissionReason.POLICY_DIRECTION_DEFINITION_MISSING in value.reasons
    assert not {"SHADOW_CANDIDATE", "SHADOW_NOT_QUALIFIED", "BULLISH", "BEARISH"} & {item.value for item in PolicyTransmissionState}


@pytest.mark.parametrize(("changes", "reason"), (
    ({"company_exposures": ()}, PolicyTransmissionReason.COMPANY_EXPOSURE_UNAVAILABLE),
    ({"affected_sectors": (), "affected_industries": ()}, PolicyTransmissionReason.POLICY_SCOPE_UNAVAILABLE),
    ({"primary_source": SourceEvidence("Media", "MEDIA", "article:1", 1.0)}, PolicyTransmissionReason.PRIMARY_SOURCE_PROVENANCE_INSUFFICIENT),
    ({"effective_at": None}, PolicyTransmissionReason.POLICY_EFFECTIVE_TIME_UNAVAILABLE),
))
def test_missing_policy_or_exposure_readiness_fails_closed(changes, reason):
    value = evaluate(**changes)
    assert value.state is PolicyTransmissionState.DATA_INSUFFICIENT
    assert value.reasons == (reason,)


def test_exact_other_company_is_not_applicable_and_unverified_target_is_insufficient():
    other = CompanyExposure("NSE:INE000000002", None, ExposureType.DIRECT, 1.0, "VERIFIED")
    assert evaluate(company_exposures=(other,)).state is PolicyTransmissionState.NOT_APPLICABLE
    unverified = CompanyExposure(TARGET, None, ExposureType.DIRECT, 1.0, "UNVERIFIED_INFERENCE")
    assert evaluate(company_exposures=(unverified,)).reasons == (PolicyTransmissionReason.COMPANY_EXPOSURE_UNAVAILABLE,)


def test_primary_event_stage_and_pit_are_required():
    unsupported = evidence(event=ExternalEvent("desk", "event-2", EventType.EARNINGS, "x", "IN", "CORPORATE", Materiality.HIGH, T - timedelta(days=2), PolicyStage.NOTIFIED))
    assert evaluate_policy_transmission_research_shadow(receipt(unsupported), unsupported, PolicyTransmissionBusinessBranch.NON_FINANCIAL_CORPORATE).reasons == (PolicyTransmissionReason.POLICY_EVENT_TYPE_UNSUPPORTED,)
    assert evaluate(event=ExternalEvent("desk", "event-3", EventType.GOVERNMENT_POLICY, "x", "IN", "MACRO", Materiality.HIGH, T - timedelta(days=2), PolicyStage.STATEMENT)).reasons == (PolicyTransmissionReason.POLICY_STAGE_INSUFFICIENT,)
    assert evaluate(received_at=T + timedelta(seconds=1)).reasons == (PolicyTransmissionReason.SOURCE_RECEIPT_TEMPORALLY_INVALID,)
    assert evaluate(primary_source=SourceEvidence("Ministry", " government", "notice:1", 1.0)).reasons == (PolicyTransmissionReason.PRIMARY_SOURCE_PROVENANCE_INSUFFICIENT,)


@pytest.mark.parametrize("state", (ResearchShadowCoverageState.CONFLICTED, ResearchShadowCoverageState.UNAVAILABLE, ResearchShadowCoverageState.STALE, ResearchShadowCoverageState.NON_COMPARABLE))
def test_source_receipt_conflict_and_insufficiency_propagate(state):
    value = evaluate(source=state)
    assert value.state is (PolicyTransmissionState.EVIDENCE_CONFLICTED if state is ResearchShadowCoverageState.CONFLICTED else PolicyTransmissionState.DATA_INSUFFICIENT)


@pytest.mark.parametrize("branch", (PolicyTransmissionBusinessBranch.BANK, PolicyTransmissionBusinessBranch.NBFC, PolicyTransmissionBusinessBranch.INSURER))
def test_financial_branches_preserve_exposure_readiness_without_an_industrial_formula(branch):
    assert evaluate(branch=branch).state is PolicyTransmissionState.POLICY_DEFINITION_MISSING


@pytest.mark.parametrize("branch", (PolicyTransmissionBusinessBranch.UNKNOWN, PolicyTransmissionBusinessBranch.STRUCTURALLY_NON_COMPARABLE))
def test_unknown_and_noncomparable_company_branches_are_not_evaluated(branch):
    assert evaluate(branch=branch).state is PolicyTransmissionState.NOT_APPLICABLE


def test_output_is_immutable_deterministic_and_serialized_stably():
    first, second = evaluate(), evaluate()
    assert first.result_id == second.result_id and first.fingerprint == second.fingerprint
    assert serialize_policy_transmission(first) == serialize_policy_transmission(second)
    with pytest.raises(FrozenInstanceError):
        first.state = PolicyTransmissionState.DATA_INSUFFICIENT


def test_tampered_evidence_lineage_is_rejected_on_verification():
    value = evaluate()
    object.__setattr__(value.policy_evidence, "summary", "tampered")
    with pytest.raises(PolicyTransmissionResearchShadowError, match="EVIDENCE"):
        value.verify()


def test_primary_policy_coverage_must_bind_to_the_exact_evidence_version():
    item = evidence()
    unrelated = evidence(event=ExternalEvent("desk", "policy-other", EventType.GOVERNMENT_POLICY, "x", "IN", "MACRO", Materiality.HIGH, T - timedelta(days=2), PolicyStage.NOTIFIED))
    value = evaluate_policy_transmission_research_shadow(receipt(unrelated), item, PolicyTransmissionBusinessBranch.NON_FINANCIAL_CORPORATE)
    assert value.reasons == (PolicyTransmissionReason.PRIMARY_POLICY_COVERAGE_LINEAGE_UNVERIFIABLE,)


def test_conflicting_exact_exposure_and_contradictory_manual_state_are_rejected():
    duplicate = (
        CompanyExposure(TARGET, None, ExposureType.DIRECT, 1.0, "VERIFIED"),
        CompanyExposure(TARGET, None, ExposureType.SUPPLY_CHAIN, 1.0, "VERIFIED"),
    )
    assert evaluate(company_exposures=duplicate).reasons == (PolicyTransmissionReason.EXPOSURE_LINEAGE_CONFLICTED,)
    with pytest.raises(PolicyTransmissionResearchShadowError, match="STATE_REASON"):
        PolicyTransmissionResearchShadow(
            receipt(evidence()), evidence(), PolicyTransmissionBusinessBranch.NON_FINANCIAL_CORPORATE,
            PolicyTransmissionState.POLICY_DEFINITION_MISSING,
            (PolicyTransmissionReason.POLICY_SCOPE_UNAVAILABLE,),
        )


def test_no_forbidden_dependencies_or_outputs():
    import app.intelligence.long_term_policy_transmission_research_shadow as module
    text = open(module.__file__, encoding="utf-8").read()
    for forbidden in ("app.signals", "app.storage", "portfolio", "broker", "order", "api", "datetime.now", "DecisionScore"):
        assert forbidden not in text
