"""U16 read-only application-service and public-DTO coverage."""
from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import test_brain_research_comparison_state_v2 as v2_helpers
import test_shared_brain_production as u15
from app.api.main import create_app
from app.intelligence.shared_brain_application import (
    SharedBrainApplicationError,
    SharedBrainApplicationInputs,
    SharedBrainApplicationService,
)
from app.fundamentals.financial_research_observation_wrapper import wrap_financial_research_observation_bundle
from app.fundamentals.financial_research_observation_wrapper_schema import (
    CURRENT_FROZEN_FINANCIAL_RESEARCH_OBSERVATION_WRAPPER_SCHEMA,
)
from app.fundamentals.store import SQLiteFinancialFactStore
from app.intelligence.unified_state import BrainOutputContext
from app.intelligence.shared_brain_application import StoredSharedBrainEvidenceAssembler
from app.universe_analysis.models import NseEquityInstrument


T = u15.T


class _Resolver:
    def __init__(self) -> None:
        self.calls: list[tuple[str, datetime]] = []
        self.instrument = NseEquityInstrument(
            "NSE:ALPHA", "ALPHA", "INE000A01001", "DEMO", "SOFTWARE",
            "LISTED", None, True, T, "TEST_OFFICIAL", company_name="Alpha Limited",
        )

    def resolve(self, identifier: str, *, as_of: datetime) -> NseEquityInstrument:
        self.calls.append((identifier, as_of))
        if identifier.strip().upper() not in {"ALPHA", "NSE:ALPHA"}:
            raise SharedBrainApplicationError("SHARED_BRAIN_INSTRUMENT_NOT_FOUND", "The requested canonical NSE instrument is not available at this cutoff.")
        return self.instrument


class _Assembler:
    def __init__(self, bundle) -> None:
        self.bundle = bundle
        self.calls: list[tuple[str, datetime]] = []

    def assemble(self, instrument, *, as_of: datetime) -> SharedBrainApplicationInputs:
        self.calls.append((instrument.instrument_id, as_of))
        assert as_of == self.bundle.as_of
        return SharedBrainApplicationInputs(
            u15._unified(as_of=as_of), self.bundle,
            wrap_financial_research_observation_bundle(
                self.bundle,
                wrapper_schema=CURRENT_FROZEN_FINANCIAL_RESEARCH_OBSERVATION_WRAPPER_SCHEMA,
            ), self.bundle.failures,
        )


def _service(bundle=None) -> tuple[SharedBrainApplicationService, _Resolver, _Assembler]:
    assembler = _Assembler(bundle or u15._rich_bundle())
    resolver = _Resolver()
    return SharedBrainApplicationService(resolver=resolver, evidence_assembler=assembler, clock=lambda: T), resolver, assembler


def test_service_resolves_exact_instrument_propagates_as_of_and_reuses_u15_snapshot():
    service, resolver, assembler = _service()
    view = service.analyze_stock("alpha", context=BrainOutputContext.DEEP_ANALYSIS, as_of=T)
    assert (view.canonical_instrument_id, view.symbol, view.as_of) == ("NSE:ALPHA", "ALPHA", T)
    assert resolver.calls == [("alpha", T)] and assembler.calls == [("NSE:ALPHA", T)]
    assert view.snapshot_fingerprint and view.brain_research_state_v2_fingerprint
    assert view.materiality_calibration_status == "CALIBRATION_REQUIRED"


def test_all_existing_contexts_share_the_identical_financial_semantic_artifacts():
    service, _, _ = _service()
    views = tuple(service.analyze_stock("ALPHA", context=context, as_of=T) for context in BrainOutputContext)
    assert {item.snapshot_fingerprint for item in views} == {views[0].snapshot_fingerprint}
    assert {item.financial_semantic_section_fingerprint for item in views} == {views[0].financial_semantic_section_fingerprint}
    assert {tuple(item.trajectory_fingerprint for item in view.financial_semantics) for view in views} == {
        tuple(item.trajectory_fingerprint for item in views[0].financial_semantics)
    }
    assert len({item.context_projection_fingerprint for item in views}) == len(BrainOutputContext)


def test_display_only_factual_phrase_preserves_existing_directionality_and_calibration_status():
    service, _, _ = _service()
    view = service.analyze_stock("ALPHA", context=BrainOutputContext.DEEP_ANALYSIS, as_of=T)
    by_pair = {(item.metric, item.trajectory_basis): item for item in view.financial_semantics}
    pat = by_pair[("PAT", "YEAR_OVER_YEAR_QUARTER")]
    assert (pat.previous_value, pat.current_value, pat.absolute_delta) == (-100, -50, 50)
    assert pat.factual_display_phrase == "loss narrowed"
    assert pat.directionality_orientation == "POTENTIALLY_FAVORABLE"
    assert pat.materiality_governance_state == "CALIBRATION_REQUIRED"
    assert all(item.materiality_governance_state != "MATERIAL" for item in view.financial_semantics)


def test_invalid_instrument_and_naive_as_of_fail_as_typed_read_only_errors():
    service, _, _ = _service()
    with pytest.raises(SharedBrainApplicationError, match="available") as missing:
        service.analyze_stock("UNKNOWN", context=BrainOutputContext.DEEP_ANALYSIS, as_of=T)
    assert missing.value.code == "SHARED_BRAIN_INSTRUMENT_NOT_FOUND"
    with pytest.raises(SharedBrainApplicationError, match="timezone") as naive:
        service.analyze_stock("ALPHA", context=BrainOutputContext.DEEP_ANALYSIS, as_of=datetime(2026, 8, 1))
    assert naive.value.code == "SHARED_BRAIN_AS_OF_TIMEZONE_REQUIRED"


def test_failure_only_bundle_returns_partial_usable_view_with_blockers_not_a_fake_neutral():
    failure = v2_helpers._failure(as_of=T)
    service, _, _ = _service(u15._bundle(failures=(failure,)))
    view = service.analyze_stock("ALPHA", context=BrainOutputContext.DEEP_ANALYSIS, as_of=T)
    assert view.financial_semantics == ()
    assert "NO_PIT_ELIGIBLE_FACT" in view.blockers
    assert view.evidence_status == "PARTIAL"


def test_public_route_returns_controlled_dto_and_never_a_raw_internal_snapshot():
    service, _, _ = _service()
    with TestClient(create_app(shared_brain_application_service=service)) as client:
        params = {"context": "DEEP_ANALYSIS", "as_of": T.isoformat()}
        response = client.get("/api/v1/stocks/ALPHA/shared-brain", params=params)
        missing = client.get("/api/v1/stocks/UNKNOWN/shared-brain", params=params)
    assert response.status_code == 200
    payload = response.json()
    assert payload["canonical_instrument_id"] == "NSE:ALPHA"
    assert payload["financial_semantics"] and payload["materiality_calibration_status"] == "CALIBRATION_REQUIRED"
    assert payload["forward_performance_intelligence"]["instrument_history"]["evidence_sufficiency"] == "NO_EVIDENCE"
    assert "unified_state" not in payload and "financial_bundle" not in payload
    assert missing.status_code == 404 and missing.json()["error"]["code"] == "SHARED_BRAIN_INSTRUMENT_NOT_FOUND"


def test_service_is_deterministic_and_read_only_without_provider_or_action_imports():
    service, _, _ = _service()
    assert service.analyze_stock("ALPHA", context=BrainOutputContext.DEEP_ANALYSIS, as_of=T) == service.analyze_stock("ALPHA", context=BrainOutputContext.DEEP_ANALYSIS, as_of=T)
    source = (Path(__file__).parents[2] / "app" / "intelligence" / "shared_brain_application.py").read_text(encoding="utf-8")
    for forbidden in ("requests", "urllib", "NeoAPI", "yfinance", "save(", "BUY", "SELL", "scorecard", "ExecutionGate"):
        assert forbidden not in source


def test_stored_fact_assembler_builds_one_pit_valid_bundle_without_writing(tmp_path):
    store = SQLiteFinancialFactStore(tmp_path / "facts.sqlite")
    first = v2_helpers._fact("stored-q1", period_end=datetime(2026, 6, 30, tzinfo=UTC), as_of=T)
    second = v2_helpers._fact("stored-q2", period_end=datetime(2026, 9, 30, tzinfo=UTC), as_of=T)
    store.save(first)
    store.save(second)
    instrument = _Resolver().instrument
    result = StoredSharedBrainEvidenceAssembler(store).assemble(instrument, as_of=T)
    assert result.unified_state.canonical_instrument_id == "NSE:ALPHA"
    assert len(result.financial_bundle.observations) == 2
    assert len(result.financial_wrappers) == 2 and result.financial_failures == ()


def test_stored_financial_and_earnings_lineage_can_share_one_integrity_artifact():
    """One official fact legitimately projects to both evidence domains."""
    store = SQLiteFinancialFactStore(":memory:")
    fact = v2_helpers._fact("shared-lineage", period_end=datetime(2026, 6, 30, tzinfo=UTC), as_of=T)
    store.save(fact)
    service = SharedBrainApplicationService(
        resolver=_Resolver(),
        evidence_assembler=StoredSharedBrainEvidenceAssembler(store),
        clock=lambda: T,
    )

    view = service.analyze_stock("ALPHA", context=BrainOutputContext.DEEP_ANALYSIS, as_of=T)

    assert view.evidence_status == "PARTIAL"
    assert dict(view.evidence_domains)["FUNDAMENTALS"] == "AVAILABLE"
    assert dict(view.evidence_domains)["EARNINGS"] == "AVAILABLE"
