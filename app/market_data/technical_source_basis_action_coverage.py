"""Pure source-basis and action-coverage decisions for technical evidence.

This module decides only whether supplied source semantics and corporate-action
coverage can support a technical *continuity* claim.  It neither fetches nor
stores data, transforms a price, builds a bar, calculates an indicator, or
creates a signal.  In particular, an HSI no-transformation fact is kept
separate from a provider's documented price basis.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from hashlib import sha256
import json
import re

from app.historical.security_master import CorporateActionKind, HistoricalCorporateAction
from app.market_data.models import Timeframe
from app.market_data.technical_price_adjustment_integrity import ProviderPriceBasisState


CONTRACT_ID = "canonical-technical-source-basis-and-action-coverage-decision"
CONTRACT_VERSION = "v1"
POLICY_ID = "technical-source-basis-action-coverage"
POLICY_VERSION = "v1"
_ID = re.compile(r"[A-Za-z0-9._:-]+\Z")
_FP = re.compile(r"sha256:[0-9a-f]{64}\Z")
_CONTINUITY_KINDS = frozenset({
    CorporateActionKind.SPLIT,
    CorporateActionKind.BONUS,
    CorporateActionKind.RIGHTS,
    CorporateActionKind.DIVIDEND,
    CorporateActionKind.MERGER,
    CorporateActionKind.DEMERGER,
    CorporateActionKind.SYMBOL_CHANGE,
    CorporateActionKind.DELISTING,
    CorporateActionKind.SUSPENSION,
    CorporateActionKind.RELISTING,
})


class TechnicalSourceBasisCoverageError(ValueError):
    """Stable fail-closed error for a malformed source/coverage decision."""


class SourceBasisReadiness(StrEnum):
    READY = "READY"
    PARTIAL = "PARTIAL"
    NOT_READY = "NOT_READY"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class HsiTransformationState(StrEnum):
    HSI_DID_NOT_ADJUST = "HSI_DID_NOT_ADJUST"
    HSI_DERIVED_VERSIONED_ARTIFACT = "HSI_DERIVED_VERSIONED_ARTIFACT"


class SourceBasisReason(StrEnum):
    OFFICIAL_BASIS_NOT_DOCUMENTED = "OFFICIAL_BASIS_NOT_DOCUMENTED"
    HSI_NO_TRANSFORMATION_DOES_NOT_PROVE_RAW = "HSI_NO_TRANSFORMATION_DOES_NOT_PROVE_RAW"
    DHAN_DAILY_SPLIT_BONUS_ADJUSTED = "DHAN_DAILY_SPLIT_BONUS_ADJUSTED"
    PROVIDER_ADJUSTMENT_METHOD_UNVERIFIED = "PROVIDER_ADJUSTMENT_METHOD_UNVERIFIED"
    LIVE_OBSERVATION_BASIS_NOT_DOCUMENTED = "LIVE_OBSERVATION_BASIS_NOT_DOCUMENTED"
    PROSPECTIVE_IMMUTABLE_BAR_CAPTURE_NOT_IMPLEMENTED = "PROSPECTIVE_IMMUTABLE_BAR_CAPTURE_NOT_IMPLEMENTED"
    INDEX_METHOD_SOURCE_SPECIFIC = "INDEX_METHOD_SOURCE_SPECIFIC"


class CorporateActionCoverageState(StrEnum):
    READY = "READY"
    PARTIAL = "PARTIAL"
    NOT_READY = "NOT_READY"


class CorporateActionCoverageReason(StrEnum):
    OFFICIAL_SOURCE_WINDOW_COMPLETE = "OFFICIAL_SOURCE_WINDOW_COMPLETE"
    SOURCE_WINDOW_PARTIAL = "SOURCE_WINDOW_PARTIAL"
    SOURCE_WINDOW_NOT_ESTABLISHED = "SOURCE_WINDOW_NOT_ESTABLISHED"
    SOURCE_COVERAGE_NOT_KNOWN_AS_OF = "SOURCE_COVERAGE_NOT_KNOWN_AS_OF"
    REQUIRED_ACTION_FAMILIES_INCOMPLETE = "REQUIRED_ACTION_FAMILIES_INCOMPLETE"


class ActionFreeWindowState(StrEnum):
    NO_KNOWN_PRICE_DISCONTINUITY_WITHIN_WINDOW = "NO_KNOWN_PRICE_DISCONTINUITY_WITHIN_WINDOW"
    KNOWN_SPLIT_BONUS_REQUIRES_DERIVATION_GATE = "KNOWN_SPLIT_BONUS_REQUIRES_DERIVATION_GATE"
    NON_COMPARABLE_ACROSS_WINDOW = "NON_COMPARABLE_ACROSS_WINDOW"
    NOT_CERTIFIED = "NOT_CERTIFIED"


class ActionFreeWindowReason(StrEnum):
    COVERAGE_NOT_COMPLETE = "COVERAGE_NOT_COMPLETE"
    COVERAGE_NOT_KNOWN_AS_OF = "COVERAGE_NOT_KNOWN_AS_OF"
    EXACT_INSTRUMENT_MISMATCH = "EXACT_INSTRUMENT_MISMATCH"
    ACTION_NOT_KNOWN_AS_OF = "ACTION_NOT_KNOWN_AS_OF"
    ACTION_EFFECTIVE_AFTER_AS_OF = "ACTION_EFFECTIVE_AFTER_AS_OF"
    DUPLICATE_ACTION_ID = "DUPLICATE_ACTION_ID"
    SPLIT_BONUS_ACTION_IN_WINDOW = "SPLIT_BONUS_ACTION_IN_WINDOW"
    RIGHTS_OR_COMPLEX_ACTION_IN_WINDOW = "RIGHTS_OR_COMPLEX_ACTION_IN_WINDOW"
    CASH_DISTRIBUTION_POLICY_UNAVAILABLE = "CASH_DISTRIBUTION_POLICY_UNAVAILABLE"


class TechnicalWindowReadiness(StrEnum):
    READY = "READY"
    NOT_READY = "NOT_READY"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class TechnicalWindowReason(StrEnum):
    SOURCE_BASIS_UNKNOWN = "SOURCE_BASIS_UNKNOWN"
    PROVIDER_ADJUSTMENT_METHOD_UNVERIFIED = "PROVIDER_ADJUSTMENT_METHOD_UNVERIFIED"
    ACTION_WINDOW_NOT_CERTIFIED = "ACTION_WINDOW_NOT_CERTIFIED"
    SOURCE_BASIS_NOT_READY = "SOURCE_BASIS_NOT_READY"


@dataclass(frozen=True, slots=True)
class SourceBasisEvidence:
    """A stable local reference to an authoritative source-semantic statement.

    Its fingerprint is of this contract's exact reference tuple, not a claim to
    hash a remote provider page or to freeze an external website.
    """

    evidence_id: str
    evidence_fingerprint: str
    authoritative: bool

    def __post_init__(self) -> None:
        if not _ID.fullmatch(self.evidence_id) or not _FP.fullmatch(self.evidence_fingerprint):
            raise TechnicalSourceBasisCoverageError("SOURCE_BASIS_EVIDENCE_INVALID")


@dataclass(frozen=True, slots=True)
class TechnicalSourceBasisDecision:
    decision_id: str
    source_family: str
    source_version: str
    timeframe: Timeframe
    provider_basis: ProviderPriceBasisState
    hsi_transformation: HsiTransformationState
    supporting_evidence: tuple[SourceBasisEvidence, ...]
    historical_readiness: SourceBasisReadiness
    forward_readiness: SourceBasisReadiness
    reasons: tuple[SourceBasisReason, ...]
    fingerprint: str

    def __post_init__(self) -> None:
        evidence = tuple(sorted(self.supporting_evidence, key=lambda item: item.evidence_id))
        reasons = _sorted_unique(self.reasons)
        expected = _fingerprint(_source_payload(self, evidence, reasons))
        if (
            not _ID.fullmatch(self.decision_id)
            or not _ID.fullmatch(self.source_family)
            or not _ID.fullmatch(self.source_version)
            or not isinstance(self.timeframe, Timeframe)
            or not isinstance(self.provider_basis, ProviderPriceBasisState)
            or not isinstance(self.hsi_transformation, HsiTransformationState)
            or not isinstance(self.historical_readiness, SourceBasisReadiness)
            or not isinstance(self.forward_readiness, SourceBasisReadiness)
            or not evidence
            or self.supporting_evidence != evidence
            or len({item.evidence_id for item in evidence}) != len(evidence)
            or self.reasons != reasons
            or self.fingerprint != expected
            or (
                self.provider_basis is ProviderPriceBasisState.RAW
                and not any(item.authoritative for item in evidence)
            )
        ):
            raise TechnicalSourceBasisCoverageError("TECHNICAL_SOURCE_BASIS_DECISION_INVALID")


@dataclass(frozen=True, slots=True)
class CorporateActionCoverageAssertion:
    """A security/window-specific coverage assertion, never an absence inference."""

    coverage_id: str
    canonical_instrument_id: str
    window_start: datetime
    window_end: datetime
    source_known_at: datetime
    source_evidence: SourceBasisEvidence
    covered_action_kinds: tuple[CorporateActionKind, ...]
    coverage_state: CorporateActionCoverageState
    reasons: tuple[CorporateActionCoverageReason, ...]
    fingerprint: str

    def __post_init__(self) -> None:
        kinds = tuple(sorted(set(self.covered_action_kinds), key=lambda item: item.value))
        reasons = _sorted_unique(self.reasons)
        expected = _fingerprint(_coverage_payload(self, kinds, reasons))
        if (
            not _ID.fullmatch(self.coverage_id)
            or not _ID.fullmatch(self.canonical_instrument_id)
            or not _aware(self.window_start)
            or not _aware(self.window_end)
            or not _aware(self.source_known_at)
            or _utc(self.window_end) < _utc(self.window_start)
            or not isinstance(self.source_evidence, SourceBasisEvidence)
            or not isinstance(self.coverage_state, CorporateActionCoverageState)
            or not kinds
            or self.covered_action_kinds != kinds
            or self.reasons != reasons
            or self.fingerprint != expected
            or (
                self.coverage_state is CorporateActionCoverageState.READY
                and (
                    not self.source_evidence.authoritative
                    or not _CONTINUITY_KINDS.issubset(kinds)
                    or CorporateActionCoverageReason.OFFICIAL_SOURCE_WINDOW_COMPLETE not in reasons
                    or any(reason is not CorporateActionCoverageReason.OFFICIAL_SOURCE_WINDOW_COMPLETE for reason in reasons)
                )
            )
        ):
            raise TechnicalSourceBasisCoverageError("CORPORATE_ACTION_COVERAGE_ASSERTION_INVALID")


@dataclass(frozen=True, slots=True)
class ActionFreeWindowAssessment:
    assessment_id: str
    canonical_instrument_id: str
    window_start: datetime
    window_end: datetime
    as_of: datetime
    coverage_id: str
    coverage_fingerprint: str
    action_ids: tuple[str, ...]
    action_fingerprints: tuple[str, ...]
    state: ActionFreeWindowState
    reasons: tuple[ActionFreeWindowReason, ...]
    fingerprint: str

    def __post_init__(self) -> None:
        actions = tuple(sorted(zip(self.action_ids, self.action_fingerprints)))
        reasons = _sorted_unique(self.reasons)
        expected = _fingerprint(_window_payload(self, actions, reasons))
        action_free = self.state is ActionFreeWindowState.NO_KNOWN_PRICE_DISCONTINUITY_WITHIN_WINDOW
        if (
            not _ID.fullmatch(self.assessment_id)
            or not _ID.fullmatch(self.canonical_instrument_id)
            or not _ID.fullmatch(self.coverage_id)
            or not _FP.fullmatch(self.coverage_fingerprint)
            or not _aware(self.window_start)
            or not _aware(self.window_end)
            or not _aware(self.as_of)
            or _utc(self.window_end) < _utc(self.window_start)
            or tuple(zip(self.action_ids, self.action_fingerprints)) != actions
            or any(not _ID.fullmatch(identifier) or not _FP.fullmatch(fingerprint) for identifier, fingerprint in actions)
            or len({identifier for identifier, _ in actions}) != len(actions)
            or not isinstance(self.state, ActionFreeWindowState)
            or self.reasons != reasons
            or self.fingerprint != expected
            or (action_free and actions)
        ):
            raise TechnicalSourceBasisCoverageError("ACTION_FREE_WINDOW_ASSESSMENT_INVALID")


@dataclass(frozen=True, slots=True)
class TechnicalWindowSourceIntegrity:
    """Combines source-basis and action-window facts without calculating a rule."""

    integrity_id: str
    source_basis_decision_id: str
    source_basis_fingerprint: str
    action_window_assessment_id: str
    action_window_fingerprint: str
    readiness: TechnicalWindowReadiness
    reasons: tuple[TechnicalWindowReason, ...]
    fingerprint: str

    def __post_init__(self) -> None:
        reasons = _sorted_unique(self.reasons)
        expected = _fingerprint(_integrity_payload(self, reasons))
        if (
            not _ID.fullmatch(self.integrity_id)
            or not _ID.fullmatch(self.source_basis_decision_id)
            or not _FP.fullmatch(self.source_basis_fingerprint)
            or not _ID.fullmatch(self.action_window_assessment_id)
            or not _FP.fullmatch(self.action_window_fingerprint)
            or not isinstance(self.readiness, TechnicalWindowReadiness)
            or self.reasons != reasons
            or self.fingerprint != expected
            or (self.readiness is TechnicalWindowReadiness.READY and reasons)
        ):
            raise TechnicalSourceBasisCoverageError("TECHNICAL_WINDOW_SOURCE_INTEGRITY_INVALID")


def official_upstox_historical_v3_basis(*, timeframe: Timeframe) -> TechnicalSourceBasisDecision:
    """Official V3 docs specify OHLC/timeframe, not its adjustment semantics."""
    evidence = _evidence("upstox-historical-candle-v3-documentation")
    return _source_decision(
        source_family="upstox", source_version="upstox-history-v3", timeframe=timeframe,
        provider_basis=ProviderPriceBasisState.UNKNOWN,
        historical=SourceBasisReadiness.NOT_READY, forward=SourceBasisReadiness.NOT_READY,
        evidence=(evidence,), reasons=(
            SourceBasisReason.OFFICIAL_BASIS_NOT_DOCUMENTED,
            SourceBasisReason.HSI_NO_TRANSFORMATION_DOES_NOT_PROVE_RAW,
        ),
    )


def create_source_basis_decision(
    *, source_family: str, source_version: str, timeframe: Timeframe,
    provider_basis: ProviderPriceBasisState, historical_readiness: SourceBasisReadiness,
    forward_readiness: SourceBasisReadiness, supporting_evidence: tuple[SourceBasisEvidence, ...],
    reasons: tuple[SourceBasisReason, ...],
) -> TechnicalSourceBasisDecision:
    """Construct a source-bound decision from caller-supplied authoritative facts."""
    return _source_decision(
        source_family=source_family, source_version=source_version, timeframe=timeframe,
        provider_basis=provider_basis, historical=historical_readiness, forward=forward_readiness,
        evidence=supporting_evidence, reasons=reasons,
    )


def create_corporate_action_coverage_assertion(
    *, coverage_id: str, canonical_instrument_id: str, window_start: datetime,
    window_end: datetime, source_known_at: datetime, source_evidence: SourceBasisEvidence,
    covered_action_kinds: tuple[CorporateActionKind, ...], coverage_state: CorporateActionCoverageState,
    reasons: tuple[CorporateActionCoverageReason, ...],
) -> CorporateActionCoverageAssertion:
    """Construct an explicit source-window assertion; absence is never inferred."""
    kinds = tuple(sorted(set(covered_action_kinds), key=lambda item: item.value))
    actual_reasons = _sorted_unique(reasons)
    values = dict(
        coverage_id=coverage_id, canonical_instrument_id=canonical_instrument_id,
        window_start=_utc(window_start), window_end=_utc(window_end),
        source_known_at=_utc(source_known_at), source_evidence=source_evidence,
        covered_action_kinds=kinds, coverage_state=coverage_state, reasons=actual_reasons,
    )
    return CorporateActionCoverageAssertion(**values, fingerprint=_fingerprint(_coverage_payload_values(values)))


def official_dhan_daily_historical_basis() -> TechnicalSourceBasisDecision:
    """Dhan documents split/bonus adjustment, but not a canonical method contract."""
    evidence = _evidence("dhan-daily-historical-corporate-action-adjustment-documentation")
    return _source_decision(
        source_family="dhan", source_version="dhan-daily-historical-v1", timeframe=Timeframe.DAILY,
        provider_basis=ProviderPriceBasisState.PROVIDER_ADJUSTED_UNKNOWN_METHOD,
        historical=SourceBasisReadiness.PARTIAL, forward=SourceBasisReadiness.PARTIAL,
        evidence=(evidence,), reasons=(
            SourceBasisReason.DHAN_DAILY_SPLIT_BONUS_ADJUSTED,
            SourceBasisReason.PROVIDER_ADJUSTMENT_METHOD_UNVERIFIED,
        ),
    )


def official_nse_bhavcopy_basis() -> TechnicalSourceBasisDecision:
    evidence = _evidence("nse-full-bhavcopy-price-basis-documentation")
    return _source_decision(
        source_family="NSE_OFFICIAL", source_version="nse-full-bhavcopy-v1", timeframe=Timeframe.DAILY,
        provider_basis=ProviderPriceBasisState.UNKNOWN,
        historical=SourceBasisReadiness.NOT_READY, forward=SourceBasisReadiness.NOT_READY,
        evidence=(evidence,), reasons=(
            SourceBasisReason.OFFICIAL_BASIS_NOT_DOCUMENTED,
            SourceBasisReason.HSI_NO_TRANSFORMATION_DOES_NOT_PROVE_RAW,
        ),
    )


def dhan_live_forward_basis_readiness() -> TechnicalSourceBasisDecision:
    """Existing live state is in-memory LTP, not an immutable session-bar capture."""
    evidence = _evidence("dhan-live-market-feed-documentation")
    return _source_decision(
        source_family="dhan", source_version="dhan-live-feed-v2", timeframe=Timeframe.DAILY,
        provider_basis=ProviderPriceBasisState.UNKNOWN,
        historical=SourceBasisReadiness.NOT_APPLICABLE, forward=SourceBasisReadiness.PARTIAL,
        evidence=(evidence,), reasons=(
            SourceBasisReason.LIVE_OBSERVATION_BASIS_NOT_DOCUMENTED,
            SourceBasisReason.PROSPECTIVE_IMMUTABLE_BAR_CAPTURE_NOT_IMPLEMENTED,
        ),
    )


def assess_action_free_window(
    *, canonical_instrument_id: str, window_start: datetime, window_end: datetime,
    as_of: datetime, coverage: CorporateActionCoverageAssertion,
    actions: tuple[HistoricalCorporateAction, ...],
) -> ActionFreeWindowAssessment:
    """Certify an action-free window only from complete, PIT-visible coverage."""
    if (
        not _ID.fullmatch(canonical_instrument_id)
        or not _aware(window_start)
        or not _aware(window_end)
        or not _aware(as_of)
        or _utc(window_end) < _utc(window_start)
        or coverage.canonical_instrument_id != canonical_instrument_id
    ):
        raise TechnicalSourceBasisCoverageError("ACTION_FREE_WINDOW_INPUT_INVALID")
    start, end, at = _utc(window_start), _utc(window_end), _utc(as_of)
    reasons: list[ActionFreeWindowReason] = []
    selected: list[HistoricalCorporateAction] = []
    duplicate_ids: set[str] = set()
    seen: set[str] = set()
    for action in sorted(actions, key=lambda item: item.action_id):
        if action.action_id in seen:
            duplicate_ids.add(action.action_id)
            continue
        seen.add(action.action_id)
        if action.canonical_instrument_id != canonical_instrument_id:
            reasons.append(ActionFreeWindowReason.EXACT_INSTRUMENT_MISMATCH)
            continue
        if not _aware(action.as_of) or not _aware(action.effective_date):
            raise TechnicalSourceBasisCoverageError("CORPORATE_ACTION_TIMESTAMP_INVALID")
        if _utc(action.as_of) > at:
            reasons.append(ActionFreeWindowReason.ACTION_NOT_KNOWN_AS_OF)
            continue
        if _utc(action.effective_date) > at:
            reasons.append(ActionFreeWindowReason.ACTION_EFFECTIVE_AFTER_AS_OF)
            continue
        if start <= _utc(action.effective_date) <= end:
            selected.append(action)
    if duplicate_ids:
        reasons.append(ActionFreeWindowReason.DUPLICATE_ACTION_ID)
    coverage_complete = (
        coverage.coverage_state is CorporateActionCoverageState.READY
        and _utc(coverage.window_start) <= start
        and end <= _utc(coverage.window_end)
        and _utc(coverage.source_known_at) <= at
    )
    if coverage.coverage_state is not CorporateActionCoverageState.READY or not (
        _utc(coverage.window_start) <= start and end <= _utc(coverage.window_end)
    ):
        reasons.append(ActionFreeWindowReason.COVERAGE_NOT_COMPLETE)
    if _utc(coverage.source_known_at) > at:
        reasons.append(ActionFreeWindowReason.COVERAGE_NOT_KNOWN_AS_OF)
    fingerprints = tuple(_action_fingerprint(item) for item in selected)
    if duplicate_ids:
        state = ActionFreeWindowState.NOT_CERTIFIED
        selected = []
        fingerprints = ()
    elif any(
        item.kind in {
            CorporateActionKind.RIGHTS,
            CorporateActionKind.MERGER,
            CorporateActionKind.DEMERGER,
            CorporateActionKind.SYMBOL_CHANGE,
            CorporateActionKind.DELISTING,
            CorporateActionKind.SUSPENSION,
            CorporateActionKind.RELISTING,
        }
        for item in selected
    ):
        state = ActionFreeWindowState.NON_COMPARABLE_ACROSS_WINDOW
        reasons.append(ActionFreeWindowReason.RIGHTS_OR_COMPLEX_ACTION_IN_WINDOW)
    elif any(item.kind is CorporateActionKind.DIVIDEND for item in selected):
        state = ActionFreeWindowState.NON_COMPARABLE_ACROSS_WINDOW
        reasons.append(ActionFreeWindowReason.CASH_DISTRIBUTION_POLICY_UNAVAILABLE)
    elif selected:
        state = ActionFreeWindowState.KNOWN_SPLIT_BONUS_REQUIRES_DERIVATION_GATE
        reasons.append(ActionFreeWindowReason.SPLIT_BONUS_ACTION_IN_WINDOW)
    elif coverage_complete:
        state = ActionFreeWindowState.NO_KNOWN_PRICE_DISCONTINUITY_WITHIN_WINDOW
    else:
        state = ActionFreeWindowState.NOT_CERTIFIED
    action_ids = tuple(item.action_id for item in selected)
    action_pairs = tuple(sorted(zip(action_ids, fingerprints)))
    actual_reasons = _sorted_unique(reasons)
    values = dict(
        assessment_id=_identifier("action-free-window", {
            "instrument": canonical_instrument_id, "start": _time(start), "end": _time(end),
            "as_of": _time(at), "coverage": coverage.fingerprint,
            "actions": [fingerprint for _, fingerprint in action_pairs], "policy": POLICY_VERSION,
        }),
        canonical_instrument_id=canonical_instrument_id, window_start=start, window_end=end, as_of=at,
        coverage_id=coverage.coverage_id, coverage_fingerprint=coverage.fingerprint,
        action_ids=tuple(item[0] for item in action_pairs), action_fingerprints=tuple(item[1] for item in action_pairs),
        state=state, reasons=actual_reasons,
    )
    return ActionFreeWindowAssessment(**values, fingerprint=_fingerprint(_window_payload_values(values)))


def assess_technical_window_source_integrity(
    *, source_basis: TechnicalSourceBasisDecision,
    action_window: ActionFreeWindowAssessment,
) -> TechnicalWindowSourceIntegrity:
    """Unknown or undocumented provider basis is never promoted by a quiet window."""
    reasons: list[TechnicalWindowReason] = []
    if source_basis.provider_basis is ProviderPriceBasisState.UNKNOWN:
        reasons.append(TechnicalWindowReason.SOURCE_BASIS_UNKNOWN)
    elif source_basis.provider_basis is ProviderPriceBasisState.PROVIDER_ADJUSTED_UNKNOWN_METHOD:
        reasons.append(TechnicalWindowReason.PROVIDER_ADJUSTMENT_METHOD_UNVERIFIED)
    if source_basis.historical_readiness is not SourceBasisReadiness.READY:
        reasons.append(TechnicalWindowReason.SOURCE_BASIS_NOT_READY)
    if action_window.state is not ActionFreeWindowState.NO_KNOWN_PRICE_DISCONTINUITY_WITHIN_WINDOW:
        reasons.append(TechnicalWindowReason.ACTION_WINDOW_NOT_CERTIFIED)
    actual_reasons = _sorted_unique(reasons)
    values = dict(
        integrity_id=_identifier("technical-window-source-integrity", {
            "source": source_basis.fingerprint, "window": action_window.fingerprint, "policy": POLICY_VERSION,
        }),
        source_basis_decision_id=source_basis.decision_id, source_basis_fingerprint=source_basis.fingerprint,
        action_window_assessment_id=action_window.assessment_id, action_window_fingerprint=action_window.fingerprint,
        readiness=TechnicalWindowReadiness.READY if not actual_reasons else TechnicalWindowReadiness.NOT_READY,
        reasons=actual_reasons,
    )
    return TechnicalWindowSourceIntegrity(**values, fingerprint=_fingerprint(_integrity_payload_values(values)))


def serialize_source_basis_decision(value: TechnicalSourceBasisDecision) -> str:
    value.__post_init__()
    return _canonical(_source_payload(value, value.supporting_evidence, value.reasons) | {"fingerprint": value.fingerprint})


def serialize_action_free_window(value: ActionFreeWindowAssessment) -> str:
    value.__post_init__()
    return _canonical(_window_payload(value, tuple(zip(value.action_ids, value.action_fingerprints)), value.reasons) | {"fingerprint": value.fingerprint})


def _source_decision(*, source_family: str, source_version: str, timeframe: Timeframe, provider_basis: ProviderPriceBasisState, historical: SourceBasisReadiness, forward: SourceBasisReadiness, evidence: tuple[SourceBasisEvidence, ...], reasons: tuple[SourceBasisReason, ...]) -> TechnicalSourceBasisDecision:
    values = dict(
        decision_id=_identifier("technical-source-basis", {
            "source_family": source_family, "source_version": source_version, "timeframe": timeframe.value,
            "provider_basis": provider_basis.value, "evidence": [item.evidence_fingerprint for item in evidence],
            "policy": POLICY_VERSION,
        }),
        source_family=source_family, source_version=source_version, timeframe=timeframe,
        provider_basis=provider_basis, hsi_transformation=HsiTransformationState.HSI_DID_NOT_ADJUST,
        supporting_evidence=tuple(sorted(evidence, key=lambda item: item.evidence_id)),
        historical_readiness=historical, forward_readiness=forward, reasons=_sorted_unique(reasons),
    )
    return TechnicalSourceBasisDecision(**values, fingerprint=_fingerprint(_source_payload_values(values)))


def _evidence(evidence_id: str) -> SourceBasisEvidence:
    values = {"contract": CONTRACT_ID, "version": CONTRACT_VERSION, "evidence_id": evidence_id}
    return SourceBasisEvidence(evidence_id, _fingerprint(values), True)


def _action_fingerprint(value: HistoricalCorporateAction) -> str:
    return _fingerprint({
        "action_id": value.action_id, "instrument": value.canonical_instrument_id,
        "kind": value.kind.value, "effective_at": _time(value.effective_date),
        "known_at": _time(value.as_of), "source": value.source, "revision": value.revision,
        "source_reference": value.source_reference, "ratio_numerator": str(value.ratio_numerator),
        "ratio_denominator": str(value.ratio_denominator), "details": value.details,
    })


def _source_payload(value: TechnicalSourceBasisDecision, evidence: tuple[SourceBasisEvidence, ...], reasons: tuple[SourceBasisReason, ...]) -> dict[str, object]:
    return _source_payload_values({name: getattr(value, name) for name in TechnicalSourceBasisDecision.__dataclass_fields__ if name != "fingerprint"} | {"supporting_evidence": evidence, "reasons": reasons})


def _source_payload_values(value: dict[str, object]) -> dict[str, object]:
    return {
        "contract": CONTRACT_ID, "version": CONTRACT_VERSION, "decision_id": value["decision_id"],
        "source_family": value["source_family"], "source_version": value["source_version"],
        "timeframe": _enum(value["timeframe"]), "provider_basis": _enum(value["provider_basis"]),
        "hsi_transformation": _enum(value["hsi_transformation"]),
        "supporting_evidence": [{"id": item.evidence_id, "fingerprint": item.evidence_fingerprint, "authoritative": item.authoritative} for item in value["supporting_evidence"]],
        "historical_readiness": _enum(value["historical_readiness"]), "forward_readiness": _enum(value["forward_readiness"]),
        "reasons": [_enum(item) for item in value["reasons"]], "policy_id": POLICY_ID, "policy_version": POLICY_VERSION,
    }


def _coverage_payload(value: CorporateActionCoverageAssertion, kinds: tuple[CorporateActionKind, ...], reasons: tuple[CorporateActionCoverageReason, ...]) -> dict[str, object]:
    return _coverage_payload_values({name: getattr(value, name) for name in CorporateActionCoverageAssertion.__dataclass_fields__ if name != "fingerprint"} | {"covered_action_kinds": kinds, "reasons": reasons})


def _coverage_payload_values(value: dict[str, object]) -> dict[str, object]:
    evidence = value["source_evidence"]
    assert isinstance(evidence, SourceBasisEvidence)
    return {
        "contract": CONTRACT_ID, "version": CONTRACT_VERSION, "coverage_id": value["coverage_id"],
        "instrument": value["canonical_instrument_id"], "window_start": _time(value["window_start"]),
        "window_end": _time(value["window_end"]), "source_known_at": _time(value["source_known_at"]),
        "source_evidence": {"id": evidence.evidence_id, "fingerprint": evidence.evidence_fingerprint, "authoritative": evidence.authoritative},
        "covered_action_kinds": [item.value for item in value["covered_action_kinds"]], "coverage_state": _enum(value["coverage_state"]),
        "reasons": [_enum(item) for item in value["reasons"]], "policy_id": POLICY_ID, "policy_version": POLICY_VERSION,
    }


def _window_payload(value: ActionFreeWindowAssessment, actions: tuple[tuple[str, str], ...], reasons: tuple[ActionFreeWindowReason, ...]) -> dict[str, object]:
    return _window_payload_values({name: getattr(value, name) for name in ActionFreeWindowAssessment.__dataclass_fields__ if name != "fingerprint"} | {"action_ids": tuple(item[0] for item in actions), "action_fingerprints": tuple(item[1] for item in actions), "reasons": reasons})


def _window_payload_values(value: dict[str, object]) -> dict[str, object]:
    return {
        "contract": CONTRACT_ID, "version": CONTRACT_VERSION, "assessment_id": value["assessment_id"],
        "instrument": value["canonical_instrument_id"], "window_start": _time(value["window_start"]),
        "window_end": _time(value["window_end"]), "as_of": _time(value["as_of"]),
        "coverage_id": value["coverage_id"], "coverage_fingerprint": value["coverage_fingerprint"],
        "actions": [{"id": identifier, "fingerprint": fingerprint} for identifier, fingerprint in zip(value["action_ids"], value["action_fingerprints"], strict=True)],
        "state": _enum(value["state"]), "reasons": [_enum(item) for item in value["reasons"]],
        "policy_id": POLICY_ID, "policy_version": POLICY_VERSION,
    }


def _integrity_payload(value: TechnicalWindowSourceIntegrity, reasons: tuple[TechnicalWindowReason, ...]) -> dict[str, object]:
    return _integrity_payload_values({name: getattr(value, name) for name in TechnicalWindowSourceIntegrity.__dataclass_fields__ if name != "fingerprint"} | {"reasons": reasons})


def _integrity_payload_values(value: dict[str, object]) -> dict[str, object]:
    return {
        "contract": CONTRACT_ID, "version": CONTRACT_VERSION, "integrity_id": value["integrity_id"],
        "source_basis": {"id": value["source_basis_decision_id"], "fingerprint": value["source_basis_fingerprint"]},
        "action_window": {"id": value["action_window_assessment_id"], "fingerprint": value["action_window_fingerprint"]},
        "readiness": _enum(value["readiness"]), "reasons": [_enum(item) for item in value["reasons"]],
        "policy_id": POLICY_ID, "policy_version": POLICY_VERSION,
    }


def _identifier(prefix: str, value: object) -> str:
    return prefix + ":" + sha256(_canonical(value).encode()).hexdigest()[:24]


def _sorted_unique(values):
    return tuple(sorted(set(values), key=lambda item: item.value))


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _fingerprint(value: object) -> str:
    return "sha256:" + sha256(_canonical(value).encode()).hexdigest()


def _aware(value: object) -> bool:
    return isinstance(value, datetime) and value.tzinfo is not None and value.utcoffset() is not None


def _utc(value: datetime) -> datetime:
    if not _aware(value):
        raise TechnicalSourceBasisCoverageError("TECHNICAL_SOURCE_BASIS_TIMESTAMP_AWARE_REQUIRED")
    return value.astimezone(UTC)


def _time(value: datetime) -> str:
    return _utc(value).isoformat()


def _enum(value: object) -> str:
    return value.value if isinstance(value, StrEnum) else str(value)


__all__ = (
    "ActionFreeWindowAssessment", "ActionFreeWindowReason", "ActionFreeWindowState",
    "CONTRACT_ID", "CONTRACT_VERSION", "CorporateActionCoverageAssertion",
    "CorporateActionCoverageReason", "CorporateActionCoverageState", "HsiTransformationState",
    "POLICY_ID", "POLICY_VERSION", "SourceBasisEvidence", "SourceBasisReadiness",
    "SourceBasisReason", "TechnicalSourceBasisCoverageError", "TechnicalSourceBasisDecision",
    "TechnicalWindowReadiness", "TechnicalWindowReason", "TechnicalWindowSourceIntegrity",
    "assess_action_free_window", "assess_technical_window_source_integrity",
    "create_corporate_action_coverage_assertion", "create_source_basis_decision",
    "dhan_live_forward_basis_readiness", "official_dhan_daily_historical_basis",
    "official_nse_bhavcopy_basis", "official_upstox_historical_v3_basis",
    "serialize_action_free_window", "serialize_source_basis_decision",
)
