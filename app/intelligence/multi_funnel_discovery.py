"""Canonical, read-only Multi-Funnel Discovery foundation.

This module deliberately records discovery *recall* provenance only.  It does
not inspect a market universe, invoke a source funnel, union leads, judge a
security, create a setup, calculate a score, or access portfolio/execution
state.  Adapters and candidate-union materialization are separate slices.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum

from app.historical.guard import manifest_fingerprint


MULTI_FUNNEL_DISCOVERY_CONTRACT = "multi-funnel-discovery/v1"
MULTI_FUNNEL_DISCOVERY_REGISTRY_ID = "hsi-multi-funnel-discovery-registry"
MULTI_FUNNEL_DISCOVERY_REGISTRY_VERSION = "v1"
_ID = re.compile(r"[A-Za-z0-9._:-]+\Z")
_FP = re.compile(r"(?:sha256:)?[0-9a-f]{64}\Z")


class MultiFunnelDiscoveryError(ValueError):
    """Stable fail-closed error for malformed discovery contracts."""


class DiscoveryFunnelId(StrEnum):
    MOMENTUM = "MOMENTUM"
    PRE_BREAKOUT = "PRE_BREAKOUT"
    FUNDAMENTAL_INFLECTION = "FUNDAMENTAL_INFLECTION"
    COMPOUNDER = "COMPOUNDER"
    EMERGING_COMPOUNDER = "EMERGING_COMPOUNDER"
    EARNINGS_ACCELERATION = "EARNINGS_ACCELERATION"
    ORDERBOOK_CAPEX = "ORDERBOOK_CAPEX"
    SECTOR_ROTATION = "SECTOR_ROTATION"
    NEWS_CATALYST = "NEWS_CATALYST"
    POLICY_TRANSMISSION = "POLICY_TRANSMISSION"
    VALUATION_RECOVERY = "VALUATION_RECOVERY"
    MARKET_DISLOCATION = "MARKET_DISLOCATION"
    HOLDING_STATE_CHANGE = "HOLDING_STATE_CHANGE"
    WATCHLIST_STATE_CHANGE = "WATCHLIST_STATE_CHANGE"


class DiscoveryFunnelStatus(StrEnum):
    OPERATIONAL = "OPERATIONAL"
    PARTIAL = "PARTIAL"
    RESEARCH_SHADOW = "RESEARCH_SHADOW"
    CONTRACT_ONLY = "CONTRACT_ONLY"
    DATA_BLOCKED = "DATA_BLOCKED"
    POLICY_BLOCKED = "POLICY_BLOCKED"
    NOT_IMPLEMENTED = "NOT_IMPLEMENTED"


class DiscoverySourceLayer(StrEnum):
    FACT = "FACT"
    DATA = "DATA"
    INTERPRETATION = "INTERPRETATION"
    INFERENCE = "INFERENCE"


class DiscoveryHorizon(StrEnum):
    POSITIONAL = "POSITIONAL"
    LONG_TERM = "LONG_TERM"


class DiscoveryLeadReadiness(StrEnum):
    READY_FOR_INSPECTION = "READY_FOR_INSPECTION"
    RESEARCH_INSPECTION = "RESEARCH_INSPECTION"
    DATA_PARTIAL = "DATA_PARTIAL"


class DiscoveryDataQualityState(StrEnum):
    VERIFIED = "VERIFIED"
    PARTIAL = "PARTIAL"
    CONFLICTED = "CONFLICTED"


class DiscoveryReferenceKind(StrEnum):
    OBSERVATION = "OBSERVATION"
    EVIDENCE = "EVIDENCE"
    RECEIPT = "RECEIPT"
    ARTIFACT = "ARTIFACT"


class DiscoveryTriggerCode(StrEnum):
    GOVERNED_PREBREAKOUT_SETUP_AVAILABLE = "GOVERNED_PREBREAKOUT_SETUP_AVAILABLE"
    RELATIVE_STRENGTH_WATCH_STATE = "RELATIVE_STRENGTH_WATCH_STATE"
    EARNINGS_ACCELERATION_OBSERVED = "EARNINGS_ACCELERATION_OBSERVED"
    COMPOUNDER_PROSPECTIVE_OBSERVATION_AVAILABLE = "COMPOUNDER_PROSPECTIVE_OBSERVATION_AVAILABLE"
    INFLECTION_ACCOUNTING_OBSERVATION_AVAILABLE = "INFLECTION_ACCOUNTING_OBSERVATION_AVAILABLE"
    ORDER_BOOK_ACCELERATION_OBSERVED = "ORDER_BOOK_ACCELERATION_OBSERVED"
    SECTOR_ROTATION_STATE = "SECTOR_ROTATION_STATE"
    CATALYST_WATCH_EVIDENCE = "CATALYST_WATCH_EVIDENCE"
    POLICY_TRANSMISSION_RESEARCH_OBSERVATION = "POLICY_TRANSMISSION_RESEARCH_OBSERVATION"
    MARKET_REGIME_DISLOCATION_OBSERVED = "MARKET_REGIME_DISLOCATION_OBSERVED"
    HOLDING_INTELLIGENCE_STATE_CHANGE = "HOLDING_INTELLIGENCE_STATE_CHANGE"
    WATCHLIST_STATE_CHANGE = "WATCHLIST_STATE_CHANGE"


class DiscoveryCoverageState(StrEnum):
    LEADS_EMITTED = "LEADS_EMITTED"
    EVALUATED_NO_LEADS = "EVALUATED_NO_LEADS"
    NOT_EVALUATED = "NOT_EVALUATED"
    POLICY_BLOCKED = "POLICY_BLOCKED"
    DATA_BLOCKED = "DATA_BLOCKED"


@dataclass(frozen=True, slots=True)
class DiscoveryLineageReference:
    reference_id: str
    reference_fingerprint: str
    kind: DiscoveryReferenceKind
    known_at: datetime

    def __post_init__(self) -> None:
        _require_id(self.reference_id, "MULTI_FUNNEL_DISCOVERY_LINEAGE_ID_INVALID")
        _require_fp(self.reference_fingerprint, "MULTI_FUNNEL_DISCOVERY_LINEAGE_FINGERPRINT_INVALID")
        if not isinstance(self.kind, DiscoveryReferenceKind):
            raise MultiFunnelDiscoveryError("MULTI_FUNNEL_DISCOVERY_LINEAGE_KIND_INVALID")
        object.__setattr__(self, "known_at", _timestamp(self.known_at, "MULTI_FUNNEL_DISCOVERY_LINEAGE_KNOWN_AT_INVALID"))


@dataclass(frozen=True, slots=True)
class CanonicalDiscoveryLead:
    """An inspection lead, never a candidate qualification or an action."""

    canonical_instrument_id: str
    funnel_id: DiscoveryFunnelId
    funnel_version: str
    discovery_as_of: datetime
    source_layer: DiscoverySourceLayer
    trigger_codes: tuple[DiscoveryTriggerCode, ...]
    readiness: DiscoveryLeadReadiness
    data_quality: DiscoveryDataQualityState
    lineage: tuple[DiscoveryLineageReference, ...]
    intended_horizons: tuple[DiscoveryHorizon, ...] = ()
    issuer_id: str | None = None
    parent_discovery_id: str | None = None
    blocker_codes: tuple[str, ...] = ()
    contract_version: str = MULTI_FUNNEL_DISCOVERY_CONTRACT
    lead_id: str = field(init=False)
    fingerprint: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "discovery_as_of", _timestamp(self.discovery_as_of, "MULTI_FUNNEL_DISCOVERY_AS_OF_INVALID"))
        object.__setattr__(self, "trigger_codes", _enum_tuple(self.trigger_codes, DiscoveryTriggerCode, "MULTI_FUNNEL_DISCOVERY_TRIGGER_CODES_INVALID"))
        object.__setattr__(self, "intended_horizons", _enum_tuple(self.intended_horizons, DiscoveryHorizon, "MULTI_FUNNEL_DISCOVERY_HORIZONS_INVALID"))
        object.__setattr__(self, "lineage", _canonical_lineage(self.lineage))
        object.__setattr__(self, "blocker_codes", _codes(self.blocker_codes, "MULTI_FUNNEL_DISCOVERY_BLOCKERS_INVALID"))
        _validate_lead(self)
        object.__setattr__(self, "lead_id", "discovery-lead:" + manifest_fingerprint(**_lead_identity(self))[:32])
        object.__setattr__(self, "fingerprint", manifest_fingerprint(**_lead_payload(self)))

    def verify(self) -> None:
        _validate_lead(self)
        if self.lead_id != "discovery-lead:" + manifest_fingerprint(**_lead_identity(self))[:32]:
            raise MultiFunnelDiscoveryError("MULTI_FUNNEL_DISCOVERY_LEAD_IDENTITY_MISMATCH")
        if self.fingerprint != manifest_fingerprint(**_lead_payload(self)):
            raise MultiFunnelDiscoveryError("MULTI_FUNNEL_DISCOVERY_LEAD_FINGERPRINT_MISMATCH")


@dataclass(frozen=True, slots=True)
class FunnelCoverage:
    funnel_id: DiscoveryFunnelId
    universe_eligible: int
    securities_examined: int
    securities_with_required_data: int
    lead_ids: tuple[str, ...]
    data_insufficient: int
    policy_blocked: int
    excluded: int
    conflicted: int
    stale: int
    unsupported: int
    state: DiscoveryCoverageState

    def __post_init__(self) -> None:
        object.__setattr__(self, "lead_ids", _string_tuple(self.lead_ids, "MULTI_FUNNEL_DISCOVERY_COVERAGE_LEAD_IDS_INVALID"))
        values = (self.universe_eligible, self.securities_examined, self.securities_with_required_data, self.data_insufficient, self.policy_blocked, self.excluded, self.conflicted, self.stale, self.unsupported)
        if not all(isinstance(value, int) and value >= 0 for value in values):
            raise MultiFunnelDiscoveryError("MULTI_FUNNEL_DISCOVERY_COVERAGE_COUNT_INVALID")
        if self.securities_examined > self.universe_eligible or self.securities_with_required_data > self.securities_examined:
            raise MultiFunnelDiscoveryError("MULTI_FUNNEL_DISCOVERY_COVERAGE_COUNT_INCONSISTENT")
        if not isinstance(self.state, DiscoveryCoverageState):
            raise MultiFunnelDiscoveryError("MULTI_FUNNEL_DISCOVERY_COVERAGE_STATE_INVALID")
        if self.state is DiscoveryCoverageState.LEADS_EMITTED and not self.lead_ids:
            raise MultiFunnelDiscoveryError("MULTI_FUNNEL_DISCOVERY_COVERAGE_LEADS_REQUIRED")
        if self.state is DiscoveryCoverageState.EVALUATED_NO_LEADS and self.lead_ids:
            raise MultiFunnelDiscoveryError("MULTI_FUNNEL_DISCOVERY_COVERAGE_NO_LEADS_CONTRADICTION")
        if self.state is DiscoveryCoverageState.NOT_EVALUATED and self.securities_examined:
            raise MultiFunnelDiscoveryError("MULTI_FUNNEL_DISCOVERY_COVERAGE_NOT_EVALUATED_CONTRADICTION")


@dataclass(frozen=True, slots=True)
class MultiFunnelDiscoveryBatch:
    """Future-run envelope; this contract does not execute a batch."""

    as_of: datetime
    universe_snapshot_id: str
    universe_snapshot_fingerprint: str
    registry: "MultiFunnelDiscoveryRegistry"
    requested_funnels: tuple[DiscoveryFunnelId, ...]
    executed_funnels: tuple[DiscoveryFunnelId, ...]
    blocked_funnels: tuple[DiscoveryFunnelId, ...]
    coverage: tuple[FunnelCoverage, ...]
    emitted_lead_ids: tuple[str, ...]
    batch_id: str = field(init=False)
    fingerprint: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "as_of", _timestamp(self.as_of, "MULTI_FUNNEL_DISCOVERY_BATCH_AS_OF_INVALID"))
        for item in ("requested_funnels", "executed_funnels", "blocked_funnels"):
            object.__setattr__(self, item, _enum_tuple(getattr(self, item), DiscoveryFunnelId, "MULTI_FUNNEL_DISCOVERY_BATCH_FUNNELS_INVALID"))
        object.__setattr__(self, "coverage", tuple(sorted(self.coverage, key=lambda item: item.funnel_id.value)))
        object.__setattr__(self, "emitted_lead_ids", _string_tuple(self.emitted_lead_ids, "MULTI_FUNNEL_DISCOVERY_BATCH_LEAD_IDS_INVALID"))
        _validate_batch(self)
        object.__setattr__(self, "batch_id", "discovery-batch:" + manifest_fingerprint(**_batch_identity(self))[:32])
        object.__setattr__(self, "fingerprint", manifest_fingerprint(**_batch_payload(self)))

    def verify(self) -> None:
        _validate_batch(self)
        if self.batch_id != "discovery-batch:" + manifest_fingerprint(**_batch_identity(self))[:32]:
            raise MultiFunnelDiscoveryError("MULTI_FUNNEL_DISCOVERY_BATCH_IDENTITY_MISMATCH")
        if self.fingerprint != manifest_fingerprint(**_batch_payload(self)):
            raise MultiFunnelDiscoveryError("MULTI_FUNNEL_DISCOVERY_BATCH_FINGERPRINT_MISMATCH")


@dataclass(frozen=True, slots=True)
class MultiFunnelDiscoveryRegistryEntry:
    funnel_id: DiscoveryFunnelId
    version: str
    status: DiscoveryFunnelStatus
    horizons: tuple[DiscoveryHorizon, ...]
    required_inputs: tuple[str, ...]
    eligibility: str
    output_lead_type: str
    source_layer: DiscoverySourceLayer
    freshness_requirement: str
    trigger_semantics: str
    fail_closed_codes: tuple[str, ...]
    temporal_mode: str
    implementation_entry_point: str | None
    policy_identity: str | None

    def __post_init__(self) -> None:
        object.__setattr__(self, "horizons", _enum_tuple(self.horizons, DiscoveryHorizon, "MULTI_FUNNEL_DISCOVERY_REGISTRY_HORIZONS_INVALID"))
        for value in (self.version, self.eligibility, self.output_lead_type, self.freshness_requirement, self.trigger_semantics, self.temporal_mode):
            if not isinstance(value, str) or not value.strip():
                raise MultiFunnelDiscoveryError("MULTI_FUNNEL_DISCOVERY_REGISTRY_FIELD_INVALID")
        object.__setattr__(self, "required_inputs", _codes(self.required_inputs, "MULTI_FUNNEL_DISCOVERY_REGISTRY_INPUTS_INVALID"))
        object.__setattr__(self, "fail_closed_codes", _codes(self.fail_closed_codes, "MULTI_FUNNEL_DISCOVERY_REGISTRY_FAILURES_INVALID"))
        for value in (self.implementation_entry_point, self.policy_identity):
            if value is not None:
                _require_id(value, "MULTI_FUNNEL_DISCOVERY_REGISTRY_REFERENCE_INVALID")


@dataclass(frozen=True, slots=True)
class MultiFunnelDiscoveryRegistry:
    entries: tuple[MultiFunnelDiscoveryRegistryEntry, ...]
    registry_id: str = MULTI_FUNNEL_DISCOVERY_REGISTRY_ID
    version: str = MULTI_FUNNEL_DISCOVERY_REGISTRY_VERSION
    fingerprint: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "entries", tuple(sorted(self.entries, key=lambda item: item.funnel_id.value)))
        if self.registry_id != MULTI_FUNNEL_DISCOVERY_REGISTRY_ID or self.version != MULTI_FUNNEL_DISCOVERY_REGISTRY_VERSION:
            raise MultiFunnelDiscoveryError("MULTI_FUNNEL_DISCOVERY_REGISTRY_IDENTITY_INVALID")
        if len(self.entries) != len(DiscoveryFunnelId) or {item.funnel_id for item in self.entries} != set(DiscoveryFunnelId):
            raise MultiFunnelDiscoveryError("MULTI_FUNNEL_DISCOVERY_REGISTRY_CATALOGUE_INCOMPLETE")
        if len({item.funnel_id for item in self.entries}) != len(self.entries):
            raise MultiFunnelDiscoveryError("MULTI_FUNNEL_DISCOVERY_REGISTRY_DUPLICATE_FUNNEL")
        object.__setattr__(self, "fingerprint", manifest_fingerprint(**_registry_payload(self)))

    def get(self, funnel_id: DiscoveryFunnelId) -> MultiFunnelDiscoveryRegistryEntry:
        if not isinstance(funnel_id, DiscoveryFunnelId):
            raise MultiFunnelDiscoveryError("MULTI_FUNNEL_DISCOVERY_FUNNEL_ID_INVALID")
        return next(item for item in self.entries if item.funnel_id is funnel_id)

    def verify(self) -> None:
        if self.fingerprint != manifest_fingerprint(**_registry_payload(self)):
            raise MultiFunnelDiscoveryError("MULTI_FUNNEL_DISCOVERY_REGISTRY_FINGERPRINT_MISMATCH")


def multi_funnel_discovery_registry() -> MultiFunnelDiscoveryRegistry:
    """Return the fixed V1 inventory; it imports no producer or runtime state."""
    return MultiFunnelDiscoveryRegistry(_registry_entries())


def discovery_lead_payload(value: CanonicalDiscoveryLead) -> dict[str, object]:
    value.verify()
    return _lead_payload(value) | {"lead_id": value.lead_id, "fingerprint": value.fingerprint}


def serialize_discovery_lead(value: CanonicalDiscoveryLead) -> str:
    return json.dumps(discovery_lead_payload(value), sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _entry(funnel_id, status, horizons, inputs, lead_type, layer, entry, policy, blockers, *, eligibility="APPROVED_NSE_EQUITY_WHERE_APPLICABLE", freshness="SOURCE_DEFINED", trigger="SOURCE_STATE_ONLY", temporal="PIT_AS_OF"):
    return MultiFunnelDiscoveryRegistryEntry(
        funnel_id, "v1", status, tuple(sorted(horizons, key=lambda item: item.value)), tuple(sorted(inputs)),
        eligibility, lead_type, layer, freshness, trigger, tuple(sorted(blockers)), temporal, entry, policy,
    )


def _registry_entries() -> tuple[MultiFunnelDiscoveryRegistryEntry, ...]:
    return (
    _entry(DiscoveryFunnelId.MOMENTUM, DiscoveryFunnelStatus.PARTIAL, (DiscoveryHorizon.POSITIONAL,), ("CANONICAL_RELATIVE_STRENGTH", "PIT_OHLCV"), "TECHNICAL_INSPECTION_LEAD", DiscoverySourceLayer.DATA, "app.intelligence.opportunity_archetypes.OpportunityArchetypeRouter", None, ("MOMENTUM_TRIGGER_POLICY_UNAVAILABLE",)),
    _entry(DiscoveryFunnelId.PRE_BREAKOUT, DiscoveryFunnelStatus.OPERATIONAL, (DiscoveryHorizon.POSITIONAL,), ("GOVERNED_PREBREAKOUT_SETUP", "PIT_OHLCV", "CANONICAL_SECURITY_IDENTITY"), "SETUP_INSPECTION_LEAD", DiscoverySourceLayer.INTERPRETATION, "app.production_v1.top3_opportunity_finder.Top3OpportunityFinderService", "pre-breakout-policy:v1", ("SETUP_DATA_UNAVAILABLE", "PREBREAKOUT_POLICY_UNAVAILABLE")),
    _entry(DiscoveryFunnelId.FUNDAMENTAL_INFLECTION, DiscoveryFunnelStatus.RESEARCH_SHADOW, (DiscoveryHorizon.LONG_TERM, DiscoveryHorizon.POSITIONAL), ("PIT_QUARTERLY_FINANCIAL_FACTS", "PIT_COMPANY_TYPE"), "RESEARCH_INSPECTION_LEAD", DiscoverySourceLayer.DATA, "app.intelligence.inflection_accounting_prospective_shadow.run_inflection_accounting_prospective_batch", "inflection-accounting-prospective-shadow:v1", ("INFLECTION_QUALIFICATION_NOT_ACTIVE", "FILING_TIMESTAMP_TIMEZONE_COVERAGE_UNAVAILABLE"), temporal="PROSPECTIVE_PIT_AS_OF"),
    _entry(DiscoveryFunnelId.COMPOUNDER, DiscoveryFunnelStatus.RESEARCH_SHADOW, (DiscoveryHorizon.LONG_TERM,), ("PIT_ANNUAL_FINANCIAL_FACTS", "PIT_COMPANY_TYPE"), "RESEARCH_INSPECTION_LEAD", DiscoverySourceLayer.DATA, "app.intelligence.compounder_prospective_shadow_validation.run_compounder_prospective_batch", "compounder-prospective-shadow:v1", ("COMPOUNDER_QUALIFICATION_DEFERRED_PENDING_EMPIRICAL_VALIDATION",), temporal="PROSPECTIVE_PIT_AS_OF"),
    _entry(DiscoveryFunnelId.EMERGING_COMPOUNDER, DiscoveryFunnelStatus.NOT_IMPLEMENTED, (DiscoveryHorizon.LONG_TERM,), ("APPROVED_EMERGING_COMPOUNDER_POLICY",), "UNAVAILABLE", DiscoverySourceLayer.INTERPRETATION, None, None, ("EMERGING_COMPOUNDER_POLICY_UNAVAILABLE",)),
    _entry(DiscoveryFunnelId.EARNINGS_ACCELERATION, DiscoveryFunnelStatus.PARTIAL, (DiscoveryHorizon.POSITIONAL,), ("CANONICAL_DIAGNOSTIC_RULE_24",), "DIAGNOSTIC_INSPECTION_LEAD", DiscoverySourceLayer.DATA, "app.intelligence.opportunity_archetypes.OpportunityArchetypeRouter", "canonical-universe-analysis:v1", ("INDEPENDENT_EARNINGS_ACCELERATION_FUNNEL_NOT_DEFINED",)),
    _entry(DiscoveryFunnelId.ORDERBOOK_CAPEX, DiscoveryFunnelStatus.PARTIAL, (DiscoveryHorizon.POSITIONAL,), ("CANONICAL_DIAGNOSTIC_RULE_27", "OFFICIAL_FINANCIAL_EVIDENCE"), "DIAGNOSTIC_INSPECTION_LEAD", DiscoverySourceLayer.DATA, "app.intelligence.opportunity_archetypes.OpportunityArchetypeRouter", "canonical-universe-analysis:v1", ("ORDERBOOK_CAPEX_TRIGGER_POLICY_UNAVAILABLE",)),
    _entry(DiscoveryFunnelId.SECTOR_ROTATION, DiscoveryFunnelStatus.OPERATIONAL, (DiscoveryHorizon.POSITIONAL,), ("CURRENT_SECTOR_RANKING", "EXACT_CONSTITUENT_MAPPING"), "SECTOR_CONSTITUENT_INSPECTION_LEAD", DiscoverySourceLayer.DATA, "app.production_v1.top3_opportunity_finder.Top3OpportunityFinderService", "nse-sector-ranking:v1", ("SECTOR_TO_STOCK_LEAD_ADAPTER_NOT_IMPLEMENTED",)),
    _entry(DiscoveryFunnelId.NEWS_CATALYST, DiscoveryFunnelStatus.PARTIAL, (), ("VERIFIED_EXTERNAL_INTELLIGENCE", "EXACT_COMPANY_EXPOSURE"), "CATALYST_INSPECTION_LEAD", DiscoverySourceLayer.FACT, "app.intelligence.opportunity_archetypes.OpportunityArchetypeRouter", None, ("EVENT_CATALYST_CALIBRATION_REQUIRED", "FRESHNESS_POLICY_UNAVAILABLE")),
    _entry(DiscoveryFunnelId.POLICY_TRANSMISSION, DiscoveryFunnelStatus.RESEARCH_SHADOW, (DiscoveryHorizon.POSITIONAL, DiscoveryHorizon.LONG_TERM), ("VERIFIED_POLICY_EVIDENCE", "EXACT_COMPANY_EXPOSURE"), "RESEARCH_INSPECTION_LEAD", DiscoverySourceLayer.INTERPRETATION, "app.intelligence.long_term_policy_transmission_research_shadow", "long-term-policy-transmission-research-shadow:v1", ("POLICY_TRANSMISSION_QUALIFICATION_NOT_ACTIVE",)),
    _entry(DiscoveryFunnelId.VALUATION_RECOVERY, DiscoveryFunnelStatus.POLICY_BLOCKED, (DiscoveryHorizon.LONG_TERM,), ("APPROVED_VALUATION_RECOVERY_POLICY", "PIT_VALUATION_EVIDENCE"), "UNAVAILABLE", DiscoverySourceLayer.INTERPRETATION, None, None, ("VALUATION_RECOVERY_POLICY_UNAVAILABLE",)),
    _entry(DiscoveryFunnelId.MARKET_DISLOCATION, DiscoveryFunnelStatus.PARTIAL, (), ("MARKET_EXTREMES_ASSURANCE",), "REGIME_CONTEXT_ONLY", DiscoverySourceLayer.DATA, "app.intelligence.market_extremes_assurance_projection.project_market_extremes_assurance", "market-extremes-assurance:v1", ("SECURITY_LEVEL_DISLOCATION_TRIGGER_UNAVAILABLE",)),
    _entry(DiscoveryFunnelId.HOLDING_STATE_CHANGE, DiscoveryFunnelStatus.PARTIAL, (), ("CANONICAL_HOLDING_INTELLIGENCE",), "CONTEXTUAL_REVIEW_LEAD", DiscoverySourceLayer.INTERPRETATION, "app.portfolio.holding_intelligence.compose_holding_intelligence", None, ("HOLDING_CHANGE_DISCOVERY_ADAPTER_NOT_IMPLEMENTED",), eligibility="EXISTING_PORTFOLIO_HOLDINGS_ONLY"),
    _entry(DiscoveryFunnelId.WATCHLIST_STATE_CHANGE, DiscoveryFunnelStatus.NOT_IMPLEMENTED, (), ("APPROVED_WATCHLIST_STATE_CONTRACT",), "UNAVAILABLE", DiscoverySourceLayer.DATA, None, None, ("WATCHLIST_STATE_CONTRACT_UNAVAILABLE",), eligibility="GOVERNED_WATCHLIST_ONLY"),
)


def _timestamp(value: datetime, code: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise MultiFunnelDiscoveryError(code)
    return value.astimezone(UTC)


def _require_id(value: str, code: str) -> None:
    if not isinstance(value, str) or not _ID.fullmatch(value):
        raise MultiFunnelDiscoveryError(code)


def _require_fp(value: str, code: str) -> None:
    if not isinstance(value, str) or not _FP.fullmatch(value):
        raise MultiFunnelDiscoveryError(code)


def _codes(values, code: str) -> tuple[str, ...]:
    result = tuple(sorted(values))
    if result != tuple(values) or len(result) != len(set(result)) or not all(isinstance(item, str) and _ID.fullmatch(item) for item in result):
        raise MultiFunnelDiscoveryError(code)
    return result


def _string_tuple(values, code: str) -> tuple[str, ...]:
    return _codes(values, code)


def _enum_tuple(values, cls, code: str):
    result = tuple(sorted(values, key=lambda item: item.value if isinstance(item, cls) else ""))
    if result != tuple(values) or len(result) != len(set(result)) or not all(isinstance(item, cls) for item in result):
        raise MultiFunnelDiscoveryError(code)
    return result


def _canonical_lineage(values) -> tuple[DiscoveryLineageReference, ...]:
    if not values or not all(isinstance(item, DiscoveryLineageReference) for item in values):
        raise MultiFunnelDiscoveryError("MULTI_FUNNEL_DISCOVERY_LINEAGE_REQUIRED")
    result = tuple(sorted(values, key=lambda item: (item.kind.value, item.reference_id, item.reference_fingerprint)))
    ids = {(item.kind, item.reference_id) for item in result}
    if len(ids) != len(result):
        raise MultiFunnelDiscoveryError("MULTI_FUNNEL_DISCOVERY_LINEAGE_DUPLICATE_OR_CONFLICT")
    return result


def _validate_lead(value: CanonicalDiscoveryLead) -> None:
    _require_id(value.canonical_instrument_id, "MULTI_FUNNEL_DISCOVERY_INSTRUMENT_INVALID")
    _require_id(value.funnel_version, "MULTI_FUNNEL_DISCOVERY_FUNNEL_VERSION_INVALID")
    if value.issuer_id is not None:
        _require_id(value.issuer_id, "MULTI_FUNNEL_DISCOVERY_ISSUER_INVALID")
    if value.parent_discovery_id is not None:
        _require_id(value.parent_discovery_id, "MULTI_FUNNEL_DISCOVERY_PARENT_ID_INVALID")
    if value.contract_version != MULTI_FUNNEL_DISCOVERY_CONTRACT:
        raise MultiFunnelDiscoveryError("MULTI_FUNNEL_DISCOVERY_CONTRACT_VERSION_INVALID")
    if not isinstance(value.funnel_id, DiscoveryFunnelId) or not isinstance(value.source_layer, DiscoverySourceLayer) or not isinstance(value.readiness, DiscoveryLeadReadiness) or not isinstance(value.data_quality, DiscoveryDataQualityState):
        raise MultiFunnelDiscoveryError("MULTI_FUNNEL_DISCOVERY_LEAD_ENUM_INVALID")
    if not value.trigger_codes:
        raise MultiFunnelDiscoveryError("MULTI_FUNNEL_DISCOVERY_TRIGGER_CODES_REQUIRED")
    if any(item.known_at > value.discovery_as_of for item in value.lineage):
        raise MultiFunnelDiscoveryError("MULTI_FUNNEL_DISCOVERY_FUTURE_LINEAGE_FORBIDDEN")
    if value.readiness is DiscoveryLeadReadiness.RESEARCH_INSPECTION and value.funnel_id not in {DiscoveryFunnelId.COMPOUNDER, DiscoveryFunnelId.FUNDAMENTAL_INFLECTION, DiscoveryFunnelId.POLICY_TRANSMISSION}:
        raise MultiFunnelDiscoveryError("MULTI_FUNNEL_DISCOVERY_RESEARCH_POSTURE_INVALID")


def _validate_batch(value: MultiFunnelDiscoveryBatch) -> None:
    _require_id(value.universe_snapshot_id, "MULTI_FUNNEL_DISCOVERY_UNIVERSE_ID_INVALID")
    _require_fp(value.universe_snapshot_fingerprint, "MULTI_FUNNEL_DISCOVERY_UNIVERSE_FINGERPRINT_INVALID")
    if not isinstance(value.registry, MultiFunnelDiscoveryRegistry):
        raise MultiFunnelDiscoveryError("MULTI_FUNNEL_DISCOVERY_BATCH_REGISTRY_REQUIRED")
    value.registry.verify()
    if not value.requested_funnels or not set(value.executed_funnels).isdisjoint(value.blocked_funnels):
        raise MultiFunnelDiscoveryError("MULTI_FUNNEL_DISCOVERY_BATCH_FUNNEL_PARTITION_INVALID")
    if not set((*value.executed_funnels, *value.blocked_funnels)) <= set(value.requested_funnels):
        raise MultiFunnelDiscoveryError("MULTI_FUNNEL_DISCOVERY_BATCH_FUNNEL_NOT_REQUESTED")
    if len({item.funnel_id for item in value.coverage}) != len(value.coverage) or {item.funnel_id for item in value.coverage} != set((*value.executed_funnels, *value.blocked_funnels)):
        raise MultiFunnelDiscoveryError("MULTI_FUNNEL_DISCOVERY_BATCH_COVERAGE_INVALID")
    covered_leads = tuple(sorted(lead for item in value.coverage for lead in item.lead_ids))
    if covered_leads != value.emitted_lead_ids:
        raise MultiFunnelDiscoveryError("MULTI_FUNNEL_DISCOVERY_BATCH_LEAD_LINEAGE_INVALID")


def _lineage_payload(item: DiscoveryLineageReference) -> dict[str, object]:
    return {"reference_id": item.reference_id, "reference_fingerprint": item.reference_fingerprint, "kind": item.kind.value, "known_at": item.known_at.isoformat()}


def _lead_identity(value: CanonicalDiscoveryLead) -> dict[str, object]:
    return {"contract": value.contract_version, "instrument": value.canonical_instrument_id, "funnel": value.funnel_id.value, "funnel_version": value.funnel_version, "as_of": value.discovery_as_of.isoformat(), "lineage": tuple(_lineage_payload(item) for item in value.lineage)}


def _lead_payload(value: CanonicalDiscoveryLead) -> dict[str, object]:
    return _lead_identity(value) | {"issuer_id": value.issuer_id, "parent_discovery_id": value.parent_discovery_id, "source_layer": value.source_layer.value, "trigger_codes": tuple(item.value for item in value.trigger_codes), "readiness": value.readiness.value, "data_quality": value.data_quality.value, "intended_horizons": tuple(item.value for item in value.intended_horizons), "blocker_codes": value.blocker_codes}


def _entry_payload(value: MultiFunnelDiscoveryRegistryEntry) -> dict[str, object]:
    return {"funnel_id": value.funnel_id.value, "version": value.version, "status": value.status.value, "horizons": tuple(item.value for item in value.horizons), "required_inputs": value.required_inputs, "eligibility": value.eligibility, "output_lead_type": value.output_lead_type, "source_layer": value.source_layer.value, "freshness_requirement": value.freshness_requirement, "trigger_semantics": value.trigger_semantics, "fail_closed_codes": value.fail_closed_codes, "temporal_mode": value.temporal_mode, "implementation_entry_point": value.implementation_entry_point, "policy_identity": value.policy_identity}


def _registry_payload(value: MultiFunnelDiscoveryRegistry) -> dict[str, object]:
    return {"registry_id": value.registry_id, "version": value.version, "entries": tuple(_entry_payload(item) for item in value.entries)}


def _coverage_payload(value: FunnelCoverage) -> dict[str, object]:
    return {"funnel": value.funnel_id.value, "universe_eligible": value.universe_eligible, "securities_examined": value.securities_examined, "securities_with_required_data": value.securities_with_required_data, "lead_ids": value.lead_ids, "data_insufficient": value.data_insufficient, "policy_blocked": value.policy_blocked, "excluded": value.excluded, "conflicted": value.conflicted, "stale": value.stale, "unsupported": value.unsupported, "state": value.state.value}


def _batch_identity(value: MultiFunnelDiscoveryBatch) -> dict[str, object]:
    return {"contract": MULTI_FUNNEL_DISCOVERY_CONTRACT, "as_of": value.as_of.isoformat(), "universe_snapshot_id": value.universe_snapshot_id, "universe_snapshot_fingerprint": value.universe_snapshot_fingerprint, "registry_id": value.registry.registry_id, "registry_version": value.registry.version, "registry_fingerprint": value.registry.fingerprint, "requested_funnels": tuple(item.value for item in value.requested_funnels)}


def _batch_payload(value: MultiFunnelDiscoveryBatch) -> dict[str, object]:
    return _batch_identity(value) | {"executed_funnels": tuple(item.value for item in value.executed_funnels), "blocked_funnels": tuple(item.value for item in value.blocked_funnels), "coverage": tuple(_coverage_payload(item) for item in value.coverage), "emitted_lead_ids": value.emitted_lead_ids}


__all__ = [
    "CanonicalDiscoveryLead", "DiscoveryCoverageState", "DiscoveryDataQualityState", "DiscoveryFunnelId", "DiscoveryFunnelStatus", "DiscoveryHorizon", "DiscoveryLeadReadiness", "DiscoveryLineageReference", "DiscoveryReferenceKind", "DiscoverySourceLayer", "DiscoveryTriggerCode", "FunnelCoverage", "MULTI_FUNNEL_DISCOVERY_CONTRACT", "MULTI_FUNNEL_DISCOVERY_REGISTRY_ID", "MULTI_FUNNEL_DISCOVERY_REGISTRY_VERSION", "MultiFunnelDiscoveryBatch", "MultiFunnelDiscoveryError", "MultiFunnelDiscoveryRegistry", "MultiFunnelDiscoveryRegistryEntry", "discovery_lead_payload", "multi_funnel_discovery_registry", "serialize_discovery_lead",
]
