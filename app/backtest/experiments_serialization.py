from __future__ import annotations
from datetime import datetime
from decimal import Decimal
from .experiments import *
from app.backtest.serialization import dump
from app.historical.models import PartitionType
def _dec(value):return Decimal(value) if value is not None else None
def budget_from(value):
 value=dict(value);value["permitted_ranges"]={key:tuple(Decimal(item) for item in pair) for key,pair in value["permitted_ranges"].items()};return ExperimentBudget(**value)
def delta_from(value):return StrategyCandidateDelta(**dict(value))
def experiment_from(value):
 value=dict(value);value["experimental_candidate_ids"]=tuple(value["experimental_candidate_ids"]);value["permitted_partition_ids"]=tuple(value["permitted_partition_ids"]);value["forbidden_test_partition_ids"]=tuple(value["forbidden_test_partition_ids"]);value["created_at"]=datetime.fromisoformat(value["created_at"]);value["status"]=ExperimentStatus(value["status"]);value["warnings"]=tuple(value["warnings"]);return StrategyExperiment(**value)
def evidence_from(value):
 value=dict(value)
 for key in ("evaluated_at",):value[key]=datetime.fromisoformat(value[key])
 for key in ("return_value","drawdown","sharpe","sortino","expectancy","profit_factor","costs"):value[key]=_dec(value[key])
 value["partition_type"]=PartitionType(value["partition_type"]);value["warnings"]=tuple(value["warnings"]);return CandidateEvaluationEvidence(**value)
def robustness_from(value):
 value=dict(value);value["neighboring_candidate_ids"]=tuple(value["neighboring_candidate_ids"]);value["evidence_ids"]=tuple(value["evidence_ids"]);value["metric_dispersion"]=_dec(value["metric_dispersion"]);value["warnings"]=tuple(value["warnings"]);value["status"]=RobustnessStatus(value["status"]);return CandidateRobustnessResult(**value)
def policy_from(value):
 value=dict(value)
 for key in ("minimum_expectancy_improvement","minimum_sharpe_improvement","maximum_drawdown_worsening","maximum_cost_worsening","complexity_penalty_per_changed_parameter","knife_edge_dispersion"):value[key]=_dec(value[key])
 return CandidateSelectionPolicy(**value)
def selection_from(value):
 value=dict(value);value["candidate_ids"]=tuple(value["candidate_ids"]);value["evidence_ids"]=tuple(value["evidence_ids"]);value["robustness_result_ids"]=tuple(value["robustness_result_ids"]);value["reasons"]=tuple(value["reasons"]);value["warnings"]=tuple(value["warnings"]);value["selection_timestamp"]=datetime.fromisoformat(value["selection_timestamp"]);value["status"]=CandidateSelectionStatus(value["status"]);return CandidateSelectionResult(**value)
