"""Versioned, source-family facts for daily-bar temporal interpretation.

This is deliberately a pure interpretation boundary.  It neither rewrites a
stored OHLCV bar nor makes a daily bar complete, market-known, or PIT-usable.
Those decisions remain with ``daily_technical_bar_temporal_evidence`` and the
canonical session calendar.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from enum import StrEnum
from hashlib import sha256
import json
import re
from zoneinfo import ZoneInfo

from app.market_data.models import CanonicalOHLCVBar, Timeframe


CONTRACT_ID = "canonical-daily-source-session-and-publication-semantics"
CONTRACT_VERSION = "v1"
_ID = re.compile(r"[A-Za-z0-9._:-]+\Z")
_FP = re.compile(r"sha256:[0-9a-f]{64}\Z")


class DailySourceTimestampRole(StrEnum):
    """A raw source timestamp's factual role, never an inferred known-at."""

    INTERVAL_START = "INTERVAL_START"
    INTERVAL_END = "INTERVAL_END"
    TRADING_DATE = "TRADING_DATE"
    SOURCE_PUBLICATION_TIME = "SOURCE_PUBLICATION_TIME"
    SOURCE_DISSEMINATION_TIME = "SOURCE_DISSEMINATION_TIME"
    PROVIDER_OBSERVED_TIME = "PROVIDER_OBSERVED_TIME"
    HSI_INGESTED_TIME = "HSI_INGESTED_TIME"
    UNKNOWN = "UNKNOWN"


class DailySourceAvailabilityState(StrEnum):
    """Availability and HSI observation have intentionally distinct states."""

    SOURCE_AVAILABILITY_RESOLVED = "SOURCE_AVAILABILITY_RESOLVED"
    HSI_OBSERVED_AT_ONLY = "HSI_OBSERVED_AT_ONLY"
    HISTORICAL_KNOWN_AT_UNAVAILABLE = "HISTORICAL_KNOWN_AT_UNAVAILABLE"
    SOURCE_TIMING_UNRESOLVED = "SOURCE_TIMING_UNRESOLVED"


class DailySourceLegacyState(StrEnum):
    """Applicability of the source interpretation to a retained record."""

    SOURCE_SEMANTICS_RESOLVED = "SOURCE_SEMANTICS_RESOLVED"
    LEGACY_SEMANTICS_AMBIGUOUS = "LEGACY_SEMANTICS_AMBIGUOUS"
    SOURCE_SEMANTICS_CONFLICTED = "SOURCE_SEMANTICS_CONFLICTED"


@dataclass(frozen=True, slots=True)
class DailySourceTemporalSemantics:
    """Source-contract facts for one provider/version/daily normalization path.

    ``supporting_reference_fingerprint`` fingerprints the stable reference
    tuple below; it is explicitly not a claim to hash an externally downloaded
    provider document.  This keeps the contract reproducible without inventing
    immutable document bytes that the repository did not retain.
    """

    source_family: str
    source_version: str
    interval: Timeframe
    raw_timestamp_role: DailySourceTimestampRole
    source_timezone_id: str | None
    session_date_from_raw_timestamp: bool
    source_publication_time_available: bool
    hsi_observed_at_fallback_permitted: bool
    historical_applicability: DailySourceLegacyState
    forward_applicability: DailySourceLegacyState
    policy_id: str
    policy_version: str
    supporting_evidence_id: str
    supporting_reference: str
    supporting_reference_fingerprint: str

    def __post_init__(self) -> None:
        if (
            not _ID.fullmatch(self.source_family)
            or not _ID.fullmatch(self.source_version)
            or self.interval is not Timeframe.DAILY
            or not isinstance(self.raw_timestamp_role, DailySourceTimestampRole)
            or self.source_timezone_id not in {None, "Asia/Kolkata"}
            or not _ID.fullmatch(self.policy_id)
            or not _ID.fullmatch(self.policy_version)
            or not _ID.fullmatch(self.supporting_evidence_id)
            or not self.supporting_reference.startswith("https://")
            or not _FP.fullmatch(self.supporting_reference_fingerprint)
            or self.supporting_reference_fingerprint
            != _reference_fingerprint(self.supporting_evidence_id, self.supporting_reference)
            or self.raw_timestamp_role is DailySourceTimestampRole.UNKNOWN and self.session_date_from_raw_timestamp
            or self.source_publication_time_available
            and self.raw_timestamp_role is DailySourceTimestampRole.UNKNOWN
        ):
            raise ValueError("DAILY_SOURCE_TEMPORAL_SEMANTICS_INVALID")

    @property
    def fingerprint(self) -> str:
        return _fingerprint(_semantics_payload(self))


@dataclass(frozen=True, slots=True)
class DailySourceTemporalFacts:
    """One bar's factual source-time interpretation.

    ``source_available_at`` stays ``None`` unless the source itself supplied a
    verifiable finished-bar availability/publication instant.  ``hsi_observed``
    is an immutable provenance receipt and can be forward-safe only; it never
    backdates the bar's historical market availability.
    """

    source_family: str
    source_version: str
    raw_timestamp: datetime | None
    raw_timestamp_role: DailySourceTimestampRole
    session_date: date | None
    source_available_at: datetime | None
    hsi_observed_at: datetime
    availability_state: DailySourceAvailabilityState
    legacy_state: DailySourceLegacyState
    policy_id: str
    policy_fingerprint: str
    fingerprint: str

    def __post_init__(self) -> None:
        expected = _fingerprint(_facts_payload(self))
        if (
            not _ID.fullmatch(self.source_family)
            or not _ID.fullmatch(self.source_version)
            or not isinstance(self.raw_timestamp_role, DailySourceTimestampRole)
            or not isinstance(self.availability_state, DailySourceAvailabilityState)
            or not isinstance(self.legacy_state, DailySourceLegacyState)
            or self.raw_timestamp is not None and not _aware(self.raw_timestamp)
            or self.raw_timestamp_role is DailySourceTimestampRole.UNKNOWN and self.session_date is not None
            or self.source_available_at is not None and not _aware(self.source_available_at)
            or not _aware(self.hsi_observed_at)
            or not _ID.fullmatch(self.policy_id)
            or not _FP.fullmatch(self.policy_fingerprint)
            or self.fingerprint != expected
            or self.availability_state is DailySourceAvailabilityState.SOURCE_AVAILABILITY_RESOLVED
            and self.source_available_at is None
            or self.availability_state is not DailySourceAvailabilityState.SOURCE_AVAILABILITY_RESOLVED
            and self.source_available_at is not None
        ):
            raise ValueError("DAILY_SOURCE_TEMPORAL_FACTS_INVALID")

    @property
    def forward_known_at(self) -> datetime | None:
        """A source fact or conservative HSI receipt; never a historical claim."""
        if self.legacy_state is not DailySourceLegacyState.SOURCE_SEMANTICS_RESOLVED:
            return None
        if self.availability_state is DailySourceAvailabilityState.SOURCE_AVAILABILITY_RESOLVED:
            return self.source_available_at
        if self.availability_state is DailySourceAvailabilityState.HSI_OBSERVED_AT_ONLY:
            return self.hsi_observed_at
        return None


def upstox_v3_daily_legacy_semantics() -> DailySourceTemporalSemantics:
    """Retained V3 path: raw start survives, but canonical end is mislabelled."""
    return _semantics(
        "upstox", "upstox-history-v3", DailySourceTimestampRole.INTERVAL_START,
        "Asia/Kolkata", True, False, True,
        DailySourceLegacyState.LEGACY_SEMANTICS_AMBIGUOUS,
        DailySourceLegacyState.LEGACY_SEMANTICS_AMBIGUOUS,
        "upstox-v3-daily-legacy-source-semantics",
        "upstox-v3-historical-candle-doc",
        "https://upstox.com/developer/api-documentation/v3/get-historical-candle-data/",
    )


def upstox_v4_daily_interval_start_semantics() -> DailySourceTemporalSemantics:
    """Forward path: raw V3 timestamp is retained as interval start, not end."""
    return _semantics(
        "upstox", "upstox-history-v4-interval-start", DailySourceTimestampRole.INTERVAL_START,
        "Asia/Kolkata", True, False, True,
        DailySourceLegacyState.SOURCE_SEMANTICS_RESOLVED,
        DailySourceLegacyState.SOURCE_SEMANTICS_RESOLVED,
        "upstox-v4-daily-source-semantics",
        "upstox-v3-historical-candle-doc",
        "https://upstox.com/developer/api-documentation/v3/get-historical-candle-data/",
    )


def nse_bhavcopy_daily_semantics() -> DailySourceTemporalSemantics:
    return _semantics(
        "NSE_OFFICIAL", "nse-full-bhavcopy-v1", DailySourceTimestampRole.TRADING_DATE,
        "Asia/Kolkata", True, False, True,
        DailySourceLegacyState.SOURCE_SEMANTICS_RESOLVED,
        DailySourceLegacyState.SOURCE_SEMANTICS_RESOLVED,
        "nse-full-bhavcopy-daily-source-semantics",
        "nse-eod-historical-data-source",
        "https://www.nseindia.com/static/market-data/eod-historical-data-subscription",
    )


def yfinance_daily_semantics() -> DailySourceTemporalSemantics:
    return _semantics(
        "yfinance", "yfinance-history-v1", DailySourceTimestampRole.UNKNOWN,
        None, False, False, False,
        DailySourceLegacyState.LEGACY_SEMANTICS_AMBIGUOUS,
        DailySourceLegacyState.LEGACY_SEMANTICS_AMBIGUOUS,
        "yfinance-daily-source-semantics",
        "yfinance-library-reference",
        "https://ranaroussi.github.io/yfinance/",
    )


def resolve_daily_source_temporal_facts(
    bar: CanonicalOHLCVBar, semantics: DailySourceTemporalSemantics,
) -> DailySourceTemporalFacts:
    """Return source facts without inferring session end or publication time."""
    if (
        bar.timeframe is not Timeframe.DAILY
        or bar.provenance.provider != semantics.source_family
        or bar.provenance.normalization_version != semantics.source_version
    ):
        raise ValueError("DAILY_SOURCE_TEMPORAL_FACTS_INPUT_INVALID")
    raw = bar.provenance.exchange_timestamp or bar.provenance.provider_timestamp
    state = semantics.historical_applicability
    if raw is None and semantics.raw_timestamp_role is not DailySourceTimestampRole.UNKNOWN:
        state = DailySourceLegacyState.SOURCE_SEMANTICS_CONFLICTED
    if semantics.source_version == "upstox-history-v3" and raw is not None and bar.end_time.astimezone(UTC) != raw.astimezone(UTC):
        state = DailySourceLegacyState.SOURCE_SEMANTICS_CONFLICTED
    if semantics.source_version == "upstox-history-v4-interval-start" and raw is not None and (
        bar.start_time.astimezone(UTC) != raw.astimezone(UTC)
        or bar.end_time.astimezone(UTC) != raw.astimezone(UTC)
    ):
        state = DailySourceLegacyState.SOURCE_SEMANTICS_CONFLICTED
    session = _session_date(raw, semantics)
    availability = (
        DailySourceAvailabilityState.HSI_OBSERVED_AT_ONLY
        if semantics.hsi_observed_at_fallback_permitted and state is not DailySourceLegacyState.SOURCE_SEMANTICS_CONFLICTED
        else DailySourceAvailabilityState.HISTORICAL_KNOWN_AT_UNAVAILABLE
    )
    values = dict(
        source_family=semantics.source_family,
        source_version=semantics.source_version,
        raw_timestamp=raw.astimezone(UTC) if raw else None,
        raw_timestamp_role=semantics.raw_timestamp_role,
        session_date=session,
        source_available_at=None,
        hsi_observed_at=bar.provenance.received_at.astimezone(UTC),
        availability_state=availability,
        legacy_state=state,
        policy_id=semantics.policy_id,
        policy_fingerprint=semantics.fingerprint,
    )
    return DailySourceTemporalFacts(**values, fingerprint=_fingerprint(_facts_payload_dict(values)))


def daily_interval_end_is_trusted(
    bar: CanonicalOHLCVBar, facts: DailySourceTemporalFacts,
) -> bool:
    """Small explicit guard for strict consumers of a daily canonical end.

    Raw Upstox V3 start timestamps and the corrected V4 unbound representation
    deliberately return ``False``: only the session contract may later derive
    an actual daily session end.  Existing generic historical readers are not
    silently reinterpreted by this source-facts slice.
    """
    return (
        bar.timeframe is Timeframe.DAILY
        and facts.legacy_state is DailySourceLegacyState.SOURCE_SEMANTICS_RESOLVED
        and facts.raw_timestamp_role is DailySourceTimestampRole.INTERVAL_END
        and facts.raw_timestamp is not None
        and bar.end_time.astimezone(UTC) == facts.raw_timestamp.astimezone(UTC)
    )


def daily_source_timing_from_temporal_facts(facts: DailySourceTemporalFacts):
    """Adapt resolved source facts to the existing daily-temporal receipt input.

    Importing locally keeps the source-fact contract free from a module cycle.
    Legacy ambiguity, unresolved source timing, and secondary yfinance facts
    cannot obtain a timing receipt through this bridge.
    """
    from app.market_data.daily_technical_bar_temporal_evidence import (
        DailyBarSourceTimingEvidence,
        DailySourceAvailabilitySemantics,
    )

    if (
        facts.legacy_state is not DailySourceLegacyState.SOURCE_SEMANTICS_RESOLVED
        or facts.availability_state is not DailySourceAvailabilityState.HSI_OBSERVED_AT_ONLY
        or facts.session_date is None
    ):
        raise ValueError("DAILY_SOURCE_TIMING_BRIDGE_UNAVAILABLE")
    return DailyBarSourceTimingEvidence(
        facts.source_family,
        facts.session_date,
        DailySourceAvailabilitySemantics.HSI_OBSERVED_AT_FORWARD_ONLY,
        None,
        "daily-source-temporal:" + facts.fingerprint.removeprefix("sha256:"),
        facts.fingerprint,
        facts.hsi_observed_at,
    )


def _semantics(
    source_family: str, source_version: str, role: DailySourceTimestampRole,
    timezone_id: str | None, session_date_from_raw_timestamp: bool,
    source_publication_time_available: bool, observed_fallback: bool,
    historical: DailySourceLegacyState, forward: DailySourceLegacyState,
    policy_id: str, evidence_id: str, reference: str,
) -> DailySourceTemporalSemantics:
    return DailySourceTemporalSemantics(
        source_family, source_version, Timeframe.DAILY, role, timezone_id,
        session_date_from_raw_timestamp, source_publication_time_available,
        observed_fallback, historical, forward, policy_id, "v1", evidence_id,
        reference, _reference_fingerprint(evidence_id, reference),
    )


def _session_date(raw: datetime | None, semantics: DailySourceTemporalSemantics) -> date | None:
    if raw is None or not semantics.session_date_from_raw_timestamp or semantics.source_timezone_id is None:
        return None
    return raw.astimezone(ZoneInfo(semantics.source_timezone_id)).date()


def _semantics_payload(value: DailySourceTemporalSemantics) -> dict[str, object]:
    return _payload({name: getattr(value, name) for name in DailySourceTemporalSemantics.__dataclass_fields__})


def _facts_payload(value: DailySourceTemporalFacts) -> dict[str, object]:
    return _facts_payload_dict({name: getattr(value, name) for name in DailySourceTemporalFacts.__dataclass_fields__ if name != "fingerprint"})


def _facts_payload_dict(value: dict[str, object]) -> dict[str, object]:
    return _payload(value)


def _payload(value: dict[str, object]) -> dict[str, object]:
    return {
        "contract": CONTRACT_ID,
        "version": CONTRACT_VERSION,
        **{
            key: _timestamp(item) if isinstance(item, datetime)
            else item.isoformat() if isinstance(item, date)
            else item.value if isinstance(item, StrEnum)
            else item
            for key, item in value.items()
        },
    }


def _reference_fingerprint(evidence_id: str, reference: str) -> str:
    return _fingerprint({"evidence_id": evidence_id, "reference": reference})


def _fingerprint(value: object) -> str:
    return "sha256:" + sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()).hexdigest()


def _aware(value: object) -> bool:
    return isinstance(value, datetime) and value.tzinfo is not None and value.utcoffset() is not None


def _timestamp(value: datetime) -> str:
    return value.astimezone(UTC).isoformat()


__all__ = (
    "CONTRACT_ID", "CONTRACT_VERSION", "DailySourceAvailabilityState",
    "DailySourceLegacyState", "DailySourceTemporalFacts",
    "DailySourceTemporalSemantics", "DailySourceTimestampRole",
    "daily_interval_end_is_trusted", "daily_source_timing_from_temporal_facts",
    "nse_bhavcopy_daily_semantics",
    "resolve_daily_source_temporal_facts", "upstox_v3_daily_legacy_semantics",
    "upstox_v4_daily_interval_start_semantics", "yfinance_daily_semantics",
)
