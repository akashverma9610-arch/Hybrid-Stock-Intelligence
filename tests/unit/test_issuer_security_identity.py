from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime, timedelta, timezone
import gzip
import inspect

import pytest

import app.historical.issuer_security_identity as bridge_contract
from app.historical.nse_mii_security_master import (
    NseMiiSecurityMasterHttpResponse,
    extract_nse_mii_security_master,
    nse_mii_security_master_url,
)
from app.historical.nse_session_identity import (
    activate_nse_session_identity_policy,
    approve_nse_session_identity_policy,
    session_point_identity_from_row,
)


T = datetime(2026, 9, 4, 10, tzinfo=UTC)
HEADERS = "FinInstrmId,TckrSymb,SctySrs,FinInstrmNm,ISIN,SctyStsNrmlMkt,ListgDt,RmvlDt,FinInstrmTp,SctyTp\n"


def _session(day: date = date(2026, 8, 31), *, symbol: str = "EXACT", isin: str = "INE000A01001"):
    extraction = extract_nse_mii_security_master(NseMiiSecurityMasterHttpResponse(
        day, nse_mii_security_master_url(day), "application/x-gzip",
        gzip.compress((HEADERS + f"100,{symbol},EQ,Exact Ltd,{isin},6,100,0,EQ,EQUITY\n").encode()), T,
    ))
    approval = approve_nse_session_identity_policy(
        approval_id="issuer-bridge-session-approval", approved_by="human:approved", approved_at=T,
    )
    activation = activate_nse_session_identity_policy(
        selection_id="issuer-bridge-session-activation", approval=approval,
        activated_by="human:approved", activated_at=T,
    )
    return session_point_identity_from_row(activation=activation, snapshot=extraction.snapshot, row=extraction.rows[0])


def _bridge(
    session,
    *,
    identifier_type=bridge_contract.IssuerIdentifierType.CIN,
    identifier_value="L12345MH2010PLC123456",
    evidence_id="official:filing:exact-one",
    evidence_fingerprint="sha256:" + "1" * 64,
    source_as_of: date | None = None,
    observed_at: datetime = T,
    known_at: datetime | None = None,
    semantics=bridge_contract.IssuerSecurityBridgeTemporalSemantics.EXACT_SESSION_DATE,
    effective_from: date | None = None,
    effective_to: date | None = None,
):
    return bridge_contract.create_issuer_security_bridge(
        session_security=session,
        issuer_identifier_type=identifier_type,
        issuer_identifier_value=identifier_value,
        source_evidence_id=evidence_id,
        source_evidence_fingerprint=evidence_fingerprint,
        source_type=bridge_contract.IssuerSecurityBridgeSourceType.OFFICIAL_CORPORATE_FILING_STRUCTURED_IDENTITY,
        source_reference="https://exchange.example/filing/exact-one",
        source_as_of_date=source_as_of or session.session_date,
        source_observed_at=observed_at,
        historical_known_at=known_at,
        temporal_semantics=semantics,
        effective_from=effective_from,
        effective_to=effective_to,
    )


def test_exact_security_to_issuer_bridge_preserves_isin_identifier_and_immutable_serialization():
    session = _session()
    value = _bridge(session)
    assert (value.exchange, value.symbol, value.isin) == ("NSE", "EXACT", "INE000A01001")
    assert value.issuer_identifier_value == "L12345MH2010PLC123456"
    assert value.issuer_legal_entity_id == "issuer:cin:L12345MH2010PLC123456"
    assert bridge_contract.serialize_issuer_security_bridge(value) == bridge_contract.serialize_issuer_security_bridge(value)
    with pytest.raises((AttributeError, TypeError)):
        value.isin = "INE000A01002"  # type: ignore[misc]


def test_exact_exchange_symbol_is_preserved_without_identifier_normalization():
    session = _session(symbol="M&M")
    assert _bridge(session).symbol == "M&M"


@pytest.mark.parametrize(
    ("identifier_type", "identifier_value", "expected_id"),
    (
        (bridge_contract.IssuerIdentifierType.CIN, "L12345MH2010PLC123456", "issuer:cin:L12345MH2010PLC123456"),
        (bridge_contract.IssuerIdentifierType.LEI, "5493001KJTIIGC8Y1R12", "issuer:lei:5493001KJTIIGC8Y1R12"),
        (bridge_contract.IssuerIdentifierType.REGULATOR_REGISTRATION_ID, "rbi:nbfc:12345", "issuer:regulator_registration_id:rbi:nbfc:12345"),
    ),
)
def test_exact_issuer_identifier_types_are_preserved_without_name_reconciliation(identifier_type, identifier_value, expected_id):
    value = _bridge(_session(), identifier_type=identifier_type, identifier_value=identifier_value)
    assert value.issuer_identifier_value == identifier_value
    assert value.issuer_legal_entity_id == expected_id


def test_malformed_identifier_and_free_form_name_are_rejected():
    session = _session()
    with pytest.raises(bridge_contract.IssuerSecurityBridgeError, match="ISSUER_IDENTIFIER_INVALID"):
        _bridge(session, identifier_value="Exact Limited")
    with pytest.raises(bridge_contract.IssuerSecurityBridgeError, match="IDENTIFIER_TYPE_INVALID"):
        _bridge(session, identifier_type="NAME")  # type: ignore[arg-type]


def test_parent_or_subsidiary_fields_are_not_a_bridge_surface_and_no_name_matching_path_exists():
    signature = inspect.signature(bridge_contract.create_issuer_security_bridge)
    assert "parent" not in signature.parameters and "subsidiary" not in signature.parameters and "issuer_name" not in signature.parameters
    with pytest.raises(TypeError):
        bridge_contract.create_issuer_security_bridge(  # type: ignore[call-arg]
            session_security=_session(), issuer_identifier_type=bridge_contract.IssuerIdentifierType.CIN,
            issuer_identifier_value="L12345MH2010PLC123456", source_evidence_id="official:one",
            source_evidence_fingerprint="sha256:" + "1" * 64,
            source_type=bridge_contract.IssuerSecurityBridgeSourceType.NSE_OFFICIAL_LISTING_RECORD,
            source_reference="https://exchange.example/one", source_as_of_date=date(2026, 8, 31),
            source_observed_at=T, parent_issuer="issuer:parent",
        )


def test_exact_same_session_resolution_is_idempotent_and_duplicate_input_is_not_false_ambiguity():
    session = _session(); value = _bridge(session)
    first = bridge_contract.resolve_issuer_security_bridge(session, bridges=(value, value))
    second = bridge_contract.resolve_issuer_security_bridge(session, bridges=(value,))
    assert first == second
    assert first.readiness is bridge_contract.IssuerSecurityBridgeReadiness.EXACT_ISSUER_BRIDGE
    assert first.reasons == (bridge_contract.IssuerSecurityBridgeReason.EXACT_PRIMARY_BRIDGE_PRESENT,)
    assert len(first.bridges) == 1
    assert bridge_contract.serialize_issuer_security_bridge_resolution(first) == bridge_contract.serialize_issuer_security_bridge_resolution(second)


def test_current_bridge_is_not_leaked_to_a_different_historical_session():
    current = _session(date(2026, 8, 31)); historical = _session(date(2024, 2, 5))
    result = bridge_contract.resolve_issuer_security_bridge(historical, bridges=(_bridge(current),))
    assert result.readiness is bridge_contract.IssuerSecurityBridgeReadiness.PIT_DATE_UNSUPPORTED
    assert result.reasons == (bridge_contract.IssuerSecurityBridgeReason.SESSION_SCOPED_BRIDGE_REQUIRED,)
    assert result.bridges[0].session_date == date(2026, 8, 31)


def test_changed_isin_is_not_stitched_even_when_the_symbol_and_issuer_identifier_match():
    old = _session(date(2024, 2, 5), isin="INE000A01001")
    changed = _session(date(2026, 8, 31), isin="INE000A01002")
    result = bridge_contract.resolve_issuer_security_bridge(changed, bridges=(_bridge(old),))
    assert result.readiness is bridge_contract.IssuerSecurityBridgeReadiness.ISSUER_EVIDENCE_UNAVAILABLE
    assert not result.bridges


def test_source_date_and_known_time_prevent_future_evidence_from_becoming_a_bridge():
    historical = _session(date(2024, 2, 5))
    with pytest.raises(bridge_contract.IssuerSecurityBridgeError, match="EXACT_SESSION_SEMANTICS_INVALID"):
        _bridge(historical, source_as_of=date(2026, 8, 31))
    with pytest.raises(bridge_contract.IssuerSecurityBridgeError, match="FUTURE_EVIDENCE"):
        _bridge(historical, known_at=datetime(2026, 8, 31, tzinfo=UTC))


def test_explicit_effective_interval_requires_real_bounds_and_never_fabricates_dates():
    session = _session()
    with pytest.raises(bridge_contract.IssuerSecurityBridgeError, match="EFFECTIVE_INTERVAL_REQUIRED"):
        _bridge(session, semantics=bridge_contract.IssuerSecurityBridgeTemporalSemantics.EXPLICIT_EFFECTIVE_INTERVAL)
    value = _bridge(
        session, semantics=bridge_contract.IssuerSecurityBridgeTemporalSemantics.EXPLICIT_EFFECTIVE_INTERVAL,
        effective_from=date(2026, 1, 1), effective_to=date(2026, 12, 31),
    )
    assert (value.effective_from, value.effective_to) == (date(2026, 1, 1), date(2026, 12, 31))
    with pytest.raises(bridge_contract.IssuerSecurityBridgeError, match="FUTURE_OR_OUTSIDE_EFFECTIVE_EVIDENCE"):
        _bridge(
            session, semantics=bridge_contract.IssuerSecurityBridgeTemporalSemantics.EXPLICIT_EFFECTIVE_INTERVAL,
            source_as_of=date(2026, 9, 1), effective_from=date(2026, 1, 1),
        )
    with pytest.raises(bridge_contract.IssuerSecurityBridgeError, match="FUTURE_OR_OUTSIDE_EFFECTIVE_EVIDENCE"):
        _bridge(
            session, semantics=bridge_contract.IssuerSecurityBridgeTemporalSemantics.EXPLICIT_EFFECTIVE_INTERVAL,
            effective_from=date(2026, 9, 1),
        )


def test_conflicting_exact_issuer_evidence_fails_closed_with_all_lineage_retained():
    session = _session()
    cin = _bridge(session)
    lei = _bridge(
        session, identifier_type=bridge_contract.IssuerIdentifierType.LEI,
        identifier_value="5493001KJTIIGC8Y1R12", evidence_id="official:filing:exact-two",
        evidence_fingerprint="sha256:" + "2" * 64,
    )
    result = bridge_contract.resolve_issuer_security_bridge(session, bridges=(lei, cin))
    assert result.readiness is bridge_contract.IssuerSecurityBridgeReadiness.EVIDENCE_CONFLICTED
    assert result.reasons == (bridge_contract.IssuerSecurityBridgeReason.CONFLICTING_EXACT_ISSUER_EVIDENCE,)
    assert tuple(item.bridge_id for item in result.bridges) == tuple(sorted(item.bridge_id for item in (cin, lei)))


def test_tampered_bridge_or_empty_issuer_lineage_is_rejected():
    value = _bridge(_session())
    with pytest.raises(bridge_contract.IssuerSecurityBridgeError, match="INVALID|IDENTITY_MISMATCH|FINGERPRINT_MISMATCH"):
        replace(value, issuer_identifier_value="L12345MH2010PLC123457")
    with pytest.raises(bridge_contract.IssuerSecurityBridgeError, match="INVALID"):
        replace(value, source_evidence_id="")


def test_equivalent_timezone_aware_observation_values_have_stable_fingerprints():
    session = _session()
    utc_value = _bridge(session, observed_at=T)
    offset_value = _bridge(session, observed_at=T.astimezone(timezone(timedelta(hours=5, minutes=30))))
    assert utc_value == offset_value
    assert utc_value.fingerprint == offset_value.fingerprint


def test_identity_and_content_fingerprint_are_separate_without_circularity():
    session = _session(T.date())
    first = _bridge(session, observed_at=T, known_at=T)
    observed_again = _bridge(session, observed_at=T + timedelta(minutes=1), known_at=T)
    later_known = _bridge(session, observed_at=T, known_at=T.replace(hour=11))
    assert first.bridge_id == observed_again.bridge_id
    assert first.fingerprint != observed_again.fingerprint
    assert first.bridge_id != later_known.bridge_id


def test_missing_or_invalid_session_identity_stays_explicitly_unresolved():
    missing = bridge_contract.resolve_issuer_security_bridge(None, bridges=())
    assert missing.readiness is bridge_contract.IssuerSecurityBridgeReadiness.SECURITY_IDENTITY_UNRESOLVED
    assert missing.reasons == (bridge_contract.IssuerSecurityBridgeReason.EXACT_SESSION_SECURITY_REQUIRED,)
    session = _session()
    with pytest.raises(bridge_contract.IssuerSecurityBridgeError, match="SESSION_SECURITY_INVALID"):
        bridge_contract.create_issuer_security_bridge(
            session_security=object(),  # type: ignore[arg-type]
            issuer_identifier_type=bridge_contract.IssuerIdentifierType.CIN,
            issuer_identifier_value="L12345MH2010PLC123456", source_evidence_id="official:one",
            source_evidence_fingerprint="sha256:" + "1" * 64,
            source_type=bridge_contract.IssuerSecurityBridgeSourceType.NSE_OFFICIAL_LISTING_RECORD,
            source_reference="https://exchange.example/one", source_as_of_date=session.session_date, source_observed_at=T,
        )


def test_static_boundaries_exclude_company_type_backtests_portfolio_persistence_and_execution():
    source = open(bridge_contract.__file__, encoding="utf-8").read()
    for forbidden in (
        "app.intelligence.pit_company_type", "app.portfolio", "app.broker", "app.orders", "app.api",
        "app.runtime", "app.discovery", "sqlite3", "backtest", "place_order", "buy", "sell", "rotate",
    ):
        assert forbidden not in source.lower()
