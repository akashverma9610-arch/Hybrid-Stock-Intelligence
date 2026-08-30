"""Controlled, registry-driven NSE equity opportunity orchestration.

This package assembles stored point-in-time evidence and invokes existing
diagnostic, score, gate, and rotation components.  It never fetches providers,
changes strategy governance, or executes trades.
"""

from .models import (
    DiagnosticCompleteness,
    NseEquityInstrument,
    UniverseAnalysisJob,
    UniverseAnalysisJobStatus, UniverseAnalysisStage, UniverseAnalysisItem, UniverseSnapshot, AnalyzedUniverseCandidate,
    PortfolioUniverseRotationSnapshot, OpportunityCoverageStatus,
    CoverageDomain, CoverageDomainStatus, CoverageDomainRecord, UniverseInstrumentCoverage,
    UniverseEligibility,
    UniverseEligibilityStatus,
    UniverseOpportunitySnapshot,
    ProviderInstrumentMappingRecord, ProviderMappingStatus,
)
from .requirements import DIAGNOSTIC_INPUT_REQUIREMENTS
from .service import Canonical61DiagnosticRunner, StockDiagnosticInputAssembler, UniverseAnalysisService
from .importer import OfficialNseUniverseImporter, UniverseImportReport

__all__ = (
    "Canonical61DiagnosticRunner", "DIAGNOSTIC_INPUT_REQUIREMENTS", "DiagnosticCompleteness",
    "NseEquityInstrument", "StockDiagnosticInputAssembler", "UniverseAnalysisJob",
    "UniverseAnalysisJobStatus", "UniverseAnalysisStage", "UniverseAnalysisItem", "UniverseSnapshot", "AnalyzedUniverseCandidate",
    "PortfolioUniverseRotationSnapshot", "OpportunityCoverageStatus", "UniverseAnalysisService", "UniverseEligibility",
    "CoverageDomain", "CoverageDomainStatus", "CoverageDomainRecord", "UniverseInstrumentCoverage",
    "UniverseEligibilityStatus", "UniverseOpportunitySnapshot",
    "ProviderInstrumentMappingRecord", "ProviderMappingStatus",
    "OfficialNseUniverseImporter", "UniverseImportReport",
)
