"""U14D-6V deterministic, in-memory factual-chain QA.

The primary fixture deliberately traverses selector -> materializer -> bundle
-> wrapper -> State v2 -> delta.  It never accesses a store or provider.
"""
from __future__ import annotations

from dataclasses import replace
from datetime import UTC, timedelta

import pytest

import test_brain_research_comparison_state_v2 as helpers
from app.fundamentals.financial_fact_vintage_selection_policy import (
    CURRENT_FROZEN_FINANCIAL_FACT_VINTAGE_SELECTION_POLICY,
)
from app.fundamentals.financial_fact_vintage_selector import select_financial_fact_vintages
from app.fundamentals.financial_metric_observation_materializer import materialize_financial_metric_observation
from app.fundamentals.financial_research_observation_wrapper import wrap_financial_research_observation_bundle
from app.fundamentals.financial_research_observation_wrapper_schema import CURRENT_FROZEN_FINANCIAL_RESEARCH_OBSERVATION_WRAPPER_SCHEMA
from app.intelligence.brain_research_comparability_policy import ResearchComparabilityDomain
from app.intelligence.research_state_delta import ResearchMetricChangeKind, research_observation_slot_key


def _chain(facts, *, as_of, reference: bool = True):
    """Run every factual stage using only supplied immutable facts."""
    batch = select_financial_fact_vintages(
        facts, canonical_instrument_id="NSE:ALPHA", as_of=as_of,
        policy=CURRENT_FROZEN_FINANCIAL_FACT_VINTAGE_SELECTION_POLICY,
    )
    facts_by_id = {item.fact_id: item for item in facts}
    pairs = []
    for selection in batch.selections:
        if selection.selected_fact_id is None:
            continue
        fact = facts_by_id[selection.selected_fact_id]
        result = materialize_financial_metric_observation(
            fact, selection=selection, schema=helpers.CURRENT_FROZEN_FINANCIAL_METRIC_OBSERVATION_SCHEMA,
        )
        assert result.observation is not None
        pairs.append((result.observation, selection))
    bundle = helpers._bundle(*pairs, as_of=as_of)
    wrappers = wrap_financial_research_observation_bundle(
        bundle, wrapper_schema=CURRENT_FROZEN_FINANCIAL_RESEARCH_OBSERVATION_WRAPPER_SCHEMA,
    )
    state = helpers._v2(bundle, wrappers, as_of=as_of, reference=reference)
    return batch, bundle, wrappers, state


def _financial(state):
    return next(item for item in state.dimensions if item.dimension is ResearchComparabilityDomain.FINANCIAL_RAW)


def test_full_chain_preserves_pit_revision_new_period_and_determinism() -> None:
    t1 = helpers.T1
    t2 = t1 + timedelta(days=30)
    original = helpers._fact("f1", value="100", as_of=t1)
    revised = replace(
        helpers._fact("f2", value="95", as_of=t2),
        parent_fact_ids=("f1",), revision_of_fact_id="f1",
    )
    q2 = helpers._fact("q2", value="120", period_end=t2, as_of=t2)

    first_batch, first_bundle, first_wrappers, first_state = _chain((q2, revised, original), as_of=t1)
    second_batch, second_bundle, second_wrappers, second_state = _chain((original, q2, revised), as_of=t2)
    assert first_batch.selections[0].selected_fact_id == "f1"
    assert first_bundle.observations[0].value == 100
    assert first_wrappers[0].lineage_components != second_wrappers[0].lineage_components
    assert second_batch.selections and {item.value for item in second_bundle.observations} == {95, 120}
    assert second_state.as_of == t2

    delta = helpers.compare_brain_research_states(
        first_state, second_state, policy=helpers.FROZEN_BRAIN_RESEARCH_COMPARABILITY_POLICY_V2,
    )
    financial = next(item for item in delta.dimension_deltas if item.dimension is ResearchComparabilityDomain.FINANCIAL_RAW)
    assert {item.change_kind for item in financial.observation_deltas} >= {
        ResearchMetricChangeKind.VALUE_CHANGED, ResearchMetricChangeKind.ADDED,
    }
    repeated = _chain((revised, original, q2), as_of=t2)
    assert (second_batch.fingerprint, second_bundle.fingerprint, second_wrappers, second_state.fingerprint) == (
        repeated[0].fingerprint, repeated[1].fingerprint, repeated[2], repeated[3].fingerprint,
    )


def test_full_chain_preserves_partial_failure_only_mixed_and_source_role_boundaries() -> None:
    partial, selection = helpers._prepared(helpers._fact("partial", partial=True), as_of=helpers.T1)
    bundle = helpers._bundle((partial, selection), as_of=helpers.T1, failures=(helpers._failure(as_of=helpers.T1),))
    wrappers = wrap_financial_research_observation_bundle(bundle, wrapper_schema=CURRENT_FROZEN_FINANCIAL_RESEARCH_OBSERVATION_WRAPPER_SCHEMA)
    state = helpers._v2(bundle, wrappers, as_of=helpers.T1, failures=tuple(reversed(bundle.failures)))
    dimension = _financial(state)
    assert dict(wrappers[0].identity_components)["financial_period_strength"] == "PARTIAL"
    assert any(item.value_type.value == "ARTIFACT_REFERENCE" for item in dimension.observations)
    assert any(item.value_type.value == "FACTUAL_VALUE" for item in dimension.observations)
    assert "FINANCIAL_INPUT_SELECTION_UNAVAILABLE" in dimension.blockers
    assert len({research_observation_slot_key(item) for item in dimension.observations}) == len(dimension.observations)

    failure = helpers._failure(as_of=helpers.T1)
    failed_bundle = helpers._bundle(as_of=helpers.T1, failures=(failure,))
    failed_state = helpers._v2(failed_bundle, (), as_of=helpers.T1, failures=(failure,), reference=False)
    assert _financial(failed_state).availability.value == "PARTIAL"
    assert not [item for item in _financial(failed_state).observations if item.value_type.value == "FACTUAL_VALUE"]


def test_full_chain_tamper_and_duplicate_slots_fail_closed_without_repair() -> None:
    observation, selection = helpers._prepared(helpers._fact("q1"), as_of=helpers.T1)
    bundle = helpers._bundle((observation, selection), as_of=helpers.T1)
    wrapper = wrap_financial_research_observation_bundle(bundle, wrapper_schema=CURRENT_FROZEN_FINANCIAL_RESEARCH_OBSERVATION_WRAPPER_SCHEMA)[0]
    with pytest.raises(Exception, match="WRAPPER_COUNT_INVALID"):
        helpers._v2(bundle, (wrapper, wrapper), as_of=helpers.T1)
    with pytest.raises(Exception, match="WRAPPER_MAPPING_INVALID|WRAPPER_BINDING_INVALID"):
        helpers._v2(bundle, (replace(wrapper, value=101),), as_of=helpers.T1)
    object.__setattr__(bundle, "fingerprint", "0" * 64)
    with pytest.raises(Exception, match="BUNDLE_INVALID|BUNDLE_TAMPERED"):
        helpers._v2(bundle, (wrapper,), as_of=helpers.T1)
