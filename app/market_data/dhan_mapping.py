"""Immutable, ISIN-first Dhan provider-mapping materialization.

This module consumes only the canonical portfolio and stored Top-3 finder
sources.  It neither obtains credentials nor invokes Dhan market endpoints.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol

from app.market_data.dhan import DHAN_PROVIDER, DhanInstrumentMaster, DhanInstrumentRecord, DhanLtpTarget
from app.market_data.models import Exchange, InstrumentIdentity, InstrumentType, ProviderInstrumentMapping
from app.universe_analysis.models import NseEquityInstrument, ProviderInstrumentMappingRecord


class DhanMappingStatus(StrEnum):
    MAPPED_EXACT = "MAPPED_EXACT"
    IDENTICAL_EXISTING = "IDENTICAL_EXISTING"
    PROVIDER_IDENTITY_NOT_FOUND = "PROVIDER_IDENTITY_NOT_FOUND"
    AMBIGUOUS_PROVIDER_IDENTITY = "AMBIGUOUS_PROVIDER_IDENTITY"
    SYMBOL_CONFLICT = "SYMBOL_CONFLICT"
    SECURITY_CLASS_MISMATCH = "SECURITY_CLASS_MISMATCH"
    EXISTING_MAPPING_CONFLICT = "EXISTING_MAPPING_CONFLICT"


@dataclass(frozen=True, slots=True)
class DhanCurrentTargetSet:
    portfolio_ids: tuple[str, ...]
    top3_ids: tuple[str, ...]
    setup_ids: tuple[str, ...]
    canonical_instrument_ids: tuple[str, ...]

    @property
    def count(self) -> int:
        return len(self.canonical_instrument_ids)


@dataclass(frozen=True, slots=True)
class DhanMappingOutcome:
    canonical_instrument_id: str
    isin: str | None
    symbol: str
    status: DhanMappingStatus
    mapping: ProviderInstrumentMappingRecord | None = None
    dhan_security_id: int | None = None


@dataclass(frozen=True, slots=True)
class DhanMappingMaterialization:
    target_set: DhanCurrentTargetSet
    master_fingerprint: str
    effective_as_of: datetime
    outcomes: tuple[DhanMappingOutcome, ...]

    @property
    def created_count(self) -> int:
        return sum(item.status is DhanMappingStatus.MAPPED_EXACT for item in self.outcomes)

    @property
    def identical_count(self) -> int:
        return sum(item.status is DhanMappingStatus.IDENTICAL_EXISTING for item in self.outcomes)

    @property
    def blocked_count(self) -> int:
        return len(self.outcomes) - self.created_count - self.identical_count


class _PortfolioSource(Protocol):
    def get_snapshot(self): ...


class _Top3Source(Protocol):
    def list(self): ...


class _SetupOpportunitySource(Protocol):
    def list(self, *, as_of: datetime): ...


class _UniverseStore(Protocol):
    def instruments_as_of(self, at: datetime) -> tuple[NseEquityInstrument, ...]: ...
    def provider_mapping(self, *, canonical_instrument_id: str, provider: str, as_of: datetime | None = None) -> ProviderInstrumentMappingRecord | None: ...
    def capture_provider_mapping(self, instrument: InstrumentIdentity, *, provider: str, effective_as_of: datetime, resolved_instrument: InstrumentIdentity | None = None, source_reference: str | None = None, source_checksum: str | None = None, provider_instrument_type: str | None = None, provider_name: str | None = None, raw_provider_exchange: str | None = None, raw_provider_segment: str | None = None, raw_provider_instrument: str | None = None, raw_provider_instrument_type: str | None = None, raw_provider_series: str | None = None, normalized_instrument: str | None = None) -> ProviderInstrumentMappingRecord: ...


def current_dhan_targets(
    *, portfolio: _PortfolioSource, top3_runs: _Top3Source,
    setup_opportunities: _SetupOpportunitySource | None = None, as_of: datetime | None = None,
) -> DhanCurrentTargetSet:
    """Return the exact, de-duplicated stored target union without symbols.

    Setup monitoring reads existing canonical setup artifacts only.  It never
    forms a setup merely to subscribe an instrument.
    """
    holdings = portfolio.get_snapshot().holdings
    portfolio_ids = tuple(sorted({item.instrument_id for item in holdings if item.active and item.instrument_id}))
    runs = tuple(top3_runs.list())
    top3_ids = tuple(sorted(set(runs[-1].candidate_ids))) if runs else ()
    setup_ids = () if setup_opportunities is None else tuple(sorted({
        item.canonical_instrument_id for item in setup_opportunities.list(as_of=as_of or datetime.now().astimezone())
        if item.canonical_instrument_id
    }))
    return DhanCurrentTargetSet(
        portfolio_ids, top3_ids, setup_ids,
        tuple(sorted(set(portfolio_ids) | set(top3_ids) | set(setup_ids))),
    )


class DhanProviderMappingService:
    """Persist only a previously validated official-master Dhan mapping."""
    def __init__(self, universe: _UniverseStore) -> None:
        self._universe = universe

    def materialize(self, *, targets: DhanCurrentTargetSet, master: DhanInstrumentMaster, as_of: datetime) -> DhanMappingMaterialization:
        if as_of.tzinfo is None or as_of.utcoffset() is None:
            raise ValueError("DHAN_MAPPING_AS_OF_NAIVE")
        by_id = {item.instrument_id: item for item in self._universe.instruments_as_of(as_of)}
        outcomes = tuple(self._materialize_one(by_id.get(identifier), master, as_of) for identifier in targets.canonical_instrument_ids)
        return DhanMappingMaterialization(targets, master.fingerprint, as_of, outcomes)

    def ltp_targets(self, *, targets: DhanCurrentTargetSet, as_of: datetime) -> tuple[DhanLtpTarget, ...]:
        """Read stored mappings only; never resolve or fetch the master during live LTP."""
        result: list[DhanLtpTarget] = []
        for identifier in targets.canonical_instrument_ids:
            record = self._universe.provider_mapping(canonical_instrument_id=identifier, provider=DHAN_PROVIDER, as_of=as_of)
            if record is None or record.provider_exchange_segment != "NSE_EQ":
                raise ValueError("DHAN_CURRENT_TARGET_MAPPING_MISSING")
            try:
                security_id = int(record.provider_instrument_reference)
            except ValueError:
                raise ValueError("DHAN_CURRENT_TARGET_MAPPING_INVALID") from None
            result.append(DhanLtpTarget(identifier, record.provider_exchange_segment, security_id))
        return tuple(result)

    def _materialize_one(self, instrument: NseEquityInstrument | None, master: DhanInstrumentMaster, as_of: datetime) -> DhanMappingOutcome:
        if instrument is None:
            return DhanMappingOutcome("UNKNOWN", None, "UNKNOWN", DhanMappingStatus.PROVIDER_IDENTITY_NOT_FOUND)
        if instrument.exchange.upper() != "NSE" or instrument.security_type.upper() != "EQUITY" or not instrument.isin:
            return DhanMappingOutcome(instrument.instrument_id, instrument.isin, instrument.symbol, DhanMappingStatus.SECURITY_CLASS_MISMATCH)
        record, status = _resolve_exact(instrument, master.records)
        if record is None:
            return DhanMappingOutcome(instrument.instrument_id, instrument.isin, instrument.symbol, status)
        existing = self._universe.provider_mapping(canonical_instrument_id=instrument.instrument_id, provider=DHAN_PROVIDER, as_of=as_of)
        if existing is not None:
            if (
                existing.provider_instrument_reference == str(record.security_id)
                and existing.provider_exchange_segment == "NSE_EQ"
                and existing.source_checksum == master.fingerprint
            ):
                return DhanMappingOutcome(instrument.instrument_id, instrument.isin, instrument.symbol, DhanMappingStatus.IDENTICAL_EXISTING, existing, record.security_id)
            # A changed master gets a new effective mapping only after a later,
            # explicit reconciliation policy.  This operation never rewrites it.
            return DhanMappingOutcome(instrument.instrument_id, instrument.isin, instrument.symbol, DhanMappingStatus.EXISTING_MAPPING_CONFLICT, existing, record.security_id)
        identity = InstrumentIdentity(
            instrument.instrument_id, Exchange.NSE, instrument.symbol, instrument.symbol, instrument.isin,
            None, InstrumentType.NSE_EQUITY, instrument.company_name,
        )
        resolved = InstrumentIdentity(
            identity.instrument_id, identity.exchange, identity.symbol, identity.trading_symbol, identity.isin,
            identity.series, identity.instrument_type, identity.name,
            provider_mappings=(ProviderInstrumentMapping(DHAN_PROVIDER, str(record.security_id), record.trading_symbol, "dhan-v2-master", "NSE_EQ"),),
        )
        saved = self._universe.capture_provider_mapping(
            identity, provider=DHAN_PROVIDER, effective_as_of=as_of, resolved_instrument=resolved,
            source_reference=master.source_url, source_checksum=master.fingerprint,
            provider_instrument_type=record.raw_instrument_type, provider_name=record.name,
            raw_provider_exchange=record.exchange, raw_provider_segment=record.segment,
            raw_provider_instrument=record.instrument, raw_provider_instrument_type=record.raw_instrument_type,
            raw_provider_series=record.series, normalized_instrument="EQUITY",
        )
        return DhanMappingOutcome(instrument.instrument_id, instrument.isin, instrument.symbol, DhanMappingStatus.MAPPED_EXACT, saved, record.security_id)


def _resolve_exact(instrument: NseEquityInstrument, records: tuple[DhanInstrumentRecord, ...]) -> tuple[DhanInstrumentRecord | None, DhanMappingStatus]:
    same_isin = tuple(item for item in records if item.isin and item.isin.upper() == instrument.isin.upper())
    # The detailed master uses ``E`` for its raw equity segment.  It is not
    # the API request enum; a row becomes ``NSE_EQ`` only after all four raw
    # source dimensions establish an ordinary NSE equity.
    candidates = tuple(
        item for item in same_isin
        if item.exchange == "NSE"
        and item.segment in {"E", "EQ", "NSE_EQ"}
        and (not item.instrument or item.instrument.upper() in {"EQ", "EQUITY"})
        and (not item.series or item.series.upper() == "EQ")
    )
    if not candidates:
        return None, DhanMappingStatus.SECURITY_CLASS_MISMATCH if same_isin else DhanMappingStatus.PROVIDER_IDENTITY_NOT_FOUND
    if len(candidates) != 1:
        return None, DhanMappingStatus.AMBIGUOUS_PROVIDER_IDENTITY
    candidate = candidates[0]
    expected = (instrument.symbol or "").upper()
    if expected and candidate.trading_symbol and candidate.trading_symbol.upper() != expected:
        return None, DhanMappingStatus.SYMBOL_CONFLICT
    return candidate, DhanMappingStatus.MAPPED_EXACT
