"""Named source gaps, not authority grants or new canonical producers.

The legacy exception message remains stable. The additive classification
separates a missing producer from a version/provenance defect. Constructing a
descriptor or exception cannot admit evidence; only the existing independently
configured gate authorities can do that.
"""
from dataclasses import dataclass
from enum import StrEnum

from app.gates.version_compatibility import GateVersionBlocked


VERSION = "six-gates-source-readiness/v1"


class SourceReadiness(StrEnum):
    READY_EXISTING_CANONICAL_PRODUCER = "READY_EXISTING_CANONICAL_PRODUCER"
    READY_AFTER_NARROW_ADAPTER = "READY_AFTER_NARROW_ADAPTER"
    CONTRACT_EXISTS_DATA_ABSENT = "CONTRACT_EXISTS_DATA_ABSENT"
    SOURCE_AVAILABLE_ADAPTER_MISSING = "SOURCE_AVAILABLE_ADAPTER_MISSING"
    SOURCE_GOVERNANCE_REQUIRED = "SOURCE_GOVERNANCE_REQUIRED"
    SOURCE_NOT_IMPLEMENTED = "SOURCE_NOT_IMPLEMENTED"
    POLICY_NOT_APPROVED = "POLICY_NOT_APPROVED"
    NOT_APPLICABLE = "NOT_APPLICABLE"


@dataclass(frozen=True, slots=True)
class GateSourceGap:
    input_field: str
    gate_id: str
    state: SourceReadiness
    blocker: str
    future_slice: str


# Exact eight neutral inputs from the accepted Repair 2 matrix. Existing
# score and stored holding-date adapters are deliberately not listed as gaps.
SOURCE_GAPS = (
    GateSourceGap("expected_incremental_return", "GATE_1_ROTATION",
        SourceReadiness.SOURCE_GOVERNANCE_REQUIRED, "GATE1_FRICTION_POLICY_AUTHORITY_NOT_READY",
        "GATE1_FRICTION_POLICY_AUTHORITY_V1"),
    GateSourceGap("modeled_switching_friction", "GATE_1_ROTATION",
        SourceReadiness.SOURCE_GOVERNANCE_REQUIRED, "GATE1_FRICTION_POLICY_AUTHORITY_NOT_READY",
        "GATE1_FRICTION_POLICY_AUTHORITY_V1"),
    GateSourceGap("atr_expansion", "GATE_2_VELOCITY",
        SourceReadiness.SOURCE_GOVERNANCE_REQUIRED, "GATE2_ATR_AUTHORITY_NOT_READY",
        "GATE2_ATR_EXPANSION_SOURCE_GOVERNANCE_V1"),
    GateSourceGap("surveillance", "GATE_3_SURVEILLANCE",
        SourceReadiness.SOURCE_NOT_IMPLEMENTED, "GATE3_SURVEILLANCE_SOURCE_AUTHORITY_NOT_READY",
        "GATE3_SURVEILLANCE_SOURCE_AUTHORITY_V1"),
    GateSourceGap("trade_plan", "GATE_4_TRADE_PLAN",
        SourceReadiness.SOURCE_GOVERNANCE_REQUIRED, "GATE4_TRADE_PLAN_AUTHORITY_NOT_READY",
        "TRADE_PLAN_AUTHORITY_CONTRACT_V1"),
    GateSourceGap("exposure", "GATE_5_HEAT",
        SourceReadiness.SOURCE_GOVERNANCE_REQUIRED, "GATE5_RISK_ALLOCATION_AUTHORITY_NOT_READY",
        "PORTFOLIO_RISK_SCENARIO_AUTHORITY_V1"),
    GateSourceGap("earnings_scheduled_at", "GATE_6_EARNINGS",
        SourceReadiness.SOURCE_AVAILABLE_ADAPTER_MISSING, "EARNINGS_CALENDAR_AUTHORITY_NOT_READY",
        "EARNINGS_CALENDAR_SOURCE_GOVERNANCE_V1"),
    GateSourceGap("earnings_schedule_verified_at", "GATE_6_EARNINGS",
        SourceReadiness.SOURCE_AVAILABLE_ADAPTER_MISSING, "EARNINGS_CALENDAR_AUTHORITY_NOT_READY",
        "EARNINGS_CALENDAR_SOURCE_GOVERNANCE_V1"),
)


def source_gap(input_field: str) -> GateSourceGap | None:
    return next((item for item in SOURCE_GAPS if item.input_field == input_field), None)


class GateSourceNotReady(GateVersionBlocked):
    """Backward-compatible rejection with an exact, non-secret source gap."""

    def __init__(self, legacy_message: str, *, input_field: str):
        super().__init__(legacy_message)
        gap = source_gap(input_field)
        if gap is None:
            raise ValueError("GATE_SOURCE_GAP_UNKNOWN")
        self.source_gap = gap
