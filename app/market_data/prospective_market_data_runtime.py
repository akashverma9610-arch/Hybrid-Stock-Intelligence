"""Explicit, shared, disabled-by-default prospective market-data runtime.

This module is deliberately an operator-owned coordinator, not an application
startup hook or a user-facing feed.  It accepts a governed Dhan universe and
an injected transport, preserves packet receipt times, and routes only
normalised prospective evidence into the accepted one-minute and canonical
15-minute contracts.  It owns no technical reader, signal, portfolio, order,
broker, API, or raw-tick retention surface.
"""
from __future__ import annotations

from collections import Counter, deque
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from enum import StrEnum
from hashlib import sha256
import json
import os
import re
from threading import Lock
from typing import Callable, Mapping, Protocol

from app.historical.canonical_market_session_event_time import CanonicalMarketSessionCalendar
from app.market_data.dhan import DHAN_PROVIDER
from app.market_data.dhan_live import parse_dhan_disconnect_packet
from app.market_data.dhan_live_bar import (
    DHAN_QUOTE_PACKET,
    DhanLiveBarError,
    DhanProspectiveInstrumentIdentity,
    DhanProspectiveBarState,
    ProspectiveDhanOneMinuteBarBuilder,
    bind_dhan_event_to_regular_minute,
    dhan_v2_live_provider_contract,
    normalize_dhan_quote_packet,
    parse_dhan_quote_packets,
    plan_dhan_quote_subscription,
    quote_subscription_messages,
)
from app.market_data.prospective_fifteen_minute_bar import (
    CanonicalProspectiveMinuteEvidence,
    ProspectiveCanonicalFifteenMinuteStore,
    bind_canonical_prospective_fifteen_minute_session,
    canonical_prospective_fifteen_minute_partitions,
    derive_canonical_prospective_fifteen_minute_receipt,
    prospective_minute_evidence_from_dhan,
)


CONTRACT_ID = "prospective-market-data-runtime-orchestrator"
CONTRACT_VERSION = "v1"
CROSS_HOST_MARKET_RUNTIME_LEASE = "NOT_READY"
WHOLE_UNIVERSE_LONG_RETENTION_1M = "NOT_APPROVED"
RAW_TICK_RETENTION_POLICY = "UNSET"
_IDENTIFIER = re.compile(r"[A-Za-z0-9._:-]+\Z")
_FINGERPRINT = re.compile(r"sha256:[0-9a-f]{64}\Z")


class ProspectiveMarketDataRuntimeError(ValueError):
    """Stable, non-secret failure at the prospective-runtime boundary."""


class ProspectiveMarketDataRuntimeState(StrEnum):
    STOPPED = "STOPPED"
    STARTING = "STARTING"
    CONNECTING = "CONNECTING"
    SUBSCRIBING = "SUBSCRIBING"
    RUNNING = "RUNNING"
    DEGRADED = "DEGRADED"
    RECONNECTING = "RECONNECTING"
    STOPPING = "STOPPING"
    FAILED = "FAILED"


class ProspectiveMarketDataRuntimeReason(StrEnum):
    DISABLED_BY_CONFIGURATION = "DISABLED_BY_CONFIGURATION"
    RUNTIME_ALREADY_OWNED = "RUNTIME_ALREADY_OWNED"
    CONNECTION_FAILED = "CONNECTION_FAILED"
    SUBSCRIPTION_FAILED = "SUBSCRIPTION_FAILED"
    RECONNECT_LIMIT_EXHAUSTED = "RECONNECT_LIMIT_EXHAUSTED"
    PROVIDER_DISCONNECTED = "PROVIDER_DISCONNECTED"
    BACKPRESSURE_GAP = "BACKPRESSURE_GAP"
    MALFORMED_PACKET = "MALFORMED_PACKET"
    UNKNOWN_PROVIDER_SECURITY = "UNKNOWN_PROVIDER_SECURITY"
    SESSION_EXCLUDED = "SESSION_EXCLUDED"
    STORAGE_RETENTION_UNSET = "STORAGE_RETENTION_UNSET"


class ProspectiveMarketDataFrameOutcome(StrEnum):
    QUEUED = "QUEUED"
    BACKPRESSURE_REJECTED = "BACKPRESSURE_REJECTED"
    NORMALIZED = "NORMALIZED"
    DUPLICATE = "DUPLICATE"
    UNSUPPORTED = "UNSUPPORTED"
    MALFORMED = "MALFORMED"
    UNKNOWN_SECURITY = "UNKNOWN_SECURITY"
    SESSION_EXCLUDED = "SESSION_EXCLUDED"
    PROVIDER_DISCONNECTED = "PROVIDER_DISCONNECTED"


class _QuoteTransport(Protocol):
    def send(self, payload: str) -> None: ...
    def close(self) -> None: ...


@dataclass(frozen=True, slots=True)
class ProspectiveMarketDataRuntimeSettings:
    """Non-secret operator settings.  The only enable switch is explicit."""

    enabled: bool = False
    queue_capacity: int = 256
    max_reconnect_attempts: int = 3
    provider: str = DHAN_PROVIDER

    def __post_init__(self) -> None:
        if (
            not isinstance(self.enabled, bool)
            or not isinstance(self.queue_capacity, int)
            or not isinstance(self.max_reconnect_attempts, int)
            or self.queue_capacity < 1
            or self.max_reconnect_attempts < 1
            or self.provider != DHAN_PROVIDER
        ):
            raise ProspectiveMarketDataRuntimeError("PROSPECTIVE_RUNTIME_SETTINGS_INVALID")

    @classmethod
    def from_environment(cls, environ: Mapping[str, str] | None = None) -> "ProspectiveMarketDataRuntimeSettings":
        """Reuse the existing explicit Dhan enablement flag; default is inert."""
        values = environ if environ is not None else os.environ
        enabled = values.get("DHAN_LIVE_MARKET_ENABLED", "").strip().lower() == "true"
        return cls(enabled=enabled)

    @property
    def fingerprint(self) -> str:
        return _digest({
            "contract": CONTRACT_ID, "version": CONTRACT_VERSION,
            "enabled": self.enabled, "queue_capacity": self.queue_capacity,
            "max_reconnect_attempts": self.max_reconnect_attempts, "provider": self.provider,
        })


@dataclass(frozen=True, slots=True)
class ProspectiveMarketDataBlockedIdentity:
    canonical_security_id: str
    blocker_code: str

    def __post_init__(self) -> None:
        if not _identifier(self.canonical_security_id) or not _identifier(self.blocker_code):
            raise ProspectiveMarketDataRuntimeError("PROSPECTIVE_RUNTIME_BLOCKED_IDENTITY_INVALID")


@dataclass(frozen=True, slots=True)
class ProspectiveMarketDataUniverse:
    """Immutable selected-denominator mapping snapshot; blocked rows stay visible."""

    selected_denominator: int
    exact_identities: tuple[DhanProspectiveInstrumentIdentity, ...]
    blocked_identities: tuple[ProspectiveMarketDataBlockedIdentity, ...]
    fingerprint: str

    def __post_init__(self) -> None:
        exact = tuple(sorted(self.exact_identities, key=lambda value: (value.canonical_security_id, value.provider_security_id)))
        blocked = tuple(sorted(self.blocked_identities, key=lambda value: (value.canonical_security_id, value.blocker_code)))
        values = _universe_values(self.selected_denominator, exact, blocked)
        identifiers = tuple(value.canonical_security_id for value in exact) + tuple(value.canonical_security_id for value in blocked)
        if (
            self.selected_denominator < 0
            or self.selected_denominator != len(exact) + len(blocked)
            or self.exact_identities != exact
            or self.blocked_identities != blocked
            or len(set(identifiers)) != len(identifiers)
            or len({value.provider_security_id for value in exact}) != len(exact)
            or any(not isinstance(value, DhanProspectiveInstrumentIdentity) for value in exact)
            or any(not isinstance(value, ProspectiveMarketDataBlockedIdentity) for value in blocked)
            or self.fingerprint != _digest(values)
        ):
            raise ProspectiveMarketDataRuntimeError("PROSPECTIVE_RUNTIME_UNIVERSE_INVALID")

    @property
    def blocker_distribution(self) -> tuple[tuple[str, int], ...]:
        return tuple(sorted(Counter(value.blocker_code for value in self.blocked_identities).items()))


def make_prospective_market_data_universe(
    *, selected_denominator: int,
    exact_identities: tuple[DhanProspectiveInstrumentIdentity, ...],
    blocked_identities: tuple[ProspectiveMarketDataBlockedIdentity, ...],
) -> ProspectiveMarketDataUniverse:
    exact = tuple(sorted(exact_identities, key=lambda value: (value.canonical_security_id, value.provider_security_id)))
    blocked = tuple(sorted(blocked_identities, key=lambda value: (value.canonical_security_id, value.blocker_code)))
    return ProspectiveMarketDataUniverse(
        selected_denominator, exact, blocked, _digest(_universe_values(selected_denominator, exact, blocked)),
    )


@dataclass(frozen=True, slots=True)
class ProspectiveMarketDataRunReceipt:
    run_id: str
    provider: str
    runtime_version: str
    started_at: datetime
    configuration_fingerprint: str
    universe_fingerprint: str
    selected_denominator: int
    subscribed_exact_ready_count: int
    blocked_count: int
    blocker_distribution: tuple[tuple[str, int], ...]
    provider_contract_version: str
    provider_contract_fingerprint: str
    session_calendar_policy_version: str
    calendar_id: str
    calendar_fingerprint: str
    fingerprint: str

    def __post_init__(self) -> None:
        distribution = tuple(sorted(self.blocker_distribution))
        values = _run_receipt_values(self, distribution)
        if (
            not _identifier(self.run_id)
            or self.provider != DHAN_PROVIDER
            or self.runtime_version != CONTRACT_VERSION
            or not _utc_aware(self.started_at)
            or not _fingerprint(self.configuration_fingerprint)
            or not _fingerprint(self.universe_fingerprint)
            or self.selected_denominator != self.subscribed_exact_ready_count + self.blocked_count
            or self.subscribed_exact_ready_count < 0 or self.blocked_count < 0
            or self.blocker_distribution != distribution
            or any(not _identifier(code) or count < 1 for code, count in distribution)
            or sum(count for _, count in distribution) != self.blocked_count
            or self.provider_contract_version != "v2"
            or not _fingerprint(self.provider_contract_fingerprint)
            or self.session_calendar_policy_version != "canonical-market-session-calendar-v1"
            or not _identifier(self.calendar_id) or not _fingerprint(self.calendar_fingerprint)
            or self.fingerprint != _digest(values)
        ):
            raise ProspectiveMarketDataRuntimeError("PROSPECTIVE_RUNTIME_RUN_RECEIPT_INVALID")


@dataclass(frozen=True, slots=True)
class ProspectiveMarketDataRuntimeHealth:
    state: ProspectiveMarketDataRuntimeState
    run_id: str | None
    provider: str
    started_at: datetime | None
    last_provider_message_at: datetime | None
    last_normalized_event_at: datetime | None
    subscription_requested: int
    subscription_active: int | None
    blocked_security_count: int
    reconnect_count: int
    gap_count: int
    parse_error_count: int
    finalized_fifteen_minute_count: int
    last_error_code: str | None
    storage_retention_state: str
    cross_host_lease_state: str

    def __post_init__(self) -> None:
        if (
            not isinstance(self.state, ProspectiveMarketDataRuntimeState)
            or (self.run_id is not None and not _identifier(self.run_id))
            or self.provider != DHAN_PROVIDER
            or any(value is not None and not _utc_aware(value) for value in (self.started_at, self.last_provider_message_at, self.last_normalized_event_at))
            or any(value < 0 for value in (self.subscription_requested, self.blocked_security_count, self.reconnect_count, self.gap_count, self.parse_error_count, self.finalized_fifteen_minute_count))
            or (self.subscription_active is not None and self.subscription_active < 0)
            or (self.last_error_code is not None and not _identifier(self.last_error_code))
            or self.storage_retention_state != WHOLE_UNIVERSE_LONG_RETENTION_1M
            or self.cross_host_lease_state != CROSS_HOST_MARKET_RUNTIME_LEASE
        ):
            raise ProspectiveMarketDataRuntimeError("PROSPECTIVE_RUNTIME_HEALTH_INVALID")


@dataclass(frozen=True, slots=True)
class _QueuedFrame:
    frame: bytes
    received_at: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.frame, bytes) or not self.frame or not _utc_aware(self.received_at):
            raise ProspectiveMarketDataRuntimeError("PROSPECTIVE_RUNTIME_FRAME_INVALID")


class ProspectiveMarketDataRuntime:
    """Explicit one-process coordinator.  It never self-starts or self-schedules."""

    _ownership_lock = Lock()
    _active_owner: str | None = None

    def __init__(
        self,
        *,
        settings: ProspectiveMarketDataRuntimeSettings,
        universe: ProspectiveMarketDataUniverse,
        calendar: CanonicalMarketSessionCalendar,
        transport_factory: Callable[[], _QuoteTransport],
        fifteen_minute_store: ProspectiveCanonicalFifteenMinuteStore,
    ) -> None:
        if not isinstance(settings, ProspectiveMarketDataRuntimeSettings) or not isinstance(universe, ProspectiveMarketDataUniverse):
            raise ProspectiveMarketDataRuntimeError("PROSPECTIVE_RUNTIME_INPUT_INVALID")
        if not isinstance(calendar, CanonicalMarketSessionCalendar) or not isinstance(fifteen_minute_store, ProspectiveCanonicalFifteenMinuteStore):
            raise ProspectiveMarketDataRuntimeError("PROSPECTIVE_RUNTIME_DEPENDENCY_INVALID")
        self._settings = settings
        self._universe = universe
        self._calendar = calendar
        self._transport_factory = transport_factory
        self._fifteen_minute_store = fifteen_minute_store
        self._state = ProspectiveMarketDataRuntimeState.STOPPED
        self._run: ProspectiveMarketDataRunReceipt | None = None
        self._transport: _QuoteTransport | None = None
        self._connection_id: str | None = None
        self._connection_sequence = 0
        self._builder = ProspectiveDhanOneMinuteBarBuilder()
        self._frames: deque[_QueuedFrame] = deque()
        self._minute_evidence: dict[tuple[str, str, datetime], CanonicalProspectiveMinuteEvidence] = {}
        self._derived_fifteen: set[str] = set()
        self._last_provider_message_at: datetime | None = None
        self._last_normalized_event_at: datetime | None = None
        self._pending_gap_at: datetime | None = None
        self._reconnect_count = 0
        self._gap_count = 0
        self._parse_error_count = 0
        self._finalized_fifteen_count = 0
        self._last_error_code: str | None = None
        self._seen_run_ids: set[str] = set()

    @property
    def state(self) -> ProspectiveMarketDataRuntimeState:
        return self._state

    @property
    def run_receipt(self) -> ProspectiveMarketDataRunReceipt | None:
        return self._run

    def health(self) -> ProspectiveMarketDataRuntimeHealth:
        return ProspectiveMarketDataRuntimeHealth(
            self._state, None if self._run is None else self._run.run_id, DHAN_PROVIDER,
            None if self._run is None else self._run.started_at,
            self._last_provider_message_at, self._last_normalized_event_at,
            len(self._universe.exact_identities) if self._run is not None else 0,
            None, len(self._universe.blocked_identities), self._reconnect_count,
            self._gap_count, self._parse_error_count, self._finalized_fifteen_count,
            self._last_error_code, WHOLE_UNIVERSE_LONG_RETENTION_1M, CROSS_HOST_MARKET_RUNTIME_LEASE,
        )

    def start(self, *, run_id: str, started_at: datetime) -> ProspectiveMarketDataRunReceipt | None:
        """Open one explicitly authorised connection; disabled settings are inert."""
        start = _utc_required(started_at)
        if self._state is not ProspectiveMarketDataRuntimeState.STOPPED:
            raise ProspectiveMarketDataRuntimeError("PROSPECTIVE_RUNTIME_START_STATE_INVALID")
        if not self._settings.enabled:
            self._last_error_code = ProspectiveMarketDataRuntimeReason.DISABLED_BY_CONFIGURATION.value
            return None
        if not _identifier(run_id):
            raise ProspectiveMarketDataRuntimeError("PROSPECTIVE_RUNTIME_RUN_ID_INVALID")
        self._claim_ownership(run_id)
        self._reset_run_capture_state()
        self._state = ProspectiveMarketDataRuntimeState.STARTING
        provider_contract = dhan_v2_live_provider_contract()
        self._run = ProspectiveMarketDataRunReceipt(
            run_id, DHAN_PROVIDER, CONTRACT_VERSION, start, self._settings.fingerprint,
            self._universe.fingerprint, self._universe.selected_denominator,
            len(self._universe.exact_identities), len(self._universe.blocked_identities),
            self._universe.blocker_distribution, provider_contract.version, provider_contract.fingerprint,
            "canonical-market-session-calendar-v1", self._calendar.calendar_id, self._calendar.fingerprint,
            _digest(_run_receipt_values_from(
                run_id=run_id, started_at=start, settings_fingerprint=self._settings.fingerprint,
                universe=self._universe, provider_contract_fingerprint=provider_contract.fingerprint,
                calendar=self._calendar,
            )),
        )
        try:
            self._open_and_subscribe(at=start)
        except Exception:
            self._state = ProspectiveMarketDataRuntimeState.FAILED
            self._last_error_code = ProspectiveMarketDataRuntimeReason.CONNECTION_FAILED.value
            self._release_ownership()
            raise ProspectiveMarketDataRuntimeError("PROSPECTIVE_RUNTIME_CONNECTION_FAILED") from None
        return self._run

    def enqueue_frame(self, *, frame: bytes, received_at: datetime) -> ProspectiveMarketDataFrameOutcome:
        """Accept bounded raw input without rewriting its original receipt time."""
        queued = _QueuedFrame(frame, _utc_required(received_at))
        self._require_running()
        if len(self._frames) >= self._settings.queue_capacity:
            self._begin_gap(queued.received_at, ProspectiveMarketDataRuntimeReason.BACKPRESSURE_GAP)
            return ProspectiveMarketDataFrameOutcome.BACKPRESSURE_REJECTED
        self._frames.append(queued)
        return ProspectiveMarketDataFrameOutcome.QUEUED

    def drain_one(self) -> ProspectiveMarketDataFrameOutcome | None:
        """Process one queued provider frame synchronously and deterministically."""
        self._require_running()
        if not self._frames:
            return None
        queued = self._frames.popleft()
        if self._pending_gap_at is not None:
            self._close_gap(queued.received_at)
        self._last_provider_message_at = queued.received_at
        disconnect = parse_dhan_disconnect_packet(queued.frame)
        if disconnect is not None:
            self.connection_lost(at=queued.received_at)
            return ProspectiveMarketDataFrameOutcome.PROVIDER_DISCONNECTED
        if not queued.frame or queued.frame[0] != DHAN_QUOTE_PACKET:
            return ProspectiveMarketDataFrameOutcome.UNSUPPORTED
        try:
            packets = parse_dhan_quote_packets(queued.frame)
        except DhanLiveBarError:
            self._parse_error_count += 1
            self._last_error_code = ProspectiveMarketDataRuntimeReason.MALFORMED_PACKET.value
            return ProspectiveMarketDataFrameOutcome.MALFORMED
        lookup = {value.provider_security_id: value for value in self._universe.exact_identities}
        outcome = ProspectiveMarketDataFrameOutcome.UNSUPPORTED
        for packet in packets:
            identity = lookup.get(packet.security_id)
            if identity is None:
                self._last_error_code = ProspectiveMarketDataRuntimeReason.UNKNOWN_PROVIDER_SECURITY.value
                outcome = ProspectiveMarketDataFrameOutcome.UNKNOWN_SECURITY
                continue
            assert self._connection_id is not None
            event = normalize_dhan_quote_packet(packet, identity=identity, received_at=queued.received_at, connection_id=self._connection_id)
            binding = bind_dhan_event_to_regular_minute(event, calendar=self._calendar)
            if binding.state.value != "BOUND_REGULAR_SESSION":
                self._last_error_code = ProspectiveMarketDataRuntimeReason.SESSION_EXCLUDED.value
                outcome = ProspectiveMarketDataFrameOutcome.SESSION_EXCLUDED
                continue
            observed = self._builder.observe(event, binding=binding)
            if observed == "DUPLICATE":
                outcome = ProspectiveMarketDataFrameOutcome.DUPLICATE
                continue
            self._last_normalized_event_at = event.received_at
            outcome = ProspectiveMarketDataFrameOutcome.NORMALIZED
        return outcome

    def finalize_through(self, *, known_at: datetime) -> int:
        """Finalise only already-observed whole minutes and derive covered 15m receipts."""
        self._require_running()
        cutoff = _utc_required(known_at)
        finalized = self._builder.finalize_through(known_at=cutoff)
        for receipt in finalized:
            evidence = prospective_minute_evidence_from_dhan(receipt)
            key = (evidence.canonical_security_id, evidence.session_id, evidence.interval_start)
            existing = self._minute_evidence.get(key)
            if existing is not None and existing != evidence:
                raise ProspectiveMarketDataRuntimeError("PROSPECTIVE_RUNTIME_MINUTE_LINEAGE_CONFLICT")
            self._minute_evidence[key] = evidence
            self._derive_covered_fifteen(evidence=evidence, known_at=cutoff)
        return len(finalized)

    def connection_lost(self, *, at: datetime) -> None:
        """Record the unobserved boundary.  A caller must explicitly retry later."""
        self._require_running()
        self._begin_gap(_utc_required(at), ProspectiveMarketDataRuntimeReason.PROVIDER_DISCONNECTED)
        self._state = ProspectiveMarketDataRuntimeState.RECONNECTING
        self._close_transport()

    def reconnect(self, *, at: datetime) -> None:
        """Bounded explicit reconnect with the same immutable universe snapshot."""
        moment = _utc_required(at)
        if self._state is not ProspectiveMarketDataRuntimeState.RECONNECTING:
            raise ProspectiveMarketDataRuntimeError("PROSPECTIVE_RUNTIME_RECONNECT_STATE_INVALID")
        if self._reconnect_count >= self._settings.max_reconnect_attempts:
            self._state = ProspectiveMarketDataRuntimeState.FAILED
            self._last_error_code = ProspectiveMarketDataRuntimeReason.RECONNECT_LIMIT_EXHAUSTED.value
            raise ProspectiveMarketDataRuntimeError("PROSPECTIVE_RUNTIME_RECONNECT_LIMIT_EXHAUSTED")
        self._reconnect_count += 1
        try:
            # The gap belongs to the disconnected connection, never the fresh
            # socket.  Keep that prior lineage across resubscription.
            previous_connection, pending_gap = self._connection_id, self._pending_gap_at
            self._open_and_subscribe(at=moment)
            if pending_gap is not None and previous_connection is not None and moment > pending_gap:
                self._builder.record_gap(
                    connection_id=previous_connection,
                    disconnected_at=pending_gap,
                    reconnected_at=moment,
                )
            self._pending_gap_at = None
        except Exception:
            self._state = ProspectiveMarketDataRuntimeState.RECONNECTING
            self._last_error_code = ProspectiveMarketDataRuntimeReason.CONNECTION_FAILED.value
            raise ProspectiveMarketDataRuntimeError("PROSPECTIVE_RUNTIME_RECONNECT_FAILED") from None

    def stop(self) -> None:
        """Release only this in-process owner; active partial windows are never promoted."""
        if self._state is ProspectiveMarketDataRuntimeState.STOPPED:
            return
        self._state = ProspectiveMarketDataRuntimeState.STOPPING
        self._frames.clear()
        self._close_transport()
        self._release_ownership()
        self._state = ProspectiveMarketDataRuntimeState.STOPPED

    def _open_and_subscribe(self, *, at: datetime) -> None:
        self._state = ProspectiveMarketDataRuntimeState.CONNECTING
        transport = self._transport_factory()
        try:
            self._state = ProspectiveMarketDataRuntimeState.SUBSCRIBING
            for message in quote_subscription_messages(self._universe.exact_identities):
                transport.send(message)
        except Exception:
            transport.close()
            raise
        self._transport = transport
        self._connection_sequence += 1
        assert self._run is not None
        self._connection_id = f"{self._run.run_id}:connection:{self._connection_sequence}"
        self._builder.begin_connection(connection_id=self._connection_id, observed_at=at)
        self._state = ProspectiveMarketDataRuntimeState.RUNNING

    def _derive_covered_fifteen(self, *, evidence: CanonicalProspectiveMinuteEvidence, known_at: datetime) -> None:
        session_day = evidence.period.session_dates[0]
        session = bind_canonical_prospective_fifteen_minute_session(
            calendar=self._calendar, session_date=session_day, as_of=known_at,
        )
        if session.session_id != evidence.session_id:
            return
        partition = next(
            (value for value in canonical_prospective_fifteen_minute_partitions(session)
             if value.interval_start <= evidence.interval_start < value.interval_end),
            None,
        )
        if partition is None:
            return
        expected = tuple(
            self._minute_evidence.get((evidence.canonical_security_id, evidence.session_id, start))
            for start in (partition.interval_start + timedelta(minutes=index) for index in range(15))
        )
        if any(value is None for value in expected):
            return
        sources = tuple(value for value in expected if value is not None)
        receipt = derive_canonical_prospective_fifteen_minute_receipt(
            partition=partition, canonical_security_id=evidence.canonical_security_id,
            isin=evidence.isin, source_evidence=sources, finalized_at=known_at,
        )
        if receipt.receipt_id in self._derived_fifteen:
            return
        self._fifteen_minute_store.save(receipt, detected_at=known_at)
        self._derived_fifteen.add(receipt.receipt_id)
        self._finalized_fifteen_count += 1

    def _begin_gap(self, at: datetime, reason: ProspectiveMarketDataRuntimeReason) -> None:
        if self._pending_gap_at is None:
            self._pending_gap_at = at
            self._gap_count += 1
        self._last_error_code = reason.value
        if self._state is ProspectiveMarketDataRuntimeState.RUNNING:
            self._state = ProspectiveMarketDataRuntimeState.DEGRADED

    def _close_gap(self, at: datetime) -> None:
        if self._pending_gap_at is None:
            return
        if at <= self._pending_gap_at:
            return
        if self._connection_id is not None:
            self._builder.record_gap(
                connection_id=self._connection_id, disconnected_at=self._pending_gap_at, reconnected_at=at,
            )
        self._pending_gap_at = None
        if self._state is ProspectiveMarketDataRuntimeState.DEGRADED:
            self._state = ProspectiveMarketDataRuntimeState.RUNNING

    def _require_running(self) -> None:
        if self._state not in {
            ProspectiveMarketDataRuntimeState.RUNNING,
            ProspectiveMarketDataRuntimeState.DEGRADED,
        }:
            raise ProspectiveMarketDataRuntimeError("PROSPECTIVE_RUNTIME_NOT_RUNNING")

    def _claim_ownership(self, run_id: str) -> None:
        with self._ownership_lock:
            if self._active_owner is not None:
                raise ProspectiveMarketDataRuntimeError("PROSPECTIVE_RUNTIME_ALREADY_OWNED")
            if run_id in self._seen_run_ids:
                raise ProspectiveMarketDataRuntimeError("PROSPECTIVE_RUNTIME_RUN_ID_REUSED")
            type(self)._active_owner = run_id
            self._seen_run_ids.add(run_id)

    def _release_ownership(self) -> None:
        with self._ownership_lock:
            if self._run is not None and self._active_owner == self._run.run_id:
                type(self)._active_owner = None

    def _close_transport(self) -> None:
        if self._transport is not None:
            try:
                self._transport.close()
            finally:
                self._transport = None

    def _reset_run_capture_state(self) -> None:
        """A process restart has no authority to join incomplete prior windows."""
        self._transport = None
        self._connection_id = None
        self._connection_sequence = 0
        self._builder = ProspectiveDhanOneMinuteBarBuilder()
        self._frames.clear()
        self._minute_evidence.clear()
        self._derived_fifteen.clear()
        self._last_provider_message_at = None
        self._last_normalized_event_at = None
        self._pending_gap_at = None
        self._reconnect_count = 0
        self._gap_count = 0
        self._parse_error_count = 0
        self._finalized_fifteen_count = 0
        self._last_error_code = None


def serialize_prospective_market_data_runtime_health(value: ProspectiveMarketDataRuntimeHealth) -> str:
    value.__post_init__()
    return _canonical({
        "contract": CONTRACT_ID, "version": CONTRACT_VERSION, "state": value.state.value,
        "run_id": value.run_id, "provider": value.provider, "started_at": _time(value.started_at),
        "last_provider_message_at": _time(value.last_provider_message_at),
        "last_normalized_event_at": _time(value.last_normalized_event_at),
        "subscription_requested": value.subscription_requested, "subscription_active": value.subscription_active,
        "blocked_security_count": value.blocked_security_count, "reconnect_count": value.reconnect_count,
        "gap_count": value.gap_count, "parse_error_count": value.parse_error_count,
        "finalized_fifteen_minute_count": value.finalized_fifteen_minute_count,
        "last_error_code": value.last_error_code, "storage_retention_state": value.storage_retention_state,
        "cross_host_lease_state": value.cross_host_lease_state,
    })


def _universe_values(selected: int, exact: tuple[DhanProspectiveInstrumentIdentity, ...], blocked: tuple[ProspectiveMarketDataBlockedIdentity, ...]) -> dict[str, object]:
    return {
        "contract": CONTRACT_ID, "version": CONTRACT_VERSION, "selected_denominator": selected,
        "exact": [{"canonical_security_id": value.canonical_security_id, "isin": value.isin, "provider_security_id": value.provider_security_id, "master_fingerprint": value.master_fingerprint} for value in exact],
        "blocked": [{"canonical_security_id": value.canonical_security_id, "blocker_code": value.blocker_code} for value in blocked],
    }


def _run_receipt_values(value: ProspectiveMarketDataRunReceipt, distribution: tuple[tuple[str, int], ...]) -> dict[str, object]:
    return {
        "contract": CONTRACT_ID, "version": CONTRACT_VERSION, "run_id": value.run_id,
        "provider": value.provider, "runtime_version": value.runtime_version, "started_at": _time(value.started_at),
        "configuration_fingerprint": value.configuration_fingerprint, "universe_fingerprint": value.universe_fingerprint,
        "selected_denominator": value.selected_denominator, "subscribed_exact_ready_count": value.subscribed_exact_ready_count,
        "blocked_count": value.blocked_count, "blocker_distribution": list(distribution),
        "provider_contract_version": value.provider_contract_version, "provider_contract_fingerprint": value.provider_contract_fingerprint,
        "session_calendar_policy_version": value.session_calendar_policy_version,
        "calendar_id": value.calendar_id, "calendar_fingerprint": value.calendar_fingerprint,
    }


def _run_receipt_values_from(*, run_id: str, started_at: datetime, settings_fingerprint: str, universe: ProspectiveMarketDataUniverse, provider_contract_fingerprint: str, calendar: CanonicalMarketSessionCalendar) -> dict[str, object]:
    return {
        "contract": CONTRACT_ID, "version": CONTRACT_VERSION, "run_id": run_id, "provider": DHAN_PROVIDER,
        "runtime_version": CONTRACT_VERSION, "started_at": _time(started_at),
        "configuration_fingerprint": settings_fingerprint, "universe_fingerprint": universe.fingerprint,
        "selected_denominator": universe.selected_denominator, "subscribed_exact_ready_count": len(universe.exact_identities),
        "blocked_count": len(universe.blocked_identities), "blocker_distribution": list(universe.blocker_distribution),
        "provider_contract_version": "v2", "provider_contract_fingerprint": provider_contract_fingerprint,
        "session_calendar_policy_version": "canonical-market-session-calendar-v1",
        "calendar_id": calendar.calendar_id, "calendar_fingerprint": calendar.fingerprint,
    }


def _utc_required(value: datetime) -> datetime:
    if not _utc_aware(value):
        raise ProspectiveMarketDataRuntimeError("PROSPECTIVE_RUNTIME_TIMESTAMP_INVALID")
    return value.astimezone(UTC)


def _utc_aware(value: object) -> bool:
    return isinstance(value, datetime) and value.tzinfo is not None and value.utcoffset() is not None and value.astimezone(UTC).tzinfo is UTC


def _identifier(value: object) -> bool:
    return isinstance(value, str) and bool(_IDENTIFIER.fullmatch(value))


def _fingerprint(value: object) -> bool:
    return isinstance(value, str) and bool(_FINGERPRINT.fullmatch(value))


def _time(value: datetime | None) -> str | None:
    return None if value is None else _utc_required(value).isoformat()


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _digest(value: object) -> str:
    return "sha256:" + sha256(_canonical(value).encode()).hexdigest()


__all__ = [
    "CROSS_HOST_MARKET_RUNTIME_LEASE", "RAW_TICK_RETENTION_POLICY", "WHOLE_UNIVERSE_LONG_RETENTION_1M",
    "ProspectiveMarketDataBlockedIdentity", "ProspectiveMarketDataFrameOutcome", "ProspectiveMarketDataRunReceipt",
    "ProspectiveMarketDataRuntime", "ProspectiveMarketDataRuntimeError", "ProspectiveMarketDataRuntimeHealth",
    "ProspectiveMarketDataRuntimeReason", "ProspectiveMarketDataRuntimeSettings", "ProspectiveMarketDataRuntimeState",
    "ProspectiveMarketDataUniverse", "make_prospective_market_data_universe", "serialize_prospective_market_data_runtime_health",
]
