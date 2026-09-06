"""Recheck preserved collision evidence against exact series-aware observations.

This is the semantic continuation of the existing source-row classifier and
storage repair. It owns no ledger, storage, source priority or revision policy.
An old artifact alone remains unresolved. Only a verified distinct-series pair
whose two archived values are still retained resolves a structural collision.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from hashlib import sha256
import json
from typing import Iterable
from zoneinfo import ZoneInfo

from app.market_data.historical import (
    HistoricalBarConflictArtifact, HistoricalBarNormalizedValues,
    _normalized_bar_fingerprint,
)
from app.market_data.models import CanonicalOHLCVBar, MarketDataQualityValidator
from app.market_data.nse_udiff_conflict_semantics import (
    NseUdiffConflictClass, NseUdiffSourceRowEvidence, VALUE_FIELDS,
    classify_source_rows,
)
from app.market_data.nse_udiff_daily_history import _fingerprint as source_fingerprint
from app.market_data.nse_udiff_source_identity import PROVIDER, source_fields

CONTRACT_VERSION = "nse-udiff-conflict-resolution-v1"
_VALUES = ("open", "high", "low", "close", "volume", "turnover", "trade_count")


class NseUdiffCurrentConflictState(StrEnum):
    RESOLVED_STRUCTURAL_CONFLICT = "RESOLVED_STRUCTURAL_CONFLICT"
    CURRENT_TRUE_SOURCE_CONFLICT = "CURRENT_TRUE_SOURCE_CONFLICT"
    CURRENT_UNRESOLVED_CONFLICT = "CURRENT_UNRESOLVED_CONFLICT"


@dataclass(frozen=True, slots=True)
class NseUdiffConflictReconciliation:
    artifact: HistoricalBarConflictArtifact
    stored_row: NseUdiffSourceRowEvidence
    incoming_row: NseUdiffSourceRowEvidence
    retained_bars: tuple[CanonicalOHLCVBar, ...]
    classification: NseUdiffConflictClass
    state: NseUdiffCurrentConflictState
    fingerprint: str

    def __post_init__(self) -> None:
        classification, state = _classify(
            self.artifact, self.stored_row, self.incoming_row, self.retained_bars,
        )
        if (self.classification is not classification or self.state is not state
                or self.fingerprint != _fingerprint(self._body())):
            raise ValueError("NSE_UDIFF_CONFLICT_RECONCILIATION_INVALID")

    @property
    def known_at(self) -> datetime:
        # Current descriptive evidence availability, never historical known-at.
        return max(self.artifact.detected_at, self.stored_row.observed_at,
                   self.incoming_row.observed_at,
                   *(bar.provenance.received_at for bar in self.retained_bars)).astimezone(UTC)

    def resolves_window(self, bars: Iterable[CanonicalOHLCVBar], as_of: datetime) -> bool:
        self.__post_init__()
        if (as_of.tzinfo is None or as_of.utcoffset() is None
                or self.state is not NseUdiffCurrentConflictState.RESOLVED_STRUCTURAL_CONFLICT
                or self.known_at > as_of):
            return False
        current = tuple(bars)
        # Recheck both sides in this read's actual raw observation bundle. A
        # previous storage repair cannot excuse a missing/changed side today.
        return all(sum(_matches(bar, row, self.artifact) for bar in current) == 1
                   for row in (self.stored_row, self.incoming_row))

    def _body(self) -> dict[str, object]:
        return {
            "contract": CONTRACT_VERSION,
            "historical_conflict_artifact": self.artifact.conflict_fingerprint,
            "detected_at": self.artifact.detected_at.astimezone(UTC).isoformat(),
            "source_rows": [self.stored_row.to_dict(), self.incoming_row.to_dict()],
            "retained_bars": [_bar_lineage(bar) for bar in self.retained_bars],
            "classification": self.classification.value, "state": self.state.value,
        }

    def to_dict(self) -> dict[str, object]:
        self.__post_init__()
        return self._body() | {"fingerprint": self.fingerprint}


def reconcile_udiff_conflict(
    *, artifact: HistoricalBarConflictArtifact, stored_row: NseUdiffSourceRowEvidence,
    incoming_row: NseUdiffSourceRowEvidence, retained_bars: Iterable[CanonicalOHLCVBar],
) -> NseUdiffConflictReconciliation:
    bars = tuple(sorted(retained_bars, key=lambda bar: bar.bar_id))
    classification, state = _classify(artifact, stored_row, incoming_row, bars)
    values = dict(artifact=artifact, stored_row=stored_row, incoming_row=incoming_row,
                  retained_bars=bars, classification=classification, state=state)
    # Build the same complete payload used at construction/serialization.
    body = {
        "contract": CONTRACT_VERSION,
        "historical_conflict_artifact": artifact.conflict_fingerprint,
        "detected_at": artifact.detected_at.astimezone(UTC).isoformat(),
        "source_rows": [stored_row.to_dict(), incoming_row.to_dict()],
        "retained_bars": [_bar_lineage(bar) for bar in bars],
        "classification": classification.value, "state": state.value,
    }
    return NseUdiffConflictReconciliation(**values, fingerprint=_fingerprint(body))


def _classify(
    artifact: HistoricalBarConflictArtifact, stored_row: NseUdiffSourceRowEvidence,
    incoming_row: NseUdiffSourceRowEvidence, bars: tuple[CanonicalOHLCVBar, ...],
) -> tuple[NseUdiffConflictClass, NseUdiffCurrentConflictState]:
    artifact.__post_init__()
    for side, row in (("stored", stored_row), ("incoming", incoming_row)):
        row.__post_init__()
        fields = dict(row.fields)
        lineage = getattr(artifact, side + "_lineage")
        values = getattr(artifact, side + "_values")
        if (artifact.canonical_instrument_id != "NSE:" + fields["ISIN"]
                or artifact.timeframe.value != "1D"
                or values.adjustment_status.value != "RAW"
                or lineage.provider_identity != PROVIDER
                or lineage.provider_version != "v1"
                or lineage.normalizer_version != "nse-udiff-final-bhavcopy-v1"
                or lineage.source_identity != row.source_url
                or lineage.provider_instrument_reference != "NSE:CM:" + fields["FinInstrmId"]
                or (lineage.source_observation_identity is not None
                    and lineage.source_observation_identity != row.source_row_id)
                or tuple(Decimal(str(getattr(values, key))) for key in _VALUES)
                   != tuple(Decimal(fields[key]) for key in VALUE_FIELDS)):
            raise ValueError("NSE_UDIFF_CONFLICT_SOURCE_BINDING_INVALID")
        # Match the existing exchange interval rules through source_fields.
        if artifact.start_time.astimezone(ZoneInfo("Asia/Kolkata")).date().isoformat() != fields["TradDt"]:
            raise ValueError("NSE_UDIFF_CONFLICT_SOURCE_DATE_INVALID")
        for bar in bars:
            if (_matches(bar, row, artifact) and _normalized_bar_fingerprint(bar)
                    != getattr(artifact, side + "_bar_fingerprint")):
                raise ValueError("NSE_UDIFF_CONFLICT_SOURCE_VALUES_FINGERPRINT_MISMATCH")
    if (type(bars) is not tuple or bars != tuple(sorted(bars, key=lambda bar: bar.bar_id))
            or len({bar.bar_id for bar in bars}) != len(bars)):
        raise ValueError("NSE_UDIFF_CONFLICT_RETAINED_BARS_INVALID")
    for bar in bars:
        MarketDataQualityValidator.validate_bar(bar)
        if not any(_matches(bar, row, artifact) for row in (stored_row, incoming_row)):
            raise ValueError("NSE_UDIFF_CONFLICT_RETAINED_SOURCE_MISMATCH")
    classification = classify_source_rows(stored_row, incoming_row)
    state = NseUdiffCurrentConflictState.CURRENT_UNRESOLVED_CONFLICT
    if classification is NseUdiffConflictClass.TRUE_SOURCE_VALUE_CONFLICT:
        state = NseUdiffCurrentConflictState.CURRENT_TRUE_SOURCE_CONFLICT
    elif (classification is NseUdiffConflictClass.DISTINCT_SERIES
          and stored_row.artifact_id == incoming_row.artifact_id
          and stored_row.artifact_fingerprint == incoming_row.artifact_fingerprint
          and stored_row.content_sha256 == incoming_row.content_sha256
          and stored_row.source_row_id != incoming_row.source_row_id
          and len(bars) == 2
          and all(sum(_matches(bar, row, artifact) for bar in bars) == 1
                  for row in (stored_row, incoming_row))):
        state = NseUdiffCurrentConflictState.RESOLVED_STRUCTURAL_CONFLICT
    return classification, state


def _matches(bar: CanonicalOHLCVBar, row: NseUdiffSourceRowEvidence,
             artifact: HistoricalBarConflictArtifact) -> bool:
    try:
        fields = source_fields(bar)
        numbers = HistoricalBarNormalizedValues.from_bar(bar)
        row_fingerprint = source_fingerprint({"artifact": row.content_sha256,
                                              "row_index": row.row_index, "row": row.fields})
        return (
            bar.instrument.instrument_id == artifact.canonical_instrument_id
            and (bar.start_time, bar.end_time) == (artifact.start_time, artifact.end_time)
            and fields == {key: dict(row.fields)[key] for key in fields}
            and bar.source_observation_identity == row.source_row_id
            and bar.provenance.source_reference == row.source_url
            and bar.provenance.schema_version == "v1"
            and bar.provenance.request_reference == f"{row.artifact_id}:row:{row.row_index}:{row_fingerprint}"
            and tuple(Decimal(str(getattr(numbers, key))) for key in _VALUES)
                == tuple(Decimal(dict(row.fields)[key]) for key in VALUE_FIELDS)
        )
    except (ValueError, TypeError, ArithmeticError):
        return False


def _bar_lineage(bar):
    return {"bar_id": bar.bar_id, "source_observation_id": bar.source_observation_identity,
            "values_fingerprint": _normalized_bar_fingerprint(bar),
            "source": bar.provenance.source_reference, "row": bar.provenance.request_reference,
            "received_at": bar.provenance.received_at.astimezone(UTC).isoformat()}


def _fingerprint(value):
    return "sha256:" + sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                        ensure_ascii=True, allow_nan=False).encode()).hexdigest()
