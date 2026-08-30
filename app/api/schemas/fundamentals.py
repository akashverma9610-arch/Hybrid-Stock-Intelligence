from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel

class FinancialFactResponse(BaseModel):
    fact_id:str; instrument_id:str; metric:str; value:Decimal; currency:str; unit:str; scale:str; period_type:str; value_basis:str; period_start:datetime|None; period_end:datetime; fiscal_year:int|None; fiscal_quarter:int|None; statement_scope:str; fact_kind:str; source:str; filing_id:str|None; source_reference:str|None; published_at:datetime; received_at:datetime; normalization_version:str; provenance:tuple[str,...]; parent_fact_ids:tuple[str,...]; revision_of_fact_id:str|None; quality_flags:tuple[str,...]
class FinancialSeriesResponse(BaseModel): items:tuple[FinancialFactResponse,...]
class FundamentalSnapshotResponse(BaseModel): snapshot_id:str; instrument_id:str; statement_scope:str; data_as_of:datetime; latest_quarter_end:datetime|None; latest_annual_end:datetime|None; quality_flags:tuple[str,...]; provenance:tuple[str,...]; values:tuple[FinancialFactResponse,...]
