"""Immutable official NSE Full Bhavcopy OHLCV import boundary.

This boundary accepts an already-retained official ``sec_bhavdata_full`` CSV.
It never downloads data, derives prices, or resolves a ticker by fuzzy name.
The existing provider-versioned historical store remains the only writer.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from io import StringIO
from pathlib import Path
import re
from typing import Iterable, Mapping
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from app.data_operations.upstox import _equity_identity
from app.domain.models import DataQuality
from app.market_data.historical import HistoricalBarStore, HistoricalIngestionService
from app.market_data.models import (
    AdjustmentStatus, CanonicalOHLCVBar, ErrorCode, HistoricalBarsRequest,
    MarketDataError, MarketDataProvenance, Timeframe,
)
from app.universe_analysis.models import NseEquityInstrument


NSE_OFFICIAL_BAR_PROVIDER = "NSE_OFFICIAL"
NSE_FULL_BHAVCOPY_NORMALIZATION_VERSION = "nse-full-bhavcopy-v1"
_IST = ZoneInfo("Asia/Kolkata")
# ``NseDeliveryStagingJob`` retains accepted immutable files as
# ``<source-stem>-<sha256-prefix>.csv``.  Accept that one bounded local archive
# representation in addition to the official filename; arbitrary suffixes are
# still rejected.
_FILENAME = re.compile(r"sec_bhavdata_full_(\d{8})(?:-[a-f0-9]{12})?\.csv\Z", re.IGNORECASE)
_REQUIRED = frozenset({"SYMBOL", "SERIES", "DATE1", "OPEN_PRICE", "HIGH_PRICE", "LOW_PRICE", "CLOSE_PRICE", "TTL_TRD_QNTY"})


@dataclass(frozen=True, slots=True)
class NseFullBhavcopyTarget:
    canonical_instrument_id: str
    symbol: str
    isin: str
    series: str = "EQ"
    instrument: object | None = None

    @classmethod
    def from_instrument(cls, value: NseEquityInstrument) -> "NseFullBhavcopyTarget":
        if (
            value.exchange.upper() != "NSE" or value.security_type.upper() != "EQUITY"
            or not value.isin or not value.symbol or not value.instrument_id
        ):
            raise ValueError("NSE_FULL_BHAVCOPY_EXACT_EQUITY_IDENTITY_REQUIRED")
        return cls(value.instrument_id, value.symbol.upper(), value.isin.upper(), "EQ", value)

    def __post_init__(self) -> None:
        if not all(isinstance(value, str) and value.strip() for value in (
            self.canonical_instrument_id, self.symbol, self.isin, self.series,
        )):
            raise ValueError("NSE_FULL_BHAVCOPY_TARGET_IDENTITY_REQUIRED")
        if self.series.upper() != "EQ":
            raise ValueError("NSE_FULL_BHAVCOPY_TARGET_SERIES_UNSUPPORTED")
        if self.instrument is None:
            raise ValueError("NSE_FULL_BHAVCOPY_TARGET_INSTRUMENT_REQUIRED")


@dataclass(frozen=True, slots=True)
class NseFullBhavcopyTargetResult:
    canonical_instrument_id: str
    symbol: str
    isin: str
    accepted: int
    duplicates: int
    conflicts: int
    rejected: int
    session: datetime | None
    blocker: str | None


@dataclass(frozen=True, slots=True)
class NseFullBhavcopyImportReport:
    source_file: str
    source_url: str
    source_sha256: str
    retrieved_at: datetime
    trade_date: datetime
    source_columns: tuple[str, ...]
    rows_seen: int
    eq_rows_seen: int
    target_rows_seen: int
    accepted: int
    duplicates: int
    conflicts: int
    rejected: int
    missing_targets: int
    results: tuple[NseFullBhavcopyTargetResult, ...]


class NseFullBhavcopyOhlcvImporter:
    """Import exact, positive OHLCV rows through historical-bar governance."""

    def __init__(self, store: HistoricalBarStore, targets: Iterable[NseFullBhavcopyTarget]) -> None:
        self._store = store
        values = tuple(targets)
        by_symbol: dict[str, NseFullBhavcopyTarget] = {}
        for value in values:
            key = value.symbol.upper()
            if key in by_symbol:
                raise ValueError("NSE_FULL_BHAVCOPY_TARGET_SYMBOL_AMBIGUOUS")
            by_symbol[key] = value
        self._targets = by_symbol

    def import_file(self, path: str | Path, *, source_url: str, retrieved_at: datetime) -> NseFullBhavcopyImportReport:
        _require_aware(retrieved_at)
        _validate_source_url(source_url)
        source = Path(path)
        trade_date = _trade_date_from_filename(source.name)
        try:
            raw = source.read_bytes()
            text = raw.decode("utf-8-sig", errors="strict")
        except FileNotFoundError as error:
            raise ValueError("NSE_FULL_BHAVCOPY_FILE_NOT_FOUND") from error
        except UnicodeError as error:
            raise ValueError("NSE_FULL_BHAVCOPY_TEXT_INVALID") from error
        reader = csv.DictReader(StringIO(text))
        headers = tuple(reader.fieldnames or ())
        fields = {header.strip().upper(): header for header in headers}
        if not _REQUIRED <= set(fields):
            raise ValueError("NSE_FULL_BHAVCOPY_OHLCV_FIELDS_REQUIRED")

        parsed: dict[str, CanonicalOHLCVBar] = {}
        rows_seen = eq_rows_seen = target_rows_seen = rejected = 0
        for row in reader:
            rows_seen += 1
            symbol = _text(row.get(fields["SYMBOL"])).upper()
            series = _text(row.get(fields["SERIES"])).upper()
            if series != "EQ":
                continue
            eq_rows_seen += 1
            target = self._targets.get(symbol)
            if target is None:
                continue
            target_rows_seen += 1
            if symbol in parsed:
                rejected += 1
                continue
            try:
                parsed[symbol] = _bar_from_row(
                    row, fields=fields, target=target, trade_date=trade_date,
                    retrieved_at=retrieved_at, source_url=source_url, source_sha256=sha256(raw).hexdigest(),
                )
            except ValueError:
                rejected += 1

        accepted = duplicates = conflicts = 0
        results: list[NseFullBhavcopyTargetResult] = []
        for symbol, target in sorted(self._targets.items()):
            value = parsed.get(symbol)
            if value is None:
                results.append(NseFullBhavcopyTargetResult(
                    target.canonical_instrument_id, target.symbol, target.isin,
                    0, 0, 0, 0, None, "OFFICIAL_NSE_EOD_OHLCV_UNAVAILABLE",
                ))
                continue
            report = HistoricalIngestionService(
                _NseFullBhavcopyProvider({target.canonical_instrument_id: value}), self._store,
                clock=lambda: retrieved_at,
            ).ingest(HistoricalBarsRequest(
                value.instrument, Timeframe.DAILY, value.start_time, value.end_time,
                AdjustmentStatus.UNKNOWN, NSE_OFFICIAL_BAR_PROVIDER,
            ))
            accepted += report.accepted_count
            duplicates += report.duplicate_count
            conflicts += report.conflict_count
            rejected += report.rejected_count
            results.append(NseFullBhavcopyTargetResult(
                target.canonical_instrument_id, target.symbol, target.isin,
                report.accepted_count, report.duplicate_count, report.conflict_count,
                report.rejected_count, value.end_time,
                report.warnings[0] if report.rejected_count else None,
            ))
        return NseFullBhavcopyImportReport(
            source.name, source_url, sha256(raw).hexdigest(), retrieved_at.astimezone(UTC), trade_date,
            headers, rows_seen, eq_rows_seen, target_rows_seen, accepted, duplicates, conflicts,
            rejected, len(self._targets) - len(parsed), tuple(results),
        )


class _NseFullBhavcopyProvider:
    """A local one-artifact provider for ``HistoricalIngestionService`` only."""

    def __init__(self, bars: Mapping[str, CanonicalOHLCVBar]) -> None:
        self._bars = dict(bars)

    def get_historical_bars(self, request: HistoricalBarsRequest) -> tuple[CanonicalOHLCVBar, ...]:
        value = self._bars.get(request.instrument.instrument_id)
        if value is None or not request.start <= value.end_time <= request.end:
            raise MarketDataError(ErrorCode.INSTRUMENT_NOT_FOUND, "Official NSE Full Bhavcopy row is unavailable.")
        return (value,)


def _bar_from_row(
    row: Mapping[str, str], *, fields: Mapping[str, str], target: NseFullBhavcopyTarget,
    trade_date: datetime, retrieved_at: datetime, source_url: str, source_sha256: str,
) -> CanonicalOHLCVBar:
    if _parse_trade_date(_text(row.get(fields["DATE1"]))) != trade_date.date():
        raise ValueError("NSE_FULL_BHAVCOPY_TRADE_DATE_MISMATCH")
    open_, high, low, close = tuple(_positive_decimal(row.get(fields[name])) for name in (
        "OPEN_PRICE", "HIGH_PRICE", "LOW_PRICE", "CLOSE_PRICE",
    ))
    volume = _positive_integer(row.get(fields["TTL_TRD_QNTY"]))
    if high < max(open_, low, close) or low > min(open_, high, close):
        raise ValueError("NSE_FULL_BHAVCOPY_OHLC_INVALID")
    turnover = _turnover(row, fields)
    trade_count = _optional_integer(row.get(fields.get("NO_OF_TRADES", "")))
    end = datetime.combine(trade_date.date(), datetime.min.time(), tzinfo=_IST).astimezone(UTC)
    instrument = _equity_identity(target.instrument)  # type: ignore[arg-type]
    artifact_id = "nse-full-bhavcopy:" + source_sha256[:24]
    key = f"{artifact_id}|{target.canonical_instrument_id}|{end.isoformat()}"
    return CanonicalOHLCVBar(
        "nse-official:" + sha256(key.encode()).hexdigest()[:24], instrument, Timeframe.DAILY,
        end - timedelta(days=1), end, open_, high, low, close, volume, turnover, trade_count,
        AdjustmentStatus.UNKNOWN,
        MarketDataProvenance(
            NSE_OFFICIAL_BAR_PROVIDER, f"NSE:{target.symbol}:{target.series}", end, None,
            retrieved_at.astimezone(UTC), NSE_FULL_BHAVCOPY_NORMALIZATION_VERSION,
            artifact_id, source_url,
        ),
        DataQuality.HIGH,
        (
            "NSE_OFFICIAL_FULL_BHAVCOPY", "SOURCE_ISIN_NOT_PRESENT_PREVALIDATED_TARGET_MAPPING",
            "TURNOVER_LACS_NORMALIZED_TO_INR" if turnover is not None else "TURNOVER_UNAVAILABLE",
        ),
    )


def _trade_date_from_filename(value: str) -> datetime:
    match = _FILENAME.fullmatch(value)
    if match is None:
        raise ValueError("NSE_FULL_BHAVCOPY_FILENAME_UNSUPPORTED")
    try:
        return datetime.strptime(match.group(1), "%d%m%Y").replace(tzinfo=UTC)
    except ValueError as error:
        raise ValueError("NSE_FULL_BHAVCOPY_FILENAME_DATE_INVALID") from error


def _parse_trade_date(value: str) -> datetime.date:
    try:
        return datetime.strptime(value, "%d-%b-%Y").date()
    except ValueError as error:
        raise ValueError("NSE_FULL_BHAVCOPY_TRADE_DATE_INVALID") from error


def _positive_decimal(value: object) -> Decimal:
    try:
        result = Decimal(_text(value))
    except (InvalidOperation, ValueError) as error:
        raise ValueError("NSE_FULL_BHAVCOPY_DECIMAL_INVALID") from error
    if not result.is_finite() or result <= 0:
        raise ValueError("NSE_FULL_BHAVCOPY_DECIMAL_INVALID")
    return result


def _positive_integer(value: object) -> int:
    try:
        result = int(_text(value))
    except ValueError as error:
        raise ValueError("NSE_FULL_BHAVCOPY_VOLUME_INVALID") from error
    if result <= 0 or Decimal(_text(value)) != Decimal(result):
        raise ValueError("NSE_FULL_BHAVCOPY_VOLUME_INVALID")
    return result


def _optional_integer(value: object) -> int | None:
    text = _text(value)
    if not text:
        return None
    return _positive_integer(text)


def _turnover(row: Mapping[str, str], fields: Mapping[str, str]) -> Decimal | None:
    field = fields.get("TURNOVER_LACS")
    if field is None or not _text(row.get(field)):
        return None
    return _positive_decimal(row.get(field)) * Decimal("100000")


def _text(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""


def _validate_source_url(value: str) -> None:
    parsed = urlsplit(value)
    if parsed.scheme != "https" or parsed.hostname not in {"archives.nseindia.com", "nsearchives.nseindia.com"}:
        raise ValueError("NSE_FULL_BHAVCOPY_OFFICIAL_SOURCE_REQUIRED")


def _require_aware(value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("NSE_FULL_BHAVCOPY_RETRIEVED_AT_NAIVE")
