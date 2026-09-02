"""Bounded NSE/CMTR/67133 monthly tick derivation from an official Bhavcopy.

The boundary is intentionally local-only: it consumes one retained, official
Full Bhavcopy artifact and writes immutable reference evidence.  It neither
downloads quote data nor applies a price-level heuristic outside the exchange
rule captured here.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from io import StringIO
from pathlib import Path
import re
from typing import Iterable
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from app.historical.guard import manifest_fingerprint
from app.market_data.models import Exchange
from app.universe_analysis.models import NseEquityInstrument

from .repository import TickSizeObservationRepository
from .tick_size import (
    NseTickSizeObservation,
    NseTickSizeSegment,
    TickSizeAvailabilitySemantics,
    TickSizeEvidenceKind,
    TickSizeEvidenceSufficiency,
    TickSizeSourceClass,
)


NSE_CMTR_67133_RULE_ID = "NSE_CMTR_67133_PRICE_LINKED_TICK_V1"
NSE_CMTR_67133_REFERENCE = "NSE/CMTR/67133"
NSE_CMTR_62174_REFERENCE = "NSE/CMTR/62174"
_IST = ZoneInfo("Asia/Kolkata")
_FILENAME = re.compile(r"sec_bhavdata_full_(\d{8})(?:-[a-f0-9]{12})?\.csv\Z", re.IGNORECASE)
_MONTH = re.compile(r"\d{4}-\d{2}\Z")
_REQUIRED_COLUMNS = frozenset({"SYMBOL", "SERIES", "DATE1", "CLOSE_PRICE"})
_OFFICIAL_HOSTS = frozenset({"archives.nseindia.com", "nsearchives.nseindia.com"})


class NseTickRuleEligibility:
    ORDINARY_EQUITY = "ORDINARY_EQUITY"
    ETF_EXCLUDED = "ETF_EXCLUDED"
    NEW_LISTING_SPECIAL_CASE = "NEW_LISTING_SPECIAL_CASE"
    CORPORATE_ACTION_SPECIAL_CASE = "CORPORATE_ACTION_SPECIAL_CASE"
    UNSUPPORTED_SECURITY_CLASS = "UNSUPPORTED_SECURITY_CLASS"
    IDENTITY_UNRESOLVED = "IDENTITY_UNRESOLVED"


@dataclass(frozen=True, slots=True)
class NseRuleDerivedTickTarget:
    canonical_instrument_id: str
    symbol: str
    isin: str | None
    security_type: str
    exchange: str
    series: str = "EQ"
    listing_date: datetime | None = None
    corporate_action_exception: bool = False

    @classmethod
    def from_instrument(
        cls, value: NseEquityInstrument, *, corporate_action_exception: bool = False,
    ) -> "NseRuleDerivedTickTarget":
        return cls(
            value.instrument_id, value.symbol.upper(), value.isin.upper() if value.isin else None,
            value.security_type.upper(), value.exchange.upper(), "EQ", value.listing_date,
            corporate_action_exception,
        )


@dataclass(frozen=True, slots=True)
class NseRuleDerivedTickTargetResult:
    canonical_instrument_id: str
    symbol: str
    isin: str | None
    eligibility: str
    reference_close: Decimal | None
    tick_size: Decimal | None
    effective_from: datetime | None
    observation_id: str | None
    blocker: str | None


@dataclass(frozen=True, slots=True)
class NseRuleDerivedTickMaterializationReport:
    source_file: str
    source_url: str
    source_sha256: str
    received_at: datetime
    effective_month: str
    reference_session: datetime
    eligible: int
    derived: int
    exceptions: int
    blocked: int
    identity_conflicts: int
    duplicates: int
    conflicts: int
    results: tuple[NseRuleDerivedTickTargetResult, ...]


class NseRuleDerivedTickMaterializer:
    """Derive effective monthly NSE ticks through one official rule only."""

    def __init__(self, repository: TickSizeObservationRepository, targets: Iterable[NseRuleDerivedTickTarget]) -> None:
        self._repository = repository
        values = tuple(targets)
        symbols: set[str] = set()
        for value in values:
            if not value.canonical_instrument_id or not value.symbol or value.symbol in symbols:
                raise ValueError("NSE_RULE_DERIVED_TICK_TARGET_IDENTITY_INVALID")
            symbols.add(value.symbol)
        self._targets = tuple(sorted(values, key=lambda value: (value.symbol, value.canonical_instrument_id)))

    def materialize(
        self,
        path: str | Path,
        *,
        source_url: str,
        received_at: datetime,
        effective_month: str,
        reference_trade_date: datetime,
    ) -> NseRuleDerivedTickMaterializationReport:
        _require_aware(received_at, "NSE_RULE_DERIVED_TICK_RECEIVED_AT_NAIVE")
        _require_aware(reference_trade_date, "NSE_RULE_DERIVED_TICK_REFERENCE_DATE_NAIVE")
        if not _MONTH.fullmatch(effective_month):
            raise ValueError("NSE_RULE_DERIVED_TICK_EFFECTIVE_MONTH_INVALID")
        _validate_official_source(source_url)
        raw, rows, source = _read_bhavcopy(path, reference_trade_date)
        close_by_symbol = _exact_closes(rows, reference_trade_date)
        source_sha = sha256(raw).hexdigest()
        reference_session = _session_end(reference_trade_date)
        effective_from, effective_to = _month_interval(effective_month)
        if reference_session >= effective_from:
            raise ValueError("NSE_RULE_DERIVED_TICK_REFERENCE_MONTH_INVALID")

        eligible = derived = exceptions = blocked = identity_conflicts = duplicates = conflicts = 0
        results: list[NseRuleDerivedTickTargetResult] = []
        for target in self._targets:
            eligibility = _eligibility(target, reference_trade_date)
            if eligibility != NseTickRuleEligibility.ORDINARY_EQUITY:
                exceptions += 1 if eligibility.endswith("SPECIAL_CASE") or eligibility == NseTickRuleEligibility.ETF_EXCLUDED else 0
                blocked += 1
                results.append(NseRuleDerivedTickTargetResult(
                    target.canonical_instrument_id, target.symbol, target.isin, eligibility,
                    None, None, None, None, eligibility,
                ))
                continue
            if target.symbol not in close_by_symbol:
                blocked += 1
                results.append(NseRuleDerivedTickTargetResult(
                    target.canonical_instrument_id, target.symbol, target.isin, eligibility,
                    None, None, None, None, "OFFICIAL_NSE_REFERENCE_CLOSE_UNAVAILABLE",
                ))
                continue
            close = close_by_symbol[target.symbol]
            tick = nse_cmtr_67133_tick_size(close)
            observation = _observation(
                target, source_sha256=source_sha, source_url=source_url, source_file=source.name,
                received_at=received_at, effective_month=effective_month, effective_from=effective_from,
                effective_to=effective_to, reference_session=reference_session, reference_close=close,
                tick_size=tick,
            )
            existing = self._repository.get_tick_size_observation(observation.record_id)
            if existing is None:
                self._repository.save_tick_size_observation(observation)
                derived += 1
            elif existing == observation:
                duplicates += 1
            else:
                conflicts += 1
                identity_conflicts += 1
                results.append(NseRuleDerivedTickTargetResult(
                    target.canonical_instrument_id, target.symbol, target.isin, eligibility,
                    close, tick, effective_from, None, "NSE_RULE_DERIVED_TICK_IMMUTABLE_CONFLICT",
                ))
                continue
            eligible += 1
            results.append(NseRuleDerivedTickTargetResult(
                target.canonical_instrument_id, target.symbol, target.isin, eligibility,
                close, tick, effective_from, observation.record_id, None,
            ))
        return NseRuleDerivedTickMaterializationReport(
            source.name, source_url, source_sha, received_at.astimezone(UTC), effective_month,
            reference_session, eligible, derived, exceptions, blocked, identity_conflicts,
            duplicates, conflicts, tuple(results),
        )


def nse_cmtr_67133_tick_size(reference_close: Decimal) -> Decimal:
    """Return the exact exchange-defined price-linked tick bucket."""
    if not isinstance(reference_close, Decimal) or not reference_close.is_finite() or reference_close <= 0:
        raise ValueError("NSE_RULE_DERIVED_TICK_REFERENCE_CLOSE_INVALID")
    if reference_close < Decimal("250"):
        return Decimal("0.01")
    if reference_close <= Decimal("1000"):
        return Decimal("0.05")
    if reference_close <= Decimal("5000"):
        return Decimal("0.10")
    if reference_close <= Decimal("10000"):
        return Decimal("0.50")
    if reference_close <= Decimal("20000"):
        return Decimal("1.00")
    return Decimal("5.00")


def _eligibility(target: NseRuleDerivedTickTarget, reference_trade_date: datetime) -> str:
    if target.exchange != "NSE" or not target.canonical_instrument_id or not target.isin:
        return NseTickRuleEligibility.IDENTITY_UNRESOLVED
    if target.security_type == "ETF":
        return NseTickRuleEligibility.ETF_EXCLUDED
    if target.security_type != "EQUITY" or target.series != "EQ":
        return NseTickRuleEligibility.UNSUPPORTED_SECURITY_CLASS
    if target.corporate_action_exception:
        return NseTickRuleEligibility.CORPORATE_ACTION_SPECIAL_CASE
    if target.listing_date is not None and target.listing_date.astimezone(UTC) >= reference_trade_date.astimezone(UTC):
        return NseTickRuleEligibility.NEW_LISTING_SPECIAL_CASE
    return NseTickRuleEligibility.ORDINARY_EQUITY


def _read_bhavcopy(path: str | Path, reference_trade_date: datetime) -> tuple[bytes, tuple[dict[str, str], ...], Path]:
    source = Path(path)
    if _FILENAME.fullmatch(source.name) is None:
        raise ValueError("NSE_RULE_DERIVED_TICK_BHAVCOPY_FILENAME_UNSUPPORTED")
    try:
        raw = source.read_bytes()
        text = raw.decode("utf-8-sig", errors="strict")
    except FileNotFoundError as error:
        raise ValueError("NSE_RULE_DERIVED_TICK_BHAVCOPY_NOT_FOUND") from error
    except UnicodeError as error:
        raise ValueError("NSE_RULE_DERIVED_TICK_BHAVCOPY_TEXT_INVALID") from error
    reader = csv.DictReader(StringIO(text))
    fields = {item.strip().upper(): item for item in reader.fieldnames or ()}
    if not _REQUIRED_COLUMNS <= set(fields):
        raise ValueError("NSE_RULE_DERIVED_TICK_BHAVCOPY_COLUMNS_REQUIRED")
    rows = tuple({key: (row.get(value) or "").strip() for key, value in fields.items()} for row in reader)
    filename_date = datetime.strptime(_FILENAME.fullmatch(source.name).group(1), "%d%m%Y").replace(tzinfo=UTC)
    if filename_date.date() != reference_trade_date.astimezone(UTC).date():
        raise ValueError("NSE_RULE_DERIVED_TICK_REFERENCE_DATE_MISMATCH")
    return raw, rows, source


def _exact_closes(rows: tuple[dict[str, str], ...], reference_trade_date: datetime) -> dict[str, Decimal]:
    values: dict[str, Decimal] = {}
    for row in rows:
        if row.get("SERIES", "").upper() != "EQ":
            continue
        symbol = row.get("SYMBOL", "").upper()
        if not symbol:
            continue
        if _row_date(row.get("DATE1", "")) != reference_trade_date.astimezone(UTC).date():
            continue
        close = _positive_decimal(row.get("CLOSE_PRICE", ""))
        if symbol in values:
            raise ValueError("NSE_RULE_DERIVED_TICK_BHAVCOPY_SYMBOL_AMBIGUOUS")
        values[symbol] = close
    return values


def _observation(
    target: NseRuleDerivedTickTarget, *, source_sha256: str, source_url: str, source_file: str,
    received_at: datetime, effective_month: str, effective_from: datetime, effective_to: datetime,
    reference_session: datetime, reference_close: Decimal, tick_size: Decimal,
) -> NseTickSizeObservation:
    record_id = "nse-rule-tick:" + manifest_fingerprint(
        canonical_instrument_id=target.canonical_instrument_id, effective_month=effective_month,
        reference_session=reference_session, reference_close=str(reference_close), tick_size=str(tick_size),
        source_sha256=source_sha256, rule_id=NSE_CMTR_67133_RULE_ID,
    )[:32]
    return NseTickSizeObservation(
        record_id=record_id, canonical_instrument_id=target.canonical_instrument_id,
        exchange=Exchange.NSE, segment=NseTickSizeSegment.NSE_CASH_EQUITY, isin=target.isin,
        tick_size=tick_size, source_class=TickSizeSourceClass.OFFICIAL_EXCHANGE,
        source_name="NSE official rule-derived monthly tick", source_artifact_fingerprint=source_sha256,
        observed_at=received_at, effective_from=effective_from, effective_to=effective_to,
        availability_semantics=TickSizeAvailabilitySemantics.EXPLICIT_EFFECTIVE_PERIOD,
        warnings=("OFFICIAL_RULE_DERIVED", "NSE_SECURITY_FILE_TICKSZ_BLANK_PRESERVED", "SOURCE_ISIN_NOT_PRESENT_PREVALIDATED_TARGET_MAPPING"),
        evidence_kind=TickSizeEvidenceKind.OFFICIAL_RULE_DERIVED, symbol=target.symbol,
        series=target.series, effective_month=effective_month, reference_trading_session=reference_session,
        reference_close=reference_close, rule_id=NSE_CMTR_67133_RULE_ID,
        source_circular_reference=f"{NSE_CMTR_67133_REFERENCE}; {NSE_CMTR_62174_REFERENCE}",
        source_artifact_reference=source_url,
        derivation_details=(
            "LATEST_CLOSE_ON_LAST_TRADING_DAY_OF_PREVIOUS_TRADING_MONTH",
            f"SOURCE_FILE:{source_file}", f"REFERENCE_CLOSE:{reference_close}",
        ),
        evidence_sufficiency=TickSizeEvidenceSufficiency.SUFFICIENT,
    )


def _month_interval(effective_month: str) -> tuple[datetime, datetime]:
    year, month = (int(part) for part in effective_month.split("-"))
    start = datetime(year, month, 1, tzinfo=_IST).astimezone(UTC)
    following_year, following_month = (year + 1, 1) if month == 12 else (year, month + 1)
    end = datetime(following_year, following_month, 1, tzinfo=_IST).astimezone(UTC)
    return start, end


def _session_end(trade_date: datetime) -> datetime:
    return datetime.combine(trade_date.astimezone(UTC).date(), datetime.min.time(), tzinfo=_IST).astimezone(UTC)


def _row_date(value: str):
    try:
        return datetime.strptime(value, "%d-%b-%Y").date()
    except ValueError as error:
        raise ValueError("NSE_RULE_DERIVED_TICK_BHAVCOPY_DATE_INVALID") from error


def _positive_decimal(value: str) -> Decimal:
    try:
        result = Decimal(value)
    except InvalidOperation as error:
        raise ValueError("NSE_RULE_DERIVED_TICK_BHAVCOPY_CLOSE_INVALID") from error
    if not result.is_finite() or result <= 0:
        raise ValueError("NSE_RULE_DERIVED_TICK_BHAVCOPY_CLOSE_INVALID")
    return result


def _validate_official_source(value: str) -> None:
    parsed = urlsplit(value)
    if parsed.scheme != "https" or parsed.hostname not in _OFFICIAL_HOSTS:
        raise ValueError("NSE_RULE_DERIVED_TICK_OFFICIAL_SOURCE_REQUIRED")


def _require_aware(value: datetime, code: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(code)
