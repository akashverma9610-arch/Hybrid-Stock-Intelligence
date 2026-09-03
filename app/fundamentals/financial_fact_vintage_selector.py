"""Pure stored-only PIT financial fact-vintage selection.

The functions here accept already-loaded immutable FinancialFact values plus an
explicit approved policy. They do not query a store, call a provider, persist a
result, materialize an observation, build a trajectory, or derive investment
meaning.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Iterable

from app.data_sources.models import FundamentalFactKind
from app.fundamentals.financial_fact_vintage_selection_policy import (
    FinancialFactVintageAvailabilityRule,
    FinancialFactVintageDuplicateRequirement,
    FinancialFactVintageFactFingerprintOwner,
    FinancialFactVintageRevisionRequirement,
    FinancialFactVintageSelectionMode,
    FinancialFactVintageSelectionReason,
    FinancialFactVintageSelectionStatus,
    FinancialFactVintageSelectionWarning,
    FrozenFinancialFactVintageSelectionPolicy,
    financial_fact_vintage_selection_policy_fingerprint,
)
from app.fundamentals.models import (
    FinancialFact,
    FinancialMetric,
    FinancialPeriodType,
    FinancialValueBasis,
    FinancialValueDimension,
    NumericScale,
    StatementScope,
)
from app.historical.guard import manifest_fingerprint


_REQUIRED_POLICY_ID = "financial-fact-vintage-selection-policy"
_REQUIRED_POLICY_VERSION = "v1-approved"
_REQUIRED_POLICY_FINGERPRINT = "862dc470ebd58abd2d066f2604440908eaf3aa9827e6c93b588b5f1bf806fc13"


@dataclass(frozen=True, slots=True)
class FinancialFactSemanticKey:
    """Exact stored-fact identity under which revision candidates may compete."""

    canonical_instrument_id: str
    metric: FinancialMetric
    fact_kind: FundamentalFactKind
    statement_scope: StatementScope
    period_type: FinancialPeriodType
    value_basis: FinancialValueBasis
    period_start: datetime | None
    period_end: datetime
    fiscal_year: int | None
    fiscal_quarter: int | None
    value_dimension: FinancialValueDimension
    currency: str
    unit: str
    scale: NumericScale
    normalization_version: str

    def __post_init__(self) -> None:
        if not all((
            self.canonical_instrument_id,
            self.currency,
            self.unit,
            self.normalization_version,
        )):
            raise ValueError("FINANCIAL_FACT_VINTAGE_SEMANTIC_KEY_REQUIRED_FIELD")
        if not _timezone_aware(self.period_end) or (
            self.period_start is not None and not _timezone_aware(self.period_start)
        ):
            raise ValueError("FINANCIAL_FACT_VINTAGE_SEMANTIC_KEY_TIMEZONE_REQUIRED")
        if self.fiscal_year is not None and self.fiscal_year <= 0:
            raise ValueError("FINANCIAL_FACT_VINTAGE_SEMANTIC_KEY_FISCAL_YEAR_INVALID")
        if self.fiscal_quarter is not None and self.fiscal_quarter not in {1, 2, 3, 4}:
            raise ValueError("FINANCIAL_FACT_VINTAGE_SEMANTIC_KEY_FISCAL_QUARTER_INVALID")

    def ordering_key(self) -> tuple[str, ...]:
        return (
            self.canonical_instrument_id,
            self.metric.value,
            self.fact_kind.value,
            self.statement_scope.value,
            self.period_type.value,
            self.value_basis.value,
            _timestamp_key(self.period_start),
            _timestamp_key(self.period_end),
            "" if self.fiscal_year is None else str(self.fiscal_year),
            "" if self.fiscal_quarter is None else str(self.fiscal_quarter),
            self.value_dimension.value,
            self.currency,
            self.unit,
            self.scale.value,
            self.normalization_version,
        )


@dataclass(frozen=True, slots=True)
class FinancialFactVintageSelection:
    """One factual, non-semantic result for a semantic key at a fixed as-of."""

    semantic_key: FinancialFactSemanticKey | None
    as_of: datetime
    status: FinancialFactVintageSelectionStatus
    selected_fact_id: str | None
    candidate_fact_ids: tuple[str, ...]
    excluded_future_fact_ids: tuple[str, ...]
    superseded_fact_ids: tuple[str, ...]
    duplicate_fact_ids: tuple[str, ...]
    conflicting_fact_ids: tuple[str, ...]
    revision_lineage_fact_ids: tuple[str, ...]
    warnings: tuple[FinancialFactVintageSelectionWarning, ...]
    reasons: tuple[FinancialFactVintageSelectionReason, ...]
    policy_id: str
    policy_version: str
    policy_fingerprint: str
    fingerprint: str

    def __post_init__(self) -> None:
        if not _timezone_aware(self.as_of):
            raise ValueError("FINANCIAL_FACT_VINTAGE_SELECTION_AS_OF_TIMEZONE_REQUIRED")
        if not self.candidate_fact_ids:
            raise ValueError("FINANCIAL_FACT_VINTAGE_SELECTION_CANDIDATES_REQUIRED")
        for values, label in (
            (self.candidate_fact_ids, "CANDIDATES"),
            (self.excluded_future_fact_ids, "FUTURE"),
            (self.superseded_fact_ids, "SUPERSEDED"),
            (self.duplicate_fact_ids, "DUPLICATES"),
            (self.conflicting_fact_ids, "CONFLICTS"),
            (self.revision_lineage_fact_ids, "LINEAGE"),
        ):
            if values != tuple(sorted(set(values))):
                raise ValueError("FINANCIAL_FACT_VINTAGE_SELECTION_" + label + "_NONCANONICAL")
        if self.warnings != tuple(sorted(set(self.warnings), key=lambda value: value.value)):
            raise ValueError("FINANCIAL_FACT_VINTAGE_SELECTION_WARNINGS_NONCANONICAL")
        if self.reasons != tuple(sorted(set(self.reasons), key=lambda value: value.value)):
            raise ValueError("FINANCIAL_FACT_VINTAGE_SELECTION_REASONS_NONCANONICAL")
        if self.status is FinancialFactVintageSelectionStatus.SELECTED:
            if self.selected_fact_id is None or self.reasons:
                raise ValueError("FINANCIAL_FACT_VINTAGE_SELECTION_SELECTED_CONTRACT_INVALID")
        elif self.selected_fact_id is not None:
            raise ValueError("FINANCIAL_FACT_VINTAGE_SELECTION_UNSELECTED_FACT_INVALID")
        if self.fingerprint != financial_fact_vintage_selection_fingerprint(self):
            raise ValueError("FINANCIAL_FACT_VINTAGE_SELECTION_FINGERPRINT_MISMATCH")

    def ordering_key(self) -> tuple[str, ...]:
        if self.semantic_key is not None:
            return ("1", *self.semantic_key.ordering_key())
        return ("0", *self.candidate_fact_ids)


@dataclass(frozen=True, slots=True)
class FinancialFactVintageSelectionBatch:
    """Deterministic rebuildable selector output; it is never persisted here."""

    canonical_instrument_id: str
    as_of: datetime
    policy_id: str
    policy_version: str
    policy_fingerprint: str
    selections: tuple[FinancialFactVintageSelection, ...]
    status_counts: tuple[tuple[FinancialFactVintageSelectionStatus, int], ...]
    reason_counts: tuple[tuple[FinancialFactVintageSelectionReason, int], ...]
    foundational_warnings: tuple[str, ...]
    fingerprint: str

    def __post_init__(self) -> None:
        if not self.canonical_instrument_id or not _timezone_aware(self.as_of):
            raise ValueError("FINANCIAL_FACT_VINTAGE_BATCH_REQUEST_INVALID")
        if self.selections != tuple(sorted(self.selections, key=lambda value: value.ordering_key())):
            raise ValueError("FINANCIAL_FACT_VINTAGE_BATCH_SELECTIONS_NONCANONICAL")
        if self.status_counts != _ordered_status_counts(dict(self.status_counts)):
            raise ValueError("FINANCIAL_FACT_VINTAGE_BATCH_STATUS_COUNTS_NONCANONICAL")
        if self.reason_counts != _ordered_reason_counts(dict(self.reason_counts)):
            raise ValueError("FINANCIAL_FACT_VINTAGE_BATCH_REASON_COUNTS_NONCANONICAL")
        if self.foundational_warnings != tuple(sorted(set(self.foundational_warnings))):
            raise ValueError("FINANCIAL_FACT_VINTAGE_BATCH_WARNINGS_NONCANONICAL")
        if self.fingerprint != financial_fact_vintage_selection_batch_fingerprint(self):
            raise ValueError("FINANCIAL_FACT_VINTAGE_BATCH_FINGERPRINT_MISMATCH")


def select_financial_fact_vintages(
    facts: Iterable[FinancialFact],
    *,
    canonical_instrument_id: str,
    as_of: datetime,
    policy: FrozenFinancialFactVintageSelectionPolicy,
) -> FinancialFactVintageSelectionBatch:
    """Select factual PIT vintages from supplied facts under one explicit policy."""

    _validate_policy(policy)
    if not canonical_instrument_id:
        raise ValueError("FINANCIAL_FACT_VINTAGE_SELECTOR_CANONICAL_INSTRUMENT_REQUIRED")
    if not _timezone_aware(as_of):
        raise ValueError("FINANCIAL_FACT_VINTAGE_SELECTOR_AS_OF_TIMEZONE_REQUIRED")

    values = _canonical_fact_input(facts, canonical_instrument_id)
    groups: dict[FinancialFactSemanticKey, list[FinancialFact]] = defaultdict(list)
    invalid: list[FinancialFact] = []
    for fact in values:
        key = _semantic_key_or_none(fact)
        if key is None:
            invalid.append(fact)
        else:
            groups[key].append(fact)
    supplied_facts_by_id = {fact.fact_id: fact for fact in values}

    selections = [
        _insufficient_identity_selection(fact, as_of, policy)
        for fact in sorted(invalid, key=lambda value: value.fact_id)
    ]
    selections.extend(
        _select_key(
            key,
            group,
            supplied_facts_by_id,
            as_of,
            policy,
        )
        for key, group in sorted(groups.items(), key=lambda item: item[0].ordering_key())
    )
    ordered = tuple(sorted(selections, key=lambda value: value.ordering_key()))
    status_counts = _ordered_status_counts(Counter(value.status for value in ordered))
    reason_counts = _ordered_reason_counts(
        Counter(reason for value in ordered for reason in value.reasons)
    )
    values_for_fingerprint = dict(
        canonical_instrument_id=canonical_instrument_id,
        as_of=as_of,
        policy_id=policy.policy_id,
        policy_version=policy.version,
        policy_fingerprint=policy.fingerprint,
        selections=ordered,
        status_counts=status_counts,
        reason_counts=reason_counts,
        foundational_warnings=(),
    )
    return FinancialFactVintageSelectionBatch(
        **values_for_fingerprint,
        fingerprint=financial_fact_vintage_selection_batch_fingerprint_values(values_for_fingerprint),
    )


def financial_fact_vintage_selection_fingerprint(value: FinancialFactVintageSelection) -> str:
    return financial_fact_vintage_selection_fingerprint_values({
        field: getattr(value, field) for field in value.__dataclass_fields__ if field != "fingerprint"
    })


def financial_fact_vintage_selection_fingerprint_values(values: dict) -> str:
    key = values["semantic_key"]
    return manifest_fingerprint(
        semantic_key=None if key is None else _semantic_key_values(key),
        as_of=_timestamp_key(values["as_of"]),
        status=values["status"].value,
        selected_fact_id=values["selected_fact_id"],
        candidate_fact_ids=values["candidate_fact_ids"],
        excluded_future_fact_ids=values["excluded_future_fact_ids"],
        superseded_fact_ids=values["superseded_fact_ids"],
        duplicate_fact_ids=values["duplicate_fact_ids"],
        conflicting_fact_ids=values["conflicting_fact_ids"],
        revision_lineage_fact_ids=values["revision_lineage_fact_ids"],
        warnings=tuple(item.value for item in values["warnings"]),
        reasons=tuple(item.value for item in values["reasons"]),
        policy_id=values["policy_id"],
        policy_version=values["policy_version"],
        policy_fingerprint=values["policy_fingerprint"],
    )


def financial_fact_vintage_selection_batch_fingerprint(
    value: FinancialFactVintageSelectionBatch,
) -> str:
    return financial_fact_vintage_selection_batch_fingerprint_values({
        field: getattr(value, field) for field in value.__dataclass_fields__ if field != "fingerprint"
    })


def financial_fact_vintage_selection_batch_fingerprint_values(values: dict) -> str:
    return manifest_fingerprint(
        canonical_instrument_id=values["canonical_instrument_id"],
        as_of=_timestamp_key(values["as_of"]),
        policy_id=values["policy_id"],
        policy_version=values["policy_version"],
        policy_fingerprint=values["policy_fingerprint"],
        selection_fingerprints=tuple(item.fingerprint for item in values["selections"]),
        status_counts=tuple((status.value, count) for status, count in values["status_counts"]),
        reason_counts=tuple((reason.value, count) for reason, count in values["reason_counts"]),
        foundational_warnings=values["foundational_warnings"],
    )


def _validate_policy(policy: FrozenFinancialFactVintageSelectionPolicy) -> None:
    if not isinstance(policy, FrozenFinancialFactVintageSelectionPolicy):
        raise ValueError("FINANCIAL_FACT_VINTAGE_SELECTOR_POLICY_INVALID")
    if (
        policy.policy_id != _REQUIRED_POLICY_ID
        or policy.version != _REQUIRED_POLICY_VERSION
        or policy.fingerprint != _REQUIRED_POLICY_FINGERPRINT
    ):
        raise ValueError("FINANCIAL_FACT_VINTAGE_SELECTOR_POLICY_UNSUPPORTED")
    if financial_fact_vintage_selection_policy_fingerprint(policy) != policy.fingerprint:
        raise ValueError("FINANCIAL_FACT_VINTAGE_SELECTOR_POLICY_TAMPERED")
    if (
        policy.selection_mode is not FinancialFactVintageSelectionMode.KNOWLEDGE_AT_THE_TIME
        or policy.active
        or policy.selected_for_future_selector
        or policy.availability_rule is not FinancialFactVintageAvailabilityRule.MAX_PUBLISHED_AT_RECEIVED_AT
        or policy.fact_fingerprint_owner is not FinancialFactVintageFactFingerprintOwner.FUTURE_FINANCIAL_METRIC_OBSERVATION_SCHEMA
    ):
        raise ValueError("FINANCIAL_FACT_VINTAGE_SELECTOR_POLICY_MODE_INVALID")


def _canonical_fact_input(
    facts: Iterable[FinancialFact],
    canonical_instrument_id: str,
) -> tuple[FinancialFact, ...]:
    values: dict[str, FinancialFact] = {}
    for fact in facts:
        if not isinstance(fact, FinancialFact):
            raise ValueError("FINANCIAL_FACT_VINTAGE_SELECTOR_FACT_TYPE_INVALID")
        if fact.instrument.instrument_id != canonical_instrument_id:
            raise ValueError("FINANCIAL_FACT_VINTAGE_SELECTOR_MIXED_INSTRUMENT_INPUT")
        existing = values.get(fact.fact_id)
        if existing is not None and existing != fact:
            raise ValueError("FINANCIAL_FACT_VINTAGE_SELECTOR_FACT_ID_CONFLICT")
        values[fact.fact_id] = fact
    return tuple(sorted(values.values(), key=lambda value: value.fact_id))


def _semantic_key_or_none(fact: FinancialFact) -> FinancialFactSemanticKey | None:
    if not all((
        fact.instrument.instrument_id,
        fact.currency,
        fact.unit,
        fact.normalization_version,
        _timezone_aware(fact.published_at),
        _timezone_aware(fact.received_at),
        _timezone_aware(fact.period_end),
    )):
        return None
    if fact.period_start is not None and not _timezone_aware(fact.period_start):
        return None
    try:
        return FinancialFactSemanticKey(
            canonical_instrument_id=fact.instrument.instrument_id,
            metric=fact.metric,
            fact_kind=fact.fact_kind,
            statement_scope=fact.statement_scope,
            period_type=fact.period_type,
            value_basis=fact.value_basis,
            period_start=fact.period_start,
            period_end=fact.period_end,
            fiscal_year=fact.fiscal_year,
            fiscal_quarter=fact.fiscal_quarter,
            value_dimension=fact.value_dimension,
            currency=fact.currency,
            unit=fact.unit,
            scale=fact.scale,
            normalization_version=fact.normalization_version,
        )
    except (TypeError, ValueError):
        return None


def _insufficient_identity_selection(
    fact: FinancialFact,
    as_of: datetime,
    policy: FrozenFinancialFactVintageSelectionPolicy,
) -> FinancialFactVintageSelection:
    values = dict(
        semantic_key=None,
        as_of=as_of,
        status=FinancialFactVintageSelectionStatus.INSUFFICIENT_IDENTITY,
        selected_fact_id=None,
        candidate_fact_ids=(fact.fact_id,),
        excluded_future_fact_ids=(),
        superseded_fact_ids=(),
        duplicate_fact_ids=(),
        conflicting_fact_ids=(),
        revision_lineage_fact_ids=(),
        warnings=(),
        reasons=(FinancialFactVintageSelectionReason.AMBIGUOUS_SEMANTIC_KEY,),
        policy_id=policy.policy_id,
        policy_version=policy.version,
        policy_fingerprint=policy.fingerprint,
    )
    return FinancialFactVintageSelection(
        **values,
        fingerprint=financial_fact_vintage_selection_fingerprint_values(values),
    )


def _select_key(
    key: FinancialFactSemanticKey,
    facts: list[FinancialFact],
    supplied_facts_by_id: dict[str, FinancialFact],
    as_of: datetime,
    policy: FrozenFinancialFactVintageSelectionPolicy,
) -> FinancialFactVintageSelection:
    candidates = tuple(sorted((fact.fact_id for fact in facts)))
    eligible = tuple(sorted(
        (fact for fact in facts if fact.available_at <= as_of),
        key=lambda value: value.fact_id,
    ))
    future = tuple(sorted(set(candidates) - {fact.fact_id for fact in eligible}))
    if not eligible:
        return _result(
            key, as_of, FinancialFactVintageSelectionStatus.UNAVAILABLE, policy,
            candidates=candidates, future=future,
            reasons=(FinancialFactVintageSelectionReason.NO_PIT_ELIGIBLE_FACT,),
        )

    components, representative_by_id = _duplicate_components(eligible)
    representative_facts = {
        representative: next(
            fact for fact in eligible if fact.fact_id == representative
        )
        for representative in components
    }
    component_ids = {
        representative: tuple(sorted(component))
        for representative, component in components.items()
    }
    duplicates = tuple(sorted(
        fact_id
        for representative, component in component_ids.items()
        for fact_id in component
        if fact_id != representative
    ))

    edges: dict[str, str] = {}
    lineage_ids: set[str] = set()
    revised_without_parent: set[str] = set()
    for fact in eligible:
        representative = representative_by_id[fact.fact_id]
        if fact.revision_of_fact_id is None:
            if _is_revised_without_parent(fact):
                revised_without_parent.add(representative)
            continue
        parent = supplied_facts_by_id.get(fact.revision_of_fact_id)
        if parent is None:
            return _invalid_lineage(
                key, as_of, policy, candidates, future, duplicates,
                (FinancialFactVintageSelectionReason.REVISION_PARENT_MISSING,),
                lineage_ids | {fact.fact_id},
            )
        parent_key = _semantic_key_or_none(parent)
        if parent_key != key:
            return _invalid_lineage(
                key, as_of, policy, candidates, future, duplicates,
                (FinancialFactVintageSelectionReason.CROSS_SEMANTIC_REVISION,),
                lineage_ids | {fact.fact_id, parent.fact_id},
            )
        if fact.available_at < parent.available_at:
            return _invalid_lineage(
                key, as_of, policy, candidates, future, duplicates,
                (FinancialFactVintageSelectionReason.INVALID_REVISION_CHRONOLOGY,),
                lineage_ids | {fact.fact_id, parent.fact_id},
            )
        parent_representative = representative_by_id.get(parent.fact_id)
        if parent_representative is None:
            return _invalid_lineage(
                key, as_of, policy, candidates, future, duplicates,
                (FinancialFactVintageSelectionReason.REVISION_PARENT_MISSING,),
                lineage_ids | {fact.fact_id, parent.fact_id},
            )
        if representative != parent_representative:
            previous = edges.get(representative)
            if previous is not None and previous != parent_representative:
                return _invalid_lineage(
                    key, as_of, policy, candidates, future, duplicates,
                    (FinancialFactVintageSelectionReason.CROSS_SEMANTIC_REVISION,),
                    lineage_ids | {fact.fact_id, parent.fact_id},
                )
            edges[representative] = parent_representative
            lineage_ids.update(component_ids[representative])
            lineage_ids.update(component_ids[parent_representative])

    if _contains_cycle(edges):
        return _invalid_lineage(
            key, as_of, policy, candidates, future, duplicates,
            (FinancialFactVintageSelectionReason.REVISION_CYCLE,),
            lineage_ids,
        )

    children: dict[str, set[str]] = defaultdict(set)
    for child, parent in edges.items():
        children[parent].add(child)
    if any(len(values) > 1 for values in children.values()):
        return _invalid_lineage(
            key, as_of, policy, candidates, future, duplicates,
            (FinancialFactVintageSelectionReason.REVISION_BRANCH_CONFLICT,),
            lineage_ids,
        )

    terminals = tuple(sorted(
        representative
        for representative in representative_facts
        if representative not in children
    ))
    if len(terminals) != 1:
        conflicts = tuple(sorted(
            fact_id
            for representative in terminals
            for fact_id in component_ids[representative]
        ))
        return _result(
            key, as_of, FinancialFactVintageSelectionStatus.CONFLICTED, policy,
            candidates=candidates, future=future, duplicates=duplicates,
            conflicts=conflicts, lineage=tuple(sorted(lineage_ids)),
            reasons=(FinancialFactVintageSelectionReason.UNRESOLVED_FACT_CONFLICT,),
        )

    selected = terminals[0]
    warnings = (
        (FinancialFactVintageSelectionWarning.REVISED_WITHOUT_EXPLICIT_PARENT,)
        if selected in revised_without_parent
        else ()
    )
    superseded = tuple(sorted(
        fact_id
        for representative in children
        for fact_id in component_ids[representative]
    ))
    return _result(
        key, as_of, FinancialFactVintageSelectionStatus.SELECTED, policy,
        selected=selected, candidates=candidates, future=future,
        superseded=superseded, duplicates=duplicates,
        lineage=tuple(sorted(lineage_ids)), warnings=warnings,
    )


def _duplicate_components(
    eligible: tuple[FinancialFact, ...],
) -> tuple[dict[str, tuple[str, ...]], dict[str, str]]:
    parents = {fact.fact_id: fact.fact_id for fact in eligible}

    def root(fact_id: str) -> str:
        while parents[fact_id] != fact_id:
            parents[fact_id] = parents[parents[fact_id]]
            fact_id = parents[fact_id]
        return fact_id

    def join(left: str, right: str) -> None:
        left_root, right_root = root(left), root(right)
        if left_root != right_root:
            parents[max(left_root, right_root)] = min(left_root, right_root)

    for index, left in enumerate(eligible):
        for right in eligible[index + 1:]:
            if _exact_duplicate(left, right):
                join(left.fact_id, right.fact_id)

    raw_components: dict[str, list[str]] = defaultdict(list)
    for fact in eligible:
        raw_components[root(fact.fact_id)].append(fact.fact_id)
    components: dict[str, tuple[str, ...]] = {}
    representative_by_id: dict[str, str] = {}
    for component in raw_components.values():
        ordered = tuple(sorted(component))
        representative = ordered[0]
        components[representative] = ordered
        representative_by_id.update({fact_id: representative for fact_id in ordered})
    return components, representative_by_id


def _exact_duplicate(left: FinancialFact, right: FinancialFact) -> bool:
    if left.value != right.value:
        return False
    if left.source != right.source:
        return False
    same_filing = bool(left.filing_id and left.filing_id == right.filing_id)
    same_reference = bool(
        left.source_reference and left.source_reference == right.source_reference
    )
    if not (same_filing or same_reference):
        return False
    return (
        left.revision_of_fact_id == right.revision_of_fact_id
        and left.parent_fact_ids == right.parent_fact_ids
    )


def _contains_cycle(edges: dict[str, str]) -> bool:
    visited: set[str] = set()
    for start in sorted(edges):
        path: set[str] = set()
        node = start
        while node in edges:
            if node in path:
                return True
            if node in visited:
                break
            path.add(node)
            node = edges[node]
        visited.update(path)
    return False


def _is_revised_without_parent(fact: FinancialFact) -> bool:
    return any(flag.value == "REVISED" for flag in fact.quality_flags)


def _invalid_lineage(
    key: FinancialFactSemanticKey,
    as_of: datetime,
    policy: FrozenFinancialFactVintageSelectionPolicy,
    candidates: tuple[str, ...],
    future: tuple[str, ...],
    duplicates: tuple[str, ...],
    reasons: tuple[FinancialFactVintageSelectionReason, ...],
    lineage: set[str],
) -> FinancialFactVintageSelection:
    return _result(
        key, as_of, FinancialFactVintageSelectionStatus.INVALID_LINEAGE, policy,
        candidates=candidates, future=future, duplicates=duplicates,
        lineage=tuple(sorted(lineage)), reasons=reasons,
    )


def _result(
    key: FinancialFactSemanticKey | None,
    as_of: datetime,
    status: FinancialFactVintageSelectionStatus,
    policy: FrozenFinancialFactVintageSelectionPolicy,
    *,
    selected: str | None = None,
    candidates: tuple[str, ...],
    future: tuple[str, ...] = (),
    superseded: tuple[str, ...] = (),
    duplicates: tuple[str, ...] = (),
    conflicts: tuple[str, ...] = (),
    lineage: tuple[str, ...] = (),
    warnings: tuple[FinancialFactVintageSelectionWarning, ...] = (),
    reasons: tuple[FinancialFactVintageSelectionReason, ...] = (),
) -> FinancialFactVintageSelection:
    values = dict(
        semantic_key=key,
        as_of=as_of,
        status=status,
        selected_fact_id=selected,
        candidate_fact_ids=tuple(sorted(set(candidates))),
        excluded_future_fact_ids=tuple(sorted(set(future))),
        superseded_fact_ids=tuple(sorted(set(superseded))),
        duplicate_fact_ids=tuple(sorted(set(duplicates))),
        conflicting_fact_ids=tuple(sorted(set(conflicts))),
        revision_lineage_fact_ids=tuple(sorted(set(lineage))),
        warnings=tuple(sorted(set(warnings), key=lambda value: value.value)),
        reasons=tuple(sorted(set(reasons), key=lambda value: value.value)),
        policy_id=policy.policy_id,
        policy_version=policy.version,
        policy_fingerprint=policy.fingerprint,
    )
    return FinancialFactVintageSelection(
        **values,
        fingerprint=financial_fact_vintage_selection_fingerprint_values(values),
    )


def _ordered_status_counts(
    values: dict[FinancialFactVintageSelectionStatus, int],
) -> tuple[tuple[FinancialFactVintageSelectionStatus, int], ...]:
    return tuple(
        (status, values[status])
        for status in FinancialFactVintageSelectionStatus
        if values.get(status, 0)
    )


def _ordered_reason_counts(
    values: dict[FinancialFactVintageSelectionReason, int],
) -> tuple[tuple[FinancialFactVintageSelectionReason, int], ...]:
    return tuple(
        (reason, values[reason])
        for reason in FinancialFactVintageSelectionReason
        if values.get(reason, 0)
    )


def _semantic_key_values(value: FinancialFactSemanticKey) -> tuple[str, ...]:
    return value.ordering_key()


def _timestamp_key(value: datetime | None) -> str:
    """A total ordering key for optional period boundaries.

    Optional ``period_start`` is an established stored-fact state.  It must
    remain distinct from a timestamp while still allowing semantic keys with
    and without that optional boundary to be sorted deterministically.
    """
    return value.astimezone(UTC).isoformat() if value is not None else ""


def _timezone_aware(value: datetime) -> bool:
    return value.tzinfo is not None and value.utcoffset() is not None


__all__ = (
    "FinancialFactSemanticKey",
    "FinancialFactVintageSelection",
    "FinancialFactVintageSelectionBatch",
    "financial_fact_vintage_selection_batch_fingerprint",
    "financial_fact_vintage_selection_fingerprint",
    "select_financial_fact_vintages",
)
