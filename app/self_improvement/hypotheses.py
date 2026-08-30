"""Research-only hypothesis generation from frozen recurring patterns."""
from collections import defaultdict
from decimal import Decimal

from app.historical.guard import manifest_fingerprint
from .models import *


class SelfImprovementHypothesisService:
    _PROHIBITED = ("lookahead", "point_in_time", "pit", "audit", "six_gate", "immutable", "human_promotion", "human_activation", "benchmark_fairness", "real_account", "broker")
    _MAPPING = {
        ErrorCategory.FALSE_BREAKOUT.value: (HypothesisType.THRESHOLD_ADJUSTMENT, ConfigurableTargetDomain.SIGNAL, "volume_confirmation_threshold", "STRICTER", "Filter marginal breakouts lacking frozen confirmation.", "May reduce false-breakout associations.", "May reduce trade count, enter later, and miss early breakouts.", "LOW"),
        ErrorCategory.VOLUME_CONFIRMATION_FAILURE.value: (HypothesisType.THRESHOLD_ADJUSTMENT, ConfigurableTargetDomain.SIGNAL, "volume_confirmation_threshold", "STRICTER", "Require stronger observable participation before breakout entry.", "May reduce weak-volume failures.", "May reduce trade count and miss valid low-volume breakouts.", "LOW"),
        ErrorCategory.STOP_TOO_TIGHT.value: (HypothesisType.EXIT_PARAMETER_CHANGE, ConfigurableTargetDomain.EXIT, "structural_stop_width", "MODESTLY_WIDER", "Test whether a modestly wider structural stop avoids observed whipsaws.", "May reduce stop-out associations.", "Larger loss per stop, lower fixed-risk size, and worse capital efficiency.", "MODERATE"),
        ErrorCategory.CAPITAL_ROTATION_TOO_EARLY.value: (HypothesisType.ROTATION_PARAMETER_CHANGE, ConfigurableTargetDomain.ROTATION, "rotation_advantage_hurdle", "INCREASE", "Require stronger frozen rotation advantage before replacement.", "May reduce premature rotations.", "May retain weak holdings longer and incur opportunity cost.", "LOW"),
        ErrorCategory.EXCESSIVE_FRICTION.value: (HypothesisType.SIGNAL_PARAMETER_CHANGE, ConfigurableTargetDomain.SIGNAL, "minimum_expected_edge_after_friction", "INCREASE", "Require observed edge to clear frozen transaction costs.", "May reduce cost-erased trades.", "May reduce opportunities and delay entries.", "LOW"),
        ErrorCategory.HIGH_SCORE_FAILURE.value: (HypothesisType.THRESHOLD_ADJUSTMENT, ConfigurableTargetDomain.DECISION_SCORE, "minimum_score_threshold", "REVIEW_STRICTER", "Test whether existing high-score selectivity is sufficiently discriminative.", "May improve score discrimination.", "May reject profitable high-score setups.", "LOW"),
        SuccessCategory.MULTI_FACTOR_ALIGNMENT.value: (HypothesisType.THRESHOLD_ADJUSTMENT, ConfigurableTargetDomain.SIGNAL, "minimum_multi_factor_alignment", "REVIEW_STRICTER", "Test whether preserving observed alignment improves selectivity.", "May preserve multi-factor success associations.", "May reduce trade count and overfit prior successes.", "MODERATE"),
        SuccessCategory.HIGH_RS_BREAKOUT_SUCCESS.value: (HypothesisType.THRESHOLD_ADJUSTMENT, ConfigurableTargetDomain.DECISION_SCORE, "relative_strength_threshold", "REVIEW_STRICTER", "Test whether existing strong-RS selection is worth preserving.", "May preserve high-RS success associations.", "May enter later and miss emerging leaders.", "LOW"),
    }

    def __init__(self, repository): self.repository = repository

    def validate_target(self, domain: ConfigurableTargetDomain, field: str | None):
        token = f"{domain.value}:{field or ''}".lower()
        if any(item in token for item in self._PROHIBITED): raise ValueError("Hypothesis target would alter a protected governance or safety invariant.")
        if domain is ConfigurableTargetDomain.NONE and field is not None: raise ValueError("No-change hypotheses cannot target a field.")

    def is_stale(self, hypothesis: StrategyImprovementHypothesis, active_approved_id: str | None) -> bool:
        return active_approved_id is not None and hypothesis.target_approved_strategy_id != active_approved_id

    def generate(self, *, run_id: str, evidence_policy_id: str, generation_policy_id: str, budget_id: str, target_approved_strategy_id: str, created_at, persist: bool = True):
        run=self.repository.get_self_improvement_run(run_id); evidence=self.repository.get_self_improvement_evidence_policy(evidence_policy_id); policy=self.repository.get_hypothesis_generation_policy(generation_policy_id); budget=self.repository.get_hypothesis_proposal_budget(budget_id); target=self.repository.get_approved_strategy_version(target_approved_strategy_id)
        if None in (run,evidence,policy,budget,target): raise ValueError("Hypothesis generation requires persisted frozen run, evidence policy, generation policy, budget, and approved target.")
        if not run.strategy_version.endswith(target.version): raise ValueError("Hypothesis target version does not match the frozen self-improvement run.")
        patterns=self.repository.list_recurring_strategy_patterns(run_id); error_summaries=self.repository.list_strategy_error_summaries(run_id)
        candidates=[]
        for pattern in patterns:
            proposal=self._from_pattern(run,target,policy,pattern,patterns,created_at)
            if proposal is not None: candidates.append(proposal)
        for summary in error_summaries:
            if summary.category==ErrorCategory.DATA_QUALITY_FAILURE.value and summary.count>=evidence.minimum_observations:
                candidates.append(self._data_quality(run,target,policy,summary,created_at))
        merged=self._deduplicate(candidates)
        actionable=[item for item in merged if item.hypothesis_type not in {HypothesisType.REQUEST_MORE_EVIDENCE,HypothesisType.NO_CHANGE_RECOMMENDED}]
        maximum=min(budget.maximum_experiment_proposals,policy.maximum_actionable_hypotheses)
        ranked=sorted(actionable,key=self._priority,reverse=True); accepted=[]; excluded=[]; domains=defaultdict(int)
        for item in ranked:
            if len(accepted)>=maximum: excluded.append((item.hypothesis_id,"PROPOSAL_BUDGET_EXCEEDED")); continue
            if domains[item.target_domain]>=policy.maximum_per_target_domain: excluded.append((item.hypothesis_id,"TARGET_DOMAIN_BUDGET_EXCEEDED")); continue
            accepted.append(item); domains[item.target_domain]+=1
        retained=accepted+[item for item in merged if item.hypothesis_type is HypothesisType.REQUEST_MORE_EVIDENCE]
        if not retained:
            retained=[self._no_change(run,target,policy,created_at,"NO_POLICY_QUALIFIED_RECURRING_PATTERN")]
        ranking=self._ranking(run,policy,retained,excluded)
        result=(tuple(retained),ranking)
        if persist: self._persist(result)
        return result

    def _from_pattern(self, run, target, policy, pattern, all_patterns, created_at):
        mapping=self._MAPPING.get(pattern.category)
        if mapping is None: return None
        status=pattern.evidence_status
        if status is PatternEvidenceStatus.ANECDOTAL: return self._request(run,target,policy,pattern,created_at,"ANECDOTAL_PATTERN")
        if status in {PatternEvidenceStatus.MIXED,PatternEvidenceStatus.INCONCLUSIVE,PatternEvidenceStatus.INSUFFICIENT_EVIDENCE}: return self._request(run,target,policy,pattern,created_at,"MIXED_OR_INSUFFICIENT_EVIDENCE")
        if pattern.weighted_evidence_count<policy.minimum_evidence_score: return self._request(run,target,policy,pattern,created_at,"WEIGHTED_EVIDENCE_BELOW_POLICY")
        hypothesis_type,domain,field,direction,mechanism,benefit,downside,complexity=mapping; self.validate_target(domain,field)
        relevant_success=[value for value in all_patterns if value.attribution_kind is AttributionKind.SUCCESS and self._MAPPING.get(value.category,(None,domain,None))[1] is domain]
        counter=tuple(identifier for value in relevant_success for identifier in value.supporting_attribution_ids)
        warning=list(pattern.warnings)
        if counter: warning.append("SUCCESS_COUNTEREVIDENCE_RETAINED")
        confidence="STRONG_EVIDENCE_FOR_EXPERIMENT" if not counter else "MODERATE"
        return self._hypothesis(run,target,policy,pattern,hypothesis_type,domain,field,direction,mechanism,benefit,downside,complexity,status,confidence,counter,created_at,tuple(warning))

    def _request(self, run,target,policy,pattern,created_at,reason):
        return self._hypothesis(run,target,policy,pattern,HypothesisType.REQUEST_MORE_EVIDENCE,ConfigurableTargetDomain.NONE,None,"GATHER_MORE_EVIDENCE","Observed pattern does not meet the frozen policy for an actionable change.","Retains the association for later governed research.","No strategy change is proposed; more evidence may still be inconclusive.","LOW",pattern.evidence_status,"LOW",(),created_at,(reason,*pattern.warnings))

    def _data_quality(self, run,target,policy,summary,created_at):
        fingerprint=manifest_fingerprint(run=run.fingerprint,target=target.fingerprint,policy=policy.fingerprint,summary=summary.fingerprint,type="DATA_QUALITY")
        return StrategyImprovementHypothesis("hypothesis-"+fingerprint[:24],run.run_id,target.approved_id,target.version,"Improve source data quality","Repeated frozen data-quality failures require infrastructure research.",(),(),(),summary.category,HypothesisType.DATA_QUALITY_CHANGE,ConfigurableTargetDomain.DATA_QUALITY_INFRASTRUCTURE,"source_quality_policy","STRENGTHEN","Improve stale/missing/PIT source controls before drawing strategy conclusions.","May improve evidence reliability.","May reduce available coverage and delay research.",(),(),PatternEvidenceStatus.ELIGIBLE,"MODERATE","LOW",created_at,("DATA_QUALITY_ROUTING_ONLY",),manifest_fingerprint(summary=summary.fingerprint),policy.policy_id,policy.version,fingerprint)

    def _no_change(self, run,target,policy,created_at,reason):
        fingerprint=manifest_fingerprint(run=run.fingerprint,target=target.fingerprint,policy=policy.fingerprint,type="NO_CHANGE",reason=reason)
        return StrategyImprovementHypothesis("hypothesis-"+fingerprint[:24],run.run_id,target.approved_id,target.version,"No change recommended","No recurring frozen pattern meets the policy for a research change.",(),(),(),"NO_QUALIFIED_PATTERN",HypothesisType.NO_CHANGE_RECOMMENDED,ConfigurableTargetDomain.NONE,None,"NO_CHANGE","Avoid unsupported configuration changes.","Preserves current governed baseline.","Potential improvements may remain undiscovered until more evidence exists.",(),(),PatternEvidenceStatus.INSUFFICIENT_EVIDENCE,"LOW","LOW",created_at,(reason,),manifest_fingerprint(run=run.fingerprint,reason=reason),policy.policy_id,policy.version,fingerprint)

    def _hypothesis(self, run,target,policy,pattern,hypothesis_type,domain,field,direction,mechanism,benefit,downside,complexity,status,confidence,counter,created_at,warnings):
        self.validate_target(domain,field)
        fingerprint=manifest_fingerprint(run=run.fingerprint,target=target.fingerprint,policy=policy.fingerprint,pattern=pattern.fingerprint,type=hypothesis_type.value,domain=domain.value,field=field,direction=direction,counter=counter)
        return StrategyImprovementHypothesis("hypothesis-"+fingerprint[:24],run.run_id,target.approved_id,target.version,f"{pattern.category.replace('_',' ').title()} research proposal",f"Research-only proposal derived from {pattern.category} recurring association.",(pattern.pattern_id,),pattern.supporting_attribution_ids,counter,pattern.category,hypothesis_type,domain,field,direction,mechanism,benefit,downside,pattern.regimes,pattern.sectors,status,confidence,complexity,created_at,warnings,manifest_fingerprint(pattern=pattern.fingerprint,support=pattern.supporting_attribution_ids,counter=counter),policy.policy_id,policy.version,fingerprint)

    def _deduplicate(self, hypotheses):
        groups=defaultdict(list)
        for value in hypotheses: groups[(value.hypothesis_type,value.target_domain,value.target_field,value.proposed_direction,value.applicable_regimes,value.applicable_sectors)].append(value)
        merged=[]
        for values in groups.values():
            first=values[0]
            if len(values)==1: merged.append(first); continue
            patterns=tuple(sorted({identifier for value in values for identifier in value.originating_pattern_ids})); support=tuple(sorted({identifier for value in values for identifier in value.supporting_attribution_ids})); counter=tuple(sorted({identifier for value in values for identifier in value.counterevidence_ids})); categories="+".join(sorted({value.problem_category for value in values})); fingerprint=manifest_fingerprint(base=first.fingerprint,patterns=patterns,support=support,counter=counter,categories=categories)
            merged.append(StrategyImprovementHypothesis("hypothesis-"+fingerprint[:24],first.run_id,first.target_approved_strategy_id,first.target_strategy_version,first.title,first.description,patterns,support,counter,categories,first.hypothesis_type,first.target_domain,first.target_field,first.proposed_direction,first.expected_mechanism,first.expected_benefit,first.potential_downside,first.applicable_regimes,first.applicable_sectors,first.evidence_status,first.confidence,first.complexity_estimate,first.created_at,tuple(sorted({warning for value in values for warning in value.warnings})),manifest_fingerprint(patterns=patterns,support=support,counter=counter),first.generation_policy_id,first.generation_policy_version,fingerprint))
        return merged

    def _priority(self, value):
        complexity=Decimal("2") if value.complexity_estimate=="MODERATE" else Decimal("1")
        return Decimal(len(value.supporting_attribution_ids))+Decimal("2")-Decimal(len(value.counterevidence_ids))-complexity

    def _ranking(self, run,policy,hypotheses,excluded):
        ordered=tuple(value.hypothesis_id for value in sorted(hypotheses,key=self._priority,reverse=True)); factors=tuple((value.hypothesis_id,(("SUPPORT",Decimal(len(value.supporting_attribution_ids))),("COUNTEREVIDENCE_PENALTY",Decimal(-len(value.counterevidence_ids))),("COMPLEXITY_PENALTY",Decimal(-2 if value.complexity_estimate=="MODERATE" else -1)),("PRIORITY",self._priority(value)))) for value in sorted(hypotheses,key=self._priority,reverse=True)); fingerprint=manifest_fingerprint(run=run.fingerprint,policy=policy.fingerprint,ordered=ordered,factors=factors,excluded=excluded)
        return StrategyHypothesisRanking("hypothesis-ranking-"+fingerprint[:24],run.run_id,ordered,factors,tuple(excluded),policy.methodology_version,(),fingerprint)

    def _persist(self,result):
        hypotheses,ranking=result
        for value in hypotheses:
            existing=self.repository.get_strategy_improvement_hypothesis(value.hypothesis_id)
            if existing is None:self.repository.save_strategy_improvement_hypothesis(value)
            elif existing!=value:raise ValueError("Frozen generated hypothesis does not match deterministic reconstruction.")
        existing=self.repository.get_strategy_hypothesis_ranking(ranking.ranking_id)
        if existing is None:self.repository.save_strategy_hypothesis_ranking(ranking)
        elif existing!=ranking:raise ValueError("Frozen hypothesis ranking does not match deterministic reconstruction.")
