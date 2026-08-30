"""Distilled fail-closed propagation across reconciliation and coverage facts."""
from __future__ import annotations

from dataclasses import dataclass

from app.data_quality.reconciliation import ReconciliationResult, ReconciliationStatus
from app.evidence_coverage import EvidenceCoverage, EvidenceCoverageService, EvidenceCoverageState
from app.reliability import ReliabilityStatus


@dataclass(frozen=True, slots=True)
class FailurePropagationDecision:
    reliability: ReliabilityStatus
    coverage: EvidenceCoverageState
    public_action: str
    warnings: tuple[str, ...]


class FailurePropagationService:
    """Does not calculate a score or mutate a gate; it only prevents false confidence."""
    def decide(self, *, reconciliation: ReconciliationResult | None, coverage: EvidenceCoverage, confidence: float | None, proposed_action: str) -> FailurePropagationDecision:
        if reconciliation is not None and reconciliation.status in {ReconciliationStatus.MATERIAL_CONFLICT, ReconciliationStatus.STALE, ReconciliationStatus.INCOMPLETE, ReconciliationStatus.UNVERIFIABLE}:
            return FailurePropagationDecision(ReliabilityStatus.DEGRADED, EvidenceCoverageState.PARTIAL if coverage.state is not EvidenceCoverageState.INSUFFICIENT else coverage.state, "DATA_UNRELIABLE", tuple((*reconciliation.conflicts, "RECONCILIATION_DOWNGRADES_EVIDENCE")))
        action = EvidenceCoverageService.public_actionability(coverage=coverage, confidence=confidence, proposed_action=proposed_action)
        return FailurePropagationDecision(ReliabilityStatus.READY, coverage.state, action, coverage.warnings)
