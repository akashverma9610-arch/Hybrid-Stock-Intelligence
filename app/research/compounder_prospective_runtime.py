"""Local composition for the explicit Compounder prospective-shadow command."""
from __future__ import annotations

from datetime import datetime

from app.fundamentals.store import SQLiteFinancialFactStore
from app.historical.nse_session_identity import NseSessionPointIdentityStore
from app.historical.pit_company_type_classification_activation import PitCompanyTypeClassificationStore
from app.intelligence.compounder_prospective_shadow_validation import (
    CompounderProspectiveShadowStore,
    CompounderProspectiveBatchReport,
    run_compounder_prospective_batch,
)
from app.storage.database import DatabaseBackend, DatabaseSettings
from app.storage.repository_factory import create_core_api_snapshot_repository


def run_local_compounder_prospective_shadow(*, as_of: datetime) -> CompounderProspectiveBatchReport:
    """Run one explicit-cutoff batch against the operator's persistent SQLite DB."""
    database = DatabaseSettings.local_runtime()
    if database.backend is not DatabaseBackend.SQLITE or database.url.endswith(":memory:"):
        raise ValueError("COMPOUNDER_PROSPECTIVE_SHADOW_REQUIRES_PERSISTENT_SQLITE")
    path = database.url.removeprefix("sqlite:///")
    repository = create_core_api_snapshot_repository(database)
    facts = SQLiteFinancialFactStore(path)
    try:
        report, _ = run_compounder_prospective_batch(
            as_of=as_of,
            company_type_receipts=PitCompanyTypeClassificationStore(repository).receipts(),
            security_identities=NseSessionPointIdentityStore(repository).receipts(),
            facts_for_instrument=facts.facts,
            store=CompounderProspectiveShadowStore(repository),
        )
        return report
    finally:
        facts._connection.close()
        if hasattr(repository, "close"):
            repository.close()
