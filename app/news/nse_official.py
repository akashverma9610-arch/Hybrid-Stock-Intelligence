"""Fail-closed acquisition for official NSE corporate-announcement metadata.

This is deliberately a small source adapter.  It has no synthetic fallback,
no publisher-page scraping, and no interpretation of an announcement's
direction, impact, or materiality.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from typing import Callable, Mapping
from zoneinfo import ZoneInfo

import requests


NSE_OFFICIAL_NEWS_PROVIDER = "NSE_OFFICIAL"
NSE_CORPORATE_ANNOUNCEMENTS_ENDPOINT = "https://www.nseindia.com/api/corporate-announcements?index=equities"
NSE_HOME_URL = "https://www.nseindia.com/"
NSE_TIMEZONE = ZoneInfo("Asia/Kolkata")


class NseAnnouncementSourceError(ValueError):
    """Public-safe failure category for the official source boundary."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True, slots=True)
class NseCorporateAnnouncement:
    symbol: str
    isin: str | None
    company_name: str | None
    subject: str
    details: str | None
    published_at: datetime
    exchange_received_at: datetime | None
    source_sequence_id: str
    attachment_url: str | None
    attachment_identity: str | None
    xbrl_identity: str | None
    source_fingerprint: str

    @property
    def event_identity(self) -> str:
        """Immutable source record/version identity; no headline similarity."""
        return f"{self.source_sequence_id}:{self.source_fingerprint}"


class NseCorporateAnnouncementsSource:
    """Bounded official NSE JSON source with the exchange's normal session flow."""

    endpoint = NSE_CORPORATE_ANNOUNCEMENTS_ENDPOINT
    home_url = NSE_HOME_URL

    def __init__(
        self,
        *,
        session_factory: Callable[[], requests.Session] = requests.Session,
        timeout_seconds: float = 15.0,
        maximum_records: int = 50,
        received_at: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        if timeout_seconds <= 0 or not 1 <= maximum_records <= 100:
            raise ValueError("NSE_NEWS_SOURCE_CONFIGURATION_INVALID")
        self._session_factory = session_factory
        self._timeout, self._maximum, self._received_at = timeout_seconds, maximum_records, received_at

    def fetch(self) -> tuple[tuple[NseCorporateAnnouncement, ...], datetime]:
        session = self._session_factory()
        try:
            # NSE may permit the API call without a homepage response; the
            # homepage is session initialization only and is never a fallback.
            try:
                session.get(self.home_url, headers=_homepage_headers(), timeout=self._timeout)
            except requests.RequestException:
                pass
            response = session.get(self.endpoint, headers=_api_headers(), timeout=self._timeout)
        except requests.Timeout as error:
            raise NseAnnouncementSourceError("SOURCE_UNAVAILABLE") from error
        except requests.RequestException as error:
            raise NseAnnouncementSourceError("SOURCE_UNAVAILABLE") from error
        if response.status_code == 429:
            raise NseAnnouncementSourceError("RATE_LIMITED")
        if response.status_code >= 400:
            raise NseAnnouncementSourceError("HTTP_ERROR")
        try:
            payload = response.json()
        except ValueError as error:
            raise NseAnnouncementSourceError("INVALID_RESPONSE") from error
        if not isinstance(payload, list):
            raise NseAnnouncementSourceError("INVALID_RESPONSE")
        received = _aware(self._received_at(), "received_at")
        try:
            records = tuple(_announcement(item) for item in payload[: self._maximum])
        except (KeyError, TypeError, ValueError) as error:
            raise NseAnnouncementSourceError("PARSE_ERROR") from error
        return records, received


def _homepage_headers() -> dict[str, str]:
    return {
        "User-Agent": _user_agent(),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }


def _api_headers() -> dict[str, str]:
    return {
        "User-Agent": _user_agent(),
        "Accept": "application/json",
        "Referer": NSE_HOME_URL,
    }


def _user_agent() -> str:
    # A normal, transparent HTTP client identity; never a browser-automation
    # or anti-bot circumvention technique.
    return "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"


def _announcement(value: object) -> NseCorporateAnnouncement:
    if not isinstance(value, Mapping):
        raise ValueError("NSE_ANNOUNCEMENT_RECORD_INVALID")
    symbol = _text(value.get("symbol")).upper()
    sequence = _text(value.get("seq_id"))
    subject = _text(value.get("desc"))
    if not all((symbol, sequence, subject)):
        raise ValueError("NSE_ANNOUNCEMENT_REQUIRED_FIELDS_MISSING")
    published = _first_time(value, "an_dt", "sort_date", "dt")
    received = _optional_time(value.get("exchdisstime"))
    attachment = _optional_url(value.get("attchmntFile"))
    raw_fingerprint = sha256(_canonical_record(value).encode("utf-8")).hexdigest()
    return NseCorporateAnnouncement(
        symbol=symbol,
        isin=(_optional_text(value.get("sm_isin")) or "").upper() or None,
        company_name=_optional_text(value.get("sm_name")),
        subject=subject,
        details=_optional_text(value.get("attchmntText")),
        published_at=published,
        exchange_received_at=received,
        source_sequence_id=sequence,
        attachment_url=attachment,
        attachment_identity=_optional_text(value.get("attchmntFile")) or _optional_text(value.get("csvName")),
        xbrl_identity=("NSE_XBRL_AVAILABLE" if value.get("hasXbrl") is True else None),
        source_fingerprint=raw_fingerprint,
    )


def _canonical_record(value: Mapping[str, object]) -> str:
    return "|".join(f"{key}={value[key]!r}" for key in sorted(value))


def _text(value: object) -> str:
    return str(value or "").strip()


def _optional_text(value: object) -> str | None:
    text = _text(value)
    return text or None


def _optional_url(value: object) -> str | None:
    text = _optional_text(value)
    if text is None:
        return None
    if text.startswith("https://") or text.startswith("http://"):
        return text
    if text.startswith("/"):
        return "https://www.nseindia.com" + text
    return "https://nsearchives.nseindia.com" + ("/" if not text.startswith("/") else "") + text


def _first_time(value: Mapping[str, object], *keys: str) -> datetime:
    for key in keys:
        parsed = _optional_time(value.get(key))
        if parsed is not None:
            return parsed
    raise ValueError("NSE_ANNOUNCEMENT_PUBLICATION_TIME_MISSING")


def _optional_time(value: object) -> datetime | None:
    raw = _optional_text(value)
    if raw is None:
        return None
    for form in (
        "%d-%b-%Y %H:%M:%S", "%d-%b-%Y %H:%M", "%d-%b-%Y",
        "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S.%f%z",
    ):
        try:
            parsed = datetime.strptime(raw, form)
        except ValueError:
            continue
        return parsed.replace(tzinfo=NSE_TIMEZONE).astimezone(UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.replace(tzinfo=NSE_TIMEZONE).astimezone(UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)


def _aware(value: datetime, field: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field} must be timezone-aware")
    return value.astimezone(UTC)


__all__ = (
    "NSE_CORPORATE_ANNOUNCEMENTS_ENDPOINT", "NSE_OFFICIAL_NEWS_PROVIDER",
    "NseAnnouncementSourceError", "NseCorporateAnnouncement", "NseCorporateAnnouncementsSource",
)
