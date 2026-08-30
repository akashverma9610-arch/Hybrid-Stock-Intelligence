"""Research/paper execution realism; it does not submit, modify, or cancel orders."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum


class ExecutionFeasibilityStatus(StrEnum):
    EXECUTABLE = "EXECUTABLE"
    SETUP_VALID_EXECUTION_REJECTED = "SETUP_VALID_EXECUTION_REJECTED"
    RESEARCH_REQUIRED = "RESEARCH_REQUIRED"


@dataclass(frozen=True, slots=True)
class ExecutionSimulationConfig:
    version: str
    brokerage: Decimal
    stt: Decimal
    exchange_charges: Decimal
    gst: Decimal
    stamp_duty: Decimal
    slippage: Decimal
    impact_cost: Decimal

    @property
    def total_cost_rate(self) -> Decimal:
        return sum((self.brokerage, self.stt, self.exchange_charges, self.gst, self.stamp_duty, self.slippage, self.impact_cost), Decimal("0"))


@dataclass(frozen=True, slots=True)
class ExecutionSimulation:
    gross_pnl: Decimal
    transaction_cost: Decimal
    slippage_cost: Decimal
    impact_cost: Decimal
    net_pnl: Decimal
    requested_quantity: Decimal
    filled_quantity: Decimal
    status: str
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ExecutionFeasibility:
    status: ExecutionFeasibilityStatus
    expected_spread: Decimal | None
    expected_slippage: Decimal | None
    position_to_adv: Decimal | None
    circuit_risk: bool | None
    fill_fraction: Decimal | None
    warnings: tuple[str, ...] = ()


class ExecutionSimulationService:
    def simulate(self, *, entry_price: Decimal, exit_price: Decimal, requested_quantity: Decimal, fill_fraction: Decimal, config: ExecutionSimulationConfig) -> ExecutionSimulation:
        if entry_price <= 0 or exit_price <= 0 or requested_quantity <= 0 or not Decimal("0") <= fill_fraction <= Decimal("1"):
            raise ValueError("Execution simulation inputs are invalid.")
        filled = requested_quantity * fill_fraction
        gross = (exit_price - entry_price) * filled
        notional = (entry_price + exit_price) * filled
        friction = notional * config.total_cost_rate
        slippage = notional * config.slippage
        impact = notional * config.impact_cost
        status = "FAILED_FILL" if filled == 0 else "PARTIAL_FILL" if filled < requested_quantity else "FILLED"
        return ExecutionSimulation(gross, friction, slippage, impact, gross - friction, requested_quantity, filled, status, ("PARTIAL_FILL_RETAINS_REDUCED_EXPOSURE",) if status == "PARTIAL_FILL" else ())


class ExecutionFeasibilityService:
    def assess(self, *, expected_spread: Decimal | None, expected_slippage: Decimal | None, position_value: Decimal | None, average_daily_value: Decimal | None, circuit_risk: bool | None, fill_fraction: Decimal | None) -> ExecutionFeasibility:
        if None in (expected_spread, expected_slippage, position_value, average_daily_value, circuit_risk, fill_fraction):
            return ExecutionFeasibility(ExecutionFeasibilityStatus.RESEARCH_REQUIRED, expected_spread, expected_slippage, None, circuit_risk, fill_fraction, ("EXECUTION_INPUT_NOT_CONFIGURED",))
        ratio = position_value / average_daily_value if average_daily_value and average_daily_value > 0 else None
        if ratio is None or circuit_risk or fill_fraction <= 0:
            return ExecutionFeasibility(ExecutionFeasibilityStatus.SETUP_VALID_EXECUTION_REJECTED, expected_spread, expected_slippage, ratio, circuit_risk, fill_fraction, ("EXECUTION_NOT_FEASIBLE",))
        return ExecutionFeasibility(ExecutionFeasibilityStatus.EXECUTABLE, expected_spread, expected_slippage, ratio, circuit_risk, fill_fraction)
