from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.backtest.engine import backtest_run_fingerprint
from app.backtest.models import BacktestDataGapBehavior, BacktestDataGapPolicy, BacktestEvent, BacktestEventType, BacktestRun, BacktestRunStatus, EvaluationLabel, ExecutionTimingPolicy, ReplayFrequency, ReplaySchedule
from app.backtest.portfolio import BacktestPortfolioLedgerEvent, BacktestPortfolioLedgerType, BacktestPortfolioReplayEngine, BacktestPortfolioReplayService
from app.gates.engine import ExchangeCalendar
from app.historical.models import DatasetQuality, HistoricalDatasetManifest
from app.portfolio.models import PriceReference
from app.services.audit_reconstruction_service import AuditReconstructionError, AuditReconstructionService
from app.storage.sqlite_governance_repository import SQLiteStrategyGovernanceRepository


T = datetime(2026, 1, 2, 15, 30, tzinfo=UTC)
CALENDAR = ExchangeCalendar("portfolio-calendar", frozenset())


def setup_repo(tmp_path):
    repo = SQLiteStrategyGovernanceRepository(tmp_path / "portfolio.db")
    manifest = HistoricalDatasetManifest("portfolio-data", "1", T, T - timedelta(days=10), T + timedelta(days=10), CALENDAR.calendar_id, "portfolio-universe", {}, {}, DatasetQuality.HIGH_QUALITY, (), "raw", __import__("app.historical.models", fromlist=["SurvivorshipStatus"]).SurvivorshipStatus.POINT_IN_TIME_UNIVERSE, "FULL", (), "portfolio-fingerprint")
    repo.save_historical_manifest(manifest)
    schedule = ReplaySchedule("portfolio-schedule", "1", ReplayFrequency.DAILY_CLOSE, "UTC", CALENDAR.calendar_id, "close", ExecutionTimingPolicy.NEXT_ELIGIBLE_BAR, T.replace(hour=0), T.replace(hour=23, minute=59))
    gap = BacktestDataGapPolicy("portfolio-gap", "1", BacktestDataGapBehavior.FAIL_RUN)
    run = BacktestRun("portfolio-run", manifest.dataset_id, manifest.dataset_version, manifest.fingerprint, None, "strategy", "diagnostic-registry-v1", "score", "gates", "rotation", "signal", "paper", "performance", "backtest", schedule.schedule_id, schedule.version, gap.policy_id, gap.version, CALENDAR.calendar_id, "1", schedule.start, schedule.end, Decimal("100"), "cost", "slippage", "portfolio-universe", (), BacktestRunStatus.CREATED, DatasetQuality.HIGH_QUALITY, EvaluationLabel.IN_SAMPLE, (), (), "", T)
    run = replace(run, fingerprint=backtest_run_fingerprint(run))
    repo.save_replay_schedule(schedule); repo.save_backtest_data_gap_policy(gap); repo.save_backtest_run(run)
    repo.append_backtest_event(BacktestEvent("portfolio-start", run.backtest_run_id, BacktestEventType.REPLAY_STARTED, T, 0, T, (), "start", {}, T))
    return repo, run


def ledger(identifier, kind, *, instrument=None, quantity=None, price=None, gross=Decimal("0"), cash=Decimal("0"), ratio=None, at=T):
    return BacktestPortfolioLedgerEvent(identifier, "portfolio-run", kind, at, at, "fixture", identifier, instrument, quantity, price, gross, Decimal("0"), Decimal("0"), cash, ratio)


def test_ledger_and_state_round_trip_audit_and_duplicate_immutability(tmp_path):
    repo, run = setup_repo(tmp_path)
    events = (ledger("initial", BacktestPortfolioLedgerType.INITIAL_CAPITAL, cash=Decimal("100")), ledger("buy-a", BacktestPortfolioLedgerType.HYPOTHETICAL_BUY, instrument="A", quantity=Decimal("4"), price=Decimal("10"), gross=Decimal("40"), cash=Decimal("-40")), ledger("buy-a2", BacktestPortfolioLedgerType.HYPOTHETICAL_BUY, instrument="A", quantity=Decimal("2"), price=Decimal("20"), gross=Decimal("40"), cash=Decimal("-40")), ledger("sell-a", BacktestPortfolioLedgerType.HYPOTHETICAL_SELL, instrument="A", quantity=Decimal("2"), price=Decimal("15"), gross=Decimal("30"), cash=Decimal("30")), ledger("buy-b", BacktestPortfolioLedgerType.HYPOTHETICAL_BUY, instrument="B", quantity=Decimal("1"), price=Decimal("10"), gross=Decimal("10"), cash=Decimal("-10")))
    for item in events: repo.append_backtest_portfolio_ledger_event(item)
    assert repo.get_backtest_portfolio_ledger_event("buy-a") == events[1]
    with pytest.raises(ValueError): repo.append_backtest_portfolio_ledger_event(events[1])
    prices = (PriceReference("mark-a", "A", Decimal("15"), T, T), PriceReference("mark-b", "B", Decimal("8"), T, T))
    state = BacktestPortfolioReplayService(repo, CALENDAR).reconstruct_and_persist(run_id=run.backtest_run_id, step_number=1, at=T, starting_capital=Decimal("100"), events=events, prices=prices)
    assert repo.get_backtest_portfolio_state(state.backtest_portfolio_state_id) == state
    assert state.snapshot.cash.amount == Decimal("40") and len(state.snapshot.holdings) == 2
    holding_a = next(x for x in state.snapshot.holdings if x.instrument_id == "A")
    expected_average = Decimal("80") / Decimal("6")
    assert holding_a.quantity == Decimal("4") and holding_a.cost_basis == Decimal("80") - expected_average * Decimal("2") and holding_a.realized_pnl == Decimal("30") - expected_average * Decimal("2")
    assert AuditReconstructionService(repo).reconstruct_backtest_portfolio_state(state.backtest_portfolio_state_id, CALENDAR) == state
    with pytest.raises(ValueError): repo.save_backtest_portfolio_state(state)
    events_out = repo.list_backtest_events(run.backtest_run_id)
    assert [x.event_type for x in events_out[-2:]] == [BacktestEventType.PORTFOLIO_RECONSTRUCTED, BacktestEventType.PORTFOLIO_VALUED]


def test_missing_mark_future_inputs_and_audit_tampering_are_frozen(tmp_path):
    repo, run = setup_repo(tmp_path)
    events = (ledger("initial", BacktestPortfolioLedgerType.INITIAL_CAPITAL, cash=Decimal("100")), ledger("buy", BacktestPortfolioLedgerType.HYPOTHETICAL_BUY, instrument="A", quantity=Decimal("5"), price=Decimal("10"), gross=Decimal("50"), cash=Decimal("-50")))
    for item in events: repo.append_backtest_portfolio_ledger_event(item)
    state = BacktestPortfolioReplayService(repo, CALENDAR).reconstruct_and_persist(run_id=run.backtest_run_id, step_number=1, at=T, starting_capital=Decimal("100"), events=events, prices=())
    assert state.snapshot.data_status.value == "PARTIAL" and "MISSING_MARK" in state.warnings
    later = ledger("future-buy", BacktestPortfolioLedgerType.HYPOTHETICAL_BUY, instrument="A", quantity=Decimal("1"), price=Decimal("1"), gross=Decimal("1"), cash=Decimal("-1"), at=T + timedelta(days=1))
    repo.append_backtest_portfolio_ledger_event(later)
    assert repo.get_backtest_portfolio_state(state.backtest_portfolio_state_id) == state
    assert AuditReconstructionService(repo).reconstruct_backtest_portfolio_state(state.backtest_portfolio_state_id, CALENDAR) == state
    tampered = replace(state, source_ledger_ids=("missing-ledger",))
    import json
    from app.backtest.portfolio import state_dump
    repo._connection.execute("UPDATE backtest_portfolio_states SET payload_json=? WHERE id=?", (json.dumps(state_dump(tampered)), state.backtest_portfolio_state_id)); repo._connection.commit()
    with pytest.raises(AuditReconstructionError): AuditReconstructionService(repo).reconstruct_backtest_portfolio_state(state.backtest_portfolio_state_id, CALENDAR)


def test_cash_only_split_bonus_and_cash_constraint(tmp_path):
    repo, run = setup_repo(tmp_path)
    initial = ledger("initial", BacktestPortfolioLedgerType.INITIAL_CAPITAL, cash=Decimal("100"))
    repo.append_backtest_portfolio_ledger_event(initial)
    cash_state = BacktestPortfolioReplayEngine(CALENDAR).reconstruct(run_id=run.backtest_run_id, step_number=1, at=T, starting_capital=Decimal("100"), events=(initial,), prices=())
    assert cash_state.snapshot.cash.amount == Decimal("100") and not cash_state.snapshot.holdings
    too_large = ledger("too-large", BacktestPortfolioLedgerType.HYPOTHETICAL_BUY, instrument="A", quantity=Decimal("20"), price=Decimal("10"), gross=Decimal("200"), cash=Decimal("-200"))
    with pytest.raises(ValueError, match="cannot deploy"): BacktestPortfolioReplayEngine(CALENDAR).reconstruct(run_id=run.backtest_run_id, step_number=1, at=T, starting_capital=Decimal("100"), events=(initial, too_large), prices=())


@pytest.mark.parametrize("kind,ratio,quantity", [(BacktestPortfolioLedgerType.SPLIT, Decimal("2"), Decimal("10")), (BacktestPortfolioLedgerType.BONUS, Decimal("1"), Decimal("10"))])
def test_split_and_bonus_preserve_cost_basis_and_cash(tmp_path, kind, ratio, quantity):
    repo, run = setup_repo(tmp_path); initial=ledger("initial",BacktestPortfolioLedgerType.INITIAL_CAPITAL,cash=Decimal("100")); buy=ledger("buy",BacktestPortfolioLedgerType.HYPOTHETICAL_BUY,instrument="A",quantity=Decimal("5"),price=Decimal("10"),gross=Decimal("50"),cash=Decimal("-50")); action=ledger("action",kind,instrument="A",ratio=ratio,at=T + timedelta(minutes=1))
    state=BacktestPortfolioReplayEngine(CALENDAR).reconstruct(run_id=run.backtest_run_id,step_number=1,at=T + timedelta(minutes=1),starting_capital=Decimal("100"),events=(initial,buy,action),prices=(PriceReference("p","A",Decimal("10"),T,T),))
    holding=state.snapshot.holdings[0]
    assert holding.quantity == quantity and holding.cost_basis == Decimal("50") and state.snapshot.cash.amount == Decimal("50")
    assert holding.average_cost == Decimal("5")


def test_full_sale_stale_unknown_sector_heat_and_frozen_mark_tamper(tmp_path):
    repo, run=setup_repo(tmp_path); initial=ledger("initial",BacktestPortfolioLedgerType.INITIAL_CAPITAL,cash=Decimal("100")); buy=ledger("buy",BacktestPortfolioLedgerType.HYPOTHETICAL_BUY,instrument="A",quantity=Decimal("5"),price=Decimal("10"),gross=Decimal("50"),cash=Decimal("-50")); sale=ledger("sale",BacktestPortfolioLedgerType.HYPOTHETICAL_SELL,instrument="A",quantity=Decimal("5"),price=Decimal("12"),gross=Decimal("60"),cash=Decimal("60"))
    closed=BacktestPortfolioReplayEngine(CALENDAR).reconstruct(run_id=run.backtest_run_id,step_number=1,at=T,starting_capital=Decimal("100"),events=(initial,buy,sale),prices=())
    assert not closed.snapshot.holdings and closed.snapshot.cash.amount == Decimal("110") and closed.snapshot.realized_pnl == Decimal("10")
    stale=BacktestPortfolioReplayEngine(CALENDAR).reconstruct(run_id=run.backtest_run_id,step_number=1,at=T,starting_capital=Decimal("100"),events=(initial,buy),prices=(PriceReference("stale","A",Decimal("99"),T,T,stale=True),))
    assert "STALE_MARK" in stale.warnings and stale.snapshot.holdings[0].market_value is None
    with_stop=replace(buy,ledger_event_id="buy-stop",structural_stop=Decimal("8"))
    marked=BacktestPortfolioReplayEngine(CALENDAR).reconstruct(run_id=run.backtest_run_id,step_number=1,at=T,starting_capital=Decimal("100"),events=(initial,with_stop),prices=(PriceReference("p1","A",Decimal("10"),T,T),))
    assert marked.snapshot.holdings[0].sector == "UNKNOWN" and marked.snapshot.risk.heat_coverage == Decimal("1") and marked.snapshot.risk.total_heat == Decimal(".1")


def _persisted_marked_state(tmp_path):
    repo, run=setup_repo(tmp_path); initial=ledger("initial",BacktestPortfolioLedgerType.INITIAL_CAPITAL,cash=Decimal("100")); buy=ledger("buy",BacktestPortfolioLedgerType.HYPOTHETICAL_BUY,instrument="A",quantity=Decimal("5"),price=Decimal("10"),gross=Decimal("50"),cash=Decimal("-50"))
    for event in (initial,buy): repo.append_backtest_portfolio_ledger_event(event)
    state=BacktestPortfolioReplayService(repo,CALENDAR).reconstruct_and_persist(run_id=run.backtest_run_id,step_number=1,at=T,starting_capital=Decimal("100"),events=(initial,buy),prices=(PriceReference("P1","A",Decimal("12"),T,T),))
    return repo, run, state


def test_future_price_and_corporate_actions_do_not_change_frozen_portfolio_state(tmp_path):
    repo, run, state=_persisted_marked_state(tmp_path)
    before=repo.get_backtest_portfolio_state(state.backtest_portfolio_state_id)
    future=T + timedelta(days=1)
    future_split=ledger("future-split",BacktestPortfolioLedgerType.SPLIT,instrument="A",ratio=Decimal("2"),at=future)
    future_bonus=ledger("future-bonus",BacktestPortfolioLedgerType.BONUS,instrument="A",ratio=Decimal("1"),at=future)
    repo.append_backtest_portfolio_ledger_event(future_split); repo.append_backtest_portfolio_ledger_event(future_bonus)
    # P2 is deliberately not supplied to the frozen-state audit path.
    p2=PriceReference("P2","A",Decimal("99"),future,future)
    assert p2.observation_id not in state.price_reference_ids and "future-split" not in state.source_ledger_ids and "future-bonus" not in state.source_ledger_ids
    assert repo.get_backtest_portfolio_state(state.backtest_portfolio_state_id) == before
    assert AuditReconstructionService(repo).reconstruct_backtest_portfolio_state(state.backtest_portfolio_state_id,CALENDAR) == before


def test_accounting_and_frozen_mark_tampering_fail_audit(tmp_path):
    repo, _run, state=_persisted_marked_state(tmp_path)
    import json
    from app.backtest.portfolio import state_dump
    bad_snapshot=replace(state.snapshot,cash=replace(state.snapshot.cash,amount=Decimal("999")))
    accounting_tamper=replace(state,snapshot=bad_snapshot)
    repo._connection.execute("UPDATE backtest_portfolio_states SET payload_json=? WHERE id=?",(json.dumps(state_dump(accounting_tamper)),state.backtest_portfolio_state_id)); repo._connection.commit()
    with pytest.raises(AuditReconstructionError,match="mismatch"): AuditReconstructionService(repo).reconstruct_backtest_portfolio_state(state.backtest_portfolio_state_id,CALENDAR)
    # Keep the canonical snapshot but corrupt the frozen valuation input.
    bad_mark=replace(state.frozen_price_marks[0],observation_id="tampered-P1")
    mark_tamper=replace(state,frozen_price_marks=(bad_mark,))
    repo._connection.execute("UPDATE backtest_portfolio_states SET payload_json=? WHERE id=?",(json.dumps(state_dump(mark_tamper)),state.backtest_portfolio_state_id)); repo._connection.commit()
    with pytest.raises(AuditReconstructionError,match="mismatch"): AuditReconstructionService(repo).reconstruct_backtest_portfolio_state(state.backtest_portfolio_state_id,CALENDAR)
