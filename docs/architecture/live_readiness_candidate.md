# Brain Architecture v2.3-live-readiness — Candidate Only

This is a candidate hardening layer. **Brain Architecture v2.2-hardened remains
the approved architecture** until #035 receives full review and regression
approval.

Candidate flow:

`Sources → Provider Normalization & Reconciliation → Reliability/Fallback → Historical Integrity → Evidence Coverage & Validation → Market Regime / Extremes → Sector Intelligence → Cheap Universe Scan → Deep Candidate Research → Market Integrity → Setup Engine → Decision Score + Confidence + Calibration → Execution Feasibility → Six Hard Gates → Portfolio Factor Risk → Capital Rotation + Anti-Churn → Risk / Execution Simulation → Monitoring → Outcomes → Benchmark → Calibration / Ablation → Governance & Drift → Audit & Reproducibility → Human Validation / Deployment`

## Guardrails

- Reconciliation reports conflict, stale, incomplete, or unverifiable evidence;
  it does not average conflicting source facts.
- Coverage is separate from Decision Score and confidence. Insufficient coverage
  yields `RESEARCH_INCOMPLETE`, not a high-confidence action.
- Execution simulation and feasibility are analytical/paper evidence only.
  `SETUP_VALID_EXECUTION_REJECTED` is not a seventh score gate and creates no order.
- Calibration, redundancy, ablation, and regime-validation outputs are research
  observations for governance, never automatic weight/formula changes.
- Rotation uses existing configured superiority, friction, confirmations, and
  cooldown. The candidate hurdle adds no arbitrary constants; unavailable terms
  remain `NOT_CONFIGURED` / `RESEARCH_REQUIRED`.
- Emergency modes can freeze new entries, require review, disable rotation, or
  mark data degraded. They cannot liquidate, deploy, mutate a model, or trade.
- Event clusters represent underlying news events, retaining original timing;
  article replication cannot multiply confidence.
- LLM assistance is schema-bound and cannot own numerical truth, override gates,
  or best-guess malformed output.
- Stage 1 creates a deterministic shortlist only; Stage 2 deep analysis remains
  controlled and canonical. No opportunity is a valid `NO_TRADE`/cash outcome.

All records use existing append-only Core snapshot persistence when retained.
Public APIs remain distilled and expose neither diagnostic/gate/weight/threshold
internals nor redundancy/ablation research details.
