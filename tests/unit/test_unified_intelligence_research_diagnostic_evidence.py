from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.domain.models import DiagnosticResult, FreshnessStatus, StrategyVersionReference
from app.historical.guard import manifest_fingerprint
from app.intelligence.company_evidence import CompositeStoredIntelligenceSource
from app.intelligence.research_diagnostic_evidence import (
    ResearchDiagnosticEvidenceStoredSource,
    StrategyGovernanceDiagnosticResultSource,
)
from app.intelligence.unified_state import (
    IntelligenceEvidenceAvailability,
    IntelligenceEvidenceDomain,
    IntelligenceInvalidationDomain,
)
from app.intelligence.unified_state_builder import StoredIntelligenceArtifact, UnifiedIntelligenceStateBuilder


T = datetime(2026, 8, 29, 12, tzinfo=UTC)
I = "NSE:RESEARCH"
REFERENCE = StrategyVersionReference("shared-brain", "diagnostic-v1")
SUCCESSOR = StrategyVersionReference("shared-brain", "diagnostic-v2")


class _CoreSource:
    def list_stored_intelligence_artifacts(self, canonical_instrument_id: str, *, as_of: datetime):
        return tuple(
            StoredIntelligenceArtifact(
                canonical_instrument_id, domain, f"core:{domain.value}",
                manifest_fingerprint(domain=domain.value, instrument=canonical_instrument_id),
                IntelligenceEvidenceAvailability.AVAILABLE, T - timedelta(days=5), T - timedelta(days=5),
                T - timedelta(days=5), FreshnessStatus.FRESH, None, None, None,
                IntelligenceInvalidationDomain.PRICE if domain is IntelligenceEvidenceDomain.MARKET_DATA else IntelligenceInvalidationDomain.REFERENCE_DATA,
            )
            for domain in (IntelligenceEvidenceDomain.REFERENCE_DATA, IntelligenceEvidenceDomain.MARKET_DATA)
        )


class _Diagnostics:
    def __init__(self, values: tuple[DiagnosticResult, ...]) -> None:
        self.values = values

    def list_stored_diagnostic_results(self, canonical_instrument_id: str, *, as_of: datetime) -> tuple[DiagnosticResult, ...]:
        return self.values


def _diagnostic(
    rule: int,
    *,
    instrument: str = I,
    reference: StrategyVersionReference = REFERENCE,
    at: datetime = T - timedelta(days=1),
    evaluated: datetime | None = None,
    result: str = "DURABLE_RULE_RESULT",
) -> DiagnosticResult:
    return DiagnosticResult(
        f"diagnostic:{reference.version}:{at.date().isoformat()}:{instrument}:{rule}", instrument, str(rule), reference,
        result, None, 0.8, (f"evidence:{rule}",), (f"observation:{rule}",), evaluated or at, at,
    )


def _builder(values: tuple[DiagnosticResult, ...] | None = None) -> UnifiedIntelligenceStateBuilder:
    source = ResearchDiagnosticEvidenceStoredSource(_Diagnostics(values) if values is not None else None)
    return UnifiedIntelligenceStateBuilder(CompositeStoredIntelligenceSource(_CoreSource(), source))


def _reference(state):
    return next(item for item in state.evidence_references if item.domain is IntelligenceEvidenceDomain.RESEARCH_DIAGNOSTICS)


def test_missing_research_and_diagnostic_boundaries_are_explicit() -> None:
    reference = _reference(_builder().build(I, as_of=T))
    assert reference.availability is IntelligenceEvidenceAvailability.UNAVAILABLE
    assert reference.warnings == (
        "DIAGNOSTIC_DURABLE_READ_BOUNDARY_MISSING",
        "RESEARCH_DURABLE_READ_BOUNDARY_MISSING",
    )


def test_durable_full_61_diagnostic_bundle_is_bounded_and_available() -> None:
    state = _builder(tuple(_diagnostic(rule) for rule in range(1, 62))).build(I, as_of=T)
    reference = _reference(state)
    assert reference.availability is IntelligenceEvidenceAvailability.AVAILABLE
    assert len(reference.artifact_ids) == len(reference.artifact_fingerprints) == 1
    assert reference.artifact_ids[0].startswith("diagnostic-61:shared-brain:diagnostic-v1:")
    assert "DURABLE_RULE_RESULT" not in repr(state)
    assert "RESEARCH_DURABLE_READ_BOUNDARY_MISSING" in reference.warnings


def test_partial_diagnostic_is_available_as_partial_without_calculation() -> None:
    reference = _reference(_builder((_diagnostic(1),)).build(I, as_of=T))
    assert reference.availability is IntelligenceEvidenceAvailability.PARTIAL
    assert "DIAGNOSTIC_61_BUNDLE_PARTIAL" in reference.warnings


def test_future_and_first_observed_diagnostics_do_not_backdate() -> None:
    future = _diagnostic(1, at=T + timedelta(days=1))
    first_observed = _diagnostic(2, at=T - timedelta(days=1), evaluated=T + timedelta(days=1))
    builder = _builder((future, first_observed))
    before = _reference(builder.build(I, as_of=T))
    after = _reference(builder.build(I, as_of=T + timedelta(days=1)))
    assert before.availability is IntelligenceEvidenceAvailability.UNAVAILABLE
    assert after.availability is IntelligenceEvidenceAvailability.PARTIAL
    assert before.artifact_ids == ("diagnostic-evidence:unavailable",)


def test_historical_version_is_preserved_and_latest_eligible_bundle_is_deterministic() -> None:
    old_at, new_at = T - timedelta(days=2), T - timedelta(days=1)
    old = _diagnostic(1, reference=REFERENCE, at=old_at)
    new = _diagnostic(1, reference=SUCCESSOR, at=new_at)
    builder = _builder((new, old))
    old_reference = _reference(builder.build(I, as_of=old_at))
    new_reference = _reference(builder.build(I, as_of=T))
    reversed_reference = _reference(_builder((old, new)).build(I, as_of=T))
    assert "diagnostic-v1" in old_reference.artifact_ids[0]
    assert "diagnostic-v2" in new_reference.artifact_ids[0]
    assert new_reference == reversed_reference


def test_exact_instrument_identity_is_required_and_new_eligible_bundle_changes_fingerprint() -> None:
    valid = _diagnostic(1)
    wrong = _diagnostic(2, instrument="NSE:OTHER")
    before = _builder((valid, wrong)).build(I, as_of=T)
    after = _builder((valid, _diagnostic(3))).build(I, as_of=T)
    reference = _reference(before)
    assert "NSE:OTHER" not in " ".join(reference.artifact_ids)
    assert before.fingerprint != after.fingerprint


def test_dependency_lineage_is_deterministic_and_uses_existing_nearest_vocabulary() -> None:
    state = _builder((_diagnostic(2), _diagnostic(1))).build(I, as_of=T)
    dependency = next(item for item in state.dependency_lineage if item.artifact_id.startswith("diagnostic-61:"))
    assert dependency.invalidation_domain is IntelligenceInvalidationDomain.REFERENCE_DATA
    assert "DIAGNOSTIC_INVALIDATION_REFERENCE_DATA" in _reference(state).warnings
    assert _builder((_diagnostic(1), _diagnostic(2))).reconstruct(I, as_of=T, expected_state=state) == state


def test_existing_governance_repository_read_contract_is_exact_strategy_and_as_of_only() -> None:
    values = (_diagnostic(1), _diagnostic(1, instrument="NSE:OTHER"))

    class _Repository:
        def __init__(self) -> None:
            self.calls: list[tuple[StrategyVersionReference, datetime]] = []

        def list_diagnostic_results(self, reference, as_of_timestamp):
            self.calls.append((reference, as_of_timestamp))
            return values

    repository = _Repository()
    source = StrategyGovernanceDiagnosticResultSource(
        repository, strategy_version=REFERENCE, evaluation_as_of=T - timedelta(days=1),
    )
    assert source.list_stored_diagnostic_results(I, as_of=T) == (_diagnostic(1),)
    assert repository.calls == [(REFERENCE, T - timedelta(days=1))]


def test_research_diagnostic_adapter_is_stored_only_and_excludes_decision_gate_and_execution() -> None:
    source = (Path(__file__).parents[2] / "app" / "intelligence" / "research_diagnostic_evidence.py").read_text(encoding="utf-8")
    assert not any(token in source for token in (
        "Canonical61DiagnosticRunner", "ResearchAnalysis", "DecisionScore", "SixGate", "requests.", "urlopen",
        "httpx", "CREATE TABLE", "INSERT INTO", "Signal", "PaperTrade", "order(",
    ))
