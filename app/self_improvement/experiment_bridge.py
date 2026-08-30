"""Human-approved, non-executing bridge into the existing experiment records."""
import re
from dataclasses import replace
from datetime import datetime
from decimal import Decimal

from app.backtest.experiments import ControlledCandidateExperimentService, ExperimentStatus, StrategyCandidateDelta, StrategyExperiment
from app.historical.guard import manifest_fingerprint
from .hypotheses import SelfImprovementHypothesisService
from .models import ConfigurableTargetDomain, HypothesisExperimentLink, HypothesisReviewDecision, HypothesisType


class SelfImprovementExperimentBridge:
    _ACTIONABLE = {HypothesisType.WEIGHT_ADJUSTMENT,HypothesisType.THRESHOLD_ADJUSTMENT,HypothesisType.GATE_PARAMETER_CHANGE,HypothesisType.ROTATION_PARAMETER_CHANGE,HypothesisType.SIGNAL_PARAMETER_CHANGE,HypothesisType.EXIT_PARAMETER_CHANGE,HypothesisType.SIZING_PARAMETER_CHANGE}

    def __init__(self, repository): self.repository=repository

    @staticmethod
    def _reviewed_value(comments: str) -> str:
        match=re.search(r"(?:^|\s)EXPERIMENT_VALUE=([-+]?\d+(?:\.\d+)?)(?:\s|$)",comments)
        if match is None: raise ValueError("Direction-only hypothesis requires an explicit human-reviewed EXPERIMENT_VALUE before experiment creation.")
        return match.group(1)

    def create(self, *, hypothesis_id: str, review_id: str, budget_id: str, baseline_candidate_id: str, dataset_id: str, dataset_version: str, permitted_partition_ids: tuple[str,...], forbidden_test_partition_ids: tuple[str,...], current_approved_strategy_id: str, created_at: datetime, baseline_value: str):
        hypothesis=self.repository.get_strategy_improvement_hypothesis(hypothesis_id); review=self.repository.get_hypothesis_review(review_id); budget=self.repository.get_experiment_budget(budget_id); baseline=self.repository.get_strategy_candidate(baseline_candidate_id)
        if None in (hypothesis,review,budget,baseline): raise ValueError("Bridge requires persisted frozen hypothesis, human review, budget, and complete baseline candidate.")
        target=self.repository.get_approved_strategy_version(hypothesis.target_approved_strategy_id)
        if target is None or hypothesis.target_approved_strategy_id!=current_approved_strategy_id or not baseline.strategy_version.endswith(target.version): raise ValueError("Hypothesis target baseline is stale or does not match the complete candidate.")
        if review.hypothesis_id!=hypothesis_id or review.decision is not HypothesisReviewDecision.APPROVE_FOR_EXPERIMENT or not review.reviewer_id.startswith("human:") or review.evidence_fingerprint!=hypothesis.evidence_fingerprint or review.reviewed_at<hypothesis.created_at: raise ValueError("Bridge requires an exact explicit human APPROVE_FOR_EXPERIMENT review.")
        if hypothesis.hypothesis_type not in self._ACTIONABLE or hypothesis.target_domain in {ConfigurableTargetDomain.NONE,ConfigurableTargetDomain.DATA_QUALITY_INFRASTRUCTURE}: raise ValueError("Hypothesis type is not applicable to a trading strategy experiment.")
        SelfImprovementHypothesisService(self.repository).validate_target(hypothesis.target_domain,hypothesis.target_field)
        if hypothesis.target_field is None or hypothesis.target_field not in budget.permitted_ranges: raise ValueError("Hypothesis target field is not supported by the frozen experiment budget.")
        experimental_value=self._reviewed_value(review.comments)
        lower,upper=budget.permitted_ranges[hypothesis.target_field]
        if not lower<=Decimal(experimental_value)<=upper: raise ValueError("Reviewed experimental value is outside the frozen experiment budget range.")
        seed=manifest_fingerprint(hypothesis=hypothesis.fingerprint,review=review.fingerprint,budget=budget.fingerprint,baseline=baseline.fingerprint,value=experimental_value,dataset=(dataset_id,dataset_version),partitions=permitted_partition_ids)
        link_id="hypothesis-experiment-link-"+seed[:24]
        if self.repository.get_hypothesis_experiment_link(link_id) is not None: raise ValueError("This frozen hypothesis/review/baseline/budget bridge already exists.")
        candidate_id="hypothesis-candidate-"+seed[:24]
        candidate=replace(baseline,candidate_id=candidate_id,fingerprint=manifest_fingerprint(baseline=baseline.fingerprint,hypothesis=hypothesis.fingerprint,review=review.fingerprint,value=experimental_value))
        experiment_id="hypothesis-experiment-"+seed[:24]
        experiment=StrategyExperiment(experiment_id,f"Hypothesis experiment: {hypothesis.title}",f"HYPOTHESIS_ID:{hypothesis.hypothesis_id}\n{hypothesis.description}",baseline.candidate_id,(candidate.candidate_id,),dataset_id,dataset_version,permitted_partition_ids,forbidden_test_partition_ids,budget.budget_id,"self-improvement-bridge-v1",created_at,ExperimentStatus.PLANNED,(f"HYPOTHESIS_ID:{hypothesis.hypothesis_id}",f"HYPOTHESIS_REVIEW_ID:{review.review_id}","DRAFT_ONLY_NOT_EXECUTED"),manifest_fingerprint(seed=seed,experiment="v1"))
        delta=StrategyCandidateDelta("hypothesis-delta-"+seed[:24],candidate.candidate_id,hypothesis.target_field,baseline_value,experimental_value,hypothesis.expected_mechanism,manifest_fingerprint(seed=seed,delta=hypothesis.target_field),experiment.experiment_id)
        self._validate_with_candidate(candidate,experiment,budget,delta)
        link=HypothesisExperimentLink(link_id,hypothesis.run_id,hypothesis.hypothesis_id,review.review_id,experiment.experiment_id,(delta.delta_id,),baseline.candidate_id,hypothesis.target_approved_strategy_id,hypothesis.target_strategy_version,budget.budget_id,budget.version,created_at,("EXPERIMENT_DRAFT_ONLY",),manifest_fingerprint(seed=seed,link="v1"))
        self.repository.save_strategy_candidate(candidate); self.repository.save_strategy_experiment(experiment); self.repository.save_strategy_candidate_delta(delta); ControlledCandidateExperimentService(self.repository).validate_experiment(experiment,budget,(delta,)); self.repository.save_hypothesis_experiment_link(link)
        return experiment,delta,candidate,link

    def _validate_with_candidate(self,candidate,experiment,budget,delta):
        """All checks available before persistence; full validation follows candidate persistence."""
        if budget.maximum_candidate_count<1 or budget.maximum_changed_parameters<1: raise ValueError("Frozen experiment budget does not permit a candidate delta.")
        if any(token in delta.changed_field.upper() for token in {"PIT","LOOKAHEAD","SIX_GATE","AUDIT","IMMUTABLE","REAL_ACCOUNT"}): raise ValueError("Experiment bridge cannot alter hard invariants.")
        return True
