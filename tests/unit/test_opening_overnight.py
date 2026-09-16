"""Isolated reported-open evidence; never a live-open or execution canary."""
import ast
from dataclasses import FrozenInstanceError, replace
from datetime import UTC, date, datetime, timedelta, timezone
from decimal import Decimal, localcontext
from pathlib import Path

import pytest

from app.domain.models import FreshnessStatus
from app.historical.security_master import CorporateActionKind
from app.intelligence.opening_overnight import (
    OpeningGapStatus, OpeningOvernightEvidenceSource, build_opening_overnight, serialize_opening_overnight,
)
from app.intelligence.unified_state import IntelligenceEvidenceDomain as Domain, IntelligenceEvidenceAvailability as Availability
from app.intelligence.unified_state import IntelligenceInvalidationDomain
from app.intelligence.unified_state_builder import StoredIntelligenceArtifact
from app.intelligence.shared_brain_application import StoredSharedBrainEvidenceAssembler
from app.fundamentals.store import SQLiteFinancialFactStore
from app.market_data.models import AdjustmentStatus, InstrumentType
from app.market_data.nse_udiff_daily_technical_read import (
    NseUdiffDailyTechnicalReadEvidence, NseUdiffDailyTechnicalReadRequest, NseUdiffDailyTechnicalUseMode,
)
from app.market_data.nse_udiff_daily_technical_eligibility import DailyTechnicalRequirement, DailyTechnicalRequirementProfile
from tests.unit.test_nse_udiff_daily_technical_eligibility import AT, INSTRUMENT, bar, interval, coverage, action
from tests.unit.test_canonical_market_session_event_time import _calendar
from tests.unit.test_external_intelligence_reevaluation import _ExactResolver

PREV, CURRENT = date(2025, 6, 2), date(2025, 6, 3)
LOWER = datetime(2025, 6, 2, 10, tzinfo=UTC)
UPPER = datetime(2025, 6, 3, 3, 45, tzinfo=UTC)


def inputs(*, opening="105", previous=PREV, current=CURRENT):
    bars = (bar(previous), replace(bar(current), open=Decimal(opening), high=Decimal("200"), low=Decimal("1")))
    return dict(
        request=NseUdiffDailyTechnicalReadRequest(INSTRUMENT.instrument_id, previous, current,
            DailyTechnicalRequirement(DailyTechnicalRequirementProfile.PRICE_ONLY),
            NseUdiffDailyTechnicalUseMode.CURRENT_DESCRIPTIVE_TECHNICAL, AT),
        evidence=NseUdiffDailyTechnicalReadEvidence((previous, current), bars,
            tuple(sorted((interval(b) for b in bars), key=lambda i: i.interval_id)), coverage(previous, current)),
        calendar=_calendar(), prior_decision_cutoff=datetime.combine(previous, LOWER.timetz()),
        event_window_end=datetime.combine(current, UPPER.timetz()),
    )


def event(identifier="event:one", at=LOWER + timedelta(hours=1), **changes):
    value = StoredIntelligenceArtifact(INSTRUMENT.instrument_id, Domain.NEWS_CATALYSTS,
        identifier, "sha256:" + "a" * 64, Availability.PARTIAL, at, at, at,
        FreshnessStatus.UNKNOWN, None, "b" * 64, "c" * 64,
        IntelligenceInvalidationDomain.NEWS, ("SECONDARY_RESEARCH",))
    return replace(value, **changes)


@pytest.mark.parametrize("opening,status,gap", [
    ("105", "GAP_UP", "3"), ("99", "GAP_DOWN", "-3"), ("102", "FLAT", "0"),
])
def test_exact_gap_is_factual_not_materiality_or_trade(opening, status, gap):
    result = build_opening_overnight(**inputs(opening=opening))
    assert result.status.value == status and result.gap_inr == Decimal(gap)
    with localcontext() as ctx:
        ctx.prec = 34
        assert result.gap_pct == (Decimal(opening) / Decimal(102) - 1) * 100
    assert (result.actionability, result.execution_status) == ("WATCH_ONLY", "NON_EXECUTABLE")
    assert "PREOPEN_SOURCE_NOT_READY" in result.blockers
    assert "CURRENT_DESCRIPTIVE_NOT_OPEN_TIME_PROOF" in result.blockers


@pytest.mark.parametrize("previous,current", [
    (date(2025, 5, 30), date(2025, 6, 2)),  # Weekend.
    (date(2025, 3, 13), date(2025, 3, 17)),  # Declared holiday and weekend.
    (date(2025, 1, 31), date(2025, 2, 1)),  # Declared Saturday special session.
])
def test_native_calendar_not_calendar_day_subtraction(previous, current):
    value = build_opening_overnight(**inputs(previous=previous, current=current))
    assert value.previous_session == previous and value.status is OpeningGapStatus.GAP_UP


def test_non_adjacent_pair_cannot_skip_security_no_trade_session():
    data = inputs(previous=date(2025, 5, 30))
    data["prior_decision_cutoff"] = LOWER
    value = build_opening_overnight(**data)
    assert value.gap_inr is None and "EXACT_ADJACENT_DAILY_PAIR_REQUIRED" in value.blockers


def test_window_excludes_old_future_and_later_revision_without_causal_claim():
    first = event()
    refs = (event("old", LOWER), first, first, event("future", UPPER + timedelta(microseconds=1)),
            event("later-revision", AT), event("at-end", UPPER))
    value = build_opening_overnight(**inputs(), event_references=refs)
    assert tuple(r.artifact_id for r in value.event_references) == ("at-end", "event:one")
    assert "CAUSAL_ATTRIBUTION_UNSUPPORTED" in value.blockers
    assert value == build_opening_overnight(**inputs(), event_references=tuple(reversed(refs)))


def test_conflicting_event_provenance_is_retained_without_changing_raw_gap():
    refs = (event(), event(artifact_fingerprint="sha256:" + "d" * 64))
    value = build_opening_overnight(**inputs(), event_references=refs)
    assert len(value.event_references) == 2 and value.status is OpeningGapStatus.GAP_UP
    assert "OVERNIGHT_EVENT_EVIDENCE_CONFLICTED" in value.blockers
    assert OpeningOvernightEvidenceSource(value).list_stored_intelligence_artifacts(INSTRUMENT.instrument_id, as_of=AT)[0].availability is Availability.CONFLICTED
    with pytest.raises(ValueError, match="LINEAGE_CONFLICT"):
        build_opening_overnight(**inputs(), event_references=(event(), event(warnings=("changed",))))


@pytest.mark.parametrize("changes", [{"canonical_instrument_id": "NSE:OTHER"}, {"available_at": None}, {"domain": Domain.MACRO}])
def test_event_identity_and_knownness_required(changes):
    with pytest.raises(ValueError, match="OPENING_OVERNIGHT_EVENT"):
        build_opening_overnight(**inputs(), event_references=(event(**changes),))


@pytest.mark.parametrize("kind", [CorporateActionKind.SPLIT, CorporateActionKind.BONUS,
    CorporateActionKind.RIGHTS, CorporateActionKind.DIVIDEND, CorporateActionKind.MERGER,
    CorporateActionKind.SUSPENSION, CorporateActionKind.DELISTING])
def test_native_corporate_action_and_lifecycle_blocks_mechanical_gap(kind):
    data = inputs(opening="51")
    data["evidence"] = replace(data["evidence"], actions=(action(kind, CURRENT),))
    value = build_opening_overnight(**data)
    assert value.gap_inr is None and value.current_open is None
    assert value.status is OpeningGapStatus.INSUFFICIENT_DATA


@pytest.mark.parametrize("case", ["missing", "no_trade", "unknown_basis", "mixed_basis", "coverage_missing", "identity_missing"])
def test_missing_or_noncomparable_price_fails_closed(case):
    data = inputs()
    evidence = data["evidence"]
    if case == "missing": evidence = replace(evidence, observed_bars=evidence.observed_bars[:1])
    if case == "no_trade": evidence = replace(evidence, observed_bars=(evidence.observed_bars[0], replace(evidence.observed_bars[1], volume=0)))
    if case in {"unknown_basis", "mixed_basis"}:
        basis = AdjustmentStatus.UNKNOWN if case == "unknown_basis" else AdjustmentStatus.ADJUSTED
        evidence = replace(evidence, observed_bars=(evidence.observed_bars[0], replace(evidence.observed_bars[1], adjustment_status=basis)))
    if case == "coverage_missing": evidence = replace(evidence, action_coverage=None)
    if case == "identity_missing": evidence = replace(evidence, identity_intervals=())
    value = build_opening_overnight(**(data | {"evidence": evidence}))
    assert value.gap_inr is None and value.gap_pct is None


def test_future_price_receipt_and_strict_historical_mode_never_backcast():
    data = inputs()
    early = replace(data["request"], evaluation_as_of=AT - timedelta(seconds=1))
    assert build_opening_overnight(**(data | {"request": early})).gap_inr is None
    strict = replace(data["request"], use_mode=NseUdiffDailyTechnicalUseMode.STRICT_HISTORICAL_PIT_TECHNICAL)
    value = build_opening_overnight(**(data | {"request": strict, "evidence": None}))
    assert value.gap_inr is None
    assert "STRICT_HISTORICAL_PIT_SOURCE_AVAILABILITY_UNAVAILABLE" in value.blockers


def test_aligned_index_is_not_silently_admitted_by_equity_source_policy():
    data = inputs()
    bars = tuple(replace(b, instrument=replace(b.instrument, instrument_type=InstrumentType.BROAD_INDEX)) for b in data["evidence"].observed_bars)
    value = build_opening_overnight(**(data | {"evidence": replace(data["evidence"], observed_bars=bars)}))
    assert value.gap_inr is None
    assert "BENCHMARK_SECTOR_OPEN_SOURCE_NOT_READY" in value.blockers


def test_immutability_tamper_rejection_timezone_and_decimal_context_independence():
    data = inputs()
    one = build_opening_overnight(**data)
    with localcontext() as ctx:
        ctx.prec = 7
        two = build_opening_overnight(**(data | {"prior_decision_cutoff": LOWER.astimezone(timezone(timedelta(hours=5, minutes=30)))}))
    assert one == two
    assert serialize_opening_overnight(one) == serialize_opening_overnight(two)
    with pytest.raises(FrozenInstanceError): one.gap_inr = Decimal(0)
    with pytest.raises(ValueError): replace(one, gap_inr=Decimal(0))
    with pytest.raises(ValueError): replace(one, fingerprint="sha256:" + "0" * 64)
    with pytest.raises(ValueError): replace(one, execution_status="EXECUTABLE")
    with pytest.raises(ValueError): replace(one, status="GAP_UP")


@pytest.mark.parametrize("changes", [
    {"prior_decision_cutoff": UPPER},
    {"event_window_end": UPPER + timedelta(days=1)},
    {"prior_decision_cutoff": LOWER.replace(tzinfo=None)},
])
def test_overnight_window_cannot_be_relabelled(changes):
    with pytest.raises(ValueError, match="OPENING_OVERNIGHT"):
        build_opening_overnight(**(inputs() | changes))


def test_non_inr_pair_never_claims_inr_gap():
    data = inputs()
    bars = tuple(replace(b, instrument=replace(b.instrument, currency="USD")) for b in data["evidence"].observed_bars)
    value = build_opening_overnight(**(data | {"evidence": replace(data["evidence"], observed_bars=bars)}))
    assert value.gap_inr is None and "EXACT_NSE_EQUITY_INR_PAIR_REQUIRED" in value.blockers


def test_native_brain_composition_and_no_asof_relabel(tmp_path):
    value = build_opening_overnight(**inputs(), event_references=(event(),))
    source = OpeningOvernightEvidenceSource(value)
    assert source.list_stored_intelligence_artifacts(INSTRUMENT.instrument_id, as_of=AT - timedelta(seconds=1)) == ()
    facts = SQLiteFinancialFactStore(tmp_path / "brain.sqlite")
    try:
        assembler = StoredSharedBrainEvidenceAssembler(facts, market_technical_artifacts=source)
        instrument = replace(_ExactResolver().instrument, instrument_id=INSTRUMENT.instrument_id)
        brain = assembler.assemble(instrument, as_of=AT).unified_state
        refs = {ref.domain: ref for ref in brain.evidence_references}
        assert refs[Domain.MARKET_DATA].artifact_ids == (value.artifact_id,)
        assert refs[Domain.MARKET_DATA].availability is Availability.PARTIAL
        assert refs[Domain.DECISION_SCORE].availability is Availability.UNAVAILABLE
        assert refs[Domain.SIX_GATES].availability is Availability.UNAVAILABLE
    finally:
        facts._connection.close()


def test_no_new_provider_clock_or_execution_dependencies():
    tree = ast.parse(Path("app/intelligence/opening_overnight.py").read_text())
    imports = {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
    assert not any(name.startswith(("app.portfolio", "app.gates", "app.scoring", "app.api", "app.runtime", "app.providers")) for name in imports)
    calls = {node.func.attr for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)}
    assert not calls & {"now", "utcnow", "save", "execute", "connect", "post", "get", "submit_order"}
