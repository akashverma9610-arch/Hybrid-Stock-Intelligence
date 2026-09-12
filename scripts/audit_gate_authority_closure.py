"""Final bounded B08 audit; frozen production observations are NOT live data.

Only deterministic isolated gate replay executes. No DB/provider/policy writes,
no acquisition, and no new producer is inferred from a data structure.
"""
from dataclasses import asdict
import json

from app.fundamentals.diagnostic_comparability import content_fingerprint
from app.gates.source_readiness import SOURCE_GAPS, SourceReadiness, VERSION, source_gap
from scripts.audit_gate_source_authority import matrix as before_matrix, receipt as before_receipt


BASELINE = "c76affb4dad6521a031ebdd4f294d396aee04216"
NEXT = "EARNINGS_CALENDAR_SOURCE_GOVERNANCE_V1"

# Repository discovery findings, not executable adapters or policy definitions.
DISCOVERY = (
    ("GATE_1_ROTATION", ("app/gates/production_policy.py", "app/backtest/portfolio_gates.py", "app/rotation/models.py"),
     "Effective-dated immutable approved policy and statutory friction formula exist; user costs and advantage remain caller scenario inputs.",
     "No approved scenario identity/known-at/eligibility binds expected return, turnover, brokerage, slippage, tax or taxable services.",
     "Rotation economic clearance unavailable; not a bearish stock assessment."),
    ("GATE_2_VELOCITY", ("app/analysis/technical.py", "app/analysis/models.py", "app/strategies/pre_breakout/materialization.py", "app/registry/canonical.py"),
     "technical-v1 Wilder ATR and governed daily ATR14 contraction evidence exist, with source observation IDs and PIT status.",
     "No canonical holding-period ATR expansion definition/result: ATR price units, ATR contraction and >1 ATR expansion are not interchangeable. Timeframe, displacement anchor and normalization need governance.",
     "Velocity adjustment evidence unavailable; no invented ATR, penalty or stock weakness."),
    ("GATE_3_SURVEILLANCE", ("app/gates/production_policy.py", "app/backtest/analytical.py", "app/gates/engine.py"),
     "Approved official-nse-surveillance-v1 declaration and gate observation carrier exist.",
     "No source-backed ASM/GSM/price-band/security-status producer with exact identity, publication/receipt time, coverage and revision proof. Generic MarketObservation plus authoritative=True is not authority.",
     "Fresh-entry surveillance clearance unavailable."),
    ("GATE_4_TRADE_PLAN", ("app/signals/models.py", "app/storage/sqlite_governance_repository.py", "app/strategies/pre_breakout/setup_assessment.py", "app/gates/engine.py"),
     "Stored analytical TradePlan and governed Pre-Breakout assessment exist. Zero stored plans is not absence of these contracts.",
     "TradePlan lacks its own instrument/as-of/policy fingerprint and management tranche/reduction/breakeven terms. Setup assessment stops before candidate formation. Signal gate references cannot bootstrap their own prerequisite plan authority.",
     "Candidate cannot receive plan clearance or become ENTRY_READY."),
    ("GATE_5_HEAT", ("app/portfolio/models.py", "app/portfolio/engine.py", "app/backtest/portfolio_gates.py"),
     "Canonical PortfolioSnapshot has existing exposure, heat, cash and PIT identity; stored holding-date adapter remains admitted.",
     "No approved candidate-risk/allocation scenario binds candidate identity, capital, sector, policy and known-at. Frozen replay parameters are not user approval; production cash/equity/heat are unknown.",
     "Allocation/execution readiness blocked; no capital or candidate quantity inferred."),
    ("GATE_6_EARNINGS", ("app/filings/models.py", "app/filings/providers.py", "app/filings/store.py", "app/gates/earnings_schedule_evidence.py", "app/gates/production_policy.py"),
     "CorporateFiling retains board-meeting metadata, announcements, receipts and revisions; approved official-nse-earnings-calendar-v1 declaration exists.",
     "No admitted results-purpose future-schedule producer, exact session/date semantics, verification, cancellation/revision coverage or absence proof. Candidate calendar explicitly remains UNVERIFIED_SOURCE_AUTHORITY.",
     "Fresh-entry earnings-blackout clearance unavailable; existing risk-management exemption unchanged."),
)


def _seal(body):
    return body | {"fingerprint": content_fingerprint(body)}


def matrices():
    before = before_matrix()
    rows = []
    for row in before["fields"]:
        gap = source_gap(row["input_field"])
        admitted = row["input_field"] in {"raw_decision_score", "comparison_score", "holding_entry_date"}
        rows.append(dict(field=row["field"], input_field=row["input_field"], gates=row["gates"],
            before_readiness=row["final_readiness"],
            authority_readiness=gap.state if gap else SourceReadiness.READY_EXISTING_CANONICAL_PRODUCER if admitted else SourceReadiness.NOT_APPLICABLE,
            blocker=gap.blocker if gap else None, future_slice=gap.future_slice if gap else None))
    compatibility = [dict(gate_id=gate, version_compatibility="CLOSED_FOR_ACTIVATION_COMPATIBILITY",
        authority_enforcement="ENFORCED", caller_spoof_resistance="INDEPENDENT_AUTHORITY_OR_REJECTION",
        v2_rejection="VERSION_BLOCKED", v1_replay="FROZEN_21_SCENARIOS_UNCHANGED")
        for gate, *_ in DISCOVERY]
    production = []
    for gate, modules, existing, missing, impact in DISCOVERY:
        gaps = [asdict(item) for item in SOURCE_GAPS if item.gate_id == gate]
        production.append(dict(gate_id=gate, modules=modules, existing_producer=existing, missing_producer=missing,
            source_gaps=gaps, current_required_data_complete=False, freshness_proven=False,
            real_evidence_clearance_ready=False, senseedge_impact=impact))
    return _seal(dict(version=VERSION, baseline=BASELINE, before_matrix_fingerprint=before["fingerprint"],
        before_receipt_fingerprint=before_receipt()["fingerprint"], expanded_fields=rows,
        prior_eight_blocked_fields=before["neutral_fields_blocked_without_adapter"],
        admitted_inputs=["raw_decision_score", "comparison_score", "holding_entry_date"],
        new_adapters=0, gate_compatibility=compatibility, production_source_readiness=production,
        production_observation=dict(kind="FROZEN_READ_ONLY_AUDIT_NOT_LIVE_STATUS", audit_date="2026-09-12",
            db_size=18346504192, db_mtime_ns=1789150260641346800, approved_gate_policies=1,
            canonical_scorecards=3, score_as_of="2026-08-31T18:21:20.437011+00:00",
            corporate_filings=455, results_filings=425, ownership_filings=30, board_schedule_metadata_rows=0,
            trade_plans=0, portfolio_snapshots=1, cash="UNKNOWN", portfolio_equity=None, portfolio_heat=None,
            portfolio_payload_fingerprint="sha256:4fe5ca7f9cc36706367b269efff559c9a9ba54a46ee54e98815420cfdb0c1889"),
        calendar_source_feasibility="SOURCE_AVAILABLE_ADAPTER_MISSING",
        threat_model=before["threat_model"]))


def receipt():
    previous = before_receipt()  # Replays real admission attacks and 21 frozen isolated scenarios.
    return _seal(dict(version=VERSION, baseline=BASELINE, matrix_fingerprint=matrices()["fingerprint"],
        prior_receipt_fingerprint=previous["fingerprint"], legacy_receipt_unchanged=True,
        unsafe_ingress_accepted=previous["unsafe_self_declared_ingress_accepted"],
        admission_attacks=previous["admission_attacks"],
        named_source_blockers=[asdict(item) for item in SOURCE_GAPS],
        v1_replay_cases=previous["frozen_v1_replay_cases"], v1_replay_fingerprint=previous["frozen_v1_replay_fingerprint"],
        b08_before="CLOSED_FOR_SHADOW_COMPATIBILITY", b08_after="CLOSED_FOR_ACTIVATION_COMPATIBILITY",
        gate_source_data_readiness="NOT_READY", b09="STILL_BLOCKING_ACTIVATION", b14="STILL_BLOCKING_ACTIVATION",
        v1_active=True, v2_active=False, v2_shadow_only=True, ai_decision_authority=False,
        new_producers=0, writes=0, provider_acquisition_calls=0, orders=0,
        next_continuation=NEXT, generic_repair_4=False))


if __name__ == "__main__":
    print(json.dumps(dict(matrices=matrices(), receipt=receipt()), sort_keys=True, indent=2))
