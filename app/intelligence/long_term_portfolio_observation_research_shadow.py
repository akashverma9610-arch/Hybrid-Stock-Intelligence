"""Pure PIT-safe association of immutable portfolio snapshots and thesis receipts."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
import hashlib
import json
import re

from app.intelligence.long_term_thesis_invalidation_research_shadow import (
    LongTermThesisInvalidationResearchShadow,
    LongTermThesisLifecycleState,
)
from app.portfolio.models import CashPosition, CashState, PortfolioHolding, PortfolioSnapshot


CONTRACT_VERSION = "long-term-portfolio-observation-research-shadow/v1"
_ID = re.compile(r"[A-Za-z0-9._:-]+")
_FINGERPRINT = re.compile(r"sha256:[0-9a-f]{64}")


class LongTermPortfolioObservationError(ValueError):
    """Raised when the immutable adapter input or result is malformed."""


class PortfolioObservationState(StrEnum):
    DATA_INSUFFICIENT = "DATA_INSUFFICIENT"
    EVIDENCE_CONFLICTED = "EVIDENCE_CONFLICTED"
    POLICY_DEFINITION_MISSING = "POLICY_DEFINITION_MISSING"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    NON_COMPARABLE = "NON_COMPARABLE"
    IDENTITY_UNAVAILABLE = "IDENTITY_UNAVAILABLE"
    LIFECYCLE_RECEIPT_UNAVAILABLE = "LIFECYCLE_RECEIPT_UNAVAILABLE"
    LIFECYCLE_RECEIPT_AMBIGUOUS = "LIFECYCLE_RECEIPT_AMBIGUOUS"


class PortfolioObservationReason(StrEnum):
    CANONICAL_INSTRUMENT_IDENTITY_UNAVAILABLE = "CANONICAL_INSTRUMENT_IDENTITY_UNAVAILABLE"
    CASH_IS_VALID_ALLOCATION = "CASH_IS_VALID_ALLOCATION"
    LIFECYCLE_DATA_INSUFFICIENT = "LIFECYCLE_DATA_INSUFFICIENT"
    LIFECYCLE_EVIDENCE_CONFLICTED = "LIFECYCLE_EVIDENCE_CONFLICTED"
    LIFECYCLE_POLICY_DEFINITION_MISSING = "LIFECYCLE_POLICY_DEFINITION_MISSING"
    LIFECYCLE_NOT_APPLICABLE = "LIFECYCLE_NOT_APPLICABLE"
    LIFECYCLE_RECEIPT_UNAVAILABLE = "LIFECYCLE_RECEIPT_UNAVAILABLE"
    FUTURE_LIFECYCLE_RECEIPT_EXCLUDED = "FUTURE_LIFECYCLE_RECEIPT_EXCLUDED"
    LIFECYCLE_SELECTION_UNGOVERNED = "LIFECYCLE_SELECTION_UNGOVERNED"
    STRUCTURALLY_NON_COMPARABLE = "STRUCTURALLY_NON_COMPARABLE"
    BUSINESS_CLASSIFICATION_UNAVAILABLE = "BUSINESS_CLASSIFICATION_UNAVAILABLE"
    BUSINESS_CLASSIFICATION_CONFLICTED = "BUSINESS_CLASSIFICATION_CONFLICTED"


@dataclass(frozen=True, slots=True)
class PortfolioHoldingObservation:
    """Descriptive association state for one retained portfolio holding."""

    holding_id: str
    canonical_instrument_id: str | None
    state: PortfolioObservationState
    reasons: tuple[PortfolioObservationReason, ...]
    lifecycle_id: str | None = None
    lifecycle_fingerprint: str | None = None
    lifecycle_as_of: datetime | None = None
    lifecycle_state: LongTermThesisLifecycleState | None = None

    def __post_init__(self) -> None:
        _validate_holding_observation(self)


@dataclass(frozen=True, slots=True)
class PortfolioCashObservation:
    """Cash is preserved as a valid allocation, never as an equity thesis."""

    cash_state: CashState
    state: PortfolioObservationState = PortfolioObservationState.NOT_APPLICABLE
    reasons: tuple[PortfolioObservationReason, ...] = (
        PortfolioObservationReason.CASH_IS_VALID_ALLOCATION,
    )

    def __post_init__(self) -> None:
        if (not isinstance(self.cash_state, CashState)
                or self.state is not PortfolioObservationState.NOT_APPLICABLE
                or self.reasons != (PortfolioObservationReason.CASH_IS_VALID_ALLOCATION,)):
            raise LongTermPortfolioObservationError("PORTFOLIO_OBSERVATION_CASH_CONTRACT_INVALID")


@dataclass(frozen=True, slots=True)
class LongTermPortfolioObservationResearchShadow:
    """Immutable on-demand portfolio-to-lifecycle provenance projection."""

    portfolio_snapshot_id: str
    portfolio_id: str
    snapshot_as_of: datetime
    holdings: tuple[PortfolioHoldingObservation, ...]
    cash: PortfolioCashObservation
    observation_id: str = field(init=False)
    fingerprint: str = field(init=False)
    contract_version: str = CONTRACT_VERSION
    actionability: str = "WATCH_ONLY"
    execution_status: str = "NON_EXECUTABLE"
    research_status: str = "RESEARCH_SHADOW_V1"

    def __post_init__(self) -> None:
        _validate_result(self)
        object.__setattr__(self, "observation_id", "long-term-portfolio-observation:" + _hash(_identity(self))[:24])
        object.__setattr__(self, "fingerprint", "sha256:" + _hash(_payload(self)))

    def verify(self) -> None:
        _validate_result(self)
        if self.observation_id != "long-term-portfolio-observation:" + _hash(_identity(self))[:24]:
            raise LongTermPortfolioObservationError("PORTFOLIO_OBSERVATION_IDENTITY_MISMATCH")
        if self.fingerprint != "sha256:" + _hash(_payload(self)):
            raise LongTermPortfolioObservationError("PORTFOLIO_OBSERVATION_FINGERPRINT_MISMATCH")


def observe_long_term_portfolio_research_shadow(
    snapshot: PortfolioSnapshot,
    lifecycle_receipts: tuple[LongTermThesisInvalidationResearchShadow, ...] = (),
) -> LongTermPortfolioObservationResearchShadow:
    """Associate only exact, verified, non-future lifecycle receipts.

    There is intentionally no repository lookup or implicit latest receipt.
    Callers must supply the immutable receipts that are in scope for this
    read-only evaluation.
    """
    _validate_snapshot(snapshot)
    receipts = _canonical_receipts(lifecycle_receipts)
    observations = tuple(
        _observe_holding(holding, snapshot.as_of_timestamp, receipts)
        for holding in snapshot.holdings
    )
    return LongTermPortfolioObservationResearchShadow(
        portfolio_snapshot_id=snapshot.snapshot_id,
        portfolio_id=snapshot.portfolio_id,
        snapshot_as_of=_utc(snapshot.as_of_timestamp),
        holdings=tuple(sorted(observations, key=lambda value: value.holding_id)),
        cash=PortfolioCashObservation(snapshot.cash.cash_state),
    )


def portfolio_observation_payload(value: LongTermPortfolioObservationResearchShadow) -> dict[str, object]:
    value.verify()
    return _payload(value) | {"fingerprint": value.fingerprint}


def serialize_long_term_portfolio_observation(value: LongTermPortfolioObservationResearchShadow) -> str:
    return json.dumps(portfolio_observation_payload(value), sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _observe_holding(
    holding: PortfolioHolding,
    snapshot_as_of: datetime,
    receipts: tuple[LongTermThesisInvalidationResearchShadow, ...],
) -> PortfolioHoldingObservation:
    if not _valid_id(holding.instrument_id):
        return PortfolioHoldingObservation(
            holding.holding_id,
            None,
            PortfolioObservationState.IDENTITY_UNAVAILABLE,
            (PortfolioObservationReason.CANONICAL_INSTRUMENT_IDENTITY_UNAVAILABLE,),
        )

    matching = tuple(value for value in receipts if _receipt_instrument(value) == holding.instrument_id)
    eligible = tuple(value for value in matching if _receipt_as_of(value) <= _utc(snapshot_as_of))
    if not eligible:
        reason = (
            PortfolioObservationReason.FUTURE_LIFECYCLE_RECEIPT_EXCLUDED
            if matching else PortfolioObservationReason.LIFECYCLE_RECEIPT_UNAVAILABLE
        )
        return PortfolioHoldingObservation(
            holding.holding_id,
            holding.instrument_id,
            PortfolioObservationState.LIFECYCLE_RECEIPT_UNAVAILABLE,
            (reason,),
        )
    if len(eligible) != 1:
        return PortfolioHoldingObservation(
            holding.holding_id,
            holding.instrument_id,
            PortfolioObservationState.LIFECYCLE_RECEIPT_AMBIGUOUS,
            (PortfolioObservationReason.LIFECYCLE_SELECTION_UNGOVERNED,),
        )

    receipt = eligible[0]
    state, reasons = _associated_state(receipt)
    return PortfolioHoldingObservation(
        holding.holding_id,
        holding.instrument_id,
        state,
        reasons,
        receipt.lifecycle_id,
        receipt.fingerprint,
        _receipt_as_of(receipt),
        receipt.state,
    )


def _associated_state(
    receipt: LongTermThesisInvalidationResearchShadow,
) -> tuple[PortfolioObservationState, tuple[PortfolioObservationReason, ...]]:
    branches = frozenset(str(value.business_branch) for value in receipt.shadows)
    if len(branches) != 1:
        return (PortfolioObservationState.EVIDENCE_CONFLICTED, (
            PortfolioObservationReason.BUSINESS_CLASSIFICATION_CONFLICTED,
        ))
    branch = next(iter(branches))
    if branch == "STRUCTURALLY_NON_COMPARABLE":
        return (PortfolioObservationState.NON_COMPARABLE, (
            PortfolioObservationReason.STRUCTURALLY_NON_COMPARABLE,
        ))
    if branch == "UNKNOWN":
        return (PortfolioObservationState.NOT_APPLICABLE, (
            PortfolioObservationReason.BUSINESS_CLASSIFICATION_UNAVAILABLE,
        ))
    mapping = {
        LongTermThesisLifecycleState.DATA_INSUFFICIENT: (
            PortfolioObservationState.DATA_INSUFFICIENT,
            PortfolioObservationReason.LIFECYCLE_DATA_INSUFFICIENT,
        ),
        LongTermThesisLifecycleState.EVIDENCE_CONFLICTED: (
            PortfolioObservationState.EVIDENCE_CONFLICTED,
            PortfolioObservationReason.LIFECYCLE_EVIDENCE_CONFLICTED,
        ),
        LongTermThesisLifecycleState.POLICY_DEFINITION_MISSING: (
            PortfolioObservationState.POLICY_DEFINITION_MISSING,
            PortfolioObservationReason.LIFECYCLE_POLICY_DEFINITION_MISSING,
        ),
        LongTermThesisLifecycleState.NOT_APPLICABLE: (
            PortfolioObservationState.NOT_APPLICABLE,
            PortfolioObservationReason.LIFECYCLE_NOT_APPLICABLE,
        ),
    }
    state, reason = mapping[receipt.state]
    return state, (reason,)


def _canonical_receipts(
    values: tuple[LongTermThesisInvalidationResearchShadow, ...],
) -> tuple[LongTermThesisInvalidationResearchShadow, ...]:
    if not isinstance(values, tuple) or not all(isinstance(value, LongTermThesisInvalidationResearchShadow) for value in values):
        raise LongTermPortfolioObservationError("PORTFOLIO_OBSERVATION_LIFECYCLES_INVALID")
    for value in values:
        try:
            value.verify()
        except ValueError as error:
            raise LongTermPortfolioObservationError("PORTFOLIO_OBSERVATION_LIFECYCLE_UNVERIFIABLE") from error
    keys = tuple((value.lifecycle_id, value.fingerprint) for value in values)
    if len(set(keys)) != len(keys) or len({value.lifecycle_id for value in values}) != len(values):
        raise LongTermPortfolioObservationError("PORTFOLIO_OBSERVATION_LIFECYCLE_DUPLICATE")
    return tuple(sorted(values, key=lambda value: (
        _receipt_instrument(value), _time(_receipt_as_of(value)), value.lifecycle_id, value.fingerprint,
    )))


def _validate_snapshot(snapshot: PortfolioSnapshot) -> None:
    if not isinstance(snapshot, PortfolioSnapshot):
        raise LongTermPortfolioObservationError("PORTFOLIO_OBSERVATION_SNAPSHOT_INVALID")
    _require_id(snapshot.snapshot_id, "PORTFOLIO_OBSERVATION_SNAPSHOT_ID_INVALID")
    _require_id(snapshot.portfolio_id, "PORTFOLIO_OBSERVATION_PORTFOLIO_ID_INVALID")
    as_of = _utc(snapshot.as_of_timestamp)
    if _utc(snapshot.source_transaction_cutoff) > as_of:
        raise LongTermPortfolioObservationError("PORTFOLIO_OBSERVATION_SOURCE_CUTOFF_AFTER_SNAPSHOT")
    if not isinstance(snapshot.cash, CashPosition) or _utc(snapshot.cash.as_of_timestamp) > as_of:
        raise LongTermPortfolioObservationError("PORTFOLIO_OBSERVATION_CASH_TIMING_INVALID")
    if not isinstance(snapshot.holdings, tuple) or not all(isinstance(value, PortfolioHolding) for value in snapshot.holdings):
        raise LongTermPortfolioObservationError("PORTFOLIO_OBSERVATION_HOLDINGS_INVALID")
    holding_ids = tuple(value.holding_id for value in snapshot.holdings)
    if not all(_valid_id(value) for value in holding_ids) or len(set(holding_ids)) != len(holding_ids):
        raise LongTermPortfolioObservationError("PORTFOLIO_OBSERVATION_HOLDING_IDENTITY_INVALID")


def _validate_holding_observation(value: PortfolioHoldingObservation) -> None:
    _require_id(value.holding_id, "PORTFOLIO_OBSERVATION_HOLDING_ID_INVALID")
    if not isinstance(value.state, PortfolioObservationState):
        raise LongTermPortfolioObservationError("PORTFOLIO_OBSERVATION_STATE_INVALID")
    if (not isinstance(value.reasons, tuple)
            or value.reasons != tuple(sorted(set(value.reasons), key=lambda item: item.value))
            or not value.reasons
            or not all(isinstance(item, PortfolioObservationReason) for item in value.reasons)):
        raise LongTermPortfolioObservationError("PORTFOLIO_OBSERVATION_REASONS_INVALID")

    associated = value.lifecycle_id is not None
    lifecycle_fields = (value.lifecycle_id, value.lifecycle_fingerprint, value.lifecycle_as_of, value.lifecycle_state)
    if associated:
        if any(item is None for item in lifecycle_fields):
            raise LongTermPortfolioObservationError("PORTFOLIO_OBSERVATION_LIFECYCLE_PROVENANCE_INVALID")
        _require_id(value.lifecycle_id, "PORTFOLIO_OBSERVATION_LIFECYCLE_ID_INVALID")
        _require_fingerprint(value.lifecycle_fingerprint, "PORTFOLIO_OBSERVATION_LIFECYCLE_FINGERPRINT_INVALID")
        _utc(value.lifecycle_as_of)
        if not isinstance(value.lifecycle_state, LongTermThesisLifecycleState):
            raise LongTermPortfolioObservationError("PORTFOLIO_OBSERVATION_LIFECYCLE_STATE_INVALID")
        _require_id(value.canonical_instrument_id, "PORTFOLIO_OBSERVATION_INSTRUMENT_ID_INVALID")
    elif any(item is not None for item in lifecycle_fields):
        raise LongTermPortfolioObservationError("PORTFOLIO_OBSERVATION_LIFECYCLE_PROVENANCE_INVALID")

    expected = {
        PortfolioObservationState.IDENTITY_UNAVAILABLE: (
            None,
            False,
            (PortfolioObservationReason.CANONICAL_INSTRUMENT_IDENTITY_UNAVAILABLE,),
        ),
        PortfolioObservationState.LIFECYCLE_RECEIPT_UNAVAILABLE: (
            "instrument",
            False,
            (PortfolioObservationReason.LIFECYCLE_RECEIPT_UNAVAILABLE,),
        ),
        PortfolioObservationState.LIFECYCLE_RECEIPT_AMBIGUOUS: (
            "instrument",
            False,
            (PortfolioObservationReason.LIFECYCLE_SELECTION_UNGOVERNED,),
        ),
    }.get(value.state)
    if expected is not None:
        instrument, requires_lifecycle, reasons = expected
        allowed_reasons = (
            reasons,
            (PortfolioObservationReason.FUTURE_LIFECYCLE_RECEIPT_EXCLUDED,),
        ) if value.state is PortfolioObservationState.LIFECYCLE_RECEIPT_UNAVAILABLE else (reasons,)
        if value.reasons not in allowed_reasons:
            raise LongTermPortfolioObservationError("PORTFOLIO_OBSERVATION_STATE_REASON_CONTRADICTION")
        if instrument is None and value.canonical_instrument_id is not None:
            raise LongTermPortfolioObservationError("PORTFOLIO_OBSERVATION_STATE_REASON_CONTRADICTION")
        if instrument == "instrument":
            _require_id(value.canonical_instrument_id, "PORTFOLIO_OBSERVATION_INSTRUMENT_ID_INVALID")
        if associated is not requires_lifecycle:
            raise LongTermPortfolioObservationError("PORTFOLIO_OBSERVATION_STATE_REASON_CONTRADICTION")
    elif not associated:
        raise LongTermPortfolioObservationError("PORTFOLIO_OBSERVATION_LIFECYCLE_PROVENANCE_INVALID")
    else:
        expected_associated = {
            PortfolioObservationState.DATA_INSUFFICIENT: (
                LongTermThesisLifecycleState.DATA_INSUFFICIENT,
                PortfolioObservationReason.LIFECYCLE_DATA_INSUFFICIENT,
            ),
            PortfolioObservationState.POLICY_DEFINITION_MISSING: (
                LongTermThesisLifecycleState.POLICY_DEFINITION_MISSING,
                PortfolioObservationReason.LIFECYCLE_POLICY_DEFINITION_MISSING,
            ),
            PortfolioObservationState.NOT_APPLICABLE: (
                LongTermThesisLifecycleState.NOT_APPLICABLE,
                PortfolioObservationReason.LIFECYCLE_NOT_APPLICABLE,
            ),
            PortfolioObservationState.NON_COMPARABLE: (
                LongTermThesisLifecycleState.NOT_APPLICABLE,
                PortfolioObservationReason.STRUCTURALLY_NON_COMPARABLE,
            ),
        }.get(value.state)
        if expected_associated is not None:
            required_lifecycle_state, required_reason = expected_associated
            if value.lifecycle_state is not required_lifecycle_state or value.reasons not in (
                (required_reason,),
                (PortfolioObservationReason.BUSINESS_CLASSIFICATION_UNAVAILABLE,),
            ):
                raise LongTermPortfolioObservationError("PORTFOLIO_OBSERVATION_STATE_REASON_CONTRADICTION")
        elif value.state is PortfolioObservationState.EVIDENCE_CONFLICTED:
            if value.reasons == (PortfolioObservationReason.LIFECYCLE_EVIDENCE_CONFLICTED,):
                if value.lifecycle_state is not LongTermThesisLifecycleState.EVIDENCE_CONFLICTED:
                    raise LongTermPortfolioObservationError("PORTFOLIO_OBSERVATION_STATE_REASON_CONTRADICTION")
            elif value.reasons != (PortfolioObservationReason.BUSINESS_CLASSIFICATION_CONFLICTED,):
                raise LongTermPortfolioObservationError("PORTFOLIO_OBSERVATION_STATE_REASON_CONTRADICTION")


def _validate_result(value: LongTermPortfolioObservationResearchShadow) -> None:
    _require_id(value.portfolio_snapshot_id, "PORTFOLIO_OBSERVATION_SNAPSHOT_ID_INVALID")
    _require_id(value.portfolio_id, "PORTFOLIO_OBSERVATION_PORTFOLIO_ID_INVALID")
    _utc(value.snapshot_as_of)
    if (not isinstance(value.holdings, tuple)
            or not all(isinstance(item, PortfolioHoldingObservation) for item in value.holdings)
            or value.holdings != tuple(sorted(value.holdings, key=lambda item: item.holding_id))
            or len({item.holding_id for item in value.holdings}) != len(value.holdings)):
        raise LongTermPortfolioObservationError("PORTFOLIO_OBSERVATION_HOLDINGS_NONCANONICAL")
    for item in value.holdings:
        if item.lifecycle_as_of is not None and _utc(item.lifecycle_as_of) > _utc(value.snapshot_as_of):
            raise LongTermPortfolioObservationError("PORTFOLIO_OBSERVATION_FUTURE_LIFECYCLE_ASSOCIATION")
    if not isinstance(value.cash, PortfolioCashObservation):
        raise LongTermPortfolioObservationError("PORTFOLIO_OBSERVATION_CASH_CONTRACT_INVALID")
    if (value.contract_version, value.actionability, value.execution_status, value.research_status) != (
        CONTRACT_VERSION, "WATCH_ONLY", "NON_EXECUTABLE", "RESEARCH_SHADOW_V1",
    ):
        raise LongTermPortfolioObservationError("PORTFOLIO_OBSERVATION_BOUNDARY_INVALID")


def _receipt_instrument(value: LongTermThesisInvalidationResearchShadow) -> str:
    return value.shadows[0].source_receipt.source_review.canonical_instrument_id


def _receipt_as_of(value: LongTermThesisInvalidationResearchShadow) -> datetime:
    return _utc(value.shadows[0].source_receipt.source_review.context.as_of)


def _identity(value: LongTermPortfolioObservationResearchShadow) -> dict[str, object]:
    return {
        "contract": value.contract_version,
        "portfolio_snapshot_id": value.portfolio_snapshot_id,
        "portfolio_id": value.portfolio_id,
        "snapshot_as_of": _time(value.snapshot_as_of),
        "holdings": tuple(_holding_identity(item) for item in value.holdings),
        "cash_state": value.cash.cash_state.value,
    }


def _payload(value: LongTermPortfolioObservationResearchShadow) -> dict[str, object]:
    return _identity(value) | {
        "holdings": tuple(_holding_payload(item) for item in value.holdings),
        "cash": {
            "cash_state": value.cash.cash_state.value,
            "state": value.cash.state.value,
            "reasons": tuple(reason.value for reason in value.cash.reasons),
        },
        "observation_id": value.observation_id,
        "actionability": value.actionability,
        "execution_status": value.execution_status,
        "research_status": value.research_status,
    }


def _holding_identity(value: PortfolioHoldingObservation) -> dict[str, object]:
    return {
        "holding_id": value.holding_id,
        "instrument": value.canonical_instrument_id,
        "lifecycle_id": value.lifecycle_id,
        "lifecycle_fingerprint": value.lifecycle_fingerprint,
        "lifecycle_as_of": _time(value.lifecycle_as_of) if value.lifecycle_as_of else None,
    }


def _holding_payload(value: PortfolioHoldingObservation) -> dict[str, object]:
    return _holding_identity(value) | {
        "state": value.state.value,
        "lifecycle_state": value.lifecycle_state.value if value.lifecycle_state else None,
        "reasons": tuple(reason.value for reason in value.reasons),
    }


def _valid_id(value: object) -> bool:
    return isinstance(value, str) and bool(_ID.fullmatch(value))


def _require_id(value: object, code: str) -> None:
    if not _valid_id(value):
        raise LongTermPortfolioObservationError(code)


def _require_fingerprint(value: object, code: str) -> None:
    if not isinstance(value, str) or not _FINGERPRINT.fullmatch(value):
        raise LongTermPortfolioObservationError(code)


def _utc(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise LongTermPortfolioObservationError("PORTFOLIO_OBSERVATION_TIMESTAMP_INVALID")
    return value.astimezone(UTC)


def _time(value: datetime) -> str:
    return _utc(value).isoformat()


def _hash(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    ).hexdigest()


__all__ = (
    "CONTRACT_VERSION", "LongTermPortfolioObservationError",
    "LongTermPortfolioObservationResearchShadow", "PortfolioCashObservation",
    "PortfolioHoldingObservation", "PortfolioObservationReason", "PortfolioObservationState",
    "observe_long_term_portfolio_research_shadow", "portfolio_observation_payload",
    "serialize_long_term_portfolio_observation",
)
