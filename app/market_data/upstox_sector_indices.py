"""Bounded Upstox V3 history population for official NSE sector indices.

The module deliberately performs only operator-invoked mapping and ingestion.
It reads Task 38's already-persisted official NSE index identities, resolves
them against the public Upstox BOD master without fuzzy matching, and writes
through the existing immutable mapping and historical-bar boundaries.  It is
not a diagnostic dependency and never fetches data during a replay.
"""
from __future__ import annotations

import csv
import json
import re
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Callable, Iterable, Sequence

from app.market_data.historical import HistoricalCoverageStatus, HistoricalIngestionReport, HistoricalIngestionService
from app.market_data.models import (
    AdjustmentStatus, Exchange, HistoricalBarsRequest, InstrumentIdentity,
    InstrumentType, ProviderInstrumentMapping, Timeframe,
)
from app.market_data.upstox import UPSTOX_PROVIDER, UpstoxHistoricalProvider, UpstoxInstrumentRecord
from app.taxonomy.nse_sector_indices import NseSectorIndexMapping, SectorIndexMappingStatus
from app.universe_analysis.service import CoreUniverseAnalysisStore


NIFTY_500_INDEX_ID = "NIFTY_500"
NIFTY_500_INDEX_NAME = "NIFTY 500"

# These aliases were individually reviewed against the official NSE index
# registry and the Upstox NSE_INDEX BOD master.  They are provider-instrument
# identities, not name-search hints: an alias is usable only when the exact
# BOD instrument key occurs once among eligible NSE index records.
_REVIEWED_EXACT_INDEX_ALIASES: dict[str, str] = {
    "Nifty Financial Services": "NSE_INDEX|Nifty Fin Service",
    "Nifty Consumer Durables Index": "NSE_INDEX|NIFTY CONSR DURBL",
    "Nifty Healthcare Index": "NSE_INDEX|NIFTY HEALTHCARE",
}

RESOLVED_INDEX_MAPPING_STATUSES = frozenset({"EXACT", "NORMALIZED_EXACT", "REVIEWED_ALIAS"})


@dataclass(frozen=True, slots=True)
class UpstoxNseIndexMapping:
    canonical_sector: str | None
    official_index_name: str
    upstox_name: str | None
    trading_symbol: str | None
    instrument_key: str | None
    resolution_status: str
    canonical_instrument_id: str


@dataclass(frozen=True, slots=True)
class UpstoxNseIndexPopulationReport:
    mappings: tuple[UpstoxNseIndexMapping, ...]
    reports: tuple[HistoricalIngestionReport, ...]
    provider_requests: int

    @property
    def resolved(self) -> tuple[UpstoxNseIndexMapping, ...]:
        return tuple(item for item in self.mappings if item.resolution_status in RESOLVED_INDEX_MAPPING_STATUSES)


@dataclass(frozen=True, slots=True)
class UpstoxNseIndexHistoryStatus:
    canonical_instrument_id: str
    official_index_name: str
    yahoo_observations: int
    upstox_observations: int
    raw_observations: int
    canonical_observations: int
    canonical_upstox_selected: int
    canonical_yahoo_selected: int


def nse_index_records(records: Iterable[UpstoxInstrumentRecord]) -> tuple[UpstoxInstrumentRecord, ...]:
    """Retain only official BOD records that are explicitly NSE index records."""
    return tuple(
        item for item in records
        if item.segment.upper() == "NSE_INDEX" and (item.instrument_type or "").upper() == "INDEX"
    )


def resolve_official_nse_index_mappings(
    sector_mappings: Iterable[NseSectorIndexMapping], records: Iterable[UpstoxInstrumentRecord],
) -> tuple[UpstoxNseIndexMapping, ...]:
    """Resolve NIFTY 500 and Task 38's deterministic official sector identities.

    Only exact or punctuation/whitespace/case-normalised equality is permitted.
    More than one BOD candidate remains an explicit ambiguity.
    """
    eligible = nse_index_records(records)
    requests: list[tuple[str | None, str, str, InstrumentType]] = [
        (None, NIFTY_500_INDEX_NAME, NIFTY_500_INDEX_ID, InstrumentType.BROAD_INDEX),
    ]
    for mapping in sector_mappings:
        if mapping.status not in {
            SectorIndexMappingStatus.EXACT_OFFICIAL,
            SectorIndexMappingStatus.DETERMINISTIC_FROM_OFFICIAL_CONSTITUENTS,
        } or not mapping.official_index_name:
            continue
        requests.append((mapping.canonical_sector, mapping.official_index_name, _sector_index_id(mapping.canonical_sector), InstrumentType.SECTOR_INDEX))

    results: list[UpstoxNseIndexMapping] = []
    for sector, official_name, identifier, _ in requests:
        exact = tuple(item for item in eligible if _clean(item.trading_symbol) == _clean(official_name) or _clean(item.name) == _clean(official_name))
        if len(exact) == 1:
            item = exact[0]
            results.append(UpstoxNseIndexMapping(sector, official_name, item.name, item.trading_symbol, item.instrument_key, "EXACT", identifier))
            continue
        normalized = tuple(item for item in eligible if _normalised(item.trading_symbol) == _normalised(official_name) or _normalised(item.name) == _normalised(official_name))
        if len(normalized) == 1:
            item = normalized[0]
            results.append(UpstoxNseIndexMapping(sector, official_name, item.name, item.trading_symbol, item.instrument_key, "NORMALIZED_EXACT", identifier))
        elif len(exact) > 1 or len(normalized) > 1:
            results.append(UpstoxNseIndexMapping(sector, official_name, None, None, None, "AMBIGUOUS", identifier))
        elif (alias_key := _REVIEWED_EXACT_INDEX_ALIASES.get(official_name)) is not None:
            alias_matches = tuple(item for item in eligible if item.instrument_key == alias_key)
            if len(alias_matches) == 1:
                item = alias_matches[0]
                results.append(UpstoxNseIndexMapping(sector, official_name, item.name, item.trading_symbol, item.instrument_key, "REVIEWED_ALIAS", identifier))
            else:
                results.append(UpstoxNseIndexMapping(sector, official_name, None, None, None, "AMBIGUOUS" if len(alias_matches) > 1 else "UNRESOLVED", identifier))
        else:
            results.append(UpstoxNseIndexMapping(sector, official_name, None, None, None, "UNRESOLVED", identifier))
    return tuple(results)


def write_upstox_nse_index_mapping_reports(values: Sequence[UpstoxNseIndexMapping], directory: Path) -> tuple[Path, Path]:
    """Write public-safe mapping evidence; provider keys are routing metadata only."""
    directory.mkdir(parents=True, exist_ok=True)
    fields = ("canonical_sector", "official_index_name", "upstox_name", "trading_symbol", "instrument_key", "resolution_status", "canonical_instrument_id")
    json_path = directory / "upstox_nse_index_mapping.json"
    csv_path = directory / "upstox_nse_index_mapping.csv"
    rows = [asdict(item) for item in values]
    json_path.write_text(json.dumps({"mappings": rows}, indent=2, sort_keys=True), encoding="utf-8")
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader(); writer.writerows(rows)
    return json_path, csv_path


def stored_nse_index_history_status(
    store, sector_mappings: Iterable[NseSectorIndexMapping], *, start: datetime = datetime(1970, 1, 1, tzinfo=UTC), end: datetime = datetime.max.replace(tzinfo=UTC),
) -> tuple[UpstoxNseIndexHistoryStatus, ...]:
    """Read raw and canonical evidence only; it opens no provider client."""
    values: list[UpstoxNseIndexHistoryStatus] = [
        _history_status(store, NIFTY_500_INDEX_ID, NIFTY_500_INDEX_NAME, start, end),
    ]
    for mapping in sector_mappings:
        if mapping.status in {SectorIndexMappingStatus.EXACT_OFFICIAL, SectorIndexMappingStatus.DETERMINISTIC_FROM_OFFICIAL_CONSTITUENTS} and mapping.official_index_name:
            values.append(_history_status(store, _sector_index_id(mapping.canonical_sector), mapping.official_index_name, start, end))
    return tuple(values)


class UpstoxNseIndexPopulationService:
    """Persist only already-resolved official indices and their daily V3 bars."""

    def __init__(self, *, universe_store: CoreUniverseAnalysisStore, historical_store,
                 provider_factory: Callable[[str], UpstoxHistoricalProvider] = UpstoxHistoricalProvider,
                 clock: Callable[[], datetime] = lambda: datetime.now(UTC)) -> None:
        self._universe = universe_store
        self._historical = historical_store
        self._provider_factory = provider_factory
        self._clock = clock

    def populate(
        self, *, sector_mappings: Iterable[NseSectorIndexMapping], master_records: Iterable[UpstoxInstrumentRecord],
        access_token: str, years: int = 3, master_source_reference: str | None = None,
        master_checksum: str | None = None,
    ) -> UpstoxNseIndexPopulationReport:
        if not access_token:
            raise ValueError("UPSTOX_ACCESS_TOKEN_REQUIRED")
        if years < 1 or years > 3:
            raise ValueError("UPSTOX_INDEX_HISTORY_YEARS_MUST_BE_1_TO_3")
        at = self._clock().astimezone(UTC)
        start = at - timedelta(days=366 * years)
        mappings = resolve_official_nse_index_mappings(sector_mappings, master_records)
        provider = self._provider_factory(access_token)
        reports: list[HistoricalIngestionReport] = []
        for mapping in mappings:
            if mapping.resolution_status not in RESOLVED_INDEX_MAPPING_STATUSES:
                continue
            identity = _identity(mapping)
            self._persist_mapping(identity, at, master_source_reference, master_checksum)
            reports.append(HistoricalIngestionService(provider, self._historical, clock=self._clock).ingest(
                HistoricalBarsRequest(identity, Timeframe.DAILY, start, at, AdjustmentStatus.UNKNOWN, UPSTOX_PROVIDER)
            ))
        return UpstoxNseIndexPopulationReport(mappings, tuple(reports), len(reports))

    def probe(
        self, *, sector_mappings: Iterable[NseSectorIndexMapping], master_records: Iterable[UpstoxInstrumentRecord],
        access_token: str, years: int = 3,
    ) -> UpstoxNseIndexPopulationReport:
        """Make at most the required three bounded index-history requests.

        The probe deliberately does not write bars or mappings.  An operator
        must observe its result before invoking ``populate`` for the complete
        deterministic mapping set.
        """
        if not access_token:
            raise ValueError("UPSTOX_ACCESS_TOKEN_REQUIRED")
        if years < 1 or years > 3:
            raise ValueError("UPSTOX_INDEX_HISTORY_YEARS_MUST_BE_1_TO_3")
        at = self._clock().astimezone(UTC)
        mappings = resolve_official_nse_index_mappings(sector_mappings, master_records)
        resolved = [item for item in mappings if item.resolution_status in RESOLVED_INDEX_MAPPING_STATUSES]
        benchmark = next((item for item in resolved if item.canonical_sector is None), None)
        healthcare = next((item for item in resolved if _normalised(item.canonical_sector) == "healthcare"), None)
        third = next((item for item in resolved if item not in {benchmark, healthcare} and _normalised(item.canonical_sector) == "fast moving consumer goods"), None)
        third = third or next((item for item in resolved if item not in {benchmark, healthcare}), None)
        selected = tuple(item for item in (benchmark, healthcare, third) if item is not None)
        provider = self._provider_factory(access_token)
        reports = tuple(
            _probe_report(provider, _identity(mapping), at - timedelta(days=366 * years), at)
            for mapping in selected
        )
        return UpstoxNseIndexPopulationReport(mappings, reports, len(reports))

    def _persist_mapping(self, identity: InstrumentIdentity, at: datetime, source: str | None, checksum: str | None) -> None:
        current = self._universe.provider_mapping(canonical_instrument_id=identity.instrument_id, provider=UPSTOX_PROVIDER, as_of=at)
        reference = identity.provider_mappings[0].provider_instrument_reference
        if current is not None and current.provider_instrument_reference == reference:
            return
        self._universe.capture_provider_mapping(identity, provider=UPSTOX_PROVIDER, effective_as_of=at,
                                                source_reference=source or "upstox-nse-bod-json", source_checksum=checksum)


def _identity(mapping: UpstoxNseIndexMapping) -> InstrumentIdentity:
    assert mapping.instrument_key is not None
    return InstrumentIdentity(
        mapping.canonical_instrument_id, Exchange.INDEX, mapping.official_index_name,
        mapping.trading_symbol or mapping.official_index_name, None, None,
        InstrumentType.BROAD_INDEX if mapping.canonical_sector is None else InstrumentType.SECTOR_INDEX,
        mapping.official_index_name, provider_mappings=(ProviderInstrumentMapping(
            UPSTOX_PROVIDER, mapping.instrument_key, mapping.trading_symbol, "upstox-v3", "NSE_INDEX",
        ),),
    )


def _history_status(store, identifier: str, name: str, start: datetime, end: datetime) -> UpstoxNseIndexHistoryStatus:
    raw = store.raw_range(identifier, Timeframe.DAILY, start, end)
    canonical = store.range(identifier, Timeframe.DAILY, start, end)
    return UpstoxNseIndexHistoryStatus(
        identifier, name,
        sum(item.provenance.provider.casefold() in {"yahoo", "yfinance", "yahoo_finance"} for item in raw),
        sum(item.provenance.provider.casefold() == UPSTOX_PROVIDER for item in raw), len(raw), len(canonical),
        sum(item.provenance.provider.casefold() == UPSTOX_PROVIDER for item in canonical),
        sum(item.provenance.provider.casefold() in {"yahoo", "yfinance", "yahoo_finance"} for item in canonical),
    )


def _probe_report(provider: UpstoxHistoricalProvider, identity: InstrumentIdentity, start: datetime, end: datetime) -> HistoricalIngestionReport:
    """Build an auditable, non-persisting report from a single V3 request."""
    bars = provider.get_historical_bars(HistoricalBarsRequest(identity, Timeframe.DAILY, start, end, AdjustmentStatus.UNKNOWN, UPSTOX_PROVIDER))
    return HistoricalIngestionReport(
        UPSTOX_PROVIDER, identity.instrument_id, Timeframe.DAILY, start, end, len(bars), len(bars), 0, 0, 0, 0,
        bars[0].start_time if bars else None, bars[-1].end_time if bars else None, AdjustmentStatus.UNKNOWN,
        # A successful V3 response is usable even if it does not span every
        # calendar day; exchange session-gap assessment belongs to the store.
        HistoricalCoverageStatus.COMPLETE if bars else HistoricalCoverageStatus.UNAVAILABLE,
        tuple(sorted({warning for bar in bars for warning in bar.warnings})),
        tuple(sorted({bar.provenance.source_reference or UPSTOX_PROVIDER for bar in bars})), start, end,
    )


def _sector_index_id(value: str) -> str:
    return "NSE_SECTOR_INDEX:" + _normalised(value).replace(" ", "_").upper()


def _clean(value: object) -> str:
    return " ".join(str(value or "").split()).casefold()


def _normalised(value: object) -> str:
    # This is intentionally only case/whitespace/punctuation equivalence.  It
    # never turns synonymous names (for example Banks/Financial Services) into
    # a match.
    return " ".join(re.sub(r"[^a-z0-9]+", " ", _clean(value)).split())


__all__ = (
    "NIFTY_500_INDEX_ID", "NIFTY_500_INDEX_NAME", "UpstoxNseIndexMapping",
    "UpstoxNseIndexPopulationReport", "UpstoxNseIndexPopulationService", "UpstoxNseIndexHistoryStatus",
    "nse_index_records", "resolve_official_nse_index_mappings", "write_upstox_nse_index_mapping_reports",
    "RESOLVED_INDEX_MAPPING_STATUSES",
    "stored_nse_index_history_status",
)
