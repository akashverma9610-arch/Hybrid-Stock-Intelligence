"""Offline import boundary for lawfully obtained NSE/NDAL CM security masters.

This module intentionally accepts only an explicit local ``security.txt`` or
``security.gz`` file.  It neither discovers nor downloads an NSE source and it
does not choose a tick value for an as-of timestamp.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
import gzip
from hashlib import sha256
from pathlib import Path
import re
from typing import Iterable

from app.historical.guard import manifest_fingerprint
from app.market_data.models import Exchange
from app.universe_analysis.models import NseEquityInstrument

from .repository import TickSizeObservationRepository
from .tick_size import (
    NseTickSizeObservation,
    NseTickSizeSegment,
    TickSizeAvailabilitySemantics,
    TickSizeSourceClass,
)


_MASTER_FILE_NAMES = frozenset({"security.txt", "security.gz"})
_CM_RECORD_FIELD_COUNT = 43
_SUPPORTED_CASH_EQUITY_SERIES = frozenset({"EQ"})
_ISIN = re.compile(r"[A-Z]{2}[A-Z0-9]{9}[0-9]\Z")
_INTEGER = re.compile(r"-?\d+\Z")

# NSE/NDAL Masters Data CM ``security.txt`` documented field positions.
_TOKEN = 0
_SYMBOL = 1
_SERIES = 2
_INSTRUMENT_TYPE = 3
_TICK_SIZE_PAISE = 9
_DELETE_FLAG = 40
_ISIN_NUMBER = 42


@dataclass(frozen=True, slots=True)
class NseTickMasterImportFailure:
    line_number: int
    code: str


@dataclass(frozen=True, slots=True)
class NseTickMasterImportReport:
    source_file: str
    source_fingerprint: str
    observed_at: datetime
    source_header_date_seconds: int
    rows_seen: int
    eligible_rows: int
    accepted: int
    duplicates: int
    unresolved_identity: int
    invalid_tick: int
    malformed: int
    conflicts: int
    stopped: bool
    failures: tuple[NseTickMasterImportFailure, ...] = ()


class NseTickMasterLocalImporter:
    """Parse one strict local CM master and append exact mapped evidence only."""

    def __init__(
        self,
        repository: TickSizeObservationRepository,
        canonical_instruments: Iterable[NseEquityInstrument],
    ) -> None:
        self._repository = repository
        self._canonical_by_isin = _canonical_instruments_by_isin(canonical_instruments)

    def import_file(
        self, path: str | Path, *, observed_at: datetime | None = None,
    ) -> NseTickMasterImportReport:
        observed = observed_at or datetime.now(UTC)
        _require_aware(observed)
        source = Path(path)
        raw = _read_local_master(source)
        source_fingerprint = sha256(raw).hexdigest()
        header, lines = _parse_master(raw)
        candidates: dict[str, tuple[NseTickSizeObservation, int]] = {}
        conflict_ids: set[str] = set()
        failures: list[NseTickMasterImportFailure] = []
        rows_seen = eligible_rows = duplicates = unresolved = invalid_tick = malformed = conflicts = 0

        for line_number, fields in lines:
            rows_seen += 1
            parsed = _parse_row(fields)
            if parsed is None:
                malformed += 1
                _failure(failures, line_number, "NSE_TICK_MASTER_CASH_SCOPE_UNSUPPORTED")
                continue
            token, symbol, series, isin, raw_tick = parsed
            tick = _decode_tick_paise(raw_tick)
            if tick is None:
                invalid_tick += 1
                _failure(failures, line_number, "NSE_TICK_MASTER_TICK_INVALID")
                continue
            eligible_rows += 1
            identity = _exact_identity(self._canonical_by_isin, isin, symbol)
            if identity is None:
                unresolved += 1
                _failure(failures, line_number, "UNRESOLVED_IDENTITY")
                continue
            value = _observation(
                identity, isin=isin, tick=tick, source_file=source.name,
                source_fingerprint=source_fingerprint, source_header_date_seconds=header.date_seconds,
                observed_at=observed,
            )
            prior = candidates.get(value.canonical_instrument_id)
            if prior is None:
                candidates[value.canonical_instrument_id] = (value, line_number)
            elif prior[0].tick_size == value.tick_size:
                duplicates += 1
                _failure(failures, line_number, "SOURCE_ARTIFACT_DUPLICATE")
            else:
                conflict_ids.add(value.canonical_instrument_id)

        for canonical_instrument_id in sorted(conflict_ids):
            conflicts += 1
            line_number = candidates[canonical_instrument_id][1]
            _failure(failures, line_number, "SOURCE_ARTIFACT_CONFLICT")
            candidates.pop(canonical_instrument_id, None)

        accepted = 0
        for value, line_number in sorted(candidates.values(), key=lambda item: item[0].record_id):
            existing = self._repository.get_tick_size_observation(value.record_id)
            if existing is not None:
                if existing == value:
                    duplicates += 1
                    _failure(failures, line_number, "PERSISTED_ARTIFACT_DUPLICATE")
                    continue
                conflicts += 1
                _failure(failures, line_number, "PERSISTED_ARTIFACT_CONFLICT")
                continue
            self._repository.save_tick_size_observation(value)
            accepted += 1

        return NseTickMasterImportReport(
            source_file=source.name,
            source_fingerprint=source_fingerprint,
            observed_at=observed,
            source_header_date_seconds=header.date_seconds,
            rows_seen=rows_seen,
            eligible_rows=eligible_rows,
            accepted=accepted,
            duplicates=duplicates,
            unresolved_identity=unresolved,
            invalid_tick=invalid_tick,
            malformed=malformed,
            conflicts=conflicts,
            stopped=False,
            failures=tuple(failures),
        )


@dataclass(frozen=True, slots=True)
class _MasterHeader:
    date_seconds: int


def _read_local_master(path: Path) -> bytes:
    if path.name.lower() not in _MASTER_FILE_NAMES:
        raise ValueError("NSE_TICK_MASTER_FILENAME_UNSUPPORTED")
    try:
        raw = path.read_bytes()
        return gzip.decompress(raw) if path.suffix.lower() == ".gz" else raw
    except FileNotFoundError as error:
        raise ValueError("NSE_TICK_MASTER_FILE_NOT_FOUND") from error
    except OSError as error:
        raise ValueError("NSE_TICK_MASTER_GZIP_INVALID") from error


def _parse_master(raw: bytes) -> tuple[_MasterHeader, tuple[tuple[int, tuple[str, ...]], ...]]:
    try:
        lines = raw.decode("utf-8-sig").splitlines()
    except UnicodeDecodeError as error:
        raise ValueError("NSE_TICK_MASTER_TEXT_INVALID") from error
    if not lines:
        raise ValueError("NSE_TICK_MASTER_SCHEMA_UNSUPPORTED")
    header_fields = tuple(part.strip() for part in lines[0].split("|"))
    if len(header_fields) != 3 or header_fields[0] != "NEATCM" or not header_fields[1] or not _INTEGER.fullmatch(header_fields[2]):
        raise ValueError("NSE_TICK_MASTER_SCHEMA_UNSUPPORTED")
    records: list[tuple[int, tuple[str, ...]]] = []
    for line_number, line in enumerate(lines[1:], start=2):
        if not line.strip():
            continue
        fields = tuple(part.strip() for part in line.split("|"))
        if len(fields) != _CM_RECORD_FIELD_COUNT:
            raise ValueError("NSE_TICK_MASTER_SCHEMA_UNSUPPORTED")
        records.append((line_number, fields))
    return _MasterHeader(date_seconds=int(header_fields[2])), tuple(records)


def _parse_row(fields: tuple[str, ...]) -> tuple[str, str, str, str, str] | None:
    token, symbol, series = fields[_TOKEN], fields[_SYMBOL], fields[_SERIES]
    instrument_type, delete_flag, isin = fields[_INSTRUMENT_TYPE], fields[_DELETE_FLAG], fields[_ISIN_NUMBER]
    if not _INTEGER.fullmatch(token) or not symbol or not _ISIN.fullmatch(isin.upper()):
        return None
    if instrument_type != "0" or series.upper() not in _SUPPORTED_CASH_EQUITY_SERIES or delete_flag.upper() != "N":
        return None
    return token, symbol, series.upper(), isin.upper(), fields[_TICK_SIZE_PAISE]


def _decode_tick_paise(raw_tick: str) -> Decimal | None:
    if not _INTEGER.fullmatch(raw_tick):
        return None
    try:
        value = Decimal(raw_tick)
    except InvalidOperation:
        return None
    if not value.is_finite() or value <= Decimal("0"):
        return None
    return value / Decimal("100")


def _canonical_instruments_by_isin(
    instruments: Iterable[NseEquityInstrument],
) -> dict[str, tuple[NseEquityInstrument, ...]]:
    grouped: dict[str, list[NseEquityInstrument]] = {}
    for instrument in instruments:
        if (
            instrument.exchange.upper() == "NSE"
            and instrument.security_type.upper() == "EQUITY"
            and instrument.isin
        ):
            grouped.setdefault(instrument.isin.upper(), []).append(instrument)
    return {isin: tuple(values) for isin, values in grouped.items()}


def _exact_identity(
    canonical_by_isin: dict[str, tuple[NseEquityInstrument, ...]], isin: str, symbol: str,
) -> NseEquityInstrument | None:
    matches = canonical_by_isin.get(isin, ())
    if len(matches) != 1:
        return None
    value = matches[0]
    return value if value.symbol.upper() == symbol.upper() else None


def _observation(
    instrument: NseEquityInstrument, *, isin: str, tick: Decimal, source_file: str,
    source_fingerprint: str, source_header_date_seconds: int, observed_at: datetime,
) -> NseTickSizeObservation:
    record_id = "nse-tick:" + manifest_fingerprint(
        canonical_instrument_id=instrument.instrument_id,
        source_fingerprint=source_fingerprint,
        source_file=source_file,
        observed_at=observed_at.isoformat(),
    )[:32]
    return NseTickSizeObservation(
        record_id=record_id,
        canonical_instrument_id=instrument.instrument_id,
        exchange=Exchange.NSE,
        segment=NseTickSizeSegment.NSE_CASH_EQUITY,
        isin=isin,
        tick_size=tick,
        source_class=TickSizeSourceClass.OFFICIAL_EXCHANGE,
        source_name="NSE/NDAL Masters Data CM",
        source_artifact_fingerprint=source_fingerprint,
        observed_at=observed_at,
        effective_from=None,
        effective_to=None,
        availability_semantics=TickSizeAvailabilitySemantics.FIRST_OBSERVED_ONLY,
        warnings=(
            "NSE_CM_MASTER_LOCAL_IMPORT",
            f"SOURCE_FILE:{source_file}",
            f"SOURCE_HEADER_DATE_SECONDS:{source_header_date_seconds}",
        ),
    )


def _failure(
    values: list[NseTickMasterImportFailure], line_number: int, code: str,
) -> None:
    if len(values) < 20:
        values.append(NseTickMasterImportFailure(line_number, code))


def _require_aware(value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("NSE_TICK_OBSERVED_AT_NAIVE")
