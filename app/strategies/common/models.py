"""Shared immutable contracts for strategy setup discovery.

They deliberately contain no final-decision vocabulary.  A candidate is a
research handoff, not a trade instruction.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum


class CandidateStatus(StrEnum):
    CANDIDATE_GENERATED = "CANDIDATE_GENERATED"
    PARTIAL = "PARTIAL"
    RESEARCH_INCOMPLETE = "RESEARCH_INCOMPLETE"
    SETUP_REJECTED = "SETUP_REJECTED"
    SETUP_VALID_EXECUTION_REJECTED = "SETUP_VALID_EXECUTION_REJECTED"
    INELIGIBLE = "INELIGIBLE"


class StrategyFamily(StrEnum):
    PRE_BREAKOUT = "PRE_BREAKOUT"
    INFLECTION = "INFLECTION"


@dataclass(frozen=True, slots=True)
class SetupQuality:
    """Fit to one setup only; not Decision Score, confidence, or an action."""

    quality_id: str
    strategy_family: StrategyFamily
    config_version: str
    value: Decimal
    evaluated_components: tuple[str, ...]
    passed_components: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not Decimal("0") <= self.value <= Decimal("100"):
            raise ValueError("Setup quality must be between zero and one hundred.")


@dataclass(frozen=True, slots=True)
class StrategyCandidate:
    candidate_id: str
    strategy_family: StrategyFamily
    strategy_config_version: str
    instrument_id: str
    sector: str | None
    scan_as_of: datetime
    universe_snapshot_id: str
    status: CandidateStatus
    setup_quality: SetupQuality
    evidence_ids: tuple[str, ...]
    evidence_coverage: tuple[str, ...]
    horizon: str
    trigger: Decimal | None = None
    structural_stop: Decimal | None = None
    realistic_target: Decimal | None = None
    reward_risk: Decimal | None = None
    sector_or_theme_evidence_ids: tuple[str, ...] = ()
    catalyst_evidence_ids: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class StrategyOutcomeAttribution:
    """Separate research attribution contracts; no pooled strategy performance."""

    attribution_id: str
    strategy_family: StrategyFamily
    strategy_config_version: str
    candidate_id: str
    outcome_reference_id: str
    benchmark_reference_id: str | None
    measured_fields: tuple[str, ...]
    created_at: datetime
    warnings: tuple[str, ...] = ()
