from __future__ import annotations

import ast
from dataclasses import replace

import pytest

from app.market_data.nse_udiff_daily_technical_eligibility import (
    DailyTechnicalRequirement,
    DailyTechnicalRequirementProfile,
)
from app.historical.nse_udiff_effective_identity_coverage import NseUdiffEffectiveIdentityCoverageIndex
from app.market_data.nse_udiff_daily_technical_read import (
    NseUdiffDailyTechnicalReadEvidence,
    NseUdiffDailyTechnicalReadReason,
    NseUdiffDailyTechnicalReadRequest,
    NseUdiffDailyTechnicalReadState,
    NseUdiffDailyTechnicalUseMode,
    read_certified_daily_technical_bars,
    serialize_nse_udiff_certified_daily_technical_read,
)
from tests.unit.test_nse_udiff_daily_technical_eligibility import (
    AT,
    D1,
    D2,
    D3,
    INSTRUMENT,
    action,
    bar,
    coverage,
    interval,
)
from app.historical.security_master import CorporateActionKind


def request(*, mode=NseUdiffDailyTechnicalUseMode.CURRENT_DESCRIPTIVE_TECHNICAL, profile=DailyTechnicalRequirementProfile.PRICE_AND_VOLUME):
    return NseUdiffDailyTechnicalReadRequest(
        INSTRUMENT.instrument_id, D1, D3, DailyTechnicalRequirement(profile), mode, AT,
    )


def evidence(*, bars=(bar(D1), bar(D2), bar(D3)), action_coverage=None, actions=(), intervals=None):
    bars = tuple(sorted(bars, key=lambda item: (item.start_time, item.bar_id)))
    return NseUdiffDailyTechnicalReadEvidence(
        (D1, D2, D3), bars, tuple(sorted(tuple(interval(item) for item in bars) if intervals is None else intervals, key=lambda item: item.interval_id)),
        coverage() if action_coverage is None else action_coverage, tuple(sorted(actions, key=lambda item: (item.effective_date, item.action_id))), (),
    )


def test_current_descriptive_read_returns_exact_complete_certified_bars_with_lineage():
    value = read_certified_daily_technical_bars(request=request(), evidence=evidence())
    assert value.state is NseUdiffDailyTechnicalReadState.READY
    assert len(value.bars) == 3
    assert {item.bar_id for item in value.bars} == set(value.certification.source_bar_ids)
    assert value.source_observation_ids == tuple(sorted(item.source_observation_identity for item in value.bars))
    assert value.certification.identity_interval_ids
    assert value.certification.action_coverage_fingerprint
    assert value.certification.price_continuity.value == "PRICE_CONTINUITY_READY"
    assert value.certification.volume_continuity.value == "VOLUME_CONTINUITY_READY"


def test_certificate_lineage_id_order_does_not_replace_nse_session_order():
    values = (replace(bar(D1), bar_id="z-first"), replace(bar(D2), bar_id="a-second"), replace(bar(D3), bar_id="m-third"))
    result = read_certified_daily_technical_bars(request=request(), evidence=evidence(bars=values))
    assert result.state is NseUdiffDailyTechnicalReadState.READY
    assert tuple(item.bar_id for item in result.bars) == ("z-first", "a-second", "m-third")
    assert set(result.certification.source_bar_ids) == {"z-first", "a-second", "m-third"}


def test_reader_reuses_the_existing_immutable_identity_index_without_rebuilding_it():
    values = (bar(D1), bar(D2), bar(D3))
    indexed = NseUdiffDailyTechnicalReadEvidence(
        (D1, D2, D3), values, NseUdiffEffectiveIdentityCoverageIndex(tuple(interval(item) for item in values)), coverage(), (), (),
    )
    result = read_certified_daily_technical_bars(request=request(), evidence=indexed)
    assert result.state is NseUdiffDailyTechnicalReadState.READY


def test_strict_pit_does_not_read_or_cache_current_descriptive_udiff_history():
    current = read_certified_daily_technical_bars(request=request(), evidence=evidence())
    strict = read_certified_daily_technical_bars(
        # Strict PIT must not inspect the retrospective UDiFF source bundle.
        request=request(mode=NseUdiffDailyTechnicalUseMode.STRICT_HISTORICAL_PIT_TECHNICAL), evidence=None,
    )
    assert current.state is NseUdiffDailyTechnicalReadState.READY
    assert strict.state is NseUdiffDailyTechnicalReadState.NOT_READY
    assert strict.bars == () and strict.certification is None
    assert strict.reasons == (NseUdiffDailyTechnicalReadReason.STRICT_HISTORICAL_PIT_SOURCE_AVAILABILITY_UNAVAILABLE.value,)


def test_price_and_volume_request_cannot_downgrade_to_price_only():
    value = read_certified_daily_technical_bars(request=request(), evidence=evidence(bars=(bar(D1), bar(D2, volume=0), bar(D3))))
    assert value.state is NseUdiffDailyTechnicalReadState.NOT_READY
    assert NseUdiffDailyTechnicalReadReason.CERTIFICATION_NOT_READY.value in value.reasons
    assert "VOLUME_REQUIRED_BUT_ZERO_OR_MISSING" in value.reasons
    assert value.bars == ()


def test_other_provider_bar_cannot_be_merged_or_used_as_a_fallback():
    mixed = (bar(D1), replace(bar(D2), provenance=replace(bar(D2).provenance, provider="upstox")), bar(D3))
    result = read_certified_daily_technical_bars(request=request(), evidence=evidence(bars=mixed, intervals=(interval(bar(D1)), interval(bar(D3)))))
    assert result.state is NseUdiffDailyTechnicalReadState.NOT_READY
    assert "SOURCE_ROW_INVALID" in result.reasons
    assert result.bars == ()


def test_missing_source_artifact_lineage_cannot_escape_as_a_ready_read():
    values = (bar(D1), bar(D2), replace(bar(D3), provenance=replace(bar(D3).provenance, source_reference=None)))
    result = read_certified_daily_technical_bars(request=request(), evidence=evidence(bars=values))
    assert result.state is NseUdiffDailyTechnicalReadState.NOT_READY
    assert result.reasons == (NseUdiffDailyTechnicalReadReason.CERTIFIED_SOURCE_MISMATCH.value,)


@pytest.mark.parametrize("series, reason", (("BL", "BL_NOT_ORDINARY_DAILY_TECHNICAL_PRICE_SERIES"), ("T0", "T0_DISTINCT_SETTLEMENT_SERIES")))
def test_nonordinary_series_never_returns_an_ordinary_daily_read(series, reason):
    values = (bar(D1, series=series), bar(D2, series=series), bar(D3, series=series))
    result = read_certified_daily_technical_bars(request=request(), evidence=evidence(bars=values))
    assert result.state is NseUdiffDailyTechnicalReadState.NOT_READY
    assert reason in result.reasons


def test_exact_post_event_segment_can_be_read_without_weakening_prior_action_block():
    blocked = read_certified_daily_technical_bars(
        request=request(), evidence=evidence(actions=(action(CorporateActionKind.RIGHTS, D2),)),
    )
    post = read_certified_daily_technical_bars(
        request=NseUdiffDailyTechnicalReadRequest(INSTRUMENT.instrument_id, D3, D3, DailyTechnicalRequirement(DailyTechnicalRequirementProfile.PRICE_ONLY), NseUdiffDailyTechnicalUseMode.CURRENT_DESCRIPTIVE_TECHNICAL, AT),
        evidence=NseUdiffDailyTechnicalReadEvidence((D3,), (bar(D3),), (interval(bar(D3)),), coverage(D3, D3), (), ()),
    )
    assert blocked.state is NseUdiffDailyTechnicalReadState.NOT_READY
    assert "RIGHTS_ADJUSTMENT_NOT_READY" in blocked.reasons
    assert post.state is NseUdiffDailyTechnicalReadState.READY


def test_deterministic_serialization_and_certification_tampering_is_rejected_as_blocked():
    first = read_certified_daily_technical_bars(request=request(), evidence=evidence())
    second = read_certified_daily_technical_bars(request=request(), evidence=evidence())
    assert first == second
    assert serialize_nse_udiff_certified_daily_technical_read(first) == serialize_nse_udiff_certified_daily_technical_read(second)
    # The result's fingerprint binds the exact selected bars and certification;
    # a caller cannot relabel an existing successful read after the fact.
    with pytest.raises(ValueError, match="RESULT_INVALID"):
        replace(first, fingerprint="sha256:" + "0" * 64)


def test_reader_has_no_provider_fallback_or_analysis_side_effect_dependencies():
    source = open("app/market_data/nse_udiff_daily_technical_read.py", encoding="utf-8").read()
    tree = ast.parse(source)
    imports = {alias.name for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.module for alias in node.names if node.module}
    forbidden = {"app.market_data.upstox", "app.market_data.providers", "app.analysis.series", "app.api", "app.portfolio", "app.orders", "app.broker"}
    assert not imports & forbidden
    assert "NseUdiffDailyTechnicalReadEvidence" in source
    assert "datetime.now" not in source and "current_time" not in source
