from __future__ import annotations

from datetime import UTC, datetime, timedelta
from dataclasses import replace
from decimal import Decimal
from pathlib import Path

import pytest

from app.data_operations.models import EvidenceDataFamily, EvidenceRefreshMode, EvidenceRefreshRequest, EvidenceRefreshStatus
from app.data_operations.rbi_macro import (
    RBI_CURRENT_RATES_URL,
    RbiCurrentRatesRefreshJob,
    RbiCurrentRatesResponse,
    RbiCurrentRatesSource,
    RbiMacroSourceError,
)
from app.intelligence.macro import IntelligenceSourceTier, MacroEvidence, MacroInputFamily, MacroObservationFrequency
from app.intelligence.macro.store import MacroEvidenceStore, MacroEvidenceWriteOutcome, macro_evidence_fingerprint
from app.intelligence.macro_news_evidence import MacroEvidenceAdapter
from app.intelligence.unified_state import IntelligenceEvidenceAvailability
from app.production_v1.models import ProductionComponent, ProductionComponentHealth, ProductionReadinessState, ProductionSourceHealth, ProductionSourceStatus
from app.production_v1.service import build_readiness_report
from app.storage.sqlite_core_api_snapshot_repository import SQLiteCoreApiSnapshotRepository


T = datetime(2026, 8, 30, 12, tzinfo=UTC)
_HTML = """
<html><body>
Policy Repo Rate | : 5.50%<br/>
INR / 1 USD | : 87.1234<br/>
(As at 1.00pm of August 29, 2026)
</body></html>
"""


class _Response:
    def __init__(self, *, status: int = 200, text: str = _HTML, content_type: str = "text/html") -> None:
        self.status_code, self.text = status, text
        self.content = text.encode()
        self.headers = {"Content-Type": content_type}


class _Session:
    def __init__(self, response: _Response) -> None:
        self.response, self.calls = response, []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return self.response


class _Source:
    def __init__(self, values: tuple, fingerprint: str = "artifact") -> None:
        self.response = RbiCurrentRatesResponse(values, RBI_CURRENT_RATES_URL, fingerprint)

    def fetch(self):
        return self.response


class _FailingSource:
    def fetch(self):
        raise RbiMacroSourceError("SOURCE_UNAVAILABLE")


def _request() -> EvidenceRefreshRequest:
    return EvidenceRefreshRequest("macro-run", EvidenceDataFamily.MACRO, EvidenceRefreshMode.INCREMENTAL, T, T, None, 0)


def _store(tmp_path: Path) -> MacroEvidenceStore:
    return MacroEvidenceStore(SQLiteCoreApiSnapshotRepository(tmp_path / "macro.sqlite"))


def _value(component: str = "policy_repo_rate", value: str = "5.50") -> MacroEvidence:
    return MacroEvidence(
        f"rbi:{component}:{value}", MacroInputFamily.MONETARY_RATES, component, "RAW_OBSERVATION",
        IntelligenceSourceTier.OFFICIAL, RBI_CURRENT_RATES_URL, None, None, T, None, 1.0, "FRESH",
        warnings=("SOURCE_PUBLICATION_TIMESTAMP_UNKNOWN_FIRST_OBSERVED",), value=Decimal(value),
        unit="PERCENT", frequency=MacroObservationFrequency.EVENT, source_artifact_fingerprint="artifact", received_at=T,
    )


def test_official_rbi_current_rates_parse_preserves_decimal_units_frequency_and_source_headers() -> None:
    session = _Session(_Response())
    response = RbiCurrentRatesSource(session=session).fetch()
    assert session.calls[0][0] == RBI_CURRENT_RATES_URL
    assert session.calls[0][1]["headers"]["Accept"].startswith("text/html")
    assert tuple((item.component, item.value, item.unit, item.frequency.value) for item in response.values) == (
        ("policy_repo_rate", Decimal("5.50"), "PERCENT", "EVENT"),
        ("inr_usd_reference_rate", Decimal("87.1234"), "INR_PER_USD", "DAILY"),
    )
    assert response.values[1].observed_at == datetime(2026, 8, 28, 18, 30, tzinfo=UTC)


@pytest.mark.parametrize(("response", "code"), [
    (_Response(status=429), "RATE_LIMITED"), (_Response(status=503), "HTTP_ERROR"),
    (_Response(content_type="application/json"), "INVALID_RESPONSE"), (_Response(text="<html>empty</html>"), "PARSE_ERROR"),
])
def test_official_rbi_failure_is_typed_and_never_fabricates_evidence(response, code) -> None:
    with pytest.raises(RbiMacroSourceError, match=code):
        RbiCurrentRatesSource(session=_Session(response)).fetch()


def test_macro_store_is_durable_idempotent_and_tamper_closed(tmp_path: Path) -> None:
    store = _store(tmp_path)
    value = _value()
    assert store.save(value) is MacroEvidenceWriteOutcome.INSERTED
    assert store.save(value) is MacroEvidenceWriteOutcome.DUPLICATE
    assert MacroEvidenceStore(SQLiteCoreApiSnapshotRepository(tmp_path / "macro.sqlite")).get(value.evidence_id) == value
    changed = replace(value, value=Decimal("5.75"))
    with pytest.raises(ValueError, match="immutable"):
        store.save(changed)


def test_job_preserves_first_observed_pit_and_adds_explicit_revision(tmp_path: Path) -> None:
    source = RbiCurrentRatesSource(session=_Session(_Response())).fetch()
    store = _store(tmp_path)
    first = RbiCurrentRatesRefreshJob(source=_Source(source.values), store=store, clock=lambda: T).refresh(_request())
    second = RbiCurrentRatesRefreshJob(source=_Source(source.values, "changed-page-artifact"), store=store, clock=lambda: T + timedelta(days=1)).refresh(_request())
    assert first.status is EvidenceRefreshStatus.COMPLETE and second.status is EvidenceRefreshStatus.NO_CHANGE
    assert first.accepted_count == 2 and second.duplicate_count == 2
    before = store.list_stored_macro_evidence(as_of=T - timedelta(seconds=1))
    after = store.list_stored_macro_evidence(as_of=T)
    assert before == () and len(after) == 2 and all(item.received_at == T for item in after)
    revised = tuple(list(source.values[:-1]) + [source.values[-1].__class__(
        source.values[-1].component, source.values[-1].family, Decimal("88.0000"), source.values[-1].unit,
        source.values[-1].frequency, source.values[-1].observed_at, source.values[-1].effective_at, source.values[-1].warnings,
    )])
    third = RbiCurrentRatesRefreshJob(source=_Source(revised, "revision-artifact"), store=store, clock=lambda: T + timedelta(days=2)).refresh(_request())
    values = store.list_stored_macro_evidence(as_of=T + timedelta(days=2))
    assert third.accepted_count == 1 and len(values) == 3
    assert next(item for item in values if item.value == Decimal("88.0000")).revision_of is not None


def test_source_outage_retains_last_known_good_without_zero_or_default_value(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.save(_value())
    outcome = RbiCurrentRatesRefreshJob(source=_FailingSource(), store=store, clock=lambda: T + timedelta(days=1)).refresh(_request())
    assert outcome.status is EvidenceRefreshStatus.SOURCE_UNAVAILABLE and outcome.error_summary == "SOURCE_UNAVAILABLE"
    retained = store.list_stored_macro_evidence(as_of=T + timedelta(days=1))
    assert retained == (_value(),) and retained[0].value == Decimal("5.50")


def test_macro_adapter_exposes_only_pit_visible_raw_official_evidence(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.save(_value())
    adapter = MacroEvidenceAdapter(evidence_source=store)
    before = adapter.artifacts("NSE:ALPHA", as_of=T - timedelta(seconds=1))
    after = adapter.artifacts("NSE:ALPHA", as_of=T)
    assert before[0].availability is IntelligenceEvidenceAvailability.UNAVAILABLE
    assert after[0].availability is IntelligenceEvidenceAvailability.AVAILABLE
    assert after[0].artifact_id.startswith("macro-evidence:") and "RAW_OBSERVATION" not in repr(after[0])


def test_macro_operational_limitation_is_not_a_p0_when_official_source_is_healthy() -> None:
    components = tuple(
        ProductionComponentHealth(item, ProductionReadinessState.DEGRADED if item is ProductionComponent.MACRO else ProductionReadinessState.READY)
        for item in ProductionComponent
    )
    sources = tuple(
        ProductionSourceHealth(item, "official", "adapter", ProductionSourceStatus.OPERATIONAL_WITH_LIMITATION if item is ProductionComponent.MACRO else ProductionSourceStatus.OPERATIONAL, "coverage")
        for item in (
            ProductionComponent.OHLCV, ProductionComponent.INDEX_BARS, ProductionComponent.DELIVERY,
            ProductionComponent.MEMBERSHIP, ProductionComponent.TAXONOMY, ProductionComponent.CORPORATE_ACTIONS,
            ProductionComponent.FINANCIALS, ProductionComponent.SHAREHOLDING, ProductionComponent.MACRO, ProductionComponent.NEWS,
        )
    )
    report = build_readiness_report(generated_at=T, components=components, sources=sources)
    assert not any(item.startswith("MACRO:") for item in report.p0_blockers)


def test_macro_implementation_has_no_yahoo_media_or_action_semantics() -> None:
    source = (Path(__file__).parents[2] / "app" / "data_operations" / "rbi_macro.py").read_text(encoding="utf-8").lower()
    assert not any(token in source for token in ("yahoo", "gemini", "bullish", "bearish", "buy", "sell", "score", "sixgate", "papertrade"))
