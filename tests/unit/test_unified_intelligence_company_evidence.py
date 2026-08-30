from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from app.data_sources.models import FundamentalFactKind
from app.domain.models import FreshnessStatus
from app.filings.models import CorporateFiling, FilingTextAvailability, FilingType, PrimarySourceQuality
from app.filings.store import SQLiteCorporateFilingsStore
from app.fundamentals.models import FinancialFact, FinancialMetric, FinancialPeriodType, FinancialQualityFlag, FinancialValueBasis, NumericScale, StatementScope
from app.fundamentals.store import SQLiteFinancialFactStore
from app.historical.security_master import CorporateActionKind, HistoricalCorporateAction, HistoricalSecurityMasterStore
from app.intelligence.company_evidence import CompanyEvidenceStoredSource, CompositeStoredIntelligenceSource
from app.intelligence.unified_state import IntelligenceEvidenceAvailability, IntelligenceEvidenceDomain, IntelligenceInvalidationDomain
from app.intelligence.unified_state_builder import StoredIntelligenceArtifact, UnifiedIntelligenceStateBuilder
from app.market_data.models import Exchange, InstrumentIdentity, InstrumentType, MarketDataProvenance
from app.storage.sqlite_core_api_snapshot_repository import SQLiteCoreApiSnapshotRepository


T = datetime(2026, 8, 28, 12, tzinfo=UTC)
I = InstrumentIdentity("NSE:COMPANY", Exchange.NSE, "COMPANY", "COMPANY", "INE000A01001", "EQ", InstrumentType.NSE_EQUITY, "Company Ltd")


class _CoreSource:
    def list_stored_intelligence_artifacts(self, canonical_instrument_id: str, *, as_of: datetime):
        if canonical_instrument_id != I.instrument_id:
            return ()
        return tuple(_artifact(domain) for domain in (IntelligenceEvidenceDomain.REFERENCE_DATA, IntelligenceEvidenceDomain.MARKET_DATA))


def _artifact(domain: IntelligenceEvidenceDomain) -> StoredIntelligenceArtifact:
    return StoredIntelligenceArtifact(
        I.instrument_id, domain, f"{domain.value}:core", f"{domain.value}:fingerprint",
        IntelligenceEvidenceAvailability.AVAILABLE, T - timedelta(days=1), T - timedelta(days=1),
        T - timedelta(days=1), FreshnessStatus.FRESH, None, f"{domain.value}:source",
        None, IntelligenceInvalidationDomain.PRICE if domain is IntelligenceEvidenceDomain.MARKET_DATA else IntelligenceInvalidationDomain.REFERENCE_DATA,
    )


def _fact(identifier: str, metric: FinancialMetric = FinancialMetric.REVENUE, *, source: str = "BSE_OFFICIAL_XBRL", published: datetime = T - timedelta(days=5), received: datetime | None = None) -> FinancialFact:
    arrival = received or published
    return FinancialFact(
        identifier, I, metric, Decimal("100"), "INR", "INR", NumericScale.UNITS,
        FinancialPeriodType.QUARTERLY, FinancialValueBasis.QUARTER_ONLY, None,
        T - timedelta(days=30), 2027, 1, StatementScope.CONSOLIDATED,
        FundamentalFactKind.REPORTED, source, f"filing:{identifier}", f"source:{identifier}",
        published, arrival, "v1", (source,), (), None, (FinancialQualityFlag.COMPLETE,),
    )


def _filing(identifier: str, *, announced: datetime = T - timedelta(days=4), received: datetime | None = None) -> CorporateFiling:
    arrival = received or announced
    return CorporateFiling(
        identifier, I, Exchange.NSE, "NSE_OFFICIAL_FILINGS", PrimarySourceQuality.PRIMARY_EXCHANGE,
        FilingType.SHAREHOLDING_PATTERN, None, "Shareholding pattern", announced, arrival,
        f"source:{identifier}", None,
        MarketDataProvenance("NSE_OFFICIAL_FILINGS", None, announced, announced, arrival, "v1"),
        reporting_as_of=announced, text_availability=FilingTextAvailability.DOCUMENT_ONLY,
    )


def _build(*, facts=None, filings=None, actions=None, path: Path) -> UnifiedIntelligenceStateBuilder:
    path.mkdir(parents=True, exist_ok=True)
    financial_store = SQLiteFinancialFactStore(path / "facts.sqlite")
    filing_store = SQLiteCorporateFilingsStore(path / "filings.sqlite")
    action_store = HistoricalSecurityMasterStore(SQLiteCoreApiSnapshotRepository(path / "actions.sqlite"))
    for fact in facts or (): financial_store.save(fact)
    for filing in filings or (): filing_store.save(filing)
    for action in actions or (): action_store.save_action(action)
    company = CompanyEvidenceStoredSource(financial_facts=financial_store, filings=filing_store, historical_security_master=action_store)
    return UnifiedIntelligenceStateBuilder(CompositeStoredIntelligenceSource(_CoreSource(), company))


def _reference(state, domain: IntelligenceEvidenceDomain):
    return next(value for value in state.evidence_references if value.domain is domain)


def test_canonical_financial_facts_feed_bounded_fundamentals_and_earnings_references(tmp_path: Path) -> None:
    state = _build(facts=(_fact("revenue"), _fact("assets", FinancialMetric.TOTAL_ASSETS)), path=tmp_path).build(I.instrument_id, as_of=T)
    fundamentals, earnings = _reference(state, IntelligenceEvidenceDomain.FUNDAMENTALS), _reference(state, IntelligenceEvidenceDomain.EARNINGS)
    assert fundamentals.availability is earnings.availability is IntelligenceEvidenceAvailability.AVAILABLE
    assert fundamentals.artifact_ids == ("financial-fact:assets", "financial-fact:revenue")
    assert earnings.artifact_ids == ("financial-fact:revenue",)
    assert all("100" not in identifier for identifier in fundamentals.artifact_ids)


def test_financial_facts_are_not_backdated_and_newly_eligible_facts_change_state(tmp_path: Path) -> None:
    later = _fact("future-revenue", received=T + timedelta(days=1))
    builder = _build(facts=(later,), path=tmp_path)
    before, after = builder.build(I.instrument_id, as_of=T), builder.build(I.instrument_id, as_of=T + timedelta(days=1))
    assert _reference(before, IntelligenceEvidenceDomain.FUNDAMENTALS).availability is IntelligenceEvidenceAvailability.UNAVAILABLE
    assert _reference(after, IntelligenceEvidenceDomain.FUNDAMENTALS).availability is IntelligenceEvidenceAvailability.AVAILABLE
    assert before.fingerprint != after.fingerprint


def test_secondary_only_financial_evidence_remains_partial_not_promoted(tmp_path: Path) -> None:
    state = _build(facts=(_fact("secondary", source="UPSTOX_ANALYTICS"),), path=tmp_path).build(I.instrument_id, as_of=T)
    reference = _reference(state, IntelligenceEvidenceDomain.FUNDAMENTALS)
    assert reference.availability is IntelligenceEvidenceAvailability.PARTIAL
    assert "SECONDARY_OR_UNGOVERNED_FINANCIAL_SOURCE" in reference.warnings


def test_shareholding_disclosure_is_pit_safe_partial_lineage_without_institutional_calculation(tmp_path: Path) -> None:
    future = _filing("holding", received=T + timedelta(days=1))
    builder = _build(filings=(future,), path=tmp_path)
    before, after = builder.build(I.instrument_id, as_of=T), builder.build(I.instrument_id, as_of=T + timedelta(days=1))
    assert _reference(before, IntelligenceEvidenceDomain.OWNERSHIP).availability is IntelligenceEvidenceAvailability.UNAVAILABLE
    ownership = _reference(after, IntelligenceEvidenceDomain.OWNERSHIP)
    assert ownership.availability is IntelligenceEvidenceAvailability.PARTIAL
    assert ownership.artifact_ids == ("shareholding-filing:holding",)
    assert "SHAREHOLDING_FACTS_NOT_MATERIALIZED" in ownership.warnings


def test_official_corporate_actions_are_bounded_pit_safe_and_reference_data_invalidated(tmp_path: Path) -> None:
    known = HistoricalCorporateAction("bonus", I.instrument_id, CorporateActionKind.BONUS, T - timedelta(days=5), T - timedelta(days=4), T - timedelta(days=3), T - timedelta(days=3), Decimal("1"), Decimal("1"), None, "NSE_OFFICIAL_CORPORATE_ACTION_EXPORT", "v1", T - timedelta(days=5))
    future = HistoricalCorporateAction("future", I.instrument_id, CorporateActionKind.SPLIT, T + timedelta(days=1), None, T + timedelta(days=2), T + timedelta(days=2), Decimal("2"), Decimal("1"), None, "NSE_OFFICIAL_CORPORATE_ACTION_EXPORT", "v1", T + timedelta(days=1))
    state = _build(actions=(future, known), path=tmp_path).build(I.instrument_id, as_of=T)
    reference = _reference(state, IntelligenceEvidenceDomain.CORPORATE_ACTIONS)
    assert reference.availability is IntelligenceEvidenceAvailability.AVAILABLE
    assert reference.artifact_ids == ("corporate-action:bonus",)
    assert {(value.invalidation_domain, value.artifact_id) for value in state.dependency_lineage if value.artifact_id.startswith("corporate-action:")} == {(IntelligenceInvalidationDomain.REFERENCE_DATA, "corporate-action:bonus")}


def test_company_artifact_order_does_not_change_domain_or_state_fingerprint(tmp_path: Path) -> None:
    facts = (_fact("revenue"), _fact("assets", FinancialMetric.TOTAL_ASSETS))
    left = _build(facts=facts, path=tmp_path / "left").build(I.instrument_id, as_of=T)
    right = _build(facts=tuple(reversed(facts)), path=tmp_path / "right").build(I.instrument_id, as_of=T)
    assert left == right


def test_company_evidence_keeps_other_missing_domains_partial_and_reconstructs(tmp_path: Path) -> None:
    builder = _build(facts=(_fact("revenue"),), path=tmp_path)
    state = builder.build(I.instrument_id, as_of=T)
    assert state.completeness.value == "PARTIAL"
    assert IntelligenceEvidenceDomain.NEWS_CATALYSTS in state.degraded_domains
    assert builder.reconstruct(I.instrument_id, as_of=T, expected_state=state) == state


def test_company_adapter_source_is_stored_only_and_never_invokes_provider_or_execution_surfaces() -> None:
    source = (Path(__file__).parents[2] / "app" / "intelligence" / "company_evidence.py").read_text(encoding="utf-8")
    assert not any(token in source for token in ("requests.", "urlopen", "httpx", "CREATE TABLE", "INSERT INTO", "DecisionScore", "SixGate", "Signal", "PaperTrade", "order("))
