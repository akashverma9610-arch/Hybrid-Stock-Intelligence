from datetime import datetime

from pydantic import BaseModel


class WatchEvidenceReferenceResponse(BaseModel):
    rule_id: str
    diagnostic_result: str
    artifact_id: str
    artifact_fingerprint: str


class WatchExternalEvidenceReferenceResponse(BaseModel):
    canonical_event_id: str
    evidence_version_id: str
    event_type: str
    materiality: str
    policy_stage: str | None
    primary_source_type: str
    exposure_type: str
    exposure_verification_status: str
    evidence_fingerprint: str


class MarketWideWatchRecordResponse(BaseModel):
    watch_id: str
    canonical_instrument_id: str
    symbol: str
    company_name: str | None
    watch_as_of: datetime
    classifications: tuple[str, ...]
    status: str
    evidence_sufficiency: str
    evidence_references: tuple[WatchEvidenceReferenceResponse, ...]
    sector: str | None
    sector_rank: int | None
    top3_eligible: bool
    decision_score_id: str | None
    decision_score_status: str
    decision_score_value: str | None
    setup_state: str
    six_gates_state: str
    reliability_state: str
    blocker_codes: tuple[str, ...]
    last_evidence_as_of: datetime | None
    policy_identity: str
    fingerprint: str
    archetypes: tuple[str, ...]
    external_evidence_references: tuple[WatchExternalEvidenceReferenceResponse, ...]
    policy_maturity: str | None
    historical_quality_state: str
    current_inflection_state: str
    setup_policy_routes: tuple[tuple[str, str], ...]
    lifecycle_flags: tuple[str, ...]
    evidence_domain_coverage: tuple[str, ...]
    rotation_challenger_state: str
    comparison_readiness: str


class MarketWideWatchResponse(BaseModel):
    run_id: str
    watch_as_of: datetime
    universe_id: str
    universe_count: int
    eligible_count: int
    excluded_count: int
    exclusion_counts: tuple[tuple[str, int], ...]
    evidence_ready_count: int
    watch_candidate_count: int
    classification_counts: tuple[tuple[str, int], ...]
    top3_eligible_count: int
    setup_candidate_count: int
    valid_setup_count: int
    decision_score_ready_count: int
    six_gates_evaluated_count: int
    six_gates_pass_count: int
    filter_attribution: tuple[tuple[str, int], ...]
    unsupported_classifications: tuple[str, ...]
    records: tuple[MarketWideWatchRecordResponse, ...]
    portfolio_records: tuple[MarketWideWatchRecordResponse, ...]
    policy_identity: str
    fingerprint: str
    archetype_counts: tuple[tuple[str, int], ...]
    rotation_funnel: tuple[tuple[str, int], ...]
    rotation_challenger_count: int
    actual_rotation_candidate_count: int
    evidence_readiness_counts: tuple[tuple[str, int], ...] = ()
    evidence_domain_counts: tuple[tuple[str, int], ...] = ()
    evidence_blocker_attribution: tuple[tuple[str, int], ...] = ()
