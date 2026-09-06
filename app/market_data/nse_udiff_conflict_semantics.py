"""Pure source-row comparison; never repairs or selects a historical bar.

An exact archived exchange observation is not an effective identity interval.
The source date and the local observed-at timestamp remain separate facts.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from hashlib import sha256
import json
import re

from app.market_data.nse_udiff_daily_history import (
    NSE_UDIFF_START,
    NseUdiffDailySourceArtifact, UDIFF_COLUMNS, _parse_valid_archive,
)
from app.market_data.nse_udiff_source_identity import source_row_id

CONTRACT_VERSION = "nse-udiff-conflict-semantics-v1"
IDENTITY_FIELDS = (
    "TradDt", "BizDt", "FinInstrmId", "ISIN", "TckrSymb", "SctySrs", "SsnId",
)
VALUE_FIELDS = (
    "OpnPric", "HghPric", "LwPric", "ClsPric", "TtlTradgVol",
    "TtlTrfVal", "TtlNbOfTxsExctd",
)


class NseUdiffConflictClass(StrEnum):
    DUPLICATE_EQUIVALENT = "DUPLICATE_EQUIVALENT"
    DISTINCT_SERIES = "DISTINCT_SERIES"
    DISTINCT_SESSION = "DISTINCT_SESSION"
    DISTINCT_SOURCE_SECURITY_IDENTITY = "DISTINCT_SOURCE_SECURITY_IDENTITY"
    HISTORICAL_IDENTITY_DISCONTINUITY = "HISTORICAL_IDENTITY_DISCONTINUITY"
    TRUE_SOURCE_VALUE_CONFLICT = "TRUE_SOURCE_VALUE_CONFLICT"
    UNRESOLVED = "UNRESOLVED"


def _digest(value: object) -> str:
    return "sha256:" + sha256(json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class NseUdiffSourceRowEvidence:
    """A sealed source row, not an assertion of continuity or technical fitness."""

    artifact_id: str
    artifact_fingerprint: str
    content_sha256: str
    source_url: str
    observed_at: datetime
    row_index: int
    fields: tuple[tuple[str, str], ...]
    fingerprint: str

    def __post_init__(self) -> None:
        if (type(self.fields) is not tuple or
                any(type(pair) is not tuple or len(pair) != 2 or
                    any(type(part) is not str for part in pair) for pair in self.fields) or
                tuple(key for key, _ in self.fields) != UDIFF_COLUMNS):
            raise ValueError("NSE_UDIFF_SOURCE_ROW_SCHEMA_INVALID")
        row = dict(self.fields)
        try:
            day = date.fromisoformat(row["TradDt"])
            business = date.fromisoformat(row["BizDt"])
        except ValueError as error:
            raise ValueError("NSE_UDIFF_SOURCE_ROW_DATE_INVALID") from error
        if (day < NSE_UDIFF_START or day != business or
                (row["Sgmt"], row["Src"], row["FinInstrmTp"]) != ("CM", "NSE", "STK") or
                any(not row[key] or row[key] != row[key].strip() for key in IDENTITY_FIELDS) or
                not re.fullmatch(r"[0-9]+", row["FinInstrmId"]) or
                not re.fullmatch(r"[A-Z]{2}[A-Z0-9]{9}[0-9]", row["ISIN"])):
            raise ValueError("NSE_UDIFF_SOURCE_ROW_IDENTITY_INVALID")
        expected_url = f"https://nsearchives.nseindia.com/content/cm/BhavCopy_NSE_CM_0_0_0_{day:%Y%m%d}_F_0000.csv.zip"
        if (not self.artifact_id.startswith("nse-udiff-artifact:") or
                not re.fullmatch(r"sha256:[0-9a-f]{64}", self.artifact_fingerprint) or
                not re.fullmatch(r"[0-9a-f]{64}", self.content_sha256) or
                self.source_url != expected_url or type(self.row_index) is not int or
                self.row_index < 0 or self.observed_at.tzinfo is None or
                self.observed_at.utcoffset() is None):
            raise ValueError("NSE_UDIFF_SOURCE_ROW_PROVENANCE_INVALID")
        if self.fingerprint != _digest(self._body()):
            raise ValueError("NSE_UDIFF_SOURCE_ROW_FINGERPRINT_MISMATCH")

    @property
    def source_row_id(self) -> str:
        return source_row_id(dict(self.fields))

    def _body(self) -> dict[str, object]:
        return {
            "contract": CONTRACT_VERSION, "artifact_id": self.artifact_id,
            "artifact_fingerprint": self.artifact_fingerprint,
            "content_sha256": self.content_sha256, "source_url": self.source_url,
            "observed_at": self.observed_at.astimezone(UTC).isoformat(),
            "row_index": self.row_index, "fields": self.fields,
        }

    def to_dict(self) -> dict[str, object]:
        return {**self._body(), "source_row_id": self.source_row_id, "fingerprint": self.fingerprint}


def source_row_evidence(
    artifact: NseUdiffDailySourceArtifact, row_index: int,
) -> NseUdiffSourceRowEvidence:
    """Revalidate archived bytes, then bind one exact ordinal without remapping."""
    artifact.__post_init__()
    parsed = _parse_valid_archive(artifact)
    if type(row_index) is not int or not 0 <= row_index < len(parsed.rows):
        raise ValueError("NSE_UDIFF_SOURCE_ROW_INDEX_INVALID")
    fields = tuple((key, parsed.rows[row_index][key]) for key in UDIFF_COLUMNS)
    body = {
        "contract": CONTRACT_VERSION, "artifact_id": artifact.artifact_id,
        "artifact_fingerprint": artifact.fingerprint,
        "content_sha256": artifact.content_sha256, "source_url": artifact.source_url,
        "observed_at": artifact.observed_at.astimezone(UTC).isoformat(),
        "row_index": row_index, "fields": fields,
    }
    return NseUdiffSourceRowEvidence(
        artifact.artifact_id, artifact.fingerprint, artifact.content_sha256,
        artifact.source_url, artifact.observed_at, row_index, fields, _digest(body),
    )


def classify_source_rows(
    left: NseUdiffSourceRowEvidence, right: NseUdiffSourceRowEvidence,
) -> NseUdiffConflictClass:
    """Symmetric classification. Different artifact values have no implicit precedence."""
    left.__post_init__()
    right.__post_init__()
    a, b = dict(left.fields), dict(right.fields)
    if any(a[key] != b[key] for key in ("TradDt", "BizDt")):
        return NseUdiffConflictClass.UNRESOLVED
    if a["ISIN"] != b["ISIN"] or a["TckrSymb"] != b["TckrSymb"]:
        return NseUdiffConflictClass.HISTORICAL_IDENTITY_DISCONTINUITY
    if a["SctySrs"] != b["SctySrs"]:
        return NseUdiffConflictClass.DISTINCT_SERIES
    if a["SsnId"] != b["SsnId"]:
        return NseUdiffConflictClass.DISTINCT_SESSION
    if a["FinInstrmId"] != b["FinInstrmId"]:
        return NseUdiffConflictClass.DISTINCT_SOURCE_SECURITY_IDENTITY
    if left.fields == right.fields:
        return NseUdiffConflictClass.DUPLICATE_EQUIVALENT
    try:
        av, bv = tuple(Decimal(a[k]) for k in VALUE_FIELDS), tuple(Decimal(b[k]) for k in VALUE_FIELDS)
    except InvalidOperation:
        return NseUdiffConflictClass.UNRESOLVED
    if any(not v.is_finite() for v in (*av, *bv)):
        return NseUdiffConflictClass.UNRESOLVED
    if av != bv:
        return NseUdiffConflictClass.TRUE_SOURCE_VALUE_CONFLICT
    # Metadata differences or numeric formatting alone do not prove complete
    # semantic equivalence. No amendment/revision precedence is inferred.
    return NseUdiffConflictClass.UNRESOLVED
