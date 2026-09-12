"""Explicit synthetic authority for isolated gate arithmetic tests only.

Never imported by app code. Values are unchanged, including missing values;
this replaces the old implicit authority of raw test fixtures, not production
source verification. Rejection tests call the real engine without this helper.
"""
from app.gates.engine import ExecutionGateEvaluation, ExecutionEligibility
from app.gates.score_provenance import score_evidence
from app.gates.version_compatibility import (DOMAIN_FIELDS, domain_lineage, gate_evidence_context,
                                             require_gate_inputs)
from app.fundamentals.diagnostic_comparability import content_fingerprint
from app.registry.canonical import DIAGNOSTIC_REGISTRY_VERSION as V1
from app.scoring.engine import DecisionScorecard


def synthetic_card(inputs, *, instrument, strategy, scoring, at, incumbent=False):
    return DecisionScorecard("synthetic-incumbent" if incumbent else inputs.scorecard_id,
        "TEST:INCUMBENT" if incumbent else instrument, strategy, V1, scoring, at, at, (),
        inputs.comparison_score if incumbent else inputs.raw_decision_score,
        "COMPLETE", None, ("SYNTHETIC_TEST_ONLY",))


def synthetic_comparison(card, gate_version):
    return ExecutionGateEvaluation("synthetic-comparison", card.instrument_id, card.strategy_version,
        V1, card.configuration_version, gate_version, card.id, "synthetic-snapshot", None,
        card.as_of_timestamp, card.evaluated_at, card.final_score, None, card.final_score, (),
        ExecutionEligibility.INSUFFICIENT_DATA, (), (), ("SYNTHETIC_TEST_ONLY",), (), (), {})


def synthetic_context(inputs, config, *, existing=None):
    refs = list(existing.dependencies) if existing else []
    bound = {x.input_field for x in refs}
    for field in DOMAIN_FIELDS:
        value = getattr(inputs, field)
        if value is None or field in bound:
            continue
        known = inputs.earnings_schedule_verified_at if field == "earnings_schedule_verified_at" else inputs.snapshot_as_of_timestamp
        refs.append(domain_lineage(field, value,
            source_id=getattr(value, "id", inputs.snapshot_id or "synthetic-source"),
            source_version="synthetic-fixture/v1", policy_version=config.version,
            as_of=inputs.snapshot_as_of_timestamp, known_at=known,
            source_fingerprints=(content_fingerprint("synthetic-source:" + field),)))
    return gate_evidence_context(inputs, as_of=inputs.snapshot_as_of_timestamp,
        gate_policy_version=config.version, dependencies=tuple(refs)) if refs else existing


def synthetic_evaluate(engine, **args):
    inputs = args["inputs"]
    # Retain pre-existing firewall assertions before adding fixture provenance.
    require_gate_inputs(inputs, registry_version=args["registry_version"],
        as_of=args["as_of_timestamp"], gate_policy_version=engine.config.version,
        evidence_context=args.get("evidence_context"))
    card = synthetic_card(inputs, instrument=args["instrument_id"], strategy=args["strategy_version"],
        scoring=args["scoring_configuration_version"], at=args["as_of_timestamp"])
    args.setdefault("candidate_score_evidence", score_evidence(card))
    if inputs.comparison_score is not None:
        incumbent = synthetic_card(inputs, instrument="TEST:INCUMBENT", strategy=args["strategy_version"],
            scoring=args["scoring_configuration_version"], at=args["as_of_timestamp"], incumbent=True)
        args.setdefault("incumbent_score_evidence", score_evidence(incumbent,
            comparison_result=synthetic_comparison(incumbent, engine.config.version)))
    if inputs.snapshot_as_of_timestamp == args["as_of_timestamp"]:
        args["evidence_context"] = synthetic_context(inputs, engine.config, existing=args.get("evidence_context"))
    return engine.evaluate(**args)
