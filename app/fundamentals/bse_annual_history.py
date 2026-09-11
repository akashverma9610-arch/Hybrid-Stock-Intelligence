"""Select missing official annual endpoints; never calculate financial metrics.

The caller supplies the existing canonical comparability, exact BSE mapping,
and official archive aliases. Acquisition/staging/normalization remain owned by
the existing BSE collector. Six endpoints are Rule 16's existing input depth,
not a newly approved investment threshold or a claim of metric completeness.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import re
from urllib.parse import urlparse

from app.universe_analysis.models import ProviderInstrumentMappingRecord, ProviderMappingStatus
from app.fundamentals.bse_official import BseResultMetadata, BseResultMetadataAliases, BseTimestampStatus
from app.fundamentals.diagnostic_comparability import CanonicalFinancialComparability, content_fingerprint
from app.fundamentals.models import FinancialPeriodType as P, FinancialValueBasis as B, StatementScope

POLICY_VERSION = "bse-missing-six-annual-endpoints-v1"


@dataclass(frozen=True, slots=True)
class BseAnnualHistorySelection:
    canonical_instrument_id: str
    as_of: datetime
    scope: StatementScope
    source_fingerprint: str
    mapping_fingerprint: str
    existing_endpoints: tuple[datetime, ...]
    requested_endpoints: tuple[datetime, ...]
    selected: tuple[BseResultMetadata, ...]
    unavailable: tuple[tuple[datetime | None, str], ...]
    policy_version: str = POLICY_VERSION

    @property
    def fingerprint(self) -> str:
        return content_fingerprint(self)


def select_missing_annual_history(
    comparable: CanonicalFinancialComparability,
    mapping: ProviderInstrumentMappingRecord,
    archives: tuple[BseResultMetadataAliases, ...],
) -> BseAnnualHistorySelection:
    """Deterministic same-scope annual source selection at an explicit cutoff.

    No scope fallback, prior-year comparative extraction, fabricated prelisting
    accounts, quarterly aggregation, or silent revision/order tie-breaking.
    Archive dates are candidate endpoints only; the existing importer must
    verify actual XBRL duration, ISIN, code, scope, units and document period.
    """
    comparable.__post_init__()
    cutoff = comparable.as_of.astimezone(UTC)
    existing = tuple(sorted({key[3].astimezone(UTC) for key in comparable.anchors(P.ANNUAL)}))

    def result(requested=(), selected=(), unavailable=()):
        return BseAnnualHistorySelection(
            comparable.canonical_instrument_id, cutoff, comparable.scope,
            comparable.fingerprint, content_fingerprint(mapping), existing,
            requested, selected, unavailable,
        )

    if (mapping.status is not ProviderMappingStatus.ACTIVE or mapping.provider != "BSE_OFFICIAL"
            or mapping.canonical_instrument_id != comparable.canonical_instrument_id
            or not mapping.isin or mapping.canonical_instrument_id != "NSE:" + mapping.isin
            or not mapping.provider_instrument_reference or len(mapping.provider_instrument_reference) != 6
            or not mapping.provider_instrument_reference.isdigit()
            or not re.fullmatch(r"[a-f0-9]{64}", mapping.source_checksum or "")
            or mapping.provider_exchange_segment != "BSE_EQ"
            or mapping.mapping_version != "bse-xbrl-v1"
            or mapping.effective_as_of.tzinfo is None or mapping.effective_as_of > cutoff):
        return result(unavailable=((None, "EXACT_PIT_BSE_MAPPING_REQUIRED"),))
    if comparable.scope not in {StatementScope.CONSOLIDATED, StatementScope.STANDALONE}:
        return result(unavailable=((None, "ANNUAL_SCOPE_UNAVAILABLE"),))
    anchors = comparable.anchors(P.ANNUAL)
    # The approved BSE context importer supports Apr--Mar annual durations.
    # Changed/non-calendar years must not be forced into that representation.
    if any(
        (key[2].month, key[2].day, key[3].month, key[3].day) != (4, 1, 3, 31)
        or key[2].year + 1 != key[3].year or key[0] != key[3].year
        for key in anchors
    ) or len(anchors) != len(existing):
        return result(unavailable=((None, "ANNUAL_ANCHOR_MISSING_OR_NONCOMPARABLE"),))
    archive_ends = tuple(meta.period_end for group in archives for meta in group.aliases
        if meta.security_code == mapping.provider_instrument_reference
        and meta.scope is comparable.scope and meta.period_type is P.ANNUAL
        and meta.value_basis is B.FULL_YEAR and meta.period_end.tzinfo is not None
        and meta.period_end <= cutoff and (meta.period_end.month, meta.period_end.day) == (3, 31)
        and meta.filing_at.tzinfo is not None and meta.filing_at <= cutoff)
    if not existing and not archive_ends:
        return result(unavailable=((None, "ANNUAL_ANCHOR_MISSING_OR_NONCOMPARABLE"),))
    newest = existing[-1] if existing else max(archive_ends).astimezone(UTC)
    window = tuple(newest.replace(year=year) for year in range(newest.year - 5, newest.year + 1))
    requested = tuple(end for end in window if end not in existing)
    selected, unavailable = [], []
    for end in requested:
        candidates = []
        for group in archives:
            for meta in group.aliases:
                url = urlparse(meta.xbrl_url)
                if (meta.security_code == mapping.provider_instrument_reference
                        and meta.period_type is P.ANNUAL and meta.value_basis is B.FULL_YEAR
                        and meta.scope is comparable.scope and meta.period_end == end
                        and meta.filing_at.tzinfo is not None and meta.filing_at <= cutoff
                        and (meta.revised_at is None or meta.revised_at.tzinfo is not None
                             and meta.revised_at <= cutoff)
                        and meta.timestamp_status in {BseTimestampStatus.DOCUMENTED,
                                                       BseTimestampStatus.EXCHANGE_LOCAL_ASSUMPTION}
                        and group.document_url == meta.xbrl_url
                        and url.scheme == "https" and url.hostname == "www.bseindia.com"
                        and url.username is None and url.password is None
                        and url.path.startswith("/XBRLFILES/") and url.path.lower().endswith(".xml")
                        and not url.query and not url.fragment):
                    candidates.append(meta)
        if not candidates:
            unavailable.append((end, "OFFICIAL_SAME_SCOPE_ANNUAL_SOURCE_UNAVAILABLE"))
            continue
        latest = max(meta.revised_at or meta.filing_at for meta in candidates)
        versions = {content_fingerprint(meta): meta for meta in candidates
                    if (meta.revised_at or meta.filing_at) == latest}
        if len(versions) != 1:
            unavailable.append((end, "OFFICIAL_ANNUAL_REVISION_AMBIGUOUS"))
            continue
        selected.append(next(iter(versions.values())))
    return result(requested, tuple(selected), tuple(unavailable))
