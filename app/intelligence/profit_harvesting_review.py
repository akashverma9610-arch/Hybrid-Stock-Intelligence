"""Watch-only Profit-Harvesting review from Market-Extremes assurance only."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
import json

from app.crisis.models import UpsideExcessState
from app.historical.guard import manifest_fingerprint
from app.intelligence.market_extremes_assurance_projection import (
    MarketExtremesAssuranceProjection, MarketExtremesAssuranceReason,
    MarketExtremesAssuranceState,
)


PROFIT_HARVESTING_POLICY_ID = "profit-harvesting-review-policy"
PROFIT_HARVESTING_POLICY_VERSION = "market-extremes-euphoria-shadow-v1"


class ProfitHarvestingReviewError(ValueError): pass


class ProfitHarvestingReviewStatus(StrEnum):
    PROFIT_REVIEW_UNAVAILABLE = "PROFIT_REVIEW_UNAVAILABLE"
    NO_PROFIT_REVIEW_EVIDENCE = "NO_PROFIT_REVIEW_EVIDENCE"
    MONITOR_PROFIT = "MONITOR_PROFIT"
    CONFLICTED_PROFIT_REVIEW = "CONFLICTED_PROFIT_REVIEW"


class ProfitHarvestingActionability(StrEnum): WATCH_ONLY = "WATCH_ONLY"
class ProfitHarvestingExecutionStatus(StrEnum): NON_EXECUTABLE = "NON_EXECUTABLE"


class ProfitHarvestingUnavailableDomain(StrEnum):
    VALUATION_EXTENSION = "VALUATION_EXTENSION"
    PRICE_EXTENSION = "PRICE_EXTENSION"
    PEER_PERCENTILE = "PEER_PERCENTILE"
    VOLUME_CONFIRMATION = "VOLUME_CONFIRMATION"
    THESIS_MILESTONE = "THESIS_MILESTONE"
    CATALYST_REALIZATION = "CATALYST_REALIZATION"
    FORWARD_REWARD_RISK = "FORWARD_REWARD_RISK"
    FUNDAMENTALS_PRICED_IN = "FUNDAMENTALS_PRICED_IN"
    THESIS_REALIZATION = "THESIS_REALIZATION"
    PURCHASE_PRICE_RETURN = "PURCHASE_PRICE_RETURN"
    PORTFOLIO_CONCENTRATION = "PORTFOLIO_CONCENTRATION"
    SIZING_QUANTITY = "SIZING_QUANTITY"
    TAX_SLIPPAGE_FRICTION = "TAX_SLIPPAGE_FRICTION"
    REPLACEMENT_ROTATION = "REPLACEMENT_ROTATION"


_UNAVAILABLE = tuple(ProfitHarvestingUnavailableDomain)


@dataclass(frozen=True, slots=True)
class ProfitHarvestingReview:
    canonical_instrument_id: str | None
    evaluation_as_of: datetime
    assurance_projection_id: str
    assurance_projection_fingerprint: str
    assurance_state: MarketExtremesAssuranceState
    assurance_reason_codes: tuple[MarketExtremesAssuranceReason, ...]
    assurance_evidence_references: tuple[str, ...]
    status: ProfitHarvestingReviewStatus
    selected_snapshot_id: str | None
    selected_snapshot_fingerprint: str | None
    selected_regime: UpsideExcessState | None
    policy_id: str = PROFIT_HARVESTING_POLICY_ID
    policy_version: str = PROFIT_HARVESTING_POLICY_VERSION
    actionability: ProfitHarvestingActionability = field(default=ProfitHarvestingActionability.WATCH_ONLY, init=False)
    execution_status: ProfitHarvestingExecutionStatus = field(default=ProfitHarvestingExecutionStatus.NON_EXECUTABLE, init=False)
    source_domain: str = field(default="MARKET_EXTREMES_ASSURANCE", init=False)
    unavailable_domains: tuple[ProfitHarvestingUnavailableDomain, ...] = field(default=_UNAVAILABLE, init=False)
    review_id: str = field(init=False)
    fingerprint: str = field(init=False)

    def __post_init__(self) -> None:
        _validate(self)
        object.__setattr__(self, "review_id", "profit-harvesting-review:" + manifest_fingerprint(**_identity(self))[:24])
        object.__setattr__(self, "fingerprint", "sha256:" + manifest_fingerprint(**_payload(self)))

    def verify(self) -> None:
        _validate(self)
        if self.review_id != "profit-harvesting-review:" + manifest_fingerprint(**_identity(self))[:24]:
            raise ProfitHarvestingReviewError("PROFIT_HARVESTING_REVIEW_IDENTITY_MISMATCH")
        if self.fingerprint != "sha256:" + manifest_fingerprint(**_payload(self)):
            raise ProfitHarvestingReviewError("PROFIT_HARVESTING_REVIEW_FINGERPRINT_MISMATCH")


def evaluate_profit_harvesting_review(*, assurance: MarketExtremesAssuranceProjection, canonical_instrument_id: str | None = None) -> ProfitHarvestingReview:
    if not isinstance(assurance, MarketExtremesAssuranceProjection):
        raise ProfitHarvestingReviewError("PROFIT_HARVESTING_ASSURANCE_REQUIRED")
    assurance.verify()
    if canonical_instrument_id is not None and (not canonical_instrument_id.strip() or canonical_instrument_id != canonical_instrument_id.strip()):
        raise ProfitHarvestingReviewError("PROFIT_HARVESTING_INSTRUMENT_INVALID")
    status = _status(assurance)
    usable = assurance.assurance_state is MarketExtremesAssuranceState.READY
    evidence = tuple(sorted({item.reference_id for item in assurance.candidate_references}))
    return ProfitHarvestingReview(
        canonical_instrument_id, assurance.context.as_of, assurance.projection_id, assurance.fingerprint,
        assurance.assurance_state, assurance.reason_codes, evidence, status,
        assurance.selected_snapshot_id if usable else None,
        assurance.selected_snapshot_fingerprint if usable else None,
        assurance.selected_regime if usable else None,
    )


def serialize_profit_harvesting_review(value: ProfitHarvestingReview) -> str:
    value.verify()
    return json.dumps(_payload(value) | {"fingerprint": value.fingerprint}, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _status(value: MarketExtremesAssuranceProjection) -> ProfitHarvestingReviewStatus:
    if value.assurance_state is MarketExtremesAssuranceState.CONFLICTED:
        return ProfitHarvestingReviewStatus.CONFLICTED_PROFIT_REVIEW
    if value.assurance_state is not MarketExtremesAssuranceState.READY:
        return ProfitHarvestingReviewStatus.PROFIT_REVIEW_UNAVAILABLE
    return ProfitHarvestingReviewStatus.MONITOR_PROFIT if value.selected_regime is UpsideExcessState.EUPHORIA else ProfitHarvestingReviewStatus.NO_PROFIT_REVIEW_EVIDENCE


def _validate(value: ProfitHarvestingReview) -> None:
    if value.policy_id != PROFIT_HARVESTING_POLICY_ID or value.policy_version != PROFIT_HARVESTING_POLICY_VERSION:
        raise ProfitHarvestingReviewError("PROFIT_HARVESTING_POLICY_INVALID")
    if value.evaluation_as_of.tzinfo is None or value.evaluation_as_of.utcoffset() is None:
        raise ProfitHarvestingReviewError("PROFIT_HARVESTING_AS_OF_INVALID")
    if value.actionability is not ProfitHarvestingActionability.WATCH_ONLY or value.execution_status is not ProfitHarvestingExecutionStatus.NON_EXECUTABLE:
        raise ProfitHarvestingReviewError("PROFIT_HARVESTING_FIXED_STATE_INVALID")
    if value.unavailable_domains != _UNAVAILABLE or value.assurance_evidence_references != tuple(sorted(set(value.assurance_evidence_references))):
        raise ProfitHarvestingReviewError("PROFIT_HARVESTING_COLLECTION_INVALID")
    if value.status is ProfitHarvestingReviewStatus.MONITOR_PROFIT and (value.assurance_state is not MarketExtremesAssuranceState.READY or value.selected_regime is not UpsideExcessState.EUPHORIA):
        raise ProfitHarvestingReviewError("PROFIT_HARVESTING_MAPPING_INVALID")
    if value.status is ProfitHarvestingReviewStatus.CONFLICTED_PROFIT_REVIEW and value.assurance_state is not MarketExtremesAssuranceState.CONFLICTED:
        raise ProfitHarvestingReviewError("PROFIT_HARVESTING_MAPPING_INVALID")
    if value.status is ProfitHarvestingReviewStatus.PROFIT_REVIEW_UNAVAILABLE and value.assurance_state in {MarketExtremesAssuranceState.READY, MarketExtremesAssuranceState.CONFLICTED}:
        raise ProfitHarvestingReviewError("PROFIT_HARVESTING_MAPPING_INVALID")
    if value.status is ProfitHarvestingReviewStatus.NO_PROFIT_REVIEW_EVIDENCE and (value.assurance_state is not MarketExtremesAssuranceState.READY or value.selected_regime is UpsideExcessState.EUPHORIA):
        raise ProfitHarvestingReviewError("PROFIT_HARVESTING_MAPPING_INVALID")


def _timestamp(value: datetime) -> str: return value.astimezone(UTC).isoformat()
def _identity(value: ProfitHarvestingReview) -> dict[str, object]:
    return {"policy_id": value.policy_id, "policy_version": value.policy_version, "instrument": value.canonical_instrument_id, "as_of": _timestamp(value.evaluation_as_of), "assurance_id": value.assurance_projection_id, "assurance_fingerprint": value.assurance_projection_fingerprint, "status": value.status.value}
def _payload(value: ProfitHarvestingReview) -> dict[str, object]:
    return _identity(value) | {"review_id": value.review_id, "assurance_state": value.assurance_state.value, "assurance_reasons": tuple(x.value for x in value.assurance_reason_codes), "evidence_references": value.assurance_evidence_references, "selected_snapshot_id": value.selected_snapshot_id, "selected_snapshot_fingerprint": value.selected_snapshot_fingerprint, "selected_regime": None if value.selected_regime is None else value.selected_regime.value, "actionability": value.actionability.value, "execution_status": value.execution_status.value, "source_domain": value.source_domain, "unavailable_domains": tuple(x.value for x in value.unavailable_domains)}


__all__ = ("PROFIT_HARVESTING_POLICY_ID", "PROFIT_HARVESTING_POLICY_VERSION", "ProfitHarvestingActionability", "ProfitHarvestingExecutionStatus", "ProfitHarvestingReview", "ProfitHarvestingReviewError", "ProfitHarvestingReviewStatus", "ProfitHarvestingUnavailableDomain", "evaluate_profit_harvesting_review", "serialize_profit_harvesting_review")
