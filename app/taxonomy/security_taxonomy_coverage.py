"""Pure current-descriptive coverage audit for official NSE Indices taxonomy.

This contract audits one supplied official-source snapshot against one supplied
canonical security population.  It neither obtains source material nor writes
taxonomy evidence.  ``InstrumentTaxonomyClassification`` and
``NseIndicesTaxonomyImporter`` remain the only canonical persistence and
promotion paths.

In particular, an index constituent row is evidence only when its exact ISIN
and symbol resolve to a canonical security.  Constituent membership never
becomes a sector classification by itself.
"""
from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from hashlib import sha256
from typing import Iterable

from app.taxonomy.models import InstrumentTaxonomyClassification
from app.taxonomy.nse_indices import (
    NSE_INDICES_OFFICIAL,
    NseIndicesConstituent,
    NseIndustryHierarchyEntry,
    NseTaxonomyResolution,
    _canonical_indexes,
    _choose_current_rows,
    _constituent_label_level,
    _resolve_instrument,
    resolve_nse_indices_label,
)
from app.universe_analysis.models import NseEquityInstrument


CONTRACT_ID = "canonical-security-taxonomy-coverage-source-and-identity"
CONTRACT_VERSION = "v1"
_ID = re.compile(r"[A-Za-z0-9._:-]+\Z")
_FP = re.compile(r"sha256:[0-9a-f]{64}\Z")
_SHA = re.compile(r"[0-9a-f]{64}\Z")


class CurrentTaxonomyApplicability(StrEnum):
    CURRENT_DESCRIPTIVE = "CURRENT_DESCRIPTIVE"


class StrictHistoricalPitTaxonomyState(StrEnum):
    NOT_READY = "NOT_READY"


class SecurityTaxonomyCoverageState(StrEnum):
    TAXONOMY_READY = "TAXONOMY_READY"
    SOURCE_UNIVERSE_LIMITATION = "SOURCE_UNIVERSE_LIMITATION"
    IDENTITY_UNRESOLVED = "IDENTITY_UNRESOLVED"
    IDENTITY_AMBIGUOUS = "IDENTITY_AMBIGUOUS"
    UNSUPPORTED_SECURITY_SERIES = "UNSUPPORTED_SECURITY_SERIES"
    TAXONOMY_EVIDENCE_CONFLICTED = "TAXONOMY_EVIDENCE_CONFLICTED"
    OTHER_EXACT_REASON = "OTHER_EXACT_REASON"


class SecurityTaxonomyCoverageReason(StrEnum):
    EXACT_CURRENT_CLASSIFICATION = "EXACT_CURRENT_CLASSIFICATION"
    TAXONOMY_PROMOTION_AVAILABLE = "TAXONOMY_PROMOTION_AVAILABLE"
    SOURCE_UNIVERSE_LIMITATION = "SOURCE_UNIVERSE_LIMITATION"
    ISIN_SYMBOL_CONFLICT = "ISIN_SYMBOL_CONFLICT"
    AMBIGUOUS_OFFICIAL_IDENTITY = "AMBIGUOUS_OFFICIAL_IDENTITY"
    OFFICIAL_SOURCE_TAXONOMY_CONFLICT = "OFFICIAL_SOURCE_TAXONOMY_CONFLICT"
    NSE_INDICES_HIERARCHY_LABEL_UNRESOLVED = "NSE_INDICES_HIERARCHY_LABEL_UNRESOLVED"
    EXISTING_TAXONOMY_CONFLICT = "EXISTING_TAXONOMY_CONFLICT"
    CANONICAL_IDENTITY_AFTER_AUDIT_AS_OF = "CANONICAL_IDENTITY_AFTER_AUDIT_AS_OF"
    UNSUPPORTED_SECURITY_SERIES = "UNSUPPORTED_SECURITY_SERIES"


class ExistingTaxonomyRegressionState(StrEnum):
    NOT_PREVIOUSLY_CLASSIFIED = "NOT_PREVIOUSLY_CLASSIFIED"
    EXACT_SAME = "EXACT_SAME"
    MISSING_IN_NEW_SOURCE = "MISSING_IN_NEW_SOURCE"
    IDENTITY_CHANGED = "IDENTITY_CHANGED"
    CONFLICT = "CONFLICT"


class SecurityTaxonomyCoverageError(ValueError):
    """Stable fail-closed error for malformed taxonomy-audit evidence."""


@dataclass(frozen=True, slots=True)
class SecurityTaxonomyCoverageInput:
    """Existing selected taxonomy and explicit scope for one security."""

    instrument: NseEquityInstrument
    existing_classification: InstrumentTaxonomyClassification | None
    in_current_technical_scope: bool

    def __post_init__(self) -> None:
        if (
            not isinstance(self.instrument, NseEquityInstrument)
            or not _aware(self.instrument.data_as_of)
            or not isinstance(self.in_current_technical_scope, bool)
            or (
                self.existing_classification is not None
                and not isinstance(self.existing_classification, InstrumentTaxonomyClassification)
            )
        ):
            raise SecurityTaxonomyCoverageError("SECURITY_TAXONOMY_COVERAGE_INPUT_INVALID")


@dataclass(frozen=True, slots=True)
class SecurityTaxonomyCoverageRecord:
    """One non-persisted, deterministic security-level coverage conclusion."""

    canonical_instrument_id: str
    symbol: str
    isin: str | None
    in_current_technical_scope: bool
    source_symbol: str | None
    source_series: str | None
    source_isin: str | None
    source_name: str | None
    source_sha256: str | None
    source_line_number: int | None
    raw_classification_label: str | None
    macro_sector: str | None
    sector: str | None
    industry: str | None
    basic_industry: str | None
    existing_classification_id: str | None
    coverage_state: SecurityTaxonomyCoverageState
    reason_code: SecurityTaxonomyCoverageReason
    regression_state: ExistingTaxonomyRegressionState
    applicability: CurrentTaxonomyApplicability
    strict_historical_pit_state: StrictHistoricalPitTaxonomyState
    fingerprint: str

    def __post_init__(self) -> None:
        values = _record_values(self)
        source_present = self.source_name is not None
        taxonomy_present = self.sector is not None
        exact_current = self.reason_code is SecurityTaxonomyCoverageReason.EXACT_CURRENT_CLASSIFICATION
        promotion = self.reason_code is SecurityTaxonomyCoverageReason.TAXONOMY_PROMOTION_AVAILABLE
        if (
            not _ID.fullmatch(self.canonical_instrument_id)
            or not _nonempty(self.symbol)
            or (self.isin is not None and not _nonempty(self.isin))
            or not isinstance(self.in_current_technical_scope, bool)
            or not isinstance(self.coverage_state, SecurityTaxonomyCoverageState)
            or not isinstance(self.reason_code, SecurityTaxonomyCoverageReason)
            or not isinstance(self.regression_state, ExistingTaxonomyRegressionState)
            or self.applicability is not CurrentTaxonomyApplicability.CURRENT_DESCRIPTIVE
            or self.strict_historical_pit_state is not StrictHistoricalPitTaxonomyState.NOT_READY
            or not _FP.fullmatch(self.fingerprint)
            or self.fingerprint != _fingerprint(values)
            or source_present != all(value is not None for value in (
                self.source_symbol, self.source_series, self.source_isin, self.source_sha256,
                self.source_line_number, self.raw_classification_label,
            ))
            or (source_present and (
                self.source_name not in {"NIFTY_500_CONSTITUENTS", "NIFTY_TOTAL_MARKET_CONSTITUENTS"}
                or not _nonempty(self.source_symbol)
                or not _nonempty(self.source_series)
                or not _nonempty(self.source_isin)
                or not _SHA.fullmatch(self.source_sha256 or "")
            ))
            or (self.source_line_number is not None and self.source_line_number < 2)
            or (taxonomy_present != all(value is not None for value in (self.macro_sector, self.sector)))
            or (self.industry is not None or self.basic_industry is not None)
            or (self.coverage_state is SecurityTaxonomyCoverageState.TAXONOMY_READY and not taxonomy_present)
            or (exact_current and self.regression_state is not ExistingTaxonomyRegressionState.EXACT_SAME)
            or (promotion and self.regression_state is not ExistingTaxonomyRegressionState.NOT_PREVIOUSLY_CLASSIFIED)
            or ((exact_current or promotion) and self.coverage_state is not SecurityTaxonomyCoverageState.TAXONOMY_READY)
            or (self.coverage_state is SecurityTaxonomyCoverageState.SOURCE_UNIVERSE_LIMITATION and source_present)
            or not _state_reason_valid(self.coverage_state, self.reason_code)
            or (
                self.coverage_state is SecurityTaxonomyCoverageState.OTHER_EXACT_REASON
                and self.reason_code
                not in {
                    SecurityTaxonomyCoverageReason.NSE_INDICES_HIERARCHY_LABEL_UNRESOLVED,
                    SecurityTaxonomyCoverageReason.CANONICAL_IDENTITY_AFTER_AUDIT_AS_OF,
                }
            )
            or (
                self.coverage_state is SecurityTaxonomyCoverageState.IDENTITY_UNRESOLVED
                and self.reason_code is not SecurityTaxonomyCoverageReason.ISIN_SYMBOL_CONFLICT
            )
            or (
                self.coverage_state is SecurityTaxonomyCoverageState.IDENTITY_AMBIGUOUS
                and self.reason_code is not SecurityTaxonomyCoverageReason.AMBIGUOUS_OFFICIAL_IDENTITY
            )
            or (
                self.coverage_state is SecurityTaxonomyCoverageState.TAXONOMY_EVIDENCE_CONFLICTED
                and self.reason_code
                not in {
                    SecurityTaxonomyCoverageReason.OFFICIAL_SOURCE_TAXONOMY_CONFLICT,
                    SecurityTaxonomyCoverageReason.EXISTING_TAXONOMY_CONFLICT,
                }
            )
        ):
            raise SecurityTaxonomyCoverageError("SECURITY_TAXONOMY_COVERAGE_RECORD_INVALID")


@dataclass(frozen=True, slots=True)
class SecurityTaxonomyCoverageAudit:
    """The whole-universe audit; it is intentionally not a taxonomy receipt."""

    audit_as_of: datetime
    source_family: str
    source_label_level: str
    source_row_count: int
    records: tuple[SecurityTaxonomyCoverageRecord, ...]
    unmatched_source_records: tuple[NseIndicesConstituent, ...]
    applicability: CurrentTaxonomyApplicability
    strict_historical_pit_state: StrictHistoricalPitTaxonomyState
    fingerprint: str

    def __post_init__(self) -> None:
        ordered = tuple(sorted(self.records, key=lambda value: value.canonical_instrument_id))
        unmatched = tuple(sorted(self.unmatched_source_records, key=_source_sort_key))
        values = _audit_values(
            self.audit_as_of, self.source_family, self.source_label_level,
            self.source_row_count, ordered, unmatched,
        )
        if (
            not _aware(self.audit_as_of)
            or self.source_family != NSE_INDICES_OFFICIAL
            or self.source_label_level not in {"MACRO_ECONOMIC_SECTOR", "SECTOR", "INDUSTRY", "BASIC_INDUSTRY"}
            or self.source_row_count < 0
            or self.records != ordered
            or self.unmatched_source_records != unmatched
            or len({value.canonical_instrument_id for value in self.records}) != len(self.records)
            or self.applicability is not CurrentTaxonomyApplicability.CURRENT_DESCRIPTIVE
            or self.strict_historical_pit_state is not StrictHistoricalPitTaxonomyState.NOT_READY
            or not _FP.fullmatch(self.fingerprint)
            or self.fingerprint != _fingerprint(values)
        ):
            raise SecurityTaxonomyCoverageError("SECURITY_TAXONOMY_COVERAGE_AUDIT_INVALID")

    @property
    def technical_scope_records(self) -> tuple[SecurityTaxonomyCoverageRecord, ...]:
        return tuple(value for value in self.records if value.in_current_technical_scope)

    def coverage_counts(self, *, technical_scope_only: bool = False) -> tuple[tuple[str, int], ...]:
        values = self.technical_scope_records if technical_scope_only else self.records
        return tuple(sorted(Counter(value.coverage_state.value for value in values).items()))

    def regression_counts(self) -> tuple[tuple[str, int], ...]:
        return tuple(sorted(Counter(value.regression_state.value for value in self.records).items()))

    def hierarchy_counts(self) -> tuple[tuple[str, int], ...]:
        return (
            ("macro_sector", sum(value.macro_sector is not None for value in self.records)),
            ("sector", sum(value.sector is not None for value in self.records)),
            ("industry", sum(value.industry is not None for value in self.records)),
            ("basic_industry", sum(value.basic_industry is not None for value in self.records)),
        )


def audit_current_nse_indices_taxonomy_coverage(
    *,
    audit_as_of: datetime,
    inputs: Iterable[SecurityTaxonomyCoverageInput],
    source_rows: Iterable[NseIndicesConstituent],
    hierarchy: Iterable[NseIndustryHierarchyEntry],
) -> SecurityTaxonomyCoverageAudit:
    """Audit injected official evidence without a clock, I/O, or persistence.

    The newest supplied Total Market row is selected only after cross-source
    conflicts and same-source duplicate identities are made explicit.  The
    function deliberately does not invoke the importer: a candidate cannot be
    promoted just by being audited.
    """
    if not _aware(audit_as_of):
        raise SecurityTaxonomyCoverageError("SECURITY_TAXONOMY_COVERAGE_AUDIT_AS_OF_REQUIRED")
    cutoff = audit_as_of.astimezone(UTC)
    values = tuple(inputs)
    rows = tuple(source_rows)
    entries = tuple(hierarchy)
    if (
        not values
        or any(not isinstance(value, SecurityTaxonomyCoverageInput) for value in values)
        or len({value.instrument.instrument_id for value in values}) != len(values)
        or any(not isinstance(row, NseIndicesConstituent) for row in rows)
        or any(row.source_name not in {"NIFTY_500_CONSTITUENTS", "NIFTY_TOTAL_MARKET_CONSTITUENTS"} for row in rows)
        or any(not isinstance(entry, NseIndustryHierarchyEntry) for entry in entries)
    ):
        raise SecurityTaxonomyCoverageError("SECURITY_TAXONOMY_COVERAGE_INPUT_INVALID")
    for value in values:
        value.__post_init__()
    if not entries:
        raise SecurityTaxonomyCoverageError("NSE_INDICES_CLASSIFICATION_STRUCTURE_UNAVAILABLE")
    level = _constituent_label_level(rows, entries)
    if level is None:
        raise SecurityTaxonomyCoverageError("NSE_INDICES_CONSTITUENT_CLASSIFICATION_SCHEMA_UNRESOLVED")
    duplicate_source_identities = _duplicate_source_identities(rows)
    conflicting_source_labels = _conflicting_source_labels(rows)
    nifty500 = tuple(row for row in rows if row.source_name == "NIFTY_500_CONSTITUENTS")
    total_market = tuple(row for row in rows if row.source_name == "NIFTY_TOTAL_MARKET_CONSTITUENTS")
    selected = _choose_current_rows(nifty500, total_market)
    by_isin, by_symbol = _canonical_indexes(tuple(value.instrument for value in values))
    candidates: dict[str, tuple[NseIndicesConstituent, str, NseTaxonomyResolution]] = {}
    source_problem: dict[str, tuple[SecurityTaxonomyCoverageState, SecurityTaxonomyCoverageReason, NseIndicesConstituent]] = {}
    unmatched: list[NseIndicesConstituent] = []
    for row in selected:
        instrument, identity = _resolve_instrument(row, by_isin, by_symbol)
        if instrument is None:
            unmatched.append(row)
            if identity == "ISIN_SYMBOL_CONFLICT":
                for candidate in by_isin.get(row.isin, ()):
                    source_problem[candidate.instrument_id] = (
                        SecurityTaxonomyCoverageState.IDENTITY_UNRESOLVED,
                        SecurityTaxonomyCoverageReason.ISIN_SYMBOL_CONFLICT,
                        row,
                    )
            elif identity == "UNMAPPED_TO_CANONICAL_UNIVERSE" and row.isin:
                # A source ISIN which no longer resolves cannot be overridden
                # by a same-looking symbol.  Retain the exact contradiction on
                # the one canonical symbol candidate, if there is one.
                symbol_candidates = by_symbol.get(row.symbol, ())
                if len(symbol_candidates) == 1:
                    source_problem[symbol_candidates[0].instrument_id] = (
                        SecurityTaxonomyCoverageState.IDENTITY_UNRESOLVED,
                        SecurityTaxonomyCoverageReason.ISIN_SYMBOL_CONFLICT,
                        row,
                    )
            continue
        key = (row.source_name, row.isin, row.symbol)
        pair = (row.isin, row.symbol)
        if key in duplicate_source_identities:
            source_problem[instrument.instrument_id] = (
                SecurityTaxonomyCoverageState.IDENTITY_AMBIGUOUS,
                SecurityTaxonomyCoverageReason.AMBIGUOUS_OFFICIAL_IDENTITY,
                row,
            )
            continue
        if pair in conflicting_source_labels:
            source_problem[instrument.instrument_id] = (
                SecurityTaxonomyCoverageState.TAXONOMY_EVIDENCE_CONFLICTED,
                SecurityTaxonomyCoverageReason.OFFICIAL_SOURCE_TAXONOMY_CONFLICT,
                row,
            )
            continue
        resolution = resolve_nse_indices_label(row.raw_label, entries, expected_level=level)
        prior = candidates.get(instrument.instrument_id)
        if prior is not None and _candidate_values(prior) != _candidate_values((row, identity, resolution)):
            source_problem[instrument.instrument_id] = (
                SecurityTaxonomyCoverageState.TAXONOMY_EVIDENCE_CONFLICTED,
                SecurityTaxonomyCoverageReason.OFFICIAL_SOURCE_TAXONOMY_CONFLICT,
                row,
            )
            continue
        candidates[instrument.instrument_id] = (row, identity, resolution)
    records = tuple(sorted(
        (_coverage_record(value, cutoff, candidates.get(value.instrument.instrument_id), source_problem.get(value.instrument.instrument_id))
        for value in values),
        key=lambda value: value.canonical_instrument_id,
    ))
    audit_values = _audit_values(cutoff, NSE_INDICES_OFFICIAL, level, len(selected), records, tuple(unmatched))
    return SecurityTaxonomyCoverageAudit(
        cutoff, NSE_INDICES_OFFICIAL, level, len(selected), records,
        tuple(sorted(unmatched, key=_source_sort_key)),
        CurrentTaxonomyApplicability.CURRENT_DESCRIPTIVE,
        StrictHistoricalPitTaxonomyState.NOT_READY,
        _fingerprint(audit_values),
    )


def serialize_security_taxonomy_coverage_audit(value: SecurityTaxonomyCoverageAudit) -> str:
    """Serialize every deterministic audit input using stable JSON."""
    value.__post_init__()
    return json.dumps(
        _audit_values(
            value.audit_as_of, value.source_family, value.source_label_level,
            value.source_row_count, value.records, value.unmatched_source_records,
        ) | {"fingerprint": value.fingerprint},
        sort_keys=True, separators=(",", ":"), ensure_ascii=True,
    )


def _coverage_record(
    value: SecurityTaxonomyCoverageInput,
    cutoff: datetime,
    candidate: tuple[NseIndicesConstituent, str, NseTaxonomyResolution] | None,
    problem: tuple[SecurityTaxonomyCoverageState, SecurityTaxonomyCoverageReason, NseIndicesConstituent] | None,
) -> SecurityTaxonomyCoverageRecord:
    instrument = value.instrument
    existing = value.existing_classification
    if instrument.data_as_of.astimezone(UTC) > cutoff:
        return _build_record(value, None, None, SecurityTaxonomyCoverageState.OTHER_EXACT_REASON,
                             SecurityTaxonomyCoverageReason.CANONICAL_IDENTITY_AFTER_AUDIT_AS_OF,
                             ExistingTaxonomyRegressionState.MISSING_IN_NEW_SOURCE)
    if problem is not None:
        state, reason, row = problem
        regression = ExistingTaxonomyRegressionState.IDENTITY_CHANGED if state in {
            SecurityTaxonomyCoverageState.IDENTITY_UNRESOLVED,
            SecurityTaxonomyCoverageState.IDENTITY_AMBIGUOUS,
        } and existing is not None else ExistingTaxonomyRegressionState.CONFLICT if existing is not None else ExistingTaxonomyRegressionState.NOT_PREVIOUSLY_CLASSIFIED
        return _build_record(value, row, None, state, reason, regression)
    if candidate is None:
        regression = (
            ExistingTaxonomyRegressionState.MISSING_IN_NEW_SOURCE
            if existing is not None else ExistingTaxonomyRegressionState.NOT_PREVIOUSLY_CLASSIFIED
        )
        return _build_record(value, None, None, SecurityTaxonomyCoverageState.SOURCE_UNIVERSE_LIMITATION,
                             SecurityTaxonomyCoverageReason.SOURCE_UNIVERSE_LIMITATION, regression)
    row, _, resolution = candidate
    if resolution.status != "EXACT_UNIQUE":
        regression = ExistingTaxonomyRegressionState.CONFLICT if existing is not None else ExistingTaxonomyRegressionState.NOT_PREVIOUSLY_CLASSIFIED
        return _build_record(value, row, resolution, SecurityTaxonomyCoverageState.OTHER_EXACT_REASON,
                             SecurityTaxonomyCoverageReason.NSE_INDICES_HIERARCHY_LABEL_UNRESOLVED, regression)
    if existing is None:
        return _build_record(value, row, resolution, SecurityTaxonomyCoverageState.TAXONOMY_READY,
                             SecurityTaxonomyCoverageReason.TAXONOMY_PROMOTION_AVAILABLE,
                             ExistingTaxonomyRegressionState.NOT_PREVIOUSLY_CLASSIFIED)
    if not _current_existing_classification(existing, instrument, cutoff) or not _matches_resolution(existing, row, resolution):
        return _build_record(value, row, resolution, SecurityTaxonomyCoverageState.TAXONOMY_EVIDENCE_CONFLICTED,
                             SecurityTaxonomyCoverageReason.EXISTING_TAXONOMY_CONFLICT,
                             ExistingTaxonomyRegressionState.CONFLICT)
    return _build_record(value, row, resolution, SecurityTaxonomyCoverageState.TAXONOMY_READY,
                         SecurityTaxonomyCoverageReason.EXACT_CURRENT_CLASSIFICATION,
                         ExistingTaxonomyRegressionState.EXACT_SAME)


def _build_record(
    value: SecurityTaxonomyCoverageInput,
    row: NseIndicesConstituent | None,
    resolution: NseTaxonomyResolution | None,
    state: SecurityTaxonomyCoverageState,
    reason: SecurityTaxonomyCoverageReason,
    regression: ExistingTaxonomyRegressionState,
) -> SecurityTaxonomyCoverageRecord:
    instrument = value.instrument
    existing = value.existing_classification
    fields = {
        "canonical_instrument_id": instrument.instrument_id,
        "symbol": instrument.symbol,
        "isin": instrument.isin,
        "in_current_technical_scope": value.in_current_technical_scope,
        "source_symbol": None if row is None else row.symbol,
        "source_series": None if row is None else row.series,
        "source_isin": None if row is None else row.isin,
        "source_name": None if row is None else row.source_name,
        "source_sha256": None if row is None else row.source_sha256,
        "source_line_number": None if row is None else row.line_number,
        "raw_classification_label": None if row is None else row.raw_label,
        "macro_sector": None if resolution is None or resolution.status != "EXACT_UNIQUE" else resolution.macro_name,
        "sector": None if resolution is None or resolution.status != "EXACT_UNIQUE" else resolution.sector_name,
        "industry": None,
        "basic_industry": None,
        "existing_classification_id": None if existing is None else existing.classification_id,
        "coverage_state": state,
        "reason_code": reason,
        "regression_state": regression,
        "applicability": CurrentTaxonomyApplicability.CURRENT_DESCRIPTIVE,
        "strict_historical_pit_state": StrictHistoricalPitTaxonomyState.NOT_READY,
    }
    return SecurityTaxonomyCoverageRecord(**fields, fingerprint=_fingerprint(_record_values_from(fields)))


def _duplicate_source_identities(rows: tuple[NseIndicesConstituent, ...]) -> frozenset[tuple[str, str, str]]:
    counts = Counter((row.source_name, row.isin, row.symbol) for row in rows)
    return frozenset(key for key, count in counts.items() if count > 1)


def _conflicting_source_labels(rows: tuple[NseIndicesConstituent, ...]) -> frozenset[tuple[str, str]]:
    labels: dict[tuple[str, str], set[str]] = defaultdict(set)
    for row in rows:
        labels[(row.isin, row.symbol)].add(row.raw_label)
    return frozenset(key for key, values in labels.items() if len(values) > 1)


def _current_existing_classification(
    value: InstrumentTaxonomyClassification, instrument: NseEquityInstrument, cutoff: datetime,
) -> bool:
    return (
        value.instrument_id == instrument.instrument_id
        and bool(value.classification_id)
        and _aware(value.effective_from)
        and _aware(value.as_of)
        and value.effective_from.astimezone(UTC) <= cutoff
        and value.as_of.astimezone(UTC) <= cutoff
        and (value.effective_to is None or (_aware(value.effective_to) and value.effective_to.astimezone(UTC) >= cutoff))
    )


def _matches_resolution(
    value: InstrumentTaxonomyClassification, row: NseIndicesConstituent, resolution: NseTaxonomyResolution,
) -> bool:
    return (
        value.source == NSE_INDICES_OFFICIAL
        and value.source_type.value == "OFFICIAL"
        and value.classification_version == "nse-indices-taxonomy-v1"
        and value.source_sha256 == row.source_sha256
        and value.source_reference == _expected_source_reference(row)
        and value.super_sector == resolution.macro_name
        and value.sector == resolution.sector_name
        and value.industry is None
        and value.basic_industry is None
        and value.raw_classification_label == resolution.raw_label
        and value.resolution_status == "EXACT_UNIQUE"
    )


def _expected_source_reference(row: NseIndicesConstituent) -> str:
    return f"source={row.source_name};sha256={row.source_sha256};line={row.line_number};mapping=EXACT_ISIN_AND_SYMBOL"


def _candidate_values(value: tuple[NseIndicesConstituent, str, NseTaxonomyResolution]) -> tuple[object, ...]:
    row, identity, resolution = value
    return (row.isin, row.symbol, row.raw_label, identity, resolution.status, resolution.macro_name, resolution.sector_name)


def _record_values(value: SecurityTaxonomyCoverageRecord) -> dict[str, object]:
    return _record_values_from({field: getattr(value, field) for field in value.__dataclass_fields__ if field != "fingerprint"})


def _record_values_from(values: dict[str, object]) -> dict[str, object]:
    return {key: _enum(value) for key, value in values.items()}


def _audit_values(
    audit_as_of: datetime,
    source_family: str,
    source_label_level: str,
    source_row_count: int,
    records: tuple[SecurityTaxonomyCoverageRecord, ...],
    unmatched_source_records: tuple[NseIndicesConstituent, ...],
) -> dict[str, object]:
    return {
        "contract": CONTRACT_ID,
        "version": CONTRACT_VERSION,
        "audit_as_of": audit_as_of.astimezone(UTC).isoformat(),
        "source_family": source_family,
        "source_label_level": source_label_level,
        "source_row_count": source_row_count,
        "applicability": CurrentTaxonomyApplicability.CURRENT_DESCRIPTIVE.value,
        "strict_historical_pit_state": StrictHistoricalPitTaxonomyState.NOT_READY.value,
        "records": [_record_values(value) | {"fingerprint": value.fingerprint} for value in records],
        "unmatched_source_records": [_source_values(value) for value in unmatched_source_records],
    }


def _source_values(value: NseIndicesConstituent) -> dict[str, object]:
    return {
        "company_name": value.company_name,
        "raw_label": value.raw_label,
        "symbol": value.symbol,
        "series": value.series,
        "isin": value.isin,
        "source_name": value.source_name,
        "source_sha256": value.source_sha256,
        "line_number": value.line_number,
    }


def _source_sort_key(value: NseIndicesConstituent) -> tuple[str, str, str, int]:
    return (value.symbol, value.isin, value.source_name, value.line_number)


def _aware(value: object) -> bool:
    return isinstance(value, datetime) and value.tzinfo is not None and value.utcoffset() is not None


def _nonempty(value: object) -> bool:
    return isinstance(value, str) and bool(value)


def _state_reason_valid(
    state: SecurityTaxonomyCoverageState, reason: SecurityTaxonomyCoverageReason,
) -> bool:
    return reason in {
        SecurityTaxonomyCoverageState.TAXONOMY_READY: {
            SecurityTaxonomyCoverageReason.EXACT_CURRENT_CLASSIFICATION,
            SecurityTaxonomyCoverageReason.TAXONOMY_PROMOTION_AVAILABLE,
        },
        SecurityTaxonomyCoverageState.SOURCE_UNIVERSE_LIMITATION: {
            SecurityTaxonomyCoverageReason.SOURCE_UNIVERSE_LIMITATION,
        },
        SecurityTaxonomyCoverageState.IDENTITY_UNRESOLVED: {
            SecurityTaxonomyCoverageReason.ISIN_SYMBOL_CONFLICT,
        },
        SecurityTaxonomyCoverageState.IDENTITY_AMBIGUOUS: {
            SecurityTaxonomyCoverageReason.AMBIGUOUS_OFFICIAL_IDENTITY,
        },
        SecurityTaxonomyCoverageState.UNSUPPORTED_SECURITY_SERIES: {
            SecurityTaxonomyCoverageReason.UNSUPPORTED_SECURITY_SERIES,
        },
        SecurityTaxonomyCoverageState.TAXONOMY_EVIDENCE_CONFLICTED: {
            SecurityTaxonomyCoverageReason.OFFICIAL_SOURCE_TAXONOMY_CONFLICT,
            SecurityTaxonomyCoverageReason.EXISTING_TAXONOMY_CONFLICT,
        },
        SecurityTaxonomyCoverageState.OTHER_EXACT_REASON: {
            SecurityTaxonomyCoverageReason.NSE_INDICES_HIERARCHY_LABEL_UNRESOLVED,
            SecurityTaxonomyCoverageReason.CANONICAL_IDENTITY_AFTER_AUDIT_AS_OF,
        },
    }[state]


def _enum(value: object) -> object:
    return value.value if isinstance(value, StrEnum) else value


def _fingerprint(value: object) -> str:
    return "sha256:" + sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")).hexdigest()


__all__ = (
    "CONTRACT_ID", "CONTRACT_VERSION", "CurrentTaxonomyApplicability",
    "ExistingTaxonomyRegressionState", "SecurityTaxonomyCoverageAudit",
    "SecurityTaxonomyCoverageError", "SecurityTaxonomyCoverageInput",
    "SecurityTaxonomyCoverageReason", "SecurityTaxonomyCoverageRecord",
    "SecurityTaxonomyCoverageState", "StrictHistoricalPitTaxonomyState",
    "audit_current_nse_indices_taxonomy_coverage",
    "serialize_security_taxonomy_coverage_audit",
)
