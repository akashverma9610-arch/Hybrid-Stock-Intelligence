from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from app.intelligence.macro.service import MacroState


class SensitivityDirection(StrEnum): POSITIVE="POSITIVE"; NEGATIVE="NEGATIVE"; MIXED="MIXED"; NEUTRAL="NEUTRAL"; UNKNOWN="UNKNOWN"
class SensitivityMagnitude(StrEnum): LOW="LOW"; MODERATE="MODERATE"; HIGH="HIGH"; UNKNOWN="UNKNOWN"
class ProfileProvenance(StrEnum): SOURCE_DERIVED="SOURCE_DERIVED"; RULE_DERIVED="RULE_DERIVED"; MANUALLY_REVIEWED="MANUALLY_REVIEWED"; UNKNOWN="UNKNOWN"

@dataclass(frozen=True, slots=True)
class SectorSensitivity:
    driver: str
    direction_when_adverse: SensitivityDirection
    magnitude: SensitivityMagnitude
    lag: str | None
    confidence: float | None
    evidence_ids: tuple[str, ...]
    conditions: tuple[str, ...] = ()

@dataclass(frozen=True, slots=True)
class SectorSensitivityProfile:
    profile_id: str
    sector: str
    version: str
    sensitivities: tuple[SectorSensitivity, ...]
    provenance: ProfileProvenance
    as_of: object
    warnings: tuple[str, ...] = ()

@dataclass(frozen=True, slots=True)
class SectorEconomicImpact:
    impact_id: str
    sector: str
    driver: str
    macro_state: str
    direction: SensitivityDirection
    impact_strength: SensitivityMagnitude
    time_horizon: str | None
    transmission_path: str
    confidence: float | None
    as_of: object
    evidence_ids: tuple[str, ...]
    warnings: tuple[str, ...] = ()

class SectorTransmissionService:
    def transmit(self, *, macro: MacroState, profile: SectorSensitivityProfile) -> tuple[SectorEconomicImpact, ...]:
        output = []
        for sensitivity in profile.sensitivities:
            value = _macro_value(macro, sensitivity.driver)
            if value is None:
                output.append(SectorEconomicImpact("sector-impact:" + profile.profile_id + ":" + sensitivity.driver, profile.sector, sensitivity.driver, "UNKNOWN", SensitivityDirection.UNKNOWN, SensitivityMagnitude.UNKNOWN, sensitivity.lag, "MACRO_INPUT_UNAVAILABLE", sensitivity.confidence, macro.as_of, sensitivity.evidence_ids, ("MACRO_DRIVER_MISSING",)))
            else:
                output.append(SectorEconomicImpact("sector-impact:" + profile.profile_id + ":" + sensitivity.driver, profile.sector, sensitivity.driver, value, sensitivity.direction_when_adverse, sensitivity.magnitude, sensitivity.lag, f"{sensitivity.driver}:{value}→{profile.sector}", sensitivity.confidence, macro.as_of, tuple(dict.fromkeys((*macro.evidence_ids, *sensitivity.evidence_ids))), sensitivity.conditions))
        return tuple(output)

def _macro_value(macro, driver):
    value = getattr(macro, driver, None)
    return value.value if value is not None else dict(macro.commodity_regimes).get(driver)
