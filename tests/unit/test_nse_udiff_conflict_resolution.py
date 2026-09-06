from dataclasses import FrozenInstanceError, replace
from datetime import timedelta, timezone
from decimal import Decimal
import inspect
import json

import pytest

from app.market_data.historical import (
    HistoricalBarConflictArtifact, HistoricalBarNormalizedValues,
    _bar_lineage, _conflict_differing_fields, _historical_conflict_fingerprint,
    _normalized_bar_fingerprint, _conflict_artifact_payload,
)
from app.market_data.nse_udiff_conflict_resolution import (
    NseUdiffCurrentConflictState as State, reconcile_udiff_conflict,
)
from app.market_data.nse_udiff_conflict_semantics import source_row_evidence
from app.market_data.nse_udiff_daily_history import _artifact_from_bytes, _parse_valid_archive, _bar_from_row
from app.market_data.nse_udiff_daily_integrity import audit_udiff_same_provider_conflicts
from app.market_data.nse_udiff_daily_technical_read import (
    NseUdiffDailyTechnicalReadEvidence, NseUdiffDailyTechnicalReadRequest,
    NseUdiffDailyTechnicalUseMode, read_certified_daily_technical_bars,
    serialize_nse_udiff_certified_daily_technical_read,
)
from app.market_data.nse_udiff_daily_technical_eligibility import (
    DailyTechnicalRequirement, DailyTechnicalRequirementProfile,
)
from tests.unit.test_nse_udiff_daily_history import archive, row, result, target, D, T
from tests.unit.test_nse_udiff_daily_technical_eligibility import AT, coverage, interval, action
from app.historical.security_master import CorporateActionKind


def legacy_conflict(left, right):
    """Reproduce the sealed old coarse-key artifact without altering storage."""
    a, b = HistoricalBarNormalizedValues.from_bar(left), HistoricalBarNormalizedValues.from_bar(right)
    values = dict(canonical_instrument_id=left.instrument.instrument_id, timeframe=left.timeframe,
                  start_time=left.start_time, end_time=left.end_time,
                  stored_bar_fingerprint=_normalized_bar_fingerprint(left),
                  incoming_bar_fingerprint=_normalized_bar_fingerprint(right),
                  differing_fields=_conflict_differing_fields(a, b),
                  stored_lineage=replace(_bar_lineage(left), source_observation_identity=None),
                  incoming_lineage=replace(_bar_lineage(right), source_observation_identity=None))
    return HistoricalBarConflictArtifact(
        **values, conflict_fingerprint=_historical_conflict_fingerprint(**values),
        stored_values=a, incoming_values=b, detected_at=T,
    )


def pair(series="BL", *, second_changes=None):
    rows = ({**row(), "SctySrs": series, "FinInstrmId": "777", "ClsPric": "101"},
            {**row(), **(second_changes or {})})
    artifact = _artifact_from_bytes("nse-udiff-acquisition:test", result(archive(rows)))
    parsed = _parse_valid_archive(artifact)
    bars = tuple(_bar_from_row(artifact, parsed, i, r, target())[0] for i, r in enumerate(parsed.rows))
    sources = tuple(source_row_evidence(artifact, i) for i in range(2))
    conflict = legacy_conflict(*bars)
    return conflict, sources, bars


def proof(conflict, sources, bars):
    return reconcile_udiff_conflict(artifact=conflict, stored_row=sources[0], incoming_row=sources[1], retained_bars=bars)


def read(conflict, sources, bars, *, retained=None, actions=(), at=AT):
    resolution = proof(conflict, sources, bars if retained is None else retained)
    assessments = audit_udiff_same_provider_conflicts((conflict,), reconciliations=(resolution,))
    request = NseUdiffDailyTechnicalReadRequest(target().canonical_instrument_id, D, D,
        DailyTechnicalRequirement(DailyTechnicalRequirementProfile.PRICE_AND_VOLUME),
        NseUdiffDailyTechnicalUseMode.CURRENT_DESCRIPTIVE_TECHNICAL, at)
    values = tuple(sorted(bars, key=lambda bar: (bar.start_time, bar.bar_id)))
    evidence = NseUdiffDailyTechnicalReadEvidence((D,), values,
        tuple(sorted({interval(bar) for bar in bars}, key=lambda item: item.interval_id)),
        coverage(D, D), actions, assessments)
    return read_certified_daily_technical_bars(request=request, evidence=evidence), resolution


@pytest.mark.parametrize("series", ["BL", "T0"])
def test_resolved_distinct_series_returns_only_eq_and_preserves_historical_artifact(series):
    conflict, sources, bars = pair(series)
    before = _conflict_artifact_payload(conflict)
    result, resolution = read(conflict, sources, bars)
    assert resolution.state is State.RESOLVED_STRUCTURAL_CONFLICT
    assert result.state.value == "READY"
    assert result.bars == (bars[1],)
    assert result.certification.conflict_fingerprints  # resolution lineage is not dropped
    assert _conflict_artifact_payload(conflict) == before
    old = audit_udiff_same_provider_conflicts((conflict,))[0]
    assert old.current_state is State.CURRENT_UNRESOLVED_CONFLICT
    assert old.blocks_window(bars, AT)


def test_classification_alone_cannot_resolve_missing_storage_side():
    conflict, sources, bars = pair()
    result, resolution = read(conflict, sources, bars, retained=bars[:1])
    assert resolution.classification.value == "DISTINCT_SERIES"
    assert resolution.state is State.CURRENT_UNRESOLVED_CONFLICT
    assert result.state.value == "NOT_READY" and "SAME_PROVIDER_CONFLICT" in result.reasons


def test_resolution_is_rechecked_against_current_reader_observations():
    conflict, sources, bars = pair()
    resolution = proof(conflict, sources, bars)
    assert not resolution.resolves_window(bars[1:], AT)
    assert not resolution.resolves_window(bars + (bars[1],), AT)
    assert not resolution.resolves_window((bars[0], replace(bars[1], close=Decimal("100"))), AT)


@pytest.mark.parametrize("change", [
    {"request_reference": "nse-udiff-artifact:forged:row:1:sha256:bad"},
    {"schema_version": "v2"}, {"normalization_version": "other"},
    {"provider": "other"},
])
def test_retained_provider_version_or_archive_reference_cannot_be_substituted(change):
    conflict, sources, bars = pair()
    altered = replace(bars[1], provenance=replace(bars[1].provenance, **change))
    with pytest.raises(ValueError, match="RETAINED_SOURCE_MISMATCH"):
        proof(conflict, sources, (bars[0], altered))


def test_audit_connection_and_bar_query_are_read_only(tmp_path):
    import sqlite3
    from scripts.audit_nse_udiff_identity_boundary import open_readonly
    from scripts.audit_nse_udiff_resolved_conflict_eligibility import _bars
    db = tmp_path / "fixture.db"
    with sqlite3.connect(db) as c:
        c.execute("CREATE TABLE historical_bars (instrument_id TEXT, provider_identity TEXT, start_time TEXT, bar_id TEXT)")
    with open_readonly(db) as c:
        assert _bars(c, "NSE:INE000A01001", D, D) == ()
        with pytest.raises(sqlite3.OperationalError, match="readonly"):
            c.execute("DELETE FROM historical_bars")


def test_same_exact_source_series_value_conflict_always_blocks():
    conflict, sources, bars = pair("EQ", second_changes={"FinInstrmId": "777"})
    result, resolution = read(conflict, sources, bars, retained=bars[:1])
    assert sources[0].source_row_id == sources[1].source_row_id
    assert resolution.state is State.CURRENT_TRUE_SOURCE_CONFLICT
    assert result.state.value == "NOT_READY" and "SAME_PROVIDER_CONFLICT" in result.reasons


@pytest.mark.parametrize("series", ["BE", "BZ"])
def test_distinct_ordinary_series_cannot_choose_arbitrary_eq_winner(series):
    conflict, sources, bars = pair(series)
    result, resolution = read(conflict, sources, bars)
    assert resolution.state is State.RESOLVED_STRUCTURAL_CONFLICT
    assert result.state.value == "NOT_READY"
    assert "AMBIGUOUS_SECURITY_SESSION" in result.reasons
    assert "SAME_PROVIDER_CONFLICT" not in result.reasons


@pytest.mark.parametrize("kind", [CorporateActionKind.DIVIDEND, CorporateActionKind.RIGHTS,
                                 CorporateActionKind.SPLIT, CorporateActionKind.BONUS,
                                 CorporateActionKind.DEMERGER])
def test_resolution_never_overrides_action_continuity(kind):
    conflict, sources, bars = pair()
    result, _ = read(conflict, sources, bars, actions=(action(kind, D),))
    assert result.state.value == "NOT_READY"
    assert "SAME_PROVIDER_CONFLICT" not in result.reasons


def test_future_resolution_evidence_cannot_clear_block_and_strict_pit_unchanged():
    conflict, sources, bars = pair()
    p = proof(conflict, sources, bars)
    assert p.resolves_window(bars, p.known_at)
    assert not p.resolves_window(bars, p.known_at - timedelta(microseconds=1))
    value, _ = read(conflict, sources, bars)
    strict = read_certified_daily_technical_bars(request=replace(value.request,
        use_mode=NseUdiffDailyTechnicalUseMode.STRICT_HISTORICAL_PIT_TECHNICAL), evidence=None)
    assert strict.state.value == "NOT_READY" and strict.certification is None
    assert strict.reasons == ("STRICT_HISTORICAL_PIT_SOURCE_AVAILABILITY_UNAVAILABLE",)


def test_resolution_identity_order_timezone_serialization_and_tampering():
    conflict, sources, bars = pair()
    a = proof(conflict, sources, bars)
    b = proof(conflict, sources, tuple(reversed(bars)))
    assert a == b and a.to_dict() == b.to_dict()
    tz = timezone(timedelta(hours=5, minutes=30))
    c = proof(replace(conflict, detected_at=conflict.detected_at.astimezone(tz)),
              tuple(replace(s, observed_at=s.observed_at.astimezone(tz)) for s in sources), bars)
    assert c.fingerprint == a.fingerprint
    with pytest.raises(FrozenInstanceError):
        a.state = State.CURRENT_TRUE_SOURCE_CONFLICT
    with pytest.raises(ValueError, match="RECONCILIATION_INVALID"):
        replace(a, fingerprint="sha256:" + "0" * 64)
    with pytest.raises(ValueError, match="RECONCILIATION_INVALID"):
        replace(a, state=State.CURRENT_TRUE_SOURCE_CONFLICT)
    value, _ = read(conflict, sources, bars)
    assert json.loads(serialize_nse_udiff_certified_daily_technical_read(value))["fingerprint"] == value.fingerprint


@pytest.mark.parametrize("case", ["row", "artifact", "storage", "duplicate", "swapped"])
def test_tampered_or_ambiguous_resolution_evidence_rejected(case):
    conflict, sources, bars = pair()
    with pytest.raises(ValueError):
        if case == "row":
            object.__setattr__(sources[0], "fingerprint", "sha256:" + "0" * 64)
        elif case == "artifact":
            object.__setattr__(conflict, "conflict_fingerprint", "0" * 64)
        elif case == "storage":
            bars = (replace(bars[0], close=Decimal("100")), bars[1])
        elif case == "duplicate":
            bars = bars + bars[:1]
        elif case == "swapped":
            sources = tuple(reversed(sources))
        proof(conflict, sources, bars)


def test_duplicate_and_orphan_reconciliation_rejected():
    conflict, sources, bars = pair()
    p = proof(conflict, sources, bars)
    for artifacts, proofs in (((conflict,), (p, p)), ((), (p,))):
        with pytest.raises(ValueError, match="RECONCILIATION_(DUPLICATE|ORPHAN)"):
            audit_udiff_same_provider_conflicts(artifacts, reconciliations=proofs)


def test_resolved_assessment_cannot_be_detached_from_its_proof():
    conflict, sources, bars = pair()
    p = proof(conflict, sources, bars)
    a, = audit_udiff_same_provider_conflicts((conflict,), reconciliations=(p,))
    with pytest.raises(ValueError, match="ASSESSMENT_INVALID"):
        replace(a, reconciliation=None)


def test_no_runtime_clock_network_persistence_or_execution_calls():
    import app.market_data.nse_udiff_conflict_resolution as module
    text = inspect.getsource(module)
    for forbidden in ("datetime.now", "sqlite3", "requests", "app.portfolio", "app.broker",
                      "app.orders", "app.api", "app.signals", "app.analysis", "upstox"):
        assert forbidden not in text
