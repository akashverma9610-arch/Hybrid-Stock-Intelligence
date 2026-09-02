from datetime import UTC, datetime, timedelta

from app.domain.models import DiagnosticResult, DiagnosticStrategyLineageType, StrategyVersionReference
from app.intelligence.market_wide_evidence_readiness import (
    EvidenceReadinessState, MarketWideEvidenceReadinessService,
)
from app.universe_analysis.models import NseEquityInstrument


T = datetime(2026, 9, 1, tzinfo=UTC)


class _Bar:
    def __init__(self, end_time): self.end_time = end_time


class _Historical:
    def __init__(self, count): self.count = count
    def latest(self, *_args, **_kwargs): return tuple(_Bar(T - timedelta(days=index)) for index in range(self.count))[::-1]
    def list_conflict_artifacts(self, **_kwargs): return ()


class _Diagnostics:
    def __init__(self, values): self.values = values
    def latest_canonical_diagnostic_results(self, instrument_id, *, as_of): return self.values.get(instrument_id, ())


def _instrument(identifier="NSE:INE000000001"):
    return NseEquityInstrument(identifier, "ALPHA", "Alpha Ltd", "Industrials", None, "ACTIVE", None, True, T, "NSE_OFFICIAL", main_board=True)


def _diagnostic(instrument_id, rule_id):
    return DiagnosticResult(
        id=f"result:{rule_id}", instrument_id=instrument_id, rule_id=str(rule_id),
        strategy_version=StrategyVersionReference("canonical-universe-analysis", "v1"), result="PASS",
        score=None, confidence=1.0, evidence_ids=("evidence",), input_observation_ids=(),
        evaluated_at=T, as_of_timestamp=T,
        strategy_lineage_type=DiagnosticStrategyLineageType.CANONICAL_DIAGNOSTIC_STRATEGY,
        canonical_strategy_fingerprint="strategy", canonical_limitations_fingerprint="limits",
        diagnostic_fingerprint=f"sha256:{rule_id}",
    )


def test_readiness_is_categorical_and_financial_absence_is_not_a_global_market_gate():
    instrument = _instrument()
    service = MarketWideEvidenceReadinessService(historical=_Historical(200), diagnostics=_Diagnostics({}))
    first = service.assess((instrument,), as_of=T)
    second = service.assess((instrument,), as_of=T)
    record = first.records[0]
    assert record.readiness is EvidenceReadinessState.READY
    assert dict(record.domain_states)["FINANCIALS"].value == "UNAVAILABLE"
    assert "OFFICIAL_FINANCIAL_EVIDENCE_UNAVAILABLE" in record.blocker_codes
    assert first.fingerprint == second.fingerprint
    assert first.readiness_counts == (("EVIDENCE_PARTIAL", 0), ("EVIDENCE_READY", 1), ("EVIDENCE_UNAVAILABLE", 0))


def test_short_listing_history_is_partial_not_a_fabricated_market_failure():
    instrument = _instrument()
    service = MarketWideEvidenceReadinessService(historical=_Historical(20), diagnostics=_Diagnostics({}))
    record = service.assess((instrument,), as_of=T).records[0]
    assert record.readiness is EvidenceReadinessState.PARTIAL
    assert "INSUFFICIENT_LISTING_HISTORY" in record.blocker_codes


def test_canonical_61_readiness_is_counted_without_creating_generic_lineage():
    instrument = _instrument()
    diagnostics = _Diagnostics({instrument.instrument_id: tuple(_diagnostic(instrument.instrument_id, index) for index in range(1, 62))})
    service = MarketWideEvidenceReadinessService(historical=_Historical(200), diagnostics=diagnostics)
    record = service.assess((instrument,), as_of=T).records[0]
    assert dict(record.domain_states)["CANONICAL_DIAGNOSTICS"].value == "READY"
    assert len(record.evidence_references) == 61
