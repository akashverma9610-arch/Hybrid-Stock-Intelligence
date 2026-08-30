from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.data_coverage.models import DataCoverageDomain, DataCoverageStatus, DomainCoverage
from app.domain.models import DataQuality
from app.market_data.historical import SQLiteHistoricalBarStore
from app.market_data.models import AdjustmentStatus, CanonicalOHLCVBar, Exchange, InstrumentIdentity, InstrumentType, MarketDataProvenance, Timeframe
from app.real_brain.local import StoredTrialObservationSource, _trial_price_integrity
from app.data_coverage.service import DataCoverageService
from app.real_brain.models import RealBrainTrialStatus
from app.real_brain.service import (
    DeterministicRealSampleSelector, RealBrainTrialError, RealBrainTrialService, RealBrainTrialStore,
)
from app.storage.core_api_snapshot_repository import CoreApiSnapshotFamily
from app.storage.sqlite_core_api_snapshot_repository import SQLiteCoreApiSnapshotRepository
from app.universe_analysis.models import NseEquityInstrument
from app.universe_analysis.service import Canonical61DiagnosticRunner, StockDiagnosticInputAssembler, build_universe_snapshot


T = datetime(2026, 8, 24, tzinfo=UTC)


class StoredEvidence:
    canonical_stored_only = True

    def __init__(self):
        self.calls = 0

    def observations_as_of(self, at):
        self.calls += 1
        return ()


class NonCanonicalEvidence(StoredEvidence):
    canonical_stored_only = False


def _instruments(count: int = 45):
    return tuple(
        NseEquityInstrument(f"NSE:{number:04}", f"S{number:04}", f"INE{number:08}A", None, None, "ACTIVE", None, True, T, "NSE_OFFICIAL_EXPORT")
        for number in range(count)
    )


def _coverage(instrument_id: str, *, quote: DataCoverageStatus = DataCoverageStatus.MISSING):
    values = []
    for domain in DataCoverageDomain:
        status = DataCoverageStatus.READY if domain is DataCoverageDomain.IDENTITY else quote if domain is DataCoverageDomain.CURRENT_QUOTES else DataCoverageStatus.MISSING
        values.append(DomainCoverage(domain, status, T if status is not DataCoverageStatus.MISSING else None, (), None if status is DataCoverageStatus.READY else "NO_CANONICAL_EVIDENCE"))
    return DataCoverageService().record(universe_snapshot_id="universe-real", instrument_id=instrument_id, as_of=T, domains=tuple(values))


def _service(tmp_path, source):
    repository = SQLiteCoreApiSnapshotRepository(tmp_path / "trial.sqlite")
    return RealBrainTrialService(
        selector=DeterministicRealSampleSelector(), assembler=StockDiagnosticInputAssembler(source),
        runner=Canonical61DiagnosticRunner(), store=RealBrainTrialStore(repository), clock=lambda: T,
    ), RealBrainTrialStore(repository), repository


def test_snapshot_sample_is_deterministic_bounded_and_not_a_strategy_shortlist():
    instruments = _instruments(); snapshot = build_universe_snapshot(snapshot_id="universe-real", as_of=T, source="NSE_OFFICIAL_EXPORT", instruments=instruments)
    selector = DeterministicRealSampleSelector()
    first = selector.select(snapshot=snapshot, instruments=instruments, sample_size=30)
    second = selector.select(snapshot=snapshot, instruments=tuple(reversed(instruments)), sample_size=30)
    assert first == second
    assert len(first.instruments) == 30 and first.method == "SNAPSHOT_SCOPED_STABLE_HASH_NO_TAXONOMY_INFERENCE"
    assert {item.symbol for item in first.instruments}.isdisjoint({"BEL", "HAL", "LT", "L&T"})
    with pytest.raises(RealBrainTrialError, match="between 30 and 50"):
        selector.select(snapshot=snapshot, instruments=instruments, sample_size=51)


def test_trial_requires_canonical_stored_evidence_and_never_runs_the_full_universe(tmp_path):
    instruments = _instruments(); snapshot = build_universe_snapshot(snapshot_id="universe-real", as_of=T, source="NSE_OFFICIAL_EXPORT", instruments=instruments)
    source = NonCanonicalEvidence(); service, _, _ = _service(tmp_path, source)
    with pytest.raises(RealBrainTrialError, match="CANONICAL_STORED"):
        service.run(snapshot=snapshot, instruments=instruments, coverage_by_instrument={item.instrument_id: _coverage(item.instrument_id) for item in instruments}, source=source, sample_size=30)
    assert source.calls == 0


def test_sparse_real_style_trial_keeps_missing_domains_missing_non_actionable_and_auditable(tmp_path):
    instruments = _instruments(); snapshot = build_universe_snapshot(snapshot_id="universe-real", as_of=T, source="NSE_OFFICIAL_EXPORT", instruments=instruments)
    source = StoredEvidence(); service, store, repository = _service(tmp_path, source)
    selected_id = DeterministicRealSampleSelector().select(snapshot=snapshot, instruments=instruments, sample_size=30).instruments[0].instrument_id
    coverage = {item.instrument_id: _coverage(item.instrument_id, quote=DataCoverageStatus.STALE if item.instrument_id == selected_id else DataCoverageStatus.MISSING) for item in instruments}
    result = service.run(snapshot=snapshot, instruments=instruments, coverage_by_instrument=coverage, source=source, sample_size=30)
    rows = store.results(result.trial_id)
    assert len(rows) == 30 and source.calls == 1
    assert result.provider_calls == 0 and result.diagnostic_total_per_stock == 61
    assert result.complete_count == 0 and result.unavailable_count >= 29 and result.partial_count <= 1
    assert all(row.diagnostic_total == 61 and row.diagnostic_evaluated + row.diagnostic_missing == 61 for row in rows)
    assert all(row.decision_score is None and row.confidence is None and row.execution_eligibility == "UNAVAILABLE" for row in rows)
    assert all(not row.technical_ready and not row.fundamental_ready and not row.ownership_ready and not row.delivery_ready for row in rows)
    assert all(row.pre_breakout.value != "READY" and row.inflection.value != "READY" for row in rows)
    assert all("NO_TAXONOMY" in row.blockers and "NO_OWNERSHIP" in row.blockers for row in rows)
    assert store.get_trial(result.trial_id) == result
    assert {item.family for item in repository.list_snapshots(CoreApiSnapshotFamily.REAL_BRAIN_STOCK_RESULT, limit=100)} == {CoreApiSnapshotFamily.REAL_BRAIN_STOCK_RESULT}
    assert "NO_ALPHA_CLAIMS" in result.warnings and not hasattr(result, "cagr") and not hasattr(result, "win_rate")
    protected = {CoreApiSnapshotFamily.PROMOTION_PROPOSAL, CoreApiSnapshotFamily.PROMOTION_ELIGIBILITY, CoreApiSnapshotFamily.PROMOTION_REVIEW, CoreApiSnapshotFamily.APPROVED_STRATEGY_VERSION, CoreApiSnapshotFamily.STRATEGY_ACTIVATION, CoreApiSnapshotFamily.PAPER_TRADE}
    assert all(not repository.list_snapshots(family, limit=1) for family in protected)


def test_known_taxonomy_balances_selection_without_inventing_a_sector(tmp_path):
    instruments = _instruments(); snapshot = build_universe_snapshot(snapshot_id="universe-real", as_of=T, source="NSE_OFFICIAL_EXPORT", instruments=instruments)
    sectors = {item.instrument_id: "A" if int(item.symbol[1:]) % 2 else "B" for item in instruments}
    selection = DeterministicRealSampleSelector().select(snapshot=snapshot, instruments=instruments, sample_size=30, sectors=sectors)
    chosen = [sectors[item.instrument_id] for item in selection.instruments]
    assert selection.method.startswith("KNOWN_TAXONOMY") and abs(chosen.count("A") - chosen.count("B")) <= 1


def test_frozen_cohort_reuses_exact_prior_symbols_even_if_taxonomy_arrives_later(tmp_path):
    instruments = _instruments(); snapshot = build_universe_snapshot(snapshot_id="universe-real", as_of=T, source="NSE_OFFICIAL_EXPORT", instruments=instruments)
    source = StoredEvidence(); service, store, _ = _service(tmp_path, source)
    coverage = {item.instrument_id: _coverage(item.instrument_id) for item in instruments}
    first = service.run(snapshot=snapshot, instruments=instruments, coverage_by_instrument=coverage, source=source, sample_size=30)
    sectors = {item.instrument_id: "A" if int(item.symbol[1:]) % 2 else "B" for item in instruments}
    second = service.run(snapshot=snapshot, instruments=instruments, coverage_by_instrument=coverage, source=source, sample_size=30, sectors=sectors,
                         frozen_cohort_instrument_ids=first.selected_instrument_ids, frozen_cohort_reference=first.trial_id)
    assert second.selected_instrument_ids == first.selected_instrument_ids
    assert second.selected_symbols == first.selected_symbols
    assert second.selection_method == "FROZEN_COHORT_FROM_PRIOR_REAL_BRAIN_TRIAL"
    assert second.frozen_cohort_reference == first.trial_id
    assert store.get_trial(second.trial_id) == second


def test_frozen_cohort_cannot_be_rebased_to_another_universe(tmp_path):
    instruments = _instruments(); snapshot = build_universe_snapshot(snapshot_id="universe-real", as_of=T, source="NSE_OFFICIAL_EXPORT", instruments=instruments)
    source = StoredEvidence(); service, _, _ = _service(tmp_path, source)
    coverage = {item.instrument_id: _coverage(item.instrument_id) for item in instruments}
    with pytest.raises(RealBrainTrialError, match="not fully present"):
        service.run(snapshot=snapshot, instruments=instruments, coverage_by_instrument=coverage, source=source, sample_size=30, frozen_cohort_instrument_ids=tuple(f"OTHER:{number}" for number in range(30)))


def test_same_cohort_comparison_reports_coverage_and_61_deltas_without_recalculation(tmp_path):
    instruments = _instruments(); snapshot = build_universe_snapshot(snapshot_id="universe-real", as_of=T, source="NSE_OFFICIAL_EXPORT", instruments=instruments)
    source = StoredEvidence(); service, store, _ = _service(tmp_path, source)
    before_coverage = {item.instrument_id: _coverage(item.instrument_id) for item in instruments}
    before = service.run(snapshot=snapshot, instruments=instruments, coverage_by_instrument=before_coverage, source=source, sample_size=30)
    selected = set(before.selected_instrument_ids)
    after_coverage = {item.instrument_id: _coverage(item.instrument_id, quote=DataCoverageStatus.READY if item.instrument_id in selected else DataCoverageStatus.MISSING) for item in instruments}
    after = service.run(snapshot=snapshot, instruments=instruments, coverage_by_instrument=after_coverage, source=source, sample_size=30, frozen_cohort_instrument_ids=before.selected_instrument_ids, frozen_cohort_reference=before.trial_id)
    report = store.compare(before_trial_id=before.trial_id, after_trial_id=after.trial_id)
    current_quotes = next(item for item in report.coverage if item.domain == "CURRENT_QUOTES")
    assert (report.cohort_size, current_quotes.before_ready, current_quotes.after_ready) == (30, 0, 30)
    assert report.before_diagnostic_evaluated == before.diagnostic_evaluated_total
    assert report.after_diagnostic_missing == after.diagnostic_missing_total


def test_stored_historical_bars_are_rehydrated_with_explicit_validation_for_existing_technical_engines(tmp_path):
    identity = InstrumentIdentity("NSE:ALPHA", Exchange.NSE, "ALPHA", "ALPHA", "INE000A01000", None, InstrumentType.NSE_EQUITY, "Alpha")
    store = SQLiteHistoricalBarStore(tmp_path / "history.sqlite")
    for offset in range(8):
        end = T - timedelta(days=8 - offset)
        store.upsert(CanonicalOHLCVBar(
            f"bar:{offset}", identity, Timeframe.DAILY, end - timedelta(days=1), end,
            Decimal("100"), Decimal("102"), Decimal("99"), Decimal("101"), 1000, None, None,
            AdjustmentStatus.RAW, MarketDataProvenance("fixture", "ALPHA", end, end, end, "test"), DataQuality.MEDIUM,
        ))
    source = StoredTrialObservationSource(historical=store, instrument_ids=(identity.instrument_id,), as_of=T)
    instrument = NseEquityInstrument(identity.instrument_id, "ALPHA", identity.isin, None, None, "ACTIVE", None, True, T, "fixture")
    evidence = StockDiagnosticInputAssembler(source).assemble(instrument, T)
    assert len(evidence.snapshot.observations) == 8
    assert all(item.validation is not None and item.validation.eligible_for_analysis for item in evidence.snapshot.observations)
    store.close()


def test_stored_trial_source_excludes_bars_retrieved_after_the_analysis_as_of(tmp_path):
    identity = InstrumentIdentity("NSE:ALPHA", Exchange.NSE, "ALPHA", "ALPHA", "INE000A01000", None, InstrumentType.NSE_EQUITY, "Alpha")
    store = SQLiteHistoricalBarStore(tmp_path / "history.sqlite")
    bar_end = T - timedelta(days=1)
    store.upsert(CanonicalOHLCVBar(
        "bar:later-retrieved", identity, Timeframe.DAILY, bar_end - timedelta(days=1), bar_end,
        Decimal("100"), Decimal("102"), Decimal("99"), Decimal("101"), 1000, None, None,
        AdjustmentStatus.RAW, MarketDataProvenance("fixture", "ALPHA", bar_end, bar_end, T, "test"), DataQuality.MEDIUM,
    ))
    old_source = StoredTrialObservationSource(historical=store, instrument_ids=(identity.instrument_id,), as_of=bar_end)
    current_source = StoredTrialObservationSource(historical=store, instrument_ids=(identity.instrument_id,), as_of=T)
    assert old_source.observations_as_of(bar_end) == ()
    assert len(current_source.observations_as_of(T)) == 1
    store.close()


def test_raw_trial_history_without_official_corporate_action_provenance_remains_partial(tmp_path):
    identity = InstrumentIdentity("NSE:ALPHA", Exchange.NSE, "ALPHA", "ALPHA", "INE000A01000", None, InstrumentType.NSE_EQUITY, "Alpha")
    end = T - timedelta(days=1)
    bar = CanonicalOHLCVBar(
        "bar:raw", identity, Timeframe.DAILY, end - timedelta(days=1), end,
        Decimal("100"), Decimal("102"), Decimal("99"), Decimal("101"), 1000, None, None,
        AdjustmentStatus.RAW, MarketDataProvenance("fixture", "ALPHA", end, end, end, "test"), DataQuality.MEDIUM,
    )
    integrity = _trial_price_integrity(instrument_id=identity.instrument_id, bars=(bar,), actions=(), as_of=T)
    assert integrity.status.value == "PARTIAL"
    assert "CORPORATE_ACTION_SOURCE_REQUIRED" in integrity.warnings
