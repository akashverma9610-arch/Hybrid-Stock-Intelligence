"""Pure, rejection-only registry admission; compatibility is not gate clearance.

Legacy nominal inputs remain V1. Optional lineage binds supplied dependencies
to the complete input; it cannot replace inputs or confer execution authority.
No registry loading, clock, repository or action implementation lives here.
"""
from dataclasses import dataclass, fields
from datetime import UTC, date, datetime
from decimal import Decimal
import re

from app.diagnostics.brain_lineage import require_production_evidence
from app.domain.models import StrategyVersionReference
from app.fundamentals.diagnostic_comparability import canonical_json, content_fingerprint
from app.registry.canonical import DIAGNOSTIC_REGISTRY_VERSION
from app.registry.versioned import RegistryMode, V2_VERSION

VERSION = "fundamental-six-gates-version-compatibility/v1"
SHADOW_FORBIDDEN = "V2_SHADOW_GATE_CONSUMPTION_FORBIDDEN"
CROSS_REGISTRY = "CROSS_REGISTRY_GATE_CONSUMPTION_FORBIDDEN"


class GateVersionBlocked(ValueError):
    """Infrastructure ineligibility, never a company-risk FAIL or a gate PASS."""
    compatibility_state = "VERSION_BLOCKED"


def require_gate_registry(version):
    if version == V2_VERSION:
        raise GateVersionBlocked(SHADOW_FORBIDDEN)
    # Exact pre-existing V1 engine fixture label, not a latest/unknown alias.
    # New typed lineage below always requires the canonical registry identity.
    if version not in (DIAGNOSTIC_REGISTRY_VERSION, "v1"):
        raise GateVersionBlocked(CROSS_REGISTRY)


def require_gate_source(value, *, _seen=()):
    """Call before extracting a scalar from a versioned production artifact."""
    if value is None:
        return
    if id(value) in _seen:
        raise GateVersionBlocked("GATE_EVIDENCE_CYCLE_UNVERIFIED")
    getter = value.get if isinstance(value, dict) else lambda k, default=None: getattr(value, k, default)
    require_gate_registry(getter("registry_version", DIAGNOSTIC_REGISTRY_VERSION))
    try:
        require_production_evidence(value, reason=SHADOW_FORBIDDEN, legacy_version_label=True)
    except ValueError:
        raise GateVersionBlocked(SHADOW_FORBIDDEN) from None
    if (getter("mode", RegistryMode.ACTIVE) != RegistryMode.ACTIVE
            or getter("shadow_only", False) is not False
            or getter("purpose") == "OBSERVATIONAL_RESEARCH_ONLY"
            or getter("core_state") is not None or getter("component_states") is not None
            or any(getter(key, True) is not True for key in
                   ("score_eligible", "execution_eligible", "portfolio_action_eligible"))):
        raise GateVersionBlocked(SHADOW_FORBIDDEN)
    # Fixed dependency names only; never unwrap or use any numeric component.
    for key in ("components", "diagnostics"):
        children = getter(key, ())
        if type(children) is not tuple:
            raise GateVersionBlocked("GATE_DEPENDENCY_CONTAINER_UNVERIFIED")
        for child in children:
            require_gate_source(child, _seen=_seen+(id(value),))


def _utc(value):
    if type(value) is not datetime or value.tzinfo is None or value.utcoffset() is None:
        raise GateVersionBlocked("GATE_LINEAGE_AS_OF_INVALID")
    return value.astimezone(UTC)


def _text(value):
    return type(value) is str and bool(value) and value == value.strip()


def _fingerprint(value):
    return type(value) is str and re.fullmatch(r"sha256:[0-9a-f]{64}", value) is not None


def _payload(value):
    return {f.name: getattr(value, f.name) for f in fields(value) if f.name != "fingerprint"}


def gate_input_fingerprint(inputs):
    """The legacy holding date is a date, not an invented timestamp."""
    body = {f.name: getattr(inputs, f.name) for f in fields(inputs)}
    if type(body.get("holding_entry_date")) is date:
        body["holding_entry_date"] = body["holding_entry_date"].isoformat()
    return content_fingerprint(body)


@dataclass(frozen=True, slots=True)
class GateEvidenceLineage:
    """Descriptive provenance for one named GateInput field; no evidence value."""
    input_field: str
    registry_version: str
    mode: RegistryMode
    strategy_version: StrategyVersionReference | None
    policy_version: str | None
    as_of: datetime
    source_fingerprints: tuple[str, ...]
    score_eligible: bool
    execution_eligible: bool
    portfolio_action_eligible: bool

    def __post_init__(self):
        from app.gates.engine import GateInput
        if self.input_field not in {f.name for f in fields(GateInput)}:
            raise GateVersionBlocked("GATE_LINEAGE_INPUT_FIELD_UNKNOWN")
        if self.registry_version not in (DIAGNOSTIC_REGISTRY_VERSION, V2_VERSION) or type(self.mode) is not RegistryMode:
            raise GateVersionBlocked(CROSS_REGISTRY)
        if self.strategy_version is not None and (type(self.strategy_version) is not StrategyVersionReference
                or not _text(self.strategy_version.strategy_id) or not _text(self.strategy_version.version)):
            raise GateVersionBlocked("GATE_LINEAGE_STRATEGY_INVALID")
        if self.policy_version is not None and not _text(self.policy_version):
            raise GateVersionBlocked("GATE_LINEAGE_POLICY_INVALID")
        object.__setattr__(self, "as_of", _utc(self.as_of))
        if (type(self.source_fingerprints) is not tuple or not self.source_fingerprints
                or any(not _fingerprint(x) for x in self.source_fingerprints)
                or len(set(self.source_fingerprints)) != len(self.source_fingerprints)):
            raise GateVersionBlocked("GATE_LINEAGE_SOURCE_INVALID")
        object.__setattr__(self, "source_fingerprints", tuple(sorted(self.source_fingerprints)))
        flags = (self.score_eligible, self.execution_eligible, self.portfolio_action_eligible)
        if any(type(x) is not bool for x in flags):
            raise GateVersionBlocked("GATE_LINEAGE_ELIGIBILITY_INVALID")
        if (self.registry_version == V2_VERSION or self.mode is RegistryMode.SHADOW) and (
                self.mode is not RegistryMode.SHADOW or any(flags)):
            raise GateVersionBlocked("GATE_LINEAGE_SHADOW_AUTHORITY_CONTRADICTION")


@dataclass(frozen=True, slots=True)
class GateEvidenceContext:
    """In-memory audit binding only. Never persisted in legacy gate results."""
    as_of: datetime
    gate_policy_version: str
    input_fingerprint: str
    dependencies: tuple[GateEvidenceLineage, ...]
    fingerprint: str
    contract_version: str = VERSION

    def __post_init__(self):
        object.__setattr__(self, "as_of", _utc(self.as_of))
        if self.contract_version != VERSION or not _text(self.gate_policy_version) or not _fingerprint(self.input_fingerprint):
            raise GateVersionBlocked("GATE_LINEAGE_BINDING_INVALID")
        if type(self.dependencies) is not tuple or not self.dependencies:
            raise GateVersionBlocked("GATE_LINEAGE_DEPENDENCIES_REQUIRED")
        for item in self.dependencies:
            if type(item) is not GateEvidenceLineage:
                raise GateVersionBlocked("GATE_LINEAGE_DEPENDENCY_INVALID")
            item.__post_init__()
            if item.as_of > self.as_of:
                raise GateVersionBlocked("GATE_LINEAGE_FUTURE_EVIDENCE")
        keys = tuple(item.input_field for item in self.dependencies)
        if len(set(keys)) != len(keys):
            raise GateVersionBlocked("GATE_LINEAGE_DUPLICATE_OR_CONFLICTING_DEPENDENCY")
        object.__setattr__(self, "dependencies", tuple(sorted(self.dependencies, key=lambda x: x.input_field)))
        if self.fingerprint != content_fingerprint(_payload(self)):
            raise GateVersionBlocked("GATE_LINEAGE_FINGERPRINT_MISMATCH")

    def to_json(self):
        self.__post_init__()
        return canonical_json(self)


def gate_evidence_context(inputs, *, as_of, gate_policy_version, dependencies):
    """Bind explicit references; never infer provenance or strip a shadow object."""
    require_gate_inputs(inputs)
    if type(dependencies) is not tuple or any(type(x) is not GateEvidenceLineage for x in dependencies):
        raise GateVersionBlocked("GATE_LINEAGE_DEPENDENCY_INVALID")
    body = dict(as_of=_utc(as_of), gate_policy_version=gate_policy_version,
                input_fingerprint=gate_input_fingerprint(inputs),
                dependencies=tuple(sorted(dependencies, key=lambda x: x.input_field)), contract_version=VERSION)
    return GateEvidenceContext(**body, fingerprint=content_fingerprint(body))


def require_gate_inputs(inputs, *, registry_version=DIAGNOSTIC_REGISTRY_VERSION,
                        as_of=None, gate_policy_version=None, evidence_context=None):
    """One admission firewall before any of the six unchanged gate methods."""
    from app.gates.engine import GateInput, PortfolioExposure, SurveillanceObservation, TradeManagementPlan
    require_gate_registry(registry_version)
    require_gate_source(inputs)
    if type(inputs) is not GateInput:
        raise GateVersionBlocked(CROSS_REGISTRY)

    def check(value, expected, *, optional=True):
        if value is None and optional:
            return
        require_gate_source(value)
        if type(value) is not expected:
            raise GateVersionBlocked("GATE_EVIDENCE_TYPE_UNVERIFIED")
        if expected is Decimal and not value.is_finite():
            raise GateVersionBlocked("GATE_NUMERIC_EVIDENCE_INVALID")
        if expected is datetime:
            _utc(value)
        if expected is tuple:
            if any(type(x) is not str for x in value):
                raise GateVersionBlocked("GATE_EVIDENCE_REFERENCE_INVALID")

    for name in ("raw_decision_score", "comparison_score", "expected_incremental_return", "modeled_switching_friction", "atr_expansion"):
        check(getattr(inputs, name), Decimal)
    for name in ("snapshot_as_of_timestamp", "earnings_scheduled_at", "earnings_schedule_verified_at"):
        check(getattr(inputs, name), datetime)
    check(inputs.holding_entry_date, date)
    for name in ("scorecard_id", "snapshot_id"):
        check(getattr(inputs, name), str)
    check(inputs.evidence_ids, tuple, optional=False)
    check(inputs.diagnostic_ids, tuple, optional=False)
    structures = (
        (inputs.surveillance, SurveillanceObservation, dict(id=str, effective_at=datetime, source=str, authoritative=bool,
                                                        asm_stage=int, gsm_stage=int, circuit_limit=Decimal, evidence_ids=tuple)),
        (inputs.trade_plan, TradeManagementPlan, dict(id=str, initial_tranche=Decimal, t1_reduction=Decimal,
                 stop_defined=bool, t1_defined=bool, breakeven_conditions=str, structural_conditions=str,
                 strategy_version=str, configuration_version=str)),
        (inputs.exposure, PortfolioExposure, dict(portfolio_equity=Decimal, existing_risk_amount=Decimal,
                 candidate_risk_amount=Decimal, candidate_allocation=Decimal, sector_allocation=Decimal, evidence_ids=tuple)),
    )
    for item, nominal, schema in structures:
        check(item, nominal)
        if item is not None:
            for name, expected in schema.items():
                check(getattr(item, name), expected, optional=expected not in (bool, tuple))
    if evidence_context is not None:
        if type(evidence_context) is not GateEvidenceContext:
            require_gate_source(evidence_context)
            raise GateVersionBlocked(CROSS_REGISTRY)
        evidence_context.__post_init__()
        if (evidence_context.as_of != _utc(as_of) or evidence_context.gate_policy_version != gate_policy_version
                or evidence_context.input_fingerprint != gate_input_fingerprint(inputs)):
            raise GateVersionBlocked("GATE_LINEAGE_BINDING_MISMATCH")
        for source in evidence_context.dependencies:
            require_gate_source(source)
