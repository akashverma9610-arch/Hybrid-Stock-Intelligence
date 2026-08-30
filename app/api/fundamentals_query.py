from datetime import datetime
from typing import Protocol

from app.api.errors import APIRequestError
from app.fundamentals.models import FinancialFact, FinancialMetric, FinancialPeriodType, FundamentalSnapshot, StatementScope
from app.fundamentals.service import FinancialDerivationService
from app.fundamentals.store import FinancialFactStore


class FundamentalsQueryService(Protocol):
    def snapshot(self, symbol: str, *, as_of: datetime | None, scope: StatementScope) -> FundamentalSnapshot: ...
    def series(self, symbol: str, metric: FinancialMetric, *, period_type: FinancialPeriodType | None, scope: StatementScope | None, as_of: datetime | None, limit: int) -> tuple[FinancialFact, ...]: ...


class UnavailableFundamentalsQueryService:
    def snapshot(self, *args, **kwargs): raise APIRequestError(status_code=503, code="FUNDAMENTALS_UNAVAILABLE", message="Canonical financial facts are unavailable.")
    def series(self, *args, **kwargs): raise APIRequestError(status_code=503, code="FUNDAMENTALS_UNAVAILABLE", message="Canonical financial facts are unavailable.")


class RepositoryFundamentalsQueryService:
    def __init__(self, store: FinancialFactStore) -> None: self._store=store;self._derive=FinancialDerivationService()
    def series(self,symbol,metric,*,period_type,scope,as_of,limit): return self._store.series(symbol,metric,period_type=period_type,scope=scope,as_of=as_of,limit=limit)
    def snapshot(self,symbol,*,as_of,scope):
        if as_of is None: raise APIRequestError(status_code=422,code="AS_OF_REQUIRED",message="Fundamental snapshots require an as_of timestamp.")
        values=self._store.facts(symbol,scope=scope,as_of=as_of,limit=500)
        if not values: raise APIRequestError(status_code=404,code="FUNDAMENTALS_NOT_FOUND",message="No eligible financial facts were found.")
        return self._derive.snapshot(values[0].instrument,values,data_as_of=as_of,scope=scope)
