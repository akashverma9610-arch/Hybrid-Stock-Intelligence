from __future__ import annotations

from dataclasses import dataclass

from app.intelligence.sector_economics.service import ProfileProvenance, SensitivityDirection, SensitivityMagnitude, SectorEconomicImpact


@dataclass(frozen=True, slots=True)
class CompanySensitivity:
    driver: str
    direction_when_adverse: SensitivityDirection
    magnitude: SensitivityMagnitude
    pass_through: str | None
    lag: str | None
    confidence: float | None
    provenance: ProfileProvenance
    evidence_ids: tuple[str, ...]
    qualifiers: tuple[str, ...] = ()

@dataclass(frozen=True, slots=True)
class CompanySensitivityProfile:
    profile_id: str
    company_id: str
    sector: str
    version: str
    sensitivities: tuple[CompanySensitivity, ...]
    as_of: object
    warnings: tuple[str, ...] = ()

@dataclass(frozen=True, slots=True)
class MacroEarningsTransmission:
    transmission_id: str
    company_id: str
    sector_impact_ids: tuple[str, ...]
    profile_id: str
    revenue_impact: SensitivityDirection
    margin_impact: SensitivityDirection
    cash_flow_impact: SensitivityDirection
    balance_sheet_impact: SensitivityDirection
    strength: SensitivityMagnitude
    horizon: str | None
    confidence: float | None
    as_of: object
    evidence_ids: tuple[str, ...]
    warnings: tuple[str, ...] = ()

class MacroToEarningsTransmissionEngine:
    """Produces bounded directional context; never an EPS forecast or action."""
    def transmit(self, *, profile: CompanySensitivityProfile, sector_impacts: tuple[SectorEconomicImpact, ...]) -> tuple[MacroEarningsTransmission, ...]:
        own = {item.driver: item for item in profile.sensitivities}; results = []
        for impact in sector_impacts:
            sensitivity = own.get(impact.driver)
            if sensitivity is None:
                results.append(MacroEarningsTransmission("transmission:" + profile.profile_id + ":" + impact.driver, profile.company_id, (impact.impact_id,), profile.profile_id, SensitivityDirection.UNKNOWN, SensitivityDirection.UNKNOWN, SensitivityDirection.UNKNOWN, SensitivityDirection.UNKNOWN, SensitivityMagnitude.UNKNOWN, None, None, impact.as_of, impact.evidence_ids, ("COMPANY_SENSITIVITY_UNKNOWN_NO_SECTOR_FACT_SUBSTITUTION",)))
                continue
            direction = sensitivity.direction_when_adverse
            evidence = tuple(dict.fromkeys((*impact.evidence_ids, *sensitivity.evidence_ids)))
            results.append(MacroEarningsTransmission("transmission:" + profile.profile_id + ":" + impact.driver, profile.company_id, (impact.impact_id,), profile.profile_id, direction, direction, direction, direction, sensitivity.magnitude, sensitivity.lag, sensitivity.confidence, impact.as_of, evidence, sensitivity.qualifiers))
        return tuple(results)
