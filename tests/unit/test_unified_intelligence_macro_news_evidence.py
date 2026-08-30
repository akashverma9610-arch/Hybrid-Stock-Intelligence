from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.data_sources.models import DataFamily, SourceRecordProvenance
from app.domain.models import FreshnessStatus
from app.filings.models import CorporateFiling, FilingType, PrimarySourceQuality
from app.filings.store import SQLiteCorporateFilingsStore
from app.historical.guard import manifest_fingerprint
from app.intelligence.catalysts import CatalystEvent, CatalystType
from app.intelligence.catalysts.service import PricedInState
from app.intelligence.company_evidence import CompositeStoredIntelligenceSource
from app.intelligence.macro import MacroEvidence, MacroInputFamily, MacroState
from app.intelligence.macro.service import IntelligenceSourceTier
from app.intelligence.macro_news_evidence import MacroNewsEvidenceStoredSource
from app.intelligence.store import IntelligenceSnapshotStore
from app.intelligence.unified_state import (
    IntelligenceEvidenceAvailability,
    IntelligenceEvidenceDomain,
    IntelligenceInvalidationDomain,
)
from app.intelligence.unified_state_builder import StoredIntelligenceArtifact, UnifiedIntelligenceStateBuilder
from app.market_data.models import Exchange, InstrumentIdentity, InstrumentType, MarketDataProvenance
from app.news.models import NewsArticleEvidence, NewsEventCategory, NewsSourceQuality
from app.news.store import SQLiteNewsEvidenceStore
from app.storage.core_api_snapshot_repository import CoreApiSnapshotFamily
from app.storage.sqlite_core_api_snapshot_repository import SQLiteCoreApiSnapshotRepository


T = datetime(2026, 8, 28, 12, tzinfo=UTC)
ALPHA = InstrumentIdentity("NSE:ALPHA", Exchange.NSE, "ALPHA", "ALPHA", "INE000A01001", "EQ", InstrumentType.NSE_EQUITY, "Alpha Ltd")
BETA = InstrumentIdentity("NSE:BETA", Exchange.NSE, "BETA", "BETA", "INE000A01002", "EQ", InstrumentType.NSE_EQUITY, "Beta Ltd")


class _CoreSource:
    def list_stored_intelligence_artifacts(self, canonical_instrument_id: str, *, as_of: datetime):
        return tuple(
            StoredIntelligenceArtifact(
                canonical_instrument_id, domain, f"core:{canonical_instrument_id}:{domain.value}",
                manifest_fingerprint(instrument=canonical_instrument_id, domain=domain.value),
                IntelligenceEvidenceAvailability.AVAILABLE, T - timedelta(days=1), T - timedelta(days=1),
                T - timedelta(days=1), FreshnessStatus.FRESH, None, None, None,
                IntelligenceInvalidationDomain.PRICE if domain is IntelligenceEvidenceDomain.MARKET_DATA else IntelligenceInvalidationDomain.REFERENCE_DATA,
            )
            for domain in (IntelligenceEvidenceDomain.REFERENCE_DATA, IntelligenceEvidenceDomain.MARKET_DATA)
        )


class _MacroSource:
    def __init__(self, values: tuple[MacroEvidence, ...]) -> None:
        self.values = values

    def list_stored_macro_evidence(self, *, as_of: datetime) -> tuple[MacroEvidence, ...]:
        return self.values


class _CatalystSource:
    def __init__(self, values: tuple[CatalystEvent, ...]) -> None:
        self.values = values

    def list_stored_catalyst_events(self, canonical_instrument_id: str, *, as_of: datetime) -> tuple[CatalystEvent, ...]:
        return self.values


def _macro(identifier: str, *, available: datetime = T - timedelta(days=1), freshness: str = "FRESH") -> MacroEvidence:
    return MacroEvidence(
        identifier, MacroInputFamily.MONETARY_RATES, "rates", "TIGHTENING", IntelligenceSourceTier.OFFICIAL,
        f"official:{identifier}", available - timedelta(hours=1), available - timedelta(hours=1), available,
        available - timedelta(hours=1), 0.9, freshness,
    )


def _news(identifier: str, *, instrument_ids: tuple[str, ...] = (ALPHA.instrument_id,), published: datetime = T - timedelta(days=2), received: datetime | None = None, quality: NewsSourceQuality = NewsSourceQuality.REPUTABLE_NEWS, warnings: tuple[str, ...] = ()) -> NewsArticleEvidence:
    arrival = received or published
    provenance = SourceRecordProvenance(
        identifier, "stored-news", f"source:{identifier}", published, published, arrival, None, None,
        DataFamily.NEWS_RESEARCH, "v1", "v1",
    )
    return NewsArticleEvidence(
        identifier, "stored-news", "Publisher", None, f"https://example.test/{identifier}", "Bounded title", "Bounded description",
        published, arrival, "en", "in", instrument_ids, (), (), quality, provenance,
        NewsEventCategory.ORDER_CONTRACT, None, (), warnings,
    )


def _filing(identifier: str) -> CorporateFiling:
    return CorporateFiling(
        identifier, ALPHA, Exchange.NSE, "NSE_OFFICIAL_FILINGS", PrimarySourceQuality.PRIMARY_EXCHANGE,
        FilingType.ORDER_CONTRACT, None, "Order disclosure", T - timedelta(days=2), T - timedelta(days=1),
        f"source:{identifier}", None,
        MarketDataProvenance("NSE_OFFICIAL_FILINGS", None, T - timedelta(days=2), T - timedelta(days=2), T - timedelta(days=1), "v1"),
    )


def _catalyst(identifier: str, *, company_id: str | None = ALPHA.instrument_id) -> CatalystEvent:
    return CatalystEvent(
        identifier, CatalystType.ORDER_WIN, company_id, "INDUSTRIAL", T - timedelta(days=3), T - timedelta(days=2),
        T - timedelta(days=1), NewsSourceQuality.PRIMARY_EXCHANGE, True, True, "UNCERTAIN", None,
        PricedInState.UNKNOWN, None, "cluster", ("news-1",), (),
    )


def _builder(*, macro=None, macro_snapshots=None, filings=None, news=None, catalysts=None, catalyst_snapshots=None) -> UnifiedIntelligenceStateBuilder:
    source = MacroNewsEvidenceStoredSource(
        macro_evidence_source=_MacroSource(tuple(macro)) if macro is not None else None,
        macro_snapshots=macro_snapshots,
        filings=filings,
        news=news,
        catalyst_source=_CatalystSource(tuple(catalysts)) if catalysts is not None else None,
        catalyst_snapshots=catalyst_snapshots,
    )
    return UnifiedIntelligenceStateBuilder(CompositeStoredIntelligenceSource(_CoreSource(), source))


def _reference(state, domain: IntelligenceEvidenceDomain):
    return next(item for item in state.evidence_references if item.domain is domain)


def test_durable_macro_evidence_is_global_pit_safe_and_deterministic() -> None:
    values = (_macro("a"), _macro("b"))
    first = _builder(macro=values).build(ALPHA.instrument_id, as_of=T)
    second = _builder(macro=tuple(reversed(values))).build(ALPHA.instrument_id, as_of=T)
    beta = _builder(macro=values).build(BETA.instrument_id, as_of=T)
    macro = _reference(first, IntelligenceEvidenceDomain.MACRO)
    assert macro.availability is IntelligenceEvidenceAvailability.AVAILABLE
    assert macro.artifact_ids == ("macro-evidence:a", "macro-evidence:b")
    assert first.fingerprint == second.fingerprint
    assert _reference(beta, IntelligenceEvidenceDomain.MACRO).artifact_ids == macro.artifact_ids
    assert all(item.invalidation_domain is IntelligenceInvalidationDomain.MACRO for item in first.dependency_lineage if item.artifact_id.startswith("macro-"))


def test_macro_future_and_first_observed_evidence_never_backdate() -> None:
    future = _macro("future", available=T + timedelta(days=1))
    first_observed = _macro("first-observed", available=T + timedelta(days=1))
    builder = _builder(macro=(future, first_observed))
    before = builder.build(ALPHA.instrument_id, as_of=T)
    after = builder.build(ALPHA.instrument_id, as_of=T + timedelta(days=1))
    assert _reference(before, IntelligenceEvidenceDomain.MACRO).availability is IntelligenceEvidenceAvailability.UNAVAILABLE
    assert _reference(after, IntelligenceEvidenceDomain.MACRO).artifact_ids == ("macro-evidence:first-observed", "macro-evidence:future")
    assert before.fingerprint != after.fingerprint


def test_macro_missing_durable_boundary_is_explicit() -> None:
    macro = _reference(_builder().build(ALPHA.instrument_id, as_of=T), IntelligenceEvidenceDomain.MACRO)
    assert macro.availability is IntelligenceEvidenceAvailability.UNAVAILABLE
    assert macro.warnings == ("MACRO_DURABLE_READ_BOUNDARY_MISSING",)


def test_immutable_first_observed_macro_snapshot_is_bounded_without_recomputation(tmp_path: Path) -> None:
    repository = SQLiteCoreApiSnapshotRepository(tmp_path / "snapshots.sqlite")
    value = MacroState("stored-macro", T - timedelta(days=1), None, None, None, None, None, None, None, (), ("source-evidence",), None, (), "macro-state-v1")
    IntelligenceSnapshotStore(repository).save(
        record_id=value.state_id, family=CoreApiSnapshotFamily.MACRO_STATE, value=value,
        created_at=T - timedelta(hours=12),
    )
    macro = _reference(_builder(macro_snapshots=repository).build(ALPHA.instrument_id, as_of=T), IntelligenceEvidenceDomain.MACRO)
    assert macro.availability is IntelligenceEvidenceAvailability.PARTIAL
    assert macro.artifact_ids == ("macro-state:stored-macro",)
    assert "MACRO_DERIVED_STATE_FIRST_OBSERVED_ONLY" in macro.warnings


def test_news_preserves_official_and_secondary_authority_without_raw_payload(tmp_path: Path) -> None:
    filing_store = SQLiteCorporateFilingsStore(tmp_path / "filings.sqlite")
    news_store = SQLiteNewsEvidenceStore(tmp_path / "news.sqlite")
    filing_store.save(_filing("filing"))
    news_store.save(_news("secondary"))
    state = _builder(filings=filing_store, news=news_store).build(ALPHA.instrument_id, as_of=T)
    reference = _reference(state, IntelligenceEvidenceDomain.NEWS_CATALYSTS)
    assert reference.availability is IntelligenceEvidenceAvailability.PARTIAL
    assert reference.artifact_ids == ("exchange-disclosure:filing", "news-evidence:secondary")
    assert "OFFICIAL_EXCHANGE_DISCLOSURE" in reference.warnings
    assert "SECONDARY_RESEARCH_EVIDENCE" in reference.warnings
    assert "Bounded title" not in repr(state) and "Bounded description" not in repr(state)


def test_news_pit_exact_identity_and_conflict_are_preserved(tmp_path: Path) -> None:
    store = SQLiteNewsEvidenceStore(tmp_path / "news.sqlite")
    store.save(_news("future", received=T + timedelta(days=1)))
    store.save(_news("unmapped", instrument_ids=()))
    store.save(_news("conflicted", warnings=("CONFLICTED",)))
    state = _builder(news=store).build(ALPHA.instrument_id, as_of=T)
    news = _reference(state, IntelligenceEvidenceDomain.NEWS_CATALYSTS)
    assert news.availability is IntelligenceEvidenceAvailability.CONFLICTED
    assert news.artifact_ids == ("news-evidence:conflicted",)
    assert "news-evidence:future" not in news.artifact_ids
    assert "news-evidence:unmapped" not in news.artifact_ids


def test_stored_catalyst_is_referenced_only_after_exact_identity_and_pit_checks() -> None:
    state = _builder(catalysts=(_catalyst("valid"), _catalyst("unmapped", company_id=None))).build(ALPHA.instrument_id, as_of=T)
    news = _reference(state, IntelligenceEvidenceDomain.NEWS_CATALYSTS)
    assert news.artifact_ids == ("catalyst-event:valid",)
    assert "STORED_CATALYST_ARTIFACT" in news.warnings
    assert any(item.invalidation_domain is IntelligenceInvalidationDomain.NEWS for item in state.dependency_lineage if item.artifact_id == "catalyst-event:valid")


def test_immutable_catalyst_snapshot_is_read_without_recomputing_it(tmp_path: Path) -> None:
    repository = SQLiteCoreApiSnapshotRepository(tmp_path / "snapshots.sqlite")
    event = _catalyst("snapshot")
    IntelligenceSnapshotStore(repository).save(
        record_id=event.event_id, family=CoreApiSnapshotFamily.CATALYST_EVENT, value=event,
        created_at=T - timedelta(hours=12),
    )
    news = _reference(_builder(catalyst_snapshots=repository).build(ALPHA.instrument_id, as_of=T), IntelligenceEvidenceDomain.NEWS_CATALYSTS)
    assert news.artifact_ids == ("catalyst-event:snapshot",)
    assert "STORED_CATALYST_ARTIFACT" in news.warnings


def test_macro_news_future_artifacts_do_not_change_past_reconstruction_or_portfolio_independent_state(tmp_path: Path) -> None:
    store = SQLiteNewsEvidenceStore(tmp_path / "news.sqlite")
    store.save(_news("eligible"))
    store.save(_news("future", received=T + timedelta(days=1)))
    builder = _builder(macro=(_macro("eligible"), _macro("future", available=T + timedelta(days=1))), news=store)
    state = builder.build(ALPHA.instrument_id, as_of=T)
    assert builder.reconstruct(ALPHA.instrument_id, as_of=T, expected_state=state) == state
    assert "future" not in " ".join(_reference(state, IntelligenceEvidenceDomain.MACRO).artifact_ids + _reference(state, IntelligenceEvidenceDomain.NEWS_CATALYSTS).artifact_ids)


def test_macro_news_adapter_is_read_only_and_has_no_provider_or_decision_execution() -> None:
    source = (Path(__file__).parents[2] / "app" / "intelligence" / "macro_news_evidence.py").read_text(encoding="utf-8")
    assert not any(token in source for token in ("requests.", "urlopen", "httpx", "CREATE TABLE", "INSERT INTO", "MacroStateService", "CatalystService", "DecisionScore", "SixGate", "Signal", "PaperTrade", "order("))
