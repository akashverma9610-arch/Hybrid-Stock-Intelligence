from dataclasses import replace
from datetime import timedelta
from decimal import Decimal

import pytest

from app.backtest.experiments import *
from app.backtest.walk_forward import StrategyCandidate
from app.historical.guard import manifest_fingerprint
from app.historical.models import PartitionType
from app.services.audit_reconstruction_service import AuditReconstructionError, AuditReconstructionService
from tests.integration.test_walk_forward_execution import T, frozen_objects


def setup(tmp_path):
    repo, data, baseline, _plan, windows, _run=frozen_objects(tmp_path)
    baseline=replace(baseline,candidate_id="baseline",fingerprint=manifest_fingerprint(candidate="baseline")); repo.save_strategy_candidate(baseline)
    variant=replace(baseline,candidate_id="variant",strategy_version="strategy-v2.1-exp",fingerprint=manifest_fingerprint(candidate="variant")); repo.save_strategy_candidate(variant)
    budget=ExperimentBudget("budget", "1", 2, 2, {"rotation_hurdle":(Decimal(".8"),Decimal("1.2"))}, 3, "experiment-v1", manifest_fingerprint(budget="1")); repo.save_experiment_budget(budget)
    experiment=StrategyExperiment("experiment","Higher rotation hurdle","Test a stricter approved rotation hurdle",baseline.candidate_id,(variant.candidate_id,),data.dataset_id,data.dataset_version,("train","validation"),(windows[0].test.partition_id,),budget.budget_id,"experiment-v1",T,ExperimentStatus.PLANNED,(),manifest_fingerprint(experiment="1")); repo.save_strategy_experiment(experiment)
    delta=StrategyCandidateDelta("delta",variant.candidate_id,"rotation_hurdle","0.8","1.0","Explicit local parameter change",manifest_fingerprint(delta="1"),experiment.experiment_id); repo.save_strategy_candidate_delta(delta)
    policy=CandidateSelectionPolicy("selection-policy","1",3,Decimal("1"),Decimal(".1"),Decimal(".05"),Decimal("10"),Decimal(".1"),Decimal(".3"),"selection-v1",manifest_fingerprint(policy="1"))
    return repo, baseline, variant, experiment, budget, policy


def evidence(experiment,candidate,identifier,partition,at,expectancy,sharpe,drawdown=Decimal("-.1"),trades=5):
    return CandidateEvaluationEvidence(identifier,experiment.experiment_id,candidate.candidate_id,partition,partition.value.lower(),f"run-{identifier}",f"report-{identifier}",None,at,trades,Decimal(".1"),drawdown,sharpe,sharpe,expectancy,Decimal("2"),Decimal("1"),"COMPLETED",(),manifest_fingerprint(identifier=identifier))


def test_explicit_experiment_selects_only_validation_candidate_and_round_trips(tmp_path):
    repo, baseline, variant, experiment, budget, policy=setup(tmp_path); service=ControlledCandidateExperimentService(repo)
    delta=repo.list_strategy_candidate_deltas(experiment.experiment_id)[0]; service.validate_experiment(experiment,budget,(delta,))
    for item in (evidence(experiment,baseline,"base-train",PartitionType.TRAIN,T,Decimal("1"),Decimal(".5")),evidence(experiment,variant,"var-train",PartitionType.TRAIN,T,Decimal("2"),Decimal(".7")),evidence(experiment,baseline,"base-val",PartitionType.VALIDATION,T+timedelta(days=1),Decimal("1"),Decimal(".5")),evidence(experiment,variant,"var-val",PartitionType.VALIDATION,T+timedelta(days=1),Decimal("2.5"),Decimal(".8"))): repo.save_candidate_evaluation_evidence(item)
    selection=service.select(experiment_id=experiment.experiment_id,policy=policy,selection_timestamp=T+timedelta(days=2))
    assert selection.status is CandidateSelectionStatus.CANDIDATE_SELECTED and selection.selected_candidate_id==variant.candidate_id
    assert repo.get_candidate_selection_result(selection.selection_id)==selection
    assert AuditReconstructionService(repo).reconstruct_candidate_selection_result(selection.selection_id)[0]==selection
    with pytest.raises(ValueError,match="immutable"): repo.save_candidate_selection_result(selection)


def test_test_evidence_and_budget_overrun_fail_closed(tmp_path):
    repo, baseline, variant, experiment, budget, policy=setup(tmp_path); service=ControlledCandidateExperimentService(repo)
    repo.save_candidate_evaluation_evidence(evidence(experiment,baseline,"base-test",PartitionType.TEST,T,Decimal("1"),Decimal("1")))
    with pytest.raises(ValueError,match="TEST evidence"): service.select(experiment_id=experiment.experiment_id,policy=policy,selection_timestamp=T+timedelta(days=1))
    too_many=replace(budget,maximum_changed_parameters=0)
    with pytest.raises(ValueError,match="changed-parameter budget"): service.validate_experiment(experiment,too_many,repo.list_strategy_candidate_deltas(experiment.experiment_id))


def test_robustness_marks_knife_edge_without_strategy_mutation(tmp_path):
    repo, baseline, variant, experiment, _budget, _policy=setup(tmp_path); service=ControlledCandidateExperimentService(repo)
    items=(evidence(experiment,variant,"near-low",PartitionType.VALIDATION,T,Decimal("1"),Decimal(".5")),evidence(experiment,variant,"near-high",PartitionType.VALIDATION,T,Decimal("1"),Decimal(".5")))
    items=(replace(items[0],return_value=Decimal("-.3")),replace(items[1],return_value=Decimal(".5")))
    robust=service.robustness(experiment_id=experiment.experiment_id,candidate_id=variant.candidate_id,neighboring_candidate_ids=("near-low","near-high"),evidence=items,knife_edge=Decimal(".2")); repo.save_candidate_robustness_result(robust)
    assert robust.status is RobustnessStatus.FRAGILE and "KNIFE_EDGE_PARAMETER_SENSITIVITY" in robust.warnings
    assert repo.get_strategy_candidate(baseline.candidate_id)==baseline and repo.get_strategy_candidate(variant.candidate_id)==variant
