"""Read-only adapters from existing HSI evidence into inspection leads.

No adapter calculates a funnel, fetches a provider, persists a lead, unions
leads, or invokes any downstream Brain/portfolio/execution boundary.  Each
adapter merely verifies an already materialized, PIT-valid source contract.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Iterable

from app.intelligence.inflection_accounting_prospective_shadow import (
    InflectionAccountingObservationState, InflectionAccountingProspectiveObservation,
)
from app.intelligence.long_term_policy_transmission_research_shadow import (
    PolicyTransmissionResearchShadow, PolicyTransmissionState,
)
from app.intelligence.multi_funnel_discovery import (
    CanonicalDiscoveryLead, DiscoveryDataQualityState, DiscoveryFunnelId,
    DiscoveryHorizon, DiscoveryLeadReadiness, DiscoveryLineageReference,
    DiscoveryReferenceKind, DiscoverySourceLayer, DiscoveryTriggerCode,
)
from app.intelligence.compounder_prospective_shadow_validation import CompounderProspectiveObservation
from app.production_v1.canonical_setup_activation import CanonicalSetupOpportunity
from app.production_v1.top3_opportunity_finder import Top3OpportunityFinderRun


DISCOVERY_ADAPTER_REGISTRY_ID = "hsi-multi-funnel-discovery-adapters"
DISCOVERY_ADAPTER_REGISTRY_VERSION = "v1"
DISCOVERY_ADAPTER_CONTRACT = f"{DISCOVERY_ADAPTER_REGISTRY_ID}/{DISCOVERY_ADAPTER_REGISTRY_VERSION}"
_ID = re.compile(r"[A-Za-z0-9._:-]+\Z")
_FP = re.compile(r"(?:sha256:)?[0-9a-f]{64}\Z")


class DiscoveryAdapterError(ValueError):
    """Stable fail-closed error for malformed adapter inputs/results."""


class DiscoveryAdapterState(StrEnum):
    ADAPTER_ACTIVE = "ADAPTER_ACTIVE"
    ADAPTER_PARTIAL = "ADAPTER_PARTIAL"
    ADAPTER_NOT_APPLICABLE = "ADAPTER_NOT_APPLICABLE"
    SOURCE_BLOCKED = "SOURCE_BLOCKED"
    NOT_IMPLEMENTED = "NOT_IMPLEMENTED"


class DiscoveryAdapterCoverageState(StrEnum):
    LEADS_EMITTED = "LEADS_EMITTED"
    EVALUATED_NO_LEADS = "EVALUATED_NO_LEADS"
    NOT_EVALUATED = "NOT_EVALUATED"
    DATA_BLOCKED = "DATA_BLOCKED"
    POLICY_BLOCKED = "POLICY_BLOCKED"
    IDENTITY_BLOCKED = "IDENTITY_BLOCKED"
    SOURCE_NOT_OPERATIONAL = "SOURCE_NOT_OPERATIONAL"
    EVIDENCE_CONFLICTED = "EVIDENCE_CONFLICTED"
    STALE = "STALE"


class DiscoveryAdapterReason(StrEnum):
    SOURCE_AFTER_AS_OF = "SOURCE_AFTER_AS_OF"
    SOURCE_LINEAGE_INVALID = "SOURCE_LINEAGE_INVALID"
    SOURCE_IDENTITY_INVALID = "SOURCE_IDENTITY_INVALID"
    SOURCE_DUPLICATE_CONFLICT = "SOURCE_DUPLICATE_CONFLICT"
    INFLECTION_OBSERVATION_NOT_AVAILABLE = "INFLECTION_OBSERVATION_NOT_AVAILABLE"
    COMPOUNDER_OBSERVATION_NOT_AVAILABLE = "COMPOUNDER_OBSERVATION_NOT_AVAILABLE"
    POLICY_EXPOSURE_PATH_NOT_AVAILABLE = "POLICY_EXPOSURE_PATH_NOT_AVAILABLE"
    SECTOR_CONSTITUENT_PATH_NOT_AVAILABLE = "SECTOR_CONSTITUENT_PATH_NOT_AVAILABLE"
    MOMENTUM_TRIGGER_POLICY_UNAVAILABLE = "MOMENTUM_TRIGGER_POLICY_UNAVAILABLE"
    EARNINGS_ACCELERATION_NOT_INDEPENDENT = "EARNINGS_ACCELERATION_NOT_INDEPENDENT"
    ORDERBOOK_CAPEX_TRIGGER_POLICY_UNAVAILABLE = "ORDERBOOK_CAPEX_TRIGGER_POLICY_UNAVAILABLE"
    NEWS_CATALYST_ADAPTER_POLICY_UNAVAILABLE = "NEWS_CATALYST_ADAPTER_POLICY_UNAVAILABLE"
    MARKET_DISLOCATION_SECURITY_SCOPE_UNAVAILABLE = "MARKET_DISLOCATION_SECURITY_SCOPE_UNAVAILABLE"
    HOLDING_STATE_CHANGE_CONTRACT_UNAVAILABLE = "HOLDING_STATE_CHANGE_CONTRACT_UNAVAILABLE"
    FUNNEL_NOT_IMPLEMENTED = "FUNNEL_NOT_IMPLEMENTED"
    FUNNEL_POLICY_BLOCKED = "FUNNEL_POLICY_BLOCKED"


@dataclass(frozen=True, slots=True)
class DiscoveryAdapterCoverage:
    funnel_id: DiscoveryFunnelId
    adapter_state: DiscoveryAdapterState
    state: DiscoveryAdapterCoverageState
    source_observations_examined: int
    securities_examined: int
    lead_ids: tuple[str, ...]
    data_blocked: int = 0
    identity_blocked: int = 0
    policy_blocked: int = 0
    conflicted: int = 0
    no_lead: int = 0
    stale: int = 0
    reason_codes: tuple[DiscoveryAdapterReason, ...] = ()
    fingerprint: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.funnel_id, DiscoveryFunnelId) or not isinstance(self.adapter_state, DiscoveryAdapterState) or not isinstance(self.state, DiscoveryAdapterCoverageState):
            raise DiscoveryAdapterError("MULTI_FUNNEL_ADAPTER_COVERAGE_ENUM_INVALID")
        values = (self.source_observations_examined, self.securities_examined, self.data_blocked, self.identity_blocked, self.policy_blocked, self.conflicted, self.no_lead, self.stale)
        if not all(isinstance(item, int) and item >= 0 for item in values):
            raise DiscoveryAdapterError("MULTI_FUNNEL_ADAPTER_COVERAGE_COUNT_INVALID")
        object.__setattr__(self, "lead_ids", _strings(self.lead_ids, "MULTI_FUNNEL_ADAPTER_LEAD_IDS_INVALID"))
        object.__setattr__(self, "reason_codes", _enums(self.reason_codes, DiscoveryAdapterReason, "MULTI_FUNNEL_ADAPTER_REASONS_INVALID"))
        if self.state is DiscoveryAdapterCoverageState.LEADS_EMITTED and not self.lead_ids:
            raise DiscoveryAdapterError("MULTI_FUNNEL_ADAPTER_LEADS_REQUIRED")
        if self.state is DiscoveryAdapterCoverageState.EVALUATED_NO_LEADS and self.lead_ids:
            raise DiscoveryAdapterError("MULTI_FUNNEL_ADAPTER_NO_LEADS_CONTRADICTION")
        if self.state is DiscoveryAdapterCoverageState.NOT_EVALUATED and self.securities_examined:
            raise DiscoveryAdapterError("MULTI_FUNNEL_ADAPTER_NOT_EVALUATED_CONTRADICTION")
        object.__setattr__(self, "fingerprint", "sha256:" + _hash(_coverage_payload(self)))


@dataclass(frozen=True, slots=True)
class DiscoveryAdapterResult:
    funnel_id: DiscoveryFunnelId
    as_of: datetime
    leads: tuple[CanonicalDiscoveryLead, ...]
    coverage: DiscoveryAdapterCoverage
    adapter_id: str = DISCOVERY_ADAPTER_REGISTRY_ID
    adapter_version: str = DISCOVERY_ADAPTER_REGISTRY_VERSION
    fingerprint: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "as_of", _utc(self.as_of, "MULTI_FUNNEL_ADAPTER_AS_OF_INVALID"))
        object.__setattr__(self, "leads", tuple(sorted(self.leads, key=lambda item: item.lead_id)))
        if not all(isinstance(item, CanonicalDiscoveryLead) for item in self.leads):
            raise DiscoveryAdapterError("MULTI_FUNNEL_ADAPTER_LEAD_TYPE_INVALID")
        if len({item.lead_id for item in self.leads}) != len(self.leads):
            raise DiscoveryAdapterError("MULTI_FUNNEL_ADAPTER_LEAD_DUPLICATE")
        if any(item.funnel_id is not self.funnel_id for item in self.leads) or self.coverage.funnel_id is not self.funnel_id:
            raise DiscoveryAdapterError("MULTI_FUNNEL_ADAPTER_FUNNEL_MISMATCH")
        if tuple(item.lead_id for item in self.leads) != self.coverage.lead_ids:
            raise DiscoveryAdapterError("MULTI_FUNNEL_ADAPTER_COVERAGE_LINEAGE_MISMATCH")
        if (self.adapter_id, self.adapter_version) != (DISCOVERY_ADAPTER_REGISTRY_ID, DISCOVERY_ADAPTER_REGISTRY_VERSION):
            raise DiscoveryAdapterError("MULTI_FUNNEL_ADAPTER_VERSION_INVALID")
        object.__setattr__(self, "fingerprint", "sha256:" + _hash(_result_payload(self)))

    def verify(self) -> None:
        for item in self.leads:
            item.verify()
        if self.fingerprint != "sha256:" + _hash(_result_payload(self)):
            raise DiscoveryAdapterError("MULTI_FUNNEL_ADAPTER_FINGERPRINT_MISMATCH")


def adapt_pre_breakout(*, as_of: datetime, opportunities: Iterable[CanonicalSetupOpportunity]) -> DiscoveryAdapterResult:
    """Adapt stored governed setup opportunities; never re-run setup logic."""
    cutoff = _utc(as_of, "MULTI_FUNNEL_ADAPTER_AS_OF_INVALID")
    leads, counters = _adapt_sources(
        funnel=DiscoveryFunnelId.PRE_BREAKOUT, cutoff=cutoff, values=opportunities,
        lead_for=_pre_breakout_lead,
    )
    return _result(DiscoveryFunnelId.PRE_BREAKOUT, cutoff, leads, counters, DiscoveryAdapterState.ADAPTER_ACTIVE)


def adapt_sector_rotation(*, as_of: datetime, runs: Iterable[Top3OpportunityFinderRun]) -> DiscoveryAdapterResult:
    """Adapt only exact, stored Top-3 constituent inspection paths."""
    cutoff = _utc(as_of, "MULTI_FUNNEL_ADAPTER_AS_OF_INVALID")
    leads, counters = _adapt_sources(
        funnel=DiscoveryFunnelId.SECTOR_ROTATION, cutoff=cutoff, values=runs,
        lead_for=_sector_rotation_leads,
    )
    return _result(DiscoveryFunnelId.SECTOR_ROTATION, cutoff, leads, counters, DiscoveryAdapterState.ADAPTER_ACTIVE)


def adapt_fundamental_inflection(*, as_of: datetime, observations: Iterable[InflectionAccountingProspectiveObservation]) -> DiscoveryAdapterResult:
    cutoff = _utc(as_of, "MULTI_FUNNEL_ADAPTER_AS_OF_INVALID")
    leads, counters = _adapt_sources(
        funnel=DiscoveryFunnelId.FUNDAMENTAL_INFLECTION, cutoff=cutoff, values=observations,
        lead_for=_inflection_lead,
    )
    return _result(DiscoveryFunnelId.FUNDAMENTAL_INFLECTION, cutoff, leads, counters, DiscoveryAdapterState.ADAPTER_PARTIAL)


def adapt_compounder(*, as_of: datetime, observations: Iterable[CompounderProspectiveObservation]) -> DiscoveryAdapterResult:
    cutoff = _utc(as_of, "MULTI_FUNNEL_ADAPTER_AS_OF_INVALID")
    leads, counters = _adapt_sources(
        funnel=DiscoveryFunnelId.COMPOUNDER, cutoff=cutoff, values=observations,
        lead_for=_compounder_lead,
    )
    return _result(DiscoveryFunnelId.COMPOUNDER, cutoff, leads, counters, DiscoveryAdapterState.ADAPTER_PARTIAL)


def adapt_policy_transmission(*, as_of: datetime, observations: Iterable[PolicyTransmissionResearchShadow]) -> DiscoveryAdapterResult:
    cutoff = _utc(as_of, "MULTI_FUNNEL_ADAPTER_AS_OF_INVALID")
    leads, counters = _adapt_sources(
        funnel=DiscoveryFunnelId.POLICY_TRANSMISSION, cutoff=cutoff, values=observations,
        lead_for=_policy_transmission_lead,
    )
    return _result(DiscoveryFunnelId.POLICY_TRANSMISSION, cutoff, leads, counters, DiscoveryAdapterState.ADAPTER_PARTIAL)


def unavailable_adapter(*, funnel_id: DiscoveryFunnelId, as_of: datetime) -> DiscoveryAdapterResult:
    """Make every unadapted V1 funnel explicit instead of silently zeroing it."""
    cutoff = _utc(as_of, "MULTI_FUNNEL_ADAPTER_AS_OF_INVALID")
    mapping = {
        DiscoveryFunnelId.MOMENTUM: (DiscoveryAdapterState.ADAPTER_PARTIAL, DiscoveryAdapterCoverageState.SOURCE_NOT_OPERATIONAL, DiscoveryAdapterReason.MOMENTUM_TRIGGER_POLICY_UNAVAILABLE),
        DiscoveryFunnelId.EARNINGS_ACCELERATION: (DiscoveryAdapterState.ADAPTER_PARTIAL, DiscoveryAdapterCoverageState.SOURCE_NOT_OPERATIONAL, DiscoveryAdapterReason.EARNINGS_ACCELERATION_NOT_INDEPENDENT),
        DiscoveryFunnelId.ORDERBOOK_CAPEX: (DiscoveryAdapterState.ADAPTER_PARTIAL, DiscoveryAdapterCoverageState.SOURCE_NOT_OPERATIONAL, DiscoveryAdapterReason.ORDERBOOK_CAPEX_TRIGGER_POLICY_UNAVAILABLE),
        DiscoveryFunnelId.NEWS_CATALYST: (DiscoveryAdapterState.ADAPTER_PARTIAL, DiscoveryAdapterCoverageState.POLICY_BLOCKED, DiscoveryAdapterReason.NEWS_CATALYST_ADAPTER_POLICY_UNAVAILABLE),
        DiscoveryFunnelId.MARKET_DISLOCATION: (DiscoveryAdapterState.ADAPTER_PARTIAL, DiscoveryAdapterCoverageState.SOURCE_NOT_OPERATIONAL, DiscoveryAdapterReason.MARKET_DISLOCATION_SECURITY_SCOPE_UNAVAILABLE),
        DiscoveryFunnelId.HOLDING_STATE_CHANGE: (DiscoveryAdapterState.ADAPTER_PARTIAL, DiscoveryAdapterCoverageState.SOURCE_NOT_OPERATIONAL, DiscoveryAdapterReason.HOLDING_STATE_CHANGE_CONTRACT_UNAVAILABLE),
        DiscoveryFunnelId.EMERGING_COMPOUNDER: (DiscoveryAdapterState.NOT_IMPLEMENTED, DiscoveryAdapterCoverageState.SOURCE_NOT_OPERATIONAL, DiscoveryAdapterReason.FUNNEL_NOT_IMPLEMENTED),
        DiscoveryFunnelId.VALUATION_RECOVERY: (DiscoveryAdapterState.SOURCE_BLOCKED, DiscoveryAdapterCoverageState.POLICY_BLOCKED, DiscoveryAdapterReason.FUNNEL_POLICY_BLOCKED),
        DiscoveryFunnelId.WATCHLIST_STATE_CHANGE: (DiscoveryAdapterState.NOT_IMPLEMENTED, DiscoveryAdapterCoverageState.SOURCE_NOT_OPERATIONAL, DiscoveryAdapterReason.FUNNEL_NOT_IMPLEMENTED),
    }
    if funnel_id not in mapping:
        raise DiscoveryAdapterError("MULTI_FUNNEL_ADAPTER_FUNNEL_HAS_SOURCE_ADAPTER")
    adapter_state, state, reason = mapping[funnel_id]
    coverage = DiscoveryAdapterCoverage(funnel_id, adapter_state, state, 0, 0, (), reason_codes=(reason,))
    return DiscoveryAdapterResult(funnel_id, cutoff, (), coverage)


def _adapt_sources(*, funnel, cutoff, values, lead_for):
    leads: list[CanonicalDiscoveryLead] = []
    counters = {"source": 0, "securities": set(), "data": 0, "identity": 0, "policy": 0, "conflict": 0, "no_lead": 0, "stale": 0, "reasons": set()}
    seen: dict[str, str] = {}
    for value in tuple(values):
        counters["source"] += 1
        try:
            generated, source_id, source_fingerprint, source_as_of = lead_for(value, cutoff)
        except _AdapterSourceError as error:
            counters[error.bucket] += 1
            counters["reasons"].add(error.reason)
            continue
        if source_as_of > cutoff:
            counters["stale"] += 1; counters["reasons"].add(DiscoveryAdapterReason.SOURCE_AFTER_AS_OF); continue
        prior = seen.get(source_id)
        if prior is not None:
            if prior != source_fingerprint:
                counters["conflict"] += 1; counters["reasons"].add(DiscoveryAdapterReason.SOURCE_DUPLICATE_CONFLICT)
            continue
        seen[source_id] = source_fingerprint
        if not generated:
            counters["no_lead"] += 1
        for lead in generated:
            lead.verify(); leads.append(lead); counters["securities"].add(lead.canonical_instrument_id)
    return tuple(sorted(leads, key=lambda item: item.lead_id)), counters


def _pre_breakout_lead(value, cutoff):
    if not isinstance(value, CanonicalSetupOpportunity):
        raise _AdapterSourceError("data", DiscoveryAdapterReason.SOURCE_LINEAGE_INVALID)
    try: value.__post_init__()
    except ValueError: raise _AdapterSourceError("conflict", DiscoveryAdapterReason.SOURCE_LINEAGE_INVALID)
    lead = _lead(
        instrument=value.canonical_instrument_id, funnel=DiscoveryFunnelId.PRE_BREAKOUT, version=value.candidate.policy_version,
        as_of=value.decision_as_of, layer=DiscoverySourceLayer.INTERPRETATION,
        trigger=DiscoveryTriggerCode.GOVERNED_PREBREAKOUT_SETUP_AVAILABLE, readiness=DiscoveryLeadReadiness.READY_FOR_INSPECTION,
        quality=DiscoveryDataQualityState.VERIFIED, horizons=(DiscoveryHorizon.POSITIONAL,),
        lineage=(
            _lineage(value.opportunity_id, value.fingerprint, DiscoveryReferenceKind.ARTIFACT, value.decision_as_of),
            _lineage(value.assessment_id, value.assessment_fingerprint, DiscoveryReferenceKind.ARTIFACT, value.decision_as_of),
            _lineage(value.candidate.policy_id, value.policy_fingerprint, DiscoveryReferenceKind.RECEIPT, value.decision_as_of),
        ),
    )
    return (lead,), value.opportunity_id, value.fingerprint, value.decision_as_of.astimezone(UTC)


def _sector_rotation_leads(value, cutoff):
    if not isinstance(value, Top3OpportunityFinderRun):
        raise _AdapterSourceError("data", DiscoveryAdapterReason.SECTOR_CONSTITUENT_PATH_NOT_AVAILABLE)
    if not _aware(value.as_of) or not _id(value.run_id) or not _fp(value.fingerprint) or not _id(value.ranking_id):
        raise _AdapterSourceError("conflict", DiscoveryAdapterReason.SOURCE_LINEAGE_INVALID)
    if len(value.candidate_ids) != len(set(value.candidate_ids)) or not all(_id(item) for item in value.candidate_ids):
        raise _AdapterSourceError("identity", DiscoveryAdapterReason.SOURCE_IDENTITY_INVALID)
    leads = tuple(_lead(
        instrument=instrument, funnel=DiscoveryFunnelId.SECTOR_ROTATION, version="v1", as_of=value.as_of,
        layer=DiscoverySourceLayer.DATA, trigger=DiscoveryTriggerCode.SECTOR_ROTATION_STATE,
        readiness=DiscoveryLeadReadiness.READY_FOR_INSPECTION, quality=DiscoveryDataQualityState.VERIFIED,
        horizons=(DiscoveryHorizon.POSITIONAL,), lineage=(
            _lineage(value.run_id, value.fingerprint, DiscoveryReferenceKind.ARTIFACT, value.as_of),
            _lineage(value.ranking_id, value.fingerprint, DiscoveryReferenceKind.OBSERVATION, value.as_of),
        ), parent=value.run_id,
    ) for instrument in value.candidate_ids)
    return leads, value.run_id, value.fingerprint, value.as_of.astimezone(UTC)


def _inflection_lead(value, cutoff):
    if not isinstance(value, InflectionAccountingProspectiveObservation):
        raise _AdapterSourceError("data", DiscoveryAdapterReason.INFLECTION_OBSERVATION_NOT_AVAILABLE)
    try: value.verify()
    except ValueError: raise _AdapterSourceError("conflict", DiscoveryAdapterReason.SOURCE_LINEAGE_INVALID)
    if value.observation_state is not InflectionAccountingObservationState.ACCOUNTING_INFLECTION_OBSERVATION_AVAILABLE:
        return (), value.observation_id, value.fingerprint, value.as_of.astimezone(UTC)
    lead = _lead(
        instrument=value.canonical_instrument_id, issuer=value.canonical_issuer_id, funnel=DiscoveryFunnelId.FUNDAMENTAL_INFLECTION,
        version=value.contract_version, as_of=value.as_of, layer=DiscoverySourceLayer.DATA,
        trigger=DiscoveryTriggerCode.INFLECTION_ACCOUNTING_OBSERVATION_AVAILABLE, readiness=DiscoveryLeadReadiness.RESEARCH_INSPECTION,
        quality=DiscoveryDataQualityState.VERIFIED, horizons=(DiscoveryHorizon.LONG_TERM, DiscoveryHorizon.POSITIONAL),
        lineage=(
            _lineage(value.observation_id, value.fingerprint, DiscoveryReferenceKind.OBSERVATION, value.as_of),
            _lineage(value.revenue.receipt_id, value.revenue.fingerprint, DiscoveryReferenceKind.RECEIPT, value.as_of),
            _lineage(value.pat.receipt_id, value.pat.fingerprint, DiscoveryReferenceKind.RECEIPT, value.as_of),
            _lineage(value.company_type_receipt.receipt_id, value.company_type_receipt.fingerprint, DiscoveryReferenceKind.RECEIPT, value.as_of),
        ), blocker=(value.exact_intraday_event_time.value,),
    )
    return (lead,), value.observation_id, value.fingerprint, value.as_of.astimezone(UTC)


def _compounder_lead(value, cutoff):
    if not isinstance(value, CompounderProspectiveObservation):
        raise _AdapterSourceError("data", DiscoveryAdapterReason.COMPOUNDER_OBSERVATION_NOT_AVAILABLE)
    try: value.verify()
    except ValueError: raise _AdapterSourceError("conflict", DiscoveryAdapterReason.SOURCE_LINEAGE_INVALID)
    lead = _lead(
        instrument=value.canonical_instrument_id, issuer=value.canonical_issuer_id, funnel=DiscoveryFunnelId.COMPOUNDER,
        version=value.contract_version, as_of=value.as_of, layer=DiscoverySourceLayer.DATA,
        trigger=DiscoveryTriggerCode.COMPOUNDER_PROSPECTIVE_OBSERVATION_AVAILABLE, readiness=DiscoveryLeadReadiness.RESEARCH_INSPECTION,
        quality=DiscoveryDataQualityState.VERIFIED, horizons=(DiscoveryHorizon.LONG_TERM,), lineage=(
            _lineage(value.observation_id, value.fingerprint, DiscoveryReferenceKind.OBSERVATION, value.input_known_at),
            _lineage(value.issuer_observation_id, value.issuer_observation_fingerprint, DiscoveryReferenceKind.RECEIPT, value.input_known_at),
            _lineage(value.company_type_receipt.receipt_id, value.company_type_receipt.fingerprint, DiscoveryReferenceKind.RECEIPT, value.input_known_at),
            _lineage(value.candidate_grid_plan_id, value.candidate_grid_fingerprint, DiscoveryReferenceKind.ARTIFACT, value.input_known_at),
        ),
    )
    return (lead,), value.observation_id, value.fingerprint, value.as_of.astimezone(UTC)


def _policy_transmission_lead(value, cutoff):
    if not isinstance(value, PolicyTransmissionResearchShadow):
        raise _AdapterSourceError("data", DiscoveryAdapterReason.POLICY_EXPOSURE_PATH_NOT_AVAILABLE)
    try: value.verify()
    except ValueError: raise _AdapterSourceError("conflict", DiscoveryAdapterReason.SOURCE_LINEAGE_INVALID)
    if value.state is not PolicyTransmissionState.POLICY_DEFINITION_MISSING:
        return (), value.result_id, value.fingerprint, value.source_receipt.source_review.context.as_of.astimezone(UTC)
    source = value.source_receipt
    lead = _lead(
        instrument=source.source_review.canonical_instrument_id, funnel=DiscoveryFunnelId.POLICY_TRANSMISSION,
        version=value.contract_version.rsplit("/", 1)[-1], as_of=source.source_review.context.as_of, layer=DiscoverySourceLayer.INTERPRETATION,
        trigger=DiscoveryTriggerCode.POLICY_TRANSMISSION_RESEARCH_OBSERVATION, readiness=DiscoveryLeadReadiness.RESEARCH_INSPECTION,
        quality=DiscoveryDataQualityState.VERIFIED, horizons=(DiscoveryHorizon.LONG_TERM, DiscoveryHorizon.POSITIONAL), lineage=(
            _lineage(value.result_id, value.fingerprint, DiscoveryReferenceKind.OBSERVATION, source.source_review.context.as_of),
            _lineage(value.policy_evidence_id, value.policy_evidence_fingerprint, DiscoveryReferenceKind.EVIDENCE, value.policy_evidence.received_at),
            _lineage(source.receipt_id, source.fingerprint, DiscoveryReferenceKind.RECEIPT, source.source_review.context.as_of),
        ), blocker=tuple(reason.value for reason in value.reasons),
    )
    return (lead,), value.result_id, value.fingerprint, source.source_review.context.as_of.astimezone(UTC)


def _lead(*, instrument, funnel, version, as_of, layer, trigger, readiness, quality, horizons, lineage, issuer=None, parent=None, blocker=()):
    return CanonicalDiscoveryLead(
        canonical_instrument_id=instrument, issuer_id=issuer, funnel_id=funnel, funnel_version=version,
        discovery_as_of=as_of, source_layer=layer, trigger_codes=(trigger,), readiness=readiness,
        data_quality=quality, intended_horizons=tuple(sorted(horizons, key=lambda item: item.value)),
        lineage=tuple(sorted(lineage, key=lambda item: (item.kind.value, item.reference_id, item.reference_fingerprint))),
        parent_discovery_id=parent, blocker_codes=tuple(sorted(blocker)),
    )


def _lineage(identifier, fingerprint, kind, known_at):
    return DiscoveryLineageReference(identifier, fingerprint, kind, known_at)


def _result(funnel, cutoff, leads, counters, adapter_state):
    if leads:
        state = DiscoveryAdapterCoverageState.LEADS_EMITTED
    elif counters["conflict"]:
        state = DiscoveryAdapterCoverageState.EVIDENCE_CONFLICTED
    elif counters["identity"]:
        state = DiscoveryAdapterCoverageState.IDENTITY_BLOCKED
    elif counters["stale"]:
        state = DiscoveryAdapterCoverageState.STALE
    elif counters["data"]:
        state = DiscoveryAdapterCoverageState.DATA_BLOCKED
    else:
        state = DiscoveryAdapterCoverageState.EVALUATED_NO_LEADS
    coverage = DiscoveryAdapterCoverage(
        funnel, adapter_state, state, counters["source"], len(counters["securities"]), tuple(item.lead_id for item in leads),
        counters["data"], counters["identity"], counters["policy"], counters["conflict"], counters["no_lead"], counters["stale"],
        tuple(sorted(counters["reasons"], key=lambda item: item.value)),
    )
    return DiscoveryAdapterResult(funnel, cutoff, leads, coverage)


@dataclass(frozen=True, slots=True)
class _AdapterSourceError(Exception):
    bucket: str
    reason: DiscoveryAdapterReason


def _utc(value, code):
    if not _aware(value): raise DiscoveryAdapterError(code)
    return value.astimezone(UTC)
def _aware(value): return isinstance(value, datetime) and value.tzinfo is not None and value.utcoffset() is not None
def _id(value): return isinstance(value, str) and bool(_ID.fullmatch(value))
def _fp(value): return isinstance(value, str) and bool(_FP.fullmatch(value))
def _strings(values, code):
    result = tuple(sorted(values))
    if result != tuple(values) or len(result) != len(set(result)) or not all(_id(item) for item in result): raise DiscoveryAdapterError(code)
    return result
def _enums(values, cls, code):
    result = tuple(sorted(values, key=lambda item: item.value if isinstance(item, cls) else ""))
    if result != tuple(values) or len(result) != len(set(result)) or not all(isinstance(item, cls) for item in result): raise DiscoveryAdapterError(code)
    return result
def _hash(value): return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()).hexdigest()
def _coverage_payload(value): return {"funnel": value.funnel_id.value, "adapter_state": value.adapter_state.value, "state": value.state.value, "source_observations_examined": value.source_observations_examined, "securities_examined": value.securities_examined, "lead_ids": value.lead_ids, "data_blocked": value.data_blocked, "identity_blocked": value.identity_blocked, "policy_blocked": value.policy_blocked, "conflicted": value.conflicted, "no_lead": value.no_lead, "stale": value.stale, "reason_codes": tuple(item.value for item in value.reason_codes)}
def _result_payload(value): return {"contract": DISCOVERY_ADAPTER_CONTRACT, "funnel": value.funnel_id.value, "as_of": value.as_of.isoformat(), "lead_ids": tuple((item.lead_id, item.fingerprint) for item in value.leads), "coverage_fingerprint": value.coverage.fingerprint}


__all__ = [
    "DISCOVERY_ADAPTER_CONTRACT", "DISCOVERY_ADAPTER_REGISTRY_ID", "DISCOVERY_ADAPTER_REGISTRY_VERSION", "DiscoveryAdapterCoverage", "DiscoveryAdapterCoverageState", "DiscoveryAdapterError", "DiscoveryAdapterReason", "DiscoveryAdapterResult", "DiscoveryAdapterState", "adapt_compounder", "adapt_fundamental_inflection", "adapt_policy_transmission", "adapt_pre_breakout", "adapt_sector_rotation", "unavailable_adapter",
]
