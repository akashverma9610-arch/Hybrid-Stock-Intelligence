"""Pure, fail-closed reconciliation of NSE Indices report-name aliases.

This is an evidence comparison only.  It does not fetch a source, mutate an
index mapping, save an observation, or make an OHLC series operational.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from hashlib import sha256
from typing import Iterable

from app.market_data.official_nse_index_ohlc_feasibility import OfficialIndexReturnFamily
from app.taxonomy.nse_sector_indices import NseSectorIndexMapping, SectorIndexMappingStatus


RECONCILIATION_VERSION = "official-nse-index-ohlc-source-name-reconciliation-v1"
SOURCE_QUERY_ALIAS_VERSION = "official-nse-index-source-query-alias-v1"


class OfficialIndexIdentityReconciliationStatus(StrEnum):
    IDENTITY_RECONCILED = "IDENTITY_RECONCILED"
    SOURCE_PARAMETER_ALIAS_CONFIRMED = "SOURCE_PARAMETER_ALIAS_CONFIRMED"
    IDENTITY_NOT_RECONCILED = "IDENTITY_NOT_RECONCILED"
    SOURCE_PARAMETER_ALIAS_REJECTED = "SOURCE_PARAMETER_ALIAS_REJECTED"
    IDENTITY_AMBIGUOUS = "IDENTITY_AMBIGUOUS"


class OfficialIndexSourceQueryResolutionStatus(StrEnum):
    EXACT_CANONICAL_SOURCE_QUERY = "EXACT_CANONICAL_SOURCE_QUERY"
    SOURCE_QUERY_ALIAS_PROVEN = "SOURCE_QUERY_ALIAS_PROVEN"


@dataclass(frozen=True, slots=True)
class OfficialNseIndexSourceNameTarget:
    """Exact, first-party product identities allowed in this bounded audit."""

    canonical_index_id: str
    canonical_mapping_name: str
    catalogue_name: str
    dedicated_page_name: str
    factsheet_name: str
    historical_parameter: str
    distinct_product_names: tuple[str, ...]
    affected_security_count: int

    def __post_init__(self) -> None:
        names = (
            self.canonical_index_id, self.canonical_mapping_name,
            self.catalogue_name, self.dedicated_page_name,
            self.factsheet_name, self.historical_parameter,
        )
        distinct = tuple(sorted(set(self.distinct_product_names), key=str.casefold))
        if (
            not all(isinstance(value, str) and value.strip() for value in names)
            or not self.canonical_index_id.startswith("NSE_SECTOR_INDEX:")
            or distinct != self.distinct_product_names
            or any(value.casefold() == self.historical_parameter.casefold() for value in distinct)
            or self.affected_security_count <= 0
        ):
            raise ValueError("OFFICIAL_INDEX_RECONCILIATION_TARGET_INVALID")


@dataclass(frozen=True, slots=True)
class OfficialIndexSourceQueryResolution:
    """One exact, first-party source-query choice for a stable HSI index ID.

    It authorizes an initial current-descriptive canonicalization only.  It
    does not replace the stricter close-lineage comparison retained below for
    later source-to-source reconciliation.
    """

    canonical_index_id: str
    canonical_mapping_name: str
    source_query_name: str
    return_family: OfficialIndexReturnFamily
    status: OfficialIndexSourceQueryResolutionStatus
    evidence_references: tuple[str, ...]
    fingerprint: str

    def __post_init__(self) -> None:
        references = tuple(sorted(set(self.evidence_references)))
        is_alias = self.source_query_name != self.canonical_mapping_name
        values = _source_query_resolution_values(self, include_fingerprint=False)
        if (
            not self.canonical_index_id.startswith("NSE_SECTOR_INDEX:")
            or not all(isinstance(value, str) and value.strip() for value in (
                self.canonical_mapping_name, self.source_query_name,
            ))
            or not isinstance(self.return_family, OfficialIndexReturnFamily)
            or self.return_family is not OfficialIndexReturnFamily.PRICE_RETURN_INDEX
            or not isinstance(self.status, OfficialIndexSourceQueryResolutionStatus)
            or self.evidence_references != references
            or not all(isinstance(value, str) and value.strip() for value in references)
            or (is_alias and (
                self.status is not OfficialIndexSourceQueryResolutionStatus.SOURCE_QUERY_ALIAS_PROVEN
                or not references
            ))
            or (not is_alias and (
                self.status is not OfficialIndexSourceQueryResolutionStatus.EXACT_CANONICAL_SOURCE_QUERY
                or references
            ))
            or len(self.fingerprint) != 64
            or any(value not in "0123456789abcdef" for value in self.fingerprint)
            or self.fingerprint != _fingerprint(values)
        ):
            raise ValueError("OFFICIAL_INDEX_SOURCE_QUERY_RESOLUTION_INVALID")


CONSUMER_DURABLES_TARGET = OfficialNseIndexSourceNameTarget(
    canonical_index_id="NSE_SECTOR_INDEX:CONSUMER_DURABLES",
    canonical_mapping_name="Nifty Consumer Durables Index",
    catalogue_name="Nifty Consumer Durables",
    dedicated_page_name="Nifty Consumer Durables Index",
    factsheet_name="Nifty Consumer Durables Index",
    historical_parameter="Nifty Consumer Durables",
    distinct_product_names=(),
    affected_security_count=41,
)

HEALTHCARE_TARGET = OfficialNseIndexSourceNameTarget(
    canonical_index_id="NSE_SECTOR_INDEX:HEALTHCARE",
    canonical_mapping_name="Nifty Healthcare Index",
    catalogue_name="Nifty Healthcare",
    dedicated_page_name="Nifty Healthcare Index",
    factsheet_name="Nifty Healthcare Index",
    historical_parameter="Nifty Healthcare",
    distinct_product_names=("Nifty MidSmall Healthcare", "Nifty500 Healthcare"),
    affected_security_count=70,
)


_ALIAS_TARGETS = {
    CONSUMER_DURABLES_TARGET.canonical_index_id: CONSUMER_DURABLES_TARGET,
    HEALTHCARE_TARGET.canonical_index_id: HEALTHCARE_TARGET,
}
_ALIAS_EVIDENCE_REFERENCES = (
    "NSE_INDICES_DEDICATED_INDEX_PAGE",
    "NSE_INDICES_EQUITY_INDEX_METHODOLOGY",
    "NSE_INDICES_FACTSHEET",
    "NSE_INDICES_HISTORICAL_DATA_REPORT",
    "NSE_INDICES_SECTORAL_CATALOGUE",
)


def resolve_official_nse_index_source_query(
    *, mapping: NseSectorIndexMapping, canonical_index_id: str,
) -> OfficialIndexSourceQueryResolution:
    """Resolve an exact first-party report parameter without changing index ID.

    The two aliases below are explicit product-identity facts, not a string
    normalizer.  A mapping that does not exactly match the retained official
    relation fails closed instead of receiving a similar-looking parameter.
    """
    if (
        not isinstance(mapping, NseSectorIndexMapping)
        or mapping.status is not SectorIndexMappingStatus.EXACT_OFFICIAL
        or not mapping.official_index_name
        or canonical_index_id != _canonical_index_id(mapping.canonical_sector)
    ):
        raise ValueError("OFFICIAL_INDEX_SOURCE_QUERY_MAPPING_INVALID")
    target = _ALIAS_TARGETS.get(canonical_index_id)
    if target is None:
        values = {
            "canonical_index_id": canonical_index_id,
            "canonical_mapping_name": mapping.official_index_name,
            "source_query_name": mapping.official_index_name,
            "return_family": OfficialIndexReturnFamily.PRICE_RETURN_INDEX,
            "status": OfficialIndexSourceQueryResolutionStatus.EXACT_CANONICAL_SOURCE_QUERY,
            "evidence_references": (),
        }
        return OfficialIndexSourceQueryResolution(
            **values,
            fingerprint=_fingerprint(_source_query_resolution_values_from(values)),
        )
    if mapping.official_index_name != target.canonical_mapping_name:
        raise ValueError("OFFICIAL_INDEX_SOURCE_QUERY_ALIAS_MAPPING_NAME_MISMATCH")
    evidence = OfficialNseIndexIdentityEvidence(
        canonical_index_id=target.canonical_index_id,
        catalogue_name=target.catalogue_name,
        dedicated_page_name=target.dedicated_page_name,
        factsheet_name=target.factsheet_name,
        historical_parameter=target.historical_parameter,
        historical_observed_name=target.historical_parameter,
        return_family=OfficialIndexReturnFamily.PRICE_RETURN_INDEX,
        evidence_references=_ALIAS_EVIDENCE_REFERENCES,
    )
    if _identity_reason_codes(target, evidence):  # Defensive against a future static-data edit.
        raise ValueError("OFFICIAL_INDEX_SOURCE_QUERY_ALIAS_EVIDENCE_INVALID")
    values = {
        "canonical_index_id": canonical_index_id,
        "canonical_mapping_name": mapping.official_index_name,
        "source_query_name": target.historical_parameter,
        "return_family": OfficialIndexReturnFamily.PRICE_RETURN_INDEX,
        "status": OfficialIndexSourceQueryResolutionStatus.SOURCE_QUERY_ALIAS_PROVEN,
        "evidence_references": _ALIAS_EVIDENCE_REFERENCES,
    }
    return OfficialIndexSourceQueryResolution(
        **values,
        fingerprint=_fingerprint(_source_query_resolution_values_from(values)),
    )


@dataclass(frozen=True, slots=True)
class OfficialNseIndexIdentityEvidence:
    """The selected first-party identity labels, supplied by an audit caller."""

    canonical_index_id: str
    catalogue_name: str
    dedicated_page_name: str
    factsheet_name: str
    historical_parameter: str
    historical_observed_name: str
    return_family: OfficialIndexReturnFamily
    evidence_references: tuple[str, ...]

    def __post_init__(self) -> None:
        references = tuple(sorted(set(self.evidence_references)))
        values = (
            self.canonical_index_id, self.catalogue_name, self.dedicated_page_name,
            self.factsheet_name, self.historical_parameter, self.historical_observed_name,
        )
        if (
            not all(isinstance(value, str) and value.strip() for value in values)
            or not self.canonical_index_id.startswith("NSE_SECTOR_INDEX:")
            or self.historical_observed_name.casefold() != self.historical_parameter.casefold()
            or not isinstance(self.return_family, OfficialIndexReturnFamily)
            or not references
            or not all(isinstance(value, str) and value.strip() for value in references)
            or references != self.evidence_references
        ):
            raise ValueError("OFFICIAL_INDEX_RECONCILIATION_EVIDENCE_INVALID")


@dataclass(frozen=True, slots=True)
class OfficialIndexCloseLineagePoint:
    session: date
    close: Decimal

    def __post_init__(self) -> None:
        if (
            not isinstance(self.session, date)
            or isinstance(self.session, datetime)
            or not isinstance(self.close, Decimal)
            or not self.close.is_finite()
            or self.close <= 0
        ):
            raise ValueError("OFFICIAL_INDEX_RECONCILIATION_CLOSE_POINT_INVALID")


@dataclass(frozen=True, slots=True)
class OfficialNseIndexSourceNameReconciliationResult:
    canonical_index_id: str
    status: OfficialIndexIdentityReconciliationStatus
    reason_codes: tuple[str, ...]
    canonical_close_session_count: int
    alternate_close_session_count: int
    overlapping_session_count: int
    canonical_missing_from_alternate_count: int
    alternate_missing_from_canonical_count: int
    exact_close_match_count: int
    conflict_count: int
    overlap_start: date | None
    overlap_end: date | None
    maximum_absolute_difference: Decimal | None
    maximum_relative_difference: Decimal | None
    reconciliation_fingerprint: str

    def __post_init__(self) -> None:
        reasons = tuple(sorted(set(self.reason_codes)))
        counts = (
            self.canonical_close_session_count, self.alternate_close_session_count,
            self.overlapping_session_count, self.canonical_missing_from_alternate_count,
            self.alternate_missing_from_canonical_count, self.exact_close_match_count,
            self.conflict_count,
        )
        missing_lineage = "CANONICAL_CLOSE_LINEAGE_ABSENT" in reasons or "ALTERNATE_CLOSE_LINEAGE_ABSENT" in reasons
        if (
            not self.canonical_index_id.startswith("NSE_SECTOR_INDEX:")
            or not isinstance(self.status, OfficialIndexIdentityReconciliationStatus)
            or not reasons
            or reasons != self.reason_codes
            or any(value < 0 for value in counts)
            or self.overlapping_session_count != self.exact_close_match_count + self.conflict_count
            or (self.overlapping_session_count == 0 and (self.overlap_start is not None or self.overlap_end is not None))
            or (self.overlapping_session_count > 0 and (self.overlap_start is None or self.overlap_end is None or self.overlap_start > self.overlap_end))
            or (self.maximum_absolute_difference is None) != (self.maximum_relative_difference is None)
            or (self.maximum_absolute_difference is not None and (self.maximum_absolute_difference < 0 or self.maximum_relative_difference is None or self.maximum_relative_difference < 0))
            or len(self.reconciliation_fingerprint) != 64
            or any(value not in "0123456789abcdef" for value in self.reconciliation_fingerprint)
            or (
                self.status in {
                    OfficialIndexIdentityReconciliationStatus.IDENTITY_RECONCILED,
                    OfficialIndexIdentityReconciliationStatus.SOURCE_PARAMETER_ALIAS_CONFIRMED,
                }
                and (missing_lineage or self.conflict_count or self.canonical_missing_from_alternate_count or self.alternate_missing_from_canonical_count)
            )
        ):
            raise ValueError("OFFICIAL_INDEX_RECONCILIATION_RESULT_INVALID")


def reconcile_official_nse_index_source_name(
    *,
    target: OfficialNseIndexSourceNameTarget,
    evidence: OfficialNseIndexIdentityEvidence,
    canonical_close_points: Iterable[OfficialIndexCloseLineagePoint],
    alternate_close_points: Iterable[OfficialIndexCloseLineagePoint],
) -> OfficialNseIndexSourceNameReconciliationResult:
    """Reconcile only exact first-party identities and exact decimal closes."""
    target.__post_init__()
    evidence.__post_init__()
    canonical, canonical_duplicate = _points(canonical_close_points)
    alternate, alternate_duplicate = _points(alternate_close_points)
    static_reasons = _identity_reason_codes(target, evidence)
    if static_reasons:
        return _result(target, evidence, OfficialIndexIdentityReconciliationStatus.IDENTITY_NOT_RECONCILED, static_reasons, canonical, alternate)
    if canonical_duplicate or alternate_duplicate:
        return _result(target, evidence, OfficialIndexIdentityReconciliationStatus.IDENTITY_AMBIGUOUS, ("CLOSE_LINEAGE_DUPLICATE_SESSION",), canonical, alternate)
    if not canonical:
        return _result(target, evidence, OfficialIndexIdentityReconciliationStatus.IDENTITY_AMBIGUOUS, ("CANONICAL_CLOSE_LINEAGE_ABSENT",), canonical, alternate)
    if not alternate:
        return _result(target, evidence, OfficialIndexIdentityReconciliationStatus.IDENTITY_AMBIGUOUS, ("ALTERNATE_CLOSE_LINEAGE_ABSENT",), canonical, alternate)
    canonical_sessions, alternate_sessions = set(canonical), set(alternate)
    if canonical_sessions != alternate_sessions:
        return _result(target, evidence, OfficialIndexIdentityReconciliationStatus.IDENTITY_AMBIGUOUS, ("CLOSE_LINEAGE_INSUFFICIENT_OVERLAP",), canonical, alternate)
    differences = {session: abs(canonical[session] - alternate[session]) for session in canonical_sessions}
    if any(value for value in differences.values()):
        return _result(
            target, evidence,
            _alias_or_identity_status(target, confirmed=False),
            ("CLOSE_LINEAGE_VALUE_MISMATCH",), canonical, alternate,
        )
    return _result(
        target, evidence, _alias_or_identity_status(target, confirmed=True),
        ("EXACT_FIRST_PARTY_IDENTITY_AND_CLOSE_LINEAGE_VERIFIED",), canonical, alternate,
    )


def serialize_official_nse_index_source_name_reconciliation(
    value: OfficialNseIndexSourceNameReconciliationResult,
) -> str:
    value.__post_init__()
    return json.dumps({
        "alternate_close_session_count": value.alternate_close_session_count,
        "alternate_missing_from_canonical_count": value.alternate_missing_from_canonical_count,
        "canonical_close_session_count": value.canonical_close_session_count,
        "canonical_index_id": value.canonical_index_id,
        "canonical_missing_from_alternate_count": value.canonical_missing_from_alternate_count,
        "conflict_count": value.conflict_count,
        "exact_close_match_count": value.exact_close_match_count,
        "reconciliation_fingerprint": value.reconciliation_fingerprint,
        "maximum_absolute_difference": _decimal_text(value.maximum_absolute_difference),
        "maximum_relative_difference": _decimal_text(value.maximum_relative_difference),
        "overlap_end": value.overlap_end.isoformat() if value.overlap_end else None,
        "overlap_start": value.overlap_start.isoformat() if value.overlap_start else None,
        "overlapping_session_count": value.overlapping_session_count,
        "reason_codes": value.reason_codes,
        "reconciliation_version": RECONCILIATION_VERSION,
        "status": value.status.value,
    }, sort_keys=True, separators=(",", ":"))


def _identity_reason_codes(
    target: OfficialNseIndexSourceNameTarget,
    evidence: OfficialNseIndexIdentityEvidence,
) -> tuple[str, ...]:
    if evidence.canonical_index_id != target.canonical_index_id:
        return ("CANONICAL_INDEX_ID_MISMATCH",)
    if evidence.return_family is not OfficialIndexReturnFamily.PRICE_RETURN_INDEX:
        return ("PRI_TRI_MISMATCH",)
    observed = (
        evidence.catalogue_name, evidence.dedicated_page_name,
        evidence.factsheet_name, evidence.historical_parameter,
        evidence.historical_observed_name,
    )
    if any(value.casefold() in {item.casefold() for item in target.distinct_product_names} for value in observed):
        return ("DISTINCT_OFFICIAL_INDEX_PRODUCT",)
    expected = (
        target.catalogue_name, target.dedicated_page_name, target.factsheet_name,
        target.historical_parameter, target.historical_parameter,
    )
    if any(actual.casefold() != expected_value.casefold() for actual, expected_value in zip(observed, expected, strict=True)):
        return ("OFFICIAL_IDENTITY_EVIDENCE_INCOMPLETE",)
    return ()


def _points(values: Iterable[OfficialIndexCloseLineagePoint]) -> tuple[dict[date, Decimal], bool]:
    points: dict[date, Decimal] = {}
    duplicate = False
    for value in values:
        if not isinstance(value, OfficialIndexCloseLineagePoint):
            raise ValueError("OFFICIAL_INDEX_RECONCILIATION_CLOSE_POINT_INVALID")
        value.__post_init__()
        if value.session in points:
            duplicate = True
        else:
            points[value.session] = value.close.normalize()
    return points, duplicate


def _result(
    target: OfficialNseIndexSourceNameTarget,
    evidence: OfficialNseIndexIdentityEvidence,
    status: OfficialIndexIdentityReconciliationStatus,
    reasons: tuple[str, ...],
    canonical: dict[date, Decimal],
    alternate: dict[date, Decimal],
) -> OfficialNseIndexSourceNameReconciliationResult:
    overlap = tuple(sorted(set(canonical) & set(alternate)))
    differences = tuple(abs(canonical[session] - alternate[session]) for session in overlap)
    max_abs = max(differences, default=None)
    max_relative = max((difference / canonical[session] for session, difference in zip(overlap, differences, strict=True)), default=None)
    matches = sum(canonical[session] == alternate[session] for session in overlap)
    conflicts = len(overlap) - matches
    fingerprint = _fingerprint({
        "alternate_close_lineage": _point_values(alternate),
        "canonical_close_lineage": _point_values(canonical),
        "evidence": _evidence_values(evidence),
        "target": _target_values(target),
        "version": RECONCILIATION_VERSION,
    })
    return OfficialNseIndexSourceNameReconciliationResult(
        target.canonical_index_id, status, tuple(sorted(set(reasons))), len(canonical), len(alternate),
        len(overlap), len(set(canonical) - set(alternate)), len(set(alternate) - set(canonical)),
        matches, conflicts, overlap[0] if overlap else None, overlap[-1] if overlap else None,
        max_abs, max_relative, fingerprint,
    )


def _alias_or_identity_status(
    target: OfficialNseIndexSourceNameTarget, *, confirmed: bool,
) -> OfficialIndexIdentityReconciliationStatus:
    is_alias = target.canonical_mapping_name.casefold() != target.historical_parameter.casefold()
    if is_alias:
        return (
            OfficialIndexIdentityReconciliationStatus.SOURCE_PARAMETER_ALIAS_CONFIRMED
            if confirmed
            else OfficialIndexIdentityReconciliationStatus.SOURCE_PARAMETER_ALIAS_REJECTED
        )
    return (
        OfficialIndexIdentityReconciliationStatus.IDENTITY_RECONCILED
        if confirmed
        else OfficialIndexIdentityReconciliationStatus.IDENTITY_NOT_RECONCILED
    )


def _point_values(values: dict[date, Decimal]) -> tuple[tuple[str, str], ...]:
    return tuple((session.isoformat(), _decimal_text(close)) for session, close in sorted(values.items()))


def _target_values(value: OfficialNseIndexSourceNameTarget) -> dict[str, object]:
    return {
        "affected_security_count": value.affected_security_count,
        "canonical_index_id": value.canonical_index_id,
        "canonical_mapping_name": value.canonical_mapping_name,
        "catalogue_name": value.catalogue_name,
        "dedicated_page_name": value.dedicated_page_name,
        "distinct_product_names": value.distinct_product_names,
        "factsheet_name": value.factsheet_name,
        "historical_parameter": value.historical_parameter,
    }


def _source_query_resolution_values(
    value: OfficialIndexSourceQueryResolution, *, include_fingerprint: bool,
) -> dict[str, object]:
    values = _source_query_resolution_values_from({
        "canonical_index_id": value.canonical_index_id,
        "canonical_mapping_name": value.canonical_mapping_name,
        "source_query_name": value.source_query_name,
        "return_family": value.return_family,
        "status": value.status,
        "evidence_references": value.evidence_references,
    })
    return values | ({"fingerprint": value.fingerprint} if include_fingerprint else {})


def _source_query_resolution_values_from(values: dict[str, object]) -> dict[str, object]:
    return {
        "canonical_index_id": values["canonical_index_id"],
        "canonical_mapping_name": values["canonical_mapping_name"],
        "source_query_name": values["source_query_name"],
        "return_family": values["return_family"].value,
        "status": values["status"].value,
        "evidence_references": values["evidence_references"],
        "version": SOURCE_QUERY_ALIAS_VERSION,
    }


def _canonical_index_id(sector: str) -> str:
    token = "".join(character if character.isalnum() else "_" for character in sector.upper()).strip("_")
    if not token:
        raise ValueError("OFFICIAL_INDEX_SOURCE_QUERY_CANONICAL_SECTOR_REQUIRED")
    while "__" in token:
        token = token.replace("__", "_")
    return "NSE_SECTOR_INDEX:" + token


def _evidence_values(value: OfficialNseIndexIdentityEvidence) -> dict[str, object]:
    return {
        "canonical_index_id": value.canonical_index_id,
        "catalogue_name": value.catalogue_name,
        "dedicated_page_name": value.dedicated_page_name,
        "evidence_references": value.evidence_references,
        "factsheet_name": value.factsheet_name,
        "historical_observed_name": value.historical_observed_name,
        "historical_parameter": value.historical_parameter,
        "return_family": value.return_family.value,
    }


def _decimal_text(value: Decimal | None) -> str | None:
    return None if value is None else format(value.normalize(), "f")


def _fingerprint(values: object) -> str:
    return sha256(json.dumps(values, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


__all__ = (
    "CONSUMER_DURABLES_TARGET", "HEALTHCARE_TARGET", "OfficialIndexCloseLineagePoint",
    "OfficialIndexIdentityReconciliationStatus", "OfficialIndexSourceQueryResolution",
    "OfficialIndexSourceQueryResolutionStatus", "OfficialNseIndexIdentityEvidence",
    "OfficialNseIndexSourceNameReconciliationResult", "OfficialNseIndexSourceNameTarget",
    "RECONCILIATION_VERSION", "SOURCE_QUERY_ALIAS_VERSION",
    "reconcile_official_nse_index_source_name", "resolve_official_nse_index_source_query",
    "serialize_official_nse_index_source_name_reconciliation",
)
