"""Pure PIT-safe, non-qualifying annual derived-metric research receipts.

This is deliberately downstream of the canonical annual-fact readiness
contract.  It neither reads a store nor persists, ranks, scores, qualifies, or
interprets an instrument.  Derived research is not a Compounder policy.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, localcontext
from enum import StrEnum
import json
from statistics import median
from typing import Iterable

from app.fundamentals.compounder_canonical_annual_facts import (
    CanonicalAnnualFactCoverage,
    CanonicalAnnualFactReadinessStatus,
    assess_canonical_annual_facts,
    canonical_annual_facts_readiness_fingerprint,
)
from app.fundamentals.models import FinancialFact, FinancialMetric, StatementScope
from app.historical.guard import manifest_fingerprint


CONTRACT_ID = "compounder-testable-derived-metrics"
CONTRACT_VERSION = "v1-research-only"


class CompounderDerivedMetric(StrEnum):
    REVENUE_YOY = "REVENUE_YOY"; REVENUE_CAGR_3Y = "REVENUE_CAGR_3Y"; REVENUE_CAGR_5Y = "REVENUE_CAGR_5Y"
    PAT_YOY = "PAT_YOY"; PAT_CAGR_3Y = "PAT_CAGR_3Y"; PAT_CAGR_5Y = "PAT_CAGR_5Y"
    REVENUE_PERSISTENCE = "REVENUE_PERSISTENCE"; PAT_PERSISTENCE = "PAT_PERSISTENCE"
    ROE_CLOSING_EQUITY = "ROE_CLOSING_EQUITY"; ROE_AVERAGE_EQUITY = "ROE_AVERAGE_EQUITY"
    ROE_SUMMARY_3 = "ROE_SUMMARY_3"; ROE_SUMMARY_5 = "ROE_SUMMARY_5"
    CFO_PAT_ANNUAL = "CFO_PAT_ANNUAL"; CFO_PAT_CUMULATIVE_3 = "CFO_PAT_CUMULATIVE_3"; CFO_PAT_CUMULATIVE_5 = "CFO_PAT_CUMULATIVE_5"
    CASH_TRAJECTORY = "CASH_TRAJECTORY"


class CompounderDerivedWindow(StrEnum):
    ANNUAL_INTERVAL = "ANNUAL_INTERVAL"; THREE_ANNUAL_OBSERVATIONS = "THREE_ANNUAL_OBSERVATIONS"; FIVE_ANNUAL_OBSERVATIONS = "FIVE_ANNUAL_OBSERVATIONS"; FULL_AVAILABLE_SERIES = "FULL_AVAILABLE_SERIES"


class CompounderDerivedStatus(StrEnum):
    AVAILABLE = "AVAILABLE"; DATA_INSUFFICIENT = "DATA_INSUFFICIENT"; NON_COMPARABLE = "NON_COMPARABLE"; EVIDENCE_CONFLICTED = "EVIDENCE_CONFLICTED"


class CompounderDerivedReason(StrEnum):
    SOURCE_DATA_INSUFFICIENT = "SOURCE_DATA_INSUFFICIENT"; SOURCE_EVIDENCE_CONFLICTED = "SOURCE_EVIDENCE_CONFLICTED"; SOURCE_NOT_PIT_READY = "SOURCE_NOT_PIT_READY"
    CONTINUOUS_ANNUAL_PERIODS_REQUIRED = "CONTINUOUS_ANNUAL_PERIODS_REQUIRED"; POSITIVE_GROWTH_BASE_REQUIRED = "POSITIVE_GROWTH_BASE_REQUIRED"
    LOSS_TO_PROFIT = "LOSS_TO_PROFIT"; PROFIT_TO_LOSS = "PROFIT_TO_LOSS"; LOSS_TO_LOSS = "LOSS_TO_LOSS"; ZERO_OR_NEAR_ZERO_DENOMINATOR = "ZERO_OR_NEAR_ZERO_DENOMINATOR"
    MATCHING_EQUITY_REQUIRED = "MATCHING_EQUITY_REQUIRED"; OPENING_EQUITY_REQUIRED = "OPENING_EQUITY_REQUIRED"; POSITIVE_EQUITY_REQUIRED = "POSITIVE_EQUITY_REQUIRED"
    MATCHING_CFO_REQUIRED = "MATCHING_CFO_REQUIRED"; POSITIVE_CUMULATIVE_PAT_REQUIRED = "POSITIVE_CUMULATIVE_PAT_REQUIRED"; REQUIRED_WINDOW_UNAVAILABLE = "REQUIRED_WINDOW_UNAVAILABLE"


class CashTrajectoryObservation(StrEnum):
    INCREASING = "INCREASING"; DECREASING = "DECREASING"; FLAT = "FLAT"; MIXED = "MIXED"; SINGLE_PERIOD = "SINGLE_PERIOD"


@dataclass(frozen=True, slots=True)
class CompounderDerivedResearchReceipt:
    canonical_instrument_id: str
    statement_scope: StatementScope
    as_of: datetime
    metric: CompounderDerivedMetric
    window: CompounderDerivedWindow
    status: CompounderDerivedStatus
    reasons: tuple[CompounderDerivedReason, ...]
    period_ends: tuple[datetime, ...]
    input_fact_ids: tuple[str, ...]
    input_fact_fingerprints: tuple[str, ...]
    source_coverage_fingerprints: tuple[str, ...]
    values: tuple[tuple[str, Decimal], ...]
    observation: CashTrajectoryObservation | None
    contract_id: str = CONTRACT_ID
    contract_version: str = CONTRACT_VERSION
    actionability: str = "WATCH_ONLY"
    execution_status: str = "NON_EXECUTABLE"
    research_status: str = "RESEARCH_ONLY"
    fingerprint: str = ""

    def __post_init__(self) -> None:
        if not self.canonical_instrument_id or not _aware(self.as_of): raise ValueError("COMPOUNDER_DERIVED_RECEIPT_SCOPE_REQUIRED")
        if self.reasons != _reasons(self.reasons): raise ValueError("COMPOUNDER_DERIVED_RECEIPT_REASONS_NONCANONICAL")
        if self.period_ends != tuple(sorted(set(self.period_ends), key=_time)): raise ValueError("COMPOUNDER_DERIVED_RECEIPT_PERIODS_NONCANONICAL")
        for values, name in ((self.input_fact_ids, "FACT_IDS"), (self.input_fact_fingerprints, "FACT_FINGERPRINTS"), (self.source_coverage_fingerprints, "COVERAGES")):
            if values != tuple(sorted(set(values))): raise ValueError("COMPOUNDER_DERIVED_RECEIPT_" + name + "_NONCANONICAL")
        if self.values != tuple(sorted(self.values)) or len({key for key, _ in self.values}) != len(self.values): raise ValueError("COMPOUNDER_DERIVED_RECEIPT_VALUES_NONCANONICAL")
        if self.status is CompounderDerivedStatus.AVAILABLE:
            if not self.values or self.reasons or not self.input_fact_ids: raise ValueError("COMPOUNDER_DERIVED_RECEIPT_AVAILABLE_FIELDS_REQUIRED")
        elif self.values: raise ValueError("COMPOUNDER_DERIVED_RECEIPT_UNAVAILABLE_VALUES_FORBIDDEN")
        if self.metric is not CompounderDerivedMetric.CASH_TRAJECTORY and self.observation is not None: raise ValueError("COMPOUNDER_DERIVED_RECEIPT_OBSERVATION_FORBIDDEN")
        if (self.contract_id, self.contract_version, self.actionability, self.execution_status, self.research_status) != (CONTRACT_ID, CONTRACT_VERSION, "WATCH_ONLY", "NON_EXECUTABLE", "RESEARCH_ONLY"): raise ValueError("COMPOUNDER_DERIVED_RECEIPT_BOUNDARY_INVALID")
        if self.fingerprint != _fingerprint(_payload(self)): raise ValueError("COMPOUNDER_DERIVED_RECEIPT_FINGERPRINT_MISMATCH")


@dataclass(frozen=True, slots=True)
class CompounderDerivedResearchEvaluation:
    canonical_instrument_id: str
    statement_scope: StatementScope
    as_of: datetime
    receipts: tuple[CompounderDerivedResearchReceipt, ...]
    contract_id: str = CONTRACT_ID
    contract_version: str = CONTRACT_VERSION
    fingerprint: str = ""

    def __post_init__(self) -> None:
        if not self.canonical_instrument_id or not _aware(self.as_of): raise ValueError("COMPOUNDER_DERIVED_EVALUATION_SCOPE_REQUIRED")
        if self.receipts != tuple(sorted(self.receipts, key=lambda value: (value.metric.value, value.window.value, tuple(_time(x) for x in value.period_ends)))): raise ValueError("COMPOUNDER_DERIVED_EVALUATION_RECEIPTS_NONCANONICAL")
        if any(value.canonical_instrument_id != self.canonical_instrument_id or value.statement_scope is not self.statement_scope or value.as_of != self.as_of for value in self.receipts): raise ValueError("COMPOUNDER_DERIVED_EVALUATION_RECEIPT_SCOPE_INVALID")
        if self.contract_id != CONTRACT_ID or self.contract_version != CONTRACT_VERSION or self.fingerprint != _evaluation_fingerprint(self): raise ValueError("COMPOUNDER_DERIVED_EVALUATION_FINGERPRINT_MISMATCH")


def evaluate_compounder_testable_derived_metrics(
    facts: Iterable[FinancialFact], *, canonical_instrument_id: str,
    statement_scope: StatementScope, as_of: datetime,
) -> CompounderDerivedResearchEvaluation:
    """Evaluate only reported annual inputs at the supplied historical cutoff."""
    values = tuple(facts)
    readiness = assess_canonical_annual_facts(values, canonical_instrument_id=canonical_instrument_id, statement_scope=statement_scope, as_of=as_of)
    if readiness.fingerprint != canonical_annual_facts_readiness_fingerprint(readiness): raise ValueError("COMPOUNDER_DERIVED_SOURCE_READINESS_TAMPERED")
    fact_by_id = {value.fact_id: value for value in values}
    covers = {cover.metric: cover for cover in readiness.covers if cover.metric is not None}
    revenue = _series(covers.get(FinancialMetric.REVENUE), fact_by_id)
    pat = _series(covers.get(FinancialMetric.PAT), fact_by_id)
    cfo = _series(covers.get(FinancialMetric.CFO), fact_by_id)
    equity = _series(covers.get(FinancialMetric.TOTAL_EQUITY), fact_by_id)
    cash = _series(covers.get(FinancialMetric.CASH_AND_EQUIVALENTS), fact_by_id)
    receipts = (
        *_growth(CompounderDerivedMetric.REVENUE_YOY, CompounderDerivedMetric.REVENUE_CAGR_3Y, CompounderDerivedMetric.REVENUE_CAGR_5Y, CompounderDerivedMetric.REVENUE_PERSISTENCE, revenue, canonical_instrument_id, statement_scope, as_of, pat_mode=False),
        *_growth(CompounderDerivedMetric.PAT_YOY, CompounderDerivedMetric.PAT_CAGR_3Y, CompounderDerivedMetric.PAT_CAGR_5Y, CompounderDerivedMetric.PAT_PERSISTENCE, pat, canonical_instrument_id, statement_scope, as_of, pat_mode=True),
        *_roe(pat, equity, canonical_instrument_id, statement_scope, as_of),
        *_cash_conversion(cfo, pat, canonical_instrument_id, statement_scope, as_of),
        _cash(cash, canonical_instrument_id, statement_scope, as_of),
    )
    ordered = tuple(sorted(receipts, key=lambda value: (value.metric.value, value.window.value, tuple(_time(x) for x in value.period_ends))))
    body = dict(canonical_instrument_id=canonical_instrument_id, statement_scope=statement_scope, as_of=as_of, receipts=ordered)
    return CompounderDerivedResearchEvaluation(**body, fingerprint=_evaluation_fingerprint_values(body))


def serialize_compounder_derived_research(value: CompounderDerivedResearchEvaluation) -> str:
    if value.fingerprint != _evaluation_fingerprint(value): raise ValueError("COMPOUNDER_DERIVED_EVALUATION_FINGERPRINT_MISMATCH")
    return json.dumps({"canonical_instrument_id": value.canonical_instrument_id, "statement_scope": value.statement_scope.value, "as_of": _time(value.as_of), "contract_id": value.contract_id, "contract_version": value.contract_version, "receipts": tuple(_payload(x) | {"fingerprint": x.fingerprint} for x in value.receipts), "fingerprint": value.fingerprint}, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _series(cover: CanonicalAnnualFactCoverage | None, facts: dict[str, FinancialFact]) -> tuple[CanonicalAnnualFactCoverage | None, tuple[FinancialFact, ...]]:
    if cover is None or cover.status is not CanonicalAnnualFactReadinessStatus.PIT_READY: return cover, ()
    selected = tuple(facts[item] for item in cover.selected_fact_ids if item in facts)
    if len(selected) != len(cover.selected_fact_ids): return cover, ()
    return cover, tuple(sorted(selected, key=lambda value: (value.period_end, value.fact_id)))


def _growth(yoy_metric, cagr3_metric, cagr5_metric, persistence_metric, source, instrument, scope, as_of, *, pat_mode: bool) -> tuple[CompounderDerivedResearchReceipt, ...]:
    cover, series = source
    if not series:
        base = _source_block(yoy_metric, CompounderDerivedWindow.ANNUAL_INTERVAL, cover, instrument, scope, as_of)
        return (base, _source_block(cagr3_metric, CompounderDerivedWindow.THREE_ANNUAL_OBSERVATIONS, cover, instrument, scope, as_of), _source_block(cagr5_metric, CompounderDerivedWindow.FIVE_ANNUAL_OBSERVATIONS, cover, instrument, scope, as_of), _source_block(persistence_metric, CompounderDerivedWindow.FULL_AVAILABLE_SERIES, cover, instrument, scope, as_of))
    pairs = tuple(_yoy(yoy_metric, left, right, cover, instrument, scope, as_of, pat_mode) for left, right in zip(series, series[1:]))
    persistence = _persistence(persistence_metric, pairs, series, cover, instrument, scope, as_of)
    return (*pairs, _cagr(cagr3_metric, series, 3, cover, instrument, scope, as_of), _cagr(cagr5_metric, series, 5, cover, instrument, scope, as_of), persistence)


def _yoy(metric, left, right, cover, instrument, scope, as_of, pat_mode):
    if not _consecutive(left, right): return _record(metric, CompounderDerivedWindow.ANNUAL_INTERVAL, CompounderDerivedStatus.NON_COMPARABLE, (CompounderDerivedReason.CONTINUOUS_ANNUAL_PERIODS_REQUIRED,), (left, right), cover, instrument, scope, as_of)
    if left.value <= 0:
        reason = CompounderDerivedReason.ZERO_OR_NEAR_ZERO_DENOMINATOR if left.value == 0 else CompounderDerivedReason.POSITIVE_GROWTH_BASE_REQUIRED
        if pat_mode and left.value < 0 < right.value: reason = CompounderDerivedReason.LOSS_TO_PROFIT
        elif pat_mode and left.value > 0 > right.value: reason = CompounderDerivedReason.PROFIT_TO_LOSS
        elif pat_mode and left.value < 0 and right.value < 0: reason = CompounderDerivedReason.LOSS_TO_LOSS
        return _record(metric, CompounderDerivedWindow.ANNUAL_INTERVAL, CompounderDerivedStatus.NON_COMPARABLE, (reason,), (left, right), cover, instrument, scope, as_of)
    if pat_mode and right.value <= 0:
        reason = CompounderDerivedReason.PROFIT_TO_LOSS if right.value < 0 else CompounderDerivedReason.ZERO_OR_NEAR_ZERO_DENOMINATOR
        return _record(metric, CompounderDerivedWindow.ANNUAL_INTERVAL, CompounderDerivedStatus.NON_COMPARABLE, (reason,), (left, right), cover, instrument, scope, as_of)
    return _record(metric, CompounderDerivedWindow.ANNUAL_INTERVAL, CompounderDerivedStatus.AVAILABLE, (), (left, right), cover, instrument, scope, as_of, values=((str(right.fiscal_year), (right.value-left.value)/left.value),))


def _cagr(metric, series, observations, cover, instrument, scope, as_of):
    window = CompounderDerivedWindow.THREE_ANNUAL_OBSERVATIONS if observations == 3 else CompounderDerivedWindow.FIVE_ANNUAL_OBSERVATIONS
    if len(series) < observations: return _record(metric, window, CompounderDerivedStatus.DATA_INSUFFICIENT, (CompounderDerivedReason.REQUIRED_WINDOW_UNAVAILABLE,), (), cover, instrument, scope, as_of)
    values = series[-observations:]
    if not _continuous(values): return _record(metric, window, CompounderDerivedStatus.NON_COMPARABLE, (CompounderDerivedReason.CONTINUOUS_ANNUAL_PERIODS_REQUIRED,), values, cover, instrument, scope, as_of)
    if values[0].value <= 0: return _record(metric, window, CompounderDerivedStatus.NON_COMPARABLE, (CompounderDerivedReason.POSITIVE_GROWTH_BASE_REQUIRED,), values, cover, instrument, scope, as_of)
    intervals = values[-1].fiscal_year - values[0].fiscal_year if values[-1].fiscal_year and values[0].fiscal_year else 0
    if intervals <= 0: return _record(metric, window, CompounderDerivedStatus.NON_COMPARABLE, (CompounderDerivedReason.CONTINUOUS_ANNUAL_PERIODS_REQUIRED,), values, cover, instrument, scope, as_of)
    with localcontext() as context:
        context.prec = 34; result = ((values[-1].value / values[0].value).ln() / Decimal(intervals)).exp() - Decimal(1)
    return _record(metric, window, CompounderDerivedStatus.AVAILABLE, (), values, cover, instrument, scope, as_of, values=(("cagr", result), ("elapsed_intervals", Decimal(intervals))))


def _persistence(metric, pairs, series, cover, instrument, scope, as_of):
    comparable = tuple(value for value in pairs if value.status is CompounderDerivedStatus.AVAILABLE)
    if not pairs: return _record(metric, CompounderDerivedWindow.FULL_AVAILABLE_SERIES, CompounderDerivedStatus.DATA_INSUFFICIENT, (CompounderDerivedReason.REQUIRED_WINDOW_UNAVAILABLE,), series, cover, instrument, scope, as_of)
    positive = sum(1 for value in comparable if value.values[0][1] > 0); negative = sum(1 for value in comparable if value.values[0][1] < 0)
    return _record(metric, CompounderDerivedWindow.FULL_AVAILABLE_SERIES, CompounderDerivedStatus.AVAILABLE, (), series, cover, instrument, scope, as_of, values=(("comparable_intervals", Decimal(len(comparable))), ("negative_intervals", Decimal(negative)), ("non_comparable_intervals", Decimal(len(pairs)-len(comparable))), ("positive_intervals", Decimal(positive))))


def _roe(pat_source, equity_source, instrument, scope, as_of):
    pat_cover, pats = pat_source; equity_cover, equities = equity_source
    if not pats or not equities:
        return (_source_block(CompounderDerivedMetric.ROE_CLOSING_EQUITY, CompounderDerivedWindow.ANNUAL_INTERVAL, pat_cover or equity_cover, instrument, scope, as_of), _source_block(CompounderDerivedMetric.ROE_AVERAGE_EQUITY, CompounderDerivedWindow.ANNUAL_INTERVAL, pat_cover or equity_cover, instrument, scope, as_of), _source_block(CompounderDerivedMetric.ROE_SUMMARY_3, CompounderDerivedWindow.THREE_ANNUAL_OBSERVATIONS, pat_cover or equity_cover, instrument, scope, as_of), _source_block(CompounderDerivedMetric.ROE_SUMMARY_5, CompounderDerivedWindow.FIVE_ANNUAL_OBSERVATIONS, pat_cover or equity_cover, instrument, scope, as_of))
    equity_by_year = {item.fiscal_year:item for item in equities}; closing=[]; average=[]
    for item in pats:
        eq = equity_by_year.get(item.fiscal_year)
        if eq is None: closing.append(_record(CompounderDerivedMetric.ROE_CLOSING_EQUITY, CompounderDerivedWindow.ANNUAL_INTERVAL, CompounderDerivedStatus.DATA_INSUFFICIENT, (CompounderDerivedReason.MATCHING_EQUITY_REQUIRED,), (item,), (pat_cover,equity_cover), instrument, scope, as_of)); continue
        if eq.value <= 0: closing.append(_record(CompounderDerivedMetric.ROE_CLOSING_EQUITY, CompounderDerivedWindow.ANNUAL_INTERVAL, CompounderDerivedStatus.NON_COMPARABLE, (CompounderDerivedReason.POSITIVE_EQUITY_REQUIRED,), (item,eq), (pat_cover,equity_cover), instrument, scope, as_of)); continue
        closing.append(_record(CompounderDerivedMetric.ROE_CLOSING_EQUITY, CompounderDerivedWindow.ANNUAL_INTERVAL, CompounderDerivedStatus.AVAILABLE, (), (item,eq), (pat_cover,equity_cover), instrument, scope, as_of, values=((str(item.fiscal_year),item.value/eq.value),)))
        opening=equity_by_year.get(item.fiscal_year-1 if item.fiscal_year else None)
        if opening is None: average.append(_record(CompounderDerivedMetric.ROE_AVERAGE_EQUITY, CompounderDerivedWindow.ANNUAL_INTERVAL, CompounderDerivedStatus.DATA_INSUFFICIENT, (CompounderDerivedReason.OPENING_EQUITY_REQUIRED,), (item,eq), (pat_cover,equity_cover), instrument, scope, as_of)); continue
        if opening.value <= 0 or eq.value <= 0: average.append(_record(CompounderDerivedMetric.ROE_AVERAGE_EQUITY, CompounderDerivedWindow.ANNUAL_INTERVAL, CompounderDerivedStatus.NON_COMPARABLE, (CompounderDerivedReason.POSITIVE_EQUITY_REQUIRED,), (item,opening,eq), (pat_cover,equity_cover), instrument, scope, as_of)); continue
        average.append(_record(CompounderDerivedMetric.ROE_AVERAGE_EQUITY, CompounderDerivedWindow.ANNUAL_INTERVAL, CompounderDerivedStatus.AVAILABLE, (), (item,opening,eq), (pat_cover,equity_cover), instrument, scope, as_of, values=((str(item.fiscal_year),item.value/((opening.value+eq.value)/2)),)))
    sources = tuple(pats) + tuple(equities)
    return (*closing,*average,_summary(CompounderDerivedMetric.ROE_SUMMARY_3, closing, 3, sources, (pat_cover,equity_cover), instrument, scope, as_of),_summary(CompounderDerivedMetric.ROE_SUMMARY_5, closing, 5, sources, (pat_cover,equity_cover), instrument, scope, as_of))


def _summary(metric, receipts, count, facts, cover, instrument, scope, as_of):
    window=CompounderDerivedWindow.THREE_ANNUAL_OBSERVATIONS if count==3 else CompounderDerivedWindow.FIVE_ANNUAL_OBSERVATIONS; usable=[r for r in receipts if r.status is CompounderDerivedStatus.AVAILABLE]
    if len(usable)<count:return _record(metric,window,CompounderDerivedStatus.DATA_INSUFFICIENT,(CompounderDerivedReason.REQUIRED_WINDOW_UNAVAILABLE,),facts,cover,instrument,scope,as_of)
    selected=usable[-count:]; ratios=[r.values[0][1] for r in selected]
    return _record(metric,window,CompounderDerivedStatus.AVAILABLE,(),facts,cover,instrument,scope,as_of,values=(("maximum",max(ratios)),("median",median(ratios)),("minimum",min(ratios)),("valid_period_count",Decimal(count))))


def _cash_conversion(cfo_source, pat_source, instrument, scope, as_of):
    cfo_cover, cfos=cfo_source; pat_cover,pats=pat_source
    if not cfos or not pats:return (_source_block(CompounderDerivedMetric.CFO_PAT_ANNUAL,CompounderDerivedWindow.ANNUAL_INTERVAL,cfo_cover or pat_cover,instrument,scope,as_of),_source_block(CompounderDerivedMetric.CFO_PAT_CUMULATIVE_3,CompounderDerivedWindow.THREE_ANNUAL_OBSERVATIONS,cfo_cover or pat_cover,instrument,scope,as_of),_source_block(CompounderDerivedMetric.CFO_PAT_CUMULATIVE_5,CompounderDerivedWindow.FIVE_ANNUAL_OBSERVATIONS,cfo_cover or pat_cover,instrument,scope,as_of))
    cfo_by_year={x.fiscal_year:x for x in cfos}; annual=[]
    for pat in pats:
        cfo=cfo_by_year.get(pat.fiscal_year)
        if cfo is None:annual.append(_record(CompounderDerivedMetric.CFO_PAT_ANNUAL,CompounderDerivedWindow.ANNUAL_INTERVAL,CompounderDerivedStatus.DATA_INSUFFICIENT,(CompounderDerivedReason.MATCHING_CFO_REQUIRED,),(pat,),(cfo_cover,pat_cover),instrument,scope,as_of));continue
        if pat.value<=0:annual.append(_record(CompounderDerivedMetric.CFO_PAT_ANNUAL,CompounderDerivedWindow.ANNUAL_INTERVAL,CompounderDerivedStatus.NON_COMPARABLE,(CompounderDerivedReason.ZERO_OR_NEAR_ZERO_DENOMINATOR if pat.value==0 else CompounderDerivedReason.POSITIVE_GROWTH_BASE_REQUIRED,),(cfo,pat),(cfo_cover,pat_cover),instrument,scope,as_of));continue
        annual.append(_record(CompounderDerivedMetric.CFO_PAT_ANNUAL,CompounderDerivedWindow.ANNUAL_INTERVAL,CompounderDerivedStatus.AVAILABLE,(),(cfo,pat),(cfo_cover,pat_cover),instrument,scope,as_of,values=((str(pat.fiscal_year),cfo.value/pat.value),)))
    return (*annual,_cumulative(CompounderDerivedMetric.CFO_PAT_CUMULATIVE_3,cfos,pats,3,(cfo_cover,pat_cover),instrument,scope,as_of),_cumulative(CompounderDerivedMetric.CFO_PAT_CUMULATIVE_5,cfos,pats,5,(cfo_cover,pat_cover),instrument,scope,as_of))


def _cumulative(metric,cfos,pats,count,cover,instrument,scope,as_of):
    window=CompounderDerivedWindow.THREE_ANNUAL_OBSERVATIONS if count==3 else CompounderDerivedWindow.FIVE_ANNUAL_OBSERVATIONS; cfo_by_year={x.fiscal_year:x for x in cfos}; common=[(p,cfo_by_year[p.fiscal_year]) for p in pats if p.fiscal_year in cfo_by_year]
    if len(common)<count:return _record(metric,window,CompounderDerivedStatus.DATA_INSUFFICIENT,(CompounderDerivedReason.REQUIRED_WINDOW_UNAVAILABLE,),(),cover,instrument,scope,as_of)
    selected=common[-count:]; inputs=tuple(x for pair in selected for x in pair)
    if not _continuous(tuple(x[0] for x in selected)):return _record(metric,window,CompounderDerivedStatus.NON_COMPARABLE,(CompounderDerivedReason.CONTINUOUS_ANNUAL_PERIODS_REQUIRED,),inputs,cover,instrument,scope,as_of)
    total_pat=sum((x.value for x,_ in selected),Decimal()); total_cfo=sum((x.value for _,x in selected),Decimal())
    if total_pat<=0:return _record(metric,window,CompounderDerivedStatus.NON_COMPARABLE,(CompounderDerivedReason.POSITIVE_CUMULATIVE_PAT_REQUIRED,),inputs,cover,instrument,scope,as_of)
    return _record(metric,window,CompounderDerivedStatus.AVAILABLE,(),inputs,cover,instrument,scope,as_of,values=(("cumulative_cfo",total_cfo),("cumulative_pat",total_pat),("ratio",total_cfo/total_pat)))


def _cash(source,instrument,scope,as_of):
    cover,series=source
    if not series:return _source_block(CompounderDerivedMetric.CASH_TRAJECTORY,CompounderDerivedWindow.FULL_AVAILABLE_SERIES,cover,instrument,scope,as_of)
    changes=tuple(right.value-left.value for left,right in zip(series,series[1:])); observation=CashTrajectoryObservation.SINGLE_PERIOD if not changes else CashTrajectoryObservation.INCREASING if all(x>0 for x in changes) else CashTrajectoryObservation.DECREASING if all(x<0 for x in changes) else CashTrajectoryObservation.FLAT if all(x==0 for x in changes) else CashTrajectoryObservation.MIXED
    values=tuple(("cash:"+str(x.fiscal_year),x.value) for x in series)+tuple(("change:"+str(right.fiscal_year),right.value-left.value) for left,right in zip(series,series[1:]))
    return _record(CompounderDerivedMetric.CASH_TRAJECTORY,CompounderDerivedWindow.FULL_AVAILABLE_SERIES,CompounderDerivedStatus.AVAILABLE,(),series,cover,instrument,scope,as_of,values=values,observation=observation)


def _source_block(metric,window,cover,instrument,scope,as_of):
    if cover is not None and cover.status is CanonicalAnnualFactReadinessStatus.EVIDENCE_CONFLICTED: status,reason=CompounderDerivedStatus.EVIDENCE_CONFLICTED,CompounderDerivedReason.SOURCE_EVIDENCE_CONFLICTED
    elif cover is not None and cover.status is CanonicalAnnualFactReadinessStatus.PIT_READY: status,reason=CompounderDerivedStatus.DATA_INSUFFICIENT,CompounderDerivedReason.SOURCE_DATA_INSUFFICIENT
    elif cover is not None and cover.status.name.startswith("PIT"): status,reason=CompounderDerivedStatus.DATA_INSUFFICIENT,CompounderDerivedReason.SOURCE_NOT_PIT_READY
    else: status,reason=CompounderDerivedStatus.DATA_INSUFFICIENT,CompounderDerivedReason.SOURCE_DATA_INSUFFICIENT
    return _record(metric,window,status,(reason,),(),cover,instrument,scope,as_of)


def _record(metric,window,status,reasons,facts,cover,instrument,scope,as_of,*,values=(),observation=None):
    source_fps = tuple(sorted({item.fingerprint for item in _covers(cover)}))
    ids = tuple(sorted({x.fact_id for x in facts}))
    fact_fps = tuple(sorted({_fact_fingerprint(x) for x in facts}))
    body=dict(canonical_instrument_id=instrument,statement_scope=scope,as_of=as_of,metric=metric,window=window,status=status,reasons=_reasons(reasons),period_ends=tuple(sorted({x.period_end for x in facts},key=_time)),input_fact_ids=ids,input_fact_fingerprints=fact_fps,source_coverage_fingerprints=source_fps,values=tuple(sorted(values)),observation=observation,contract_id=CONTRACT_ID,contract_version=CONTRACT_VERSION,actionability="WATCH_ONLY",execution_status="NON_EXECUTABLE",research_status="RESEARCH_ONLY")
    return CompounderDerivedResearchReceipt(**body,fingerprint=_fingerprint(_payload_values(body)))


def _covers(value):
    if value is None: return ()
    return tuple(item for item in (value if isinstance(value, tuple) else (value,)) if item is not None)
def _fact_fingerprint(value):
    return _fingerprint({"fact_id":value.fact_id,"canonical_instrument_id":value.instrument.instrument_id,"metric":value.metric.value,"value":str(value.value),"period_end":_time(value.period_end),"fiscal_year":value.fiscal_year,"statement_scope":value.statement_scope.value,"published_at":_time(value.published_at),"received_at":_time(value.received_at),"filing_id":value.filing_id,"source_reference":value.source_reference,"normalization_version":value.normalization_version})
def _consecutive(left,right): return left.fiscal_year is not None and right.fiscal_year==left.fiscal_year+1
def _continuous(values): return bool(values) and all(_consecutive(left,right) for left,right in zip(values,values[1:]))
def _reasons(values): return tuple(sorted(set(values),key=lambda value:value.value))
def _aware(value): return value.tzinfo is not None and value.utcoffset() is not None
def _time(value): return value.astimezone(UTC).isoformat()
def _payload(value): return _payload_values({field:getattr(value,field) for field in value.__dataclass_fields__ if field!="fingerprint"})
def _payload_values(values):
    def convert(value):
        if isinstance(value,StrEnum):return value.value
        if isinstance(value,Decimal):return str(value)
        if isinstance(value,datetime):return _time(value)
        if isinstance(value,tuple):return tuple(convert(x) for x in value)
        return value
    return {key:convert(value) for key,value in values.items()}
def _fingerprint(values): return "sha256:"+manifest_fingerprint(**values).removeprefix("sha256:")
def _evaluation_fingerprint(value): return _evaluation_fingerprint_values({"canonical_instrument_id":value.canonical_instrument_id,"statement_scope":value.statement_scope,"as_of":value.as_of,"receipts":value.receipts})
def _evaluation_fingerprint_values(values): return _fingerprint({"canonical_instrument_id":values["canonical_instrument_id"],"statement_scope":values["statement_scope"].value,"as_of":_time(values["as_of"]),"receipt_fingerprints":tuple(x.fingerprint for x in values["receipts"]),"contract_id":CONTRACT_ID,"contract_version":CONTRACT_VERSION})


__all__=("CONTRACT_ID","CONTRACT_VERSION","CashTrajectoryObservation","CompounderDerivedMetric","CompounderDerivedReason","CompounderDerivedResearchEvaluation","CompounderDerivedResearchReceipt","CompounderDerivedStatus","CompounderDerivedWindow","evaluate_compounder_testable_derived_metrics","serialize_compounder_derived_research")
