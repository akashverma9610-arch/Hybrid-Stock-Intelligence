"""Analytical execution-eligibility gates; this package never creates orders."""

from .engine import (
    ActionContext, ExecutionEligibility, ExecutionGateConfig, ExecutionGateEngine,
    ExecutionGateEvaluation, GateInput, GateOutcome, ExchangeCalendar,
)

__all__ = ["ActionContext", "ExecutionEligibility", "ExecutionGateConfig", "ExecutionGateEngine", "ExecutionGateEvaluation", "GateInput", "GateOutcome", "ExchangeCalendar"]
