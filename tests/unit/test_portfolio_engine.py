from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest

from app.gates.engine import ExchangeCalendar
from app.portfolio.engine import PortfolioEngine
from app.portfolio.models import (
    CashPosition, CorporateAction, CorporateActionType, HoldingAnalytics, Portfolio,
    PortfolioDataStatus, PortfolioState, PortfolioTransaction, PortfolioStatus, PriceReference, TransactionType,
)


T0 = datetime(2026, 8, 3, 10, tzinfo=UTC)
ASOF = datetime(2026, 8, 20, 10, tzinfo=UTC)
ENGINE = PortfolioEngine(ExchangeCalendar("nse-mock-v1", frozenset({date(2026, 8, 19)})))
PORTFOLIO = Portfolio("portfolio-1", "Mock Delivery", "INR", T0, "strategy/0.1", None, PortfolioStatus.ACTIVE, {})
CASH = CashPosition(Decimal("20000"), "INR", Decimal("0"), T0)


def tx(identifier, kind, *, instrument="stock", quantity=None, price=None, gross=Decimal("0"), cash=Decimal("0"), when=T0, known=None, fees=Decimal("0"), taxes=Decimal("0")):
    return PortfolioTransaction(identifier, PORTFOLIO.portfolio_id, kind, when, known or when, "mock-ledger", identifier,
        instrument, quantity, price, gross, fees, taxes, cash)


def price(value=Decimal("120"), when=ASOF, identifier="price-1", known=None):
    return PriceReference(identifier, "stock", value, when, known or when)


def analysis(stop=Decimal("90"), score=Decimal("8.8"), when=ASOF, known=None, sector="TECH", scorecard_id="score-1", gate_id="gate-1"):
    return HoldingAnalytics("stock", when, known or when, scorecard_id, score, "COMPLETE", .9, gate_id, "EXECUTABLE", structural_stop=stop, sector=sector)


def build(transactions=(), actions=(), prices=(price(),), analytics=(analysis(),), asof=ASOF):
    return ENGINE.reconstruct(portfolio=PORTFOLIO, as_of_timestamp=asof, initial_cash=CASH, transactions=tuple(transactions), actions=tuple(actions), prices=tuple(prices), analytics=tuple(analytics))


def buy100():
    return tx("buy-100", TransactionType.BUY, quantity=Decimal("100"), price=Decimal("100"), gross=Decimal("10000"), cash=Decimal("-10000"))


def test_all_cash_is_a_valid_portfolio_state_without_stock():
    snap = build(prices=(), analytics=())
    assert snap.portfolio_state is PortfolioState.ALL_CASH and snap.cash.available_amount == Decimal("20000") and not snap.holdings


def test_weighted_average_cost_add_partial_reduction_and_full_exit():
    add = tx("add-50", TransactionType.ADD, quantity=Decimal("50"), price=Decimal("130"), gross=Decimal("6500"), cash=Decimal("-6500"), when=T0 + timedelta(days=1))
    partial = tx("sell-60", TransactionType.SELL, quantity=Decimal("60"), price=Decimal("140"), gross=Decimal("8400"), cash=Decimal("8400"), when=T0 + timedelta(days=2))
    snap = build((buy100(), add, partial))
    holding = snap.holdings[0]
    assert holding.quantity == Decimal("90") and holding.average_cost == Decimal("110") and holding.cost_basis == Decimal("9900")
    assert holding.realized_pnl == Decimal("1800")
    exit_tx = tx("exit", TransactionType.SELL, quantity=Decimal("90"), price=Decimal("120"), gross=Decimal("10800"), cash=Decimal("10800"), when=T0 + timedelta(days=3))
    exited = build((buy100(), add, partial, exit_tx), prices=(), analytics=())
    assert not exited.holdings and exited.realized_pnl == Decimal("2700") and exited.portfolio_state is PortfolioState.ALL_CASH


def test_split_and_bonus_preserve_total_cost_and_adjust_per_share_cost():
    split = CorporateAction("split", PORTFOLIO.portfolio_id, "stock", CorporateActionType.SPLIT, Decimal("2"), T0 + timedelta(days=1), T0 + timedelta(days=1), "mock", "split")
    post_split = build((buy100(),), (split,), prices=(price(Decimal("60")),))
    assert post_split.holdings[0].quantity == Decimal("200") and post_split.holdings[0].average_cost == Decimal("50") and post_split.holdings[0].cost_basis == Decimal("10000")
    bonus = CorporateAction("bonus", PORTFOLIO.portfolio_id, "stock", CorporateActionType.BONUS, Decimal("1"), T0 + timedelta(days=1), T0 + timedelta(days=1), "mock", "bonus")
    post_bonus = build((buy100(),), (bonus,), prices=(price(Decimal("60")),))
    assert post_bonus.holdings[0].quantity == Decimal("200") and post_bonus.holdings[0].average_cost == Decimal("50")


def test_dividend_is_separate_cash_flow_not_mark_to_market_pnl():
    dividend = tx("dividend", TransactionType.DIVIDEND, instrument=None, gross=Decimal("200"), cash=Decimal("200"), when=T0 + timedelta(days=1))
    snap = build((buy100(), dividend))
    assert snap.dividends == Decimal("200") and snap.holdings[0].unrealized_pnl == Decimal("2000") and snap.cash.amount == Decimal("10200")


def test_missing_price_is_partial_and_does_not_fabricate_market_value_or_heat():
    snap = build((buy100(),), prices=(), analytics=(analysis(stop=None),))
    assert snap.holdings[0].market_value is None and snap.portfolio_equity is None
    assert snap.risk.total_heat is None and snap.risk.status is PortfolioDataStatus.PARTIAL


def test_invalid_or_stale_price_is_excluded_from_valuation():
    stale = PriceReference("stale-price", "stock", Decimal("999"), ASOF, ASOF, valid=True, stale=True)
    invalid = PriceReference("invalid-price", "stock", Decimal("999"), ASOF, ASOF, valid=False)
    snap = build((buy100(),), prices=(stale, invalid))
    assert snap.holdings[0].market_value is None and snap.data_status is PortfolioDataStatus.PARTIAL


def test_unknown_sector_is_retained_in_exposure_denominator():
    snap = build((buy100(),), analytics=(analysis(sector=None),))
    assert "UNKNOWN" in snap.exposure.sector_exposure and snap.exposure.sector_exposure["UNKNOWN"] == Decimal(6) / Decimal(11)


def test_missing_analytics_is_unavailable_not_a_fabricated_score_or_stop():
    snap = build((buy100(),), analytics=())
    assert snap.holdings[0].analytics is None and snap.holdings[0].risk_amount is None


def test_holding_age_uses_calendar_sessions_separately_from_days():
    snap = build((buy100(),))
    assert snap.holdings[0].calendar_holding_days == 17 and snap.holdings[0].trading_sessions_held == 12


def test_future_events_prices_analytics_stops_and_sector_do_not_change_earlier_snapshot():
    current = build((buy100(),), prices=(price(),), analytics=(analysis(),))
    future = T0 + timedelta(days=30)
    future_buy = tx("future-buy", TransactionType.BUY, quantity=Decimal("10"), price=Decimal("200"), gross=Decimal("2000"), cash=Decimal("-2000"), when=future)
    future_sell = tx("future-sell", TransactionType.SELL, quantity=Decimal("50"), price=Decimal("150"), gross=Decimal("7500"), cash=Decimal("7500"), when=future)
    split = CorporateAction("future-split", PORTFOLIO.portfolio_id, "stock", CorporateActionType.SPLIT, Decimal("2"), future, future, "mock", "future-split")
    bonus = CorporateAction("future-bonus", PORTFOLIO.portfolio_id, "stock", CorporateActionType.BONUS, Decimal("1"), future, future, "mock", "future-bonus")
    future_price = price(Decimal("999"), future, "future-price")
    future_analysis = analysis(Decimal("150"), Decimal("10"), future, future, "FUTURE-SECTOR", "future-score", "future-gate")
    reconstructed = build((buy100(), future_buy, future_sell), (split, bonus), (price(), future_price), (analysis(), future_analysis))
    assert current == reconstructed
    assert "future" not in str(reconstructed)


def test_future_known_data_cannot_bypass_asof_even_if_effective_earlier():
    late_price = price(Decimal("999"), ASOF - timedelta(days=1), "late-price", ASOF + timedelta(days=1))
    late_analysis = analysis(Decimal("999"), Decimal("10"), ASOF - timedelta(days=1), ASOF + timedelta(days=1), "LATE")
    snap = build((buy100(),), prices=(price(), late_price), analytics=(analysis(), late_analysis))
    assert snap.holdings[0].current_price == Decimal("120") and snap.holdings[0].analytics.sector == "TECH"


def test_portfolio_engine_exposes_state_but_has_no_rotation_decision_api():
    snap = build((buy100(),))
    assert snap.exposure.concentration == Decimal(6) / Decimal(11) and not hasattr(snap, "recommendation") and not hasattr(ENGINE, "rotate")


def test_invalid_reduction_is_rejected_not_rewritten():
    invalid = tx("too-much", TransactionType.SELL, quantity=Decimal("101"), price=Decimal("120"), gross=Decimal("12120"), cash=Decimal("12120"))
    with pytest.raises(ValueError): build((buy100(), invalid))
