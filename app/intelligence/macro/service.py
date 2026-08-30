"""Point-in-time macro state composition from supplied canonical evidence only."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum


class RatesState(StrEnum): EASING="EASING"; NEUTRAL="NEUTRAL"; TIGHTENING="TIGHTENING"
class LiquidityState(StrEnum): SURPLUS="SURPLUS"; BALANCED="BALANCED"; DEFICIT="DEFICIT"
class InflationState(StrEnum): COOLING="COOLING"; STABLE="STABLE"; ACCELERATING="ACCELERATING"
class GrowthState(StrEnum): CONTRACTING="CONTRACTING"; SLOWING="SLOWING"; EXPANDING="EXPANDING"; OVERHEATING="OVERHEATING"
class FiscalImpulseState(StrEnum): NEGATIVE="NEGATIVE"; NEUTRAL="NEUTRAL"; POSITIVE="POSITIVE"
class InrState(StrEnum): STRENGTHENING="STRENGTHENING"; STABLE="STABLE"; WEAKENING="WEAKENING"
class FlowState(StrEnum): STRONG_OUTFLOW="STRONG_OUTFLOW"; OUTFLOW="OUTFLOW"; NEUTRAL="NEUTRAL"; INFLOW="INFLOW"; STRONG_INFLOW="STRONG_INFLOW"
class IntelligenceSourceTier(StrEnum): OFFICIAL="OFFICIAL"; PRIMARY="PRIMARY"; CREDIBLE="CREDIBLE"; SECONDARY="SECONDARY"; COMMENTARY="COMMENTARY"
class MacroObservationFrequency(StrEnum): DAILY="DAILY"; WEEKLY="WEEKLY"; MONTHLY="MONTHLY"; QUARTERLY="QUARTERLY"; EVENT="EVENT"
class MacroInputFamily(StrEnum):
    MONETARY_RATES="MONETARY_RATES"; INFLATION="INFLATION"; GROWTH_FISCAL="GROWTH_FISCAL"; FX_EXTERNAL="FX_EXTERNAL"; FLOWS="FLOWS"; CREDIT_CYCLE="CREDIT_CYCLE"; RURAL="RURAL"; POWER="POWER"; GLOBAL="GLOBAL"; EARNINGS_REVISION_BREADTH="EARNINGS_REVISION_BREADTH"; INVENTORY_CYCLE="INVENTORY_CYCLE"; CAPACITY_CYCLE="CAPACITY_CYCLE"; CREDIT_RATING_MIGRATION="CREDIT_RATING_MIGRATION"; POLICY_IMPLEMENTATION_GAP="POLICY_IMPLEMENTATION_GAP"

@dataclass(frozen=True, slots=True)
class MacroEvidence:
    evidence_id: str
    family: MacroInputFamily
    component: str
    state: str
    source_tier: IntelligenceSourceTier
    source_reference: str
    observed_at: datetime | None
    published_at: datetime | None
    available_at: datetime
    effective_at: datetime | None
    reliability: float | None
    freshness: str
    revision_of: str | None = None
    warnings: tuple[str, ...] = ()
    # Raw source facts remain separate from the existing descriptive MacroState
    # vocabulary.  A source adapter must not infer a directional state merely
    # to make its evidence consumable.
    value: Decimal | None = None
    unit: str | None = None
    frequency: MacroObservationFrequency | None = None
    source_artifact_fingerprint: str | None = None
    received_at: datetime | None = None

    def eligible_as_of(self, as_of: datetime) -> bool:
        return self.available_at <= as_of and (self.published_at is None or self.published_at <= as_of) and (self.effective_at is None or self.effective_at <= as_of)

@dataclass(frozen=True, slots=True)
class MacroState:
    state_id: str
    as_of: datetime
    rates: RatesState | None
    liquidity: LiquidityState | None
    inflation: InflationState | None
    growth: GrowthState | None
    fiscal_impulse: FiscalImpulseState | None
    inr: InrState | None
    fii_flow: FlowState | None
    commodity_regimes: tuple[tuple[str, str], ...]
    evidence_ids: tuple[str, ...]
    confidence: float | None
    warnings: tuple[str, ...]
    version: str = "macro-state-v1"

@dataclass(frozen=True, slots=True)
class EconomicRegime:
    regime_id: str
    macro_state_id: str
    label: str
    component_states: tuple[tuple[str, str | None], ...]
    as_of: datetime
    evidence_ids: tuple[str, ...]
    confidence: float | None
    warnings: tuple[str, ...]
    version: str = "economic-regime-v1"


class MacroStateService:
    _COMPONENTS = {"rates": RatesState, "liquidity": LiquidityState, "inflation": InflationState, "growth": GrowthState, "fiscal_impulse": FiscalImpulseState, "inr": InrState, "fii_flow": FlowState}
    def build(self, *, state_id: str, evidence: tuple[MacroEvidence, ...], as_of: datetime) -> MacroState:
        eligible = tuple(item for item in evidence if item.eligible_as_of(as_of))
        warnings = ["MACRO_EVIDENCE_EXCLUDED_AS_OF" for item in evidence if item not in eligible]
        values: dict[str, object | None] = {key: None for key in self._COMPONENTS}; ids = []
        for component, enum in self._COMPONENTS.items():
            found = tuple(item for item in eligible if item.component == component)
            states = {item.state for item in found}
            if len(states) > 1: warnings.append("MACRO_SOURCE_CONFLICT:" + component)
            elif found:
                try: values[component] = enum(found[0].state); ids.extend(item.evidence_id for item in found)
                except ValueError: warnings.append("MACRO_STATE_UNRECOGNIZED:" + component)
        commodities = tuple(sorted((item.component.removeprefix("commodity:"), item.state) for item in eligible if item.component.startswith("commodity:")))
        ids.extend(item.evidence_id for item in eligible if item.component.startswith("commodity:"))
        reliable = tuple(item.reliability for item in eligible if item.reliability is not None)
        return MacroState(state_id, as_of, values["rates"], values["liquidity"], values["inflation"], values["growth"], values["fiscal_impulse"], values["inr"], values["fii_flow"], commodities, tuple(dict.fromkeys(ids)), sum(reliable)/len(reliable) if reliable else None, tuple(sorted(set(warnings))))

    def describe(self, *, regime_id: str, state: MacroState) -> EconomicRegime:
        components = tuple((name, getattr(state, name).value if getattr(state, name) is not None else None) for name in self._COMPONENTS)
        known = tuple(value for _, value in components if value is not None)
        label = "MACRO_CONTEXT_INCOMPLETE" if not known else " / ".join(known)
        return EconomicRegime(regime_id, state.state_id, label, components, state.as_of, state.evidence_ids, state.confidence, state.warnings)
