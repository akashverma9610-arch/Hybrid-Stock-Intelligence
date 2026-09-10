"""Pure financial comparability over existing facts, vintages and observations.

No acquisition, store, derivation or investment policy lives at this boundary.
"""
from __future__ import annotations

from calendar import monthrange
from dataclasses import dataclass, fields, is_dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from hashlib import sha256
import json

from app.data_sources.models import FundamentalFactKind
from app.filings.models import CorporateFiling, FilingType, PrimarySourceQuality
from app.fundamentals.financial_fact_vintage_selection_policy import (
    CURRENT_FROZEN_FINANCIAL_FACT_VINTAGE_SELECTION_POLICY,
    FinancialFactVintageSelectionStatus as VintageStatus,
)
from app.fundamentals.financial_fact_vintage_selector import (
    FinancialFactVintageSelectionBatch, select_financial_fact_vintages,
)
from app.fundamentals.financial_metric_observation_materializer import materialize_financial_metric_observation
from app.fundamentals.financial_metric_observation_schema import (
    CURRENT_FROZEN_FINANCIAL_METRIC_OBSERVATION_SCHEMA, FinancialMetricObservation,
)
from app.fundamentals.models import (
    FinancialFact, FinancialMetric, FinancialPeriodType, FinancialQualityFlag,
    FinancialValueBasis, NumericScale, StatementScope,
)

CONTRACT_ID = "canonical-financial-diagnostic-comparability"
CONTRACT_VERSION = "v1"


class ComparabilityState(StrEnum):
    READY = "READY"
    PARTIAL = "PARTIAL"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    EVIDENCE_CONFLICTED = "EVIDENCE_CONFLICTED"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    POLICY_BLOCKED = "POLICY_BLOCKED"


def canonical_json(value: object) -> str:
    """Explicit versioned-content encoding; UTC, Decimal strings, ordered keys."""
    def encode(item):
        if isinstance(item, datetime):
            if item.tzinfo is None or item.utcoffset() is None:
                raise ValueError("FINANCIAL_COMPARABILITY_TIMEZONE_REQUIRED")
            return item.astimezone(UTC).isoformat()
        if isinstance(item, Decimal):
            if not item.is_finite():
                raise ValueError("FINANCIAL_COMPARABILITY_NONFINITE_VALUE")
            return str(item)
        if is_dataclass(item):
            return {f.name: encode(getattr(item, f.name)) for f in fields(item)}
        if isinstance(item, (tuple, list)):
            return [encode(v) for v in item]
        if isinstance(item, dict):
            return {k: encode(v) for k, v in item.items()}
        return item
    return json.dumps(encode(value), sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)


def content_fingerprint(value: object) -> str:
    return "sha256:" + sha256(canonical_json(value).encode("utf-8")).hexdigest()


def fiscal_key(fact: FinancialFact | FinancialMetricObservation) -> tuple[int, int, datetime, datetime]:
    p = fact.period_identity if isinstance(fact, FinancialMetricObservation) else fact
    return (p.fiscal_year or 0, p.fiscal_quarter or 0,
            p.period_start or p.period_end, p.period_end)


def representation(value: FinancialMetricObservation) -> tuple[str, str, NumericScale, str]:
    return value.currency, value.unit, value.scale, value.normalization_version


def _plus_months(value: date, months: int) -> date:
    index = value.year * 12 + value.month - 1 + months
    year, month = divmod(index, 12)
    return date(year, month + 1, min(value.day, monthrange(year, month + 1)[1]))


def period_valid(fact: FinancialFact) -> bool:
    """Exact calendar accounting interval, never an approximate day tolerance."""
    if not fact.fiscal_year or fact.period_end.tzinfo is None:
        return False
    if fact.period_type is FinancialPeriodType.POINT_IN_TIME:
        return fact.period_start is None and fact.value_basis is FinancialValueBasis.UNKNOWN
    if fact.period_start is None or fact.period_start.tzinfo is None:
        return False
    start, end = fact.period_start.astimezone(UTC).date(), fact.period_end.astimezone(UTC).date()
    if start.day != 1 or end.day != monthrange(end.year, end.month)[1]:
        return False
    if fact.period_type is FinancialPeriodType.ANNUAL:
        months = 12
        if fact.value_basis is not FinancialValueBasis.FULL_YEAR:
            return False
    elif fact.period_type is FinancialPeriodType.QUARTERLY:
        if fact.fiscal_quarter not in {1, 2, 3, 4}:
            return False
        months = 3 if fact.value_basis is FinancialValueBasis.QUARTER_ONLY else 3 * fact.fiscal_quarter
        if fact.value_basis not in {FinancialValueBasis.QUARTER_ONLY, FinancialValueBasis.YEAR_TO_DATE}:
            return False
    else:
        return False  # no new TTM or non-calendar accounting policy
    return _plus_months(start, months) - timedelta(days=1) == end


def consecutive(keys: tuple[tuple[int, int, datetime, datetime], ...], *, quarterly: bool) -> bool:
    for a, b in zip(keys, keys[1:]):
        if b[2].astimezone(UTC).date() != a[3].astimezone(UTC).date() + timedelta(days=1):
            return False
        expected = (a[0] + (a[1] == 4), a[1] % 4 + 1) if quarterly else (a[0] + 1, b[1])
        if b[:2] != expected:
            return False
    return True


@dataclass(frozen=True, slots=True)
class ComparableFinancialSeries:
    canonical_instrument_id: str
    as_of: datetime
    metric: FinancialMetric
    scope: StatementScope
    period_type: FinancialPeriodType
    value_basis: FinancialValueBasis
    requested_period_ends: tuple[datetime, ...] | None
    observations: tuple[FinancialMetricObservation, ...]
    candidate_fact_ids: tuple[str, ...]
    selection_fingerprints: tuple[str, ...]
    state: ComparabilityState
    reasons: tuple[str, ...]
    fingerprint: str

    def __post_init__(self):
        if self.fingerprint != content_fingerprint({f.name: getattr(self, f.name) for f in fields(self) if f.name != "fingerprint"}):
            raise ValueError("FINANCIAL_COMPARABLE_SERIES_FINGERPRINT_MISMATCH")
        for value in self.observations:
            value.period_identity.__post_init__()
            value.__post_init__()
            if value.canonical_instrument_id != self.canonical_instrument_id or value.visible_as_of > self.as_of:
                raise ValueError("FINANCIAL_COMPARABLE_SERIES_IDENTITY_OR_PIT_MISMATCH")


@dataclass(frozen=True, slots=True)
class CanonicalFinancialComparability:
    canonical_instrument_id: str
    as_of: datetime
    scope: StatementScope
    facts: tuple[FinancialFact, ...]
    vintage: FinancialFactVintageSelectionBatch
    observations: tuple[FinancialMetricObservation, ...]
    rejected: tuple[tuple[str, str], ...]
    filing_fingerprints: tuple[tuple[str, str], ...]
    complete_input: bool
    fingerprint: str
    contract_id: str = CONTRACT_ID
    contract_version: str = CONTRACT_VERSION

    def __post_init__(self):
        if self.contract_id != CONTRACT_ID or self.contract_version != CONTRACT_VERSION:
            raise ValueError("FINANCIAL_COMPARABILITY_CONTRACT_MISMATCH")
        self.vintage.__post_init__()
        for value in self.observations:
            value.period_identity.__post_init__()
            value.__post_init__()
        if self.fingerprint != comparability_fingerprint(self):
            raise ValueError("FINANCIAL_COMPARABILITY_FINGERPRINT_MISMATCH")

    def anchors(self, period_type: FinancialPeriodType) -> tuple[tuple[int, int, datetime, datetime], ...]:
        basis = FinancialValueBasis.FULL_YEAR if period_type is FinancialPeriodType.ANNUAL else FinancialValueBasis.QUARTER_ONLY
        # Include unavailable/conflicted recent anchors: never retreat to an
        # older complete period simply because the latest facts were rejected.
        return tuple(sorted({fiscal_key(f) for f in self.facts if f.statement_scope is self.scope
            and f.period_type is period_type and f.value_basis is basis and f.available_at <= self.as_of
            and f.period_end <= self.as_of}, key=lambda k: (k[3], k)))

    def series(self, metric: FinancialMetric, period_type: FinancialPeriodType,
               basis: FinancialValueBasis, *, period_ends: tuple[datetime, ...] | None = None) -> ComparableFinancialSeries:
        if period_ends is not None and period_ends != tuple(sorted(set(period_ends))):
            raise ValueError("FINANCIAL_COMPARABILITY_PERIOD_WINDOW_NONCANONICAL")
        candidates = tuple(f for f in self.facts if f.metric is metric and f.statement_scope is self.scope
            and f.period_type is period_type and f.value_basis is basis and f.available_at <= self.as_of
            and f.period_end <= self.as_of and (period_ends is None or f.period_end in period_ends))
        ids = {f.fact_id for f in candidates}
        selected = tuple(s for s in self.vintage.selections if ids.intersection(s.candidate_fact_ids))
        points = tuple(sorted((o for o in self.observations if o.source_fact_id in ids), key=lambda o: (fiscal_key(o)[3], o.source_fact_id)))
        reasons = {reason for fid, reason in self.rejected if fid in ids}
        if not self.complete_input:
            reasons.add("SOURCE_COMPLETENESS_UNPROVEN")
        if self.scope is StatementScope.UNKNOWN:
            reasons.add("SCOPE_SELECTION_POLICY_UNAVAILABLE")
        if not candidates:
            reasons.add("DIRECT_COMPARABLE_METRIC_MISSING")
        if len({representation(o) for o in points}) > 1:
            reasons.add("UNIT_CURRENCY_OR_NORMALIZATION_MISMATCH")
        keys = [fiscal_key(o) for o in points]
        identities = {(k[0], k[3]) if period_type is FinancialPeriodType.POINT_IN_TIME else k[:2] for k in keys}
        if len(identities) != len(keys):
            reasons.add("AMBIGUOUS_FISCAL_PERIOD")
        if period_type is not FinancialPeriodType.POINT_IN_TIME and not consecutive(tuple(keys), quarterly=period_type is FinancialPeriodType.QUARTERLY):
            reasons.add("MISSING_OR_NONCOMPARABLE_FISCAL_PERIOD")
        conflicted = any(s.status in {VintageStatus.CONFLICTED, VintageStatus.INVALID_LINEAGE} for s in selected) or "AMBIGUOUS_FISCAL_PERIOD" in reasons
        state = ComparabilityState.EVIDENCE_CONFLICTED if conflicted else ComparabilityState.INSUFFICIENT_DATA if reasons or not points else ComparabilityState.READY
        values = dict(canonical_instrument_id=self.canonical_instrument_id, as_of=self.as_of, metric=metric,
            scope=self.scope, period_type=period_type, value_basis=basis, requested_period_ends=period_ends, observations=points,
            candidate_fact_ids=tuple(sorted(ids)), selection_fingerprints=tuple(sorted(s.fingerprint for s in selected)),
            state=state, reasons=tuple(sorted(reasons)))
        return ComparableFinancialSeries(**values, fingerprint=content_fingerprint(values))


def comparability_fingerprint(value: CanonicalFinancialComparability) -> str:
    return content_fingerprint({f.name: getattr(value, f.name) for f in fields(value) if f.name != "fingerprint"})


def assemble_financial_comparability(facts: tuple[FinancialFact, ...], filings: tuple[CorporateFiling, ...], *,
        canonical_instrument_id: str, as_of: datetime,
        preferred_scope: StatementScope = StatementScope.CONSOLIDATED,
        complete_input: bool = True) -> CanonicalFinancialComparability:
    if not canonical_instrument_id or as_of.tzinfo is None or as_of.utcoffset() is None:
        raise ValueError("FINANCIAL_COMPARABILITY_REQUEST_INVALID")
    if preferred_scope not in {StatementScope.CONSOLIDATED, StatementScope.STANDALONE}:
        raise ValueError("FINANCIAL_COMPARABILITY_EXACT_SCOPE_REQUIRED")
    as_of = as_of.astimezone(UTC)
    by_id = {}
    for fact in facts:
        fact.__post_init__()
        fact.instrument.__post_init__()
        if fact.instrument.instrument_id != canonical_instrument_id:
            raise ValueError("FINANCIAL_COMPARABILITY_INSTRUMENT_MISMATCH")
        if fact.fact_id in by_id and canonical_json(by_id[fact.fact_id]) != canonical_json(fact):
            raise ValueError("FINANCIAL_COMPARABILITY_DUPLICATE_ID_CONFLICT")
        by_id[fact.fact_id] = fact
    values = tuple(by_id[key] for key in sorted(by_id))
    identities = {(f.instrument.exchange, f.instrument.symbol, f.instrument.isin, f.instrument.instrument_type, f.instrument.currency)
        for f in values if f.available_at <= as_of}
    if len(identities) > 1:
        raise ValueError("FINANCIAL_COMPARABILITY_CANONICAL_IDENTITY_CONFLICT")
    scoped = {f.statement_scope for f in values if f.fact_kind is FundamentalFactKind.REPORTED
        and f.available_at <= as_of and f.period_end <= as_of}
    scope = preferred_scope if preferred_scope in scoped else StatementScope.STANDALONE if StatementScope.STANDALONE in scoped else StatementScope.UNKNOWN
    filing_map = {}
    for filing in filings:
        if filing.filing_id in filing_map and filing_map[filing.filing_id] != filing:
            raise ValueError("FINANCIAL_COMPARABILITY_FILING_ID_CONFLICT")
        filing_map[filing.filing_id] = filing
    vintage = select_financial_fact_vintages(values, canonical_instrument_id=canonical_instrument_id,
        as_of=as_of, policy=CURRENT_FROZEN_FINANCIAL_FACT_VINTAGE_SELECTION_POLICY)
    rejected = []
    observations = []
    for selection in vintage.selections:
        if selection.status is not VintageStatus.SELECTED:
            rejected.extend((fid, reason.value) for fid in selection.candidate_fact_ids
                if fid not in selection.excluded_future_fact_ids for reason in selection.reasons)
            continue
        fact = by_id[selection.selected_fact_id]
        filing = filing_map.get(fact.filing_id)
        reasons = []
        if fact.fact_kind is not FundamentalFactKind.REPORTED:
            reasons.append("DIRECT_REPORTED_METRIC_REQUIRED")
        if filing is None or filing.instrument.instrument_id != canonical_instrument_id or filing.filing_type is not FilingType.FINANCIAL_RESULTS:
            reasons.append("EXACT_FINANCIAL_FILING_REQUIRED")
        elif (filing.source_quality not in {PrimarySourceQuality.PRIMARY_EXCHANGE, PrimarySourceQuality.PRIMARY_ISSUER}
              or filing.source != fact.source or filing.announced_at != fact.published_at or filing.received_at != fact.received_at
              or max(filing.announced_at, filing.received_at) > as_of):
            reasons.append("FILING_SOURCE_OR_PIT_LINEAGE_INVALID")
        if fact.period_end > as_of:
            reasons.append("FUTURE_PERIOD_EXCLUDED")
        if not period_valid(fact):
            reasons.append("EXACT_FISCAL_PERIOD_REQUIRED")
        if fact.currency != "INR" or fact.unit != "INR" or not isinstance(fact.scale, NumericScale):
            reasons.append("UNIT_CURRENCY_POLICY_UNAVAILABLE")
        if FinancialQualityFlag.INCONSISTENT in fact.quality_flags:
            reasons.append("INCONSISTENT_FACT_QUALITY")
        if reasons:
            rejected.extend((fact.fact_id, r) for r in reasons)
            continue
        result = materialize_financial_metric_observation(fact, selection=selection,
            schema=CURRENT_FROZEN_FINANCIAL_METRIC_OBSERVATION_SCHEMA)
        if result.observation is None:
            rejected.extend((fact.fact_id, r.value) for r in result.reasons)
        else:
            observations.append(result.observation)
    payload = dict(canonical_instrument_id=canonical_instrument_id, as_of=as_of, scope=scope, facts=values,
        vintage=vintage, observations=tuple(sorted(observations, key=lambda o: o.source_fact_id)),
        rejected=tuple(sorted(set(rejected))), filing_fingerprints=tuple(sorted((fid, content_fingerprint(f)) for fid, f in filing_map.items())),
        complete_input=complete_input, contract_id=CONTRACT_ID, contract_version=CONTRACT_VERSION)
    return CanonicalFinancialComparability(**payload, fingerprint=content_fingerprint(payload))
