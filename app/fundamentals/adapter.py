"""Canonical facts/filings -> existing legacy financial-observation input boundary.

No diagnostic, score, gate, valuation, or catalyst formula lives here.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Iterable

from app.data_sources.models import FundamentalFactKind
from app.domain.models import (AsOfSnapshot, DataQuality, FinancialObservation, FinancialPeriodType as LegacyPeriodType, Freshness, FreshnessStatus, Instrument, ObservationKind, Provenance, ValidationResult, ValidationStatus)
from app.filings.models import CorporateFiling, FilingType
from app.filings.store import CorporateFilingsStore
from app.fundamentals.models import FinancialFact, FinancialMetric, FinancialPeriodType, StatementScope
from app.fundamentals.store import FinancialFactStore


_PAYLOAD_METRICS = {
    FinancialMetric.REVENUE: "revenue", FinancialMetric.EBITDA: "ebitda", FinancialMetric.OPERATING_PROFIT: "ebitda",
    FinancialMetric.EBIT: "ebit", FinancialMetric.PAT: "pat", FinancialMetric.EPS_BASIC: "eps",
    FinancialMetric.TOTAL_EQUITY: "total_equity", FinancialMetric.NET_WORTH: "total_equity", FinancialMetric.TOTAL_DEBT: "total_debt",
    FinancialMetric.CASH_AND_EQUIVALENTS: "cash", FinancialMetric.CFO: "operating_cash_flow", FinancialMetric.CAPEX: "capex",
    FinancialMetric.TOTAL_ASSETS: "total_assets", FinancialMetric.CURRENT_ASSETS: "current_assets", FinancialMetric.CURRENT_LIABILITIES: "current_liabilities",
    FinancialMetric.INVENTORY: "inventory", FinancialMetric.RECEIVABLES: "receivables", FinancialMetric.PAYABLES: "payables",
    FinancialMetric.FINANCE_COST: "interest_expense", FinancialMetric.SHARES_OUTSTANDING: "shares_outstanding",
}


@dataclass(frozen=True, slots=True)
class FilingContext:
    latest_financial_result_filing_id: str | None; filing_ids: tuple[str, ...]; revision_filing_ids: tuple[str, ...]
    investor_presentation_filing_ids: tuple[str, ...]; board_meeting_filing_ids: tuple[str, ...]
    corporate_action_filing_ids: tuple[str, ...]; shareholding_filing_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class FundamentalEngineInput:
    instrument_id: str; as_of: datetime; statement_scope: StatementScope | None; snapshot: AsOfSnapshot
    completeness: str; freshness: str; revised: bool; filing_context: FilingContext; fact_ids: tuple[str, ...]
    warnings: tuple[str, ...]


class FundamentalsEngineAdapter:
    """Builds only the historical input the already-existing diagnostics consume."""
    def __init__(self, facts: FinancialFactStore, filings: CorporateFilingsStore) -> None: self._facts,self._filings=facts,filings
    def build(self, instrument_id: str, *, as_of: datetime, preferred_scope: StatementScope = StatementScope.CONSOLIDATED) -> FundamentalEngineInput:
        if as_of.tzinfo is None: raise ValueError("Fundamental engine input requires a timezone-aware as_of timestamp.")
        reported=tuple(f for f in self._facts.facts(instrument_id,as_of=as_of,limit=500) if f.fact_kind is FundamentalFactKind.REPORTED)
        scope,warnings=self._scope(reported,preferred_scope)
        selected=tuple(f for f in reported if f.statement_scope is scope) if scope else ()
        observations, conflicts=self._observations(selected,as_of)
        warnings=tuple((*warnings,*conflicts))
        all_filings=self._filings.list(instrument_id=instrument_id,as_of=as_of,limit=500)
        context=_context(all_filings)
        completeness=_completeness(observations); fresh="FRESH" if observations and max(x.publication_timestamp for x in observations if x.publication_timestamp)<=as_of else "UNAVAILABLE"
        instrument=selected[0].instrument if selected else None
        legacy=Instrument(instrument_id,instrument.symbol if instrument else instrument_id.rsplit(":",1)[-1],instrument.exchange.value if instrument else "UNKNOWN",instrument.isin if instrument else None)
        snapshot=AsOfSnapshot("canonical-fundamentals:"+instrument_id+":"+as_of.isoformat(),as_of,as_of,"canonical-financial-facts-v1",observations)
        return FundamentalEngineInput(instrument_id,as_of,scope,snapshot,completeness,fresh,any(f.revision_of_fact_id for f in selected),context,tuple(f.fact_id for f in selected),warnings)
    def _scope(self, facts: tuple[FinancialFact,...], preferred: StatementScope) -> tuple[StatementScope|None,tuple[str,...]]:
        scopes={f.statement_scope for f in facts}
        if preferred in scopes:return preferred,("STATEMENT_SCOPE_CONSOLIDATED" if preferred is StatementScope.CONSOLIDATED else "STATEMENT_SCOPE_PREFERRED",)
        if StatementScope.STANDALONE in scopes:return StatementScope.STANDALONE,("STANDALONE_FALLBACK",)
        return None,("FUNDAMENTALS_UNAVAILABLE",)
    def _observations(self,facts:tuple[FinancialFact,...],as_of:datetime)->tuple[tuple[FinancialObservation,...],tuple[str,...]]:
        period_groups:dict[tuple[FinancialPeriodType,datetime],list[FinancialFact]]={}
        for fact in facts:
            if fact.metric in _PAYLOAD_METRICS and fact.period_type in {FinancialPeriodType.QUARTERLY,FinancialPeriodType.ANNUAL}: period_groups.setdefault((fact.period_type,fact.period_end),[]).append(fact)
        observations=[];warnings=[]
        for (period_type,end), values in sorted(period_groups.items(),key=lambda item:item[0][1]):
            by_metric:dict[FinancialMetric,list[FinancialFact]]={}
            for item in values:by_metric.setdefault(item.metric,[]).append(item)
            chosen:dict[FinancialMetric,FinancialFact]={}
            for metric,candidates in by_metric.items():
                choice,conflict=_choose(candidates)
                if conflict:warnings.append("UNRESOLVED_FINANCIAL_FACT_CONFLICT:"+metric.value)
                elif choice:chosen[metric]=choice
            if not chosen:continue
            base=max(chosen.values(),key=lambda f:(f.available_at,f.fact_id)); payload={"period_end":end.isoformat(),"publication_timestamp":max(f.published_at for f in chosen.values()).isoformat(),"period_type":"quarterly" if period_type is FinancialPeriodType.QUARTERLY else "annual","statement_scope":base.statement_scope.value,"fact_ids":tuple(f.fact_id for f in chosen.values()),"filing_ids":tuple(sorted({f.filing_id for f in chosen.values() if f.filing_id}))}
            for metric,item in chosen.items(): payload[_PAYLOAD_METRICS[metric]]=float(item.value)
            ident="canonical-financial-observation:"+"|".join(sorted(f.fact_id for f in chosen.values())); published=max(f.published_at for f in chosen.values());received=max(f.received_at for f in chosen.values())
            provenance=Provenance("stored_canonical",base.source_reference,published,received,DataQuality.HIGH,Freshness(FreshnessStatus.FRESH,published,as_of,(as_of-published).total_seconds(),None),payload)
            validation=ValidationResult(ValidationStatus.VALID,as_of,(),provenance.freshness)
            legacy_type=LegacyPeriodType.QUARTERLY if period_type is FinancialPeriodType.QUARTERLY else LegacyPeriodType.ANNUAL
            instrument=Instrument(base.instrument.instrument_id,base.instrument.symbol,base.instrument.exchange.value,base.instrument.isin)
            observations.append(FinancialObservation(ident,instrument,ObservationKind.FUNDAMENTAL,payload,provenance,validation,None,end,published,legacy_type,None))
        return tuple(observations),tuple(warnings)


def _choose(candidates:list[FinancialFact])->tuple[FinancialFact|None,bool]:
    if len(candidates)==1:return candidates[0],False
    ordered=sorted(candidates,key=lambda f:(f.available_at,f.fact_id)); newest=ordered[-1]
    # A revision is explicit lineage, not an implicit latest-value rule.
    if newest.revision_of_fact_id and newest.revision_of_fact_id in {f.fact_id for f in ordered[:-1]}:return newest,False
    return None,True
def _completeness(observations:tuple[FinancialObservation,...])->str:
    quarterly=[x for x in observations if x.period_type is LegacyPeriodType.QUARTERLY]
    if not quarterly:return "INSUFFICIENT"
    latest=quarterly[-1].payload; required=("revenue","ebitda","pat","eps")
    return "COMPLETE" if all(latest.get(x) is not None for x in required) else "PARTIAL"
def _context(values:tuple[CorporateFiling,...])->FilingContext:
    of=lambda types:tuple(x.filing_id for x in values if x.filing_type in types)
    financial=of({FilingType.FINANCIAL_RESULTS})
    return FilingContext(financial[0] if financial else None,financial,tuple(x.filing_id for x in values if x.revision_of_filing_id),of({FilingType.INVESTOR_PRESENTATION}),of({FilingType.BOARD_MEETING}),tuple(x.filing_id for x in values if x.action is not None),of({FilingType.SHAREHOLDING_PATTERN}))
