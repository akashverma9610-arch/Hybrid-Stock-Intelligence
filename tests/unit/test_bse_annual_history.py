from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
import ast

import pytest

from app.fundamentals.bse_annual_history import select_missing_annual_history
from app.universe_analysis.models import ProviderInstrumentMappingRecord, ProviderMappingStatus
from app.fundamentals.bse_official import BseResultMetadata, BseResultMetadataAliases, BseTimestampStatus, parse_bse_xbrl
from app.fundamentals.diagnostic_comparability import canonical_json
from app.fundamentals.models import FinancialMetric as M, FinancialPeriodType as P, FinancialValueBasis as B, StatementScope as S
from tests.unit.test_financial_diagnostic_comparability import T, ID, INSTRUMENT, comparable, fact, inputs
from tests.unit.test_bse_official_financial_results import _xbrl


def mapping():
    return ProviderInstrumentMappingRecord("mapping:fixture", ID, "BSE_OFFICIAL", "BSE_EQ", "532259",
        None, INSTRUMENT.isin, ProviderMappingStatus.ACTIVE, T,
        "https://www.bseindia.com/XBRLFILES/exact.xml", "a" * 64, "bse-xbrl-v1")


def metadata(year=2021, **changes):
    value = BseResultMetadata("532259", f"{year-1}-{year}", f"Consolidated-Mar-{str(year)[2:]}",
        "Year", "NEW", datetime(year, 5, 1, tzinfo=UTC), None, None, S.CONSOLIDATED,
        datetime(year, 3, 31, tzinfo=UTC), P.ANNUAL, B.FULL_YEAR,
        f"https://www.bseindia.com/XBRLFILES/FourOneUploadDocument/annual-{year}.xml",
        "https://api.bseindia.com/BseIndiaAPI/api/Result_Arch_Download/w?scrip_cd=532259", BseTimestampStatus.DOCUMENTED)
    return replace(value, **changes)


def aliases(*values):
    return tuple(BseResultMetadataAliases(v.xbrl_url, (v,), v) for v in values)


def select(*values, years=range(2022, 2027), mapped=None):
    return select_missing_annual_history(comparable(tuple(fact(year=y) for y in years)),
                                       mapped or mapping(), aliases(*values))


def test_only_missing_sixth_endpoint_is_selected_and_no_positive_rule16():
    result = select(metadata(), metadata(2020))
    assert result.requested_endpoints == (datetime(2021, 3, 31, tzinfo=UTC),)
    assert result.selected == (metadata(),)
    assert result.unavailable == ()
    assert inputs(tuple(fact(year=y) for y in range(2021, 2027))).rule_input(16).state.value != "READY"
    with pytest.raises(FrozenInstanceError):
        result.scope = S.STANDALONE


def test_four_endpoints_request_two_and_six_request_none():
    assert len(select(metadata(), metadata(2022), years=range(2023, 2027)).selected) == 2
    assert select(metadata(), years=range(2021, 2027)).selected == ()


def test_gap_is_requested_without_retreat_to_older_complete_window():
    result = select(metadata(2023), metadata(2020), years=(2021, 2022, 2024, 2025, 2026))
    assert result.selected == (metadata(2023),)


@pytest.mark.parametrize("changes", [
    {"scope": S.STANDALONE}, {"security_code": "999999"}, {"period_type": P.QUARTERLY},
    {"value_basis": B.YEAR_TO_DATE}, {"filing_at": T + timedelta(seconds=1)},
    {"revised_at": T + timedelta(seconds=1)}, {"timestamp_status": BseTimestampStatus.UNKNOWN},
    {"xbrl_url": "https://www.bseindia.com/XBRLFILES/FourOneUploadDocument/"},
    {"xbrl_url": "https://other.example/annual.xml"},
])
def test_ineligible_archive_never_becomes_canonical_history(changes):
    result = select(metadata(**changes))
    assert not result.selected
    assert result.unavailable[0][1] == "OFFICIAL_SAME_SCOPE_ANNUAL_SOURCE_UNAVAILABLE"


@pytest.mark.parametrize("changes", [
    {"provider": "OTHER"}, {"isin": "INE000000001"},
    {"effective_as_of": T + timedelta(seconds=1)}, {"provider_instrument_reference": "123"},
])
def test_exact_mapping_and_mapping_pit_required(changes):
    result = select(metadata(), mapped=replace(mapping(), **changes))
    assert result.unavailable == ((None, "EXACT_PIT_BSE_MAPPING_REQUIRED"),)


def test_duplicate_and_permuted_archive_rows_are_idempotent():
    older, newer = metadata(filing_at=datetime(2021, 4, 30, tzinfo=UTC)), metadata()
    assert canonical_json(select(older, newer, newer)) == canonical_json(select(newer, older))
    assert select(newer).fingerprint == select(newer, newer).fingerprint


def test_conflicting_equal_time_revision_does_not_choose_by_order():
    a, b = metadata(), metadata(xbrl_url="https://www.bseindia.com/XBRLFILES/other.xml")
    left, right = select(a, b), select(b, a)
    assert left == right and not left.selected
    assert left.unavailable[0][1] == "OFFICIAL_ANNUAL_REVISION_AMBIGUOUS"


def test_latest_eligible_revision_and_inclusive_time_boundary():
    newer = metadata(status="REVISED", revised_at=T)
    assert select(metadata(), newer).selected == (newer,)
    assert select(newer).fingerprint == select(replace(newer, revised_at=T.astimezone(timezone(timedelta(hours=5, minutes=30))))).fingerprint


def test_existing_archive_timezone_assumption_is_preserved_not_promoted():
    source = metadata(timestamp_status=BseTimestampStatus.EXCHANGE_LOCAL_ASSUMPTION,
        raw_filing_timestamp="05/01/2021 10:30:00",
        raw_filing_timestamp_field_path="BSE_RESULT_ARCHIVE.CSV.Filing_Date_Time")
    assert select(source).selected == (source,)
    assert select(source).selected[0].timestamp_status is BseTimestampStatus.EXCHANGE_LOCAL_ASSUMPTION


def test_noncalendar_or_ambiguous_annual_anchor_is_not_relabelled():
    bad = replace(fact(), period_start=datetime(2025, 1, 1, tzinfo=UTC))
    result = select_missing_annual_history(comparable((bad,)), mapping(), aliases(metadata()))
    assert result.unavailable == ((None, "ANNUAL_ANCHOR_MISSING_OR_NONCOMPARABLE"),)


def test_first_annual_requires_explicit_official_same_scope_anchor():
    quarters = comparable((fact(quarter=1),))
    empty = select_missing_annual_history(quarters, mapping(), ())
    assert not empty.selected
    first = select_missing_annual_history(quarters, mapping(), aliases(metadata(2026)))
    assert first.selected == (metadata(2026),)
    assert len(first.requested_endpoints) == 6


def test_worker_lock_and_provider_halt_are_never_removed_or_resumed(tmp_path, monkeypatch):
    from scripts import acquire_bse_missing_annual_history as worker
    monkeypatch.setattr(worker, "ROOT", tmp_path)
    monkeypatch.setattr(worker.sys, "argv", ["worker", "--execute"])
    root = tmp_path / "reports" / "bse-annual-history-v1" / "acquisition"
    root.mkdir(parents=True)
    lock = root / "worker.lock"
    lock.write_text("existing-owner", encoding="ascii")
    with pytest.raises(FileExistsError):
        worker.main()
    assert lock.read_text() == "existing-owner"
    halt = root / "PROVIDER_HALT.json"
    halt.write_text("{}", encoding="ascii")
    with pytest.raises(SystemExit):
        worker.main()
    assert lock.read_text() == "existing-owner" and halt.exists()


def test_worker_owns_only_its_lock_and_enforces_batch_bound(tmp_path, monkeypatch):
    from scripts import acquire_bse_missing_annual_history as worker
    monkeypatch.setattr(worker, "ROOT", tmp_path)
    called = []
    monkeypatch.setattr(worker, "acquire", lambda **kwargs: called.append(kwargs["max_documents"]))
    monkeypatch.setattr(worker.sys, "argv", ["worker", "--execute", "--max-documents", "25"])
    worker.main()
    assert called == [25]
    assert not (tmp_path / "reports/bse-annual-history-v1/acquisition/worker.lock").exists()
    monkeypatch.setattr(worker.sys, "argv", ["worker", "--execute", "--max-documents", "26"])
    with pytest.raises(SystemExit):
        worker.main()
    assert called == [25]


def test_replay_invariant_stops_outer_acquisition_loop(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from scripts import acquire_bse_missing_annual_history as worker
    from app.fundamentals.bse_collector import BseOfficialHttpResponse
    from app.fundamentals.bse_official import BseLocalIngestionReport, BsePublicationAvailability
    from app.filings.store import FilingWriteOutcome
    monkeypatch.setattr(worker, "ROOT", tmp_path)
    monkeypatch.setattr(worker, "_inputs", lambda *_: ((INSTRUMENT, mapping(), comparable(tuple(fact(year=y) for y in range(2022, 2027)))),))
    response = BseOfficialHttpResponse(metadata().xbrl_url, "text/xml", b"fixture", T)
    monkeypatch.setattr(worker, "BseOfficialHttpTransport", lambda: SimpleNamespace(
        fetch_results_archive_response=lambda _: response, fetch_xbrl=lambda _: response))
    monkeypatch.setattr(worker, "BseOfficialArchiveSnapshotStore", lambda _: SimpleNamespace(capture=lambda **_: None))
    monkeypatch.setattr(worker, "BSEOfficialFinancialResultsArchiveProvider", lambda **_: SimpleNamespace(result_metadata_aliases=lambda _: aliases(metadata())))
    monkeypatch.setattr(worker, "BseOfficialXbrlStaging", lambda _: SimpleNamespace(
        stage=lambda **_: SimpleNamespace(path=tmp_path / "raw.xml", sha256="a" * 64),
        preserve_archive_aliases=lambda **_: None))
    report = BseLocalIngestionReport(ID, "532259", "raw.xml", True, FilingWriteOutcome.INSERTED,
        1, 0, 0, T, BsePublicationAvailability.SOURCE_PUBLICATION_KNOWN, ())
    monkeypatch.setattr(worker, "BSEOfficialLocalXbrlIngestionService", lambda *_: SimpleNamespace(ingest_official_staged=lambda *_, **__: report))
    monkeypatch.setattr(worker, "SQLiteCorporateFilingsStore", lambda _: None)
    monkeypatch.setattr(worker, "SQLiteFinancialFactStore", lambda _: None)
    monkeypatch.setattr(worker, "sleep", lambda _: None)
    output = tmp_path / "receipts"
    output.mkdir()
    with pytest.raises(ValueError, match="ANNUAL_REPLAY_INVARIANT_FAILED"):
        worker.acquire(database=tmp_path / "unused.db", source_root=tmp_path / "sources", report_root=output, max_documents=5)
    assert (output / "INVARIANT_HALT.json").exists()


def test_no_synthetic_ebitda_ebit_or_segment_operating_profit_mapping():
    xml = _xbrl(pat="10", scope="Standalone").replace("</xbrli:xbrl>", """
      <in-capmkt:OperatingProfitBeforeProvisionAndContingencies contextRef="quarter">900</in-capmkt:OperatingProfitBeforeProvisionAndContingencies>
      <in-capmkt:SegmentProfitLossBeforeTaxAndFinanceCosts contextRef="quarter">800</in-capmkt:SegmentProfitLossBeforeTaxAndFinanceCosts>
      <in-capmkt:FinanceCosts contextRef="quarter">5</in-capmkt:FinanceCosts>
      <in-capmkt:DepreciationDepletionAndAmortisationExpense contextRef="quarter">5</in-capmkt:DepreciationDepletionAndAmortisationExpense>
      </xbrli:xbrl>""")
    document = parse_bse_xbrl(xml, "https://www.bseindia.com/XBRLFILES/test.xml", period_end=datetime(2026, 6, 30, tzinfo=UTC))
    metrics = {f.metric for f in document.context_facts}
    assert {M.PBT, M.FINANCE_COST, M.DEPRECIATION} <= metrics
    assert not {M.EBIT, M.EBITDA, M.OPERATING_PROFIT} & metrics


def test_readonly_loader_reuses_persisted_correction_record_type_and_pit(tmp_path):
    import sqlite3
    from scripts.audit_bse_annual_history import _Corrections
    from app.data_operations.financial_period_identity_repair import FinancialPeriodIdentityProjection
    from tests.unit.test_financial_period_identity_repair import _seed, _fact, T as known_at
    original = _fact("fact:quarter", M.REVENUE, "100")
    _, _, store, service, repository = _seed(tmp_path, (original,))
    try:
        service.audit_and_apply((original.instrument.instrument_id,))
        with sqlite3.connect((tmp_path / "core.sqlite").as_uri() + "?mode=ro", uri=True) as connection:
            reader = _Corrections(connection)
        assert reader.corrections() == store.corrections()
        assert len(reader.corrections()) == 1
        projection = FinancialPeriodIdentityProjection(reader)
        assert projection.project((original,), as_of=known_at - timedelta(seconds=1)) == (original,)
        current = projection.project((original,), as_of=known_at)[0]
        assert current.period_start == datetime(2025, 7, 1, tzinfo=UTC)
        assert original.period_start == datetime(2025, 4, 1, tzinfo=UTC)
    finally:
        repository.close()


def test_selection_has_no_io_evaluator_clock_or_trade_calls():
    source = Path("app/fundamentals/bse_annual_history.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    calls = {n.func.attr if isinstance(n.func, ast.Attribute) else n.func.id
             for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, (ast.Attribute, ast.Name))}
    assert not calls & {"now", "today", "save", "execute", "connect", "open", "fetch", "place_order"}
    imports = {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
    assert all(not any(part in (name or "") for part in ("portfolio", "broker", "orders", "analysis.fundamentals", "runtime")) for name in imports)
