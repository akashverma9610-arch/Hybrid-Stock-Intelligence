"""Persistent local Shared-Brain/U16 composition regressions."""
from __future__ import annotations

from datetime import UTC, datetime

from fastapi.testclient import TestClient

import test_brain_research_comparison_state_v2 as v2_helpers
from app.api.main import create_app
from app.api.settings import APISettings
from app.fundamentals.store import SQLiteFinancialFactStore
from app.intelligence.unified_state import BrainOutputContext
from app.storage.database import DatabaseSettings
from app.storage.repository_factory import create_core_api_snapshot_repository
from app.universe_analysis.models import NseEquityInstrument
from app.universe_analysis.service import CoreUniverseAnalysisStore, build_universe_snapshot


T = datetime(2026, 8, 30, tzinfo=UTC)


def test_u16_api_uses_the_configured_persistent_shared_brain_root(tmp_path):
    path = tmp_path / "persistent-shared-brain.sqlite"
    settings = DatabaseSettings(url=f"sqlite:///{path}")
    repository = create_core_api_snapshot_repository(settings)
    universe = CoreUniverseAnalysisStore(repository)
    instrument = NseEquityInstrument(
        "NSE:ALPHA", "ALPHA", "INE000A01001", None, None, "LISTED", None,
        True, T, "NSE_OFFICIAL", company_name="Alpha Limited",
    )
    universe.save_instrument(instrument)
    universe.save_universe_snapshot(build_universe_snapshot(
        snapshot_id="persistent-universe", as_of=T, source="NSE_OFFICIAL", instruments=(instrument,),
    ))
    SQLiteFinancialFactStore(path).save(v2_helpers._fact(
        "persistent-revenue", period_end=datetime(2026, 6, 30, tzinfo=UTC), as_of=T,
    ))
    repository.close()

    app = create_app(api_settings=APISettings(database=settings))
    with TestClient(app) as client:
        response = client.get(
            "/api/v1/stocks/ALPHA/shared-brain",
            params={"context": BrainOutputContext.DEEP_ANALYSIS.value, "as_of": T.isoformat()},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["canonical_instrument_id"] == "NSE:ALPHA"
    assert payload["evidence_status"] == "PARTIAL"
    assert {item["domain"]: item["availability"] for item in payload["evidence_domains"]}["FUNDAMENTALS"] == "AVAILABLE"
