from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.historical.security_identity_selector import (
    HistoricalSecurityIdentityResolutionReason as Reason,
    HistoricalSecurityIdentityResolutionStatus as Status,
    historical_security_identity_resolution_fingerprint,
    resolve_historical_security_identity,
)
from app.historical.security_master import HistoricalSecurityIdentity, HistoricalSecurityStatus


T = datetime(2026, 9, 4, tzinfo=UTC)
INSTRUMENT = "NSE:INE000A01001"


def identity(*, identifier="identity", symbol="OLD", known=T - timedelta(days=10), effective=T - timedelta(days=5), effective_to=None, listed_from=T - timedelta(days=100), listed_until=None, status=HistoricalSecurityStatus.ACTIVE, isin="INE000A01001"):
    return HistoricalSecurityIdentity(identifier, INSTRUMENT, isin, "NSE", symbol, "EQ", listed_from, listed_until, listed_from, listed_until, effective, effective_to, status, "NSE_OFFICIAL", known, "v1", "primary://identity")


def test_exact_identity_is_pit_selected_and_serialized_deterministically():
    value = identity()
    result = resolve_historical_security_identity((value,), canonical_instrument_id=INSTRUMENT, as_of=T)
    assert result.status is Status.RESOLVED
    assert (result.symbol, result.isin, result.listed, result.eligible) == ("OLD", "INE000A01001", True, True)
    assert result.fingerprint == historical_security_identity_resolution_fingerprint(result)
    assert resolve_historical_security_identity((value,), canonical_instrument_id=INSTRUMENT, as_of=T) == result


def test_known_time_and_effective_time_are_distinct_and_future_symbol_is_not_substituted():
    old = identity(effective=T - timedelta(days=50), effective_to=T + timedelta(days=5))
    new = identity(identifier="new", symbol="NEW", known=T - timedelta(days=2), effective=T + timedelta(days=6))
    before = resolve_historical_security_identity((old, new), canonical_instrument_id=INSTRUMENT, as_of=T)
    after = resolve_historical_security_identity((old, new), canonical_instrument_id=INSTRUMENT, as_of=T + timedelta(days=7))
    assert before.status is Status.RESOLVED and before.symbol == "OLD"
    assert after.status is Status.RESOLVED and after.symbol == "NEW"


def test_future_known_identity_is_excluded_and_missing_identity_fails_closed():
    future = identity(known=T + timedelta(days=1), effective=T + timedelta(days=2))
    assert resolve_historical_security_identity((future,), canonical_instrument_id=INSTRUMENT, as_of=T).reasons == (Reason.IDENTITY_NOT_KNOWN_AT_AS_OF,)
    assert resolve_historical_security_identity((), canonical_instrument_id=INSTRUMENT, as_of=T).reasons == (Reason.IDENTITY_EVIDENCE_REQUIRED,)


@pytest.mark.parametrize("value,reason", ((identity(listed_until=T - timedelta(days=1)), Reason.LISTING_INTERVAL_EXCLUDES_AS_OF), (identity(status=HistoricalSecurityStatus.DELISTED), Reason.LIFECYCLE_NOT_ACTIVE), (identity(status=HistoricalSecurityStatus.INACTIVE), Reason.LIFECYCLE_NOT_ACTIVE)))
def test_listing_and_lifecycle_are_explicit_never_inferred_from_missing_prices(value, reason):
    result = resolve_historical_security_identity((value,), canonical_instrument_id=INSTRUMENT, as_of=T)
    assert result.status is Status.NOT_LISTED and result.reasons == (reason,)


def test_conflicting_effective_identity_fails_closed_and_identical_duplicate_is_deterministic():
    one = identity(identifier="a")
    conflict = identity(identifier="b", symbol="OTHER")
    result = resolve_historical_security_identity((one, conflict), canonical_instrument_id=INSTRUMENT, as_of=T)
    assert result.status is Status.EVIDENCE_CONFLICTED and result.reasons == (Reason.AMBIGUOUS_EFFECTIVE_IDENTITY,)
    duplicate = identity(identifier="b")
    assert resolve_historical_security_identity((duplicate, one), canonical_instrument_id=INSTRUMENT, as_of=T).identity_id == "a"


def test_tampered_resolution_and_naive_time_are_rejected():
    result = resolve_historical_security_identity((identity(),), canonical_instrument_id=INSTRUMENT, as_of=T)
    object.__setattr__(result, "symbol", "TAMPERED")
    assert result.fingerprint != historical_security_identity_resolution_fingerprint(result)
    with pytest.raises(ValueError, match="AS_OF_REQUIRED"):
        resolve_historical_security_identity((identity(),), canonical_instrument_id=INSTRUMENT, as_of=datetime(2026, 1, 1))
