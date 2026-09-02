"""UI-safe schema for the provider-neutral Decision Trust Envelope."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class DecisionTrustDomainResponse(BaseModel):
    domain: str
    availability: str
    freshness: str
    evidence_as_of: datetime | None
    observed_at: datetime | None
    artifact_ids: tuple[str, ...]
    artifact_fingerprints: tuple[str, ...]
    blockers: tuple[str, ...]


class DecisionScoreTrustResponse(BaseModel):
    state: str
    value: Decimal | None
    artifact_id: str | None
    policy_version: str | None
    policy_fingerprint: str | None
    score_as_of: datetime | None
    blockers: tuple[str, ...]


class SetupTrustResponse(BaseModel):
    state: str
    setup_id: str | None
    setup_as_of: datetime | None
    setup_type: str | None
    entry: Decimal | None
    structural_invalidation: Decimal | None
    target_1: Decimal | None
    target_2: Decimal | None
    extended_target: Decimal | None
    risk_reward: Decimal | None
    maximum_executable_entry: Decimal | None
    blockers: tuple[str, ...]


class SixGatesTrustResponse(BaseModel):
    state: str
    evaluation_id: str | None
    policy_id: str | None
    policy_version: str | None
    policy_fingerprint: str | None
    evaluation_as_of: datetime | None
    aggregate_state: str | None
    gate_results: tuple[tuple[str, str], ...]
    blockers: tuple[str, ...]


class ThesisTrustResponse(BaseModel):
    trading_thesis: str | None
    investment_thesis: str | None
    invalidation_status: str | None
    structural_invalidation: Decimal | None
    source_as_of: datetime | None
    blockers: tuple[str, ...]


class LiveMarketContextResponse(BaseModel):
    ltp: Decimal | None
    received_at: datetime | None
    freshness: str | None


class DecisionTrustEnvelopeResponse(BaseModel):
    version: str
    canonical_instrument_id: str
    symbol: str
    intelligence_as_of: datetime
    latest_completed_market_session: datetime | None
    shared_brain_state: str
    domains: tuple[DecisionTrustDomainResponse, ...]
    coverage_count: int
    coverage_total: int
    coverage_pct: Decimal
    missing_domains: tuple[str, ...]
    blockers: tuple[str, ...]
    decision_readiness: str
    decision_score: DecisionScoreTrustResponse
    setup: SetupTrustResponse
    six_gates: SixGatesTrustResponse
    thesis: ThesisTrustResponse
    live_market: LiveMarketContextResponse
    fingerprint: str
