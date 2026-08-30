from __future__ import annotations

import hashlib
from datetime import datetime
from decimal import Decimal

from app.gates.engine import ExchangeCalendar
from .models import (
    EntryType, RevalidationInput, SignalConfig, SignalEventType, SignalLifecycleEvent,
    SignalRecord, SignalRequest, SignalStatus, SignalType, TradePlan, TriggerComparison,
    TriggerCondition, TriggerObservation,
)


class SignalOrchestrator:
    """Creates immutable analytical setups/events and deliberately has no order interface."""
    def __init__(self, config: SignalConfig, calendar: ExchangeCalendar): self.config, self.calendar = config, calendar

    def create(self, request: SignalRequest, generated_at: datetime) -> tuple[SignalRecord, SignalLifecycleEvent]:
        unresolved = self.config.unresolved(); status, warnings = self._initial_status(request, unresolved)
        identifier = "signal-" + hashlib.sha256(f"{request.instrument_id}|{request.signal_type.value}|{request.as_of_timestamp.isoformat()}".encode()).hexdigest()[:20]
        signal = SignalRecord(identifier, request.instrument_id, request.portfolio_id, request.strategy_version, request.registry_version,
            request.scoring_configuration_version, request.gate_configuration_version, request.rotation_configuration_version, request.as_of_timestamp,
            generated_at, request.signal_type, status, request.portfolio_snapshot_id, request.scorecard_id, request.gate_evaluation_id,
            request.rotation_evaluation_id, request.trade_plan.plan_id if request.trade_plan else None, request.diagnostic_ids, request.evidence_ids,
            request.data_confidence, self._signal_confidence(request), tuple(sorted(set(warnings + ["NO_ORDER_OR_PORTFOLIO_MUTATION_CREATED"]))),
            tuple(x for x in (request.scorecard_id, request.gate_evaluation_id, request.rotation_evaluation_id) if x))
        event = SignalLifecycleEvent(f"event-created-{identifier}", identifier, SignalEventType.SIGNAL_CREATED, generated_at, request.as_of_timestamp, status,
            "analytical setup created; no execution instruction exists", request.evidence_ids, request.diagnostic_ids, request.scorecard_id, request.gate_evaluation_id, request.rotation_evaluation_id)
        return signal, event

    def revalidate(self, signal: SignalRecord, plan: TradePlan | None, prior_events: tuple[SignalLifecycleEvent, ...], data: RevalidationInput, triggers: tuple[TriggerObservation, ...]) -> SignalLifecycleEvent | None:
        if data.as_of_timestamp < signal.as_of_timestamp or data.known_at > data.as_of_timestamp: raise ValueError("Revalidation must use an approved later as-of input.")
        if data.invalidation_triggered: return self._event(signal, SignalEventType.THESIS_INVALIDATED, SignalStatus.INVALIDATED, data, "exact thesis invalidation triggered")
        if data.catalyst_cancelled: return self._event(signal, SignalEventType.CANCELLED, SignalStatus.CANCELLED, data, "required catalyst cancelled")
        if data.gate_status != self.config.required_gate_status or data.earnings_blackout: return self._event(signal, SignalEventType.GATE_BLOCKED, SignalStatus.BLOCKED, data, "required execution gate status or earnings condition no longer holds")
        if data.score is not None and data.score < self.config.minimum_score: return self._event(signal, SignalEventType.REVALIDATED, SignalStatus.BLOCKED, data, "score no longer meets configured threshold")
        if signal.signal_type is SignalType.ROTATION_ENTRY_SETUP and self.config.require_rotation_for_rotation_entry and data.rotation_stance != "ROTATION_OPPORTUNITY": return self._event(signal, SignalEventType.REVALIDATED, SignalStatus.BLOCKED, data, "rotation context no longer permits setup")
        if self.calendar.sessions_between(signal.as_of_timestamp.date(), data.as_of_timestamp.date()) > self.config.expiry_sessions: return self._event(signal, SignalEventType.EXPIRED, SignalStatus.EXPIRED, data, "configured trading-session expiry reached")
        satisfied = any(self._trigger_matches(condition, observation, data.as_of_timestamp) for condition in (plan.trigger_conditions if plan else ()) for observation in triggers)
        if satisfied: return self._event(signal, SignalEventType.TRIGGER_CONDITION_MET, SignalStatus.TRIGGERED_ANALYTICALLY, data, "configured machine-testable trigger condition met")
        return self._event(signal, SignalEventType.REVALIDATED, SignalStatus.WAITING_FOR_TRIGGER, data, "setup remains analytical and awaits trigger")

    def _initial_status(self, request, unresolved):
        warnings = [f"UNRESOLVED_CONFIG:{x}" for x in unresolved]
        if request.signal_type in {SignalType.CASH_SETUP, SignalType.WAIT_SETUP}: return SignalStatus.WAITING_FOR_TRIGGER, warnings
        if unresolved: return SignalStatus.INSUFFICIENT_DATA, warnings
        if request.invalidation_triggered: return SignalStatus.INVALIDATED, warnings
        if request.raw_decision_score is None or request.score_status != "COMPLETE" or request.data_confidence is None: return SignalStatus.INSUFFICIENT_DATA, warnings
        if request.gate_status != self.config.required_gate_status: return SignalStatus.BLOCKED, warnings
        if request.raw_decision_score < self.config.minimum_score or request.data_confidence < self.config.minimum_confidence: return SignalStatus.BLOCKED, warnings
        if request.signal_type is SignalType.ROTATION_ENTRY_SETUP and self.config.require_rotation_for_rotation_entry and request.rotation_stance != "ROTATION_OPPORTUNITY": return SignalStatus.BLOCKED, warnings
        plan = request.trade_plan
        if plan is None or not plan.complete_entry_plan: return SignalStatus.INSUFFICIENT_DATA, warnings
        if plan.entry_type not in self.config.allowed_entry_types or plan.risk_reward_t1 is None or plan.risk_reward_t1 < self.config.minimum_risk_reward: return SignalStatus.BLOCKED, warnings
        if request.setup_confirmations < self.config.minimum_setup_confirmations: return SignalStatus.WAITING_FOR_TRIGGER, warnings + ["SETUP_PERSISTENCE_PENDING"]
        return SignalStatus.WAITING_FOR_TRIGGER, warnings

    @staticmethod
    def _signal_confidence(request):
        fields = (request.scorecard_id, request.raw_decision_score, request.data_confidence, request.gate_evaluation_id, request.trade_plan)
        return sum(x is not None for x in fields) / len(fields)

    def _trigger_matches(self, condition, observation, asof):
        if observation.observed_at > asof or observation.known_at > asof or observation.timeframe != condition.timeframe: return False
        if condition.confirmation_required and not observation.confirmed: return False
        if condition.comparison is TriggerComparison.ABOVE: return condition.threshold is not None and observation.price > condition.threshold
        if condition.comparison is TriggerComparison.BELOW: return condition.threshold is not None and observation.price < condition.threshold
        return condition.zone_low is not None and condition.zone_high is not None and condition.zone_low <= observation.price <= condition.zone_high

    @staticmethod
    def _event(signal, kind, status, data, reason):
        return SignalLifecycleEvent(f"event-{kind.value.lower()}-{signal.signal_id}-{data.as_of_timestamp.isoformat()}", signal.signal_id, kind, data.as_of_timestamp, data.as_of_timestamp, status, reason,
            data.evidence_ids, signal.diagnostic_ids, signal.decision_scorecard_id, signal.execution_gate_evaluation_id, signal.portfolio_rotation_evaluation_id)
