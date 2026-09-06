"""UDiFF-only observation identity, shared by ingestion, storage and audit.

No canonical-security selection or cross-date continuity is implied.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from hashlib import sha256
import json
import re
from typing import Mapping, TYPE_CHECKING
from zoneinfo import ZoneInfo

if TYPE_CHECKING:
    from app.market_data.models import CanonicalOHLCVBar

PROVIDER = "nse_udiff_official"
IDENTITY_FIELDS = ("TradDt", "BizDt", "FinInstrmId", "ISIN", "TckrSymb", "SctySrs", "SsnId")


def source_row_id(fields: Mapping[str, str]) -> str:
    if any(not fields.get(k) or fields[k] != fields[k].strip() for k in IDENTITY_FIELDS):
        raise ValueError("NSE_UDIFF_SOURCE_IDENTITY_REQUIRED")
    day = date.fromisoformat(fields["TradDt"])
    if (day < date(2024, 7, 8) or fields["BizDt"] != day.isoformat() or
            not re.fullmatch(r"[A-Z]{2}[A-Z0-9]{9}[0-9]", fields["ISIN"]) or
            not re.fullmatch(r"[0-9]+", fields["FinInstrmId"])):
        raise ValueError("NSE_UDIFF_SOURCE_IDENTITY_INVALID")
    body = {
        "contract": "nse-udiff-conflict-semantics-v1",
        "source_family": "NSE_CM_UDIFF_FINAL_BHAVCOPY",
        "source_version": "nse-udiff-final-bhavcopy-v1",
        "identity": tuple((key, fields[key]) for key in IDENTITY_FIELDS),
    }
    return "nse-udiff-source-row:" + sha256(json.dumps(
        body, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
        allow_nan=False,
    ).encode()).hexdigest()


def is_udiff(bar: CanonicalOHLCVBar) -> bool:
    return bar.provenance.provider.strip().casefold() == PROVIDER


def source_fields(bar: CanonicalOHLCVBar) -> dict[str, str]:
    """Read retained source provenance, never a current master lookup.

    Legacy UDiFF instrument.symbol was admitted only after exact source-symbol
    matching. The migration verifies that assumption against archived bytes.
    """
    def label(prefix: str) -> str:
        values = [s.removeprefix(prefix) for s in bar.warnings if s.startswith(prefix)]
        if len(values) != 1:
            raise ValueError("NSE_UDIFF_SOURCE_PROVENANCE_AMBIGUOUS")
        return values[0]
    if not is_udiff(bar) or bar.timeframe.value != "1D" or bar.adjustment_status.value != "RAW":
        raise ValueError("NSE_UDIFF_SOURCE_SCOPE_INVALID")
    if bar.provenance.normalization_version != "nse-udiff-final-bhavcopy-v1":
        raise ValueError("NSE_UDIFF_SOURCE_VERSION_UNSUPPORTED")
    local_day = bar.start_time.astimezone(ZoneInfo("Asia/Kolkata")).date()
    start = datetime.combine(local_day, datetime.min.time(), tzinfo=ZoneInfo("Asia/Kolkata"))
    if bar.start_time != start or bar.end_time != start + timedelta(days=1):
        raise ValueError("NSE_UDIFF_SOURCE_INTERVAL_INVALID")
    reference = bar.provenance.provider_instrument_reference
    if not isinstance(reference, str) or not reference.startswith("NSE:CM:"):
        raise ValueError("NSE_UDIFF_SOURCE_TOKEN_REQUIRED")
    fields = {
        "TradDt": local_day.isoformat(),
        "BizDt": label("NSE_UDIFF_BIZ_DATE:"), "FinInstrmId": reference.removeprefix("NSE:CM:"),
        "ISIN": bar.instrument.isin or "", "TckrSymb": bar.instrument.symbol,
        "SctySrs": label("NSE_UDIFF_SERIES:"), "SsnId": label("NSE_UDIFF_SESSION:"),
    }
    source_row_id(fields)
    return fields


def observation_key(bar: CanonicalOHLCVBar) -> str:
    """Empty scope preserves all non-UDiFF provider keys unchanged."""
    return source_row_id(source_fields(bar)) if is_udiff(bar) else ""
