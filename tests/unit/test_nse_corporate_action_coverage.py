from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
import json
from pathlib import Path

import pytest

from app.historical.nse_corporate_action_coverage import (
    NSE_CORPORATE_ACTIONS_ENDPOINT,
    NseCorporateActionAcquisitionError,
    NseCorporateActionContinuityStatus,
    NseCorporateActionCoverageBackfill,
    NseCorporateActionCoverageStore,
    NseCorporateActionFamily,
    NseCorporateActionIdentityStatus,
    NseCorporateActionQueryStatus,
    NseCorporateActionQueryWindow,
    NseCorporateActionSecurityCoverageStatus,
    NseCorporateActionSourceResult,
    NseOfficialCorporateActionsSource,
    monthly_windows,
)
from app.historical.security_master import CorporateActionKind, HistoricalCorporateAction, HistoricalSecurityMasterStore
from app.storage.core_api_snapshot_repository import CoreApiSnapshotFamily
from app.storage.sqlite_core_api_snapshot_repository import SQLiteCoreApiSnapshotRepository
from app.universe_analysis.models import NseEquityInstrument, UniverseSnapshot
from app.universe_analysis.service import CoreUniverseAnalysisStore


T = datetime(2026, 9, 6, 8, 0, tzinfo=UTC)
START, END = date(2024, 1, 1), date(2024, 2, 29)


def _instrument(identifier: str, symbol: str, isin: str) -> NseEquityInstrument:
    return NseEquityInstrument(identifier, symbol, isin, "Industry", None, "ACTIVE", None, True, T, "fixture", company_name=f"{symbol} Limited")


def _universe(repo: SQLiteCoreApiSnapshotRepository, instruments: tuple[NseEquityInstrument, ...]) -> CoreUniverseAnalysisStore:
    store = CoreUniverseAnalysisStore(repo)
    snapshot = UniverseSnapshot("nse-universe:coverage-fixture", T, "fixture", len(instruments), len(instruments), 0, (), "v1", "checksum", tuple(item.instrument_id for item in instruments))
    store.save_universe_snapshot(snapshot)
    for item in instruments:
        store.save_instrument(item)
    return store


def _record(*, symbol: str = "ALPHA", isin: str = "INE000A01001", subject: str = "Bonus 1:1", ex_date: str = "10-Jan-2024", record_date: str = "11-Jan-2024") -> dict[str, object]:
    return {
        "symbol": symbol, "isin": isin, "series": "EQ", "subject": subject,
        "exDate": ex_date, "recDate": record_date, "bcStartDate": "-", "bcEndDate": "-",
        "faceVal": "10", "comp": "Alpha Limited", "caBroadcastDate": None,
    }


class _Source:
    def __init__(self, outcomes: dict[str, NseCorporateActionSourceResult]) -> None:
        self.outcomes, self.calls = outcomes, []

    def fetch(self, window: NseCorporateActionQueryWindow) -> NseCorporateActionSourceResult:
        self.calls.append(window.key)
        return self.outcomes[window.key]


def _success(window: NseCorporateActionQueryWindow, *records: dict[str, object]) -> NseCorporateActionSourceResult:
    payload = list(records)
    return NseCorporateActionSourceResult(
        NseCorporateActionQueryStatus.SUCCESS_WITH_ACTIONS if payload else NseCorporateActionQueryStatus.SUCCESS_EMPTY,
        window,
        T,
        json.dumps(payload, separators=(",", ":")),
        tuple(payload),
    )


def _failure(window: NseCorporateActionQueryWindow, *, blocked: bool = False) -> NseCorporateActionSourceResult:
    return NseCorporateActionSourceResult(
        NseCorporateActionQueryStatus.SOURCE_BLOCKED if blocked else NseCorporateActionQueryStatus.SOURCE_FAILED,
        window,
        T,
        None,
        (),
        "NSE_CORPORATE_ACTION_SOURCE_BLOCKED" if blocked else "NSE_CORPORATE_ACTION_HTTP_FAILURE",
    )


def _backfill(tmp_path: Path, source: _Source, instruments: tuple[NseEquityInstrument, ...] | None = None) -> tuple[NseCorporateActionCoverageBackfill, SQLiteCoreApiSnapshotRepository]:
    repo = SQLiteCoreApiSnapshotRepository(tmp_path / "coverage.sqlite")
    values = instruments or (_instrument("NSE:INE000A01001", "ALPHA", "INE000A01001"), _instrument("NSE:INE000A01002", "BETA", "INE000A01002"))
    return NseCorporateActionCoverageBackfill(repository=repo, universe=_universe(repo, values), source=source, minimum_interval_seconds=0, sleeper=lambda _: None), repo


def test_monthly_windows_are_exact_non_overlapping_and_deterministic():
    windows = monthly_windows(date(2023, 8, 21), date(2023, 10, 2))
    assert [(item.start_date, item.end_date) for item in windows] == [
        (date(2023, 8, 21), date(2023, 8, 31)),
        (date(2023, 9, 1), date(2023, 9, 30)),
        (date(2023, 10, 1), date(2023, 10, 2)),
    ]


def test_success_with_actions_preserves_raw_primary_evidence_maps_exact_identity_and_appends_action(tmp_path: Path):
    windows = monthly_windows(START, END)
    source = _Source({windows[0].key: _success(windows[0], _record()), windows[1].key: _success(windows[1])})
    job, repo = _backfill(tmp_path, source)

    result = job.run(acquisition_id="nse-ca-backfill:fixture", start_date=START, end_date=END, observed_at=T)

    assert result.replayed is False
    assert [item.status for item in result.query_receipts] == [NseCorporateActionQueryStatus.SUCCESS_WITH_ACTIONS, NseCorporateActionQueryStatus.SUCCESS_EMPTY]
    assert result.manifest.observation_count == result.manifest.new_canonical_action_count == 1
    assert result.manifest.requested_instrument_ids == ("NSE:INE000A01001", "NSE:INE000A01002")
    assert result.manifest.successful_query_count == 2
    assert result.manifest.empty_successful_query_count == 1
    assert result.manifest.failed_query_count == result.manifest.blocked_query_count == result.manifest.invalid_query_count == 0
    observation = NseCorporateActionCoverageStore(repo).observations("nse-ca-backfill:fixture")[0]
    assert observation.identity_status is NseCorporateActionIdentityStatus.EXACT_ISIN_AND_SYMBOL
    assert observation.family is NseCorporateActionFamily.BONUS
    assert observation.adjustment_input_complete is True
    assert "HISTORICAL_SOURCE_KNOWN_AT_UNAVAILABLE" in observation.warnings
    assert observation.canonical_action_id is not None
    assert observation.observed_at == T and observation.ex_date == datetime(2024, 1, 10, tzinfo=UTC)
    artifacts = repo.list_snapshots(CoreApiSnapshotFamily.NSE_CORPORATE_ACTION_SOURCE_ARTIFACT)
    assert any('"subject":"Bonus 1:1"' in item.payload.raw_response for item in artifacts)
    actions = HistoricalSecurityMasterStore(repo).actions_as_of("NSE:INE000A01001", T + timedelta(days=1))
    assert len(actions) == 1 and actions[0].kind is CorporateActionKind.BONUS
    assert actions[0].as_of == T and actions[0].effective_date == datetime(2024, 1, 10, tzinfo=UTC)


def test_successful_empty_query_is_never_conflated_with_failure_or_no_query(tmp_path: Path):
    windows = monthly_windows(START, END)
    source = _Source({windows[0].key: _success(windows[0]), windows[1].key: _failure(windows[1])})
    job, _ = _backfill(tmp_path, source)
    result = job.run(acquisition_id="nse-ca-backfill:empty-failure", start_date=START, end_date=END, observed_at=T)

    assert {item.status for item in result.query_receipts} == {NseCorporateActionQueryStatus.SUCCESS_EMPTY, NseCorporateActionQueryStatus.SOURCE_FAILED}
    assert {item.status for item in result.assessment.coverages} == {NseCorporateActionSecurityCoverageStatus.QUERY_FAILED}
    assert all(item.continuity_status is NseCorporateActionContinuityStatus.LIFECYCLE_SOURCE_REQUIRED for item in result.assessment.coverages)


def test_identity_requires_exact_isin_and_symbol_and_never_fuzzy_maps(tmp_path: Path):
    windows = monthly_windows(START, END)
    source = _Source({
        windows[0].key: _success(windows[0], _record(isin="INE999A01001")),
        windows[1].key: _success(windows[1]),
    })
    job, repo = _backfill(tmp_path, source)
    result = job.run(acquisition_id="nse-ca-backfill:identity", start_date=START, end_date=END, observed_at=T)

    observation = NseCorporateActionCoverageStore(repo).observations("nse-ca-backfill:identity")[0]
    assert observation.identity_status is NseCorporateActionIdentityStatus.IDENTITY_CONFLICT
    assert observation.canonical_instrument_id is observation.canonical_action_id is None
    alpha = next(item for item in result.assessment.coverages if item.canonical_instrument_id == "NSE:INE000A01001")
    assert alpha.status is NseCorporateActionSecurityCoverageStatus.IDENTITY_UNRESOLVED
    assert HistoricalSecurityMasterStore(repo).actions_as_of("NSE:INE000A01001", T + timedelta(days=1)) == ()


def test_backfill_uses_only_the_snapshot_frozen_eligible_population_and_accepts_canonical_ampersand_symbols(tmp_path: Path):
    window = NseCorporateActionQueryWindow(START, date(2024, 1, 31))
    repository = SQLiteCoreApiSnapshotRepository(tmp_path / "frozen-universe.sqlite")
    target = _instrument("NSE:M&M", "M&M", "INE101A01026")
    universe = _universe(repository, (target,))
    universe.save_instrument(_instrument("NSE:INE000A01002", "LATER", "INE000A01002"))
    source = _Source({window.key: _success(window, _record(symbol="M&M", isin="INE101A01026"))})

    result = NseCorporateActionCoverageBackfill(
        repository=repository, universe=universe, source=source,
        minimum_interval_seconds=0, sleeper=lambda _: None,
    ).run(acquisition_id="nse-ca-backfill:frozen-universe", start_date=START, end_date=window.end_date, observed_at=T)

    assert result.manifest.requested_instrument_ids == ("NSE:M&M",)
    assert tuple(item.canonical_instrument_id for item in result.assessment.coverages) == ("NSE:M&M",)
    assert result.assessment.coverages[0].status is NseCorporateActionSecurityCoverageStatus.QUERY_SUCCESS_WITH_ACTIONS


def test_non_equity_series_is_retained_as_raw_evidence_but_never_promoted_by_symbol_or_isin(tmp_path: Path):
    window = NseCorporateActionQueryWindow(START, date(2024, 1, 31))
    record = _record()
    record["series"] = "BE"
    source = _Source({window.key: _success(window, record)})
    job, repo = _backfill(tmp_path, source)

    job.run(acquisition_id="nse-ca-backfill:non-equity-series", start_date=START, end_date=window.end_date, observed_at=T)

    observation = NseCorporateActionCoverageStore(repo).observations("nse-ca-backfill:non-equity-series")[0]
    assert observation.series == "BE"
    assert observation.identity_status is NseCorporateActionIdentityStatus.IDENTITY_UNRESOLVED
    assert observation.canonical_instrument_id is observation.canonical_action_id is None


@pytest.mark.parametrize(
    ("subject", "family", "canonical_kind", "ratio_complete"),
    (
        ("Face Value Split (Sub-Division) - From Rs 10 Per Share To Rs 5 Per Share", NseCorporateActionFamily.SPLIT, CorporateActionKind.SPLIT, True),
        ("Bonus 1:2", NseCorporateActionFamily.BONUS, CorporateActionKind.BONUS, True),
        ("Rights 1:4 @ Premium Rs 10", NseCorporateActionFamily.RIGHTS, CorporateActionKind.RIGHTS, False),
        ("Special Dividend - Rs 5 Per Share", NseCorporateActionFamily.SPECIAL_DIVIDEND, CorporateActionKind.DIVIDEND, False),
        ("Buy Back", NseCorporateActionFamily.BUYBACK, None, False),
        ("Face Value Change", NseCorporateActionFamily.FACE_VALUE_CHANGE, None, False),
        ("Demerger", NseCorporateActionFamily.DEMERGER, CorporateActionKind.DEMERGER, False),
    ),
)
def test_deterministic_normalization_preserves_raw_purpose_without_activating_unsupported_adjustments(tmp_path: Path, subject: str, family: NseCorporateActionFamily, canonical_kind: CorporateActionKind | None, ratio_complete: bool):
    window = NseCorporateActionQueryWindow(START, date(2024, 1, 31))
    source = _Source({window.key: _success(window, _record(subject=subject))})
    job, repo = _backfill(tmp_path, source)
    job.run(acquisition_id="nse-ca-backfill:" + family.value.lower(), start_date=START, end_date=window.end_date, observed_at=T)
    observation = NseCorporateActionCoverageStore(repo).observations("nse-ca-backfill:" + family.value.lower())[0]
    assert (observation.family, observation.raw_purpose, observation.adjustment_input_complete) == (family, subject, ratio_complete)
    actions = HistoricalSecurityMasterStore(repo).actions_as_of("NSE:INE000A01001", T + timedelta(days=1))
    assert [item.kind for item in actions] == ([] if canonical_kind is None else [canonical_kind])
    if family is NseCorporateActionFamily.RIGHTS:
        assert observation.canonical_action_id is not None
    if canonical_kind is None:
        assert observation.canonical_action_id is None


def test_existing_equivalent_receipt_is_never_overwritten_and_new_source_observation_is_reconciled(tmp_path: Path):
    window = NseCorporateActionQueryWindow(START, date(2024, 1, 31))
    source = _Source({window.key: _success(window, _record())})
    job, repo = _backfill(tmp_path, source)
    legacy = HistoricalCorporateAction(
        "legacy-action", "NSE:INE000A01001", CorporateActionKind.BONUS, None,
        datetime(2024, 1, 11, tzinfo=UTC), datetime(2024, 1, 10, tzinfo=UTC), datetime(2024, 1, 10, tzinfo=UTC),
        Decimal("1"), Decimal("1"), json.dumps({"original_purpose": "Bonus 1:1"}),
        "NSE_OFFICIAL_CORPORATE_ACTION_EXPORT", "nse-corporate-action-v1", T - timedelta(days=1), "legacy",
    )
    HistoricalSecurityMasterStore(repo).save_action(legacy)

    result = job.run(acquisition_id="nse-ca-backfill:reconcile", start_date=START, end_date=window.end_date, observed_at=T)

    assert result.manifest.new_canonical_action_count == 0
    assert result.manifest.duplicate_canonical_action_count == 1
    actions = HistoricalSecurityMasterStore(repo).actions_as_of("NSE:INE000A01001", T + timedelta(days=1))
    assert [item.action_id for item in actions] == ["legacy-action"]
    observation = NseCorporateActionCoverageStore(repo).observations("nse-ca-backfill:reconcile")[0]
    assert observation.canonical_action_id == "legacy-action"


def test_replay_is_idempotent_and_does_not_refetch_or_create_duplicate_canonical_history(tmp_path: Path):
    window = NseCorporateActionQueryWindow(START, date(2024, 1, 31))
    source = _Source({window.key: _success(window, _record())})
    job, repo = _backfill(tmp_path, source)
    first = job.run(acquisition_id="nse-ca-backfill:replay", start_date=START, end_date=window.end_date, observed_at=T)
    before = len(repo.list_snapshots(CoreApiSnapshotFamily.HISTORICAL_CORPORATE_ACTION))
    second = job.run(acquisition_id="nse-ca-backfill:replay", start_date=START, end_date=window.end_date, observed_at=T + timedelta(days=1))

    assert first.replayed is False and second.replayed is True
    assert source.calls == [window.key]
    assert len(repo.list_snapshots(CoreApiSnapshotFamily.HISTORICAL_CORPORATE_ACTION)) == before == 1
    assert second.manifest.fingerprint == first.manifest.fingerprint


def test_duplicate_raw_rows_retain_distinct_provenance_but_only_one_logical_action_and_reopen_durably(tmp_path: Path):
    window = NseCorporateActionQueryWindow(START, date(2024, 1, 31))
    record = _record()
    source = _Source({window.key: _success(window, record, record)})
    path = tmp_path / "duplicate.sqlite"
    repository = SQLiteCoreApiSnapshotRepository(path)
    values = (_instrument("NSE:INE000A01001", "ALPHA", "INE000A01001"),)
    job = NseCorporateActionCoverageBackfill(
        repository=repository,
        universe=_universe(repository, values),
        source=source,
        minimum_interval_seconds=0,
        sleeper=lambda _: None,
    )

    result = job.run(acquisition_id="nse-ca-backfill:duplicate-raw", start_date=START, end_date=window.end_date, observed_at=T)

    assert result.manifest.observation_count == 2
    assert result.manifest.new_canonical_action_count == 1
    assert result.manifest.duplicate_canonical_action_count == 1
    repository.close()
    reopened = SQLiteCoreApiSnapshotRepository(path)
    observations = NseCorporateActionCoverageStore(reopened).observations("nse-ca-backfill:duplicate-raw")
    assert len(observations) == 2
    assert len({item.observation_id for item in observations}) == 2
    assert len({item.canonical_action_id for item in observations}) == 1
    assert observations[0].canonical_action_id is not None
    assert len(HistoricalSecurityMasterStore(reopened).actions_as_of("NSE:INE000A01001", T + timedelta(days=1))) == 1


class _Response:
    def __init__(self, status: int, payload: object) -> None:
        self.status_code = status
        self.content = json.dumps(payload, separators=(",", ":")).encode("utf-8")


class _Session:
    def __init__(self, response: _Response) -> None:
        self.response, self.calls, self.closed = response, [], 0

    def get(self, url, *, headers, params=None, timeout):
        self.calls.append((url, headers, params, timeout))
        return self.response

    def close(self):
        self.closed += 1


def test_official_source_uses_exchange_wide_date_query_and_preserves_empty_success():
    session = _Session(_Response(200, []))
    source = NseOfficialCorporateActionsSource(session_factory=lambda: session, observed_at=lambda: T)
    window = NseCorporateActionQueryWindow(date(2024, 1, 1), date(2024, 1, 31))
    result = source.fetch(window)
    assert result.status is NseCorporateActionQueryStatus.SUCCESS_EMPTY
    assert session.calls[-1][0] == NSE_CORPORATE_ACTIONS_ENDPOINT
    assert session.calls[-1][2] == {"index": "equities", "from_date": "01-01-2024", "to_date": "31-01-2024"}
    assert session.closed == 1


def test_source_failures_are_typed_and_cannot_become_empty_coverage():
    session = _Session(_Response(429, []))
    source = NseOfficialCorporateActionsSource(session_factory=lambda: session, observed_at=lambda: T)
    result = source.fetch(NseCorporateActionQueryWindow(START, date(2024, 1, 31)))
    assert result.status is NseCorporateActionQueryStatus.SOURCE_BLOCKED
    assert result.error_code == "NSE_CORPORATE_ACTION_SOURCE_BLOCKED"
    assert session.closed == 1


def test_invalid_response_preserves_raw_artifact_but_remains_a_typed_failed_receipt(tmp_path: Path):
    session = _Session(_Response(200, {"unexpected": True}))
    source = NseOfficialCorporateActionsSource(session_factory=lambda: session, observed_at=lambda: T)
    window = NseCorporateActionQueryWindow(START, date(2024, 1, 31))
    source_result = source.fetch(window)
    assert source_result.status is NseCorporateActionQueryStatus.INVALID_RESPONSE
    assert source_result.raw_response == '{"unexpected":true}'
    assert session.closed == 1
    job, repo = _backfill(tmp_path, _Source({window.key: source_result}))

    result = job.run(acquisition_id="nse-ca-backfill:invalid-response", start_date=START, end_date=window.end_date, observed_at=T)

    assert result.query_receipts[0].status is NseCorporateActionQueryStatus.INVALID_RESPONSE
    assert result.query_receipts[0].artifact_id is not None
    assert result.manifest.invalid_query_count == 1
    artifacts = repo.list_snapshots(CoreApiSnapshotFamily.NSE_CORPORATE_ACTION_SOURCE_ARTIFACT)
    assert artifacts[0].payload.raw_response == '{"unexpected":true}'


def test_action_free_continuity_remains_not_certified_without_lifecycle_source_composition(tmp_path: Path):
    window = NseCorporateActionQueryWindow(START, date(2024, 1, 31))
    source = _Source({window.key: _success(window)})
    job, _ = _backfill(tmp_path, source)
    result = job.run(acquisition_id="nse-ca-backfill:lifecycle", start_date=START, end_date=window.end_date, observed_at=T)
    assert {item.status for item in result.assessment.coverages} == {NseCorporateActionSecurityCoverageStatus.QUERY_SUCCESS_NO_ACTIONS}
    assert {item.continuity_status for item in result.assessment.coverages} == {NseCorporateActionContinuityStatus.LIFECYCLE_SOURCE_REQUIRED}


def test_contract_rejects_invalid_windows_and_has_no_weekly_indicator_or_execution_dependency():
    with pytest.raises(NseCorporateActionAcquisitionError, match="QUERY_WINDOW_INVALID"):
        NseCorporateActionQueryWindow(date(2024, 2, 1), date(2024, 1, 1))
    import app.historical.nse_corporate_action_coverage as module
    source = Path(module.__file__).read_text(encoding="utf-8")
    forbidden = ("app.api", "app.portfolio", "app.broker", "app.orders", "app.signals", "weekly", "monthly bar", "MACD", "Stochastic", "CCI", "Williams")
    assert not any(item in source for item in forbidden)
