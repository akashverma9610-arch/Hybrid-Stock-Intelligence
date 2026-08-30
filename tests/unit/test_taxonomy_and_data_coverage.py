from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from app.data_coverage.models import DataCoverageDomain, DataCoverageStatus, DeepAnalysisReadiness, DomainCoverage, StrategyCoverageReadiness
from app.data_coverage.service import DataCoverageService
from app.data_coverage.store import DataCoverageSnapshotStore
from app.storage.core_api_snapshot_repository import CoreApiSnapshotFamily
from app.storage.sqlite_core_api_snapshot_repository import SQLiteCoreApiSnapshotRepository
from app.taxonomy.models import ClassificationSourceStatus, InstrumentTaxonomyClassification, ThemeMembership
from app.taxonomy.service import TaxonomyCsvImporter, TaxonomySnapshotStore
from app.universe_analysis.models import NseEquityInstrument


UTC = timezone.utc
T = datetime(2026, 8, 24, tzinfo=UTC)


def _instrument(symbol="ALPHA", isin="INE000A01001"):
    return NseEquityInstrument(f"NSE:{symbol}", symbol, isin, None, None, "ACTIVE", None, True, T, "NSE_OFFICIAL_EXPORT")


def _classification(instrument="NSE:ALPHA", effective=T - timedelta(days=10)):
    return InstrumentTaxonomyClassification("taxonomy-1", instrument, "Cables", "Electrical Equipment", "Industrials", "Official taxonomy", ClassificationSourceStatus.OFFICIAL, effective, None, T - timedelta(days=1), 1.0, "taxonomy-v1")


def test_taxonomy_is_isin_first_historical_and_theme_is_not_sector(tmp_path: Path):
    repository = SQLiteCoreApiSnapshotRepository(tmp_path / "taxonomy.sqlite"); store = TaxonomySnapshotStore(repository)
    classification = _classification(); store.save_classification(classification)
    theme = ThemeMembership("theme-1", "NSE:ALPHA", "Power T&D", "Primary filing", ClassificationSourceStatus.PRIMARY_SOURCE_DERIVED, T - timedelta(days=5), None, T - timedelta(days=1), .8, "theme-v1", ("filing-1",))
    store.save_theme_membership(theme)
    assert store.classification_as_of("NSE:ALPHA", T) == classification
    assert store.classification_as_of("NSE:ALPHA", T - timedelta(days=20)) is None
    assert store.themes_as_of("NSE:ALPHA", T) == (theme,)
    assert classification.sector != theme.theme
    repository.close()
    reopened = TaxonomySnapshotStore(SQLiteCoreApiSnapshotRepository(tmp_path / "taxonomy.sqlite"))
    assert reopened.classification_as_of("NSE:ALPHA", T) == classification


def test_taxonomy_csv_mapping_is_exact_isin_then_safe_symbol_and_rejects_ambiguity(tmp_path: Path):
    repository = SQLiteCoreApiSnapshotRepository(tmp_path / "taxonomy.sqlite"); importer = TaxonomyCsvImporter(TaxonomySnapshotStore(repository))
    file = tmp_path / "taxonomy.csv"
    file.write_text("ISIN,SYMBOL,INDUSTRY,SECTOR,SUPER_SECTOR,SOURCE,SOURCE_TYPE,EFFECTIVE_FROM\nINE000A01001,WRONG,Cables,Electrical Equipment,Industrials,Official,OFFICIAL,2026-08-01T00:00:00+00:00\n,SAFE,Software,IT,Services,Review,MANUALLY_REVIEWED,2026-08-01T00:00:00+00:00\n,AMB,Unknown,Unknown,Unknown,Review,UNKNOWN,2026-08-01T00:00:00+00:00\n", encoding="utf-8")
    alpha = _instrument(); safe = _instrument("SAFE", "INE000A01002"); amb_a = _instrument("AMB", "INE000A01003"); amb_b = NseEquityInstrument("NSE:AMB-2", "AMB", "INE000A01004", None, None, "ACTIVE", None, True, T, "NSE")
    report = importer.import_csv(file, instruments=(alpha, safe, amb_a, amb_b), as_of=T, dry_run=False)
    assert (report.accepted, report.unresolved, report.ambiguous) == (2, 0, 1)
    store = TaxonomySnapshotStore(repository)
    assert store.classification_as_of(alpha.instrument_id, T).industry == "Cables"  # exact ISIN beats wrong symbol
    assert store.classification_as_of(safe.instrument_id, T).sector == "IT"
    assert store.classification_as_of(amb_a.instrument_id, T) is None


def test_missing_taxonomy_stays_unknown_and_duplicate_snapshot_does_not_overwrite(tmp_path: Path):
    repository = SQLiteCoreApiSnapshotRepository(tmp_path / "taxonomy.sqlite"); store = TaxonomySnapshotStore(repository)
    assert store.classification_as_of("NSE:MISSING", T) is None
    value = _classification(); store.save_classification(value)
    with pytest.raises(ValueError, match="immutable"):
        store.save_classification(value)
    source = Path(__file__).resolve().parents[2] / "app" / "taxonomy"
    assert "openai" not in "\n".join(path.read_text(encoding="utf-8").lower() for path in source.rglob("*.py"))


def _domains(**overrides):
    statuses = {domain: DataCoverageStatus.MISSING for domain in DataCoverageDomain}; statuses.update(overrides)
    return tuple(DomainCoverage(domain, status, T if status is not DataCoverageStatus.MISSING else None) for domain, status in statuses.items())


def test_coverage_keeps_missing_data_missing_and_derives_strategy_readiness():
    service = DataCoverageService()
    full = service.record(universe_snapshot_id="u", instrument_id="NSE:FULL", as_of=T, domains=_domains(**{domain: DataCoverageStatus.READY for domain in DataCoverageDomain}))
    assert full.deep_analysis is DeepAnalysisReadiness.DEEP_ANALYSIS_READY
    assert full.pre_breakout is StrategyCoverageReadiness.READY and full.inflection is StrategyCoverageReadiness.READY
    partial = service.record(universe_snapshot_id="u", instrument_id="NSE:PART", as_of=T, domains=_domains(DELIVERY_DATA=DataCoverageStatus.UNAVAILABLE, OWNERSHIP=DataCoverageStatus.PARTIAL, CURRENT_QUOTES=DataCoverageStatus.STALE))
    assert next(item for item in partial.domains if item.domain is DataCoverageDomain.DELIVERY_DATA).status is DataCoverageStatus.UNAVAILABLE
    assert partial.pre_breakout is StrategyCoverageReadiness.PARTIAL
    assert partial.inflection is StrategyCoverageReadiness.PARTIAL
    absent = service.record(universe_snapshot_id="u", instrument_id="NSE:EMPTY", as_of=T, domains=())
    assert absent.deep_analysis is DeepAnalysisReadiness.DEEP_ANALYSIS_UNAVAILABLE
    assert absent.pre_breakout is StrategyCoverageReadiness.UNAVAILABLE


def test_coverage_summary_counts_conflict_stale_gaps_and_no_investment_rank():
    service = DataCoverageService()
    a = service.record(universe_snapshot_id="u", instrument_id="A", as_of=T, domains=_domains(IDENTITY=DataCoverageStatus.READY, DELIVERY_DATA=DataCoverageStatus.UNAVAILABLE))
    b = service.record(universe_snapshot_id="u", instrument_id="B", as_of=T, domains=_domains(IDENTITY=DataCoverageStatus.READY, CURRENT_QUOTES=DataCoverageStatus.STALE, HISTORICAL_OHLCV=DataCoverageStatus.CONFLICTED))
    summary = service.summarize(universe_snapshot_id="u", as_of=T, records=(a, b))
    quote = next(item for item in summary.domains if item.domain is DataCoverageDomain.CURRENT_QUOTES)
    history = next(item for item in summary.domains if item.domain is DataCoverageDomain.HISTORICAL_OHLCV)
    assert quote.stale == 1 and history.conflicted == 1
    delivery_gap = next(item for item in summary.gaps if item.domain is DataCoverageDomain.DELIVERY_DATA)
    assert delivery_gap.downstream_engines_blocked == ("PRE_BREAKOUT", "VOLUME_QUALITY_DIAGNOSTICS")
    assert "TAXONOMY_SOURCE_REQUIRED" in summary.warnings


def test_coverage_snapshot_families_are_append_only_and_separate_from_legacy_coverage():
    assert CoreApiSnapshotFamily.TAXONOMY_CLASSIFICATION.value == "TAXONOMY_CLASSIFICATION"
    assert CoreApiSnapshotFamily.THEME_MEMBERSHIP.value == "THEME_MEMBERSHIP"
    assert CoreApiSnapshotFamily.DATA_COVERAGE_RECORD.value == "DATA_COVERAGE_RECORD"
    assert CoreApiSnapshotFamily.DATA_COVERAGE_SUMMARY.value == "DATA_COVERAGE_SUMMARY"


def test_coverage_record_and_summary_round_trip_immutably(tmp_path: Path):
    repository = SQLiteCoreApiSnapshotRepository(tmp_path / "coverage.sqlite"); service = DataCoverageService(); store = DataCoverageSnapshotStore(repository)
    record = service.record(universe_snapshot_id="u", instrument_id="NSE:ABC", as_of=T, domains=_domains(IDENTITY=DataCoverageStatus.READY))
    summary = service.summarize(universe_snapshot_id="u", as_of=T, records=(record,))
    store.save_record(record); store.save_summary(summary)
    assert store.get_record(record.coverage_id) == record
    assert store.get_summary(summary.summary_id) == summary
    with pytest.raises(ValueError, match="immutable"):
        store.save_record(record)
