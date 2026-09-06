from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from app.market_data.official_nse_index_ohlc_feasibility import (
    OfficialIndexOhlcAvailability,
    OfficialIndexReturnFamily,
    OfficialNseIndexOhlcFeasibilityProbe,
    OfficialNseIndexOhlcProbeTarget,
    serialize_official_nse_index_ohlc_feasibility,
)


START = date(2026, 9, 3)
END = date(2026, 9, 4)
SESSIONS = (START, END)


def _target(*, query_names: tuple[str, ...] = ("Nifty Chemicals",), affected: int = 45) -> OfficialNseIndexOhlcProbeTarget:
    return OfficialNseIndexOhlcProbeTarget(
        canonical_sector="Chemicals",
        canonical_index_id="NSE_SECTOR_INDEX:CHEMICALS",
        configured_official_name=query_names[0],
        historical_query_names=query_names,
        return_family=OfficialIndexReturnFamily.PRICE_RETURN_INDEX,
        affected_security_count=affected,
    )


def _raw(
    *,
    name: str = "Nifty Chemicals",
    open_value: str = "100.0",
    high: str = "102.0",
    low: str = "99.0",
    close: str = "101.0",
    sessions: tuple[date, ...] = SESSIONS,
) -> bytes:
    rows = [{
        "INDEX_NAME": name,
        "HistoricalDate": item.strftime("%d %b %Y"),
        "OPEN": open_value,
        "HIGH": high,
        "LOW": low,
        "CLOSE": close,
    } for item in reversed(sessions)]
    return json.dumps(rows, separators=(",", ":")).encode()


class _Transport:
    def __init__(self, responses: dict[str, bytes]) -> None:
        self.responses = responses
        self.calls: list[str] = []

    def fetch(self, *, official_index_name: str, start: date, end: date) -> bytes:
        assert (start, end) == (START, END)
        self.calls.append(official_index_name)
        return self.responses[official_index_name]


def _probe(transport: _Transport, *, pauses: list[float] | None = None) -> OfficialNseIndexOhlcFeasibilityProbe:
    return OfficialNseIndexOhlcFeasibilityProbe(
        transport=transport,
        request_interval_seconds=1.0,
        sleeper=(pauses if pauses is not None else []).append,
    )


def test_exact_first_party_full_ohlc_is_session_aligned_and_deterministic() -> None:
    transport = _Transport({"Nifty Chemicals": _raw()})
    result = _probe(transport).probe(target=_target(), start=START, end=END, expected_sessions=(item for item in SESSIONS))
    assert result.availability is OfficialIndexOhlcAvailability.OFFICIAL_OHLC_VERIFIED
    assert result.observed_fields == ("DATE", "OPEN", "HIGH", "LOW", "CLOSE")
    assert result.first_session == START and result.last_session == END
    assert result.session_count == 2
    assert result.duplicate_count == result.conflict_count == result.missing_expected_session_count == 0
    assert result.potential_rule_2_3_coverage_gain == 45
    assert serialize_official_nse_index_ohlc_feasibility(result) == serialize_official_nse_index_ohlc_feasibility(result)


def test_close_only_receipt_is_descriptive_and_cannot_claim_ohlc_coverage() -> None:
    transport = _Transport({"Nifty Chemicals": _raw(open_value="-", high="-", low="-")})
    result = _probe(transport).probe(target=_target(), start=START, end=END, expected_sessions=SESSIONS)
    assert result.availability is OfficialIndexOhlcAvailability.OFFICIAL_CLOSE_ONLY
    assert result.observed_fields == ("DATE", "CLOSE")
    assert result.potential_rule_2_3_coverage_gain == 0


def test_partially_populated_ohlc_columns_are_not_misclassified_as_close_only() -> None:
    raw = json.loads(_raw().decode())
    raw[0]["HIGH"] = "-"
    transport = _Transport({"Nifty Chemicals": json.dumps(raw).encode()})
    result = _probe(transport).probe(target=_target(), start=START, end=END, expected_sessions=SESSIONS)
    assert result.availability is OfficialIndexOhlcAvailability.OFFICIAL_INDEX_EXISTS_OHLC_NOT_FOUND
    assert result.observed_fields == ("DATE", "OPEN", "HIGH", "LOW", "CLOSE")
    assert result.potential_rule_2_3_coverage_gain == 0


def test_alternate_official_query_name_is_reported_as_non_activating_mapping_mismatch() -> None:
    configured, alternate = "Nifty Consumer Durables Index", "Nifty Consumer Durables"
    target = _target(query_names=(configured, alternate), affected=41)
    pauses: list[float] = []
    transport = _Transport({configured: b"[]", alternate: _raw(name=alternate)})
    result = _probe(transport, pauses=pauses).probe(target=target, start=START, end=END, expected_sessions=SESSIONS)
    assert result.availability is OfficialIndexOhlcAvailability.OFFICIAL_NAME_OR_PARAMETER_MISMATCH
    assert result.observed_official_name == alternate
    assert result.reason_code == "NSE_INDICES_HISTORICAL_CONFIGURED_NAME_NOT_RETRIEVABLE_ALTERNATE_VERIFIED"
    assert result.potential_rule_2_3_coverage_gain == 41
    assert transport.calls == [configured, alternate]
    assert pauses == [1.0]


def test_missing_expected_session_never_receives_synthetic_fill_or_verified_status() -> None:
    transport = _Transport({"Nifty Chemicals": _raw(sessions=(START,))})
    result = _probe(transport).probe(target=_target(), start=START, end=END, expected_sessions=SESSIONS)
    assert result.availability is OfficialIndexOhlcAvailability.NOT_VERIFIED
    assert result.missing_expected_session_count == 1
    assert result.reason_code == "NSE_INDICES_HISTORICAL_SESSION_ALIGNMENT_FAILED"
    assert result.potential_rule_2_3_coverage_gain == 0


def test_duplicate_session_conflict_is_rejected_without_arbitrary_row_selection() -> None:
    raw = json.loads(_raw().decode())
    raw.append({**raw[0], "CLOSE": "99.0"})
    transport = _Transport({"Nifty Chemicals": json.dumps(raw).encode()})
    result = _probe(transport).probe(target=_target(), start=START, end=END, expected_sessions=SESSIONS)
    assert result.availability is OfficialIndexOhlcAvailability.NOT_VERIFIED
    assert result.duplicate_count == result.conflict_count == 1
    assert result.reason_code == "NSE_INDICES_HISTORICAL_DUPLICATE_SESSION_CONFLICT"


def test_malformed_or_wrong_index_response_fails_closed() -> None:
    malformed = _probe(_Transport({"Nifty Chemicals": b"not json"})).probe(target=_target(), start=START, end=END, expected_sessions=SESSIONS)
    wrong_name = _probe(_Transport({"Nifty Chemicals": _raw(name="Nifty Chemicals TRI")})).probe(target=_target(), start=START, end=END, expected_sessions=SESSIONS)
    assert malformed.availability is OfficialIndexOhlcAvailability.NOT_VERIFIED
    assert malformed.reason_code == "NSE_INDICES_HISTORICAL_RESPONSE_MALFORMED"
    assert wrong_name.availability is OfficialIndexOhlcAvailability.OFFICIAL_NAME_OR_PARAMETER_MISMATCH
    assert wrong_name.potential_rule_2_3_coverage_gain == 0


def test_duplicate_or_invalid_expected_sessions_are_rejected_at_construction_boundary() -> None:
    with pytest.raises(ValueError, match="EXPECTED_SESSIONS_INVALID"):
        _probe(_Transport({"Nifty Chemicals": _raw()})).probe(
            target=_target(), start=START, end=END, expected_sessions=(START, START),
        )
    with pytest.raises(ValueError, match="PROBE_TARGET_INVALID"):
        OfficialNseIndexOhlcProbeTarget(
            "Chemicals", "NSE_SECTOR_INDEX:CHEMICALS", "Nifty Chemicals", ("Nifty Chemicals",),
            OfficialIndexReturnFamily.TOTAL_RETURN_INDEX, 45,
        )


def test_feasibility_contract_has_no_storage_provider_or_runtime_dependencies() -> None:
    source = (Path(__file__).parents[2] / "app" / "market_data" / "official_nse_index_ohlc_feasibility.py").read_text(encoding="utf-8")
    imports = "\n".join(line.lower() for line in source.splitlines() if line.startswith(("from ", "import ")))
    forbidden = ("sqlite", "upstox", "yfinance", "broker", "portfolio", "app.storage", "app.signals")
    assert not any(item in imports for item in forbidden)
    assert "datetime.now" not in source and "date.today" not in source
    assert "NSE_INDICES_HISTORICAL_URL" in source
