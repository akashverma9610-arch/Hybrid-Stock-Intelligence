"""Normalization and deterministic derived-metric services for financial facts."""
from __future__ import annotations

import hashlib
from dataclasses import replace
from datetime import datetime
from decimal import Decimal
from typing import Iterable

from app.data_sources.models import FundamentalFactKind
from app.filings.models import CorporateFiling, FilingType
from app.fundamentals.models import (FinancialDerivedMetric, FinancialFact, FinancialMetric, FinancialPeriodType, FinancialQualityFlag, FinancialValueBasis, FundamentalSnapshot, StatementScope, StructuredFinancialRecord)


class FinancialFactNormalizationService:
    """Converts already-structured provider records; it never parses documents or fetches a network source."""
    def normalize(self, value: StructuredFinancialRecord, filing: CorporateFiling) -> FinancialFact:
        if filing.filing_id != value.filing_id or filing.instrument.instrument_id != value.instrument.instrument_id: raise ValueError("Financial structured record must reference its exact filing and instrument.")
        if filing.filing_type is not FilingType.FINANCIAL_RESULTS: raise ValueError("Reported financial facts must reference a financial-results filing.")
        if filing.announced_at != value.published_at or filing.received_at != value.received_at: raise ValueError("Financial fact timing must match immutable filing publication and receipt timestamps.")
        expected=_fact_id(value)
        flags=(FinancialQualityFlag.REVISED,) if filing.revision_of_filing_id or filing.financial_result and filing.financial_result.revised else ((FinancialQualityFlag.UNKNOWN_BASIS,) if value.value_basis is FinancialValueBasis.UNKNOWN else (FinancialQualityFlag.COMPLETE,))
        return FinancialFact(expected,value.instrument,value.metric,value.value,value.currency,value.unit,value.scale,value.period_type,value.value_basis,value.period_start,value.period_end,value.fiscal_year,value.fiscal_quarter,value.statement_scope,FundamentalFactKind.REPORTED,value.source,value.filing_id,value.source_reference,value.published_at,value.received_at,value.normalization_version,tuple((value.attachment_reference or "",*value.provenance)),(),value.revision_of_fact_id,flags)


class FinancialDerivationService:
    """Small conservative fact derivations. Incompatible scope/basis/currency never gets merged."""
    def derive_q4(self, annual: FinancialFact, nine_months: FinancialFact) -> FinancialFact | None:
        if not _compatible(annual,nine_months, same_metric=True) or annual.period_type is not FinancialPeriodType.ANNUAL or nine_months.value_basis is not FinancialValueBasis.YEAR_TO_DATE or annual.fiscal_year != nine_months.fiscal_year: return None
        return self._derived(annual,annual.value-nine_months.value,FinancialPeriodType.QUARTERLY,FinancialValueBasis.QUARTER_ONLY,4,(annual.fact_id,nine_months.fact_id),annual.period_start)
    def ttm(self, quarters: Iterable[FinancialFact]) -> FinancialFact | None:
        values=sorted(tuple(quarters),key=lambda f:(f.period_end,f.published_at,f.fact_id))
        if len(values)<4: return None
        values=values[-4:]
        if any(f.period_type is not FinancialPeriodType.QUARTERLY or f.value_basis is not FinancialValueBasis.QUARTER_ONLY for f in values) or any(not _compatible(values[0],f, same_metric=True) for f in values[1:]): return None
        periods={(f.fiscal_year,f.fiscal_quarter) for f in values}
        if len(periods)!=4 or any(f.fiscal_quarter is None for f in values): return None
        anchor=values[-1]
        return self._derived(anchor,sum((f.value for f in values),Decimal()),FinancialPeriodType.TRAILING_TWELVE_MONTHS,FinancialValueBasis.QUARTER_ONLY,None,tuple(f.fact_id for f in values),values[0].period_start)
    def growth(self,current:FinancialFact,previous:FinancialFact,kind:str)->FinancialDerivedMetric:
        if not _compatible(current,previous, same_metric=True) or previous.value==0:return self._unavailable(f"{current.metric.value}_{kind}",current,"INVALID_COMPARISON")
        return FinancialDerivedMetric(f"{current.metric.value}_{kind}",current.instrument.instrument_id,(current.value-previous.value)/abs(previous.value),current.period_end,current.statement_scope,(current.fact_id,previous.fact_id),(FinancialQualityFlag.COMPLETE,))
    def margin(self,numerator:FinancialFact,revenue:FinancialFact,label:str)->FinancialDerivedMetric:
        if not _compatible(numerator,revenue) or revenue.value==0:return self._unavailable(label,numerator,"INVALID_DENOMINATOR")
        return FinancialDerivedMetric(label,numerator.instrument.instrument_id,numerator.value/revenue.value,numerator.period_end,numerator.statement_scope,(numerator.fact_id,revenue.fact_id),(FinancialQualityFlag.COMPLETE,))
    def balance(self,metric:str,left:FinancialFact,right:FinancialFact,operation:str)->FinancialDerivedMetric:
        if not _compatible(left,right) or (operation=="ratio" and right.value==0):return self._unavailable(metric,left,"INVALID_DENOMINATOR")
        value=left.value-right.value if operation=="subtract" else left.value/right.value
        return FinancialDerivedMetric(metric,left.instrument.instrument_id,value,left.period_end,left.statement_scope,(left.fact_id,right.fact_id),(FinancialQualityFlag.COMPLETE,))
    def free_cash_flow(self,cfo:FinancialFact,capex:FinancialFact)->FinancialDerivedMetric:
        if not _compatible(cfo,capex) or capex.value>0:return self._unavailable("FREE_CASH_FLOW",cfo,"AMBIGUOUS_CAPEX_SIGN")
        return FinancialDerivedMetric("FREE_CASH_FLOW",cfo.instrument.instrument_id,cfo.value+capex.value,cfo.period_end,cfo.statement_scope,(cfo.fact_id,capex.fact_id),(FinancialQualityFlag.COMPLETE,))
    def snapshot(self,instrument, facts:Iterable[FinancialFact], *, data_as_of:datetime, scope:StatementScope)->FundamentalSnapshot:
        values=tuple(f for f in facts if f.statement_scope is scope and f.published_at<=data_as_of and f.received_at<=data_as_of)
        latest_quarter=max((f.period_end for f in values if f.period_type is FinancialPeriodType.QUARTERLY),default=None);latest_annual=max((f.period_end for f in values if f.period_type is FinancialPeriodType.ANNUAL),default=None)
        flags=(FinancialQualityFlag.COMPLETE,) if values else (FinancialQualityFlag.INSUFFICIENT_HISTORY,)
        digest=hashlib.sha256("|".join(f.fact_id for f in values).encode()).hexdigest()[:16]
        return FundamentalSnapshot(f"snapshot:{instrument.instrument_id}:{data_as_of.isoformat()}:{digest}",instrument,scope,data_as_of,latest_quarter,latest_annual,values,(),flags,tuple(f.fact_id for f in values))
    def _derived(self,anchor:FinancialFact,value:Decimal,period_type:FinancialPeriodType,basis:FinancialValueBasis,quarter:int|None,parents:tuple[str,...],period_start:datetime|None)->FinancialFact:
        key="|".join((anchor.instrument.instrument_id,anchor.metric.value,period_type.value,anchor.period_end.isoformat(),*parents));identifier="derived:"+hashlib.sha256(key.encode()).hexdigest()[:24]
        return FinancialFact(identifier,anchor.instrument,anchor.metric,value,anchor.currency,anchor.unit,anchor.scale,period_type,basis,period_start,anchor.period_end,anchor.fiscal_year,quarter,anchor.statement_scope,FundamentalFactKind.DERIVED,"financial_derivation",None,anchor.source_reference,anchor.published_at,anchor.received_at,"financial-derived-v1",("DERIVED",),parents,None,(FinancialQualityFlag.COMPLETE,))
    def _unavailable(self,label:str,anchor:FinancialFact,reason:str)->FinancialDerivedMetric:return FinancialDerivedMetric(label,anchor.instrument.instrument_id,None,anchor.period_end,anchor.statement_scope,(anchor.fact_id,),(FinancialQualityFlag.PARTIAL,FinancialQualityFlag.INSUFFICIENT_HISTORY),reason)


def _fact_id(value:StructuredFinancialRecord)->str:
    raw="|".join((value.source,value.filing_id,value.instrument.instrument_id,value.metric.value,value.period_type.value,value.period_end.isoformat(),value.statement_scope.value,value.source_reference or ""));return "fact:"+hashlib.sha256(raw.encode()).hexdigest()[:24]
def _compatible(left:FinancialFact,right:FinancialFact,*,same_metric:bool=False)->bool:return left.instrument.instrument_id==right.instrument.instrument_id and (not same_metric or left.metric==right.metric) and left.statement_scope==right.statement_scope and left.currency==right.currency and left.unit==right.unit and left.scale==right.scale
