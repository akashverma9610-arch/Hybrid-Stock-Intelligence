"""Immutable canonical financial-fact contracts; this module performs no retrieval."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from app.data_sources.models import FundamentalFactKind
from app.market_data.models import InstrumentIdentity


class FinancialMetric(StrEnum):
    REVENUE="REVENUE"; OTHER_INCOME="OTHER_INCOME"; EBITDA="EBITDA"; OPERATING_PROFIT="OPERATING_PROFIT"; EBIT="EBIT"; DEPRECIATION="DEPRECIATION"; FINANCE_COST="FINANCE_COST"; PBT="PBT"; TAX="TAX"; PAT="PAT"; MINORITY_INTEREST="MINORITY_INTEREST"; EPS_BASIC="EPS_BASIC"; EPS_DILUTED="EPS_DILUTED"
    TOTAL_ASSETS="TOTAL_ASSETS"; TOTAL_LIABILITIES="TOTAL_LIABILITIES"; TOTAL_EQUITY="TOTAL_EQUITY"; NET_WORTH="NET_WORTH"; TOTAL_DEBT="TOTAL_DEBT"; CURRENT_BORROWINGS="CURRENT_BORROWINGS"; NONCURRENT_BORROWINGS="NONCURRENT_BORROWINGS"; CASH_AND_EQUIVALENTS="CASH_AND_EQUIVALENTS"; OTHER_BANK_BALANCES="OTHER_BANK_BALANCES"; CURRENT_ASSETS="CURRENT_ASSETS"; CURRENT_LIABILITIES="CURRENT_LIABILITIES"; INVENTORY="INVENTORY"; RECEIVABLES="RECEIVABLES"; PAYABLES="PAYABLES"
    CFO="CFO"; CFI="CFI"; CFF="CFF"; CAPEX="CAPEX"; PURCHASE_OF_PROPERTY_PLANT_EQUIPMENT="PURCHASE_OF_PROPERTY_PLANT_EQUIPMENT"; PURCHASE_OF_INTANGIBLE_ASSETS="PURCHASE_OF_INTANGIBLE_ASSETS"; FREE_CASH_FLOW="FREE_CASH_FLOW"; SHARES_OUTSTANDING="SHARES_OUTSTANDING"; FACE_VALUE="FACE_VALUE"


class FinancialPeriodType(StrEnum):
    QUARTERLY="QUARTERLY"; ANNUAL="ANNUAL"; TRAILING_TWELVE_MONTHS="TRAILING_TWELVE_MONTHS"; POINT_IN_TIME="POINT_IN_TIME"


class StatementScope(StrEnum): STANDALONE="STANDALONE"; CONSOLIDATED="CONSOLIDATED"; UNKNOWN="UNKNOWN"
class FinancialValueBasis(StrEnum): QUARTER_ONLY="QUARTER_ONLY"; YEAR_TO_DATE="YEAR_TO_DATE"; FULL_YEAR="FULL_YEAR"; UNKNOWN="UNKNOWN"
class NumericScale(StrEnum): UNITS="UNITS"; THOUSANDS="THOUSANDS"; LAKHS="LAKHS"; CRORES="CRORES"; MILLIONS="MILLIONS"
class FinancialValueDimension(StrEnum): MONETARY="MONETARY"; PER_SHARE="PER_SHARE"; PERCENTAGE="PERCENTAGE"; RATIO="RATIO"; COUNT="COUNT"
class FinancialQualityFlag(StrEnum): COMPLETE="COMPLETE"; PARTIAL="PARTIAL"; INCONSISTENT="INCONSISTENT"; REVISED="REVISED"; INSUFFICIENT_HISTORY="INSUFFICIENT_HISTORY"; UNKNOWN_BASIS="UNKNOWN_BASIS"


@dataclass(frozen=True, slots=True)
class StructuredFinancialRecord:
    """Provider-neutral structured input; document/PDF parsing is explicitly out of scope."""
    instrument: InstrumentIdentity; metric: FinancialMetric; value: Decimal; currency: str; unit: str
    scale: NumericScale; period_type: FinancialPeriodType; value_basis: FinancialValueBasis
    period_start: datetime | None; period_end: datetime; fiscal_year: int | None; fiscal_quarter: int | None
    statement_scope: StatementScope; source: str; filing_id: str; published_at: datetime; received_at: datetime
    source_reference: str | None = None; attachment_reference: str | None = None; normalization_version: str = "financial-facts-v1"
    revision_of_fact_id: str | None = None; provenance: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class FinancialFact:
    fact_id: str; instrument: InstrumentIdentity; metric: FinancialMetric; value: Decimal; currency: str; unit: str
    scale: NumericScale; period_type: FinancialPeriodType; value_basis: FinancialValueBasis; period_start: datetime | None
    period_end: datetime; fiscal_year: int | None; fiscal_quarter: int | None; statement_scope: StatementScope
    fact_kind: FundamentalFactKind; source: str; filing_id: str | None; source_reference: str | None
    published_at: datetime; received_at: datetime; normalization_version: str; provenance: tuple[str, ...] = ()
    parent_fact_ids: tuple[str, ...] = (); revision_of_fact_id: str | None = None
    quality_flags: tuple[FinancialQualityFlag, ...] = (FinancialQualityFlag.COMPLETE,)

    def __post_init__(self) -> None:
        if not self.fact_id or not self.source or not self.currency or not self.unit: raise ValueError("Financial fact identity, source, currency, and unit are required.")
        if self.published_at.tzinfo is None or self.received_at.tzinfo is None or self.period_end.tzinfo is None: raise ValueError("Financial fact timestamps must be timezone-aware.")
        if self.received_at < self.published_at: raise ValueError("Financial fact receipt cannot precede publication.")
        if self.fact_kind is FundamentalFactKind.REPORTED and not self.filing_id: raise ValueError("Reported financial facts require a filing ID.")
        if self.period_type is FinancialPeriodType.QUARTERLY and self.fiscal_quarter not in {1,2,3,4,None}: raise ValueError("Fiscal quarter must be between one and four.")
        if self.fact_kind is FundamentalFactKind.DERIVED and not self.parent_fact_ids: raise ValueError("Derived financial facts require immutable parent fact references.")

    @property
    def available_at(self) -> datetime: return max(self.published_at, self.received_at)

    @property
    def value_dimension(self) -> FinancialValueDimension:
        """Deterministic semantic dimension without changing persisted shape.

        Numeric scale describes a representation; it must never turn EPS into
        a monetary value merely because a filing has a statement-wide display
        rounding declaration.
        """
        if self.metric in {FinancialMetric.EPS_BASIC, FinancialMetric.EPS_DILUTED, FinancialMetric.FACE_VALUE}:
            return FinancialValueDimension.PER_SHARE
        if self.metric is FinancialMetric.SHARES_OUTSTANDING:
            return FinancialValueDimension.COUNT
        return FinancialValueDimension.MONETARY


@dataclass(frozen=True, slots=True)
class FinancialDerivedMetric:
    metric: str; instrument_id: str; value: Decimal | None; period_end: datetime; statement_scope: StatementScope
    parent_fact_ids: tuple[str, ...]; quality_flags: tuple[FinancialQualityFlag, ...]; calculation_version: str = "financial-derived-v1"


@dataclass(frozen=True, slots=True)
class FundamentalSnapshot:
    snapshot_id: str; instrument: InstrumentIdentity; statement_scope: StatementScope; data_as_of: datetime
    latest_quarter_end: datetime | None; latest_annual_end: datetime | None; values: tuple[FinancialFact, ...]
    derived_metrics: tuple[FinancialDerivedMetric, ...]; quality_flags: tuple[FinancialQualityFlag, ...]
    provenance: tuple[str, ...]; normalization_version: str = "fundamental-snapshot-v1"
