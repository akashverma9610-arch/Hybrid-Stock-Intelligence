"""Evidence completeness is separate from attractiveness and confidence."""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class EvidenceCoverageState(StrEnum):
    COMPLETE = "COMPLETE"
    SUFFICIENT = "SUFFICIENT"
    PARTIAL = "PARTIAL"
    INSUFFICIENT = "INSUFFICIENT"


class EvidenceDomain(StrEnum):
    PRICE_HISTORY = "price_history"
    CORPORATE_ACTIONS = "corporate_actions"
    FINANCIALS = "financials"
    OWNERSHIP = "ownership"
    NEWS = "news"
    HISTORICAL_MEMBERSHIP = "historical_membership"
    DELIVERY_LIQUIDITY = "delivery_liquidity"
    MARKET_CONTEXT = "market_context"
    SECTOR_CONTEXT = "sector_context"


@dataclass(frozen=True, slots=True)
class EvidenceCoverage:
    subject_id: str
    state: EvidenceCoverageState
    available_domains: tuple[EvidenceDomain, ...]
    required_domains: tuple[EvidenceDomain, ...]
    missing_domains: tuple[EvidenceDomain, ...]
    warnings: tuple[str, ...] = ()


class EvidenceCoverageService:
    def assess(self, *, subject_id: str, required_domains: tuple[EvidenceDomain, ...], available_domains: tuple[EvidenceDomain, ...]) -> EvidenceCoverage:
        required = tuple(dict.fromkeys(required_domains)); available = tuple(dict.fromkeys(available_domains))
        missing = tuple(item for item in required if item not in set(available))
        state = EvidenceCoverageState.COMPLETE if not missing else EvidenceCoverageState.INSUFFICIENT if not available else EvidenceCoverageState.SUFFICIENT if len(missing) == 1 else EvidenceCoverageState.PARTIAL
        warnings = ("EVIDENCE_INSUFFICIENT_NO_HIGH_CONFIDENCE_ACTION",) if state is EvidenceCoverageState.INSUFFICIENT else ("EVIDENCE_PARTIAL",) if missing else ()
        return EvidenceCoverage(subject_id, state, available, required, missing, warnings)

    @staticmethod
    def public_actionability(*, coverage: EvidenceCoverage, confidence: float | None, proposed_action: str) -> str:
        if coverage.state is EvidenceCoverageState.INSUFFICIENT:
            return "RESEARCH_INCOMPLETE"
        if confidence is None:
            return "RESEARCH_INCOMPLETE"
        return proposed_action
