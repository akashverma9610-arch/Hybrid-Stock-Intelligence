"""Frozen-input deterministic association and recurring-pattern analysis.

This module intentionally emits associations, never causal claims, hypotheses,
experiments, strategy configuration changes, approvals, or activations.
"""
from collections import defaultdict
from decimal import Decimal

from app.historical.guard import manifest_fingerprint
from .models import *


class SelfImprovementAttributionService:
    def __init__(self, repository): self.repository = repository

    def analyze(self, run_id: str, policy_id: str, rule_set_id: str, *, persist: bool = True):
        run = self.repository.get_self_improvement_run(run_id)
        policy = self.repository.get_self_improvement_evidence_policy(policy_id)
        rules = self.repository.get_attribution_rule_set(rule_set_id)
        if run is None or policy is None or rules is None: raise ValueError("Attribution requires persisted frozen run, evidence policy, and rule set.")
        errors, successes = [], []
        for observation in self.repository.list_self_improvement_observations(run_id):
            eligibility = self._eligibility(run, policy, observation)
            if eligibility is not None:
                if eligibility.startswith("SKIP_"):
                    continue
                errors.append(self._error(run, observation, rules, ErrorCategory.DATA_QUALITY_FAILURE, AttributionStrength.INSUFFICIENT_EVIDENCE, (eligibility,)))
                continue
            errors.extend(self._errors_for(run, observation, rules))
            successes.extend(self._successes_for(run, observation, rules))
        patterns = self._patterns(run, policy, rules, tuple(errors), tuple(successes))
        error_summaries = self._summaries(run, policy, rules, tuple(errors), AttributionKind.ERROR)
        success_summaries = self._summaries(run, policy, rules, tuple(successes), AttributionKind.SUCCESS)
        result = (tuple(errors), tuple(successes), tuple(patterns), tuple(error_summaries), tuple(success_summaries))
        if persist: self._persist(result)
        return result

    def _eligibility(self, run, policy, observation):
        if observation.strategy_version != run.strategy_version: return "SKIP_STRATEGY_VERSION_MISMATCH"
        if not run.analysis_start <= observation.occurred_at <= run.analysis_end: return "SKIP_OUTSIDE_FROZEN_ANALYSIS_WINDOW"
        if observation.source.value not in policy.permitted_sources: return "SKIP_SOURCE_TYPE_NOT_PERMITTED"
        fields = observation.fields
        if not observation.provenance_ids or fields.get("auditable") is not True: return "SOURCE_NOT_AUDITABLE"
        if fields.get("pit_eligible") is not True: return "POINT_IN_TIME_INSUFFICIENT"
        if fields.get("audit_valid") is not True: return "SOURCE_AUDIT_INVALID"
        if fields.get("data_quality") in {"STALE", "MISSING", "INCOMPLETE", "INSUFFICIENT"}: return "SOURCE_DATA_QUALITY_INSUFFICIENT"
        return None

    @staticmethod
    def _decimal(value, default="0"):
        return Decimal(str(default if value is None else value))

    def _failed(self, fields): return fields.get("outcome") in {"LOSS", "FAILED", "STOPPED"} or fields.get("failed") is True or fields.get("stop_hit") is True
    def _won(self, fields): return fields.get("outcome") in {"WIN", "SUCCESS"} or fields.get("successful") is True

    def _errors_for(self, run, observation, rules):
        fields = observation.fields; categories = []
        failed = self._failed(fields); breakout = fields.get("setup_type") in {"BREAKOUT", "CONFIRMATION_BREAKOUT"}
        triggered_filled = fields.get("triggered") is True and fields.get("filled") is True
        if breakout and fields.get("triggered") is True and fields.get("structure_failed") is True and (fields.get("stop_hit") is True or self._decimal(fields.get("mae_r")) >= rules.minimum_adverse_r) and fields.get("continuation_failed") is True: categories.append(ErrorCategory.FALSE_BREAKOUT)
        if failed and triggered_filled and self._decimal(fields.get("decision_score")) >= rules.high_score_threshold and fields.get("gates_passed") is True: categories.append(ErrorCategory.HIGH_SCORE_FAILURE)
        if failed and fields.get("relative_strength") in {"WEAK", "DECLINING"}: categories.append(ErrorCategory.WEAK_RELATIVE_STRENGTH)
        if failed and fields.get("sector_phase") in {"WEAK", "ROTATING_OUT"}: categories.append(ErrorCategory.SECTOR_MISALIGNMENT)
        if failed and fields.get("regime_match") is False: categories.append(ErrorCategory.REGIME_MISMATCH)
        if failed and self._decimal(fields.get("rr"), "999") <= rules.low_rr_threshold: categories.append(ErrorCategory.LOW_REWARD_TO_RISK)
        if breakout and failed and fields.get("volume_confirmed") is False and any(key in fields for key in ("rvol", "obv_trend", "vwap_acceptance")): categories.append(ErrorCategory.VOLUME_CONFIRMATION_FAILURE)
        if fields.get("stop_hit") is True and fields.get("counterfactual_target_reached") is True and self._decimal(fields.get("wider_stop_required"), "999") <= self._decimal(fields.get("modest_wider_stop_limit"), "999"): categories.append(ErrorCategory.STOP_TOO_TIGHT)
        if failed and self._decimal(fields.get("stop_loss_r")) > rules.minimum_adverse_r and self._decimal(fields.get("mfe_r")) < rules.minimum_favorable_r: categories.append(ErrorCategory.STOP_TOO_LOOSE)
        if failed and fields.get("entry_before_confirmation") is True and fields.get("later_confirmation") is True and self._decimal(fields.get("early_mae_r")) >= rules.minimum_adverse_r: categories.append(ErrorCategory.ENTRY_TOO_EARLY)
        if failed and fields.get("intended_entry_price") is not None and fields.get("actual_fill_price") is not None and abs(self._decimal(fields["actual_fill_price"])-self._decimal(fields["intended_entry_price"])) / self._decimal(fields["intended_entry_price"], "1") >= rules.max_entry_delay_pct: categories.append(ErrorCategory.ENTRY_TOO_LATE)
        gross = self._decimal(fields.get("gross_pnl")); costs = self._decimal(fields.get("transaction_cost"))
        if gross > 0 and costs / gross >= rules.max_cost_to_gross_ratio and self._decimal(fields.get("net_pnl")) <= 0: categories.append(ErrorCategory.EXCESSIVE_FRICTION)
        if self._decimal(fields.get("hold_sessions")) >= rules.low_velocity_sessions and self._decimal(fields.get("mfe_r")) < rules.minimum_favorable_r: categories.append(ErrorCategory.LOW_CAPITAL_VELOCITY)
        if fields.get("rotation_underperformed_incumbent") is True and fields.get("rotation_timing") == "EARLY": categories.append(ErrorCategory.CAPITAL_ROTATION_TOO_EARLY)
        if fields.get("rotation_underperformed_incumbent") is True and fields.get("rotation_timing") == "LATE": categories.append(ErrorCategory.CAPITAL_ROTATION_TOO_LATE)
        return tuple(self._error(run, observation, rules, category, AttributionStrength.LIKELY_CONTRIBUTOR if category is ErrorCategory.STOP_TOO_TIGHT else AttributionStrength.ASSOCIATED_WITH, ()) for category in dict.fromkeys(categories))

    def _successes_for(self, run, observation, rules):
        fields = observation.fields
        strict_false_negative = fields.get("counterfactual_executable") is True and fields.get("counterfactual_outcome") == "WIN" and fields.get("rejected_or_expired") is True
        if not self._won(fields) and not strict_false_negative: return ()
        categories = []
        if strict_false_negative: categories.append(SuccessCategory.STRICT_EXECUTABLE_FALSE_NEGATIVE)
        if strict_false_negative and fields.get("capital_insufficient") is True: categories.append(SuccessCategory.CAPITAL_CONSTRAINT_MISS)
        if fields.get("setup_type") in {"BREAKOUT", "CONFIRMATION_BREAKOUT"} and fields.get("relative_strength") == "STRONG": categories.append(SuccessCategory.HIGH_RS_BREAKOUT_SUCCESS)
        if fields.get("earnings_acceleration") is True: categories.append(SuccessCategory.EARNINGS_ACCELERATION_SUCCESS)
        if fields.get("sector_phase") in {"LEADING", "IMPROVING"}: categories.append(SuccessCategory.SECTOR_ROTATION_ALIGNMENT)
        if fields.get("volume_confirmed") is True: categories.append(SuccessCategory.VOLUME_CONFIRMATION_SUCCESS)
        if fields.get("catalyst_follow_through") is True: categories.append(SuccessCategory.CATALYST_FOLLOW_THROUGH)
        if self._decimal(fields.get("rr")) > rules.low_rr_threshold: categories.append(SuccessCategory.STRONG_RR_SUCCESS)
        if self._decimal(fields.get("hold_sessions")) < rules.low_velocity_sessions and self._decimal(fields.get("mfe_r")) >= rules.minimum_favorable_r: categories.append(SuccessCategory.FAST_CAPITAL_VELOCITY)
        if fields.get("multi_factor_aligned") is True: categories.append(SuccessCategory.MULTI_FACTOR_ALIGNMENT)
        if fields.get("regime_match") is True: categories.append(SuccessCategory.REGIME_MATCH_SUCCESS)
        return tuple(self._success(run, observation, rules, category) for category in dict.fromkeys(categories))

    def _error(self, run, observation, rules, category, strength, extra_warnings):
        fields = observation.fields; counterfactual = "MODEST_WIDER_STOP_COUNTERFACTUAL_ONLY" if category is ErrorCategory.STOP_TOO_TIGHT else None
        return StrategyErrorAttribution("error-" + manifest_fingerprint(run=run.fingerprint,observation=observation.fingerprint,rules=rules.fingerprint,category=category.value)[:24],run.run_id,observation.observation_id,run.strategy_version,category,strength,str(fields.get("severity","MEDIUM")),(observation.observation_id,*observation.provenance_ids),tuple(fields.get("diagnostic_ids",())),counterfactual,tuple(extra_warnings)+("ASSOCIATION_NOT_CAUSATION",),manifest_fingerprint(run=run.fingerprint,observation=observation.fingerprint,rules=rules.fingerprint,category=category.value,strength=strength.value),observation.source,rules.rule_set_id)

    def _success(self, run, observation, rules, category):
        fields = observation.fields
        return StrategySuccessAttribution("success-" + manifest_fingerprint(run=run.fingerprint,observation=observation.fingerprint,rules=rules.fingerprint,category=category.value)[:24],run.run_id,observation.observation_id,run.strategy_version,category,AttributionStrength.ASSOCIATED_WITH,str(fields.get("severity","LOW")),(observation.observation_id,*observation.provenance_ids),("ASSOCIATION_NOT_CAUSATION",),manifest_fingerprint(run=run.fingerprint,observation=observation.fingerprint,rules=rules.fingerprint,category=category.value),observation.source,rules.rule_set_id)

    def _patterns(self, run, policy, rules, errors, successes):
        records=[]; observations={value.observation_id:value for value in self.repository.list_self_improvement_observations(run.run_id)}
        groups=defaultdict(list)
        for value in errors:
            if value.category is not ErrorCategory.DATA_QUALITY_FAILURE: groups[(AttributionKind.ERROR,value.category.value)].append(value)
        for value in successes: groups[(AttributionKind.SUCCESS,value.category.value)].append(value)
        for (kind, category), attributions in sorted(groups.items(),key=lambda item:(item[0][0].value,item[0][1])):
            source_observations=[observations[value.source_observation_id] for value in attributions]
            weights=dict(policy.source_weights); source_split=tuple(sorted((source.value,sum(1 for value in attributions if value.source is source)) for source in ObservationSource if any(value.source is source for value in attributions)))
            regimes=tuple(sorted({str(value.fields.get("regime","UNKNOWN")) for value in source_observations})); sectors=tuple(sorted({str(value.fields.get("sector","UNKNOWN")) for value in source_observations}))
            threshold=policy.recurrence_threshold or policy.minimum_observations; warnings=[]; count=len(attributions); oos=sum(value.source is ObservationSource.WALK_FORWARD_OOS for value in attributions)
            if count < threshold: status=PatternEvidenceStatus.ANECDOTAL
            elif oos < policy.minimum_oos_observations: status=PatternEvidenceStatus.INSUFFICIENT_EVIDENCE; warnings.append("OOS_SAMPLE_INSUFFICIENT")
            elif len(regimes)<policy.minimum_regime_breadth or len(sectors)<policy.minimum_sector_breadth: status=PatternEvidenceStatus.INCONCLUSIVE; warnings.append("BREADTH_REQUIREMENT_NOT_MET")
            elif any(value.fields.get("counterevidence") is True for value in source_observations): status=PatternEvidenceStatus.MIXED; warnings.append("COUNTEREVIDENCE_RETAINED")
            else: status=PatternEvidenceStatus.ELIGIBLE
            if count>1 and len(regimes)==1: warnings.append("REGIME_CONCENTRATED")
            if count>1 and len(sectors)==1: warnings.append("SECTOR_CONCENTRATED")
            r_values=[self._decimal(value.fields.get("r_impact")) for value in source_observations if value.fields.get("r_impact") is not None]; cost_values=[self._decimal(value.fields.get("transaction_cost")) for value in source_observations if value.fields.get("transaction_cost") is not None]
            fingerprint=manifest_fingerprint(run=run.fingerprint,policy=policy.fingerprint,rules=rules.fingerprint,kind=kind.value,category=category,support=[value.attribution_id for value in attributions])
            records.append(RecurringStrategyPattern("pattern-"+fingerprint[:24],run.run_id,category,kind,tuple(value.attribution_id for value in attributions),count,sum((weights.get(value.source.value,Decimal("0")) for value in attributions),Decimal("0")),oos,sum(value.source is ObservationSource.HISTORICAL_BACKTEST for value in attributions),sum(value.source is ObservationSource.PAPER_FORWARD_TEST for value in attributions),source_split,regimes,sectors,tuple(sorted({str(value.fields.get("score_band","UNKNOWN")) for value in source_observations})),tuple(sorted({str(value.fields.get("confidence_band","UNKNOWN")) for value in source_observations})),sum(r_values,Decimal("0")) if r_values else None,sum(cost_values,Decimal("0")) if cost_values else None,status,tuple(warnings),policy.policy_id,policy.version,rules.rule_set_id,rules.version,fingerprint))
        return tuple(records)

    def _summaries(self, run, policy, rules, attributions, kind):
        observations={value.observation_id:value for value in self.repository.list_self_improvement_observations(run.run_id)}; groups=defaultdict(list); weights=dict(policy.source_weights)
        for value in attributions: groups[value.category.value].append(value)
        model=StrategyErrorSummary if kind is AttributionKind.ERROR else StrategySuccessSummary; result=[]
        for category, values in sorted(groups.items()):
            source_observations=[observations[value.source_observation_id] for value in values]; split=lambda key:tuple(sorted((item,sum(1 for observation in source_observations if str(observation.fields.get(key,"UNKNOWN"))==item)) for item in {str(observation.fields.get(key,"UNKNOWN")) for observation in source_observations}))
            fingerprint=manifest_fingerprint(run=run.fingerprint,rules=rules.fingerprint,kind=kind.value,category=category,support=[value.attribution_id for value in values])
            r_values=[self._decimal(observation.fields.get("r_impact")) for observation in source_observations if observation.fields.get("r_impact") is not None]; costs=[self._decimal(observation.fields.get("transaction_cost")) for observation in source_observations if observation.fields.get("transaction_cost") is not None]
            def groups(name, labels):
                counts=defaultdict(int)
                for observation in source_observations:
                    for label in labels(observation): counts[str(label)]+=1
                return (name,tuple(sorted(counts.items())))
            analysis_groups=(
                groups("GATE_OUTCOME",lambda observation:(observation.fields.get("gate_outcome","PASS" if observation.fields.get("gates_passed") is True else "UNKNOWN"),)),
                groups("SETUP_TYPE",lambda observation:(observation.fields.get("setup_type","UNKNOWN"),)),
                groups("CATALYST",lambda observation:(observation.fields.get("catalyst","UNKNOWN"),)),
                groups("THRESHOLD_NEIGHBORHOOD",lambda observation:(observation.fields.get("threshold_neighborhood","UNKNOWN"),)),
                groups("KEY_DIAGNOSTIC",lambda observation:tuple(observation.fields.get("diagnostic_ids",("UNKNOWN",)))),
                groups("SCORE_COMPONENT",lambda observation:tuple(f"{key}:{value}" for key,value in observation.fields.get("score_components",{}).items()) or ("UNKNOWN",)),
            )
            result.append(model("summary-"+fingerprint[:24],run.run_id,category,len(values),sum((weights.get(value.source.value,Decimal("0")) for value in values),Decimal("0")),tuple(sorted((source.value,sum(value.source is source for value in values)) for source in ObservationSource if any(value.source is source for value in values))),split("regime"),split("sector"),sum(r_values,Decimal("0")) if r_values else None,sum(costs,Decimal("0")) if costs else None,(),rules.rule_set_id,fingerprint,analysis_groups))
        return tuple(result)

    def _persist(self, result):
        errors, successes, patterns, error_summaries, success_summaries=result
        for values, getter, saver, identifier in ((errors,self.repository.get_strategy_error_attribution,self.repository.save_strategy_error_attribution,"attribution_id"),(successes,self.repository.get_strategy_success_attribution,self.repository.save_strategy_success_attribution,"attribution_id"),(patterns,self.repository.get_recurring_strategy_pattern,self.repository.save_recurring_strategy_pattern,"pattern_id"),(error_summaries,self.repository.get_strategy_error_summary,self.repository.save_strategy_error_summary,"summary_id"),(success_summaries,self.repository.get_strategy_success_summary,self.repository.save_strategy_success_summary,"summary_id")):
            for value in values:
                existing=getter(getattr(value,identifier))
                if existing is None: saver(value)
                elif existing != value: raise ValueError("Frozen self-improvement artifact does not match deterministic reconstruction.")
