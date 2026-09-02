"""Immutable, human-approved production policy for the existing Six Gates.

The module defines policy and provider-neutral input contracts only.  It never
fetches surveillance or earnings data and never evaluates a gate or places an
order.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from app.gates.engine import ExchangeCalendar, ExecutionGateConfig, ExecutionGateEngine
from app.historical.guard import manifest_fingerprint


POLICY_ID = "six-gates-production-v1"
FRICTION_MODEL_VERSION = "nse-cash-delivery-friction-v1"


@dataclass(frozen=True, slots=True)
class OfficialSourceContract:
    contract_id: str
    authority: str
    coverage: tuple[str, ...]
    latest_eligible_completed_session_required: bool
    absence_is_pass: bool


@dataclass(frozen=True, slots=True)
class SetupDependencyContract:
    contract_id: str
    required_fields: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class GatePitContract:
    contract_id: str = "six-gates-pit-v1"

    def validate(
        self,
        *,
        decision_score_as_of: datetime,
        portfolio_snapshot_as_of: datetime | None,
        setup_as_of: datetime | None,
        surveillance_as_of: datetime | None,
        earnings_verified_as_of: datetime | None,
        friction_policy_effective_at: datetime,
        execution_gate_as_of: datetime,
    ) -> None:
        values = (decision_score_as_of, friction_policy_effective_at, execution_gate_as_of)
        if any(not _aware(item) for item in values):
            raise ValueError("SIX_GATES_PIT_TIMESTAMP_REQUIRED")
        if decision_score_as_of > execution_gate_as_of or friction_policy_effective_at > execution_gate_as_of:
            raise ValueError("SIX_GATES_PIT_LOOKAHEAD_REJECTED")
        for item in (portfolio_snapshot_as_of, setup_as_of, surveillance_as_of, earnings_verified_as_of):
            if item is not None and (not _aware(item) or item > execution_gate_as_of):
                raise ValueError("SIX_GATES_PIT_LOOKAHEAD_REJECTED")


@dataclass(frozen=True, slots=True)
class NseCashDeliveryFrictionModel:
    """Effective-dated official charges plus explicit user-specific inputs."""

    model_id: str
    version: str
    effective_at: datetime
    stt_purchase_rate: Decimal
    stt_sale_rate: Decimal
    sebi_turnover_rate_each_side: Decimal
    stamp_duty_purchase_rate: Decimal
    gst_rate: Decimal
    nse_member_outflow_per_crore_each_side: Decimal
    official_source_references: tuple[str, ...]
    fingerprint: str

    def verify_integrity(self) -> None:
        if self.model_id != FRICTION_MODEL_VERSION or self.version != "v1" or not _aware(self.effective_at):
            raise ValueError("NSE_CASH_DELIVERY_FRICTION_MODEL_IDENTITY_INVALID")
        if any(item < 0 for item in (
            self.stt_purchase_rate, self.stt_sale_rate, self.sebi_turnover_rate_each_side,
            self.stamp_duty_purchase_rate, self.gst_rate, self.nse_member_outflow_per_crore_each_side,
        )):
            raise ValueError("NSE_CASH_DELIVERY_FRICTION_MODEL_VALUE_INVALID")
        if self.fingerprint != friction_model_fingerprint(self):
            raise ValueError("NSE_CASH_DELIVERY_FRICTION_MODEL_FINGERPRINT_MISMATCH")

    def modeled_switching_friction(
        self,
        *,
        purchase_turnover: Decimal,
        sale_turnover: Decimal,
        brokerage: Decimal | None,
        slippage: Decimal | None,
        capital_gains_tax: Decimal | None,
        gst_taxable_services: Decimal | None,
    ) -> Decimal | None:
        """Return no value until all user-specific costs are explicit."""
        self.verify_integrity()
        if any(item is None for item in (brokerage, slippage, capital_gains_tax, gst_taxable_services)):
            return None
        if any(item < 0 for item in (purchase_turnover, sale_turnover, brokerage, slippage, capital_gains_tax, gst_taxable_services)):
            raise ValueError("NSE_CASH_DELIVERY_FRICTION_INPUT_INVALID")
        nse_outflow = (purchase_turnover + sale_turnover) * self.nse_member_outflow_per_crore_each_side / Decimal("10000000")
        statutory = (
            purchase_turnover * (self.stt_purchase_rate + self.sebi_turnover_rate_each_side + self.stamp_duty_purchase_rate)
            + sale_turnover * (self.stt_sale_rate + self.sebi_turnover_rate_each_side)
            + nse_outflow
        )
        return statutory + brokerage + slippage + capital_gains_tax + (gst_taxable_services * self.gst_rate)


@dataclass(frozen=True, slots=True)
class SixGatesProductionPolicy:
    approval_id: str
    policy_id: str
    version: str
    reviewer_authority: str
    approved_at: datetime
    effective_at: datetime
    gate_config: ExecutionGateConfig
    friction_model: NseCashDeliveryFrictionModel
    surveillance_source: OfficialSourceContract
    earnings_source: OfficialSourceContract
    setup_contract: SetupDependencyContract
    pit_contract: GatePitContract
    fingerprint: str

    def verify_integrity(self) -> None:
        if (self.policy_id != POLICY_ID or self.version != "v1" or self.reviewer_authority != "HUMAN_APPROVED"
                or not _aware(self.approved_at) or not _aware(self.effective_at) or self.effective_at < self.approved_at):
            raise ValueError("SIX_GATES_PRODUCTION_POLICY_APPROVAL_INVALID")
        if self.gate_config.version != POLICY_ID or self.gate_config.unresolved():
            raise ValueError("SIX_GATES_PRODUCTION_POLICY_UNRESOLVED_CONFIGURATION")
        self.friction_model.verify_integrity()
        if self.friction_model.version != "v1" or self.friction_model.effective_at > self.effective_at:
            raise ValueError("SIX_GATES_PRODUCTION_POLICY_FRICTION_LINEAGE_INVALID")
        if self.fingerprint != six_gates_production_policy_fingerprint(self):
            raise ValueError("SIX_GATES_PRODUCTION_POLICY_FINGERPRINT_MISMATCH")


def approved_six_gates_production_policy(
    *, approved_at: datetime, effective_at: datetime | None = None,
) -> SixGatesProductionPolicy:
    """Materialize exactly the human-approved V1 values from this task."""
    effective = effective_at or approved_at
    if not _aware(approved_at) or not _aware(effective):
        raise ValueError("SIX_GATES_PRODUCTION_POLICY_TIMESTAMP_REQUIRED")
    friction = _friction_model()
    initial = SixGatesProductionPolicy(
        approval_id="six-gates-production-v1:human-approved",
        policy_id=POLICY_ID,
        version="v1",
        reviewer_authority="HUMAN_APPROVED",
        approved_at=approved_at,
        effective_at=effective,
        gate_config=ExecutionGateConfig(
            POLICY_ID, Decimal("1.00"), FRICTION_MODEL_VERSION, Decimal("0.00"), True,
            12, Decimal("1.0"), Decimal("-0.50"), 2, True, Decimal("0.05"), 4,
            Decimal("0.50"), Decimal("0.50"), True, Decimal("0.06"), Decimal("0.25"),
            Decimal("0.35"), 5, "portfolio-structural-risk-heat-v1", "trading_sessions",
        ),
        friction_model=friction,
        surveillance_source=OfficialSourceContract(
            "official-nse-surveillance-v1", "NSE", ("ASM", "GSM", "PRICE_BAND", "SECURITY_STATUS"), True, False,
        ),
        earnings_source=OfficialSourceContract(
            "official-nse-earnings-calendar-v1", "NSE", ("BOARD_MEETING", "FINANCIAL_RESULTS"), True, False,
        ),
        setup_contract=SetupDependencyContract(
            "six-gates-setup-dependency-v1",
            ("setup_identity_version", "entry_trigger_or_zone", "structural_stop_invalidation", "t1", "additional_targets", "risk_reward", "setup_horizon", "tranche_compatibility", "breakeven_profit_protection_conditions", "setup_as_of", "evidence_lineage"),
        ),
        pit_contract=GatePitContract(),
        fingerprint="",
    )
    return SixGatesProductionPolicy(**{**_fields(initial), "fingerprint": six_gates_production_policy_fingerprint(initial)})


def _friction_model() -> NseCashDeliveryFrictionModel:
    initial = NseCashDeliveryFrictionModel(
        model_id=FRICTION_MODEL_VERSION, version="v1", effective_at=datetime(2026, 3, 1, tzinfo=UTC),
        stt_purchase_rate=Decimal("0.001"), stt_sale_rate=Decimal("0.001"),
        sebi_turnover_rate_each_side=Decimal("0.000001"), stamp_duty_purchase_rate=Decimal("0.00015"),
        gst_rate=Decimal("0.18"), nse_member_outflow_per_crore_each_side=Decimal("307"),
        official_source_references=(
            "Official NSE cash-market exchange/member outflow effective 2026-03-01",
            "Official SEBI turnover-fee schedule", "Official statutory STT and stamp-duty schedule", "Official GST schedule",
        ), fingerprint="",
    )
    return NseCashDeliveryFrictionModel(**{**_fields(initial), "fingerprint": friction_model_fingerprint(initial)})


def friction_model_fingerprint(value: NseCashDeliveryFrictionModel) -> str:
    return manifest_fingerprint(**_serializable(value, omit=("fingerprint",)))


def six_gates_production_policy_fingerprint(value: SixGatesProductionPolicy) -> str:
    return manifest_fingerprint(**_serializable(value, omit=("fingerprint",)))


def policy_to_dict(value: SixGatesProductionPolicy) -> dict[str, Any]:
    value.verify_integrity()
    return _serializable(value)


def policy_from_dict(value: dict[str, Any]) -> SixGatesProductionPolicy:
    friction = NseCashDeliveryFrictionModel(
        **{**value["friction_model"], "effective_at": datetime.fromisoformat(value["friction_model"]["effective_at"]),
           "official_source_references": tuple(value["friction_model"]["official_source_references"]),
           **{name: Decimal(value["friction_model"][name]) for name in _FRICTION_DECIMALS}},
    )
    config = ExecutionGateConfig(
        **{**value["gate_config"], **{name: Decimal(value["gate_config"][name]) if value["gate_config"][name] is not None else None for name in _CONFIG_DECIMALS}},
    )
    item = SixGatesProductionPolicy(
        approval_id=value["approval_id"], policy_id=value["policy_id"], version=value["version"],
        reviewer_authority=value["reviewer_authority"], approved_at=datetime.fromisoformat(value["approved_at"]),
        effective_at=datetime.fromisoformat(value["effective_at"]), gate_config=config, friction_model=friction,
        surveillance_source=OfficialSourceContract(
            **{**value["surveillance_source"], "coverage": tuple(value["surveillance_source"]["coverage"])},
        ),
        earnings_source=OfficialSourceContract(
            **{**value["earnings_source"], "coverage": tuple(value["earnings_source"]["coverage"])},
        ),
        setup_contract=SetupDependencyContract(
            **{**value["setup_contract"], "required_fields": tuple(value["setup_contract"]["required_fields"])},
        ), pit_contract=GatePitContract(**value["pit_contract"]),
        fingerprint=value["fingerprint"],
    )
    item.verify_integrity()
    return item


def selected_production_gate_engine(*, repository, calendar: ExchangeCalendar, as_of: datetime) -> ExecutionGateEngine:
    """Select only an effective immutable production policy, never the fallback."""
    if not _aware(as_of):
        raise ValueError("SIX_GATES_PRODUCTION_POLICY_TIMESTAMP_REQUIRED")
    policy = repository.selected_six_gates_production_policy(as_of=as_of)
    if policy is None:
        raise ValueError("SIX_GATES_PRODUCTION_POLICY_NOT_SELECTED")
    policy.verify_integrity()
    return ExecutionGateEngine(policy.gate_config, calendar)


_CONFIG_DECIMALS = (
    "min_score_advantage", "net_economic_hurdle", "atr_expansion_threshold", "velocity_penalty",
    "circuit_limit_threshold", "initial_tranche", "t1_reduction", "max_total_heat",
    "max_stock_allocation", "max_sector_allocation",
)
_FRICTION_DECIMALS = (
    "stt_purchase_rate", "stt_sale_rate", "sebi_turnover_rate_each_side", "stamp_duty_purchase_rate",
    "gst_rate", "nse_member_outflow_per_crore_each_side",
)


def _serializable(value: object, *, omit: tuple[str, ...] = ()) -> dict[str, Any]:
    def convert(item):
        if isinstance(item, datetime): return item.isoformat()
        if isinstance(item, Decimal): return str(item)
        if hasattr(item, "__dataclass_fields__"):
            return {name: convert(getattr(item, name)) for name in item.__dataclass_fields__ if name not in omit}
        if isinstance(item, tuple): return [convert(part) for part in item]
        return item
    return convert(value)


def _fields(value: object) -> dict[str, Any]:
    return {name: getattr(value, name) for name in value.__dataclass_fields__}


def _aware(value: datetime) -> bool:
    return value.tzinfo is not None and value.utcoffset() is not None


__all__ = (
    "FRICTION_MODEL_VERSION", "POLICY_ID", "GatePitContract", "NseCashDeliveryFrictionModel",
    "OfficialSourceContract", "SetupDependencyContract", "SixGatesProductionPolicy",
    "approved_six_gates_production_policy", "friction_model_fingerprint", "policy_from_dict",
    "policy_to_dict", "selected_production_gate_engine", "six_gates_production_policy_fingerprint",
)
