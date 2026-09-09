from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
import ast
import struct

import pytest

from app.historical.nse_capital_market_session_evidence_2022_2026 import nse_capital_market_calendar_2022_2026
from app.market_data.dhan_live_bar import DhanProspectiveInstrumentIdentity
from app.market_data.prospective_fifteen_minute_bar import ProspectiveCanonicalFifteenMinuteStore
from app.market_data.prospective_market_data_runtime import (
    CROSS_HOST_MARKET_RUNTIME_LEASE,
    WHOLE_UNIVERSE_LONG_RETENTION_1M,
    ProspectiveMarketDataBlockedIdentity,
    ProspectiveMarketDataFrameOutcome,
    ProspectiveMarketDataRuntime,
    ProspectiveMarketDataRuntimeError,
    ProspectiveMarketDataRuntimeReason,
    ProspectiveMarketDataRuntimeSettings,
    ProspectiveMarketDataRuntimeState,
    make_prospective_market_data_universe,
    serialize_prospective_market_data_runtime_health,
)


T = datetime(2026, 9, 8, 3, 45, tzinfo=UTC)
MASTER = "sha256:" + "a" * 64


class _Repository:
    def __init__(self) -> None:
        self.values = {}

    def get_snapshot(self, snapshot_id):
        return self.values.get(snapshot_id)

    def save_snapshot(self, value) -> None:
        if value.snapshot_id in self.values:
            raise AssertionError("append-only snapshot collision")
        self.values[value.snapshot_id] = value


class _Transport:
    def __init__(self) -> None:
        self.sent: list[str] = []
        self.closed = False

    def send(self, payload: str) -> None:
        self.sent.append(payload)

    def close(self) -> None:
        self.closed = True


def _identity(index: int = 1) -> DhanProspectiveInstrumentIdentity:
    return DhanProspectiveInstrumentIdentity(
        f"NSE:ALPHA{index}", f"INE{index:09d}", 1000 + index, "NSE_EQ", "EQ", MASTER,
    )


def _frame(*, security: int = 1001, at: datetime = T, volume: int = 100, price: float = 100.0) -> bytes:
    return struct.pack("<BhBi", 4, 50, 1, security) + struct.pack(
        "<fhifiiiffff", price, 1, int(at.timestamp()), price, volume, 0, 0, 99.0, 0.0, 101.0, 98.0,
    )


def _runtime(*, enabled: bool = True, queue_capacity: int = 32, identities=None, blocked=()):
    identities = (_identity(),) if identities is None else identities
    universe = make_prospective_market_data_universe(
        selected_denominator=len(identities) + len(blocked), exact_identities=identities, blocked_identities=blocked,
    )
    transport = _Transport()
    repository = _Repository()
    runtime = ProspectiveMarketDataRuntime(
        settings=ProspectiveMarketDataRuntimeSettings(enabled=enabled, queue_capacity=queue_capacity),
        universe=universe, calendar=nse_capital_market_calendar_2022_2026(),
        transport_factory=lambda: transport, fifteen_minute_store=ProspectiveCanonicalFifteenMinuteStore(repository),
    )
    return runtime, transport, repository


def _start(runtime: ProspectiveMarketDataRuntime, suffix: str = "one") -> None:
    runtime.start(run_id=f"runtime:{suffix}", started_at=T)


def test_disabled_default_and_import_safe_never_constructs_provider_connection() -> None:
    runtime, transport, _ = _runtime(enabled=False)
    assert runtime.start(run_id="runtime:disabled", started_at=T) is None
    assert runtime.state is ProspectiveMarketDataRuntimeState.STOPPED
    assert transport.sent == [] and not transport.closed
    assert runtime.health().last_error_code == ProspectiveMarketDataRuntimeReason.DISABLED_BY_CONFIGURATION.value
    assert not ProspectiveMarketDataRuntimeSettings.from_environment({}).enabled
    assert ProspectiveMarketDataRuntimeSettings.from_environment({"DHAN_LIVE_MARKET_ENABLED": "true"}).enabled


def test_run_receipt_universe_snapshot_and_provider_limit_batches_are_exact() -> None:
    identities = tuple(_identity(index) for index in range(1, 2288))
    blocked = (
        ProspectiveMarketDataBlockedIdentity("NSE:BLOCKED1", "PROVIDER_IDENTITY_NOT_FOUND"),
        ProspectiveMarketDataBlockedIdentity("NSE:BLOCKED2", "SECURITY_CLASS_MISMATCH"),
    )
    runtime, transport, _ = _runtime(identities=identities, blocked=blocked)
    receipt = runtime.start(run_id="runtime:batching", started_at=T)
    assert receipt is not None
    assert receipt.selected_denominator == 2289 and receipt.subscribed_exact_ready_count == 2287
    assert receipt.blocker_distribution == (("PROVIDER_IDENTITY_NOT_FOUND", 1), ("SECURITY_CLASS_MISMATCH", 1))
    assert len(transport.sent) == 23  # 100 instruments per verified request.
    assert runtime.state is ProspectiveMarketDataRuntimeState.RUNNING
    runtime.stop()


def test_single_runtime_owner_is_guarded_and_released_on_graceful_stop() -> None:
    first, _, _ = _runtime(); second, _, _ = _runtime()
    _start(first, "owner-one")
    with pytest.raises(ProspectiveMarketDataRuntimeError, match="ALREADY_OWNED"):
        _start(second, "owner-two")
    first.stop()
    _start(second, "owner-two")
    second.stop()


def test_run_identifier_cannot_be_reused_after_a_stopped_in_process_session() -> None:
    first, _, _ = _runtime(); _start(first, "unique"); first.stop()
    with pytest.raises(ProspectiveMarketDataRuntimeError, match="RUN_ID_REUSED"):
        _start(first, "unique")


def test_event_and_received_times_are_preserved_and_unknown_malformed_isolated() -> None:
    runtime, _, _ = _runtime(); _start(runtime)
    event_at, received_at = T + timedelta(minutes=1, seconds=10), T + timedelta(minutes=1, seconds=25)
    assert runtime.enqueue_frame(frame=_frame(at=event_at, volume=120), received_at=received_at) is ProspectiveMarketDataFrameOutcome.QUEUED
    assert runtime.drain_one() is ProspectiveMarketDataFrameOutcome.NORMALIZED
    assert runtime.health().last_normalized_event_at == received_at
    assert runtime.enqueue_frame(frame=_frame(security=9999, at=event_at, volume=121), received_at=received_at + timedelta(seconds=1)) is ProspectiveMarketDataFrameOutcome.QUEUED
    assert runtime.drain_one() is ProspectiveMarketDataFrameOutcome.UNKNOWN_SECURITY
    assert runtime.enqueue_frame(frame=b"\x04", received_at=received_at + timedelta(seconds=2)) is ProspectiveMarketDataFrameOutcome.QUEUED
    assert runtime.drain_one() is ProspectiveMarketDataFrameOutcome.MALFORMED
    assert runtime.health().parse_error_count == 1
    runtime.stop()


def test_duplicates_and_non_regular_packets_do_not_mutate_base_evidence() -> None:
    runtime, _, _ = _runtime(); _start(runtime)
    frame = _frame(at=T + timedelta(minutes=1, seconds=10), volume=120)
    runtime.enqueue_frame(frame=frame, received_at=T + timedelta(minutes=1, seconds=12)); assert runtime.drain_one() is ProspectiveMarketDataFrameOutcome.NORMALIZED
    runtime.enqueue_frame(frame=frame, received_at=T + timedelta(minutes=1, seconds=12)); assert runtime.drain_one() is ProspectiveMarketDataFrameOutcome.DUPLICATE
    runtime.enqueue_frame(frame=_frame(at=T - timedelta(minutes=1), volume=1), received_at=T + timedelta(seconds=1)); assert runtime.drain_one() is ProspectiveMarketDataFrameOutcome.SESSION_EXCLUDED
    runtime.stop()


def test_backpressure_is_bounded_and_marks_gap_without_claiming_completeness() -> None:
    runtime, _, _ = _runtime(queue_capacity=1); _start(runtime)
    runtime.enqueue_frame(frame=_frame(at=T + timedelta(minutes=1, seconds=10), volume=120), received_at=T + timedelta(minutes=1, seconds=11))
    assert runtime.enqueue_frame(frame=_frame(at=T + timedelta(minutes=1, seconds=20), volume=121), received_at=T + timedelta(minutes=1, seconds=21)) is ProspectiveMarketDataFrameOutcome.BACKPRESSURE_REJECTED
    assert runtime.state is ProspectiveMarketDataRuntimeState.DEGRADED
    assert runtime.drain_one() is ProspectiveMarketDataFrameOutcome.NORMALIZED
    assert runtime.health().gap_count == 1
    assert runtime.health().last_error_code == ProspectiveMarketDataRuntimeReason.BACKPRESSURE_GAP.value
    runtime.stop()


def test_socket_liveness_is_distinct_from_security_inactivity() -> None:
    runtime, _, _ = _runtime(); _start(runtime)
    assert runtime.health().state is ProspectiveMarketDataRuntimeState.RUNNING
    assert runtime.health().last_normalized_event_at is None
    assert runtime.enqueue_frame(frame=b"\x02", received_at=T + timedelta(seconds=10)) is ProspectiveMarketDataFrameOutcome.QUEUED
    assert runtime.drain_one() is ProspectiveMarketDataFrameOutcome.UNSUPPORTED
    assert runtime.health().last_provider_message_at == T + timedelta(seconds=10)
    assert runtime.health().state is ProspectiveMarketDataRuntimeState.RUNNING
    runtime.stop()


def test_disconnect_reconnect_resubscribes_same_snapshot_and_never_repairs_gap() -> None:
    transports: list[_Transport] = []
    runtime, _, _ = _runtime()
    def factory():
        value = _Transport(); transports.append(value); return value
    runtime._transport_factory = factory
    _start(runtime, "reconnect")
    assert len(transports) == 1
    runtime.connection_lost(at=T + timedelta(minutes=1, seconds=10))
    assert runtime.state is ProspectiveMarketDataRuntimeState.RECONNECTING
    runtime.reconnect(at=T + timedelta(minutes=1, seconds=30))
    assert runtime.state is ProspectiveMarketDataRuntimeState.RUNNING
    assert runtime.health().reconnect_count == 1 and len(transports) == 2
    assert transports[0].closed
    runtime.stop()


def test_restart_mid_window_and_shutdown_do_not_force_finalize() -> None:
    runtime, transport, _ = _runtime(); _start(runtime, "shutdown")
    runtime.enqueue_frame(frame=_frame(at=T + timedelta(seconds=20), volume=100), received_at=T + timedelta(seconds=21)); runtime.drain_one()
    assert runtime.finalize_through(known_at=T + timedelta(seconds=40)) == 0
    runtime.stop()
    assert runtime.state is ProspectiveMarketDataRuntimeState.STOPPED and transport.closed
    assert runtime.health().finalized_fifteen_minute_count == 0


def test_restart_discards_unfinished_window_instead_of_joining_old_observation() -> None:
    runtime, _, _ = _runtime(); _start(runtime, "restart-one")
    runtime.enqueue_frame(frame=_frame(at=T + timedelta(seconds=20), volume=100), received_at=T + timedelta(seconds=21)); runtime.drain_one()
    runtime.stop()
    runtime.start(run_id="runtime:restart-two", started_at=T + timedelta(seconds=40))
    assert runtime.finalize_through(known_at=T + timedelta(minutes=1)) == 0
    runtime.stop()


def test_one_minute_to_fifteen_minute_runtime_integration_persists_only_covered_receipt() -> None:
    runtime, _, repository = _runtime(); _start(runtime, "fifteen")
    # A 09:29 baseline supports the next complete 09:30--09:45 partition.
    for index in range(16):
        event_at = T + timedelta(minutes=14 + index, seconds=10)
        runtime.enqueue_frame(frame=_frame(at=event_at, volume=100 + index), received_at=event_at + timedelta(seconds=1))
        assert runtime.drain_one() is ProspectiveMarketDataFrameOutcome.NORMALIZED
    assert runtime.finalize_through(known_at=T + timedelta(minutes=30)) == 16
    assert runtime.health().finalized_fifteen_minute_count == 1
    assert len(repository.values) == 1
    runtime.stop()


def test_health_serialization_is_stable_and_contains_no_credential_surface() -> None:
    runtime, _, _ = _runtime(); _start(runtime, "health")
    health = runtime.health()
    assert serialize_prospective_market_data_runtime_health(health) == serialize_prospective_market_data_runtime_health(health)
    payload = serialize_prospective_market_data_runtime_health(health).lower()
    assert "token" not in payload and "secret" not in payload and "authorization" not in payload
    assert health.storage_retention_state == WHOLE_UNIVERSE_LONG_RETENTION_1M
    assert health.cross_host_lease_state == CROSS_HOST_MARKET_RUNTIME_LEASE
    runtime.stop()


def test_static_boundaries_exclude_api_broker_orders_portfolio_reader_and_clock() -> None:
    source = open("app/market_data/prospective_market_data_runtime.py", encoding="utf-8").read().lower()
    imports = {
        getattr(node, "module", "") or ""
        for node in ast.walk(ast.parse(source))
        if isinstance(node, (ast.Import, ast.ImportFrom))
    }
    for forbidden in ("app.api", "broker", "order", "portfolio", "internal_radar", "technical_reader"):
        assert all(forbidden not in item for item in imports)
    assert "datetime.now" not in source
    assert "dhan_live_websocket_url" not in source
