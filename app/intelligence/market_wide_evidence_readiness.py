"""Deterministic, stored-evidence readiness for the governed NIFTY 500.

This is deliberately categorical.  It neither fetches data nor turns missing
optional evidence into a universal discovery gate.
"""
from __future__ import annotations

from dataclasses import dataclass, fields
from datetime import datetime
from enum import StrEnum
from typing import Callable, Protocol

from app.domain.models import DiagnosticResult
from app.historical.guard import manifest_fingerprint
from app.market_data.models import Timeframe
from app.market_data.ohlcv_readiness import OhlcvReadinessService, OhlcvReadinessStatus


READINESS_CONTRACT = "market-wide-evidence-readiness/v1"


class EvidenceReadinessState(StrEnum):
    READY = "EVIDENCE_READY"
    PARTIAL = "EVIDENCE_PARTIAL"
    UNAVAILABLE = "EVIDENCE_UNAVAILABLE"


class DomainReadinessState(StrEnum):
    READY = "READY"
    PARTIAL = "PARTIAL"
    UNAVAILABLE = "UNAVAILABLE"


class _DiagnosticSource(Protocol):
    def latest_canonical_diagnostic_results(self, canonical_instrument_id: str, *, as_of: datetime) -> tuple[DiagnosticResult, ...]: ...


@dataclass(frozen=True, slots=True)
class MarketWideEvidenceReadinessRecord:
    canonical_instrument_id: str
    symbol: str
    intelligence_as_of: datetime
    latest_completed_session: datetime | None
    readiness: EvidenceReadinessState
    domain_states: tuple[tuple[str, DomainReadinessState], ...]
    blocker_codes: tuple[str, ...]
    evidence_references: tuple[str, ...]
    policy_identity: str
    fingerprint: str

    @classmethod
    def create(cls, **values) -> "MarketWideEvidenceReadinessRecord":
        values["domain_states"] = tuple(sorted(dict(values["domain_states"]).items()))
        values["blocker_codes"] = tuple(sorted(set(values["blocker_codes"])))
        values["evidence_references"] = tuple(sorted(set(values["evidence_references"])))
        provisional = cls(**values, fingerprint="")
        return cls(**{**values, "fingerprint": manifest_fingerprint(**_semantic(provisional))})


@dataclass(frozen=True, slots=True)
class MarketWideEvidenceReadinessRun:
    readiness_as_of: datetime
    universe_id: str
    records: tuple[MarketWideEvidenceReadinessRecord, ...]
    readiness_counts: tuple[tuple[str, int], ...]
    domain_counts: tuple[tuple[str, int], ...]
    blocker_attribution: tuple[tuple[str, int], ...]
    policy_identity: str
    fingerprint: str

    @classmethod
    def create(cls, **values) -> "MarketWideEvidenceReadinessRun":
        values["records"] = tuple(sorted(values["records"], key=lambda value: value.canonical_instrument_id))
        values["readiness_counts"] = tuple(sorted(values["readiness_counts"]))
        values["domain_counts"] = tuple(sorted(values["domain_counts"]))
        values["blocker_attribution"] = tuple(sorted(values["blocker_attribution"]))
        provisional = cls(**values, fingerprint="")
        return cls(**{**values, "fingerprint": manifest_fingerprint(**_semantic(provisional))})


class MarketWideEvidenceReadinessService:
    """Compose a reusable readiness read-model from canonical stored evidence."""

    def __init__(
        self, *, historical, diagnostics: _DiagnosticSource,
        financial_fact_count: Callable[[str], int] | None = None,
        filing_count: Callable[[str], int] | None = None,
        ownership_available: Callable[[str], bool] | None = None,
        news_available: Callable[[str], bool] | None = None,
        reliability_available: Callable[[str], bool] | None = None,
    ) -> None:
        self._ohlcv = OhlcvReadinessService(historical)
        self._diagnostics = diagnostics
        self._financial_fact_count = financial_fact_count or (lambda _id: 0)
        self._filing_count = filing_count or (lambda _id: 0)
        self._ownership_available = ownership_available or (lambda _id: False)
        self._news_available = news_available or (lambda _id: False)
        self._reliability_available = reliability_available or (lambda _id: False)

    def assess(self, instruments, *, as_of: datetime) -> MarketWideEvidenceReadinessRun:
        if as_of.tzinfo is None or as_of.utcoffset() is None:
            raise ValueError("MARKET_WIDE_EVIDENCE_READINESS_AS_OF_REQUIRED")
        records = tuple(self._record(item, as_of=as_of) for item in instruments)
        readiness_counts = tuple((state.value, sum(item.readiness is state for item in records)) for state in EvidenceReadinessState)
        domains = sorted({domain for item in records for domain, _ in item.domain_states})
        domain_counts = tuple((f"{domain}:{state.value}", sum(dict(item.domain_states).get(domain) is state for item in records)) for domain in domains for state in DomainReadinessState)
        blockers = sorted({blocker for item in records for blocker in item.blocker_codes})
        blocker_attribution = tuple((blocker, sum(blocker in item.blocker_codes for item in records)) for blocker in blockers)
        return MarketWideEvidenceReadinessRun.create(
            readiness_as_of=as_of, universe_id="NIFTY_500", records=records,
            readiness_counts=readiness_counts, domain_counts=domain_counts,
            blocker_attribution=blocker_attribution, policy_identity=READINESS_CONTRACT,
        )

    def _record(self, instrument, *, as_of: datetime) -> MarketWideEvidenceReadinessRecord:
        identifier = instrument.instrument_id
        ohlcv = self._ohlcv.assess(identifier, as_of=as_of)
        market = DomainReadinessState.READY if ohlcv.session_count >= 200 and ohlcv.status is not OhlcvReadinessStatus.CONFLICTED else (
            DomainReadinessState.PARTIAL if ohlcv.session_count else DomainReadinessState.UNAVAILABLE
        )
        # The same governed 200-session minimum supports the existing moving
        # averages, RSI, ATR, BBW and high-window calculations.  A shorter
        # legitimate listing is partial, not an acquisition error.
        technical = DomainReadinessState.READY if ohlcv.session_count >= 200 else (
            DomainReadinessState.PARTIAL if ohlcv.session_count else DomainReadinessState.UNAVAILABLE
        )
        diagnostics = self._diagnostics.latest_canonical_diagnostic_results(identifier, as_of=as_of)
        diagnostic_state = DomainReadinessState.READY if len({str(value.rule_id) for value in diagnostics}) >= 61 else (
            DomainReadinessState.PARTIAL if diagnostics else DomainReadinessState.UNAVAILABLE
        )
        financial = self._financial_fact_count(identifier) > 0 and self._filing_count(identifier) > 0
        domains = {
            "IDENTITY": DomainReadinessState.READY if identifier.startswith("NSE:") else DomainReadinessState.UNAVAILABLE,
            "TAXONOMY": DomainReadinessState.READY if getattr(instrument, "sector", None) else DomainReadinessState.PARTIAL,
            "MARKET_DATA": market,
            "TECHNICAL": technical,
            "FINANCIALS": DomainReadinessState.READY if financial else DomainReadinessState.UNAVAILABLE,
            "EARNINGS": DomainReadinessState.READY if financial else DomainReadinessState.UNAVAILABLE,
            "OWNERSHIP": DomainReadinessState.READY if self._ownership_available(identifier) else DomainReadinessState.UNAVAILABLE,
            "NEWS": DomainReadinessState.READY if self._news_available(identifier) else DomainReadinessState.PARTIAL,
            "RELIABILITY": DomainReadinessState.READY if self._reliability_available(identifier) else DomainReadinessState.UNAVAILABLE,
            "CANONICAL_DIAGNOSTICS": diagnostic_state,
        }
        blockers: list[str] = []
        if domains["IDENTITY"] is not DomainReadinessState.READY: blockers.append("CANONICAL_IDENTITY_UNRESOLVED")
        if market is not DomainReadinessState.READY: blockers.append(ohlcv.reason)
        if technical is not DomainReadinessState.READY: blockers.append("INSUFFICIENT_LISTING_HISTORY" if ohlcv.session_count else "TECHNICAL_HISTORY_UNAVAILABLE")
        if not financial: blockers.append("OFFICIAL_FINANCIAL_EVIDENCE_UNAVAILABLE")
        if diagnostic_state is not DomainReadinessState.READY: blockers.append("CANONICAL_DIAGNOSTICS_NOT_MATERIALIZED")
        # Basic discovery readiness intentionally excludes optional domains;
        # their absence is visible but never silently becomes a global gate.
        core = (domains["IDENTITY"], market, technical)
        readiness = EvidenceReadinessState.READY if all(value is DomainReadinessState.READY for value in core) else (
            EvidenceReadinessState.PARTIAL if any(value is not DomainReadinessState.UNAVAILABLE for value in core) else EvidenceReadinessState.UNAVAILABLE
        )
        references = tuple(value.id for value in diagnostics)
        return MarketWideEvidenceReadinessRecord.create(
            canonical_instrument_id=identifier, symbol=instrument.symbol, intelligence_as_of=as_of,
            latest_completed_session=ohlcv.latest_bar_at, readiness=readiness,
            domain_states=tuple(domains.items()), blocker_codes=tuple(blockers), evidence_references=references,
            policy_identity=READINESS_CONTRACT,
        )


def _semantic(value) -> dict:
    def normalize(item):
        if isinstance(item, StrEnum): return item.value
        if isinstance(item, datetime): return item.isoformat()
        if isinstance(item, tuple): return tuple(normalize(part) for part in item)
        return item
    return {field.name: normalize(getattr(value, field.name)) for field in fields(value) if field.name != "fingerprint"}


__all__ = (
    "DomainReadinessState", "EvidenceReadinessState", "MarketWideEvidenceReadinessRecord",
    "MarketWideEvidenceReadinessRun", "MarketWideEvidenceReadinessService", "READINESS_CONTRACT",
)
