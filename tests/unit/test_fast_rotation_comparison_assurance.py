from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime, timedelta, timezone
import ast
import inspect
from pathlib import Path

import pytest

import app.intelligence.fast_rotation_comparison_assurance as module
from app.intelligence.fast_rotation_comparison_assurance import (
    FAST_ROTATION_ASSURANCE_FINGERPRINT_SCHEME, FastRotationAlternativeKind,
    FastRotationAssuranceContext, FastRotationAssuranceError, FastRotationDomainEvidence,
    FastRotationEvidenceDomain, FastRotationEvidenceState, FastRotationLineageReference,
    FastRotationObservationState, FastRotationPolicyReadiness, FastRotationReason,
    assess_fast_rotation_comparison, fast_rotation_comparison_candidate,
    serialize_fast_rotation_assurance,
)


T = datetime(2026, 9, 3, 10, 0, tzinfo=UTC)
FP = "sha256:" + "a" * 64


def _lineage(name: str, at: datetime = T - timedelta(minutes=5)):
    return FastRotationLineageReference(name, FP, at)


def _domains(*, state: FastRotationEvidenceState = FastRotationEvidenceState.AVAILABLE, at: datetime = T - timedelta(minutes=5)):
    return tuple(FastRotationDomainEvidence(domain, state, f"source:{domain.value}", FP, at) for domain in FastRotationEvidenceDomain)


def _candidate(**changes):
    values = dict(
        source_evaluation_id="evaluation:1", source_comparison_id="comparison:1", source_configuration_version="rotation-v1",
        source_content_fingerprint=FP, source_as_of=T - timedelta(minutes=5), source_available_at=T - timedelta(minutes=4),
        challenger_instrument_id="instrument:challenger", alternative_kind=FastRotationAlternativeKind.INCUMBENT,
        alternative_identity="instrument:incumbent", challenger_lineage=(_lineage("lineage:challenger"),),
        alternative_lineage=(_lineage("lineage:incumbent"),), domain_evidence=_domains(),
    )
    values.update(changes)
    return fast_rotation_comparison_candidate(**values)


def _context(**changes):
    values = dict(as_of=T, expected_configuration_version="rotation-v1", expected_fingerprint_scheme=FAST_ROTATION_ASSURANCE_FINGERPRINT_SCHEME)
    values.update(changes)
    return FastRotationAssuranceContext(**values)


def test_verified_observation_is_research_usable_but_policy_is_explicitly_unavailable():
    value = assess_fast_rotation_comparison(_context(), _candidate())
    assert value.observation_state is FastRotationObservationState.CORE_COMPARISON_OBSERVED
    assert value.policy_readiness is FastRotationPolicyReadiness.POLICY_PARAMETER_UNAVAILABLE
    assert set((FastRotationReason.BUCKET_POLICY_UNAVAILABLE, FastRotationReason.FRICTION_TAX_POLICY_UNAVAILABLE)).issubset(value.reason_codes)
    assert value.challenger_instrument_id == "instrument:challenger"


def test_cash_is_an_identity_only_alternative_and_has_no_amount_or_allocation():
    value = assess_fast_rotation_comparison(_context(), _candidate(alternative_kind=FastRotationAlternativeKind.CASH, alternative_identity="CASH", alternative_lineage=(_lineage("lineage:cash"),)))
    assert value.alternative_kind is FastRotationAlternativeKind.CASH
    assert value.alternative_identity == "CASH"
    fields = set(value.__dataclass_fields__)
    assert not fields & {"cash_amount", "price", "quantity", "allocation", "portfolio", "action"}


def test_future_source_or_evidence_is_excluded_by_the_explicit_cutoff():
    future_source = assess_fast_rotation_comparison(_context(), _candidate(source_available_at=T + timedelta(seconds=1)))
    future_evidence = assess_fast_rotation_comparison(_context(), _candidate(domain_evidence=_domains(at=T + timedelta(seconds=1))))
    assert future_source.observation_state is FastRotationObservationState.TEMPORALLY_INVALID
    assert future_evidence.observation_state is FastRotationObservationState.TEMPORALLY_INVALID
    assert FastRotationReason.SOURCE_COMPARISON_AFTER_AS_OF in future_source.reason_codes
    assert FastRotationReason.EVIDENCE_AFTER_AS_OF in future_evidence.reason_codes


@pytest.mark.parametrize(("state", "expected", "reason"), [
    (FastRotationEvidenceState.UNAVAILABLE, FastRotationObservationState.DATA_INSUFFICIENT, FastRotationReason.EVIDENCE_UNAVAILABLE),
    (FastRotationEvidenceState.STALE, FastRotationObservationState.DATA_INSUFFICIENT, FastRotationReason.EVIDENCE_STALE),
    (FastRotationEvidenceState.NON_COMPARABLE, FastRotationObservationState.DATA_INSUFFICIENT, FastRotationReason.EVIDENCE_NON_COMPARABLE),
    (FastRotationEvidenceState.CONFLICTED, FastRotationObservationState.CONFLICTED, FastRotationReason.EVIDENCE_CONFLICTED),
])
def test_injected_evidence_states_fail_closed_without_reinterpretation(state, expected, reason):
    value = assess_fast_rotation_comparison(_context(), _candidate(domain_evidence=_domains(state=state)))
    assert value.observation_state is expected
    assert value.policy_readiness is FastRotationPolicyReadiness.NOT_EVALUATED
    assert value.reason_codes == (reason,)


def test_tampered_source_fingerprint_or_version_is_unverifiable_not_repaired():
    fingerprint = assess_fast_rotation_comparison(_context(), replace(_candidate(), stored_fingerprint="sha256:" + "b" * 64))
    version = assess_fast_rotation_comparison(_context(), _candidate(source_configuration_version="rotation-v0"))
    assert fingerprint.observation_state is FastRotationObservationState.UNVERIFIABLE
    assert version.observation_state is FastRotationObservationState.UNVERIFIABLE


def test_identity_uses_source_provenance_while_content_fingerprint_covers_full_lineage():
    base = assess_fast_rotation_comparison(_context(), _candidate())
    alternate = assess_fast_rotation_comparison(_context(), _candidate(challenger_lineage=(_lineage("lineage:challenger:other"),)))
    assert base.assurance_id == alternate.assurance_id
    assert base.fingerprint != alternate.fingerprint
    assert base.source_configuration_version == "rotation-v1"


def test_canonicalization_is_order_independent_and_rejects_duplicate_lineage_or_domains():
    india = timezone(timedelta(hours=5, minutes=30))
    first = _candidate(challenger_lineage=(_lineage("lineage:b"), _lineage("lineage:a")))
    second = _candidate(challenger_lineage=(_lineage("lineage:a"), _lineage("lineage:b")), source_as_of=(T - timedelta(minutes=5)).astimezone(india))
    assert first.stored_fingerprint == second.stored_fingerprint
    assert serialize_fast_rotation_assurance(assess_fast_rotation_comparison(_context(), first)) == serialize_fast_rotation_assurance(assess_fast_rotation_comparison(_context(), second))
    with pytest.raises(FastRotationAssuranceError, match="LINEAGE_DUPLICATE"):
        _candidate(challenger_lineage=(_lineage("lineage:a"), _lineage("lineage:a")))
    with pytest.raises(FastRotationAssuranceError, match="DOMAIN_COVERAGE_INVALID"):
        _candidate(domain_evidence=_domains()[:-1])


def test_immutability_and_fingerprint_verification_are_tamper_evident():
    value = assess_fast_rotation_comparison(_context(), _candidate())
    with pytest.raises(FrozenInstanceError):
        value.observation_state = FastRotationObservationState.DATA_INSUFFICIENT
    object.__setattr__(value, "fingerprint", "sha256:" + "c" * 64)
    with pytest.raises(FastRotationAssuranceError, match="FINGERPRINT_MISMATCH"):
        value.verify()


def test_observed_output_cannot_carry_insufficiency_or_noncanonical_reason_codes():
    value = assess_fast_rotation_comparison(_context(), _candidate())
    with pytest.raises(FastRotationAssuranceError, match="REASONS_NONCANONICAL"):
        replace(value, reason_codes=value.reason_codes + (FastRotationReason.EVIDENCE_UNAVAILABLE,))
    with pytest.raises(FastRotationAssuranceError, match="REASON_INVALID"):
        replace(value, reason_codes=("not-a-reason",))


def test_invalid_identity_and_cash_invariants_are_rejected_at_construction():
    with pytest.raises(FastRotationAssuranceError, match="CHALLENGER_ID_INVALID"):
        _candidate(challenger_instrument_id="not canonical")
    with pytest.raises(FastRotationAssuranceError, match="CASH_IDENTITY_INVALID"):
        _candidate(alternative_kind=FastRotationAlternativeKind.CASH, alternative_identity="instrument:cash")
    with pytest.raises(FastRotationAssuranceError, match="INCUMBENT_IDENTITY_INVALID"):
        _candidate(alternative_identity="instrument:challenger")


def test_source_module_has_no_clock_io_or_forbidden_dependency_or_action_surface():
    source = Path(inspect.getfile(module)).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports = {alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names} | {node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
    assert not any(name.startswith(prefix) for name in imports for prefix in ("app.portfolio", "app.storage", "app.api", "app.broker", "app.orders", "app.signals"))
    assert "datetime.now" not in source and "datetime.utcnow" not in source
    public = set(module.FastRotationComparisonAssurance.__dataclass_fields__)
    assert not public & {"price", "entry", "stop", "target", "quantity", "sizing", "allocation", "portfolio", "order", "broker"}
