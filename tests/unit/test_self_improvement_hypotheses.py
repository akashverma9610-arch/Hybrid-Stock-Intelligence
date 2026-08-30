from datetime import UTC, datetime, timedelta
from decimal import Decimal
from dataclasses import replace
import json

import pytest

from app.backtest.promotion import ApprovedStrategyStatus, ApprovedStrategyVersion, PromotionProposalStatus, ReviewDecision, StrategyPromotionProposal, StrategyPromotionReview
from app.backtest.experiments import ExperimentBudget
from app.backtest.walk_forward import StrategyCandidate
from app.historical.guard import manifest_fingerprint
from app.self_improvement.attribution import SelfImprovementAttributionService
from app.self_improvement.experiment_bridge import SelfImprovementExperimentBridge
from app.self_improvement.hypotheses import SelfImprovementHypothesisService
from app.self_improvement.models import *
from app.services.audit_reconstruction_service import AuditReconstructionError, AuditReconstructionService
from app.storage.sqlite_governance_repository import SQLiteStrategyGovernanceRepository

T = datetime(2026, 10, 1, tzinfo=UTC)


def frozen_run(identifier="hypothesis-run"):
    return SelfImprovementRun(identifier, "strategy-2.1", T, T + timedelta(days=20), (), (), (), (), (), "self-improvement-v1", T, "COMPLETE", (), manifest_fingerprint(run=identifier))


def foundation(repository, value, *observations):
    evidence = SelfImprovementEvidencePolicy("evidence", "1", 2, 1, "evidence-v1", manifest_fingerprint(evidence="1"), recurrence_threshold=2, source_weights=(("HISTORICAL_BACKTEST", Decimal("1")), ("WALK_FORWARD_OOS", Decimal("3")), ("PAPER_FORWARD_TEST", Decimal("3")), ("OTHER_GOVERNED_RESEARCH", Decimal("1"))))
    rules = AttributionRuleSet("rules", "1", 5, Decimal("8"), Decimal("2"), Decimal("1"), Decimal("1"), Decimal(".02"), Decimal(".5"), 10, "rules-v1", manifest_fingerprint(rules="1"))
    generation = HypothesisGenerationPolicy("generation", "1", Decimal("1"), 2, 1, False, "generation-v1", manifest_fingerprint(generation="1"))
    budget = HypothesisProposalBudget("budget", "1", 2, "budget-v1", manifest_fingerprint(budget="1"))
    repository.save_self_improvement_run(value); repository.save_self_improvement_evidence_policy(evidence); repository.save_attribution_rule_set(rules); repository.save_hypothesis_generation_policy(generation); repository.save_hypothesis_proposal_budget(budget)
    for item in observations: repository.save_self_improvement_observation(item)
    return evidence, rules, generation, budget


def observation(identifier, source, run_id, offset=1, **changes):
    fields={"auditable":True,"pit_eligible":True,"audit_valid":True,"outcome":"LOSS","setup_type":"BREAKOUT","triggered":True,"filled":True,"structure_failed":True,"stop_hit":True,"mae_r":"1.2","continuation_failed":True,"volume_confirmed":False,"rvol":".8","regime":"BEAR","sector":"IT","r_impact":"-1","transaction_cost":".1"}
    fields.update(changes)
    return SelfImprovementObservation(identifier,run_id,source,identifier,T+timedelta(days=offset),"strategy-2.1",fields,(f"evidence-{identifier}",),(),manifest_fingerprint(observation=identifier,fields=fields))


def approved_target(repository):
    proposal=StrategyPromotionProposal("proposal","candidate","strategy","2.1","experiment","selection",(),(),(),(),("candidate-fp",),"research",T,PromotionProposalStatus.READY_FOR_REVIEW,(),manifest_fingerprint(proposal="hypothesis"))
    review=StrategyPromotionReview("promotion-review",proposal.proposal_id,"human:promoter",T,ReviewDecision.APPROVE,"approved",(),"1","evidence",manifest_fingerprint(review="hypothesis"))
    target=ApprovedStrategyVersion("approved-target","strategy","2.1",None,proposal.proposal_id,review.review_id,"candidate",("candidate-fp",),T,T+timedelta(days=1),ApprovedStrategyStatus.APPROVED,(),manifest_fingerprint(target="hypothesis"))
    repository.save_strategy_promotion_proposal(proposal); repository.save_strategy_promotion_review(review); repository.save_approved_strategy_version(target)
    return target


def test_actionable_hypothesis_is_deduplicated_ranked_and_auditable(tmp_path):
    repository=SQLiteStrategyGovernanceRepository(tmp_path/"hypotheses.db"); value=frozen_run()
    first=observation("oos",ObservationSource.WALK_FORWARD_OOS,value.run_id)
    second=observation("historical",ObservationSource.HISTORICAL_BACKTEST,value.run_id,2)
    evidence,rules,generation,budget=foundation(repository,value,first,second); target=approved_target(repository)
    SelfImprovementAttributionService(repository).analyze(value.run_id,evidence.policy_id,rules.rule_set_id)
    protected=("approved_strategy_versions","strategy_activations","strategy_experiments","strategy_candidate_deltas")
    before=tuple(repository._connection.execute(f"SELECT COUNT(*) AS count FROM {table}").fetchone()["count"] for table in protected)
    hypotheses,ranking=SelfImprovementHypothesisService(repository).generate(run_id=value.run_id,evidence_policy_id=evidence.policy_id,generation_policy_id=generation.policy_id,budget_id=budget.budget_id,target_approved_strategy_id=target.approved_id,created_at=T+timedelta(days=3))
    actionable=[item for item in hypotheses if item.hypothesis_type is not HypothesisType.REQUEST_MORE_EVIDENCE]
    assert len(actionable)==1 and actionable[0].target_field=="volume_confirmation_threshold"
    assert actionable[0].expected_mechanism and actionable[0].potential_downside and len(actionable[0].originating_pattern_ids)>=2
    assert repository.get_strategy_improvement_hypothesis(actionable[0].hypothesis_id)==actionable[0]
    assert repository.get_strategy_hypothesis_ranking(ranking.ranking_id)==ranking
    assert tuple(repository._connection.execute(f"SELECT COUNT(*) AS count FROM {table}").fetchone()["count"] for table in protected)==before
    AuditReconstructionService(repository).reconstruct_self_improvement_hypotheses(value.run_id,evidence_policy_id=evidence.policy_id,rule_set_id=rules.rule_set_id,generation_policy_id=generation.policy_id,budget_id=budget.budget_id,target_approved_strategy_id=target.approved_id,ranking_id=ranking.ranking_id)


def test_anecdotal_data_quality_no_change_and_hard_invariants(tmp_path):
    repository=SQLiteStrategyGovernanceRepository(tmp_path/"safety.db")
    anecdotal=frozen_run("anecdotal"); evidence,rules,generation,budget=foundation(repository,anecdotal,observation("only",ObservationSource.WALK_FORWARD_OOS,anecdotal.run_id)); target=approved_target(repository)
    SelfImprovementAttributionService(repository).analyze(anecdotal.run_id,evidence.policy_id,rules.rule_set_id)
    generated,_=SelfImprovementHypothesisService(repository).generate(run_id=anecdotal.run_id,evidence_policy_id=evidence.policy_id,generation_policy_id=generation.policy_id,budget_id=budget.budget_id,target_approved_strategy_id=target.approved_id,created_at=T+timedelta(days=3))
    assert {item.hypothesis_type for item in generated}=={HypothesisType.REQUEST_MORE_EVIDENCE}

    quality=frozen_run("quality"); repository.save_self_improvement_run(quality)
    for source,identifier in ((ObservationSource.WALK_FORWARD_OOS,"bad-1"),(ObservationSource.HISTORICAL_BACKTEST,"bad-2")):
        repository.save_self_improvement_observation(observation(identifier,source,quality.run_id,pit_eligible=False))
    SelfImprovementAttributionService(repository).analyze(quality.run_id,evidence.policy_id,rules.rule_set_id)
    generated,_=SelfImprovementHypothesisService(repository).generate(run_id=quality.run_id,evidence_policy_id=evidence.policy_id,generation_policy_id=generation.policy_id,budget_id=budget.budget_id,target_approved_strategy_id=target.approved_id,created_at=T+timedelta(days=3))
    assert {item.hypothesis_type for item in generated}=={HypothesisType.DATA_QUALITY_CHANGE}
    assert all(item.target_domain is ConfigurableTargetDomain.DATA_QUALITY_INFRASTRUCTURE for item in generated)

    empty=frozen_run("empty"); repository.save_self_improvement_run(empty)
    generated,_=SelfImprovementHypothesisService(repository).generate(run_id=empty.run_id,evidence_policy_id=evidence.policy_id,generation_policy_id=generation.policy_id,budget_id=budget.budget_id,target_approved_strategy_id=target.approved_id,created_at=T+timedelta(days=3))
    assert generated[0].hypothesis_type is HypothesisType.NO_CHANGE_RECOMMENDED
    with pytest.raises(ValueError,match="protected"):
        SelfImprovementHypothesisService(repository).validate_target(ConfigurableTargetDomain.EXECUTION_GATE,"pit_lookahead_safety")


def test_human_review_future_evidence_staleness_and_tampering_fail_closed(tmp_path):
    repository=SQLiteStrategyGovernanceRepository(tmp_path/"review.db"); value=frozen_run()
    evidence,rules,generation,budget=foundation(repository,value,observation("oos",ObservationSource.WALK_FORWARD_OOS,value.run_id),observation("historical",ObservationSource.HISTORICAL_BACKTEST,value.run_id,2)); target=approved_target(repository)
    SelfImprovementAttributionService(repository).analyze(value.run_id,evidence.policy_id,rules.rule_set_id)
    hypotheses,ranking=SelfImprovementHypothesisService(repository).generate(run_id=value.run_id,evidence_policy_id=evidence.policy_id,generation_policy_id=generation.policy_id,budget_id=budget.budget_id,target_approved_strategy_id=target.approved_id,created_at=T+timedelta(days=3)); hypothesis=hypotheses[0]
    review=HypothesisReview("human-review",hypothesis.hypothesis_id,"human:research-owner",T+timedelta(days=4),HypothesisReviewDecision.APPROVE_FOR_EXPERIMENT,"EXPERIMENT_VALUE=1.2",hypothesis.evidence_fingerprint,(),"")
    review=replace(review,fingerprint=hypothesis_review_fingerprint(review)); repository.save_hypothesis_review(review)
    assert repository.get_hypothesis_review(review.review_id)==review
    with pytest.raises(ValueError,match="human"):
        repository.save_hypothesis_review(replace(review,review_id="automated",reviewer_id="automation:engine"))
    with pytest.raises(ValueError,match="immutable"):
        repository.save_hypothesis_review(review)
    for identifier, decision in (("rejected-review", HypothesisReviewDecision.REJECT), ("more-evidence-review", HypothesisReviewDecision.REQUEST_MORE_EVIDENCE)):
        alternate=HypothesisReview(identifier,hypothesis.hypothesis_id,"human:research-owner",T+timedelta(days=4),decision,"immutable alternate review",hypothesis.evidence_fingerprint,(),"")
        alternate=replace(alternate,fingerprint=hypothesis_review_fingerprint(alternate)); repository.save_hypothesis_review(alternate)
        assert repository.get_hypothesis_review(identifier)==alternate
    assert SelfImprovementHypothesisService(repository).is_stale(hypothesis,"later-approved-version")
    future=observation("future",ObservationSource.PAPER_FORWARD_TEST,value.run_id,40); repository.save_self_improvement_observation(future)
    assert repository.get_strategy_improvement_hypothesis(hypothesis.hypothesis_id)==hypothesis

    audit=AuditReconstructionService(repository); audit.reconstruct_self_improvement_hypotheses(value.run_id,evidence_policy_id=evidence.policy_id,rule_set_id=rules.rule_set_id,generation_policy_id=generation.policy_id,budget_id=budget.budget_id,target_approved_strategy_id=target.approved_id,ranking_id=ranking.ranking_id,review_id=review.review_id)
    experiment_budget=ExperimentBudget("experiment-budget","1",1,1,{"volume_confirmation_threshold":(Decimal(".5"),Decimal("2"))},1,"experiment-v1",manifest_fingerprint(experiment_budget="1")); repository.save_experiment_budget(experiment_budget)
    baseline=StrategyCandidate("baseline-candidate","strategy-2.1","registry-v1","score-v1","gate-v1","rotation-v1","signal-v1","paper-v1","allocation-v1","performance-v1",manifest_fingerprint(candidate="baseline")); repository.save_strategy_candidate(baseline)
    protected=("strategy_promotion_proposals","promotion_eligibility_results","strategy_promotion_reviews","approved_strategy_versions","strategy_activations","candidate_evaluation_evidence","candidate_selection_results")
    protected_before=tuple(repository._connection.execute(f"SELECT COUNT(*) AS count FROM {table}").fetchone()["count"] for table in protected)
    experiment,delta,candidate,link=SelfImprovementExperimentBridge(repository).create(hypothesis_id=hypothesis.hypothesis_id,review_id=review.review_id,budget_id=experiment_budget.budget_id,baseline_candidate_id=baseline.candidate_id,dataset_id="dataset-v1",dataset_version="1",permitted_partition_ids=("train","validation"),forbidden_test_partition_ids=("test",),current_approved_strategy_id=target.approved_id,created_at=T+timedelta(days=5),baseline_value="1.0")
    assert experiment.status.value=="PLANNED" and delta.experimental_value=="1.2" and candidate.candidate_id in experiment.experimental_candidate_ids
    assert repository.get_hypothesis_experiment_link(link.link_id)==link
    AuditReconstructionService(repository).reconstruct_hypothesis_experiment_link(link.link_id,evidence_policy_id=evidence.policy_id,rule_set_id=rules.rule_set_id,generation_policy_id=generation.policy_id,hypothesis_budget_id=budget.budget_id,ranking_id=ranking.ranking_id)
    assert tuple(repository._connection.execute(f"SELECT COUNT(*) AS count FROM {table}").fetchone()["count"] for table in protected)==protected_before
    with pytest.raises(ValueError,match="already exists"):
        SelfImprovementExperimentBridge(repository).create(hypothesis_id=hypothesis.hypothesis_id,review_id=review.review_id,budget_id=experiment_budget.budget_id,baseline_candidate_id=baseline.candidate_id,dataset_id="dataset-v1",dataset_version="1",permitted_partition_ids=("train","validation"),forbidden_test_partition_ids=("test",),current_approved_strategy_id=target.approved_id,created_at=T+timedelta(days=5),baseline_value="1.0")
    with pytest.raises(ValueError,match="stale"):
        SelfImprovementExperimentBridge(repository).create(hypothesis_id=hypothesis.hypothesis_id,review_id=review.review_id,budget_id=experiment_budget.budget_id,baseline_candidate_id=baseline.candidate_id,dataset_id="dataset-v1",dataset_version="1",permitted_partition_ids=("train",),forbidden_test_partition_ids=("test",),current_approved_strategy_id="later-approved",created_at=T+timedelta(days=5),baseline_value="1.0")
    for identifier,decision,comment,error in (("bridge-reject",HypothesisReviewDecision.REJECT,"EXPERIMENT_VALUE=1.2","APPROVE_FOR_EXPERIMENT"),("bridge-more",HypothesisReviewDecision.REQUEST_MORE_EVIDENCE,"EXPERIMENT_VALUE=1.2","APPROVE_FOR_EXPERIMENT"),("bridge-direction",HypothesisReviewDecision.APPROVE_FOR_EXPERIMENT,"direction only","explicit human-reviewed"),("bridge-range",HypothesisReviewDecision.APPROVE_FOR_EXPERIMENT,"EXPERIMENT_VALUE=9","outside")):
        alternate=HypothesisReview(identifier,hypothesis.hypothesis_id,"human:research-owner",T+timedelta(days=4),decision,comment,hypothesis.evidence_fingerprint,(),""); alternate=replace(alternate,fingerprint=hypothesis_review_fingerprint(alternate)); repository.save_hypothesis_review(alternate)
        with pytest.raises(ValueError,match=error): SelfImprovementExperimentBridge(repository).create(hypothesis_id=hypothesis.hypothesis_id,review_id=alternate.review_id,budget_id=experiment_budget.budget_id,baseline_candidate_id=baseline.candidate_id,dataset_id="dataset-v1",dataset_version="1",permitted_partition_ids=("train",),forbidden_test_partition_ids=("test",),current_approved_strategy_id=target.approved_id,created_at=T+timedelta(days=5),baseline_value="1.0")
    future_after_experiment=observation("future-after-experiment",ObservationSource.PAPER_FORWARD_TEST,value.run_id,50); repository.save_self_improvement_observation(future_after_experiment)
    assert repository.get_hypothesis_experiment_link(link.link_id)==link
    AuditReconstructionService(repository).reconstruct_hypothesis_experiment_link(link.link_id,evidence_policy_id=evidence.policy_id,rule_set_id=rules.rule_set_id,generation_policy_id=generation.policy_id,hypothesis_budget_id=budget.budget_id,ranking_id=ranking.ranking_id)
    def tamper_bridge(table,identifier,mutate):
        original=repository._connection.execute(f"SELECT payload_json FROM {table} WHERE id=?",(identifier,)).fetchone()["payload_json"]; changed=json.loads(original); mutate(changed); repository._connection.execute(f"UPDATE {table} SET payload_json=? WHERE id=?",(json.dumps(changed),identifier)); repository._connection.commit()
        with pytest.raises(AuditReconstructionError): AuditReconstructionService(repository).reconstruct_hypothesis_experiment_link(link.link_id,evidence_policy_id=evidence.policy_id,rule_set_id=rules.rule_set_id,generation_policy_id=generation.policy_id,hypothesis_budget_id=budget.budget_id,ranking_id=ranking.ranking_id)
        repository._connection.execute(f"UPDATE {table} SET payload_json=? WHERE id=?",(original,identifier)); repository._connection.commit()
    tamper_bridge("strategy_candidate_deltas",delta.delta_id,lambda item:item.__setitem__("experimental_value","1.3"))
    tamper_bridge("strategy_experiments",experiment.experiment_id,lambda item:item.__setitem__("status","COMPLETED"))
    tamper_bridge("strategy_candidates",candidate.candidate_id,lambda item:item.__setitem__("fingerprint","tampered"))
    tamper_bridge("hypothesis_experiment_links",link.link_id,lambda item:item.__setitem__("baseline_candidate_id","other"))
    def tamper(table,identifier,mutate):
        original=repository._connection.execute(f"SELECT payload_json FROM {table} WHERE id=?",(identifier,)).fetchone()["payload_json"]; changed=json.loads(original); mutate(changed); repository._connection.execute(f"UPDATE {table} SET payload_json=? WHERE id=?",(json.dumps(changed),identifier)); repository._connection.commit()
        with pytest.raises(AuditReconstructionError): audit.reconstruct_self_improvement_hypotheses(value.run_id,evidence_policy_id=evidence.policy_id,rule_set_id=rules.rule_set_id,generation_policy_id=generation.policy_id,budget_id=budget.budget_id,target_approved_strategy_id=target.approved_id,ranking_id=ranking.ranking_id,review_id=review.review_id)
        repository._connection.execute(f"UPDATE {table} SET payload_json=? WHERE id=?",(original,identifier)); repository._connection.commit()
    tamper("strategy_improvement_hypotheses",hypothesis.hypothesis_id,lambda item:item.__setitem__("target_field","pit_lookahead_safety"))
    tamper("strategy_improvement_hypotheses",hypothesis.hypothesis_id,lambda item:item.__setitem__("target_strategy_version","9.9"))
    tamper("strategy_improvement_hypotheses",hypothesis.hypothesis_id,lambda item:item.__setitem__("hypothesis_type","EXIT_PARAMETER_CHANGE"))
    tamper("strategy_improvement_hypotheses",hypothesis.hypothesis_id,lambda item:item.__setitem__("target_domain","EXIT"))
    tamper("strategy_improvement_hypotheses",hypothesis.hypothesis_id,lambda item:item.__setitem__("proposed_direction","LOOSER"))
    tamper("strategy_improvement_hypotheses",hypothesis.hypothesis_id,lambda item:item.__setitem__("expected_mechanism","tampered"))
    tamper("strategy_improvement_hypotheses",hypothesis.hypothesis_id,lambda item:item.__setitem__("potential_downside",""))
    tamper("strategy_improvement_hypotheses",hypothesis.hypothesis_id,lambda item:item.__setitem__("evidence_status","MIXED"))
    tamper("strategy_improvement_hypotheses",hypothesis.hypothesis_id,lambda item:item.__setitem__("complexity_estimate","HIGH"))
    pattern=repository.list_recurring_strategy_patterns(value.run_id)[0]
    tamper("recurring_strategy_patterns",pattern.pattern_id,lambda item:item.__setitem__("supporting_attribution_ids",[]))
    tamper("strategy_hypothesis_rankings",ranking.ranking_id,lambda item:item.__setitem__("ordered_hypothesis_ids",[]))
    tamper("strategy_hypothesis_rankings",ranking.ranking_id,lambda item:item.__setitem__("factor_values",[]))
    tamper("hypothesis_reviews",review.review_id,lambda item:item.__setitem__("decision","REJECT"))
    tamper("hypothesis_reviews",review.review_id,lambda item:item.__setitem__("reviewer_id","human:other"))
    tamper("hypothesis_reviews",review.review_id,lambda item:item.__setitem__("reviewed_at",(T+timedelta(days=5)).isoformat()))


def test_hypothesis_budget_is_deterministic_and_does_not_create_experiments(tmp_path):
    repository=SQLiteStrategyGovernanceRepository(tmp_path/"budget.db"); value=frozen_run("budget-run")
    evidence,rules,generation,budget=foundation(repository,value); target=approved_target(repository)
    def pattern(identifier, category):
        fingerprint=manifest_fingerprint(pattern=identifier)
        return RecurringStrategyPattern(identifier,value.run_id,category,AttributionKind.ERROR,(f"support-{identifier}",),3,Decimal("5"),2,1,0,(("WALK_FORWARD_OOS",2),("HISTORICAL_BACKTEST",1)),("BEAR",),("IT",),("HIGH",),("HIGH",),Decimal("-3"),Decimal(".3"),PatternEvidenceStatus.ELIGIBLE,(),evidence.policy_id,evidence.version,rules.rule_set_id,rules.version,fingerprint)
    repository.save_recurring_strategy_pattern(pattern("pattern-false",ErrorCategory.FALSE_BREAKOUT.value)); repository.save_recurring_strategy_pattern(pattern("pattern-stop",ErrorCategory.STOP_TOO_TIGHT.value))
    limited=replace(budget,budget_id="budget-one",maximum_experiment_proposals=1,fingerprint=manifest_fingerprint(budget="one")); repository.save_hypothesis_proposal_budget(limited)
    hypotheses,ranking=SelfImprovementHypothesisService(repository).generate(run_id=value.run_id,evidence_policy_id=evidence.policy_id,generation_policy_id=generation.policy_id,budget_id=limited.budget_id,target_approved_strategy_id=target.approved_id,created_at=T+timedelta(days=3))
    assert len(hypotheses)==1 and ranking.excluded_hypothesis_reasons and ranking.excluded_hypothesis_reasons[0][1]=="PROPOSAL_BUDGET_EXCEEDED"
    assert repository._connection.execute("SELECT COUNT(*) AS count FROM strategy_experiments").fetchone()["count"]==0
