"""Certified financial inputs for nine existing diagnostics, not new evaluators."""
from __future__ import annotations

from dataclasses import dataclass, fields
from datetime import UTC
from math import isfinite

from app.analysis.models import AnalysisStatus
from app.analysis.series import price_bar_series
from app.domain.models import (
    AsOfSnapshot, DataQuality, FinancialObservation, FinancialPeriodType as LegacyPeriod,
    Freshness, FreshnessStatus, Instrument, ObservationKind, Provenance,
    ValidationResult, ValidationStatus,
)
from app.fundamentals.diagnostic_comparability import (
    CanonicalFinancialComparability, ComparabilityState as State, consecutive,
    content_fingerprint, fiscal_key, representation,
)
from app.fundamentals.financial_metric_observation_schema import FinancialMetricObservation
from app.fundamentals.models import FinancialMetric as M, FinancialPeriodType as P, FinancialValueBasis as B, NumericScale
from app.historical.pit_company_type_classification_activation import (
    PitCompanyType, PitCompanyTypeClassificationReceipt, PitCompanyTypeClassificationState,
)

APPROVED_FINANCIAL_RULE_IDS = (16, 17, 18, 19, 20, 24, 25, 26, 29)
# Input annotations only. The sole Rule registry and evaluator formulas are unchanged.
_PAYLOAD = {
    M.REVENUE: "revenue", M.EBITDA: "ebitda", M.EBIT: "ebit", M.PAT: "pat", M.EPS_BASIC: "eps",
    M.CFO: "operating_cash_flow", M.CAPEX: "capex", M.TOTAL_DEBT: "total_debt", M.TOTAL_EQUITY: "total_equity",
    M.CASH_AND_EQUIVALENTS: "cash", M.FINANCE_COST: "interest_expense", M.RECEIVABLES: "receivables",
    M.INVENTORY: "inventory", M.PAYABLES: "payables",
}
_BALANCES = frozenset({M.TOTAL_DEBT, M.TOTAL_EQUITY, M.CASH_AND_EQUIVALENTS, M.RECEIVABLES, M.INVENTORY, M.PAYABLES})
_REQUIRED = {
    16: (M.REVENUE, M.EBITDA, M.PAT, M.EPS_BASIC),
    17: (M.PAT, M.EBIT, M.TOTAL_EQUITY, M.TOTAL_DEBT, M.CASH_AND_EQUIVALENTS),
    18: (M.CFO, M.CAPEX, M.PAT),
    19: (M.TOTAL_DEBT, M.TOTAL_EQUITY, M.CASH_AND_EQUIVALENTS, M.EBIT, M.FINANCE_COST),
    20: (M.REVENUE, M.RECEIVABLES, M.INVENTORY, M.PAYABLES),
    24: (M.REVENUE,), 25: (M.REVENUE, M.EBITDA, M.PAT, M.EPS_BASIC),
    26: (M.REVENUE, M.EBITDA), 29: (M.EPS_BASIC,),
}


@dataclass(frozen=True, slots=True)
class FinancialRuleInput:
    rule_id: int
    state: State
    reasons: tuple[str, ...]
    metric_states: tuple[tuple[str, State, tuple[str, ...]], ...]
    source_fingerprint: str
    market_fingerprint: str | None
    fact_ids: tuple[str, ...]
    snapshot: AsOfSnapshot | None
    fingerprint: str

    def __post_init__(self):
        if self.fingerprint != content_fingerprint({f.name: getattr(self, f.name) for f in fields(self) if f.name != "fingerprint"}):
            raise ValueError("FINANCIAL_RULE_INPUT_FINGERPRINT_MISMATCH")


@dataclass(frozen=True, slots=True)
class CanonicalFinancialDiagnosticInput:
    comparable: CanonicalFinancialComparability
    company_type: PitCompanyTypeClassificationReceipt | None = None

    @property
    def canonical_instrument_id(self):
        return self.comparable.canonical_instrument_id

    @property
    def as_of(self):
        return self.comparable.as_of

    @property
    def fingerprint(self):
        return content_fingerprint((self.comparable.fingerprint, None if self.company_type is None else self.company_type.fingerprint))

    def __post_init__(self):
        self.comparable.__post_init__()
        if self.company_type is not None:
            self.company_type.verify()
            if self.company_type.canonical_instrument_id != self.canonical_instrument_id or self.company_type.evaluated_as_of != self.as_of:
                raise ValueError("FINANCIAL_DIAGNOSTIC_COMPANY_TYPE_PIT_MISMATCH")

    def rule_input(self, rule_id: int, market: AsOfSnapshot | None = None) -> FinancialRuleInput:
        if rule_id not in APPROVED_FINANCIAL_RULE_IDS:
            raise ValueError("FINANCIAL_DIAGNOSTIC_RULE_OUT_OF_SCOPE")
        self.__post_init__()
        c = self.comparable
        quarterly = rule_id in {24, 25, 26}
        period = P.QUARTERLY if quarterly else P.ANNUAL
        basis = B.QUARTER_ONLY if quarterly else B.FULL_YEAR
        depth = 5 if quarterly else 6 if rule_id == 16 else 2 if rule_id in {17, 18, 20} else 1
        anchors = c.anchors(period)[-depth:]
        minimum = depth if rule_id in {16, 24, 25, 26} else 1
        reasons = set()
        if len(anchors) < minimum:
            reasons.add("INSUFFICIENT_COMPARABLE_HISTORY")
        if not consecutive(anchors, quarterly=quarterly) or len({k[:2] for k in anchors}) != len(anchors):
            reasons.add("MISSING_OR_AMBIGUOUS_FISCAL_PERIOD")
        metrics = []
        admitted = {}
        for metric in _REQUIRED[rule_id]:
            balance = metric in _BALANCES
            series = c.series(metric, P.POINT_IN_TIME if balance else period, B.UNKNOWN if balance else basis,
                period_ends=tuple(sorted({key[3] for key in anchors})))
            metric_reasons = set(series.reasons)
            points = []
            for anchor in anchors:
                if rule_id in {17, 20} and not balance and anchor != anchors[-1]:
                    continue
                if balance:
                    match = [o for o in series.observations if
                        o.period_identity.fiscal_year == anchor[0] and o.period_identity.period_end == anchor[3]]
                else:
                    match = [o for o in series.observations if fiscal_key(o) == anchor]
                if len(match) == 1:
                    points.append((anchor, match[0]))
                elif len(match) > 1:
                    metric_reasons.add("AMBIGUOUS_FISCAL_PERIOD")
                else:
                    if not (balance and rule_id in {17, 20} and anchor != anchors[-1]):
                        metric_reasons.add("REQUIRED_FISCAL_PERIOD_MISSING")
            if len(anchors) < minimum:
                metric_reasons.add("INSUFFICIENT_COMPARABLE_HISTORY")
            if any(not isfinite(float(o.value)) for _, o in points):
                metric_reasons.add("LEGACY_NUMERIC_REPRESENTATION_UNAVAILABLE")
            # Match existing evaluator denominator/endpoint validity, not a new
            # economic threshold. Missing is never changed to zero.
            positive = rule_id in {16, 24, 25} or metric is M.REVENUE and rule_id in {20, 26}
            positive = positive or rule_id in {17, 19} and metric in {M.TOTAL_EQUITY, M.FINANCE_COST}
            positive = positive or rule_id == 29 and metric is M.EPS_BASIC
            positive_points = points
            if rule_id in {16, 24} and points:
                positive_points = (points[0], points[-1])
            elif rule_id == 25 and len(points) >= 5:
                positive_points = (points[-1], points[-2], points[-5])
            if positive and any(o.value <= 0 for _, o in positive_points):
                metric_reasons.add("EXISTING_EVALUATOR_POSITIVE_INPUT_REQUIRED")
            if rule_id == 18 and metric is M.PAT and any(o.value == 0 for _, o in points):
                metric_reasons.add("EXISTING_EVALUATOR_NONZERO_PAT_REQUIRED")
            state = State.EVIDENCE_CONFLICTED if series.state is State.EVIDENCE_CONFLICTED or "AMBIGUOUS_FISCAL_PERIOD" in metric_reasons else State.INSUFFICIENT_DATA if metric_reasons or not points else State.READY
            metrics.append((metric.value, state, tuple(sorted(metric_reasons))))
            if state is State.READY:
                admitted[metric] = tuple(points)
        # Monetary ratios/subtractions require cross-metric representation too.
        monetary = {representation(o) for m, values in admitted.items() if m is not M.EPS_BASIC for _, o in values}
        if len(monetary) > 1 and rule_id in {17, 18, 19, 20, 26}:
            reasons.add("CROSS_METRIC_UNIT_CURRENCY_MISMATCH")
        if rule_id in {17, 18, 19, 20, 26}:
            classification = self.company_type
            if classification is None or classification.state is not PitCompanyTypeClassificationState.CLASSIFIED:
                reasons.add("POLICY_DEFINITION_MISSING:EXACT_COMPANY_TYPE_APPLICABILITY")
            elif classification.company_type is not PitCompanyType.NON_FINANCIAL:
                reasons.add("POLICY_DEFINITION_MISSING:" + classification.company_type.value + "_RULE_BRANCH")
        if rule_id == 18 and M.CAPEX in admitted:
            reasons.add("POLICY_DEFINITION_MISSING:CAPEX_SIGN_BRIDGE")
        if rule_id == 17 and {M.TOTAL_EQUITY, M.TOTAL_DEBT, M.CASH_AND_EQUIVALENTS} <= admitted.keys():
            capitals = []
            for anchor in anchors:
                values = {m: o.value for m, entries in admitted.items() for key, o in entries if key == anchor}
                if {M.TOTAL_EQUITY, M.TOTAL_DEBT, M.CASH_AND_EQUIVALENTS} <= values.keys():
                    capitals.append(values[M.TOTAL_EQUITY] + values[M.TOTAL_DEBT] - values[M.CASH_AND_EQUIVALENTS])
            if not capitals or sum(capitals) <= 0:
                reasons.add("EXISTING_EVALUATOR_POSITIVE_CAPITAL_REQUIRED")
        if rule_id == 20:
            metrics.append(("CCC", State.POLICY_BLOCKED, ("CANONICAL_COGS_MAPPING_UNAVAILABLE",)))
        if rule_id == 24:
            metrics.append(("ORGANIC_VS_ONE_OFF", State.POLICY_BLOCKED, ("CANONICAL_ATTRIBUTION_UNAVAILABLE",)))
        if rule_id == 26:
            metrics.append(("GROSS_MARGIN", State.POLICY_BLOCKED, ("CANONICAL_GROSS_MARGIN_MAPPING_UNAVAILABLE",)))
        if rule_id == 29:
            prices = price_bar_series(market, self.canonical_instrument_id) if market is not None else None
            if market is None or market.as_of_timestamp != self.as_of or prices.status is not AnalysisStatus.VALID or not prices.bars:
                reasons.add("PIT_ALIGNED_PRICE_UNAVAILABLE")
            elif any(not isfinite(float(x.payload["close"])) or float(x.payload["close"]) <= 0 for x in prices.bars):
                reasons.add("PIT_ALIGNED_PRICE_INVALID")
            eps = admitted.get(M.EPS_BASIC, ())
            if eps and any(o.scale is not NumericScale.UNITS for _, o in eps):
                reasons.add("PRICE_EPS_RAW_INR_UNIT_ALIGNMENT_REQUIRED")
            metrics.extend((label, State.POLICY_BLOCKED, (reason,)) for label, reason in (
                ("FORWARD_PE", "CANONICAL_FORWARD_EPS_UNAVAILABLE"),
                ("PEG", "CANONICAL_CONFIGURED_GROWTH_UNAVAILABLE"),
                ("EV_EBITDA", "PERIOD_END_SHARES_MAPPING_UNAVAILABLE"),
                ("PB", "PERIOD_END_SHARES_MAPPING_UNAVAILABLE")))
            pe_ready = bool(eps) and not reasons
            metrics.append(("PE", State.READY if pe_ready else State.INSUFFICIENT_DATA, tuple(sorted(reasons))))
        required = set(_REQUIRED[rule_id])
        # Existing 25 permits metric-level partiality; 20 permits DSO-only.
        enough = bool(admitted) if rule_id == 25 else {M.REVENUE, M.RECEIVABLES} <= admitted.keys() if rule_id == 20 else required <= admitted.keys()
        conflicted = any(state is State.EVIDENCE_CONFLICTED for _, state, _ in metrics)
        if conflicted:
            reasons.add("EVIDENCE_CONFLICTED")
        if not enough:
            reasons.add("REQUIRED_DIRECT_METRICS_UNAVAILABLE")
        policy_blocked = any(r.startswith("POLICY_DEFINITION_MISSING") for r in reasons)
        state = State.EVIDENCE_CONFLICTED if conflicted else State.POLICY_BLOCKED if policy_blocked else State.INSUFFICIENT_DATA if reasons else State.READY
        if state is State.READY and (rule_id in {20, 24, 26, 29} or len(admitted) < len(required)):
            state = State.PARTIAL
        snapshot = _snapshot(c, anchors, admitted) if state in {State.READY, State.PARTIAL} else None
        fact_ids = tuple(sorted({o.source_fact_id for values in admitted.values() for _, o in values}))
        payload = dict(rule_id=rule_id, state=state, reasons=tuple(sorted(reasons)), metric_states=tuple(metrics),
            source_fingerprint=self.fingerprint, market_fingerprint=content_fingerprint(market) if rule_id == 29 and market is not None else None,
            fact_ids=fact_ids, snapshot=snapshot)
        return FinancialRuleInput(**payload, fingerprint=content_fingerprint(payload))


def _snapshot(c, anchors, admitted):
    observations = []
    for anchor in anchors:
        chosen = {metric: o for metric, values in admitted.items() for key, o in values if key == anchor}
        if not chosen:
            continue
        source = next(f for f in c.facts if f.fact_id == next(iter(chosen.values())).source_fact_id)
        published = max(o.published_at for o in chosen.values())
        received = max(o.received_at for o in chosen.values())
        quarterly = any(o.period_identity.period_type is P.QUARTERLY for o in chosen.values())
        ids = tuple(sorted(o.source_fact_id for o in chosen.values()))
        payload = {"period_end": anchor[3].astimezone(UTC).isoformat(), "period_start": anchor[2].astimezone(UTC).isoformat(),
            "fiscal_year": anchor[0], "fiscal_quarter": anchor[1] or None,
            "publication_timestamp": published.astimezone(UTC).isoformat(), "period_type": "quarterly" if quarterly else "annual",
            "value_basis": "QUARTER_ONLY" if quarterly else "FULL_YEAR", "statement_scope": c.scope.value,
            "fact_ids": ids, "filing_ids": tuple(sorted({o.filing_id for o in chosen.values()})),
            "comparability_fingerprint": c.fingerprint,
            "metric_lineage": tuple((m.value, o.fingerprint, o.selection_result_fingerprint, representation(o)) for m, o in sorted(chosen.items()))}
        payload.update({_PAYLOAD[m]: float(o.value) for m, o in chosen.items()})
        fresh = Freshness(FreshnessStatus.UNKNOWN, published, c.as_of, (c.as_of - published).total_seconds(), None)
        provenance = Provenance("canonical_financial_comparable", source.source_reference, published, received, DataQuality.HIGH, fresh, payload)
        observations.append(FinancialObservation("comparable-financial:" + content_fingerprint(payload),
            Instrument(source.instrument.instrument_id, source.instrument.symbol, source.instrument.exchange.value, source.instrument.isin),
            ObservationKind.FUNDAMENTAL, payload, provenance, ValidationResult(ValidationStatus.VALID, c.as_of, (), fresh),
            None, anchor[3], published, LegacyPeriod.QUARTERLY if quarterly else LegacyPeriod.ANNUAL, None))
    return AsOfSnapshot("comparable-financial:" + content_fingerprint(tuple(o.id for o in observations)),
        c.as_of, c.as_of, "canonical-financial-comparability-v1", tuple(observations))
