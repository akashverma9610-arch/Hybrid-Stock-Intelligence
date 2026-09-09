"""Deterministic proofs for canonical prospective 15m bar derivation."""
from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from app.historical.canonical_market_session_event_time import (
    SessionPhaseType,
    TradingDayState,
    make_canonical_market_session_calendar,
    make_effective_session_phase_timing,
    make_first_party_session_source,
    make_special_trading_day,
)
from app.historical.nse_capital_market_session_evidence_2022_2026 import nse_capital_market_calendar_2022_2026
from app.market_data.models import AdjustmentStatus, Exchange
from app.market_data.dhan_live_bar import (
    DhanProspectiveInstrumentIdentity,
    DhanQuotePacket,
    ProspectiveDhanOneMinuteBarBuilder,
    bind_dhan_event_to_regular_minute,
    normalize_dhan_quote_packet,
)
from app.market_data.prospective_fifteen_minute_bar import (
    POLICY_FINGERPRINT,
    CanonicalProspectiveFifteenMinuteSession,
    ProspectiveCanonicalFifteenMinuteStore,
    ProspectiveFifteenMinuteBarError,
    ProspectiveFifteenMinuteReason,
    ProspectiveFifteenMinuteState,
    ProspectiveFifteenMinuteWriteOutcome,
    ProspectiveMinuteEvidenceState,
    bind_canonical_prospective_fifteen_minute_session,
    canonical_prospective_fifteen_minute_partitions,
    derive_canonical_prospective_fifteen_minute_receipt,
    make_prospective_minute_evidence,
    prospective_minute_evidence_from_dhan,
    serialize_canonical_prospective_fifteen_minute_receipt,
)
from app.market_data.technical_bar_contract import TechnicalTradingPeriod
from app.storage.core_api_snapshot_repository import CoreApiSnapshotFamily
from app.storage.sqlite_core_api_snapshot_repository import SQLiteCoreApiSnapshotRepository


AS_OF = datetime(2026, 9, 8, 16, tzinfo=UTC)
SECURITY = "NSE:INE000000001"
ISIN = "INE000000001"


def _session(*, as_of: datetime = AS_OF) -> CanonicalProspectiveFifteenMinuteSession:
    return bind_canonical_prospective_fifteen_minute_session(
        calendar=nse_capital_market_calendar_2022_2026(), session_date=date(2026, 9, 8), as_of=as_of,
    )


def _source_period(session: CanonicalProspectiveFifteenMinuteSession, start: datetime, end: datetime, index: int) -> TechnicalTradingPeriod:
    return TechnicalTradingPeriod(
        venue=Exchange.NSE,
        segment="CAPITAL_MARKET",
        period_id=f"test-source-minute:{index:03d}",
        session_dates=session.period.session_dates,
        starts_at=start,
        ends_at=end,
        timezone_id=session.period.timezone_id,
        calendar_id=session.period.calendar_id,
        calendar_fingerprint=session.period.calendar_fingerprint,
        session_source_ids=session.period.session_source_ids,
        session_source_fingerprints=session.period.session_source_fingerprints,
    )


def _evidence(
    session: CanonicalProspectiveFifteenMinuteSession,
    partition_index: int = 0,
    *, no_trade: frozenset[int] = frozenset(), incomplete: frozenset[int] = frozenset(),
    conflicted: frozenset[int] = frozenset(), provider: str = "provider-a",
    start_offset: int = 0, price_offset: int = 0,
) -> tuple:
    partition = canonical_prospective_fifteen_minute_partitions(session)[partition_index]
    result = []
    for index in range(15):
        start = partition.interval_start + timedelta(minutes=index + start_offset)
        end = start + timedelta(minutes=1)
        fingerprint = "sha256:" + f"{(partition_index + 1) * 100 + index + price_offset:064x}"
        common = dict(
            source_receipt_id=f"minute:{partition_index:03d}:{index:03d}:{price_offset}",
            source_receipt_fingerprint=fingerprint,
            canonical_security_id=SECURITY,
            isin=ISIN,
            provider_family=provider,
            session_id=session.session_id,
            period=_source_period(session, start, end, index),
            interval_start=start,
            interval_end=end,
            known_at=end + timedelta(seconds=4),
        )
        if index in no_trade:
            result.append(make_prospective_minute_evidence(
                **common, state=ProspectiveMinuteEvidenceState.NO_TRADE_OBSERVED,
                source_reasons=("NO_TRADE_OBSERVED",),
            ))
        elif index in incomplete:
            result.append(make_prospective_minute_evidence(
                **common, state=ProspectiveMinuteEvidenceState.INCOMPLETE,
                source_reasons=("PROVIDER_GAP",),
            ))
        elif index in conflicted:
            result.append(make_prospective_minute_evidence(
                **common, state=ProspectiveMinuteEvidenceState.EVIDENCE_CONFLICTED,
                source_reasons=("SAME_EVENT_TIME_ORDER_UNRESOLVED",),
            ))
        else:
            price = Decimal(100 + price_offset + index)
            result.append(make_prospective_minute_evidence(
                **common, state=ProspectiveMinuteEvidenceState.CLOSED,
                open=price, high=price + Decimal("2"), low=price - Decimal("1"),
                close=price + Decimal("1"), volume=index + 1, event_count=2,
            ))
    return tuple(result)


def _derive(session: CanonicalProspectiveFifteenMinuteSession, evidence: tuple, *, index: int = 0, delayed_seconds: int = 0):
    partition = canonical_prospective_fifteen_minute_partitions(session)[index]
    actual_finalization = max(
        partition.interval_end + timedelta(seconds=4 + delayed_seconds),
        *(value.known_at + timedelta(seconds=delayed_seconds) for value in evidence),
    )
    return derive_canonical_prospective_fifteen_minute_receipt(
        partition=partition, canonical_security_id=SECURITY, isin=ISIN,
        source_evidence=evidence, finalized_at=actual_finalization,
    )


def test_standard_calendar_session_has_exact_phase_anchored_25_full_partitions() -> None:
    session = _session()
    partitions = canonical_prospective_fifteen_minute_partitions(session)
    assert len(partitions) == 25
    assert partitions[0].interval_start == session.period.starts_at.astimezone(UTC)
    assert partitions[-1].interval_end == session.period.ends_at.astimezone(UTC)
    assert all(value.interval_end - value.interval_start == timedelta(minutes=15) for value in partitions)


def test_short_special_phase_excludes_residual_tail_instead_of_mislabeling_it() -> None:
    source = make_first_party_session_source(
        source_id="fixture-short-special", source_reference="https://nsearchives.nseindia.com/content/circulars/fixture-short-special.pdf",
        published_on=date(2025, 1, 1),
    )
    calendar = make_canonical_market_session_calendar(
        calendar_id="fixture-short-calendar", coverage_start=date(2025, 1, 1), coverage_end=date(2025, 12, 31),
        annual_holiday_schedules=(), weekday_conventions=(),
        special_trading_days=(make_special_trading_day(session_date=date(2025, 2, 1), state=TradingDayState.SPECIAL_TRADING_DAY, source=source),),
        phase_timings=(make_effective_session_phase_timing(
            timing_id="fixture-short-regular", effective_from=date(2025, 2, 1), effective_to=date(2025, 2, 1),
            applies_to_states=(TradingDayState.SPECIAL_TRADING_DAY,), phase_type=SessionPhaseType.REGULAR_CONTINUOUS,
            starts_at_local=time(9, 15), ends_at_local=time(9, 52), source=source,
        ),),
    )
    session = bind_canonical_prospective_fifteen_minute_session(calendar=calendar, session_date=date(2025, 2, 1), as_of=datetime(2025, 2, 2, tzinfo=UTC))
    partitions = canonical_prospective_fifteen_minute_partitions(session)
    assert [(value.interval_start.time(), value.interval_end.time()) for value in partitions] == [
        (time(3, 45), time(4, 0)), (time(4, 0), time(4, 15)),
    ]
    assert session.period.ends_at.astimezone(UTC) - partitions[-1].interval_end == timedelta(minutes=7)


def test_closed_bar_uses_only_genuine_trade_ohlc_and_incremental_volume() -> None:
    session = _session(); receipt = _derive(session, _evidence(session, no_trade=frozenset({5})))
    assert receipt.state is ProspectiveFifteenMinuteState.CLOSED and receipt.bar is not None
    assert (receipt.bar.open, receipt.bar.high, receipt.bar.low, receipt.bar.close) == (
        Decimal("100"), Decimal("116"), Decimal("99"), Decimal("115"),
    )
    assert receipt.bar.volume == sum(index + 1 for index in range(15) if index != 5)
    assert receipt.bar.traded_minute_count == 14 and receipt.bar.derivation_policy_fingerprint == POLICY_FINGERPRINT


def test_existing_dhan_one_minute_receipt_adapts_without_dhan_canonical_timeframe_identity() -> None:
    session = _session(); partition = canonical_prospective_fifteen_minute_partitions(session)[0]
    identity = DhanProspectiveInstrumentIdentity(SECURITY, ISIN, 1001, "NSE_EQ", "EQ", "sha256:" + "a" * 64)
    packet = DhanQuotePacket(
        1, 1001, Decimal("100"), 0, partition.interval_start + timedelta(seconds=10),
        Decimal("100"), 100, None, None, None, None,
    )
    event = normalize_dhan_quote_packet(packet, identity=identity, received_at=partition.interval_start + timedelta(seconds=11), connection_id="connection:one")
    binding = bind_dhan_event_to_regular_minute(event, calendar=nse_capital_market_calendar_2022_2026())
    receipt = ProspectiveDhanOneMinuteBarBuilder().no_trade_receipt(identity=identity, binding=binding, known_at=partition.interval_start + timedelta(minutes=1))
    adapted = prospective_minute_evidence_from_dhan(receipt)
    assert adapted.state is ProspectiveMinuteEvidenceState.NO_TRADE_OBSERVED
    assert adapted.provider_family == "dhan-v2-live-quote" and "dhan" not in partition.period.period_id


def test_entire_window_no_trade_is_descriptive_not_zero_or_previous_close_ohlcv() -> None:
    session = _session(); receipt = _derive(session, _evidence(session, no_trade=frozenset(range(15))))
    assert receipt.state is ProspectiveFifteenMinuteState.NO_TRADE_OBSERVED and receipt.bar is None
    assert receipt.reasons == (ProspectiveFifteenMinuteReason.ALL_NO_TRADE_OBSERVED,)


def test_mid_window_start_missing_coverage_and_reconnect_gap_never_close() -> None:
    session = _session()
    partial = _evidence(session)[7:]
    receipt = _derive(session, partial)
    assert receipt.state is ProspectiveFifteenMinuteState.INCOMPLETE
    assert ProspectiveFifteenMinuteReason.SOURCE_COVERAGE_MISSING in receipt.reasons
    reconnect = _derive(session, _evidence(session, incomplete=frozenset({7})))
    assert reconnect.state is ProspectiveFifteenMinuteState.INCOMPLETE
    assert ProspectiveFifteenMinuteReason.PROVIDER_GAP_OR_UNOBSERVED in reconnect.reasons


def test_conflicted_source_duplicate_source_and_cross_session_source_fail_closed() -> None:
    session = _session(); base = _evidence(session)
    conflicted = _derive(session, _evidence(session, conflicted=frozenset({4})))
    assert conflicted.state is ProspectiveFifteenMinuteState.EVIDENCE_CONFLICTED
    assert ProspectiveFifteenMinuteReason.SOURCE_EVIDENCE_CONFLICTED in conflicted.reasons
    changed = _evidence(session, price_offset=1)[0]
    duplicate = _derive(session, (*base, changed))
    assert duplicate.state is ProspectiveFifteenMinuteState.EVIDENCE_CONFLICTED
    assert ProspectiveFifteenMinuteReason.DUPLICATE_SOURCE_CONFLICT in duplicate.reasons
    cross = _evidence(session, start_offset=15)
    receipt = _derive(session, cross)
    assert receipt.state is ProspectiveFifteenMinuteState.INCOMPLETE
    assert ProspectiveFifteenMinuteReason.SOURCE_COVERAGE_MISSING in receipt.reasons


def test_finalization_is_actual_time_after_all_sources_and_timestamp_boundaries_are_utc() -> None:
    session = _session(); evidence = _evidence(session)
    partition = canonical_prospective_fifteen_minute_partitions(session)[0]
    with pytest.raises(ProspectiveFifteenMinuteBarError, match="FINALIZATION_EARLY"):
        derive_canonical_prospective_fifteen_minute_receipt(partition=partition, canonical_security_id=SECURITY, isin=ISIN, source_evidence=evidence, finalized_at=partition.interval_end - timedelta(seconds=1))
    delayed = _derive(session, evidence, delayed_seconds=4)
    assert delayed.known_at == partition.interval_end + timedelta(seconds=8)
    assert delayed.known_at.tzinfo is UTC and delayed.bar is not None and delayed.bar.known_at == delayed.known_at


def test_identity_is_provider_neutral_and_same_explicit_calendar_phase_has_stable_identity() -> None:
    first = _session(as_of=AS_OF)
    second = _session(as_of=AS_OF + timedelta(days=1))
    first_receipt = _derive(first, _evidence(first, provider="provider-a"))
    second_receipt = _derive(second, _evidence(second, provider="provider-b"))
    assert first_receipt.receipt_id == second_receipt.receipt_id
    assert first_receipt.bar is not None and second_receipt.bar is not None
    assert first_receipt.bar.provider_families == ("provider-a",)
    assert second_receipt.bar.provider_families == ("provider-b",)
    assert "dhan" not in first_receipt.receipt_id


def test_deterministic_replay_serialization_and_immutable_sqlite_conflict(tmp_path) -> None:
    session = _session(); evidence = _evidence(session)
    first = _derive(session, evidence, delayed_seconds=3)
    replay = _derive(session, tuple(reversed(evidence)), delayed_seconds=3)
    assert first == replay
    assert serialize_canonical_prospective_fifteen_minute_receipt(first) == serialize_canonical_prospective_fifteen_minute_receipt(replay)
    repository = SQLiteCoreApiSnapshotRepository(tmp_path / "fifteen.sqlite")
    store = ProspectiveCanonicalFifteenMinuteStore(repository)
    assert store.save(first, detected_at=first.known_at) is ProspectiveFifteenMinuteWriteOutcome.INSERTED
    assert store.save(replay, detected_at=replay.known_at) is ProspectiveFifteenMinuteWriteOutcome.ALREADY_PRESENT
    changed = _derive(session, _evidence(session, price_offset=9), delayed_seconds=3)
    assert store.save(changed, detected_at=changed.known_at) is ProspectiveFifteenMinuteWriteOutcome.CONFLICT
    assert store.get(first.receipt_id) == first
    assert len(repository.list_snapshots(CoreApiSnapshotFamily.PROSPECTIVE_CANONICAL_FIFTEEN_MINUTE_CONFLICT)) == 1
    repository.close()
    reopened = SQLiteCoreApiSnapshotRepository(tmp_path / "fifteen.sqlite")
    assert ProspectiveCanonicalFifteenMinuteStore(reopened).get(first.receipt_id) == first
    reopened.close()


def test_late_equivalent_finalization_is_idempotent_without_mutating_stored_receipt(tmp_path) -> None:
    session = _session(); evidence = _evidence(session)
    first = _derive(session, evidence, delayed_seconds=1)
    late = _derive(session, evidence, delayed_seconds=9)
    repository = SQLiteCoreApiSnapshotRepository(tmp_path / "late.sqlite")
    store = ProspectiveCanonicalFifteenMinuteStore(repository)
    assert store.save(first, detected_at=first.known_at) is ProspectiveFifteenMinuteWriteOutcome.INSERTED
    assert store.save(late, detected_at=late.known_at) is ProspectiveFifteenMinuteWriteOutcome.ALREADY_PRESENT
    assert store.get(first.receipt_id) == first
    repository.close()


def test_tampering_immutability_and_no_forbidden_dependencies() -> None:
    session = _session(); receipt = _derive(session, _evidence(session))
    with pytest.raises(FrozenInstanceError):
        receipt.known_at = receipt.known_at  # type: ignore[misc]
    with pytest.raises(ProspectiveFifteenMinuteBarError, match="RECEIPT_INVALID"):
        replace(receipt, derivation_policy_fingerprint="sha256:" + "0" * 64)
    with pytest.raises(ProspectiveFifteenMinuteBarError, match="RECEIPT_INVALID"):
        replace(receipt, source_lineage=receipt.source_lineage[:-1])
    source = (Path(__file__).parents[2] / "app" / "market_data" / "prospective_fifteen_minute_bar.py").read_text(encoding="utf-8")
    for forbidden in ("app.signals", "app.portfolio", "app.broker", "app.orders", "app.api", "datetime.now", "sqlite3"):
        assert forbidden not in source
    for forbidden_field in ("entry_price", "stop_loss", "target_price", "quantity", "allocation", "BUY", "SELL", "ROTATE"):
        assert forbidden_field not in source


def test_no_timeframe_substitution_and_current_fifteen_minute_contract_is_exact() -> None:
    session = _session(); receipt = _derive(session, _evidence(session))
    assert receipt.bar is not None
    assert receipt.bar.partition.period.period_id.endswith(":15m:000")
    assert receipt.bar.derivation_policy_id == "canonical-intraday-timeframe-derivation-policy"
    assert receipt.bar.derivation_policy_version == "v1-candidate"
