"""Pure, PIT-safe readiness receipts for unapproved Long-Term Thesis families."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
import hashlib
import json
import re

from app.intelligence.long_term_thesis_review import (
    LongTermThesisFamily,
    LongTermThesisReview,
    ThesisPolicyAvailability,
    ThesisReviewState,
)

CONTRACT_VERSION = "long-term-thesis-research-shadow/v1"
FINGERPRINT_SCHEME = "long-term-thesis-research-shadow/sha256/v1"
_ID = re.compile(r"[A-Za-z0-9._:-]+")
_FP = re.compile(r"sha256:[0-9a-f]{64}")


class LongTermResearchShadowError(ValueError):
    pass


class ResearchShadowCoverageState(StrEnum):
    AVAILABLE = "AVAILABLE"
    UNAVAILABLE = "UNAVAILABLE"
    STALE = "STALE"
    CONFLICTED = "CONFLICTED"
    NON_COMPARABLE = "NON_COMPARABLE"


class LongTermResearchShadowState(StrEnum):
    DATA_INSUFFICIENT = "DATA_INSUFFICIENT"
    CONFLICTED = "CONFLICTED"
    TEMPORALLY_INVALID = "TEMPORALLY_INVALID"
    UNVERIFIABLE = "UNVERIFIABLE"
    POLICY_UNAVAILABLE = "POLICY_UNAVAILABLE"


class LongTermCoverageDomain(StrEnum):
    COMPARABLE_FINANCIAL_PERIODS = "COMPARABLE_FINANCIAL_PERIODS"
    GOVERNANCE_RELIABILITY = "GOVERNANCE_RELIABILITY"
    REVIEW_AND_SHADOW_LINEAGE = "REVIEW_AND_SHADOW_LINEAGE"
    RETURN_ON_CAPITAL_OR_EQUITY = "RETURN_ON_CAPITAL_OR_EQUITY"
    CASH_CONVERSION = "CASH_CONVERSION"
    LEVERAGE_OR_INTEREST_COVERAGE = "LEVERAGE_OR_INTEREST_COVERAGE"
    VALUATION_COMPARABILITY = "VALUATION_COMPARABILITY"
    REVENUE_AND_PROFIT_PERIODS = "REVENUE_AND_PROFIT_PERIODS"
    MARGIN_OR_OPERATING_LEVERAGE = "MARGIN_OR_OPERATING_LEVERAGE"
    WORKING_CAPITAL = "WORKING_CAPITAL"
    DEBT_TRAJECTORY = "DEBT_TRAJECTORY"
    COMPARABLE_BASELINE = "COMPARABLE_BASELINE"
    CONFIRMING_PERIODS = "CONFIRMING_PERIODS"
    RESTATEMENT_SELECTION = "RESTATEMENT_SELECTION"
    EXCEPTIONAL_ITEM_TREATMENT = "EXCEPTIONAL_ITEM_TREATMENT"
    PRIMARY_POLICY_EVIDENCE = "PRIMARY_POLICY_EVIDENCE"
    EXACT_EXPOSURE = "EXACT_EXPOSURE"
    LEGAL_OR_RULE_STAGE = "LEGAL_OR_RULE_STAGE"
    FUNDING_STAGE = "FUNDING_STAGE"
    TENDER_OR_ORDER_STAGE = "TENDER_OR_ORDER_STAGE"
    CAPACITY_STAGE = "CAPACITY_STAGE"
    EXECUTION_STAGE = "EXECUTION_STAGE"
    REVENUE_STAGE = "REVENUE_STAGE"
    CASH_FLOW_STAGE = "CASH_FLOW_STAGE"
    CANCELLATION_OR_SUPERSESSION = "CANCELLATION_OR_SUPERSESSION"
    GROWTH_PATH = "GROWTH_PATH"
    DILUTION = "DILUTION"
    LIQUIDITY = "LIQUIDITY"
    BALANCE_SHEET = "BALANCE_SHEET"
    SURVIVORSHIP_SHADOW = "SURVIVORSHIP_SHADOW"


class LongTermResearchShadowReason(StrEnum):
    SOURCE_REVIEW_UNVERIFIABLE = "SOURCE_REVIEW_UNVERIFIABLE"
    SOURCE_REVIEW_NOT_PIT_VALID = "SOURCE_REVIEW_NOT_PIT_VALID"
    COVERAGE_AFTER_AS_OF = "COVERAGE_AFTER_AS_OF"
    COVERAGE_CONFLICTED = "COVERAGE_CONFLICTED"
    COVERAGE_UNAVAILABLE = "COVERAGE_UNAVAILABLE"
    COVERAGE_STALE = "COVERAGE_STALE"
    COVERAGE_NON_COMPARABLE = "COVERAGE_NON_COMPARABLE"
    REQUIRED_COVERAGE_MISSING = "REQUIRED_COVERAGE_MISSING"
    FAMILY_POLICY_UNAVAILABLE = "FAMILY_POLICY_UNAVAILABLE"


_REQUIRED_DOMAINS: dict[LongTermThesisFamily, frozenset[LongTermCoverageDomain]] = {
    LongTermThesisFamily.QUALITY_FAIR_VALUE: frozenset((
        LongTermCoverageDomain.COMPARABLE_FINANCIAL_PERIODS,
        LongTermCoverageDomain.GOVERNANCE_RELIABILITY,
        LongTermCoverageDomain.REVIEW_AND_SHADOW_LINEAGE,
        LongTermCoverageDomain.RETURN_ON_CAPITAL_OR_EQUITY,
        LongTermCoverageDomain.CASH_CONVERSION,
        LongTermCoverageDomain.LEVERAGE_OR_INTEREST_COVERAGE,
        LongTermCoverageDomain.VALUATION_COMPARABILITY,
    )),
    LongTermThesisFamily.FUNDAMENTAL_COMPOUNDER: frozenset((
        LongTermCoverageDomain.GOVERNANCE_RELIABILITY,
        LongTermCoverageDomain.REVIEW_AND_SHADOW_LINEAGE,
        LongTermCoverageDomain.REVENUE_AND_PROFIT_PERIODS,
        LongTermCoverageDomain.MARGIN_OR_OPERATING_LEVERAGE,
        LongTermCoverageDomain.CASH_CONVERSION,
        LongTermCoverageDomain.WORKING_CAPITAL,
        LongTermCoverageDomain.DEBT_TRAJECTORY,
    )),
    LongTermThesisFamily.FUNDAMENTAL_INFLECTION: frozenset((
        LongTermCoverageDomain.GOVERNANCE_RELIABILITY,
        LongTermCoverageDomain.REVIEW_AND_SHADOW_LINEAGE,
        LongTermCoverageDomain.COMPARABLE_BASELINE,
        LongTermCoverageDomain.CONFIRMING_PERIODS,
        LongTermCoverageDomain.RESTATEMENT_SELECTION,
        LongTermCoverageDomain.EXCEPTIONAL_ITEM_TREATMENT,
    )),
    LongTermThesisFamily.POLICY_TRANSMISSION: frozenset((
        LongTermCoverageDomain.REVIEW_AND_SHADOW_LINEAGE,
        LongTermCoverageDomain.PRIMARY_POLICY_EVIDENCE,
        LongTermCoverageDomain.EXACT_EXPOSURE,
        LongTermCoverageDomain.LEGAL_OR_RULE_STAGE,
        LongTermCoverageDomain.FUNDING_STAGE,
        LongTermCoverageDomain.TENDER_OR_ORDER_STAGE,
        LongTermCoverageDomain.CAPACITY_STAGE,
        LongTermCoverageDomain.EXECUTION_STAGE,
        LongTermCoverageDomain.REVENUE_STAGE,
        LongTermCoverageDomain.CASH_FLOW_STAGE,
        LongTermCoverageDomain.CANCELLATION_OR_SUPERSESSION,
    )),
    LongTermThesisFamily.ASYMMETRIC_EMERGING_COMPOUNDER: frozenset((
        LongTermCoverageDomain.GOVERNANCE_RELIABILITY,
        LongTermCoverageDomain.REVIEW_AND_SHADOW_LINEAGE,
        LongTermCoverageDomain.GROWTH_PATH,
        LongTermCoverageDomain.DILUTION,
        LongTermCoverageDomain.LIQUIDITY,
        LongTermCoverageDomain.BALANCE_SHEET,
        LongTermCoverageDomain.VALUATION_COMPARABILITY,
        LongTermCoverageDomain.SURVIVORSHIP_SHADOW,
    )),
}


@dataclass(frozen=True, slots=True)
class LongTermCoverageObservation:
    domain: LongTermCoverageDomain
    state: ResearchShadowCoverageState
    reference_id: str
    fingerprint: str
    available_at: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.domain, LongTermCoverageDomain):
            raise LongTermResearchShadowError("THESIS_SHADOW_DOMAIN_INVALID")
        if not isinstance(self.state, ResearchShadowCoverageState):
            raise LongTermResearchShadowError("THESIS_SHADOW_COVERAGE_STATE_INVALID")
        _id(self.reference_id, "THESIS_SHADOW_REFERENCE_ID_INVALID")
        _fingerprint(self.fingerprint, "THESIS_SHADOW_REFERENCE_FINGERPRINT_INVALID")
        _aware(self.available_at, "THESIS_SHADOW_REFERENCE_TIMESTAMP_INVALID")


@dataclass(frozen=True, slots=True)
class LongTermThesisResearchShadow:
    source_review: LongTermThesisReview
    state: LongTermResearchShadowState
    coverage: tuple[LongTermCoverageObservation, ...]
    blockers: tuple[LongTermResearchShadowReason, ...]
    receipt_id: str = field(init=False)
    fingerprint: str = field(init=False)
    contract_version: str = CONTRACT_VERSION
    actionability: str = "WATCH_ONLY"
    execution_status: str = "NON_EXECUTABLE"

    def __post_init__(self) -> None:
        _validate(self)
        object.__setattr__(self, "receipt_id", "long-term-shadow:" + _hash(_identity(self))[:24])
        object.__setattr__(self, "fingerprint", "sha256:" + _hash(_payload(self)))

    def verify(self) -> None:
        _validate(self)
        if self.receipt_id != "long-term-shadow:" + _hash(_identity(self))[:24]:
            raise LongTermResearchShadowError("THESIS_SHADOW_IDENTITY_MISMATCH")
        if self.fingerprint != "sha256:" + _hash(_payload(self)):
            raise LongTermResearchShadowError("THESIS_SHADOW_FINGERPRINT_MISMATCH")


def review_long_term_research_shadow(
    source_review: LongTermThesisReview,
    coverage: tuple[LongTermCoverageObservation, ...],
) -> LongTermThesisResearchShadow:
    if not isinstance(source_review, LongTermThesisReview):
        raise LongTermResearchShadowError("THESIS_SHADOW_SOURCE_REVIEW_INVALID")
    try:
        source_review.verify()
    except ValueError:
        return LongTermThesisResearchShadow(source_review, LongTermResearchShadowState.UNVERIFIABLE, _canonical_coverage(coverage), (LongTermResearchShadowReason.SOURCE_REVIEW_UNVERIFIABLE,))
    canonical = _canonical_coverage(coverage)
    if not {value.domain for value in canonical}.issubset(_REQUIRED_DOMAINS[source_review.family]):
        raise LongTermResearchShadowError("THESIS_SHADOW_COVERAGE_DOMAIN_UNSUPPORTED")
    if source_review.review_state is not ThesisReviewState.DOSSIER_OBSERVED or source_review.policy_availability is not ThesisPolicyAvailability.POLICY_UNAVAILABLE:
        return LongTermThesisResearchShadow(source_review, LongTermResearchShadowState.DATA_INSUFFICIENT, canonical, (LongTermResearchShadowReason.SOURCE_REVIEW_NOT_PIT_VALID,))
    as_of = source_review.context.as_of
    if any(_utc(value.available_at) > _utc(as_of) for value in canonical):
        return LongTermThesisResearchShadow(source_review, LongTermResearchShadowState.TEMPORALLY_INVALID, canonical, (LongTermResearchShadowReason.COVERAGE_AFTER_AS_OF,))
    required = _REQUIRED_DOMAINS[source_review.family]
    domains = {value.domain for value in canonical}
    if not required.issubset(domains):
        return LongTermThesisResearchShadow(source_review, LongTermResearchShadowState.DATA_INSUFFICIENT, canonical, (LongTermResearchShadowReason.REQUIRED_COVERAGE_MISSING,))
    selected = tuple(value for value in canonical if value.domain in required)
    if any(value.state is ResearchShadowCoverageState.CONFLICTED for value in selected):
        return LongTermThesisResearchShadow(source_review, LongTermResearchShadowState.CONFLICTED, canonical, (LongTermResearchShadowReason.COVERAGE_CONFLICTED,))
    reasons = tuple(sorted({
        LongTermResearchShadowReason.COVERAGE_UNAVAILABLE if value.state is ResearchShadowCoverageState.UNAVAILABLE else
        LongTermResearchShadowReason.COVERAGE_STALE if value.state is ResearchShadowCoverageState.STALE else
        LongTermResearchShadowReason.COVERAGE_NON_COMPARABLE
        for value in selected if value.state is not ResearchShadowCoverageState.AVAILABLE
    }, key=lambda value: value.value))
    if reasons:
        return LongTermThesisResearchShadow(source_review, LongTermResearchShadowState.DATA_INSUFFICIENT, canonical, reasons)
    return LongTermThesisResearchShadow(source_review, LongTermResearchShadowState.POLICY_UNAVAILABLE, canonical, (LongTermResearchShadowReason.FAMILY_POLICY_UNAVAILABLE,))


def research_shadow_payload(value: LongTermThesisResearchShadow) -> dict[str, object]:
    value.verify()
    return _payload(value) | {"fingerprint": value.fingerprint}


def serialize_research_shadow(value: LongTermThesisResearchShadow) -> str:
    return json.dumps(research_shadow_payload(value), sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def required_coverage_domains(family: LongTermThesisFamily) -> tuple[LongTermCoverageDomain, ...]:
    if not isinstance(family, LongTermThesisFamily):
        raise LongTermResearchShadowError("THESIS_SHADOW_FAMILY_INVALID")
    return tuple(sorted(_REQUIRED_DOMAINS[family], key=lambda value: value.value))


def _validate(value: LongTermThesisResearchShadow) -> None:
    if not isinstance(value.source_review, LongTermThesisReview) or not isinstance(value.state, LongTermResearchShadowState):
        raise LongTermResearchShadowError("THESIS_SHADOW_CONTRACT_INVALID")
    _canonical_coverage(value.coverage)
    if value.coverage != _canonical_coverage(value.coverage):
        raise LongTermResearchShadowError("THESIS_SHADOW_COVERAGE_NONCANONICAL")
    if not {item.domain for item in value.coverage}.issubset(_REQUIRED_DOMAINS[value.source_review.family]):
        raise LongTermResearchShadowError("THESIS_SHADOW_COVERAGE_DOMAIN_UNSUPPORTED")
    if value.blockers != tuple(sorted(set(value.blockers), key=lambda item: item.value)) or not all(isinstance(item, LongTermResearchShadowReason) for item in value.blockers):
        raise LongTermResearchShadowError("THESIS_SHADOW_BLOCKERS_NONCANONICAL")
    if value.contract_version != CONTRACT_VERSION or value.actionability != "WATCH_ONLY" or value.execution_status != "NON_EXECUTABLE":
        raise LongTermResearchShadowError("THESIS_SHADOW_BOUNDARY_INVALID")
    expected = {
        LongTermResearchShadowState.UNVERIFIABLE: (LongTermResearchShadowReason.SOURCE_REVIEW_UNVERIFIABLE,),
        LongTermResearchShadowState.DATA_INSUFFICIENT: None,
        LongTermResearchShadowState.CONFLICTED: (LongTermResearchShadowReason.COVERAGE_CONFLICTED,),
        LongTermResearchShadowState.TEMPORALLY_INVALID: (LongTermResearchShadowReason.COVERAGE_AFTER_AS_OF,),
        LongTermResearchShadowState.POLICY_UNAVAILABLE: (LongTermResearchShadowReason.FAMILY_POLICY_UNAVAILABLE,),
    }[value.state]
    if expected is not None and value.blockers != expected:
        raise LongTermResearchShadowError("THESIS_SHADOW_STATE_BLOCKER_CONTRADICTION")
    if value.state is LongTermResearchShadowState.DATA_INSUFFICIENT and not value.blockers:
        raise LongTermResearchShadowError("THESIS_SHADOW_STATE_BLOCKER_CONTRADICTION")


def _canonical_coverage(values: tuple[LongTermCoverageObservation, ...]) -> tuple[LongTermCoverageObservation, ...]:
    if not values or not all(isinstance(value, LongTermCoverageObservation) for value in values):
        raise LongTermResearchShadowError("THESIS_SHADOW_COVERAGE_INVALID")
    if len({value.domain for value in values}) != len(values):
        raise LongTermResearchShadowError("THESIS_SHADOW_COVERAGE_DOMAIN_DUPLICATE")
    if len({value.reference_id for value in values}) != len(values):
        raise LongTermResearchShadowError("THESIS_SHADOW_COVERAGE_REFERENCE_DUPLICATE")
    return tuple(sorted(values, key=lambda value: (value.domain.value, value.reference_id, value.fingerprint, _time(value.available_at))))


def _identity(value: LongTermThesisResearchShadow) -> dict[str, object]:
    source = value.source_review
    return {
        "contract": value.contract_version,
        "family": source.family.value,
        "instrument": source.canonical_instrument_id,
        "as_of": _time(source.context.as_of),
        "review_id": source.review_id,
        "review_fingerprint": source.fingerprint,
        "coverage": tuple(_coverage(item) for item in value.coverage),
    }


def _payload(value: LongTermThesisResearchShadow) -> dict[str, object]:
    return _identity(value) | {
        "state": value.state.value,
        "blockers": tuple(item.value for item in value.blockers),
        "receipt_id": value.receipt_id,
        "actionability": value.actionability,
        "execution_status": value.execution_status,
    }


def _coverage(value: LongTermCoverageObservation) -> dict[str, str]:
    return {"domain": value.domain.value, "state": value.state.value, "id": value.reference_id, "fingerprint": value.fingerprint, "available_at": _time(value.available_at)}


def _id(value: str, code: str) -> None:
    if not isinstance(value, str) or not _ID.fullmatch(value):
        raise LongTermResearchShadowError(code)


def _fingerprint(value: str, code: str) -> None:
    if not isinstance(value, str) or not _FP.fullmatch(value):
        raise LongTermResearchShadowError(code)


def _aware(value: datetime, code: str) -> None:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise LongTermResearchShadowError(code)


def _utc(value: datetime) -> datetime:
    _aware(value, "THESIS_SHADOW_TIMESTAMP_INVALID")
    return value.astimezone(UTC)


def _time(value: datetime) -> str:
    return _utc(value).isoformat()


def _hash(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()).hexdigest()
