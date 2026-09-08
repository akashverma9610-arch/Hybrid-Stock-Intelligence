from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
import json
from pathlib import Path
import struct
from zoneinfo import ZoneInfo

import pytest

from app.connections.credentials import InMemoryCredentialStore
from app.historical.nse_capital_market_session_evidence_2022_2026 import nse_capital_market_calendar_2022_2026
from app.market_data.dhan import DHAN_CONNECTION_ID, DhanCredentialService
from app.market_data.dhan_live_bar import (
    DHAN_MAX_INSTRUMENTS_PER_CONNECTION,
    DhanLiveBarConnectionState,
    DhanLiveBarError,
    DhanProspectiveBarReason,
    DhanProspectiveBarState,
    DhanProspectiveBarWriteOutcome,
    DhanProspectiveInstrumentIdentity,
    DhanProspectiveQuoteFeedAdapter,
    DhanQuotePacket,
    DhanSessionBindingState,
    ProspectiveDhanMinuteStore,
    ProspectiveDhanOneMinuteBarBuilder,
    bind_dhan_event_to_regular_minute,
    dhan_v2_live_provider_contract,
    normalize_dhan_quote_packet,
    parse_dhan_quote_packets,
    plan_dhan_quote_subscription,
    quote_subscription_messages,
)
from app.market_data.models import Timeframe
from app.market_data.technical_bar_contract import interval_from_timeframe
from app.storage.core_api_snapshot_repository import CoreApiSnapshot, CoreApiSnapshotFamily, snapshot_json
from app.storage.sqlite_core_api_snapshot_repository import SQLiteCoreApiSnapshotRepository


IST_0915 = datetime(2026, 9, 8, 3, 45, tzinfo=UTC)
MASTER = "sha256:" + "a" * 64


def _identity(index: int = 1) -> DhanProspectiveInstrumentIdentity:
    return DhanProspectiveInstrumentIdentity(
        f"NSE:ALPHA{index}", f"INE{index:09d}", 1000 + index, "NSE_EQ", "EQ", MASTER,
    )


def _frame(*, security: int = 1001, price: float = 100.0, quantity: int = 10, epoch: int | None = None, volume: int = 100) -> bytes:
    timestamp = epoch if epoch is not None else int(IST_0915.timestamp())
    return struct.pack("<BhBi", 4, 50, 1, security) + struct.pack(
        "<fhifiiiffff", price, quantity, timestamp, price, volume, 0, 0, 99.0, 0.0, 101.0, 98.0,
    )


def _event(
    identity: DhanProspectiveInstrumentIdentity,
    *,
    event_at: datetime,
    received_at: datetime | None = None,
    price: Decimal = Decimal("100"),
    volume: int = 100,
    quantity: int = 10,
    connection: str = "connection:one",
):
    packet = DhanQuotePacket(1, identity.provider_security_id, price, quantity, event_at, price, volume, None, None, None, None)
    return normalize_dhan_quote_packet(packet, identity=identity, received_at=received_at or event_at + timedelta(seconds=1), connection_id=connection)


def _bound(event):
    value = bind_dhan_event_to_regular_minute(event, calendar=nse_capital_market_calendar_2022_2026())
    assert value.state is DhanSessionBindingState.BOUND_REGULAR_SESSION
    return value


def _builder_with_baseline(identity: DhanProspectiveInstrumentIdentity):
    builder = ProspectiveDhanOneMinuteBarBuilder()
    builder.begin_connection(connection_id="connection:one", observed_at=IST_0915)
    baseline = _event(identity, event_at=IST_0915 + timedelta(seconds=10), volume=100)
    assert builder.observe(baseline, binding=_bound(baseline)) == "ACCEPTED"
    return builder


def test_current_official_provider_contract_is_exact_and_quote_only() -> None:
    contract = dhan_v2_live_provider_contract()
    assert contract.version == "v2"
    assert contract.max_connections_per_user == 5
    assert contract.max_instruments_per_connection == 5000
    assert contract.max_instruments_per_subscription == 100
    assert contract.request_encoding == "JSON" and contract.response_encoding == "BINARY"
    assert contract.endianness == "LITTLE_ENDIAN" and contract.quote_subscribe_request_code == 17


def test_quote_parser_is_little_endian_exact_and_rejects_wrong_packet_type() -> None:
    packet = parse_dhan_quote_packets(_frame())[0]
    assert packet.security_id == 1001 and packet.latest_traded_price == Decimal("100.0")
    assert packet.last_trade_time.tzinfo is UTC and packet.cumulative_session_volume == 100
    assert packet.day_close is None  # documented post-close field is not used to construct a minute bar.
    with pytest.raises(DhanLiveBarError, match="LENGTH_INVALID"):
        parse_dhan_quote_packets(_frame()[:-1])
    with pytest.raises(DhanLiveBarError, match="UNSUPPORTED"):
        parse_dhan_quote_packets(_frame().replace(bytes([4]), bytes([2]), 1))


def test_normalized_event_preserves_event_time_received_at_and_exact_identity() -> None:
    identity = _identity()
    event = _event(identity, event_at=IST_0915 + timedelta(seconds=10), received_at=IST_0915 + timedelta(seconds=12))
    assert event.event_time == IST_0915 + timedelta(seconds=10)
    assert event.received_at == IST_0915 + timedelta(seconds=12)
    assert event.event_identity.startswith("dhan-event:") and event.fingerprint.startswith("sha256:")
    wrong = DhanQuotePacket(1, 9999, Decimal("100"), 1, IST_0915, Decimal("100"), 1, None, None, None, None)
    with pytest.raises(DhanLiveBarError, match="EXACT_IDENTITY"):
        normalize_dhan_quote_packet(wrong, identity=identity, received_at=IST_0915, connection_id="connection:one")


def test_identity_ambiguity_and_noncanonical_isin_fail_closed() -> None:
    with pytest.raises(DhanLiveBarError, match="IDENTITY_INVALID"):
        DhanProspectiveInstrumentIdentity("NSE:ALPHA", "ine000000001", 1001, "NSE_EQ", "EQ", MASTER)
    identity = _identity()
    duplicate_canonical = DhanProspectiveInstrumentIdentity("NSE:ALPHA1", "INE000000002", 1002, "NSE_EQ", "EQ", MASTER)
    with pytest.raises(DhanLiveBarError, match="IDENTITY_SET_INVALID"):
        quote_subscription_messages((identity, duplicate_canonical))
    duplicate_provider = DhanProspectiveInstrumentIdentity("NSE:BETA", "INE000000003", 1001, "NSE_EQ", "EQ", MASTER)
    with pytest.raises(DhanLiveBarError, match="IDENTITY_SET_INVALID"):
        plan_dhan_quote_subscription((identity, duplicate_provider))


def test_received_time_is_normalized_to_utc_and_direct_packet_requires_utc() -> None:
    identity = _identity()
    packet = DhanQuotePacket(1, identity.provider_security_id, Decimal("100"), 1, IST_0915, Decimal("100"), 1, None, None, None, None)
    received_in_ist = (IST_0915 + timedelta(seconds=1)).astimezone(ZoneInfo("Asia/Kolkata"))
    event = normalize_dhan_quote_packet(packet, identity=identity, received_at=received_in_ist, connection_id="connection:one")
    assert event.received_at.tzinfo is UTC and event.received_at == IST_0915 + timedelta(seconds=1)
    with pytest.raises(DhanLiveBarError, match="PACKET_INVALID"):
        DhanQuotePacket(1, identity.provider_security_id, Decimal("100"), 1, received_in_ist, Decimal("100"), 1, None, None, None, None)


def test_subscription_batches_exact_mapped_identities_and_enforces_capacity() -> None:
    identities = tuple(_identity(index) for index in range(1, 102))
    messages = quote_subscription_messages(identities)
    assert len(messages) == 2
    assert [json.loads(item)["InstrumentCount"] for item in messages] == [100, 1]
    plan = plan_dhan_quote_subscription(identities)
    assert plan.messages_required == 2 and plan.fits_one_connection
    too_many = tuple(_identity(index) for index in range(1, DHAN_MAX_INSTRUMENTS_PER_CONNECTION + 2))
    with pytest.raises(DhanLiveBarError, match="CAPACITY"):
        quote_subscription_messages(too_many)


def test_session_binding_accepts_only_source_backed_regular_continuous_minutes() -> None:
    identity = _identity()
    regular = _event(identity, event_at=IST_0915 + timedelta(seconds=10))
    binding = _bound(regular)
    assert binding.interval_start == IST_0915 and binding.interval_end == IST_0915 + timedelta(minutes=1)
    preopen = _event(identity, event_at=IST_0915 - timedelta(minutes=1))
    assert bind_dhan_event_to_regular_minute(preopen, calendar=nse_capital_market_calendar_2022_2026()).state is DhanSessionBindingState.OUTSIDE_REGULAR_SESSION


def test_complete_one_minute_ohlc_uses_trade_order_and_cumulative_volume_delta() -> None:
    identity = _identity()
    builder = _builder_with_baseline(identity)
    first = _event(identity, event_at=IST_0915 + timedelta(minutes=1, seconds=10), price=Decimal("101"), volume=130)
    last = _event(identity, event_at=IST_0915 + timedelta(minutes=1, seconds=40), price=Decimal("103"), volume=150)
    assert builder.observe(first, binding=_bound(first)) == "ACCEPTED"
    assert builder.observe(last, binding=_bound(last)) == "ACCEPTED"
    receipts = builder.finalize_through(known_at=IST_0915 + timedelta(minutes=2))
    closed = next(value for value in receipts if value.state is DhanProspectiveBarState.CLOSED)
    assert closed.bar is not None
    assert (closed.bar.open, closed.bar.high, closed.bar.low, closed.bar.close, closed.bar.volume) == (
        Decimal("101"), Decimal("103"), Decimal("101"), Decimal("103"), 50,
    )
    assert closed.bar.known_at >= closed.bar.interval_end


def test_same_second_increasing_cumulative_volume_is_deterministic() -> None:
    identity = _identity()
    builder = _builder_with_baseline(identity)
    at = IST_0915 + timedelta(minutes=1, seconds=20)
    first = _event(identity, event_at=at, received_at=at + timedelta(seconds=2), price=Decimal("102"), volume=120)
    second = _event(identity, event_at=at, received_at=at + timedelta(seconds=3), price=Decimal("103"), volume=140)
    builder.observe(first, binding=_bound(first)); builder.observe(second, binding=_bound(second))
    closed = next(value for value in builder.finalize_through(known_at=IST_0915 + timedelta(minutes=2)) if value.state is DhanProspectiveBarState.CLOSED)
    assert closed.bar is not None and closed.bar.open == Decimal("102") and closed.bar.close == Decimal("103")


def test_duplicate_packet_is_idempotent_and_replayed_packet_cannot_mutate_finalized_bar() -> None:
    identity = _identity()
    builder = _builder_with_baseline(identity)
    event = _event(identity, event_at=IST_0915 + timedelta(minutes=1, seconds=10), volume=130)
    assert builder.observe(event, binding=_bound(event)) == "ACCEPTED"
    assert builder.observe(event, binding=_bound(event)) == "DUPLICATE"
    builder.finalize_through(known_at=IST_0915 + timedelta(minutes=2))
    assert builder.observe(event, binding=_bound(event)) == DhanProspectiveBarReason.LATE_EVENT_AFTER_FINALIZATION.value


def test_mid_interval_start_and_provider_gap_cannot_create_complete_bar() -> None:
    identity = _identity()
    builder = ProspectiveDhanOneMinuteBarBuilder()
    builder.begin_connection(connection_id="connection:one", observed_at=IST_0915 + timedelta(seconds=30))
    partial = _event(identity, event_at=IST_0915 + timedelta(seconds=40), volume=100)
    builder.observe(partial, binding=_bound(partial))
    receipt = builder.finalize_through(known_at=IST_0915 + timedelta(minutes=1))[0]
    assert receipt.state is DhanProspectiveBarState.INCOMPLETE
    assert DhanProspectiveBarReason.MID_INTERVAL_START in receipt.reasons

    builder = _builder_with_baseline(identity)
    builder.record_gap(connection_id="connection:one", disconnected_at=IST_0915 + timedelta(minutes=1, seconds=15), reconnected_at=IST_0915 + timedelta(minutes=1, seconds=35))
    after_gap = _event(identity, event_at=IST_0915 + timedelta(minutes=1, seconds=40), volume=150)
    builder.observe(after_gap, binding=_bound(after_gap))
    gap_receipt = next(value for value in builder.finalize_through(known_at=IST_0915 + timedelta(minutes=2)) if value.observed_event_count == 1 and value.interval_start == IST_0915 + timedelta(minutes=1))
    assert gap_receipt.state is DhanProspectiveBarState.INCOMPLETE
    assert DhanProspectiveBarReason.PROVIDER_GAP in gap_receipt.reasons


def test_reconnection_cannot_borrow_prior_connection_volume_baseline() -> None:
    identity = _identity()
    builder = _builder_with_baseline(identity)
    builder.record_gap(connection_id="connection:one", disconnected_at=IST_0915 + timedelta(minutes=1, seconds=5), reconnected_at=IST_0915 + timedelta(minutes=1, seconds=20))
    builder.begin_connection(connection_id="connection:two", observed_at=IST_0915 + timedelta(minutes=1))
    event = _event(identity, event_at=IST_0915 + timedelta(minutes=1, seconds=30), received_at=IST_0915 + timedelta(minutes=1, seconds=31), volume=130, connection="connection:two")
    assert builder.observe(event, binding=_bound(event)) == "ACCEPTED"
    receipt = next(value for value in builder.finalize_through(known_at=IST_0915 + timedelta(minutes=2)) if value.interval_start == IST_0915 + timedelta(minutes=1))
    assert receipt.state is DhanProspectiveBarState.INCOMPLETE
    assert DhanProspectiveBarReason.VOLUME_BASELINE_UNAVAILABLE in receipt.reasons


def test_gap_recovery_requires_post_gap_baseline_before_later_minute_can_close() -> None:
    identity = _identity()
    builder = _builder_with_baseline(identity)
    builder.record_gap(connection_id="connection:one", disconnected_at=IST_0915 + timedelta(minutes=1, seconds=15), reconnected_at=IST_0915 + timedelta(minutes=1, seconds=35))
    recovery = _event(identity, event_at=IST_0915 + timedelta(minutes=1, seconds=40), volume=130)
    next_minute = _event(identity, event_at=IST_0915 + timedelta(minutes=2, seconds=10), volume=150)
    builder.observe(recovery, binding=_bound(recovery))
    builder.observe(next_minute, binding=_bound(next_minute))
    receipts = builder.finalize_through(known_at=IST_0915 + timedelta(minutes=3))
    gap_minute = next(value for value in receipts if value.interval_start == IST_0915 + timedelta(minutes=1))
    recovered_minute = next(value for value in receipts if value.interval_start == IST_0915 + timedelta(minutes=2))
    assert gap_minute.state is DhanProspectiveBarState.INCOMPLETE
    assert DhanProspectiveBarReason.PROVIDER_GAP in gap_minute.reasons
    assert recovered_minute.state is DhanProspectiveBarState.CLOSED
    assert recovered_minute.bar is not None and recovered_minute.bar.volume == 20


def test_out_of_order_observations_replay_by_event_time_and_conflicting_same_timestamp_fails_closed() -> None:
    identity = _identity()
    builder = _builder_with_baseline(identity)
    later = _event(identity, event_at=IST_0915 + timedelta(minutes=1, seconds=45), received_at=IST_0915 + timedelta(minutes=1, seconds=50), price=Decimal("105"), volume=150)
    earlier = _event(identity, event_at=IST_0915 + timedelta(minutes=1, seconds=10), received_at=IST_0915 + timedelta(minutes=1, seconds=55), price=Decimal("101"), volume=120)
    builder.observe(later, binding=_bound(later)); builder.observe(earlier, binding=_bound(earlier))
    closed = next(value for value in builder.finalize_through(known_at=IST_0915 + timedelta(minutes=2)) if value.state is DhanProspectiveBarState.CLOSED)
    assert closed.bar is not None and closed.bar.open == Decimal("101") and closed.bar.close == Decimal("105")

    builder = _builder_with_baseline(identity)
    left = _event(identity, event_at=IST_0915 + timedelta(minutes=1, seconds=10), price=Decimal("101"), volume=120)
    right = _event(identity, event_at=IST_0915 + timedelta(minutes=1, seconds=10), price=Decimal("102"), volume=120, quantity=11)
    builder.observe(left, binding=_bound(left)); builder.observe(right, binding=_bound(right))
    conflicted = next(value for value in builder.finalize_through(known_at=IST_0915 + timedelta(minutes=2)) if value.interval_start == IST_0915 + timedelta(minutes=1))
    assert conflicted.state is DhanProspectiveBarState.EVIDENCE_CONFLICTED
    assert DhanProspectiveBarReason.SAME_EVENT_TIME_ORDER_UNRESOLVED in conflicted.reasons


def test_volume_regression_and_no_trade_interval_fail_closed_without_synthetic_prices() -> None:
    identity = _identity()
    builder = _builder_with_baseline(identity)
    regression = _event(identity, event_at=IST_0915 + timedelta(minutes=1, seconds=10), volume=90)
    builder.observe(regression, binding=_bound(regression))
    receipt = next(value for value in builder.finalize_through(known_at=IST_0915 + timedelta(minutes=2)) if value.interval_start == IST_0915 + timedelta(minutes=1))
    assert receipt.state is DhanProspectiveBarState.EVIDENCE_CONFLICTED
    assert DhanProspectiveBarReason.CUMULATIVE_VOLUME_REGRESSION in receipt.reasons

    empty = ProspectiveDhanOneMinuteBarBuilder().no_trade_receipt(identity=identity, binding=_bound(_event(identity, event_at=IST_0915 + timedelta(minutes=1))), known_at=IST_0915 + timedelta(minutes=2))
    assert empty.state is DhanProspectiveBarState.NO_TRADE_OBSERVED and empty.bar is None


def test_immutable_receipts_reopen_idempotently_and_conflict_without_rewrite(tmp_path) -> None:
    identity = _identity()
    builder = _builder_with_baseline(identity)
    event = _event(identity, event_at=IST_0915 + timedelta(minutes=1, seconds=10), volume=130)
    builder.observe(event, binding=_bound(event))
    receipt = next(value for value in builder.finalize_through(known_at=IST_0915 + timedelta(minutes=2)) if value.state is DhanProspectiveBarState.CLOSED)
    repository = SQLiteCoreApiSnapshotRepository(tmp_path / "bars.sqlite")
    store = ProspectiveDhanMinuteStore(repository)
    assert store.save(receipt, detected_at=receipt.known_at) is DhanProspectiveBarWriteOutcome.INSERTED
    assert store.save(receipt, detected_at=receipt.known_at) is DhanProspectiveBarWriteOutcome.ALREADY_PRESENT
    repository.close()
    repository = SQLiteCoreApiSnapshotRepository(tmp_path / "bars.sqlite")
    store = ProspectiveDhanMinuteStore(repository)
    assert store.get(receipt.receipt_id) == receipt

    changed_builder = _builder_with_baseline(identity)
    changed = _event(identity, event_at=IST_0915 + timedelta(minutes=1, seconds=10), price=Decimal("101"), volume=130)
    changed_builder.observe(changed, binding=_bound(changed))
    changed_receipt = next(value for value in changed_builder.finalize_through(known_at=IST_0915 + timedelta(minutes=2)) if value.state is DhanProspectiveBarState.CLOSED)
    assert store.save(changed_receipt, detected_at=changed_receipt.known_at) is DhanProspectiveBarWriteOutcome.CONFLICT
    assert store.get(receipt.receipt_id) == receipt
    repository.close()


def test_finalization_waits_for_interval_end_and_tampered_lineage_is_rejected() -> None:
    identity = _identity()
    builder = _builder_with_baseline(identity)
    event = _event(identity, event_at=IST_0915 + timedelta(minutes=1, seconds=10), volume=130)
    builder.observe(event, binding=_bound(event))
    early = builder.finalize_through(known_at=IST_0915 + timedelta(minutes=1, seconds=59))
    assert all(value.interval_start != IST_0915 + timedelta(minutes=1) for value in early)
    receipt = next(value for value in builder.finalize_through(known_at=IST_0915 + timedelta(minutes=2)) if value.state is DhanProspectiveBarState.CLOSED)
    assert receipt.known_at >= receipt.interval_end
    with pytest.raises(DhanLiveBarError, match="EVENT_INVALID"):
        replace(event, master_fingerprint="sha256:" + "b" * 64)


def test_snapshot_serialization_is_stable_and_conflict_timestamp_is_tamper_evident(tmp_path) -> None:
    identity = _identity()
    builder = _builder_with_baseline(identity)
    event = _event(identity, event_at=IST_0915 + timedelta(minutes=1, seconds=10), volume=130)
    builder.observe(event, binding=_bound(event))
    receipt = next(value for value in builder.finalize_through(known_at=IST_0915 + timedelta(minutes=2)) if value.state is DhanProspectiveBarState.CLOSED)
    snapshot = CoreApiSnapshot("receipt:test", CoreApiSnapshotFamily.PROSPECTIVE_DHAN_ONE_MINUTE_BAR, "v1", "test", receipt.fingerprint, receipt.known_at, receipt)
    assert snapshot_json(snapshot) == snapshot_json(snapshot)
    repository = SQLiteCoreApiSnapshotRepository(tmp_path / "conflict.sqlite")
    store = ProspectiveDhanMinuteStore(repository)
    assert store.save(receipt, detected_at=receipt.known_at) is DhanProspectiveBarWriteOutcome.INSERTED
    changed_builder = _builder_with_baseline(identity)
    changed = _event(identity, event_at=IST_0915 + timedelta(minutes=1, seconds=10), price=Decimal("101"), volume=130)
    changed_builder.observe(changed, binding=_bound(changed))
    changed_receipt = next(value for value in changed_builder.finalize_through(known_at=IST_0915 + timedelta(minutes=2)) if value.state is DhanProspectiveBarState.CLOSED)
    assert store.save(changed_receipt, detected_at=changed_receipt.known_at) is DhanProspectiveBarWriteOutcome.CONFLICT
    conflict = repository.list_snapshots(CoreApiSnapshotFamily.PROSPECTIVE_DHAN_ONE_MINUTE_CONFLICT)[0].payload
    with pytest.raises(DhanLiveBarError, match="CONFLICT_INVALID"):
        replace(conflict, detected_at=conflict.detected_at + timedelta(seconds=1))
    repository.close()


def test_bounded_quote_adapter_uses_quote_subscription_and_never_exposes_secret() -> None:
    credentials = DhanCredentialService(InMemoryCredentialStore(values={DHAN_CONNECTION_ID: {
        "dhan_client_id": "synthetic-client", "api_key": "synthetic-key", "api_secret": "synthetic-secret",
        "access_token": "synthetic-access-token", "access_token_expiry": (IST_0915 + timedelta(hours=1)).isoformat(),
    }}), clock=lambda: IST_0915)

    class Transport:
        def __init__(self): self.sent: list[str] = []; self.closed = False
        def send(self, payload: str) -> None: self.sent.append(payload)
        def recv(self) -> bytes: return _frame(epoch=int((IST_0915 + timedelta(seconds=10)).timestamp()))
        def close(self) -> None: self.closed = True

    transport = Transport()
    adapter = DhanProspectiveQuoteFeedAdapter(credentials, identities=(_identity(),), clock=lambda: IST_0915 + timedelta(seconds=12), transport_factory=lambda _url: transport)
    result = adapter.bounded_probe(connection_id="connection:one")
    assert result.state is DhanLiveBarConnectionState.SUBSCRIBED and len(result.normalized_events) == 1 and transport.closed
    assert json.loads(transport.sent[0])["RequestCode"] == 17 and json.loads(transport.sent[-1])["RequestCode"] == 12
    assert "synthetic-access-token" not in repr(result) and "synthetic-client" not in repr(result)


def test_documented_non_quote_packets_are_not_promoted_to_market_events() -> None:
    credentials = DhanCredentialService(InMemoryCredentialStore(values={DHAN_CONNECTION_ID: {
        "dhan_client_id": "synthetic-client", "api_key": "synthetic-key", "api_secret": "synthetic-secret",
        "access_token": "synthetic-access-token", "access_token_expiry": (IST_0915 + timedelta(hours=1)).isoformat(),
    }}), clock=lambda: IST_0915)

    class Transport:
        def send(self, _payload: str) -> None: pass
        def recv(self) -> bytes: return struct.pack("<BhBi", 6, 8, 1, 1001)
        def close(self) -> None: pass

    result = DhanProspectiveQuoteFeedAdapter(credentials, identities=(_identity(),), clock=lambda: IST_0915, transport_factory=lambda _url: Transport()).bounded_probe(connection_id="connection:one")
    assert result.state is DhanLiveBarConnectionState.SUBSCRIBED and result.normalized_events == ()


def test_daily_and_weekly_contracts_remain_distinct_from_prospective_one_minute() -> None:
    assert interval_from_timeframe(Timeframe.DAILY).interval_id == "1D"
    assert interval_from_timeframe(Timeframe.WEEKLY).interval_id == "1W"
    assert interval_from_timeframe(Timeframe.ONE_MINUTE).interval_id == "1m"


def test_live_bar_module_has_no_forbidden_runtime_or_execution_dependency() -> None:
    source = (Path(__file__).parents[2] / "app" / "market_data" / "dhan_live_bar.py").read_text(encoding="utf-8")
    for forbidden in ("app.signals", "app.portfolio", "app.broker", "app.orders", "app.api", "datetime.now", "sqlite3"):
        assert forbidden not in source
