"""PIT-constrained fundamental inflection candidate discovery only."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP

from app.intelligence.company_sensitivity.service import MacroEarningsTransmission
from app.intelligence.sector_economics.service import SensitivityDirection
from app.strategies.common.models import CandidateStatus, SetupQuality, StrategyCandidate, StrategyFamily


@dataclass(frozen=True, slots=True)
class InflectionConfig:
    version: str = "inflection-v1"
    market_cap_min_crore: Decimal = Decimal("1000")
    market_cap_max_crore: Decimal = Decimal("25000")
    roce_min_pct: Decimal = Decimal("15")
    debt_equity_max: Decimal = Decimal("0.8")
    gross_block_yoy_min_pct: Decimal = Decimal("15")
    opm_expansion_min_bps: Decimal = Decimal("200")
    combined_fii_dii_min_pp: Decimal = Decimal("1.0")


@dataclass(frozen=True, slots=True)
class InflectionInput:
    candidate_id: str
    instrument_id: str
    sector: str
    scan_as_of: datetime
    universe_snapshot_id: str
    evidence_ids: tuple[str, ...]
    market_cap_crore: Decimal | None
    roce_pct: Decimal | None
    debt_equity: Decimal | None
    gross_block_current: Decimal | None
    gross_block_prior_year: Decimal | None
    opm_current_pct: Decimal | None
    opm_prior_year_pct: Decimal | None
    fii_current_pct: Decimal | None
    fii_prior_two_quarters_pct: Decimal | None
    dii_current_pct: Decimal | None
    dii_prior_two_quarters_pct: Decimal | None
    promoter_pledge_current_pct: Decimal | None
    promoter_pledge_prior_pct: Decimal | None
    theme_evidence_ids: tuple[str, ...]
    company_transmissions: tuple[MacroEarningsTransmission, ...] = ()
    catalyst_evidence_ids: tuple[str, ...] = ()
    integrity_warnings: tuple[str, ...] = ()


class InflectionEngine:
    def evaluate(self, value: InflectionInput, *, config: InflectionConfig) -> StrategyCandidate:
        gross = _growth(value.gross_block_current, value.gross_block_prior_year)
        opm_bps = _bps(value.opm_current_pct, value.opm_prior_year_pct)
        ownership_pp = _ownership_pp(value)
        pledge = _pledge(value.promoter_pledge_current_pct, value.promoter_pledge_prior_pct)
        checks: list[tuple[str, bool | None]] = [
            ("MARKET_CAP", None if value.market_cap_crore is None else config.market_cap_min_crore <= value.market_cap_crore <= config.market_cap_max_crore),
            ("ROCE", None if value.roce_pct is None else value.roce_pct > config.roce_min_pct),
            ("DEBT_EQUITY", None if value.debt_equity is None else value.debt_equity < config.debt_equity_max),
            ("GROSS_BLOCK_YOY", None if gross is None else gross > config.gross_block_yoy_min_pct),
            ("OPM_EXPANSION", None if opm_bps is None else opm_bps >= config.opm_expansion_min_bps),
            ("FII_DII_PP", None if ownership_pp is None else ownership_pp >= config.combined_fii_dii_min_pp),
            ("PROMOTER_PLEDGE", pledge),
            ("DYNAMIC_THEME", bool(value.theme_evidence_ids)),
            ("COMPANY_SENSITIVITY", _company_sensitivity_ok(value.company_transmissions)),
        ]
        evaluated = tuple(name for name, result in checks if result is not None)
        passed = tuple(name for name, result in checks if result is True)
        quality = SetupQuality("setup-quality:" + value.candidate_id, StrategyFamily.INFLECTION, config.version,
                               _quality(passed, evaluated), evaluated, passed, value.evidence_ids,
                               tuple(name + "_UNAVAILABLE" for name, result in checks if result is None))
        warnings = list(value.integrity_warnings) + list(quality.warnings)
        if any(result is False for _, result in checks):
            return _candidate(value, config, CandidateStatus.INELIGIBLE, quality, warnings + [name + "_FILTER_FAILED" for name, result in checks if result is False])
        if any(result is None for _, result in checks):
            return _candidate(value, config, CandidateStatus.RESEARCH_INCOMPLETE, quality, warnings + ["FUNDAMENTAL_INFLECTION_PARTIAL"])
        return _candidate(value, config, CandidateStatus.CANDIDATE_GENERATED, quality, warnings)


def _candidate(value: InflectionInput, config: InflectionConfig, status: CandidateStatus, quality: SetupQuality, warnings: list[str]) -> StrategyCandidate:
    transmission_ids = tuple(item.transmission_id for item in value.company_transmissions)
    return StrategyCandidate(value.candidate_id, StrategyFamily.INFLECTION, config.version, value.instrument_id, value.sector,
                             value.scan_as_of, value.universe_snapshot_id, status, quality, value.evidence_ids,
                             ("FUNDAMENTALS", "OWNERSHIP", "MACRO_SECTOR", "COMPANY_SENSITIVITY", "CATALYSTS", "MARKET_INTEGRITY"), "6_TO_18_MONTHS",
                             None, None, None, None, tuple(dict.fromkeys((*value.theme_evidence_ids, *transmission_ids))),
                             value.catalyst_evidence_ids, tuple(sorted(set(warnings))))


def _growth(current: Decimal | None, prior: Decimal | None) -> Decimal | None:
    if current is None or prior is None or prior <= 0:
        return None
    return Decimal("100") * (current / prior - Decimal("1"))


def _bps(current: Decimal | None, prior: Decimal | None) -> Decimal | None:
    return None if current is None or prior is None else (current - prior) * Decimal("100")


def _ownership_pp(value: InflectionInput) -> Decimal | None:
    required = (value.fii_current_pct, value.fii_prior_two_quarters_pct, value.dii_current_pct, value.dii_prior_two_quarters_pct)
    return None if any(item is None for item in required) else (value.fii_current_pct + value.dii_current_pct) - (value.fii_prior_two_quarters_pct + value.dii_prior_two_quarters_pct)  # type: ignore[operator]


def _pledge(current: Decimal | None, prior: Decimal | None) -> bool | None:
    if current is None:
        return None
    return current == 0 or (prior is not None and current <= prior)


def _company_sensitivity_ok(values: tuple[MacroEarningsTransmission, ...]) -> bool | None:
    if not values:
        return None
    directions = tuple(item.margin_impact for item in values)
    if any(item is SensitivityDirection.NEGATIVE for item in directions):
        return False
    return any(item is SensitivityDirection.POSITIVE for item in directions)


def _quality(passed: tuple[str, ...], evaluated: tuple[str, ...]) -> Decimal:
    if not evaluated:
        return Decimal("0")
    return (Decimal("100") * Decimal(len(passed)) / Decimal(len(evaluated))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
