"""Focused proofs for the bounded canonical 15m technical-reader boundary."""
from __future__ import annotations

from copy import deepcopy
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from app.historical.nse_capital_market_session_evidence_2022_2026 import nse_capital_market_calendar_2022_2026
from app.domain.models import Instrument
from app.market_data.canonical_fifteen_minute_technical_reader import (
    CanonicalFifteenMinuteContinuityState,
    CanonicalFifteenMinuteInputState,
    CanonicalFifteenMinuteTechnicalReadMode,
    CanonicalFifteenMinuteTechnicalReadReason,
    CanonicalFifteenMinuteTechnicalReadRequest,
    CanonicalFifteenMinuteTechnicalReadState,
    canonical_fifteen_minute_technical_input,
    read_canonical_prospective_fifteen_minute_bars,
    serialize_canonical_fifteen_minute_technical_read,
)
from app.market_data.models import AdjustmentStatus, Exchange, Timeframe
from app.market_data.prospective_fifteen_minute_bar import (
    CanonicalProspectiveFifteenMinuteSession,
    ProspectiveCanonicalFifteenMinuteStore,
    ProspectiveFifteenMinuteState,
    ProspectiveMinuteEvidenceState,
    bind_canonical_prospective_fifteen_minute_session,
    canonical_prospective_fifteen_minute_partitions,
    derive_canonical_prospective_fifteen_minute_receipt,
    make_prospective_minute_evidence,
)
from app.market_data.technical_bar_contract import TechnicalTradingPeriod
from app.storage.core_api_snapshot_repository import CoreApiSnapshot, CoreApiSnapshotFamily
from app.storage.sqlite_core_api_snapshot_repository import SQLiteCoreApiSnapshotRepository


AS_OF = datetime(2026, 9, 8, 16, tzinfo=UTC)
SECURITY = "NSE:INE000000001"
ISIN = "INE000000001"


def _session() -> CanonicalProspectiveFifteenMinuteSession:
    return bind_canonical_prospective_fifteen_minute_session(
        calendar=nse_capital_market_calendar_2022_2026(), session_date=date(2026, 9, 8), as_of=AS_OF,
    )


def _source_period(session: CanonicalProspectiveFifteenMinuteSession, start: datetime, end: datetime, index: int) -> TechnicalTradingPeriod:
    return TechnicalTradingPeriod(
        venue=Exchange.NSE, segment="CAPITAL_MARKET", period_id=f"reader-minute:{index:03d}",
        session_dates=session.period.session_dates, starts_at=start, ends_at=end,
        timezone_id=session.period.timezone_id, calendar_id=session.period.calendar_id,
        calendar_fingerprint=session.period.calendar_fingerprint,
        session_source_ids=session.period.session_source_ids, session_source_fingerprints=session.period.session_source_fingerprints,
    )


def _receipt(
    session: CanonicalProspectiveFifteenMinuteSession, *, partition_index: int = 0,
    state: ProspectiveMinuteEvidenceState = ProspectiveMinuteEvidenceState.CLOSED, price_offset: int = 0,
):
    partition = canonical_prospective_fifteen_minute_partitions(session)[partition_index]
    evidence = []
    for index in range(15):
        start = partition.interval_start + timedelta(minutes=index)
        end = start + timedelta(minutes=1)
        common = dict(
            source_receipt_id=f"reader-minute:{partition_index:03d}:{index:03d}:{price_offset}",
            source_receipt_fingerprint="sha256:" + f"{partition_index * 1000 + index + 1 + price_offset:064x}",
            canonical_security_id=SECURITY, isin=ISIN, provider_family="fixture-provider", session_id=session.session_id,
            period=_source_period(session, start, end, index), interval_start=start, interval_end=end,
            known_at=end + timedelta(seconds=4),
        )
        if state is ProspectiveMinuteEvidenceState.CLOSED:
            price = Decimal(100 + price_offset + index)
            evidence.append(make_prospective_minute_evidence(
                **common, state=state, open=price, high=price + 2, low=price - 1,
                close=price + 1, volume=index + 1, event_count=1,
            ))
        elif state is ProspectiveMinuteEvidenceState.NO_TRADE_OBSERVED:
            evidence.append(make_prospective_minute_evidence(**common, state=state, source_reasons=("NO_TRADE_OBSERVED",)))
        elif state is ProspectiveMinuteEvidenceState.INCOMPLETE:
            evidence.append(make_prospective_minute_evidence(**common, state=state, source_reasons=("PROVIDER_GAP",)))
        else:
            evidence.append(make_prospective_minute_evidence(**common, state=state, source_reasons=("SOURCE_CONFLICT",)))
    return derive_canonical_prospective_fifteen_minute_receipt(
        partition=partition, canonical_security_id=SECURITY, isin=ISIN, source_evidence=evidence,
        finalized_at=partition.interval_end + timedelta(seconds=4),
    )


def _repository(tmp_path) -> SQLiteCoreApiSnapshotRepository:
    return SQLiteCoreApiSnapshotRepository(tmp_path / "reader.db")


def _save(repository: SQLiteCoreApiSnapshotRepository, *receipts) -> None:
    store = ProspectiveCanonicalFifteenMinuteStore(repository)
    for receipt in receipts:
        store.save(receipt, detected_at=receipt.known_at)


def _request(*, count: int = 1, mode: CanonicalFifteenMinuteTechnicalReadMode = CanonicalFifteenMinuteTechnicalReadMode.AS_OF_PROSPECTIVE_PIT, as_of: datetime | None = AS_OF):
    return CanonicalFifteenMinuteTechnicalReadRequest(SECURITY, count, mode, as_of)


def test_exact_finalized_complete_identity_read_and_minimal_technical_input(tmp_path) -> None:
    session = _session(); repository = _repository(tmp_path); receipt = _receipt(session)
    _save(repository, receipt)

    value = read_canonical_prospective_fifteen_minute_bars(repository=repository, request=_request())
    adapter = canonical_fifteen_minute_technical_input(value, instrument=Instrument(SECURITY, "FIXTURE", "NSE", ISIN))

    assert value.state is CanonicalFifteenMinuteTechnicalReadState.READY
    assert value.bars[0].canonical_security_id == SECURITY
    assert value.bars[0].timeframe is Timeframe.FIFTEEN_MINUTES
    assert value.bars[0].known_at == receipt.known_at
    assert value.bars[0].bar_fingerprint == receipt.bar.fingerprint
    assert adapter.state is CanonicalFifteenMinuteInputState.CANONICAL_15M_INPUT_AVAILABLE
    assert adapter.snapshot is not None and adapter.snapshot.observations[0].payload["timeframe"] == "15m"
    assert "dhan" not in serialize_canonical_fifteen_minute_technical_read(value).lower()


def test_unknown_exact_security_empty_store_is_fail_closed(tmp_path) -> None:
    repository = _repository(tmp_path)
    request = CanonicalFifteenMinuteTechnicalReadRequest("NSE:UNKNOWN", 1, CanonicalFifteenMinuteTechnicalReadMode.AS_OF_PROSPECTIVE_PIT, AS_OF)
    value = read_canonical_prospective_fifteen_minute_bars(repository=repository, request=request)
    assert value.state is CanonicalFifteenMinuteTechnicalReadState.INSUFFICIENT
    assert CanonicalFifteenMinuteTechnicalReadReason.CANONICAL_SECURITY_NO_STORED_RECEIPTS in value.reasons


@pytest.mark.parametrize("state,reason,continuity", [
    (ProspectiveMinuteEvidenceState.INCOMPLETE, CanonicalFifteenMinuteTechnicalReadReason.RECEIPT_INCOMPLETE, CanonicalFifteenMinuteContinuityState.OBSERVATION_GAP_OR_INCOMPLETE),
    (ProspectiveMinuteEvidenceState.EVIDENCE_CONFLICTED, CanonicalFifteenMinuteTechnicalReadReason.RECEIPT_CONFLICTED, CanonicalFifteenMinuteContinuityState.EVIDENCE_CONFLICTED),
    (ProspectiveMinuteEvidenceState.NO_TRADE_OBSERVED, CanonicalFifteenMinuteTechnicalReadReason.RECEIPT_NO_TRADE_NOT_MATERIALIZED, CanonicalFifteenMinuteContinuityState.NO_TRADE_UNMATERIALIZED),
])
def test_noneligible_receipt_states_stay_distinct_without_synthetic_fill(tmp_path, state, reason, continuity) -> None:
    session = _session(); repository = _repository(tmp_path); receipt = _receipt(session, state=state)
    _save(repository, receipt)
    value = read_canonical_prospective_fifteen_minute_bars(repository=repository, request=_request())
    assert value.state is CanonicalFifteenMinuteTechnicalReadState.INSUFFICIENT and value.bars == ()
    assert reason in value.reasons and continuity in value.continuity_states
    assert CanonicalFifteenMinuteTechnicalReadReason.ELIGIBLE_LOOKBACK_INSUFFICIENT in value.reasons


def test_conflict_artifact_blocks_an_otherwise_closed_bar(tmp_path) -> None:
    session = _session(); repository = _repository(tmp_path); first = _receipt(session); changed = _receipt(session, price_offset=100)
    _save(repository, first)
    assert ProspectiveCanonicalFifteenMinuteStore(repository).save(changed, detected_at=changed.known_at) is not None
    value = read_canonical_prospective_fifteen_minute_bars(repository=repository, request=_request())
    assert value.bars == () and CanonicalFifteenMinuteTechnicalReadReason.CONFLICT_ARTIFACT_PRESENT in value.reasons


def test_future_conflict_artifact_does_not_rewrite_an_earlier_as_of_read(tmp_path) -> None:
    session = _session(); repository = _repository(tmp_path); first = _receipt(session); changed = _receipt(session, price_offset=100)
    _save(repository, first)
    ProspectiveCanonicalFifteenMinuteStore(repository).save(changed, detected_at=AS_OF + timedelta(days=1))
    strict = read_canonical_prospective_fifteen_minute_bars(repository=repository, request=_request())
    current = read_canonical_prospective_fifteen_minute_bars(repository=repository, request=_request(mode=CanonicalFifteenMinuteTechnicalReadMode.CURRENT_DESCRIPTIVE, as_of=None))
    assert strict.state is CanonicalFifteenMinuteTechnicalReadState.READY
    assert current.state is CanonicalFifteenMinuteTechnicalReadState.INSUFFICIENT
    assert CanonicalFifteenMinuteTechnicalReadReason.CONFLICT_ARTIFACT_PRESENT in current.reasons


def test_as_of_excludes_not_yet_finalized_bars_but_current_descriptive_can_read_them(tmp_path) -> None:
    session = _session(); repository = _repository(tmp_path); receipt = _receipt(session)
    _save(repository, receipt)
    early = _request(as_of=receipt.known_at - timedelta(microseconds=1))
    current = _request(mode=CanonicalFifteenMinuteTechnicalReadMode.CURRENT_DESCRIPTIVE, as_of=None)
    assert read_canonical_prospective_fifteen_minute_bars(repository=repository, request=early).bars == ()
    assert read_canonical_prospective_fifteen_minute_bars(repository=repository, request=current).state is CanonicalFifteenMinuteTechnicalReadState.READY


def test_ordering_bounded_lookback_and_insufficiency_are_deterministic(tmp_path) -> None:
    session = _session(); repository = _repository(tmp_path)
    _save(repository, _receipt(session, partition_index=2), _receipt(session, partition_index=0), _receipt(session, partition_index=1))
    value = read_canonical_prospective_fifteen_minute_bars(repository=repository, request=_request(count=2))
    partial = read_canonical_prospective_fifteen_minute_bars(repository=repository, request=_request(count=4))
    assert [item.interval_start for item in value.bars] == sorted(item.interval_start for item in value.bars)
    assert [item.interval_start for item in value.bars] == [canonical_prospective_fifteen_minute_partitions(session)[1].interval_start, canonical_prospective_fifteen_minute_partitions(session)[2].interval_start]
    assert partial.state is CanonicalFifteenMinuteTechnicalReadState.INSUFFICIENT and len(partial.bars) == 3
    assert CanonicalFifteenMinuteTechnicalReadReason.ELIGIBLE_LOOKBACK_INSUFFICIENT in partial.reasons


def test_duplicate_and_malformed_interval_artifacts_fail_closed_without_arbitrary_selection() -> None:
    session = _session(); receipt = _receipt(session)
    snapshot = CoreApiSnapshot(f"canonical-prospective-15m:{receipt.receipt_id}", CoreApiSnapshotFamily.PROSPECTIVE_CANONICAL_FIFTEEN_MINUTE_BAR, "v1", "canonical-prospective-fifteen-minute-receipt-v1", receipt.fingerprint, receipt.known_at, receipt)
    # A shortened residual/cross-session artifact cannot be constructed by the
    # canonical derivation contract.  A malformed persisted payload is still
    # rejected, rather than being coerced into a 15m interval.
    malformed = deepcopy(receipt)
    object.__setattr__(malformed.partition, "interval_end", malformed.partition.interval_end + timedelta(minutes=1))
    invalid = CoreApiSnapshot(f"canonical-prospective-15m:{malformed.receipt_id}", CoreApiSnapshotFamily.PROSPECTIVE_CANONICAL_FIFTEEN_MINUTE_BAR, "v1", "canonical-prospective-fifteen-minute-receipt-v1", receipt.fingerprint, receipt.known_at, malformed)

    class Repository:
        def list_canonical_prospective_fifteen_minute_snapshots(self, *_args, **_kwargs): return (snapshot, snapshot, invalid)
        def list_canonical_prospective_fifteen_minute_conflicts(self, _receipt_ids, *, detected_at_lte): return ()

    value = read_canonical_prospective_fifteen_minute_bars(repository=Repository(), request=_request())
    assert value.bars == ()
    assert CanonicalFifteenMinuteTechnicalReadReason.DUPLICATE_CANONICAL_INTERVAL in value.reasons
    assert CanonicalFifteenMinuteTechnicalReadReason.RECEIPT_INVALID in value.reasons


def test_serialization_is_stable_and_forbidden_dependencies_are_absent(tmp_path) -> None:
    session = _session(); repository = _repository(tmp_path); _save(repository, _receipt(session))
    first = read_canonical_prospective_fifteen_minute_bars(repository=repository, request=_request())
    second = read_canonical_prospective_fifteen_minute_bars(repository=repository, request=_request())
    source = (Path(__file__).parents[2] / "app" / "market_data" / "canonical_fifteen_minute_technical_reader.py").read_text(encoding="utf-8")
    assert first.fingerprint == second.fingerprint
    assert serialize_canonical_fifteen_minute_technical_read(first) == serialize_canonical_fifteen_minute_technical_read(second)
    for forbidden in ("app.signals", "app.portfolio", "app.broker", "app.api", "app.market_data.dhan", "datetime.now", "save_snapshot"):
        assert forbidden not in source
