from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha256

from app.data_operations.nse_reg31_identity import (
    NseReg31IdentityReconciliationStore, Reg31IdentityEvidence, Reg31IdentityRelationship, Reg31IdentitySufficiency, Reg31SecurityClass,
    classify_reg31_identity,
)
from app.storage.database import DatabaseBackend, DatabaseSettings
from app.storage.repository_factory import create_core_api_snapshot_repository


T = datetime(2026, 9, 1, tzinfo=UTC)


def _evidence(isin: str, symbol: str = "DEEPINDS", issuer: str = "Deep Industries Limited", security_class: Reg31SecurityClass = Reg31SecurityClass.EQUITY) -> Reg31IdentityEvidence:
    reference = "https://nsearchives.nseindia.com/corporate/xbrl/example.xml"
    return Reg31IdentityEvidence(isin, symbol, issuer, security_class, T, reference, sha256((isin + symbol + issuer).encode()).hexdigest())


def _classify(current: Reg31IdentityEvidence, returned: Reg31IdentityEvidence, **kwargs):
    return classify_reg31_identity(
        canonical_instrument_id="NSE:" + current.isin, current_identity=current, returned_identity=returned,
        known_at=T, official_evidence_references=(current.source_reference, returned.source_reference), **kwargs,
    )


def test_current_exact_identity_is_sufficient_and_deterministic() -> None:
    current = _evidence("INE0FHS01024")
    first = _classify(current, current)
    second = _classify(current, current)
    assert first.relationship is Reg31IdentityRelationship.CURRENT_MATCH
    assert first.sufficiency is Reg31IdentitySufficiency.SUFFICIENT
    assert first.fingerprint == second.fingerprint and first.acquisition_permitted


def test_verified_predecessor_requires_exact_continuity_and_effective_date() -> None:
    value = _classify(
        _evidence("INE0FHS01024"), _evidence("INE0FHS01016"), predecessor_proven=True,
        effective_date=datetime(2023, 4, 10, tzinfo=UTC),
    )
    assert value.relationship is Reg31IdentityRelationship.VERIFIED_PREDECESSOR
    assert value.sufficiency is Reg31IdentitySufficiency.SUFFICIENT and value.acquisition_permitted


def test_partly_paid_legacy_security_is_distinct_and_quarantined() -> None:
    value = _classify(
        _evidence("INE090A01021", "ICICIBANK", "ICICI Bank Limited"),
        _evidence("IN9090A01011", "ICICIBANK", "ICICI Bank Limited", Reg31SecurityClass.EQUITY_PARTLY_PAID),
    )
    assert value.relationship is Reg31IdentityRelationship.DISTINCT_LEGACY_SECURITY
    assert not value.acquisition_permitted


def test_same_class_mismatch_without_proven_predecessor_is_anomaly_not_acceptance() -> None:
    value = _classify(_evidence("INE0FHS01024"), _evidence("INE0FHS01016"))
    assert value.relationship is Reg31IdentityRelationship.SOURCE_METADATA_ANOMALY
    assert value.sufficiency is Reg31IdentitySufficiency.INSUFFICIENT and not value.acquisition_permitted


def test_symbol_or_issuer_only_match_is_never_accepted() -> None:
    value = _classify(_evidence("INE0FHS01024"), _evidence("INE0FHS01016", issuer="Other Issuer"))
    assert value.relationship is Reg31IdentityRelationship.UNRESOLVED
    assert not value.acquisition_permitted


def test_no_canonical_identity_or_ownership_values_are_mutated() -> None:
    current = _evidence("INE0FHS01024")
    value = _classify(current, _evidence("INE0FHS01016"), predecessor_proven=True, effective_date=datetime(2023, 4, 10, tzinfo=UTC))
    assert value.current_identity.isin == "INE0FHS01024"
    assert "percentage" not in repr(value).lower() and "promoter" not in repr(value).lower()


def test_reconciliation_is_immutable_and_reopens_point_in_time_safely(tmp_path) -> None:
    repository = create_core_api_snapshot_repository(DatabaseSettings(DatabaseBackend.SQLITE, f"sqlite:///{tmp_path / 'identity.db'}"))
    value = _classify(_evidence("INE0FHS01024"), _evidence("INE0FHS01016"), predecessor_proven=True, effective_date=datetime(2023, 4, 10, tzinfo=UTC))
    NseReg31IdentityReconciliationStore(repository).save(value)
    reopened = NseReg31IdentityReconciliationStore(repository).get(
        canonical_instrument_id="NSE:INE0FHS01024", returned_isin="INE0FHS01016", as_of=T,
    )
    assert reopened == value
