"""Six approved descriptive measurements, isolated from the active V1 engine.

Consumes the existing comparability/vintage boundary. No retrieval, persistence,
economic thresholds, scoring or supportive synthesis is implemented here.
"""
from dataclasses import dataclass, fields
from datetime import UTC, datetime, timedelta
from decimal import Context, Decimal, DecimalException, InvalidOperation, Underflow, localcontext
from enum import StrEnum
import json
import re

from app.analysis.models import AnalysisStatus
from app.analysis.valuation_trade import ValuationRules, valuation
from app.domain.models import AsOfSnapshot
from app.fundamentals.diagnostic_comparability import (
    ComparableFinancialSeries, ComparabilityState as State, canonical_json,
    consecutive, content_fingerprint, fiscal_key, representation,
)
from app.fundamentals.diagnostic_input import CanonicalFinancialDiagnosticInput
from app.fundamentals.models import FinancialMetric as M, FinancialPeriodType as P, FinancialValueBasis as B
from app.historical.pit_company_type_classification_activation import PitCompanyTypeClassificationState
from app.registry.canonical import DIAGNOSTIC_REGISTRY_VERSION
from app.registry.versioned import (
    APPROVAL_FINGERPRINT, PROPOSAL_FINGERPRINT, RegistryMode, V2_RULE_IDS,
    V2_VERSION, approved_shadow_component_schema, resolve_diagnostic_registry,
)

EVALUATOR_VERSION = "fundamental-diagnostic-v2-shadow/v1"
_FP = re.compile(r"sha256:[0-9a-f]{64}\Z")
_EVIDENCE_FP = re.compile(r"(?:sha256:)?[0-9a-f]{64}\Z")


class ShadowEntity(StrEnum):
    NON_FINANCIAL = "NON_FINANCIAL"
    BANK = "BANK"
    NBFC = "NBFC"
    INSURER = "INSURER"
    UNKNOWN_NON_COMPARABLE = "UNKNOWN_NON_COMPARABLE"


def _payload(value):
    return {f.name: getattr(value, f.name) for f in fields(value) if f.name != "fingerprint"}


def _checked_strings(values):
    return isinstance(values, tuple) and values == tuple(sorted(set(values))) and all(isinstance(v, str) and v for v in values)


@dataclass(frozen=True, slots=True)
class ShadowComponent:
    component_id: str
    role: str
    state: State
    measurements: tuple[tuple[str, Decimal], ...]
    reasons: tuple[str, ...]
    series: tuple[ComparableFinancialSeries, ...]
    fingerprint: str

    def __post_init__(self):
        if (not self.component_id or self.role not in {"MANDATORY_CORE", "OPTIONAL_COMPONENT"}
                or not isinstance(self.state, State) or not _checked_strings(self.reasons)
                or not isinstance(self.measurements, tuple) or not isinstance(self.series, tuple)):
            raise ValueError("V2_SHADOW_COMPONENT_INVALID")
        names = tuple(name for name, _ in self.measurements)
        if names != tuple(sorted(set(names))) or any(not name or not isinstance(v, Decimal) or not v.is_finite() for name, v in self.measurements):
            raise ValueError("V2_SHADOW_MEASUREMENTS_INVALID")
        if (self.state is State.READY) != bool(self.measurements) or self.state is not State.READY and not self.reasons:
            raise ValueError("V2_SHADOW_COMPONENT_STATE_CONTRADICTION")
        keys = tuple((s.metric.value, s.period_type.value, s.value_basis.value) for s in self.series)
        if keys != tuple(sorted(set(keys))):
            raise ValueError("V2_SHADOW_SERIES_ORDER_OR_DUPLICATE")
        for series in self.series:
            series.__post_init__()
        if self.fingerprint != content_fingerprint(_payload(self)):
            raise ValueError("V2_SHADOW_COMPONENT_FINGERPRINT_MISMATCH")


def _core_state(components):
    core = tuple(c for c in components if c.role == "MANDATORY_CORE")
    values = core or components  # Rule 29: one qualified multiple is descriptive availability only.
    states = tuple(c.state for c in values)
    if not core and State.READY in states:
        return State.READY
    if State.EVIDENCE_CONFLICTED in states:
        return State.EVIDENCE_CONFLICTED
    if all(s is State.READY for s in states):
        return State.READY
    if State.READY in states:
        return State.PARTIAL
    if State.POLICY_BLOCKED in states and all(s is State.POLICY_BLOCKED for s in states):
        return State.POLICY_BLOCKED
    return State.INSUFFICIENT_DATA


def _coverage(components):
    optional = tuple(c for c in components if c.role == "OPTIONAL_COMPONENT")
    if any(c.state is State.EVIDENCE_CONFLICTED for c in optional):
        return "CONFLICTED"
    return "COMPLETE" if all(c.state is State.READY for c in optional) else "INCOMPLETE"


@dataclass(frozen=True, slots=True)
class FundamentalV2ShadowResult:
    registry_version: str
    parent_registry_version: str
    evaluator_version: str
    proposal_fingerprint: str
    approval_fingerprint: str
    rule_id: int
    canonical_instrument_id: str
    entity_type: ShadowEntity
    as_of: datetime
    input_fingerprint: str
    entity_fingerprint: str | None
    market_fingerprint: str | None
    component_states: tuple[ShadowComponent, ...]
    core_state: State
    optional_coverage: str
    blockers: tuple[str, ...]
    input_evidence_ids: tuple[str, ...]
    input_evidence_fingerprints: tuple[str, ...]
    fingerprint: str
    classification_state: State = State.POLICY_BLOCKED
    confidence: None = None
    score_eligible: bool = False
    execution_eligible: bool = False
    shadow_only: bool = True
    actionability: str = "WATCH_ONLY"
    execution_status: str = "NON_EXECUTABLE"

    def __post_init__(self):
        if ((self.registry_version, self.parent_registry_version, self.evaluator_version) !=
                (V2_VERSION, DIAGNOSTIC_REGISTRY_VERSION, EVALUATOR_VERSION)
                or (self.proposal_fingerprint, self.approval_fingerprint) != (PROPOSAL_FINGERPRINT, APPROVAL_FINGERPRINT)
                or self.rule_id not in V2_RULE_IDS or not self.canonical_instrument_id
                or not isinstance(self.entity_type, ShadowEntity) or not isinstance(self.core_state, State)
                or self.as_of.tzinfo is None or self.as_of.utcoffset() is None):
            raise ValueError("V2_SHADOW_RESULT_IDENTITY_INVALID")
        object.__setattr__(self, "as_of", self.as_of.astimezone(UTC))
        if (self.score_eligible is not False or self.execution_eligible is not False or self.shadow_only is not True
                or self.actionability != "WATCH_ONLY" or self.execution_status != "NON_EXECUTABLE"
                or self.classification_state is not State.POLICY_BLOCKED or self.confidence is not None):
            raise ValueError("V2_SHADOW_AUTHORITY_FORBIDDEN")
        if not isinstance(self.component_states, tuple) or not self.component_states:
            raise ValueError("V2_SHADOW_COMPONENTS_REQUIRED")
        ids = tuple(c.component_id for c in self.component_states)
        if ids != tuple(sorted(set(ids))):
            raise ValueError("V2_SHADOW_COMPONENT_ORDER_OR_DUPLICATE")
        if tuple((c.component_id, c.role) for c in self.component_states) != dict(approved_shadow_component_schema())[self.rule_id]:
            raise ValueError("V2_SHADOW_COMPONENT_SCHEMA_MISMATCH")
        for c in self.component_states:
            c.__post_init__()
            for s in c.series:
                if s.canonical_instrument_id != self.canonical_instrument_id or s.as_of != self.as_of:
                    raise ValueError("V2_SHADOW_LINEAGE_PIT_MISMATCH")
        if self.core_state is not _core_state(self.component_states) or self.optional_coverage != _coverage(self.component_states):
            raise ValueError("V2_SHADOW_READINESS_CONTRADICTION")
        if self.entity_type is not ShadowEntity.NON_FINANCIAL and any(c.state is not State.POLICY_BLOCKED for c in self.component_states):
            raise ValueError("V2_SHADOW_ENTITY_POLICY_BLOCKED")
        for values in (self.blockers, self.input_evidence_ids, self.input_evidence_fingerprints):
            if not _checked_strings(values):
                raise ValueError("V2_SHADOW_LINEAGE_ORDER_OR_DUPLICATE")
        if not self.blockers or not self.input_evidence_fingerprints:
            raise ValueError("V2_SHADOW_LINEAGE_REQUIRED")
        required_blockers = {r for c in self.component_states for r in c.reasons}
        required_blockers.add("POLICY_BLOCKED_THRESHOLD_NOT_APPROVED" if self.rule_id == 26 else "ECONOMIC_CLASSIFICATION_POLICY_NOT_APPROVED")
        if self.blockers != tuple(sorted(required_blockers)):
            raise ValueError("V2_SHADOW_BLOCKERS_MISMATCH")
        for fp in self.input_evidence_fingerprints:
            if not _EVIDENCE_FP.fullmatch(fp):
                raise ValueError("V2_SHADOW_LINEAGE_FINGERPRINT_INVALID")
        for fp in (self.input_fingerprint, self.entity_fingerprint, self.market_fingerprint):
            if fp is not None and not _FP.fullmatch(fp):
                raise ValueError("V2_SHADOW_LINEAGE_FINGERPRINT_INVALID")
        if self.fingerprint != content_fingerprint(_payload(self)):
            raise ValueError("V2_SHADOW_RESULT_FINGERPRINT_MISMATCH")

    @property
    def result_id(self):
        return "fundamental-v2-shadow:" + self.fingerprint.removeprefix("sha256:")

    @property
    def eligibility(self):
        # Explicit tripwire for the existing score/synthesis duck-typed entry.
        # This is NOT an adapter and never returns EvaluationEligibility.
        raise ValueError("V2_SHADOW_SCORE_FORBIDDEN")

    @property
    def record(self):
        raise ValueError("V2_SHADOW_LEGACY_CONSUMER_FORBIDDEN")

    def to_json(self):
        self.__post_init__()
        return canonical_json(self)


def _component(definition, series=(), measurements=(), reasons=(), policy=None):
    series = tuple(sorted(series, key=lambda s: (s.metric.value, s.period_type.value, s.value_basis.value)))
    reasons = set(reasons)
    reasons.update(r for s in series for r in s.reasons)
    if policy:
        reasons.add(policy)
    state = (State.EVIDENCE_CONFLICTED if any(s.state is State.EVIDENCE_CONFLICTED for s in series) else State.POLICY_BLOCKED if policy
             else State.INSUFFICIENT_DATA if reasons or not measurements else State.READY)
    # Even a policy-gated component retains conflict provenance and reasons.
    if any(s.state is State.EVIDENCE_CONFLICTED for s in series):
        reasons.add("EVIDENCE_CONFLICTED")
    payload = dict(component_id=definition["component_id"], role=definition["role"], state=state,
        measurements=tuple(sorted(measurements)) if state is State.READY else (), reasons=tuple(sorted(reasons)), series=series)
    return ShadowComponent(**payload, fingerprint=content_fingerprint(payload))


def _window(c, metric, anchors, *, quarterly=False, balance=False):
    period, basis = (P.POINT_IN_TIME, B.UNKNOWN) if balance else (P.QUARTERLY, B.QUARTER_ONLY) if quarterly else (P.ANNUAL, B.FULL_YEAR)
    series = c.series(metric, period, basis, period_ends=tuple(sorted({a[3] for a in anchors})))
    reasons = set(series.reasons)
    points = []
    for anchor in anchors:
        matching = [o for o in series.observations if
            ((o.period_identity.fiscal_year == anchor[0] and o.period_identity.period_end == anchor[3])
             if balance else fiscal_key(o) == anchor)]
        if len(matching) != 1:
            reasons.add("REQUIRED_FISCAL_PERIOD_MISSING_OR_AMBIGUOUS")
        else:
            points.append(matching[0])
    if not anchors:
        reasons.add("INSUFFICIENT_COMPARABLE_HISTORY")
    return series, tuple(points), reasons


def _duration(c, metric, depth, quarterly=False):
    anchors = c.anchors(P.QUARTERLY if quarterly else P.ANNUAL)[-depth:]
    s, points, reasons = _window(c, metric, anchors, quarterly=quarterly)
    if len(anchors) != depth:
        reasons.add("INSUFFICIENT_COMPARABLE_HISTORY")
    if not consecutive(anchors, quarterly=quarterly):
        reasons.add("MISSING_OR_NONCOMPARABLE_FISCAL_PERIOD")
    return s, points, reasons


def _ratio_compatibility(*points):
    return set() if len({representation(o) for group in points for o in group}) <= 1 else {"CROSS_METRIC_UNIT_CURRENCY_OR_BASIS_MISMATCH"}


def _balance_window(c):
    return tuple(sorted({fiscal_key(f) for f in c.facts if f.statement_scope is c.scope and
        f.period_type is P.POINT_IN_TIME and f.available_at <= c.as_of and f.period_end <= c.as_of}, key=lambda k: (k[3], k)))[-1:]


class FundamentalDiagnosticV2ShadowEvaluator:
    """Pure evaluation after an explicit, pinned shadow-version resolution."""

    def evaluate(self, financial: CanonicalFinancialDiagnosticInput, *, registry_version: str,
                 as_of: datetime, entity_type: ShadowEntity | None, market: AsOfSnapshot | None = None):
        registry = resolve_diagnostic_registry(registry_version, mode=RegistryMode.SHADOW)
        if registry.registry_version != V2_VERSION:
            raise ValueError("V2_SHADOW_EXPLICIT_VERSION_REQUIRED")
        financial.__post_init__()
        if as_of.tzinfo is None or as_of.utcoffset() is None or financial.as_of != as_of:
            raise ValueError("V2_SHADOW_INPUT_ASOF_MISMATCH")
        as_of = as_of.astimezone(UTC)
        try:
            entity = ShadowEntity(entity_type) if entity_type is not None else ShadowEntity.UNKNOWN_NON_COMPARABLE
        except (TypeError, ValueError):
            raise ValueError("V2_SHADOW_ENTITY_UNKNOWN") from None
        classification = financial.company_type
        entity_reason = None
        if classification is None or classification.state is not PitCompanyTypeClassificationState.CLASSIFIED:
            entity_reason = "GOVERNED_ENTITY_TYPE_UNAVAILABLE"
        elif entity.value != classification.company_type.value:
            entity_reason = "GOVERNED_ENTITY_TYPE_MISMATCH"
        if entity is not ShadowEntity.NON_FINANCIAL:
            entity_reason = "ENTITY_BRANCH_POLICY_BLOCKED:" + entity.value
        c = financial.comparable
        results = []
        for rule in registry.rules:
            if rule.rule_id not in V2_RULE_IDS:
                continue
            definition = json.loads(rule.definition_json)
            components = []
            for spec in definition["components"]:
                if entity_reason:
                    component = _component(spec, reasons=tuple(r.value for r in classification.reasons) if classification else (), policy=entity_reason)
                else:
                    with localcontext(Context(prec=34)) as arithmetic:
                        arithmetic.traps[Underflow] = True
                        try:
                            component = self._measure(rule.rule_id, spec, financial, market)
                        except DecimalException:
                            component = _component(spec, reasons=("ARITHMETIC_DOMAIN_OR_REPRESENTATION_UNAVAILABLE",))
                components.append(component)
            components = tuple(sorted(components, key=lambda item: item.component_id))
            blockers = {r for comp in components for r in comp.reasons}
            blockers.add("POLICY_BLOCKED_THRESHOLD_NOT_APPROVED" if rule.rule_id == 26 else "ECONOMIC_CLASSIFICATION_POLICY_NOT_APPROVED")
            source_ids = {fid for comp in components for s in comp.series for fid in s.candidate_fact_ids}
            fps = {financial.fingerprint, c.fingerprint, *(s.fingerprint for comp in components for s in comp.series)}
            fps.update(o.fingerprint for comp in components for s in comp.series for o in s.observations)
            entity_fp = classification.fingerprint if classification else None
            market_fp = content_fingerprint(market) if rule.rule_id == 29 and market is not None else None
            if entity_fp:
                fps.add(entity_fp)
                source_ids.add(classification.receipt_id)
            if market_fp:
                fps.add(market_fp)
                source_ids.update(o.id for o in market.observations)
            payload = dict(registry_version=registry_version, parent_registry_version=DIAGNOSTIC_REGISTRY_VERSION,
                evaluator_version=EVALUATOR_VERSION, proposal_fingerprint=PROPOSAL_FINGERPRINT, approval_fingerprint=APPROVAL_FINGERPRINT,
                rule_id=rule.rule_id, canonical_instrument_id=c.canonical_instrument_id, entity_type=entity, as_of=as_of,
                input_fingerprint=financial.fingerprint, entity_fingerprint=entity_fp, market_fingerprint=market_fp,
                component_states=components, core_state=_core_state(components), optional_coverage=_coverage(components),
                blockers=tuple(sorted(blockers)), input_evidence_ids=tuple(sorted(source_ids)), input_evidence_fingerprints=tuple(sorted(fps)),
                classification_state=State.POLICY_BLOCKED, confidence=None, score_eligible=False, execution_eligible=False,
                shadow_only=True, actionability="WATCH_ONLY", execution_status="NON_EXECUTABLE")
            results.append(FundamentalV2ShadowResult(**payload, fingerprint=content_fingerprint(payload)))
        return tuple(results)

    def _measure(self, rule, spec, financial, market):
        c, name = financial.comparable, spec["component_id"]
        if spec["policy_availability"] != "PROPOSED_ONLY":
            # No new debt/cash boundary, EBIT numerator, forecast, share bridge,
            # or issuer-ratio formula is approved by existence of a raw fact.
            series = ()
            if name == "NET_DEBT":
                series = tuple(_window(c, m, _balance_window(c), balance=True)[0] for m in (M.TOTAL_DEBT, M.CASH_AND_EQUIVALENTS))
            return _component(spec, series, policy="COMPONENT_POLICY_NOT_APPROVED:" + name)
        if rule in {16, 25}:
            metric = M.REVENUE if name.startswith("REVENUE") else M.PAT if name.startswith("PAT") else M.EPS_BASIC
            s, points, reasons = _duration(c, metric, 6 if rule == 16 else 5, quarterly=rule == 25)
            values = ()
            if not reasons:
                required = (points[0], points[-1]) if rule == 16 else (points[-1], points[-2], points[-5])
                if any(p.value <= 0 for p in required):
                    reasons.add("POSITIVE_ENDPOINT_OR_COMPARISON_DOMAIN_REQUIRED")
                else:
                    values = (("CAGR", (points[-1].value / points[0].value) ** (Decimal(1) / 5) - 1),) if rule == 16 else (
                        ("YOY", points[-1].value / points[-5].value - 1), ("QOQ", points[-1].value / points[-2].value - 1))
            return _component(spec, (s,), values, reasons)
        if rule == 17:
            pat, profits, reasons = _duration(c, M.PAT, 1)
            anchors = c.anchors(P.ANNUAL)[-1:]
            balances = ()
            if anchors:
                year, _, start, end = anchors[0]
                before = start - timedelta(days=1)
                balances = ((year - 1, 0, before, before), (year, 0, end, end))
            eq, equity, missing = _window(c, M.TOTAL_EQUITY, balances, balance=True)
            reasons |= missing | _ratio_compatibility(profits, equity)
            values = ()
            if not reasons:
                average = (equity[0].value + equity[1].value) / 2
                if average <= 0:
                    reasons.add("POSITIVE_AVERAGE_EQUITY_REQUIRED")
                else:
                    values = (("ROE", profits[-1].value / average),)
            return _component(spec, (pat, eq), values, reasons)
        if rule == 19:
            anchors = _balance_window(c)
            debt, debts, reasons = _window(c, M.TOTAL_DEBT, anchors, balance=True)
            eq, equity, missing = _window(c, M.TOTAL_EQUITY, anchors, balance=True)
            reasons |= missing | _ratio_compatibility(debts, equity)
            values = ()
            if not reasons:
                if equity[-1].value <= 0:
                    reasons.add("POSITIVE_EQUITY_REQUIRED")
                else:
                    values = (("DEBT_EQUITY", debts[-1].value / equity[-1].value),)
            return _component(spec, (debt, eq), values, reasons)
        if rule == 26:
            income, profits, reasons = _duration(c, M.PAT if name == "NET_PROFIT_MARGIN" else M.PBT, 5, quarterly=True)
            rev, revenues, missing = _duration(c, M.REVENUE, 5, quarterly=True)
            reasons |= missing | _ratio_compatibility(profits, revenues)
            values = ()
            if not reasons:
                if any(p.value <= 0 for p in revenues):
                    reasons.add("POSITIVE_REVENUE_REQUIRED")
                else:
                    margins = tuple(p.value / r.value for p, r in zip(profits, revenues, strict=True))
                    values = ((name, margins[-1]), (name + "_PRIOR_YEAR", margins[-5]),
                              (name + "_YOY_PERCENTAGE_POINTS", 100 * (margins[-1] - margins[-5])))
            return _component(spec, (income, rev), values, reasons)
        # Only P/E has a currently admitted canonical valuation input/formula.
        # Reuse V1's certified bridge and measurement; discard ALL its verdicts
        # and confidence. Never copy that favourable text into a shadow result.
        eps, _, reasons = _duration(c, M.EPS_BASIC, 1)
        certified = financial.rule_input(29, market)
        reasons |= set(certified.reasons)
        values = ()
        if not reasons and certified.snapshot is not None:
            existing = valuation(market, certified.snapshot, c.canonical_instrument_id, ValuationRules(15, 35))
            if existing.status is AnalysisStatus.VALID:
                try:
                    pe = Decimal(dict(existing.details)["pe"])
                    if pe.is_finite() and pe > 0:
                        values = (("PE", pe),)
                except (InvalidOperation, KeyError):
                    pass
        if not values:
            reasons.add("CANONICAL_PE_INPUT_UNAVAILABLE")
        return _component(spec, (eps,), values, reasons)
