from datetime import datetime
from typing import Protocol

from app.api.errors import APIRequestError
from app.filings.models import CorporateFiling, FilingType
from app.filings.store import CorporateFilingsStore
from app.market_data.models import Exchange


class FilingsQueryService(Protocol):
    def list_filings(self, *, instrument_id: str | None, filing_type: FilingType | None, start: datetime | None, end: datetime | None, limit: int) -> tuple[CorporateFiling, ...]: ...
    def filing(self, filing_id: str) -> CorporateFiling: ...


class UnavailableFilingsQueryService:
    def list_filings(self, **kwargs):
        del kwargs; raise APIRequestError(status_code=503, code="FILINGS_UNAVAILABLE", message="Corporate filing data is unavailable.")
    def filing(self, filing_id: str):
        del filing_id; raise APIRequestError(status_code=503, code="FILINGS_UNAVAILABLE", message="Corporate filing data is unavailable.")


class RepositoryFilingsQueryService:
    def __init__(self, store: CorporateFilingsStore) -> None: self._store = store
    def list_filings(self, *, instrument_id, filing_type, start, end, limit): return self._store.list(instrument_id=instrument_id, filing_type=filing_type, start=start, end=end, limit=limit)
    def filing(self, filing_id: str):
        value = self._store.get(filing_id)
        if value is None: raise APIRequestError(status_code=404, code="FILING_NOT_FOUND", message="Corporate filing was not found.")
        return value
