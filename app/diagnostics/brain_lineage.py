"""Read-only diagnostic lineage sidecars, never production Brain/action objects.

No evidence selection, strategy interpretation, repository, clock or financial
calculation. The existing Brain remains the sole production assembler.
"""
from dataclasses import dataclass, fields
from datetime import UTC, datetime

from app.diagnostics.downstream import ShadowDiagnosticEnvelope, active_v1_rejection, shadow_diagnostic_envelope
from app.diagnostics.models import EvaluatedDiagnostic
from app.domain.canonical_diagnostic_strategy import CANONICAL_61_SEMANTIC_FINGERPRINT, CANONICAL_61_STRATEGY_REFERENCE
from app.domain.models import DiagnosticResult, DiagnosticStrategyLineageType, StrategyVersionReference, canonical_diagnostic_result_fingerprint
from app.fundamentals.diagnostic_comparability import canonical_json, content_fingerprint
from app.registry.canonical import DIAGNOSTIC_REGISTRY_VERSION
from app.registry.versioned import RegistryMode, V2_RULE_IDS, V2_VERSION, resolve_diagnostic_registry

VERSION = "fundamental-brain-portfolio-lineage/v1"
CROSS_BRAIN = "CROSS_REGISTRY_BRAIN_CONSUMPTION_FORBIDDEN"
CROSS_PORTFOLIO = "CROSS_REGISTRY_PORTFOLIO_CONSUMPTION_FORBIDDEN"


def _utc(value):
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("BRAIN_DIAGNOSTIC_AS_OF_INVALID")
    return value.astimezone(UTC)


def _text(value):
    return isinstance(value, str) and bool(value) and value == value.strip()


def _payload(value):
    return {f.name: getattr(value, f.name) for f in fields(value) if f.name != "fingerprint"}


def require_production_evidence(value, *, reason=CROSS_PORTFOLIO, legacy_version_label=False):
    """Reject research wrappers before legacy duck-typed consumers inspect them.

Unversioned legacy inputs retain V1 meaning. An explicit foreign registry,
shadow flag or action-ineligible sidecar can never be stripped to legacy data.
This function does not confer authority on otherwise-valid legacy inputs.
"""
    version = getattr(value, "registry_version", DIAGNOSTIC_REGISTRY_VERSION)
    if (isinstance(value, (ShadowDiagnosticEnvelope,
                           BrainDiagnosticResearch, FundamentalPortfolioObservation))
            or version == V2_VERSION or not legacy_version_label and version != DIAGNOSTIC_REGISTRY_VERSION
            or getattr(value, "mode", RegistryMode.ACTIVE) == RegistryMode.SHADOW
            or getattr(value, "shadow_only", False) is not False
            or getattr(value, "portfolio_action_eligible", None) is False):
        raise ValueError(reason)


def require_v1_stored_diagnostic(value):
    """Legacy stored results are V1, not a license to relabel arbitrary objects."""
    if not isinstance(value, DiagnosticResult):
        raise ValueError(CROSS_BRAIN)
    if value.strategy_lineage_type is DiagnosticStrategyLineageType.CANONICAL_DIAGNOSTIC_STRATEGY:
        if (value.strategy_version != CANONICAL_61_STRATEGY_REFERENCE
                or value.canonical_strategy_fingerprint != CANONICAL_61_SEMANTIC_FINGERPRINT
                or value.diagnostic_fingerprint != canonical_diagnostic_result_fingerprint(value)):
            raise ValueError("BRAIN_CANONICAL_DIAGNOSTIC_LINEAGE_INVALID")
    elif value.strategy_lineage_type is not DiagnosticStrategyLineageType.GENERIC_STRATEGY_VERSION:
        raise ValueError(CROSS_BRAIN)
    elif any((value.canonical_strategy_fingerprint, value.canonical_limitations_fingerprint, value.diagnostic_fingerprint)):
        raise ValueError("BRAIN_GENERIC_CANONICAL_LINEAGE_CONTRADICTION")


@dataclass(frozen=True, slots=True)
class BrainDiagnosticResearch:
    """Versioned observational reference, separate from SharedBrainAnalysisView.

V1 references bind the unchanged production view fingerprint. V2 references
carry all six verified shadow outputs and never contain a production view.
All flags refer to this sidecar, not to the underlying V1 source's eligibility.
"""
    canonical_instrument_id: str
    as_of: datetime
    registry_version: str
    mode: RegistryMode
    strategy_version: StrategyVersionReference | None
    policy_version: str | None
    sources: tuple[EvaluatedDiagnostic | ShadowDiagnosticEnvelope, ...]
    diagnostic_result_fingerprint: str
    production_brain_fingerprint: str | None
    fingerprint: str
    production_brain_blocker: str | None = None
    contract_version: str = VERSION
    purpose: str = "OBSERVATIONAL_RESEARCH_ONLY"
    score_eligible: bool = False
    execution_eligible: bool = False
    portfolio_action_eligible: bool = False

    def __post_init__(self):
        object.__setattr__(self, "as_of", _utc(self.as_of))
        if (not _text(self.canonical_instrument_id) or not self.canonical_instrument_id.startswith("NSE:") or len(self.canonical_instrument_id) <= 4
                or not isinstance(self.mode, RegistryMode) or not isinstance(self.sources, tuple) or not self.sources
                or self.contract_version != VERSION or self.purpose != "OBSERVATIONAL_RESEARCH_ONLY"
                or self.score_eligible is not False or self.execution_eligible is not False
                or self.portfolio_action_eligible is not False):
            raise ValueError("BRAIN_DIAGNOSTIC_RESEARCH_CONTRACT_INVALID")
        resolve_diagnostic_registry(self.registry_version, mode=self.mode)
        if self.registry_version == DIAGNOSTIC_REGISTRY_VERSION:
            if (self.mode is not RegistryMode.ACTIVE or self.policy_version is not None
                    or not ((self.production_brain_fingerprint is None and _text(self.production_brain_blocker))
                            or (_text(self.production_brain_fingerprint) and self.production_brain_blocker is None))):
                raise ValueError(CROSS_BRAIN)
            for item in self.sources:
                if active_v1_rejection(item, self.registry_version):
                    raise ValueError(CROSS_BRAIN)
                require_v1_stored_diagnostic(item.record)
                if (item.record.instrument_id != self.canonical_instrument_id
                        or _utc(item.record.as_of_timestamp) != self.as_of
                        or _utc(item.record.evaluated_at) > self.as_of):
                    raise ValueError("BRAIN_DIAGNOSTIC_PIT_OR_INSTRUMENT_MISMATCH")
            strategies = {item.record.strategy_version for item in self.sources}
            if len(strategies) != 1 or self.strategy_version not in strategies or not isinstance(self.strategy_version, StrategyVersionReference):
                raise ValueError("BRAIN_DIAGNOSTIC_STRATEGY_AMBIGUOUS")
            keys = tuple(item.canonical_rule_id for item in self.sources)
            if any(not isinstance(k, int) or not 1 <= k <= 61 for k in keys):
                raise ValueError("BRAIN_DIAGNOSTIC_RULE_INVALID")
            if any(str(item.canonical_rule_id) != item.record.rule_id for item in self.sources):
                raise ValueError("BRAIN_DIAGNOSTIC_RULE_MISMATCH")
        else:
            if (self.mode is not RegistryMode.SHADOW or self.strategy_version is not None
                    or self.production_brain_fingerprint is not None or self.production_brain_blocker is not None):
                raise ValueError(CROSS_BRAIN)
            for item in self.sources:
                if not isinstance(item, ShadowDiagnosticEnvelope):
                    raise ValueError(CROSS_BRAIN)
                item.__post_init__()
                if (item.source.canonical_instrument_id != self.canonical_instrument_id
                        or item.as_of != self.as_of or item.policy_version != self.policy_version):
                    raise ValueError("BRAIN_DIAGNOSTIC_PIT_OR_INSTRUMENT_MISMATCH")
            keys = tuple(item.source.rule_id for item in self.sources)
            if keys != V2_RULE_IDS:
                raise ValueError("BRAIN_SHADOW_SIX_RULES_REQUIRED")
            # Only Rule 29 canonically owns market lineage; never require its
            # optional market input on unrelated fundamental rules.
            if len({(item.source.input_fingerprint, item.source.entity_fingerprint, item.source.entity_type) for item in self.sources}) != 1:
                raise ValueError("BRAIN_SHADOW_SOURCE_CONTEXT_CONFLICTED")
        if keys != tuple(sorted(set(keys))):
            raise ValueError("BRAIN_DIAGNOSTIC_DUPLICATE_OR_UNORDERED_LINEAGE")
        if (self.diagnostic_result_fingerprint != content_fingerprint(self.sources)
                or self.fingerprint != content_fingerprint(_payload(self))):
            raise ValueError("BRAIN_DIAGNOSTIC_FINGERPRINT_MISMATCH")

    def to_json(self):
        self.__post_init__()
        return canonical_json(self)


def brain_diagnostic_research(*, canonical_instrument_id, as_of, diagnostics,
                              registry_version=DIAGNOSTIC_REGISTRY_VERSION,
                              mode=RegistryMode.ACTIVE, production_brain_fingerprint=None, production_brain_blocker=None):
    registry = resolve_diagnostic_registry(registry_version, mode=mode)
    if not isinstance(diagnostics, tuple) or not diagnostics:
        raise ValueError("BRAIN_DIAGNOSTIC_INPUT_REQUIRED")
    if registry_version == DIAGNOSTIC_REGISTRY_VERSION:
        if any(active_v1_rejection(item, registry_version) for item in diagnostics):
            raise ValueError(CROSS_BRAIN)
        sources = tuple(sorted(diagnostics, key=lambda item: item.canonical_rule_id))
        strategy, policy = sources[0].record.strategy_version, None
    else:
        from app.fundamentals.diagnostic_v2_shadow import FundamentalV2ShadowResult
        if any(not isinstance(item, (FundamentalV2ShadowResult, ShadowDiagnosticEnvelope)) for item in diagnostics):
            raise ValueError(CROSS_BRAIN)
        sources = tuple(sorted((shadow_diagnostic_envelope(item.source if isinstance(item, ShadowDiagnosticEnvelope) else item, as_of=as_of)
                                for item in diagnostics), key=lambda item: item.source.rule_id))
        # Verify supplied envelopes too; never repair a tampered wrapper.
        for item in diagnostics:
            if isinstance(item, ShadowDiagnosticEnvelope): item.__post_init__()
        strategy, policy = None, sources[0].policy_version
    values = dict(canonical_instrument_id=canonical_instrument_id, as_of=_utc(as_of),
                  registry_version=registry_version, mode=registry.mode, strategy_version=strategy,
                  policy_version=policy, sources=sources, diagnostic_result_fingerprint=content_fingerprint(sources),
                  production_brain_fingerprint=production_brain_fingerprint, production_brain_blocker=production_brain_blocker, contract_version=VERSION,
                  purpose="OBSERVATIONAL_RESEARCH_ONLY", score_eligible=False, execution_eligible=False,
                  portfolio_action_eligible=False)
    return BrainDiagnosticResearch(**values, fingerprint=content_fingerprint(values))


@dataclass(frozen=True, slots=True)
class FundamentalPortfolioObservation:
    """A holding reference only, never holdings/analytics or an action container."""
    research: BrainDiagnosticResearch
    holding_reference: str | None
    fingerprint: str
    portfolio_action_eligible: bool = False

    def __post_init__(self):
        if not isinstance(self.research, BrainDiagnosticResearch): raise ValueError(CROSS_PORTFOLIO)
        self.research.__post_init__()
        if (self.research.registry_version != V2_VERSION or self.research.mode is not RegistryMode.SHADOW
                or self.holding_reference is not None and not _text(self.holding_reference)
                or self.portfolio_action_eligible is not False):
            raise ValueError(CROSS_PORTFOLIO)
        if self.fingerprint != content_fingerprint(_payload(self)):
            raise ValueError("PORTFOLIO_OBSERVATION_FINGERPRINT_MISMATCH")

    def to_json(self):
        self.__post_init__()
        return canonical_json(self)


def portfolio_observation(research, *, holding_reference=None):
    values = dict(research=research, holding_reference=holding_reference, portfolio_action_eligible=False)
    return FundamentalPortfolioObservation(**values, fingerprint=content_fingerprint(values))


def compare_brain_diagnostics(v1: BrainDiagnosticResearch, v2: BrainDiagnosticResearch):
    """Exact state/readiness juxtaposition; no economic preference or action."""
    if not isinstance(v1, BrainDiagnosticResearch) or not isinstance(v2, BrainDiagnosticResearch): raise ValueError(CROSS_BRAIN)
    v1.__post_init__(); v2.__post_init__()
    if (v1.registry_version != DIAGNOSTIC_REGISTRY_VERSION or v2.registry_version != V2_VERSION
            or (v1.canonical_instrument_id, v1.as_of) != (v2.canonical_instrument_id, v2.as_of)):
        raise ValueError("BRAIN_COMPARISON_VERSION_OR_CONTEXT_MISMATCH")
    states = {item.canonical_rule_id: item.record.result for item in v1.sources}
    values = dict(contract_version=VERSION, canonical_instrument_id=v1.canonical_instrument_id, as_of=v1.as_of,
                  v1_registry=v1.registry_version, v2_registry=v2.registry_version,
                  v1_production_fingerprint=v1.production_brain_fingerprint,
                  v1_production_blocker=v1.production_brain_blocker,
                  v1_evidence_fingerprint=v1.diagnostic_result_fingerprint, v2_evidence_fingerprint=v2.diagnostic_result_fingerprint,
                  v1_reference_fingerprint=v1.fingerprint, v2_reference_fingerprint=v2.fingerprint,
                  observations=tuple((s.source.rule_id, states.get(s.source.rule_id), s.source.core_state.value,
                                      tuple((c.component_id, c.state.value) for c in s.source.component_states), s.source.blockers) for s in v2.sources),
                  purpose="OBSERVATIONAL_RESEARCH_ONLY", score_eligible=False, execution_eligible=False, portfolio_action_eligible=False)
    return canonical_json(dict(values, fingerprint=content_fingerprint(values)))
