"""Frozen factual comparability governance for future Shared-Brain research.

This module is static policy metadata only.  It deliberately does not build a
research state, compare observations, calculate a delta, or produce thesis,
opportunity, recommendation, alert, or execution semantics.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from app.historical.guard import manifest_fingerprint


class BrainResearchComparabilityPolicyApprovalStatus(StrEnum):
    PROPOSED = "PROPOSED"
    APPROVED = "APPROVED"


class ResearchComparisonMode(StrEnum):
    KNOWLEDGE_AT_THE_TIME = "KNOWLEDGE_AT_THE_TIME"


class ResearchSourceEligibility(StrEnum):
    PIT_REBUILDABLE = "PIT_REBUILDABLE"
    DURABLE_ARTIFACT_ONLY = "DURABLE_ARTIFACT_ONLY"
    CURRENT_ONLY = "CURRENT_ONLY"
    REFERENCE_ONLY = "REFERENCE_ONLY"
    UNSUPPORTED = "UNSUPPORTED"


class ResearchComparabilityStatus(StrEnum):
    COMPARABLE = "COMPARABLE"
    INSUFFICIENT = "INSUFFICIENT"
    NON_COMPARABLE = "NON_COMPARABLE"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class ResearchComparabilityDomain(StrEnum):
    FINANCIAL_RAW = "FINANCIAL_RAW"
    NEWS_CATALYST = "NEWS_CATALYST"
    OFFICIAL_DELIVERY = "OFFICIAL_DELIVERY"
    CORPORATE_ACTION = "CORPORATE_ACTION"
    MARKET_PRICE = "MARKET_PRICE"
    SECTOR_IDENTITY = "SECTOR_IDENTITY"
    MARKET_REGIME = "MARKET_REGIME"
    PRE_BREAKOUT_SETUP = "PRE_BREAKOUT_SETUP"
    PRE_BREAKOUT_CANDIDATE = "PRE_BREAKOUT_CANDIDATE"
    ENTRY_ECONOMICS = "ENTRY_ECONOMICS"
    DIAGNOSTIC = "DIAGNOSTIC"
    DECISION_SCORE = "DECISION_SCORE"
    RELIABILITY = "RELIABILITY"
    MACRO_STATE = "MACRO_STATE"
    SECTOR_RS = "SECTOR_RS"
    SECTOR_BREADTH = "SECTOR_BREADTH"
    SECTOR_RANK = "SECTOR_RANK"
    SECTOR_TOP3 = "SECTOR_TOP3"
    TECHNICAL_MATERIALIZATION = "TECHNICAL_MATERIALIZATION"
    OWNERSHIP_PERCENTAGE = "OWNERSHIP_PERCENTAGE"
    VALUATION = "VALUATION"
    CORPORATE_ACTION_REFERENCE = "CORPORATE_ACTION_REFERENCE"


class ResearchFoundationalIdentityRule(StrEnum):
    SAME_CANONICAL_INSTRUMENT = "SAME_CANONICAL_INSTRUMENT"
    VALID_TIMEZONE_AWARE_TEMPORAL_ORDER = "VALID_TIMEZONE_AWARE_TEMPORAL_ORDER"
    CONSISTENT_SOURCE_STATE_LINEAGE = "CONSISTENT_SOURCE_STATE_LINEAGE"
    VALID_STATE_METHODOLOGY_IDENTITY = "VALID_STATE_METHODOLOGY_IDENTITY"
    SAME_COMPARISON_MODE = "SAME_COMPARISON_MODE"


class ResearchNonComparableCase(StrEnum):
    REQUIRED_VERSION_OR_METHODOLOGY_MISMATCH = "REQUIRED_VERSION_OR_METHODOLOGY_MISMATCH"
    FINANCIAL_SCOPE_MISMATCH = "FINANCIAL_SCOPE_MISMATCH"
    FINANCIAL_PERIOD_OR_BASIS_MISMATCH = "FINANCIAL_PERIOD_OR_BASIS_MISMATCH"
    FINANCIAL_UNIT_SCALE_OR_DIMENSION_MISMATCH = "FINANCIAL_UNIT_SCALE_OR_DIMENSION_MISMATCH"
    UNSUPPORTED_FINANCIAL_CONVERSION = "UNSUPPORTED_FINANCIAL_CONVERSION"
    OWNERSHIP_PERCENTAGES_UNSUPPORTED = "OWNERSHIP_PERCENTAGES_UNSUPPORTED"
    PRICE_ACTION_BASIS_UNPROVEN = "PRICE_ACTION_BASIS_UNPROVEN"
    TECHNICAL_WINDOW_OR_FORMULA_MISMATCH = "TECHNICAL_WINDOW_OR_FORMULA_MISMATCH"
    SECTOR_DERIVED_CURRENT_ONLY = "SECTOR_DERIVED_CURRENT_ONLY"
    SETUP_POLICY_FINGERPRINT_MISMATCH = "SETUP_POLICY_FINGERPRINT_MISMATCH"
    CONFLICTED_RELIABILITY = "CONFLICTED_RELIABILITY"
    HISTORICAL_INTEGRITY_INVALID = "HISTORICAL_INTEGRITY_INVALID"
    PROJECTED_NATIVE_STATE_RECONSTRUCTION = "PROJECTED_NATIVE_STATE_RECONSTRUCTION"


class ResearchEvidencePrecondition(StrEnum):
    RELIABILITY_CONFLICTED = "RELIABILITY_CONFLICTED"
    HISTORICAL_INTEGRITY_INVALID = "HISTORICAL_INTEGRITY_INVALID"
    REQUIRED_EVIDENCE_UNAVAILABLE = "REQUIRED_EVIDENCE_UNAVAILABLE"
    EVIDENCE_STALE = "EVIDENCE_STALE"


class ResearchComparabilityExclusion(StrEnum):
    THESIS_DIRECTION = "THESIS_DIRECTION"
    OPPORTUNITY_DIRECTION = "OPPORTUNITY_DIRECTION"
    INVESTMENT_RISK_DIRECTION = "INVESTMENT_RISK_DIRECTION"
    BULLISH_BEARISH = "BULLISH_BEARISH"
    RECOMMENDATION = "RECOMMENDATION"
    ALERT_AUTHORIZATION = "ALERT_AUTHORIZATION"
    EXECUTION_DECISION = "EXECUTION_DECISION"
    BUY_HOLD_SELL_TRIM_ROTATE = "BUY_HOLD_SELL_TRIM_ROTATE"


class FinancialObservationSlotIdentityComponent(StrEnum):
    """Frozen v2 accounting-slot fields; never a matcher implementation."""

    CANONICAL_INSTRUMENT = "CANONICAL_INSTRUMENT"
    FACT_KIND = "FACT_KIND"
    METRIC = "METRIC"
    STATEMENT_SCOPE = "STATEMENT_SCOPE"
    PERIOD_TYPE = "PERIOD_TYPE"
    VALUE_BASIS = "VALUE_BASIS"
    PERIOD_START = "PERIOD_START"
    PERIOD_END = "PERIOD_END"
    FISCAL_YEAR = "FISCAL_YEAR"
    FISCAL_QUARTER = "FISCAL_QUARTER"
    VALUE_DIMENSION = "VALUE_DIMENSION"
    CURRENCY = "CURRENCY"
    UNIT = "UNIT"
    SCALE = "SCALE"
    NORMALIZATION_IDENTITY = "NORMALIZATION_IDENTITY"
    PERIOD_FINGERPRINT = "PERIOD_FINGERPRINT"
    SOURCE_ROLE = "SOURCE_ROLE"
    OBSERVATION_SCHEMA_IDENTITY = "OBSERVATION_SCHEMA_IDENTITY"


class FinancialObservationLineageOnlyField(StrEnum):
    SOURCE_FACT_ID = "SOURCE_FACT_ID"
    SOURCE_FACT_SEMANTIC_FINGERPRINT = "SOURCE_FACT_SEMANTIC_FINGERPRINT"
    OBSERVATION_FINGERPRINT = "OBSERVATION_FINGERPRINT"


class FinancialObservationSourceRole(StrEnum):
    FINANCIAL_EVIDENCE_REFERENCE = "FINANCIAL_EVIDENCE_REFERENCE"
    FINANCIAL_NUMERIC_OBSERVATION = "FINANCIAL_NUMERIC_OBSERVATION"


class FinancialObservationPeriodDisposition(StrEnum):
    COMPLETE_NUMERIC_COMPARISON_ELIGIBLE = "COMPLETE_NUMERIC_COMPARISON_ELIGIBLE"
    PARTIAL_NUMERIC_COMPARISON_INSUFFICIENT = "PARTIAL_NUMERIC_COMPARISON_INSUFFICIENT"
    INSUFFICIENT_NOT_ADMISSIBLE = "INSUFFICIENT_NOT_ADMISSIBLE"


class FinancialObservationMatchingRequirement(StrEnum):
    FULL_SEMANTIC_SLOT_KEY = "FULL_SEMANTIC_SLOT_KEY"
    EXACT_KEY_PAIRING = "EXACT_KEY_PAIRING"
    PREVIOUS_ONLY_REMOVED = "PREVIOUS_ONLY_REMOVED"
    CURRENT_ONLY_ADDED = "CURRENT_ONLY_ADDED"
    NO_METRIC_LABEL_FALLBACK = "NO_METRIC_LABEL_FALLBACK"
    NO_SAME_LABEL_ZIP_FALLBACK = "NO_SAME_LABEL_ZIP_FALLBACK"
    DUPLICATE_FULL_SLOT_FAIL_CLOSED = "DUPLICATE_FULL_SLOT_FAIL_CLOSED"


@dataclass(frozen=True, slots=True)
class ResearchSourceEligibilityRule:
    """One audited source boundary, never an operational comparator rule."""

    domain: ResearchComparabilityDomain
    eligibility: ResearchSourceEligibility
    source_boundary: str
    prerequisites: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.source_boundary:
            raise ValueError("BRAIN_RESEARCH_COMPARABILITY_SOURCE_BOUNDARY_REQUIRED")
        if self.prerequisites != tuple(sorted(set(self.prerequisites))):
            raise ValueError("BRAIN_RESEARCH_COMPARABILITY_SOURCE_PREREQUISITES_NONCANONICAL")


@dataclass(frozen=True, slots=True)
class ResearchDomainComparabilityRule:
    """Identity parity requirements for a factual research dimension."""

    domain: ResearchComparabilityDomain
    required_identity: tuple[str, ...]
    non_comparable_cases: tuple[ResearchNonComparableCase, ...]

    def __post_init__(self) -> None:
        if not self.required_identity:
            raise ValueError("BRAIN_RESEARCH_COMPARABILITY_IDENTITY_REQUIRED")
        if self.required_identity != tuple(sorted(set(self.required_identity))):
            raise ValueError("BRAIN_RESEARCH_COMPARABILITY_IDENTITY_NONCANONICAL")
        if self.non_comparable_cases != tuple(sorted(set(self.non_comparable_cases), key=lambda value: value.value)):
            raise ValueError("BRAIN_RESEARCH_COMPARABILITY_CASES_NONCANONICAL")


@dataclass(frozen=True, slots=True)
class ResearchEvidencePreconditionRule:
    """Frozen factual safety disposition; it does not compare an observation."""

    condition: ResearchEvidencePrecondition
    status: ResearchComparabilityStatus
    domain_specific_rule_required: bool = False

    def __post_init__(self) -> None:
        if self.condition is ResearchEvidencePrecondition.EVIDENCE_STALE:
            if self.status is not ResearchComparabilityStatus.INSUFFICIENT or not self.domain_specific_rule_required:
                raise ValueError("BRAIN_RESEARCH_COMPARABILITY_STALE_DOMAIN_RULE_REQUIRED")
        elif self.domain_specific_rule_required:
            raise ValueError("BRAIN_RESEARCH_COMPARABILITY_PRECONDITION_DOMAIN_RULE_INVALID")


@dataclass(frozen=True, slots=True)
class FinancialObservationComparabilityRule:
    """Frozen v2 financial requirements; it does not compare observations."""

    domain: ResearchComparabilityDomain
    bundle_schema_id: str
    bundle_schema_version: str
    bundle_schema_fingerprint: str
    observation_schema_id: str
    observation_schema_version: str
    observation_schema_fingerprint: str
    selector_policy_id: str
    selector_policy_version: str
    selector_policy_fingerprint: str
    knowledge_mode: ResearchComparisonMode
    selector_as_of_exact_required: bool
    visible_as_of_must_not_exceed_state_as_of: bool
    missing_selector_attestation_status: ResearchComparabilityStatus
    contradictory_selector_attestation_disposition: str
    slot_identity_components: tuple[FinancialObservationSlotIdentityComponent, ...]
    lineage_only_fields: tuple[FinancialObservationLineageOnlyField, ...]
    source_roles: tuple[FinancialObservationSourceRole, ...]
    reference_numeric_pairing_prohibited: bool
    period_dispositions: tuple[FinancialObservationPeriodDisposition, ...]
    matching_requirements: tuple[FinancialObservationMatchingRequirement, ...]

    def __post_init__(self) -> None:
        if self.domain is not ResearchComparabilityDomain.FINANCIAL_RAW:
            raise ValueError("BRAIN_RESEARCH_COMPARABILITY_FINANCIAL_DOMAIN_REQUIRED")
        if not all((
            self.bundle_schema_id, self.bundle_schema_version, self.bundle_schema_fingerprint,
            self.observation_schema_id, self.observation_schema_version, self.observation_schema_fingerprint,
            self.selector_policy_id, self.selector_policy_version, self.selector_policy_fingerprint,
            self.contradictory_selector_attestation_disposition,
        )):
            raise ValueError("BRAIN_RESEARCH_COMPARABILITY_FINANCIAL_LINEAGE_REQUIRED")
        if self.knowledge_mode is not ResearchComparisonMode.KNOWLEDGE_AT_THE_TIME:
            raise ValueError("BRAIN_RESEARCH_COMPARABILITY_FINANCIAL_KNOWLEDGE_MODE_REQUIRED")
        if not self.selector_as_of_exact_required or not self.visible_as_of_must_not_exceed_state_as_of:
            raise ValueError("BRAIN_RESEARCH_COMPARABILITY_FINANCIAL_PIT_RULE_REQUIRED")
        if self.missing_selector_attestation_status is not ResearchComparabilityStatus.INSUFFICIENT:
            raise ValueError("BRAIN_RESEARCH_COMPARABILITY_FINANCIAL_MISSING_ATTESTATION_REQUIRED")
        if self.slot_identity_components != tuple(FinancialObservationSlotIdentityComponent):
            raise ValueError("BRAIN_RESEARCH_COMPARABILITY_FINANCIAL_SLOT_IDENTITY_REQUIRED")
        if self.lineage_only_fields != tuple(FinancialObservationLineageOnlyField):
            raise ValueError("BRAIN_RESEARCH_COMPARABILITY_FINANCIAL_LINEAGE_ONLY_REQUIRED")
        if self.source_roles != tuple(FinancialObservationSourceRole) or not self.reference_numeric_pairing_prohibited:
            raise ValueError("BRAIN_RESEARCH_COMPARABILITY_FINANCIAL_SOURCE_ROLE_REQUIRED")
        if self.period_dispositions != tuple(FinancialObservationPeriodDisposition):
            raise ValueError("BRAIN_RESEARCH_COMPARABILITY_FINANCIAL_PERIOD_DISPOSITION_REQUIRED")
        if self.matching_requirements != tuple(FinancialObservationMatchingRequirement):
            raise ValueError("BRAIN_RESEARCH_COMPARABILITY_FINANCIAL_MATCHING_REQUIRED")


@dataclass(frozen=True, slots=True)
class FrozenBrainResearchComparabilityPolicy:
    """Approved but deliberately unselected and inactive factual policy."""

    policy_id: str
    version: str
    proposal_policy_id: str
    proposal_version: str
    approval_status: BrainResearchComparabilityPolicyApprovalStatus
    approved_by: str
    selected_for_future_comparator: bool
    active: bool
    comparison_mode: ResearchComparisonMode
    restated_history_enabled: bool
    dimension_local_failure: bool
    no_cross_version_equivalence: bool
    native_typed_lineage_required: bool
    missing_is_not_zero: bool
    source_eligibility_vocabulary: tuple[ResearchSourceEligibility, ...]
    comparability_status_vocabulary: tuple[ResearchComparabilityStatus, ...]
    foundational_identity_rules: tuple[ResearchFoundationalIdentityRule, ...]
    source_rules: tuple[ResearchSourceEligibilityRule, ...]
    domain_rules: tuple[ResearchDomainComparabilityRule, ...]
    evidence_preconditions: tuple[ResearchEvidencePreconditionRule, ...]
    non_comparable_cases: tuple[ResearchNonComparableCase, ...]
    exclusions: tuple[ResearchComparabilityExclusion, ...]
    provenance: tuple[tuple[str, str], ...]
    fingerprint: str
    predecessor_policy_id: str | None = None
    predecessor_policy_version: str | None = None
    predecessor_policy_fingerprint: str | None = None
    financial_observation_rule: FinancialObservationComparabilityRule | None = None

    def __post_init__(self) -> None:
        if not all((self.policy_id, self.version, self.proposal_policy_id, self.proposal_version, self.approved_by)):
            raise ValueError("BRAIN_RESEARCH_COMPARABILITY_POLICY_REQUIRED_FIELD")
        if not self.approved_by.startswith("human:"):
            raise ValueError("BRAIN_RESEARCH_COMPARABILITY_POLICY_HUMAN_APPROVAL_REQUIRED")
        if self.approval_status is not BrainResearchComparabilityPolicyApprovalStatus.APPROVED:
            raise ValueError("BRAIN_RESEARCH_COMPARABILITY_POLICY_APPROVAL_REQUIRED")
        if self.selected_for_future_comparator or self.active:
            raise ValueError("BRAIN_RESEARCH_COMPARABILITY_POLICY_MUST_NOT_BE_ACTIVE")
        if self.comparison_mode is not ResearchComparisonMode.KNOWLEDGE_AT_THE_TIME or self.restated_history_enabled:
            raise ValueError("BRAIN_RESEARCH_COMPARABILITY_POLICY_KNOWLEDGE_AT_TIME_REQUIRED")
        if not all((self.dimension_local_failure, self.no_cross_version_equivalence, self.native_typed_lineage_required, self.missing_is_not_zero)):
            raise ValueError("BRAIN_RESEARCH_COMPARABILITY_POLICY_CORE_SAFETY_REQUIRED")
        if self.source_eligibility_vocabulary != tuple(ResearchSourceEligibility):
            raise ValueError("BRAIN_RESEARCH_COMPARABILITY_POLICY_ELIGIBILITY_VOCABULARY_REQUIRED")
        if self.comparability_status_vocabulary != tuple(ResearchComparabilityStatus):
            raise ValueError("BRAIN_RESEARCH_COMPARABILITY_POLICY_STATUS_VOCABULARY_REQUIRED")
        if self.foundational_identity_rules != tuple(ResearchFoundationalIdentityRule):
            raise ValueError("BRAIN_RESEARCH_COMPARABILITY_POLICY_FOUNDATIONAL_RULES_REQUIRED")
        if self.source_rules != tuple(sorted(set(self.source_rules), key=_source_rule_key)):
            raise ValueError("BRAIN_RESEARCH_COMPARABILITY_POLICY_SOURCE_RULES_NONCANONICAL")
        if self.domain_rules != tuple(sorted(set(self.domain_rules), key=_domain_rule_key)):
            raise ValueError("BRAIN_RESEARCH_COMPARABILITY_POLICY_DOMAIN_RULES_NONCANONICAL")
        if self.evidence_preconditions != tuple(sorted(set(self.evidence_preconditions), key=lambda value: value.condition.value)):
            raise ValueError("BRAIN_RESEARCH_COMPARABILITY_POLICY_PRECONDITIONS_NONCANONICAL")
        if {value.condition for value in self.evidence_preconditions} != set(ResearchEvidencePrecondition):
            raise ValueError("BRAIN_RESEARCH_COMPARABILITY_POLICY_PRECONDITION_COVERAGE_REQUIRED")
        if self.non_comparable_cases != tuple(sorted(set(self.non_comparable_cases), key=lambda value: value.value)):
            raise ValueError("BRAIN_RESEARCH_COMPARABILITY_POLICY_CASES_NONCANONICAL")
        if self.exclusions != tuple(ResearchComparabilityExclusion):
            raise ValueError("BRAIN_RESEARCH_COMPARABILITY_POLICY_EXCLUSIONS_REQUIRED")
        if self.provenance != tuple(sorted(set(self.provenance))):
            raise ValueError("BRAIN_RESEARCH_COMPARABILITY_POLICY_PROVENANCE_NONCANONICAL")
        predecessor = (
            self.predecessor_policy_id,
            self.predecessor_policy_version,
            self.predecessor_policy_fingerprint,
        )
        if self.financial_observation_rule is None:
            if any(value is not None for value in predecessor):
                raise ValueError("BRAIN_RESEARCH_COMPARABILITY_POLICY_PREDECESSOR_INVALID")
        else:
            if self.version != "v2-approved" or predecessor != (
                "brain-research-comparability-policy", "v1-approved",
                "361a2f7e8cd9a5acd7a2731d10a56c32ae52227c7fd412fbd2f1967b37ca1bc2",
            ):
                raise ValueError("BRAIN_RESEARCH_COMPARABILITY_POLICY_V2_LINEAGE_REQUIRED")
        if self.fingerprint != brain_research_comparability_policy_fingerprint(self):
            raise ValueError("BRAIN_RESEARCH_COMPARABILITY_POLICY_FINGERPRINT_MISMATCH")


def _source_rule_key(value: ResearchSourceEligibilityRule) -> tuple[str, str, str, tuple[str, ...]]:
    return value.domain.value, value.eligibility.value, value.source_boundary, value.prerequisites


def _domain_rule_key(value: ResearchDomainComparabilityRule) -> tuple[str, tuple[str, ...], tuple[str, ...]]:
    return value.domain.value, value.required_identity, tuple(item.value for item in value.non_comparable_cases)


def create_frozen_brain_research_comparability_policy(
    *, policy_id: str, version: str, proposal_policy_id: str, proposal_version: str,
    approved_by: str, source_rules: tuple[ResearchSourceEligibilityRule, ...],
    domain_rules: tuple[ResearchDomainComparabilityRule, ...],
    evidence_preconditions: tuple[ResearchEvidencePreconditionRule, ...],
    non_comparable_cases: tuple[ResearchNonComparableCase, ...],
    exclusions: tuple[ResearchComparabilityExclusion, ...], provenance: tuple[tuple[str, str], ...],
    predecessor_policy_id: str | None = None,
    predecessor_policy_version: str | None = None,
    predecessor_policy_fingerprint: str | None = None,
    financial_observation_rule: FinancialObservationComparabilityRule | None = None,
) -> FrozenBrainResearchComparabilityPolicy:
    values = dict(
        policy_id=policy_id,
        version=version,
        proposal_policy_id=proposal_policy_id,
        proposal_version=proposal_version,
        approval_status=BrainResearchComparabilityPolicyApprovalStatus.APPROVED,
        approved_by=approved_by,
        selected_for_future_comparator=False,
        active=False,
        comparison_mode=ResearchComparisonMode.KNOWLEDGE_AT_THE_TIME,
        restated_history_enabled=False,
        dimension_local_failure=True,
        no_cross_version_equivalence=True,
        native_typed_lineage_required=True,
        missing_is_not_zero=True,
        source_eligibility_vocabulary=tuple(ResearchSourceEligibility),
        comparability_status_vocabulary=tuple(ResearchComparabilityStatus),
        foundational_identity_rules=tuple(ResearchFoundationalIdentityRule),
        source_rules=tuple(sorted(set(source_rules), key=_source_rule_key)),
        domain_rules=tuple(sorted(set(domain_rules), key=_domain_rule_key)),
        evidence_preconditions=tuple(sorted(set(evidence_preconditions), key=lambda value: value.condition.value)),
        non_comparable_cases=tuple(sorted(set(non_comparable_cases), key=lambda value: value.value)),
        exclusions=tuple(ResearchComparabilityExclusion),
        provenance=tuple(sorted(set(provenance))),
        predecessor_policy_id=predecessor_policy_id,
        predecessor_policy_version=predecessor_policy_version,
        predecessor_policy_fingerprint=predecessor_policy_fingerprint,
        financial_observation_rule=financial_observation_rule,
    )
    return FrozenBrainResearchComparabilityPolicy(
        **values, fingerprint=brain_research_comparability_policy_fingerprint_values(values),
    )


def brain_research_comparability_policy_fingerprint(value: FrozenBrainResearchComparabilityPolicy) -> str:
    return brain_research_comparability_policy_fingerprint_values({
        field: getattr(value, field) for field in value.__dataclass_fields__ if field != "fingerprint"
    })


def brain_research_comparability_policy_fingerprint_values(values: dict) -> str:
    base_fingerprint = manifest_fingerprint(
        policy_id=values["policy_id"], version=values["version"],
        proposal_policy_id=values["proposal_policy_id"], proposal_version=values["proposal_version"],
        approval_status=values["approval_status"].value, approved_by=values["approved_by"],
        selected_for_future_comparator=values["selected_for_future_comparator"], active=values["active"],
        comparison_mode=values["comparison_mode"].value, restated_history_enabled=values["restated_history_enabled"],
        dimension_local_failure=values["dimension_local_failure"],
        no_cross_version_equivalence=values["no_cross_version_equivalence"],
        native_typed_lineage_required=values["native_typed_lineage_required"], missing_is_not_zero=values["missing_is_not_zero"],
        source_eligibility_vocabulary=tuple(item.value for item in values["source_eligibility_vocabulary"]),
        comparability_status_vocabulary=tuple(item.value for item in values["comparability_status_vocabulary"]),
        foundational_identity_rules=tuple(item.value for item in values["foundational_identity_rules"]),
        source_rules=tuple((item.domain.value, item.eligibility.value, item.source_boundary, item.prerequisites) for item in values["source_rules"]),
        domain_rules=tuple((item.domain.value, item.required_identity, tuple(case.value for case in item.non_comparable_cases)) for item in values["domain_rules"]),
        evidence_preconditions=tuple((item.condition.value, item.status.value, item.domain_specific_rule_required) for item in values["evidence_preconditions"]),
        non_comparable_cases=tuple(item.value for item in values["non_comparable_cases"]),
        exclusions=tuple(item.value for item in values["exclusions"]), provenance=values["provenance"],
    )
    financial_rule = values.get("financial_observation_rule")
    if financial_rule is None:
        return base_fingerprint
    return manifest_fingerprint(
        base_policy_fingerprint=base_fingerprint,
        predecessor_policy_id=values.get("predecessor_policy_id"),
        predecessor_policy_version=values.get("predecessor_policy_version"),
        predecessor_policy_fingerprint=values.get("predecessor_policy_fingerprint"),
        financial_observation_rule=_financial_observation_rule_values(financial_rule),
    )


def _financial_observation_rule_values(value: FinancialObservationComparabilityRule) -> dict:
    return {
        "domain": value.domain.value,
        "bundle_schema": (value.bundle_schema_id, value.bundle_schema_version, value.bundle_schema_fingerprint),
        "observation_schema": (value.observation_schema_id, value.observation_schema_version, value.observation_schema_fingerprint),
        "selector_policy": (value.selector_policy_id, value.selector_policy_version, value.selector_policy_fingerprint),
        "knowledge_mode": value.knowledge_mode.value,
        "selector_as_of_exact_required": value.selector_as_of_exact_required,
        "visible_as_of_must_not_exceed_state_as_of": value.visible_as_of_must_not_exceed_state_as_of,
        "missing_selector_attestation_status": value.missing_selector_attestation_status.value,
        "contradictory_selector_attestation_disposition": value.contradictory_selector_attestation_disposition,
        "slot_identity_components": tuple(item.value for item in value.slot_identity_components),
        "lineage_only_fields": tuple(item.value for item in value.lineage_only_fields),
        "source_roles": tuple(item.value for item in value.source_roles),
        "reference_numeric_pairing_prohibited": value.reference_numeric_pairing_prohibited,
        "period_dispositions": tuple(item.value for item in value.period_dispositions),
        "matching_requirements": tuple(item.value for item in value.matching_requirements),
    }


def _source(domain: ResearchComparabilityDomain, eligibility: ResearchSourceEligibility, boundary: str, *prerequisites: str) -> ResearchSourceEligibilityRule:
    return ResearchSourceEligibilityRule(domain, eligibility, boundary, tuple(sorted(set(prerequisites))))


def _domain(domain: ResearchComparabilityDomain, *required_identity: str, cases: tuple[ResearchNonComparableCase, ...] = ()) -> ResearchDomainComparabilityRule:
    return ResearchDomainComparabilityRule(domain, tuple(sorted(set(required_identity))), tuple(sorted(set(cases), key=lambda value: value.value)))


_SOURCE_RULES = (
    _source(ResearchComparabilityDomain.FINANCIAL_RAW, ResearchSourceEligibility.PIT_REBUILDABLE, "FinancialFactStore", "PIT_VISIBLE_FACT", "QUALITY_PREREQUISITES"),
    _source(ResearchComparabilityDomain.NEWS_CATALYST, ResearchSourceEligibility.PIT_REBUILDABLE, "eligible_stored_news_filings_catalysts", "PIT_VISIBLE_EVENT"),
    _source(ResearchComparabilityDomain.OFFICIAL_DELIVERY, ResearchSourceEligibility.PIT_REBUILDABLE, "NseDeliveryStore", "OFFICIAL_REPORT", "AVAILABLE_AT"),
    _source(ResearchComparabilityDomain.CORPORATE_ACTION, ResearchSourceEligibility.PIT_REBUILDABLE, "HistoricalSecurityMasterStore.actions_as_of", "PIT_ACTION_LINEAGE"),
    _source(ResearchComparabilityDomain.MARKET_PRICE, ResearchSourceEligibility.PIT_REBUILDABLE, "provider_versioned_HistoricalBarStore", "HISTORICAL_INTEGRITY", "PROVENANCE"),
    _source(ResearchComparabilityDomain.SECTOR_IDENTITY, ResearchSourceEligibility.PIT_REBUILDABLE, "taxonomy_membership_intervals", "PIT_MEMBERSHIP_LINEAGE"),
    _source(ResearchComparabilityDomain.MARKET_REGIME, ResearchSourceEligibility.DURABLE_ARTIFACT_ONLY, "stored_MarketRegimeResult", "EXACT_ARTIFACT_REQUIRED"),
    _source(ResearchComparabilityDomain.PRE_BREAKOUT_SETUP, ResearchSourceEligibility.DURABLE_ARTIFACT_ONLY, "GovernedPreBreakoutSetupAssessment", "EXACT_GOVERNED_LINEAGE"),
    _source(ResearchComparabilityDomain.PRE_BREAKOUT_CANDIDATE, ResearchSourceEligibility.DURABLE_ARTIFACT_ONLY, "PreBreakoutCandidate", "EXACT_CANDIDATE_OR_ASSESSMENT_REQUIRED"),
    _source(ResearchComparabilityDomain.ENTRY_ECONOMICS, ResearchSourceEligibility.DURABLE_ARTIFACT_ONLY, "governed_structural_geometry", "EXACT_SETUP_LINEAGE"),
    _source(ResearchComparabilityDomain.DIAGNOSTIC, ResearchSourceEligibility.DURABLE_ARTIFACT_ONLY, "DiagnosticResult", "EXACT_DURABLE_ARTIFACT_REQUIRED"),
    _source(ResearchComparabilityDomain.DECISION_SCORE, ResearchSourceEligibility.DURABLE_ARTIFACT_ONLY, "DecisionScorecard", "EXACT_DURABLE_ARTIFACT_REQUIRED"),
    _source(ResearchComparabilityDomain.RELIABILITY, ResearchSourceEligibility.DURABLE_ARTIFACT_ONLY, "StoredReliabilityDecision", "NATIVE_TYPED_LINEAGE"),
    _source(ResearchComparabilityDomain.MACRO_STATE, ResearchSourceEligibility.DURABLE_ARTIFACT_ONLY, "first_observed_MacroState", "EXACT_ARTIFACT_REQUIRED"),
    _source(ResearchComparabilityDomain.SECTOR_RS, ResearchSourceEligibility.CURRENT_ONLY, "CurrentSectorRotationService", "NO_HISTORICAL_DURABLE_MANIFEST"),
    _source(ResearchComparabilityDomain.SECTOR_BREADTH, ResearchSourceEligibility.CURRENT_ONLY, "CurrentSectorRotationService", "NO_HISTORICAL_DURABLE_MANIFEST"),
    _source(ResearchComparabilityDomain.SECTOR_RANK, ResearchSourceEligibility.CURRENT_ONLY, "CurrentSectorRotationService", "NO_HISTORICAL_DURABLE_MANIFEST"),
    _source(ResearchComparabilityDomain.SECTOR_TOP3, ResearchSourceEligibility.CURRENT_ONLY, "CurrentSectorRotationService", "NO_HISTORICAL_DURABLE_MANIFEST"),
    _source(ResearchComparabilityDomain.TECHNICAL_MATERIALIZATION, ResearchSourceEligibility.CURRENT_ONLY, "non_durable_technical_materialization", "NO_HISTORICAL_DURABLE_ARTIFACT"),
    _source(ResearchComparabilityDomain.OWNERSHIP_PERCENTAGE, ResearchSourceEligibility.UNSUPPORTED, "shareholding_disclosure_lineage", "NORMALIZED_PIT_PERCENTAGE_ABSENT"),
    _source(ResearchComparabilityDomain.VALUATION, ResearchSourceEligibility.UNSUPPORTED, "valuation", "CANONICAL_COMPARISON_CONTRACT_ABSENT"),
    _source(ResearchComparabilityDomain.CORPORATE_ACTION_REFERENCE, ResearchSourceEligibility.REFERENCE_ONLY, "corporate_action_normalization_reference", "IDENTITY_AND_BASIS_REFERENCE"),
)


_DOMAIN_RULES = (
    _domain(ResearchComparabilityDomain.FINANCIAL_RAW, "CANONICAL_INSTRUMENT", "METRIC", "STATEMENT_SCOPE", "CURRENCY", "VALUE_DIMENSION", "UNIT", "SCALE", "PERIOD_TYPE", "VALUE_BASIS", "FISCAL_ALIGNMENT", "NORMALIZATION", "REVISION", "PIT", "QUALITY", cases=(ResearchNonComparableCase.FINANCIAL_SCOPE_MISMATCH, ResearchNonComparableCase.FINANCIAL_PERIOD_OR_BASIS_MISMATCH, ResearchNonComparableCase.FINANCIAL_UNIT_SCALE_OR_DIMENSION_MISMATCH, ResearchNonComparableCase.UNSUPPORTED_FINANCIAL_CONVERSION)),
    _domain(ResearchComparabilityDomain.MARKET_PRICE, "CANONICAL_INSTRUMENT", "EXCHANGE_SERIES", "SESSION", "TIMEFRAME", "PRICE_BASIS", "PROVIDER_IDENTITY_VERSION", "PROVENANCE", "HISTORICAL_INTEGRITY", "CORPORATE_ACTION_TREATMENT", cases=(ResearchNonComparableCase.PRICE_ACTION_BASIS_UNPROVEN, ResearchNonComparableCase.HISTORICAL_INTEGRITY_INVALID)),
    _domain(ResearchComparabilityDomain.TECHNICAL_MATERIALIZATION, "PRICE_BASIS", "HISTORICAL_INTEGRITY", "CALENDAR_SESSION", "LOOKBACK", "MINIMUM_PERIODS", "FORMULA", "METHODOLOGY_VERSION", "CORPORATE_ACTION_TREATMENT", "SELECTED_POLICY", cases=(ResearchNonComparableCase.TECHNICAL_WINDOW_OR_FORMULA_MISMATCH,)),
    _domain(ResearchComparabilityDomain.SECTOR_RS, "BENCHMARK", "TAXONOMY", "SECTOR", "PIT_MEMBERSHIP", "CONSTITUENT_COVERAGE", "LOOKBACK", "FORMULA", "RANKING_METHODOLOGY", "METHODOLOGY_VERSION", cases=(ResearchNonComparableCase.SECTOR_DERIVED_CURRENT_ONLY,)),
    _domain(ResearchComparabilityDomain.SECTOR_BREADTH, "TAXONOMY", "PIT_MEMBERSHIP", "CONSTITUENT_COVERAGE", "SESSION", "MOVING_AVERAGE_METHODOLOGY", "COVERAGE_THRESHOLD", cases=(ResearchNonComparableCase.SECTOR_DERIVED_CURRENT_ONLY,)),
    _domain(ResearchComparabilityDomain.SECTOR_RANK, "BENCHMARK", "TAXONOMY", "PIT_MEMBERSHIP", "RANKING_METHODOLOGY", "TIE_TREATMENT", cases=(ResearchNonComparableCase.SECTOR_DERIVED_CURRENT_ONLY,)),
    _domain(ResearchComparabilityDomain.SECTOR_TOP3, "BENCHMARK", "TAXONOMY", "PIT_MEMBERSHIP", "RANKING_METHODOLOGY", "TOP3_POLICY", cases=(ResearchNonComparableCase.SECTOR_DERIVED_CURRENT_ONLY,)),
    _domain(ResearchComparabilityDomain.PRE_BREAKOUT_SETUP, "CANONICAL_INSTRUMENT", "POLICY_ID", "POLICY_VERSION", "POLICY_FINGERPRINT", "PIT_EVIDENCE", "PRICE_BASIS", "DELIVERY_LINEAGE", "STRUCTURAL_SEMANTICS", "TICK_RESOLUTION", "HISTORICAL_INTEGRITY", "DEPENDENCY_FINGERPRINTS", cases=(ResearchNonComparableCase.SETUP_POLICY_FINGERPRINT_MISMATCH,)),
    _domain(ResearchComparabilityDomain.ENTRY_ECONOMICS, "GOVERNED_SETUP_LINEAGE", "PRICE_BASIS", "TICK_RESOLUTION", "ENTRY_GEOMETRY", "REFERENCE_RR", cases=(ResearchNonComparableCase.SETUP_POLICY_FINGERPRINT_MISMATCH,)),
    _domain(ResearchComparabilityDomain.DECISION_SCORE, "STRATEGY", "REGISTRY", "CONFIGURATION", "COMPONENTS", "WEIGHTS", "NORMALIZATION", "MISSING_DATA_TREATMENT", "COMPLETENESS", "CONFIDENCE", "EVIDENCE_LINEAGE"),
    _domain(ResearchComparabilityDomain.DIAGNOSTIC, "STRATEGY", "REGISTRY", "RULE_DEFINITION", "INPUT_SEMANTICS", "COMPLETENESS", "EVIDENCE_LINEAGE", "VERSION"),
    _domain(ResearchComparabilityDomain.NEWS_CATALYST, "EVENT_IDENTITY", "ENTITY", "SCHEMA_TYPE", "SOURCE", "PUBLICATION_EFFECTIVE_RECEIPT", "CONFIRMATION", "MATERIALITY", "SUPERSESSION"),
    _domain(ResearchComparabilityDomain.MACRO_STATE, "METRIC_FAMILY_COMPONENT", "GEOGRAPHY", "PERIOD", "RELEASE_VINTAGE", "SOURCE", "REVISION", "METHODOLOGY"),
)


_EVIDENCE_PRECONDITIONS = (
    ResearchEvidencePreconditionRule(ResearchEvidencePrecondition.RELIABILITY_CONFLICTED, ResearchComparabilityStatus.NON_COMPARABLE),
    ResearchEvidencePreconditionRule(ResearchEvidencePrecondition.HISTORICAL_INTEGRITY_INVALID, ResearchComparabilityStatus.NON_COMPARABLE),
    ResearchEvidencePreconditionRule(ResearchEvidencePrecondition.REQUIRED_EVIDENCE_UNAVAILABLE, ResearchComparabilityStatus.INSUFFICIENT),
    ResearchEvidencePreconditionRule(ResearchEvidencePrecondition.EVIDENCE_STALE, ResearchComparabilityStatus.INSUFFICIENT, True),
)


CURRENT_FROZEN_BRAIN_RESEARCH_COMPARABILITY_POLICY = create_frozen_brain_research_comparability_policy(
    policy_id="brain-research-comparability-policy",
    version="v1-approved",
    proposal_policy_id="brain-research-comparability-policy",
    proposal_version="v1-proposed",
    approved_by="human:Akash-Verma",
    source_rules=_SOURCE_RULES,
    domain_rules=_DOMAIN_RULES,
    evidence_preconditions=_EVIDENCE_PRECONDITIONS,
    non_comparable_cases=tuple(ResearchNonComparableCase),
    exclusions=tuple(ResearchComparabilityExclusion),
    provenance=(
        ("governance_approval", "U14D-5D"),
        ("proposal_policy", "brain-research-comparability-policy/v1-proposed"),
        ("scope", "FACTUAL_COMPARABILITY_ONLY"),
    ),
)


_V2_FINANCIAL_OBSERVATION_RULE = FinancialObservationComparabilityRule(
    domain=ResearchComparabilityDomain.FINANCIAL_RAW,
    bundle_schema_id="financial-research-observation-bundle-schema",
    bundle_schema_version="v1-approved",
    bundle_schema_fingerprint="aba6123afc78781b4ac011fe048ed10d91b7e8af3f10944f25558be5f2036a89",
    observation_schema_id="financial-metric-observation-schema",
    observation_schema_version="v1-approved",
    observation_schema_fingerprint="6d55e73ee78f0074789165952a287d9b8b6ec801ce98703e9a136603f3da3caf",
    selector_policy_id="financial-fact-vintage-selection-policy",
    selector_policy_version="v1-approved",
    selector_policy_fingerprint="862dc470ebd58abd2d066f2604440908eaf3aa9827e6c93b588b5f1bf806fc13",
    knowledge_mode=ResearchComparisonMode.KNOWLEDGE_AT_THE_TIME,
    selector_as_of_exact_required=True,
    visible_as_of_must_not_exceed_state_as_of=True,
    missing_selector_attestation_status=ResearchComparabilityStatus.INSUFFICIENT,
    contradictory_selector_attestation_disposition="INVALID_FINANCIAL_DIMENSION_INPUT",
    slot_identity_components=tuple(FinancialObservationSlotIdentityComponent),
    lineage_only_fields=tuple(FinancialObservationLineageOnlyField),
    source_roles=tuple(FinancialObservationSourceRole),
    reference_numeric_pairing_prohibited=True,
    period_dispositions=tuple(FinancialObservationPeriodDisposition),
    matching_requirements=tuple(FinancialObservationMatchingRequirement),
)


FROZEN_BRAIN_RESEARCH_COMPARABILITY_POLICY_V2 = create_frozen_brain_research_comparability_policy(
    policy_id="brain-research-comparability-policy",
    version="v2-approved",
    proposal_policy_id="brain-research-comparability-policy",
    proposal_version="v2-proposed",
    approved_by="human:Akash-Verma",
    source_rules=_SOURCE_RULES,
    domain_rules=_DOMAIN_RULES,
    evidence_preconditions=_EVIDENCE_PRECONDITIONS,
    non_comparable_cases=tuple(ResearchNonComparableCase),
    exclusions=tuple(ResearchComparabilityExclusion),
    provenance=(
        ("governance_approval", "U14D-6N"),
        ("predecessor_policy", "brain-research-comparability-policy/v1-approved"),
        ("proposal_policy", "brain-research-comparability-policy/v2-proposed"),
        ("scope", "FINANCIAL_OBSERVATION_COMPARABILITY_GOVERNANCE_ONLY"),
    ),
    predecessor_policy_id=CURRENT_FROZEN_BRAIN_RESEARCH_COMPARABILITY_POLICY.policy_id,
    predecessor_policy_version=CURRENT_FROZEN_BRAIN_RESEARCH_COMPARABILITY_POLICY.version,
    predecessor_policy_fingerprint=CURRENT_FROZEN_BRAIN_RESEARCH_COMPARABILITY_POLICY.fingerprint,
    financial_observation_rule=_V2_FINANCIAL_OBSERVATION_RULE,
)


__all__ = (
    "BrainResearchComparabilityPolicyApprovalStatus",
    "CURRENT_FROZEN_BRAIN_RESEARCH_COMPARABILITY_POLICY",
    "FROZEN_BRAIN_RESEARCH_COMPARABILITY_POLICY_V2",
    "FinancialObservationComparabilityRule",
    "FinancialObservationLineageOnlyField",
    "FinancialObservationMatchingRequirement",
    "FinancialObservationPeriodDisposition",
    "FinancialObservationSlotIdentityComponent",
    "FinancialObservationSourceRole",
    "FrozenBrainResearchComparabilityPolicy",
    "ResearchComparabilityDomain",
    "ResearchComparabilityExclusion",
    "ResearchComparabilityStatus",
    "ResearchComparisonMode",
    "ResearchDomainComparabilityRule",
    "ResearchEvidencePrecondition",
    "ResearchEvidencePreconditionRule",
    "ResearchFoundationalIdentityRule",
    "ResearchNonComparableCase",
    "ResearchSourceEligibility",
    "ResearchSourceEligibilityRule",
    "brain_research_comparability_policy_fingerprint",
    "create_frozen_brain_research_comparability_policy",
)
