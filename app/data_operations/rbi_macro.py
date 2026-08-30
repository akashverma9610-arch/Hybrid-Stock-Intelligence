"""Official RBI current-rates acquisition for raw Macro evidence only.

This adapter intentionally preserves raw values and does not infer the
descriptive MacroState enums (for example, ``TIGHTENING`` or ``WEAKENING``).
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from html import unescape
import re
from zoneinfo import ZoneInfo

import requests

from app.data_operations.models import (
    EvidenceRefreshFailureKind,
    EvidenceRefreshMode,
    EvidenceRefreshOutcome,
    EvidenceRefreshRequest,
    EvidenceRefreshStatus,
)
from app.historical.guard import manifest_fingerprint
from app.intelligence.macro import (
    IntelligenceSourceTier,
    MacroEvidence,
    MacroInputFamily,
    MacroObservationFrequency,
)
from app.intelligence.macro.store import MacroEvidenceStore, MacroEvidenceWriteOutcome


RBI_CURRENT_RATES_URL = "https://m.rbi.org.in/"
RBI_CURRENT_RATES_PROVIDER = "RBI_OFFICIAL_CURRENT_RATES"
_IST = ZoneInfo("Asia/Kolkata")
_HEADERS = {
    "Accept": "text/html,application/xhtml+xml",
    "User-Agent": "HSI-NSE-Stock-Manager/1.0 (+local official macro refresh)",
}


class RbiMacroSourceError(RuntimeError):
    """Public-safe official-source acquisition failure."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True, slots=True)
class RbiCurrentRate:
    component: str
    family: MacroInputFamily
    value: Decimal
    unit: str
    frequency: MacroObservationFrequency
    observed_at: datetime | None
    effective_at: datetime | None
    warnings: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RbiCurrentRatesResponse:
    values: tuple[RbiCurrentRate, ...]
    source_reference: str
    source_artifact_fingerprint: str


class RbiCurrentRatesSource:
    """One bounded public RBI current-rates request; no credentials required."""

    def __init__(self, *, session: requests.Session | None = None, timeout_seconds: int = 15) -> None:
        self._session = session or requests.Session()
        self._timeout_seconds = timeout_seconds

    def fetch(self) -> RbiCurrentRatesResponse:
        try:
            response = self._session.get(RBI_CURRENT_RATES_URL, headers=_HEADERS, timeout=self._timeout_seconds)
        except requests.RequestException as error:
            raise RbiMacroSourceError("SOURCE_UNAVAILABLE") from error
        if response.status_code == 429:
            raise RbiMacroSourceError("RATE_LIMITED")
        if response.status_code != 200:
            raise RbiMacroSourceError("HTTP_ERROR")
        content_type = response.headers.get("Content-Type", "")
        if "html" not in content_type.lower() or not response.text.strip():
            raise RbiMacroSourceError("INVALID_RESPONSE")
        try:
            values = _parse_current_rates(response.text)
        except ValueError as error:
            raise RbiMacroSourceError("PARSE_ERROR") from error
        return RbiCurrentRatesResponse(
            values=values,
            source_reference=RBI_CURRENT_RATES_URL,
            source_artifact_fingerprint=sha256(response.content).hexdigest(),
        )


class RbiCurrentRatesRefreshJob:
    """U17 adapter: append raw official values and retain first-observed PIT."""

    def __init__(self, *, source: RbiCurrentRatesSource, store: MacroEvidenceStore, clock=lambda: datetime.now(UTC)) -> None:
        self._source, self._store, self._clock = source, store, clock

    def refresh(self, request: EvidenceRefreshRequest) -> EvidenceRefreshOutcome:
        try:
            response = self._source.fetch()
        except RbiMacroSourceError as error:
            return EvidenceRefreshOutcome(
                EvidenceRefreshStatus.SOURCE_UNAVAILABLE,
                RBI_CURRENT_RATES_PROVIDER,
                failure_kind=EvidenceRefreshFailureKind.TRANSIENT,
                error_summary=error.code,
                warnings=(error.code,),
                source_references=(RBI_CURRENT_RATES_URL,),
            )
        received_at = self._clock()
        existing = self._store.list_all()
        accepted = duplicates = 0
        accepted_through: datetime | None = None
        for item in response.values:
            current = _evidence(item, response, received_at, existing)
            previous = _matching_existing(current, existing)
            if previous is not None:
                # The source page also contains other current-rate rows, so a
                # changed page artifact alone is not a revision of this exact
                # series observation.  Preserve its first observed artifact.
                current = previous
            elif (prior := _latest_component(current.component, existing)) is not None:
                current = replace(current, revision_of=prior.evidence_id)
            outcome = self._store.save(current)
            if outcome is MacroEvidenceWriteOutcome.INSERTED:
                accepted += 1
                accepted_through = max(accepted_through or current.available_at, current.available_at)
            else:
                duplicates += 1
                accepted_through = max(accepted_through or current.available_at, current.available_at)
        status = EvidenceRefreshStatus.COMPLETE if accepted else EvidenceRefreshStatus.NO_CHANGE
        return EvidenceRefreshOutcome(
            status,
            RBI_CURRENT_RATES_PROVIDER,
            discovered_count=len(response.values),
            accepted_count=accepted,
            duplicate_count=duplicates,
            accepted_through=accepted_through,
            source_fingerprint=response.source_artifact_fingerprint,
            verified_from_store=accepted_through is not None,
            warnings=("RAW_MACRO_VALUES_NO_DIRECTIONAL_STATE_MAPPING",),
            source_references=(response.source_reference,),
        )


def _evidence(
    value: RbiCurrentRate,
    source: RbiCurrentRatesResponse,
    received_at: datetime,
    existing: tuple[MacroEvidence, ...],
) -> MacroEvidence:
    # Identity is source series + exact reported value.  A changed official
    # value becomes an immutable revision rather than overwriting a vintage.
    evidence_id = "rbi-current-rates:" + manifest_fingerprint(
        component=value.component, value=str(value.value), unit=value.unit,
        observed_at=value.observed_at,
    )[:24]
    return MacroEvidence(
        evidence_id=evidence_id,
        family=value.family,
        component=value.component,
        state="RAW_OBSERVATION",
        source_tier=IntelligenceSourceTier.OFFICIAL,
        source_reference=source.source_reference,
        observed_at=value.observed_at,
        published_at=None,
        available_at=received_at,
        effective_at=value.effective_at,
        reliability=1.0,
        freshness="FRESH",
        warnings=tuple(sorted({"SOURCE_PUBLICATION_TIMESTAMP_UNKNOWN_FIRST_OBSERVED", *value.warnings})),
        value=value.value,
        unit=value.unit,
        frequency=value.frequency,
        source_artifact_fingerprint=source.source_artifact_fingerprint,
        received_at=received_at,
    )


def _matching_existing(value: MacroEvidence, values: tuple[MacroEvidence, ...]) -> MacroEvidence | None:
    return next((item for item in values if item.evidence_id == value.evidence_id), None)


def _latest_component(component: str, values: tuple[MacroEvidence, ...]) -> MacroEvidence | None:
    candidates = tuple(item for item in values if item.component == component)
    return max(candidates, key=lambda item: (item.available_at, item.evidence_id), default=None)


def _parse_current_rates(payload: str) -> tuple[RbiCurrentRate, ...]:
    text = _normalise_text(payload)
    # RBI's mobile and desktop rendering differ only in the optional table
    # separator.  Both are the same official labelled field, not fuzzy text.
    repo = _decimal(_match(text, r"Policy\s+Repo\s+Rate\s*(?:\|\s*)?:\s*([0-9]+(?:\.[0-9]+)?)\s*%"))
    inr_usd = _decimal(_match(text, r"INR\s*/\s*1\s*USD\s*(?:\|\s*)?:\s*([0-9]+(?:\.[0-9]+)?)"))
    as_at = _as_at(text)
    values = [RbiCurrentRate(
        "policy_repo_rate", MacroInputFamily.MONETARY_RATES, repo, "PERCENT",
        MacroObservationFrequency.EVENT, None, None,
        ("RBI_CURRENT_RATE_EFFECTIVE_TIME_NOT_PUBLISHED",),
    )]
    values.append(RbiCurrentRate(
        "inr_usd_reference_rate", MacroInputFamily.FX_EXTERNAL, inr_usd, "INR_PER_USD",
        MacroObservationFrequency.DAILY, as_at, as_at,
        ("RBI_SOURCE_DATE_TIME_UNKNOWN",),
    ))
    return tuple(values)


def _normalise_text(value: str) -> str:
    return " ".join(unescape(re.sub(r"<[^>]+>", " ", value)).replace("\xa0", " ").split())


def _match(value: str, pattern: str) -> str:
    found = re.search(pattern, value, flags=re.IGNORECASE)
    if found is None:
        raise ValueError("RBI_CURRENT_RATES_FIELD_MISSING")
    return found.group(1)


def _decimal(value: str) -> Decimal:
    try:
        return Decimal(value)
    except InvalidOperation as error:
        raise ValueError("RBI_CURRENT_RATES_VALUE_INVALID") from error


def _as_at(value: str) -> datetime:
    found = re.search(r"As\s+at\s+(?:[0-9.:]+\s*(?:am|pm)\s+of\s+)?([A-Za-z]+\s+\d{1,2},\s+\d{4})", value, flags=re.IGNORECASE)
    if found is None:
        raise ValueError("RBI_CURRENT_RATES_AS_AT_MISSING")
    try:
        return datetime.strptime(found.group(1), "%B %d, %Y").replace(tzinfo=_IST).astimezone(UTC)
    except ValueError as error:
        raise ValueError("RBI_CURRENT_RATES_AS_AT_INVALID") from error


__all__ = (
    "RBI_CURRENT_RATES_PROVIDER", "RBI_CURRENT_RATES_URL", "RbiCurrentRate",
    "RbiCurrentRatesRefreshJob", "RbiCurrentRatesResponse", "RbiCurrentRatesSource",
    "RbiMacroSourceError",
)
