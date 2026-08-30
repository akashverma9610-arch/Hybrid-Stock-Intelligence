from datetime import UTC, datetime, timedelta
from decimal import Decimal
import json
from dataclasses import replace

import pytest

from app.historical.guard import manifest_fingerprint
from app.self_improvement.attribution import SelfImprovementAttributionService
from app.self_improvement.models import (
    AttributionRuleSet, ErrorCategory, ObservationSource, PatternEvidenceStatus,
    SelfImprovementEvidencePolicy, SelfImprovementObservation, SelfImprovementRun,
    SuccessCategory,
)
from app.services.audit_reconstruction_service import AuditReconstructionError, AuditReconstructionService
from app.storage.sqlite_governance_repository import SQLiteStrategyGovernanceRepository

T = datetime(2026, 9, 1, tzinfo=UTC)


def run(identifier="research-run"):
    return SelfImprovementRun(identifier, "strategy-2.1", T, T + timedelta(days=30), ("backtest",), ("walk-forward",), ("aggregate",), (), (), "self-improvement-v1", T, "COMPLETE", (), manifest_fingerprint(run=identifier))


def policy():
    return SelfImprovementEvidencePolicy("evidence-policy", "1", 2, 1, "policy-v1", manifest_fingerprint(policy="v1"), recurrence_threshold=2, source_weights=(("HISTORICAL_BACKTEST", Decimal("1")), ("WALK_FORWARD_OOS", Decimal("3")), ("PAPER_FORWARD_TEST", Decimal("3")), ("OTHER_GOVERNED_RESEARCH", Decimal("1"))))


def rules():
    return AttributionRuleSet("attribution-rules", "1", 5, Decimal("8"), Decimal("2"), Decimal("1"), Decimal("1"), Decimal(".02"), Decimal(".5"), 10, "attribution-v1", manifest_fingerprint(rules="v1"))


def observation(identifier, source, *, run_id="research-run", offset=1, **overrides):
    fields = {
        "auditable": True, "pit_eligible": True, "audit_valid": True,
        "outcome": "LOSS", "setup_type": "BREAKOUT", "triggered": True,
        "filled": True, "structure_failed": True, "stop_hit": True,
        "mae_r": "1.2", "continuation_failed": True, "decision_score": "9",
        "gates_passed": True, "rvol": "0.8", "volume_confirmed": False,
        "regime": "BEAR", "sector": "IT", "score_band": "HIGH",
        "confidence_band": "HIGH", "r_impact": "-1.1", "transaction_cost": "0.1",
    }
    fields.update(overrides)
    return SelfImprovementObservation(identifier, run_id, source, f"artifact-{identifier}", T + timedelta(days=offset), "strategy-2.1", fields, (f"evidence-{identifier}",), (), manifest_fingerprint(observation=identifier, fields=fields))


def persist_foundation(repository, value, *observations):
    repository.save_self_improvement_run(value)
    repository.save_self_improvement_evidence_policy(policy())
    repository.save_attribution_rule_set(rules())
    for item in observations: repository.save_self_improvement_observation(item)


def test_repeated_pattern_is_eligible_and_all_outputs_round_trip(tmp_path):
    repository = SQLiteStrategyGovernanceRepository(tmp_path / "attribution.db")
    value = run()
    first = observation("false-breakout-oos", ObservationSource.WALK_FORWARD_OOS, offset=1)
    second = observation("false-breakout-historical", ObservationSource.HISTORICAL_BACKTEST, offset=2, regime="RANGE", sector="BANK")
    persist_foundation(repository, value, first, second)
    protected_tables = ("approved_strategy_versions", "strategy_activations", "decision_scorecards", "execution_gate_evaluations", "historical_rotation_evaluations", "signal_config_snapshots", "paper_config_snapshots")
    protected_before = tuple(repository._connection.execute(f"SELECT COUNT(*) AS count FROM {table}").fetchone()["count"] for table in protected_tables)
    assert repository.get_attribution_rule_set("attribution-rules") == rules()
    with pytest.raises(ValueError, match="immutable"):
        repository.save_attribution_rule_set(rules())
    errors, successes, patterns, error_summaries, success_summaries = SelfImprovementAttributionService(repository).analyze(value.run_id, "evidence-policy", "attribution-rules")
    false_breakout = next(item for item in patterns if item.category == ErrorCategory.FALSE_BREAKOUT.value)
    assert false_breakout.evidence_status is PatternEvidenceStatus.ELIGIBLE
    assert false_breakout.occurrence_count == 2 and false_breakout.oos_occurrence_count == 1
    assert false_breakout.weighted_evidence_count == Decimal("4")
    assert all(item.source in {ObservationSource.WALK_FORWARD_OOS, ObservationSource.HISTORICAL_BACKTEST} for item in errors)
    assert repository.list_strategy_error_attributions(value.run_id) == tuple(sorted(errors, key=lambda item: item.attribution_id))
    assert repository.list_strategy_success_attributions(value.run_id) == successes
    assert repository.list_recurring_strategy_patterns(value.run_id) == tuple(sorted(patterns, key=lambda item: item.pattern_id))
    assert repository.list_strategy_error_summaries(value.run_id) == tuple(sorted(error_summaries, key=lambda item: item.summary_id))
    assert repository.list_strategy_success_summaries(value.run_id) == success_summaries
    assert tuple(repository._connection.execute(f"SELECT COUNT(*) AS count FROM {table}").fetchone()["count"] for table in protected_tables) == protected_before
    with pytest.raises(ValueError, match="immutable"):
        repository.save_recurring_strategy_pattern(false_breakout)
    assert AuditReconstructionService(repository).reconstruct_self_improvement(value.run_id, policy_id="evidence-policy", rule_set_id="attribution-rules")[0] == value


def test_single_data_quality_and_mixed_evidence_are_not_generalized(tmp_path):
    repository = SQLiteStrategyGovernanceRepository(tmp_path / "safety.db")
    isolated = run("isolated-run")
    only = observation("isolated-failure", ObservationSource.WALK_FORWARD_OOS, run_id=isolated.run_id)
    persist_foundation(repository, isolated, only)
    errors, _, patterns, _, _ = SelfImprovementAttributionService(repository).analyze(isolated.run_id, "evidence-policy", "attribution-rules")
    assert ErrorCategory.FALSE_BREAKOUT in {item.category for item in errors}
    assert next(item for item in patterns if item.category == ErrorCategory.FALSE_BREAKOUT.value).evidence_status is PatternEvidenceStatus.ANECDOTAL
    assert repository.get_improvement_hypothesis("hypothesis-never-generated") is None

    mixed = run("mixed-run")
    first = observation("mixed-one", ObservationSource.WALK_FORWARD_OOS, run_id=mixed.run_id)
    second = observation("mixed-two", ObservationSource.HISTORICAL_BACKTEST, run_id=mixed.run_id, offset=2, counterevidence=True)
    repository.save_self_improvement_run(mixed)
    repository.save_self_improvement_observation(first); repository.save_self_improvement_observation(second)
    _, _, mixed_patterns, _, _ = SelfImprovementAttributionService(repository).analyze(mixed.run_id, "evidence-policy", "attribution-rules")
    pattern = next(item for item in mixed_patterns if item.category == ErrorCategory.FALSE_BREAKOUT.value)
    assert pattern.evidence_status is PatternEvidenceStatus.MIXED and "COUNTEREVIDENCE_RETAINED" in pattern.warnings and "REGIME_CONCENTRATED" in pattern.warnings

    quality = run("quality-run")
    bad = observation("stale-source", ObservationSource.PAPER_FORWARD_TEST, run_id=quality.run_id, pit_eligible=False)
    repository.save_self_improvement_run(quality); repository.save_self_improvement_observation(bad)
    quality_errors, _, quality_patterns, _, _ = SelfImprovementAttributionService(repository).analyze(quality.run_id, "evidence-policy", "attribution-rules")
    assert {item.category for item in quality_errors} == {ErrorCategory.DATA_QUALITY_FAILURE}
    assert quality_patterns == ()


def test_success_false_negative_and_grouped_diagnostics_remain_descriptive(tmp_path):
    repository = SQLiteStrategyGovernanceRepository(tmp_path / "success.db")
    value = run("success-run")
    first = observation("success-oos", ObservationSource.WALK_FORWARD_OOS, run_id=value.run_id, outcome="WIN", relative_strength="STRONG", sector_phase="LEADING", volume_confirmed=True, earnings_acceleration=True, catalyst_follow_through=True, rr="3", hold_sessions=3, mfe_r="2", multi_factor_aligned=True, regime_match=True, diagnostic_ids=("RULE_6",), score_components={"RS": "STRONG"}, threshold_neighborhood="SCORE_ABOVE")
    second = observation("success-paper", ObservationSource.PAPER_FORWARD_TEST, run_id=value.run_id, offset=2, **first.fields)
    persist_foundation(repository, value, first, second)
    _, successes, patterns, _, summaries = SelfImprovementAttributionService(repository).analyze(value.run_id, "evidence-policy", "attribution-rules")
    assert SuccessCategory.HIGH_RS_BREAKOUT_SUCCESS in {item.category for item in successes}
    assert next(item for item in patterns if item.category == SuccessCategory.HIGH_RS_BREAKOUT_SUCCESS.value).evidence_status is PatternEvidenceStatus.ELIGIBLE
    assert any(name == "KEY_DIAGNOSTIC" and values == (("RULE_6", 2),) for name, values in summaries[0].analysis_groups)
    assert any(name == "SCORE_COMPONENT" and values == (("RS:STRONG", 2),) for name, values in summaries[0].analysis_groups)

    false_negative = run("false-negative-run")
    missed = observation("strict-miss", ObservationSource.WALK_FORWARD_OOS, run_id=false_negative.run_id, rejected_or_expired=True, counterfactual_executable=True, counterfactual_outcome="WIN", capital_insufficient=True)
    repository.save_self_improvement_run(false_negative); repository.save_self_improvement_observation(missed)
    _, missed_successes, _, _, _ = SelfImprovementAttributionService(repository).analyze(false_negative.run_id, "evidence-policy", "attribution-rules")
    assert {SuccessCategory.STRICT_EXECUTABLE_FALSE_NEGATIVE, SuccessCategory.CAPITAL_CONSTRAINT_MISS} <= {item.category for item in missed_successes}


def test_classifier_matrix_future_evidence_and_audit_tampering_fail_closed(tmp_path):
    repository = SQLiteStrategyGovernanceRepository(tmp_path / "tamper.db")
    value = run()
    first = observation("matrix-oos", ObservationSource.WALK_FORWARD_OOS, relative_strength="WEAK", sector_phase="ROTATING_OUT", regime_match=False, rr="1.5", counterfactual_target_reached=True, wider_stop_required="1.1", modest_wider_stop_limit="1.2", stop_loss_r="2", mfe_r="0.2", entry_before_confirmation=True, later_confirmation=True, early_mae_r="1.1", intended_entry_price="100", actual_fill_price="103", gross_pnl="1", transaction_cost="0.6", net_pnl="-0.1", hold_sessions=12, rotation_underperformed_incumbent=True, rotation_timing="EARLY")
    second = observation("matrix-historical", ObservationSource.HISTORICAL_BACKTEST, offset=2, **first.fields)
    persist_foundation(repository, value, first, second)
    errors, _, patterns, summaries, _ = SelfImprovementAttributionService(repository).analyze(value.run_id, "evidence-policy", "attribution-rules")
    expected = {ErrorCategory.FALSE_BREAKOUT, ErrorCategory.HIGH_SCORE_FAILURE, ErrorCategory.WEAK_RELATIVE_STRENGTH, ErrorCategory.SECTOR_MISALIGNMENT, ErrorCategory.REGIME_MISMATCH, ErrorCategory.LOW_REWARD_TO_RISK, ErrorCategory.VOLUME_CONFIRMATION_FAILURE, ErrorCategory.STOP_TOO_TIGHT, ErrorCategory.STOP_TOO_LOOSE, ErrorCategory.ENTRY_TOO_EARLY, ErrorCategory.ENTRY_TOO_LATE, ErrorCategory.EXCESSIVE_FRICTION, ErrorCategory.LOW_CAPITAL_VELOCITY, ErrorCategory.CAPITAL_ROTATION_TOO_EARLY}
    assert expected <= {item.category for item in errors}
    assert all(pattern.rule_set_version == "1" for pattern in patterns) and summaries
    audit = AuditReconstructionService(repository); audit.reconstruct_self_improvement(value.run_id, policy_id="evidence-policy", rule_set_id="attribution-rules")

    def tamper(table, identifier, mutate):
        original = repository._connection.execute(f"SELECT payload_json FROM {table} WHERE id=?", (identifier,)).fetchone()["payload_json"]
        changed = json.loads(original); mutate(changed)
        repository._connection.execute(f"UPDATE {table} SET payload_json=? WHERE id=?", (json.dumps(changed), identifier)); repository._connection.commit()
        with pytest.raises(AuditReconstructionError): audit.reconstruct_self_improvement(value.run_id, policy_id="evidence-policy", rule_set_id="attribution-rules")
        repository._connection.execute(f"UPDATE {table} SET payload_json=? WHERE id=?", (original, identifier)); repository._connection.commit()

    tamper("self_improvement_observations", first.observation_id, lambda item: item.__setitem__("source", "PAPER_FORWARD_TEST"))
    tamper("self_improvement_observations", first.observation_id, lambda item: item.__setitem__("strategy_version", "other-strategy"))
    tamper("self_improvement_evidence_policies", "evidence-policy", lambda item: item.__setitem__("version", "2"))
    tamper("attribution_rule_sets", "attribution-rules", lambda item: item.__setitem__("high_score_threshold", "99"))
    tamper("strategy_error_attributions", errors[0].attribution_id, lambda item: item.__setitem__("category", "DATA_QUALITY_FAILURE"))
    tamper("strategy_error_attributions", errors[0].attribution_id, lambda item: item.__setitem__("strength", "INSUFFICIENT_EVIDENCE"))
    tamper("recurring_strategy_patterns", patterns[0].pattern_id, lambda item: item.__setitem__("supporting_attribution_ids", []))
    tamper("recurring_strategy_patterns", patterns[0].pattern_id, lambda item: item.__setitem__("occurrence_count", 99))
    tamper("recurring_strategy_patterns", patterns[0].pattern_id, lambda item: item.__setitem__("oos_occurrence_count", 99))
    tamper("strategy_error_summaries", summaries[0].summary_id, lambda item: item.__setitem__("count", 99))
    tamper("strategy_error_summaries", summaries[0].summary_id, lambda item: item.__setitem__("regime_split", [["OTHER", 99]]))
    v2 = replace(rules(), rule_set_id="attribution-rules-v2", version="2", fingerprint=manifest_fingerprint(rules="v2"))
    repository.save_attribution_rule_set(v2)
    assert repository.get_attribution_rule_set("attribution-rules") == rules()
    later = observation("future-evidence", ObservationSource.PAPER_FORWARD_TEST, offset=40)
    repository.save_self_improvement_observation(later)
    assert repository.list_recurring_strategy_patterns(value.run_id) == tuple(sorted(patterns, key=lambda item: item.pattern_id))
    audit.reconstruct_self_improvement(value.run_id, policy_id="evidence-policy", rule_set_id="attribution-rules")
