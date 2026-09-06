from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from app.domain.models import DataQuality
from app.historical.nse_capital_market_session_evidence_2022_2026 import nse_capital_market_calendar_2022_2026
from app.historical.security_identity_selector import resolve_historical_security_identity
from app.historical.security_master import HistoricalSecurityIdentity, HistoricalSecurityStatus
from app.market_data.historical import HistoricalBarConflictArtifact
from app.market_data.models import (
    AdjustmentStatus,
    CanonicalOHLCVBar,
    Exchange,
    InstrumentIdentity,
    InstrumentType,
    MarketDataProvenance,
    Timeframe,
)
from app.market_data.nse_udiff_daily_history import NseUdiffDailyStatus, _receipt
from app.market_data.nse_udiff_daily_integrity import (
    NseUdiffConflictCause,
    NseUdiffConflictState,
    NseUdiffDivergenceClassification,
    NseUdiffDailyIntegrityStore,
    NseUdiffDailySourceSelectionState,
    NseUdiffSessionCoverageState,
    NseUdiffSourceGapClassification,
    audit_udiff_same_provider_conflicts,
    audit_udiff_upstox_divergence,
    build_udiff_session_coverage_manifest,
    select_eligible_udiff_daily_bar,
)


T = datetime(2026, 9, 6, 12, tzinfo=UTC)
ACQUISITION = "nse-udiff-acquisition:fixture"
INSTRUMENT = InstrumentIdentity("NSE:INE000A01001", Exchange.NSE, "ALPHA", "ALPHA", "INE000A01001", "EQ", InstrumentType.NSE_EQUITY, "Alpha", "INR")


def receipt(day: date, status: NseUdiffDailyStatus, *, artifact_id: str | None = None):
    return _receipt(
        acquisition_id=ACQUISITION,
        trade_date=day,
        status=status,
        observed_at=T,
        artifact_id=artifact_id,
        source_url=f"https://nsearchives.nseindia.com/content/cm/{day:%Y%m%d}.zip",
        rows_seen=0,
        eligible_rows=0,
        exact_identity_rows=0,
        identity_discontinuities=0,
        unresolved_identity_rows=0,
        invalid_rows=0,
        zero_volume_rows=0,
        inserted=0,
        duplicates=0,
        conflicts=0,
        error_code=None if status is NseUdiffDailyStatus.ARTIFACT_VALID else "NSE_UDIFF_ARTIFACT_UNAVAILABLE",
    )


def bar(*, provider: str, start: datetime, close: str = "102", open_: str = "100", high: str = "105", low: str = "99", volume: int = 1000, reference: str = "NSE:CM:1") -> CanonicalOHLCVBar:
    return CanonicalOHLCVBar(
        f"{provider}-{start.isoformat()}-{reference}", INSTRUMENT, Timeframe.DAILY, start, start + timedelta(days=1),
        Decimal(open_), Decimal(high), Decimal(low), Decimal(close), volume, Decimal("102000"), 50,
        AdjustmentStatus.RAW,
        MarketDataProvenance(provider, reference, start, None, T, "nse-udiff-final-bhavcopy-v1", "fixture", "https://nsearchives.nseindia.com/content/cm/fixture.zip"),
        DataQuality.HIGH,
    )


def saved_legacy_conflict(stored, incoming):
    """Pre-series artifact fixture: new writes must not create coarse conflicts.

    Keep testing the old audit/selection behavior for retained historical
    artifacts with absent source-observation identity, not new creation.
    """
    from app.market_data.historical import (
        HistoricalBarNormalizedValues, HistoricalBarLineage,
        _normalized_bar_fingerprint, _historical_conflict_fingerprint,
        _conflict_differing_fields,
    )
    def lineage(b):
        p = b.provenance
        return HistoricalBarLineage(p.provider.lower(), p.schema_version or None, None,
                                    p.normalization_version, p.source_reference,
                                    p.provider_instrument_reference)
    left, right = HistoricalBarNormalizedValues.from_bar(stored), HistoricalBarNormalizedValues.from_bar(incoming)
    values = dict(canonical_instrument_id=stored.instrument.instrument_id, timeframe=stored.timeframe,
                  start_time=stored.start_time, end_time=stored.end_time,
                  stored_bar_fingerprint=_normalized_bar_fingerprint(stored), incoming_bar_fingerprint=_normalized_bar_fingerprint(incoming),
                  differing_fields=_conflict_differing_fields(left, right),
                  stored_lineage=lineage(stored), incoming_lineage=lineage(incoming))
    return HistoricalBarConflictArtifact(**values, conflict_fingerprint=_historical_conflict_fingerprint(**values),
                                         stored_values=left, incoming_values=right, detected_at=T, ingestion_run_id=ACQUISITION)


def test_date_specific_nse_election_amendments_close_all_source_unavailable_dates():
    dates = (
        date(2024, 11, 20),
        date(2026, 1, 15),
        date(2025, 8, 15),
    )
    manifest = build_udiff_session_coverage_manifest(
        acquisition_id=ACQUISITION,
        requested_dates=dates,
        receipts=tuple(receipt(day, NseUdiffDailyStatus.SOURCE_UNAVAILABLE) for day in dates),
        calendar=nse_capital_market_calendar_2022_2026(),
        as_of=T,
    )
    assert all(item.state is NseUdiffSessionCoverageState.CONFIRMED_NON_TRADING_DAY for item in manifest.entries)
    assert all(item.source_gap is NseUdiffSourceGapClassification.CONFIRMED_EXCHANGE_HOLIDAY for item in manifest.entries)
    assert {source for item in manifest.entries if item.trade_date in {date(2024, 11, 20), date(2026, 1, 15)} for source in item.source_ids} >= {
        "nse-cmtr-64960-2024-maharashtra-election",
        "nse-cmtr-72260-2026-maharashtra-election",
    }


def test_valid_artifact_is_a_session_fact_and_missing_artifact_is_not_a_holiday():
    artifact_day = date(2024, 7, 8)
    unresolved_day = date(2024, 11, 21)
    manifest = build_udiff_session_coverage_manifest(
        acquisition_id=ACQUISITION,
        requested_dates=(artifact_day, unresolved_day),
        receipts=(receipt(artifact_day, NseUdiffDailyStatus.ARTIFACT_VALID, artifact_id="nse-udiff-artifact:fixture"),),
        calendar=nse_capital_market_calendar_2022_2026(),
        as_of=T,
        artifact_session_ids={artifact_day: ("F1",)},
    )
    valid, missing = manifest.entries
    assert valid.state is NseUdiffSessionCoverageState.ARTIFACT_VALID_SESSION
    assert valid.source_gap is None and valid.artifact_id == "nse-udiff-artifact:fixture"
    assert valid.session_ids == ("F1",)
    assert missing.state is NseUdiffSessionCoverageState.HISTORICAL_SESSION_UNRESOLVED
    assert missing.source_gap is NseUdiffSourceGapClassification.HISTORICAL_SESSION_UNRESOLVED


def test_same_source_different_provider_reference_is_an_unresolved_ingestion_key_collision():
    start = datetime(2024, 7, 7, 18, 30, tzinfo=UTC)
    stored = bar(provider="NSE_UDIFF_OFFICIAL", start=start, reference="NSE:CM:101")
    incoming = bar(provider="NSE_UDIFF_OFFICIAL", start=start, close="103", reference="NSE:CM:202")
    artifact = saved_legacy_conflict(stored, incoming)
    assessment = audit_udiff_same_provider_conflicts((artifact,))[0]
    assert assessment.state is NseUdiffConflictState.CONFLICT_UNRESOLVED
    assert assessment.cause is NseUdiffConflictCause.INGESTION_KEY_COLLISION
    assert assessment.fingerprint.startswith("sha256:")


def test_divergence_audit_is_deterministic_and_does_not_promote_upstox():
    start = datetime(2024, 7, 7, 18, 30, tzinfo=UTC)
    audit = audit_udiff_upstox_divergence(
        canonical_instrument_id=INSTRUMENT.instrument_id,
        udiff_bars=(bar(provider="NSE_UDIFF_OFFICIAL", start=start, close="200", open_="196", high="210", low="190"),),
        upstox_bars=(bar(provider="UPSTOX", start=start, close="100", open_="98", high="105", low="95"),),
    )
    assert audit.classification is NseUdiffDivergenceClassification.CONSTANT_MULTIPLICATIVE_RATIO
    assert audit.close_ratio == Decimal("2")
    assert audit.fingerprint.startswith("sha256:")


def test_divergence_reports_volume_only_mismatch_without_merging_candles():
    start = datetime(2024, 7, 7, 18, 30, tzinfo=UTC)
    audit = audit_udiff_upstox_divergence(
        canonical_instrument_id=INSTRUMENT.instrument_id,
        udiff_bars=(bar(provider="NSE_UDIFF_OFFICIAL", start=start, volume=1000),),
        upstox_bars=(bar(provider="UPSTOX", start=start, volume=999),),
    )
    assert audit.classification is NseUdiffDivergenceClassification.VOLUME_ONLY_MISMATCH
    assert audit.near_ohlc_count == 1 and audit.near_ohlc_exact_volume_count == 0


def test_divergence_detects_date_shift_and_field_mapping_without_repairing_bars():
    start = datetime(2024, 7, 7, 18, 30, tzinfo=UTC)
    shifted = audit_udiff_upstox_divergence(
        canonical_instrument_id=INSTRUMENT.instrument_id,
        udiff_bars=(
            bar(provider="NSE_UDIFF_OFFICIAL", start=start, close="100", high="105"),
            bar(provider="NSE_UDIFF_OFFICIAL", start=start + timedelta(days=1), close="110", high="115"),
            bar(provider="NSE_UDIFF_OFFICIAL", start=start + timedelta(days=2), close="120", high="125"),
        ),
        upstox_bars=(
            bar(provider="UPSTOX", start=start, close="110", high="115"),
            bar(provider="UPSTOX", start=start + timedelta(days=1), close="120", high="125"),
            bar(provider="UPSTOX", start=start + timedelta(days=2), close="130", high="135"),
        ),
    )
    assert shifted.classification is NseUdiffDivergenceClassification.ONE_SESSION_DATE_SHIFT_SUSPECTED

    mapped = audit_udiff_upstox_divergence(
        canonical_instrument_id=INSTRUMENT.instrument_id,
        udiff_bars=(
            bar(provider="NSE_UDIFF_OFFICIAL", start=start, close="100", high="105"),
            bar(provider="NSE_UDIFF_OFFICIAL", start=start + timedelta(days=1), close="110", high="115"),
        ),
        upstox_bars=(
            bar(provider="UPSTOX", start=start, open_="100", high="105", low="20", close="30"),
            bar(provider="UPSTOX", start=start + timedelta(days=1), open_="110", high="115", low="50", close="60"),
        ),
    )
    assert mapped.classification is NseUdiffDivergenceClassification.FIELD_MAPPING_SUSPECTED


def test_selection_uses_nse_session_date_and_never_falls_back_to_another_provider():
    start = datetime(2024, 7, 7, 18, 30, tzinfo=UTC)  # 2024-07-08 in NSE time.
    udiff = bar(provider="NSE_UDIFF_OFFICIAL", start=start)
    day = date(2024, 7, 8)
    manifest = build_udiff_session_coverage_manifest(
        acquisition_id=ACQUISITION,
        requested_dates=(day,),
        receipts=(receipt(day, NseUdiffDailyStatus.ARTIFACT_VALID, artifact_id="nse-udiff-artifact:fixture"),),
        calendar=nse_capital_market_calendar_2022_2026(),
        as_of=T,
    )
    identity = HistoricalSecurityIdentity(
        "alpha-2024", INSTRUMENT.instrument_id, INSTRUMENT.isin, "NSE", "ALPHA", "EQ",
        start, None, start, None, start, None, HistoricalSecurityStatus.ACTIVE,
        "NSE_OFFICIAL", start, "v1", "primary://alpha",
    )
    resolved = resolve_historical_security_identity(
        (identity,), canonical_instrument_id=INSTRUMENT.instrument_id, as_of=udiff.end_time,
    )
    selected = select_eligible_udiff_daily_bar(
        bar=udiff, coverage=manifest, identity=resolved, conflicts=(),
    )
    assert selected.trade_date == day
    assert selected.state is NseUdiffDailySourceSelectionState.SERIES_SELECTION_NOT_ACTIVE
    assert selected.selected_provider is None
    assert selected.reason == "NSE_UDIFF_TECHNICAL_SERIES_SELECTION_NOT_ACTIVE"

    mismatch = resolve_historical_security_identity(
        (identity,), canonical_instrument_id=INSTRUMENT.instrument_id, as_of=udiff.end_time + timedelta(seconds=1),
    )
    unavailable = select_eligible_udiff_daily_bar(
        bar=udiff, coverage=manifest, identity=mismatch, conflicts=(),
    )
    assert unavailable.state is NseUdiffDailySourceSelectionState.HISTORICAL_IDENTITY_UNRESOLVED
    assert unavailable.selected_provider is None
    assert unavailable.reason == "NSE_UDIFF_IDENTITY_PIT_CUTOFF_REQUIRED"


def test_selection_fails_closed_for_a_same_provider_conflict_without_fallback():
    start = datetime(2024, 7, 7, 18, 30, tzinfo=UTC)
    udiff = bar(provider="NSE_UDIFF_OFFICIAL", start=start, reference="NSE:CM:101")
    day = date(2024, 7, 8)
    manifest = build_udiff_session_coverage_manifest(
        acquisition_id=ACQUISITION,
        requested_dates=(day,),
        receipts=(receipt(day, NseUdiffDailyStatus.ARTIFACT_VALID, artifact_id="nse-udiff-artifact:fixture"),),
        calendar=nse_capital_market_calendar_2022_2026(),
        as_of=T,
    )
    identity = HistoricalSecurityIdentity(
        "alpha-2024", INSTRUMENT.instrument_id, INSTRUMENT.isin, "NSE", "ALPHA", "EQ",
        start, None, start, None, start, None, HistoricalSecurityStatus.ACTIVE,
        "NSE_OFFICIAL", start, "v1", "primary://alpha",
    )
    resolved = resolve_historical_security_identity(
        (identity,), canonical_instrument_id=INSTRUMENT.instrument_id, as_of=udiff.end_time,
    )
    conflict = saved_legacy_conflict(
        udiff, bar(provider="NSE_UDIFF_OFFICIAL", start=start, close="103", reference="NSE:CM:202"),
    )
    result = select_eligible_udiff_daily_bar(
        bar=udiff, coverage=manifest, identity=resolved,
        conflicts=audit_udiff_same_provider_conflicts((conflict,)),
    )
    assert result.state is NseUdiffDailySourceSelectionState.CONFLICT_UNRESOLVED
    assert result.selected_provider is None
    assert result.reason == "NSE_UDIFF_SAME_PROVIDER_CONFLICT"


def test_selection_rejects_pre_udiff_era_without_promoting_another_source():
    old = bar(provider="NSE_UDIFF_OFFICIAL", start=datetime(2024, 7, 5, 18, 30, tzinfo=UTC))
    manifest = build_udiff_session_coverage_manifest(
        acquisition_id=ACQUISITION,
        requested_dates=(date(2024, 7, 5),), receipts=(),
        calendar=nse_capital_market_calendar_2022_2026(), as_of=T,
    )
    unresolved = resolve_historical_security_identity(
        (), canonical_instrument_id=INSTRUMENT.instrument_id, as_of=old.end_time,
    )
    result = select_eligible_udiff_daily_bar(bar=old, coverage=manifest, identity=unresolved, conflicts=())
    assert result.state is NseUdiffDailySourceSelectionState.OUT_OF_ERA
    assert result.selected_provider is None


def test_coverage_contract_revision_does_not_change_the_established_snapshot_envelope():
    day = date(2024, 7, 8)
    manifest = build_udiff_session_coverage_manifest(
        acquisition_id=ACQUISITION, requested_dates=(day,),
        receipts=(receipt(day, NseUdiffDailyStatus.ARTIFACT_VALID, artifact_id="nse-udiff-artifact:fixture"),),
        calendar=nse_capital_market_calendar_2022_2026(), as_of=T,
        artifact_session_ids={day: ("F1",)},
    )

    class Repository:
        def __init__(self): self.saved = []
        def get_snapshot(self, _): return None
        def save_snapshot(self, value): self.saved.append(value)

    repository = Repository()
    assert NseUdiffDailyIntegrityStore(repository).save_session_coverage(manifest) is True
    assert repository.saved[0].schema_version == "v1"
    assert repository.saved[0].payload.contract_version == "v2"


def test_integrity_module_has_no_forbidden_runtime_or_execution_dependencies():
    source = Path(__file__).parents[2] / "app" / "market_data" / "nse_udiff_daily_integrity.py"
    text = source.read_text(encoding="utf-8")
    for forbidden in ("app.signals", "app.portfolio", "app.broker", "app.orders", "app.api", "datetime.now", "requests."):
        assert forbidden not in text
