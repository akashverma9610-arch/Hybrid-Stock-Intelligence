"""One completed NSE session, separate from the frozen historical backfill.

Reuses the official archive, exact-identity parser and provider-versioned bar
writer. This job does not select a technical price basis or claim index coverage.
The existing calendar supplies session completion, never the machine weekday.
"""
from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from hashlib import sha256
from typing import Iterable
from zoneinfo import ZoneInfo

from app.data_operations.models import (
    EvidenceRefreshFailureKind, EvidenceRefreshOutcome, EvidenceRefreshRequest,
    EvidenceRefreshStatus, ReconciliationStatus,
)
from app.historical.canonical_market_session_event_time import (
    CanonicalMarketSessionCalendar, SessionPhaseType, TradingDayState,
)
from app.market_data.historical import BarWriteOutcome, HistoricalBarStore
from app.market_data.models import MarketDataQualityValidator
from app.market_data.nse_udiff_daily_history import (
    NSE_UDIFF_BAR_PROVIDER, NSE_UDIFF_END, NseUdiffDailyHistoryStore,
    NseUdiffDailySource, NseUdiffDailyStatus, NseUdiffDailyTarget,
    NseUdiffIdentityStatus, _artifact_from_bytes, _bar_from_row,
    _parse_valid_archive, _resolve_target, _upsert_many,
)

CONTRACT = "current-nse-eod/v1"


def latest_completed_session(calendar: CanonicalMarketSessionCalendar, *, as_of: datetime) -> tuple[date, datetime]:
    if as_of.tzinfo is None or as_of.utcoffset() is None:
        raise ValueError("CURRENT_EOD_AWARE_CUTOFF_REQUIRED")
    calendar.__post_init__()
    day = as_of.astimezone(ZoneInfo(calendar.timezone_id)).date()
    if not calendar.coverage_start <= day <= calendar.coverage_end:
        raise ValueError("CURRENT_EOD_CALENDAR_OUTSIDE_COVERAGE")
    while day >= calendar.coverage_start:
        resolved = calendar.resolve_trading_day(day, as_of=as_of)
        if resolved.state is TradingDayState.UNKNOWN:
            raise ValueError("CURRENT_EOD_CALENDAR_UNRESOLVED")
        if resolved.state in {TradingDayState.REGULAR_TRADING_DAY, TradingDayState.SPECIAL_TRADING_DAY, TradingDayState.MUHURAT_TRADING}:
            phases = tuple(p for p in calendar.phases_for(day, as_of=as_of)
                           if p.phase_type is SessionPhaseType.REGULAR_CONTINUOUS)
            if len(phases) != 1:
                raise ValueError("CURRENT_EOD_SESSION_CLOSE_UNRESOLVED")
            close = phases[0].ends_at.astimezone(UTC)
            if close <= as_of:
                return day, close
        day -= timedelta(days=1)
    raise ValueError("CURRENT_EOD_COMPLETED_SESSION_UNAVAILABLE")


class CurrentNseEodRefreshJob:
    """Shared explicit target set; a single fetch per session, no user context.

    Run receipts retain ingestion completion independently of archive observed_at.
    Replays reuse the retained archive (including its first observation time).
    This additive job is not installed into automatic runtime composition here.
    """

    def __init__(self, *, source: NseUdiffDailySource, evidence: NseUdiffDailyHistoryStore,
                 bars: HistoricalBarStore, targets: Iterable[NseUdiffDailyTarget],
                 calendar: CanonicalMarketSessionCalendar, universe_reference: str,
                 universe_as_of: datetime):
        values = tuple(sorted(targets, key=lambda t: t.canonical_instrument_id))
        if not values or not universe_reference.strip():
            raise ValueError("CURRENT_EOD_TARGETS_AND_UNIVERSE_REQUIRED")
        if universe_as_of.tzinfo is None or universe_as_of.utcoffset() is None:
            raise ValueError("CURRENT_EOD_UNIVERSE_AWARE_TIME_REQUIRED")
        self._universe_as_of = universe_as_of.astimezone(UTC)
        if len({t.isin for t in values}) != len(values) or len({t.canonical_instrument_id for t in values}) != len(values):
            raise ValueError("CURRENT_EOD_TARGET_IDENTITY_AMBIGUOUS")
        self._targets = {t.isin: t for t in values}
        self._source, self._evidence, self._bars, self._calendar = source, evidence, bars, calendar
        # Full target identities distinguish shared scopes, not account/user IDs.
        scope = repr((CONTRACT, universe_reference, self._universe_as_of.isoformat(), calendar.fingerprint,
                      tuple((t.canonical_instrument_id, t.isin, t.current_symbol) for t in values)))
        self.acquisition_id = "nse-udiff-acquisition:current:" + sha256(scope.encode()).hexdigest()

    def refresh(self, request: EvidenceRefreshRequest) -> EvidenceRefreshOutcome:
        if self._universe_as_of > request.requested_as_of:
            return self._blocked("CURRENT_EOD_UNIVERSE_NOT_PIT_VISIBLE")
        try:
            session, closed_at = latest_completed_session(self._calendar, as_of=request.requested_as_of)
        except ValueError as error:
            return self._blocked(str(error))
        if session <= NSE_UDIFF_END:
            return self._blocked("CURRENT_EOD_FROZEN_BACKFILL_SESSION_EXCLUDED")
        artifact = self._evidence.artifact(self.acquisition_id, session)
        if artifact is None:
            fetched = self._source.fetch(session)
            if fetched.status is not NseUdiffDailyStatus.ARTIFACT_VALID:
                return self._blocked(fetched.error_code or fetched.status.value,
                                     transient=fetched.status is NseUdiffDailyStatus.SOURCE_TRANSPORT_FAILURE)
            if fetched.trade_date != session or fetched.observed_at < closed_at:
                return self._blocked("CURRENT_EOD_SOURCE_SESSION_OR_RECEIPT_INVALID")
            artifact = _artifact_from_bytes(self.acquisition_id, fetched)
            self._evidence.save_artifact(artifact)
        artifact.__post_init__()
        if artifact.acquisition_id != self.acquisition_id or artifact.trade_date != session or artifact.observed_at < closed_at:
            return self._blocked("CURRENT_EOD_RETAINED_ARTIFACT_SCOPE_INVALID")
        if artifact.schema_status is not NseUdiffDailyStatus.ARTIFACT_VALID:
            return self._blocked(artifact.schema_status.value)
        parsed = _parse_valid_archive(artifact)
        grouped = {}
        findings = []
        for index, row in enumerate(parsed.rows):
            status, target = _resolve_target(row, self._targets)
            if status is NseUdiffIdentityStatus.OUT_OF_ELIGIBLE_UNIVERSE:
                continue
            if target is None or status is not NseUdiffIdentityStatus.EXACT_IDENTITY_RESOLVED:
                findings.append((ReconciliationStatus.GAP_FOUND, row.get("ISIN", "UNRESOLVED"), status.value))
                continue
            grouped.setdefault(target.canonical_instrument_id, []).append((index, row, target))
        bars = []
        for target in self._targets.values():
            rows = grouped.get(target.canonical_instrument_id, ())
            if len(rows) != 1:
                findings.append((ReconciliationStatus.GAP_FOUND, target.canonical_instrument_id,
                                 "CURRENT_EOD_TARGET_MISSING" if not rows else "CURRENT_EOD_TARGET_AMBIGUOUS"))
                continue
            index, row, target = rows[0]
            try:
                bar, _ = _bar_from_row(artifact, parsed, index, row, target)
                MarketDataQualityValidator.validate_bar(bar)
            except ValueError:
                findings.append((ReconciliationStatus.INVALID_EVIDENCE, target.canonical_instrument_id, "CURRENT_EOD_ROW_INVALID"))
                continue
            bars.append(bar)
        outcomes = _upsert_many(self._bars, bars)
        conflicts = sum(x is BarWriteOutcome.CONFLICT for x in outcomes)
        accepted = sum(x is BarWriteOutcome.INSERTED for x in outcomes)
        duplicates = sum(x is BarWriteOutcome.IDENTICAL for x in outcomes)
        verified = bool(bars) and not conflicts and all(self._bars.same_provider_bar(bar) == bar for bar in bars)
        if bars and not conflicts and not verified:
            return self._blocked("CURRENT_EOD_STORE_READBACK_FAILED")
        # No COMPLETE if even one requested identity lacks a valid canonical bar.
        status = (EvidenceRefreshStatus.CONFLICT_FOUND if conflicts else
                  EvidenceRefreshStatus.PARTIAL if findings else
                  EvidenceRefreshStatus.COMPLETE if accepted else EvidenceRefreshStatus.NO_CHANGE)
        return EvidenceRefreshOutcome(
            status, NSE_UDIFF_BAR_PROVIDER, discovered_count=len(parsed.rows),
            accepted_count=accepted, duplicate_count=duplicates, conflict_count=conflicts,
            gap_count=len(findings), accepted_through=closed_at if bars and not conflicts else None,
            verified_from_store=verified,
            source_fingerprint=artifact.fingerprint,
            source_references=tuple(sorted((artifact.artifact_id, self._calendar.calendar_id))),
            warnings=("CURRENT_EOD_RAW_ONLY_TECHNICAL_ELIGIBILITY_NOT_GRANTED", "SOURCE_PUBLICATION_TIME_UNAVAILABLE"),
            findings=tuple(sorted(set(findings))),
        )

    @staticmethod
    def _blocked(reason: str, *, transient: bool = False) -> EvidenceRefreshOutcome:
        return EvidenceRefreshOutcome(
            EvidenceRefreshStatus.SOURCE_UNAVAILABLE, NSE_UDIFF_BAR_PROVIDER,
            failure_kind=EvidenceRefreshFailureKind.TRANSIENT if transient else EvidenceRefreshFailureKind.SOURCE_UNAVAILABLE,
            error_summary=reason, warnings=(reason,),
        )
