"""Private machine-readable input inventory for the canonical diagnostic registry."""
from __future__ import annotations

from app.registry.canonical import DIAGNOSTIC_RULES
from .models import DiagnosticInputRequirement


def _domain(rule_id: int) -> str:
    if rule_id == 1:
        return "MARKET"
    if rule_id in {2, 3}:
        return "SECTOR"
    if rule_id in {4, 5, 10, 37, 38, 40, 41, 42, 43, 44, 45, 46}:
        return "PRICE_STRUCTURE"
    if rule_id in {6}:
        return "RELATIVE_STRENGTH"
    if rule_id in {7, 8, 9, 50, 51, 52, 53, 54, 58}:
        return "SMART_MONEY_PROXY"
    if rule_id in {11, 35, 36, 39}:
        return "VOLUME_FLOW"
    if rule_id in {12, 13, 14, 59}:
        return "MTF"
    if 15 <= rule_id <= 30:
        return "FUNDAMENTALS" if rule_id not in {21, 22, 23, 28, 30} else "GOVERNANCE"
    if 31 <= rule_id <= 34:
        return "RISK_REWARD"
    return "RESEARCH" if rule_id in {47, 48, 49, 55, 56, 57, 60, 61} else "DATA_QUALITY"


def _requirement(rule_id: int) -> DiagnosticInputRequirement:
    domain = _domain(rule_id)
    technical = domain in {"MARKET", "SECTOR", "PRICE_STRUCTURE", "RELATIVE_STRENGTH", "SMART_MONEY_PROXY", "VOLUME_FLOW", "MTF"}
    fundamentals = 15 <= rule_id <= 30 or rule_id in {31, 33, 34}
    research = rule_id in {15, 23, 28, 30, 47, 48, 49, 55, 56, 57, 60, 61}
    liquidity = rule_id in {7, 8, 9, 11, 35, 36, 50, 51, 52, 53, 54, 58}
    sector = rule_id in {2, 3, 6, 31}
    market = technical or rule_id in {31, 34, 55, 56, 57}
    return DiagnosticInputRequirement(
        diagnostic_id=rule_id, domain=domain,
        required_evidence=("validated as-of snapshot",) + (("validated market observations",) if market else ("validated filings or disclosures",)),
        optional_evidence=("corroborating evidence", "approved provider metadata"),
        minimum_lookback=3 if technical else None,
        market_dependency=market, sector_dependency=sector, fundamental_dependency=fundamentals,
        technical_dependency=technical, research_dependency=research, filings_dependency=fundamentals or research,
        primary_market_dependency=False, ownership_dependency=rule_id in {21, 22},
        liquidity_dependency=liquidity, crisis_extremes_dependency=rule_id in {1, 31, 34},
    )


# Derived from the canonical registry: an import-time mismatch prevents a new
# registry definition from silently escaping the orchestration requirements.
DIAGNOSTIC_INPUT_REQUIREMENTS = tuple(_requirement(rule.rule_id) for rule in DIAGNOSTIC_RULES)
assert tuple(item.diagnostic_id for item in DIAGNOSTIC_INPUT_REQUIREMENTS) == tuple(rule.rule_id for rule in DIAGNOSTIC_RULES)
