from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.data_operations.models import DataOperationsFamilyHealth, DataOperationsHealthStatus, EvidenceDataFamily, EvidenceRefreshWatermark
from app.data_operations.upstox import MINIMUM_REQUIRED_DAILY_SESSIONS
from app.domain.models import DataQuality
from app.forward_paper.composition import StoredExecutableSetup, StoredExecutableSetupStore
from app.market_data.historical import SQLiteHistoricalBarStore
from app.market_data.models import AdjustmentStatus, CanonicalOHLCVBar, Exchange, InstrumentIdentity, InstrumentType, MarketDataProvenance, Timeframe
from app.market_data.upstox import UPSTOX_PROVIDER
from app.market_data.upstox_sector_indices import NIFTY_500_INDEX_ID
from app.production_v1.governed_setup_source import GovernedExecutableSetupSourceState
from app.production_v1.local import (
    _index_bars_consumer_readiness,
    _nifty500_benchmark_readiness,
    _paper_bar_composition_readiness,
    _paper_setup_composition_readiness,
)
from app.production_v1.sector_universe_coverage import assess_sector_universe_coverage
from types import SimpleNamespace
from app.production_v1.models import ProductionComponent, ProductionComponentHealth, ProductionReadinessState, ProductionSourceHealth, ProductionSourceStatus, ProductionV1FinalStatus
from app.production_v1.service import ProductionV1Cycle, build_readiness_report
from app.storage.sqlite_core_api_snapshot_repository import SQLiteCoreApiSnapshotRepository

T = datetime(2026, 8, 29, tzinfo=UTC)


def components(state=ProductionReadinessState.READY):
    return tuple(ProductionComponentHealth(item, state) for item in ProductionComponent)


def sources(status=ProductionSourceStatus.OPERATIONAL):
    families = (ProductionComponent.OHLCV, ProductionComponent.INDEX_BARS, ProductionComponent.DELIVERY, ProductionComponent.MEMBERSHIP, ProductionComponent.TAXONOMY, ProductionComponent.CORPORATE_ACTIONS, ProductionComponent.FINANCIALS, ProductionComponent.SHAREHOLDING, ProductionComponent.MACRO, ProductionComponent.NEWS)
    return tuple(ProductionSourceHealth(item, "approved", "adapter", status, "complete") for item in families)


def test_readiness_is_not_ready_for_any_missing_p0_and_ready_only_with_full_proof():
    blocked = build_readiness_report(generated_at=T, components=components(), sources=sources(ProductionSourceStatus.BLOCKED_CONFIGURATION))
    assert blocked.final_status is ProductionV1FinalStatus.PRODUCTION_V1_NOT_READY and blocked.p0_blockers
    ready = build_readiness_report(generated_at=T, components=components(), sources=sources())
    assert ready.final_status is ProductionV1FinalStatus.PRODUCTION_V1_READY and not ready.p0_blockers


def test_cycle_refreshes_and_reconciles_before_brain_setup_and_paper():
    seen=[]; report=build_readiness_report(generated_at=T, components=components(), sources=sources())
    cycle=ProductionV1Cycle(refresh=lambda at: seen.append("refresh"), reconcile=lambda at: seen.append("reconcile"), readiness=lambda at: report, brain=lambda at: seen.append("brain"), setup=lambda at: seen.append("setup"), paper=lambda at: seen.append("paper"), clock=lambda:T)
    _, stages, result=cycle.run_once()
    assert stages == ("REFRESH", "RECONCILE", "READINESS", "SHARED_BRAIN", "SETUP", "PAPER")
    assert seen == ["refresh", "reconcile", "brain", "setup", "paper"] and result is report


def test_cycle_blocks_before_brain_or_paper_when_readiness_is_not_ready():
    seen=[]; report=build_readiness_report(generated_at=T, components=components(), sources=sources(ProductionSourceStatus.BLOCKED_CONFIGURATION))
    cycle=ProductionV1Cycle(refresh=lambda at: seen.append("refresh"), reconcile=lambda at: seen.append("reconcile"), readiness=lambda at: report, brain=lambda at: seen.append("brain"), setup=lambda at: seen.append("setup"), paper=lambda at: seen.append("paper"), clock=lambda:T)
    _, stages, _=cycle.run_once()
    assert stages == ("REFRESH", "RECONCILE", "READINESS") and seen == ["refresh", "reconcile"]


def test_stored_executable_setup_is_immutable_durable_and_converts_to_paper_admission(tmp_path):
    path=tmp_path / "production.sqlite"; repo=SQLiteCoreApiSnapshotRepository(path); store=StoredExecutableSetupStore(repo)
    item=StoredExecutableSetup.create(setup_id="setup:1", canonical_instrument_id="stock:1", setup_fingerprint="setup-fp", source_candidate_fingerprint="candidate-fp", strategy_version="v1", policy_fingerprint="policy-fp", decision_as_of=T, trigger=Decimal("100"), structural_stop=Decimal("95"), target=Decimal("115"), maximum_entry=Decimal("103"), time_stop_sessions=10)
    assert store.save(item) and not store.save(item); assert store.list(as_of=T)[0].admission().trigger == Decimal("100")
    repo.close(); reopened=SQLiteCoreApiSnapshotRepository(path)
    assert StoredExecutableSetupStore(reopened).list(as_of=T) == (item,)


def test_u18_composition_capabilities_are_ready_without_manufacturing_a_current_setup():
    run = SimpleNamespace(state=GovernedExecutableSetupSourceState.READY_NO_CURRENT_SETUP)

    assert _paper_setup_composition_readiness(run, ()) == (
        ProductionReadinessState.READY, "PAPER_SETUP_COMPOSITION_OPERATIONAL_NO_CURRENT_SETUP",
    )
    assert _paper_bar_composition_readiness(run, ()) == (
        ProductionReadinessState.READY, "PAPER_BAR_COMPOSITION_OPERATIONAL_NO_CURRENT_SETUP",
    )


def test_u18_composition_fails_closed_when_governed_output_claims_a_setup_but_persists_none():
    run = SimpleNamespace(state=GovernedExecutableSetupSourceState.READY_WITH_EXECUTABLE_SETUP)

    assert _paper_setup_composition_readiness(run, ())[0] is ProductionReadinessState.BLOCKED
    assert _paper_bar_composition_readiness(run, ())[0] is ProductionReadinessState.BLOCKED


def test_source_blocker_is_explicit_not_hidden_as_healthy():
    report=build_readiness_report(generated_at=T, components=components(), sources=sources(ProductionSourceStatus.BLOCKED_MISSING_APPROVED_SOURCE))
    assert any("OHLCV" in item for item in report.p0_blockers)


def _nifty500_history(tmp_path, *, count=MINIMUM_REQUIRED_DAILY_SESSIONS):
    store = SQLiteHistoricalBarStore(tmp_path / "nifty500.sqlite")
    identity = InstrumentIdentity(NIFTY_500_INDEX_ID, Exchange.INDEX, "NIFTY 500", "NIFTY 500", None, None, InstrumentType.BROAD_INDEX, "NIFTY 500")
    start = T - timedelta(days=count)
    for index in range(count):
        end = start + timedelta(days=index + 1)
        store.upsert(CanonicalOHLCVBar(
            f"upstox:nifty500:{index}", identity, Timeframe.DAILY, end - timedelta(days=1), end,
            Decimal("100"), Decimal("101"), Decimal("99"), Decimal("100"), None, None, None,
            AdjustmentStatus.UNKNOWN, MarketDataProvenance(UPSTOX_PROVIDER, "NSE_INDEX|Nifty 500", end, end, T,
            "upstox-history-v3"), DataQuality.HIGH,
        ))
    return store


def _index_health(*, status=DataOperationsHealthStatus.DEGRADED, next_due_at=T + timedelta(days=1), reasons=("PARTIAL",)):
    return DataOperationsFamilyHealth(EvidenceDataFamily.INDEX_BARS, status, None, next_due_at, reasons)


def _index_watermark():
    return EvidenceRefreshWatermark(
        "watermark:index", EvidenceDataFamily.INDEX_BARS, UPSTOX_PROVIDER, "DEFAULT", T, T + timedelta(seconds=1), "run:index", "source", True,
    )


def test_nifty500_benchmark_is_ready_with_sufficient_current_upstox_bars_despite_partial_sector_family(tmp_path):
    store = _nifty500_history(tmp_path)
    assert _nifty500_benchmark_readiness(store, watermark=_index_watermark(), index_health=_index_health(), now=T) == (ProductionReadinessState.READY, None)


def test_nifty500_benchmark_blocks_when_its_own_history_is_insufficient(tmp_path):
    store = _nifty500_history(tmp_path, count=MINIMUM_REQUIRED_DAILY_SESSIONS - 1)
    state, reason = _nifty500_benchmark_readiness(store, watermark=_index_watermark(), index_health=_index_health(), now=T)
    assert state is ProductionReadinessState.BLOCKED and reason == "NIFTY500_HISTORICAL_COVERAGE_INSUFFICIENT"


def test_nifty500_benchmark_is_not_reported_fresh_when_index_refresh_is_overdue(tmp_path):
    store = _nifty500_history(tmp_path)
    state, reason = _nifty500_benchmark_readiness(
        store, watermark=_index_watermark(), index_health=_index_health(next_due_at=T - timedelta(seconds=1), reasons=("PARTIAL", "REFRESH_OVERDUE")), now=T,
    )
    assert state is ProductionReadinessState.DEGRADED and reason == "NIFTY500_INDEX_BARS_REFRESH_OVERDUE"


def _partial_sector_coverage(*, ready_count=3):
    ready = tuple(f"Sector-{value}" for value in range(ready_count))
    items = tuple(
        SimpleNamespace(sector=value, official_index=f"Nifty {value}", rs20=Decimal("1"), rs60=Decimal("1"),
                        rs120=Decimal("1"), exclusion_reason=None)
        for value in ready
    ) + (SimpleNamespace(sector="Unavailable", official_index="Nifty Unavailable", rs20=None, rs60=None,
                         rs120=None, exclusion_reason="INSUFFICIENT_ALIGNED_120_SESSION_HISTORY"),)
    return assess_sector_universe_coverage(SimpleNamespace(
        generated_at=T, relative_strength=items,
        breadth=tuple(SimpleNamespace(sector=item.sector, status="READY") for item in items),
        ranked_sectors=ready, top3=ready[:3],
    ))


def test_partial_index_family_can_be_consumer_ready_with_explicit_sector_limitations() -> None:
    source = ProductionSourceHealth(ProductionComponent.INDEX_BARS, "upstox", "adapter",
                                    ProductionSourceStatus.OPERATIONAL_WITH_LIMITATION, "current", "PARTIAL")
    state, reason = _index_bars_consumer_readiness(
        source, _partial_sector_coverage(), benchmark_state=ProductionReadinessState.READY, benchmark_reason=None,
    )
    assert state is ProductionReadinessState.DEGRADED
    assert "PARTIAL" in reason and "EXCLUDED_SECTORS=Unavailable:Nifty Unavailable:INSUFFICIENT_ALIGNED_120_SESSION_HISTORY" in reason


def test_partial_index_family_remains_blocked_when_fewer_than_top3_sectors_have_evidence() -> None:
    source = ProductionSourceHealth(ProductionComponent.INDEX_BARS, "upstox", "adapter",
                                    ProductionSourceStatus.OPERATIONAL_WITH_LIMITATION, "current", "PARTIAL")
    state, reason = _index_bars_consumer_readiness(
        source, _partial_sector_coverage(ready_count=2), benchmark_state=ProductionReadinessState.READY, benchmark_reason=None,
    )
    assert state is ProductionReadinessState.BLOCKED
    assert "SECTOR_UNIVERSE_TOP3_EVIDENCE_INSUFFICIENT" in reason
