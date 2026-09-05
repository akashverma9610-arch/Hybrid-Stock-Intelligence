"""Local composition for the explicit Inflection accounting-shadow command."""
from __future__ import annotations

from datetime import datetime

from app.filings.store import SQLiteCorporateFilingsStore
from app.fundamentals.store import SQLiteFinancialFactStore
from app.historical.pit_company_type_classification_activation import PitCompanyTypeClassificationStore
from app.intelligence.inflection_accounting_prospective_shadow import (
    InflectionAccountingProspectiveBatchReport, InflectionAccountingProspectiveStore,
    run_inflection_accounting_prospective_batch,
)
from app.storage.database import DatabaseBackend, DatabaseSettings
from app.storage.repository_factory import create_core_api_snapshot_repository


def run_local_inflection_accounting_prospective_shadow(*, as_of: datetime) -> InflectionAccountingProspectiveBatchReport:
    """Persist one explicit-cutoff, forward-only accounting receipt batch."""
    database = DatabaseSettings.local_runtime()
    if database.backend is not DatabaseBackend.SQLITE or database.url.endswith(":memory:"):
        raise ValueError("INFLECTION_ACCOUNTING_PROSPECTIVE_SHADOW_REQUIRES_PERSISTENT_SQLITE")
    path = database.url.removeprefix("sqlite:///")
    repository = create_core_api_snapshot_repository(database)
    facts = SQLiteFinancialFactStore(path)
    filings = SQLiteCorporateFilingsStore(path)
    try:
        report, _ = run_inflection_accounting_prospective_batch(
            as_of=as_of,
            company_type_receipts=PitCompanyTypeClassificationStore(repository).receipts(),
            facts_for_instrument=facts.facts,
            filings_for_instrument=lambda instrument: filings.list(instrument_id=instrument, limit=500),
            store=InflectionAccountingProspectiveStore(repository),
        )
        return report
    finally:
        facts._connection.close()
        filings._connection.close()
        if hasattr(repository, "close"):
            repository.close()
