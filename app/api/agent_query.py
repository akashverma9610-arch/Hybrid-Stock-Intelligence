"""Explicit read-only Agent queries over existing services. No new intelligence."""
from app.api.errors import APIRequestError
from app.api.schemas.agent_tools import DiagnosticRequest, DiagnosticRuleResponse, DiagnosticsResponse, ToolEnvelope
from app.data_operations.financial_period_identity_repair import FinancialPeriodIdentityCorrectionStore, FinancialPeriodIdentityProjection
from app.fundamentals.adapter import FundamentalsEngineAdapter
from app.fundamentals.diagnostic_comparability import content_fingerprint
from app.intelligence.shared_brain_application import CoreUniverseInstrumentResolver
from app.real_brain.local import StoredTrialObservationSource
from app.universe_analysis.service import Canonical61DiagnosticRunner, CoreUniverseAnalysisStore, StockDiagnosticInputAssembler


class StoredAgentDiagnostics:
    """Single-security direct inspection, not a discovery lead or union rewrite.

    Reuses the stored real-Brain source (bounded 300 bars per instrument and
    existing benchmark IDs), the canonical PIT assembler and authorized runner.
    Caller-supplied evidence/policies are never accepted by HTTP.
    """
    def __init__(self, *, universe, governance, source_factory):
        self._universe, self._governance, self._source_factory = universe, governance, source_factory

    def evaluate(self, request: DiagnosticRequest) -> ToolEnvelope[DiagnosticsResponse]:
        if request.temporal_mode != "CURRENT_DESCRIPTIVE":
            return ToolEnvelope(status="BLOCKED", as_of=request.as_of, blockers=("STRICT_HISTORICAL_PIT_NOT_READY",))
        instrument = CoreUniverseInstrumentResolver(self._universe).resolve(request.canonical_security_id, as_of=request.as_of)
        if (instrument.instrument_id != request.canonical_security_id or instrument.isin != request.canonical_security_id[4:]
                or instrument.security_type != "EQUITY" or instrument.data_as_of > request.as_of):
            raise ValueError("CANONICAL_EQUITY_IDENTITY_REQUIRED")
        runner = Canonical61DiagnosticRunner()
        definition = runner.authorize(self._governance)
        if max(definition.created_at, definition.registered_at) > request.as_of:
            return ToolEnvelope(status="BLOCKED", as_of=request.as_of, blockers=("FUTURE_DIAGNOSTIC_GOVERNANCE",))
        source = self._source_factory(request.canonical_security_id, request.as_of)
        evidence = StockDiagnosticInputAssembler(source).assemble(instrument, request.as_of)
        fingerprint = content_fingerprint(evidence)
        result = runner.run(evidence, governance=self._governance)
        if tuple(item.canonical_rule_id for item in result.evaluations) != tuple(range(1, 62)):
            raise ValueError("CANONICAL_RULE_INVENTORY_INVALID")
        rules = tuple(DiagnosticRuleResponse(
            rule_id=item.canonical_rule_id, result_id=item.record.id, result=item.record.result,
            eligibility=item.eligibility.value, evidence_refs=item.record.evidence_ids,
            observation_refs=item.record.input_observation_ids,
        ) for item in result.evaluations)
        return ToolEnvelope(
            status="PARTIAL" if result.evaluated else "BLOCKED", as_of=request.as_of,
            data=DiagnosticsResponse(canonical_security_id=instrument.instrument_id,
                completeness=result.completeness.value, evaluated_count=result.evaluated, missing_count=result.missing,
                strategy_id=definition.strategy_id, strategy_version=definition.strategy_version,
                strategy_fingerprint=definition.semantic_fingerprint, input_fingerprint=fingerprint, rules=rules),
            evidence_refs=tuple(sorted({ref for rule in rules for ref in (*rule.evidence_refs, *rule.observation_refs)})),
            blockers=("CERTIFIED_RADAR_TECHNICAL_BINDING_NOT_CONFIGURED",),
            warnings=(*result.warnings, *evidence.warnings, "CURRENT_DESCRIPTIVE_NOT_STRICT_HISTORICAL_PIT"),
            provenance=(definition.semantic_fingerprint, fingerprint, "canonical-universe-analysis/v1"),
        )


def diagnostics_from_existing_state(state) -> StoredAgentDiagnostics:
    """Borrow existing API-owned resources; open/create/close no stores here."""
    resources = getattr(state, "market_wide_evidence_resources", ())
    repository = getattr(state, "core_api_snapshot_repository", None)
    governance = getattr(state, "decision_score_governance_repository", None)
    if len(resources) != 3 or repository is None or governance is None:
        raise APIRequestError(status_code=503, code="AGENT_DIAGNOSTIC_RESOURCES_UNAVAILABLE",
                              message="Stored diagnostic resources are unavailable.")
    historical, facts, filings = resources
    fundamentals = FundamentalsEngineAdapter(facts, filings,
        FinancialPeriodIdentityProjection(FinancialPeriodIdentityCorrectionStore(repository)))
    return StoredAgentDiagnostics(universe=CoreUniverseAnalysisStore(repository), governance=governance,
        source_factory=lambda security, at: StoredTrialObservationSource(historical=historical,
            instrument_ids=(security,), as_of=at, fundamentals=fundamentals))
