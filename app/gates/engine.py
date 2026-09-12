from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import date, datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Mapping, TYPE_CHECKING

if TYPE_CHECKING:
    from app.gates.version_compatibility import GateEvidenceContext
    from app.gates.score_provenance import GateScoreEvidence


class ActionContext(str, Enum):
    FRESH_ENTRY = "FRESH_ENTRY"
    ADD_TO_POSITION = "ADD_TO_POSITION"
    ROTATE_IN = "ROTATE_IN"
    HOLD_EXISTING = "HOLD_EXISTING"
    REDUCE_EXISTING = "REDUCE_EXISTING"
    EXIT_EXISTING = "EXIT_EXISTING"
    RISK_MANAGEMENT = "RISK_MANAGEMENT"


class GateOutcome(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


class ExecutionEligibility(str, Enum):
    EXECUTABLE = "EXECUTABLE"
    BLOCKED = "BLOCKED"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


@dataclass(frozen=True, slots=True)
class ExchangeCalendar:
    """Provider-independent calendar: weekdays minus explicit holidays only."""
    calendar_id: str
    holidays: frozenset[date] = frozenset()

    def is_trading_day(self, value: date) -> bool:
        return value.weekday() < 5 and value not in self.holidays

    def sessions_between(self, start: date, end: date) -> int:
        if end <= start:
            return 0
        current, sessions = start + timedelta(days=1), 0
        while current <= end:
            sessions += self.is_trading_day(current)
            current += timedelta(days=1)
        return sessions


@dataclass(frozen=True, slots=True)
class ExecutionGateConfig:
    version: str
    min_score_advantage: Decimal | None
    friction_model_version: str | None
    net_economic_hurdle: Decimal | None
    require_economic_hurdle: bool
    inactivity_sessions: int | None
    atr_expansion_threshold: Decimal | None
    velocity_penalty: Decimal | None
    disallowed_asm_stage: int | None
    disallow_gsm: bool | None
    circuit_limit_threshold: Decimal | None
    surveillance_max_age_days: int | None
    initial_tranche: Decimal | None
    t1_reduction: Decimal | None
    require_breakeven_plan: bool | None
    max_total_heat: Decimal | None
    max_stock_allocation: Decimal | None
    max_sector_allocation: Decimal | None
    blackout_sessions: int | None
    heat_methodology_version: str | None = None
    surveillance_freshness_basis: str = "calendar_days"

    def unresolved(self) -> tuple[str, ...]:
        required = {
            "min_score_advantage": self.min_score_advantage, "friction_model_version": self.friction_model_version,
            "inactivity_sessions": self.inactivity_sessions, "atr_expansion_threshold": self.atr_expansion_threshold,
            "velocity_penalty": self.velocity_penalty, "disallowed_asm_stage": self.disallowed_asm_stage,
            "disallow_gsm": self.disallow_gsm, "circuit_limit_threshold": self.circuit_limit_threshold,
            "surveillance_max_age_days": self.surveillance_max_age_days, "initial_tranche": self.initial_tranche,
            "t1_reduction": self.t1_reduction, "require_breakeven_plan": self.require_breakeven_plan,
            "max_total_heat": self.max_total_heat, "max_stock_allocation": self.max_stock_allocation,
            "max_sector_allocation": self.max_sector_allocation, "blackout_sessions": self.blackout_sessions,
            "heat_methodology_version": self.heat_methodology_version,
        }
        return tuple(name for name, value in required.items() if value is None)


@dataclass(frozen=True, slots=True)
class SurveillanceObservation:
    id: str
    effective_at: datetime
    source: str
    authoritative: bool
    asm_stage: int | None
    gsm_stage: int | None
    circuit_limit: Decimal | None
    evidence_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class TradeManagementPlan:
    id: str
    initial_tranche: Decimal | None
    t1_reduction: Decimal | None
    stop_defined: bool
    t1_defined: bool
    breakeven_conditions: str | None
    structural_conditions: str | None
    strategy_version: str
    configuration_version: str


@dataclass(frozen=True, slots=True)
class PortfolioExposure:
    portfolio_equity: Decimal | None
    existing_risk_amount: Decimal | None
    candidate_risk_amount: Decimal | None
    candidate_allocation: Decimal | None
    sector_allocation: Decimal | None
    evidence_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class GateInput:
    scorecard_id: str
    raw_decision_score: Decimal | None
    snapshot_id: str | None = None
    snapshot_as_of_timestamp: datetime | None = None
    comparison_score: Decimal | None = None
    expected_incremental_return: Decimal | None = None
    modeled_switching_friction: Decimal | None = None
    holding_entry_date: date | None = None
    atr_expansion: Decimal | None = None
    surveillance: SurveillanceObservation | None = None
    trade_plan: TradeManagementPlan | None = None
    exposure: PortfolioExposure | None = None
    earnings_scheduled_at: datetime | None = None
    earnings_schedule_verified_at: datetime | None = None
    evidence_ids: tuple[str, ...] = ()
    diagnostic_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class GateDecisionRecord:
    gate_id: str
    outcome: GateOutcome
    detail: str
    confidence: float | None
    evidence_ids: tuple[str, ...]
    parameters: Mapping[str, str]


@dataclass(frozen=True, slots=True)
class ExecutionGateEvaluation:
    id: str
    instrument_id: str
    strategy_version: object
    registry_version: str
    scoring_configuration_version: str
    gate_configuration_version: str
    scorecard_id: str
    input_snapshot_id: str | None
    action_context: ActionContext
    as_of_timestamp: datetime
    evaluated_at: datetime
    raw_decision_score: Decimal | None
    rotation_adjustment: Decimal | None
    comparison_score: Decimal | None
    decisions: tuple[GateDecisionRecord, ...]
    eligibility: ExecutionEligibility
    failed_gate_ids: tuple[str, ...]
    insufficient_gate_ids: tuple[str, ...]
    warnings: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    diagnostic_ids: tuple[str, ...]
    configuration_parameters: Mapping[str, str]


class ExecutionGateEngine:
    """Pure evaluator. An EXECUTABLE result is analytical permission only."""
    def __init__(self, config: ExecutionGateConfig, calendar: ExchangeCalendar):
        self.config, self.calendar = config, calendar

    def evaluate(self, *, instrument_id: str, strategy_version: object, registry_version: str,
                 scoring_configuration_version: str, action_context: ActionContext,
                 as_of_timestamp: datetime, evaluated_at: datetime, inputs: GateInput,
                 evidence_context: GateEvidenceContext | None = None,
                 candidate_score_evidence: GateScoreEvidence | None = None,
                 incumbent_score_evidence: GateScoreEvidence | None = None) -> ExecutionGateEvaluation:
        from app.gates.version_compatibility import require_gate_inputs, require_gate_source
        require_gate_source(strategy_version)
        require_gate_inputs(inputs, registry_version=registry_version, as_of=as_of_timestamp,
                            gate_policy_version=getattr(self.config, "version", None), evidence_context=evidence_context)
        if inputs.snapshot_as_of_timestamp != as_of_timestamp:
            raise ValueError("Gate inputs must be an approved as-of snapshot matching the requested evaluation time.")
        from app.gates.score_provenance import require_score_provenance
        from app.gates.version_compatibility import require_domain_provenance
        require_score_provenance(inputs, instrument_id=instrument_id, strategy_version=strategy_version,
                                 scoring_version=scoring_configuration_version, gate_version=self.config.version,
                                 as_of=as_of_timestamp, candidate=candidate_score_evidence,
                                 incumbent=incumbent_score_evidence)
        require_domain_provenance(inputs, evidence_context=evidence_context)
        unresolved = self.config.unresolved()
        decisions = (
            self._rotation(action_context, inputs, unresolved), self._velocity(action_context, as_of_timestamp, inputs, unresolved),
            self._surveillance(as_of_timestamp, inputs, unresolved), self._plan(inputs, unresolved),
            self._heat(inputs, unresolved), self._blackout(action_context, as_of_timestamp, inputs, unresolved),
        )
        failed = tuple(x.gate_id for x in decisions if x.outcome is GateOutcome.FAIL)
        insufficient = tuple(x.gate_id for x in decisions if x.outcome is GateOutcome.INSUFFICIENT_DATA)
        status = ExecutionEligibility.BLOCKED if failed else (ExecutionEligibility.INSUFFICIENT_DATA if insufficient else ExecutionEligibility.EXECUTABLE)
        adjustment = -self.config.velocity_penalty if decisions[1].detail.startswith("inactive") and self.config.velocity_penalty is not None else Decimal("0")
        comparison = inputs.raw_decision_score + adjustment if inputs.raw_decision_score is not None else None
        identifier = f"execution-gates-{instrument_id}-{inputs.scorecard_id}-{as_of_timestamp.isoformat()}"
        evidence = tuple(sorted(set(inputs.evidence_ids + tuple(e for d in decisions for e in d.evidence_ids))))
        warnings = tuple(sorted({f"UNRESOLVED_CONFIG:{x}" for x in unresolved} | {"NO_ACTION_OR_ORDER_CREATED"}))
        return ExecutionGateEvaluation(identifier, instrument_id, strategy_version, registry_version, scoring_configuration_version,
            self.config.version, inputs.scorecard_id, inputs.snapshot_id, action_context, as_of_timestamp, evaluated_at, inputs.raw_decision_score,
            adjustment, comparison, decisions, status, failed, insufficient, warnings, evidence, inputs.diagnostic_ids,
            {key: str(value) for key, value in asdict(self.config).items()})

    def _decision(self, gate: str, outcome: GateOutcome, detail: str, evidence: tuple[str, ...] = (), **parameters) -> GateDecisionRecord:
        return GateDecisionRecord(gate, outcome, detail, 1.0 if outcome is GateOutcome.PASS else None, evidence, {k: str(v) for k, v in parameters.items()})

    def _rotation(self, context, data, unresolved):
        if any(x in unresolved for x in ("min_score_advantage", "friction_model_version")):
            return self._decision("GATE_1_ROTATION", GateOutcome.INSUFFICIENT_DATA, "unresolved friction/advantage configuration")
        if context is not ActionContext.ROTATE_IN:
            return self._decision("GATE_1_ROTATION", GateOutcome.PASS, "not applicable: no holding is being replaced")
        if data.raw_decision_score is None or data.comparison_score is None:
            return self._decision("GATE_1_ROTATION", GateOutcome.INSUFFICIENT_DATA, "candidate or comparison holding score unavailable")
        advantage = data.raw_decision_score - data.comparison_score
        if advantage < self.config.min_score_advantage:
            return self._decision("GATE_1_ROTATION", GateOutcome.FAIL, "score advantage below configured hurdle", advantage=advantage)
        if self.config.require_economic_hurdle:
            if data.expected_incremental_return is None or data.modeled_switching_friction is None or self.config.net_economic_hurdle is None:
                return self._decision("GATE_1_ROTATION", GateOutcome.INSUFFICIENT_DATA, "economic friction inputs unavailable")
            if data.expected_incremental_return - data.modeled_switching_friction <= self.config.net_economic_hurdle:
                return self._decision("GATE_1_ROTATION", GateOutcome.FAIL, "net economic benefit does not exceed configured hurdle")
        return self._decision("GATE_1_ROTATION", GateOutcome.PASS, "configured rotation hurdles met", advantage=advantage)

    def _velocity(self, context, asof, data, unresolved):
        if any(x in unresolved for x in ("inactivity_sessions", "atr_expansion_threshold", "velocity_penalty")):
            return self._decision("GATE_2_VELOCITY", GateOutcome.INSUFFICIENT_DATA, "unresolved velocity configuration")
        if context not in {ActionContext.HOLD_EXISTING, ActionContext.REDUCE_EXISTING, ActionContext.EXIT_EXISTING, ActionContext.RISK_MANAGEMENT}:
            return self._decision("GATE_2_VELOCITY", GateOutcome.PASS, "not applicable: no existing holding history")
        if data.holding_entry_date is None or data.atr_expansion is None:
            return self._decision("GATE_2_VELOCITY", GateOutcome.INSUFFICIENT_DATA, "holding duration or ATR expansion unavailable")
        sessions = self.calendar.sessions_between(data.holding_entry_date, asof.date())
        if sessions >= self.config.inactivity_sessions and data.atr_expansion < self.config.atr_expansion_threshold:
            return self._decision("GATE_2_VELOCITY", GateOutcome.FAIL, "inactive holding; separate rotation adjustment recorded", sessions=sessions)
        return self._decision("GATE_2_VELOCITY", GateOutcome.PASS, "velocity threshold met", sessions=sessions)

    def _surveillance(self, asof, data, unresolved):
        if any(x in unresolved for x in ("disallowed_asm_stage", "disallow_gsm", "circuit_limit_threshold", "surveillance_max_age_days")):
            return self._decision("GATE_3_SURVEILLANCE", GateOutcome.INSUFFICIENT_DATA, "unresolved surveillance configuration")
        item = data.surveillance
        age = (
            self.calendar.sessions_between(item.effective_at.date(), asof.date())
            if item is not None and self.config.surveillance_freshness_basis == "trading_sessions"
            else (asof - item.effective_at).days if item is not None else None
        )
        if (item is None or not item.authoritative or item.effective_at > asof
                or age is None or age > self.config.surveillance_max_age_days):
            return self._decision("GATE_3_SURVEILLANCE", GateOutcome.INSUFFICIENT_DATA, "fresh authoritative surveillance observation unavailable")
        if item.asm_stage is None or item.gsm_stage is None or item.circuit_limit is None:
            return self._decision("GATE_3_SURVEILLANCE", GateOutcome.INSUFFICIENT_DATA, "surveillance fields incomplete", item.evidence_ids)
        if item.asm_stage >= self.config.disallowed_asm_stage or (self.config.disallow_gsm and item.gsm_stage > 0) or item.circuit_limit <= self.config.circuit_limit_threshold:
            return self._decision("GATE_3_SURVEILLANCE", GateOutcome.FAIL, "disqualifying ASM/GSM/circuit condition", item.evidence_ids)
        return self._decision("GATE_3_SURVEILLANCE", GateOutcome.PASS, "fresh authoritative surveillance clear", item.evidence_ids)

    def _plan(self, data, unresolved):
        if any(x in unresolved for x in ("initial_tranche", "t1_reduction", "require_breakeven_plan")):
            return self._decision("GATE_4_TRADE_PLAN", GateOutcome.INSUFFICIENT_DATA, "unresolved tranche configuration")
        plan = data.trade_plan
        if plan is None or not plan.stop_defined or not plan.t1_defined:
            return self._decision("GATE_4_TRADE_PLAN", GateOutcome.FAIL, "valid entry/stop/T1 plan unavailable")
        if plan.initial_tranche != self.config.initial_tranche or plan.t1_reduction != self.config.t1_reduction or (self.config.require_breakeven_plan and not plan.breakeven_conditions):
            return self._decision("GATE_4_TRADE_PLAN", GateOutcome.FAIL, "plan conflicts with approved tranche policy")
        return self._decision("GATE_4_TRADE_PLAN", GateOutcome.PASS, "analytical trade plan compatible")

    def _heat(self, data, unresolved):
        if any(x in unresolved for x in ("max_total_heat", "max_stock_allocation", "max_sector_allocation", "heat_methodology_version")):
            return self._decision("GATE_5_HEAT", GateOutcome.INSUFFICIENT_DATA, "unresolved exact heat/allocation configuration")
        value = data.exposure
        if value is None or value.portfolio_equity is None or value.portfolio_equity <= 0 or None in (value.existing_risk_amount, value.candidate_risk_amount, value.candidate_allocation, value.sector_allocation):
            return self._decision("GATE_5_HEAT", GateOutcome.INSUFFICIENT_DATA, "portfolio risk/allocation inputs unavailable")
        heat = (value.existing_risk_amount + value.candidate_risk_amount) / value.portfolio_equity
        if heat > self.config.max_total_heat or value.candidate_allocation > self.config.max_stock_allocation or value.sector_allocation > self.config.max_sector_allocation:
            return self._decision("GATE_5_HEAT", GateOutcome.FAIL, "projected heat or allocation cap exceeded", value.evidence_ids, heat=heat)
        return self._decision("GATE_5_HEAT", GateOutcome.PASS, "projected heat and allocation caps respected", value.evidence_ids, heat=heat)

    def _blackout(self, context, asof, data, unresolved):
        if context in {ActionContext.REDUCE_EXISTING, ActionContext.EXIT_EXISTING, ActionContext.RISK_MANAGEMENT, ActionContext.HOLD_EXISTING}:
            return self._decision("GATE_6_EARNINGS", GateOutcome.PASS, "blackout does not prohibit existing-position management")
        if "blackout_sessions" in unresolved:
            return self._decision("GATE_6_EARNINGS", GateOutcome.INSUFFICIENT_DATA, "unresolved blackout configuration")
        if data.earnings_scheduled_at is None or data.earnings_schedule_verified_at is None or data.earnings_schedule_verified_at > asof:
            return self._decision("GATE_6_EARNINGS", GateOutcome.INSUFFICIENT_DATA, "verified earnings schedule unavailable")
        sessions = self.calendar.sessions_between(asof.date(), data.earnings_scheduled_at.date())
        if data.earnings_scheduled_at >= asof and sessions <= self.config.blackout_sessions:
            return self._decision("GATE_6_EARNINGS", GateOutcome.FAIL, "within pre-earnings trading-session blackout", sessions=sessions)
        return self._decision("GATE_6_EARNINGS", GateOutcome.PASS, "outside configured earnings blackout", sessions=sessions)
