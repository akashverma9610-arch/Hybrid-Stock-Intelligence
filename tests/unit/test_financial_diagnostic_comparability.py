from __future__ import annotations

import ast
from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal
from functools import lru_cache
import json
from pathlib import Path

import pytest

from app.analysis import fundamentals as existing
from app.analysis.models import AnalysisStatus
from app.analysis.valuation_trade import valuation, ValuationRules
from app.data_sources.models import FundamentalFactKind
from app.domain.models import AsOfSnapshot, DataQuality, Instrument, MarketObservation, ObservationKind, Provenance, ValidationResult, ValidationStatus
from app.filings.models import CorporateFiling, FilingType, PrimarySourceQuality
from app.fundamentals.diagnostic_comparability import (
    assemble_financial_comparability, canonical_json, ComparabilityState as S,
)
from app.fundamentals.diagnostic_input import CanonicalFinancialDiagnosticInput, APPROVED_FINANCIAL_RULE_IDS
from app.fundamentals.models import FinancialFact, FinancialMetric as M, FinancialPeriodType as P, FinancialValueBasis as B, NumericScale as Scale, StatementScope as Scope
from app.market_data.models import Exchange, InstrumentIdentity, InstrumentType, MarketDataProvenance

T = datetime(2026, 8, 31, 23, 59, 59, tzinfo=UTC)
ID = "NSE:INE372A01015"
INSTRUMENT = InstrumentIdentity(ID, Exchange.NSE, "APARINDS", "APARINDS", "INE372A01015", "EQ", InstrumentType.NSE_EQUITY, "Synthetic APAR")
RULES = existing.FundamentalRules(.1, -.1, .1, 1.5, 2, .02)


def fact(metric=M.REVENUE, *, year=2026, quarter=None, value=100, scope=Scope.CONSOLIDATED,
         basis=None, balance=False, suffix="", scale=Scale.UNITS, published=None):
    if quarter:
        end_month = (quarter * 3 + 3 - 1) % 12 + 1
        end_year = year if quarter == 4 else year - 1
        start_month = end_month - 2
        end = datetime(end_year, end_month, 31 if end_month in {3, 12} else 30, tzinfo=UTC)
        start = datetime(end_year, start_month, 1, tzinfo=UTC)
    else:
        start, end = datetime(year - 1, 4, 1, tzinfo=UTC), datetime(year, 3, 31, tzinfo=UTC)
    identifier = f"fact:{metric.value}:{year}:{quarter or 0}:{scope.value}:{suffix}"
    return FinancialFact(identifier, INSTRUMENT, metric, Decimal(str(value)), "INR", "INR", scale,
        P.POINT_IN_TIME if balance else P.QUARTERLY if quarter else P.ANNUAL,
        basis or (B.UNKNOWN if balance else B.QUARTER_ONLY if quarter else B.FULL_YEAR),
        None if balance else start, end, year, quarter, scope, FundamentalFactKind.REPORTED,
        "official-fixture", "filing:" + identifier, "fixture:" + identifier,
        published or T - timedelta(days=1), published or T - timedelta(days=1), "fixture-v1")


def filing(f):
    return CorporateFiling(f.filing_id, f.instrument, Exchange.BSE, f.source,
        PrimarySourceQuality.PRIMARY_EXCHANGE, FilingType.FINANCIAL_RESULTS, None, "Synthetic result",
        f.published_at, f.received_at, f.source_reference, None,
        MarketDataProvenance(f.source, f.source_reference, None, None, f.received_at, "fixture-v1"))


def comparable(values, *, as_of=T, **kwargs):
    return assemble_financial_comparability(tuple(values), tuple(filing(f) for f in values),
        canonical_instrument_id=ID, as_of=as_of, **kwargs)


def quarter_facts(metrics=(M.REVENUE, M.EBITDA, M.PAT, M.EPS_BASIC)):
    return tuple(fact(m, year=y, quarter=q, value=100 + i * 10)
        for i, (y, q) in enumerate(((2025, 1), (2025, 2), (2025, 3), (2025, 4), (2026, 1))) for m in metrics)


@lru_cache
def company():
    from tests.unit.test_pit_company_type_classification_activation import _forward, _taxonomy_receipt, _report
    forward = _forward()
    return _report(forward=forward, taxonomy=(_taxonomy_receipt(forward, macro="IN07", sector="IN0702"),)).receipts[0]


def inputs(values, *, classified=False, **kwargs):
    return CanonicalFinancialDiagnosticInput(comparable(values, **kwargs), company() if classified else None)


def market(*, as_of=T, received=None):
    at = T - timedelta(days=2)
    bar = MarketObservation("price:exact", Instrument(ID, "APARINDS", "NSE", INSTRUMENT.isin), ObservationKind.PRICE_BAR,
        {"open": 100., "high": 101., "low": 99., "close": 100.},
        Provenance("stored_canonical", "source:price", at, received or at, DataQuality.HIGH),
        ValidationResult(ValidationStatus.VALID, as_of))
    return AsOfSnapshot("market:explicit", as_of, as_of, "fixture", (bar,))


def series(value, metric=M.REVENUE, period=P.ANNUAL, basis=B.FULL_YEAR):
    return value.series(metric, period, basis)


def test_same_scope_units_annual_series_and_immutable_content():
    c = comparable((fact(year=2025), fact(year=2026)))
    assert series(c).state is S.READY
    assert len(series(c).observations) == 2
    with pytest.raises(FrozenInstanceError):
        c.scope = Scope.STANDALONE
    with pytest.raises(ValueError, match="FINGERPRINT"):
        replace(c, fingerprint="sha256:" + "0" * 64)


def test_scope_cannot_fill_missing_consolidated_period_from_standalone():
    c = comparable((fact(year=2024), fact(year=2025, scope=Scope.STANDALONE), fact(year=2026)))
    assert c.scope is Scope.CONSOLIDATED
    assert series(c).state is S.INSUFFICIENT_DATA
    assert "MISSING_OR_NONCOMPARABLE_FISCAL_PERIOD" in series(c).reasons
    assert all(o.statement_scope is Scope.CONSOLIDATED for o in series(c).observations)


@pytest.mark.parametrize("change", ({"scale": Scale.CRORES}, {"currency": "USD"}, {"unit": "UNKNOWN"}, {"normalization_version": "other"}))
def test_unit_currency_and_basis_mismatch_fail_closed(change):
    c = comparable((fact(year=2025), replace(fact(year=2026), **change)))
    assert series(c).state is S.INSUFFICIENT_DATA


def test_annual_quarter_ytd_and_unknown_never_substitute():
    quarter = fact(quarter=1)
    ytd = replace(quarter, fact_id="fact:ytd", filing_id="filing:ytd", value_basis=B.YEAR_TO_DATE)
    c = comparable((quarter, ytd, fact()))
    assert len(series(c).observations) == 1
    assert len(series(c, period=P.QUARTERLY, basis=B.QUARTER_ONLY).observations) == 1
    assert len(series(c, period=P.QUARTERLY, basis=B.YEAR_TO_DATE).observations) == 1
    assert c.vintage.status_counts[0][1] >= 0
    only_ytd = inputs((ytd,)).rule_input(24)
    assert only_ytd.snapshot is None


def test_exact_yoy_qoq_and_no_missing_period_interpolation():
    value = inputs(quarter_facts()).rule_input(25)
    assert value.state is S.READY
    result = existing.latest_quarter(value.snapshot, ID, RULES)
    assert dict(result.details)["revenue_yoy"] == str(140 / 100 - 1)
    assert dict(result.details)["revenue_qoq"] == str(140 / 130 - 1)
    broken = tuple(f for f in quarter_facts() if f.fiscal_quarter != 3)
    assert inputs(broken).rule_input(25).snapshot is None


@pytest.mark.parametrize("change", ({"fiscal_year": 2040}, {"fiscal_quarter": 2}, {"period_start": None}))
def test_fiscal_identity_cannot_be_replaced_by_timestamp_proximity(change):
    facts = quarter_facts((M.REVENUE,))
    facts = facts[:-1] + (replace(facts[-1], **change),)
    assert inputs(facts).rule_input(24).snapshot is None


def test_late_restatement_explicit_parent_pit_and_deterministic_replay():
    original = fact(value=100)
    revised = replace(original, fact_id="fact:revision", filing_id="filing:revision", value=Decimal(150),
        revision_of_fact_id=original.fact_id, published_at=T + timedelta(days=1), received_at=T + timedelta(days=2))
    before = comparable((original, revised))
    assert series(before).observations[0].value == 100
    middle = comparable((original, revised), as_of=T + timedelta(days=1))
    assert series(middle).observations[0].value == 100
    after = comparable((original, revised), as_of=T + timedelta(days=2))
    assert series(after).observations[0].value == 150
    assert after == comparable((revised, original), as_of=T + timedelta(days=2))
    assert original.fact_id in after.vintage.selections[0].revision_lineage_fact_ids


def test_conflicting_vintage_never_chooses_latest_max_or_average():
    a = fact()
    b = replace(a, fact_id="fact:conflict", filing_id="filing:conflict", value=Decimal(999))
    c = comparable((a, b))
    assert series(c).state is S.EVIDENCE_CONFLICTED
    assert series(c).observations == ()
    assert CanonicalFinancialDiagnosticInput(c).rule_input(16).state is S.EVIDENCE_CONFLICTED


def test_duplicate_input_replay_is_explicit_and_conflicting_identity_rejected():
    a = fact()
    assert comparable((a, a)) == comparable((a,))
    with pytest.raises(ValueError, match="DUPLICATE_ID_CONFLICT"):
        comparable((a, replace(a, value=Decimal(999))))


def test_rule16_six_points_and_direct_ebitda_required():
    all_facts = tuple(fact(m, year=y, value=100 + (y-2021)*10)
        for y in range(2021, 2027) for m in (M.REVENUE, M.EBITDA, M.PAT, M.EPS_BASIC))
    complete = inputs(all_facts).rule_input(16)
    assert complete.state is S.READY
    assert existing.five_year_trend(complete.snapshot, ID, RULES).status is AnalysisStatus.VALID
    assert inputs(tuple(f for f in all_facts if f.fiscal_year != 2021)).rule_input(16).snapshot is None
    assert inputs(tuple(f for f in all_facts if f.metric is not M.EBITDA)).rule_input(16).snapshot is None
    substituted = tuple(replace(f, metric=M.OPERATING_PROFIT) if f.metric is M.EBITDA else f for f in all_facts)
    assert inputs(substituted).rule_input(16).snapshot is None


def test_rule17_exact_balance_end_alignment_and_existing_ending_fallback():
    facts = (fact(M.PAT), fact(M.EBIT), fact(M.TOTAL_EQUITY, balance=True, value=1000),
        fact(M.TOTAL_DEBT, balance=True, value=100), fact(M.CASH_AND_EQUIVALENTS, balance=True, value=10))
    value = inputs(facts, classified=True).rule_input(17)
    assert value.state is S.READY
    assert "ending equity" in dict(existing.return_ratios(value.snapshot, ID, RULES).details)["roe_basis"]
    bad = facts[:2] + (replace(facts[2], period_end=facts[2].period_end - timedelta(days=1)),) + facts[3:]
    assert inputs(bad, classified=True).rule_input(17).snapshot is None


def test_rule18_missing_capex_is_not_cfo_complete_and_sign_not_invented():
    data = (fact(M.CFO), fact(M.PAT))
    value = inputs(data, classified=True).rule_input(18)
    assert value.snapshot is None
    assert dict((m, s) for m, s, _ in value.metric_states)[M.CFO.value] is S.READY
    direct = inputs(data + (fact(M.CAPEX, value=-10),), classified=True).rule_input(18)
    assert "POLICY_DEFINITION_MISSING:CAPEX_SIGN_BRIDGE" in direct.reasons


def test_rule19_missing_debt_does_not_use_zero_or_borrowing_components():
    facts = tuple(fact(m, balance=m in {M.TOTAL_EQUITY, M.CASH_AND_EQUIVALENTS})
        for m in (M.EBIT, M.FINANCE_COST, M.TOTAL_EQUITY, M.CASH_AND_EQUIVALENTS))
    facts += (fact(M.CURRENT_BORROWINGS, balance=True), fact(M.NONCURRENT_BORROWINGS, balance=True))
    assert inputs(facts, classified=True).rule_input(19).snapshot is None


def test_rule20_missing_is_not_not_applicable_and_dso_partial_requires_exact_balances():
    empty = inputs((fact(),), classified=True).rule_input(20)
    assert empty.state is S.INSUFFICIENT_DATA
    partial = inputs((fact(), fact(M.RECEIVABLES, balance=True)), classified=True).rule_input(20)
    assert partial.state is S.PARTIAL
    assert existing.working_capital(partial.snapshot, ID, RULES).state == "PARTIAL"


def test_rule24_organic_remains_unassessed_and_ytd_does_not_conflict_with_quarter():
    data = quarter_facts((M.REVENUE,))
    ytd = replace(data[-1], fact_id="fact:ytd", filing_id="filing:ytd", value_basis=B.YEAR_TO_DATE)
    value = inputs(data + (ytd,)).rule_input(24)
    assert value.state is S.PARTIAL
    result = existing.earnings_acceleration(value.snapshot, ID, RULES)
    assert "unassessed" in dict(result.details)["quality"]


def test_rule25_partial_metrics_and_rule26_no_ebitda_or_gross_substitution():
    facts = quarter_facts((M.REVENUE, M.PAT, M.EPS_BASIC))
    partial = inputs(facts).rule_input(25)
    assert partial.state is S.PARTIAL
    assert "ebitda" not in canonical_json(partial.snapshot.observations[0].payload)
    missing = inputs(facts, classified=True).rule_input(26)
    assert missing.snapshot is None
    complete_operating = inputs(quarter_facts(), classified=True).rule_input(26)
    assert complete_operating.state is S.PARTIAL


def test_rule29_pe_partial_no_forward_shares_growth_or_ev_defaults():
    value = inputs((fact(M.EPS_BASIC, value=5), fact(M.SHARES_OUTSTANDING, value=100), fact(M.EBITDA))).rule_input(29, market())
    assert value.state is S.PARTIAL
    result = valuation(market(), value.snapshot, ID, ValuationRules(15, 35))
    assert dict(result.details)["pe"] == "20.0"
    for name in ("forward_pe", "peg", "ev_ebitda", "pb"):
        assert dict(result.details)[name].startswith("UNAVAILABLE")
    assert "shares_outstanding" not in value.snapshot.observations[0].payload


@pytest.mark.parametrize("case", ("future_price", "different_asof", "future_filing", "scaled_eps"))
def test_rule29_price_and_financial_visibility_alignment(case):
    f = fact(M.EPS_BASIC, value=5)
    m = market()
    if case == "future_price":
        m = market(received=T + timedelta(seconds=1))
    elif case == "different_asof":
        m = market(as_of=T - timedelta(days=2))
    elif case == "future_filing":
        f = replace(f, published_at=T + timedelta(seconds=1), received_at=T + timedelta(seconds=1))
    else:
        f = replace(f, scale=Scale.CRORES)
    assert inputs((f,)).rule_input(29, m).snapshot is None


def test_company_type_missing_never_defaults_to_industrial_or_not_applicable():
    for rule in (17, 18, 19, 20, 26):
        value = inputs(quarter_facts() + (fact(),)).rule_input(rule)
        assert value.state is S.POLICY_BLOCKED
        assert value.state is not S.NOT_APPLICABLE
    with pytest.raises(ValueError, match="PIT_MISMATCH"):
        CanonicalFinancialDiagnosticInput(comparable((fact(),), as_of=T + timedelta(days=1)), company())


def test_deterministic_fingerprint_utc_serialization_and_postconstruction_tampering():
    a = fact()
    shifted = replace(a, published_at=a.published_at.astimezone(timezone(timedelta(hours=5, minutes=30))),
        received_at=a.received_at.astimezone(timezone(timedelta(hours=5, minutes=30))))
    first, second = comparable((a,)), comparable((shifted,), as_of=T.astimezone(timezone(timedelta(hours=-4))))
    assert first.fingerprint == second.fingerprint
    assert json.loads(canonical_json(first)) == json.loads(canonical_json(second))
    object.__setattr__(first.observations[0], "value", Decimal(888))
    with pytest.raises(ValueError, match="FINGERPRINT"):
        CanonicalFinancialDiagnosticInput(first)


def test_non_primary_missing_and_mismatched_filing_do_not_materialize():
    f = fact()
    no_filing = assemble_financial_comparability((f,), (), canonical_instrument_id=ID, as_of=T)
    assert series(no_filing).state is S.INSUFFICIENT_DATA
    wrong = replace(filing(f), received_at=T + timedelta(days=1))
    c = assemble_financial_comparability((f,), (wrong,), canonical_instrument_id=ID, as_of=T)
    assert series(c).observations == ()


def test_source_cap_and_out_of_scope_fail_closed():
    c = comparable((fact(),), complete_input=False)
    assert "SOURCE_COMPLETENESS_UNPROVEN" in series(c).reasons
    for rule in (15, 21, 22, 23, 27, 28, 30, 31, 34, 61):
        with pytest.raises(ValueError, match="OUT_OF_SCOPE"):
            CanonicalFinancialDiagnosticInput(c).rule_input(rule)
    assert APPROVED_FINANCIAL_RULE_IDS == (16, 17, 18, 19, 20, 24, 25, 26, 29)


def test_same_canonical_id_cannot_mix_different_isins():
    one, two = fact(year=2025), fact(year=2026)
    two = replace(two, instrument=replace(INSTRUMENT, isin="INE000A01001"))
    with pytest.raises(ValueError, match="IDENTITY_CONFLICT"):
        comparable((one, two))


def test_valuation_input_fingerprint_binds_market_content_too():
    value = inputs((fact(M.EPS_BASIC, value=5),))
    first = market()
    second = replace(first, observations=(replace(first.observations[0], payload={**first.observations[0].payload, "close": 99.}),))
    assert value.rule_input(29, first).fingerprint != value.rule_input(29, second).fingerprint


def test_boundary_modules_have_no_clock_network_storage_or_trade_calls():
    for path in ("app/fundamentals/diagnostic_comparability.py", "app/fundamentals/diagnostic_input.py"):
        tree = ast.parse(Path(path).read_text(encoding="utf-8"))
        imports = [n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)]
        assert not any(x.startswith(("app.portfolio", "app.api", "app.runtime", "app.broker", "app.orders", "app.storage")) for x in imports)
        calls = {n.func.attr for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}
        assert not calls & {"now", "utcnow", "connect", "execute", "save", "write_text", "submit_order"}


@pytest.mark.parametrize("kind", ("BANK", "NBFC", "INSURER"))
def test_financial_company_branches_require_policy_not_industrial_formulas(kind):
    from tests.unit.test_pit_company_type_classification_activation import _forward, _regulator, _raw_link, _report, regulator_source
    source, category = {
        "BANK": ("RBI_SCHEDULED_COMMERCIAL_BANKS", "SCHEDULED_COMMERCIAL_BANK"),
        "NBFC": ("RBI_REGISTERED_NBFC_ARC", "RBI_REGISTERED_NBFC"),
        "INSURER": ("IRDAI_LIFE_INSURERS", "IRDAI_LIFE_INSURER"),
    }[kind]
    forward = _forward()
    evidence = _regulator(source=regulator_source.RegulatorEvidenceSource(source),
        kind=regulator_source.RegulatorEntityEvidenceKind(category), cin=forward.cin)
    receipt = _report(forward=forward, links=(_raw_link(forward, evidence),), evidence=(evidence,)).receipts[0]
    value = CanonicalFinancialDiagnosticInput(comparable((fact(),)), receipt).rule_input(20)
    assert value.state is S.POLICY_BLOCKED
    assert "POLICY_DEFINITION_MISSING:" + kind + "_RULE_BRANCH" in value.reasons


def test_cross_metric_units_and_wrong_balance_fiscal_year_block_ratios():
    data = (fact(M.PAT), fact(M.EBIT), fact(M.TOTAL_EQUITY, balance=True, value=1000),
        fact(M.TOTAL_DEBT, balance=True), fact(M.CASH_AND_EQUIVALENTS, balance=True))
    assert inputs(data[:-1] + (replace(data[-1], scale=Scale.CRORES),), classified=True).rule_input(17).snapshot is None
    assert inputs(data[:-1] + (replace(data[-1], fiscal_year=2025),), classified=True).rule_input(17).snapshot is None


def test_missing_recent_metric_does_not_retreat_to_older_period():
    data = quarter_facts((M.REVENUE,))
    newer = fact(M.PAT, year=2026, quarter=2)
    assert inputs(data + (newer,)).rule_input(24).snapshot is None


def test_unrelated_older_gap_does_not_poison_exact_requested_five_quarters():
    older = fact(M.REVENUE, year=2022, quarter=4)
    current = inputs(quarter_facts((M.REVENUE,)) + (older,)).rule_input(24)
    assert current.state is S.PARTIAL
    assert older.fact_id not in current.fact_ids


def test_actual_runner_uses_comparable_input_only_for_approved_rules():
    from app.universe_analysis.service import Canonical61DiagnosticRunner, StockDiagnosticInputAssembler
    from app.universe_analysis.models import NseEquityInstrument
    from types import SimpleNamespace
    from app.registry.canonical import DIAGNOSTIC_RULES
    before_registry = canonical_json(DIAGNOSTIC_RULES)
    instrument = NseEquityInstrument(instrument_id=ID, symbol="APARINDS", company_name="Synthetic", isin=INSTRUMENT.isin,
        exchange="NSE", sector=None, industry=None, listing_status="LISTED", listing_date=None, tradable=True, data_as_of=T, source="fixture")
    source = SimpleNamespace(observations_as_of=lambda _: ())
    financial = inputs(quarter_facts())
    evidence = StockDiagnosticInputAssembler(source).assemble(instrument, T, financial_input=financial)
    runner = Canonical61DiagnosticRunner()
    assert runner._evaluate(25, evidence, {}).record.result == "REPORTED"
    # Exact same evidence without financial input retains unrelated behavior.
    for rule in (15, 21, 22, 23, 27, 28, 30):
        assert runner._evaluate(rule, evidence, {}) == runner._evaluate(rule, replace(evidence, financial_input=None), {})
    assert canonical_json(DIAGNOSTIC_RULES) == before_registry
    conflict = quarter_facts()[0]
    extra = replace(conflict, fact_id="fact:conflicting", filing_id="filing:conflicting", value=Decimal(999))
    contaminated = replace(evidence, financial_input=inputs(quarter_facts() + (extra,)))
    result = runner._evaluate(25, contaminated, {})
    assert result.record.result == "EVIDENCE_CONFLICTED"
    assert result.eligibility.value == "ineligible_invalid_data"


def test_existing_stored_source_wires_adapter_and_keeps_legacy_observations(tmp_path):
    from types import SimpleNamespace
    from app.fundamentals.adapter import FundamentalsEngineAdapter
    from app.fundamentals.store import SQLiteFinancialFactStore
    from app.filings.store import SQLiteCorporateFilingsStore
    from app.real_brain.local import StoredTrialObservationSource
    from app.universe_analysis.service import StockDiagnosticInputAssembler
    from app.universe_analysis.models import NseEquityInstrument
    store = SQLiteFinancialFactStore(tmp_path / "isolated.sqlite")
    filings = SQLiteCorporateFilingsStore(tmp_path / "isolated.sqlite")
    for f in quarter_facts():
        filings.save(filing(f))
        store.save(f)
    adapter = FundamentalsEngineAdapter(store, filings)
    source = StoredTrialObservationSource(historical=SimpleNamespace(latest=lambda *a, **kw: ()),
        instrument_ids=(ID,), as_of=T, fundamentals=adapter)
    assert source.observations_as_of(T) == tuple(sorted(adapter.build(ID, as_of=T).snapshot.observations,
        key=lambda o: (o.provenance.market_timestamp, o.id)))
    instrument = NseEquityInstrument(instrument_id=ID, symbol="APARINDS", company_name="Synthetic", isin=INSTRUMENT.isin,
        exchange="NSE", sector=None, industry=None, listing_status="LISTED", listing_date=None, tradable=True, data_as_of=T, source="fixture")
    evidence = StockDiagnosticInputAssembler(source).assemble(instrument, T)
    assert evidence.financial_input.rule_input(25).state is S.READY
