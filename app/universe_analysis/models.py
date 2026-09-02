from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class UniverseEligibilityStatus(StrEnum):
    ELIGIBLE = "ELIGIBLE"
    INSUFFICIENT_HISTORY = "INSUFFICIENT_HISTORY"
    MISSING_INSTRUMENT_MAPPING = "MISSING_INSTRUMENT_MAPPING"
    UNSUPPORTED_SECURITY_TYPE = "UNSUPPORTED_SECURITY_TYPE"
    NOT_LISTED_OR_TRADABLE = "NOT_LISTED_OR_TRADABLE"
    NO_CURRENT_DATA = "NO_CURRENT_DATA"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


class DiagnosticCompleteness(StrEnum):
    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"
    UNAVAILABLE = "UNAVAILABLE"


class UniverseAnalysisJobStatus(StrEnum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"


class UniverseAnalysisStage(StrEnum):
    """Durable, public-safe progression for a stored-data universe scan."""

    UNIVERSE_READY = "UNIVERSE_READY"
    COVERAGE_PREFLIGHT = "COVERAGE_PREFLIGHT"
    ELIGIBILITY_COMPLETE = "ELIGIBILITY_COMPLETE"
    ANALYZING = "ANALYZING"
    CANDIDATES_MATERIALIZED = "CANDIDATES_MATERIALIZED"
    ROTATION_COMPARISON = "ROTATION_COMPARISON"
    COMPLETED = "COMPLETED"


class CoverageDomain(StrEnum):
    CURRENT_QUOTES = "CURRENT_QUOTES"
    HISTORICAL = "HISTORICAL"
    FUNDAMENTALS = "FUNDAMENTALS"
    FILINGS = "FILINGS"
    NEWS = "NEWS"
    OWNERSHIP = "OWNERSHIP"
    MARKET_CONTEXT = "MARKET_CONTEXT"
    SECTOR_CONTEXT = "SECTOR_CONTEXT"


class CoverageDomainStatus(StrEnum):
    READY = "READY"
    PARTIAL = "PARTIAL"
    MISSING = "MISSING"
    UNAVAILABLE = "UNAVAILABLE"
    STALE = "STALE"


class OpportunityCoverageStatus(StrEnum):
    FULL = "FULL"
    PARTIAL = "PARTIAL"
    UNAVAILABLE = "UNAVAILABLE"


@dataclass(frozen=True, slots=True)
class NseEquityInstrument:
    """Canonical stored/imported NSE equity identity; no provider is implied."""

    instrument_id: str
    symbol: str
    isin: str | None
    sector: str | None
    industry: str | None
    listing_status: str
    listing_date: datetime | None
    tradable: bool | None
    data_as_of: datetime
    source: str
    provenance_reference: str | None = None
    security_type: str = "EQUITY"
    company_name: str | None = None
    exchange: str = "NSE"
    main_board: bool | None = None


@dataclass(frozen=True, slots=True)
class UniverseEligibility:
    instrument_id: str
    symbol: str
    status: UniverseEligibilityStatus
    reason: str
    data_as_of: datetime
    observation_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class DiagnosticInputRequirement:
    diagnostic_id: int
    domain: str
    required_evidence: tuple[str, ...]
    optional_evidence: tuple[str, ...]
    minimum_lookback: int | None
    market_dependency: bool
    sector_dependency: bool
    fundamental_dependency: bool
    technical_dependency: bool
    research_dependency: bool
    filings_dependency: bool
    primary_market_dependency: bool
    ownership_dependency: bool
    liquidity_dependency: bool
    crisis_extremes_dependency: bool


@dataclass(frozen=True, slots=True)
class UniverseAnalysisJob:
    job_id: str
    revision: int
    status: UniverseAnalysisJobStatus
    requested_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    universe_id: str
    universe_as_of: datetime
    as_of: datetime
    cursor: int
    batch_size: int
    eligible_total: int
    processed: int
    complete_count: int
    partial_count: int
    unavailable_count: int
    failed_count: int
    warnings: tuple[str, ...] = ()
    universe_snapshot_id: str | None = None
    stage: UniverseAnalysisStage = UniverseAnalysisStage.UNIVERSE_READY
    coverage_ready_count: int = 0
    coverage_partial_count: int = 0
    coverage_missing_count: int = 0


@dataclass(frozen=True, slots=True)
class UniverseSnapshot:
    snapshot_id: str
    as_of: datetime
    source: str
    total_records: int
    eligible_security_count: int
    excluded_count: int
    warnings: tuple[str, ...]
    version: str
    checksum: str
    instrument_ids: tuple[str, ...]


class ProviderMappingStatus(StrEnum):
    """Lifecycle status for an immutable provider-instrument mapping record."""

    ACTIVE = "ACTIVE"
    RETIRED = "RETIRED"


@dataclass(frozen=True, slots=True)
class ProviderInstrumentMappingRecord:
    """Versioned internal provider-token mapping for one canonical instrument.

    This is provider-routing metadata, not a public analytical fact.  The
    provider reference is intentionally retained only in durable storage so a
    later quote request can use the exact mapping without rediscovering the
    provider master.
    """

    mapping_id: str
    canonical_instrument_id: str
    provider: str
    provider_exchange_segment: str
    provider_instrument_reference: str
    provider_symbol: str | None
    isin: str | None
    status: ProviderMappingStatus
    effective_as_of: datetime
    source_reference: str | None = None
    source_checksum: str | None = None
    mapping_version: str = "v1"
    # Optional provider-master metadata is evidence accompanying the exact
    # routing token.  Keeping it on the immutable mapping means a later
    # provider-master download cannot silently alter the historical record.
    provider_instrument_type: str | None = None
    provider_name: str | None = None
    raw_provider_exchange: str | None = None
    raw_provider_segment: str | None = None
    raw_provider_instrument: str | None = None
    raw_provider_instrument_type: str | None = None
    raw_provider_series: str | None = None
    normalized_instrument: str | None = None

    def __post_init__(self) -> None:
        if not all((self.mapping_id, self.canonical_instrument_id, self.provider,
                    self.provider_exchange_segment, self.provider_instrument_reference,
                    self.mapping_version)):
            raise ValueError("Provider instrument mapping fields are required.")
        if self.effective_as_of.tzinfo is None:
            raise ValueError("Provider mapping effective_as_of must be timezone-aware.")


@dataclass(frozen=True, slots=True)
class UniverseAnalysisItem:
    job_id: str
    instrument_id: str
    symbol: str
    eligibility: UniverseEligibilityStatus
    completeness: DiagnosticCompleteness
    stock_snapshot_id: str | None
    opportunity: "UniverseOpportunity | None"
    warnings: tuple[str, ...] = ()
    candidate: "AnalyzedUniverseCandidate | None" = None


@dataclass(frozen=True, slots=True)
class CoverageDomainRecord:
    domain: CoverageDomain
    status: CoverageDomainStatus
    data_as_of: datetime | None
    freshness: str
    warning: str | None = None


@dataclass(frozen=True, slots=True)
class UniverseInstrumentCoverage:
    """Readiness metadata only; it is deliberately not a stock score."""

    coverage_id: str
    universe_snapshot_id: str | None
    job_id: str
    instrument_id: str
    as_of: datetime
    domains: tuple[CoverageDomainRecord, ...]
    warnings: tuple[str, ...] = ()

    @property
    def complete(self) -> bool:
        return bool(self.domains) and all(item.status is CoverageDomainStatus.READY for item in self.domains)


@dataclass(frozen=True, slots=True)
class UniverseOpportunity:
    symbol: str
    sector: str | None
    score: object | None
    confidence: float | None
    risk_reward: str | None
    execution_status: str
    candidate_status: str
    catalyst_summary: str | None
    freshness: str
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class UniverseOpportunitySnapshot:
    snapshot_id: str
    job_id: str
    as_of: datetime
    universe_count: int
    eligible_count: int
    analyzed_count: int
    complete_count: int
    partial_count: int
    unavailable_count: int
    qualified_candidate_count: int
    opportunities: tuple[UniverseOpportunity, ...]
    warnings: tuple[str, ...]
    freshness: str
    universe_snapshot_id: str | None = None
    coverage_status: OpportunityCoverageStatus = OpportunityCoverageStatus.UNAVAILABLE


@dataclass(frozen=True, slots=True)
class AnalyzedUniverseCandidate:
    candidate_id: str
    job_id: str
    universe_snapshot_id: str
    instrument_id: str
    symbol: str
    analysis_snapshot_id: str
    scorecard_id: str | None
    decision_score: object | None
    confidence: float | None
    risk_reward: object | None
    execution_eligibility: str | None
    sector: str | None
    catalyst_context: str | None
    freshness: str
    qualification_status: str
    as_of: datetime
    warnings: tuple[str, ...] = ()
    sector_supportive: bool | None = None
    entry_valid: bool | None = None
    stop_valid: bool | None = None
    invalidation_valid: bool | None = None
    portfolio_constraints_ok: bool | None = None
    confirmation_count: int = 0


@dataclass(frozen=True, slots=True)
class PortfolioUniverseRotationSnapshot:
    snapshot_id: str
    generated_at: datetime
    data_as_of: datetime
    portfolio_snapshot_id: str
    universe_snapshot_id: str
    coverage_status: OpportunityCoverageStatus
    universe_total: int
    eligible_total: int
    analyzed_complete: int
    analyzed_partial: int
    qualified_candidates: int
    holdings_compared: int
    rotation_evaluation_id: str | None
    warnings: tuple[str, ...]
