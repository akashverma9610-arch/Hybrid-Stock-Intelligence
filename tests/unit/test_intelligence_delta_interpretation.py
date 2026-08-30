from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from app.domain.models import FreshnessStatus
from app.intelligence.intelligence_delta import compare_intelligence_states
from app.intelligence.intelligence_delta_interpretation import (
    IntelligenceDeltaInterpretationError,
    IntelligenceInterpretationEvidenceSufficiency,
    create_intelligence_domain_typed_interpretation_evidence,
    interpret_intelligence_delta,
)
from app.intelligence.intelligence_delta_interpretation_policy import (
    CURRENT_FROZEN_OBJECTIVE_INTELLIGENCE_DELTA_INTERPRETATION_POLICY as POLICY,
    ObjectiveDeltaInterpretationDimension as Dimension,
    ObjectiveDeltaInterpretationKind as Kind,
    create_frozen_objective_intelligence_delta_interpretation_policy,
)
from app.intelligence.unified_state import (
    IntelligenceEvidenceAvailability as Availability,
    IntelligenceEvidenceDomain as Domain,
    IntelligenceEvidenceReference,
    IntelligenceStateCompleteness,
    create_unified_intelligence_state,
)


T = datetime(2026, 8, 29, 10, tzinfo=UTC)


def _reference(domain: Domain, *, availability=Availability.AVAILABLE, freshness=FreshnessStatus.UNKNOWN,
               artifact="artifact:one", fingerprint="artifact-fingerprint:one", integrity="integrity:one"):
    return IntelligenceEvidenceReference(
        domain=domain, availability=availability, artifact_ids=(artifact,), artifact_fingerprints=(fingerprint,),
        evidence_as_of=T, observed_at=T, freshness_status=freshness,
        freshness_policy_reference="freshness-v1", source_provenance_fingerprint="source:one",
        historical_integrity_reference=integrity,
    )


def _state(reference, *, at=T):
    return create_unified_intelligence_state(
        canonical_instrument_id="NSE:INE000A01001", as_of=at, evaluation_session=None,
        state_schema_version="state-v1", intelligence_contract_version="intelligence-v1",
        evidence_references=(reference,), completeness=IntelligenceStateCompleteness.COMPLETE,
        blocking_domains=(), degraded_domains=(), dependency_lineage=(), origin_lineage=(),
    )


def _delta(previous: IntelligenceEvidenceReference, current: IntelligenceEvidenceReference):
    return compare_intelligence_states(_state(previous), _state(current, at=T + timedelta(days=1)))


def _interpretations(delta, dimension: Dimension):
    return tuple(value for value in interpret_intelligence_delta(delta, policy=POLICY).domain_interpretations if value.dimension is dimension)


def _typed(delta, *, dimension: Dimension, previous: str | None, current: str | None,
           previous_route: bool | None = None, current_route: bool | None = None):
    source = delta.domain_deltas[0]
    return create_intelligence_domain_typed_interpretation_evidence(
        domain=source.domain, dimension=dimension, source_domain_delta_fingerprint=source.fingerprint,
        previous_status=previous, current_status=current,
        previous_selected_usable_route=previous_route,
        current_selected_usable_route=current_route,
    )


def _one(delta, dimension: Dimension, typed=()):
    values = tuple(value for value in interpret_intelligence_delta(delta, policy=POLICY, typed_evidence=typed).domain_interpretations if value.dimension is dimension)
    assert len(values) == 1
    return values[0]


def test_artifact_is_immutable_deterministic_and_preserves_delta_and_policy_lineage() -> None:
    delta = _delta(
        _reference(Domain.MARKET_DATA, freshness=FreshnessStatus.FRESH),
        _reference(Domain.MARKET_DATA, freshness=FreshnessStatus.STALE, artifact="artifact:two", fingerprint="artifact-fingerprint:two"),
    )
    first = interpret_intelligence_delta(delta, policy=POLICY)
    second = interpret_intelligence_delta(delta, policy=POLICY)
    assert first == second
    assert (first.source_delta_id, first.source_delta_fingerprint) == (delta.delta_id, delta.fingerprint)
    assert (first.policy_id, first.policy_version, first.policy_fingerprint) == (POLICY.policy_id, POLICY.version, POLICY.fingerprint)
    with pytest.raises(FrozenInstanceError):
        first.policy_id = "tampered"


def test_freshness_supported_identical_and_unsupported_transitions_are_governed() -> None:
    degraded = _one(_delta(
        _reference(Domain.MARKET_DATA, freshness=FreshnessStatus.FRESH),
        _reference(Domain.MARKET_DATA, freshness=FreshnessStatus.STALE, artifact="two", fingerprint="two"),
    ), Dimension.FRESHNESS)
    improved = _one(_delta(
        _reference(Domain.MARKET_DATA, freshness=FreshnessStatus.STALE),
        _reference(Domain.MARKET_DATA, freshness=FreshnessStatus.FRESH, artifact="two", fingerprint="two"),
    ), Dimension.FRESHNESS)
    unchanged = _one(_delta(
        _reference(Domain.MARKET_DATA, freshness=FreshnessStatus.FRESH),
        _reference(Domain.MARKET_DATA, freshness=FreshnessStatus.FRESH, artifact="two", fingerprint="two"),
    ), Dimension.FRESHNESS)
    unsupported = _one(_delta(
        _reference(Domain.MARKET_DATA, freshness=FreshnessStatus.UNKNOWN),
        _reference(Domain.MARKET_DATA, freshness=FreshnessStatus.FRESH, artifact="two", fingerprint="two"),
    ), Dimension.FRESHNESS)
    assert (degraded.interpretation, degraded.evidence_sufficiency) == (Kind.FRESHNESS_DEGRADED, IntelligenceInterpretationEvidenceSufficiency.SUFFICIENT)
    assert improved.interpretation is Kind.FRESHNESS_IMPROVED
    assert unchanged.interpretation is Kind.NO_DIRECTIONAL_CHANGE
    assert unsupported.interpretation is Kind.NON_COMPARABLE


def test_availability_and_evidence_presence_are_not_collapsed() -> None:
    improved = _one(_delta(
        _reference(Domain.MARKET_DATA, availability=Availability.UNAVAILABLE),
        _reference(Domain.MARKET_DATA, availability=Availability.AVAILABLE, artifact="two", fingerprint="two"),
    ), Dimension.INTELLIGENCE_AVAILABILITY)
    degraded = _one(_delta(
        _reference(Domain.MARKET_DATA, availability=Availability.AVAILABLE),
        _reference(Domain.MARKET_DATA, availability=Availability.UNAVAILABLE, artifact="two", fingerprint="two"),
    ), Dimension.INTELLIGENCE_AVAILABILITY)
    assert improved.interpretation is Kind.INTELLIGENCE_AVAILABILITY_IMPROVED
    assert degraded.interpretation is Kind.INTELLIGENCE_AVAILABILITY_DEGRADED
    added = compare_intelligence_states(
        create_unified_intelligence_state(
            canonical_instrument_id="NSE:INE000A01001", as_of=T, evaluation_session=None,
            state_schema_version="state-v1", intelligence_contract_version="intelligence-v1",
            evidence_references=(), completeness=IntelligenceStateCompleteness.COMPLETE,
            blocking_domains=(), degraded_domains=(), dependency_lineage=(), origin_lineage=(),
        ),
        _state(_reference(Domain.MARKET_DATA), at=T + timedelta(days=1)),
    )
    result = _one(added, Dimension.INTELLIGENCE_AVAILABILITY)
    assert (result.interpretation, result.evidence_sufficiency) == (Kind.NON_COMPARABLE, IntelligenceInterpretationEvidenceSufficiency.NON_COMPARABLE)
    removed = compare_intelligence_states(
        _state(_reference(Domain.MARKET_DATA)),
        create_unified_intelligence_state(
            canonical_instrument_id="NSE:INE000A01001", as_of=T + timedelta(days=1), evaluation_session=None,
            state_schema_version="state-v1", intelligence_contract_version="intelligence-v1",
            evidence_references=(), completeness=IntelligenceStateCompleteness.COMPLETE,
            blocking_domains=(), degraded_domains=(), dependency_lineage=(), origin_lineage=(),
        ),
    )
    assert _one(removed, Dimension.INTELLIGENCE_AVAILABILITY).interpretation is Kind.NON_COMPARABLE


@pytest.mark.parametrize(("previous", "current", "expected"), (
    ("READY", "DEGRADED", Kind.RELIABILITY_DEGRADED),
    ("DEGRADED", "READY", Kind.RELIABILITY_IMPROVED),
))
def test_direct_reliability_transitions_require_and_honor_typed_evidence(previous, current, expected) -> None:
    delta = _delta(_reference(Domain.RELIABILITY), _reference(Domain.RELIABILITY, artifact="two", fingerprint="two"))
    result = _one(delta, Dimension.RELIABILITY, (_typed(delta, dimension=Dimension.RELIABILITY, previous=previous, current=current),))
    assert (result.interpretation, result.evidence_sufficiency) == (expected, IntelligenceInterpretationEvidenceSufficiency.SUFFICIENT)


def test_reliability_route_proof_and_composite_protections_fail_closed() -> None:
    delta = _delta(_reference(Domain.RELIABILITY), _reference(Domain.RELIABILITY, artifact="two", fingerprint="two"))
    loss = _one(delta, Dimension.RELIABILITY, (_typed(delta, dimension=Dimension.RELIABILITY, previous="READY", current="UNAVAILABLE", previous_route=True),))
    recovery = _one(delta, Dimension.RELIABILITY, (_typed(delta, dimension=Dimension.RELIABILITY, previous="UNAVAILABLE", current="READY", current_route=True),))
    missing = _one(delta, Dimension.RELIABILITY, (_typed(delta, dimension=Dimension.RELIABILITY, previous="READY", current="UNAVAILABLE"),))
    conflicted = _one(delta, Dimension.RELIABILITY, (_typed(delta, dimension=Dimension.RELIABILITY, previous="CONFLICTED", current="READY"),))
    route_causes = _one(delta, Dimension.RELIABILITY, (_typed(delta, dimension=Dimension.RELIABILITY, previous="PRIMARY_UNAVAILABLE", current="UNAVAILABLE"),))
    fallback = _one(delta, Dimension.RELIABILITY, (_typed(delta, dimension=Dimension.RELIABILITY, previous="FALLBACK_USED", current="READY"),))
    assert loss.interpretation is Kind.RELIABILITY_DEGRADED
    assert recovery.interpretation is Kind.RELIABILITY_IMPROVED
    assert missing.evidence_sufficiency is IntelligenceInterpretationEvidenceSufficiency.INSUFFICIENT
    assert all(value.interpretation is Kind.NON_COMPARABLE for value in (conflicted, route_causes, fallback))


def test_stale_ready_is_freshness_only_not_duplicate_reliability_direction() -> None:
    delta = _delta(
        _reference(Domain.RELIABILITY, freshness=FreshnessStatus.STALE),
        _reference(Domain.RELIABILITY, freshness=FreshnessStatus.FRESH, artifact="two", fingerprint="two"),
    )
    interpretation = interpret_intelligence_delta(
        delta, policy=POLICY,
        typed_evidence=(_typed(delta, dimension=Dimension.RELIABILITY, previous="STALE", current="READY"),),
    )
    outcomes = {value.dimension: value for value in interpretation.domain_interpretations}
    assert outcomes[Dimension.FRESHNESS].interpretation is Kind.FRESHNESS_IMPROVED
    assert outcomes[Dimension.RELIABILITY].interpretation is Kind.NO_DIRECTIONAL_CHANGE
    assert outcomes[Dimension.RELIABILITY].evidence_sufficiency is IntelligenceInterpretationEvidenceSufficiency.NOT_APPLICABLE


@pytest.mark.parametrize(("previous", "current", "expected"), (
    ("VALID", "PARTIAL", Kind.HISTORICAL_INTEGRITY_DEGRADED),
    ("VALID", "INVALID", Kind.HISTORICAL_INTEGRITY_DEGRADED),
    ("PARTIAL", "VALID", Kind.HISTORICAL_INTEGRITY_IMPROVED),
    ("INVALID", "VALID", Kind.HISTORICAL_INTEGRITY_IMPROVED),
    ("PARTIAL", "INVALID", Kind.HISTORICAL_INTEGRITY_DEGRADED),
    ("INVALID", "PARTIAL", Kind.HISTORICAL_INTEGRITY_IMPROVED),
))
def test_historical_integrity_approved_native_transitions(previous, current, expected) -> None:
    delta = _delta(_reference(Domain.HISTORICAL_INTEGRITY), _reference(Domain.HISTORICAL_INTEGRITY, artifact="two", fingerprint="two", integrity="two"))
    result = _one(delta, Dimension.HISTORICAL_INTEGRITY, (_typed(delta, dimension=Dimension.HISTORICAL_INTEGRITY, previous=previous, current=current),))
    assert (result.interpretation, result.evidence_sufficiency) == (expected, IntelligenceInterpretationEvidenceSufficiency.SUFFICIENT)


def test_historical_unavailable_projected_conflict_and_fingerprint_only_remain_noncomparable() -> None:
    delta = _delta(_reference(Domain.HISTORICAL_INTEGRITY), _reference(Domain.HISTORICAL_INTEGRITY, artifact="two", fingerprint="two", integrity="two"))
    unavailable = _one(delta, Dimension.HISTORICAL_INTEGRITY, (_typed(delta, dimension=Dimension.HISTORICAL_INTEGRITY, previous="UNAVAILABLE", current="VALID"),))
    projected = _one(delta, Dimension.HISTORICAL_INTEGRITY, (_typed(delta, dimension=Dimension.HISTORICAL_INTEGRITY, previous="CONFLICTED", current="VALID"),))
    fingerprint_only = _one(delta, Dimension.HISTORICAL_INTEGRITY)
    assert all(value.interpretation is Kind.NON_COMPARABLE for value in (unavailable, projected, fingerprint_only))


def test_multi_dimension_results_coexist_without_global_direction_and_policy_is_explicit() -> None:
    delta = _delta(
        _reference(Domain.RELIABILITY, freshness=FreshnessStatus.STALE),
        _reference(Domain.RELIABILITY, freshness=FreshnessStatus.FRESH, artifact="two", fingerprint="two"),
    )
    result = interpret_intelligence_delta(
        delta, policy=POLICY,
        typed_evidence=(_typed(delta, dimension=Dimension.RELIABILITY, previous="READY", current="DEGRADED"),),
    )
    outcomes = {value.dimension: value.interpretation for value in result.domain_interpretations}
    assert outcomes[Dimension.FRESHNESS] is Kind.FRESHNESS_IMPROVED
    assert outcomes[Dimension.RELIABILITY] is Kind.RELIABILITY_DEGRADED
    assert not any(hasattr(result, field) for field in ("overall", "thesis", "opportunity", "risk", "recommendation", "action"))
    with pytest.raises(IntelligenceDeltaInterpretationError, match="POLICY_REQUIRED"):
        interpret_intelligence_delta(delta, policy=None)  # type: ignore[arg-type]
    unsupported = create_frozen_objective_intelligence_delta_interpretation_policy(
        policy_id="different-policy", version=POLICY.version,
        proposal_policy_id=POLICY.proposal_policy_id, proposal_version=POLICY.proposal_version,
        approved_by=POLICY.approved_by, rules=POLICY.rules,
        non_comparable_cases=POLICY.non_comparable_cases, exclusions=POLICY.exclusions,
        provenance=POLICY.provenance,
    )
    with pytest.raises(IntelligenceDeltaInterpretationError, match="POLICY_UNSUPPORTED"):
        interpret_intelligence_delta(delta, policy=unsupported)


def test_typed_evidence_must_bind_the_exact_domain_delta_and_contract_has_no_runtime_surface() -> None:
    delta = _delta(_reference(Domain.RELIABILITY), _reference(Domain.RELIABILITY, artifact="two", fingerprint="two"))
    evidence = _typed(delta, dimension=Dimension.RELIABILITY, previous="READY", current="DEGRADED")
    with pytest.raises(IntelligenceDeltaInterpretationError, match="DELTA_LINEAGE_MISMATCH"):
        interpret_intelligence_delta(delta, policy=POLICY, typed_evidence=(
            create_intelligence_domain_typed_interpretation_evidence(
                domain=evidence.domain, dimension=evidence.dimension, source_domain_delta_fingerprint="wrong",
                previous_status=evidence.previous_status, current_status=evidence.current_status,
            ),
        ))
    source = (Path(__file__).parents[2] / "app" / "intelligence" / "intelligence_delta_interpretation.py").read_text(encoding="utf-8")
    assert not any(token in source for token in (
        "requests.", "urlopen", "httpx", "CREATE TABLE", "INSERT INTO", "project_brain_output(",
        "scheduler", "worker", "listener", "Signal", "PaperTrade", "order(", "recommend(", "FastAPI",
    ))
