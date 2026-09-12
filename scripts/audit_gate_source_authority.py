"""Deterministic isolated authority matrix/replay; no acquisition or DB access."""
from dataclasses import fields, replace
from decimal import Decimal
import json

from app.fundamentals.diagnostic_comparability import content_fingerprint
from app.gates.engine import GateInput, PortfolioExposure, SurveillanceObservation, TradeManagementPlan
from app.gates.source_authority import VERSION
from app.gates.version_compatibility import DOMAIN_FIELDS, GateVersionBlocked, domain_lineage, gate_evidence_context
from scripts.audit_fundamental_v2_gates import audit, GATE_FIELDS

BASELINE = "4027fb63b63000bd9437845d8199ffaa30d2f3dd"
NEXT = "FUNDAMENTAL_V2_SIX_GATES_VERSION_COMPATIBILITY_REPAIR_3"
SOURCES = {
    "raw_decision_score": ("build_scorecard / canonical governance reader", "DecisionScorecard / CanonicalDecisionScorecard", "INDEPENDENT_SCORE_ATTESTATION_READY"),
    "comparison_score": ("canonical governance reader", "stored incumbent scorecard + original ExecutionGateEvaluation", "INDEPENDENT_SCORE_ATTESTATION_READY"),
    "holding_entry_date": ("canonical governance portfolio-snapshot reader", "PortfolioSnapshot.holdings.acquisition_at", "STORED_HOLDING_BINDING_READY"),
    "atr_expansion": (None, "canonical market evidence exists; exact gate ATR adapter not admitted", "PRODUCER_ADAPTER_UNAVAILABLE"),
    "surveillance": (None, "official-nse-surveillance-v1 declared; generic MarketObservation is insufficient", "PRODUCER_ADAPTER_UNAVAILABLE"),
    "trade_plan": (None, "stored app.signals TradePlan is not automatically a governed Gate TradeManagementPlan", "PRODUCER_ADAPTER_UNAVAILABLE"),
    "exposure": (None, "canonical portfolio risk exists; approved candidate-risk scenario binding missing", "PRODUCER_ADAPTER_UNAVAILABLE"),
    "expected_incremental_return": (None, "hypothetical replay argument is not independent approval", "PRODUCER_ADAPTER_UNAVAILABLE"),
    "modeled_switching_friction": (None, "approved friction formula exists; user scenario attestation missing", "PRODUCER_ADAPTER_UNAVAILABLE"),
    "earnings_scheduled_at": (None, "official-nse-earnings-calendar-v1 declaration; no admitted future-event producer", "EARNINGS_CALENDAR_AUTHORITY_NOT_READY"),
    "earnings_schedule_verified_at": (None, "same future-event record required; no filing/publication substitution", "EARNINGS_CALENDAR_AUTHORITY_NOT_READY"),
}


def matrix():
    nested = dict(surveillance=SurveillanceObservation, trade_plan=TradeManagementPlan, exposure=PortfolioExposure)
    rows = []
    for item in fields(GateInput):
        name = item.name
        producer, source, state = SOURCES.get(name, (None, "binding/audit metadata only", "NOT_CLEARANCE_AUTHORITY"))
        score = name in {"raw_decision_score", "comparison_score"}
        for member in fields(nested[name]) if name in nested else (item,):
            rows.append(dict(field=name+"."+member.name if name in nested else name,
                gates=[gate for gate, _, names in GATE_FIELDS if name in names], input_field=name,
                evidence_family="DIAGNOSTIC_SCORE" if score else DOMAIN_FIELDS.get(name, "BINDING_METADATA"),
                trusted_producer=producer, canonical_object=source,
                authority_proof="independent producer recalculation / canonical reader" if score else
                    "exact stored snapshot identity, content, PIT, instrument and acquisition date" if name == "holding_entry_date" else
                    "NONE: fail closed" if name in DOMAIN_FIELDS else "never establishes authority",
                registry_version_applicable=score, policy_source_version_required=score or name in DOMAIN_FIELDS,
                fingerprint_required=score or name in DOMAIN_FIELDS,
                raw_primitive_accepted_as_authority=False, caller_metadata_accepted_as_authority=False,
                final_readiness=state))
    body = dict(version=VERSION, baseline=BASELINE, fields=rows, input_field_count=len(fields(GateInput)),
        expanded_field_count=len(rows), admitted_score_adapters=2, admitted_neutral_field_adapters=1,
        neutral_fields_blocked_without_adapter=[x for x in DOMAIN_FIELDS if x != "holding_entry_date"],
        authority_composition="trusted application constructor dependency; never supplied in evaluate/input/API data",
        threat_model="no protection against Python-code/DI replacement or canonical-store compromise; no PKI claimed")
    return body | dict(fingerprint=content_fingerprint(body))


def receipt():
    # Fixed synthetic diagnostics exercise the REAL scoring producer/admission.
    # They are not production company evidence or claimed production readiness.
    from tests.unit.test_gate_source_authority import score, complete, producer, run_args, evaluate, legacy_inputs, CONFIG
    from app.gates.score_provenance import score_evidence
    card = score(complete()); authority = producer(); a = run_args(card)
    score_attestation = authority.attest_score(score_evidence(card))
    rejections = []
    for field in DOMAIN_FIELDS:
        value = getattr(legacy_inputs(expected_incremental_return=Decimal("1"), modeled_switching_friction=Decimal(".1")), field)
        if field.startswith("earnings_"): value = card.as_of_timestamp
        data = replace(a["inputs"], **{field: value})
        ref = domain_lineage(field, value, source_id=getattr(value, "id", "caller-claims-NSE"),
            source_version="V1", policy_version=CONFIG.version, as_of=card.as_of_timestamp, known_at=card.as_of_timestamp,
            source_fingerprints=(content_fingerprint("caller-claims-TRUSTED"),))
        context = gate_evidence_context(data, as_of=card.as_of_timestamp, gate_policy_version=CONFIG.version, dependencies=(ref,))
        try:
            evaluate(a | dict(inputs=data, evidence_context=context), authority)
        except GateVersionBlocked as error:
            rejections.append(dict(field=field, reason=str(error)))
        else:
            raise AssertionError("caller-declared domain accepted")
    for label, attack in (("raw-score", a | dict(candidate_score_evidence=None)),
                          ("rehashed-fake-v1", run_args(replace(card, final_score=Decimal("7.5"))))):
        try:
            evaluate(attack, authority)
        except GateVersionBlocked as error:
            rejections.append(dict(field=label, reason=str(error)))
        else:
            raise AssertionError("forged score accepted")
    replay = audit()
    body = dict(version=VERSION, baseline=BASELINE, matrix_fingerprint=matrix()["fingerprint"],
        attestation_fingerprint=score_attestation.fingerprint, admission_attacks=rejections,
        unsafe_self_declared_ingress_accepted=0, frozen_v1_replay_cases=replay["replay_case_count"],
        frozen_v1_replay_fingerprint=replay["fingerprint"], all_six_formulas_unchanged=True,
        b08_before="CLOSED_FOR_SHADOW_COMPATIBILITY", b08_after="CLOSED_FOR_SHADOW_COMPATIBILITY",
        b09="STILL_BLOCKING_ACTIVATION", b14="STILL_BLOCKING_ACTIVATION",
        calendar_status="APPROVED_SOURCE_DECLARATION_WITHOUT_ADMITTED_FUTURE_EVENT_PRODUCER",
        remaining_blockers=matrix()["neutral_fields_blocked_without_adapter"],
        writes=0, provider_calls=0, orders=0, v1_active=True, v2_active=False, v2_shadow_only=True,
        next_continuation=NEXT)
    return body | dict(fingerprint=content_fingerprint(body))


if __name__ == "__main__":
    print(json.dumps(dict(matrix=matrix(), receipt=receipt()), sort_keys=True, indent=2))
