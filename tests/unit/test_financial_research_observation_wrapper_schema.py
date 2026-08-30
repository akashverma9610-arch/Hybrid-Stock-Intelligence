from __future__ import annotations

from dataclasses import replace
import inspect

import pytest

import app.fundamentals.financial_research_observation_wrapper_schema as module
from app.fundamentals.financial_research_observation_wrapper_schema import (
    CURRENT_FROZEN_FINANCIAL_RESEARCH_OBSERVATION_WRAPPER_SCHEMA,
    FinancialResearchObservationWrapperSchemaApprovalStatus,
    financial_research_observation_wrapper_schema_fingerprint,
)
from app.intelligence.brain_research_comparability_policy import (
    FinancialObservationSourceRole,
    ResearchComparabilityDomain,
)


SCHEMA = CURRENT_FROZEN_FINANCIAL_RESEARCH_OBSERVATION_WRAPPER_SCHEMA


def test_frozen_wrapper_schema_identity_governance_and_lossless_mapping_contract() -> None:
    assert (SCHEMA.schema_id, SCHEMA.version) == ("financial-research-observation-wrapper-schema", "v1-approved")
    assert (SCHEMA.proposal_schema_id, SCHEMA.proposal_version) == ("financial-research-observation-wrapper-schema", "v1-proposed")
    assert SCHEMA.approval_status is FinancialResearchObservationWrapperSchemaApprovalStatus.APPROVED
    assert SCHEMA.approved_by == "human:Akash-Verma"
    assert not SCHEMA.selected_for_future_wrapper and not SCHEMA.active
    assert SCHEMA.generic_dimension is ResearchComparabilityDomain.FINANCIAL_RAW
    assert SCHEMA.source_role is FinancialObservationSourceRole.FINANCIAL_NUMERIC_OBSERVATION
    assert SCHEMA.source_artifact_type == "FINANCIAL_METRIC_OBSERVATION"
    assert SCHEMA.metric_id_mapping == "FINANCIAL_METRIC_VALUE"
    assert SCHEMA.exact_decimal_value_required
    assert SCHEMA.source_artifact_fingerprint_mapping == "FINANCIAL_METRIC_OBSERVATION_FINGERPRINT"
    assert financial_research_observation_wrapper_schema_fingerprint(SCHEMA) == SCHEMA.fingerprint


def test_wrapper_schema_freezes_slot_and_non_slot_financial_mapping_without_overlap() -> None:
    assert {"financial_currency", "financial_fact_kind", "financial_period_fingerprint", "financial_period_strength", "financial_source_role", "financial_value_dimension"} <= set(SCHEMA.slot_identity_component_keys)
    assert {"financial_source_fact_id", "financial_source_semantic_fingerprint", "financial_selection_as_of", "financial_bundle_as_of", "financial_bundle_fingerprint", "financial_visible_as_of", "financial_quality_flags", "financial_provenance"} <= set(SCHEMA.non_slot_lineage_keys)
    assert not set(SCHEMA.slot_identity_component_keys).intersection(SCHEMA.non_slot_lineage_keys)
    assert SCHEMA.slot_identity_component_keys == tuple(sorted(SCHEMA.slot_identity_component_keys))
    assert SCHEMA.non_slot_lineage_keys == tuple(sorted(SCHEMA.non_slot_lineage_keys))


def test_wrapper_schema_is_tamper_closed_and_has_no_wrapper_function() -> None:
    with pytest.raises(ValueError):
        replace(SCHEMA, source_artifact_type="FINANCIAL_EVIDENCE_REFERENCE")
    with pytest.raises(ValueError):
        replace(SCHEMA, active=True)
    source = inspect.getsource(module)
    assert "def wrap_financial_research_observation_bundle" not in source
    assert "BrainResearchComparisonState" not in source
    assert "ResearchStateDelta" not in source
