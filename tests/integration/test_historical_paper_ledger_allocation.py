from datetime import timedelta
from decimal import Decimal

import pytest

from app.backtest.capital_allocation import AllocationPolicy, HistoricalPaperLedgerIntegrationService, PaperFillCandidate
from app.backtest.models import BacktestEvent, BacktestEventType, FrozenSizingSpecification, PaperTradingConfigSnapshot
from app.historical.guard import manifest_fingerprint
from app.paper.models import SizingBasis
from app.backtest.portfolio import BacktestPortfolioLedgerEvent, BacktestPortfolioLedgerType, BacktestPortfolioReplayService
from app.portfolio.models import PriceReference
from app.services.audit_reconstruction_service import AuditReconstructionError, AuditReconstructionService
from tests.integration.test_historical_analytical_replay import CALENDAR, setup
from tests.integration.test_historical_signal_paper_chronology_matrix import through_timing, bar, T


def initial(run, amount):
    return BacktestPortfolioLedgerEvent("allocation-initial", run.backtest_run_id, BacktestPortfolioLedgerType.INITIAL_CAPITAL, T, T, "fixture", "capital", None, None, None, Decimal("0"), Decimal("0"), Decimal("0"), amount)


def funded_candidate(signal_id="signal-a"):
    entry=bar("allocation-entry", T + timedelta(days=1), "106", "108", "105", "106")
    target=bar("allocation-target", T + timedelta(days=4), "106", "140", "105", "135")
    signal, _timing, trade, _events, fills, outcome=through_timing(bars=(bar("allocation-trigger", T, "100", "106", "99", "106"),entry,target),replay_at=target.timestamp)
    return PaperFillCandidate(signal_id,trade,outcome,fills[0],Decimal("9"),.9,Decimal("3"),"TECH"), signal, trade, fills[0], outcome


def test_filled_paper_trade_allocates_backtest_only_ledger_and_reconciles_outcome(tmp_path):
    repo, _manifest, schedule, _gap, run, _config=setup(tmp_path); repo.save_replay_schedule(schedule); repo.save_backtest_run(run)
    repo.append_backtest_event(BacktestEvent("allocation-start",run.backtest_run_id,BacktestEventType.REPLAY_STARTED,T,0,T,(),"start",{},T))
    first=initial(run,Decimal("1000")); repo.append_backtest_portfolio_ledger_event(first)
    candidate, signal, trade, fill, outcome=funded_candidate()
    repo.save_signal(signal); repo.save_paper_trade(trade); repo.save_paper_outcome(outcome); repo.append_paper_fill(fill)
    service=HistoricalPaperLedgerIntegrationService(repo,policy=AllocationPolicy("allocation-v1"))
    applied=service.allocate_fills(run=run,replay_step_number=2,at=fill.timestamp,starting_capital=Decimal("1000"),existing_ledger_events=(first,),candidates=(candidate,))
    link=applied.links[0]
    assert applied.allocation.selected_signal_ids == (candidate.signal_id,) and applied.ledger_events[0].net_cash_impact < 0
    settled=service.settle_outcome(run=run,replay_step_number=3,at=outcome.final_exit_timestamp,link=link,trade=trade,outcome=outcome,initial_fill=fill)
    ledger=repo.list_backtest_portfolio_ledger_events(run.backtest_run_id)
    assert settled.final_exit_ledger_event_id is not None and sum(x.net_cash_impact for x in ledger) == Decimal("1000") + settled.exit_proceeds - settled.entry_value - settled.costs
    state=BacktestPortfolioReplayService(repo,CALENDAR).reconstruct_and_persist(run_id=run.backtest_run_id,step_number=3,at=outcome.final_exit_timestamp,starting_capital=Decimal("1000"),events=ledger,prices=())
    assert not state.snapshot.holdings and state.snapshot.cash.available_amount > Decimal("1000")
    assert AuditReconstructionService(repo).reconstruct_historical_capital_allocation(applied.allocation.allocation_id,allocation_policy_version="allocation-v1")[0] == applied.allocation


def test_ranking_cash_reservation_is_deterministic_and_rejects_insufficient_or_unsupported_sizing(tmp_path):
    repo, _manifest, schedule, _gap, run, _config=setup(tmp_path); repo.save_replay_schedule(schedule); repo.save_backtest_run(run)
    repo.append_backtest_event(BacktestEvent("allocation-start",run.backtest_run_id,BacktestEventType.REPLAY_STARTED,T,0,T,(),"start",{},T))
    first=initial(run,Decimal("150")); repo.append_backtest_portfolio_ledger_event(first)
    base, signal, trade, fill, outcome=funded_candidate("signal-b"); repo.save_signal(signal); repo.save_paper_trade(trade); repo.save_paper_outcome(outcome); repo.append_paper_fill(fill)
    lower=PaperFillCandidate("signal-c",trade,outcome,fill,Decimal("8"),.9,Decimal("3"),"TECH")
    unsupported=PaperFillCandidate("signal-d",trade,outcome,fill,Decimal("10"),.9,Decimal("3"),"TECH","FIXED_NOTIONAL")
    service=HistoricalPaperLedgerIntegrationService(repo,policy=AllocationPolicy("allocation-v1"))
    applied=service.allocate_fills(run=run,replay_step_number=2,at=fill.timestamp,starting_capital=Decimal("150"),existing_ledger_events=(first,),candidates=(lower,base,unsupported))
    assert applied.allocation.selected_signal_ids == ("signal-b",) and set(applied.allocation.rejected_signal_ids) == {"signal-c","signal-d"}
    assert applied.allocation.available_cash_before - applied.allocation.reserved_capital >= 0
    with pytest.raises(ValueError,match="immutable"): repo.save_historical_capital_allocation(applied.allocation)
    # A later cash adjustment is not part of the earlier immutable allocation.
    later=BacktestPortfolioLedgerEvent("future-cash",run.backtest_run_id,BacktestPortfolioLedgerType.CASH_ADJUSTMENT,fill.timestamp+timedelta(days=1),fill.timestamp+timedelta(days=1),"fixture","future",None,None,None,Decimal("0"),Decimal("0"),Decimal("0"),Decimal("10000"))
    repo.append_backtest_portfolio_ledger_event(later)
    assert repo.get_historical_capital_allocation(applied.allocation.allocation_id) == applied.allocation
    repo._connection.execute("UPDATE historical_capital_allocations SET payload_json=? WHERE id=?", (__import__("json").dumps(__import__("app.backtest.serialization",fromlist=["dump"]).dump(__import__("dataclasses").replace(applied.allocation,reserved_capital=Decimal("1")))),applied.allocation.allocation_id))
    with pytest.raises(AuditReconstructionError,match="cash reconciliation"):
        AuditReconstructionService(repo).reconstruct_historical_capital_allocation(applied.allocation.allocation_id,allocation_policy_version="allocation-v1")


def test_frozen_notional_and_risk_sizing_use_actual_gap_fill_and_fail_closed_without_capital(tmp_path):
    repo, _manifest, schedule, _gap, run, _config=setup(tmp_path); repo.save_replay_schedule(schedule); repo.save_backtest_run(run)
    repo.append_backtest_event(BacktestEvent("allocation-start",run.backtest_run_id,BacktestEventType.REPLAY_STARTED,T,0,T,(),"start",{},T))
    first=initial(run,Decimal("1000")); repo.append_backtest_portfolio_ledger_event(first)
    gap=bar("sizing-gap",T+timedelta(days=1),"106","107","105","106")
    signal, _timing, trade, _events, fills, outcome=through_timing(bars=(bar("sizing-trigger",T,"100","106","99","106"),gap),replay_at=gap.timestamp)
    repo.save_signal(signal); repo.save_paper_trade(trade); repo.save_paper_outcome(outcome); repo.append_paper_fill(fills[0])
    notional=FrozenSizingSpecification("FIXED_NOTIONAL",Decimal("1000"),None,"FLOOR_INTEGER",Decimal("1"),False,"INR","sizing-v1",manifest_fingerprint(notional="1000",basis="FIXED_NOTIONAL"))
    risk=FrozenSizingSpecification("FIXED_R_R",None,Decimal("90"),"FLOOR_INTEGER",Decimal("1"),False,"INR","sizing-v1",manifest_fingerprint(risk="90",basis="FIXED_R_R"))
    snapshot_a=PaperTradingConfigSnapshot("paper-sizing-a",__import__("dataclasses").replace(__import__("tests.unit.test_paper_trading",fromlist=["CFG"]).CFG,sizing_basis=SizingBasis.FIXED_NOTIONAL),T,("fixture",),manifest_fingerprint(config="a",sizing=notional.fingerprint),notional)
    snapshot_b=PaperTradingConfigSnapshot("paper-sizing-b",__import__("dataclasses").replace(__import__("tests.unit.test_paper_trading",fromlist=["CFG"]).CFG,sizing_basis=SizingBasis.FIXED_R_R),T,("fixture",),manifest_fingerprint(config="b",sizing=risk.fingerprint),risk)
    repo.save_paper_config_snapshot(snapshot_a); repo.save_paper_config_snapshot(snapshot_b)
    assert repo.get_paper_config_snapshot(snapshot_a.snapshot_id)==snapshot_a and repo.get_paper_config_snapshot(snapshot_b.snapshot_id)==snapshot_b
    notional_v2=__import__("dataclasses").replace(notional,fixed_notional_amount=Decimal("2000"),fingerprint=manifest_fingerprint(notional="2000",basis="FIXED_NOTIONAL"))
    risk_v2=__import__("dataclasses").replace(risk,fixed_risk_capital_amount=Decimal("180"),fingerprint=manifest_fingerprint(risk="180",basis="FIXED_R_R"))
    repo.save_paper_config_snapshot(__import__("dataclasses").replace(snapshot_a,snapshot_id="paper-sizing-a-v2",fingerprint=manifest_fingerprint(config="a-v2",sizing=notional_v2.fingerprint),sizing_specification=notional_v2))
    repo.save_paper_config_snapshot(__import__("dataclasses").replace(snapshot_b,snapshot_id="paper-sizing-b-v2",fingerprint=manifest_fingerprint(config="b-v2",sizing=risk_v2.fingerprint),sizing_specification=risk_v2))
    assert repo.get_paper_config_snapshot(snapshot_a.snapshot_id)==snapshot_a and snapshot_a.fingerprint != repo.get_paper_config_snapshot("paper-sizing-a-v2").fingerprint
    service=HistoricalPaperLedgerIntegrationService(repo,policy=AllocationPolicy("allocation-v1"))
    fixed=PaperFillCandidate("notional",trade,outcome,fills[0],Decimal("9"),.9,Decimal("3"),"TECH","FIXED_NOTIONAL",notional,snapshot_a.snapshot_id)
    applied=service.allocate_fills(run=run,replay_step_number=2,at=gap.timestamp,starting_capital=Decimal("1000"),existing_ledger_events=(first,),candidates=(fixed,))
    assert applied.links[0].quantity==Decimal("9") and applied.links[0].raw_quantity==Decimal("1000")/Decimal("106")
    assert applied.ledger_events[0].price==Decimal("106") and applied.links[0].required_cash==Decimal("954")
    assert AuditReconstructionService(repo).reconstruct_historical_paper_ledger_link(applied.links[0].link_id)[0] == applied.links[0]
    too_risky=PaperFillCandidate("risk",trade,outcome,fills[0],Decimal("10"),.9,Decimal("3"),"TECH","FIXED_R_R",risk,snapshot_b.snapshot_id)
    rejected=service.allocate_fills(run=run,replay_step_number=3,at=gap.timestamp,starting_capital=Decimal("1000"),existing_ledger_events=(first,*applied.ledger_events),candidates=(too_risky,))
    # 90 / (106 - 95) = 8 shares, but the existing notional entry has reserved cash.
    assert rejected.allocation.selected_signal_ids == () and rejected.allocation.rejected_signal_ids == ("risk",)
    missing=PaperFillCandidate("legacy",trade,outcome,fills[0],Decimal("11"),.9,Decimal("3"),"TECH","FIXED_NOTIONAL",None,None)
    legacy=service.allocate_fills(run=run,replay_step_number=4,at=gap.timestamp,starting_capital=Decimal("1000"),existing_ledger_events=(first,),candidates=(missing,))
    assert legacy.allocation.rejected_signal_ids == ("legacy",)
